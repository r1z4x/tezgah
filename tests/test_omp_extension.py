"""hosts/omp/tezgah-hook.ts.in: the wiring from omp's events to the hook.

The generated extension is imported by node (which strips its type annotations)
against a stub pi, so which omp event reaches the hook - and what the host is
told to do with the answer - is checked without an omp session. The hook's own
behaviour is covered by tests/test_omp_hook.py; this file covers the bridge.
"""
import json
import os
import shutil
import subprocess
import unittest

import support
from support import TempHome


class OmpExtension(TempHome):
    def setUp(self):
        super().setUp()
        self.node = shutil.which("node")
        if not self.node:
            self.skipTest("node is not installed")
        # the installed form is the template with the hook's absolute path
        with open(support.OMP_EXTENSION) as fh:
            text = fh.read().replace("@HOOK@", support.OMP_HOOK)
        self.assertNotIn("@HOOK@", text)
        self.ext = os.path.join(self.home, "tezgah-hook.ts")
        with open(self.ext, "w") as fh:
            fh.write(text)

    def drive(self, calls, cwd=None):
        spec = {"extension": self.ext, "dir": cwd or self.make_repo(),
                "session": "s", "calls": calls}
        proc = subprocess.run([self.node, support.OMP_HARNESS],
                              input=json.dumps(spec), capture_output=True,
                              text=True, env=self.env(), timeout=120)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        out = json.loads(proc.stdout)
        self.assertNotIn("fatal", out, out.get("fatal"))
        return out

    def results(self, out):
        self.assertEqual([r.get("error") for r in out["results"]], [None] * len(
            out["results"]), out["results"])
        return [r.get("out") for r in out["results"]]

    def test_registers_every_omp_surface(self):
        out = self.drive([])
        self.assertEqual(
            sorted(out["handlers"]),
            ["before_agent_start", "session_start", "session_stop",
             "session_switch", "tool_call", "tool_result", "turn_end"])

    def test_session_start_sets_the_status_line_and_injects_the_state(self):
        out = self.drive([{"event": "session_start"}])
        self.results(out)
        key, text = out["statuses"][0]
        self.assertEqual(key, "tezgah")
        self.assertIn("pony", text)
        message = out["sent"][0]["message"]
        self.assertIn("Graph", message["content"])
        # the contract itself rides omp's always-on RULES.md, not this message
        self.assertNotIn("**Turkish, BLUF.**", message["content"])
        self.assertIs(message["display"], False)
        self.assertEqual(out["sent"][0]["options"]["deliverAs"], "nextTurn")

    def test_before_agent_start_returns_a_hidden_reminder(self):
        out = self.drive([{"event": "before_agent_start",
                           "arg": {"prompt": "who calls calc_total?"}}])
        returned = self.results(out)[0]
        message = returned["message"]
        self.assertIn("<harness-reminder>", message["content"])
        self.assertIs(message["display"], False)
        self.assertEqual(message["attribution"], "agent")

    def test_before_agent_start_ignores_a_textless_batch(self):
        # omp fires the event for queued batches too (the continuation after a
        # blocked Stop), and those carry no prompt to arm a reminder with
        out = self.drive([{"event": "before_agent_start", "arg": {"prompt": ""}}])
        self.assertIsNone(self.results(out)[0])

    def test_tool_call_blocks_the_attribution_credit(self):
        out = self.drive([{"event": "tool_call", "arg": {
            "toolName": "bash",
            "input": {"command": 'git commit -m "x\n\nCo-Authored-By: a"'}}}])
        blocked = self.results(out)[0]
        self.assertIs(blocked["block"], True)
        self.assertIn("attribution", blocked["reason"].lower())

    def test_a_watched_tool_result_refreshes_the_status_line(self):
        # the used marks move as tools run, so the evidence call that records
        # them also carries the new status line - one subprocess, both effects
        out = self.drive([{"event": "tool_result", "arg": {
            "toolName": "task", "input": {"prompt": "x"}}}])
        self.results(out)
        key, text = out["statuses"][0]
        self.assertEqual(key, "tezgah")
        self.assertIn("orch", text)

    def test_tool_result_without_an_outcome_does_not_license_a_done_claim(self):
        out = self.drive([
            {"event": "tool_result", "arg": {"toolName": "bash",
                                             "input": {"command": "pytest -q"}}},
            {"event": "session_stop",
             "arg": {"last_assistant_message": "Done."}},
        ])
        stop = self.results(out)[1]
        self.assertEqual(stop["decision"], "block")

    def test_tool_result_with_a_passing_outcome_clears_the_done_claim(self):
        out = self.drive([
            {"event": "tool_result", "arg": {"toolName": "bash",
                                             "input": {"command": "pytest -q"},
                                             "isError": False}},
            {"event": "session_stop",
             "arg": {"last_assistant_message": "Done."}},
        ])
        self.assertIsNone(self.results(out)[1])


if __name__ == "__main__":
    unittest.main()
