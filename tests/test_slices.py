"""hooks/tezgah_task.py's slice journal and `bin/tezgah-task slice`.

Every fixture is a real git repository under a temp HOME: the records live in
its `.tezgah/slices/`, the worktrees and branches are real, and the omp child
transcripts sit where omp writes them (`~/.omp/agent/sessions/<project>/
<stamp>_<parent>/<id>.jsonl`) under that HOME. The CLI runs in a subprocess the
way a session runs it; the assertions read the records back through `slices`.
"""
import json
import os
import subprocess
import sys
import unittest
import unittest.mock

import support
from support import TempHome

sys.path.insert(0, os.path.join(support.REPO, "hooks"))
import tezgah_paths as tp  # noqa: E402
import tezgah_task as tt  # noqa: E402

CLI = os.path.join(support.REPO, "bin", "tezgah-task")
GIT_ENV = {"GIT_CONFIG_GLOBAL": os.devnull, "GIT_CONFIG_SYSTEM": os.devnull,
           "GIT_TERMINAL_PROMPT": "0"}
PLAN = ("---\nid: 001\ntitle: a plan\nstatus: open\nphase: verification\n"
        "allowed_paths:\n  - '**'\n---\n## Goal\nthe goal\n")


class Journal(TempHome):
    """A repository with one commit on `main`, `.tezgah/` ignored."""

    def setUp(self):
        super().setUp()
        self.repo = self.make_repo()
        self.git("init", "-q", "-b", "main", self.repo, cwd=self.home)
        with open(os.path.join(self.repo, ".gitignore"), "w") as fh:
            fh.write("/.tezgah/\n")
        self.git("add", ".gitignore")
        self.git("commit", "-q", "-m", "init")

    def git(self, *args, cwd=None):
        return subprocess.run(
            ["git", "-C", cwd or self.repo, "-c", "user.name=t",
             "-c", "user.email=t@localhost"] + list(args),
            check=True, capture_output=True, text=True,
            env=dict(os.environ, **GIT_ENV)).stdout.strip()

    def commit_file(self, name, cwd=None, message=None):
        with open(os.path.join(cwd or self.repo, name), "w") as fh:
            fh.write(name)
        self.git("add", name, cwd=cwd)
        self.git("commit", "-q", "-m", message or name, cwd=cwd)

    def worktree(self, branch):
        path = os.path.join(self.home, "wt-" + branch)
        self.git("worktree", "add", "-q", "-b", branch, path)
        return os.path.realpath(path)

    def task(self, *args):
        return support.run([CLI] + list(args), env=self.env(), cwd=self.repo)

    def record(self, sid):
        return next((r for r in tt.slices(self.repo) if r["id"] == sid), None)


