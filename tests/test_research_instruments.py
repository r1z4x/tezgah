"""Unit tests of hooks/tezgah_research_evidence.py: the certainty engine, the instrument
ledger and its commands, release-check and calibration (spec sections 1, 2, 3.1, 3.2, 3.4,
4.3). The capture module's writers, its network call and its two verdicts
(write_capture, commit_capture, fetch_url, append_rows, citation_problem,
quote_problem) are replaced by stubs so these run on this module alone. The stub
stands in `sys.modules` only while this module's tests run (setUpModule /
tearDownModule): the evidence module imports capture lazily, so a stub left there
would answer every other test module's checks in the same process."""
import contextlib
import hashlib
import io
import json
import os
import shutil
import sys
import tempfile
import types
import unittest

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO, "hooks"))

import tezgah_research_capture as _real_capture  # noqa: E402

CAP = types.ModuleType("tezgah_research_capture")
CAP.__dict__.update({k: v for k, v in vars(_real_capture).items()
                     if not k.startswith("__")})
CAP.commits = []
CAP.answers = {}


def _write_capture(base, rel, data):
    path = os.path.join(base, rel)
    if os.path.exists(path):
        with open(path, "rb") as fh:
            return None if fh.read() == data else "capture exists: %s" % rel
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "wb") as fh:
        fh.write(data)
    return None


CAP.write_capture = _write_capture
CAP.commit_capture = lambda repo, base, rels, command, slug: CAP.commits.append(
    (tuple(rels), command, slug))
CAP.fetch_url = lambda url, body=None, headers=None: CAP.answers.get(
    "POST %s %s" % (url, hashlib.sha256(body).hexdigest()), (404, b""))


def _append_rows(base, rel, objs):
    path = os.path.join(base, rel)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "a", encoding="utf-8") as fh:
        fh.write("".join(json.dumps(o) + "\n" for o in objs))


CAP.append_rows = _append_rows
CAP.citation_problem = lambda row: None if row.get("title", "").startswith("Sound") \
    else "resolves in no registry"
CAP.quote_problem = lambda quote, text: None if quote in text \
    else "quote not in the captured source text"


def setUpModule():
    sys.modules["tezgah_research_capture"] = CAP


def tearDownModule():
    sys.modules["tezgah_research_capture"] = _real_capture


import tezgah_research as tr  # noqa: E402
import tezgah_research_evidence as ev  # noqa: E402


def rows(*objs):
    return "".join(json.dumps(o) + "\n" for o in objs)


class Line(unittest.TestCase):
    """A research line on disk with no git: `.tezgah/research/open/q`."""

    def setUp(self):
        self.repo = tempfile.mkdtemp(prefix="evidence-unit-")
        self.addCleanup(shutil.rmtree, self.repo)
        self.base = os.path.join(self.repo, ".tezgah", "research", "open", "q")
        os.makedirs(self.base)
        self.put("state.json", json.dumps({"rules": 8, "phase": "concluded"}))
        CAP.commits.clear()
        CAP.answers.clear()

    def put(self, rel, text):
        path = os.path.join(self.base, rel)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(text)

    def run_cmd(self, name, args, stdin=""):
        out = io.StringIO()
        old = sys.stdin
        sys.stdin = io.StringIO(stdin)
        try:
            with contextlib.redirect_stdout(out), contextlib.redirect_stderr(out):
                code = ev.COMMANDS[name](self.repo, args)
        finally:
            sys.stdin = old
        return code, out.getvalue()

    def check(self, steps=None, strict=False):
        errors, warnings, steps = [], [], steps if steps is not None else {}
        ev.check(self.repo, "q", self.base, tr._state(self.base), errors, warnings, strict,
                 False, steps)
        return errors, warnings, steps

    def items(self, name, arm_outcomes, h="h2", mde="0.10"):
        self.put("experiments/%s/protocol.md" % h, "change: x\ndesign: experiment\nmde: %s\n"
                 % mde)
        out = []
        for arm, values in arm_outcomes.items():
            out += [{"item": "i%03d" % n, "arm": arm, "instrument": name, "outcome": v,
                     "text": "row %d" % n} for n, v in enumerate(values, 1)]
        self.put("experiments/%s/results.jsonl" % h, rows(*out))

    def gold_and_label(self, name, arm, n, seed, wrong=0):
        code, out = self.run_cmd("gold", ["q", name, "--arm", arm, "--n", str(n),
                                          "--seed", str(seed)])
        self.assertEqual(code, 0, out)
        with open(os.path.join(self.base, "instruments/gold/%s-%s-%d.json"
                               % (name, arm, seed))) as fh:
            drawn = json.load(fh)["items"]
        outcomes = {r["item"]: r["outcome"] for r in ev._rows(self.base,
                    "experiments/h2/results.jsonl") if r["arm"] == arm}
        labels = rows(*({"item": i, "truth": 1 - outcomes[i] if k < wrong else outcomes[i]}
                        for k, i in enumerate(drawn)))
        code, out = self.run_cmd("label", ["q", name, "--arm", arm, "--human", "r",
                                           "--ack", "the user labelled them"], labels)
        self.assertEqual(code, 0, out)
        return drawn


