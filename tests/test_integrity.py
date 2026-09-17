"""hooks/tezgah_integrity.py + the Stop/PostToolUse hooks: the integrity gate.

The pure detectors run in-process; the ledger and the two Claude hooks run in a
subprocess with a throwaway HOME so the real cache is never touched.
"""
import json
import os
import shutil
import sys
import tempfile
import unittest
from unittest import mock

import support
from support import TempHome, run_json

sys.path.insert(0, os.path.join(support.REPO, "hooks"))
import tezgah_context as tc  # noqa: E402
import tezgah_integrity as ti  # noqa: E402


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
        self.assertEqual(ti.prior_calls("s", "dup", tail=3), (2, 1, "transient"))
        self.assertEqual(ti.prior_calls("s", "dup", tail=1), (0, None, None))
        self.assertEqual(ti.prior_calls("s", "absent", tail=3), (0, None, None))

    def test_a_refusal_or_a_nudge_is_not_an_attempt(self):
        # the gate's own deny row and the nudge row carry the same id with no
        # outcome; counting them left the refusal newest, read as "no failure",
        # and disarmed the ceiling on every second repeat
        self.append({"kind": "run", "id": "dup", "exit": 1})
        self.append({"kind": "run", "id": "dup", "exit": 1})
        self.append({"kind": "deny", "id": "dup", "detail": "loop: denied"})
        self.append({"kind": "nudge", "id": "dup", "detail": "proj"})
        self.assertEqual(ti.prior_calls("s", "dup", tail=4), (2, 1, None))

    def test_the_newest_turn_bounds_the_attempts(self):
        # reset per user turn: a failure the user then asked to retry is not this
        # turn's spent ceiling
        self.append({"kind": "run", "id": "dup", "exit": 1})
        self.append({"kind": "run", "id": "dup", "exit": 1})
        self.append({"kind": "turn", "detail": "abc"})
        self.append({"kind": "run", "id": "dup", "exit": 1})
        self.assertEqual(ti.prior_calls("s", "dup", tail=4), (1, 1, None))
        self.append({"kind": "turn", "detail": "def"})
        self.assertEqual(ti.prior_calls("s", "dup", tail=5), (0, None, None))


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
        self.seed("Edit", {"file_path": "x.py"})
        self.assertIsNone(self.stop("Toplam 5 dosya incelendi."))
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

    def test_non_check_command_records_run(self):
        self.run_hook("PostToolUse", "Bash", {"command": "ls -la"})
        self.assertIn("run", self.kinds())

    def test_edit_records_edit(self):
        self.run_hook("PostToolUse", "Edit", {"file_path": "/tmp/x.py"})
        self.assertIn("edit", self.kinds())

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


if __name__ == "__main__":
    unittest.main()
