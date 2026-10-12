"""The worktree bridge: a linked checkout is armed through its `.git` pointer,
its siblings are listed from `.git/worktrees/*/gitdir` - both without a git
fork - and every checkout of a repository shares the main checkout's `.tezgah`."""
import json
import os
import re
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
TASK = os.path.join(support.REPO, "bin", "tezgah-task")
RENDER = os.path.join(support.REPO, "skills", "plan-add", "render_table.py")


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

    def test_a_path_in_a_workspace_resolves_to_the_checkout_that_owns_it(self):
        """Plan 097 item 1: `.tezgah` keeps a git repository of its own, so the
        nearest `.git` above a path in it is the workspace. Every resolver
        answers the checkout around it, never `.tezgah` itself, at the top and
        in a subdirectory - which is what kept `<x>/.tezgah/.tezgah` from
        being written. A real clone kept inside the workspace stays its own."""
        import tezgah_task as tt
        for checkout in (self.main, self.inside):
            ws = os.path.join(checkout, ".tezgah")
            git("init", "-q", ws)
            deep = os.path.join(ws, "plans", "open")
            os.makedirs(deep)
            for where in (ws, deep):
                with self.no_fork:
                    self.assertEqual(tp._toplevel(where), checkout, where)
                    self.assertEqual(tp.project_top(where), checkout, where)
                    self.assertEqual(tt.repo_root(where, self.roots), checkout, where)
                    self.assertEqual(tt.main_repo(where), self.main, where)
                    self.assertEqual(tp.worktrees(where)[0], self.main, where)
        with self.no_fork:
            self.assertEqual(tp.linked_main(os.path.join(self.inside, ".tezgah")),
                             self.main)
        clone = os.path.join(self.main, ".tezgah", "scratch", "clone")
        os.makedirs(os.path.join(clone, ".git"))
        with self.no_fork:
            self.assertEqual(tp._toplevel(clone), clone)
            self.assertEqual(tp.project_top(clone), clone)
        # a plain project subdirectory is not a workspace and is left alone
        sub = os.path.join(self.main, "apps", "web")
        os.makedirs(sub)
        self.assertEqual(tp.project_top(sub), sub)

    def test_all_still_names_this_checkout_when_its_admin_entry_is_gone(self):
        """F4: a checkout git can no longer list (its admin entry removed, e.g.
        after an `mv`) is still this checkout and still shown."""
        import tezgah_research as tr
        moved = os.path.join(self.home, "moved")
        shutil.move(self.outside, moved)  # its admin entry still names the old path
        admin = os.path.join(self.main, ".git", "worktrees")
        pointers = []
        for name in os.listdir(admin):
            with open(os.path.join(admin, name, "gitdir"), encoding="utf-8") as fh:
                pointers.append(fh.read().strip())
        self.assertTrue(any(p.startswith(self.outside + os.sep) for p in pointers),
                        pointers)
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

    def test_a_worktree_session_reads_and_keeps_the_main_checkouts_workspace(self):
        """Plan 097: a session in a linked worktree saw neither the open plans
        nor the lessons (standing constraints) and got a `.tezgah` of its own,
        which `git worktree remove` deletes with whatever was written there."""
        os.makedirs(os.path.join(self.main, ".tezgah", "plans", "open"))
        with open(os.path.join(self.main, ".tezgah", "plans", "open", "001-a.md"), "w") as fh:
            fh.write("---\nid: 001\ntitle: alpha plan\nstatus: open\n---\n## Next\ngo\n")
        with open(os.path.join(self.main, ".tezgah", "lessons.md"), "w") as fh:
            fh.write("- Never push on red - MAIN-LESSON-1\n")
        out, proc = support.run_json(
            [support.PROBE_CONTEXT], {"fn": "context_for", "event": "session_start",
                                      "cwd": self.inside},
            env=self.env(extra={"TEZGAH_ROOTS": self.roots}))
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("MAIN-LESSON-1", out)
        self.assertIn("alpha plan", out)
        self.assertFalse(os.path.exists(os.path.join(self.inside, ".tezgah")))
        self.assertTrue(os.path.isdir(os.path.join(self.main, ".tezgah", ".git")))
        line = next(x for x in out.splitlines() if x.startswith("Worktrees:"))
        self.assertIn("%s (this checkout, uses the main checkout's `.tezgah`)"
                      % self.inside, line)

    def test_research_init_in_a_worktree_survives_its_removal(self):
        """Plan 097: `init` in a worktree wrote the line into that worktree's
        `.tezgah`, and a plain `git worktree remove` deleted it."""
        env = self.env(extra={"TEZGAH_ROOTS": self.roots})
        # the project ignores its workspace, as `ensure_workspace` sets it up
        with open(os.path.join(self.inside, ".gitignore"), "w") as fh:
            fh.write("".join(line + "\n" for line in tp.WORKSPACE_IGNORES))
        git("-C", self.inside, "add", ".gitignore")
        git("-C", self.inside, "-c", "user.email=a@b", "-c", "user.name=t",
            "commit", "-qm", "ignore")
        proc = subprocess.run([sys.executable, RESEARCH, "init", "wt-line", "--ask", "q"],
                              cwd=self.inside, capture_output=True, text=True, env=env)
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        git("-C", self.main, "worktree", "remove", self.inside)
        line = os.path.join(self.main, ".tezgah", "research", "open", "wt-line")
        self.assertTrue(os.path.isfile(os.path.join(line, "state.json")), proc.stdout)

    def test_a_worktree_workspace_left_from_before_is_named_with_its_import(self):
        import tezgah_context as tc
        line = os.path.join(self.outside, ".tezgah", "research", "open", "old")
        os.makedirs(line)
        with open(os.path.join(line, "state.json"), "w") as fh:
            json.dump({"question": "q", "phase": "inner"}, fh)
        text = tc.sibling_line(self.main)
        self.assertIn("%s (its own `.tezgah` still holds research, which `git worktree "
                      "remove` deletes: move each research line with" % self.outside, text)
        self.assertIn("import %s <slug>" % self.outside, text)
        self.assertIn("(lines: old)", text)
        self.assertIn("%s (this checkout, " % self.main, text)

    def test_a_worktree_linking_the_main_workspace_is_no_alarm(self):
        # review of plan 097, F3: a worktree whose `.tezgah` is a link to the main
        # checkout's was named as holding data `git worktree remove` deletes
        import tezgah_context as tc
        line = os.path.join(self.main, ".tezgah", "research", "open", "old")
        os.makedirs(line)
        with open(os.path.join(line, "state.json"), "w") as fh:
            json.dump({"question": "q", "phase": "inner"}, fh)
        os.symlink(os.path.join(self.main, ".tezgah"), os.path.join(self.outside, ".tezgah"))
        text = tc.sibling_line(self.main)
        self.assertIn("%s (uses the main checkout's `.tezgah`)" % self.outside, text)
        self.assertNotIn("still holds", text)

    def test_lessons_and_design_derive_in_a_worktree_use_the_main_workspace(self):
        # review of plan 097, F4: both resolved a linked worktree to itself
        env = self.env(extra={"TEZGAH_ROOTS": self.roots})
        os.makedirs(os.path.join(self.main, ".tezgah"))
        with open(os.path.join(self.main, ".tezgah", "lessons.md"), "w") as fh:
            fh.write("Run the suite once - ran it twice\n")
        proc = subprocess.run([sys.executable, os.path.join(support.REPO, "bin",
                                                            "tezgah-lessons")],
                              cwd=self.inside, capture_output=True, text=True, env=env)
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        self.assertIn("Proposals for %s" % os.path.join(self.main, ".tezgah", "lessons.md"),
                      proc.stdout)
        styles = os.path.join(self.inside, "app", "styles")
        os.makedirs(styles)
        with open(os.path.join(styles, "tokens.css"), "w") as fh:
            fh.write(":root {\n  --color-text: #111111;\n  --space-unit: 4px;\n}\n")
        proc = subprocess.run([sys.executable, os.path.join(support.REPO, "bin",
                                                            "tezgah-design"),
                               "derive", "--repo", self.inside],
                              cwd=self.inside, capture_output=True, text=True, env=env)
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        self.assertTrue(os.path.isfile(os.path.join(self.main, ".tezgah",
                                                    "design-contract.md")), proc.stdout)
        self.assertFalse(os.path.exists(os.path.join(self.inside, ".tezgah")))
        # review of plan 097, N1: the line names where the contract is, and the
        # `check --contract .tezgah/design-contract.md` the Stop refusal and the
        # reviewer prompt name finds it from the worktree too
        contract = os.path.join(self.main, ".tezgah", "design-contract.md")
        self.assertIn("wrote %s " % contract, proc.stdout)
        proc = subprocess.run([sys.executable, os.path.join(support.REPO, "bin",
                                                            "tezgah-design"),
                               "derive", "--repo", self.inside],
                              cwd=self.inside, capture_output=True, text=True, env=env)
        self.assertIn("already exists at %s:" % contract, proc.stderr)
        measured = os.path.join(self.home, "measured.json")
        with open(measured, "w") as fh:
            json.dump({"components": [{"name": "Button", "kind": "interactive",
                                       "states": [], "styles": {}}]}, fh)
        proc = subprocess.run([sys.executable, os.path.join(support.REPO, "bin",
                                                            "tezgah-design"),
                               "check", "--contract", ".tezgah/design-contract.md",
                               "--measured", measured],
                              cwd=self.inside, capture_output=True, text=True, env=env)
        self.assertNotIn("cannot read the contract", proc.stderr)
        self.assertNotEqual(proc.returncode, 2, proc.stdout + proc.stderr)


