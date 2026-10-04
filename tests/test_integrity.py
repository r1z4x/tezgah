"""hooks/tezgah_integrity.py + the Stop/PostToolUse hooks: the integrity gate.

The pure detectors run in-process; the ledger and the two Claude hooks run in a
subprocess with a throwaway HOME so the real cache is never touched.
"""
import fcntl
import hashlib
import json
import os
import shutil
import sys
import tempfile
import threading
import time
import unittest
from unittest import mock

import support
from support import TempHome, run_json

sys.path.insert(0, os.path.join(support.REPO, "hooks"))
import tezgah_context as tc  # noqa: E402
import tezgah_gate as tg  # noqa: E402  (the write-tool name the gate captures a shell write under)
import tezgah_integrity as ti  # noqa: E402
import tezgah_snapshot as tz  # noqa: E402


class FailClass(unittest.TestCase):
    """The error text a host reports, classified for the loop guard's ceiling."""

    def test_error_text_maps_to_the_four_values(self):
        for text, want in (("Command timed out after 2m", "transient"),
                           ("connection reset by peer", "transient"),
                           ("bash: foo: command not found", "permanent"),
                           ("exit status 127", "permanent"),
                           ("HTTP 401 Unauthorized", "user"),
                           ("403 Forbidden", "user"),
                           ("authentication failed for 'origin'", "user"),
                           ("Error: invalid API key", "user"),
                           ("missing credentials for registry", "user"),
                           ("You are not logged in. Run gh auth login", "user"),
                           ("open x: permission denied", "permanent"),
                           ("something odd happened", "unknown"),
                           ("", None), (None, None)):
            self.assertEqual(ti.fail_class(text), want, text)

    def test_a_number_or_a_word_alone_does_not_make_a_credential_failure(self):
        # The user class is the one that tells the agent which repair is not
        # its own, so a text that merely carries a code or a credential-ish word
        # must not borrow it: a traceback's line number is not a 401, a lexer's
        # complaint is not an invalid key, and a missing file is neither. The
        # repair the class names - stop and ask the user - is wrong for all of
        # them, and it is worse than the plain permanent text it replaces.
        for text in ('Traceback (most recent call last):\n  File "big.py", line 401',
                     "SyntaxError: invalid token",
                     "ld: 403 undefined symbols",
                     "error: no such file or directory: out.txt",
                     "expected 401 items, got 12",
                     "pytest: assertion failed at test_x.py:403"):
            self.assertNotEqual(ti.fail_class(text), "user", text)


class CallIdentity(unittest.TestCase):
    """call_id: the same string in both writers.

    opencode's half of the ledger is a JS port, so an argument the two languages
    serialize differently forks one action into two ids and the loop guard never
    fires on that host."""

    def test_an_integral_float_is_canonicalised_as_js_writes_it(self):
        # JS has a single number type: JSON.stringify(1.0) is "1", and a value
        # that came through JSON.parse can never be turned back into "1.0"
        self.assertEqual(ti.call_id("Edit", {"a": 1.0}), ti.call_id("Edit", {"a": 1}))
        self.assertEqual(ti.call_id("Edit", {"a": [1.0, {"b": 2.0}]}),
                         ti.call_id("Edit", {"a": [1, {"b": 2}]}))

    def test_a_float_js_cannot_reproduce_keeps_its_own_form(self):
        # 1e30 is printed by JS as "1e+30" and by Python as an int, so coercing
        # it would fork the identity the other way
        self.assertNotEqual(ti.call_id("Edit", {"a": 1e30}),
                            ti.call_id("Edit", {"a": int(1e30)}))


class ShortcutCommand(unittest.TestCase):
    def test_no_verify_denied(self):
        for c in ("git commit -m x --no-verify", "git push --no-verify",
                  "git -c core.hooksPath=/dev/null commit --no-verify -m x"):
            self.assertIsNotNone(ti.shortcut_command(c), c)

    def test_the_short_and_abbreviated_hook_skips_are_denied(self):
        # audit SEC-03 / L-5: commit's `-n`, git's abbreviations of the long
        # option, and a neutered check or skip inside `bash -c` / `sh -c` passed
        for c in ("git commit -n -m x", "git commit -anm x",
                  "git commit --no-verif -m x", "git commit --no-ver -m x",
                  "git push --no-verif", "bash -c 'pytest || true'",
                  "bash -lc 'ruff check . ; true'",
                  'sh -c "git commit --no-verify -m x"',
                  "sh -c \"bash -c 'git commit -n -m x'\""):
            self.assertIsNotNone(ti.shortcut_command(c), c)
        # `-n` is push's --dry-run, a message or log count is not a flag, and
        # --no-verbose is a different option
        for c in ("git push -n origin main", 'git commit -m "-n"',
                  "git commit -m-n", "git log -n 3",
                  "git commit --no-verbose -m x", "bash -c 'pytest -q'"):
            self.assertIsNone(ti.shortcut_command(c), c)

    # The review's cases, shared with the opencode mirror's test.
    STUCK_AND_WRAPPED = (
        # F4: `-S`/`-u` take no separate word, so the `-n` after them is a flag
        "git commit -S -n -m x", "git commit -u -n -m x",
        # F10: bash options before `-c` no longer hide the script
        "bash -o pipefail -c 'pytest || true'", "bash --norc -c 'pytest || true'",
        "sh -e -c 'git commit -n -m x'", "bash --rcfile /x -c 'pytest || true'")
    LONG_VALUES = (
        # F7: a long option's separate value is a value, whatever it starts with
        'git commit --message "-no-op cleanup"', "git commit --file -n.txt",
        'git commit --author "-n <a@b>" -m x', "git commit -uno -m x",
        # N8: git takes an unambiguous prefix of a long option as that option
        'git commit --mess "-no-op"', 'git commit --me "-n"')

    def test_the_reviews_hook_skip_shapes_are_read_like_git_and_bash(self):
        for c in self.STUCK_AND_WRAPPED:
            self.assertIsNotNone(ti.shortcut_command(c), c)
        for c in self.LONG_VALUES:
            self.assertIsNone(ti.shortcut_command(c), c)

    def test_neutered_check_denied(self):
        for c in ("pytest || true", "npm test || true", "ruff check . ; true",
                  "cargo test || exit 0", "pytest tests/ || :"):
            self.assertIsNotNone(ti.shortcut_command(c), c)

    def test_skip_env_denied(self):
        for c in ("SKIP=flake8 git commit -m x",
                  "HUSKY_SKIP_HOOKS=1 git commit -m x",
                  "HUSKY=0 git commit -m x"):
            self.assertIsNotNone(ti.shortcut_command(c), c)

    def test_hooks_path_redirect_beside_a_commit_denied(self):
        for c in ("git -c core.hooksPath=/dev/null commit -m x",
                  "git -c core.hookspath=/tmp/none push",
                  "git config core.hooksPath /tmp/nohooks && git commit -m x",
                  "git config --local core.hooksPath x; git push origin main",
                  # a quoted value is still an assignment
                  'git config core.hooksPath "$D" && git commit -m x',
                  "git config core.hooksPath '' && git commit -m x",
                  # the same key through --config-env and the config env vars
                  "NOH=/tmp/x git --config-env=core.hooksPath=NOH commit",
                  "GIT_CONFIG_COUNT=1 GIT_CONFIG_KEY_0=core.hooksPath "
                  "GIT_CONFIG_VALUE_0=/tmp/x git commit",
                  "GIT_CONFIG_PARAMETERS=\"'core.hooksPath'='/x'\" git commit",
                  # a quoted key is still the key
                  "git -c 'core.hooksPath=/dev/null' push",
                  'git --config-env "core.hooksPath=NOH" commit',
                  "git config 'core.hooksPath' /dev/null; git commit -m x",
                  # a quoted word earlier on the line does not hide the real one
                  'git -c "user.name=config" -c core.hooksPath=/dev/null '
                  'commit -m "core.hooksPath now"',
                  'X="GIT_CONFIG_KEY_9=" GIT_CONFIG_KEY_0=core.hooksPath '
                  'GIT_CONFIG_VALUE_0=/x GIT_CONFIG_COUNT=1 git commit -m x',
                  # a continued line is one command
                  "git -c core.hooksPath=/x \\\n  commit -m x",
                  # a line shlex cannot read is still read, not dropped
                  "git -c core.hooksPath=/x commit -m $'it\\'s'",
                  # an unquoted backtick body is a command of its own
                  "echo `git -c core.hooksPath=/x commit -m x`",
                  # a vertical tab is not a line break
                  'git -c core.hooksPath=/x commit -m "a\x0bb"',
                  # legacy `name value`: the value `get` is still a value
                  "git config core.hooksPath get && git commit -m x",
                  # a redirection is not an argument and not a subcommand
                  "git 2>/dev/null -c core.hooksPath=/dev/null commit",
                  "git -c core.hooksPath=/dev/null >/tmp/log commit",
                  "git -c core.hooksPath=/dev/null &>/dev/null commit",
                  "git -c core.hooksPath=/dev/null 2>&1 commit",
                  "git -c core.hooksPath=/dev/null </dev/null push",
                  # bash starts a comment at a word, not mid-word
                  "x=a#b git -c core.hooksPath=/dev/null commit",
                  "[ $# -eq 0 ] && git -c core.hooksPath=/dev/null commit",
                  # ANSI-C and locale quoting around the key
                  "git -c $'core.hooksPath'=/dev/null commit",
                  'git -c $"core.hooksPath"=/dev/null commit',
                  # after `--` a lookalike option is a value
                  "git config core.hooksPath -- --unset && git commit"):
            self.assertIsNotNone(ti.shortcut_command(c), c)

    def test_hooks_path_without_a_commit_or_as_a_read_passes(self):
        # husky's own setup, a read of the value, an unset, and a message that
        # names the key are not bypasses
        for c in ("git config core.hooksPath .githooks",
                  "git config --get core.hooksPath && git commit -m x",
                  "git config --unset core.hooksPath && git commit -m x",
                  'git commit -m "gate: deny core.hooksPath redirects"',
                  # a hook install that names pre-push/commit-msg is no commit
                  "git config core.hooksPath .githooks && "
                  "chmod +x .githooks/commit-msg .githooks/pre-push",
                  "git config core.hooksPath x; echo commit",
                  # a read on its own line, and an env name inside a message
                  "git config core.hooksPath\ngit commit -m x",
                  'git commit -m "docs: GIT_CONFIG_PARAMETERS=core.hooksPath"',
                  # the key inside a message beside a path named config
                  'git commit config/hooks.sh -m "set core.hooksPath in setup"',
                  'git -C config commit -m "core.hooksPath x"',
                  # a heredoc body and a comment are data
                  "git commit -F - <<'MSG'\ngit -c core.hooksPath=/x commit\nMSG",
                  "git commit -m x # git -c core.hooksPath=/x commit",
                  # the subcommand form of a read, and backticks in a message
                  "git config get core.hooksPath && git commit -m x",
                  "git commit -m 'deny `git -c core.hooksPath=x commit`'",
                  # a read with a redirection or an option after it is a read
                  "git config core.hooksPath > /tmp/hp && git commit -m x",
                  "git config core.hooksPath 2>/dev/null && git commit -m x",
                  "git config core.hooksPath --type=path && git push",
                  # a line that merely mentions git is not git
                  "echo git -c core.hooksPath=/x commit",
                  "printf '%s' x=a#b && git commit -m y",
                  # a redirection on a plain commit is not the key
                  "git commit -m x > /tmp/log"):
            self.assertIsNone(ti.shortcut_command(c), c)

    def test_a_long_run_of_git_options_is_read_in_linear_time(self):
        # a pattern whose option alternatives overlapped read `--x` two ways
        # per token and hung the gate on a long line; the word reader must not
        start = time.monotonic()
        ti.shortcut_command("git " + "--x " * 3000 + "y")
        ti.shortcut_command("git " + "-c " * 40 + "x")
        self.assertLess(time.monotonic() - start, 2.0)

    def test_skip_env_needs_a_hook_runner(self):
        # SKIP=/HUSKY= only turn checks off inside a hook runner; a read that
        # merely mentions them must pass (the gate denied this before the guard)
        for c in ('grep -rn "SKIP=" .', "rg 'HUSKY_SKIP_HOOKS=' src/",
                  "python3 -c 'print(\"SKIP=\")'"):
            self.assertIsNone(ti.shortcut_command(c), c)

    def test_plain_commands_pass(self):
        for c in ("pytest -q", "npm test", "git commit -m 'fix: typo'",
                  "git status", "ruff check .", "make test"):
            self.assertIsNone(ti.shortcut_command(c), c)

    def test_neuter_without_a_check_passes(self):
        self.assertIsNone(ti.shortcut_command("ls || true"))
        self.assertIsNone(ti.shortcut_command("git log || true"))

    def test_no_verify_without_a_git_write_passes(self):
        self.assertIsNone(ti.shortcut_command("echo --no-verify"))

    def test_naming_no_verify_in_a_message_or_a_read_passes(self):
        # a commit message that describes the rule, and a read of the rule's
        # own code, are not bypasses; only the flag in command position is
        for c in ('git commit -m "gate: deny --no-verify bypasses"',
                  "grep -rn --no-verify hooks/",
                  "git commit -F - <<'MSG'\ngate denies --no-verify\nMSG",
                  'git commit -m "x" -m \'y --no-verify\'',
                  'gh pr create --body "ban --no-verify"'):
            self.assertIsNone(ti.shortcut_command(c), c)
        for c in ("git commit --no-verify -m x", "git push --no-verify"):
            self.assertIsNotNone(ti.shortcut_command(c), c)

    def test_an_unterminated_heredoc_stays_visible(self):
        # a bypass must not hide behind a missing terminator
        self.assertIsNotNone(
            ti.shortcut_command("git commit -F - <<'MSG'\n--no-verify\n"))

    # review R1: a `<<'X'` that bash does not read as a heredoc - quoted, in a
    # comment, or a here-string - must not blank the commands after it
    FAKE_HEREDOCS = ("echo \"<<'X'\"\ngit commit --no-verify -m x\nX",
                     "ls # <<'X'\ngit commit --no-verify -m x\nX",
                     "echo \"<<'X'\"\npytest || true\nX",
                     "grep x <<< 'X'\ngit commit --no-verify -m x\nX")

    def test_only_a_heredoc_bash_reads_hides_its_body(self):
        for c in self.FAKE_HEREDOCS:
            self.assertIsNotNone(ti.shortcut_command(c), c)
        # a real one still hides its body, and the body reader agrees
        self.assertIsNone(
            ti.shortcut_command("git commit -F - <<'MSG'\n--no-verify\nMSG"))
        self.assertEqual(ti.heredoc_bodies("echo \"<<'X'\"\nbody\nX"), [])
        self.assertEqual(ti.heredoc_bodies("cat > f <<'E'\na\nb\nE\n"), ["a\nb"])

    # review S1: `<<` inside arithmetic is a shift, never a heredoc, so the
    # command after it is read. Checked against bash: `echo $((1<<2))` prints 4
    # and the next line runs.
    ARITH_SHIFTS = ("echo $((1<<2))\ngit commit --no-verify -m x\n2",
                    "(( a = 1 <<b ))\ngit commit --no-verify -m x\nb",
                    "x=$(( (1+2) << 3 ))\ngit commit --no-verify -m x\n3")
    # review S2: a heredoc inside `$( )` inside double quotes is a real one, so
    # the default commit-message shape's body is message text, not commands
    QUOTED_SUBSTITUTION_MESSAGES = (
        "git commit -m \"$(cat <<'EOF'\nfix: gate\n\n"
        "git commit -n is now refused\nEOF\n)\"",
        "git commit -m \"$(cat <<'EOF'\nfix: gate\n\n"
        "pytest || true is refused\nEOF\n)\"")

    def test_heredocs_are_read_in_bash_contexts(self):
        for c in self.ARITH_SHIFTS:
            self.assertIsNotNone(ti.shortcut_command(c), c)
        for c in self.QUOTED_SUBSTITUTION_MESSAGES:
            self.assertIsNone(ti.shortcut_command(c), c)
        # `let x=1<<2` is a command word: bash reads a heredoc there, and the
        # line after it is its body
        self.assertEqual(ti.heredoc_bodies("let x=1<<2\nbody\n2"), ["body"])

    def test_a_newline_inside_quotes_does_not_start_a_heredoc_body(self):
        # consult review 2026-10-02: bash collects a heredoc body at a newline
        # token, so a newline inside a quoted argument after the operator is
        # text, and the commit on that line runs (measured with `bash -c`)
        for c in ('cat <<X "a\nb"; git commit --no-verify -m x\nbody\nX',
                  "cat <<X $((1\n+1)); git commit --no-verify -m x\nbody\nX",
                  # a newline inside a later `$( )` belongs to it (bash 3.2)
                  "cat <<X $(echo a\necho b); git commit --no-verify -m x\nbody\nX",
                  # a closed `$( )`'s heredoc never flushes in a later sibling
                  "echo $(cat <<X); echo $(true\ngit commit --no-verify -m x\nX\n)",
                  'echo "$(cat <<X)"; echo "$(true\ngit commit --no-verify -m x\nX\n)"'):
            self.assertIsNotNone(ti.shortcut_command(c), c)
        self.assertEqual(ti.heredoc_bodies('cat <<X "a\nb"; ls\nbody\nX'),
                         ["body"])


class BookkeepingCommand(unittest.TestCase):
    """_bookkeeping_command: which shell calls leave the tree a check judged as
    it was. A false True here excuses an unverified change (review F2, F6)."""

    def test_writes_and_runs_hidden_from_the_masked_text_are_not_bookkeeping(self):
        for c in ('echo "$(./scripts/regen.sh)"', "cat src//tpl.py > src/app.py",
                  "ls a#b; sed -i s/x/y/ f.py", "cat <(sed -i s/a/b/ f.py)",
                  "echo `./x.sh`", "git log > /tmp/log.txt"):
            self.assertFalse(ti._bookkeeping_command(c), c)

    def test_readers_that_write_or_run_are_not_bookkeeping(self):
        for c in ("git diff --output=src/app.py HEAD~1", "git log --output x",
                  "tree -o src/x", "tree -fo out.txt", "file -C -m x",
                  "rg --pre ./x.sh pat",
                  "GIT_EXTERNAL_DIFF=./x.sh git diff",
                  "env GIT_EXTERNAL_DIFF=./x.sh git diff",
                  "git -c diff.external=./x.sh diff", "git diff --ext-diff"):
            self.assertFalse(ti._bookkeeping_command(c), c)

    def test_a_quote_lost_in_a_comment_or_body_fails_closed(self):
        # review N1: an apostrophe in a `#` comment, a heredoc body or an
        # ANSI-C string threw the quote tracking off and hid a later `<(`
        for c in ("git status # it's fine\ncat <(./regen.sh)",
                  "ls # don't\ncat <(./regen.sh)",
                  "cat <<'true'\ndon't\ntrue\ncat <(./regen.sh)",
                  "cat <<EOF\n$(./regen.sh)\nEOF",
                  "echo $'it\\'s' > out.txt", "echo 'unbalanced"):
            self.assertFalse(ti._bookkeeping_command(c), c)
        for c in ("git status # it's fine", "echo $'it\\'s'",
                  "git commit -F - <<'MSG'\ndon't\nMSG"):
            self.assertTrue(ti._bookkeeping_command(c), c)

    def test_only_a_real_heredoc_hides_its_lines(self):
        # review R1: `<<'EOF'` in a quoted string, a comment or a here-string
        # was read as a heredoc, and every segment equal to its tag was dropped
        for c in ("rg -n \"<<'EOF'\" docs/\npython3 - <<'EOF'\n"
                  "open('a.py','w').write('x')\nEOF",
                  "echo \"<<'X'\"\n./regen.sh\nX",
                  "cat <<'make'\nx\nmake\nmake",
                  "cat <<'make'; make\nx\nmake",
                  "echo \"<<'true'\"\n./regen.sh\ntrue",
                  "ls # see <<'true'\n./regen.sh\ntrue",
                  "grep x <<< 'true'\n./regen.sh\ntrue",
                  "cat <<'A'\nx\n"):
            self.assertFalse(ti._bookkeeping_command(c), c)
        for c in ("git commit -F - <<'MSG'\nbody\nMSG",
                  "git commit -F - <<-\"MSG\"\n\tbody\n\tMSG\ngit status",
                  "grep x <<< 'y'", 'echo "<<\'X\'"'):
            self.assertTrue(ti._bookkeeping_command(c), c)

    def test_a_program_named_by_a_path_is_not_bookkeeping(self):
        # review N9: `./scripts/cat` is whatever that file is
        for c in ("./scripts/cat x", "./git status", "tools/echo hi"):
            self.assertFalse(ti._bookkeeping_command(c), c)

    def test_a_redacted_detail_is_not_bookkeeping(self):
        # review N3: the marker swallowed `;./regen.sh` glued to the value
        stored = ti._stored_text("echo token=x;./regen.sh")
        self.assertIn("[redacted:", stored)
        self.assertFalse(ti._bookkeeping_turn([{"kind": "run", "detail": stored}]))

    def test_plain_bookkeeping_still_is(self):
        for c in ('git commit -m "fix: parser"', "git status --short",
                  "git add -A && git commit -m 'a > b'", "git log -n 3 2>&1",
                  "git diff --stat >/dev/null", "ls -la src", "git -C sub status"):
            self.assertTrue(ti._bookkeeping_command(c), c)


class PipedCheck(unittest.TestCase):
    def test_a_check_piped_into_a_trimmer_is_refused_with_both_fixes(self):
        for c in ("pnpm test 2>&1 | tail -3",
                  "cd app && python3 -m unittest discover -s tests | grep FAIL",
                  "pytest -q |& head -20",
                  "ruff check . | wc -l",
                  "make test | tee out.log | sed -n '1,5p'",
                  "npm run lint | cut -c1-80"):
            reason = ti.piped_check(c)
            self.assertIsNotNone(reason, c)
            self.assertIn("pipefail", reason, c)
        # the fix names the check as it was typed, quoted arguments included
        self.assertIn('pytest -k "a b"', ti.piped_check('pytest -k "a b" | tail'))

    def test_what_is_not_a_trimmed_check_passes(self):
        for c in ("pytest -q > /tmp/x.log 2>&1",
                  "set -o pipefail; pytest -q 2>&1 | tail -3",
                  "set -euo pipefail && pnpm test | tail",
                  "git log --oneline | head -5",
                  "cat /tmp/x.log | tail -5",
                  "pytest -q; tail -5 /tmp/x.log",
                  "pytest -q | tee /tmp/x.log",
                  "git commit -m 'run pytest | tail before this'"):
            self.assertIsNone(ti.piped_check(c), c)

    def test_pipe_hides_status(self):
        self.assertTrue(ti.pipe_hides_status("pytest | tail"))
        self.assertTrue(ti.pipe_hides_status("set -o pipefail; pytest || true"))
        self.assertFalse(ti.pipe_hides_status("set -o pipefail; pytest | tail"))
        self.assertFalse(ti.pipe_hides_status("pytest -q"))


