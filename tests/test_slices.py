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
        # one SQLite file holds the journal, not a file per record
        folder = os.path.join(self.repo, ".tezgah", "slices")
        self.assertEqual(self.record("SliceA"), rec)
        self.assertEqual(sorted(n for n in os.listdir(folder) if not n.startswith(".")),
                         ["slices.db"])
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

    def test_an_old_json_record_is_imported_once_and_removed(self):
        # the one-file-per-record journal an earlier release wrote: each file
        # goes into the table and is deleted; one that does not parse, or whose
        # id is no string, stays put; the newer of a file and a row wins
        tt.open_slice(self.repo, "good")
        tt.open_slice(self.repo, "later")
        folder = tt.slice_dir(self.repo)
        old = {"id": "Old", "status": "stopped", "parent": "S0", "failure": "quota",
               "updated": "2026-10-10T00:00:00Z", "host": "omp"}
        for name, body in (("Old.json", json.dumps(old)), ("bad.json", "{not json"),
                           ("odd.json", json.dumps({"id": ["x"]})),
                           ("good.json", json.dumps({"id": "good", "status": "done",
                                                     "updated": "2000-01-01T00:00:00Z"})),
                           ("later.json", json.dumps({"id": "later", "status": "stopped",
                                                      "updated": "2999-01-01T00:00:00Z"}))):
            with open(os.path.join(folder, name), "w") as fh:
                fh.write(body)
        self.assertEqual(sorted(r["id"] for r in tt.slices(self.repo)),
                         ["Old", "good", "later"])
        self.assertEqual(self.record("Old")["failure"], "quota")
        self.assertEqual(self.record("good")["status"], "open")
        self.assertEqual(self.record("later")["status"], "stopped")
        self.assertEqual(sorted(n for n in os.listdir(folder) if n.endswith(".json")),
                         ["bad.json", "odd.json"])

    def test_a_damaged_journal_reads_as_empty_and_a_write_says_why(self):
        # readers fail open (the Stop rule and the prompt read them); the CLI
        # names the problem instead of a traceback
        folder = tt.slice_dir(self.repo)
        os.makedirs(folder)
        with open(os.path.join(folder, tt.SLICE_DB), "w") as fh:
            fh.write("this is no database" * 100)
        self.assertEqual(tt.slices(self.repo), [])
        self.assertEqual(tt.pending(self.repo), [])
        self.assertEqual(tt.slice_lines(self.repo, session="S1", others=True), [])
        proc = self.task("slice", "open", "--id", "X", "--brief", "b")
        self.assertEqual(proc.returncode, 1, proc.stderr)
        self.assertIn("cannot write the slice record", proc.stdout)
        self.assertNotIn("Traceback", proc.stderr)

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

    def test_the_private_repository_ignores_the_journal(self):
        # the records change every turn; `git status` in `.tezgah` listed
        # `?? slices/` in every project that ran a subagent
        ws = os.path.join(self.repo, ".tezgah")
        os.makedirs(ws, exist_ok=True)
        self.git("init", "-q", ws, cwd=self.home)
        tt.open_slice(self.repo, "W1", host="omp", brief="b")
        self.assertEqual(self.git("status", "--porcelain", cwd=ws), "")
        self.assertEqual([r["id"] for r in tt.slices(self.repo)], ["W1"])


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

    def test_a_session_sees_only_the_slices_it_spawned(self):
        # owner, 2026-10-11: another session's stopped slices rode this
        # session's prompt every turn
        tt.open_slice(self.repo, "Mine", host="claude", parent="S1", brief="a")
        tt.open_slice(self.repo, "Theirs", host="claude", parent="S2", brief="b")
        tt.close_slice(self.repo, "Theirs", "stopped", "error")
        self.assertEqual([ln.split()[2] for ln in tt.slice_lines(self.repo, session="S1")],
                         ["Mine"])
        self.assertEqual(sorted(ln.split()[2] for ln in tt.slice_lines(self.repo)),
                         ["Mine", "Theirs"])
        # a record opened by hand has no owner and is everyone's; the resume
        # block's count names how many belong to other sessions
        tt.open_slice(self.repo, "Hand", host="claude", brief="c")
        lines = tt.slice_lines(self.repo, session="S1", others=True)
        self.assertEqual(sorted(ln.split()[2] for ln in lines[:-1]), ["Hand", "Mine"])
        self.assertEqual(lines[-1], "- 1 pending slice(s) of other sessions: "
                                    "tezgah-task slice reconcile")

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

    def test_a_job_past_the_background_deadline_leaves_the_pending_list(self):
        # the bg_5 pointer outlives a /clear, but not omp's 3600 s deadline
        tt.open_slice(self.repo, "job-new", kind="job", host="omp", parent="P9",
                      brief="python3 tests/neuter_matrix.py")
        old = tt.open_slice(self.repo, "job-old", kind="job", host="omp", parent="P9",
                            brief="python3 tests/impacted.py --all")
        old["opened"] = old["updated"] = "2026-10-11T08:00:00Z"
        tt._write_record(self.repo, old)
        self.assertEqual([r["id"] for r in tt.pending(self.repo)], ["job-new"])
        self.assertEqual(self.record("job-old")["status"], "stale")

    def test_an_open_record_nothing_moved_goes_stale_and_never_refuses(self):
        # a Codex child reports no end: after SLICE_IDLE_SECONDS it leaves the
        # list as stale, read neither as done nor as stopped
        rec = tt.open_slice(self.repo, "review", host="codex", brief="b")
        rec["updated"] = "2026-10-10T00:00:00Z"
        tt._write_record(self.repo, rec)
        self.assertEqual(tt.pending(self.repo), [])
        self.assertEqual((self.record("review")["status"],
                          self.record("review")["failure"]), ("stale", ""))

    def test_a_respawn_of_the_same_name_is_read_from_its_newest_transcript(self):
        # omp writes a same-name re-dispatch to `<name>-2.jsonl`; the first
        # run's end must not close the re-opened record
        with unittest.mock.patch.dict(os.environ, {"HOME": self.home}):
            self.transcript("P1", "Rev", [
                _row("assistant", stopReason="error", errorMessage="429")])
            tt.open_slice(self.repo, "Rev", host="omp", parent="P1", brief="b")
            self.assertEqual(self.record("Rev")["status"], "open")
            tt.pending(self.repo)
            self.assertEqual(self.record("Rev")["status"], "stopped")
            tt.open_slice(self.repo, "Rev", host="omp", parent="P1", brief="b")
            self.transcript("P1", "Rev-2", [
                _row("assistant", stopReason="toolUse"), _row("toolResult", toolName="bash")])
            self.assertEqual([r["id"] for r in tt.pending(self.repo)], ["Rev"])
            self.assertEqual(self.record("Rev")["status"], "open")
            self.transcript("P1", "Rev-2", [_row("toolResult", toolName="yield")])
            tt.pending(self.repo)
            self.assertEqual((self.record("Rev")["status"], self.record("Rev")["attempts"]),
                             ("done", 2))

    def test_a_redispatch_from_another_session_reads_that_sessions_transcript(self):
        # P1's run stopped on quota; the same name re-sent from P2 must not be
        # closed by P1's finished file
        with unittest.mock.patch.dict(os.environ, {"HOME": self.home}):
            self.transcript("P1", "Rev", [
                _row("assistant", stopReason="error", errorMessage="403 Key limit exceeded")])
            tt.open_slice(self.repo, "Rev", host="omp", parent="P1", brief="b")
            tt.pending(self.repo)
            self.assertEqual(self.record("Rev")["status"], "stopped")
            self.transcript("P2", "Rev", [
                _row("assistant", stopReason="toolUse"), _row("toolResult", toolName="bash")])
            tt.open_slice(self.repo, "Rev", host="omp", parent="P2", brief="b")
            self.assertIn("_P2", self.record("Rev")["transcript_dir"])
            tt.pending(self.repo)
            self.assertEqual(self.record("Rev")["status"], "open")

    def test_another_sessions_same_name_never_takes_a_stopped_slice(self):
        # research orchestrator-flow-audit S7, finding 1 (data/scripts/s7/
        # repro.py): session Y's unrelated `Fixer` re-opened X's stopped record,
        # which then left X's resume line and X's Stop rule
        with unittest.mock.patch.dict(os.environ, {"HOME": self.home}):
            task = {"tasks": [{"name": "Fixer", "agent": "task", "task": "edit app.py"}]}
            tt.note_spawn(self.repo, "sessX", "omp", "task", dict(task, context="x work"))
            tt.close_slice(self.repo, "Fixer", "stopped", "rate_limit")
            (theirs,) = tt.note_spawn(self.repo, "sessY", "omp", "task", {
                "context": "other work",
                "tasks": [{"name": "Fixer", "agent": "task", "task": "unrelated"}]})
            mine = self.record("Fixer")
            self.assertEqual((mine["parent"], mine["status"], mine["attempts"]),
                             ("sessX", "stopped", 1))
            self.assertEqual([ln.split()[2] for ln in tt.slice_lines(self.repo, session="sessX")],
                             ["Fixer"])
            self.assertTrue(theirs["id"].startswith("Fixer-"), theirs["id"])
            self.assertEqual((theirs["name"], theirs["parent"]), ("Fixer", "sessY"))
            # Y's next dispatch of that name, under another brief, is its own record
            (again,) = tt.note_spawn(self.repo, "sessY", "omp", "task", {
                "tasks": [{"name": "Fixer", "agent": "task", "task": "third brief"}]})
            self.assertEqual((again["id"], again["attempts"]), (theirs["id"], 2))
            # the child file omp writes is still `Fixer.jsonl` in Y's directory
            self.transcript("sessY", "Fixer", [_row("toolResult", toolName="yield")])
            rec = tt.open_slice(self.repo, "Fixer", host="omp", parent="sessY",
                                brief="third brief")
            self.assertEqual(rec["id"], theirs["id"])
            tt.pending(self.repo)
            self.assertEqual(self.record(theirs["id"])["status"], "done")
            # the same brief from another session is a re-dispatch and re-opens it
            (resent,) = tt.note_spawn(self.repo, "sessZ", "omp", "task",
                                      dict(task, context="x work"))
            self.assertEqual((resent["id"], resent["parent"]), ("Fixer", "sessZ"))


