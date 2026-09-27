"""hooks/projects-auto-init.py and hooks/projects-pretooluse.py (Claude envelope)."""
import os
import unittest

import support
from support import TempHome, run, run_json


class AutoInit(TempHome):
    def test_session_start_emits_context(self):
        repo = self.make_repo()
        out, proc = run_json([support.AUTO_INIT],
                             {"hook_event_name": "SessionStart", "cwd": repo,
                              "session_id": "s"}, env=self.env())
        self.assertEqual(proc.returncode, 0, proc.stderr)
        hso = out["hookSpecificOutput"]
        self.assertEqual(hso["hookEventName"], "SessionStart")
        self.assertTrue(hso["additionalContext"].strip())

    def test_outside_roots_prints_nothing(self):
        proc = run([support.AUTO_INIT],
                   {"hook_event_name": "SessionStart", "cwd": self.home},
                   env=self.env())
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(proc.stdout.strip(), "")


class AutoInitCoreInFile(TempHome):
    """install_claude writes the always-on core into `~/.claude/CLAUDE.md`, which
    Claude reads into every session, so a session whose manifest declares that
    file (`TEZGAH_CORE_IN_FILE`) has to get the core from the file and not a
    second time from this hook - while dsh, which runs this same script through
    its claude-code bridge, still gets it here."""

    def setUp(self):
        super().setUp()
        self.repo = self.make_repo("proj")

    def rules(self):
        path = os.path.join(self.home, ".claude", "CLAUDE.md")
        os.makedirs(os.path.dirname(path), exist_ok=True)
        return path

    def core(self, extra=None, event="SessionStart"):
        """The additionalContext for one event, with the manifest's own env."""
        out, proc = run_json([support.AUTO_INIT],
                             {"hook_event_name": event, "cwd": self.repo,
                              "session_id": "s"}, env=self.env(extra=extra))
        self.assertEqual(proc.returncode, 0, proc.stderr)
        return out["hookSpecificOutput"]["additionalContext"]

    def declared(self):
        return {"TEZGAH_CORE_IN_FILE": "1"}

    def test_the_core_carrying_events_drop_the_core_and_keep_the_live_state(self):
        with open(self.rules(), "w") as fh:
            fh.write("<!-- tezgah:start -->\nblock\n<!-- tezgah:end -->\n")
        full = self.core()
        self.assertIn("**Turkish, BLUF.**", full)
        for event in ("SessionStart", "PostCompact"):
            text = self.core(self.declared(), event)
            self.assertNotIn("**Turkish, BLUF.**", text, event)
            self.assertTrue(text.strip(), "the live state went with the core")
            self.assertLess(len(text), len(full))

    def test_without_the_declaration_the_hook_still_carries_the_core(self):
        # dsh's shape: the same script, a manifest that declares nothing
        with open(self.rules(), "w") as fh:
            fh.write("<!-- tezgah:start -->\nblock\n<!-- tezgah:end -->\n")
        self.assertIn("**Turkish, BLUF.**", self.core())

    def test_a_deleted_file_falls_back_to_the_hook(self):
        # the file is read, not assumed: nothing in it means the core has no
        # other channel, and a session that lost it would be armed with nothing
        self.assertIn("**Turkish, BLUF.**", self.core(self.declared()))

    def test_the_subagent_brief_is_not_what_the_declaration_drops(self):
        # a subagent's own brief is its whole text, never the file's: the
        # declaration must leave this event untouched
        with open(self.rules(), "w") as fh:
            fh.write("<!-- tezgah:start -->\nblock\n<!-- tezgah:end -->\n")
        self.assertEqual(self.core(self.declared(), "SubagentStart"),
                         self.core(None, "SubagentStart"))


class PreToolUse(TempHome):
    def setUp(self):
        super().setUp()
        self.repo = self.make_repo("proj")
        self.envv = self.env()

    def payload(self, tool, inp):
        return {"cwd": self.repo, "tool_name": tool, "tool_input": inp,
                "session_id": "s"}

    def test_explore_denied(self):
        out, proc = run_json([support.PRETOOLUSE],
                             self.payload("Agent", {"subagent_type": "Explore"}),
                             env=self.envv)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        hso = out["hookSpecificOutput"]
        self.assertEqual(hso["permissionDecision"], "deny")
        self.assertTrue(hso["permissionDecisionReason"])

    def test_attribution_commit_denied(self):
        out, _ = run_json([support.PRETOOLUSE],
                          self.payload("Bash", {
                              "command": 'git commit -m "x Co-Authored-By: Claude"'}),
                          env=self.envv)
        self.assertEqual(out["hookSpecificOutput"]["permissionDecision"], "deny")

    def test_plain_commit_prints_nothing(self):
        proc = run([support.PRETOOLUSE],
                   self.payload("Bash", {"command": 'git commit -m "plain"'}),
                   env=self.envv)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(proc.stdout.strip(), "")

    def test_outside_roots_prints_nothing(self):
        payload = {"cwd": self.home, "tool_name": "Agent",
                   "tool_input": {"subagent_type": "Explore"}, "session_id": "s"}
        proc = run([support.PRETOOLUSE], payload, env=self.envv)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(proc.stdout.strip(), "")


if __name__ == "__main__":
    unittest.main()