class Certainty(Line):
    def test_step_table_holds_every_section_two_name_with_its_effect(self):
        self.assertEqual(len(ev.STEPS), 41)
        self.assertEqual(ev.STEPS["no-interval"], ev.CEIL)
        self.assertEqual(ev.STEPS["no-replication"], ev.DEC)
        # review round two: the false refusals that became steps
        for name in ("falsifier-not-evaluable", "one-provider", "screened-outside-search"):
            self.assertEqual(ev.STEPS[name], ev.DEC, name)

    def test_decrements_apply_before_the_ceiling_and_each_step_once(self):
        self.assertEqual(ev.compute(3, ["no-power-plan", "no-power-plan"]),
                         (2, ["no-power-plan"]))
        self.assertEqual(ev.compute(3, ["no-interval", "no-replication"])[0], 1)
        self.assertEqual(ev.compute(1, ["no-interval", "no-replication"])[0], 0)
        self.assertEqual(ev.compute(0, ["untraced-number"])[0], 0)

    def test_start_levels_follow_the_parts_the_proof_cites(self):
        self.put("experiments/h1/protocol.md", "change: cache\n")
        self.put("experiments/h3/protocol.md", "metric: p95\n")
        self.put("experiments/h4/protocol.md", "change: x\ndesign: observational\n")
        classes = {"a.md": "formal", "b.md": "grey", "c.md": "agent-report"}

        def start(**claim):
            return ev.LEVELS[ev.start_level(claim, self.base, classes)]
        self.assertEqual(start(proof=["experiments/h1/results.jsonl"]), "high")
        self.assertEqual(start(proof=["experiments/h3/results.jsonl"]), "low")
        self.assertEqual(start(proof=["experiments/h4/results.jsonl"]), "low")
        self.assertEqual(start(proof=["literature/a.md", "literature/b.md"]), "moderate")
        self.assertEqual(start(proof=["literature/b.md"]), "low")
        self.assertEqual(start(proof=["literature/c.md"]), "very-low")
        self.assertEqual(start(kind="code", proof=["findings.md"]), "high")
        self.assertEqual(start(kind="derivation", proof=["findings.md"]), "moderate")

    def test_check_prints_each_claim_and_refuses_a_declared_level_above_it(self):
        self.put("experiments/h1/protocol.md", "change: cache\n")
        self.put("claims.jsonl", rows(
            {"id": "C1", "proof": ["experiments/h1/results.jsonl"], "certainty": "high"},
            {"id": "C2", "proof": ["experiments/h1/results.jsonl"]}))
        self.put("to_human/report.md", "- C1: low, exploratory\n- C2: high\n")
        errors, warnings, steps = self.check({"C1": ["no-power-plan", "no-replication"]})
        self.assertIn("certainty q: C1 low start=high steps=no-power-plan,no-replication",
                      steps["#report"])
        self.assertIn("certainty q: C2 high start=high steps=none", steps["#report"])
        self.assertEqual(steps["#certainty"]["C1"],
                         {"level": "low", "start": "high",
                          "steps": ["no-power-plan", "no-replication"]})
        self.assertEqual(errors, ["claim C1 declares certainty high above the computed low "
                                  "(no-power-plan,no-replication)"])
        self.assertEqual(warnings, [])

    def test_report_without_the_level_or_exploratory_warns_and_strict_fails(self):
        self.put("experiments/h1/protocol.md", "change: cache\n")
        self.put("claims.jsonl", rows({"id": "C1", "proof": ["experiments/h1/results.jsonl"]},
                                      {"id": "C10", "proof": ["experiments/h1/results.jsonl"]}))
        self.put("to_human/report.md", "- C1: very-low\n- C10: high\n")
        errors, warnings, _ = self.check({"C1": ["no-interval"]})
        self.assertEqual(warnings, ["report states no certainty for claim C1"])
        errors, warnings, _ = self.check({"C1": ["no-interval"]}, strict=True)
        self.assertEqual(errors, ["report states no certainty for claim C1"])


