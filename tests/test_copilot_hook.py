"""hosts/copilot/hook.py on Copilot CLI-shaped payloads: the gate, evidence, Stop
read from the session's event log, and the subagent events.

The field and tool names are Copilot's own (docs.github.com hooks-reference):
PascalCase events with snake_case fields and Claude tool names, a top-level
`permissionDecision` deny, PostToolUse's `tool_result.text_result_for_llm`,
PostToolUseFailure's `error`, and a camelCase `subagentStart` whose command
names the event. Stop carries no reply text, so the reply comes from the
`assistant.message` rows of `transcript_path`.
"""
import json
import os
import unittest

import support
from support import TempHome, run, run_json

DENIED = "git commit --no-verify -m x"
SECRET = "API = \"ghp_" + "A1b2C3d4" * 5 + "\"\n"


class CopilotHook(TempHome):
    def setUp(self):
        super().setUp()
        self.repo = self.make_repo("proj")
        self.envv = self.env()
        self.session = "s-copilot"
        self.transcript = os.path.join(self.home, "events.jsonl")

    def send(self, event, argv=(), **fields):
        payload = {"hook_event_name": event, "cwd": self.repo,
                   "session_id": self.session, "timestamp": "2026-10-29T00:00:00Z",
                   "transcript_path": self.transcript}
        if not event:
            payload.pop("hook_event_name")
        payload.update(fields)
        out, proc = run_json([support.COPILOT_HOOK, *argv], payload, env=self.envv)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        return out or {}

    def bash(self, command, event="PostToolUse", text=None, **fields):
        if text is not None:
            fields["tool_result"] = {"result_type": "success", "text_result_for_llm": text}
        return self.send(event, tool_name="Bash", tool_input={"command": command}, **fields)

    def reply(self, *rows):
        with open(self.transcript, "w", encoding="utf-8") as fh:
            for row in rows:
                fh.write(json.dumps(row) + "\n")

    def rows(self):
        rows, _ = run_json([support.PROBE_INTEGRITY],
                           {"fn": "events", "session": self.session}, env=self.envv)
        return rows

    def test_a_gate_refused_shell_call_is_denied_at_the_top_level(self):
        out = self.bash(DENIED, event="PreToolUse")
        self.assertEqual(out["permissionDecision"], "deny")
        self.assertIn("--no-verify", out["permissionDecisionReason"])
        self.assertNotIn("hookSpecificOutput", out)

    def test_an_allowed_call_answers_nothing(self):
        self.assertEqual(self.bash("ls -la", event="PreToolUse"), {})

    def test_claude_and_runtime_names_reach_the_gate(self):
        for name, inp in (("Write", {"path": os.path.join(self.repo, "a.py"),
                                     "file_text": SECRET}),
                          ("create", {"path": os.path.join(self.repo, "a.py"),
                                      "file_text": SECRET}),
                          ("Edit", {"path": os.path.join(self.repo, "b.py"),
                                    "old_str": "x = 1\n", "new_str": SECRET}),
                          ("bash", {"command": DENIED})):
            out = self.send("PreToolUse", tool_name=name, tool_input=inp)
            self.assertEqual(out.get("permissionDecision"), "deny", name)

    def test_a_patch_edit_reaches_the_gate_as_apply_patch(self):
        patch = ("*** Begin Patch\n*** Add File: %s\n+%s*** End Patch\n"
                 % (os.path.join(self.repo, "c.py"), SECRET))
        for inp in (patch, {"input": patch}):
            out = self.send("PreToolUse", tool_name="Edit", tool_input=inp)
            self.assertEqual(out.get("permissionDecision"), "deny", inp)

    def test_an_mcp_tool_maps_to_the_shared_name_for_a_known_server(self):
        os.makedirs(os.path.join(self.home, ".copilot"))
        with open(os.path.join(self.home, ".copilot", "mcp-config.json"), "w") as fh:
            json.dump({"mcpServers": {"my-graph": {}, "codegraph": {}}}, fh)
        self.send("PostToolUse", tool_name="codegraph-codegraph_explore",
                  tool_input={"query": "x"},
                  tool_result={"result_type": "success", "text_result_for_llm": "ok"})
        # an MCP answer is an `external` row naming the call (tezgah_integrity)
        details = [r.get("detail") or "" for r in self.rows() if r.get("kind") == "external"]
        self.assertTrue(any("mcp__codegraph__codegraph_explore" in d for d in details),
                        details)

    def test_both_halves_name_the_shell_call_alike(self):
        # the loop guard denies a third identical failing run only if the
        # PostToolUseFailure rows and the PreToolUse call hash to one id
        for _ in range(2):
            self.send("PostToolUseFailure", tool_name="bash",
                      tool_input={"command": "pytest -q"}, error="1 failed")
        out = self.bash("pytest -q", event="PreToolUse")
        self.assertEqual(out.get("permissionDecision"), "deny")

    def test_session_start_carries_the_core_until_the_instructions_file_does(self):
        out = self.send("SessionStart", source="startup")
        self.assertIn("**Turkish, BLUF.**", out["additionalContext"])
        rules = os.path.join(self.home, ".copilot", "copilot-instructions.md")
        os.makedirs(os.path.dirname(rules))
        with open(rules, "w") as fh:
            fh.write("<!-- tezgah:start --> (managed)\ncore\n<!-- tezgah:end -->\n")
        out = self.send("SessionStart", source="startup")
        self.assertNotIn("**Turkish, BLUF.**", out.get("additionalContext", ""))

    def test_a_prompt_writes_the_turn_row_and_answers_nothing(self):
        self.assertEqual(self.send("UserPromptSubmit", prompt="fix the parser"), {})
        self.assertIn("turn", [r.get("kind") for r in self.rows()])

    def test_unverified_done_claim_read_from_the_event_log_blocks(self):
        self.bash("ls -la", text="x\n<exited with exit code 0>")
        self.reply({"type": "user.message", "data": {"content": "fix it"}},
                   {"type": "assistant.message",
                    "data": {"content": "Done. Implemented the parser and all tests pass."}})
        out = self.send("Stop", stop_reason="end_turn", stop_hook_active=False)
        self.assertEqual(out.get("decision"), "block")
        self.assertTrue(out.get("reason"))

    def test_a_done_claim_backed_by_a_passing_check_ends_the_turn(self):
        self.bash("python3 -m pytest -q", text="3 passed\n<exited with exit code 0>")
        self.reply({"type": "assistant.message", "data": {"content": "Done. All tests pass."}})
        self.assertNotIn("decision", self.send("Stop", stop_hook_active=False))

    def test_a_shell_exit_code_overrides_a_success_event(self):
        self.bash("python3 -m pytest -q", text="1 failed\n<exited with exit code 1>")
        self.reply({"type": "assistant.message", "data": {"content": "Done. All tests pass."}})
        self.assertEqual(self.send("Stop", stop_hook_active=False).get("decision"), "block")
        self.assertIn("blocked: check failed",
                      [r.get("detail") for r in self.rows() if r.get("kind") == "claim"])

    def test_an_unread_reply_is_recorded_and_not_judged(self):
        self.bash("ls -la", text="x")
        # the log ends on the user's message: no reply written yet
        self.reply({"type": "assistant.message", "data": {"content": "Done. All tests pass."}},
                   {"type": "user.message", "data": {"content": "and now?"}})
        self.assertNotIn("decision", self.send("Stop", stop_hook_active=False))
        rows = self.rows()
        unread = [r for r in rows if r.get("kind") == "reply_unread"]
        self.assertEqual(len(unread), 1, rows)
        self.assertIn(self.transcript, unread[0]["detail"])
        self.assertFalse([r for r in rows if r.get("kind") in ("claim", "refusal")], rows)

    def test_subagent_start_briefs_and_subagent_stop_only_records(self):
        out = self.send("", argv=("subagentStart",), session_id=None,
                        sessionId=self.session, transcriptPath=self.transcript,
                        agentName="explore")
        self.assertIn("You are a subagent", out["additionalContext"])
        out = self.send("SubagentStop", agent_id="a1", agent_type="explore",
                        agent_name="explore", stop_reason="end_turn",
                        last_assistant_message="Done. All tests pass.")
        self.assertEqual(out, {})
        self.assertIn("subagent_end", [r.get("kind") for r in self.rows()])

    def test_outside_the_roots_stop_does_not_judge(self):
        proc = run([support.COPILOT_HOOK],
                   {"hook_event_name": "Stop", "cwd": self.home, "session_id": "x",
                    "transcript_path": self.transcript}, env=self.envv)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertNotIn("decision", json.loads(proc.stdout or "{}"))


if __name__ == "__main__":
    unittest.main()
