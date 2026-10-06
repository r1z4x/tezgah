"""hooks/tezgah_context.py: the per-turn context diet (plan 056).

An armed conditional paragraph is paid in full once per session and its later
matches pay one line; a compaction - PostCompact or SessionStart(source=compact)
- makes the next match pay the full paragraph again, and so does a match
ARMED_RESURFACE turns after the paragraph was last shown, for the hosts that
send no compaction signal. The per-turn skill hint is given up by the budget
before the task phase, the delta and the pointer.
"""
import json
import subprocess
import sys

import support
from support import TempHome

sys.path.insert(0, support.HOOKS)
import tezgah_context as tc  # noqa: E402

SPEC = "**Spec before building.**"
RESEARCH = "**Research: route it to OpenResearch.**"


class ArmedOncePerSession(TempHome):
    def call(self, event, payload, patch=""):
        """context_for in a child, with `patch` run against the module first:
        a module constant cannot be patched in this process."""
        proc = subprocess.run(
            [sys.executable, "-c", "import json, sys\nsys.path.insert(0, %r)\n"
             "import tezgah_context as tc\n%s\nprint(json.dumps(tc.context_for("
             "%r, %r, %r)))\n" % (support.HOOKS, patch, event, self.repo, payload)],
            capture_output=True, text=True, env=self.env())
        self.assertEqual(proc.returncode, 0, proc.stderr)
        return json.loads(proc.stdout)

    def prompt(self, text, session="s1", patch=""):
        return self.call("user_prompt", {"session_id": session, "prompt": text},
                         patch)

    def setUp(self):
        super().setUp()
        self.repo = self.make_repo()

    def test_a_second_match_pays_one_line_not_the_paragraph(self):
        first = self.prompt("make it look better")
        self.assertIn(SPEC, first)
        again = self.prompt("make the footer look better")
        self.assertNotIn("Write a\nshort checkable spec", again)
        self.assertIn(SPEC + " Armed again", again)
        self.assertIn("`tezgah-contract` skill", again)
        # the full paragraph is several times the line that replaces it
        self.assertLess(len(again), len(first))
        # another session has seen nothing
        self.assertNotIn(SPEC + " Armed again", self.prompt("make it look better", "s2"))

    def test_a_compaction_restores_the_full_paragraph(self):
        for session, event, payload in (
                ("c1", "post_compact", {"session_id": "c1", "trigger": "auto"}),
                ("c2", "session_start", {"session_id": "c2", "source": "compact"})):
            self.prompt("make it look better", session)
            self.assertIn("Armed again", self.prompt("make it look better", session))
            self.call(event, payload)
            out = self.prompt("make it look better", session)
            self.assertIn(SPEC, out)
            self.assertNotIn("Armed again", out, event)
        # a plain resume keeps what was seen
        self.call("session_start", {"session_id": "c2", "source": "resume"})
        self.assertIn("Armed again", self.prompt("make it look better", "c2"))

    def test_the_research_line_keeps_the_open_lines_fact(self):
        patch = "tc.open_lines_note = lambda root: ' OPEN-LINES-FACT.'"
        self.assertIn(RESEARCH, self.prompt("literatür taraması", patch=patch))
        again = self.prompt("literatür taraması yap", patch=patch)
        self.assertIn(RESEARCH + " Armed again", again)
        self.assertIn("OPEN-LINES-FACT", again)

    def test_the_full_paragraph_resurfaces_after_the_pinned_turn_count(self):
        # Cursor and dsh send no compaction signal, so a paragraph shown early
        # in a long session comes back in full on the first match this many
        # turns after it was last shown
        self.assertEqual(tc.ARMED_RESURFACE, 20)
        self.assertIn(SPEC, self.prompt("make it look better"))      # turn 1
        for _ in range(18):                                          # 2..19
            self.prompt("add a docstring to parse_quantity")
        self.assertIn("Armed again", self.prompt("make it look better"))  # 20
        out = self.prompt("make it look better")                     # 21
        self.assertIn(SPEC, out)
        self.assertNotIn("Armed again", out)


class SkillHintBudget(TempHome):
    def test_the_skill_hint_goes_before_the_task_the_delta_and_the_pointer(self):
        order = tc.DROP_ORDER
        self.assertIn("skill", order)
        for later in ("task", "delta", "pointer"):
            self.assertLess(order.index("skill"), order.index(later), later)
        # an over-budget turn gives the skill hint up and keeps the rest
        proc = subprocess.run(
            [sys.executable, "-c", "import json, sys\nsys.path.insert(0, %r)\n"
             "import tezgah_context as tc\ntc.CONTEXT_BUDGET['user_prompt'] = 420\n"
             "print(json.dumps(tc.budgeted('user_prompt', [('reminder', 'r' * 100),"
             " ('skill', 's' * 100), ('task', 't' * 100), ('delta', 'd' * 100),"
             " ('pointer', 'p' * 100)])))" % support.HOOKS],
            capture_output=True, text=True, env=self.env())
        self.assertEqual(proc.returncode, 0, proc.stderr)
        out = json.loads(proc.stdout)
        self.assertNotIn("s" * 100, out)
        for kept in ("r", "t", "d", "p"):
            self.assertIn(kept * 100, out)
        self.assertIn("dropped skill (100 B)", out)


if __name__ == "__main__":
    import unittest
    unittest.main()
