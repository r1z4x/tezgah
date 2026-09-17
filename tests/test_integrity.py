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

    def test_an_allowed_claim_is_recorded_too(self):
        # without the allowed rows the false-completion rate has no denominator
        self.seed("Edit", {"file_path": "x.py"})
        self.seed("Bash", {"command": "pytest -q"})
        self.assertIsNone(self.stop("Done. All tests pass."))
        counts = self.counts()
        self.assertEqual(counts["claims"], 1)
        self.assertEqual(counts["false_completion"], 0)

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
        # most tools answer with an object; the ledger keeps its size and never
        # the result itself
        result = {"stdout": "x" * 10, "stderr": ""}
        self.run_hook("PostToolUse", "Bash", {"command": "ls"},
                      tool_response=result)
        row = self.rows()[-1]
        self.assertEqual(row["out_bytes"], len(json.dumps(result)))
        self.assertNotIn("stdout", json.dumps(row))

    def test_a_piped_check_is_recorded_as_ran(self):
        self.run_hook("PostToolUse", "Bash", {"command": "pytest -q | tail -1"})
        self.assertEqual(self.kinds(), ["verify"])

    def test_counters_report_the_trace_metrics(self):
        # steps, the error rate over the rows whose outcome the host reported,
        # the claims, and how many of them a stop refused
        self.run_hook("PostToolUse", "Bash", {"command": "pytest -q"})
        self.run_hook("PostToolUseFailure", "Bash", {"command": "ls"})
        self.write_row("claim", "blocked: This turn claims done/tested/passing")
        self.write_row("claim", "ok")
        counts = self.counters()
        self.assertEqual(counts["steps"], 4)
        self.assertEqual(counts["tool_error_rate"], 0.5)
        self.assertEqual(counts["claims"], 2)
        self.assertEqual(counts["false_completion"], 1)

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
