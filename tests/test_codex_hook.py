"""hosts/codex/hook.py: SessionStart context, the gate, evidence and Stop."""
import os
import unittest

import support
from support import TempHome, run, run_json


class CodexHook(TempHome):
    def test_session_start_emits_additional_context(self):
        repo = self.make_repo()
        out, proc = run_json([support.CODEX_HOOK],
                             {"hook_event_name": "SessionStart", "cwd": repo,
                              "session_id": "s"}, env=self.env())
        self.assertEqual(proc.returncode, 0, proc.stderr)
        hso = out["hookSpecificOutput"]
        self.assertEqual(hso["hookEventName"], "SessionStart")
        self.assertTrue(hso["additionalContext"].strip())

    def test_stop_emits_system_message(self):
        repo = self.make_repo()
        out, proc = run_json([support.CODEX_HOOK],
                             {"hook_event_name": "Stop", "cwd": repo,
                              "session_id": "s"}, env=self.env())
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("systemMessage", out)
        self.assertIn("tezgah", out["systemMessage"])

    def test_outside_roots_reports_status_without_context(self):
        # The status segment is a global indicator (tezgah loads globally where
        # it ships as an instructions file), so it prints off-root too; the
        # rule context itself stays root-scoped and is absent.
        out, proc = run_json([support.CODEX_HOOK],
                             {"hook_event_name": "SessionStart", "cwd": self.home},
                             env=self.env())
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("tezgah", out["systemMessage"])
        self.assertNotIn("hookSpecificOutput", out)

    def test_post_tool_use_records_and_prints_nothing(self):
        repo = self.make_repo()
        proc = run([support.CODEX_HOOK],
                   {"hook_event_name": "PostToolUse", "cwd": repo,
                    "session_id": "s", "tool_name": "Task", "tool_input": {}},
                   env=self.env())
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(proc.stdout.strip(), "")


class CodexEvidence(TempHome):
    """The ledger the Stop gate reads: Codex fires PostToolUse for a failed
    command too, so the exit code in tool_response decides pass from fail."""

    def setUp(self):
        super().setUp()
        self.repo = self.make_repo("proj")
        self.envv = self.env()
        self.session = "s-codex"

    def post(self, tool, inp, response=None):
        payload = {"hook_event_name": "PostToolUse", "cwd": self.repo,
                   "session_id": self.session, "tool_name": tool,
                   "tool_input": inp}
        if response is not None:
            payload["tool_response"] = response
        proc = run([support.CODEX_HOOK], payload, env=self.envv)
        self.assertEqual(proc.returncode, 0, proc.stderr)

    def kinds(self):
        out, _ = run_json([support.PROBE_INTEGRITY],
                          {"fn": "kinds", "session": self.session},
                          env=self.envv)
        return out

    def test_passing_check_records_verify_ok(self):
        self.post("exec_command", {"command": "pytest -q"},
                  {"exit_code": 0, "output": "5 passed"})
        self.assertEqual(self.kinds(), ["verify_ok"])

    def test_failing_check_records_verify_fail(self):
        self.post("exec_command", {"command": "pytest -q"},
                  {"exit_code": 1, "output": "1 failed"})
        self.assertEqual(self.kinds(), ["verify_fail"])

    def test_check_without_an_exit_code_is_not_a_pass(self):
        self.post("exec_command", {"command": "pytest -q"})
        self.assertEqual(self.kinds(), ["verify"])

    def test_non_check_command_records_run(self):
        self.post("exec_command", {"command": "ls -la"}, {"exit_code": 0})
        self.assertEqual(self.kinds(), ["run"])


