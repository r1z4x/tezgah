"""hooks/tezgah_integrity.py + the Stop/PostToolUse hooks: the integrity gate.

The pure detectors run in-process; the ledger and the two Claude hooks run in a
subprocess with a throwaway HOME so the real cache is never touched.
"""
import os
import sys
import unittest

import support
from support import TempHome, run_json

sys.path.insert(0, os.path.join(support.REPO, "hooks"))
import tezgah_integrity as ti  # noqa: E402


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

    def test_plain_commands_pass(self):
        for c in ("pytest -q", "npm test", "git commit -m 'fix: typo'",
                  "git status", "ruff check .", "make test"):
            self.assertIsNone(ti.shortcut_command(c), c)

    def test_neuter_without_a_check_passes(self):
        self.assertIsNone(ti.shortcut_command("ls || true"))
        self.assertIsNone(ti.shortcut_command("git log || true"))

    def test_no_verify_without_a_git_write_passes(self):
        self.assertIsNone(ti.shortcut_command("echo --no-verify"))


class ShortcutEdit(unittest.TestCase):
    def test_adding_a_skip_denied(self):
        for new in ("@pytest.mark.skip(reason='flaky')\ndef test_x(): pass",
                    "it.skip('later', () => {})",
                    "t.Skip('flaky')",
                    "@unittest.skip('x')\nclass T: pass",
                    "test.only('a', () => {})"):
            self.assertIsNotNone(ti.shortcut_edit({"new_string": new}), new)

    def test_optional_dependency_guard_allowed(self):
        # skipUnless guards a missing optional dep; it is not a disable and
        # must not be caught (the gate denied it before the boundary fix).
        new = "@unittest." + "skipUnless(HAVE_NODE, 'node missing')\ndef t(): pass"
        self.assertIsNone(ti.shortcut_edit({"new_string": new}))

    def test_conditional_skip_reports_its_own_name(self):
        # a skipIf marker must be named as itself, not truncated to skip
        for name in ("@unittest." + "skipIf(x, 'y')",
                     "@pytest.mark." + "skipif(x, 'y')"):
            reason = ti.shortcut_edit({"new_string": name + "\ndef t(): pass"})
            self.assertIsNotNone(reason, name)
            self.assertIn(name.split("(")[0], reason)

    def test_rewriting_an_existing_skip_passes(self):
        old = "@pytest.mark.skip(reason='flaky')\ndef test_x(): pass"
        self.assertIsNone(ti.shortcut_edit(
            {"old_string": old, "new_string": old}))

    def test_plain_edit_passes(self):
        self.assertIsNone(ti.shortcut_edit(
            {"old_string": "a = 1", "new_string": "a = 2"}))

    def test_empty_edit_passes(self):
        self.assertIsNone(ti.shortcut_edit({}))

    def test_removing_an_assertion_is_not_caught(self):
        # documented ceiling: only an ADDED skip marker is mechanical; a
        # weakened assertion is not, so it is left to review by design.
        self.assertIsNone(ti.shortcut_edit(
            {"old_string": "def t():\n    assert x == 1",
             "new_string": "def t():\n    pass"}))


class StopHook(TempHome):
    def setUp(self):
        super().setUp()
        self.repo = self.make_repo("proj")
        self.envv = self.env()
        self.session = "s-stop"

    def seed(self, tool, inp, failed=False):
        run_json([support.PROBE_INTEGRITY],
                 {"fn": "note_tool", "session": self.session, "tool": tool,
                  "input": inp, "failed": failed}, env=self.envv)

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

    def test_explicit_unverified_admission_passes(self):
        self.seed("Edit", {"file_path": "x.py"})
        self.assertIsNone(self.stop("Done, but I could not verify the tests."))

    def test_sycophantic_opener_blocks(self):
        out = self.stop("Haklısın, hemen düzeltiyorum.")
        self.assertEqual(out.get("decision"), "block")
        self.assertIn("placation", out["reason"])

    def test_plain_answer_passes(self):
        self.assertIsNone(self.stop("Toplam 5 dosya incelendi."))

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

    def run_hook(self, event, tool, inp):
        out, proc = run_json([support.POSTTOOLUSE],
                             {"hook_event_name": event, "cwd": self.repo,
                              "session_id": self.session, "tool_name": tool,
                              "tool_input": inp}, env=self.envv)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        return out

    def kinds(self):
        out, _ = run_json([support.PROBE_INTEGRITY],
                          {"fn": "kinds", "session": self.session},
                          env=self.envv)
        return out

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

    def test_outside_root_records_nothing(self):
        run_json([support.POSTTOOLUSE],
                 {"hook_event_name": "PostToolUse", "cwd": self.home,
                  "session_id": self.session, "tool_name": "Bash",
                  "tool_input": {"command": "pytest"}}, env=self.envv)
        self.assertEqual(self.kinds(), [])


if __name__ == "__main__":
    unittest.main()