class ShortcutEdit(unittest.TestCase):
    TEST = {"file_path": "tests/test_x.py"}

    def edit(self, **payload):
        payload.setdefault("file_path", self.TEST["file_path"])
        return ti.shortcut_edit(payload)

    def test_adding_a_skip_denied(self):
        for new in ("@pytest.mark.skip(reason='flaky')\ndef test_x(): pass",
                    "it.skip('later', () => {})",
                    "t.Skip('flaky')",
                    "@unittest.skip('x')\nclass T: pass",
                    "test.only('a', () => {})"):
            self.assertIsNotNone(self.edit(new_string=new), new)

    def test_optional_dependency_guard_allowed(self):
        # skipUnless guards a missing optional dep; it is not a disable and
        # must not be caught (the gate denied it before the boundary fix).
        new = "@unittest." + "skipUnless(HAVE_NODE, 'node missing')\ndef t(): pass"
        self.assertIsNone(self.edit(new_string=new))

    def test_conditional_skip_reports_its_own_name(self):
        # a skipIf marker must be named as itself, not truncated to skip
        for name in ("@unittest." + "skipIf(x, 'y')",
                     "@pytest.mark." + "skipif(x, 'y')"):
            reason = self.edit(new_string=name + "\ndef t(): pass")
            self.assertIsNotNone(reason, name)
            self.assertIn(name.split("(")[0], reason)

    def test_rewriting_an_existing_skip_passes(self):
        old = "@pytest.mark.skip(reason='flaky')\ndef test_x(): pass"
        self.assertIsNone(self.edit(old_string=old, new_string=old))

    def test_one_more_skip_in_the_same_file_is_still_denied(self):
        # counting per marker, not per kind: a second skip is a second disable
        old = "@pytest.mark.skip(reason='a')\ndef t(): pass"
        new = old + "\n\n@pytest.mark.skip(reason='b')\ndef u(): pass"
        self.assertIsNotNone(self.edit(old_string=old, new_string=new))

    def test_a_skip_marker_outside_a_test_file_passes(self):
        # the rule's target is a disabled test; a probe script, a fixture or a
        # note that carries the marker disables nothing (the gate denied every
        # file before the path gate)
        for path in ("probe.py", "notes.md", "hooks/tezgah_integrity.py",
                     "web/app.js"):
            self.assertIsNone(self.edit(
                file_path=path,
                new_string="@pytest.mark.skip\ndef test_x(): pass"), path)

    def test_a_marker_inside_a_string_is_not_a_disable(self):
        # this repo's own tests are *about* the rule: the marker reaches the
        # gate as a string literal and as a comment, and neither runs a test
        self.assertIsNone(self.edit(
            new_string='CASES = ["@pytest.mark.skip", "it.skip"]'))
        self.assertIsNone(self.edit(
            new_string="# a test.skip here would hide the failure"))

    def test_plain_edit_passes(self):
        self.assertIsNone(self.edit(old_string="a = 1", new_string="a = 2"))

    def test_empty_edit_passes(self):
        self.assertIsNone(ti.shortcut_edit({}))

    def test_removing_an_assertion_is_not_caught(self):
        # documented ceiling: only an ADDED skip marker is mechanical; a
        # weakened assertion is not, so it is left to review by design.
        self.assertIsNone(self.edit(
            old_string="def t():\n    assert x == 1",
            new_string="def t():\n    pass"))


class LedgerTail(unittest.TestCase):
    """events(tail=...) and prior_calls read only the end of the ledger.

    The gate runs them on every gated call while the file grows with the
    session, so the whole file must stay unread; _path is patched so the real
    cache is never touched."""

    ROWS = 5000

    def setUp(self):
        self.dir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.dir, True)
        self.path = os.path.join(self.dir, "s.jsonl")
        self.addCleanup(setattr, ti, "_path", ti._path)
        ti._path = lambda session: self.path
        with open(self.path, "w") as fh:
            for i in range(self.ROWS):
                fh.write(json.dumps({"kind": "run", "ts": i, "id": "a%d" % i,
                                     "detail": "x" * 40}) + "\n")

    def append(self, row):
        with open(self.path, "a") as fh:
            fh.write(json.dumps(row) + "\n")

    def test_tail_returns_the_last_rows_oldest_first(self):
        rows = ti.events("s", tail=2)
        self.assertEqual([r["id"] for r in rows], ["a4998", "a4999"])

    def test_tail_never_reads_the_whole_file(self):
        read = []

        class Counting:
            def __init__(self, fh):
                self.fh, self.n = fh, 0

            def read(self, size=-1):
                data = self.fh.read(size)
                self.n += len(data)
                return data

            def __getattr__(self, name):
                return getattr(self.fh, name)

            def __enter__(self):
                return self

            def __exit__(self, *exc):
                return self.fh.__exit__(*exc)

        def counting(path, *args, **kwargs):
            fh = Counting(real_open(path, *args, **kwargs))
            read.append(fh)
            return fh

        real_open = open
        with mock.patch("builtins.open", counting):
            rows = ti.events("s", tail=2)
        self.assertEqual([r["id"] for r in rows], ["a4998", "a4999"])
        size = os.path.getsize(self.path)
        self.assertLess(sum(f.n for f in read), size // 10,
                        "the tail read pulled in the whole file")

    def test_prior_calls_count_matches_in_the_tail(self):
        self.append({"kind": "run", "id": "dup", "exit": 0})
        self.append({"kind": "run", "id": "dup", "exit": 1,
                     "fail_class": "transient"})
        self.append({"kind": "run", "id": "other", "exit": 1})
        # (turn attempts, session attempts, newest exit, its class): the two
        # repeat ceilings read the same rows, one per user turn and one per
        # session, so both counts come from this one scan
        self.assertEqual(ti.prior_calls("s", "dup", tail=3),
                         (2, 2, 1, "transient"))
        self.assertEqual(ti.prior_calls("s", "dup", tail=1), (0, 0, None, None))
        self.assertEqual(ti.prior_calls("s", "absent", tail=3),
                         (0, 0, None, None))

    def test_a_refusal_or_a_nudge_is_not_an_attempt(self):
        # the gate's own deny row and the nudge row carry the same id with no
        # outcome; counting them left the refusal newest, read as "no failure",
        # and disarmed the ceiling on every second repeat
        self.append({"kind": "run", "id": "dup", "exit": 1})
        self.append({"kind": "run", "id": "dup", "exit": 1})
        self.append({"kind": "deny", "id": "dup", "detail": "loop: denied"})
        self.append({"kind": "nudge", "id": "dup", "detail": "proj"})
        self.assertEqual(ti.prior_calls("s", "dup", tail=4), (2, 2, 1, None))

    def test_the_newest_turn_bounds_the_attempts(self):
        # reset per user turn: a failure the user then asked to retry is not this
        # turn's spent ceiling. The session count is deliberately NOT reset - it
        # is the ceiling above the guard, and a turn marker is not evidence the
        # agent changed the call.
        self.append({"kind": "run", "id": "dup", "exit": 1})
        self.append({"kind": "run", "id": "dup", "exit": 1})
        self.append({"kind": "turn", "detail": "abc"})
        self.append({"kind": "run", "id": "dup", "exit": 1})
        self.assertEqual(ti.prior_calls("s", "dup", tail=4), (1, 3, 1, None))
        self.append({"kind": "turn", "detail": "def"})
        self.assertEqual(ti.prior_calls("s", "dup", tail=5), (0, 3, None, None))


class TurnMarker(unittest.TestCase):
    """note_turn: one marker per submission.

    The marker is what resets the loop guard, so a duplicate would arm the reset
    twice and hide the failures the guard had just counted."""

    def setUp(self):
        self.dir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.dir, True)
        self.addCleanup(setattr, ti, "_path", ti._path)
        ti._path = lambda session: os.path.join(self.dir, "s.jsonl")

    def marks(self):
        return [r for r in ti.events("s") if r["kind"] == "turn"]

    def test_one_submission_writes_one_marker(self):
        ti.note_turn("s", "fix the tests", workspace="/repo")
        ti.note_turn("s", "fix the tests", workspace="/repo")
        self.assertEqual(len(self.marks()), 1)
        self.assertEqual(self.marks()[0]["workspace"], "/repo")

    def test_a_later_prompt_writes_its_own_marker(self):
        ti.note_turn("s", "fix the tests")
        ti.note("s", "run", "pytest -q")
        ti.note_turn("s", "fix the tests")
        self.assertEqual(len(self.marks()), 2)

    def test_the_marker_stores_no_prompt_text(self):
        ti.note_turn("s", "the secret the user typed")
        self.assertNotIn("secret", json.dumps(self.marks()))


class PartialStateReader(unittest.TestCase):
    """partial_state: what the newest turn did.

    The Stop rule's partial-failure branch reads this, so what is under test is
    the turn scoping and which check counts as the turn's newest. Rows go
    straight into a temp ledger; _path is patched so the real cache is untouched.
    """

    def setUp(self):
        self.dir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.dir, True)
        self.addCleanup(setattr, ti, "_path", ti._path)
        self.path = os.path.join(self.dir, "s.jsonl")
        ti._path = lambda session: self.path

    def seed(self, *rows):
        with open(self.path, "w") as fh:
            for row in rows:
                fh.write(json.dumps(row) + "\n")

    def test_a_failure_the_turn_never_resolved_is_not_verified(self):
        self.seed({"kind": "edit", "detail": "x.py"},
                  {"kind": "verify_ok", "detail": "pytest -q", "exit": 0,
                   "out_bytes": 9},
                  {"kind": "verify_fail", "detail": "ruff check . [exit!=0]",
                   "exit": 1},
                  {"kind": "verify", "detail": "mypy ."})
        self.assertEqual(ti.partial_state("s"),
                         {"edited": True, "failed": True, "verified": False})

    def test_a_pass_after_the_failure_verifies_it(self):
        self.seed({"kind": "edit", "detail": "x.py"},
                  {"kind": "verify_fail", "detail": "pytest -q", "exit": 1},
                  {"kind": "verify_ok", "detail": "pytest -q", "exit": 0,
                   "out_bytes": 9})
        self.assertEqual(ti.partial_state("s"),
                         {"edited": True, "failed": True, "verified": True})

    def test_a_green_run_before_the_failure_does_not_verify_it(self):
        # the failure has to be resolved, not merely preceded by a passing run
        self.seed({"kind": "verify_ok", "detail": "pytest -q", "exit": 0,
                   "out_bytes": 9},
                  {"kind": "verify_fail", "detail": "ruff check .", "exit": 1})
        self.assertEqual(ti.partial_state("s"),
                         {"edited": False, "failed": True, "verified": False})

    def test_the_newest_turn_is_the_only_turn_read(self):
        # a failure the user's next prompt moved past is not this turn's state
        self.seed({"kind": "edit", "detail": "x.py"},
                  {"kind": "verify_fail", "detail": "pytest -q", "exit": 1},
                  {"kind": "turn", "detail": "abc"},
                  {"kind": "verify_ok", "detail": "pytest -q", "exit": 0,
                   "out_bytes": 9})
        self.assertEqual(ti.partial_state("s"),
                         {"edited": False, "failed": False, "verified": True})

    def test_no_ledger_is_all_false(self):
        self.assertEqual(ti.partial_state("s"),
                         {"edited": False, "failed": False, "verified": False})


class StopReadBound(unittest.TestCase):
    """H5's bounded half at the Stop path: the read is the turn's, not the session's.

    The Stop handler runs once per turn while the ledger grows with the session,
    so what it parses has to be the current turn's rows - the property
    `turn_channel` was given (test_untrusted's `TurnRows`) and the one this path
    kept failing (E5b, measured: 2.638 ms of parse at 1112 rows against 0.185 ms
    for the turn's). Counted by the lines every `_parse` call is handed, the way
    `LedgerTail` counts the bytes a read pulls in, with `_path` patched so the
    real cache is never touched."""

    # Long enough that parsing it all dominates the count asserted below, short
    # enough that building it stays cheap.
    PREFIX = 4000

    def setUp(self):
        self.dir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.dir, True)
        self.addCleanup(setattr, ti, "_path", ti._path)
        ti._path = lambda session: os.path.join(self.dir, "%s.jsonl" % session)

    def seed(self, tail):
        """`PREFIX` rows, then this turn's marker, then the turn's own rows."""
        for i in range(self.PREFIX):
            ti.note("s", "run", "cmd %d" % i, id="a%d" % i, exit=0)
        ti.note("s", "turn", "abc")
        for kind, detail, extra in tail:
            ti.note("s", kind, detail, **extra)

    def parsed(self, fn):
        """(the answer, the lines `_parse` was handed while `fn` ran).

        The whole-ledger path hands `_parse` the open file itself
        (`events_path`) and the scoped one hands it a list, so both shapes are
        counted; a reader that stops parsing the session's rows stops appearing
        in the count at all."""
        given = []
        real = ti._parse

        def counting(lines):
            lines = lines if isinstance(lines, list) else list(lines)
            given.append(len(lines))
            return real(lines)

        with mock.patch.object(ti, "_parse", counting):
            out = fn()
        return out, sum(given)

    def test_stop_reason_reads_the_turn_and_not_the_whole_ledger(self):
        # one edit and no passing check: the turn is refused, which is also what
        # makes the count below a reading of the real path and not of a branch
        # that never got that far
        self.seed([("edit", "x.py", {})])
        reason, n = self.parsed(
            lambda: ti.stop_reason("Done. All tests pass.", "s"))
        self.assertIn("no check ran", reason)
        self.assertLess(n, self.PREFIX // 10,
                        "the Stop path parsed the whole ledger")

    def test_changed_files_reads_the_turn_and_not_the_whole_ledger(self):
        self.seed([("edit", "x.py", {"changed": True})])
        names, n = self.parsed(lambda: ti.changed_files("s"))
        self.assertEqual(names, {"x.py"})
        self.assertLess(n, self.PREFIX // 10,
                        "changed_files parsed the whole ledger")

    def test_the_same_reply_in_a_later_turn_is_still_a_new_claim(self):
        # The key's turn half is the ledger's own marker count. A turn-scoped
        # read holds no `turn` row itself - the read starts after it - so a count
        # taken from those rows would be 0 in every turn and this second reply
        # would be dropped as a duplicate, which is the under-count the key
        # exists to prevent.
        self.seed([("edit", "x.py", {})])
        ti.stop_reason("Done. All tests pass.", "s")
        ti.note("s", "turn", "def")
        ti.stop_reason("Done. All tests pass.", "s")
        self.assertEqual(len([r for r in ti.events("s")
                              if r.get("kind") == "claim"]), 2)


class ScratchEvidenceReader(unittest.TestCase):
    """scratch_evidence: the session whose whole evidence base is its own scratch
    work.

    The reminder line tezgah_context emits for a turn reads this, so what is
    under test is which paths count as scratch, which rows count as a passing
    check, and the answers that must stay None - including the one that matters:
    a check against a real path is evidence about the running system, so the
    scratch run beside it is not this session's evidence. Rows go straight into a
    temp ledger; _path is patched so the real cache is untouched.
    """

    def setUp(self):
        self.dir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.dir, True)
        self.addCleanup(setattr, ti, "_path", ti._path)
        self.path = os.path.join(self.dir, "s.jsonl")
        ti._path = lambda session: self.path

    def seed(self, *rows):
        with open(self.path, "w") as fh:
            for row in rows:
                fh.write(json.dumps(row) + "\n")

    def passed(self, detail):
        return {"kind": "verify_ok", "detail": detail, "exit": 0, "out_bytes": 9}

    def command(self, session="s"):
        """The command of the row the reader answers with, or None."""
        row = ti.scratch_evidence(session)
        return None if row is None else row.get("detail")

    def test_the_row_is_the_answer_not_just_its_command(self):
        self.seed(self.passed("python3 /tmp/x.py"))
        row = ti.scratch_evidence("s")
        self.assertEqual(row["kind"], "verify_ok")
        self.assertEqual(row["out_bytes"], 9)

    def test_a_temp_path_is_scratch(self):
        self.seed(self.passed("python3 /tmp/x.py"))
        self.assertEqual(self.command(), "python3 /tmp/x.py")

    def test_the_temp_paths_the_os_hands_out_are_scratch(self):
        for command in ("python3 /var/folders/xy/T/x.py",
                        'python3 "$TMPDIR/x.py"',
                        "python3 ${TMPDIR}/x.py"):
            self.seed(self.passed(command))
            self.assertEqual(self.command(), command, command)

    def test_an_output_redirect_to_temp_is_not_a_scratch_run(self):
        # the prescribed shape is `pytest > /tmp/check.log 2>&1`: the log's path
        # is not the path the check ran against, and reading it as scratch told
        # a session its green suite was a stand-in (measured 2026-10-01)
        for command in ("python3 -m unittest discover -s tests > /tmp/suite.log 2>&1",
                        "pytest -q >> /tmp/suite.log 2>&1",
                        "ruff check . > $TMPDIR/ruff.log 2>&1"):
            self.seed(self.passed(command))
            self.assertIsNone(self.command(), command)

    def test_a_scratch_target_beside_a_temp_log_is_still_scratch(self):
        self.seed(self.passed("python3 /tmp/probe.py > /tmp/probe.log 2>&1"))
        self.assertEqual(self.command(),
                         "python3 /tmp/probe.py > /tmp/probe.log 2>&1")

    def test_an_ampersand_redirect_is_stripped_too(self):
        # `&>`/`&>>` are redirects the first pattern missed (review 2026-10-01)
        for command in ("pytest -q &> /tmp/suite.log", "pytest -q &>> /tmp/suite.log",
                        "pytest -q >$TMPDIR/suite.log"):
            self.seed(self.passed(command))
            self.assertIsNone(self.command(), command)

    def test_a_word_that_names_a_check_is_not_a_check(self):
        # audit M-1: `echo pytest` was recorded as verify_ok and let a "done, all
        # tests pass" reply through; the check word has to be the command
        for command in ("echo pytest", "cat pytest.ini", 'grep -n "pytest" x',
                        "printf pytest", "man pytest"):
            self.assertIsNone(ti.verify_command(command), command)
        # the wrappers a real check arrives behind still count
        for command in ("sudo pytest -q", "env CI=1 pytest -q",
                        "cd /tmp && pytest -q", "time pytest -q"):
            self.assertIsNotNone(ti.verify_command(command), command)

    def test_the_gate_reads_a_large_command_in_linear_time(self):
        # audit H-3: the secret pattern rescanned from every start position, so
        # 100 KB took 174 s and the 5 s hook budget expired before the deny. The
        # gate's own half of the pair is timed in test_gate; this is the one
        # `redact()` uses on every ledger row.
        probe = "api_key" + "=" + "x"
        small = "echo " + "X" * 50000 + " " + probe
        big = "echo " + "X" * 100000 + " " + probe

        def timed(text):
            # the best of three: one sample under the sharded suite's load read
            # 3.1x for a doubling that measures 2.0x alone (2026-10-02)
            best = None
            for _ in range(3):
                start = time.monotonic()
                out = ti.redact(text)
                took = time.monotonic() - start
                best = took if best is None else min(best, took)
            return out, best

        small_out, small_s = timed(small)
        big_out, big_s = timed(big)
        self.assertIn("api_key=[redacted:", small_out or "")
        self.assertIn("api_key=[redacted:", big_out or "")
        # doubling the input must roughly double the time, not square it: the
        # quadratic form took 4.03 s at 16 KB and 174 s at 100 KB (audit H-3)
        self.assertLess(big_s, max(0.2, small_s * 3),
                        "50 KB %.3fs -> 100 KB %.3fs is not linear"
                        % (small_s, big_s))

    def test_the_impacted_runner_is_a_check(self):
        for command in ("python3 tests/impacted.py --run hooks/x.py",
                        "python3 tests/impacted.py --all"):
            self.assertIsNotNone(ti.verify_command(command), command)

    def test_a_stand_in_segment_is_scratch_and_a_longer_word_is_not(self):
        for command in ("python3 tools/fixtures/gen.py", "node fake/server.js",
                        "python3 stub.py", "python3 samples/big.py",
                        "bash demo.sh"):
            self.seed(self.passed(command))
            self.assertEqual(self.command(), command, command)
        # a word boundary, not a substring: the segment is the whole word
        for command in ("python3 democracy.py", "python3 -m pytest tests/"):
            self.seed(self.passed(command))
            self.assertIsNone(ti.scratch_evidence("s"), command)

    def test_the_newest_scratch_check_is_the_one_returned(self):
        self.seed(self.passed("python3 /tmp/first.py"),
                  self.passed("python3 /tmp/second.py"))
        self.assertEqual(self.command(), "python3 /tmp/second.py")

    def test_a_check_against_a_real_path_makes_the_answer_none(self):
        # the acceptance's third case, at the reader: one real check and the
        # scratch run beside it is not what this session's evidence is worth
        self.seed(self.passed("python3 /tmp/x.py"),
                  self.passed("python3 -m pytest tests/"))
        self.assertIsNone(ti.scratch_evidence("s"))

    def test_a_scratch_check_that_did_not_pass_is_not_evidence(self):
        # the reader folds with `passing_check`, not with the kind: an exit-1
        # scratch run and a piped one are checks nobody saw pass
        self.seed({"kind": "verify_fail", "detail": "python3 /tmp/x.py",
                   "exit": 1})
        self.assertIsNone(ti.scratch_evidence("s"))
        self.seed(self.passed("python3 /tmp/x.py | tail -1"))
        self.assertIsNone(ti.scratch_evidence("s"))

    def test_no_ledger_is_none(self):
        self.assertIsNone(ti.scratch_evidence("s"))


class WritersElsewhere(unittest.TestCase):
    """writers_elsewhere: which other sessions wrote this path recently.

    The cross-session rule's input, so what is under test is whose ledger counts,
    which paths match, and what the window excludes. cache_dir is patched so the
    real cache is never read."""

    def setUp(self):
        self.dir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.dir, True)
        self.addCleanup(setattr, ti, "cache_dir", ti.cache_dir)
        ti.cache_dir = lambda: self.dir
        self.evidence = os.path.join(self.dir, "evidence")
        os.makedirs(self.evidence)

    def write(self, session, rows, age=0):
        path = os.path.join(self.evidence, ti._slug(session) + ".jsonl")
        with open(path, "w") as fh:
            for row in rows:
                fh.write(json.dumps(row) + "\n")
        if age:
            os.utime(path, (time.time() - age, time.time() - age))

    def edit(self, path, age=0, workspace=None, cwd="/repo"):
        # the row the PostToolUse writer leaves: the host's own spelling in
        # `detail`, the file resolved against that session's cwd in `target`
        row = {"kind": "edit", "ts": int(time.time()) - age, "detail": path,
               "target": ti._abs_target(path, cwd)}
        if workspace:
            row["workspace"] = workspace
        return row

    def test_the_other_writers_are_newest_first(self):
        self.write("older", [self.edit("/repo/x.py", age=300)], age=300)
        self.write("newer", [self.edit("/repo/x.py", age=60)], age=60)
        self.write("mine", [self.edit("/repo/x.py")])
        self.assertEqual(ti.writers_elsewhere("/repo/x.py", "mine"),
                         [ti._slug("newer"), ti._slug("older")])

    def test_the_caller_is_never_in_the_list(self):
        self.write("mine", [self.edit("/repo/x.py")])
        self.assertEqual(ti.writers_elsewhere("/repo/x.py", "mine"), [])

    def test_a_write_outside_the_window_is_not_reported(self):
        self.write("old", [self.edit("/repo/x.py", age=20 * 60)], age=20 * 60)
        self.assertEqual(ti.writers_elsewhere("/repo/x.py", "mine"), [])

    def test_an_old_write_in_an_active_ledger_is_not_reported(self):
        # that file's mtime is recent because the session is still working, so
        # the row's own timestamp is what has to exclude the write
        self.write("busy", [self.edit("/repo/x.py", age=30 * 60),
                            self.edit("/repo/y.py")])
        self.assertEqual(ti.writers_elsewhere("/repo/x.py", "mine"), [])
        self.assertEqual(ti.writers_elsewhere("/repo/y.py", "mine"),
                         [ti._slug("busy")])

    def test_one_relative_spelling_in_two_repositories_is_two_files(self):
        # audit CHAT-03 / M-6: README.md written in repo A refused a write to
        # README.md in repo B for ten minutes, because the raw spelling was
        # compared. Each side is resolved against its own cwd now.
        self.write("a", [self.edit("README.md", cwd="/work/repo-a")])
        self.assertEqual(ti.writers_elsewhere("README.md", "mine",
                                              cwd="/work/repo-b"), [])
        self.assertEqual(ti.writers_elsewhere("README.md", "mine",
                                              cwd="/work/repo-a"),
                         [ti._slug("a")])
        # and the absolute spelling of the same file is the same file
        self.assertEqual(ti.writers_elsewhere("/work/repo-a/README.md", "mine"),
                         [ti._slug("a")])

    def test_a_row_without_a_target_names_no_file(self):
        # an older writer's row carries only the raw spelling, relative to a cwd
        # it never recorded: matching it would be the guess M-6 removed
        self.write("old", [{"kind": "edit", "ts": int(time.time()),
                            "detail": "/repo/x.py"}])
        self.assertEqual(ti.writers_elsewhere("/repo/x.py", "mine"), [])

    def test_a_damaged_foreign_ledger_costs_only_its_own_rows(self):
        # audit GAP-02 / M-7: one `[1,2]` row or one terminated non-JSON line in
        # any recently written ledger raised out of this reader, and the gate's
        # guard then let every write of every session through unchecked
        self.write("ok", [self.edit("/repo/x.py")])
        for name, junk in (("list", "[1, 2]\n"), ("torn", "{not json\n")):
            path = os.path.join(self.evidence, ti._slug(name) + ".jsonl")
            with open(path, "w") as fh:
                fh.write(json.dumps(self.edit("/repo/x.py")) + "\n" + junk)
        self.assertEqual(ti.writers_elsewhere("/repo/x.py", "mine"),
                         [ti._slug("ok")])

    def test_the_own_ledger_still_refuses_a_non_object_row(self):
        # `_parse`'s documented reading of a committed line that is not a row
        # holds for the session's own ledger: it raises, and the guard files
        # the crash row, rather than shrinking the evidence in silence
        with self.assertRaises(ValueError):
            ti._parse(['{"kind": "run"}\n', "[1, 2]\n"])
        self.assertEqual(ti._parse(['{"kind": "run"}\n', "[1, 2]"]),
                         [{"kind": "run"}])

    def test_another_file_is_not_reported(self):
        self.write("other", [self.edit("/repo/x.py")])
        self.assertEqual(ti.writers_elsewhere("/repo/y.py", "mine"), [])

    def test_an_unlistable_cache_and_an_empty_path_are_empty(self):
        shutil.rmtree(self.evidence)
        self.assertEqual(ti.writers_elsewhere("/repo/x.py", "mine"), [])
        self.assertEqual(ti.writers_elsewhere("", "mine"), [])


