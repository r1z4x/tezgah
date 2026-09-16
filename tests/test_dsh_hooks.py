"""hosts/dsh/hooks.json: the manifest the dsh patch points the bridge at.

The dsh claude-code bridge (@deepseek-ai/dsh-hooks-claude-code) knows exactly
seven event names - SessionStart, UserPromptSubmit, PreToolUse, PostToolUse,
SubagentStart, SubagentStop, Stop - and ignores every other key in the manifest
silently (its CLAUDE_EVENTS list is what it iterates). dsh therefore gets its own
manifest instead of sharing Claude's: an event no bridge runs would look armed
while never firing, and two of the nine Claude declares are exactly that.
"""
import json
import os
import re
import unittest

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DSH_MANIFEST = os.path.join(REPO, "hosts", "dsh", "hooks.json")
CLAUDE_MANIFEST = os.path.join(REPO, "hooks", "hooks.json")
# The bridge's own list, read from
# @deepseek-ai/dsh-hooks-claude-code/lib/index.js (CLAUDE_EVENTS). A manifest key
# outside it is dropped before its groups are even parsed.
BRIDGE_EVENTS = {"SessionStart", "UserPromptSubmit", "PreToolUse", "PostToolUse",
                 "SubagentStart", "SubagentStop", "Stop"}
# The events tezgah declares for Claude that this bridge cannot run.
BRIDGE_UNSUPPORTED = {"PostCompact", "PostToolUseFailure"}
SCRIPT = re.compile(r"\$\{CLAUDE_PLUGIN_ROOT\}/([^\"]+)")


class DshManifest(unittest.TestCase):
    def load(self, path):
        with open(path) as fh:
            return json.load(fh)["hooks"]

    def test_declares_only_events_the_bridge_runs(self):
        events = set(self.load(DSH_MANIFEST))
        self.assertEqual(events & BRIDGE_UNSUPPORTED, set(),
                         "the bridge drops these silently")
        self.assertEqual(events - BRIDGE_EVENTS, set())

    def test_omits_exactly_what_the_bridge_cannot_run(self):
        # Anything Claude grows that the bridge cannot run has to be left out
        # here too, or the dsh manifest claims a hook that never fires.
        missing = set(self.load(CLAUDE_MANIFEST)) - set(self.load(DSH_MANIFEST))
        self.assertEqual(missing, BRIDGE_UNSUPPORTED)

    def test_every_group_matches_claude_and_its_script_exists(self):
        claude = self.load(CLAUDE_MANIFEST)
        for event, groups in self.load(DSH_MANIFEST).items():
            self.assertEqual(groups, claude[event], event)
            for group in groups:
                for hook in group["hooks"]:
                    for path in SCRIPT.findall(hook["command"]):
                        self.assertTrue(
                            os.path.exists(os.path.join(REPO, path)), path)


if __name__ == "__main__":
    unittest.main()