class CodexLoopGuardIdentity(TempHome):
    """One call, one id: the gate maps Codex's shell name (`exec_command`) onto
    the gate's `Bash`, and `call_id` hashes the name it is handed. While the
    PostToolUse row kept the raw name the two halves hashed differently, so the
    loop guard read a history that never matched the call it was gating and
    never denied. The deny below only happens if both halves name the call the
    same way."""

    def setUp(self):
        super().setUp()
        self.repo = self.make_repo("proj")
        self.envv = self.env()
        self.session = "s-loop"

    def failed_attempt(self):
        proc = run([support.CODEX_HOOK],
                   {"hook_event_name": "PostToolUse", "cwd": self.repo,
                    "session_id": self.session, "tool_name": "exec_command",
                    "tool_input": {"command": "pytest -q"},
                    "tool_response": {"exit_code": 1, "output": "1 failed"}},
                   env=self.envv)
        self.assertEqual(proc.returncode, 0, proc.stderr)

    def test_the_gate_counts_the_failures_the_row_recorded(self):
        self.failed_attempt()
        self.failed_attempt()
        out, proc = run_json([support.CODEX_HOOK], {
            "hook_event_name": "PreToolUse", "cwd": self.repo,
            "session_id": self.session, "tool_name": "exec_command",
            "tool_input": {"command": "pytest -q"}}, env=self.envv)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        hso = out["hookSpecificOutput"]
        self.assertEqual(hso["permissionDecision"], "deny")
        self.assertTrue(hso["permissionDecisionReason"])


class CodexHookThroughTheInstalledLink(TempHome):
    """tezgah-setup wires codex to ~/.config/tezgah/bin/tezgah-codex-hook, a
    symlink. The hook derived ROOT from the unresolved link path, so every event
    died with an ImportError and the gate silently never ran."""

    def test_events_run_through_the_symlink(self):
        repo = self.make_repo()
        env = self.env()
        env.pop("PYTHONPATH", None)  # the host's own environment carries none
        link = support.linked(support.CODEX_HOOK, self.home)
        out, proc = run_json([link], {
            "hook_event_name": "PreToolUse", "cwd": repo, "session_id": "s",
            "tool_name": "exec_command",
            "tool_input": {"command": "git commit --no-verify -m x"}}, env=env)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(
            out["hookSpecificOutput"]["permissionDecision"], "deny")


class CodexStopGate(TempHome):
    """Codex's stop.output accepts {"decision": "block", "reason": ...} and its
    stop.input carries the assistant's last message, so the unverified-done rule
    runs here exactly as it does under Claude."""

    def setUp(self):
        super().setUp()
        self.repo = self.make_repo("proj")
        self.envv = self.env()
        self.session = "s-stop"

    def post(self, tool, inp, response=None):
        payload = {"hook_event_name": "PostToolUse", "cwd": self.repo,
                   "session_id": self.session, "tool_name": tool,
                   "tool_input": inp}
        if response is not None:
            payload["tool_response"] = response
        proc = run([support.CODEX_HOOK], payload, env=self.envv)
        self.assertEqual(proc.returncode, 0, proc.stderr)

    def worked(self):
        self.post("exec_command", {"command": "ls -la"}, {"exit_code": 0})

    def stop(self, text, cwd=None, **extra):
        payload = {"hook_event_name": "Stop", "cwd": cwd or self.repo,
                   "session_id": self.session, "last_assistant_message": text}
        payload.update(extra)
        out, proc = run_json([support.CODEX_HOOK], payload, env=self.envv)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        return out or {}

    def test_unverified_done_claim_blocks(self):
        self.worked()
        out = self.stop("Done. Implemented the parser and all tests pass.")
        self.assertEqual(out.get("decision"), "block")
        self.assertTrue(out.get("reason"))

    def test_verified_done_claim_passes(self):
        self.post("apply_patch", {"file_path": self.repo + "/x.py"})
        self.post("exec_command", {"command": "pytest -q"}, {"exit_code": 0})
        self.assertNotIn("decision", self.stop("Done. All tests pass."))

    def test_failed_check_blocks(self):
        self.post("exec_command", {"command": "pytest -q"}, {"exit_code": 1})
        self.assertEqual(self.stop("Done. Tests pass.").get("decision"), "block")

    def test_explicit_unverified_admission_passes(self):
        self.worked()
        self.assertNotIn("decision", self.stop("Yaptım ama doğrulanmadı."))

    def test_stop_hook_active_passes(self):
        self.worked()
        self.assertNotIn("decision", self.stop("Done.", stop_hook_active=True))

    def test_verify_off_kill_switch(self):
        self.touch(os.path.join(self.home, ".config", "tezgah", "verify-off"))
        self.worked()
        self.assertNotIn("decision", self.stop("Done. All tests pass."))

    def test_outside_root_passes(self):
        self.worked()
        self.assertNotIn("decision", self.stop("Done.", cwd=self.home))


if __name__ == "__main__":
    unittest.main()
