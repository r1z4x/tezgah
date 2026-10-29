"""hosts/commandcode/hook.py on Command Code-shaped payloads: the gate, evidence,
Stop read from the transcript, and the status message.

The field and tool names are Command Code's own (commandcode.ai/docs/hooks):
`shell_command` with `command` and optional `args`, `write_file`, `edit_file`
with `old_value`/`new_value`; PostToolUse's `tool_response` is a string; Stop
carries no reply text, so the reply comes from the `transcript_path` JSONL.
"""
import json
import os
import unittest

import support
from support import TempHome, run, run_json

DENIED = "git commit --no-verify -m x"
SECRET = "API = \"ghp_" + "A1b2C3d4" * 5 + "\"\n"


class CommandCodeHook(TempHome):
    def setUp(self):
        super().setUp()
        self.repo = self.make_repo("proj")
        self.envv = self.env()
        self.session = "s-commandcode"
        self.transcript = os.path.join(self.home, "session.jsonl")

    def send(self, event, **fields):
        payload = {"hook_event_name": event, "cwd": self.repo,
                   "session_id": self.session, "permission_mode": "default",
                   "transcript_path": self.transcript}
        payload.update(fields)
        out, proc = run_json([support.COMMANDCODE_HOOK], payload, env=self.envv)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        return out or {}

    def shell(self, command, event="PostToolUse", **fields):
        return self.send(event, tool_name="shell_command", tool_display_name="SHELL",
                         tool_use_id="t1", tool_input={"command": command}, **fields)

    def reply(self, *rows):
        with open(self.transcript, "w", encoding="utf-8") as fh:
            for row in rows:
                fh.write(json.dumps(row) + "\n")

    def test_a_gate_refused_shell_call_is_denied_in_command_code_s_shape(self):
        hso = self.shell(DENIED, event="PreToolUse")["hookSpecificOutput"]
        self.assertEqual(hso["hookEventName"], "PreToolUse")
        self.assertEqual(hso["permissionDecision"], "deny")
        self.assertIn("--no-verify", hso["permissionDecisionReason"])

    def test_the_command_and_its_split_args_reach_the_gate_together(self):
        out = self.send("PreToolUse", tool_name="shell_command", tool_display_name="SHELL",
                        tool_input={"command": "git", "args": ["commit", "--no-verify",
                                                               "-m", "a b"]})
        self.assertEqual(out["hookSpecificOutput"]["permissionDecision"], "deny")

    def test_an_allowed_call_answers_nothing(self):
        self.assertEqual(self.shell("ls -la", event="PreToolUse"), {})

    def test_write_and_edit_reach_the_gate_under_command_code_s_ids(self):
        out = self.send("PreToolUse", tool_name="write_file", tool_display_name="WRITE",
                        tool_input={"file_path": os.path.join(self.repo, "a.py"),
                                    "content": SECRET})
        self.assertEqual(out["hookSpecificOutput"]["permissionDecision"], "deny")
        # the edit's new text arrives as `new_value`
        out = self.send("PreToolUse", tool_name="edit_file", tool_display_name="EDIT",
                        tool_input={"file_path": os.path.join(self.repo, "b.py"),
                                    "old_value": "x = 1\n", "new_value": SECRET})
        self.assertEqual(out["hookSpecificOutput"]["permissionDecision"], "deny")

    def test_both_halves_name_the_shell_call_alike(self):
        # the loop guard denies a third identical failing run only if the
        # PostToolUse rows, read failed off the exit code, and the PreToolUse
        # call hash to one id
        for _ in range(2):
            self.shell("pytest -q", tool_response="1 failed\nExit code: 1")
        out = self.shell("pytest -q", event="PreToolUse")
        self.assertEqual(out["hookSpecificOutput"]["permissionDecision"], "deny")

    def test_session_start_carries_the_core_until_agents_md_does(self):
        out = self.send("SessionStart", source="startup")
        self.assertIn("**Turkish, BLUF.**", out["hookSpecificOutput"]["additionalContext"])
        self.assertTrue(out["systemMessage"].startswith("tezgah  "))
        rules = os.path.join(self.home, ".commandcode", "AGENTS.md")
        os.makedirs(os.path.dirname(rules))
        with open(rules, "w") as fh:
            fh.write("<!-- tezgah:start --> (managed)\ncore\n<!-- tezgah:end -->\n")
        out = self.send("SessionStart", source="startup")
        self.assertNotIn("**Turkish, BLUF.**",
                         (out.get("hookSpecificOutput") or {}).get("additionalContext", ""))

    def test_unverified_done_claim_read_from_the_transcript_blocks(self):
        self.shell("ls -la", tool_response="x\nexit code 0")
        self.reply({"type": "user", "message": {"role": "user", "content": "fix it"}},
                   {"type": "assistant", "message": {"role": "assistant", "content": [
                       {"type": "text",
                        "text": "Done. Implemented the parser and all tests pass."}]}})
        out = self.send("Stop", stop_hook_active=False)
        self.assertEqual(out.get("decision"), "block")
        self.assertTrue(out.get("reason"))
        self.assertTrue(out["systemMessage"].startswith("tezgah  "))

    def test_a_done_claim_backed_by_a_passing_check_ends_the_turn(self):
        self.shell("python3 -m pytest -q", tool_response="3 passed\nExit code: 0")
        self.reply({"role": "assistant", "content": "Done. All tests pass."})
        self.assertNotIn("decision", self.send("Stop", stop_hook_active=False))

    def test_a_failing_check_is_read_off_the_exit_code(self):
        self.shell("python3 -m pytest -q", tool_response="1 failed\nexit code: 1")
        self.reply({"role": "assistant", "content": "Done. All tests pass."})
        self.assertEqual(self.send("Stop", stop_hook_active=False).get("decision"), "block")
        rows, _ = run_json([support.PROBE_INTEGRITY],
                           {"fn": "events", "session": self.session}, env=self.envv)
        self.assertIn("blocked: check failed",
                      [r.get("detail") for r in rows if r.get("kind") == "claim"], rows)

    def test_a_result_with_no_exit_code_is_a_run_never_a_pass(self):
        self.shell("python3 -m pytest -q", tool_response="3 passed")
        self.reply({"role": "assistant", "content": "Done. All tests pass."})
        self.assertEqual(self.send("Stop", stop_hook_active=False).get("decision"), "block")

    def test_an_unread_reply_is_recorded_and_not_judged(self):
        self.shell("ls -la", tool_response="x\nexit code 0")
        # the transcript ends on a tool result: no reply written yet
        self.reply({"type": "assistant", "message": {"role": "assistant", "content": [
                       {"type": "text", "text": "Done. All tests pass."}]}},
                   {"type": "user", "message": {"role": "user", "content": [
                       {"type": "tool_result", "tool_use_id": "t", "content": "x"}]}})
        self.assertNotIn("decision", self.send("Stop", stop_hook_active=False))
        rows, _ = run_json([support.PROBE_INTEGRITY],
                           {"fn": "events", "session": self.session}, env=self.envv)
        unread = [r for r in rows if r.get("kind") == "reply_unread"]
        self.assertEqual(len(unread), 1, rows)
        self.assertIn(self.transcript, unread[0]["detail"])
        self.assertFalse([r for r in rows if r.get("kind") in ("claim", "refusal")], rows)

    def test_outside_the_roots_stop_does_not_judge(self):
        proc = run([support.COMMANDCODE_HOOK],
                   {"hook_event_name": "Stop", "cwd": self.home, "session_id": "x",
                    "transcript_path": self.transcript}, env=self.envv)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertNotIn("decision", json.loads(proc.stdout or "{}"))


if __name__ == "__main__":
    unittest.main()
