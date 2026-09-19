"""hooks/tezgah_integrity.py + the Stop/PostToolUse hooks: the integrity gate.

The pure detectors run in-process; the ledger and the two Claude hooks run in a
subprocess with a throwaway HOME so the real cache is never touched.
"""
import fcntl
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
                           ("something odd happened", "unknown"),
                           ("", None), (None, None)):
            self.assertEqual(ti.fail_class(text), want, text)


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

    def test_neutered_check_denied(self):
        for c in ("pytest || true", "npm test || true", "ruff check . ; true",
                  "cargo test || exit 0", "pytest tests/ || :"):
            self.assertIsNotNone(ti.shortcut_command(c), c)

    def test_skip_env_denied(self):
        for c in ("SKIP=flake8 git commit -m x",
                  "HUSKY_SKIP_HOOKS=1 git commit -m x",
                  "HUSKY=0 git commit -m x"):
            self.assertIsNotNone(ti.shortcut_command(c), c)

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

    def edit(self, path, age=0, workspace=None):
        row = {"kind": "edit", "ts": int(time.time()) - age, "detail": path}
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

    def test_a_relative_write_matches_the_same_relative_query(self):
        # the caller passes the field its own host handed it, unchanged, so the
        # two forms of one file only meet when the hosts spell them the same
        self.write("rel", [self.edit("src/a.py", workspace="/repo")])
        self.assertEqual(ti.writers_elsewhere("src/a.py", "mine"),
                         [ti._slug("rel")])
        self.assertEqual(ti.writers_elsewhere("/repo/src/a.py", "mine"), [])

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


class StaleEvidence(unittest.TestCase):
    """P1: a passing check licenses a claim only when it is newer than the newest
    write the gate saw change the tree.

    The hole was measured on the real rule before it landed
    (`.tezgah/research/infra-candidates/experiments/E0-current-stop-rule/`):
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
        self.assertIn(self.target, reason)
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
        self.assertIn(new, reason)

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

    def claim_rows(self):
        out, _ = run_json([support.PROBE_INTEGRITY],
                          {"fn": "events", "session": self.session},
                          env=self.envv)
        return [r.get("detail") for r in out if r.get("kind") == "claim"]

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

    def test_explicit_unverified_admission_passes(self):
        self.seed("Edit", {"file_path": "x.py"})
        self.assertIsNone(self.stop("Done, but I could not verify the tests."))

    def test_sycophantic_opener_blocks(self):
        out = self.stop("Haklısın, hemen düzeltiyorum.")
        self.assertEqual(out.get("decision"), "block")
        self.assertIn("placation", out["reason"])

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


if __name__ == "__main__":
    unittest.main()
