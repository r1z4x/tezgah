"""hooks/tezgah_index.py (auto-index worker) and bin/tezgah-index.

The worker is spawned detached; its CLI is called by the opencode plugin on the
first message of a session. Both are exercised here with a fake codebase-memory
CLI, so no real index is built.
"""
import fcntl
import os
import subprocess
import sys
import time
import unittest

import support
from support import TempHome

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WORKER = os.path.join(REPO, "hooks", "tezgah_index.py")
CLI = os.path.join(REPO, "bin", "tezgah-index")
LAUNCHER = os.path.join(REPO, "bin", "tezgah-dsh")

# a stand-in for codebase-memory-mcp: logs every call, and fails the first
# FAKE_CBM_FAILS index calls so the worker's retry can be exercised
FAKE = """#!/usr/bin/env python3
import os, sys
with open(os.environ["FAKE_CBM_LOG"], "a") as fh:
    fh.write(" ".join(sys.argv[1:]) + "\\n")
if sys.argv[1:2] == ["daemon"]:
    sys.exit(0)
path = os.environ["FAKE_CBM_COUNTER"]
n = int(open(path).read()) if os.path.exists(path) else 0
with open(path, "w") as fh:
    fh.write(str(n + 1))
sys.exit(1 if n < int(os.environ.get("FAKE_CBM_FAILS", "0")) else 0)
"""


class IndexWorker(TempHome):
    def setUp(self):
        super().setUp()
        self.repo = self.make_repo("proj")
        self.head = "abc123"
        self.stamp = os.path.join(self.home, "stamp")
        self.lock = os.path.join(self.home, "locks", "proj.lock")
        self.counter = os.path.join(self.home, "counter")
        self.log = os.path.join(self.home, "calls.log")
        self.cbm = os.path.join(self.home, "fake-cbm")
        with open(self.cbm, "w") as fh:
            fh.write(FAKE)
        os.chmod(self.cbm, 0o755)

    def run_worker(self, fails=0, retries=5):
        env = self.env(extra={
            "FAKE_CBM_LOG": self.log,
            "FAKE_CBM_COUNTER": self.counter,
            "FAKE_CBM_FAILS": str(fails),
            "TEZGAH_INDEX_RETRIES": str(retries),
            "TEZGAH_INDEX_RETRY_DELAY": "0",
        })
        return subprocess.run(
            [sys.executable, WORKER, self.cbm, self.repo, self.head,
             self.stamp, self.lock],
            capture_output=True, text=True, env=env, timeout=30)

    def calls(self):
        try:
            with open(self.log) as fh:
                return fh.read().splitlines()
        except OSError:
            return []

    def test_success_stamps_head(self):
        proc = self.run_worker()
        self.assertEqual(proc.returncode, 0, proc.stderr)
        with open(self.stamp) as fh:
            self.assertEqual(fh.read(), self.head)
        self.assertTrue(any(c.startswith("daemon start") for c in self.calls()))
        self.assertTrue(any("index_repository" in c for c in self.calls()))

    def test_retries_transient_failures_then_stamps(self):
        proc = self.run_worker(fails=2, retries=5)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertTrue(os.path.exists(self.stamp))
        self.assertEqual(len([c for c in self.calls() if "index_repository" in c]), 3)

    def test_gives_up_without_stamp_and_leaves_a_failure_marker(self):
        proc = self.run_worker(fails=99, retries=2)
        self.assertEqual(proc.returncode, 1)
        self.assertFalse(os.path.exists(self.stamp))
        self.assertTrue(os.path.exists(self.stamp + ".failed"))
        with open(self.stamp + ".failed") as fh:
            self.assertIn("failed after 2 attempt", fh.read())

    def test_success_clears_a_stale_failure_marker(self):
        with open(self.stamp + ".failed", "w") as fh:
            fh.write("old\n")
        proc = self.run_worker()
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertFalse(os.path.exists(self.stamp + ".failed"))

    def test_lock_held_skips_indexing(self):
        os.makedirs(os.path.dirname(self.lock), exist_ok=True)
        held = open(self.lock, "w")
        fcntl.flock(held, fcntl.LOCK_EX | fcntl.LOCK_NB)
        self.addCleanup(held.close)
        proc = self.run_worker()
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertFalse(os.path.exists(self.stamp))
        self.assertEqual(self.calls(), [])  # the CLI was never invoked