class CredentialRedaction(unittest.TestCase):
    """E4/X2: a credential the call carried never reaches the row.

    The row stores what the call carried - a command line, a path - so a token
    on a command line landed verbatim in a plain file in the cache. The scan is
    in the one append every writer goes through, and it records itself in the
    row: an evidence file altered without a mark would be a worse artifact than
    the leak it hides. `_path` is patched so the real cache is never touched."""

    def setUp(self):
        self.dir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.dir, True)
        self.addCleanup(setattr, ti, "_path", ti._path)
        ti._path = lambda session: os.path.join(self.dir, "s.jsonl")

    def test_the_named_and_bare_shapes_are_replaced_and_the_command_survives(self):
        cases = (
            ("export GITHUB_TOKEN=ghp_%s" % ("b" * 36),
             "ghp_" + "b" * 36, "GITHUB_TOKEN"),
            ("curl -H 'Authorization: Bearer sk-live-abcdefghijklmnop1234' https://x",
             "sk-live-abcdefghijklmnop1234", "curl"),
            ("aws s3 ls --access-key AKIAIOSFODNN7EXAMPLE",
             "AKIAIOSFODNN7EXAMPLE", "aws s3 ls"),
            ("mysql --password=hunter2swordfish -e select",
             "hunter2swordfish", "mysql"),
            ("slack --token xoxb-1234567890-abcdefghij post",
             "xoxb-1234567890-abcdefghij", "slack"),
        )
        for cmd, _secret, _keep in cases:
            ti.note("s", "run", cmd)
        rows = ti.events("s")
        self.assertEqual(len(rows), len(cases))
        for row, (cmd, secret, keep) in zip(rows, cases):
            with self.subTest(secret=secret):
                self.assertNotIn(secret, row["detail"])
                self.assertIn("[redacted:", row["detail"])
                self.assertIn(keep, row["detail"])

    def test_the_marker_names_what_was_removed(self):
        # the length is what a reader has to tell a one-character value from a
        # whole token: the row says a credential was there and how big it was
        key = "ghp_" + "c" * 36
        ti.note("s", "run", "export GITHUB_TOKEN=%s" % key)
        self.assertIn("[redacted:%d]" % len(key), ti.events("s")[-1]["detail"])

    def test_a_real_tool_row_is_redacted(self):
        # the writer a host reaches, not `note` directly: the detail comes from
        # the call's own command field
        ti.note_tool("s", "Bash",
                     {"command": "curl -H 'Authorization: Bearer ghp_%s' https://x"
                                 % ("d" * 36)}, failed=None)
        row = ti.events("s")[-1]
        self.assertEqual(row["kind"], "run")
        self.assertNotIn("ghp_", row["detail"])
        self.assertIn("[redacted:", row["detail"])

    def test_a_credential_past_the_stored_budget_is_still_replaced(self):
        # the scan runs over the whole command before the row's own cut: a
        # credential sitting in the last chars of the stored line is replaced
        # whole, never stored as the fragment a scan of the cut text would leave
        key = "ghp_" + "e" * 36
        ti.note("s", "run", "x" * 185 + " " + key)
        detail = ti.events("s")[-1]["detail"]
        self.assertNotIn(key, detail)
        self.assertIn("[redacted:", detail)
        self.assertLessEqual(len(detail), 200)

    def test_the_shapes_the_audit_found_stored_verbatim_are_replaced(self):
        # audit SEC-04 / L-6: a flag's next-word value, mysql's `-p`, HTTP Basic
        # (header and `-u`), URL userinfo and JSON keys all reached the row
        cases = (
            ("mysql --password hunter2swordfish -e x", "hunter2swordfish", "mysql"),
            ("tool --api-key ABCDEF1234 run", "ABCDEF1234", "--api-key"),
            ("mysql -u root -pS3cretPass db", "S3cretPass", "-u root"),
            ("mysql -u root -p S3cretPass db", "S3cretPass", "-p "),
            ("curl -H 'Authorization: Basic dXNlcjpwYXNz' x", "dXNlcjpwYXNz",
             "Authorization: "),
            ("curl -u admin:S3cretPass https://x", "S3cretPass", "admin:"),
            ("psql postgres://app:S3cretPass@db/x", "S3cretPass", "postgres://app:"),
            ('curl -d \'{"api_key":"abc123xyz","password": "pw987"}\' x',
             "abc123xyz", '"api_key":'),
            ('curl -d \'{"password": "pw987zz"}\' x', "pw987zz", "password"),
        )
        for cmd, secret, keep in cases:
            with self.subTest(cmd=cmd):
                out = ti.redact(cmd)
                self.assertNotIn(secret, out)
                self.assertIn("[redacted:", out)
                self.assertIn(keep, out)
        # what is not a credential stays: psql's `-p` is a port, `-P` mysql's,
        # `git add -u` has no user:pass, a flag followed by a flag has no value
        for cmd in ("psql -p 5432 db", "mysql -P 3306 -h h", "git add -u",
                    "tool --token-file x", "echo --password --other",
                    "curl https://host:8080/path"):
            self.assertEqual(ti.redact(cmd), cmd)

    def test_a_new_ledger_is_owner_only(self):
        # audit SEC-05 / L-6: the default umask left rows of commands and paths
        # world-readable (`-rw-r--r--`)
        path = os.path.join(self.dir, "evidence", "fresh.jsonl")
        ti._path = lambda session: path
        old = os.umask(0o022)
        self.addCleanup(os.umask, old)
        ti.note("s", "run", "ls")
        self.assertEqual(os.stat(path).st_mode & 0o777, 0o600)
        self.assertEqual(os.stat(os.path.dirname(path)).st_mode & 0o777, 0o700)


class RowContract(unittest.TestCase):
    """What every ledger row carries and what a shortened text says about itself.

    The row's own version is stamped by the writer, not passed by a caller, so it
    is not in LEDGER_FIELDS and a caller cannot set or drop it. The cut is the one
    boundary every shortened text routes through."""

    def row(self, kind="deny", **fields):
        path = os.path.join(tempfile.mkdtemp(), "led.jsonl")
        ti.note_path(path, kind, fields.pop("detail", "x"), **fields)
        with open(path, encoding="utf-8") as fh:
            return json.loads(fh.read().strip())

    def test_every_row_names_the_contract_that_wrote_it(self):
        self.assertEqual(self.row()["v"], ti.ROW_VERSION)

    def test_a_caller_cannot_set_or_drop_the_version(self):
        # `v` is the writer's, like `kind` and `ts`: a caller passing one is a
        # typo by the same rule that drops every other unknown field
        self.assertEqual(self.row(v=99)["v"], ti.ROW_VERSION)

    def test_a_child_session_s_row_keeps_its_parent_and_agent(self):
        # the route report joins a routed worker's ledger to its parent's route
        # through these two fields; the agent is the host's free text, redacted
        row = self.row("spawned", detail="", parent="p-1", agent="Scout token=abc")
        self.assertEqual((row["parent"], row["agent"]),
                         ("p-1", "Scout token=" + ti.MARKED % 3))

    def test_a_text_within_the_limit_is_returned_unchanged(self):
        self.assertEqual(ti.cut("a short rule", 80), "a short rule")

    def test_a_cut_text_names_what_it_dropped(self):
        # the marker rides on top of the limit rather than inside it: a marker a
        # second cut halved would say nothing, which is `budgeted`'s rule too
        out = ti.cut("z" * 100, 80)
        self.assertTrue(out.startswith("z" * 80))
        self.assertTrue(out.endswith("...(+20 chars)"), out)


class PostWriteState(unittest.TestCase):
    """G4: the write's after-state, the half the ledger was missing.

    The gate's `capture` records the pre-state in a `snapshot` row; `note_tool`
    records the target's hash once the host returned, and whether the two
    differ. Without the second half nothing could tell a write that landed from
    one the host accepted and did nothing with."""

    def setUp(self):
        self.dir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.dir, True)
        self.addCleanup(setattr, ti, "_path", ti._path)
        ti._path = lambda session: os.path.join(self.dir, "s.jsonl")
        self.target = os.path.join(self.dir, "x.py")
        with open(self.target, "w") as fh:
            fh.write("before\n")

    def rows(self):
        return ti.events("s")

    def pre_hash(self):
        tz.capture("Edit", {"file_path": self.target}, self.dir, "s")
        return [r for r in self.rows() if r.get("kind") == "snapshot"][-1]["hash"]

    def test_the_after_hash_is_recorded_and_differs_from_the_pre_hash(self):
        pre = self.pre_hash()
        with open(self.target, "w") as fh:
            fh.write("after\n")
        ti.note_tool("s", "Edit", {"file_path": self.target}, failed=False)
        row = self.rows()[-1]
        self.assertEqual(row["kind"], "edit")
        self.assertNotEqual(row["hash"], pre)
        self.assertTrue(row["changed"])
        self.assertEqual(ti.changed_files("s"), {self.target})

    def test_a_write_that_changed_nothing_is_recorded_as_unchanged(self):
        # a host-reported success over a file nobody touched: before this the row
        # was indistinguishable from a write that landed
        pre = self.pre_hash()
        ti.note_tool("s", "Edit", {"file_path": self.target}, failed=False)
        row = self.rows()[-1]
        self.assertEqual(row["hash"], pre)
        self.assertFalse(row["changed"])
        self.assertEqual(ti.changed_files("s"), set())

    def test_no_pre_state_leaves_the_change_unstated(self):
        # a new file has no pre-image: the after-hash is recorded and `changed`
        # is not guessed from the absence of a capture
        new = os.path.join(self.dir, "new.py")
        with open(new, "w") as fh:
            fh.write("x\n")
        ti.note_tool("s", "Write", {"file_path": new}, failed=False)
        row = self.rows()[-1]
        self.assertEqual(row["kind"], "edit")
        self.assertIn("hash", row)
        self.assertNotIn("changed", row)

    def test_a_target_that_is_not_readable_records_nothing_extra(self):
        ti.note_tool("s", "Edit", {"file_path": os.path.join(self.dir, "gone.py")},
                     failed=False)
        row = self.rows()[-1]
        self.assertNotIn("hash", row)
        self.assertNotIn("changed", row)


class WriteRowPath(unittest.TestCase):
    """006: a write row names the file the call wrote, in every dialect the gate
    already understands.

    The row's `detail` and the gate's own path reader are two readings of one
    rule - which paths does this call write - and they had drifted: the builder
    read `file_path`/`filePath` alone, so an omp `path`, a NotebookEdit's
    `notebook_path` and an `apply_patch` body recorded an empty detail, and
    `changed_files()` folded that empty string into its set."""

    def setUp(self):
        self.dir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.dir, True)
        self.addCleanup(setattr, ti, "_path", ti._path)
        ti._path = lambda session: os.path.join(self.dir, "s.jsonl")

    def path(self, name):
        return os.path.join(self.dir, name)

    def written(self, tool, inp, path):
        """One write the gate saw change `path`: the pre-state captured, then the
        host's result. Returns the row the writer appended."""
        with open(path, "w") as fh:
            fh.write("before\n")
        tz.capture(tool, {"file_path": path}, self.dir, "s")
        with open(path, "w") as fh:
            fh.write("after\n")
        ti.note_tool("s", tool, inp, failed=False, cwd=self.dir)
        return ti.events("s")[-1]

    def test_a_relative_write_records_its_absolute_real_target(self):
        # audit CHAT-03 / M-6: the race guard compares this field, so the row
        # names the file itself, not the host's spelling relative to a cwd the
        # row does not keep
        repo = os.path.join(self.dir, "repo")
        os.makedirs(repo)
        ti.note_tool("s", "Write", {"file_path": "README.md"}, failed=False,
                     cwd=repo)
        row = ti.events("s")[-1]
        self.assertEqual(row["detail"], "README.md")
        self.assertEqual(row["target"],
                         os.path.join(os.path.realpath(repo), "README.md"))

    def test_every_dialect_records_the_path_the_call_wrote(self):
        # One fixture per dialect: the four spellings a host puts a write's
        # target under, then the one whose paths live in the patch body.
        for tool, key in (("Edit", "file_path"), ("Edit", "filePath"),
                          ("edit", "path"), ("NotebookEdit", "notebook_path")):
            target = self.path(key + ".py")
            with self.subTest(dialect=key):
                row = self.written(tool, {key: target}, target)
                self.assertEqual(row["kind"], "edit", key)
                self.assertEqual(row["detail"], target, key)
        target = self.path("patched.py")
        row = self.written(
            "apply_patch",
            {"patch": "*** Begin Patch\n*** Update File: %s\n@@\n-a\n+b\n"
                      "*** End Patch" % target}, target)
        self.assertEqual(row["kind"], "edit")
        self.assertEqual(row["detail"], target)

    def test_the_row_and_the_gates_reader_cannot_drift(self):
        # The pair, not each side: a file a write row names is a file the gate's
        # own reader - the one the path, race and snapshot rules run on - also
        # answers, because a row is the only trace a reader has of the write.
        for inp in ({"file_path": "a.py"}, {"filePath": "b.py"},
                    {"path": "c.py"}, {"notebook_path": "nb.ipynb"},
                    {"patch": "*** Begin Patch\n*** Update File: p.py\n@@\n"
                              "*** Update File: q.py\n@@\n*** End Patch"}):
            with self.subTest(inp=inp):
                ti.note_tool("s", "Edit", inp, failed=False, cwd=self.dir)
                self.assertEqual(ti.events("s")[-1]["detail"],
                                 tg.write_paths(inp)[0])

    def test_changed_files_returns_the_real_set_for_two_writes(self):
        # Two files, two dialects, one session - which is the whole point of the
        # set: the stale-evidence refusal names it and any rule scoped to a
        # surface folds it.
        first, second = self.path("a.py"), self.path("b.py")
        self.written("Edit", {"file_path": first}, first)
        self.written("Edit", {"path": second}, second)      # omp's edit dialect
        self.assertEqual(ti.changed_files("s"), {first, second})


class ChangedFilesNotice(unittest.TestCase):
    """I4: the files a turn changed, on the Stop surface that can carry text
    without blocking the turn (`changed_files_notice`, which
    hosts/codex/hook.py puts on `systemMessage`).

    The reader is `changed_files`, so what is named is what was SEEN to change -
    a write the ledger recorded as unchanged is not a file to roll back."""

    def setUp(self):
        self.dir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.dir, True)
        self.addCleanup(setattr, ti, "_path", ti._path)
        ti._path = lambda session: os.path.join(self.dir, "s.jsonl")

    def edit(self, name, changed=True):
        path = os.path.join(self.dir, name)
        ti.note("s", "edit", path, changed=changed or None, id=name)
        return path

    def test_changed_files_notice_names_the_turn_s_writes_on_one_line(self):
        ti.note("s", "turn", "t1")
        self.edit("b.py")
        self.edit("a.py")
        self.edit("untouched.py", changed=False)
        self.assertEqual(ti.changed_files_notice("s", self.dir),
                         "files this turn changed: a.py, b.py")

    def test_changed_files_notice_is_absent_when_nothing_changed(self):
        ti.note("s", "turn", "t1")
        self.edit("a.py", changed=False)
        self.assertEqual(ti.changed_files_notice("s", self.dir), "")

    def test_changed_files_notice_caps_the_line_and_counts_the_rest(self):
        ti.note("s", "turn", "t1")
        for i in range(ti.CHANGED_NOTICE_MAX + 2):
            self.edit("f%02d.py" % i)
        self.assertEqual(
            ti.changed_files_notice("s", self.dir),
            "files this turn changed: %s (+2 more)"
            % ", ".join("f%02d.py" % i for i in range(ti.CHANGED_NOTICE_MAX)))

    def test_changed_files_notice_keeps_a_name_outside_the_root_whole(self):
        # a write outside the tree the notice is read in has no relative form
        # that means anything there, so it is named as the ledger has it
        ti.note("s", "turn", "t1")
        path = self.edit("a.py")
        out = ti.changed_files_notice("s", os.path.join(self.dir, "elsewhere"))
        self.assertIn(path, out)


class StaleEvidence(unittest.TestCase):
    """P1: a passing check licenses a claim only when it is newer than the newest
    write the gate saw change the tree.

    The hole was measured on the real rule before it landed
    (an internal research experiment on the stop rule):
    `edit -> verify_ok -> edit` claimed done, and an earlier turn's green run
    licensed a later turn's claim."""

    def setUp(self):
        self.dir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.dir, True)
        self.addCleanup(setattr, ti, "_path", ti._path)
        ti._path = lambda session: os.path.join(self.dir, "s.jsonl")
        self.target = os.path.join(self.dir, "x.py")

    def edit(self, text):
        """One write the gate saw change the file: pre-state captured, after-state
        recorded by the writing host."""
        tz.capture("Edit", {"file_path": self.target}, self.dir, "s")
        with open(self.target, "w") as fh:
            fh.write(text)
        ti.note_tool("s", "Edit", {"file_path": self.target}, failed=False)
        return ti.events("s")[-1]

    def check(self):
        ti.note_tool("s", "Bash", {"command": "pytest -q"}, failed=False,
                     out_bytes=42)

    def test_a_write_after_the_check_makes_the_check_stale(self):
        self.edit("v1\n")
        self.check()
        self.edit("v2\n")
        reason = ti.stop_reason("Done. All tests pass.", "s")
        self.assertIn("Stale evidence", reason)
        self.assertIn(os.path.basename(self.target), reason)
        self.assertEqual([r["detail"] for r in ti.events("s")
                          if r["kind"] == "claim"], ["blocked: stale evidence"])

    def test_a_check_after_the_last_write_still_licenses_the_claim(self):
        self.edit("v1\n")
        self.check()
        self.assertIsNone(ti.stop_reason("Done. All tests pass.", "s"))

    def test_a_write_that_changed_nothing_does_not_stale_the_check(self):
        self.edit("v1\n")
        self.check()
        # the host accepted a write that touched nothing: same bytes, so the row
        # carries `changed: false` and the tree the check saw is still the tree
        tz.capture("Edit", {"file_path": self.target}, self.dir, "s")
        ti.note_tool("s", "Edit", {"file_path": self.target}, failed=False)
        self.assertFalse(ti.events("s")[-1]["changed"])
        self.assertIsNone(ti.stop_reason("Done. All tests pass.", "s"))

    def test_a_new_file_after_the_check_makes_the_check_stale(self):
        # a file that did not exist has no pre-state, so its row carries a hash
        # and no `changed`: it is still a change to the tree
        self.edit("v1\n")
        self.check()
        new = os.path.join(self.dir, "new.py")
        with open(new, "w") as fh:
            fh.write("x\n")
        ti.note_tool("s", "Write", {"file_path": new}, failed=False)
        reason = ti.stop_reason("Done. All tests pass.", "s")
        self.assertIn("Stale evidence", reason)
        self.assertIn(os.path.basename(new), reason)

    def test_a_write_outside_the_workspace_is_not_a_change_to_the_tree(self):
        # The fold asks one question - is the newest check newer than the newest
        # write to the tree this reply is about - and a scratch file outside the
        # workspace cannot change that tree: a commit message in /tmp, a harness
        # log, a report written somewhere else. Reading one as a change refused an
        # honest turn: on 2026-09-19 the reply that reported a green suite was
        # blocked because its commit message had been written to /tmp after it.
        # The neighbours above are the control on the other side (a write inside
        # the workspace, and a new file in it, both still stale the check).
        root = os.path.join(self.dir, "root")
        os.makedirs(root, exist_ok=True)
        outside = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, outside, True)
        old = os.environ.get("TEZGAH_ROOTS")
        os.environ["TEZGAH_ROOTS"] = root
        self.addCleanup(self._restore_roots, old)
        self.check()
        scratch = os.path.join(outside, "commit-msg.txt")
        with open(scratch, "w") as fh:
            fh.write("msg\n")
        ti.note_tool("s", "Write", {"file_path": scratch}, failed=False, cwd=root)
        row = ti.events("s")[-1]
        self.assertNotIn("hash", row, row)
        self.assertFalse(ti._change_row(row))
        self.assertIsNone(ti.stop_reason("Done. All tests pass.", "s"))

    def _restore_roots(self, old):
        if old is None:
            os.environ.pop("TEZGAH_ROOTS", None)
        else:
            os.environ["TEZGAH_ROOTS"] = old

    # ---- the shell route: the same write reached through a redirect --------
    # Measured on 2026-09-19 (`E3-late-note`): the rule fired on a session that
    # wrote with the write tools, and the same append through a heredoc would have
    # been invisible, because `_changed_write` counted `edit` rows only and a
    # shell write records `run`. The two halves of that write are the gate's
    # capture of the file the command redirects into (its call site is pinned in
    # tests/test_gate.py) and `_post_write` reading the same target back.
    def shell(self, command, text=None):
        """One shell write to `self.target`: the pre-state the gate keeps, the
        command's effect, and the after-state the host's post hook records."""
        tz.capture(tg.SHELL_AS_WRITE, {"file_path": self.target}, self.dir, "s")
        if text is not None:
            with open(self.target, "w") as fh:
                fh.write(text)
        ti.note_tool("s", "Bash", {"command": command}, failed=False)
        return ti.events("s")[-1]

    def append(self, text=None):
        """The measured shape: `cat >> file <<'EOF'` writing `text`."""
        return self.shell("cat >> %s <<'EOF'\n%s\nEOF" % (self.target, text or ""),
                          text)

    def test_a_shell_write_after_the_check_makes_the_check_stale(self):
        self.edit("v1\n")
        self.check()
        row = self.append("v2\n")
        reason = ti.stop_reason("Done. All tests pass.", "s")
        self.assertIn("Stale evidence", reason)
        self.assertEqual(row["kind"], "run")
        self.assertIs(row["changed"], True)

    def test_a_shell_write_that_changed_nothing_does_not_stale_the_check(self):
        # the control the honest mechanism buys: the file's bytes are the whole
        # question, so a redirect that wrote what was already there is not a
        # change - had the row been marked changed from the command's shape, every
        # redirect would stale every check
        with open(self.target, "w") as fh:
            fh.write("v1\n")
        self.check()
        row = self.append(None)
        self.assertEqual(row["kind"], "run")
        self.assertIs(row["changed"], False)
        self.assertIsNone(ti.stop_reason("Done. All tests pass.", "s"))

    def test_a_check_after_the_last_shell_write_still_licenses_the_claim(self):
        with open(self.target, "w") as fh:
            fh.write("v1\n")
        self.append("v2\n")
        self.check()
        self.assertIsNone(ti.stop_reason("Done. All tests pass.", "s"))

    def test_a_shell_command_that_writes_no_file_is_not_a_change(self):
        # the shape test is the gate's SHELL_WRITE on the masked text: a quoted
        # `>` is not a redirect and `> /dev/null` is not a file, so the row carries
        # no after-state and the check is not staled by either
        self.check()
        for command in ("echo 'x > notes.md'",
                        "pytest -q > /dev/null",
                        "ls -la"):
            ti.note_tool("s", "Bash", {"command": command}, failed=False)
            self.assertNotIn("hash", ti.events("s")[-1])
        self.assertIsNone(ti.stop_reason("Done. All tests pass.", "s"))

    def test_a_check_that_writes_its_own_log_is_not_the_change(self):
        # The control on the other side of the cut (`_change_row`): a `verify*` row
        # is never read as a change, so a check that redirects its own output does
        # not stale itself. Were it counted, `_last_pass` and `_last_change` would
        # land on this one row and the turn that ran the check would be refused.
        with open(self.target, "w") as fh:
            fh.write("v1\n")
        tz.capture(tg.SHELL_AS_WRITE, {"file_path": self.target}, self.dir, "s")
        ti.note_tool("s", "Bash", {"command": "pytest -q > %s" % self.target},
                     failed=False, out_bytes=42)
        row = ti.events("s")[-1]
        self.assertEqual(row["kind"], "verify_ok")
        self.assertNotIn("hash", row)
        self.assertIsNone(ti.stop_reason("Done. All tests pass.", "s"))

    def test_a_turn_that_changed_nothing_is_still_never_refused(self):
        # the floor, unmoved by the shell half: nothing written, nothing run, and
        # a claim - there is no evidence to point at, so nothing refuses
        self.assertIsNone(ti.stop_reason("Done. All tests pass.", "s"))


