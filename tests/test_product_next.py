"""hooks/tezgah_product.py FLOWS and next_steps, and `tezgah-research next`: the
product-flow steps of one topic, computed from the product ledger and the spec
and design contract it cites, on the research tests' throwaway-repo fixture."""
import json
import os
import subprocess
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from test_product import DAY, Ledger, dated, row, tprod  # noqa: E402
from test_research import BEFORE, CLI  # noqa: E402

STEPS = ["research", "metrics", "assumptions", "decision", "instrumentation",
         "forward-spec", "design", "build", "re-measure"]
FEATURE = [s for s in STEPS if s not in ("metrics", "instrumentation")]
EXTERNAL = {"class": "external"}
CONTRACT = '# Contract\n\n```json\n{"components": [\n  %s\n]}\n```\n'


class Flow(Ledger):
    def add(self, kind, **changes):
        rid, problems = tprod.append_row(self.main, row(kind, **changes), date=DAY)
        self.assertEqual(problems, [], kind)
        return rid

    def steps(self, today="2026-01-10", topic="export", flow="metric-dashboard",
              repo=None):
        return {s["id"]: s for s in tprod.next_steps(repo or self.main, topic, flow,
                                                     today)}

    def expect(self, done=(), due=(), ids=STEPS, **kw):
        got = [(sid, s["status"]) for sid, s in self.steps(**kw).items()]
        want = [(sid, "n/a" if sid == "build" else "done" if sid in done
                 else "due" if sid in due else "missing") for sid in ids]
        self.assertEqual(got, want)

    def ws(self, *parts):
        return os.path.join(self.main, ".tezgah", *parts)

    def spec(self, text):
        self.write(self.ws("analysis", "export", "spec.md"), text)

    def contract(self, component):
        self.write(self.ws("design-contract.md"), CONTRACT % component)

    def chain(self):
        """Every step a ledger row or file satisfies, short of the R."""
        self.add("O")
        self.add("I")
        self.add("O", **EXTERNAL)
        self.add("M")
        self.add("A")
        self.add("D")
        self.spec("# Spec\n\nfor product:D1\n")
        self.contract('{"name": "chart", "decision": "product:D1"}')