class BriefRepo(Journal):
    """note_spawn names the repository the brief works in (finding 2), and the
    record stays in cwd's journal, the one its owner reads."""

    def spawn(self, name, brief, **kw):
        with unittest.mock.patch.dict(os.environ, {"TEZGAH_ROOTS": self.home}):
            return tt.note_spawn(self.repo, "s", "omp", "task", {
                "tasks": [{"name": name, "task": brief}]}, **kw)[0]

    def test_a_brief_naming_another_repository_names_it_and_stays_here(self):
        other = self.make_repo("other")
        self.git("init", "-q", other, cwd=self.home)
        tree = self.worktree("w1")
        away = self.spawn("Away", "Work in %s only. Edit %s/app.py." % (other, other))
        here = self.spawn("Here", "edit %s/app.py" % tree)
        both = self.spawn("Both", "%s and %s" % (other, self.repo))
        self.assertEqual((away["cwd"], away["repo"]), (self.repo, other))
        self.assertEqual((here["repo"], both["repo"]), ("", ""))
        self.assertEqual(sorted(r["id"] for r in tt.slices(self.repo)), ["Away", "Both", "Here"])
        self.assertEqual(tt.slices(other), [])
        self.assertIn("(in other)", tt.slice_line(away))

    def test_a_stopped_slice_working_on_another_repository_still_refuses_its_owner(self):
        # review of S7 (F3): journalled in the other repository, the stopped
        # slice left its owner's Stop rule, which reads cwd's journal only
        import tezgah_integrity as ti
        other = self.make_repo("other")
        self.git("init", "-q", other, cwd=self.home)
        self.spawn("Away", "edit %s/app.py" % other, failed=True, result_text="429")
        stopped = ti._stopped_slice("s", self.repo)
        self.assertEqual((stopped or {}).get("id"), "Away")

    def test_a_repositorys_own_private_tezgah_repository_is_that_repository(self):
        # review of S7 (F2): `.tezgah` keeps its own git repository, and a
        # brief naming a plan file read as work in a second repository
        other = self.make_repo("other")
        self.git("init", "-q", other, cwd=self.home)
        for repo in (self.repo, other):
            self.git("init", "-q", os.path.join(repo, ".tezgah"), cwd=self.home)
        mine = self.spawn("Plan", "tick %s/.tezgah/plans/open/001.md" % self.repo)
        theirs = self.spawn("Theirs", "read %s/.tezgah/lessons.md" % other)
        self.assertEqual((mine["repo"], theirs["repo"]), ("", other))
        self.assertEqual(tt.main_repo(os.path.join(other, ".tezgah", "x")), other)


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
        # landed by ancestry but never committed on: a slice not yet started
        self.git("branch", "plan-next")
        # landed and committed on, but tracking an upstream: long-lived
        self.git("branch", "develop")
        self.git("checkout", "-q", "develop")
        self.commit_file("dev.txt")
        self.git("checkout", "-q", "main")
        self.git("merge", "-q", "--no-ff", "--no-edit", "develop")
        self.git("config", "branch.develop.remote", ".")
        self.git("config", "branch.develop.merge", "refs/heads/main")
        proc = self.task("slice", "reconcile", "--prune")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("worktree removed: %s (slice-done)" % tree, proc.stdout)
        self.assertIn("branch deleted: loose", proc.stdout)
        self.assertIn("slice D done: slice-done landed", proc.stdout)
        self.assertIn("no open or stopped slice", proc.stdout)
        branches = self.git("for-each-ref", "--format=%(refname:short)", "refs/heads")
        self.assertEqual(sorted(branches.split()), ["develop", "main", "plan-next", "unmerged"])
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
        self.assertIn("FAIL review slice rev1 is stopped (quota): let it finish, or "
                      "resume it with `tezgah-task slice resume rev1`", refused.stdout)
        self.assertIn("`tezgah-task slice done rev1`", refused.stdout)
        self.assertEqual(self.task("review", "001", "rev1", "approve").returncode, 1)
        self.assertEqual(self.task("slice", "done", "rev1").returncode, 0)
        allowed = self.task("review", "001", "tezgah-reviewer", "approve")
        self.assertEqual(allowed.returncode, 0, allowed.stdout)
        self.assertIn("review recorded: tezgah-reviewer approve round 1", allowed.stdout)

    def plan_at_head(self):
        plans = os.path.join(self.repo, ".tezgah", "plans", "open")
        os.makedirs(plans, exist_ok=True)
        with open(os.path.join(plans, "001-a-plan.md"), "w") as fh:
            fh.write(PLAN.replace("---\n", "---\ncheckpoint: %s\n"
                                  % self.git("rev-parse", "HEAD"), 1))

    def test_a_resumed_review_hands_the_guard_to_its_re_dispatch(self):
        self.plan_at_head()
        self.task("slice", "open", "--id", "rev1", "--agent", "tezgah-reviewer",
                  "--host", "claude", "--brief", "review")
        self.task("slice", "stop", "rev1", "--class", "quota")
        self.assertEqual(self.task("slice", "resume", "rev1").returncode, 0)
        # the re-dispatch has its own record, and it is still running
        self.task("slice", "open", "--id", "rev2", "--agent", "tezgah-reviewer",
                  "--host", "claude", "--brief", "review, resumed")
        refused = self.task("review", "001", "tezgah-reviewer", "approve")
        self.assertIn("review slice rev2 is open", refused.stdout)
        self.assertNotIn("rev1", refused.stdout)
        self.task("slice", "done", "rev2")
        self.assertEqual(self.task("review", "001", "tezgah-reviewer",
                                   "approve").returncode, 0)

    def test_an_older_plans_dead_reviewer_blocks_nothing(self):
        tt.open_slice(self.repo, "rev0", agent="tezgah-reviewer", host="claude",
                      brief="an older review")
        tt.close_slice(self.repo, "rev0", "stopped", "quota")
        old = self.record("rev0")
        old["updated"] = "2026-01-01T00:00:00Z"
        tt._write_record(self.repo, old)
        self.plan_at_head()
        self.assertEqual(self.task("review", "001", "tezgah-reviewer",
                                   "approve").returncode, 0)

    def task_as(self, session, *args):
        return support.run([CLI] + list(args), cwd=self.repo,
                           env=self.env(extra={"TEZGAH_SESSION": session}))

    def test_a_suffixed_review_record_is_this_sessions_and_only_its_own(self):
        # review of S7 (F1, N1): a reviewer spawned as `Reviewer` under another
        # session's record got `Reviewer-<d6>`, which the guard did not find; an
        # exact id stays reachable from any session, a bare name only from its own
        self.plan_at_head()
        theirs = tt.open_slice(self.repo, "Reviewer", host="omp", agent="task",
                               parent="X", brief="review plan 001, first run")
        tt.close_slice(self.repo, theirs["id"], "stopped", "quota")
        mine = tt.open_slice(self.repo, "Reviewer", host="claude", agent="task",
                             parent="Y", brief="review plan 001")
        self.assertNotEqual(mine["id"], "Reviewer")
        tt.close_slice(self.repo, mine["id"], "stopped", "quota")
        refused = self.task_as("Y", "review", "001", "Reviewer", "approve")
        self.assertEqual(refused.returncode, 1, refused.stdout)
        self.assertIn("review slice %s is stopped" % mine["id"], refused.stdout)
        self.assertNotIn("review slice Reviewer is", refused.stdout)  # X's review
        # a bare name answers only for its own session (no record has it as id)
        tt._write_record(self.repo, {"id": "Rev-0a1b2c", "name": "Rev", "parent": "Y",
                                     "kind": "agent", "status": "stopped",
                                     "updated": tt._now()})
        self.assertEqual(self.task_as("Z", "slice", "done", "Rev").returncode, 1)
        self.assertEqual(self.task_as("Y", "slice", "done", "Rev").stdout.strip(),
                         "slice Rev-0a1b2c done")
        # the exact id the refusal printed closes Y's record from any session
        done = self.task_as("Z", "slice", "done", mine["id"])
        self.assertEqual(done.stdout.strip(), "slice %s done (quota)" % mine["id"])
        self.assertEqual(self.record("Reviewer")["status"], "stopped")
        allowed = self.task_as("Y", "review", "001", "Reviewer", "approve")
        self.assertEqual(allowed.returncode, 0, allowed.stdout)

    def test_a_crashed_sessions_slice_is_resumed_by_its_id_from_another(self):
        # N1: `slice reconcile` lists X's stopped Fixer; Y resumes it by that id
        tt.open_slice(self.repo, "Fixer", host="claude", parent="X", brief="fix it")
        tt.close_slice(self.repo, "Fixer", "stopped", "quota")
        proc = self.task_as("Y", "slice", "resume", "Fixer")
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        self.assertEqual(self.record("Fixer")["status"], "resumed")

    def test_the_guard_reads_its_own_plans_records_and_a_stale_review(self):
        self.plan_at_head()
        # another plan's dead reviewer, however recent, is not this plan's
        other = tt.open_slice(self.repo, "revX", agent="tezgah-reviewer",
                              host="claude", brief="x")
        self.assertEqual(other["plan"], "001")
        other["plan"] = "000"
        other["status"], other["failure"] = "stopped", "quota"
        tt._write_record(self.repo, other)
        self.assertEqual(self.task("review", "001", "tezgah-reviewer",
                                   "approve").returncode, 0)
        # this plan's review whose end nobody saw blocks like a stopped one
        tt.open_slice(self.repo, "revS", agent="tezgah-reviewer", host="codex",
                      brief="s")
        tt.close_slice(self.repo, "revS", "stale")
        refused = self.task("review", "001", "tezgah-reviewer", "approve")
        self.assertIn("review slice revS is stale", refused.stdout)
        self.task("slice", "done", "revS")
        self.assertEqual(self.task("review", "001", "tezgah-reviewer",
                                   "approve").returncode, 0)

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

    def test_a_small_window_flags_no_share_alone(self):
        # one stop in two slices is 50%, and still no pattern below the floor
        tt.open_slice(self.repo, "ok", host="omp")
        tt.close_slice(self.repo, "ok", "done")
        tt.open_slice(self.repo, "q", host="omp")
        tt.close_slice(self.repo, "q", "stopped", "quota")
        stats = json.loads(self.task("slice", "stats", "--json").stdout)
        self.assertEqual(stats["candidates"], [])

    def test_misuse_exits_two(self):
        for args in (("slice",), ("slice", "nope"), ("slice", "open"),
                     ("slice", "open", "--id", "x", "--kind", "bad"),
                     ("slice", "resume"), ("slice", "stats", "--window", "0")):
            self.assertEqual(self.task(*args).returncode, 2, args)


if __name__ == "__main__":
    unittest.main()
