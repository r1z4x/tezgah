"""hooks/tezgah_context.py: context_for scope and health_lines format."""
import os
import unittest

import support
from support import TempHome, run_json


class ContextFor(TempHome):
    def call(self, payload, env=None):
        return run_json([support.PROBE_CONTEXT], payload, env=env or self.env())

    def test_outside_roots_returns_none(self):
        out, proc = self.call({"fn": "context_for", "event": "session_start",
                               "cwd": self.home})
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIsNone(out)

    def test_inside_roots_returns_context(self):
        repo = self.make_repo()
        out, proc = self.call({"fn": "context_for", "event": "session_start",
                               "cwd": repo})
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIsInstance(out, str)
        self.assertIn("Code discovery", out)

    def test_user_prompt_reminder_and_kill_switch(self):
        repo = self.make_repo()
        out, _ = self.call({"fn": "context_for", "event": "user_prompt", "cwd": repo})
        self.assertIn("harness-reminder", out)
        self.touch(os.path.join(self.home, ".config", "tezgah", "reminder-off"))
        out2, _ = self.call({"fn": "context_for", "event": "user_prompt", "cwd": repo})
        self.assertIsNone(out2)


class HealthLines(TempHome):
    def armed_key(self):
        self.touch(os.path.join(self.home, ".config", "openrouter", "key"))

    def test_outside_roots_still_shows_checklist(self):
        # Global indicator: the checklist prints off-root too, so the opencode
        # TUI does not go silent when the session cwd is outside ~/Projects.
        out, proc = run_json([support.PROBE_CONTEXT],
                             {"fn": "health_lines", "cwd": self.home},
                             env=self.env())
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(out, "pony\u2713 exec\u2713  \u00b7  "
                              "consult\u2717 cbm\u25cb orch\u25cb")

    def test_armed_but_unused_checklist(self):
        repo = self.make_repo()
        self.armed_key()
        out, _ = run_json([support.PROBE_CONTEXT],
                          {"fn": "health_lines", "cwd": repo, "session_id": "s"},
                          env=self.env())
        self.assertEqual(out, "pony\u2713 exec\u2713  \u00b7  "
                              "consult\u25cb cbm\u25cb orch\u25cb")

    def test_used_kind_flips_a_mark(self):
        repo = self.make_repo()
        self.armed_key()
        _, proc = run_json([support.PROBE_CONTEXT],
                           {"fn": "record", "session_id": "s", "kind": "cbm"},
                           env=self.env())
        self.assertEqual(proc.returncode, 0, proc.stderr)
        out, _ = run_json([support.PROBE_CONTEXT],
                          {"fn": "health_lines", "cwd": repo, "session_id": "s"},
                          env=self.env())
        self.assertIn("cbm\u2713", out)

    def test_repo_no_cbm_mark(self):
        repo = self.make_repo()
        self.armed_key()
        self.touch(os.path.join(repo, ".no-cbm"))
        out, _ = run_json([support.PROBE_CONTEXT],
                          {"fn": "health_lines", "cwd": repo, "session_id": "s"},
                          env=self.env())
        self.assertIn("cbm\u2717", out)


if __name__ == "__main__":
    unittest.main()