class UiEvidence(unittest.TestCase):
    """A unit run never sees the screen, so a turn that changed a UI source and
    claims done owes one of the two things that do: a check that renders (a
    browser/e2e/visual run) or a read of the rendered screen. The gap was
    measured on this repository's own rule list - all thirteen gate rules are
    about code - and in the check vocabulary, which held no browser or visual
    command at all."""

    def setUp(self):
        self.dir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.dir, True)
        self.addCleanup(setattr, ti, "_path", ti._path)
        ti._path = lambda session: os.path.join(self.dir, "s.jsonl")
        self.target = os.path.join(self.dir, "admin", "components",
                                   "Button.tsx")
        # a screen the rule does not ask for a design check over: a component
        # owes the contract, the page it sits on owes the screen read
        self.screen = os.path.join(self.dir, "admin", "pages", "users.tsx")
        os.makedirs(os.path.dirname(self.target), exist_ok=True)
        os.makedirs(os.path.dirname(self.screen), exist_ok=True)

    def edit(self, path=None):
        """One write the gate saw change a UI source."""
        path = path or self.target
        tz.capture("Edit", {"file_path": path}, self.dir, "s")
        with open(path, "w") as fh:
            fh.write("export const Button = () => null\n")
        ti.note_tool("s", "Edit", {"file_path": path}, failed=False)
        return ti.events("s")[-1]

    def check(self, command, out_bytes=42):
        ti.note_tool("s", "Bash", {"command": command}, failed=False,
                     out_bytes=out_bytes)

    def detail(self):
        return [r["detail"] for r in ti.events("s") if r["kind"] == "claim"]

    def test_a_green_unit_run_does_not_license_a_ui_change(self):
        self.edit()
        self.check("pytest -q")
        reason = ti.stop_reason("Done. All tests pass.", "s")
        self.assertIn("UI evidence", reason)
        self.assertEqual(self.detail(), ["blocked: no ui_ok"])

    def test_a_browser_check_after_the_write_licenses_the_claim(self):
        # a page, not a component: a component owes `tezgah-design check` on top
        # of this (DesignContractEvidence below)
        self.edit(self.screen)
        self.check("npx playwright test")
        self.assertIsNone(ti.stop_reason("Done. All tests pass.", "s"))

    def test_a_read_of_the_screen_after_the_write_licenses_the_claim(self):
        self.edit(self.screen)
        ti.note_tool("s", "mcp__playwright__browser_take_screenshot", {},
                     failed=False)
        self.assertIsNone(ti.stop_reason("Done. All tests pass.", "s"))

    def test_an_mcp_row_that_carries_a_channel_licenses_the_claim(self):
        # omp names an MCP tool `mcp__<server>_<tool>` and records the call as
        # `external` with the channel its result came through, so a screen read
        # there is only visible if that row still knows which tool it was
        self.edit(self.screen)
        ti.note_tool("s", "mcp__playwright_browser_take_screenshot", {},
                     failed=False, source="mcp")
        row = ti.events("s")[-1]
        self.assertEqual(row["kind"], "external", row)
        self.assertIsNone(ti.stop_reason("Done. All tests pass.", "s"))

    def test_a_failed_screen_read_is_not_the_proof(self):
        # the reader keyed on the row's shape alone, so a screenshot call whose
        # result never arrived (the host reported the failure) was proof of a
        # screen nobody saw - `passing_check` refuses the same row in the check
        # family, and this is the read family's half of that
        self.edit(self.screen)
        ti.note_tool("s", "mcp__playwright__browser_take_screenshot", {},
                     failed=True)
        self.assertIn("UI evidence", ti.stop_reason("Done. All tests pass.", "s"))

    def test_a_failed_mcp_channel_row_is_not_the_proof_either(self):
        self.edit(self.screen)
        ti.note_tool("s", "mcp__playwright_browser_take_screenshot", {},
                     failed=True, source="mcp")
        row = ti.events("s")[-1]
        self.assertEqual(row["kind"], "external", row)
        self.assertTrue(row.get("fail_class") or row.get("exit"),
                        "the row has to carry the failure for this to test it")
        self.assertIn("UI evidence", ti.stop_reason("Done. All tests pass.", "s"))

    def test_a_long_shell_command_hides_its_redirect_from_the_ui_reader(self):
        # `note_path` cuts a row's `detail` to DETAIL_MAX and the shell half of
        # the write reader parses that detail, so a redirect past the cut is not
        # read while `_change_row` still counts the row as a change - the ceiling
        # `_ui_write` names. Pinned so the disagreement cannot widen unnoticed.
        tail = "> src/App.tsx"
        command = "echo %s %s" % ("x" * 210, tail)
        self.assertGreater(len(command), ti.DETAIL_MAX)
        ti.note_path(ti._path("s"), "run", command, changed=True)
        row = ti.events("s")[-1]
        self.assertLessEqual(len(row["detail"]), ti.DETAIL_MAX)
        self.assertNotIn(tail, row["detail"])
        self.assertTrue(ti._change_row(row))
        self.assertIsNone(ti._ui_write(row))

    def test_a_row_that_merely_names_an_mcp_tool_is_not_a_screen_read(self):
        # the readers matched the raw detail of ANY row, so a search whose
        # *pattern* is the tool's name was admissible screen proof
        self.edit(self.screen)
        self.run_cmd("rg -n browser_snapshot docs/")
        self.assertIn("UI evidence", ti.stop_reason("Done. All tests pass.", "s"))

    def test_a_browser_check_before_the_write_is_stale_like_any_other(self):
        self.check("npx playwright test")
        self.edit()
        self.check("pytest -q")
        reason = ti.stop_reason("Done. All tests pass.", "s")
        self.assertIn("UI evidence", reason)

    def test_a_native_or_template_screen_is_a_ui_source_too(self):
        # the rule read web extensions only, so a SwiftUI view or a Rails
        # template could close on a unit run while a `.tsx` could not
        for name in ("ProfileView.swift", "MembershipView.kt",
                     "users/index.html.erb", "Dashboard.qml"):
            path = os.path.join(self.dir, name)
            os.makedirs(os.path.dirname(path), exist_ok=True)
            self.edit(path)
            self.check("pytest -q")
            self.assertIn("UI evidence",
                          ti.stop_reason("Done. All tests pass.", "s"))

    def test_a_build_manifest_is_not_a_ui_source(self):
        # the control: `.xml` spells both an Android layout and a build file, so
        # it stays out of the list and a manifest turn keeps the unit-run rule
        path = os.path.join(self.dir, "app", "AndroidManifest.xml")
        os.makedirs(os.path.dirname(path), exist_ok=True)
        self.edit(path)
        self.check("pytest -q")
        self.assertIsNone(ti.stop_reason("Done. All tests pass.", "s"))

    def test_a_grep_that_names_a_rendering_check_is_not_a_screen_read(self):
        # the same reader, the other tool family: `rg -n playwright docs/` is a
        # passing check to `VERIFY` (the bare name is in the check vocabulary),
        # and the reader then took the mention for a screen that was seen
        self.edit(self.screen)
        self.run_cmd("rg -n playwright docs/")
        self.assertIn("UI evidence", ti.stop_reason("Done. All tests pass.", "s"))

    def test_a_grep_whose_pattern_is_the_design_checker_is_not_the_floor(self):
        self.edit(self.target)
        ti.note_tool("s", "mcp__playwright__browser_take_screenshot", {},
                     failed=False)
        self.run_cmd("rg -n tezgah-design check docs/")
        self.assertIn("tezgah-design check",
                      ti.stop_reason("Done. All tests pass.", "s"))

    def test_an_axe_core_and_a_reg_suit_run_are_checks_like_the_rest(self):
        # `UI_CHECK` named these two while `VERIFY` did not, so a run of either
        # recorded as a plain `run` and could never be the proof the regex
        # offered - the comment above the pair claimed otherwise
        self.assertEqual(ti.verify_command("npx axe-core src/index.html"),
                         "axe-core")
        self.assertEqual(ti.verify_command("npx reg-suit run"), "reg-suit")
        self.edit(self.screen)
        self.check("npx axe-core src/index.html")
        self.assertIsNone(ti.stop_reason("Done. All tests pass.", "s"))

    def test_a_failed_capture_is_not_the_proof(self):
        # the CLI half of the screen-read route read only the command, so a
        # capture that exited non-zero licensed the claim the same way a
        # successful one did; the MCP half already refused it
        self.edit()
        ti.note_tool("s", "Bash", {"command": "screencapture -x out.png"},
                     failed=True, out_bytes=10)
        self.assertIn("UI evidence",
                      ti.stop_reason("Done. All tests pass.", "s"))

    def test_a_capture_whose_outcome_nobody_reported_is_still_readable(self):
        # the control: a host that reports no outcome (omp, Cursor) leaves the
        # row usable - the rule asks for the read, not for a verdict nobody saw.
        # A screen rather than a component, so the design floor is not the
        # question this test is about.
        screen = os.path.join(self.dir, "admin", "pages", "users.tsx")
        os.makedirs(os.path.dirname(screen), exist_ok=True)
        self.edit(screen)
        ti.note_tool("s", "Bash", {"command": "screencapture -x out.png"},
                     out_bytes=10)
        self.assertIsNone(ti.stop_reason("Done. All tests pass.", "s"))

    def test_a_turn_that_wrote_no_ui_source_is_unchanged(self):
        # the control: the same shape over a `.py` file - a green unit run is
        # the evidence the UI branch does not apply to
        other = os.path.join(self.dir, "worker.py")
        self.edit(other)
        self.check("pytest -q")
        self.assertIsNone(ti.stop_reason("Done. All tests pass.", "s"))

    def run_cmd(self, command):
        """One shell row that is not a check, classified the way the hook does."""
        ti.note_tool("s", "Bash", {"command": command}, failed=False, out_bytes=42)

    def test_a_grep_that_names_the_capture_tool_is_not_a_screen_read(self):
        # the readers matched the raw detail of ANY row, so a search that merely
        # names the tool was the proof. `verify_command` scans `mask(cmd)` for
        # exactly this reason, and the row is a `run`, never a read of anything.
        self.edit(self.screen)
        self.run_cmd("rg -rn screencapture docs/")
        self.assertIn("UI evidence", ti.stop_reason("Done. All tests pass.", "s"))

    def test_a_commit_message_that_names_the_tools_is_not_a_screen_read(self):
        # the classic "text ABOUT a command": the quoted body names the capture
        # tool and the checker, and neither was run
        self.edit(self.screen)
        self.run_cmd('git commit -m "next: run tezgah-capture and '
                     'tezgah-design check"')
        self.assertIn("UI evidence", ti.stop_reason("Done. All tests pass.", "s"))

    def test_a_commit_message_is_not_the_design_check_either(self):
        # a component turn: the screen was really read, so only the design
        # branch is left, and a commit message that mentions the checker is not
        # the checker
        self.edit(self.target)
        ti.note_tool("s", "mcp__playwright__browser_take_screenshot", {},
                     failed=False)
        self.run_cmd('git commit -m "tezgah-design check --contract c"')
        self.assertIn("tezgah-design check",
                      ti.stop_reason("Done. All tests pass.", "s"))

    def test_a_shell_redirect_that_writes_a_ui_source_is_a_ui_write(self):
        # the readers counted `kind == "edit"` only, while the freshness fold
        # counts a shell write (`run`) too - so a UI source written through a
        # redirect was invisible to the rule that asks for the screen proof
        path = os.path.join(self.dir, "app", "pages", "users.tsx")
        os.makedirs(os.path.dirname(path), exist_ok=True)
        command = "cat > %s <<'EOF'\nexport const Users = () => null\nEOF" % path
        tz.capture("Bash", {"command": command}, self.dir, "s")
        with open(path, "w") as fh:
            fh.write("export const Users = () => null\n")
        self.run_cmd(command)
        self.assertTrue(ti._change_row(ti.events("s")[-1]), "not read as a change")
        self.assertIn("UI evidence", ti.stop_reason("Done. All tests pass.", "s"))

    def test_a_write_that_only_ends_in_a_ui_path_is_not_a_ui_write(self):
        # `_ui_write` searched the raw command first, so a compound line that
        # merely ENDS in a UI path - the `ls` after a real redirect - was read as
        # a write of that path and asked the turn for a screen proof it did not
        # owe
        target = os.path.join(self.dir, "out.txt")
        command = "printf a > %s; ls %s" % (target, self.screen)
        tz.capture("Bash", {"command": command}, self.dir, "s")
        with open(target, "w") as fh:
            fh.write("a")
        self.run_cmd(command)
        row = ti.events("s")[-1]
        self.assertTrue(ti._change_row(row), "not read as a change")
        self.assertIsNone(ti._ui_write(row))
        self.assertEqual(ti._ui_evidence(ti.events("s")), (-1, -1))

    def test_a_shell_redirect_that_writes_a_component_owes_the_floor(self):
        # finding 2's second half through the real branch: the redirect's target
        # is a component, so the design floor is owed over it too
        path = os.path.join(self.dir, "app", "components", "Button.tsx")
        os.makedirs(os.path.dirname(path), exist_ok=True)
        command = "cat > %s <<'EOF'\nexport const Button = () => null\nEOF" % path
        tz.capture("Bash", {"command": command}, self.dir, "s")
        with open(path, "w") as fh:
            fh.write("export const Button = () => null\n")
        self.run_cmd(command)
        ti.note_tool("s", "mcp__playwright__browser_take_screenshot", {},
                     failed=False)
        self.assertIn("tezgah-design check",
                      ti.stop_reason("Done. All tests pass.", "s"))

    def test_an_unrelated_write_after_the_screen_read_does_not_stale_it(self):
        # the compare was against the last write of anything, so a later `.py`
        # edit (with its own green run) refused a turn whose screen proof was
        # newer than the UI write it was about
        self.edit(self.screen)
        self.check("npx playwright test")
        self.edit(os.path.join(self.dir, "worker.py"))
        self.check("pytest -q")
        self.assertIsNone(ti.stop_reason("Done. All tests pass.", "s"))

    def test_an_unrelated_write_with_no_check_after_it_still_refuses(self):
        # the other side of the same rule: the screen proof settles the UI half,
        # never the unrelated write the turn left unverified
        self.edit(self.screen)
        ti.note_tool("s", "mcp__playwright__browser_take_screenshot", {},
                     failed=False)
        self.edit(os.path.join(self.dir, "worker.py"))
        reason = ti.stop_reason("Done. All tests pass.", "s")
        self.assertIn("no check", reason)


class DesignContractEvidence(unittest.TestCase):
    """A component turn owes the repository's own design contract on top of the
    screen read: a screenshot says what the component looks like, never whether
    it is on the floor the repo wrote down. The screen a person looks at is
    unchanged, and a `derive` row is not the check."""

    CHECK = ("python3 bin/tezgah-design check --contract "
             ".tezgah/design-contract.md --measured /tmp/m.json")

    def setUp(self):
        self.dir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.dir, True)
        self.addCleanup(setattr, ti, "_path", ti._path)
        ti._path = lambda session: os.path.join(self.dir, "s.jsonl")
        self.component = os.path.join(self.dir, "admin", "components",
                                      "Button.tsx")
        self.screen = os.path.join(self.dir, "admin", "pages", "users.tsx")
        for path in (self.component, self.screen):
            os.makedirs(os.path.dirname(path), exist_ok=True)

    def edit(self, path):
        tz.capture("Edit", {"file_path": path}, self.dir, "s")
        with open(path, "w") as fh:
            fh.write("export const x = () => null\n")
        ti.note_tool("s", "Edit", {"file_path": path}, failed=False)

    def screen_read(self):
        ti.note_tool("s", "mcp__playwright__browser_take_screenshot", {},
                     failed=False)

    def design_check(self):
        ti.note_tool("s", "Bash", {"command": self.CHECK}, failed=False,
                     out_bytes=64)

    def test_a_component_turn_without_the_check_names_the_command(self):
        self.edit(self.component)
        self.screen_read()
        reason = ti.stop_reason("Done. All tests pass.", "s")
        self.assertIn("tezgah-design check", reason)
        # the path is shown the way the sibling branch shows it, a long one cut
        # to its last 77 characters, so the directory and the file name survive
        self.assertIn("admin/components/", reason)
        self.assertEqual([r["detail"] for r in ti.events("s")
                          if r["kind"] == "claim"], ["blocked: no ui_ok"])

    def test_a_component_turn_that_ran_the_check_is_not_refused(self):
        self.edit(self.component)
        self.screen_read()
        self.design_check()
        self.assertIsNone(ti.stop_reason("Done. All tests pass.", "s"))

    def test_the_design_check_reaches_the_ledger_as_a_check(self):
        # the row has to be a check like any other, or the branch asking for it
        # could never be satisfied
        self.design_check()
        row = ti.events("s")[-1]
        self.assertEqual(row["kind"], "verify_ok")
        self.assertTrue(ti.passing_check(row))
        self.assertTrue(ti.verify_command(self.CHECK).endswith(
            "tezgah-design check"))

    def test_a_design_check_on_a_later_line_of_the_call_is_a_check(self):
        # a call is often multi-line; the readers matched `^` and `[|;&(]`, so
        # the same checker on the call's own second line was invisible to the
        # floor while `VERIFY` read the row as a check
        self.edit(self.component)
        self.screen_read()
        ti.note_tool("s", "Bash", {"command": "pytest -q\n" + self.CHECK},
                     failed=False, out_bytes=64)
        self.assertIsNone(ti.stop_reason("Done. All tests pass.", "s"))

    def test_a_derive_run_does_not_stand_in_for_the_check(self):
        self.edit(self.component)
        self.screen_read()
        ti.note_tool("s", "Bash",
                     {"command": "python3 bin/tezgah-design derive --repo ."},
                     failed=False, out_bytes=64)
        self.assertIn("tezgah-design check",
                      ti.stop_reason("Done. All tests pass.", "s"))

    def test_the_check_alone_does_not_stand_in_for_the_screen(self):
        self.edit(self.component)
        self.design_check()
        self.assertIn("UI evidence",
                      ti.stop_reason("Done. All tests pass.", "s"))

    def test_a_check_from_before_the_write_is_stale_like_any_other(self):
        self.design_check()
        self.edit(self.component)
        self.screen_read()
        self.assertIn("tezgah-design check",
                      ti.stop_reason("Done. All tests pass.", "s"))

    def test_a_check_with_no_outcome_is_not_the_floor(self):
        # DESIGN_CHECK was the one reader not gated on `passing_check`: a check
        # row whose outcome nobody saw satisfied the component floor, which is
        # the exact shape `passing_check` exists to refuse
        self.edit(self.component)
        self.screen_read()
        ti.note_tool("s", "Bash", {"command": self.CHECK}, failed=None,
                     out_bytes=20)
        row = ti.events("s")[-1]
        self.assertEqual(row["kind"], "verify", row)
        self.assertFalse(ti.passing_check(row))
        self.assertIn("tezgah-design check",
                      ti.stop_reason("Done. All tests pass.", "s"))

    def test_a_later_unrelated_write_does_not_stale_the_floor(self):
        # the check has to be newer than the component write it judges, which is
        # what its own docstring says - not newer than the last write of
        # anything
        self.edit(self.component)
        self.screen_read()
        self.design_check()
        self.edit(os.path.join(self.dir, "worker.py"))
        ti.note_tool("s", "Bash", {"command": "pytest -q"}, failed=False,
                     out_bytes=8)
        self.assertIsNone(ti.stop_reason("Done. All tests pass.", "s"))

    def test_a_screen_turn_needs_no_design_check(self):
        # the control: the same shape over a page, not a component
        self.edit(self.screen)
        self.screen_read()
        self.assertIsNone(ti.stop_reason("Done. All tests pass.", "s"))


