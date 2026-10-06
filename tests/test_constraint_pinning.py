"""hooks/tezgah_context.py: user constraints pinned across compaction (plan 056 h).

A constraint the user issues in a prompt ("don't touch hooks.json") rides the
session's turn stamp as its matched clause, never the prompt; the post-compact
and session-start blocks restate it, and the compaction record counts its
object among the constraint needles. tests/constraint-fixtures.md is the real
prompt set the recogniser was measured on, with its false positives listed.
"""
import json
import os
import re
import subprocess
import sys
import unittest

import support
from support import TempHome

sys.path.insert(0, support.HOOKS)
import tezgah_context as tc  # noqa: E402

FIXTURE = os.path.join(support.TESTS, "constraint-fixtures.md")
ROW = re.compile(r"^- (constraint|none|missed|false-positive) "
                 r"\((real|hand|pasted)\): (.+?)(?: => (.+) \| (.+))?$")


def fixture_rows():
    with open(FIXTURE, encoding="utf-8") as fh:
        return [m.groups() for m in map(ROW.match, fh.read().splitlines()) if m]


class Recogniser(unittest.TestCase):
    def test_every_fixture_row_gets_its_label_its_pin_and_its_needle(self):
        rows = fixture_rows()
        self.assertGreaterEqual(len(rows), 25)
        for label, _source, text, pin, needle in rows:
            got = tc.user_constraints(text)
            if label in ("constraint", "false-positive"):
                # the whole sentence the shape sits in, not the matched span:
                # "Do not remove necessary" was a pin that named nothing
                self.assertEqual(got, [pin], text)
                self.assertEqual(tc.constraint_needle(got[0]), needle, text)
            else:
                self.assertEqual(got, [], "%s: %s" % (label, text))

    def test_the_false_positives_are_the_listed_ones(self):
        # every non-constraint the recogniser pins is named in the fixture, so a
        # pattern change cannot add one silently
        flagged = [text for label, _s, text, _p, _n in fixture_rows()
                   if label in ("none", "missed") and tc.user_constraints(text)]
        self.assertEqual(flagged, [])

    def test_pasted_material_is_not_the_users_constraint(self):
        # a pasted log's sentences are false positives one by one; the length
        # bound keeps them out of a real prompt: one 387,905-char agent log
        # held six of them, which filled the stamp
        pasted = [text for _l, source, text, _p, _n in fixture_rows()
                  if source == "pasted"]
        self.assertGreaterEqual(len(pasted), 3)
        log = "\n".join(pasted) + "\n" + "x" * tc.CONSTRAINT_PROMPT_MAX
        self.assertEqual(tc.user_constraints(log), [])
        # a quoted, inline-code or fenced constraint is quoted material too
        for quoted in ('he wrote "do not modify tracked files" there',
                       "the brief says `don't touch hooks.json`",
                       "```\nBaşka repoya ve ~/.config'e dokunma.\n```",
                       "> never push to main\nship it"):
            self.assertEqual(tc.user_constraints(quoted), [], quoted)


class PinnedAcrossCompaction(TempHome):
    def call(self, event, payload, read_ledger=False):
        proc = subprocess.run(
            [sys.executable, "-c", "import json, sys\nsys.path.insert(0, %r)\n"
             "import tezgah_context as tc\nout = tc.context_for(%r, %r, %r)\n"
             "rows = []\nif %r:\n    with open(tc._ledger_path(%r)) as fh:\n"
             "        rows = [json.loads(l) for l in fh if l.strip()]\n"
             "print(json.dumps([out, rows]))\n"
             % (support.HOOKS, event, self.repo, payload, read_ledger,
                payload.get("session_id"))],
            capture_output=True, text=True, env=self.env())
        self.assertEqual(proc.returncode, 0, proc.stderr)
        return json.loads(proc.stdout)

    def setUp(self):
        super().setUp()
        self.repo = self.make_repo()

    def stamp(self, session):
        with open(os.path.join(self.home, ".cache", "tezgah", "turns",
                               session + ".json")) as fh:
            return json.load(fh)

    def test_a_constraint_is_a_needle_and_the_compaction_counts_it(self):
        prompt = "fix the parser, and don't touch hooks/hooks.json while at it"
        self.call("user_prompt", {"session_id": "k1", "prompt": prompt})
        # the stamp keeps the clause to its sentence's end, never the prompt
        # around it
        self.assertEqual(self.stamp("k1")["constraints"],
                         ["don't touch hooks/hooks.json while at it"])
        self.assertNotIn("fix the parser", json.dumps(self.stamp("k1")))
        out, rows = self.call("post_compact", {
            "session_id": "k1", "trigger": "auto",
            "compact_summary": "Fixing the parser; user said hooks/hooks.json is "
                               "off limits."}, read_ledger=True)
        row = [r for r in rows if r.get("kind") == "compact"][-1]
        # the pointer needle is absent from this summary, the user's is present
        self.assertEqual((row["constraint_found"], row["constraint_expected"]), (1, 2))
        self.assertIn("- don't touch hooks/hooks.json", out)
        # a resume restates it too; a session that issued none carries no block
        out, _ = self.call("session_start", {"session_id": "k1", "source": "resume"})
        self.assertIn("User constraints issued earlier this session", out)
        out, _ = self.call("session_start", {"session_id": "k2", "source": "resume"})
        self.assertNotIn("User constraints issued earlier this session", out)

    def test_the_stamp_keeps_at_most_five(self):
        for n in range(7):
            self.call("user_prompt", {"session_id": "k3",
                                      "prompt": "don't touch file%d.py" % n})
        self.assertEqual(self.stamp("k3")["constraints"],
                         ["don't touch file%d.py" % n for n in range(2, 7)])


if __name__ == "__main__":
    unittest.main()
