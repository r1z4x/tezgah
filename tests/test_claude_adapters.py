"""hooks/projects-auto-init.py and hooks/projects-pretooluse.py (Claude envelope)."""
import unittest

import support
from support import TempHome, run, run_json


class AutoInit(TempHome):
    def test_session_start_emits_context(self):
        repo = self.make_repo()
        out, proc = run_json([support.AUTO_INIT],
                             {"hook_event_name": "SessionStart", "cwd": repo,
                              "session_id": "s"}, env=self.env())
        self.assertEqual(proc.returncode, 0, proc.stderr)
        hso = out["hookSpecificOutput"]
        self.assertEqual(hso["hookEventName"], "SessionStart")
        self.assertTrue(hso["additionalContext"].strip())

    def test_outside_roots_prints_nothing(self):
        proc = run([support.AUTO_INIT],
                   {"hook_event_name": "SessionStart", "cwd": self.home},
                   env=self.env())
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(proc.stdout.strip(), "")


class PreToolUse(TempHome):
    def setUp(self):
        super().setUp()
        self.repo = self.make_repo("proj")
        self.envv = self.env()

    def payload(self, tool, inp):
        return {"cwd": self.repo, "tool_name": tool, "tool_input": inp,
                "session_id": "s"}

    def test_explore_denied(self):
        out, proc = run_json([support.PRETOOLUSE],
                             self.payload("Agent", {"subagent_type": "Explore"}),
                             env=self.envv)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        hso = out["hookSpecificOutput"]
        self.assertEqual(hso["permissionDecision"], "deny")
        self.assertTrue(hso["permissionDecisionReason"])

    def test_attribution_commit_denied(self):
        out, _ = run_json([support.PRETOOLUSE],
                          self.payload("Bash", {
                              "command": 'git commit -m "x Co-Authored-By: Claude"'}),
                          env=self.envv)
        self.assertEqual(out["hookSpecificOutput"]["permissionDecision"], "deny")

    def test_plain_commit_prints_nothing(self):
        proc = run([support.PRETOOLUSE],
                   self.payload("Bash", {"command": 'git commit -m "plain"'}),
                   env=self.envv)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(proc.stdout.strip(), "")

    def test_outside_roots_prints_nothing(self):
        payload = {"cwd": self.home, "tool_name": "Agent",
                   "tool_input": {"subagent_type": "Explore"}, "session_id": "s"}
        proc = run([support.PRETOOLUSE], payload, env=self.envv)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(proc.stdout.strip(), "")


if __name__ == "__main__":
    unittest.main()
