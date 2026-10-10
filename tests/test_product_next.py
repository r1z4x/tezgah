"""hooks/tezgah_product.py FLOWS and next_steps, and `tezgah-research next`: the
product-flow steps of one topic, computed from the topic's files under
`.tezgah/analysis/<topic>/` on the research tests' throwaway-repo fixture."""
import json
import os
import subprocess
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from test_research import CLI, REPO, Workspace  # noqa: E402

sys.path.insert(0, os.path.join(REPO, "hooks"))
import tezgah_product as tprod  # noqa: E402

STEPS = ["research", "metrics", "assumptions", "decision", "instrumentation",
         "forward-spec", "design", "build", "re-measure"]
FEATURE = [s for s in STEPS if s not in ("metrics", "instrumentation")]
NOTED = [s for s in STEPS if s != "forward-spec"]


class Flow(Workspace):
    def setUp(self):
        super().setUp()
        self.main = self.repo()

    def folder(self, topic="export"):
        return os.path.join(self.main, ".tezgah", "analysis", topic)

    def notes(self, *sections, topic="export"):
        """flow.md holding one `## <step>` heading per (step, body)."""
        self.write(os.path.join(self.folder(topic), "flow.md"), "# Export\n\n" + "".join(
            "## %s\n\n%s\n\n" % (s, body) for s, body in sections))

    def spec(self, topic="export"):
        self.write(os.path.join(self.folder(topic), "spec.md"), "# Spec\n")

    def steps(self, today="2026-01-10", topic="export", flow="metric-dashboard"):
        return {s["id"]: s for s in tprod.next_steps(self.main, topic, flow, today)}

    def expect(self, done=(), due=(), ids=STEPS, **kw):
        got = [(sid, s["status"]) for sid, s in self.steps(**kw).items()]
        want = [(sid, "done" if sid in done else "due" if sid in due else "missing")
                for sid in ids]
        self.assertEqual(got, want)


class Steps(Flow):
    def test_flows_hold_the_contracted_steps(self):
        # Kills: a step renamed, reordered or dropped; feature not the
        # metric-dashboard list minus its two metric steps; a step missing a key.
        self.assertEqual(set(tprod.FLOWS), {"metric-dashboard", "feature"})
        self.assertEqual([s["id"] for s in tprod.FLOWS["metric-dashboard"]], STEPS)
        self.assertEqual([s["id"] for s in tprod.FLOWS["feature"]], FEATURE)
        for step in tprod.FLOWS["metric-dashboard"]:
            self.assertEqual(sorted(step), ["command", "id", "leaves", "skill"])

    def test_each_step_flips_to_done_when_its_file_appears(self):
        # Kills, per stage: a step done without its heading, a heading counted
        # for another step, `###` read as a step heading, the spec read from
        # flow.md, a status kept from an earlier call instead of computed.
        self.expect()
        done = set()
        for sid in NOTED:
            self.notes(*[(s, "note") for s in done | {sid}])
            done.add(sid)
            self.expect(done=done)
            if sid == "instrumentation":
                self.notes(*[(s, "x") for s in done], ("forward-spec", "x"))
                self.expect(done=done)
                self.spec()
                done.add("forward-spec")
                self.expect(done=done)
        self.notes(("### research", "deeper"), ("Research", "case"))
        self.assertEqual(self.steps()["research"]["status"], "done")
        self.notes(("### research", "deeper"))
        self.assertEqual(self.steps()["research"]["status"], "missing")
        self.assertEqual(self.steps()["research"]["detail"],
                         "no ## research in .tezgah/analysis/export/flow.md")

    def test_re_measure_is_due_after_observe_after_and_done_on_its_note(self):
        # Kills: a same-day or future date read as due, a passed date ignored, a
        # date outside the decision section counted, a re-measure note ignored.
        self.notes(("decision", "ship it\nobserve after: 2020-02-01"))
        for today, status, detail in (
                ("2020-01-31", "missing", "observe after 2020-02-01, not yet"),
                ("2020-02-01", "missing", "observe after 2020-02-01, not yet"),
                ("2020-02-02", "due", "observe after 2020-02-01 has passed"),
                ("2099-01-01", "due", "observe after 2020-02-01 has passed")):
            got = self.steps(today=today)["re-measure"]
            self.assertEqual((got["status"], got["detail"]), (status, detail), today)
        self.notes(("decision", "observe after: 2099-01-01"))
        self.assertEqual(self.steps(today="2026-10-10")["re-measure"]["status"],
                         "missing")
        self.notes(("research", "observe after: 2020-02-01"), ("decision", "no date"))
        got = self.steps()["re-measure"]
        self.assertEqual((got["status"], got["detail"]), (
            "missing", "no observe after: in .tezgah/analysis/export/flow.md "
                       "## decision"))
        self.notes(("decision", "observe after: 2020-02-01"), ("re-measure", "met"))
        self.assertEqual(self.steps()["re-measure"]["status"], "done")

    def test_commands_name_files_and_the_design_check_never_a_ledger(self):
        # Kills: a command naming a cut ledger command or a `product:` token,
        # design or build not pointing at the design check, `{topic}` unfilled.
        for step in self.steps(topic="sales").values():
            self.assertNotIn("record", step["command"])
            self.assertNotIn("product:", step["command"])
            self.assertNotIn("{", step["command"])
        got = self.steps(topic="sales")
        self.assertEqual(got["research"]["command"],
                         "write ## research in .tezgah/analysis/sales/flow.md")
        self.assertEqual(got["forward-spec"]["command"],
                         "feature-audit forward mode: write "
                         ".tezgah/analysis/sales/spec.md naming the decision")
        for sid in ("design", "build"):
            self.assertTrue(got[sid]["command"].startswith("tezgah-design check"), sid)

    def test_feature_skips_the_metric_steps_until_flow_md_holds_metrics(self):
        # Kills: feature printing metrics/instrumentation without `## metrics`,
        # and never adding them once the topic holds one.
        self.notes(("research", "x"))
        self.expect(done={"research"}, ids=FEATURE, flow="feature")
        self.notes(("research", "x"), ("metrics", "orders per day"))
        self.expect(done={"research", "metrics"}, flow="feature")

    def test_a_missing_folder_or_unsafe_topic_lists_every_step_missing(self):
        # Kills: [] or an error for a topic with no folder, a topic that is no
        # kebab-case name turned into a path, an unknown flow taken.
        self.expect()
        outside = os.path.join(self.main, ".tezgah", "x")
        self.write(os.path.join(outside, "flow.md"), "## research\n")
        self.write(os.path.join(outside, "spec.md"), "# Spec\n")
        for topic in ("../x", "X", "a" * 65, "", None):
            got = tprod.next_steps(self.main, topic)
            self.assertEqual([s["status"] for s in got], ["missing"] * 9, topic)
            self.assertIn("<topic>", got[0]["command"])
        with self.assertRaises(ValueError):
            tprod.next_steps(self.main, "export", "roadmap")


