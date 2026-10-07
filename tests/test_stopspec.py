"""hooks/tezgah_stopspec.py: the Stop rule's evidence fold as a past-time temporal
spec, shadow-checked against the imperative `_evidence_block` (plan 063)."""
import os
import random
import shutil
import sys
import tempfile
import unittest
from collections import Counter
from unittest import mock

import support

sys.path.insert(0, os.path.join(support.REPO, "hooks"))
import tezgah_integrity as ti  # noqa: E402
import tezgah_stopspec as ss  # noqa: E402


def _operands(f, out):
    if isinstance(f, tuple):
        for a in f[1:]:
            _operands(a, out)
    else:
        out.add(f)
    return out


class PreRegistration(unittest.TestCase):
    """Fixed before any shadow row exists: the bounds the bet is read against."""

    def test_the_table_is_at_most_8_formulas_over_at_most_10_row_atoms(self):
        self.assertLessEqual(len(ss.FORMULAS), 8)
        self.assertLessEqual(len(ss.ROW_ATOMS), 10)
        self.assertEqual(ss.SCOPE_ATOMS, ("T",))
        used = set()
        for f in ss.FORMULAS.values():
            _operands(f, used)
        # Pb is P through the declared escapes E1/E2, not an eleventh atom
        self.assertEqual(used - {"Pb"}, set(ss.ROW_ATOMS) | set(ss.SCOPE_ATOMS))

    def test_the_escape_list_is_the_pre_registered_one(self):
        self.assertEqual([name for name, _ in ss.ESCAPES],
                         ["E1 began-join", "E2 repo-bind", "E3 lost-began"])
        self.assertEqual([name for name, _ in ss.NOT_COUNTED],
                         ["session fallbacks", "reply atoms", "evidence tampered"])
        self.assertEqual(ss.MIN_LIVE_N, 400)

    def test_go4_at_most_3_escape_predicates(self):
        self.assertLessEqual(len(ss.ESCAPES), 3)

    def test_the_decision_list_covers_every_evidence_class_once(self):
        classes = [cls for cls, _ in ss.ORDER if cls != "allow"]
        self.assertEqual(classes, ["check failed", "partial failure", "no ui_ok",
                                   "stale evidence", "no verify_ok",
                                   "no external read"])


class Differential(unittest.TestCase):
    """Seeded random traces: the spec's class equals `_evidence_block`'s on every
    one, for each work flag and with and without an external claim."""

    TRACES = int(os.environ.get("TEZGAH_STOPSPEC_TRACES", "3000"))

    def setUp(self):
        self.dir = os.path.realpath(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.dir, True)
        self.repo_a = os.path.join(self.dir, "a")
        self.repo_b = os.path.join(self.dir, "b")
        for repo in (self.repo_a, self.repo_b):
            os.makedirs(os.path.join(repo, ".git"))

    def palette(self):
        a, b = self.repo_a, self.repo_b
        ok = {"exit": 0, "out_bytes": 9}
        return [
            {"kind": "edit", "detail": "app.py", "changed": True,
             "target": os.path.join(a, "app.py")},
            {"kind": "edit", "detail": "app.py", "changed": True},
            {"kind": "edit", "detail": "app.py", "changed": False},
            {"kind": "edit", "detail": "src/App.tsx", "changed": True},
            {"kind": "edit", "detail": "src/components/Button.tsx", "changed": True,
             "target": os.path.join(a, "src/components/Button.tsx")},
            {"kind": "run", "detail": "printf x > src/App.tsx", "changed": True},
            {"kind": "run", "detail": "ruff format ."},
            {"kind": "run", "detail": "git status"},
            {"kind": "run", "detail": "npm view tezgah version"},
            {"kind": "run", "detail": "screencapture -x shot.png"},
            {"kind": "began", "id": "c1", "check": 1},
            {"kind": "began", "id": "c2", "check": 1},
            dict(ok, kind="verify_ok", id="c1", detail="pytest -q"),
            dict(ok, kind="verify_ok", id="c2", detail="pytest -q", repo=a),
            dict(ok, kind="verify_ok", id="c1", detail="pytest -q", repo=b),
            dict(ok, kind="verify_ok", detail="pytest -q | tail"),
            dict(ok, kind="verify_ok", id="c2", detail="npx playwright test"),
            dict(ok, kind="verify_ok",
                 detail="tezgah-design check --contract c.md --measured m.json"),
            {"kind": "verify_fail", "detail": "pytest", "exit": 1},
            {"kind": "verify", "detail": "pytest"},
            {"kind": "interrupted", "detail": "pytest"},
            {"kind": "unknown", "detail": ti.TOOL_NAME + "browser_snapshot"},
            {"kind": "external", "detail": "mcp mobile_take_screenshot",
             "exit": 1},
            {"kind": ti.TURN_KIND, "detail": "x"},
        ]

    def test_the_spec_agrees_with_the_imperative_fold(self):
        rng = random.Random(63)
        palette = self.palette()
        seen, bad = Counter(), []
        for n in range(self.TRACES):
            rows = [dict(rng.choice(palette)) for _ in range(rng.randint(0, 12))]
            # the two shapes the selector passes: the rows' own work kinds, or
            # those forced on (the lost-began and settled paths)
            kinds = {str(r.get("kind")) for r in rows} & ti.WORK_KINDS
            for worked in (kinds, kinds | {ti.BEGAN_KIND}):
                for external in (None, "npm 1.2.0 is published"):
                    want = ti._evidence_block(rows, worked, external)[0]
                    got = ss.fold(rows, worked, external)[0]
                    seen[want] += 1
                    if want != got:
                        bad.append((n, worked, external, want, got, rows))
        self.assertEqual(bad[:3], [])
        # not vacuous: every class and the allow are drawn
        for cls in (None, "check failed", "partial failure", "no ui_ok",
                    "stale evidence", "no verify_ok", "no external read"):
            self.assertGreater(seen[cls], 20, (cls, seen))

    def test_a_row_that_is_both_a_ui_write_and_a_screen_proof_is_refused(self):
        row = {"kind": "run", "detail": "screencapture -x src/App.tsx > src/App.tsx",
               "changed": True}
        self.assertEqual(ti._evidence_block([row], {"run"}, None)[0], "no ui_ok")
        self.assertEqual(ss.fold([row], {"run"}, None)[0], "no ui_ok")


