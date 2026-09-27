"""bin/tezgah-migrate: legacy tezgah state moved into <repo>/.tezgah.

Every fixture is a throwaway git repository under a temp HOME, and the CLI runs
in a subprocess the way a person runs it. The assertions read the result from
disk, from the project's git index and from the backup tarball - never from what
the CLI printed.
"""
import os
import subprocess
import tarfile
import unittest

import support
from support import TempHome

CLI = os.path.join(support.REPO, "bin", "tezgah-migrate")
GIT_ENV = {"GIT_CONFIG_GLOBAL": os.devnull, "GIT_CONFIG_SYSTEM": os.devnull,
           "GIT_TERMINAL_PROMPT": "0"}


def write(path, text):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(text)


def read(path):
    with open(path, encoding="utf-8") as fh:
        return fh.read()


class Migrate(TempHome):

    def env(self, roots=None, extra=None):
        return super().env(roots, dict(GIT_ENV, **(extra or {})))

    def git(self, repo, *args):
        out = subprocess.run(["git", "-C", repo, "-c", "user.name=t", "-c", "user.email=t@t"]
                             + list(args), capture_output=True, text=True,
                             env=dict(os.environ, **GIT_ENV))
        self.assertEqual(out.returncode, 0, out.stderr)
        return out.stdout

    def legacy_repo(self, name="repo"):
        """Every legacy shape at once: tracked .tezgah, tracked plans/ in plan
        format, untracked analysis/ and research/, and a CLAUDE.md that stays."""
        repo = self.make_repo(name)
        self.git(repo, "init", "-q")
        write(os.path.join(repo, ".gitignore"), "node_modules/\n")
        write(os.path.join(repo, ".tezgah", "lessons.md"), "- a lesson\n")
        write(os.path.join(repo, ".tezgah", "plans", "open", "009-new.md"), "new\n")
        write(os.path.join(repo, "plans", "README.md"), "old readme\n")
        write(os.path.join(repo, "plans", "open", "003-old.md"), "old plan\n")
        write(os.path.join(repo, "plans", "done", "001-first.md"), "done plan\n")
        write(os.path.join(repo, "CLAUDE.md"), "# House rules\nbody\n")
        write(os.path.join(repo, "src", "app.py"), "print(1)\n")
        self.git(repo, "add", "-A")
        self.git(repo, "commit", "-q", "-m", "legacy")
        write(os.path.join(repo, "analysis", "audit", "report.md"), "audit\n")
        write(os.path.join(repo, "research", "notes.md"), "notes\n")
        return repo

    def migrate(self, *args):
        return support.run([CLI] + list(args), env=self.env(), cwd=self.home)

    def tree(self, repo):
        """Every file under the repo except the project's own .git, with bytes."""
        found = {}
        for base, dirs, files in os.walk(repo):
            if base == repo:
                dirs[:] = [d for d in dirs if d != ".git"]
            for name in files:
                path = os.path.join(base, name)
                with open(path, "rb") as fh:
                    found[os.path.relpath(path, repo)] = fh.read()
        return found

    def backups(self):
        folder = os.path.join(self.home, ".config", "tezgah", "backups")
        return sorted(os.listdir(folder)) if os.path.isdir(folder) else []

    def test_a_dry_run_changes_nothing(self):
        repo = self.legacy_repo()
        before = (self.tree(repo), self.git(repo, "status", "--porcelain"),
                  self.git(repo, "ls-files"))
        proc = self.migrate("--repo", repo)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual((self.tree(repo), self.git(repo, "status", "--porcelain"),
                          self.git(repo, "ls-files")), before)
        self.assertEqual(self.backups(), [])

    def test_apply_moves_every_legacy_shape_into_the_workspace(self):
        repo = self.legacy_repo()
        head = self.git(repo, "rev-parse", "HEAD")
        proc = self.migrate("--apply", "--repo", repo)
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        tracked = self.git(repo, "ls-files").split()
        # 1: .tezgah is out of the project's index and still on disk
        self.assertFalse([p for p in tracked if p.startswith((".tezgah/", "plans/"))], tracked)
        self.assertEqual(read(os.path.join(repo, ".tezgah", "lessons.md")), "- a lesson\n")
        # 3, 4, 5: moved, sources gone
        self.assertEqual(read(os.path.join(repo, ".tezgah", "plans", "open", "003-old.md")),
                         "old plan\n")
        self.assertEqual(read(os.path.join(repo, ".tezgah", "plans", "done", "001-first.md")),
                         "done plan\n")
        self.assertEqual(read(os.path.join(repo, ".tezgah", "analysis", "audit", "report.md")),
                         "audit\n")
        self.assertEqual(read(os.path.join(repo, ".tezgah", "analysis", "imported-research",
                                           "notes.md")), "notes\n")
        for gone in ("analysis", "research", os.path.join("plans", "open")):
            self.assertFalse(os.path.exists(os.path.join(repo, gone)), gone)
        # 6: project knowledge stays and is indexed
        self.assertEqual(read(os.path.join(repo, "CLAUDE.md")), "# House rules\nbody\n")
        index = read(os.path.join(repo, ".tezgah", "analysis", "project-knowledge.md"))
        self.assertIn("CLAUDE.md", index)
        self.assertIn("House rules", index)
        # 2: ignored, private repo with one import commit naming the project head
        ignore = read(os.path.join(repo, ".gitignore")).splitlines()
        self.assertEqual(ignore[0], "node_modules/")
        self.assertIn("/.tezgah/", ignore)
        self.assertIn("/.codegraph/", ignore)
        ws = os.path.join(repo, ".tezgah")
        log = self.git(ws, "log", "--format=%s").splitlines()
        self.assertEqual(len(log), 1, log)
        self.assertIn(head[:7], log[0])
        self.assertIn("plans/open/003-old.md", self.git(ws, "ls-files"))
        # nothing committed in the project
        self.assertEqual(self.git(repo, "rev-parse", "HEAD"), head)

    def test_the_backup_holds_every_path_the_apply_moved_or_untracked(self):
        repo = self.legacy_repo()
        before = self.tree(repo)
        self.assertEqual(self.migrate("--apply", "--repo", repo).returncode, 0)
        [name] = self.backups()
        self.assertTrue(name.startswith("repo-"), name)
        with tarfile.open(os.path.join(self.home, ".config", "tezgah", "backups", name)) as tar:
            saved = {m.name: tar.extractfile(m).read() for m in tar.getmembers() if m.isfile()}
        after = self.tree(repo)
        # every file that left its path, or whose bytes changed, is in the backup as it was
        for rel, data in before.items():
            if after.get(rel) != data:
                self.assertEqual(saved.get(rel), data, rel)
        for rel in (".tezgah/lessons.md", "plans/README.md", "analysis/audit/report.md",
                    "research/notes.md", ".gitignore"):
            self.assertIn(rel, saved)

    def test_a_name_collision_is_skipped_and_the_source_stays(self):
        repo = self.legacy_repo()
        write(os.path.join(repo, ".tezgah", "plans", "README.md"), "new readme\n")
        write(os.path.join(repo, ".tezgah", "plans", "open", "003-old.md"), "old plan\n")
        self.assertEqual(self.migrate("--apply", "--repo", repo).returncode, 0)
        # differing content: both copies untouched
        self.assertEqual(read(os.path.join(repo, "plans", "README.md")), "old readme\n")
        self.assertEqual(read(os.path.join(repo, ".tezgah", "plans", "README.md")),
                         "new readme\n")
        self.assertIn("plans/README.md", self.git(repo, "ls-files"))
        # identical content: the duplicate source is dropped
        self.assertFalse(os.path.exists(os.path.join(repo, "plans", "open", "003-old.md")))
        self.assertTrue(os.path.exists(os.path.join(repo, ".tezgah", "plans", "done",
                                                    "001-first.md")))

    def test_a_second_apply_finds_nothing_to_do(self):
        repo = self.legacy_repo()
        self.assertEqual(self.migrate("--apply", "--repo", repo).returncode, 0)
        tree, status = self.tree(repo), self.git(repo, "status", "--porcelain")
        ws_log = self.git(os.path.join(repo, ".tezgah"), "log", "--format=%H")
        backups = self.backups()
        self.assertEqual(self.migrate("--apply", "--repo", repo).returncode, 0)
        self.assertEqual(self.tree(repo), tree)
        self.assertEqual(self.git(repo, "status", "--porcelain"), status)
        self.assertEqual(self.git(os.path.join(repo, ".tezgah"), "log", "--format=%H"), ws_log)
        self.assertEqual(self.backups(), backups)

    def test_discovery_skips_non_repos_the_tezgah_checkout_and_foreign_plans(self):
        plain = self.make_repo("plain")
        self.git(plain, "init", "-q")
        write(os.path.join(plain, "plans", "roadmap.txt"), "not tezgah plans\n")
        checkout = self.make_repo("tezgah")
        self.git(checkout, "init", "-q")
        write(os.path.join(checkout, "hooks", "tezgah_policy.py"), "")
        write(os.path.join(checkout, "plans", "open", "001-x.md"), "x\n")
        worktree = self.make_repo("worktree")
        write(os.path.join(worktree, ".git"), "gitdir: /nowhere\n")
        write(os.path.join(worktree, "analysis", "a.md"), "a\n")
        proc = self.migrate("--apply")
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        self.assertTrue(os.path.isdir(os.path.join(plain, ".tezgah", ".git")))
        self.assertEqual(read(os.path.join(plain, "plans", "roadmap.txt")), "not tezgah plans\n")
        self.assertFalse(os.path.exists(os.path.join(checkout, ".tezgah")))
        self.assertTrue(os.path.exists(os.path.join(checkout, "plans", "open", "001-x.md")))
        self.assertFalse(os.path.exists(os.path.join(worktree, ".tezgah")))
        self.assertTrue(os.path.exists(os.path.join(worktree, "analysis", "a.md")))


if __name__ == "__main__":
    unittest.main()
