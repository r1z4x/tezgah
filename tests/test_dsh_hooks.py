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
import subprocess
import unittest

import support
from support import TempHome, run_json

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
# Claude's matcher dialect, which the bridge implements (matchesMatcher in
# @deepseek-ai/dsh-hook-protocol): a pattern made only of these characters is a
# list of exact names, anything else an unanchored regular expression.
LITERAL = re.compile(r"^[A-Za-z0-9_\- ,|]+$")


def selects(matcher, tool):
    if LITERAL.match(matcher):
        return tool in matcher.split("|")
    return re.search(matcher, tool) is not None


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
        # The dsh manifest stays Claude's manifest: one group per event, the same
        # matcher and the same script, so what the bridge runs is what Claude runs
        # - the one deliberate difference is the outcome declaration the next test
        # pins, and a command that could drift anywhere else would desynchronise
        # them silently.
        claude = self.load(CLAUDE_MANIFEST)
        for event, groups in self.load(DSH_MANIFEST).items():
            self.assertEqual(len(groups), len(claude[event]), event)
            for ours, theirs in zip(groups, claude[event]):
                self.assertEqual(ours.get("matcher"), theirs.get("matcher"), event)
                self.assertEqual(self.scripts(ours), self.scripts(theirs), event)
                for hook in ours["hooks"]:
                    for path in SCRIPT.findall(hook["command"]):
                        self.assertTrue(
                            os.path.exists(os.path.join(REPO, path)), path)

    def test_the_post_tool_use_command_declares_that_dsh_reports_no_outcome(self):
        # The bridge runs this hook for a failed call too - dsh's
        # ToolExecutionResult is a success|failure union, and
        # `tools/post-execute` is documented to fire for tool failures - while
        # the payload it builds carries no outcome field. Without the
        # declaration a failed `pytest` on dsh would be recorded verify_ok and
        # the Stop rule would trust a pass nobody saw. Claude splits the two
        # outcomes across two events instead, so its command stays plain.
        ours = self.command("PostToolUse")
        self.assertIn("TEZGAH_CALL_OUTCOME=none ", ours)
        self.assertNotIn("TEZGAH_CALL_OUTCOME", self.claude_command("PostToolUse"))
        for event in ("SessionStart", "UserPromptSubmit", "PreToolUse", "Stop"):
            self.assertEqual(self.command(event), self.claude_command(event), event)

    def command(self, event, path=None):
        with open(path or DSH_MANIFEST) as fh:
            groups = json.load(fh)["hooks"][event]
        return groups[0]["hooks"][0]["command"]

    def claude_command(self, event):
        return self.command(event, CLAUDE_MANIFEST)

    @staticmethod
    def scripts(group):
        return [SCRIPT.findall(h["command"]) for h in group["hooks"]]


class DshToolVocabulary(unittest.TestCase):
    """The matcher has to select the names dsh itself registers, or the bridge
    never runs the hook on that host and the ledger stays empty there.

    dsh's own tool packages name these tools differently from Claude's:
    `bash` (dsh-tool-bash), `edit`/`write` (dsh-tool-fs), `pwsh` (dsh-tool-pwsh),
    `str_replace_editor` (dsh-tool-str-replace-editor), `web_search`/`web_fetch`
    (dsh-tool-web) and MCP tools as `mcp__<server>__<tool>` (dsh-mcp-client).
    Claude's spellings stay in the same group - it is one regex - so neither
    host loses a name it had."""

    def matchers(self, event):
        with open(DSH_MANIFEST) as fh:
            groups = json.load(fh)["hooks"][event]
        return [g["matcher"] for g in groups if g.get("matcher")]

    def test_post_tool_use_selects_dsh_own_effect_and_read_tools(self):
        # Without these the hook never fires on a dsh session: no step row is
        # written for a shell command or an edit, so the Stop rule reads an empty
        # ledger on that host and has nothing to decide on.
        for tool in ("bash", "pwsh", "edit", "write", "str_replace_editor",
                     "web_search", "web_fetch", "mcp__github__get_file"):
            with self.subTest(tool=tool):
                self.assertTrue(any(selects(m, tool)
                                    for m in self.matchers("PostToolUse")), tool)

    def test_post_tool_use_still_selects_claude_names(self):
        for tool in ("Bash", "PowerShell", "Edit", "Write", "MultiEdit",
                     "NotebookEdit", "WebFetch", "WebSearch"):
            with self.subTest(tool=tool):
                self.assertTrue(any(selects(m, tool)
                                    for m in self.matchers("PostToolUse")), tool)

    def test_post_tool_use_leaves_an_ordinary_read_alone(self):
        # The hook spawns python per matched call, so a read-heavy turn must not
        # pay for rows nothing reads; dsh's MCP reads come through `mcp__*`.
        for tool in ("read", "Read", "grep", "Grep", "search_graph"):
            with self.subTest(tool=tool):
                self.assertFalse(any(selects(m, tool)
                                     for m in self.matchers("PostToolUse")), tool)