class NextCli(Flow):
    def cli(self, *args):
        return subprocess.run([sys.executable, CLI, "next"] + list(args),
                              capture_output=True, text=True, env=self.env(),
                              cwd=self.main, timeout=60)

    def test_a_bad_call_is_misuse_and_an_empty_topic_is_a_report(self):
        # Kills: exit 2 on a topic with no folder yet, an unknown flow taken, a
        # missing --topic defaulted.
        proc = self.cli("--topic", "export")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(proc.stdout.count("[missing]"), 9)
        for args in (["--topic", "export", "--flow", "nope"], [],
                     ["--flow", "feature"], ["--topic"],
                     ["--topic", "export", "--topic", "export"],
                     ["--topic", "export", "--strict"]):
            proc = self.cli(*args)
            self.assertEqual((proc.returncode, proc.stdout), (2, ""), args)
        self.assertIn("unknown flow 'nope'",
                      self.cli("--topic", "export", "--flow", "nope").stderr)

    def test_text_lists_every_step_then_the_first_missing_one(self):
        # Kills: a numbering, bracket or separator change, and the next line
        # naming a done step.
        self.notes(("research", "a source, read 2026-10-10"))
        proc = self.cli("--topic", "export")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        flow = ".tezgah/analysis/export/flow.md"
        self.assertEqual(proc.stdout, "\n".join([
            "1. research [done] research - %s ## research" % flow,
            "2. metrics [missing] product-analysis - no ## metrics in %s" % flow,
            "3. assumptions [missing] product-analysis - no ## assumptions in %s"
            % flow,
            "4. decision [missing] product-analysis - no ## decision in %s" % flow,
            "5. instrumentation [missing] product-analysis - no ## instrumentation "
            "in %s" % flow,
            "6. forward-spec [missing] feature-audit - "
            ".tezgah/analysis/export/spec.md does not exist",
            "7. design [missing] design-contract - no ## design in %s" % flow,
            "8. build [missing] design-contract - no ## build in %s" % flow,
            "9. re-measure [missing] analyze-app - no observe after: in %s "
            "## decision" % flow,
            "next: product-analysis - write ## metrics in %s" % flow, ""]))

    def test_a_due_re_measure_is_next_and_its_note_leaves_nothing(self):
        # Kills: a due step skipped by the next line, and "nothing left" never
        # printed once every step is done.
        body = [(s, "x") for s in NOTED if s not in ("decision", "re-measure")]
        self.notes(*body, ("decision", "observe after: 2020-02-01"))
        self.spec()
        last = self.cli("--topic", "export").stdout.splitlines()
        self.assertEqual(last[-2], "9. re-measure [due] analyze-app - observe after "
                                   "2020-02-01 has passed")
        self.assertEqual(last[-1], "next: analyze-app - measure the decision's metric "
                                   "again, then write ## re-measure in "
                                   ".tezgah/analysis/export/flow.md")
        self.notes(*body, ("decision", "observe after: 2020-02-01"), ("re-measure", "met"))
        self.assertEqual(self.cli("--topic", "export").stdout.splitlines()[-1],
                         "next: nothing left")

    def test_json_prints_the_same_steps_as_data(self):
        # Kills: --json printing text, a payload whose steps differ from
        # next_steps, and --flow ignored.
        self.notes(("research", "x"))
        proc = self.cli("--topic", "export", "--json")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(json.loads(proc.stdout), tprod.next_steps(self.main, "export"))
        data = json.loads(self.cli("--json", "--flow", "feature",
                                   "--topic", "export").stdout)
        self.assertEqual([s["id"] for s in data], FEATURE)


if __name__ == "__main__":
    unittest.main()
