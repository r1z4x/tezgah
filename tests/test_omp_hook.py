"""hosts/omp/hook.py: the omp lifecycle envelope over the shared core.

omp's extension API is TypeScript, so the python half takes one JSON payload and
answers with one JSON object (hosts/omp/hook.py's docstring is the protocol).
These tests drive that protocol directly: they are the only host-level check
that omp's session context, gate, evidence ledger and Stop rule behave.
"""
import json
import os
import shutil
import unittest

import support
from support import TempHome, run, run_json


class OmpHook(TempHome):
    def event(self, payload, env=None):
        return run_json([support.OMP_HOOK], payload, env=env or self.env())

    def kinds(self, session):
        """The used kinds this session's ledger recorded, in order."""
        path = os.path.join(self.home, ".cache", "tezgah", "sessions",
                            support.slug(session) + ".jsonl")
        try:
            with open(path) as fh:
                return [json.loads(line)["kind"] for line in fh if line.strip()]
        except OSError:
            return []

    def indexed(self, repo):
        """Make the fixture repo's idx mark resolvable: an index db, and a code
        graph binary, so the probe is not short-circuited and really forks git."""
        d = os.path.join(self.home, ".cache", "codebase-memory-mcp")
        os.makedirs(d, exist_ok=True)
        open(os.path.join(d, support.slug(repo) + ".db"), "w").close()
        cbm = os.path.join(self.home, "cbm-shim")
        with open(cbm, "w") as fh:
            fh.write("#!/bin/sh\nexit 1\n")
        os.chmod(cbm, 0o755)
        return cbm

    def counting_env(self, cbm):
        """An env whose PATH has a `git` in front of the real one that logs every
        fork, so "the redraw forked nothing" is measured rather than assumed."""
        d = os.path.join(self.home, "bin")
        os.makedirs(d, exist_ok=True)
        log = os.path.join(self.home, "git.log")
        with open(os.path.join(d, "git"), "w") as fh:
            fh.write("#!/bin/sh\necho \"$@\" >> %s\nexec %s \"$@\"\n"
                     % (log, shutil.which("git") or "/usr/bin/git"))
        os.chmod(os.path.join(d, "git"), 0o755)
        return log, self.env(extra={
            "PATH": os.pathsep.join([d, os.environ.get("PATH", "")]),
            "TEZGAH_CBM_BIN": cbm})

    def forks(self, log):
        try:
            with open(log) as fh:
                return len([line for line in fh if line.strip()])
        except OSError:
            return 0

    def test_a_mention_of_a_tool_is_not_a_use_of_it(self):
        # the audit found the line claiming a consult the session never ran:
        # `consult` in the argument was enough to flip the mark
        repo = self.make_repo()
        cases = [
            ("grep -n consult hooks/ | head", None),
            ("ls -la /Users/x/.cargo/bin/orx", None),
            ('git commit -m "consult ran, and orx too"', None),
            ("~/.config/tezgah/bin/consult \"is this safe?\"", "consult"),
            ("orx run --project p", "research"),
            ("cd /tmp && sudo env X=1 consult --online q", "consult"),
        ]
        for cmd, kind in cases:
            session = support.slug(cmd)
            _out, proc = self.event(
                {"event": "post_tool_use", "cwd": repo, "session_id": session,
                 "tool": "bash", "input": {"command": cmd}})
            self.assertEqual(proc.returncode, 0, proc.stderr)
            # the ledger also carries a null kind per call; the marks read the
            # four names, so only those are the claim under test
            kinds = [k for k in self.kinds(session) if k]
            self.assertEqual(kinds, [] if kind is None else [kind], cmd)

    def test_a_watched_tool_result_forks_no_git(self):
        # the idx mark is the only thing on the line that costs a subprocess, and
        # the session hands back the glyph the probed answer carried, so a busy
        # turn stops paying two git forks per watched tool
        repo = self.make_repo()
        log, env = self.counting_env(self.indexed(repo))
        payload = {"event": "post_tool_use", "cwd": repo, "session_id": "s",
                   "tool": "bash", "input": {"command": "pytest -q"},
                   "idx": "\u2713"}
        before = self.forks(log)
        for _ in range(3):
            out, proc = self.event(payload, env=env)
            self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(self.forks(log) - before, 0)
        # the line still carries the mark, and the glyph the next redraw uses
        self.assertIn("idx\u2713", out["status"])
        self.assertEqual(out["idx"], "\u2713")
        # without a glyph the same event has to ask - which is what makes the
        # zero above a saving and not a probe that never happens
        before = self.forks(log)
        probed, _ = self.event({k: v for k, v in payload.items() if k != "idx"},
                               env=env)
        self.assertGreater(self.forks(log) - before, 0)
        self.assertIn("idx\u2713", probed["status"])

    def test_the_turn_boundary_still_probes_the_mark(self):
        # turn_end is where the line is read, so the glyph never stands in for
        # the probe there, and the answer hands the fresh glyph back for the
        # redraws in between
        repo = self.make_repo()
        log, env = self.counting_env(self.indexed(repo))
        before = self.forks(log)
        out, proc = self.event({"event": "status", "cwd": repo,
                                "session_id": "s", "idx": "\u2013"}, env=env)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertGreater(self.forks(log) - before, 0)
        self.assertIn("idx\u2713", out["status"])   # the probe's answer, not "–"
        self.assertEqual(out["idx"], "\u2713")

    def test_session_start_carries_repo_state_without_the_core(self):
        repo = self.make_repo()
        out, proc = self.event({"event": "session_start", "cwd": repo,
                                "session_id": "s"})
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("Graph", out["context"])
        # omp's managed RULES.md already carries the always-on core, so the
        # session payload must not pay for the contract a second time
        self.assertNotIn("**Turkish, BLUF.**", out["context"])
        self.assertIn("\033[32mpony\u2713\033[0m", out["status"])

    def test_status_answers_off_root(self):
        # the status line is the one global signal: tezgah loads as a globally
        # loaded rules file on omp, so the marks must not go silent off-root
        out, proc = self.event({"event": "status", "cwd": self.home})
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("\033[32mpony\u2713\033[0m", out["status"])

    def test_status_drops_color_when_the_environment_opts_out(self):
        # NO_COLOR must strip the escapes at the source, so a terminal that
        # asked for none cannot end up showing them literally
        out, proc = run_json([support.OMP_HOOK],
                             {"event": "status", "cwd": self.home},
                             env=self.env(extra={"NO_COLOR": "1"}))
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertNotIn("\033", out["status"])
        self.assertIn("pony\u2713", out["status"])

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