class Records(Journal):

    def test_open_writes_one_record_and_a_reopen_counts_an_attempt(self):
        tree = self.worktree("slice-a")
        rec = tt.open_slice(self.repo, "SliceA", host="omp", agent="task",
                            brief="work only in %s please" % tree, parent="p1",
                            cwd=self.repo)
        path = os.path.join(self.repo, ".tezgah", "slices", "SliceA.json")
        with open(path) as fh:
            self.assertEqual(json.load(fh), rec)
        self.assertEqual((rec["status"], rec["failure"], rec["attempts"], rec["kind"]),
                         ("open", "", 1, "agent"))
        self.assertEqual((rec["worktree"], rec["branch"]), (tree, "slice-a"))
        self.assertEqual(rec["base"], self.git("rev-parse", "HEAD"))
        tt.close_slice(self.repo, "SliceA", "stopped", "quota")
        again = tt.open_slice(self.repo, "SliceA", host="omp")
        self.assertEqual((again["status"], again["failure"], again["attempts"]),
                         ("open", "", 2))
        self.assertEqual(again["opened"], rec["opened"])
        self.assertEqual(again["worktree"], tree)

    def test_the_worktree_is_the_one_the_task_names_after_the_shared_context(self):
        first, second = self.worktree("s"), self.worktree("s-two")
        (row,) = tt.spawned("task", {
            "context": "slices: %s and %s" % (second, first),
            "tasks": [{"name": "Two", "task": "work only in %s" % second}]})
        rec = tt.open_slice(self.repo, row[0], brief=row[2])
        self.assertEqual((rec["worktree"], rec["branch"]), (second, "s-two"))

    def test_a_worktree_writes_the_main_checkouts_journal(self):
        tree = self.worktree("slice-b")
        tt.open_slice(tree, "FromTree")
        self.assertEqual(tt.slice_dir(tree), tt.slice_dir(self.repo))
        self.assertIsNotNone(self.record("FromTree"))

    def test_close_takes_the_three_terminal_statuses(self):
        tt.open_slice(self.repo, "s1")
        stopped = tt.close_slice(self.repo, "s1", "stopped", "rate_limit")
        self.assertEqual((stopped["status"], stopped["failure"]), ("stopped", "rate_limit"))
        resumed = tt.close_slice(self.repo, "s1", "resumed")
        self.assertEqual((resumed["status"], resumed["failure"], resumed["attempts"]),
                         ("resumed", "rate_limit", 1))
        done = tt.close_slice(self.repo, "s1", "done")
        # the class stays, so the stats still count the stop
        self.assertEqual((done["status"], done["failure"]), ("done", "rate_limit"))
        self.assertIsNone(tt.close_slice(self.repo, "nobody", "done"))
        with self.assertRaises(ValueError):
            tt.close_slice(self.repo, "s1", "open")

    def test_an_unreadable_record_is_skipped(self):
        tt.open_slice(self.repo, "good")
        with open(os.path.join(tt.slice_dir(self.repo), "bad.json"), "w") as fh:
            fh.write("{not json")
        self.assertEqual([r["id"] for r in tt.slices(self.repo)], ["good"])

    def test_classify(self):
        for text, want in (("Error: 429 Too Many Requests", "rate_limit"),
                           ('{"type": "rate_limit_error"}', "rate_limit"),
                           ("403 Key limit exceeded", "quota"),
                           ("You have hit your usage limit", "quota"),
                           ("402 spend limit reached", "quota"),
                           ("Request was aborted", "aborted"),
                           ("the job was cancelled", "aborted"),
                           ("command timed out after 300 s", "timeout"),
                           ("stop: max_tokens", "cut_off"),
                           ("context length exceeded", "cut_off"),
                           ("NameError: x", "error"),
                           ("", ""), (None, ""), ("   ", "")):
            self.assertEqual(tt.classify(text), want, text)

    def test_spawned_reads_every_hosts_spawn_call(self):
        omp = tt.spawned("task", {"context": "shared", "tasks": [
            {"name": "A", "agent": "explore", "task": "do a"},
            {"name": "B c", "task": "do b"}]})
        self.assertEqual(omp, [("A", "explore", "shared\n\ndo a"),
                               ("B-c", "", "shared\n\ndo b")])
        claude = tt.spawned("Agent", {"description": "d", "prompt": "p",
                                      "subagent_type": "reviewer"})
        self.assertEqual(claude, [(tt.slice_id("", "d\n\np"), "reviewer", "d\n\np")])
        self.assertEqual(len(claude[0][0]), 12)
        self.assertEqual(tt.spawned("Task", {"prompt": "p"})[0][1:], ("", "p"))
        codex = tt.spawned("spawn_agent", {"message": "m", "agent_type": "worker"})
        self.assertEqual(codex[0][1:], ("worker", "m"))
        self.assertEqual(tt.spawned("spawn_agent", {"prompt": "q", "agent": "w"})[0][1:],
                         ("w", "q"))
        opencode = tt.spawned("task", {"description": "d", "prompt": "p",
                                       "subagent_type": "general"})
        self.assertEqual(opencode[0][1:], ("general", "d\n\np"))
        self.assertEqual(tt.spawned("bash", {"command": "ls"}), [])
        self.assertEqual(tt.spawned("task", "not a dict"), [])


