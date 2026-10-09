"""The workspace's committer identity.

Two rules, both permanent because the same mistake was made twice: tezgah must
never commit under a name it invented, and a workspace created on a machine with
no global git identity must still commit as the person whose code it is. The
first is a scan over what ships, the second an end-to-end commit in a temp repo.
"""
import os
import re
import subprocess
import sys
import tempfile
import unittest

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO, "hooks"))
import tezgah_paths as tp  # noqa: E402

# A name tezgah invented and must never write again, and the argv shape that
# wrote it. Both are checked wherever a commit command can live.
FABRICATED = re.compile(r"tezgah@localhost|user\.name=tezgah|"
                        r"-c\s+user\.(?:name|email)=")
SCANNED = ("hooks", "bin", "hosts", "skills", "docs", "statusline.py")


def shipped_files():
    for entry in SCANNED:
        path = os.path.join(REPO, entry)
        if os.path.isfile(path):
            yield path
            continue
        for root, dirs, names in os.walk(path):
            dirs[:] = [d for d in dirs if d not in (".git", "__pycache__", "node_modules")]
            for name in names:
                if name.endswith((".pyc", ".db", ".json")) or name == "MANIFEST":
                    continue
                yield os.path.join(root, name)


class NoFabricatedIdentity(unittest.TestCase):
    def test_nothing_shipped_forces_a_committer_identity(self):
        offenders = []
        for path in shipped_files():
            try:
                with open(path, encoding="utf-8", errors="replace") as fh:
                    for n, line in enumerate(fh, 1):
                        if FABRICATED.search(line):
                            offenders.append("%s:%d: %s" % (
                                os.path.relpath(path, REPO), n, line.strip()[:90]))
            except OSError:
                continue
        self.assertEqual(offenders, [], "a commit must carry the repository's own "
                                        "identity, never one tezgah invents:\n" +
                                        "\n".join(offenders))

    def test_the_only_git_override_is_the_signing_agent(self):
        # the identity overrides are gone; what stays is what a hook must not
        # wait on, and it is pinned so a re-added `-c user.*` fails the scan above
        self.assertNotIn("user.name", " ".join(tp.WS_IDENTITY))
        self.assertIn("commit.gpgsign=false", tp.WS_IDENTITY)


class WorkspaceIdentity(unittest.TestCase):
    def setUp(self):
        self.repo = tempfile.mkdtemp()
        subprocess.run(["git", "init", "-q", self.repo], check=True)
        self.email = "owner@example.test"
        subprocess.run(["git", "-C", self.repo, "config", "user.name", "Owner"],
                       check=True)
        subprocess.run(["git", "-C", self.repo, "config", "user.email", self.email],
                       check=True)

    def commit_as(self, key, value, expect):
        subprocess.run(["git", "-C", self.repo, "config", key, value], check=True)
        ws = tp.ensure_workspace(self.repo)
        self.assertIsNotNone(ws, "the workspace was not created")
        proc = tp.ws_git(self.repo, "commit", "--allow-empty", "-m", "note")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        got = subprocess.run(["git", "-C", ws, "log", "-1", "--format=%ae"],
                             capture_output=True, text=True).stdout.strip()
        self.assertEqual(got, expect)

    def test_a_new_workspace_commits_as_the_project_identity(self):
        self.commit_as("user.email", self.email, self.email)

    def test_the_project_value_wins_over_an_older_workspace_value(self):
        # a workspace that already exists keeps what it has: the copy happens at
        # creation, and a later project change is the user's to make in both
        ws = tp.ensure_workspace(self.repo)
        subprocess.run(["git", "-C", ws, "config", "user.email", "first@example.test"],
                       check=True)
        subprocess.run(["git", "-C", self.repo, "config", "user.email", "second@example.test"],
                       check=True)
        tp.ws_git(self.repo, "commit", "--allow-empty", "-m", "note")
        got = subprocess.run(["git", "-C", ws, "log", "-1", "--format=%ae"],
                             capture_output=True, text=True).stdout.strip()
        self.assertEqual(got, "first@example.test")


if __name__ == "__main__":
    unittest.main()
