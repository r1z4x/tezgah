"""hosts/qwen/hook.py on Qwen Code-shaped payloads: the gate, evidence, Stop and
the subagent brief.

The field and tool names are Qwen Code 0.21.13's own (its bundled hooks doc and
the `ToolNames` table in its bundle): `run_shell_command`, `write_file`, `agent`;
PostToolUse for a call that succeeded and PostToolUseFailure, with `error` and
`is_interrupt`, for one that failed; Stop with `last_assistant_message`.
"""
import os
import unittest

import support
from support import TempHome, run, run_json

DENIED = "git commit --no-verify -m x"


class QwenHook(TempHome):
    def setUp(self):
        super().setUp()
        self.repo = self.make_repo("proj")
        self.envv = self.env()
        self.session = "s-qwen"

    def send(self, event, **fields):
        payload = {"hook_event_name": event, "cwd": self.repo,
                   "session_id": self.session,
                   "transcript_path": os.path.join(self.home, "t.jsonl"),
                   "timestamp": "2026-10-29T00:00:00Z"}
        payload.update(fields)
        out, proc = run_json([support.QWEN_HOOK], payload, env=self.envv)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        return out or {}

    def shell(self, command, event="PostToolUse", **fields):
        return self.send(event, permission_mode="default",
                         tool_name="run_shell_command",
                         tool_input={"command": command, "is_background": False},
                         tool_use_id="toolu_1", **fields)

    def test_a_gate_refused_shell_call_is_denied_in_qwen_s_shape(self):
        out = self.shell(DENIED, event="PreToolUse")
        hso = out["hookSpecificOutput"]
        self.assertEqual(hso["hookEventName"], "PreToolUse")
        self.assertEqual(hso["permissionDecision"], "deny")
        self.assertIn("--no-verify", hso["permissionDecisionReason"])

    def test_an_allowed_call_answers_nothing(self):
        self.assertEqual(self.shell("ls -la", event="PreToolUse"), {})

    def test_a_write_tool_reaches_the_gate_under_its_qwen_id(self):
        out = self.send("PreToolUse", tool_name="write_file",
                        tool_input={"file_path": os.path.join(self.repo, "a.py"),
                                    "content": "API = \"ghp_" + "A1b2C3d4" * 5 + "\"\n"})
        self.assertEqual(out["hookSpecificOutput"]["permissionDecision"], "deny")

    def test_monitor_and_notebook_edit_reach_the_gate(self):
        # review of plan 138: `monitor` runs a shell command and `notebook_edit`
        # writes a file; neither may pass the gate under its raw Qwen id
        out = self.send("PreToolUse", tool_name="monitor",
                        tool_input={"command": DENIED, "description": "watch"})
        self.assertEqual(out["hookSpecificOutput"]["permissionDecision"], "deny")
        switch = os.path.join(self.home, ".config", "tezgah", "pretooluse-off")
        out = self.send("PreToolUse", tool_name="notebook_edit",
                        tool_input={"notebook_path": switch, "new_source": "x"})
        self.assertEqual(out["hookSpecificOutput"]["permissionDecision"], "deny")

    def test_both_halves_name_the_shell_call_alike(self):
        # the loop guard denies a third identical failing run only if the
        # PostToolUseFailure rows and the PreToolUse call hash to one id
        for _ in range(2):
            self.shell("pytest -q", event="PostToolUseFailure",
                       error="Exit Code: 1", is_interrupt=False)
        out = self.shell("pytest -q", event="PreToolUse")
        self.assertEqual(out["hookSpecificOutput"]["permissionDecision"], "deny")

    def test_session_start_carries_the_core_until_qwen_md_does(self):
        start = dict(source="startup", model="qwen3-coder", permission_mode="default")
        ctx = self.send("SessionStart", **start)["hookSpecificOutput"]
        self.assertEqual(ctx["hookEventName"], "SessionStart")
        self.assertIn("**Turkish, BLUF.**", ctx["additionalContext"])
        rules = os.path.join(self.home, ".qwen", "QWEN.md")
        os.makedirs(os.path.dirname(rules))
        with open(rules, "w") as fh:
            fh.write("<!-- tezgah:start --> (managed)\ncore\n<!-- tezgah:end -->\n")
        ctx = self.send("SessionStart", **start)["hookSpecificOutput"]
        self.assertNotIn("**Turkish, BLUF.**", ctx["additionalContext"])

    def test_the_prompt_gets_the_per_turn_reminder(self):
        hso = self.send("UserPromptSubmit", prompt="fix the parser")["hookSpecificOutput"]
        self.assertEqual(hso["hookEventName"], "UserPromptSubmit")
        self.assertTrue(hso["additionalContext"].strip())

    def test_subagent_start_hands_the_delegate_a_brief(self):
        hso = self.send("SubagentStart", permission_mode="default",
                        agent_id="sub-1", agent_type="general-purpose")["hookSpecificOutput"]
        self.assertEqual(hso["hookEventName"], "SubagentStart")
        self.assertTrue(hso["additionalContext"].strip())

    def test_unverified_done_claim_blocks_with_a_reason(self):
        self.shell("ls -la", tool_response={"llmContent": "x", "returnDisplay": "x"})
        out = self.send("Stop", stop_hook_active=False,
                        last_assistant_message="Done. Implemented the parser and all tests pass.")
        self.assertEqual(out.get("decision"), "block")
        self.assertTrue(out.get("reason"))

    def test_a_done_claim_backed_by_a_passing_check_ends_the_turn(self):
        self.shell("python3 -m pytest -q",
                   tool_response={"llmContent": "3 passed", "returnDisplay": "3 passed"})
        out = self.send("Stop", stop_hook_active=False,
                        last_assistant_message="Done. All tests pass.")
        self.assertNotIn("decision", out)

    def test_a_subagent_end_is_recorded_never_blocked(self):
        out = self.send("SubagentStop", stop_hook_active=False, agent_id="sub-1",
                        agent_type="general-purpose",
                        last_assistant_message="Done. All tests pass.")
        self.assertEqual(out, {})

    def test_outside_the_roots_stop_is_inert(self):
        proc = run([support.QWEN_HOOK],
                   {"hook_event_name": "Stop", "cwd": self.home, "session_id": "x",
                    "last_assistant_message": "Done. All tests pass."}, env=self.envv)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(proc.stdout.strip(), "")


if __name__ == "__main__":
    unittest.main()
