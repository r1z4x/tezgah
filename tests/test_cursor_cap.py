"""hosts/cursor/hook.py: the per-turn text fits Cursor's additional_context cap."""
import unittest

import support
from support import TempHome, run_json

# cursor-agent 2026.10.01-2026.10.19 measures the trimmed additional_context of
# beforeSubmitPrompt and drops it whole over 10000 characters.
CAP = 10000
BUSY = ("analyse this product's retention and which feature next, research the "
        "literature and run experiments, use parallel subagents for each of the 3 "
        "items, consult a second opinion, design the UI screens, who calls parse_config")


class CursorCap(TempHome):
    def test_a_busy_turn_arrives_cut_instead_of_dropped(self):
        repo = self.make_repo("proj")
        out, proc = run_json([support.CURSOR_HOOK], {
            "hook_event_name": "beforeSubmitPrompt", "cwd": repo,
            "conversation_id": "busy", "prompt": BUSY}, env=self.env())
        self.assertEqual(proc.returncode, 0, proc.stderr)
        text = out["additional_context"]
        self.assertLessEqual(len(text.strip()), CAP)
        self.assertIn("harness-reminder", text)


if __name__ == "__main__":
    unittest.main()
