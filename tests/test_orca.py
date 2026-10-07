"""hooks/tezgah_orca.py: an Orca session is detected from its env, the session
is told to use Orca for worktrees and terminals, and the status surfaces read
Orca's own listing. No real Orca runs here: the CLI is a fake on disk and every
ORCA_* marker is a fixture (support.py strips the developer's own)."""
import json
import os
import subprocess
import sys
import tempfile
import unittest

import support
from support import TempHome, run_json

sys.path.insert(0, support.HOOKS)
import tezgah_orca  # noqa: E402

# A fake `orca` that answers `worktree ps --json` and `status --json` with the
# shape the real 1.4.222 CLI prints (trimmed to the keys tezgah reads).
FAKE = r'''#!%s
import json, os, sys
args = sys.argv[1:]
if args[:2] == ["worktree", "ps"]:
    out = {"worktrees": [
        {"path": os.environ["FAKE_MAIN"], "displayName": "main",
         "workspaceStatus": "in-progress", "status": "active",
         "liveTerminalCount": 2, "isMainWorktree": True,
         "agents": [{"agentType": "omp", "state": "working"}]},
        {"path": "/elsewhere/other-repo", "displayName": "x",
         "liveTerminalCount": 1, "agents": []}]}
elif args[:1] == ["status"]:
    out = {"app": {"running": True}, "runtime": {"reachable": True,
                                                 "appVersion": "9.9.9"}}
else:
    sys.exit(3)
print(json.dumps({"id": "t", "ok": True, "result": out}))
''' % sys.executable

STATUS = os.path.join(support.REPO, "bin", "tezgah-status.py")
SETUP = os.path.join(support.REPO, "bin", "tezgah-setup.py")


class Detect(unittest.TestCase):
    def test_no_marker_is_no_session(self):
        self.assertIsNone(tezgah_orca.session({}))
        self.assertIsNone(tezgah_orca.session({"TERM_PROGRAM": "iTerm.app"}))

    def test_the_worktree_and_terminal_come_from_orca_env(self):
        got = tezgah_orca.session({
            "ORCA_WORKTREE_ID": "55f3::/Users/me/Projects/repo",
            "ORCA_TERMINAL_HANDLE": "term_1", "ORCA_APP_VERSION": "1.4.221"})
        self.assertEqual(got["worktree"], "/Users/me/Projects/repo")
        self.assertEqual(got["terminal"], "term_1")
        self.assertEqual(got["version"], "1.4.221")

    def test_orca_term_program_alone_is_a_session(self):
        self.assertIsNotNone(tezgah_orca.session({"TERM_PROGRAM": "Orca"}))

    def test_cli_resolution_order(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        exe = os.path.join(tmp.name, "orca")
        with open(exe, "w") as fh:
            fh.write("#!/bin/sh\n")
        os.chmod(exe, 0o755)
        # the WSL wrapper Orca exports wins, split like a shell would
        self.assertEqual(tezgah_orca.cli({"ORCA_CLI_COMMAND": "wsl.exe orca",
                                          "ORCA_CLI_BIN_DIR": tmp.name}),
                         ["wsl.exe", "orca"])
        self.assertEqual(tezgah_orca.cli({"ORCA_CLI_BIN_DIR": tmp.name}), [exe])
        # outside an Orca terminal on Linux a bare `orca` is the GNOME screen
        # reader: never resolve it there
        self.assertIsNone(tezgah_orca.cli({"PATH": tmp.name}, platform="linux"))
        self.assertEqual(tezgah_orca.cli({"PATH": tmp.name, "TERM_PROGRAM": "Orca"},
                                         platform="linux"), [exe])
        # the override names one binary; a missing one is no CLI, not a fallback
        self.assertIsNone(tezgah_orca.cli({"TEZGAH_ORCA_BIN": "/no/such/orca",
                                           "ORCA_CLI_BIN_DIR": tmp.name}))


class Injected(TempHome):
    def call(self, extra):
        return run_json([support.PROBE_CONTEXT],
                        {"fn": "context_for", "event": "session_start",
                         "cwd": self.make_repo()},
                        env=self.env(extra=extra))

    def test_an_orca_session_is_told_to_use_orca_for_worktrees(self):
        out, proc = self.call({"ORCA_WORKTREE_ID": "r::/x/repo",
                               "ORCA_TERMINAL_HANDLE": "term_9"})
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("orca worktree create", out)
        self.assertIn("orca worktree ps --json", out)

    def test_outside_orca_nothing_is_said(self):
        out, proc = self.call({})
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertNotIn("orca worktree create", out)


class Tracking(TempHome):
    def setUp(self):
        super().setUp()
        self.repo = self.make_repo()
        bindir = os.path.join(self.home, "fake-orca")
        os.makedirs(bindir)
        fake = os.path.join(bindir, "orca")
        with open(fake, "w") as fh:
            fh.write(FAKE)
        os.chmod(fake, 0o755)
        self.extra = {"TEZGAH_ORCA_BIN": fake, "FAKE_MAIN": self.repo}

    def git(self, *args):
        subprocess.run(["git", "-C", self.repo] + list(args), check=True,
                       capture_output=True, env=self.env())

    def test_status_lists_this_repos_orca_worktrees_and_untracked_ones(self):
        linked = os.path.join(self.home, "linked")
        subprocess.run(["git", "init", "-q", self.repo], check=True)
        self.git("-c", "user.email=t@t.invalid", "-c", "user.name=t", "commit",
                 "-q", "--allow-empty", "-m", "init")
        self.git("worktree", "add", "-q", linked)
        proc = subprocess.run([sys.executable, STATUS, "--orca", "--json", self.repo],
                              capture_output=True, text=True,
                              env=self.env(extra=self.extra))
        self.assertEqual(proc.returncode, 0, proc.stderr)
        got = json.loads(proc.stdout)
        self.assertEqual([w["path"] for w in got["tracked"]], [self.repo])
        self.assertEqual(got["tracked"][0]["terminals"], 2)
        self.assertEqual(got["tracked"][0]["agents"], ["omp:working"])
        self.assertEqual(got["untracked"], [os.path.realpath(linked)])

    def test_status_says_when_orca_is_absent(self):
        env = self.env(extra={"TEZGAH_ORCA_BIN": os.path.join(self.home, "none")})
        proc = subprocess.run([sys.executable, STATUS, "--orca", self.repo],
                              capture_output=True, text=True, env=env)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("orca CLI not found", proc.stdout)

    def test_setup_status_reports_orca_and_its_codex_home(self):
        codex = os.path.join(self.home, "orca-codex-home")
        os.makedirs(codex)
        with open(os.path.join(codex, ".orca-managed-home"), "w") as fh:
            fh.write("acct\n")
        env = self.env(extra=dict(self.extra, CODEX_HOME=codex,
                                  ORCA_WORKTREE_ID="r::" + self.repo))
        proc = subprocess.run([sys.executable, SETUP, "--status", self.repo],
                              capture_output=True, text=True, env=env)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        line = [ln for ln in proc.stdout.splitlines() if ln.startswith("orca:")]
        self.assertEqual(len(line), 1, proc.stdout)
        self.assertIn("9.9.9", line[0])
        self.assertIn("this shell runs in an Orca terminal", line[0])
        self.assertIn("Orca-managed codex home", line[0])


if __name__ == "__main__":
    unittest.main()
