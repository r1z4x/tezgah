"""hosts/antigravity/hook.py on Antigravity CLI-shaped payloads: the gate,
evidence, the per-turn reminder and the Stop judgement.

The field and tool names are Antigravity's own (antigravity.google/docs/hooks):
the payload is camelCase and names no event, so the hook takes it as argv[1];
`toolCall.args` uses PascalCase names (`CommandLine`, `TargetFile`,
`CodeContent`, `TargetContent`/`ReplacementContent`, `ReplacementChunks`).
PreToolUse must answer a `decision`; PostToolUse carries only an `error`
string; Stop carries `fullyIdle` and `terminationReason`, no reply text, and
`{"decision": "continue"}` sends the model back into the loop.
"""
import json
import os
import unittest

import support
from support import TempHome, run_json

DENIED = "git commit --no-verify -m x"
SECRET = "API = \"ghp_" + "A1b2C3d4" * 5 + "\"\n"
CLAIM = "Done. Implemented the parser and all tests pass."


class AntigravityHook(TempHome):
    def setUp(self):
        super().setUp()
        self.repo = self.make_repo("proj")
        self.envv = self.env()
        self.session = "s-antigravity"
        self.transcript = os.path.join(self.home, "transcript.jsonl")

    def send(self, event, **fields):
        payload = {"conversationId": self.session, "workspacePaths": [self.repo],
                   "transcriptPath": self.transcript, "modelName": "m"}
        payload.update(fields)
        out, proc = run_json([support.ANTIGRAVITY_HOOK, event], payload, env=self.envv)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        return out

    def shell(self, command, event="PostToolUse", error=None):
        fields = {"error": error} if error is not None else {}
        return self.send(event, stepIdx=1, toolCall={
            "name": "run_command",
            "args": {"CommandLine": command, "Cwd": self.repo, "WaitMsBeforeAsync": 5000}},
            **fields)

    def reply(self, text):
        with open(self.transcript, "a") as fh:
            fh.write(json.dumps({"type": "user", "message": {"content": "go"}}) + "\n")
            fh.write(json.dumps({"type": "assistant", "message": {
                "content": [{"type": "text", "text": text}]}}) + "\n")

    def stop(self, **fields):
        base = {"executionNum": 1, "terminationReason": "model_stop", "error": "",
                "fullyIdle": True}
        base.update(fields)
        return self.send("Stop", **base)

    def rows(self):
        rows, _ = run_json([support.PROBE_INTEGRITY],
                           {"fn": "events", "session": self.session}, env=self.envv)
        return rows

    def test_a_gate_refused_shell_call_is_denied_with_a_top_level_decision(self):
        out = self.shell(DENIED, event="PreToolUse")
        self.assertEqual(out["decision"], "deny")
        self.assertIn("--no-verify", out["reason"])

    def test_an_allowed_call_still_answers_the_required_decision(self):
        self.assertEqual(self.shell("ls -la", event="PreToolUse"), {"decision": "allow"})

    def test_no_event_argument_answers_nothing(self):
        out, proc = run_json([support.ANTIGRAVITY_HOOK],
                             {"conversationId": self.session, "workspacePaths": [self.repo],
                              "toolCall": {"name": "run_command",
                                           "args": {"CommandLine": DENIED}}},
                             env=self.envv)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIsNone(out)

    def test_the_file_tools_reach_the_gate_through_their_pascal_case_args(self):
        target = os.path.join(self.repo, "a.py")
        for name, args in (
                ("write_to_file", {"TargetFile": target, "CodeContent": SECRET,
                                   "Overwrite": True}),
                ("replace_file_content", {"TargetFile": target, "TargetContent": "x = 1\n",
                                          "ReplacementContent": SECRET}),
                ("multi_replace_file_content", {"TargetFile": target, "ReplacementChunks": [
                    {"TargetContent": "x = 1\n", "ReplacementContent": SECRET}]})):
            out = self.send("PreToolUse", toolCall={"name": name, "args": args})
            self.assertEqual(out.get("decision"), "deny", name)

    def test_both_halves_name_the_shell_call_alike(self):
        # the loop guard denies a third identical failing run only if the
        # PostToolUse rows and the PreToolUse call hash to one id
        for _ in range(2):
            self.shell("pytest -q", error="exit status 1")
        self.assertEqual(self.shell("pytest -q", event="PreToolUse")["decision"], "deny")

    def test_session_start_injects_the_core_until_gemini_md_does(self):
        out = self.send("SessionStart")
        step, = out["injectSteps"]
        self.assertIn("**Turkish, BLUF.**", step["systemMessage"]["systemMessage"])
        rules = os.path.join(self.home, ".gemini", "GEMINI.md")
        os.makedirs(os.path.dirname(rules))
        with open(rules, "w") as fh:
            fh.write("<!-- tezgah:start --> (managed)\ncore\n<!-- tezgah:end -->\n")
        out = self.send("SessionStart")
        text = json.dumps(out)
        self.assertNotIn("**Turkish, BLUF.**", text)

    def test_the_first_invocation_writes_the_turn_row_and_the_reminder(self):
        out = self.send("PreInvocation", invocationNum=0, initialNumSteps=1)
        step, = out["injectSteps"]
        self.assertTrue(step["ephemeralMessage"])
        self.assertIn("turn", [r.get("kind") for r in self.rows()])
        self.assertEqual(self.send("PreInvocation", invocationNum=3, initialNumSteps=9), {})

    def test_an_unverified_done_claim_continues_the_loop(self):
        self.send("PreInvocation", invocationNum=0)
        self.send("PostToolUse", toolCall={"name": "write_to_file", "args": {
            "TargetFile": os.path.join(self.repo, "p.py"), "CodeContent": "x = 1\n"}},
            error="")
        self.shell("ls -la", error="")
        self.reply(CLAIM)
        out = self.stop()
        self.assertEqual(out.get("decision"), "continue")
        self.assertTrue(out.get("reason"))

    def test_a_stop_that_is_not_an_idle_model_stop_is_not_judged(self):
        self.send("PreInvocation", invocationNum=0)
        self.reply(CLAIM)
        for fields in ({"fullyIdle": False}, {"terminationReason": "max_steps_exceeded"}):
            self.assertEqual(self.stop(**fields), {"decision": "allow"}, fields)
        self.assertNotIn("claim", [r.get("kind") for r in self.rows()])

    def test_no_reply_in_the_transcript_is_a_reply_unread_row(self):
        self.assertEqual(self.stop(), {"decision": "allow"})
        self.assertIn("reply_unread", [r.get("kind") for r in self.rows()])

    def test_an_empty_error_on_a_shell_call_is_never_a_pass(self):
        # a command handed to the background also ends with an empty error
        self.send("PreInvocation", invocationNum=0)
        self.send("PostToolUse", toolCall={"name": "write_to_file", "args": {
            "TargetFile": os.path.join(self.repo, "p.py"), "CodeContent": "x = 1\n"}},
            error="")
        self.shell("python3 -m pytest -q", error="")
        kinds = [r.get("kind") for r in self.rows()]
        self.assertIn("verify", kinds)
        self.assertNotIn("verify_ok", kinds)
        self.reply("Done. All tests pass.")
        self.assertEqual(self.stop().get("decision"), "continue")

    def test_an_error_is_a_failed_check(self):
        self.send("PreInvocation", invocationNum=0)
        self.shell("python3 -m pytest -q", error="exit status 1")
        self.reply("Done. All tests pass.")
        self.assertEqual(self.stop().get("decision"), "continue")
        self.assertIn("blocked: check failed",
                      [r.get("detail") for r in self.rows() if r.get("kind") == "claim"])

    def test_the_re_entered_loop_does_not_open_a_new_turn_for_the_budget(self):
        # `continue` re-enters the loop; if that invocation restarts at 0 it
        # must not reset the refusal budget, so the same claim is recorded, not
        # refused a second time for one class
        self.send("PreInvocation", invocationNum=0)
        self.send("PostToolUse", toolCall={"name": "write_to_file", "args": {
            "TargetFile": os.path.join(self.repo, "p.py"), "CodeContent": "x = 1\n"}},
            error="")
        self.shell("ls -la", error="")
        self.reply(CLAIM)
        self.assertEqual(self.stop().get("decision"), "continue")
        turns = [r for r in self.rows() if r.get("kind") == "turn"]
        self.assertEqual(self.send("PreInvocation", invocationNum=0), {})
        self.assertEqual([r for r in self.rows() if r.get("kind") == "turn"], turns)
        self.reply(CLAIM)
        self.assertEqual(self.stop(executionNum=2), {"decision": "allow"})
        self.assertIn("after_block", [r.get("kind") for r in self.rows()])

    def test_outside_the_roots_stop_does_not_judge(self):
        self.reply(CLAIM)
        out, proc = run_json([support.ANTIGRAVITY_HOOK, "Stop"],
                             {"conversationId": "x", "workspacePaths": [self.home],
                              "transcriptPath": self.transcript, "fullyIdle": True,
                              "terminationReason": "model_stop"}, env=self.envv)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(out, {"decision": "allow"})


if __name__ == "__main__":
    unittest.main()
