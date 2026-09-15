"""hosts/cursor/hook.py: event translation and the shared gate."""
import os
import unittest

import support
from support import TempHome, run_json


class CursorHook(TempHome):
    def setUp(self):
        super().setUp()
        self.repo = self.make_repo("proj")
        self.envv = self.env()

    def call(self, payload):
        out, proc = run_json([support.CURSOR_HOOK], payload, env=self.envv)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        return out

    def test_session_start_returns_additional_context(self):
        out = self.call({"hook_event_name": "sessionStart", "cwd": self.repo,
                         "conversation_id": "s"})
        self.assertTrue(out["additional_context"].strip())

    def test_session_start_outside_roots_is_empty(self):
        out = self.call({"hook_event_name": "sessionStart", "cwd": self.home,
                         "conversation_id": "s"})
        self.assertEqual(out, {})

    def test_pre_tool_use_denies_attribution(self):
        out = self.call({"hook_event_name": "preToolUse", "tool_name": "Shell",
                         "tool_input": {"command":
                                        'git commit -m "x Co-Authored-By: Claude"'},
                         "cwd": self.repo, "conversation_id": "s"})
        self.assertEqual(out["permission"], "deny")
        self.assertTrue(out["agent_message"])

    def test_pre_tool_use_denies_explore(self):
        out = self.call({"hook_event_name": "preToolUse", "tool_name": "Task",
                         "tool_input": {"subagent_type": "Explore"},
                         "cwd": self.repo, "conversation_id": "s"})
        self.assertEqual(out["permission"], "deny")

    def test_pre_tool_use_allows_plain_commit(self):
        out = self.call({"hook_event_name": "preToolUse", "tool_name": "Shell",
                         "tool_input": {"command": 'git commit -m "plain"'},
                         "cwd": self.repo, "conversation_id": "s"})
        self.assertEqual(out, {"permission": "allow"})

    def test_before_submit_prompt_injects_the_reminder(self):
        out = self.call({"hook_event_name": "beforeSubmitPrompt", "cwd": self.repo})
        self.assertTrue(out["continue"])
        self.assertIn("harness-reminder", out["additional_context"])

    def test_before_submit_prompt_respects_reminder_off(self):
        self.touch(os.path.join(self.home, ".config", "tezgah", "reminder-off"))
        out = self.call({"hook_event_name": "beforeSubmitPrompt", "cwd": self.repo})
        self.assertEqual(out, {"continue": True})


if __name__ == "__main__":
    unittest.main()