class BareRepository(TempHome):
    """Plan 097, final pass: the worktrees of a bare repository have no main
    checkout, so each one took its own `.tezgah` - plans one worktree opened were
    no task in another, and a research line went with `git worktree remove`. The
    worktree on the bare repository's HEAD branch stands in for the main one."""

    def setUp(self):
        super().setUp()
        src = self.make_repo("src")
        git("init", "-q", "-b", "main", src)
        git("-C", src, "-c", "user.email=a@b", "-c", "user.name=t",
            "commit", "-q", "--allow-empty", "-m", "x")
        self.bare = os.path.join(self.roots, "app.git")
        git("clone", "-q", "--bare", src, self.bare)
        self.main = os.path.join(self.roots, "app-main")
        self.feature = os.path.join(self.roots, "app-feature")
        git("-C", self.bare, "worktree", "add", "-q", self.main, "main")
        git("-C", self.bare, "worktree", "add", "-q", "-b", "feature", self.feature)
        self.main, self.feature = map(os.path.realpath, (self.main, self.feature))
        patch = mock.patch.dict(os.environ, {"TEZGAH_ROOTS": self.roots})
        patch.start()
        self.addCleanup(patch.stop)

    def test_the_head_branch_worktree_holds_the_workspace(self):
        with mock.patch("subprocess.Popen", side_effect=AssertionError("git forked")):
            self.assertEqual(tp.linked_main(self.feature), self.main)
            self.assertIsNone(tp.linked_main(self.main))
            for checkout in (self.main, self.feature):
                self.assertEqual(tp.worktrees(checkout), [self.main, self.feature], checkout)
        proc = subprocess.run([sys.executable, RESEARCH, "init", "bare-line", "--ask", "q"],
                              cwd=self.feature, capture_output=True, text=True,
                              env=self.env(extra={"TEZGAH_ROOTS": self.roots}))
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        self.assertTrue(os.path.isdir(os.path.join(
            self.main, ".tezgah", "research", "open", "bare-line")), proc.stdout)
        self.assertFalse(os.path.exists(os.path.join(self.feature, ".tezgah")))

    def test_no_worktree_on_the_head_branch_keeps_each_its_own(self):
        git("-C", self.bare, "worktree", "remove", self.main)
        self.assertIsNone(tp.linked_main(self.feature))
        self.assertEqual(tp.worktrees(self.feature), [])



