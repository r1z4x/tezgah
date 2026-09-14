"""statusline.py: the pony/exec/consult/cbm/orch segment, Claude and Cursor."""
import os
import unittest

import support
from support import TempHome, run

SEGMENT = ("pony\u2713 exec\u2713  \u00b7  consult\u25cb cbm\u25cb orch\u25cb"
           "  \u00b7  idx\u2013")
NO_ROOT = "pony\u2713 exec\u2713  \u00b7  consult\u25cb cbm\u25cb orch\u25cb"


class Statusline(TempHome):
    def setUp(self):
        super().setUp()
        self.repo = self.make_repo("proj")
        self.touch(os.path.join(self.home, ".config", "openrouter", "key"))
        self.envv = self.env()

    def test_claude_mode_segment(self):
        proc = run([support.STATUSLINE], {"cwd": self.repo}, env=self.envv)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(proc.stdout.strip(), SEGMENT)

    def test_cursor_mode_segment(self):
        proc = run([support.STATUSLINE, "--cursor"],
                   {"cwd": self.repo, "session_id": "s"}, env=self.envv)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(proc.stdout.strip(), SEGMENT)

    def test_no_consult_key_flips_consult(self):
        os.remove(os.path.join(self.home, ".config", "openrouter", "key"))
        proc = run([support.STATUSLINE], {"cwd": self.repo}, env=self.envv)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("consult\u2717", proc.stdout)

    def test_outside_roots_still_shows_segment(self):
        # Global indicator: cwd outside every root still prints the checklist
        # (no repo marks, idx or plan count, but not a blank line).
        proc = run([support.STATUSLINE], {"cwd": self.home}, env=self.envv)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(proc.stdout.strip(), NO_ROOT)


if __name__ == "__main__":
    unittest.main()
