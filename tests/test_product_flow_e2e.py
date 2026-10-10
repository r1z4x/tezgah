"""End-to-end smoke of the product flow: a throwaway repo with a `sales.csv`, the
real `tezgah-research next` CLI read after each step's note lands in
`.tezgah/analysis/<topic>/flow.md` (or `spec.md`), from an empty folder to a due
re-measure and then nothing left, and `check` at the end."""
import json
import os
import subprocess
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from test_research import CLI, Workspace  # noqa: E402

TOPIC = "sales-dashboard"
SALES = "day,region,orders,revenue\n2026-09-01,eu,120,8400\n2026-09-02,eu,95,6650\n"
NOTES = [
    ("research", "sales.csv export, read 2026-10-10: orders fell from 120 to 95 in "
                 "a day. Need: the team sees order swings."),
    ("metrics", "Rests on research. Goal: the team sees order swings. Signal: daily "
                "orders. Definition: orders per day / 7-day mean. Window: 7 days. "
                "Baseline: 1.0. Logged: yes (sales.csv orders)."),
    ("assumptions", "The team opens a dashboard daily."),
    ("decision", "Ship a daily orders dashboard. Metric: daily orders >= 1.0.\n"
                 "observe after: 2020-02-01"),
    ("instrumentation", "Daily orders is logged in sales.csv."),
    ("design", "OrdersChart, decision: ship a daily orders dashboard."),
    ("build", "tezgah-design check passed."),
]


class ProductFlowE2E(Workspace):
    def ok(self, repo, *args):
        proc = subprocess.run([sys.executable, CLI] + list(args), capture_output=True,
                              text=True, env=self.env(), cwd=repo, timeout=60)
        self.assertEqual(proc.returncode, 0, (args, proc.stdout + proc.stderr))
        return proc.stdout

    def steps(self, repo):
        out = self.ok(repo, "next", "--topic", TOPIC, "--json")
        return {s["id"]: s["status"] for s in json.loads(out)}

    def test_dashboard_flow_from_csv_to_re_measure(self):
        repo = self.repo()
        self.write(os.path.join(repo, "sales.csv"), SALES)
        folder = os.path.join(repo, ".tezgah", "analysis", TOPIC)
        flow = os.path.join(folder, "flow.md")
        self.assertTrue(all(s == "missing" for s in self.steps(repo).values()))

        text = "# Sales dashboard\n\n"
        for n, (step, body) in enumerate(NOTES):
            text += "## %s\n\n%s\n\n" % (step, body)
            self.write(flow, text)
            got = self.steps(repo)
            self.assertEqual(got[step], "done", step)
            # the step the next line names is the first one still missing
            nxt = self.ok(repo, "next", "--topic", TOPIC).splitlines()[-1]
            if n + 1 < len(NOTES) and step != "instrumentation":
                self.assertIn("write ## %s" % NOTES[n + 1][0], nxt)
            if step == "instrumentation":
                self.assertIn("spec.md", nxt)
                self.write(os.path.join(folder, "spec.md"),
                           "# Orders dashboard\n\nImplements: ship a daily orders "
                           "dashboard (flow.md ## decision).\n")

        before = self.steps(repo)
        self.assertEqual(before, {
            "research": "done", "metrics": "done", "assumptions": "done",
            "decision": "done", "instrumentation": "done", "forward-spec": "done",
            "design": "done", "build": "done", "re-measure": "due"})

        self.write(flow, text + "## re-measure\n\nDaily orders 1.1 >= 1.0: met "
                                "(behaviour, sales.csv orders).\n")
        after = self.steps(repo)
        self.assertTrue(all(s == "done" for s in after.values()), after)
        self.assertIn("next: nothing left", self.ok(repo, "next", "--topic", TOPIC))
        self.ok(repo, "check")


if __name__ == "__main__":
    unittest.main()