class InsideWorkspace(TempHome):
    """Plan 097 item 1: a command or a session whose cwd is inside `.tezgah` -
    its own git repository - works on the project and never writes a `.tezgah`,
    `.cursor`, `.opencode` or `.gitignore` inside `.tezgah`. AdSentinel's
    `.tezgah/.tezgah/plans/README.md` was the empty table `render_table` wrote
    one minute after a workspace commit; this repository's `.tezgah` held
    tezgah-managed `.cursor/agents` and the workspace `.gitignore` lines."""

    GIT = {"GIT_CONFIG_GLOBAL": os.devnull, "GIT_CONFIG_SYSTEM": os.devnull}

    def git(self, *args):
        subprocess.run(["git"] + list(args), check=True, capture_output=True,
                       env=dict(os.environ, **self.GIT))

    def setUp(self):
        super().setUp()
        self.repo = self.make_repo()
        self.git("init", "-q", self.repo)
        with open(os.path.join(self.repo, ".gitignore"), "w") as fh:
            fh.write("/.tezgah/\n")
        self.git("-C", self.repo, "add", ".gitignore")
        self.git("-C", self.repo, "-c", "user.name=t", "-c", "user.email=t@localhost",
                 "commit", "-qm", "init")
        self.ws = os.path.join(self.repo, ".tezgah")
        self.git("init", "-q", self.ws)
        self.open = os.path.join(self.ws, "plans", "open")
        os.makedirs(self.open)
        with open(os.path.join(self.open, "001-first.md"), "w") as fh:
            fh.write("---\nid: 001\ntitle: first plan\nstatus: open\n---\n## Goal\ng\n")
        self.wt = os.path.join(self.home, "wt-001")
        self.git("-C", self.repo, "worktree", "add", "-q", "-b", "plan/001-first", self.wt)
        self.wt = os.path.realpath(self.wt)

    def strays(self):
        """Every path tezgah must never create inside a workspace."""
        return [os.path.join(d, n) for d in (self.ws, os.path.join(self.wt, ".tezgah"))
                for n in (".tezgah", ".cursor", ".opencode", ".codegraph", ".gitignore")
                if os.path.lexists(os.path.join(d, n))]

    def test_render_table_writes_the_projects_table_from_every_cwd(self):
        readme = os.path.join(self.ws, "plans", "README.md")
        for cwd in (self.ws, self.open, self.wt):
            if os.path.exists(readme):
                os.remove(readme)
            proc = support.run([RENDER], env=self.env(extra={"PYTHONPATH": ""}), cwd=cwd)
            self.assertEqual(proc.returncode, 0, proc.stderr)
            self.assertEqual(self.strays(), [], cwd)
            with open(readme, encoding="utf-8") as fh:
                self.assertIn("| 001 | first plan |", fh.read(), cwd)

    def test_the_cli_closes_the_projects_plan_from_inside_the_workspace(self):
        proc = support.run([TASK, "close", "001", "discarded"], env=self.env(),
                           cwd=self.open)
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        self.assertTrue(os.path.isfile(os.path.join(self.ws, "plans", "done",
                                                    "001-first.md")))
        self.assertEqual(self.strays(), [])

    def test_a_session_started_inside_the_workspace_sets_up_the_project(self):
        for d in (".cursor", os.path.join(".config", "opencode")):
            os.makedirs(os.path.join(self.home, d), exist_ok=True)
        env = self.env(extra={"TEZGAH_CODEGRAPH_BIN": sys.executable})
        for cwd in (self.ws, self.open):
            out, proc = support.run_json([support.PROBE_CONTEXT],
                                         {"fn": "context_for", "event": "session_start",
                                          "cwd": cwd}, env=env)
            self.assertEqual(proc.returncode, 0, proc.stderr)
            self.assertEqual(self.strays(), [], cwd)
        # the project got what the workspace must not: its agents, its ignore
        # lines and the index worker's log under the project's own slug
        self.assertTrue(os.path.isfile(os.path.join(
            self.repo, ".cursor", "agents", "tezgah-cheap.md")))
        with open(os.path.join(self.repo, ".gitignore"), encoding="utf-8") as fh:
            self.assertIn("/.codegraph/", fh.read())
        logs = {n for _, _, names in os.walk(self.home) for n in names}

        def slug(p):
            return re.sub(r"[^A-Za-z0-9]+", "-", p).strip("-") + ".log"
        self.assertIn(slug(self.repo), logs)
        self.assertNotIn(slug(self.ws), logs)


if __name__ == "__main__":
    unittest.main()