class NoteSpawn(Journal):

    def call(self, failed=None, text=""):
        return tt.note_spawn(self.repo, "sess", "claude", "Agent",
                             {"description": "d", "prompt": "p %s" % failed,
                              "subagent_type": "reviewer"}, failed=failed,
                             result_text=text)

    def test_a_synchronous_result_closes_the_record_at_once(self):
        (failed,) = self.call(True, "API Error: 429 rate_limit_error")
        self.assertEqual((failed["status"], failed["failure"]), ("stopped", "rate_limit"))
        (blank,) = self.call(True, "")
        self.assertEqual((blank["status"], blank["failure"]), ("stopped", "error"))
        (ok,) = self.call(False)
        self.assertEqual(ok["status"], "done")
        (running,) = self.call(None)
        self.assertEqual((running["status"], running["parent"], running["host"]),
                         ("open", "sess", "claude"))
        self.assertEqual(len(tt.slices(self.repo)), 3)

    def test_slices_off_and_a_tree_outside_git_write_nothing(self):
        switch = os.path.join(tp.OFF_DIRS[0], "slices-off")
        os.makedirs(os.path.dirname(switch), exist_ok=True)
        open(switch, "w").close()
        try:
            self.assertEqual(self.call(False), [])
        finally:
            os.remove(switch)
        self.assertFalse(os.path.exists(tt.slice_dir(self.repo)))
        outside = os.path.join(self.home, "plain")
        os.makedirs(outside)
        self.assertEqual(tt.note_spawn(outside, "s", "claude", "Agent", {"prompt": "p"}), [])


def _row(role, **fields):
    return {"type": "message", "message": dict(role=role, **fields)}


class Pending(Journal):
    """An omp record still open is closed from its child transcript."""

    def transcript(self, parent, sid, rows, pad=0):
        folder = os.path.join(self.home, ".omp", "agent", "sessions", "-proj",
                              "2026-10-11T08-00-00-000Z_" + parent)
        os.makedirs(folder, exist_ok=True)
        with open(os.path.join(folder, sid + ".jsonl"), "w") as fh:
            for _ in range(pad):
                fh.write(json.dumps(_row("user", content="x" * 500)) + "\n")
            for row in rows:
                fh.write(json.dumps(row) + "\n")

    def test_pending_closes_ended_omp_records_and_keeps_the_running_one(self):
        for sid in ("Dead", "Done", "Busy", "NoFile"):
            tt.open_slice(self.repo, sid, host="omp", agent="task", parent="P1",
                          brief="brief of " + sid)
        # past the 64 KB tail: the cut first line must not break the read
        self.transcript("P1", "Dead", [
            _row("assistant", stopReason="toolUse"),
            _row("assistant", stopReason="error", errorMessage="403 Key limit exceeded")],
            pad=200)
        self.transcript("P1", "Done", [
            _row("assistant", stopReason="toolUse",
                 content=[{"type": "toolCall", "name": "yield"}]),
            _row("toolResult", toolName="yield")])
        self.transcript("P1", "Busy", [
            _row("assistant", stopReason="toolUse"), _row("toolResult", toolName="bash")])
        with unittest.mock.patch.dict(os.environ, {"HOME": self.home}):
            rows = tt.pending(self.repo)
            lines = tt.slice_lines(self.repo, limit=5)
        self.assertEqual(sorted(r["id"] for r in rows), ["Busy", "Dead", "NoFile"])
        self.assertEqual((self.record("Dead")["status"], self.record("Dead")["failure"]),
                         ("stopped", "quota"))
        self.assertEqual(self.record("Done")["status"], "done")
        self.assertEqual(self.record("Busy")["status"], "open")
        dead = next(line for line in lines if " Dead " in line)
        self.assertEqual(dead, "- slice Dead (omp/task) stopped quota attempts 1: "
                               "tezgah-task slice resume Dead")
        self.assertTrue(all(len(line) <= tt.SLICE_LINE for line in lines), lines)

    def test_a_line_stays_bounded_and_keeps_its_command(self):
        tree = self.worktree("b" * 60)
        rec = tt.open_slice(self.repo, "x" * 80, host="claude", agent="a" * 40,
                            brief="in " + tree)
        line = tt.slice_line(rec)
        self.assertLessEqual(len(line), tt.SLICE_LINE)
        self.assertTrue(line.endswith(": tezgah-task slice resume " + "x" * 80), line)
        job = tt.open_slice(self.repo, "bg_5", kind="job", parent="P9",
                            brief="python3 tests/neuter_matrix.py > /tmp/n.log 2>&1")
        self.assertEqual(tt.slice_line(job),
                         "- job bg_5 open: python3 tests/neuter_matrix.py > /tmp/n.log "
                         "2>&1 (parent session P9) - read its result there before "
                         "re-running")


