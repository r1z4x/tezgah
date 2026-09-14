"""hooks/tezgah_gate.py: attribution gate, explore gate, first-grep nudge."""
import os
import unittest

import support
from support import TempHome, run_json


class Gate(TempHome):
    def setUp(self):
        super().setUp()
        self.repo = self.make_repo("proj")
        self.envv = self.env()
        self.probe = support.PROBE_GATE

    def decide(self, tool, inp, cwd=None, session_id="s1"):
        payload = {"tool": tool, "input": inp, "cwd": cwd or self.repo,
                   "session_id": session_id}
        out, proc = run_json([self.probe], payload, env=self.envv)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        return out

    def make_index(self):
        db_dir = os.path.join(self.home, ".cache", "codebase-memory-mcp")
        os.makedirs(db_dir, exist_ok=True)
        with open(os.path.join(db_dir, support.slug(self.repo) + ".db"), "w"):
            pass

    # ---- attribution -------------------------------------------------------
    def test_attribute_less_commit_passes(self):
        self.assertIsNone(self.decide("Bash", {"command": 'git commit -m "fix: typo"'}))

    def test_attribution_forms_deny_a_commit(self):
        for credit in ("Co-Authored-By: Claude <noreply@anthropic.com>",
                       "Generated with Claude Code",
                       "\U0001F916"):
            command = 'git commit -m "change\n\n%s"' % credit
            reason = self.decide("Bash", {"command": command})
            self.assertIsNotNone(reason, credit)
            self.assertIn("Attribution", reason)

    def test_attribution_denies_gh_pr_create(self):
        reason = self.decide("Bash", {
            "command": 'gh pr create --title "x" --body "Generated with Cursor"'})
        self.assertIsNotNone(reason)
        self.assertIn("Attribution", reason)

    def test_attribution_without_a_write_passes(self):
        self.assertIsNone(self.decide("Bash", {"command": 'echo "Generated with x"'}))

    def test_attribution_outside_roots_passes(self):
        self.assertIsNone(self.decide(
            "Bash", {"command": 'git commit -m "Co-Authored-By: x"'},
            cwd=self.home))

    # ---- explore subagent --------------------------------------------------
    def test_explore_subagent_denies(self):
        for tool, sub in (("Agent", "Explore"), ("Task", "explorer")):
            reason = self.decide(tool, {"subagent_type": sub})
            self.assertIsNotNone(reason, sub)
            self.assertIn("grep-only explorer", reason)

    def test_general_purpose_subagent_passes(self):
        self.assertIsNone(self.decide("Agent", {"subagent_type": "general-purpose"}))

    # ---- kill switch -------------------------------------------------------
    def test_pretooluse_off_kills_denials(self):
        self.touch(os.path.join(self.home, ".config", "tezgah", "pretooluse-off"))
        self.assertIsNone(self.decide("Agent", {"subagent_type": "Explore"}))

    # ---- first identifier grep nudge --------------------------------------
    def test_identifier_grep_nudged_once_then_passes(self):
        self.assertIsNone(self.decide("Grep", {"pattern": "some_identifier"}))
        self.make_index()
        first = self.decide("Grep", {"pattern": "some_identifier"})
        self.assertIsNotNone(first)
        self.assertIn("search_graph", first)
        self.assertIsNone(self.decide("Grep", {"pattern": "some_identifier"}))

    def test_bash_grep_identifier_uses_the_same_nudge(self):
        self.assertIsNone(
            self.decide("Bash", {"command": "grep some_identifier src/x.py"}))
        self.make_index()
        first = self.decide("Bash", {"command": "grep some_identifier src/x.py"},
                            session_id="b1")
        self.assertIsNotNone(first)
        self.assertIsNone(self.decide("Bash", {"command": "grep some_identifier src/x.py"},
                                      session_id="b1"))

    def test_non_identifier_search_never_nudged(self):
        self.make_index()
        self.assertIsNone(self.decide("Grep", {"pattern": "two words"}))
        self.assertIsNone(self.decide("Grep", {"pattern": "x"}))

    def test_index_for_a_different_repo_does_not_nudge(self):
        db_dir = os.path.join(self.home, ".cache", "codebase-memory-mcp")
        os.makedirs(db_dir, exist_ok=True)
        with open(os.path.join(db_dir, support.slug(self.home) + ".db"), "w"):
            pass
        self.assertIsNone(self.decide("Grep", {"pattern": "some_identifier"}))


if __name__ == "__main__":
    unittest.main()
