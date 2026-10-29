"""hosts/goose/hook.py on Goose-shaped payloads: the gate, evidence, the turn
row and the Stop judgement.

The field and tool names are Goose's own (goose docs guides/context-engineering/
hooks): the event is `event`, the directory `working_dir` on tool events only;
the developer tools are `shell` (`command`), `write` (`path`, `content`) and
`edit` (`path`, `before`, `after`); an extension's tool is `<ext>__<tool>`.
PreToolUse and Stop block with `{"decision": "block", "reason": ...}` on stdout;
PostToolUse/PostToolUseFailure carry no output, so the event is the outcome;
Stop carries `last_assistant_message` and no count of earlier blocks.
"""
import json
import os
import unittest

import support
from support import TempHome, run, run_json

DENIED = "git commit --no-verify -m x"
SECRET = "API = \"ghp_" + "A1b2C3d4" * 5 + "\"\n"
CLAIM = "Done. Implemented the parser and all tests pass."


class GooseHook(TempHome):
    def setUp(self):
        super().setUp()
        self.repo = self.make_repo("proj")
        self.envv = self.env()
        self.session = "s-goose"

    def raw(self, event, tool=True, **fields):
        payload = {"event": event, "session_id": self.session}
        if tool:
            payload["working_dir"] = self.repo
        payload.update(fields)
        # Stop and the prompt event carry no directory: the hook's cwd stands in
        proc = run([support.GOOSE_HOOK], payload, env=self.envv, cwd=self.repo)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        return proc

    def send(self, event, tool=True, **fields):
        out = self.raw(event, tool, **fields).stdout.strip()
        return json.loads(out) if out else {}

    def shell(self, command, event="PostToolUse"):
        return self.send(event, tool_name="shell", matcher_context="shell",
                         tool_call_id="c-%d" % abs(hash(command)),
                         tool_input={"command": command})

    def stop(self, reply=None):
        fields = {} if reply is None else {"last_assistant_message": reply}
        return self.send("Stop", tool=False, **fields)

    def rows(self):
        rows, _ = run_json([support.PROBE_INTEGRITY],
                           {"fn": "events", "session": self.session}, env=self.envv)
        return rows

    def test_a_gate_refused_shell_call_is_blocked_on_stdout(self):
        proc = self.raw("PreToolUse", tool_name="shell", tool_input={"command": DENIED})
        self.assertTrue(proc.stdout.startswith("{"), proc.stdout)
        out = json.loads(proc.stdout)
        self.assertEqual(out["decision"], "block")
        self.assertIn("--no-verify", out["reason"])
        self.assertIn("deny", [r.get("kind") for r in self.rows()])

    def test_an_allowed_call_prints_nothing(self):
        # exit 0 with empty stdout is Goose's clean allow
        self.assertEqual(self.raw("PreToolUse", tool_name="shell",
                                  tool_input={"command": "ls -la"}).stdout, "")

    def test_write_and_edit_reach_the_gate_in_their_own_keys(self):
        for name, inp in (("write", {"path": os.path.join(self.repo, "a.py"),
                                     "content": SECRET}),
                          ("edit", {"path": os.path.join(self.repo, "b.py"),
                                    "before": "x = 1\n", "after": SECRET})):
            out = self.send("PreToolUse", tool_name=name, tool_input=inp)
            self.assertEqual(out.get("decision"), "block", name)

    def test_an_extension_tool_maps_to_the_shared_prefix(self):
        self.send("PostToolUse", tool_name="codegraph__codegraph_explore",
                  tool_input={"query": "x"})
        details = [r.get("detail") or "" for r in self.rows() if r.get("kind") == "external"]
        self.assertTrue(any("mcp__codegraph__codegraph_explore" in d for d in details),
                        details)

    def test_both_halves_name_the_shell_call_alike(self):
        # the loop guard denies a third identical failing run only if the
        # PostToolUseFailure rows and the PreToolUse call hash to one id
        for _ in range(2):
            self.shell("pytest -q", event="PostToolUseFailure")
        self.assertEqual(self.shell("pytest -q", event="PreToolUse").get("decision"), "block")

    def test_session_start_and_the_prompt_are_observed_only(self):
        self.assertEqual(self.raw("SessionStart", tool=False).stdout, "")
        proc = self.raw("UserPromptSubmit", tool=False, message="fix the parser",
                        matcher_context="fix the parser")
        self.assertEqual(proc.stdout, "")
        self.assertIn("turn", [r.get("kind") for r in self.rows()])

    def test_an_unverified_done_claim_is_blocked_at_stop(self):
        self.shell("ls -la")
        out = self.stop(CLAIM)
        self.assertEqual(out.get("decision"), "block")
        self.assertTrue(out.get("reason"))

    def test_a_post_tool_use_check_is_a_pass(self):
        self.shell("python3 -m pytest -q")
        self.assertEqual(self.stop("Done. All tests pass."), {})

    def test_a_post_tool_use_failure_is_a_failed_check(self):
        self.shell("python3 -m pytest -q", event="PostToolUseFailure")
        self.assertEqual(self.stop("Done. All tests pass.").get("decision"), "block")
        self.assertIn("blocked: check failed",
                      [r.get("detail") for r in self.rows() if r.get("kind") == "claim"])

    def test_the_turn_rows_bound_the_reasks_with_no_host_count(self):
        # a Stop block keeps the turn going with no new prompt and no
        # stop_hook_active; the same claim again is recorded, not refused twice
        self.raw("UserPromptSubmit", tool=False, message="fix the parser")
        self.send("PostToolUse", tool_name="write",
                  tool_input={"path": os.path.join(self.repo, "p.py"), "content": "x = 1\n"})
        self.shell("ls -la")
        self.assertEqual(self.stop(CLAIM).get("decision"), "block")
        self.assertEqual(self.stop(CLAIM), {})
        self.assertIn("after_block", [r.get("kind") for r in self.rows()])

    def test_a_stop_with_no_reply_is_unread_never_judged(self):
        self.assertEqual(self.stop(), {})
        self.assertIn("reply_unread", [r.get("kind") for r in self.rows()])

    def test_outside_the_roots_stop_does_not_judge(self):
        proc = run([support.GOOSE_HOOK],
                   {"event": "Stop", "session_id": "x", "last_assistant_message": CLAIM},
                   env=self.envv, cwd=self.home)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(proc.stdout, "")


if __name__ == "__main__":
    unittest.main()