class Shadow(unittest.TestCase):
    """The shadow records, never decides; a raising shadow keeps the refusal."""

    CLAIM = "Tamamlandı, tüm testler geçti."

    def setUp(self):
        self.dir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.dir, True)
        self.addCleanup(setattr, ti, "_path", ti._path)
        ledger = os.path.join(self.dir, "evidence", "s.jsonl")
        ti._path = lambda session: ledger
        os.environ.pop(ss.STRICT, None)
        ti.note_turn("s", "do it")
        ti.note("s", "edit", "app.py", changed=True)

    def rows(self):
        return [r for r in ti.events("s") if r.get("kind") == ss.ROW_KIND]

    def test_agreement_is_recorded_beside_the_verdict(self):
        reason = ti.stop_reason(self.CLAIM, "s")
        self.assertIn("no check ran", reason)
        rows = self.rows()
        self.assertEqual([r["detail"] for r in rows], ["agree fold: no verify_ok"])
        self.assertEqual(rows[0]["v"], ti.ROW_VERSION)
        self.assertTrue(rows[0]["id"])

    def test_a_raising_spec_keeps_the_live_refusal(self):
        want = ti._stop_block(self.CLAIM, "s", rows=ti.turn_rows("s"))[1]
        with mock.patch.object(ss, "fold", side_effect=RuntimeError("boom")):
            self.assertEqual(ti.stop_reason(self.CLAIM, "s"), want)
        self.assertEqual([r["detail"] for r in self.rows()],
                         ["error: RuntimeError"])

    def test_a_stop_that_writes_no_claim_or_refusal_runs_no_shadow(self):
        # the 99% bar is read on claim and refusal rows; a quiet allowed reply
        # and a reply after a block pay nothing for the shadow
        ti.note("s", "verify_ok", "pytest -q", exit=0, out_bytes=9)
        with mock.patch.object(ss, "check") as asked:
            self.assertIsNone(ti.stop_reason("Here is the summary.", "s"))
            self.assertIsNone(ti.stop_reason(self.CLAIM, "s", record_only=True))
            self.assertIsNone(ti.stop_reason(self.CLAIM, "s", subagent=True))
        asked.assert_not_called()
        self.assertEqual(self.rows(), [])

    def test_a_verdict_the_selector_made_says_the_fold_was_not_reached(self):
        # a shape refusal is decided before any fold: agreement there is by
        # construction, so the row says so and GO 2 leaves it out
        text = "Done:\n" + "\n".join("- item %d" % k for k in range(12))
        cls = ti._stop_block(text, "s", rows=ti.turn_rows("s"))[0]
        self.assertIn(cls, ti.SHAPE_BLOCKS)
        ti.stop_reason(text, "s")
        self.assertEqual([r["detail"] for r in self.rows()],
                         ["agree selector: %s" % cls])

    def test_a_shadow_that_fails_outside_its_guard_keeps_the_refusal(self):
        want = ti._stop_block(self.CLAIM, "s", rows=ti.turn_rows("s"))[1]
        with mock.patch.object(ss, "shadow", side_effect=RuntimeError("boom")):
            self.assertEqual(ti.stop_reason(self.CLAIM, "s"), want)

    def test_a_disagreeing_spec_never_changes_the_verdict(self):
        for spec in (None, "check failed"):
            with self.subTest(spec=spec):
                want = ti._stop_block(self.CLAIM, "s", rows=ti.turn_rows("s"))[1]
                with mock.patch.object(ss, "fold", return_value=(spec, spec)):
                    self.assertEqual(ti.stop_reason(self.CLAIM + " " + str(spec), "s"),
                                     want)
        self.assertEqual([r["detail"] for r in self.rows()],
                         ["disagree fold: no verify_ok -> ok",
                          "disagree fold: no verify_ok -> check failed"])

    def test_an_allowed_turn_stays_allowed_under_a_refusing_spec(self):
        ti.note("s", "verify_ok", "pytest -q", exit=0, out_bytes=9)
        with mock.patch.object(ss, "fold", return_value=("no verify_ok", "x")):
            self.assertIsNone(ti.stop_reason(self.CLAIM, "s"))
        self.assertEqual([r["detail"] for r in self.rows()],
                         ["disagree fold: ok -> no verify_ok"])

    def test_one_row_per_reply_per_turn(self):
        ti.stop_reason(self.CLAIM, "s")
        ti.stop_reason(self.CLAIM, "s")
        self.assertEqual(len(self.rows()), 1)

    def test_strict_makes_a_disagreement_fatal(self):
        with mock.patch.dict(os.environ, {ss.STRICT: "1"}), \
                mock.patch.object(ss, "fold", return_value=(None, None)):
            with self.assertRaises(AssertionError):
                ti.stop_reason(self.CLAIM, "s")
            with self.assertRaises(AssertionError):
                ti._stop_block(self.CLAIM, "s", rows=ti.turn_rows("s"))


if __name__ == "__main__":
    unittest.main()
