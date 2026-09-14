"""hosts/codex/hook.py: SessionStart context and Stop status segment."""
import unittest

import support
from support import TempHome, run, run_json


class CodexHook(TempHome):
    def test_session_start_emits_additional_context(self):
        repo = self.make_repo()
        out, proc = run_json([support.CODEX_HOOK],
                             {"hook_event_name": "SessionStart", "cwd": repo,
                              "session_id": "s"}, env=self.env())
        self.assertEqual(proc.returncode, 0, proc.stderr)
        hso = out["hookSpecificOutput"]
        self.assertEqual(hso["hookEventName"], "SessionStart")
        self.assertTrue(hso["additionalContext"].strip())

    def test_stop_emits_system_message(self):
        repo = self.make_repo()
        out, proc = run_json([support.CODEX_HOOK],
                             {"hook_event_name": "Stop", "cwd": repo,
                              "session_id": "s"}, env=self.env())
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("systemMessage", out)
        self.assertIn("tezgah", out["systemMessage"])

    def test_outside_roots_reports_status_without_context(self):
        # The status segment is a global indicator (tezgah loads globally where
        # it ships as an instructions file), so it prints off-root too; the
        # rule context itself stays root-scoped and is absent.
        out, proc = run_json([support.CODEX_HOOK],
                             {"hook_event_name": "SessionStart", "cwd": self.home},
                             env=self.env())
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("tezgah", out["systemMessage"])
        self.assertNotIn("hookSpecificOutput", out)

    def test_post_tool_use_records_and_prints_nothing(self):
        repo = self.make_repo()
        proc = run([support.CODEX_HOOK],
                   {"hook_event_name": "PostToolUse", "cwd": repo,
                    "session_id": "s", "tool_name": "Task", "tool_input": {}},
                   env=self.env())
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(proc.stdout.strip(), "")


if __name__ == "__main__":
    unittest.main()