class Instruments(Line):
    def test_seventy_two_clean_items_per_arm_validate_and_conclude_passes(self):
        self.run_cmd("instrument", ["add", "q", "j", "--kind", "measure", "--rung", "R4",
                                    "--construct", "slow"])
        self.items("j", {"a": [k % 2 for k in range(80)], "b": [k % 2 for k in range(80)]})
        self.gold_and_label("j", "a", 72, 5)
        self.gold_and_label("j", "b", 72, 5)
        _, _, steps = self.check()
        self.assertIn("instrument q: j arm a n=72 errors=0 upper=0.0499", steps["#report"])
        self.assertIn("instrument q: j validated sum=0.0999 threshold=0.1000", steps["#report"])
        self.assertEqual(ev.conclude_problems(self.repo, "q", self.base, {}), [])
        self.assertEqual([c[1] for c in CAP.commits],
                         ["instrument add", "gold", "label", "gold", "label"])

    def test_rejected_instrument_caps_its_claims_and_blocks_conclude_until_switched(self):
        self.run_cmd("instrument", ["add", "q", "j", "--kind", "measure", "--rung", "R4",
                                    "--construct", "slow"])
        self.items("j", {"base": [1, 0] * 5, "cache": [0, 1] * 5})
        self.gold_and_label("j", "base", 10, 1, wrong=4)
        self.put("claims.jsonl", rows({"id": "C3", "proof": ["experiments/h2/results.jsonl"]}))
        _, _, steps = self.check()
        self.assertIn("instrument-rejected", steps["C3"])
        self.assertTrue(any(r.startswith("instrument q: j rejected ") for r in steps["#report"]))
        problems = ev.conclude_problems(self.repo, "q", self.base, {})
        self.assertEqual(len(problems), 1)
        self.assertIn("has no switch or narrowing row", problems[0])
        code, out = self.run_cmd("switch", ["q", "j", "--narrow", "C3 reports output only",
                                            "--reason", "4 of 10 disagree"])
        self.assertEqual(code, 0, out)
        self.assertEqual(ev.conclude_problems(self.repo, "q", self.base, {}), [])

    def test_one_labelled_arm_leaves_the_instrument_unvalidated(self):
        self.run_cmd("instrument", ["add", "q", "j", "--kind", "measure", "--rung", "R4",
                                    "--construct", "slow"])
        self.items("j", {"a": [0] * 80, "b": [0] * 80})
        self.gold_and_label("j", "a", 72, 5)
        self.put("claims.jsonl", rows({"id": "C3", "proof": ["experiments/h2/results.jsonl"]}))
        _, _, steps = self.check()
        self.assertIn("instrument-unvalidated", steps["C3"])

    def test_gold_refusals_and_misuse(self):
        self.run_cmd("instrument", ["add", "q", "j", "--kind", "measure", "--rung", "R4",
                                    "--construct", "slow"])
        self.items("j", {"a": [0] * 10})
        code, out = self.run_cmd("gold", ["q", "j", "--arm", "a", "--n", "11", "--seed", "1"])
        self.assertEqual(code, 1, out)
        drawn = self.gold_and_label("j", "a", 5, 1)
        self.assertEqual(drawn, ev.seeded_draw(["i%03d" % k for k in range(1, 11)], 1, "a", 5))
        code, out = self.run_cmd("gold", ["q", "j", "--arm", "a", "--n", "5", "--seed", "2"])
        self.assertEqual(code, 1, out)
        self.assertIn("gold draw after labels", out)
        outside = next(i for i in ("i%03d" % k for k in range(1, 11)) if i not in drawn)
        code, out = self.run_cmd("label", ["q", "j", "--arm", "a", "--human", "r", "--ack",
                                           "ok"], rows({"item": outside, "truth": 0}))
        self.assertEqual(code, 1, out)
        self.assertIn("not in the gold sample", out)
        code, _ = self.run_cmd("label", ["q", "j", "--arm", "a", "--human", "r"],
                               rows({"item": drawn[0], "truth": 0}))
        self.assertEqual(code, 2)
        code, _ = self.run_cmd("gold", ["nope", "j", "--arm", "a", "--n", "1", "--seed", "1"])
        self.assertEqual(code, 2)

    def test_the_owner_may_record_a_redraw_after_labels(self):
        """K6 rater X6: `gold draw after labels` was permanent for that instrument and
        arm, so a sample drawn over a small item set could never grow. The owner records a
        redraw with their words; the latest redraw is the draw every rule reads."""
        self.run_cmd("instrument", ["add", "q", "j", "--kind", "measure", "--rung", "R4",
                                    "--construct", "slow"])
        self.items("j", {"a": [0] * 10})
        self.gold_and_label("j", "a", 5, 1)
        code, out = self.run_cmd("gold", ["q", "j", "--arm", "a", "--n", "6", "--seed", "2",
                                          "--redraw"])
        self.assertEqual(code, 2, out)
        code, out = self.run_cmd("gold", ["q", "j", "--arm", "a", "--n", "6", "--seed", "2",
                                          "--redraw", "--ack", "the sample was too small"])
        self.assertEqual(code, 0, out)
        draws = ev.first_draws(self.base)
        self.assertEqual(len(draws[("j", "a")]["items"]), 6)
        self.assertTrue(draws[("j", "a")].get("redraw"))

    def test_a_sample_too_small_to_reach_the_threshold_leaves_the_instrument_unvalidated(self):
        """K6 rater Y6: 12 gold items with no error read `rejected` against an mde of 0.2,
        and `conclude` then held the line. The sample cannot decide - even 0 errors leaves
        a sum of uppers above the threshold - so the instrument is unvalidated, not
        rejected."""
        upper = ev.st.clopper_pearson(0, 12)[1]
        arms = {"a": upper, "b": upper}
        self.assertGreaterEqual(2 * upper, 0.2)
        self.assertEqual(ev.judge_status("measure", arms, 0.2)[0], "rejected")
        self.assertEqual(ev.judge_status("measure", arms, 0.2, 2 * upper)[0], "unvalidated")
        # a sample big enough to decide still rejects on its own uppers
        big = ev.st.clopper_pearson(0, 72)[1]
        self.assertEqual(ev.judge_status("measure", {"a": big, "b": big}, 0.2,
                                         2 * big)[0], None)

    def test_gold_and_label_read_the_rows_source_writes(self):
        """Review round two K-7: rows `source` files with `--instrument`, `--arm` and
        `--item` are instrument items, so `gold` draws them and `label` reads them."""
        orx = os.path.join(self.repo, "orx")
        with open(orx, "w", encoding="utf-8") as fh:
            fh.write("#!/bin/sh\necho 'outcome 1'\necho 'outcome 0'\n")
        os.chmod(orx, 0o755)
        self.put("experiments/h2/protocol.md", "change: x\ndesign: experiment\nmde: 0.10\n")
        for n in range(4):
            _, problems = tr.source_run(self.repo, "q", "h2", "r%d" % n, orx, arm="flagged",
                                        item="i%d" % n, instrument="kw",
                                        values=[("outcome", str(n % 2))])
            self.assertEqual(problems, [])
        code, out = self.run_cmd("gold", ["q", "kw", "--arm", "flagged", "--n", "4",
                                          "--seed", "1"])
        self.assertEqual(code, 0, out)
        code, out = self.run_cmd("label", ["q", "kw", "--arm", "flagged", "--human", "r",
                                           "--ack", "the user labelled them"],
                                 rows(*({"item": "i%d" % n, "truth": n % 2} for n in range(4))))
        self.assertEqual(code, 0, out)
        self.assertEqual(sorted((r["item"], r["output"]) for r in ev._rows(self.base, ev.LABELS)),
                         [("i0", 0), ("i1", 1), ("i2", 0), ("i3", 1)])

    def test_hand_drawn_gold_file_is_refused_and_repeated_label_warns(self):
        self.items("j", {"a": [0] * 20})
        drawn = ev.seeded_draw(["i%03d" % k for k in range(1, 21)], 7, "a", 5)
        forged = sorted({"i%03d" % k for k in range(1, 21)} - set(drawn))[:5]
        self.put("instruments/gold/j-a-7.json", json.dumps(
            {"instrument": "j", "arm": "a", "seed": 7, "n": 5, "items": forged}))
        self.put("instruments/GOLD.jsonl", rows({"instrument": "j", "arm": "a", "seed": 7,
                                                 "n": 5, "file": "instruments/gold/j-a-7.json"}))
        self.put("instruments/labels.jsonl", rows(
            {"instrument": "j", "arm": "a", "item": forged[0], "truth": 0, "output": 0},
            {"instrument": "j", "arm": "a", "item": forged[0], "truth": 1, "output": 0}))
        errors, warnings, _ = self.check()
        self.assertTrue(any("differs from the seeded draw" in e for e in errors), errors)
        self.assertIn("label repeated for %s; the first counts" % forged[0], warnings)

    def test_judged_rows_and_an_uncalibrated_verifier_cap(self):
        self.put("experiments/h1/protocol.md", "change: x\n")
        self.put("experiments/h1/results.jsonl", rows({"item": 1, "judge": "m", "score": 7}))
        self.run_cmd("instrument", ["add", "q", "v", "--kind", "verdict", "--rung", "R4",
                                    "--construct", "supports"])
        self.put("claims.jsonl", rows(
            {"id": "C1", "proof": ["experiments/h1/results.jsonl"]},
            {"id": "C2", "kind": "derivation", "proof": ["findings.md"], "verified_by": "v"}))
        _, _, steps = self.check()
        self.assertEqual(steps["C1"], ["instrument-unvalidated", "judged-row-incomplete"])
        self.assertEqual(steps["C2"], ["uncalibrated-verifier"])

    def test_provider_label_posts_the_spec_body_and_records_the_models_name(self):
        self.run_cmd("instrument", ["add", "q", "j", "--kind", "measure", "--rung", "R4",
                                    "--construct", "a slow item"])
        self.items("j", {"a": [1, 0, 1, 0]})
        self.run_cmd("gold", ["q", "j", "--arm", "a", "--n", "2", "--seed", "2"])
        drawn = ev.first_draws(self.base)[("j", "a")]["items"]
        for item in drawn:
            prompt = ev.PROMPT % ("j", "a slow item", item, "row %d" % int(item[1:]))
            body = json.dumps({"messages": [{"content": prompt, "role": "user"}],
                               "model": "m", "temperature": 0}, sort_keys=True,
                              separators=(",", ":")).encode()
            CAP.answers["POST %s %s" % (ev.OPENROUTER, hashlib.sha256(body).hexdigest())] = (
                200, json.dumps({"model": "m-2026", "choices": [
                    {"message": {"content": "Answer: 1"}}]}).encode())
        os.environ["OPENROUTER_API_KEY"] = "k"
        self.addCleanup(os.environ.pop, "OPENROUTER_API_KEY", None)
        code, out = self.run_cmd("label", ["q", "j", "--arm", "a", "--provider", "openrouter",
                                           "--model", "m"])
        self.assertEqual(code, 0, out)
        labels = ev._rows(self.base, ev.LABELS)
        self.assertEqual(sorted(r["item"] for r in labels), sorted(drawn))
        self.assertTrue(all(r["rater"] == {"kind": "model", "provider": "openrouter",
                                           "model": "m-2026"} and r["truth"] == 1
                            for r in labels))
        del os.environ["OPENROUTER_API_KEY"]
        code, _ = self.run_cmd("label", ["q", "j", "--arm", "a", "--provider", "openrouter",
                                         "--model", "m"])
        self.assertEqual(code, 2)

    def test_ppi_line_for_an_r3_instrument(self):
        self.run_cmd("instrument", ["add", "q", "j", "--kind", "measure", "--rung", "R3",
                                    "--construct", "slow"])
        self.items("j", {"a": [1, 0, 1, 1, 0, 1, 0, 0, 1, 1]})
        self.gold_and_label("j", "a", 5, 3, wrong=1)
        _, _, steps = self.check()
        self.assertTrue(any(r.startswith("ppi q: j arm a lambda=") for r in steps["#report"]),
                        steps["#report"])

    def test_gold_row_naming_another_arms_file_is_refused_and_draws_nothing(self):
        # D4-3: a GOLD row for j/a naming the file `gold` drew for k/b
        self.put("experiments/h2/protocol.md", "change: x\ndesign: experiment\nmde: 0.10\n")
        self.put("experiments/h2/results.jsonl", rows(*(
            {"item": "i%03d" % n, "arm": arm, "instrument": name, "outcome": n % 2}
            for name, arm in (("j", "a"), ("k", "b")) for n in range(1, 21))))
        code, out = self.run_cmd("gold", ["q", "k", "--arm", "b", "--n", "10", "--seed", "5"])
        self.assertEqual(code, 0, out)
        with open(os.path.join(self.base, ev.GOLD), "a", encoding="utf-8") as fh:
            fh.write(json.dumps({"instrument": "j", "arm": "a", "seed": 5, "n": 10,
                                 "file": "instruments/gold/k-b-5.json"}) + "\n")
        errors, _, _ = self.check()
        self.assertIn("instruments/gold/k-b-5.json differs from the seeded draw: its GOLD row "
                      "names j arm a seed 5 n 10, the file k arm b seed 5 n 10", errors)
        self.assertNotIn(("j", "a"), ev.first_draws(self.base))
        self.assertIn(("k", "b"), ev.first_draws(self.base))
        code, out = self.run_cmd("label", ["q", "j", "--arm", "a", "--human", "r", "--ack",
                                           "ok"], rows({"item": "i001", "truth": 1}))
        self.assertEqual(code, 1, out)
        self.assertIn("has no gold draw", out)

    def test_label_row_without_truth_and_output_leaves_the_item_unlabelled(self):
        # D1-7: no refusal, the arm stays unlabelled
        self.run_cmd("instrument", ["add", "q", "j", "--kind", "measure", "--rung", "R4",
                                    "--construct", "slow"])
        self.items("j", {"a": [k % 2 for k in range(80)], "b": [k % 2 for k in range(80)]})
        hand = []
        for arm in ("a", "b"):
            self.run_cmd("gold", ["q", "j", "--arm", arm, "--n", "72", "--seed", "5"])
            drawn = ev.first_draws(self.base)[("j", arm)]["items"]
            hand += [{"instrument": "j", "arm": arm, "item": i} for i in drawn[:70]]
            hand += [{"instrument": "j", "arm": arm, "item": drawn[70], "truth": 0},
                     {"instrument": "j", "arm": arm, "item": drawn[71], "truth": None,
                      "output": None}]
        self.put(ev.LABELS, rows(*hand))
        self.put("claims.jsonl", rows({"id": "C3", "proof": ["experiments/h2/results.jsonl"]}))
        errors, warnings, steps = self.check()
        self.assertEqual(errors, [])
        self.assertFalse(any("label repeated" in w for w in warnings), warnings)
        self.assertIn("instrument q: j unvalidated sum=0.0000 threshold=0.1000", steps["#report"])
        self.assertIn("instrument-unvalidated", steps["C3"])
        self.assertEqual(ev.first_labels(self.base), ({}, []))

    def test_label_output_unlike_its_results_row_is_refused(self):
        # D4-6b: a hand-written label whose output is forged equal to the truth
        self.items("j", {"a": [0] * 10})
        code, out = self.run_cmd("gold", ["q", "j", "--arm", "a", "--n", "5", "--seed", "1"])
        self.assertEqual(code, 0, out)
        drawn = ev.first_draws(self.base)[("j", "a")]["items"]
        self.put(ev.LABELS, rows(*({"instrument": "j", "arm": "a", "item": i, "truth": 1,
                                    "output": 1 if k == 0 else 0}
                                   for k, i in enumerate(drawn))))
        errors, _, _ = self.check()
        self.assertEqual([e for e in errors if "label output" in e],
                         ["label output differs from its results row: j arm a item %s output 1, "
                          "results row 0" % drawn[0]])

    def test_a_label_whose_item_was_refiled_after_it_is_stale(self):
        # plan 128 K7: a refile is the documented correction; the label copied the
        # replaced row's outcome, so it is stale - it does not count and the item reads
        # unlabelled (a cap) until it is labelled again, never `label output differs`
        self.run_cmd("instrument", ["add", "q", "j", "--kind", "measure", "--rung", "R4",
                                    "--construct", "slow"])
        self.put("experiments/h2/protocol.md", "change: x\ndesign: experiment\nmde: 0.10\n")
        filed = [{"run": "r%03d" % n, "item": "i%03d" % n, "arm": "a", "instrument": "j",
                  "outcome": n % 2} for n in range(1, 81)]
        self.put("experiments/h2/results.jsonl", rows(*filed))
        drawn = self.gold_and_label("j", "a", 72, 5)
        self.put("claims.jsonl", rows({"id": "C3", "proof": ["experiments/h2/results.jsonl"]}))
        _, _, steps = self.check()
        self.assertNotIn("instrument-unvalidated", steps.get("C3", []))
        old = next(r for r in filed if r["item"] == drawn[0])
        with open(os.path.join(self.base, "experiments/h2/results.jsonl"), "a") as fh:
            fh.write(json.dumps(dict(old, outcome=1 - old["outcome"])) + "\n")
        errors, warnings, steps = self.check()
        self.assertFalse([e for e in errors if "label output" in e], errors)
        self.assertIn("instrument-unvalidated", steps["C3"])
        self.assertNotIn(("j", "a", drawn[0]), ev.first_labels(self.base)[0])
        code, out = self.run_cmd("label", ["q", "j", "--arm", "a", "--human", "r", "--ack",
                                           "the user relabelled it"],
                                 rows({"item": drawn[0], "truth": 1 - old["outcome"]}))
        self.assertEqual(code, 0, out)
        errors, warnings, steps = self.check()
        self.assertFalse([e for e in errors if "label output" in e], errors)
        self.assertFalse([w for w in warnings if "label repeated" in w], warnings)
        self.assertNotIn("instrument-unvalidated", steps.get("C3", []))

    def test_measure_mde_above_one_leaves_the_instrument_unvalidated(self):
        # D4-7: the threshold reads a difference of proportions; mde 50 is no threshold
        self.run_cmd("instrument", ["add", "q", "j", "--kind", "measure", "--rung", "R4",
                                    "--construct", "slow"])
        self.items("j", {"a": [k % 2 for k in range(80)], "b": [k % 2 for k in range(80)]},
                   mde="50")
        self.gold_and_label("j", "a", 72, 5, wrong=72)
        self.gold_and_label("j", "b", 72, 5, wrong=72)
        self.put("claims.jsonl", rows({"id": "C3", "proof": ["experiments/h2/results.jsonl"]}))
        _, _, steps = self.check()
        self.assertIn("instrument q: j unvalidated sum=2.0000 threshold=50.0000 (mde above 1: "
                      "the threshold reads a difference of proportions)", steps["#report"])
        self.assertIn("instrument-unvalidated", steps["C3"])
        self.assertEqual(ev.conclude_problems(self.repo, "q", self.base, {}), [])


