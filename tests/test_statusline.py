"""statusline.py: the pony/exec/adhd/consult/research/cbm/orch segment, Claude and Cursor."""
import json
import os
import sys
import unittest

import support
from support import TempHome, run

SEGMENT = ("pony\u25cb exec\u2713 adhd\u25cb  \u00b7  consult\u25cb research\u2717 cbm\u25cb"
           " orch\u25cb  \u00b7  idx\u2013")
NO_ROOT = ("pony\u25cb exec\u2713 adhd\u25cb  \u00b7  consult\u25cb research\u2717 cbm\u25cb"
           " orch\u25cb")
# Cursor reads the store, which sees tool calls and no skill read, so those two
# marks state nothing there instead of claiming the skill is unused.
CURSOR_SEGMENT = ("pony exec\u2713 adhd  \u00b7  consult\u25cb research\u2717 cbm\u25cb"
                  " orch\u25cb  \u00b7  idx\u2013")


class Statusline(TempHome):
    def setUp(self):
        super().setUp()
        self.repo = self.make_repo("proj")
        self.touch(os.path.join(self.home, ".config", "openrouter", "key"))
        self.envv = self.env()
        self.envv["NO_COLOR"] = "1"  # the plain-form assertions below

    def test_claude_mode_segment(self):
        proc = run([support.STATUSLINE], {"cwd": self.repo}, env=self.envv)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(proc.stdout.strip(), SEGMENT)

    def test_cursor_mode_segment(self):
        proc = run([support.STATUSLINE, "--cursor"],
                   {"cwd": self.repo, "session_id": "s"}, env=self.envv)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(proc.stdout.strip(), CURSOR_SEGMENT)

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

    def orx_env(self):
        """The plain environment plus an `orx` on the PATH lookup: without it the
        research mark is `off` (no tool installed) and can never light, which is
        not what these tests are about."""
        return self.env(extra={"TEZGAH_ORX_BIN": sys.executable})

    def test_a_real_orx_run_lights_the_research_mark(self):
        # Claude's half derives its used kinds from the transcript. The token it
        # reads has to be the command the shell actually ran, or the mark never
        # lights at all (the defect this pins: `research` had no reader).
        tp = os.path.join(self.home, "transcript.jsonl")
        with open(tp, "w") as fh:
            fh.write(json.dumps({"message": {"content": [
                {"type": "tool_use", "name": "Bash",
                 "input": {"command": "orx experiment run --tree t"}}]}}) + "\n")
        proc = run([support.STATUSLINE],
                   {"cwd": self.repo, "session_id": "s", "transcript_path": tp},
                   env=self.orx_env())
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("research\u2713", proc.stdout)

    def test_mentioning_the_tool_in_an_argument_marks_nothing(self):
        # The other half of that defect: a mention used to be enough, which made
        # the line report a run that never happened.
        tp = os.path.join(self.home, "transcript.jsonl")
        with open(tp, "w") as fh:
            fh.write(json.dumps({"message": {"content": [
                {"type": "tool_use", "name": "Bash",
                 "input": {"command": "echo 'orx and consult are CLIs'"}}]}}) + "\n")
        proc = run([support.STATUSLINE],
                   {"cwd": self.repo, "session_id": "s", "transcript_path": tp},
                   env=self.orx_env())
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("research\u25cb", proc.stdout)
        self.assertIn("consult\u25cb", proc.stdout)

    def test_colors_by_state(self):
        env = dict(self.envv)
        env.pop("NO_COLOR")
        proc = run([support.STATUSLINE], {"cwd": self.repo}, env=env)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("\033[33mpony\u25cb\033[0m", proc.stdout)      # armed
        self.assertIn("\033[32mexec\u2713\033[0m", proc.stdout)      # always-on
        self.assertIn("\033[33mconsult\u25cb\033[0m", proc.stdout)   # on demand
        self.assertIn("\033[31mresearch\u2717\033[0m", proc.stdout)  # off
        self.assertIn("\033[2m  \u00b7  \033[0m", proc.stdout)       # dim separator

    def test_status_color_env_off_strips_ansi(self):
        env = dict(self.envv)
        env.pop("NO_COLOR")
        env["TEZGAH_STATUS_COLOR"] = "0"
        self.assertNotIn("\033[", run([support.STATUSLINE],
                                      {"cwd": self.repo}, env=env).stdout)


if __name__ == "__main__":
    unittest.main()