class DshLedger(TempHome):
    """The manifest's own command, run the way the bridge runs it: the string
    from hosts/dsh/hooks.json with `${CLAUDE_PLUGIN_ROOT}` substituted, and the
    payload shape the bridge builds (lib/index.js postToolPayload/stopPayload).

    Before the matcher carried dsh's tool names, no call on that host reached
    PostToolUse at all: the ledger held no step rows, so the Stop rule had no
    evidence to read and the whole integrity control was dead there."""

    def setUp(self):
        super().setUp()
        self.repo = self.make_repo("proj")
        self.envv = self.env()
        self.session = "s-dsh-ledger"

    def command(self, event):
        with open(DSH_MANIFEST) as fh:
            cmd = json.load(fh)["hooks"][event][0]["hooks"][0]["command"]
        return cmd.replace("${CLAUDE_PLUGIN_ROOT}", REPO)

    def run_command(self, event, payload):
        proc = subprocess.run(["sh", "-c", self.command(event)],
                              input=json.dumps(payload), capture_output=True,
                              text=True, env=self.envv, timeout=60)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        return proc.stdout.strip()

    def post(self, tool, inp, response=""):
        return self.run_command("PostToolUse", self.payload(tool, inp, response))

    def payload(self, tool, inp, response=""):
        return {"session_id": self.session, "transcript_path": "",
                "cwd": self.repo, "hook_event_name": "PostToolUse",
                "tool_name": tool, "tool_input": inp, "tool_use_id": "call-1",
                "tool_response": response}

    def rows(self, session=None):
        out, _ = run_json([support.PROBE_INTEGRITY],
                          {"fn": "events", "session": session or self.session},
                          env=self.envv)
        return out

    def test_a_dsh_shell_and_edit_call_reach_the_ledger(self):
        self.post("bash", {"command": "ls -la"}, "x.py")
        self.post("str_replace_editor", {"path": "x.py", "command": "str_replace"})
        self.assertEqual([(r["kind"], r["detail"]) for r in self.rows()],
                         [("run", "ls -la"), ("edit", "str_replace")])

    def test_a_dsh_check_records_that_it_ran_not_that_it_passed(self):
        # The bridge runs the hook for a failed call too and its payload carries
        # no outcome, so a pass is never claimed on this host: the row says the
        # check ran, which is what the Stop rule needs to keep a "tests pass"
        # claim from ending a turn it cannot evidence.
        self.post("bash", {"command": "pytest -q"}, "1 failed")
        self.assertEqual([(r["kind"], "exit" in r) for r in self.rows()],
                         [("verify", False)])

    def test_a_dsh_web_result_is_labelled(self):
        out = self.post("web_fetch", {"url": "https://x"}, "page text")
        self.assertIn("untrusted content", out)
        self.assertIn("a web result", out)

    def test_the_stop_rule_no_longer_needs_the_reply_the_bridge_drops(self):
        # The bridge's stopPayload sends Claude's base fields plus
        # `stop_hook_active` - no `last_assistant_message`. That used to leave the
        # Stop rule mute on dsh, and this test pinned that as a tripwire. The
        # trigger is evidence-shaped now: a turn whose ledger shows work and no
        # passing check is refused whatever the reply said, so the missing field
        # no longer disables the control here. The claim the bridge drops is still
        # refused - now on the strength of the ledger alone, which is the point.
        self.post("bash", {"command": "pytest -q"}, "1 failed")
        stop = {"session_id": self.session, "transcript_path": "", "cwd": self.repo,
                "hook_event_name": "Stop", "stop_hook_active": False}
        self.assertNotIn("last_assistant_message", stop)
        self.assertNotEqual(self.run_command("Stop", stop), "")
        # the same session, with the claim the bridge drops: still refused
        self.assertNotEqual(self.run_command(
            "Stop", dict(stop, last_assistant_message="Done. All tests pass.")), "")


if __name__ == "__main__":
    unittest.main()
