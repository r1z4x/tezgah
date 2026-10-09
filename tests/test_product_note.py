"""The session note's `product_due` part: every product-ledger decision past its
re-measure date with no R row, named on session_start and post_compact.

The ledger is written as fixture rows straight to the file, never through the
writer, so these cases pin the note and not the record path.
"""
import json
import os
import sys
import unittest

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO, "hooks"))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import test_research as trt  # noqa: E402

PAST = "2020-01-01"
NOTE = "is due for re-measure since"


def decision(n, topic="checkout", observe_after=PAST):
    return {"id": "D%d" % n, "type": "D", "topic": topic, "date": "2019-12-01",
            "from": ["M1"], "statement": "keep the one-page checkout",
            "outcome": "keep", "metric": "M1", "threshold": "conversion >= 3%",
            "observe_after": observe_after, "reopen": "conversion < 2%"}


BASE = [
    {"id": "O1", "type": "O", "topic": "checkout", "date": "2019-12-01",
     "from": [], "class": "user-verbatim", "source": "interview 3",
     "quote": "I gave up at the address form"},
    {"id": "I1", "type": "I", "topic": "checkout", "date": "2019-12-01",
     "from": ["O1"], "statement": "the address form loses buyers",
     "confidence": "medium", "downgrade": "indirectness"},
    {"id": "M1", "type": "M", "topic": "checkout", "date": "2019-12-01",
     "from": ["I1"], "goal": "buyers finish", "signal": "checkout completed",
     "definition": "completed / started", "window": "7 days",
     "baseline": "2.1%", "direction": "up", "leading": False, "logged": "yes",
     "data": "events table"},
]


class ProductNote(trt.Workspace):
    session_text = trt.ContextDrop.session_text
    dropped_keys = trt.ContextDrop.dropped_keys

    def ledger(self, repo, *rows):
        path = os.path.join(repo, ".tezgah", "product", "ledger.jsonl")
        self.write(path, "".join(json.dumps(r) + "\n" for r in BASE + list(rows)))
        return path

    def test_a_due_decision_is_named_and_its_r_clears_it(self):
        repo = self.repo()
        path = self.ledger(repo, decision(1))
        note = self.session_note(repo)
        self.assertIn("Product: D1 (checkout) %s %s" % (NOTE, PAST), note)
        self.assertIn("tezgah-research record R`.", note)
        self.append_line(path, {"id": "R1", "type": "R", "topic": "checkout",
                                "date": "2020-02-01", "from": ["D1"],
                                "decision": "D1", "verdict": "met",
                                "value": "3.4%", "class": "behaviour",
                                "source": "events table"})
        self.assertNotIn(NOTE, self.session_note(repo))

    def test_no_ledger_and_nothing_due_cost_zero_bytes(self):
        # the whole note is not compared: other parts (the generated-subagents
        # line) change between two session starts of one repo on their own
        repo = self.repo()
        self.assertNotIn("Product:", self.session_note(repo))
        self.ledger(repo, decision(1, observe_after="2999-01-01"))
        note = self.session_note(repo)
        self.assertNotIn("Product:", note)
        self.assertNotIn("re-measure", note)

    def test_at_most_three_are_named_and_the_rest_counted(self):
        repo = self.repo()
        self.ledger(repo, *[decision(n) for n in range(1, 5)])
        note = self.session_note(repo)
        self.assertEqual(note.count(NOTE), 3, note)
        self.assertIn("and 1 more due (`", note)
        self.assertIn("tezgah-research due`)", note)

    def test_research_off_silences_it(self):
        repo = self.repo()
        self.ledger(repo, decision(1))
        self.assertIn(NOTE, self.session_note(repo))
        self.touch(os.path.join(self.home, ".config", "tezgah", "research-off"))
        self.assertNotIn(NOTE, self.session_note(repo))

    def test_post_compact_carries_it_too(self):
        repo = self.repo()
        self.ledger(repo, decision(1))
        for event in ("session_start", "post_compact"):
            with self.subTest(event=event):
                self.assertIn("Product: D1 (checkout)", self.session_note(repo, event))

    def test_drop_order_holds_it_right_after_research_broken(self):
        import tezgah_context as tc
        at = tc.DROP_ORDER.index("research_broken")
        self.assertEqual(tc.DROP_ORDER[at + 1], "product_due")

    def test_a_budget_squeeze_drops_it(self):
        import tezgah_context as tc
        repo = self.repo()
        self.ledger(repo, decision(1))
        self.session_text(repo)  # settle the one-time tier-agent note
        self.assertIn(NOTE, self.session_text(repo))
        squeezed = self.session_text(repo, limit=600)
        keys = self.dropped_keys(squeezed)
        self.assertIn("product_due", keys, squeezed)
        self.assertEqual(keys, [k for k in tc.DROP_ORDER if k in keys], keys)
        self.assertNotIn(NOTE, squeezed)


if __name__ == "__main__":
    unittest.main()