class CommittedBoundary(unittest.TestCase):
    """W3: the byte boundary a ledger has committed, and what both paths do with
    a tail past it.

    A process killed inside a write leaves a fragment no newline ever terminated.
    It is not a record, so no reader may see it - but it must not stay in the
    file for ever either, and the damage that *was* terminated is the other
    damage entirely: a committed record that lost bytes is a hard error, not a
    gap a reader silently steps over. (`_path` is patched so the real cache is
    never touched.)"""

    def setUp(self):
        self.dir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.dir, True)
        self.addCleanup(setattr, ti, "_path", ti._path)
        self.path = os.path.join(self.dir, "s.jsonl")
        ti._path = lambda session: self.path

    def raw(self):
        with open(self.path, "rb") as fh:
            return fh.read()

    def torn(self):
        """The fragment a killed writer leaves: a record prefix, no newline."""
        with open(self.path, "ab") as fh:
            fh.write(b'{"kind": "run", "det')
        return len(self.raw())

    def test_the_boundary_is_the_whole_file_it_ends_in_a_newline(self):
        ti.note("s", "run", "ls")
        whole = os.path.getsize(self.path)
        with open(self.path, "a+b") as fh:
            self.assertEqual(ti.committed_size(fh), whole)
            self.assertEqual(ti.truncate_to_committed(fh), whole)
        self.assertEqual(len(self.raw()), whole)

    def test_the_boundary_stops_at_the_last_newline_and_is_zero_without_one(self):
        ti.note("s", "run", "ls")
        whole = os.path.getsize(self.path)
        self.assertEqual(self.torn(), whole + len(b'{"kind": "run", "det'))
        with open(self.path, "a+b") as fh:
            self.assertEqual(ti.committed_size(fh), whole)
            self.assertEqual(ti.truncate_to_committed(fh), whole)
        self.assertEqual(len(self.raw()), whole)
        self.assertTrue(self.raw().endswith(b"\n"))
        # a file that holds no newline has committed nothing, whatever its size
        with open(self.path, "wb") as fh:
            fh.write(b'{"kind"')
        with open(self.path, "a+b") as fh:
            self.assertEqual(ti.committed_size(fh), 0)

    def test_only_the_unterminated_tail_is_invisible_to_a_reader(self):
        ti.note("s", "run", "ls")
        self.torn()
        self.assertEqual([r["detail"] for r in ti.events("s")], ["ls"])
        self.assertEqual([r["detail"] for r in ti.events("s", tail=2)], ["ls"])
        self.assertEqual([r["detail"] for r in ti.events_path(self.path,
                                                             tail=2)], ["ls"])

    def test_a_terminated_line_that_lost_its_bytes_is_a_hard_error(self):
        # the other damage: the newline is there, so the record committed, and a
        # reader that skipped it would have shrunk the evidence in silence
        ti.note("s", "run", "ls")
        with open(self.path, "a") as fh:
            fh.write("{broken\n")
        with self.assertRaises(ValueError):
            ti.events("s")
        with self.assertRaises(ValueError):
            ti.events("s", tail=2)

    def test_the_next_append_repairs_the_torn_tail_instead_of_burying_it(self):
        # left in place, the fragment is terminated by the row written after it
        # and the two become one line no reader can parse - the file would hold
        # one record where two were written, for ever
        ti.note("s", "run", "ls")
        whole = os.path.getsize(self.path)
        self.torn()
        ti.note("s", "verify_ok", "pytest -q")
        # both rows are readable again, where the fragment left in place would
        # have merged them into a line no reader can parse
        self.assertEqual([r["detail"] for r in ti.events("s")],
                         ["ls", "pytest -q"])
        # and the file's own shape says the same: two records, the second one
        # starting exactly where the first ended
        self.assertEqual(self.raw().count(b"\n"), 2)
        self.assertTrue(self.raw()[whole:].startswith(b'{"kind": "verify_ok"'))
        self.assertEqual([json.loads(line)["detail"]
                          for line in self.raw().splitlines()], ["ls", "pytest -q"])


class LedgerAppendLock(unittest.TestCase):
    """B9: the ledger's appender serializes on an exclusive lock.

    A host fires PostToolUse once per call of a parallel batch, each in its own
    process, so two writers reach one file at once. The lock is taken on the
    ledger's own descriptor - what it must do is what is under test, exclude a
    second writer. (`_path` is patched so the real cache is never touched.)

    ponytail: a row LOST to an unlocked append could not be reproduced on APFS
    even with six writers and 400-byte lines, because one `write(2)` on an
    O_APPEND handle lands whole - so this asserts the exclusion, which is what
    the change adds and what can be observed, not a torn line this filesystem
    does not produce."""

    def setUp(self):
        self.dir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.dir, True)
        self.addCleanup(setattr, ti, "_path", ti._path)
        self.path = os.path.join(self.dir, "s.jsonl")
        ti._path = lambda session: self.path

    def test_the_append_waits_for_the_lock_a_second_writer_holds(self):
        # the lock's own premise: a holder excludes the append. Without it the
        # append returns at once and the two writers are back to racing.
        held = open(self.path, "a")
        self.addCleanup(held.close)
        fcntl.flock(held, fcntl.LOCK_EX)
        release = threading.Timer(0.4, lambda: fcntl.flock(held, fcntl.LOCK_UN))
        release.daemon = True
        release.start()
        self.addCleanup(release.cancel)
        start = time.time()
        ti.note("s", "run", "ls")
        self.assertGreaterEqual(time.time() - start, 0.3,
                                "the append did not wait for the lock")
        self.assertEqual([r["detail"] for r in ti.events("s")], ["ls"])


