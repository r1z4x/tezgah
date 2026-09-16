"""hosts/cursor/hook.py: event translation and the shared gate."""
import os
import unittest

import support
from support import TempHome, run_json


class CursorHook(TempHome):
    def setUp(self):
        super().setUp()
        self.repo = self.make_repo("proj")
        self.envv = self.env()

    def call(self, payload):
        out, proc = run_json([support.CURSOR_HOOK], payload, env=self.envv)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        return out

    def test_session_start_returns_additional_context(self):
        out = self.call({"hook_event_name": "sessionStart", "cwd": self.repo,
                         "conversation_id": "s"})
        self.assertTrue(out["additional_context"].strip())

    def test_session_start_outside_roots_is_empty(self):
        out = self.call({"hook_event_name": "sessionStart", "cwd": self.home,
                         "conversation_id": "s"})
        self.assertEqual(out, {})

    def test_pre_tool_use_denies_attribution(self):
        out = self.call({"hook_event_name": "preToolUse", "tool_name": "Shell",
                         "tool_input": {"command":
                                        'git commit -m "x Co-Authored-By: Claude"'},
                         "cwd": self.repo, "conversation_id": "s"})
        self.assertEqual(out["permission"], "deny")
        self.assertTrue(out["agent_message"])

    def test_pre_tool_use_denies_explore(self):
        out = self.call({"hook_event_name": "preToolUse", "tool_name": "Task",
                         "tool_input": {"subagent_type": "Explore"},
                         "cwd": self.repo, "conversation_id": "s"})
        self.assertEqual(out["permission"], "deny")

    def test_pre_tool_use_allows_plain_commit(self):
        out = self.call({"hook_event_name": "preToolUse", "tool_name": "Shell",
                         "tool_input": {"command": 'git commit -m "plain"'},
                         "cwd": self.repo, "conversation_id": "s"})
        self.assertEqual(out, {"permission": "allow"})

    def test_before_submit_prompt_injects_the_reminder(self):
        out = self.call({"hook_event_name": "beforeSubmitPrompt", "cwd": self.repo})
        self.assertTrue(out["continue"])
        self.assertIn("harness-reminder", out["additional_context"])

    def test_before_submit_prompt_respects_reminder_off(self):
        self.touch(os.path.join(self.home, ".config", "tezgah", "reminder-off"))
        out = self.call({"hook_event_name": "beforeSubmitPrompt", "cwd": self.repo})
        self.assertEqual(out, {"continue": True})

    # ---- the Stop rule (reply from afterAgentResponse, decision at stop) ---
    def response(self, text):
        return self.call({"hook_event_name": "afterAgentResponse", "cwd": self.repo,
                          "conversation_id": "s", "text": text})

    def stop(self, **extra):
        payload = {"hook_event_name": "stop", "cwd": self.repo,
                   "conversation_id": "s", "status": "completed"}
        payload.update(extra)
        return self.call(payload)

    def test_stop_blocks_a_done_claim_no_check_backs(self):
        self.call({"hook_event_name": "postToolUse", "cwd": self.repo,
                   "conversation_id": "s", "tool_name": "Shell",
                   "tool_input": {"command": "ls"}})
        self.response("Done. All tests pass.")
        out = self.stop()
        self.assertEqual(out.get("decision"), "block")
        self.assertTrue(out["reason"])

    def test_stop_passes_a_verified_done_claim(self):
        self.call({"hook_event_name": "postToolUse", "cwd": self.repo,
                   "conversation_id": "s", "tool_name": "Shell",
                   "tool_input": {"command": "pytest -q"}})
        self.response("Done. All tests pass.")
        self.assertEqual(self.stop(), {})

    def test_stop_passes_a_claim_free_answer(self):
        self.response("Toplam 5 dosya incelendi.")
        self.assertEqual(self.stop(), {})

    def test_stop_ignores_an_aborted_turn(self):
        self.response("Done. All tests pass.")
        self.assertEqual(self.stop(status="aborted"), {})

    def test_stop_is_inert_outside_the_roots(self):
        self.call({"hook_event_name": "afterAgentResponse", "cwd": self.home,
                   "conversation_id": "s2", "text": "Done. All tests pass."})
        self.assertEqual(self.stop(cwd=self.home, conversation_id="s2"), {})


class CursorHookThroughTheInstalledLink(TempHome):
    """tezgah-setup wires cursor to ~/.config/tezgah/bin/tezgah-cursor-hook, a
    symlink; the hook must find the repo from the link path."""

    def test_events_run_through_the_symlink(self):
        repo = self.make_repo()
        env = self.env()
        env.pop("PYTHONPATH", None)  # the host's own environment carries none
        link = support.linked(support.CURSOR_HOOK, self.home)
        out, proc = run_json([link], {
            "hook_event_name": "preToolUse", "cwd": repo,
            "conversation_id": "s", "tool_name": "Shell",
            "tool_input": {"command": "pytest -q || true"}}, env=env)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(out["permission"], "deny")


if __name__ == "__main__":
    unittest.main()