class IndexCli(TempHome):
    def test_help_prints_usage_and_starts_no_index(self):
        # --help used to be taken as PATH: the run printed the index status and
        # spawned the auto-index worker for a directory that does not exist.
        fake = os.path.join(self.home, "fake-cbm")
        with open(fake, "w") as fh:
            fh.write(FAKE)
        os.chmod(fake, 0o755)
        log = os.path.join(self.home, "calls.log")
        env = self.env(extra={"TEZGAH_CBM_BIN": fake, "FAKE_CBM_LOG": log,
                              "FAKE_CBM_COUNTER": os.path.join(self.home, "counter")})
        proc = subprocess.run([sys.executable, CLI, "--help"], capture_output=True,
                              text=True, env=env, timeout=30)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("tezgah-index [PATH]", proc.stdout)
        self.assertFalse(os.path.exists(log), "an index worker was spawned anyway")

    def test_outside_roots_is_silent(self):
        proc = subprocess.run([sys.executable, CLI, self.home],
                              capture_output=True, text=True, env=self.env(),
                              timeout=30)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(proc.stdout.strip(), "")

    def test_inside_roots_spawns_the_index(self):
        repo = self.make_repo("proj")
        fake = os.path.join(self.home, "fake-cbm")
        with open(fake, "w") as fh:
            fh.write(FAKE)
        os.chmod(fake, 0o755)
        stamp = os.path.join(self.home, ".cache", "tezgah",
                             support.slug(os.path.realpath(repo)))
        env = self.env(extra={
            "TEZGAH_CBM_BIN": fake,
            "FAKE_CBM_LOG": os.path.join(self.home, "calls.log"),
            "FAKE_CBM_COUNTER": os.path.join(self.home, "counter"),
            "FAKE_CBM_FAILS": "0",
            "TEZGAH_INDEX_RETRIES": "3",
            "TEZGAH_INDEX_RETRY_DELAY": "0",
        })
        proc = subprocess.run([sys.executable, CLI, repo], capture_output=True,
                              text=True, env=env, timeout=30)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        deadline = time.time() + 10
        while time.time() < deadline and not os.path.exists(stamp):
            time.sleep(0.1)
        self.assertTrue(os.path.exists(stamp), "auto-index did not stamp HEAD")

    def test_sandboxed_hook_reports_instead_of_spawning(self):
        # a host that sandboxes hook writes (dsh workspace-write) cannot write
        # the cbm cache; the hook must say so, not spawn a doomed worker
        repo = self.make_repo("proj")
        fake = os.path.join(self.home, "fake-cbm")
        with open(fake, "w") as fh:
            fh.write(FAKE)
        os.chmod(fake, 0o755)
        cbm_cache = os.path.join(self.home, "cbm-cache-blocked")
        open(cbm_cache, "w").close()  # a file blocks the cache dir, like EPERM
        log = os.path.join(self.home, "calls.log")
        env = self.env(extra={
            "TEZGAH_CBM_BIN": fake,
            "CBM_CACHE_DIR": cbm_cache,
            "FAKE_CBM_LOG": log,
            "FAKE_CBM_COUNTER": os.path.join(self.home, "counter"),
        })
        proc = subprocess.run([sys.executable, CLI, repo], capture_output=True,
                              text=True, env=env, timeout=30)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("sandboxed", proc.stdout)
        self.assertFalse(os.path.exists(log), "a worker was spawned anyway")

    def test_reports_a_previous_failure_then_retries(self):
        repo = self.make_repo("proj")
        fake = os.path.join(self.home, "fake-cbm")
        with open(fake, "w") as fh:
            fh.write(FAKE)
        os.chmod(fake, 0o755)
        stamp = os.path.join(self.home, ".cache", "tezgah",
                             support.slug(os.path.realpath(repo)))
        os.makedirs(os.path.dirname(stamp), exist_ok=True)
        with open(stamp + ".failed", "w") as fh:
            fh.write("boom\n")
        env = self.env(extra={
            "TEZGAH_CBM_BIN": fake,
            "FAKE_CBM_LOG": os.path.join(self.home, "calls.log"),
            "FAKE_CBM_COUNTER": os.path.join(self.home, "counter"),
            "FAKE_CBM_FAILS": "0",
            "TEZGAH_INDEX_RETRIES": "1",
            "TEZGAH_INDEX_RETRY_DELAY": "0",
        })
        proc = subprocess.run([sys.executable, CLI, repo], capture_output=True,
                              text=True, env=env, timeout=30)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("last auto-index failed", proc.stdout)

    def test_opencode_plugin_triggers_the_index(self):
        with open(os.path.join(REPO, "hosts", "opencode", "plugins",
                               "tezgah.js")) as fh:
            text = fh.read()
        self.assertIn('"chat.message"', text)
        self.assertIn("tezgah-index", text)


class DshLauncher(TempHome):
    """The dsh launcher must warm the graph index OUTSIDE dsh's sandbox, so a
    repo dsh has never seen still gets indexed (the hook cannot write the cbm
    cache from inside the workspace-write sandbox)."""

    def fake(self, path, body):
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w") as fh:
            fh.write(body)
        os.chmod(path, 0o755)

    def test_launcher_warms_the_index_then_boots_dsh(self):
        self.fake(os.path.join(self.home, ".config", "tezgah", "bin",
                               "tezgah-index"),
                  '#!/bin/sh\necho "$@" >> "$IDX_LOG"\n')
        dsh_home = os.path.join(self.home, "dsh-home")
        self.fake(os.path.join(dsh_home, "profiles", "node_modules",
                               "@deepseek-ai", "dsh", "lib", "bin.js"),
                  'require("fs").appendFileSync(process.env.DSH_RUN_LOG,'
                  ' process.argv.slice(2).join(" ") + "\\n")\n')
        idx_log = os.path.join(self.home, "idx.log")
        dsh_log = os.path.join(self.home, "dsh.log")
        repo = self.make_repo("proj")
        env = self.env(extra={"DSH_HOME": dsh_home, "IDX_LOG": idx_log,
                              "DSH_RUN_LOG": dsh_log})
        proc = subprocess.run([LAUNCHER, "--profile", "web"], capture_output=True,
                              text=True, env=env, cwd=repo, timeout=60)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        with open(idx_log) as fh:
            self.assertIn(repo, fh.read())
        with open(dsh_log) as fh:
            self.assertIn("--profile web", fh.read())


if __name__ == "__main__":
    unittest.main()
