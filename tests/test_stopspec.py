"""hooks/tezgah_stopspec.py: the Stop rule's evidence fold as a past-time temporal
spec (plan 063), the fold `_stop_block` calls since plan 101."""
import os
import sys
import unittest
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
    """Fixed before any shadow row existed: the bounds the bet was read against."""

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

    def test_go4_at_most_3_escape_predicates(self):
        self.assertLessEqual(len(ss.ESCAPES), 3)

    def test_the_decision_list_covers_every_evidence_class_once(self):
        classes = [cls for cls, _ in ss.ORDER if cls != "allow"]
        self.assertEqual(classes, ["check failed", "partial failure", "no ui_ok",
                                   "stale evidence", "no verify_ok",
                                   "no external read"])


class Fold(unittest.TestCase):
    """The spec is the fold: it picks the class and `_evidence_text` words it."""

    CLAIM = "Tamamlandı, tüm testler geçti."

    def test_a_row_that_is_both_a_ui_write_and_a_screen_proof_is_refused(self):
        row = {"kind": "run", "detail": "screencapture -x src/App.tsx > src/App.tsx",
               "changed": True}
        self.assertEqual(ss.fold([row], {"run"}, None)[0], "no ui_ok")

    def test_every_class_the_spec_can_pick_has_its_refusal_text(self):
        # a class with no words would hand `stop_reason` an empty reason, an allow
        for cls, _ in ss.ORDER:
            if cls != "allow":
                with self.subTest(cls=cls):
                    got = ti._evidence_text(cls, [], "npm 1.2.0 is published")
                    self.assertEqual(got[0], cls)
                    self.assertTrue(got[1])
        self.assertEqual(ti._evidence_text(None, [], None), (None, None))

    def test_the_selector_decides_through_the_spec(self):
        rows = [{"kind": "edit", "detail": "app.py", "changed": True},
                {"kind": "verify_ok", "detail": "pytest -q", "exit": 0, "out_bytes": 9}]
        self.assertEqual(ti._stop_block(self.CLAIM, None, rows=rows), (None, None))
        with mock.patch.object(ss, "verdict", return_value="check failed"):
            cls, reason = ti._stop_block(self.CLAIM, None, rows=rows)
        self.assertEqual(cls, "check failed")
        self.assertIn("A check failed in this turn", reason)
        self.assertNotIn("{UNVERIFIED}", reason)


if __name__ == "__main__":
    unittest.main()
