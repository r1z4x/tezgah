"""hosts/droid/hook.py on Factory Droid-shaped payloads: the gate, evidence, Stop
read from the transcript, and the record-only subagent end.

The field and tool names are Droid's own (docs.factory.com harness/hooks; the
0.251.0 bundle for ApplyPatch's `input`): `Execute`, `Create`, `ApplyPatch`;
PostToolUse for every finished call, with no failure event; Stop with no reply
text, so the reply comes from the `transcript_path` JSONL, whose rows are
`{"type": "message", "message": {"role", "content": [...]}}`.
"""
import json
import os
import unittest

import support
from support import TempHome, run, run_json

DENIED = "git commit --no-verify -m x"


class DroidHook(TempHome):
    def setUp(self):
        super().setUp()
        self.repo = self.make_repo("proj")
        self.envv = self.env()
        self.session = "s-droid"
        self.transcript = os.path.join(self.home, "session.jsonl")

    def send(self, event, **fields):
        payload = {"hook_event_name": event, "cwd": self.repo,
                   "session_id": self.session, "permission_mode": "auto-low",
                   "transcript_path": self.transcript}
        payload.update(fields)
        out, proc = run_json([support.DROID_HOOK], payload, env=self.envv)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        return out or {}

    def shell(self, command, event="PostToolUse", **fields):
        return self.send(event, tool_name="Execute",
                         tool_input={"command": command, "riskLevel": "low"}, **fields)

    def reply(self, *rows):
        """Write the transcript: (role, [block types or text]) per message row."""
        with open(self.transcript, "w", encoding="utf-8") as fh:
            for role, content in rows:
                fh.write(json.dumps({"type": "message", "id": "m",
                                     "timestamp": "2026-10-29T00:00:00.000Z",
                                     "message": {"role": role, "content": content}}) + "\n")

    def test_a_gate_refused_shell_call_is_denied_in_droid_s_shape(self):
        hso = self.shell(DENIED, event="PreToolUse")["hookSpecificOutput"]
        self.assertEqual(hso["hookEventName"], "PreToolUse")
        self.assertEqual(hso["permissionDecision"], "deny")
        self.assertIn("--no-verify", hso["permissionDecisionReason"])

    def test_an_allowed_call_answers_nothing(self):
        self.assertEqual(self.shell("ls -la", event="PreToolUse"), {})

    def test_create_and_apply_patch_reach_the_gate_under_droid_s_ids(self):
        secret = "API = \"ghp_" + "A1b2C3d4" * 5 + "\"\n"
        out = self.send("PreToolUse", tool_name="Create",
                        tool_input={"file_path": os.path.join(self.repo, "a.py"),
                                    "content": secret})
        self.assertEqual(out["hookSpecificOutput"]["permissionDecision"], "deny")
        # ApplyPatch carries its patch text as `input`
        patch = ("*** Begin Patch\n*** Add File: %s\n+%s*** End Patch"
                 % (os.path.join(self.repo, "b.py"), secret))
        out = self.send("PreToolUse", tool_name="ApplyPatch", tool_input={"input": patch})
        self.assertEqual(out["hookSpecificOutput"]["permissionDecision"], "deny")

    def test_both_halves_name_the_shell_call_alike(self):
        # the loop guard denies a third identical failing run only if the
        # PostToolUse rows, read failed off the exit line, and the PreToolUse
        # call hash to one id
        for _ in range(2):
            self.shell("pytest -q", tool_response="1 failed\n\n[Process exited with code 1]")
        out = self.shell("pytest -q", event="PreToolUse")
        self.assertEqual(out["hookSpecificOutput"]["permissionDecision"], "deny")

    def test_session_start_carries_the_core_until_agents_md_does(self):
        ctx = self.send("SessionStart", source="startup")["hookSpecificOutput"]
        self.assertEqual(ctx["hookEventName"], "SessionStart")
        self.assertIn("**Turkish, BLUF.**", ctx["additionalContext"])
        rules = os.path.join(self.home, ".factory", "AGENTS.md")
        os.makedirs(os.path.dirname(rules))
        with open(rules, "w") as fh:
            fh.write("<!-- tezgah:start --> (managed)\ncore\n<!-- tezgah:end -->\n")
        ctx = self.send("SessionStart", source="startup")["hookSpecificOutput"]
        self.assertNotIn("**Turkish, BLUF.**", ctx["additionalContext"])

    def test_the_prompt_gets_the_per_turn_reminder(self):
        hso = self.send("UserPromptSubmit", prompt="fix the parser",
                        has_images=False)["hookSpecificOutput"]
        self.assertEqual(hso["hookEventName"], "UserPromptSubmit")
        self.assertTrue(hso["additionalContext"].strip())

    def test_unverified_done_claim_read_from_the_transcript_blocks(self):
        self.shell("ls -la", tool_response="x\n\n[Process exited with code 0]")
        self.reply(("user", [{"type": "text", "text": "fix it"}]),
                   ("assistant", [{"type": "thinking", "thinking": "..."},
                                  {"type": "text",
                                   "text": "Done. Implemented the parser and all tests pass."}]))
        out = self.send("Stop", stop_hook_active=False, tool_execution_count=1,
                        elapsed_time=3)
        self.assertEqual(out.get("decision"), "block")
        self.assertTrue(out.get("reason"))

    def test_a_done_claim_backed_by_a_passing_check_ends_the_turn(self):
        self.shell("python3 -m pytest -q",
                   tool_response="3 passed\n\n[Process exited with code 0]")
        self.reply(("assistant", [{"type": "text", "text": "Done. All tests pass."}]))
        self.assertNotIn("decision", self.send("Stop", stop_hook_active=False))

    def test_a_failing_check_is_read_off_the_exit_line(self):
        self.shell("python3 -m pytest -q",
                   tool_response="1 failed\n\n[Process exited with code 1]")
        self.reply(("assistant", [{"type": "text", "text": "Done. All tests pass."}]))
        self.assertEqual(self.send("Stop", stop_hook_active=False).get("decision"), "block")
        rows, _ = run_json([support.PROBE_INTEGRITY],
                           {"fn": "events", "session": self.session}, env=self.envv)
        # a check that FAILED, not one whose outcome went unread
        self.assertIn("blocked: check failed",
                      [r.get("detail") for r in rows if r.get("kind") == "claim"], rows)

    def test_an_unread_reply_is_recorded_and_not_judged(self):
        self.shell("ls -la", tool_response="x\n\n[Process exited with code 0]")
        # the last message is a tool result: no reply written yet
        self.reply(("assistant", [{"type": "text", "text": "Done. All tests pass."},
                                  {"type": "tool_use", "id": "t", "name": "Execute",
                                   "input": {"command": "ls"}}]),
                   ("user", [{"type": "tool_result", "tool_use_id": "t", "content": "x"}]))
        self.assertEqual(self.send("Stop", stop_hook_active=False), {})
        rows, _ = run_json([support.PROBE_INTEGRITY],
                           {"fn": "events", "session": self.session}, env=self.envv)
        unread = [r for r in rows if r.get("kind") == "reply_unread"]
        self.assertEqual(len(unread), 1, rows)
        self.assertIn(self.transcript, unread[0]["detail"])
        self.assertFalse([r for r in rows if r.get("kind") in ("claim", "refusal")], rows)

    def test_a_subagent_end_is_recorded_never_blocked(self):
        out = self.send("SubagentStop", stop_hook_active=False, task_name="worker",
                        task_result="Done. All tests pass.", task_error=None)
        self.assertEqual(out, {})

    def test_outside_the_roots_stop_is_inert(self):
        proc = run([support.DROID_HOOK],
                   {"hook_event_name": "Stop", "cwd": self.home, "session_id": "x",
                    "transcript_path": self.transcript}, env=self.envv)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(proc.stdout.strip(), "")


if __name__ == "__main__":
    unittest.main()
