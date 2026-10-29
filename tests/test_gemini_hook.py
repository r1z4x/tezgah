"""hosts/gemini/hook.py on Gemini CLI-shaped payloads: the gate, evidence, the
per-turn reminder and the AfterAgent judgement.

The field and tool names are Gemini's own (geminicli hooks reference, tools
reference): BeforeTool denies with a top-level `{"decision": "deny"}`,
AfterTool's `tool_response` holds `llmContent` and an optional `error`, the
shell tool writes `Output: ...` and `Exit Code: N` only for a non-zero code
(packages/core/src/tools/shell.ts), and AfterAgent carries `prompt_response` and
`stop_hook_active`.
"""
import json
import os
import unittest

import support
from support import TempHome, run, run_json

DENIED = "git commit --no-verify -m x"
SECRET = "API = \"ghp_" + "A1b2C3d4" * 5 + "\"\n"


def shell_result(output, code=0):
    text = "Output: %s" % output + ("\nExit Code: %d" % code if code else "")
    return {"llmContent": "<untrusted_context>\n%s\n</untrusted_context>" % text,
            "returnDisplay": text}


class GeminiHook(TempHome):
    def setUp(self):
        super().setUp()
        self.repo = self.make_repo("proj")
        self.envv = self.env()
        self.session = "s-gemini"

    def send(self, event, **fields):
        payload = {"hook_event_name": event, "cwd": self.repo,
                   "session_id": self.session, "timestamp": "2026-10-29T00:00:00Z",
                   "transcript_path": os.path.join(self.home, "t.json")}
        payload.update(fields)
        out, proc = run_json([support.GEMINI_HOOK], payload, env=self.envv)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        return out or {}

    def shell(self, command, event="AfterTool", resp=None):
        fields = {"tool_response": resp} if resp is not None else {}
        return self.send(event, tool_name="run_shell_command",
                         tool_input={"command": command}, **fields)

    def rows(self):
        rows, _ = run_json([support.PROBE_INTEGRITY],
                           {"fn": "events", "session": self.session}, env=self.envv)
        return rows

    def test_a_gate_refused_shell_call_is_denied_with_a_top_level_decision(self):
        out = self.shell(DENIED, event="BeforeTool")
        self.assertEqual(out["decision"], "deny")
        self.assertIn("--no-verify", out["reason"])
        self.assertNotIn("hookSpecificOutput", out)

    def test_an_allowed_call_answers_nothing(self):
        self.assertEqual(self.shell("ls -la", event="BeforeTool"), {})

    def test_write_and_replace_reach_the_gate(self):
        for name, inp in (("write_file", {"file_path": os.path.join(self.repo, "a.py"),
                                          "content": SECRET}),
                          ("replace", {"file_path": os.path.join(self.repo, "b.py"),
                                       "old_string": "x = 1\n", "new_string": SECRET})):
            out = self.send("BeforeTool", tool_name=name, tool_input=inp)
            self.assertEqual(out.get("decision"), "deny", name)

    def test_an_mcp_tool_maps_to_the_shared_prefix(self):
        self.send("AfterTool", tool_name="mcp_codegraph_codegraph_explore",
                  tool_input={"query": "x"}, tool_response={"llmContent": "ok"})
        details = [r.get("detail") or "" for r in self.rows() if r.get("kind") == "external"]
        self.assertTrue(any("mcp__codegraph_codegraph_explore" in d for d in details),
                        details)

    def test_both_halves_name_the_shell_call_alike(self):
        # the loop guard denies a third identical failing run only if the
        # AfterTool rows and the BeforeTool call hash to one id
        for _ in range(2):
            self.shell("pytest -q", resp=shell_result("1 failed", 1))
        self.assertEqual(self.shell("pytest -q", event="BeforeTool").get("decision"), "deny")

    def test_session_start_carries_the_core_until_gemini_md_does(self):
        out = self.send("SessionStart", source="startup")
        self.assertIn("**Turkish, BLUF.**", out["hookSpecificOutput"]["additionalContext"])
        rules = os.path.join(self.home, ".gemini", "GEMINI.md")
        os.makedirs(os.path.dirname(rules))
        with open(rules, "w") as fh:
            fh.write("<!-- tezgah:start --> (managed)\ncore\n<!-- tezgah:end -->\n")
        out = self.send("SessionStart", source="startup")
        ctx = (out.get("hookSpecificOutput") or {}).get("additionalContext", "")
        self.assertNotIn("**Turkish, BLUF.**", ctx)

    def test_before_agent_writes_the_turn_row_and_carries_the_reminder(self):
        out = self.send("BeforeAgent", prompt="fix the parser")
        self.assertEqual(out["hookSpecificOutput"]["hookEventName"], "BeforeAgent")
        self.assertTrue(out["hookSpecificOutput"]["additionalContext"])
        self.assertIn("turn", [r.get("kind") for r in self.rows()])

    def test_an_unverified_done_claim_is_denied_at_after_agent(self):
        self.shell("ls -la", resp=shell_result("x"))
        out = self.send("AfterAgent", prompt="fix it", stop_hook_active=False,
                        prompt_response="Done. Implemented the parser and all tests pass.")
        self.assertEqual(out.get("decision"), "deny")
        self.assertTrue(out.get("reason"))

    def test_a_shell_run_with_no_exit_code_line_is_a_pass(self):
        # Gemini writes `Exit Code:` only for a non-zero code
        self.shell("python3 -m pytest -q", resp=shell_result("3 passed"))
        out = self.send("AfterAgent", stop_hook_active=False,
                        prompt_response="Done. All tests pass.")
        self.assertNotIn("decision", out)

    def test_a_non_zero_exit_code_is_a_failed_check(self):
        self.shell("python3 -m pytest -q", resp=shell_result("1 failed", 1))
        out = self.send("AfterAgent", stop_hook_active=False,
                        prompt_response="Done. All tests pass.")
        self.assertEqual(out.get("decision"), "deny")
        self.assertIn("blocked: check failed",
                      [r.get("detail") for r in self.rows() if r.get("kind") == "claim"])

    def test_a_runner_killed_by_a_signal_is_a_failed_check(self):
        # shell.ts writes `Signal: NAME` and no `Exit Code:` for a killed process
        text = "Output: 2 passed\nSignal: SIGKILL"
        self.shell("python3 -m pytest -q", resp={
            "llmContent": "<untrusted_context>\n%s\n</untrusted_context>" % text,
            "returnDisplay": text})
        out = self.send("AfterAgent", stop_hook_active=False,
                        prompt_response="Done. All tests pass.")
        self.assertEqual(out.get("decision"), "deny")
        self.assertIn("blocked: check failed",
                      [r.get("detail") for r in self.rows() if r.get("kind") == "claim"])

    def test_the_retry_prompt_does_not_open_a_new_turn_for_the_budget(self):
        # a deny's reason comes back through BeforeAgent as the next prompt
        # (client.ts sendMessageStream continuation); the same claim again is
        # recorded, not refused a second time for one class
        self.send("BeforeAgent", prompt="fix the parser")
        self.send("AfterTool", tool_name="write_file",
                  tool_input={"file_path": os.path.join(self.repo, "p.py"), "content": "x = 1\n"},
                  tool_response={"llmContent": "ok"})
        self.shell("ls -la", resp=shell_result("x"))
        claim = "Done. Implemented the parser and all tests pass."
        first = self.send("AfterAgent", stop_hook_active=False, prompt_response=claim)
        self.assertEqual(first.get("decision"), "deny")
        self.send("BeforeAgent", prompt=first["reason"])
        again = self.send("AfterAgent", stop_hook_active=True, prompt_response=claim)
        self.assertNotIn("decision", again)
        self.assertIn("after_block", [r.get("kind") for r in self.rows()])

    def test_an_error_or_a_background_run_is_never_a_pass(self):
        self.shell("python3 -m pytest -q",
                   resp={"llmContent": "boom", "error": {"message": "boom"}})
        self.shell("python3 -m pytest -q",
                   resp={"llmContent": "Command moved to background (PID: 1)."})
        out = self.send("AfterAgent", stop_hook_active=False,
                        prompt_response="Done. All tests pass.")
        self.assertEqual(out.get("decision"), "deny")

    def test_outside_the_roots_after_agent_does_not_judge(self):
        proc = run([support.GEMINI_HOOK],
                   {"hook_event_name": "AfterAgent", "cwd": self.home, "session_id": "x",
                    "prompt_response": "Done. All tests pass."}, env=self.envv)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertNotIn("decision", json.loads(proc.stdout or "{}"))


if __name__ == "__main__":
    unittest.main()