class StopHook(TempHome):
    def setUp(self):
        super().setUp()
        self.repo = self.make_repo("proj")
        self.envv = self.env()
        self.session = "s-stop"

    def seed(self, tool, inp, failed=False, **extra):
        payload = {"fn": "note_tool", "session": self.session, "tool": tool,
                   "input": inp, "failed": failed}
        payload.update(extra)
        run_json([support.PROBE_INTEGRITY], payload, env=self.envv)

    def counts(self):
        out, _ = run_json([support.PROBE_INTEGRITY],
                          {"fn": "counters", "session": self.session},
                          env=self.envv)
        return out

    def kinds(self):
        out, _ = run_json([support.PROBE_INTEGRITY],
                          {"fn": "kinds", "session": self.session},
                          env=self.envv)
        return out

    def stop(self, text, **extra):
        payload = {"hook_event_name": "Stop", "cwd": self.repo,
                   "session_id": self.session, "last_assistant_message": text}
        payload.update(extra)
        out, proc = run_json([support.STOP_HOOK], payload, env=self.envv)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        return out

    def turn(self, prompt="again"):
        """One user prompt, as the prompt path writes it."""
        run_json([support.PROBE_INTEGRITY],
                 {"fn": "note_turn", "session": self.session, "prompt": prompt},
                 env=self.envv)

    def rows(self, kind):
        """Every row of one kind, whole. The additive fields `reply_shape`
        records live beside `detail`, so a reader that wants only the detail goes
        through the two wrappers below."""
        out, _ = run_json([support.PROBE_INTEGRITY],
                          {"fn": "events", "session": self.session},
                          env=self.envv)
        return [r for r in out if r.get("kind") == kind]

    def claim_rows(self):
        return [r.get("detail") for r in self.rows("claim")]

    def shape_rows(self):
        return [r.get("detail") for r in self.rows("shape")]

    def test_unverified_done_claim_blocks(self):
        self.seed("Bash", {"command": "ls"})
        out = self.stop("Done. Implemented the parser and all tests pass.")
        self.assertEqual(out.get("decision"), "block")
        self.assertIn("no check ran", out["reason"])

    def test_done_claim_needs_no_edit(self):
        out = self.stop("Done, everything works.")
        self.assertIsNone(out)  # nothing was worked on: nothing to verify

    def test_verified_done_claim_passes(self):
        self.seed("Edit", {"file_path": "x.py"})
        self.seed("Bash", {"command": "pytest -q"})
        self.assertIsNone(self.stop("Done. All tests pass."))

    def pre(self, tool, inp):
        """One PreToolUse the gate lets through, as Claude's hook runs it."""
        run_json([support.PRETOOLUSE],
                 {"hook_event_name": "PreToolUse", "cwd": self.repo,
                  "session_id": self.session, "tool_name": tool,
                  "tool_input": inp}, env=self.envv)

    def test_a_check_whose_result_never_arrived_is_not_a_check_that_ran(self):
        # gortex's abandoned call: the host answered a Bash call in the first
        # turn, so it delivers results; in the second the gate let `pytest` run
        # and no PostToolUse came back. The earlier pass does not back the new
        # claim, and the session's counters name the call as unanswered.
        self.turn("first")
        self.pre("Bash", {"command": "pytest -q"})
        self.seed("Bash", {"command": "pytest -q"}, out_bytes=12)
        self.turn("second")
        self.pre("Bash", {"command": "pytest -q"})
        out = self.stop("Done. All tests pass.")
        self.assertEqual((out or {}).get("decision"), "block")
        self.assertIn("no check ran", out["reason"])
        self.assertEqual(self.claim_rows(), ["blocked: no verify_ok"])
        self.assertEqual(self.counts()["unanswered"], 1)

    def test_a_read_only_turn_on_a_host_without_post_rows_is_not_refused(self):
        # A host that sends no post event for a tool leaves every call of it
        # waiting. Counting those would make each read-only turn owe a check,
        # so a tool counts only once the host is seen to answer it: `ls` with
        # no Bash answer anywhere, and a PowerShell call beside an answered
        # Bash one, are both left out.
        self.pre("Bash", {"command": "ls"})
        self.assertIsNone(self.stop("İki dosya var: a.py ve b.py."))
        self.assertEqual(self.counts()["unanswered"], 0)
        self.session = "s-stop-tools"
        self.turn("first")
        self.pre("Bash", {"command": "pytest -q"})
        self.seed("Bash", {"command": "pytest -q"}, out_bytes=12)
        self.turn("second")
        self.pre("PowerShell", {"command": "Get-ChildItem"})
        self.assertIsNone(self.stop("İki dosya var: a.py ve b.py."))
        self.assertEqual(self.counts()["unanswered"], 0)

    def test_a_check_whose_result_arrived_is_answered(self):
        # the ordinary case: the same call with its PostToolUse is a pass, and
        # nothing is left unanswered
        self.pre("Bash", {"command": "pytest -q"})
        self.seed("Bash", {"command": "pytest -q"}, out_bytes=12)
        self.assertIsNone(self.stop("Done. All tests pass."))
        self.assertEqual(self.counts()["unanswered"], 0)

    def answered_first_turn(self):
        """Turn 1 of the reviewer's repros: the host answered both calls and
        the check passed."""
        self.turn("first")
        for command in ("ls", "pytest -q"):
            self.pre("Bash", {"command": command})
            self.seed("Bash", {"command": command}, out_bytes=12)
        self.turn("second")

    def test_a_call_the_host_refused_does_not_make_a_turn_work(self):
        # The gate writes `began` before the host's own permission layer, so a
        # command the user said no to never answers. Nothing ran, the reply
        # claims nothing, and the turn is not refused.
        self.answered_first_turn()
        self.pre("Bash", {"command": "rm -rf build"})
        self.assertIsNone(self.stop(
            "Komutu calistirmadim; build klasoru yerinde duruyor."))

    def test_a_refused_call_does_not_cancel_the_bookkeeping_exemption(self):
        # a `git status` after a green run, beside a push the user refused:
        # still bookkeeping over a settled tree
        self.answered_first_turn()
        self.pre("Bash", {"command": "git status"})
        self.seed("Bash", {"command": "git status"}, out_bytes=12)
        self.pre("Bash", {"command": "git push --force"})
        self.assertIsNone(self.stop("Commit hazir; push etmedim."))

    def test_an_abandoned_check_past_the_detail_cut_still_backs_nothing(self):
        # the stored detail stops at DETAIL_MAX; a runner past that point was
        # read as no check, and a claim rode the earlier turn's pass
        self.answered_first_turn()
        command = "cd " + "/very/long/path" * 13 + " && pytest -q tests/test_x.py"
        self.assertGreater(len(command), 200)
        self.pre("Bash", {"command": command})
        out = self.stop("Tamamlandı, tüm testler geçti.")
        self.assertEqual((out or {}).get("decision"), "block")

    def test_a_claim_in_a_turn_with_no_work_is_judged_against_the_session(self):
        # audit INT-01 / M-2: turn 1 did unverified work and ended honestly, turn
        # 2 did nothing and claimed the tests pass - allowed on all five hosts
        self.turn("parser hatasını düzelt")
        self.seed("Bash", {"command": "sed -i '' s/1/2/ a.py"})
        self.assertIsNone(self.stop("Düzeltmeyi uyguladım, doğrulanmadı."))
        self.turn("tamam mı, bitti mi?")
        out = self.stop("Tamamlandı, tüm testler geçti.")
        self.assertEqual(out.get("decision"), "block")
        self.assertIn("This session did work", out["reason"])
        self.assertEqual(self.claim_rows(), ["blocked: no verify_ok"])

    def test_a_claim_in_a_turn_with_no_work_after_a_session_pass_passes(self):
        self.turn("fix it")
        self.seed("Edit", {"file_path": "x.py"})
        self.seed("Bash", {"command": "pytest -q"})
        self.turn("is it done?")
        self.assertIsNone(self.stop("Done. All tests pass."))

    def test_a_claim_after_a_session_whose_newest_check_failed_is_refused(self):
        self.turn("fix it")
        self.seed("Bash", {"command": "pytest -q"})
        self.seed("Bash", {"command": "pytest -q"}, failed=True)
        self.assertIsNone(self.stop("Bir test kırık, doğrulanmadı."))
        self.turn("is it done?")
        out = self.stop("Done. All tests pass.")
        self.assertEqual(self.claim_rows(), ["blocked: check failed"])
        self.assertIn("A check failed in this session", out["reason"])

    def test_a_vcs_only_turn_after_a_pass_on_an_unchanged_tree_ends(self):
        # audit CHAT-04 / M-12: a commit-only turn was refused for having no
        # check of its own, and the model re-ran a suite that had just passed
        self.turn("fix it")
        self.seed("Edit", {"file_path": "x.py"})
        self.seed("Bash", {"command": "pytest -q"})
        self.turn("commit it")
        self.seed("Bash", {"command": "git status --short"})
        self.seed("Bash", {"command": 'git add -A && git commit -m "fix: parser"'})
        self.assertIsNone(self.stop("Değişiklik commitlendi."))

    def test_a_vcs_only_turn_after_an_unchecked_edit_still_owes_a_check(self):
        # the exemption is for the tree the check judged: an edit after the
        # pass, even in an earlier turn, still needs a fresh check
        self.turn("fix it")
        self.seed("Bash", {"command": "pytest -q"})
        self.seed("Edit", {"file_path": "x.py"})
        self.turn("commit it")
        self.seed("Bash", {"command": "git commit -am x"})
        out = self.stop("Değişiklik commitlendi.")
        self.assertEqual(out.get("decision"), "block")

    def test_a_turn_that_is_not_only_bookkeeping_keeps_the_turn_rule(self):
        # a command this cannot read as read-only is work, pass or no pass
        self.turn("fix it")
        self.seed("Bash", {"command": "pytest -q"})
        self.turn("clean up")
        self.seed("Bash", {"command": "rm -rf build"})
        self.assertEqual(self.stop("Temizledim.").get("decision"), "block")

    def test_a_redirect_turn_is_not_bookkeeping(self):
        # review F8: on its own, after a pass, so only the redirect guard can
        # refuse it - an earlier non-bookkeeping row would refuse it anyway
        self.turn("fix it")
        self.seed("Bash", {"command": "pytest -q"})
        self.turn("write it out")
        self.seed("Bash", {"command": "git log > /tmp/log.txt"})
        self.assertEqual(self.stop("Yazdım.").get("decision"), "block")

    def test_a_command_cut_by_the_ledger_is_not_bookkeeping(self):
        # review F1: the row keeps DETAIL_MAX characters, so a write past the
        # cut (`python3 scripts/regen.py`) was read as a run of `cat`
        self.turn("fix it")
        self.seed("Bash", {"command": "pytest -q"})
        self.turn("look around")
        self.seed("Bash", {"command": "git status --short && cat %s && "
                           "python3 scripts/regen.py" % ("src/a.py " * 25)})
        self.assertEqual(self.stop("Baktım.").get("decision"), "block")

    def ui_turn_then(self):
        """Turn 1 edits a component and runs a unit pass only, then ends
        honestly; the UI proof it owes is still missing."""
        path = os.path.join(self.repo, "app", "components", "Button.tsx")
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w") as fh:
            fh.write("export const Button = () => null\n")
        self.turn("restyle the button")
        self.seed("Edit", {"file_path": path})
        self.seed("Bash", {"command": "pytest -q"})
        self.assertIsNone(self.stop("Butonu değiştirdim, doğrulanmadı."))

    def test_a_bookkeeping_turn_keeps_a_pending_ui_check(self):
        # review F5: the session-level path judged only three of the turn
        # fold's classes, so a commit turn after an unproven UI change ended
        self.ui_turn_then()
        self.turn("commit it")
        self.seed("Bash", {"command": "git commit -am x"})
        out = self.stop("Değişiklik commitlendi.")
        self.assertEqual(out.get("decision"), "block")
        self.assertEqual(self.claim_rows()[-1], "blocked: no ui_ok")

    def test_a_no_work_claim_keeps_a_pending_ui_check(self):
        self.ui_turn_then()
        self.turn("is it done?")
        self.assertEqual(self.stop("Tamamlandı, testler geçti.").get("decision"),
                         "block")
        self.assertEqual(self.claim_rows()[-1], "blocked: no ui_ok")

    def test_a_no_work_claim_keeps_an_unresolved_partial_failure(self):
        # a failure followed by a check whose outcome nobody saw is a partial
        # failure in the turn fold, and it stays one a turn later
        self.turn("fix it")
        self.seed("Bash", {"command": "pytest -q"})
        self.seed("Bash", {"command": "ruff check ."}, failed=True)
        self.seed("Bash", {"command": "ruff check ."}, failed=None)
        self.assertIsNone(self.stop("Lint kırık, doğrulanmadı."))
        self.turn("is it done?")
        self.stop("Tamamlandı, testler geçti.")
        self.assertEqual(self.claim_rows()[-1], "blocked: partial failure")

    def test_an_idle_turn_does_not_clear_a_partial_failure(self):
        # review N5: a question turn in between made the newest turn an empty
        # one, and the partial failure before it stopped counting
        self.turn("fix it")
        self.seed("Edit", {"file_path": "x.py"})
        self.seed("Bash", {"command": "pytest -q"})
        self.seed("Bash", {"command": "pytest tests/a"}, failed=True)
        self.seed("Bash", {"command": "pytest tests/b"}, failed=None)
        self.assertIsNone(self.stop("Bir test kırık, doğrulanmadı."))
        self.turn("what broke?")
        self.turn("is it done?")
        self.stop("Tamamlandı, testler geçti.")
        self.assertEqual(self.claim_rows()[-1], "blocked: partial failure")

    def test_failed_check_blocks(self):
        self.seed("Edit", {"file_path": "x.py"})
        self.seed("Bash", {"command": "pytest -q"}, failed=True)
        out = self.stop("Done. Tests pass.")
        self.assertEqual(out.get("decision"), "block")
        self.assertIn("failed", out["reason"])

    def test_a_failure_after_a_passing_check_still_blocks(self):
        # the newest check decides: a green run does not license "the tests
        # pass" once a later run failed
        self.seed("Edit", {"file_path": "x.py"})
        self.seed("Bash", {"command": "pytest -q"})
        self.seed("Bash", {"command": "pytest -q"}, failed=True)
        out = self.stop("Done. All tests pass.")
        self.assertEqual(out.get("decision"), "block")
        self.assertIn("failed", out["reason"])

    def test_a_passing_check_after_a_failure_passes(self):
        self.seed("Edit", {"file_path": "x.py"})
        self.seed("Bash", {"command": "pytest -q"}, failed=True)
        self.seed("Bash", {"command": "pytest -q"})
        self.assertIsNone(self.stop("Done. All tests pass."))
        self.assertEqual(self.claim_rows(), ["ok"])

    def test_an_unresolved_failure_blocks_even_after_an_earlier_pass(self):
        # the hole this closes: green over one command, then a failure, then a
        # check whose outcome nobody saw. The earlier pass licensed the claim
        # before this branch existed, whatever the newest check was.
        self.seed("Edit", {"file_path": "x.py"})
        self.seed("Bash", {"command": "pytest -q"})
        self.seed("Bash", {"command": "ruff check ."}, failed=True)
        self.seed("Bash", {"command": "mypy ."}, failed=None)
        out = self.stop("Done. All tests pass.")
        self.assertEqual(out.get("decision"), "block")
        self.assertIn("ruff check .", out["reason"])
        self.assertEqual(self.claim_rows(), ["blocked: partial failure"])

    def test_a_new_turn_is_not_refused_for_the_previous_turns_failure(self):
        # boundary: the failure state is the newest turn's, so a failure the
        # user's next prompt moved past cannot refuse this turn's reply
        self.seed("Edit", {"file_path": "x.py"})
        self.seed("Bash", {"command": "pytest -q"}, failed=True)
        self.turn()
        self.seed("Bash", {"command": "pytest -q"})
        self.assertIsNone(self.stop("Done. All tests pass."))

    def test_the_unresolved_failure_branch_does_not_swallow_the_others(self):
        # a turn that ends on a failed check still reads as `check failed`, not
        # as the newer partial-failure branch
        self.seed("Edit", {"file_path": "x.py"})
        self.seed("Bash", {"command": "pytest -q"})
        self.seed("Bash", {"command": "pytest -q"}, failed=True)
        out = self.stop("Done. Tests pass.")
        self.assertEqual(out.get("decision"), "block")
        self.assertEqual(self.claim_rows(), ["blocked: check failed"])

    def test_a_component_turn_owes_the_design_check(self):
        # the same branch through the real hook process: a component whose
        # screen was read still has no floor applied to it
        path = os.path.join(self.repo, "app", "components", "Button.tsx")
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w") as fh:
            fh.write("export const Button = () => null\n")
        self.seed("Edit", {"file_path": path})
        self.seed("mcp__playwright__browser_take_screenshot", {})
        out = self.stop("Done. All tests pass.")
        self.assertEqual(out.get("decision"), "block")
        self.assertIn("tezgah-design check", out["reason"])
        self.assertEqual(self.claim_rows(), ["blocked: no ui_ok"])

    def test_a_component_turn_with_the_design_check_passes(self):
        path = os.path.join(self.repo, "app", "components", "Button.tsx")
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w") as fh:
            fh.write("export const Button = () => null\n")
        self.seed("Edit", {"file_path": path})
        self.seed("mcp__playwright__browser_take_screenshot", {})
        self.seed("Bash", {"command": "python3 bin/tezgah-design check "
                                      "--contract c.md --measured m.json"})
        self.assertIsNone(self.stop("Done. All tests pass."))

    def test_explicit_unverified_admission_passes(self):
        self.seed("Edit", {"file_path": "x.py"})
        self.assertIsNone(self.stop("Done, but I could not verify the tests."))

    def test_sycophantic_opener_blocks(self):
        out = self.stop("Haklısın, hemen düzeltiyorum.")
        self.assertEqual(out.get("decision"), "block")
        self.assertIn("placation", out["reason"])

    # Rule 10 of skills/i-have-adhd/SKILL.md lists the forms a reply may neither
    # open nor close on, and `SYCOPHANT` / `CLOSER` read those two lists. The
    # opener keeps the class it always wrote (`blocked: placating opener`); the
    # closer has its own (`blocked: forbidden closer`), so a corpus query can tell
    # which end refused the turn.
    def test_an_opener_from_the_skills_own_list_blocks(self):
        out = self.stop("Great question! The fix is one line.")
        self.assertEqual(out.get("decision"), "block")
        self.assertIn("preamble", out["reason"])
        self.assertEqual(self.claim_rows(), ["blocked: placating opener"])

    def test_a_closer_from_the_skills_own_list_blocks(self):
        out = self.stop("The parser handles the new field.\n\n"
                        "Let me know if you need anything else.")
        self.assertEqual(out.get("decision"), "block")
        self.assertIn("closer", out["reason"])
        self.assertEqual(self.claim_rows(), ["blocked: forbidden closer"])

    def test_the_two_ends_write_distinguishable_classes(self):
        self.stop("Sure! Here it is.")
        self.stop("Here it is. Hope this helps.")
        self.assertEqual(self.claim_rows(),
                         ["blocked: placating opener", "blocked: forbidden closer"])

    def test_a_quoted_opener_and_closer_in_a_code_block_are_not_this_replys(self):
        # the false-positive class the two checks accept is only the reply's own
        # text: a form quoted later is not its opener (the opener check is
        # anchored at the reply's first line) and not its closer (the reply's last
        # prose line is the line after the fence, so `_closing_prose` reads that)
        text = ("Rule 10 lists the banned forms:\n"
                "\n"
                "```\n"
                "Great question. Let me look at that.\n"
                "Hope this helps. Happy to clarify.\n"
                "```\n"
                "\n"
                "Reported above.")
        self.assertIsNone(self.stop(text))
        # and a reply that ENDS on the fence: its last non-blank line is inside
        # the block, so `_closing_prose` hands the check no prose line at all
        self.assertIsNone(self.stop("Rule 10 bans the sign-offs:\n\n```\n"
                                    "Hope this helps.\n```"))

    def test_an_answer_first_reply_that_closes_on_a_next_step_passes(self):
        # the contract's own shape at both ends, on a short reply: the two checks
        # ban the forms, not brevity and not a reply with nothing to recap
        self.assertIsNone(self.stop("Toplam 5 dosya incelendi.\n"
                                    "Sıradaki adım: `pytest -q` çalıştır."))

    def test_plain_answer_passes(self):
        self.assertIsNone(self.stop("Toplam 5 dosya incelendi."))

    def test_a_check_that_returned_nothing_is_not_support(self):
        # exit 0 with an empty result is the silent-failure case: the check ran
        # and reported nothing, which is not evidence that it passed
        self.seed("Edit", {"file_path": "x.py"})
        self.seed("Bash", {"command": "pytest -q"}, out_bytes=0)
        out = self.stop("Done. All tests pass.")
        self.assertEqual(out.get("decision"), "block")

    def test_a_piped_check_records_as_ran_not_passed(self):
        # a pipe's status belongs to its last stage, so `pytest | tail` says
        # nothing about pytest
        self.seed("Edit", {"file_path": "x.py"})
        self.seed("Bash", {"command": "pytest -q | tail -1"})
        self.assertEqual(self.kinds(), ["edit", "verify"])
        out = self.stop("Done. All tests pass.")
        self.assertEqual(out.get("decision"), "block")

    def test_a_pipefail_piped_check_is_decisive(self):
        # `set -o pipefail` hands the pipe's status back to the check, so the
        # host's verdict is the check's: a pass carries a claim, a fail blocks it
        self.seed("Edit", {"file_path": "x.py"})
        self.seed("Bash", {"command": "set -o pipefail; pytest -q 2>&1 | tail -3"})
        self.assertEqual(self.kinds(), ["edit", "verify_ok"])
        self.assertIsNone(self.stop("Done. All tests pass."))
        self.seed("Bash", {"command": "set -euo pipefail\npytest -q | tail -3"},
                  failed=True)
        self.assertIn("verify_fail", self.kinds())

    def test_pipefail_does_not_rescue_an_or_branch(self):
        # `||` answers for the failure whatever pipefail says
        self.seed("Bash", {"command": "set -o pipefail; pytest -q | tail || echo x"})
        self.assertEqual(self.kinds(), ["verify"])

    def test_a_blocked_stop_is_recorded_as_a_false_completion(self):
        self.seed("Edit", {"file_path": "x.py"})
        self.stop("Done. All tests pass.")
        counts = self.counts()
        self.assertEqual(counts["claims"], 1)
        self.assertEqual(counts["false_completion"], 1)

    def test_the_claim_row_names_the_branch_that_refused(self):
        # "did the rule fire, and why" has to be answerable from the ledger
        # alone: the reason class is what a corpus query reads, not the block
        # prose, and a turn the rule never judged writes no row at all
        self.seed("Edit", {"file_path": "x.py"})
        out = self.stop("Done. All tests pass.")
        self.assertEqual(out.get("decision"), "block")
        self.assertEqual(self.claim_rows(), ["blocked: no verify_ok"])
        self.seed("Bash", {"command": "pytest -q"}, failed=True)
        self.stop("Done. Tests pass.")
        self.stop("Haklısın, hemen düzeltiyorum.")
        # a turn the rule never judged writes no row at all: with a passing check
        # behind the work, a reply with no claim vocabulary is not this rule's
        # business (a turn with work and NO passing check is judged now, and
        # writes `blocked: no verify_ok`)
        self.seed("Bash", {"command": "pytest -q"})
        self.assertIsNone(self.stop("Toplam 5 dosya incelendi."))
        self.assertEqual(self.claim_rows(), ["blocked: no verify_ok",
                                            "blocked: check failed",
                                            "blocked: placating opener"])

    def test_an_allowed_claim_is_recorded_too(self):
        # without the allowed rows the false-completion rate has no denominator
        self.seed("Edit", {"file_path": "x.py"})
        self.seed("Bash", {"command": "pytest -q"})
        self.assertIsNone(self.stop("Done. All tests pass."))
        counts = self.counts()
        self.assertEqual(counts["claims"], 1)
        self.assertEqual(counts["false_completion"], 0)

    def test_a_repeated_identical_reply_is_one_claim(self):
        # Cursor treats a block as a follow-up and runs the Stop handler again,
        # and a model may re-emit its text: one turn's claim must not count twice
        self.seed("Edit", {"file_path": "x.py"})
        self.stop("Done. All tests pass.")
        self.stop("Done. All tests pass.")
        counts = self.counts()
        self.assertEqual(counts["claims"], 1)
        self.assertEqual(counts["false_completion"], 1)

    def test_the_same_reply_in_a_new_turn_is_a_new_claim(self):
        self.seed("Edit", {"file_path": "x.py"})
        self.stop("Done. All tests pass.")
        self.turn()
        self.stop("Done. All tests pass.")
        self.assertEqual(self.counts()["claims"], 2)

    def test_a_reply_without_a_claim_records_nothing(self):
        # the claim row is this rule's verdict on a reply: a turn with a passing
        # check behind it is a turn the rule never judged, so the false-completion
        # denominator must not grow with it
        self.seed("Edit", {"file_path": "x.py"})
        self.seed("Bash", {"command": "pytest -q"})
        self.assertIsNone(self.stop("Toplam 5 dosya incelendi."))
        self.assertEqual(self.counts()["claims"], 0)

    def test_a_completed_state_word_is_a_claim_and_still_not_a_refusal(self):
        # The vocabulary this machine's own transcripts measured as missing:
        # "güncellendi" states a completion as a completed state, and the list
        # carried only the first person ("yaptım"). It is read for the row's
        # detail - so the false-completion denominator counts the claims that
        # were made - and never for the verdict: a turn with no work rows and no
        # check is allowed whatever its wording, which is why widening the list
        # cannot block an honest turn.
        self.assertIsNone(self.stop("Dosya güncellendi, push tamam."))
        self.assertEqual(self.claim_rows(), ["ok"])

    def test_work_with_no_passing_check_is_refused_without_a_claim_word(self):
        # A1/D5/G5, the evidence-shaped half. The vocabulary list let the same
        # unfounded state through when it was stated as a description (E2
        # measured 0 of 10 implicit claims refused). The turn's own evidence is
        # the trigger now, so this reply carries no claim word and is still
        # refused - and the refusal is recorded like any other.
        self.seed("Edit", {"file_path": "x.py"})
        out = self.stop("The parser handles the new field and the wiring is in "
                        "place.")
        self.assertEqual((out or {}).get("decision"), "block")
        self.assertIn("no check ran", (out or {}).get("reason", ""))
        self.assertEqual(self.claim_rows(), ["blocked: no verify_ok"])
        self.assertEqual(self.counts()["false_completion"], 1)

    def test_a_step_that_failed_is_refused_without_a_claim_word(self):
        # the same rule over a check that ran and failed: "verify_fail" is a step
        # the turn did, and the reply says nothing about it
        self.seed("Bash", {"command": "pytest -q"}, failed=True)
        out = self.stop("The suite was slow, so I looked at the slowest file.")
        self.assertEqual((out or {}).get("decision"), "block")
        self.assertIn("failed", (out or {}).get("reason", ""))

    def test_the_admission_is_the_only_exemption(self):
        # the same state and the same absence of claim words, with the reply's own
        # `doğrulanmadı`: nothing is refused and no row is written
        self.seed("Edit", {"file_path": "x.py"})
        self.assertIsNone(
            self.stop("The parser handles the new field. doğrulanmadı."))
        self.assertEqual(self.counts()["claims"], 0)

    # P4: the reply-shape flags are reported and never refused. `stop_reason`
    # writes one `shape` row per flagged reply and blocks nothing on it: a table
    # sometimes answers best and a long reply sometimes needs no next step, so
    # the two flags stay a measurement until the counters show how often they
    # fire on replies the contract wanted.
    BAD = "\n".join(
        ["| item | count |", "| --- | --- |"]
        + ["| row %d | %d |" % (i, i) for i in range(27)]
        + ["The work is written up above."])
    GOOD = ("The parser now handles the new field.\n"
            "Next: run `pytest tests/test_parse.py`.")

    def test_a_table_first_long_recap_close_reply_flags_both(self):
        self.assertEqual(len(self.BAD.split("\n")), 30)
        self.assertEqual(ti.shape_flags(self.BAD),
                         ["table-open", "recap-close"])

    def test_a_good_reply_flags_nothing(self):
        self.assertEqual(ti.shape_flags(self.GOOD), [])

    def test_a_table_that_does_not_open_the_reply_is_not_flagged(self):
        # the flag is about where the answer is, not about using a table at all:
        # flagging every table would refuse the reply that needs one
        text = "The counts are:\n\n" + self.BAD
        self.assertNotIn("table-open", ti.shape_flags(text))

    def test_a_long_reply_that_closes_on_a_next_action_is_not_flagged(self):
        # the contract's own closing shape - a recap followed by the next step is
        # what it asks for - so the marker has to suppress the flag
        text = "\n".join(["line %d" % i for i in range(20)]
                         + ["Next: run `pytest -q` and read the tail."])
        self.assertEqual(ti.shape_flags(text), [])

    def test_a_long_reply_that_ends_in_a_code_block_is_not_flagged(self):
        # a reply closing on a code block closes on structure, not on a recap:
        # reading the last line as prose would flag every such reply
        text = "\n".join(["line %d" % i for i in range(20)]
                         + ["```", "pytest -q", "```"])
        self.assertEqual(ti.shape_flags(text), [])

    def test_the_flags_are_recorded_and_not_refused(self):
        # P4's whole choice in one test: a flagged reply passes, leaves its row,
        # and moves the counter - no block, and no claim row the rate divides by
        self.assertIsNone(self.stop(self.BAD))
        self.assertEqual(self.shape_rows(), ["table-open,recap-close"])
        self.assertEqual(self.counts()["shape"], 1)
        self.assertEqual(self.counts()["claims"], 0)

    def test_a_repeated_identical_reply_is_one_shape_row(self):
        # Cursor re-runs the Stop handler on a follow-up: the flag rate must not
        # grow with the host's retries, the reason the claim row dedups too
        self.stop(self.BAD)
        self.stop(self.BAD)
        self.assertEqual(self.counts()["shape"], 1)

    def test_a_good_reply_writes_an_unflagged_shape_row(self):
        # every judged reply leaves one row, so the flag rate has a denominator
        self.assertIsNone(self.stop(self.GOOD))
        self.assertEqual(self.shape_rows(), ["ok"])
        counts = self.counts()
        self.assertEqual((counts["shape"], counts["replies"]), (0, 1))

    # P5: the reply's size and lead ride the `claim` row `stop_reason` already
    # writes - `lines`, `chars`, `items`, `answer_first`, additively and on the
    # same row, no new kind - and nothing refuses on them. A five-item cap or a
    # lead that is not the answer cannot cost a turn until this row supplies the
    # rate that would justify it: the skill's own carve-outs (an explain/
    # walkthrough run, a question the user raised mid-work) both change what a
    # good reply looks like, so a refusal would be wrong before that rate exists.
    def test_the_claim_row_carries_the_replys_size_and_lead(self):
        text = ("| item | count |\n| --- | --- |\n| a | 1 |\n\n"
                "Done. All tests pass.")
        self.seed("Bash", {"command": "ls"})
        out = self.stop(text)
        self.assertEqual(out.get("decision"), "block")
        row = self.rows("claim")[0]
        self.assertEqual(row["detail"], "blocked: no verify_ok")
        self.assertEqual(row["lines"], 5)
        self.assertEqual(row["chars"], len(text))
        self.assertEqual(row["items"], 0)
        self.assertIs(row["answer_first"], False)

    def test_the_shape_fields_count_top_level_items_and_a_prose_lead(self):
        # a marker in column 0 is an item, an indented one belongs to the item
        # above it, and a `---` row of a table is neither
        text = ("Birinci bulgu.\n"
                "1. ilk adım\n"
                "2. ikinci adım\n"
                "  - girintili, sayılmaz\n"
                "| --- | --- |\n"
                "Next: run `pytest -q`.")
        shape = ti.reply_shape(text)
        self.assertEqual({k: shape[k] for k in ("lines", "items", "longest_list",
                                                "answer_first")},
                         {"lines": 6, "items": 2, "longest_list": 2,
                          "answer_first": True})

    # The shape blocks: a list over the cap (rule 8) and prose that is not
    # Turkish (the exec rule), each with its own switch.
    LONG_LIST = ("Yedi bulgu var:\n\n"
                 + "\n".join("%d. bulgu %d" % (i, i) for i in range(1, 8)))
    ENGLISH = ("Everything the omp session uses runs the checkout, and it is "
               "current. The live proof feeds the commands the session was "
               "refused on in September through the installed gate, and each "
               "one is refused again with the same reason.")

    def test_a_list_over_the_cap_blocks_with_its_size(self):
        out = self.stop(self.LONG_LIST)
        self.assertEqual(out.get("decision"), "block")
        self.assertIn("7 items", out["reason"])
        self.assertEqual(self.claim_rows(), ["blocked: list cap"])
        # a shape block is not a false completion: no claim was made
        counts = self.counts()
        self.assertEqual((counts["shape_blocked"], counts["false_completion"]),
                         (1, 0))

    def test_the_adhd_switches_lift_the_shape_blocks(self):
        # `adhd-off` removes the output-shape text, so it removes its blocks too
        self.touch(os.path.join(self.home, ".config", "tezgah", "adhd-off"))
        self.assertIsNone(self.stop(self.LONG_LIST))
        self.assertIsNone(self.stop("Let me check. Toplam 5 dosya."))

    def test_a_repos_no_adhd_mark_lifts_them_there(self):
        self.touch(os.path.join(self.repo, ".no-adhd"))
        self.assertIsNone(self.stop(self.LONG_LIST))

    def test_english_prose_blocks_and_names_the_language(self):
        out = self.stop(self.ENGLISH)
        self.assertEqual(out.get("decision"), "block")
        self.assertIn("Turkish", out["reason"])
        self.assertEqual(self.claim_rows(), ["blocked: reply language"])

    def test_the_exec_switch_lifts_the_language_block(self):
        self.touch(os.path.join(self.home, ".config", "tezgah", "exec-mode.off"))
        self.assertIsNone(self.stop(self.ENGLISH))

    def test_a_nested_tezgah_session_is_not_judged_for_shape(self):
        # consult runs agent CLIs with TEZGAH_NESTED=1: their English answer is
        # read by code, not by the user
        payload = {"hook_event_name": "Stop", "cwd": self.repo,
                   "session_id": self.session,
                   "last_assistant_message": self.ENGLISH}
        out, _ = run_json([support.STOP_HOOK], payload,
                          env=dict(self.envv, TEZGAH_NESTED="1"))
        self.assertIsNone(out)

    def test_stop_hook_active_passes(self):
        self.seed("Bash", {"command": "ls"})
        self.assertIsNone(self.stop("Done.", stop_hook_active=True))

    def test_verify_off_kill_switch(self):
        self.touch(os.path.join(self.home, ".config", "tezgah", "verify-off"))
        self.seed("Edit", {"file_path": "x.py"})
        self.assertIsNone(self.stop("Done. All tests pass."))

    def test_outside_root_passes(self):
        payload = {"hook_event_name": "Stop", "cwd": self.home,
                   "session_id": self.session,
                   "last_assistant_message": "Done."}
        out, _ = run_json([support.STOP_HOOK], payload, env=self.envv)
        self.assertIsNone(out)

    # The tenth Stop class: a reply that states the state of a system tezgah
    # does not own - a registry, a release, a tag, a formula, a CI run - is making
    # a claim it cannot have from here. The two turns this class comes from
    # ("npm 0.22.0 is missing", read off an out-of-date local npm client, and
    # "make NPM_TOKEN an automation token", which it already was) were both
    # advice-only: no work and no completion word, so the fold returned
    # (None, None) and neither was judged at all. The repair is an external read
    # and never a reflection - a self-critique pass with no new signal is
    # measured to leave a wrong answer more convincing than it started
    # (arXiv:2310.01798) - so the class asks for the command and names it.
    RELEASED = "npm 0.22.0 yayımlanmadı, registry'de böyle bir sürüm yok."
    TAGGED = "v0.23.0 etiketi yok, release oluşturulmamış."
    RED = "CI kırmızı, workflow başarısız görünüyor."
    ADVICE = ("Sıradaki adım: `npm publish` çalıştır, sonra sürümü 0.23.0'a "
              "yükselt.")

    def test_an_external_claim_with_no_read_is_refused(self):
        out = self.stop(self.RELEASED)
        self.assertEqual(out.get("decision"), "block")
        self.assertIn("npm view", out["reason"])
        self.assertEqual(self.claim_rows(), ["blocked: no external read"])

    def test_the_read_of_the_named_system_licenses_the_claim(self):
        for command, reply in (("npm view tezgah versions --json", self.RELEASED),
                               ("gh release view v0.23.0", self.TAGGED),
                               ("gh run list --limit 5", self.RED)):
            self.turn()
            self.seed("Bash", {"command": command})
            self.assertIsNone(self.stop(reply), command)
        self.assertEqual(self.claim_rows(), [])

    def test_a_claim_inside_inline_code_is_not_this_replys_claim(self):
        # the subject is read on the reply's prose: a command quoted in a code
        # span is text about a system, not a statement about its state
        self.assertIsNone(self.stop("`brew tap` çıktısı boş kaldı, kayıt yok."))

    def test_a_ci_status_claim_owes_the_run_list(self):
        # the run-status words pair with a CI subject alone; this is the shape
        # the pair is for
        out = self.stop(self.RED)
        self.assertEqual(out.get("decision"), "block")
        self.assertIn("gh run list", out["reason"])
        self.assertEqual(self.claim_rows(), ["blocked: no external read"])

    def test_a_run_word_without_a_ci_subject_is_not_a_claim(self):
        # the control for the split: `green` beside `release` is prose, and
        # reading it as a CI state refused honest summaries
        self.assertIsNone(self.stop("Suite green, release ready."))

    def test_a_local_client_read_is_not_the_registry_read(self):
        # the incident's own shape: `npm --version` asks the box, not the
        # registry, so it is not the read this class asks for - and the green
        # unit run beside it does not answer a claim about npm either
        self.seed("Bash", {"command": "pytest -q"})
        self.seed("Bash", {"command": "npm --version"})
        out = self.stop(self.RELEASED)
        self.assertEqual(out.get("decision"), "block")
        self.assertIn("npm view", out["reason"])
        self.assertEqual(self.claim_rows(), ["blocked: no external read"])

    def test_a_search_that_names_the_read_is_not_the_read(self):
        # the convention every other command reader follows: a quoted pattern is
        # text about a command, not a run of it
        self.seed("Bash", {"command": 'rg -n "npm view" docs/'})
        self.assertEqual(self.stop(self.RELEASED).get("decision"), "block")

    def test_an_honest_advice_only_reply_is_not_refused(self):
        # the negative control: naming npm, a version and a tag in a next step
        # states no state of the registry
        self.assertIsNone(self.stop(self.ADVICE))
        self.assertEqual(self.claim_rows(), [])

    def test_the_repositorys_own_version_is_not_a_claim(self):
        # a version number of tezgah's own code is not a claim about a system
        # tezgah does not own
        self.assertIsNone(self.stop(
            "tezgah 0.22.0 sürümü hazır, numara pyproject.toml içinde.\n"
            "Sıradaki adım: changelog'u güncelle."))

    def test_the_admission_clears_the_external_class_too(self):
        self.assertIsNone(self.stop(
            "npm 0.22.0 registry'de yok gibi görünüyor. doğrulanmadı."))
        self.assertEqual(self.claim_rows(), [])

    def test_a_fresh_check_does_not_license_an_external_claim(self):
        # the class is about the claim's object, not about the turn's work: a
        # green suite says nothing about what npm publishes
        self.seed("Edit", {"file_path": "x.py"})
        self.seed("Bash", {"command": "pytest -q"})
        self.assertEqual(self.stop(self.RELEASED).get("decision"), "block")
        self.assertEqual(self.claim_rows(), ["blocked: no external read"])

    def test_a_turn_with_unverified_work_keeps_its_own_class(self):
        # branch order: the new class sat after every evidence class, so a turn
        # the fold was already refusing is refused under its own class
        self.seed("Edit", {"file_path": "x.py"})
        self.assertEqual(self.stop(self.RELEASED).get("decision"), "block")
        self.assertEqual(self.claim_rows(), ["blocked: no verify_ok"])

    def test_a_stale_check_keeps_its_own_class_too(self):
        # a real write after the check, so the check is stale and the fold's own
        # class is the one the ledger records
        path = os.path.join(self.repo, "x.py")
        with open(path, "w") as fh:
            fh.write("v1\n")
        self.seed("Bash", {"command": "pytest -q"})
        self.seed("Edit", {"file_path": path})
        self.assertEqual(self.stop(self.RELEASED).get("decision"), "block")
        self.assertEqual(self.claim_rows(), ["blocked: stale evidence"])

    def test_the_class_counts_as_a_false_completion(self):
        # V3: the class is reached by `counters`, and it is not a shape class -
        # a reply refused here made a claim about the world that nothing checked
        self.stop(self.RELEASED)
        counts = self.counts()
        self.assertEqual((counts["claims"], counts["false_completion"],
                          counts["shape_blocked"], counts["replies"]), (1, 1, 0, 1))


