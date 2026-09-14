"""hooks/tezgah_context.py: context_for scope and health_lines format."""
import os
import subprocess
import sys
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
                              "consult\u25cb cbm\u25cb orch\u25cb  \u00b7  idx\u2013")

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

    def test_open_plans_segment(self):
        repo = self.make_repo()
        self.armed_key()
        self.touch(os.path.join(repo, "plans", "open", "001-a.md"))
        self.touch(os.path.join(repo, "plans", "open", "002-b.md"))
        with open(os.path.join(repo, "plans", "open", "001-a.md"), "w") as fh:
            fh.write("status: blocked\n")
        out, _ = run_json([support.PROBE_CONTEXT],
                          {"fn": "health_lines", "cwd": repo, "session_id": "s"},
                          env=self.env())
        self.assertIn("plans 2 (1 blk)", out)


class IndexMark(TempHome):
    """The `idx` segment: graph readiness of the enclosing repo."""

    def setUp(self):
        super().setUp()
        self.repo = self.make_repo("proj")
        # a real executable so cbm_bin() is truthy without a real index daemon
        self.envv = self.env(extra={"TEZGAH_CBM_BIN": sys.executable})
        subprocess.run(["git", "init", "-q", self.repo], check=True)
        self.touch(os.path.join(self.repo, "f"))
        subprocess.run(["git", "-C", self.repo, "add", "."], check=True)
        subprocess.run(["git", "-C", self.repo, "-c", "user.email=a@b",
                        "-c", "user.name=t", "commit", "-qm", "x"], check=True)

    def head(self):
        return subprocess.run(["git", "-C", self.repo, "rev-parse", "HEAD"],
                              capture_output=True, text=True).stdout.strip()

    def index(self, stamp):
        slug = support.slug(os.path.realpath(self.repo))
        db_dir = os.path.join(self.home, ".cache", "codebase-memory-mcp")
        os.makedirs(db_dir, exist_ok=True)
        open(os.path.join(db_dir, slug + ".db"), "w").close()
        if stamp is not None:
            self.touch(os.path.join(self.home, ".cache", "tezgah", slug))
            with open(os.path.join(self.home, ".cache", "tezgah", slug), "w") as fh:
                fh.write(stamp)

    def mark(self):
        out, proc = run_json([support.PROBE_CONTEXT],
                             {"fn": "health_lines", "cwd": self.repo},
                             env=self.envv)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        return out.rsplit("idx", 1)[1]

    def test_not_indexed(self):
        self.assertEqual(self.mark(), "\u2717")

    def test_fresh_index(self):
        self.index(self.head())
        self.assertEqual(self.mark(), "\u2713")

    def test_stale_index(self):
        self.index("deadbeef" * 5)
        self.assertEqual(self.mark(), "\u21bb")


class KillSwitchEnforcement(TempHome):
    """A documented kill switch must remove its rule from the injected text,
    not just flip a status mark. The labels are pinned here, so editing one in
    hooks/tezgah_policy.py fails this test instead of silently disabling it."""

    OFF = "**Turkish, BLUF.**"
    PONY = "**Ponytail (minimal code).**"
    CBM = "**Code discovery: graph first.**"
    CONSULT = "**Consult before irreversible.**"

    def session(self, repo):
        out, proc = run_json([support.PROBE_CONTEXT],
                             {"fn": "context_for", "event": "session_start",
                              "cwd": repo}, env=self.env())
        self.assertEqual(proc.returncode, 0, proc.stderr)
        return out

    def switch(self, name):
        self.touch(os.path.join(self.home, ".config", "tezgah", name))

    def test_default_keeps_every_rule(self):
        repo = self.make_repo()
        out = self.session(repo)
        for label in (self.OFF, self.PONY, self.CBM, self.CONSULT):
            self.assertIn(label, out)

    def test_exec_mode_off_drops_the_reporting_rule(self):
        repo = self.make_repo()
        self.switch("exec-mode.off")
        out = self.session(repo)
        self.assertNotIn(self.OFF, out)
        self.assertIn("exec-mode.off", out)

    def test_ponytail_auto_off_drops_the_ponytail_rule(self):
        repo = self.make_repo()
        self.switch("ponytail-auto.off")
        self.assertNotIn(self.PONY, self.session(repo))

    def test_repo_no_ponytail_drops_the_ponytail_rule(self):
        repo = self.make_repo()
        self.touch(os.path.join(repo, ".no-ponytail"))
        self.assertNotIn(self.PONY, self.session(repo))

    def test_consult_off_drops_the_consult_rule(self):
        repo = self.make_repo()
        self.switch("consult-off")
        self.assertNotIn(self.CONSULT, self.session(repo))

    def test_orchestrate_off_says_do_not_delegate(self):
        repo = self.make_repo()
        self.switch("orchestrate-off")
        self.assertIn("Orchestration is off", self.session(repo))

    def test_repo_no_cbm_drops_the_graph_rule(self):
        repo = self.make_repo()
        self.touch(os.path.join(repo, ".no-cbm"))
        out = self.session(repo)
        self.assertNotIn(self.CBM, out)
        self.assertIn("disabled for this repo", out)

    def test_user_prompt_names_the_disabled_rule(self):
        repo = self.make_repo()
        self.switch("exec-mode.off")
        out, proc = run_json([support.PROBE_CONTEXT],
                             {"fn": "context_for", "event": "user_prompt",
                              "cwd": repo}, env=self.env())
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("exec-mode.off", out)


if __name__ == "__main__":
    unittest.main()
