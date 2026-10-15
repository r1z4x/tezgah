"""Plan 108: the lifecycle sweep, and an idle slice that stays owed work.

The fixture is `tests/test_slices.py`'s: a real git repository under a temp HOME,
with the records in its `.tezgah/slices/`, real branches and real worktrees. The
CLI runs in a subprocess, the way a session runs it.

What is pinned here is the pair of failures the plan exists for: a tree that
leaves a landed branch or an orphan `phase:` behind, and an idle slice record
that `pending` used to forget instead of offering its resume brief.
"""
import os
import subprocess
import sys
import time
import unittest

import support
from test_slices import Journal  # the fixture this module reuses

sys.path.insert(0, os.path.join(support.REPO, "hooks"))
import tezgah_task as tt
import plan_orphans  # the census the close-over-open-item bar is read from


def old_stamp(hours=7):
    """A record time `hours` in the past, in the journal's own format."""
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(time.time() - hours * 3600))


def plan_file(repo, name, body):
    folder = os.path.join(repo, ".tezgah", "plans", "open")
    os.makedirs(folder, exist_ok=True)
    path = os.path.join(folder, name)
    with open(path, "w") as fh:
        fh.write(body)
    return path


class Sweep(Journal):

    def test_sweep_is_idempotent_and_leaves_the_pending_list_alone(self):
        # the orphan `phase:` and one pending slice, then the same tree twice
        path = plan_file(self.repo, "001-gone.md",
                         "---\nid: 001\ntitle: gone\nstatus: open\n"
                         "branch: plan/001-gone\nphase: implementation\n---\n"
                         "## Goal\nx\n")
        tt.open_slice(self.repo, "Kept", host="omp", brief="a slice nobody finished")
        first = self.task("sweep")
        self.assertEqual(first.returncode, 0, first.stderr)
        self.assertIn("phase cleared: 001", first.stdout)
        self.assertIn("swept: 1 change(s)", first.stdout)
        with open(path) as fh:
            # the empty-value shape `stop` writes: the parser reads no phase
            self.assertEqual(tt.frontmatter(fh.read()).get("phase") or "", "")
        again = self.task("sweep")
        self.assertEqual(again.returncode, 0, again.stderr)
        self.assertIn("swept: 0 change(s)", again.stdout)

        def slice_lines(out):
            return [line for line in out.splitlines() if line.startswith("- slice")]

        listed = slice_lines(again.stdout)
        self.assertTrue(listed, again.stdout)
        # the pending slice is printed both times and never written: resuming it
        # is the session's move, and closing it here would be the forgetting
        self.assertEqual(slice_lines(first.stdout), listed)
        self.assertEqual(self.record("Kept")["status"], "open")

    def test_a_landed_branch_is_deleted(self):
        self.commit_file("one.txt", message="one")
        self.git("checkout", "-q", "-b", "slice-branch")
        self.commit_file("two.txt", message="two")
        self.git("checkout", "-q", "main")
        self.git("merge", "-q", "--no-edit", "slice-branch")
        out = self.task("sweep")
        self.assertEqual(out.returncode, 0, out.stderr)
        self.assertIn("branch deleted: slice-branch", out.stdout)
        self.assertEqual(self.git("branch", "--list", "slice-branch"), "")

    def test_an_idle_slice_stays_owed_and_an_idle_job_is_stale(self):
        tt.open_slice(self.repo, "IdleOmp", host="omp", brief="stopped mid-flight")
        tt.open_slice(self.repo, "IdleJob", kind="job", host="omp", brief="a job")
        for sid in ("IdleOmp", "IdleJob"):
            rec = self.record(sid)
            rec["updated"] = old_stamp()
            tt._write_record(self.repo, rec)
        rows = {r["id"]: r for r in tt.pending(self.repo)}
        # a slice that went idle with no end is work nobody finished
        self.assertIn("IdleOmp", rows)
        self.assertEqual(rows["IdleOmp"]["status"], "stopped")
        self.assertEqual(rows["IdleOmp"]["failure"], "cut_off")
        # a job's result is in the parent transcript the record names, so it is
        # the one that closes `stale` and leaves the owed list
        self.assertNotIn("IdleJob", rows)
        self.assertEqual(self.record("IdleJob")["status"], "stale")

    def test_the_census_counts_only_the_class_that_rises(self):
        # a record with an unticked box and no `UNMET:` is the class the bar is
        # about; an `UNMET: <reason>` item is the sanctioned form and is not
        folder = os.path.join(self.home, "done")
        os.makedirs(folder)
        with open(os.path.join(folder, "001-open.md"), "w") as fh:
            fh.write("---\nid: 001\n---\n## Acceptance\n- [ ] one\n- [x] two\n")
        with open(os.path.join(folder, "002-unmet.md"), "w") as fh:
            fh.write("---\nid: 002\n---\n## Acceptance\n- [ ] one\n"
                     "      UNMET: the owner accepted it\n")
        with open(os.path.join(folder, "003-clean.md"), "w") as fh:
            fh.write("---\nid: 003\n---\n## Acceptance\n- [x] one\n")
        stats = plan_orphans.census(folder)
        self.assertEqual((stats["done"], stats["open_box"],
                          stats["open_box_no_unmet"]), (3, 2, 1))
        self.assertEqual([row["record"] for row in stats["records"]
                          if not row["unmet"]], ["001-open.md"])

    def test_the_workspace_link_of_a_linked_worktree_is_ignored(self):
        # a linked worktree shows `.tezgah` as a symlink to the main checkout's
        # workspace; `/.tezgah/` matches a directory only, so with the trailing
        # slash the link was untracked, the tree read dirty forever, and the
        # implementation phase began with a `checkpoint: pending` no commit could
        # clear
        repo = os.path.join(self.home, "link-check")
        os.makedirs(repo)
        self.git("init", "-q", "-b", "main", repo, cwd=self.home)
        with open(os.path.join(support.REPO, ".gitignore")) as fh:
            ignore = fh.read()
        with open(os.path.join(repo, ".gitignore"), "w") as fh:
            fh.write(ignore)
        os.symlink(os.path.join(self.home, "workspace"), os.path.join(repo, ".tezgah"))
        listed = subprocess.run(["git", "-C", repo, "status", "--porcelain"],
                                capture_output=True, text=True, check=False).stdout
        self.assertNotIn(".tezgah", listed)


if __name__ == "__main__":
    unittest.main()
