"""hosts/omp/hook.py: the omp lifecycle envelope over the shared core.

omp's extension API is TypeScript, so the python half takes one JSON payload and
answers with one JSON object (hosts/omp/hook.py's docstring is the protocol).
These tests drive that protocol directly: they are the only host-level check
that omp's session context, gate, evidence ledger and Stop rule behave.
"""
import os
import unittest

import support
from support import TempHome, run, run_json


class OmpHook(TempHome):
    def event(self, payload):
        return run_json([support.OMP_HOOK], payload, env=self.env())

    def test_session_start_carries_repo_state_without_the_core(self):
        repo = self.make_repo()
        out, proc = self.event({"event": "session_start", "cwd": repo,
                                "session_id": "s"})
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("Graph", out["context"])
        # omp's managed RULES.md already carries the always-on core, so the
        # session payload must not pay for the contract a second time
        self.assertNotIn("**Turkish, BLUF.**", out["context"])
        self.assertIn("pony", out["status"])

    def test_status_answers_off_root(self):
        # the status line is the one global signal: tezgah loads as a globally
        # loaded rules file on omp, so the marks must not go silent off-root
        out, proc = self.event({"event": "status", "cwd": self.home})
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("pony", out["status"])

    def test_session_context_is_inert_off_root(self):
        out, proc = self.event({"event": "session_start", "cwd": self.home})
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIsNone(out)  # an empty answer, not an empty object

    def test_user_prompt_carries_the_reminder_and_arms_by_task_class(self):
        repo = self.make_repo()
        out, proc = self.event({"event": "user_prompt", "cwd": repo,
                                "session_id": "s",
                                "prompt": "who calls calc_total?"})
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("<harness-reminder>", out["context"])
        # the matching conditional paragraph rides only this turn
        self.assertIn("**Code discovery: graph first.**", out["context"])
        other, _ = self.event({"event": "user_prompt", "cwd": repo,
                               "session_id": "s", "prompt": "add a flag"})
        self.assertNotIn("**Code discovery: graph first.**", other["context"])

    def test_pre_tool_use_denies_the_attribution_credit(self):
        repo = self.make_repo()
        out, _ = self.event({
            "event": "pre_tool_use", "cwd": repo, "session_id": "s",
            "tool": "bash",
            "input": {"command": 'git commit -m "x\n\nCo-Authored-By: Claude"'}})
        self.assertIn("attribution", out["deny"].lower())

    def test_pre_tool_use_denies_the_grep_only_explorer(self):
        repo = self.make_repo()
        out, _ = self.event({"event": "pre_tool_use", "cwd": repo,
                             "session_id": "s", "tool": "task",
                             "input": {"subagent_type": "explore"}})
        self.assertTrue(out["deny"].strip())

    def test_pre_tool_use_passes_an_ordinary_call(self):
        repo = self.make_repo()
        out, proc = self.event({"event": "pre_tool_use", "cwd": repo,
                                "session_id": "s", "tool": "read",
                                "input": {"path": "README.md"}})
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIsNone(out)  # an empty answer, not an empty object

    def test_post_tool_use_records_evidence_and_marks_the_used_kind(self):
        repo = self.make_repo()
        self.event({"event": "post_tool_use", "cwd": repo, "session_id": "s",
                    "tool": "task", "input": {"prompt": "x"}})
        ledger = os.path.join(self.home, ".cache", "tezgah", "sessions")
        files = os.listdir(ledger)
        self.assertEqual(len(files), 1, files)
        with open(os.path.join(ledger, files[0])) as fh:
            self.assertIn("orch", fh.read())

    def test_stop_blocks_a_done_claim_no_check_backs(self):
        repo = self.make_repo()
        # a check whose outcome omp never reported is recorded as one that ran,
        # never as one that passed - so it cannot license a "done"
        self.event({"event": "post_tool_use", "cwd": repo, "session_id": "s",
                    "tool": "bash", "input": {"command": "pytest -q"}})
        out, proc = self.event({"event": "stop", "cwd": repo,
                                "session_id": "s",
                                "last_assistant_message": "Done."})
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(out.get("decision"), "block")
        self.assertIn("doğrulanmadı", out["reason"])

    def test_stop_clears_when_the_check_actually_passed(self):
        repo = self.make_repo()
        self.event({"event": "post_tool_use", "cwd": repo, "session_id": "s",
                    "tool": "bash", "input": {"command": "pytest -q"},
                    "failed": False})
        out, _ = self.event({"event": "stop", "cwd": repo, "session_id": "s",
                             "last_assistant_message": "Done."})
        self.assertIsNone(out)

    def test_stop_clears_on_an_honest_unverified_claim(self):
        repo = self.make_repo()
        self.event({"event": "post_tool_use", "cwd": repo, "session_id": "s",
                    "tool": "bash", "input": {"command": "pytest -q"}})
        out, _ = self.event({"event": "stop", "cwd": repo, "session_id": "s",
                             "last_assistant_message": "Fixed; doğrulanmadı."})
        self.assertIsNone(out)

    def test_stop_hook_active_short_circuits(self):
        repo = self.make_repo()
        self.event({"event": "post_tool_use", "cwd": repo, "session_id": "s",
                    "tool": "bash", "input": {"command": "pytest -q"}})
        out, _ = self.event({"event": "stop", "cwd": repo, "session_id": "s",
                             "last_assistant_message": "Done.",
                             "stop_hook_active": True})
        self.assertIsNone(out)

    def test_unknown_event_and_broken_stdin_are_silent(self):
        proc = run([support.OMP_HOOK], {"event": "who-knows",
                                        "cwd": self.make_repo()},
                   env=self.env())
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(proc.stdout.strip(), "")
        broken = run([support.OMP_HOOK], None, env=self.env())
        self.assertEqual(broken.returncode, 0, broken.stderr)
        self.assertEqual(broken.stdout.strip(), "")


class OmpHookThroughTheInstalledPath(TempHome):
    """tezgah-setup substitutes the hook's absolute path into the extension and
    omp runs it with the user's own environment: no PYTHONPATH of its own."""

    def test_events_run_without_pythonpath(self):
        repo = self.make_repo()
        env = self.env()
        env.pop("PYTHONPATH", None)
        out, proc = run_json([support.OMP_HOOK],
                             {"event": "pre_tool_use", "cwd": repo,
                              "tool": "bash",
                              "input": {"command": 'git commit -m '
                                                   '"Co-Authored-By: x"'}},
                             env=env)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("deny", out)
        status, _ = run_json([support.OMP_HOOK],
                             {"event": "status", "cwd": repo}, env=env)
        self.assertIn("pony", status["status"])


if __name__ == "__main__":
    unittest.main()