class ReplyShapeCorpus(unittest.TestCase):
    """The two blocking shape numbers over realistic replies: which ones the
    thresholds refuse. The Turkish replies are the owner's own style - Turkish
    prose dense with English identifiers, quoted English titles, code blocks -
    because those are the replies a language check can wrongly refuse."""

    PASS = {
        "turkish with identifiers and a short list": (
            "Stop kuralı artık beşten uzun listeyi ve Türkçe olmayan düzyazıyı "
            "engelliyor; `tests/test_integrity.py` içindeki korpus testi yeşil.\n\n"
            "1. `hooks/tezgah_integrity.py:1802` liste sınırı\n"
            "2. `hooks/tezgah_integrity.py:1860` dil kontrolü\n"
            "3. `hosts/omp/hook.py` subagent yönlendirmesi\n\n"
            "Sıradaki adım: `python3 -m unittest test_integrity` çalıştır."),
        "turkish around a quoted english sentence": (
            "Düzeltildi: repo açıklaması artık \"One shared working contract for "
            "every AI coding assistant you run: Claude Code, Codex, Cursor, "
            "opencode, dsh and oh-my-pi (omp).\""),
        "turkish around english titles": (
            "lit2b dolu (tam isabet: \"A Few Pages of Markdown Committed AI "
            "Configuration\", \"The reach of a verification tool decides its "
            "value\"). Kalan iki sorguyu koşuyorum."),
        "turkish prose over an english code block": (
            "Hata `auth.spec.ts:42` satırında: başlık eksik.\n\n```\n"
            "Error: expected 200 but the server answered 401 because the "
            "request carried no Authorization header and the middleware "
            "rejected it before the handler ran at all\n```\n\n"
            "Düzeltme: isteğe başlığı ekle."),
        "short english claim": "Done. All tests pass.",
        "two headed groups of four": (
            "## Açık\n- a\n- b\n- c\n- d\n\n## Kapalı\n- e\n- f\n- g\n- h"),
        "a restarted numbered list": (
            "1. bir\n2. iki\n3. üç\n\nSonra:\n\n1. dört\n2. beş\n3. altı"),
        "nested items under five": (
            "- a\n  - a1\n  - a2\n- b\n  - b1\n- c\n- d\n- e"),
        "a long list inside a fence": (
            "Çıktı:\n\n```\n" + "\n".join("- satır %d" % i for i in range(9))
            + "\n```"),
    }
    BLOCK = {
        "english prose": (
            "Both commits are pushed to origin, and local main now matches the "
            "remote. Your edit is still local and uncommitted; the push did not "
            "include it, so restart the host once to load the new hooks."),
        "english that quotes a turkish word": (
            "The reply says the check was not run and marks it doğrulanmadı, "
            "which is the one escape the rule allows, so the turn passes and "
            "the claim row records ok for the counter to read later."),
        "six ranked items": "\n".join("%d. madde" % i for i in range(1, 7)),
        "seven bullets across blank lines": "\n\n".join(
            "- madde %d" % i for i in range(7)),
    }

    def blocked(self, text):
        # the real rule, every switch armed and no nested-session marker
        env = {k: v for k, v in os.environ.items() if k != "TEZGAH_NESTED"}
        with mock.patch.object(ti, "off", return_value=False), \
                mock.patch.dict(os.environ, env, clear=True):
            return ti._shape_block(text, None)[0] is not None

    def test_the_turkish_and_structured_replies_pass(self):
        wrong = [name for name, text in self.PASS.items() if self.blocked(text)]
        self.assertEqual(wrong, [])

    def test_the_english_and_long_list_replies_block(self):
        wrong = [name for name, text in self.BLOCK.items()
                 if not self.blocked(text)]
        self.assertEqual(wrong, [])

    def test_a_preamble_lead_is_flagged_and_an_answer_is_not(self):
        self.assertIn("preamble-open",
                      ti.shape_flags("Here is what changed:\n\n- a\n- b"))
        self.assertIn("preamble-open",
                      ti.shape_flags("Değişenler şunlar:\n- a\n- b"))
        self.assertEqual(ti.shape_flags("Üç dosya değişti.\n- a\n- b"), [])


class PromptTurn(TempHome):
    """The prompt path writes the turn marker the loop guard resets on.

    `context_for` is the one funnel every host's user_prompt event goes through
    (Claude's projects-auto-init.py, codex/hook.py, cursor/hook.py, omp/hook.py,
    and opencode through bin/tezgah-context), so the marker is written there."""

    def setUp(self):
        super().setUp()
        self.repo = self.make_repo("proj")
        self.envv = self.env()
        self.session = "turn-s"

    def prompt(self, **extra):
        payload = {"hook_event_name": "UserPromptSubmit", "cwd": self.repo,
                   "session_id": self.session, "prompt": "run the tests again"}
        payload.update(extra)
        out, proc = run_json([support.AUTO_INIT], payload, env=self.envv)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        return out

    def marks(self):
        out, _ = run_json([support.PROBE_INTEGRITY],
                          {"fn": "events", "session": self.session},
                          env=self.envv)
        return [row for row in out if row["kind"] == "turn"]

    def test_one_prompt_writes_one_marker(self):
        self.prompt()
        self.assertEqual(len(self.marks()), 1)

    def test_the_same_submission_twice_writes_one_marker(self):
        # a host that hands the hook the same submission again (a retry, a
        # resume) must not drop a second marker: the newer marker would start the
        # guard's window after the failures it had just counted
        self.prompt()
        self.prompt()
        self.assertEqual(len(self.marks()), 1)

    def test_the_marker_carries_no_prompt_text(self):
        self.prompt(prompt="change the password to hunter2")
        self.assertNotIn("hunter2", json.dumps(self.marks()))

    def test_every_prompt_path_writes_the_marker_under_its_gate_id(self):
        # one funnel, four envelopes. Whatever the host names the event and the
        # session field, the marker has to land in the ledger the shared readers
        # open for that id - a marker under another id resets nothing.
        for hook, event, id_key in ((support.AUTO_INIT, "UserPromptSubmit",
                                     "session_id"),
                                    (support.CODEX_HOOK, "UserPromptSubmit",
                                     "session_id"),
                                    (support.CURSOR_HOOK, "beforeSubmitPrompt",
                                     "conversation_id"),
                                    (support.OMP_HOOK, "user_prompt",
                                     "session_id")):
            session = "turn-%s" % hook.replace(os.sep, "-")
            payload = {"cwd": self.repo, "prompt": "run the tests again",
                       id_key: session}
            payload.update({"event": event} if hook == support.OMP_HOOK
                           else {"hook_event_name": event})
            out, proc = run_json([hook], payload, env=self.envv)
            self.assertEqual(proc.returncode, 0, proc.stderr)
            rows, _ = run_json([support.PROBE_INTEGRITY],
                               {"fn": "events", "session": session},
                               env=self.envv)
            self.assertEqual([row["kind"] for row in rows], ["turn"], hook)


class SessionId(unittest.TestCase):
    """session_of: the marker has to key the ledger the gate reads.

    A marker written under an id the PreToolUse hook never uses lands in another
    file and resets nothing, so this is the host payload shapes' one contract."""

    def test_each_host_payload_shape_yields_the_id_its_gate_gets(self):
        # Claude, Codex and omp send session_id; Cursor's adapter reads
        # conversation_id first and falls back to session_id / parent
        cases = (({"session_id": "s-1"}, "s-1"),
                 ({"conversation_id": "c-1"}, "c-1"),
                 ({"conversation_id": "c-1", "session_id": "s-9"}, "c-1"),
                 ({"parent_conversation_id": "p-1"}, "p-1"),
                 ({}, None), (None, None))
        for payload, want in cases:
            self.assertEqual(tc.session_of(payload), want, payload)


class CompactRecord(TempHome):
    """What a compaction kept, from the record.

    Claude hands the PostCompact hook the text the model is about to be given
    (`compact_summary`) and a `trigger`. The row keeps the summary's size and a
    12-hex digest, plus how many of the constraint lines tezgah injected (the
    pointer line, the active plan's line) survived in it - never the text: the
    ledger is a redacted channel and the summary is the whole conversation. It is
    a report, so no row here refuses anything."""

    PLAN = ("---\nid: 021\ntitle: a thing\n---\n## Goal\nx\n"
            "## State\nhalf done\n## Next\nwire it\n")
    SUMMARY = ("The session compacted. The next step is wiring the second half "
               "of plan 021, per the tezgah-contract skill.")

    def setUp(self):
        super().setUp()
        self.repo = self.make_repo("proj")
        self.envv = self.env()
        self.session = "compact-s"
        path = os.path.join(self.repo, ".tezgah", "plans", "open",
                            "021-thing.md")
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w") as fh:
            fh.write(self.PLAN)

    def compact(self, event="PostCompact", **extra):
        payload = {"hook_event_name": event, "cwd": self.repo,
                   "session_id": self.session}
        payload.update(extra)
        out, proc = run_json([support.AUTO_INIT], payload, env=self.envv)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        return out

    def rows(self):
        out, _ = run_json([support.PROBE_INTEGRITY],
                          {"fn": "events", "session": self.session},
                          env=self.envv)
        return [row for row in (out or []) if row["kind"] == "compact"]

    def counts(self, session=None):
        out, _ = run_json([support.PROBE_INTEGRITY],
                          {"fn": "counters", "session": session or self.session},
                          env=self.envv)
        return out

    def counts_for(self, summary):
        self.compact(compact_summary=summary, trigger="auto")
        return self.rows()[-1]

    def test_a_compact_summary_writes_one_row_of_size_digest_and_kind(self):
        self.compact(compact_summary=self.SUMMARY, trigger="auto")
        rows = self.rows()
        self.assertEqual(len(rows), 1, rows)
        self.assertEqual(rows[0]["summary_chars"], len(self.SUMMARY))
        self.assertEqual(rows[0]["summary_hash"],
                         hashlib.sha256(self.SUMMARY.encode()).hexdigest()[:12])
        # the host's own word for why it compacted is the row's free text
        self.assertEqual(rows[0]["detail"], "auto")

    def test_a_compact_with_no_summary_writes_no_row(self):
        # a host that hands the hook no summary has nothing to record, and an
        # empty row would count as a compaction that kept nothing
        self.compact(trigger="auto")
        self.compact(compact_summary="", trigger="manual")
        self.assertEqual(self.rows(), [])

    def test_the_summary_body_never_reaches_the_ledger(self):
        secret = "the passphrase is hunter2-sw0rdf1sh"
        self.compact(compact_summary=self.SUMMARY + " " + secret, trigger="auto")
        self.assertNotIn("hunter2", json.dumps(self.rows()))
        self.assertEqual(len(self.rows()), 1)

    def test_the_compact_row_counts_the_constraint_lines_that_survived(self):
        # the pointer line and the active plan's line are the two fixed
        # sentences tezgah injects, so the count is found over expected
        for summary, want in ((self.SUMMARY, (2, 2)),
                              ("nothing of ours survived it", (0, 2)),
                              ("still on the tezgah-contract skill", (1, 2))):
            row = self.counts_for(summary)
            self.assertEqual((row["constraint_found"],
                              row["constraint_expected"]), want, summary)

    def test_a_resume_writes_no_compact_row(self):
        # the summary is PostCompact's field; a SessionStart resume carries none
        # even when a host hands it the same payload
        self.compact(event="SessionStart", compact_summary=self.SUMMARY,
                     trigger="auto")
        self.assertEqual(self.rows(), [])

    def test_counters_fold_the_compact_rows(self):
        self.compact(compact_summary=self.SUMMARY, trigger="auto")   # 2 of 2
        self.compact(compact_summary="x" * 40, trigger="manual")     # 0 of 2
        counts = self.counts()
        self.assertEqual(counts["compactions"], 2)
        # the newest summary's length, and the hit rate over both rows
        self.assertEqual(counts["compact_chars"], 40)
        self.assertEqual(counts["compact_constraint_rate"], 0.5)

    def test_a_session_with_no_compaction_reports_an_unknown_rate(self):
        # a zero would read as "every compaction kept nothing", which is a
        # different claim from "no compaction was ever recorded here"
        counts = self.counts(session="quiet-s")
        self.assertEqual(counts["compactions"], 0)
        self.assertIsNone(counts["compact_chars"])
        self.assertIsNone(counts["compact_constraint_rate"])


class PostToolUse(TempHome):
    def setUp(self):
        super().setUp()
        self.repo = self.make_repo("proj")
        self.envv = self.env()
        self.session = "s-ptu"

    def run_hook(self, event, tool, inp, **extra):
        payload = {"hook_event_name": event, "cwd": self.repo,
                   "session_id": self.session, "tool_name": tool,
                   "tool_input": inp}
        payload.update(extra)
        out, proc = run_json([support.POSTTOOLUSE], payload, env=self.envv)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        return out

    def kinds(self):
        out, _ = run_json([support.PROBE_INTEGRITY],
                          {"fn": "kinds", "session": self.session},
                          env=self.envv)
        return out

    def rows(self, tail=None):
        out, _ = run_json([support.PROBE_INTEGRITY],
                          {"fn": "events", "session": self.session, "tail": tail},
                          env=self.envv)
        return out

    def write_row(self, kind, detail):
        run_json([support.PROBE_INTEGRITY],
                 {"fn": "note", "session": self.session, "kind": kind,
                  "detail": detail}, env=self.envv)

    def test_the_same_call_gets_the_same_id(self):
        # the digest is the collapsed command, so re-typing the spacing is the
        # same action and a different command is not
        self.run_hook("PostToolUse", "Bash", {"command": "pytest -q"})
        self.run_hook("PostToolUse", "Bash", {"command": "pytest  -q"})
        self.run_hook("PostToolUse", "Bash", {"command": "pytest tests/"})
        first, second, third = self.rows()
        self.assertEqual(first["id"], second["id"])
        self.assertNotEqual(first["id"], third["id"])
        self.assertEqual(len(first["id"]), 12)

    def test_a_row_carries_the_outcome_the_result_size_and_the_workspace(self):
        result = "11 passed in 0.2s"
        self.run_hook("PostToolUse", "Bash", {"command": "pytest -q"},
                      tool_response=result)
        self.run_hook("PostToolUseFailure", "Bash", {"command": "pytest -q"},
                      error="Command timed out after 2m")
        ok, bad = self.rows()
        self.assertEqual((ok["exit"], ok["out_bytes"], ok.get("fail_class")),
                         (0, len(result), None))
        self.assertEqual(ok["workspace"], self.roots)
        self.assertEqual((bad["exit"], bad.get("out_bytes"), bad["fail_class"]),
                         (1, None, "transient"))
        self.assertNotIn("[exit=0]", ok["detail"])

    def test_a_structured_result_is_measured_and_not_stored(self):
        # most tools answer with an object; the ledger keeps a size and never the
        # result itself. A container is measured by its top-level length so the
        # hook does not re-serialize the whole response on every call.
        result = {"stdout": "x" * 10, "stderr": ""}
        self.run_hook("PostToolUse", "Bash", {"command": "ls"},
                      tool_response=result)
        row = self.rows()[-1]
        self.assertEqual(row["out_bytes"], len(result))
        self.assertNotIn("stdout", json.dumps(row))

    def test_a_subagent_result_row_carries_the_report_s_byte_length(self):
        # The one structured result measured by its text: a subagent's report is
        # what this session pays to read, so its row carries the UTF-8 byte
        # length of the report's text parts - not the object's field count,
        # which is what every other structured result records.
        text = "bulgu: çalışıyor"
        self.run_hook("PostToolUse", "Agent", {"prompt": "look"},
                      tool_response={"status": "completed", "totalTokens": 9,
                                     "content": [{"type": "text", "text": text},
                                                 {"type": "text", "text": "ok"}]})
        row = self.rows()[-1]
        self.assertEqual((row["kind"], row["source"], row["out_bytes"]),
                         ("external", "subagent", len(text.encode("utf-8")) + 2))
        self.assertNotIn("bulgu", json.dumps(row))

    def test_a_piped_check_is_recorded_as_ran(self):
        self.run_hook("PostToolUse", "Bash", {"command": "pytest -q | tail -1"})
        self.assertEqual(self.kinds(), ["verify"])

    def test_counters_report_the_trace_metrics(self):
        # steps counts the work rows (a run, an edit, a check) and not the two
        # claim rows this ledger also holds; the error rate is over the rows
        # whose outcome the host reported; false_completion is the refused share
        # of the claims
        self.run_hook("PostToolUse", "Bash", {"command": "pytest -q"})
        self.run_hook("PostToolUseFailure", "Bash", {"command": "ls"})
        self.write_row("claim", "blocked: This turn claims done/tested/passing")
        self.write_row("claim", "ok")
        counts = self.counters()
        self.assertEqual(counts["steps"], 2)
        self.assertEqual(counts["events"], 4)
        self.assertEqual(counts["tool_error_rate"], 0.5)
        self.assertEqual(counts["claims"], 2)
        self.assertEqual(counts["false_completion"], 1)

    def test_every_reported_exit_counts_in_the_error_rate(self):
        # opencode's writer stores the real process code, so 2/127/130 are errors
        # and belong in both halves; a row with no outcome is not a decided
        # attempt at all
        for code in (2, 0, None):
            run_json([support.PROBE_INTEGRITY],
                     {"fn": "note", "session": self.session, "kind": "run",
                      "detail": "x", "exit": code}, env=self.envv)
        self.assertEqual(self.counters()["tool_error_rate"], 0.5)

    def test_bash_check_records_verify_ok(self):
        self.run_hook("PostToolUse", "Bash", {"command": "pytest -q"})
        self.assertIn("verify_ok", self.kinds())

    def test_bash_failure_records_verify_fail(self):
        self.run_hook("PostToolUseFailure", "Bash", {"command": "pytest -q"})
        self.assertIn("verify_fail", self.kinds())

    def test_a_check_named_in_a_message_is_not_a_check(self):
        # The scan runs on the masked text, the convention `shortcut_command`
        # follows: a check named inside a commit message is text ABOUT a command,
        # not one. Unmasked, both of these recorded `verify_ok` - and this
        # session's own ledger then had a `git commit` as its newest passing
        # check, which is what the Stop rule read when it refused a reply.
        self.run_hook("PostToolUse", "Bash",
                      {"command": "git commit -m \"run pytest before this\""})
        self.run_hook("PostToolUse", "Bash",
                      {"command": "git commit -F - <<'MSG'\nrun pytest\nMSG"})
        self.assertNotIn("verify_ok", self.kinds())

    def test_a_pwsh_call_is_a_shell_call(self):
        # dsh names its own PowerShell tool `pwsh`; while the name was outside
        # BASH_TOOLS the call reached the hook as a name no list knew and was
        # recorded `unknown`, so no shell rule and no step counter saw it
        self.run_hook("PostToolUse", "pwsh", {"command": "pytest -q"})
        self.assertEqual(self.kinds(), ["verify_ok"])

    def test_non_check_command_records_run(self):
        self.run_hook("PostToolUse", "Bash", {"command": "ls -la"})
        self.assertIn("run", self.kinds())

    def test_edit_records_edit(self):
        self.run_hook("PostToolUse", "Edit", {"file_path": "/tmp/x.py"})
        self.assertIn("edit", self.kinds())

    def test_a_tool_name_no_rule_knows_is_recorded_by_name(self):
        # B3: `classify` returns None for a name outside every list, so the call
        # left no ledger line at all and a fabricated tool was invisible in the
        # trace it exists to be in. The kind says unclassified, the detail names
        # the tool.
        self.run_hook("PostToolUse", "Fabricated", {"whatever": 1})
        rows = self.rows()
        self.assertEqual([(r["kind"], r["detail"]) for r in rows],
                         [("unknown", "unknown tool: Fabricated")])
        self.assertEqual(len(rows[-1]["id"]), 12)

    def test_an_unknown_row_is_not_a_step_of_work(self):
        # the counters and the Stop rule read the step set; an unclassified call
        # claims no work there, or every fabricated name would look like progress
        self.run_hook("PostToolUse", "Fabricated", {})
        self.assertEqual(self.counters()["steps"], 0)

    def test_a_read_tool_still_writes_no_row(self):
        # the row is for a name nothing classifies. The read/search tools are
        # known calls that do no step of work, and a row each would bury the work
        # rows every reader scans for.
        for tool in ("Read", "Grep", "Glob", "LS", "read", "grep", "glob",
                     "read_file", "list_dir", "search_files"):
            self.run_hook("PostToolUse", tool, {"file_path": "x"})
        self.assertEqual(self.kinds(), [])

    def test_unknown_outcome_records_a_run_not_a_pass(self):
        # a host that reports no exit status must never write verify_ok
        run_json([support.PROBE_INTEGRITY],
                 {"fn": "note_tool", "session": self.session, "tool": "Bash",
                  "input": {"command": "pytest -q"}, "failed": None},
                 env=self.envv)
        self.assertEqual(self.kinds(), ["verify"])

    def test_a_host_that_reports_no_outcome_writes_no_exit(self):
        # Cursor's postToolUse/afterShellExecution calls pass no failure signal
        # at all: a `failed=False` default fabricated exit 0 for them, so a
        # failing check landed as verify_ok and the Stop rule accepted the claim
        run_json([support.PROBE_INTEGRITY],
                 {"fn": "note_tool", "session": self.session, "tool": "Bash",
                  "input": {"command": "pytest -q"}}, env=self.envv)
        row = self.rows()[-1]
        self.assertEqual(row["kind"], "verify")
        self.assertNotIn("exit", row)

    def test_an_interrupted_step_is_not_a_failed_check(self):
        # Claude reports a user's cancel on PostToolUseFailure as `is_interrupt`
        # ("an abort rather than an error the tool reported"). Written as a
        # failure it armed the Stop rule's partial-failure branch, counted an
        # exit 1 in the error rate and spent a loop-guard attempt, for a check
        # nobody saw fail. It is still a step - the turn did act - so the reply
        # is refused by the "run the check" floor and not by "partial failure".
        self.run_hook("PostToolUseFailure", "Bash", {"command": "pytest -q"},
                      is_interrupt=True)
        row = self.rows()[-1]
        self.assertEqual(row["kind"], "interrupted")
        self.assertNotIn("exit", row)
        self.assertNotIn("fail_class", row)
        counts = self.counters()
        self.assertEqual(counts["steps"], 1)
        self.assertIsNone(counts["tool_error_rate"])
        reason, _ = run_json([support.PROBE_INTEGRITY],
                             {"fn": "stop_reason", "session": self.session,
                              "text": "Done. All tests pass."}, env=self.envv)
        claim = [r for r in self.rows() if r["kind"] == "claim"][-1]
        self.assertEqual(claim["detail"], "blocked: no verify_ok")
        self.assertIn("no check ran successfully", reason)

    def test_a_bash_result_the_host_marks_interrupted_is_not_a_pass(self):
        # Claude's Bash result carries `interrupted`: a command the user stopped
        # still returns a result envelope, and reading that as a pass licensed a
        # "done" over a run that was cut off.
        self.run_hook("PostToolUse", "Bash", {"command": "pytest -q"},
                      tool_response={"stdout": "", "interrupted": True})
        row = self.rows()[-1]
        self.assertEqual(row["kind"], "interrupted")
        self.assertNotIn("exit", row)
        self.assertEqual(self.kinds(), ["interrupted"])

    def test_an_interrupted_call_is_not_an_attempt_the_loop_guard_counts(self):
        # `prior_calls` counts only the rows that carry an `exit`, so an
        # interruption spends no retry: a cancel is not a rejected call, and both
        # ceilings count repeats of a call that ran.
        self.run_hook("PostToolUseFailure", "Bash", {"command": "pytest -q"},
                      is_interrupt=True)
        digest = self.rows()[-1]["id"]
        out, _ = run_json([support.PROBE_INTEGRITY],
                          {"fn": "prior_calls", "session": self.session,
                           "id": digest}, env=self.envv)
        self.assertEqual(out, [0, 0, None, None])

    def test_outside_root_records_nothing(self):
        run_json([support.POSTTOOLUSE],
                 {"hook_event_name": "PostToolUse", "cwd": self.home,
                  "session_id": self.session, "tool_name": "Bash",
                  "tool_input": {"command": "pytest"}}, env=self.envv)
        self.assertEqual(self.kinds(), [])

    def counters(self):
        out, _ = run_json([support.PROBE_INTEGRITY],
                          {"fn": "counters", "session": self.session},
                          env=self.envv)
        return out

    def test_counters_aggregate_what_the_ledger_saw(self):
        # A gate refusal, a nudge, a passing check, a consult call and a codegen
        # call that exited 2 - the numbers the report needs, from one ledger.
        self.run_hook("PostToolUse", "Bash", {"command": "pytest -q"})
        run_json([support.PROBE_INTEGRITY],
                 {"fn": "note", "session": self.session, "kind": "deny",
                  "detail": "attribution: Attribution is banned"}, env=self.envv)
        run_json([support.PROBE_INTEGRITY],
                 {"fn": "note", "session": self.session, "kind": "nudge",
                  "detail": "proj"}, env=self.envv)
        run_json([support.PROBE_INTEGRITY],
                 {"fn": "note_tool", "session": self.session, "tool": "Bash",
                  "input": {"command": "consult 'is this safe?'"}, "failed": False},
                 env=self.envv)
        run_json([support.PROBE_INTEGRITY],
                 {"fn": "note_tool", "session": self.session, "tool": "Bash",
                  "input": {"command": "codegen 'x' --files a.py"}, "failed": True},
                 env=self.envv)

        counts = self.counters()
        self.assertEqual(counts["denies"], {"attribution": 1})
        self.assertEqual(counts["nudges"], 1)
        self.assertEqual(counts["consult"], 1)
        self.assertEqual(counts["codegen"], 1)
        self.assertEqual(counts["codegen_failed"], 1)
        self.assertEqual(counts["kinds"]["verify_ok"], 1)
        self.assertEqual(counts["events"], 5)

    def test_an_unreported_outcome_is_not_counted_as_a_failure(self):
        run_json([support.PROBE_INTEGRITY],
                 {"fn": "note_tool", "session": self.session, "tool": "Bash",
                  "input": {"command": "codegen 'x'"}, "failed": None},
                 env=self.envv)
        self.assertEqual(self.counters()["codegen_failed"], 0)

    def test_a_judgement_is_counted_and_is_not_a_step(self):
        # J4: the row is the seam's cost, counted on its KIND. It is neither a
        # step nor a check (STEP_KINDS is untouched), so a judgement can never
        # make a "done" claim look backed.
        self.write_row("judge", "tezgah-triage jev-latest in=900 out=4 ms=820")
        counts = self.counters()
        self.assertEqual(counts["judge"], 1)
        self.assertEqual(counts["steps"], 0)
        self.assertEqual(counts["events"], 1)

    def test_a_row_that_merely_says_judge_is_not_a_judgement(self):
        # the consult and codegen keys count a `detail` substring; a judgement
        # must not, or a commit message that says "judge" buys a cost that
        # never happened
        self.write_row("run", "git commit -m 'judge: name the off button'")
        self.assertEqual(self.counters()["judge"], 0)

    def test_the_drift_refusal_is_a_denial_and_not_evidence(self):
        # The re-statement is a refusal (an internal plan's pre-registered revert), so
        # the fold that reads denials by rule counts it under `drift`, and the
        # marker row beside it is the once-per-turn state alone: neither is a
        # step of work (a step would help a "done" claim look backed). The
        # result channel carries no second copy of it.
        for i in range(30):
            self.write_row("run", "step %d" % i)
        edit = {"file_path": "a.py", "old_string": "x", "new_string": "y"}
        out = self.run_hook("PostToolUse", "Edit", edit)
        self.assertNotIn("Long turn", json.dumps(out or {}))
        before = self.counters()
        out, proc = run_json([support.PRETOOLUSE],
                             {"hook_event_name": "PreToolUse", "cwd": self.repo,
                              "session_id": self.session, "tool_name": "Edit",
                              "tool_input": edit}, env=self.envv)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("Long turn",
                      out["hookSpecificOutput"]["permissionDecisionReason"])
        after = self.counters()
        marker = [r for r in self.rows() if r["kind"] == "drift"]
        self.assertEqual(len(marker), 1, marker)
        self.assertEqual(marker[0]["detail"], "31")
        self.assertEqual(marker[0]["workspace"], self.roots)
        self.assertEqual(after["kinds"].get("drift"), 1)
        self.assertEqual(after["denies"].get("drift"), 1, after["denies"])
        self.assertEqual(after["steps"], before["steps"], after)


