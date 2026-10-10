"""End-to-end smoke of the product flow: a throwaway repo with a `sales.csv`, the
real `tezgah-research` CLI recording O, I, M, A, D, the forward spec and the
design contract citing `product:D1`, `next` and the session note before and
after the R that re-measures it, and `check` at the end."""
import json
import os
import subprocess
import sys
import time
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from test_research import CLI, Workspace  # noqa: E402

TOPIC = "sales-dashboard"
PAST = "2020-01-01"
DUE_AFTER = "2020-02-01"
SALES = "day,region,orders,revenue\n2026-09-01,eu,120,8400\n2026-09-02,eu,95,6650\n"

ROWS = [
    ("O", {"topic": TOPIC, "from": [], "class": "external",
           "source": "sales.csv export, rows 2026-09-01..02",
           "quote": "orders fell from 120 to 95 in a day"}),
    ("I", {"topic": TOPIC, "from": ["O1"],
           "statement": "daily orders swing and nobody sees it",
           "confidence": "high"}),
    ("M", {"topic": TOPIC, "from": ["I1"], "goal": "the team sees order swings",
           "signal": "daily orders", "definition": "orders per day / 7-day mean",
           "window": "7 days", "baseline": "1.0", "direction": "up",
           "leading": True, "logged": "yes", "data": "sales.csv orders"}),
    ("A", {"topic": TOPIC, "from": ["I1"], "kind": "desirability",
           "statement": "the team opens a dashboard daily",
           "importance": "high", "evidence": "weak"}),
    ("D", {"topic": TOPIC, "from": ["I1", "A1", "M1"],
           "statement": "ship a daily orders dashboard", "outcome": "bet",
           "metric": "M1", "threshold": ">= 1.0", "reopen": "below 0.8 for a week"}),
]
R = {"topic": TOPIC, "from": ["D1"], "decision": "D1", "verdict": "met",
     "value": "1.1", "class": "behaviour", "source": "sales.csv orders"}

CONTRACT = """# Design contract

```json
%s
```
""" % json.dumps({"components": [{"name": "OrdersChart",
                                  "decision": "product:D1"}]}, indent=2)


class ProductFlowE2E(Workspace):
    def run_cli(self, repo, *args, stdin=""):
        return subprocess.run([sys.executable, CLI] + list(args), input=stdin,
                              capture_output=True, text=True, env=self.env(),
                              cwd=repo, timeout=60)

    def ok(self, repo, *args, stdin=""):
        proc = self.run_cli(repo, *args, stdin=stdin)
        self.assertEqual(proc.returncode, 0, (args, proc.stdout + proc.stderr))
        return proc.stdout

    def steps(self, repo):
        out = self.ok(repo, "next", "--topic", TOPIC, "--json")
        return {s["id"]: s["status"] for s in json.loads(out)}

    def backdate_decision(self, repo):
        """The writer stamps today and refuses an observe_after before it, so the
        D is recorded today and then moved into the past by hand: the only way a
        smoke run on one day sees a re-measure come due."""
        path = os.path.join(repo, ".tezgah", "product", "ledger.jsonl")
        with open(path) as fh:
            rows = [json.loads(line) for line in fh if line.strip()]
        for row in rows:
            if row["id"] == "D1":
                row.update(date=PAST, observe_after=DUE_AFTER)
        self.write(path, "".join(json.dumps(r) + "\n" for r in rows))

    def test_dashboard_flow_from_csv_to_re_measure(self):
        repo = self.repo()
        self.write(os.path.join(repo, "sales.csv"), SALES)
        for kind, row in ROWS:
            if kind == "D":
                row = dict(row, observe_after=time.strftime("%Y-%m-%d"))
            self.assertEqual(self.ok(repo, "record", kind, stdin=json.dumps(row)).strip(),
                             "recorded %s1" % kind)
        self.backdate_decision(repo)
        self.write(os.path.join(repo, ".tezgah", "analysis", TOPIC, "spec.md"),
                   "# Orders dashboard\n\nDecision: product:D1\n")
        self.write(os.path.join(repo, ".tezgah", "design-contract.md"), CONTRACT)

        before = self.steps(repo)
        self.assertEqual(before, {
            "research": "done", "metrics": "done", "assumptions": "done",
            "decision": "done", "instrumentation": "done", "forward-spec": "done",
            "design": "done", "build": "n/a", "re-measure": "due"})
        self.assertIn("Product: D1 (%s)" % TOPIC, self.session_note(repo))

        self.assertEqual(self.ok(repo, "record", "R", stdin=json.dumps(R)).strip(),
                         "recorded R1")
        self.assertNotIn("Product:", self.session_note(repo))
        after = self.steps(repo)
        self.assertEqual(after["re-measure"], "done")
        self.assertTrue(all(s in ("done", "n/a") for s in after.values()), after)
        self.assertIn("next: nothing left", self.ok(repo, "next", "--topic", TOPIC))
        self.ok(repo, "check")


if __name__ == "__main__":
    unittest.main()