class Commands(Line):
    def test_calibration_brier_over_resolved_hypotheses(self):
        self.put("state.json", json.dumps({"rules": 8, "hypotheses": [
            {"status": "supported", "probability": 0.8}, {"status": "refuted",
                                                          "probability": 0.3},
            {"status": "refuted", "probability": 0.6}, {"status": "untested",
                                                        "probability": 0.9}]}))
        code, out = self.run_cmd("calibration", [])
        self.assertEqual(code, 0)
        self.assertIn("brier: %.4f over 3 resolved hypotheses"
                      % ((0.2 ** 2 + 0.3 ** 2 + 0.6 ** 2) / 3), out)

    def known_truth(self, defects, sound):
        root = os.path.join(self.repo, "kt")
        os.makedirs(root)
        cases = [{"kind": "instrument", "truth": "defect", "n": 10, "errors": 4, "mde": 0.1}
                 for _ in range(defects)]
        cases += [{"kind": "citation", "truth": "sound", "title": "Sound %d" % k}
                  for k in range(sound)]
        with open(os.path.join(root, "cases.jsonl"), "w") as fh:
            fh.write(rows(*cases))
        return self.run_cmd("release-check", ["--fixtures", root])

    def test_release_check_bounds(self):
        code, out = self.known_truth(36, 17)
        self.assertEqual(code, 0, out)
        self.assertIn("misses: 0/36 upper=0.0974", out)
        self.assertIn("false alarms: 0/17 upper=0.1951", out)
        shutil.rmtree(os.path.join(self.repo, "kt"))
        code, out = self.known_truth(20, 17)
        self.assertEqual(code, 1, out)
        self.assertIn("misses: 0/20 upper=0.1684", out)

    def test_default_known_truth_set_has_enough_cases_and_passes(self):
        with open(os.path.join(ev.KNOWN_TRUTH, "cases.jsonl")) as fh:
            cases = [json.loads(line) for line in fh if line.strip()]
        self.assertGreaterEqual(sum(c["truth"] == "defect" for c in cases), 36)
        self.assertGreaterEqual(sum(c["truth"] == "sound" for c in cases), 17)
        self.assertEqual({c["kind"] for c in cases}, {"citation", "quote", "instrument"})


if __name__ == "__main__":
    unittest.main()
