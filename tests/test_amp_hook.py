"""hosts/amp/hook.py on the payloads tezgah's Amp plugin sends: the gate, the
tri-state outcome, the session brief and the Stop judgement with its marker.

The tool and field names are Amp's (ampcode.com/docs plugin-api): a shell call
is `Bash` (or `shell_command`) and may carry its text as `cmd`; the edit tools
are `edit_file`, `create_file` and `apply_patch` with `path`; a tool result
carries `status` ('done' | 'error' | 'cancelled') and an `output` whose exit code
the plugin forwards only when it is an integer `exitCode` on an object.
"""
import json
import os
import unittest

import support
from support import TempHome, run, run_json

DENIED = "git commit --no-verify -m x"
SECRET = "API = \"ghp_" + "A1b2C3d4" * 5 + "\"\n"
CLAIM = "Done. All tests pass."


class AmpHook(TempHome):
    def setUp(self):
        super().setUp()
        self.repo = self.make_repo("proj")
        self.envv = self.env()
        self.session = "T-amp-1"

    def send(self, event, **fields):
        payload = dict({"event": event, "cwd": self.repo, "session_id": self.session},
                       **fields)
        proc = run([support.AMP_HOOK], payload, env=self.envv, cwd=self.repo)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        out = proc.stdout.strip()
        return json.loads(out) if out else {}

    def rows(self):
        rows, _ = run_json([support.PROBE_INTEGRITY],
                           {"fn": "events", "session": self.session}, env=self.envv)
        return rows

    def bash(self, command, **result):
        return self.send("post_tool_use", tool="Bash", input={"cmd": command}, **result)

    def test_a_bash_call_carrying_only_cmd_is_denied(self):
        out = self.send("pre_tool_use", tool="Bash", input={"cmd": DENIED})
        self.assertIn("--no-verify", out.get("deny", ""))
        self.assertIn("deny", [r.get("kind") for r in self.rows()])

    def test_shell_command_maps_to_the_gate_shell(self):
        out = self.send("pre_tool_use", tool="shell_command", input={"command": DENIED})
        self.assertIn("--no-verify", out.get("deny", ""))

    def test_an_allowed_call_answers_nothing(self):
        self.assertEqual(self.send("pre_tool_use", tool="Bash", input={"cmd": "ls -la"}), {})

    def test_the_edit_tools_reach_the_write_rules_in_their_own_keys(self):
        for tool, inp in (("create_file", {"path": os.path.join(self.repo, "a.py"),
                                           "content": SECRET}),
                          ("edit_file", {"path": os.path.join(self.repo, "b.py"),
                                         "old_str": "x = 1\n", "new_str": SECRET})):
            self.assertTrue(self.send("pre_tool_use", tool=tool, input=inp).get("deny"), tool)

    def test_a_done_bash_result_without_an_exit_code_is_never_a_pass(self):
        self.bash("python3 -m pytest -q", status="done")
        self.assertEqual(self.send("stop", last_assistant_message=CLAIM).get("decision"),
                         "block")

    def test_an_integer_exit_code_decides_the_outcome(self):
        self.bash("python3 -m pytest -q", status="done", exit_code=0)
        self.assertEqual(self.send("stop", last_assistant_message=CLAIM), {})
        self.session = "T-amp-2"
        self.bash("python3 -m pytest -q", status="done", exit_code=1)
        self.assertEqual(self.send("stop", last_assistant_message=CLAIM).get("decision"),
                         "block")
        self.assertIn("blocked: check failed",
                      [r.get("detail") for r in self.rows() if r.get("kind") == "claim"])

    def test_an_error_or_cancelled_result_is_a_failure(self):
        for status in ("error", "cancelled"):
            self.session = "T-amp-" + status
            self.bash("python3 -m pytest -q", status=status, exit_code=0)
            self.assertEqual(self.send("stop", last_assistant_message=CLAIM)
                             .get("decision"), "block", status)

    def test_a_marked_continue_is_judged_as_the_re_ask(self):
        # the plugin sends stop_hook_active for a turn its own continue started:
        # the same claim again is recorded, not refused a second time
        claim = "Done. Implemented the parser and all tests pass."
        self.send("user_prompt", prompt="fix the parser")
        self.send("post_tool_use", tool="create_file", status="done",
                  input={"path": os.path.join(self.repo, "p.py"), "content": "x = 1\n"})
        self.bash("ls -la", status="done", exit_code=0)
        self.assertEqual(self.send("stop", last_assistant_message=claim).get("decision"),
                         "block")
        self.assertEqual(self.send("stop", last_assistant_message=claim,
                                   stop_hook_active=True), {})
        self.assertIn("after_block", [r.get("kind") for r in self.rows()])

    def test_the_session_brief_carries_the_core_only_without_the_agents_block(self):
        core = "Ponytail"
        self.assertIn(core, self.send("session_start").get("context", ""))
        agents = os.path.join(self.home, ".config", "amp", "AGENTS.md")
        os.makedirs(os.path.dirname(agents))
        with open(agents, "w") as fh:
            fh.write("<!-- tezgah:start -->\nx\n<!-- tezgah:end -->\n")
        self.assertNotIn(core, self.send("session_start").get("context", ""))
        self.assertIn(core, self.send("session_start", ignore_guidance=True)["context"])

    def test_a_subagent_thread_opens_with_its_parent(self):
        self.send("session_start", subagent=True, parent="T-parent", agent=self.session)
        spawned = [r for r in self.rows() if r.get("kind") == "spawned"]
        self.assertEqual(spawned[-1].get("parent"), "T-parent")

    def test_the_status_answer_is_plain_text(self):
        out = self.send("status")
        self.assertTrue(out.get("status"))
        self.assertNotIn("\u001b[", out["status"])

    def test_a_web_result_gets_the_untrusted_label(self):
        out = self.send("post_tool_use", tool="read_web_page",
                        input={"url": "https://example.com"}, status="done", result_len=10)
        self.assertIn("untrusted", out.get("label", ""))

    def test_outside_the_roots_stop_does_not_judge(self):
        proc = run([support.AMP_HOOK],
                   {"event": "stop", "cwd": self.home, "session_id": "x",
                    "last_assistant_message": CLAIM},
                   env=self.envv, cwd=self.home)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(proc.stdout, "")


if __name__ == "__main__":
    unittest.main()