class Steps(Flow):
    def test_flows_hold_the_contracted_steps(self):
        # Kills: a step renamed, reordered or dropped; feature not the
        # metric-dashboard list minus its two M steps; a step missing a key.
        self.assertEqual([s["id"] for s in tprod.FLOWS["metric-dashboard"]], STEPS)
        self.assertEqual([s["id"] for s in tprod.FLOWS["feature"]], FEATURE)
        for step in tprod.FLOWS["metric-dashboard"]:
            self.assertEqual(sorted(step), ["command", "id", "leaves", "skill"])

    def test_each_step_flips_to_done_when_its_row_or_file_appears(self):
        # Kills, per stage: research done on an I alone (class external ignored)
        # or on an O alone; metrics, assumptions, decision or instrumentation
        # done without their row; a spec read as done without its citation; a
        # design contract read as prose instead of its decision fields; build
        # given a status; re-measure due before observe_after, or still due
        # after the R; a status kept from an earlier call instead of computed.
        self.add("O")
        self.expect()
        self.add("I")
        self.assertEqual(self.steps()["research"]["detail"], "no O of class external")
        self.add("O", **EXTERNAL)
        self.expect(done={"research"})
        self.assertEqual(self.steps()["research"]["detail"], "O2, I1")
        self.add("M")
        self.expect(done={"research", "metrics"})
        self.add("A")
        self.expect(done={"research", "metrics", "assumptions"})
        self.add("D")
        upto = {"research", "metrics", "assumptions", "decision", "instrumentation"}
        self.expect(done=upto)
        got = self.steps()
        self.assertEqual(got["re-measure"]["detail"], "D1 due on 2026-02-01")
        self.assertEqual(got["forward-spec"]["detail"],
                         ".tezgah/analysis/export/spec.md does not exist")
        self.assertEqual(got["forward-spec"]["command"],
                         "feature-audit forward mode: write "
                         ".tezgah/analysis/export/spec.md citing product:D1")
        self.spec("# Spec\n\nthe D1 decision, uncited, per product:O1\n")
        self.expect(done=upto)
        self.spec("# Spec\n\nfor product:D1\n")
        upto |= {"forward-spec"}
        self.expect(done=upto)
        self.write(self.ws("design-contract.md"), CONTRACT % '{"name": "chart"}'
                   + "\nprose naming product:D1\n")
        self.expect(done=upto)
        self.contract('{"name": "chart", "decision": "product:D1"}')
        upto |= {"design"}
        self.expect(done=upto)
        self.assertEqual(self.steps()["design"]["detail"],
                         ".tezgah/design-contract.md:5 cites product:D1")
        self.expect(done=upto, due={"re-measure"}, today="2026-03-01")
        self.assertEqual(self.steps(today="2026-03-01")["re-measure"]["command"],
                         "tezgah-research record R (decision D1)")
        self.add("R")
        self.expect(done=upto | {"re-measure"}, today="2026-03-01")

    def test_instrumentation_is_missing_while_the_m_a_d_names_is_unlogged(self):
        # Kills: instrumentation done whenever a D exists, any earlier M of the
        # signal counted (M1 logs `s` before M2 does not), any later logged M
        # counted whatever its signal (M3 logs `t`), and a later M of the same
        # signal ignored (M4 is how append-only rows instrument M2).
        base = [dated("O", "O1", **EXTERNAL), dated("I", "I1"),
                dated("M", "M1", signal="s"),
                dated("M", "M2", signal="s", logged="no"),
                dated("D", "D1", metric="M2", observe_after="2099-01-01")]
        self.hand(*base)
        got = self.steps()["instrumentation"]
        self.assertEqual((got["status"], got["detail"]),
                         ("missing", "M2 (signal 's') is logged: no"))
        self.hand(*base, dated("M", "M3", signal="t"))
        self.assertEqual(self.steps()["instrumentation"]["status"], "missing")
        self.hand(*base, dated("M", "M3", signal="t"), dated("M", "M4", signal="s"))
        self.assertEqual(self.steps()["instrumentation"]["status"], "done")

    def test_re_measure_is_due_after_observe_after_and_done_on_its_r(self):
        # Kills: a same-day observe_after read as due, an R for another D
        # counted, and done before every D of the topic has its R.
        rows = [dated("M", "M1"), dated("D", "D1", observe_after="2020-02-01")]
        self.hand(*rows)
        for today, status, detail in (
                ("2020-01-31", "missing", "D1 due on 2020-02-01"),
                ("2020-02-01", "missing", "D1 due on 2020-02-01"),
                ("2020-02-02", "due", "D1 due since 2020-02-01")):
            got = self.steps(today=today)["re-measure"]
            self.assertEqual((got["status"], got["detail"]), (status, detail), today)
        rows += [dated("D", "D2", observe_after="2020-03-01"),
                 dated("R", "R1", decision="D1")]
        self.hand(*rows)
        got = self.steps(today="2020-04-01")["re-measure"]
        self.assertEqual((got["status"], got["detail"]),
                         ("due", "D2 due since 2020-03-01"))
        self.assertEqual(self.steps(today="2020-02-15")["re-measure"]["status"],
                         "missing")
        self.hand(*rows, dated("R", "R2", decision="D2"))
        self.assertEqual(self.steps(today="2020-04-01")["re-measure"]["status"],
                         "done")

    def test_feature_skips_the_m_steps_until_the_topic_holds_an_m(self):
        # Kills: feature printing metrics/instrumentation for a topic with no M,
        # feature never adding them once the topic holds one, and a D measured
        # by another topic's M counted as a metric-dashboard decision.
        self.add("O")
        self.add("I")
        self.add("M")
        for kind in ("O", "I", "A"):
            self.add(kind, topic="share")
        self.add("D", topic="share", **{"from": ["I2", "A1", "M1"]})
        self.expect(done={"assumptions", "decision"}, ids=FEATURE, topic="share",
                    flow="feature")
        self.expect(done={"assumptions"}, topic="share")
        self.expect(done={"metrics"}, topic="export", flow="feature")

    def test_an_empty_or_unsafe_topic_holds_no_steps(self):
        # Kills: steps invented for a topic with no rows, a topic that is no
        # kebab-case name turned into a path, an unknown flow taken.
        self.assertEqual(tprod.next_steps(self.main, "export"), [])
        # a hand-written row may hold any topic; the writer never takes this one
        self.hand(dated("O", "O1"), dated("O", "O2", topic="../export"))
        self.assertEqual(tprod.next_steps(self.main, "other"), [])
        self.assertEqual(tprod.next_steps(self.main, "../export"), [])
        with self.assertRaises(ValueError):
            tprod.next_steps(self.main, "export", "roadmap")

    def test_a_linked_worktree_reads_the_main_checkout(self):
        # Kills: the worktree's own (empty) product ledger, spec or design
        # contract read instead of the main checkout's.
        self.commit(self.main, "base", when=BEFORE)
        wt = os.path.join(self.roots, "wt")
        self.git(self.main, "worktree", "add", "-q", "-b", "side", wt)
        self.chain()
        self.assertEqual(self.steps(repo=wt), self.steps())
        self.assertEqual(self.steps(repo=wt)["design"]["status"], "done")


