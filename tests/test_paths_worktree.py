"""The worktree bridge: a linked checkout is armed through its `.git` pointer,
its siblings are listed from `.git/worktrees/*/gitdir` - both without a git
fork - and every checkout keeps its own `.tezgah`."""
import json
import os
import shutil
import subprocess
import sys
import unittest
from unittest import mock

import support
from support import TempHome

sys.path.insert(0, support.HOOKS)
import tezgah_paths as tp  # noqa: E402

RESEARCH = os.path.join(support.REPO, "bin", "tezgah-research")


def git(*args):
    subprocess.run(["git"] + list(args), check=True, capture_output=True)


def porcelain(repo):
    """git's own list: every `worktree` path, with the prunable ones apart."""
    out = subprocess.run(["git", "-C", repo, "worktree", "list", "--porcelain"],
                         check=True, capture_output=True, text=True).stdout
    live, stale = [], []
    for block in out.strip().split("\n\n"):
        rows = block.splitlines()
        path = os.path.realpath(rows[0].split(" ", 1)[1])
        (stale if any(r.startswith("prunable") for r in rows) else live).append(path)
    return live, stale


class WorktreeBridge(TempHome):
    def setUp(self):
        super().setUp()
        self.main = self.make_repo("main")
        git("init", "-q", self.main)
        with open(os.path.join(self.main, "f"), "w") as fh:
            fh.write("x\n")
        git("-C", self.main, "add", ".")
        git("-C", self.main, "-c", "user.email=a@b", "-c", "user.name=t",
            "commit", "-qm", "x")
        # one sibling under the root, one outside every root
        self.inside = os.path.join(self.roots, "main-wt")
        self.outside = os.path.join(self.home, "elsewhere", "wt")
        os.makedirs(os.path.dirname(self.outside))
        git("-C", self.main, "worktree", "add", "-q", "--detach", self.inside)
        git("-C", self.main, "worktree", "add", "-q", "--detach", self.outside)
        self.inside = os.path.realpath(self.inside)
        self.outside = os.path.realpath(self.outside)
        patch = mock.patch.dict(os.environ, {"TEZGAH_ROOTS": self.roots})
        patch.start()
        self.addCleanup(patch.stop)
        # a git fork anywhere below fails the test: arming and listing are file reads
        forks = mock.patch("subprocess.Popen", side_effect=AssertionError("git forked"))
        self.no_fork = forks

    def test_a_worktree_outside_the_roots_is_armed_from_its_pointer_file(self):
        sub = os.path.join(self.outside, "deep")
        os.makedirs(sub)
        with self.no_fork:
            self.assertEqual(tp.linked_main(sub), self.main)
            self.assertEqual(tp.root_for(self.outside), self.outside)
            # the answer is a base the path sits under, from any depth
            self.assertEqual(tp.root_for(sub), self.outside)
            # a plain checkout and a worktree inside the roots keep their answer
            self.assertEqual(tp.root_for(self.main), self.roots)
            self.assertEqual(tp.root_for(self.inside), self.roots)
            self.assertIsNone(tp.linked_main(self.main))
            # outside the roots with no worktree pointer: still not armed
            self.assertIsNone(tp.root_for(os.path.dirname(self.outside)))

    def test_a_worktree_of_a_main_outside_the_roots_is_not_armed(self):
        other = os.path.join(self.home, "other")
        git("init", "-q", other)
        with open(os.path.join(other, "f"), "w") as fh:
            fh.write("x\n")
        git("-C", other, "add", ".")
        git("-C", other, "-c", "user.email=a@b", "-c", "user.name=t",
            "commit", "-qm", "x")
        wt = os.path.join(self.home, "other-wt")
        git("-C", other, "worktree", "add", "-q", "--detach", wt)
        self.assertIsNone(tp.root_for(wt))

    def test_a_submodule_pointer_is_not_a_worktree(self):
        sub = os.path.join(self.home, "elsewhere", "sub")
        os.makedirs(sub)
        with open(os.path.join(sub, ".git"), "w") as fh:
            fh.write("gitdir: %s/.git/modules/sub\n" % self.main)
        self.assertIsNone(tp.linked_main(sub))
        self.assertIsNone(tp.root_for(sub))

    def test_the_listing_agrees_with_git_from_every_checkout(self):
        live, stale = porcelain(self.main)
        self.assertEqual(len(live), 3, live)
        self.assertEqual(stale, [])
        for checkout in (self.main, self.inside, self.outside):
            with self.no_fork:
                got = tp.worktrees(checkout)
            self.assertEqual(got[0], self.main, checkout)
            self.assertEqual(sorted(got), sorted(live), checkout)

    def test_a_deleted_worktree_drops_out_as_git_marks_it_prunable(self):
        shutil.rmtree(self.outside)
        live, stale = porcelain(self.main)
        self.assertEqual(stale, [self.outside])
        self.assertEqual(sorted(tp.worktrees(self.main)), sorted(live))

    def test_every_checkout_keeps_its_own_workspace(self):
        checkouts = tp.worktrees(self.main)
        spaces = [tp.workspace(c) for c in checkouts]
        self.assertEqual(spaces, [os.path.join(c, ".tezgah") for c in checkouts])
        self.assertEqual(len(set(spaces)), 3)
        made = tp.ensure_workspace(self.outside)
        self.assertEqual(made, os.path.join(self.outside, ".tezgah"))
        # its own private repository, and nothing appeared in the main checkout
        self.assertTrue(os.path.isdir(os.path.join(made, ".git")))
        self.assertFalse(os.path.exists(os.path.join(self.main, ".tezgah")))

    def test_an_armed_worktree_finds_its_own_codegraph_index(self):
        """F1: a worktree base is a project, so the slug walk must include it.
        A configured root is still excluded (a root is not a project)."""
        import tezgah_gate as gate
        db = os.path.join(self.outside, ".codegraph")
        os.makedirs(db)
        open(os.path.join(db, "codegraph.db"), "w").close()
        with self.no_fork:
            base = tp.root_for(self.outside)
            self.assertIsNotNone(gate.index_slug(self.outside, base))
            self.assertIsNone(gate.index_slug(os.path.dirname(self.outside), base))
        # the in-root rule is unchanged: the root itself is still not a project
        root_db = os.path.join(self.roots, ".codegraph")
        os.makedirs(root_db)
        open(os.path.join(root_db, "codegraph.db"), "w").close()
        self.assertIsNone(gate.index_slug(self.main, tp.root_for(self.main)))

    def test_a_pointer_to_nowhere_is_not_a_worktree(self):
        """F2: git validates a pointer against its admin directory; a `.git`
        file naming a path git never wrote does not arm the directory."""
        fake = os.path.join(self.home, "elsewhere", "ghost")  # outside every root
        os.makedirs(fake)
        with open(os.path.join(fake, ".git"), "w") as fh:
            fh.write("gitdir: %s/.git/worktrees/ghost\n" % self.main)
        with self.no_fork:
            self.assertIsNone(tp.linked_main(fake))
            self.assertIsNone(tp.root_for(fake))

    def test_a_path_below_an_armed_worktree_is_armed_too(self):
        """F3: the walk tries every `.git`-holding ancestor, so the worktree's
        own `.tezgah` and a nested repo still answer the worktree."""
        ws = os.path.join(self.outside, ".tezgah", "research")
        os.makedirs(os.path.join(self.outside, ".tezgah", ".git"))
        os.makedirs(ws)
        nested = os.path.join(self.outside, "nested")
        os.makedirs(os.path.join(nested, ".git"))
        with self.no_fork:
            # the answer is the worktree, not the `.tezgah` or the nested repo
            self.assertEqual(tp.root_for(ws), self.outside)
            self.assertEqual(tp.root_for(os.path.join(nested, "deep")), self.outside)
            # ... while the nested repo answers for itself, never the checkout
            self.assertIsNone(tp.linked_main(nested))
            self.assertEqual(tp.worktrees(nested), [nested])

    def test_all_still_names_this_checkout_when_its_admin_entry_is_gone(self):
        """F4: a checkout git can no longer list (its admin entry removed, e.g.
        after an `mv`) is still this checkout and still shown."""
        import tezgah_research as tr
        moved = os.path.join(self.home, "moved")
        shutil.move(self.outside, moved)  # its admin entry still names the old path
        admin = os.path.join(self.main, ".git", "worktrees")
        names = os.listdir(admin)
        self.assertTrue(min(len(open(os.path.join(admin, n, "gitdir")).read()) > 0
                            for n in names), names)
        self.assertNotIn(moved, tp.worktrees(self.main))
        line = os.path.join(moved, ".tezgah", "research", "delta")
        os.makedirs(line)
        with open(os.path.join(line, "state.json"), "w") as fh:
            json.dump({"question": "q", "phase": "inner"}, fh)
        rows = tr.across(moved)
        self.assertIn(moved + " (this checkout)", rows)
        self.assertTrue(any(r.startswith("  delta: ") for r in rows), rows)

    def test_research_all_renders_every_checkouts_lines(self):
        for checkout, slug, phase in ((self.main, "alpha", "concluded"),
                                      (self.outside, "beta", "inner")):
            line = os.path.join(checkout, ".tezgah", "research", slug)
            os.makedirs(line)
            with open(os.path.join(line, "state.json"), "w") as fh:
                json.dump({"question": "q", "phase": phase}, fh)
        proc = subprocess.run([sys.executable, RESEARCH, "--all"], cwd=self.outside,
                              capture_output=True, text=True,
                              env=self.env(extra={"TEZGAH_ROOTS": self.roots}))
        self.assertEqual(proc.returncode, 0, proc.stderr)
        rows = proc.stdout.splitlines()
        self.assertEqual(rows[0], self.main)
        self.assertEqual(rows[1].split(" - ")[0], "  alpha: concluded")
        self.assertIn(self.inside + ": no research line", rows)
        self.assertIn(self.outside + " (this checkout)", rows)
        beta = [r for r in rows if r.startswith("  beta: ")]
        self.assertEqual(len(beta), 1, rows)
        self.assertTrue(beta[0].startswith("  beta: inner - open: phase inner"), beta)


if __name__ == "__main__":
    unittest.main()