class Cli(Journal):

    def test_open_done_stop_through_the_cli(self):
        proc = self.task("slice", "open", "--id", "c1", "--host", "codex",
                         "--agent", "worker", "--brief", "the brief")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(proc.stdout.strip(), "slice c1 open (agent, attempt 1)")
        proc = self.task("slice", "stop", "c1", "--class", "timeout")
        self.assertEqual((proc.returncode, proc.stdout.strip()),
                         (0, "slice c1 stopped (timeout)"))
        self.assertEqual(self.task("slice", "stop", "c1", "--class", "nope").returncode, 2)
        self.assertEqual(self.task("slice", "done", "c1").returncode, 0)
        self.assertEqual(self.record("c1")["status"], "done")
        missing = self.task("slice", "done", "ghost")
        self.assertEqual(missing.returncode, 1)
        self.assertIn("FAIL no slice record ghost", missing.stdout)

    def test_reconcile_prune_deletes_landed_branches_and_keeps_unmerged_ones(self):
        tree = self.worktree("slice-done")
        self.assertEqual(self.task("slice", "open", "--id", "D", "--host", "omp",
                                   "--brief", "work in " + tree).returncode, 0)
        self.commit_file("d.txt", cwd=tree)
        self.git("merge", "-q", "--no-ff", "--no-edit", "slice-done")
        self.git("branch", "loose")
        self.git("checkout", "-q", "loose")
        self.commit_file("loose.txt")
        self.git("checkout", "-q", "main")
        self.git("merge", "-q", "--no-ff", "--no-edit", "loose")
        self.git("branch", "unmerged")
        self.git("checkout", "-q", "unmerged")
        self.commit_file("u.txt")
        self.git("checkout", "-q", "main")
        proc = self.task("slice", "reconcile", "--prune")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("worktree removed: %s (slice-done)" % tree, proc.stdout)
        self.assertIn("branch deleted: loose", proc.stdout)
        self.assertIn("slice D done: slice-done landed", proc.stdout)
        self.assertIn("no open or stopped slice", proc.stdout)
        branches = self.git("for-each-ref", "--format=%(refname:short)", "refs/heads")
        self.assertEqual(sorted(branches.split()), ["main", "unmerged"])
        self.assertEqual(self.record("D")["status"], "done")

    def test_reconcile_keeps_an_unstarted_slice_open(self):
        tree = self.worktree("slice-new")
        self.task("slice", "open", "--id", "N", "--brief", "work in " + tree)
        proc = self.task("slice", "reconcile", "--prune")
        self.assertIn("worktree kept: %s" % tree, proc.stdout)
        self.assertIn("- slice N (?/?) open attempts 1", proc.stdout)
        self.assertEqual(self.record("N")["status"], "open")

    def test_resume_names_the_last_commit_and_marks_the_record_resumed(self):
        tree = self.worktree("slice-r")
        self.task("slice", "open", "--id", "R", "--host", "omp", "--parent", "P2",
                  "--brief", "build the thing in " + tree)
        self.commit_file("step.txt", cwd=tree, message="step one")
        with open(os.path.join(tree, "half.txt"), "w") as fh:
            fh.write("half")
        self.task("slice", "stop", "R", "--class", "quota")
        proc = self.task("slice", "resume", "R")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        sha = self.git("rev-parse", "--short", "HEAD", cwd=tree)
        resume = ("Resume: last commit %s step one on slice-r; uncommitted: half.txt; "
                  "continue from there, do not redo committed steps" % sha)
        out = proc.stdout.splitlines()
        self.assertTrue(out[1].startswith("  native: `write agent://R` (while omp "
                                          "session P2 still runs)"), out)
        self.assertIn("build the thing in " + tree, out)
        self.assertEqual(out[-1], resume)
        rec = self.record("R")
        self.assertEqual((rec["status"], rec["attempts"], rec["failure"]),
                         ("resumed", 1, "quota"))

    def test_approve_is_refused_until_the_reviewer_slice_is_done(self):
        plans = os.path.join(self.repo, ".tezgah", "plans", "open")
        os.makedirs(plans)
        with open(os.path.join(plans, "001-a-plan.md"), "w") as fh:
            fh.write(PLAN)
        self.task("slice", "open", "--id", "rev1", "--host", "claude",
                  "--agent", "tezgah-reviewer", "--brief", "review the diff")
        self.task("slice", "stop", "rev1", "--class", "quota")
        refused = self.task("review", "001", "tezgah-reviewer", "approve")
        self.assertEqual(refused.returncode, 1)
        self.assertIn("FAIL review slice rev1 is stopped (quota): finish it, or "
                      "resume it with `tezgah-task slice resume rev1`", refused.stdout)
        self.assertEqual(self.task("review", "001", "rev1", "approve").returncode, 1)
        self.assertEqual(self.task("slice", "done", "rev1").returncode, 0)
        allowed = self.task("review", "001", "tezgah-reviewer", "approve")
        self.assertEqual(allowed.returncode, 0, allowed.stdout)
        self.assertIn("review recorded: tezgah-reviewer approve round 1", allowed.stdout)

    def test_stats_flags_a_signature_at_three_events(self):
        for n in range(26):
            tt.open_slice(self.repo, "ok%d" % n, host="omp")
            tt.close_slice(self.repo, "ok%d" % n, "done")
        for n in range(3):
            tt.open_slice(self.repo, "rl%d" % n, host="omp")
            tt.close_slice(self.repo, "rl%d" % n, "stopped", "rate_limit")
        tt.open_slice(self.repo, "slow", host="claude")
        tt.close_slice(self.repo, "slow", "stopped", "timeout")
        proc = self.task("slice", "stats", "--window", "14", "--json")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        stats = json.loads(proc.stdout)
        self.assertEqual(stats["slices"], 30)
        self.assertEqual(stats["status"], {"done": 26, "stopped": 4})
        self.assertEqual(stats["failure"], {"rate_limit": 3, "timeout": 1})
        self.assertEqual(stats["host"], {"omp": 29, "claude": 1})
        # 1 of 30 is under 5% and under 3 events: not a candidate
        self.assertEqual(stats["candidates"], [
            {"signature": "rate_limit+omp", "events": 3, "share": 0.1,
             "lever": "hooks/tezgah_models.py fallback chain"}])
        text = self.task("slice", "stats").stdout
        self.assertIn("candidate: rate_limit+omp - 3 events (10% of slices) - lever: "
                      "hooks/tezgah_models.py fallback chain", text)

    def test_misuse_exits_two(self):
        for args in (("slice",), ("slice", "nope"), ("slice", "open"),
                     ("slice", "open", "--id", "x", "--kind", "bad"),
                     ("slice", "resume"), ("slice", "stats", "--window", "0")):
            self.assertEqual(self.task(*args).returncode, 2, args)


if __name__ == "__main__":
    unittest.main()
