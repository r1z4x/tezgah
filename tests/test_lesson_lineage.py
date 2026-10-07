"""Taint lineage for the lesson ledger (plan 061 Phase A, ADR 010).

A `.tezgah/lessons.md` write in a user turn that already holds a row carrying
`source` - a result that arrived from outside the user and this workspace, or an
effect made after one - leaves a `lesson_tainted` row per new line and is never
refused. The fold is over every row of the turn (`turn_rows`), not over
`turn_channel`, which the first effect after the read spends.
"""
import json
import os
import sys
import unittest

import support
from support import TempHome, run_json

sys.path.insert(0, support.HOOKS)
import tezgah_integrity as ti  # noqa: E402
import tezgah_lessons  # noqa: E402

KEY = tezgah_lessons.lesson_key


class Lineage(TempHome):
    def setUp(self):
        super().setUp()
        self.repo = self.make_repo("proj")
        self.ledger = tezgah_lessons.ledger(self.repo)
        os.makedirs(os.path.dirname(self.ledger))
        with open(self.ledger, "w", encoding="utf-8") as fh:
            fh.write("old rule - it happened once\n")
        self.envv = self.env()
        self.session = "s-lineage"

    def turn(self):
        out, proc = run_json([support.PROBE_INTEGRITY],
                             {"fn": "note_turn", "session": self.session,
                              "prompt": "go"}, env=self.envv)
        self.assertEqual(proc.returncode, 0, proc.stderr)

    def post(self, tool, inp, agent=None):
        payload = {"hook_event_name": "PostToolUse", "cwd": self.repo,
                   "session_id": self.session, "tool_name": tool,
                   "tool_input": inp}
        if agent:
            payload["agent_id"] = agent
        _out, proc = run_json([support.POSTTOOLUSE], payload, env=self.envv)
        self.assertEqual(proc.returncode, 0, proc.stderr)

    def gate(self, tool, inp, agent=None, record=True):
        """The gate's answer for this call, run the way a host runs it."""
        code = ("import json, sys\nsys.path.insert(0, %r)\n"
                "from tezgah_gate import decision\n"
                "print(json.dumps(decision(%r, %r, %r, %r, record=%r, agent=%r)))"
                % (support.HOOKS, tool, inp, self.repo, self.session, record, agent))
        out, proc = run_json(["-c", code], None, env=self.envv)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        return out

    def rows(self, kind):
        out, _ = run_json([support.PROBE_INTEGRITY],
                          {"fn": "events", "session": self.session}, env=self.envv)
        return [r for r in out or [] if r.get("kind") == kind]

    def write_lesson(self, line="new rule - a page said so", agent=None):
        return self.gate("Write", {"file_path": self.ledger,
                                   "content": "old rule - it happened once\n"
                                              + line + "\n"}, agent=agent)

    def test_a_write_after_a_web_read_leaves_one_row_and_no_deny(self):
        self.turn()
        self.post("WebFetch", {"url": "https://example.com"})
        self.assertIsNone(self.write_lesson())
        rows = self.rows("lesson_tainted")
        self.assertEqual(len(rows), 1, rows)
        self.assertEqual(rows[0]["key"], KEY("new rule - a page said so"))
        self.assertEqual(rows[0]["source"], "web")
        self.assertEqual(rows[0]["target"], self.ledger)
        self.assertEqual(self.rows("deny"), [])

    def test_a_turn_with_no_source_leaves_no_row(self):
        self.turn()
        self.post("Bash", {"command": "ls"})
        self.assertIsNone(self.write_lesson())
        self.assertEqual(self.rows("lesson_tainted"), [])

    def test_a_source_in_an_earlier_turn_does_not_taint(self):
        self.turn()
        self.post("WebFetch", {"url": "https://example.com"})
        self.turn()
        self.assertIsNone(self.write_lesson())
        self.assertEqual(self.rows("lesson_tainted"), [])

    def test_a_channel_an_effect_already_spent_still_taints(self):
        # turn_channel answers None after the first effect carries the channel;
        # the fold over the turn's rows still sees the read
        self.turn()
        self.post("WebFetch", {"url": "https://example.com"})
        self.post("Write", {"file_path": os.path.join(self.repo, "notes.txt"),
                            "content": "x\n"})
        self.assertIsNone(self.write_lesson())
        self.assertEqual([r["source"] for r in self.rows("lesson_tainted")], ["web"])

    def test_every_write_shape_names_its_new_lines(self):
        self.turn()
        self.post("WebFetch", {"url": "https://example.com"})
        self.assertIsNone(self.gate("Edit", {
            "file_path": ".tezgah/lessons.md",
            "old_string": "old rule - it happened once",
            "new_string": "old rule - it happened once\n- edited rule - twice"}))
        self.assertIsNone(self.gate("Bash", {
            "command": "cat >> .tezgah/lessons.md <<'EOF'\nheredoc rule - z\nEOF"}))
        # a body the gate cannot read still leaves the row, with no key
        self.assertIsNone(self.gate("Bash", {
            "command": "echo 'echo rule - y' >> .tezgah/lessons.md"}))
        self.assertEqual([r.get("key") for r in self.rows("lesson_tainted")],
                         [KEY("edited rule - twice"), KEY("heredoc rule - z"), None])

    def test_another_file_is_not_the_ledger(self):
        self.turn()
        self.post("WebFetch", {"url": "https://example.com"})
        for path in ("lessons.md", "docs/lessons.md", ".tezgah/notes.md"):
            self.assertIsNone(self.gate("Write", {
                "file_path": os.path.join(self.repo, path), "content": "a - b\n"}))
        self.assertEqual(self.rows("lesson_tainted"), [])

    def test_a_sibling_subagent_read_does_not_taint(self):
        self.turn()
        self.post("WebFetch", {"url": "https://example.com"}, agent="a1")
        self.assertIsNone(self.write_lesson(agent="a2"))
        self.assertEqual(self.rows("lesson_tainted"), [])
        self.assertIsNone(self.write_lesson(agent="a1"))
        self.assertEqual(len(self.rows("lesson_tainted")), 1)

    def test_the_dry_run_writes_no_row(self):
        self.turn()
        self.post("WebFetch", {"url": "https://example.com"})
        self.assertIsNone(self.gate("Write", {
            "file_path": self.ledger, "content": "new rule - x\n"}, record=False))
        self.assertEqual(self.rows("lesson_tainted"), [])
        code = ("import json, os, sys\nsys.path.insert(0, %r)\nimport tezgah_lessons\n"
                "print(json.dumps(os.path.exists(tezgah_lessons.taint_path(%r))))"
                % (support.HOOKS, self.repo))
        self.assertIs(run_json(["-c", code], None,
                               env=self.envv)[0], False)

    def test_the_row_fields_survive_note(self):
        self.assertTrue({"key", "source", "target", "agent", "workspace"}
                        <= ti.LEDGER_FIELDS)


if __name__ == "__main__":
    unittest.main()