class NextCli(Flow):
    def cli(self, *args):
        return subprocess.run([sys.executable, CLI, "next"] + list(args),
                              capture_output=True, text=True, env=self.env(),
                              cwd=self.main, timeout=60)

    def test_an_empty_topic_or_a_bad_call_is_misuse(self):
        # Kills: exit 0 (or 1) on a topic with no rows, an unknown flow taken,
        # a missing --topic defaulted, and a refusal that does not say how to
        # start the topic.
        proc = self.cli("--topic", "export")
        self.assertEqual(proc.returncode, 2, proc.stdout)
        self.assertIn("`tezgah-research record O`", proc.stderr)
        self.add("O")
        for args in (["--topic", "other"], ["--topic", "export", "--flow", "nope"],
                     [], ["--flow", "feature"], ["--topic"],
                     ["--topic", "export", "--topic", "export"],
                     ["--topic", "export", "--strict"]):
            proc = self.cli(*args)
            self.assertEqual((proc.returncode, proc.stdout), (2, ""), args)
        self.assertIn("unknown flow 'nope'",
                      self.cli("--topic", "export", "--flow", "nope").stderr)

    def test_text_lists_every_step_then_the_first_missing_one(self):
        # Kills: a numbering, bracket or separator change, the next line naming
        # a done step or the n/a build, and a non-zero exit for a report.
        self.add("O", **EXTERNAL)
        self.add("I")
        proc = self.cli("--topic", "export")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(proc.stdout, "\n".join([
            "1. research [done] research - O1, I1",
            "2. metrics [missing] product-analysis - no M resting on an I",
            "3. assumptions [missing] product-analysis - no A",
            "4. decision [missing] product-analysis - no D measured by one of the "
            "topic's M",
            "5. instrumentation [missing] product-analysis - no D names an M",
            "6. forward-spec [missing] feature-audit - no D yet",
            "7. design [missing] design-contract - no D yet",
            "8. build [n/a] design-contract - the Stop UI rule and tezgah-design "
            "check own it",
            "9. re-measure [missing] analyze-app - no D yet",
            "next: product-analysis - tezgah-research record M", ""]))

    def test_a_due_re_measure_is_next_and_an_r_leaves_nothing(self):
        # Kills: a due step skipped by the next line, and "nothing left" never
        # printed once every applicable step is done.
        self.chain()
        last = self.cli("--topic", "export").stdout.splitlines()
        self.assertEqual(last[-2], "9. re-measure [due] analyze-app - D1 due since "
                                   "2026-02-01")
        self.assertEqual(last[-1], "next: analyze-app - tezgah-research record R "
                                   "(decision D1)")
        self.add("R")
        self.assertEqual(self.cli("--topic", "export").stdout.splitlines()[-1],
                         "next: nothing left")

    def test_json_prints_the_same_steps_as_data(self):
        # Kills: --json printing text, a payload whose steps differ from
        # next_steps, and --flow ignored.
        self.add("O", **EXTERNAL)
        self.add("I")
        proc = self.cli("--topic", "export", "--json")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(json.loads(proc.stdout), tprod.next_steps(self.main, "export"))
        data = json.loads(self.cli("--json", "--flow", "feature",
                                   "--topic", "export").stdout)
        self.assertEqual([s["id"] for s in data], FEATURE)


if __name__ == "__main__":
    unittest.main()