class CountersAll(TempHome):
    """C14: the headline rate is a corpus question, over more than one ledger."""

    def setUp(self):
        super().setUp()
        self.evidence = os.path.join(self.home, ".cache", "tezgah", "evidence")
        os.makedirs(self.evidence)
        self.envv = self.env()
        self.cli = os.path.join(support.REPO, "bin", "tezgah-status")

    def ledger(self, name, rows):
        path = os.path.join(self.evidence, name)
        for row in rows:
            ti.note_path(path, **row)

    def counts(self, extra_env=None):
        env = self.envv if extra_env is None else dict(self.envv, **extra_env)
        out, proc = run_json([self.cli, "--counters", "--all", "--json"], env=env)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        return out

    def test_the_fold_totals_the_two_ledgers(self):
        # one ledger with a claim row that passed and a gate refusal, one with a
        # refused claim and a second refusal under the same rule: the number the
        # single-session reader cannot give is the sum of both
        self.ledger("a.jsonl", [
            {"kind": "run", "detail": "ls", "exit": 0},
            {"kind": "verify_ok", "detail": "pytest -q", "exit": 0},
            {"kind": "deny", "detail": "task: no active task"},
            {"kind": "deny", "detail": "shortcut: rewrote the check"},
            {"kind": "claim", "detail": "ok"},
        ])
        self.ledger("b.jsonl", [
            {"kind": "verify_fail", "detail": "pytest -q", "exit": 1},
            {"kind": "deny", "detail": "task: no active task"},
            {"kind": "claim", "detail": "blocked: stale evidence"},
        ])
        counts = self.counts()
        self.assertEqual(counts["ledgers"], 2)
        self.assertEqual(counts["events"], 8)
        self.assertEqual(counts["steps"], 3)
        self.assertEqual(counts["claims"], 2)
        self.assertEqual(counts["false_completion"], 1)
        # grouped by the rule name before the colon, as counters groups them
        self.assertEqual(counts["denies"], {"task": 2, "shortcut": 1})
        self.assertEqual(counts["kinds"]["claim"], 2)
        # one of the three rows carrying an exit failed
        self.assertEqual(counts["tool_error_rate"], 0.3333)

    def test_a_denied_call_issued_again_counts_under_its_rule(self):
        # the deny re-issue rate (decision-quality V3): a denied call whose id
        # comes back later in the same ledger was issued again. The id a second
        # ledger repeats is another session's call, never a re-issue.
        self.ledger("a.jsonl", [
            {"kind": "deny", "detail": "race: a sibling holds it", "id": "X"},
            {"kind": "run", "detail": "ls", "exit": 0, "id": "X"},
            {"kind": "deny", "detail": "race: a sibling holds it", "id": "Y"},
            {"kind": "deny", "detail": "task: no active task", "id": "Z"},
        ])
        self.ledger("b.jsonl", [{"kind": "run", "detail": "ls", "exit": 0,
                                 "id": "Y"}])
        counts = self.counts()
        self.assertEqual(counts["denies"], {"race": 2, "task": 1})
        self.assertEqual(counts["denies_reissued"], {"race": 1, "task": 0})
        out = support.run([self.cli, "--counters", "--all"], env=self.envv).stdout
        self.assertIn("race=1/2 0.5000", out)

    def test_blocked_claims_are_split_by_their_stop_class(self):
        # false_completion is one sum; the class says which check refused, and
        # a shape block stays out of it as it stays out of false_completion
        self.ledger("a.jsonl", [
            {"kind": "claim", "detail": "blocked: no external read"},
            {"kind": "claim", "detail": "blocked: no verify_ok"},
            {"kind": "claim", "detail": "blocked: no verify_ok"},
            {"kind": "claim", "detail": "blocked: list cap"},
        ])
        counts = self.counts()
        self.assertEqual(counts["false_completion"], 3)
        self.assertEqual(counts["blocked_claims"],
                         {"no external read": 1, "no verify_ok": 2})
        out = support.run([self.cli, "--counters", "--all"], env=self.envv).stdout
        self.assertIn("no external read=1", out)

    def test_fixture_workspaces_are_left_out_of_the_corpus(self):
        # a probe in a temp tree, an OpenResearch run copy and an arm-bench run
        # are the harness, not use: their claims must not move the corpus ratio.
        # A ledger that also names a real workspace, or none at all, stays in.
        real = "/Users/u/Projects/app"
        for name, space in (
                ("tmp.jsonl", "/private/tmp/probe-e2e"),
                ("folders.jsonl", "/private/var/folders/rf/x/T/repo"),
                ("runs.jsonl", "/Users/u/.local/share/openresearch/local-runs/3eb8/repo"),
                ("bench.jsonl", "/Users/u/src/tezgah/benchmarks/arm-bench/.runs/c01/repo")):
            self.ledger(name, [{"kind": "claim", "detail": "blocked: x",
                                "workspace": space}])
        self.ledger("real.jsonl", [{"kind": "claim", "detail": "ok", "workspace": real}])
        self.ledger("mixed.jsonl", [{"kind": "claim", "detail": "ok", "workspace": real},
                                    {"kind": "run", "detail": "ls", "workspace": "/tmp/s"}])
        self.ledger("old.jsonl", [{"kind": "claim", "detail": "ok"}])
        counts = self.counts()
        self.assertEqual((counts["ledgers"], counts["fixtures"]), (3, 4))
        self.assertEqual((counts["claims"], counts["false_completion"]), (3, 0))

    def test_a_ledger_without_a_claim_row_or_an_exit_does_not_divide_by_zero(self):
        # the rate has no decided row to divide by and the claim share has no
        # denominator: neither may raise, and neither may invent a number
        self.ledger("quiet.jsonl", [{"kind": "nudge", "detail": "proj"}])
        counts = self.counts()
        self.assertIsNone(counts["tool_error_rate"])
        self.assertEqual(counts["claims"], 0)
        self.assertEqual(counts["false_completion"], 0)

    def test_one_session_still_reads_its_own_numbers(self):
        # the reading that existed before the fold: one session's ledger, with no
        # `ledgers` key and no other ledger's rows in it
        run_json([support.PROBE_INTEGRITY],
                 {"fn": "note", "session": "s-c14", "kind": "verify_ok",
                  "detail": "pytest -q", "exit": 0}, env=self.envv)
        self.ledger("other.jsonl", [{"kind": "claim", "detail": "blocked: x"}])
        out, proc = run_json([self.cli, "--counters", "--json"],
                             env=dict(self.envv, TEZGAH_SESSION="s-c14"))
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(out["events"], 1)
        self.assertEqual(out["kinds"], {"verify_ok": 1})
        self.assertEqual(out["claims"], 0)

    def test_the_session_id_is_found_whichever_order_it_comes_in(self):
        # the help says `--counters [SESSION_ID] [PATH]`, the docs say path
        # first: both orders, and the id alone, must read the same ledger,
        # without TEZGAH_SESSION standing in for a misread argument
        env = dict(self.envv)
        env.pop("TEZGAH_SESSION", None)
        run_json([support.PROBE_INTEGRITY],
                 {"fn": "note", "session": "s-order", "kind": "verify_ok",
                  "detail": "pytest -q", "exit": 0}, env=env)
        for args in (["s-order"], ["s-order", self.home], [self.home, "s-order"]):
            out, proc = run_json([self.cli, "--counters", *args, "--json"], env=env)
            self.assertEqual(proc.returncode, 0, proc.stderr)
            self.assertEqual(out["events"], 1, args)

    def test_the_judge_count_folds_like_every_other_number(self):
        # both readers fold through `_counts`, so the corpus total and the
        # sessions it sums cannot disagree about the seam's spend
        self.ledger("a.jsonl", [{"kind": "judge", "detail":
                                 "tezgah-docs jev-latest in=900 out=4 ms=700"}])
        self.ledger("b.jsonl", [{"kind": "judge", "detail":
                                 "tezgah-triage jev-latest in=900 out=4 ms=810"}])
        out, proc = run_json([self.cli, "--counters", "--all", "--json"],
                             env=self.envv)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(out["judge"], 2)
        self.assertEqual(out["events"], 2)
        self.assertEqual(out["steps"], 0)

    def test_the_plain_printer_shows_the_judge_count(self):
        # a session that never judged reads 0 and one row moves it: the plain
        # line a reader scrapes, not only the --json one
        env = dict(self.envv, TEZGAH_SESSION="s-judge")
        proc = support.run([self.cli, "--counters"], env=env)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(self.counter("judge", proc.stdout), "0")
        run_json([support.PROBE_INTEGRITY],
                 {"fn": "note", "session": "s-judge", "kind": "judge",
                  "detail": "tezgah-triage jev-latest in=900 out=4 ms=820"},
                 env=self.envv)
        proc = support.run([self.cli, "--counters"], env=env)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(self.counter("judge", proc.stdout), "1")

    def test_counters_report_subagent_bytes_p50_and_max(self):
        # A subagent's report is the one result whose size is a cost to read,
        # so its rows are folded apart: the count of results, and the median
        # and largest byte length over the ones whose size the host reported.
        # A row with no size (omp reports a part count, so it records none) is
        # a result all the same; an effect that inherited the channel is not.
        sub = {"kind": "external", "detail": "subagent", "source": "subagent"}
        self.ledger("a.jsonl", [dict(sub, out_bytes=300), dict(sub, out_bytes=100),
                                dict(sub),
                                {"kind": "edit", "detail": "a.py",
                                 "source": "subagent", "out_bytes": 5},
                                {"kind": "external", "detail": "web",
                                 "source": "web", "out_bytes": 9000}])
        self.ledger("b.jsonl", [dict(sub, out_bytes=200)])
        counts = self.counts()
        self.assertEqual((counts["subagent_results"], counts["subagent_bytes_p50"],
                          counts["subagent_bytes_max"]), (4, 200, 300))
        proc = support.run([self.cli, "--counters", "--all"], env=self.envv)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(self.counter("subagent_results", proc.stdout), "4")
        self.assertEqual(self.counter("subagent_bytes_p50", proc.stdout), "200")
        self.assertEqual(self.counter("subagent_bytes_max", proc.stdout), "300")
        # a session that delegated nothing states no size rather than a 0
        out, proc = run_json([self.cli, "--counters", "none-such", "--json"],
                             env=self.envv)
        self.assertEqual((out["subagent_results"], out["subagent_bytes_p50"],
                          out["subagent_bytes_max"]), (0, None, None))

    def counter(self, name, out):
        """One counter's value on the plain printer's line, or None if the
        printer never printed it."""
        for line in out.splitlines():
            parts = line.split()
            if parts and parts[0] == name:
                return parts[1]
        return None


# The week the fixtures below are written against: a fixed Monday far enough
# from the epoch that a `weeks_ago` offset is unambiguous.
BASE = ti.MONDAY + 3000 * ti.WEEK


def at(weeks_ago, seconds=3600):
    """An epoch second inside the week `weeks_ago` weeks before BASE."""
    return BASE - weeks_ago * ti.WEEK + seconds


class DriftSeries(unittest.TestCase):
    """The counter fold's week buckets: the slope, not the value.

    `--counters --all` gives one number for the whole corpus, and a harness that
    is getting worse - or better - reads exactly like a flat one. The buckets
    are filled inside `_counts`, in the same pass as the totals, so the series
    cannot contradict the number it is drawn from. These run in process because
    the property under test is the arithmetic, not a surface."""

    def claim(self, weeks_ago, blocked=False):
        return {"kind": "claim", "ts": at(weeks_ago),
                "detail": "blocked: stale evidence" if blocked else "ok"}

    def ran(self, weeks_ago, code=0):
        return {"kind": "run", "ts": at(weeks_ago), "detail": "ls", "exit": code}

    def test_the_buckets_are_the_totals_split_by_week(self):
        # every per-bucket count has to add up to the total the headline number
        # is folded from: a series that disagrees with its own total is a second
        # reader, which is the thing this placement exists to prevent
        rows = [self.claim(0), self.claim(1, blocked=True), self.claim(1),
                self.ran(0), self.ran(2, code=1)]
        counts = ti._counts(rows, weeks=True)
        buckets = list(counts["weeks"].values())
        self.assertEqual(len(buckets), 3)
        for key, total in (("events", "events"), ("claims", "claims"),
                           ("false_completion", "false_completion")):
            self.assertEqual(sum(b[key] for b in buckets), counts[total])
        self.assertEqual(ti._ratio(sum(b["errors"] for b in buckets),
                                   sum(b["decided"] for b in buckets)),
                         counts["tool_error_rate"])

    def test_the_series_orders_the_weeks_and_names_the_direction(self):
        # the defect rate halves and the error rate doubles over the weeks that
        # carry a denominator; both directions have to come out of the counts
        rows = [self.claim(2, blocked=True), self.claim(2),
                self.claim(1, blocked=True), self.claim(1),
                self.claim(0), self.claim(0),
                self.ran(2), self.ran(2), self.ran(1), self.ran(1, code=1),
                self.ran(0, code=1), self.ran(0, code=1)]
        series = ti.drift_series(ti._counts(rows, weeks=True), weeks=3)
        self.assertEqual([r["date"] for r in series["rows"]],
                         [time.strftime("%Y-%m-%d", time.gmtime(at(w)))
                          for w in (2, 1, 0)])
        self.assertEqual([r["events"] for r in series["rows"]], [4, 4, 4])
        self.assertEqual([r["false_completion_rate"] for r in series["rows"]],
                         [0.5, 0.5, 0.0])
        self.assertEqual([r["tool_error_rate"] for r in series["rows"]],
                         [0.0, 0.5, 1.0])
        self.assertEqual(series["false_completion_trend"], "falling")
        self.assertEqual(series["tool_error_trend"], "rising")

    def test_a_week_with_no_row_prints_no_rate(self):
        # a corpus that went quiet for two weeks is a gap in the series, not two
        # perfect weeks: 0.0000 there would read as the harness improving
        rows = [self.claim(3, blocked=True), self.ran(3, code=1), self.claim(0)]
        series = ti.drift_series(ti._counts(rows, weeks=True), weeks=4)
        self.assertEqual([r["events"] for r in series["rows"]], [2, 0, 0, 1])
        for gap in series["rows"][1:3]:
            self.assertIsNone(gap["false_completion_rate"])
            self.assertIsNone(gap["tool_error_rate"])
        # the direction reads only the weeks that carry a denominator
        self.assertEqual(series["false_completion_trend"], "falling")

    def test_a_week_of_one_claim_still_has_a_denominator(self):
        # None is "nothing to divide", not "a small number": a week with one
        # claim and one refusal is 1.0, and reading it as None would hide the
        # worst week the corpus can have
        series = ti.drift_series(ti._counts([self.claim(1, blocked=True)],
                                            weeks=True), weeks=1)
        self.assertEqual(series["rows"][-1]["false_completion_rate"], 1.0)

    def test_the_reader_asked_for_no_series_gets_none(self):
        # the default fold is what every other caller prints, and a key it did
        # not ask for would change the JSON under it
        self.assertNotIn("weeks", ti._counts([self.claim(0)]))
        self.assertEqual(ti.drift_series(ti._counts([self.claim(0)]))["rows"], [])


class ToolFirings(TempHome):
    """Which tool a call was, and which shipped program ran.

    `classify` folds every host tool name into a kind (`Bash` -> `run`), so
    before the `tool` field no reader could say how often a tool fires - and the
    tool nobody calls is exactly the one a retirement report has to name."""

    def setUp(self):
        super().setUp()
        self.evidence = os.path.join(self.home, ".cache", "tezgah", "evidence")
        os.makedirs(self.evidence)
        self.envv = self.env()
        self.cli = os.path.join(support.REPO, "bin", "tezgah-status")

    def ledger(self, name, rows):
        """Rows written straight into the file, because `note_path` stamps `ts`
        with the clock and a series test has to choose the week a row lands in."""
        with open(os.path.join(self.evidence, name), "w", encoding="utf-8") as fh:
            for row in rows:
                fh.write(json.dumps(dict(row, v=ti.ROW_VERSION)) + "\n")

    def counts(self, *args):
        out, proc = support.run_json(
            [self.cli, "--counters", "--all", "--trend", "--json"] + list(args),
            env=self.envv)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        return out

    def test_a_recorder_row_carries_the_name_the_histogram_counts(self):
        # end to end: the host hands `note_tool` a name, the row keeps it, and
        # the fold counts it - a kind alone cannot tell `Bash` from `Write`
        for tool, payload in (("Bash", {"command": "ls"}),
                              ("Write", {"file_path": "a.py", "content": "x"})):
            run_json([support.PROBE_INTEGRITY],
                     {"fn": "note_tool", "session": "s", "tool": tool,
                      "input": payload, "failed": False}, env=self.envv)
        with open(os.path.join(self.evidence, os.listdir(self.evidence)[0])) as fh:
            rows = [json.loads(line) for line in fh]
        self.assertEqual(sorted(r["tool"] for r in rows), ["Bash", "Write"])
        self.assertEqual(self.counts()["tools"], {"bash": 1, "write": 1})

    def test_the_names_older_rows_kept_are_counted_too(self):
        # a corpus older than the field carries the name only where it survived
        # in `detail`: an unclassified call and an MCP server's answer
        self.ledger("old.jsonl", [
            {"kind": "unknown", "detail": "unknown tool: Fabricated"},
            {"kind": "external", "detail": "mcp mcp__codegen__status",
             "source": "mcp"},
            {"kind": "run", "detail": "ls", "exit": 0},
        ])
        self.assertEqual(self.counts()["tools"],
                         {"fabricated": 1, "mcp__codegen__status": 1})

    def test_the_histogram_costs_nothing_to_a_reader_who_did_not_ask(self):
        # the flagged fold adds keys; the plain one must not, or every existing
        # JSON consumer breaks for a report it never asked for
        self.ledger("a.jsonl", [{"kind": "run", "detail": "bin/consult q",
                                 "exit": 0, "tool": "Bash"}])
        out, proc = support.run_json([self.cli, "--counters", "--all", "--json"],
                                     env=self.envv)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(
            set(out) & {"weeks", "tools", "programs"}, set())

    def test_a_shipped_program_with_no_row_is_named_and_one_that_ran_is_not(self):
        # the absence is the evidence, so it can only come from a catalog: this
        # layer's own `bin/`, read at fold time rather than kept as a list that
        # goes stale on the next added tool
        self.ledger("a.jsonl", [{"kind": "run", "detail": "consult 'x'",
                                 "exit": 0}])
        counts = self.counts()
        catalog = ti.shipped_programs()
        self.assertTrue(catalog, "the checkout ships no bin/ program")
        never = ti.unfired_programs(counts)
        for name in catalog:
            self.assertEqual(name in never, name != "consult", name)

    def test_naming_a_program_is_not_running_it(self):
        # the firing test is the module's own command-position tokenizer, not a
        # substring: `grep -n consult hooks/` names the program and runs nothing,
        # and a substring reader would retire the wrong tool
        self.ledger("a.jsonl", [{"kind": "run", "detail": "grep -n consult hooks/",
                                 "exit": 0}])
        self.assertIn("consult", ti.unfired_programs(self.counts()))

    def test_the_plain_report_is_byte_identical_without_the_flag(self):
        # the whole point of the flag: a reader who did not ask gets the report
        # they had, character for character, and the series is appended after it
        self.ledger("a.jsonl", [{"kind": "claim", "detail": "ok"},
                                {"kind": "claim", "detail": "blocked: stale evidence"}])
        plain = support.run([self.cli, "--counters", "--all"], env=self.envv)
        self.assertEqual(plain.returncode, 0, plain.stderr)
        self.assertNotIn("drift:", plain.stdout)
        self.assertNotIn("tool firings:", plain.stdout)
        trend = support.run([self.cli, "--counters", "--all", "--trend"],
                            env=self.envv)
        self.assertEqual(trend.returncode, 0, trend.stderr)
        self.assertTrue(trend.stdout.startswith(plain.stdout), trend.stdout)
        self.assertIn("false_completion/claims", trend.stdout)
        self.assertIn("never fired:", trend.stdout)

    def test_the_window_is_read_from_the_flag_and_the_json_carries_the_fold(self):
        self.ledger("a.jsonl", [{"kind": "claim", "ts": at(9),
                                 "detail": "blocked: x"},
                                {"kind": "claim", "ts": at(0), "detail": "ok"}])
        out = self.counts("--weeks=2")
        self.assertEqual(len(out["series"]["rows"]), 2)
        self.assertEqual(out["series"]["rows"][-1]["claims"], 1)
        self.assertIn("never", out)

    def test_the_two_flags_are_refused_without_counters(self):
        # `--trend` alone reads like a report of its own; it is a modifier, and
        # a silent no-op would print the status line instead
        for args in (["--trend"], ["--weeks=3"], ["--weeks=x", "--counters"]):
            proc = support.run([self.cli] + args, env=self.envv)
            self.assertEqual(proc.returncode, 2, args)
            self.assertIn("tezgah-status:", proc.stderr)


if __name__ == "__main__":
    unittest.main()
