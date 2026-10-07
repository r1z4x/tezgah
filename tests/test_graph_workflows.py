"""workflows/graph-review.js and graph-impact.js: a failed agent is unknown.

The Workflow runtime answers a failed `agent()` with null. Both scripts used
to filter those nulls away and then read the silence as a result: every review
dimension failing returned "all four dimensions came back clean", a finding
whose refuters all failed was listed as refuted, a failed planner vanished and
a failed sweep became `graph_blind_spots: []`. These run each script through a
stub runtime (`tests/_workflow_harness.mjs`) and require every failure to be
named in `unknown` instead.
"""
import json
import os
import shutil
import subprocess
import unittest

import support

HARNESS = os.path.join(support.TESTS, "_workflow_harness.mjs")
REVIEW = os.path.join(support.REPO, "workflows", "graph-review.js")
IMPACT = os.path.join(support.REPO, "workflows", "graph-impact.js")
HAVE_NODE = shutil.which("node")
SCOPE = {"changed_files": ["a.py"], "changed_symbols": ["f"], "impacted_modules": ["m"]}
FINDING = {"title": "off by one", "file": "a.py", "line": 3, "summary": "s",
           "failure_scenario": "x -> crash", "severity": "high"}
TRACE = {"resolved_target": "f a.py:1", "call_sites": [
    {"module": "m1", "file": "b.py", "symbol": "g"},
    {"module": "m2", "file": "c.py", "symbol": "h"}]}


def run(workflow, args, agents):
    out = subprocess.run(["node", HARNESS], input=json.dumps(
        {"workflow": workflow, "args": args, "agents": agents}),
        capture_output=True, text=True, timeout=60)
    data = json.loads(out.stdout)
    if "error" in data and "result" not in data:
        raise AssertionError(data["error"])
    return data["result"]


@unittest.skipUnless(HAVE_NODE, "node missing")
class EveryWorkflowParses(unittest.TestCase):
    def test_each_script_runs_to_a_result(self):
        # graph-impact shipped with one closing paren too many: the runtime
        # could not parse it, so the workflow never loaded at all
        for name in sorted(os.listdir(os.path.join(support.REPO, "workflows"))):
            if name.endswith(".js"):
                path = os.path.join(support.REPO, "workflows", name)
                self.assertIsInstance(run(path, "x", {}), dict, name)


@unittest.skipUnless(HAVE_NODE, "node missing")
class GraphReview(unittest.TestCase):
    def test_every_dimension_failing_is_unknown_not_clean(self):
        res = run(REVIEW, "main", {"scope": SCOPE})
        self.assertNotIn("came back clean", res["note"])
        self.assertEqual(["review:correctness", "review:callers", "review:security",
                          "review:tests"], res["unknown"])

    def test_one_failed_dimension_is_named_beside_empty_ones(self):
        res = run(REVIEW, "main", {"scope": SCOPE, "review:": {"findings": []},
                                   "review:security": None})
        self.assertEqual(["review:security"], res["unknown"])
        self.assertIn("not clean", res["note"])

    def test_all_dimensions_empty_is_clean(self):
        res = run(REVIEW, "main", {"scope": SCOPE, "review:": {"findings": []}})
        self.assertEqual([], res["unknown"])
        self.assertIn("came back clean", res["note"])

    def test_a_failed_scope_agent_is_unknown_not_no_changes(self):
        res = run(REVIEW, "main", {})
        self.assertEqual(["scope"], res["unknown"])
        self.assertNotIn("no changes", res["note"])

    def test_a_finding_whose_refuters_all_failed_is_unverified_not_refuted(self):
        res = run(REVIEW, "main", {"scope": SCOPE, "review:": {"findings": []},
                                   "review:correctness": {"findings": [FINDING]}})
        self.assertEqual([], res["refuted"])
        self.assertEqual([], res["confirmed"])
        self.assertEqual(["off by one"], [f["title"] for f in res["unverified"]])
        self.assertIn("verify:off by one", res["unknown"])

    def test_a_live_refutation_still_refutes(self):
        res = run(REVIEW, "main", {"scope": SCOPE, "review:": {"findings": []},
                                   "review:correctness": {"findings": [FINDING]},
                                   "verify:": {"refuted": True, "reasoning": "guarded"}})
        self.assertEqual(["off by one"], [f["title"] for f in res["refuted"]])
        self.assertEqual([], res["unknown"])


@unittest.skipUnless(HAVE_NODE, "node missing")
class GraphImpact(unittest.TestCase):
    def test_a_failed_planner_is_unknown(self):
        res = run(IMPACT, "f", {"trace": TRACE, "plan:m1": {"module": "m1", "edits": []},
                                "sweep": {"missed": [], "searched": "f"}})
        self.assertEqual(["plan:m2"], res["unknown"])
        self.assertEqual(1, len(res["plans"]))

    def test_a_failed_sweep_is_not_an_empty_blind_spot_list(self):
        res = run(IMPACT, "f", {"trace": TRACE, "plan:": {"module": "m", "edits": []}})
        self.assertEqual(["sweep"], res["unknown"])
        self.assertNotEqual([], res["graph_blind_spots"])
        self.assertIn("unknown", res["graph_blind_spots"])

    def test_a_clean_sweep_reports_no_blind_spots(self):
        res = run(IMPACT, "f", {"trace": TRACE, "plan:": {"module": "m", "edits": []},
                                "sweep": {"missed": [], "searched": "f"}})
        self.assertEqual([], res["unknown"])
        self.assertEqual([], res["graph_blind_spots"])

    def test_a_failed_trace_is_unknown(self):
        res = run(IMPACT, "f", {})
        self.assertEqual(["trace"], res["unknown"])
        self.assertNotIn("graph_blind_spots", res)


if __name__ == "__main__":
    unittest.main()
