"""hooks/tezgah_index.py (auto-index worker) and bin/tezgah-index.

The worker is spawned detached; its CLI is called by the opencode plugin on the
first message of a session. Both are exercised here with a fake codegraph CLI, so
no real index is built.
"""
import fcntl
import os
import re
import subprocess
import sys
import time
import unittest

import support
from support import TempHome

sys.path.insert(0, os.path.join(support.REPO, "hooks"))
import tezgah_index as worker  # noqa: E402

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WORKER = os.path.join(REPO, "hooks", "tezgah_index.py")
CLI = os.path.join(REPO, "bin", "tezgah-index")
LAUNCHER = os.path.join(REPO, "bin", "tezgah-dsh")

# a stand-in for codegraph: logs every call it is asked to run, and fails the
# first FAKE_GRAPH_FAILS calls so the worker's retry can be exercised
FAKE = """#!/usr/bin/env python3
import os, sys
with open(os.environ["FAKE_GRAPH_LOG"], "a") as fh:
    fh.write(" ".join(sys.argv[1:]) + "\\n")
path = os.environ["FAKE_GRAPH_COUNTER"]
n = int(open(path).read()) if os.path.exists(path) else 0
with open(path, "w") as fh:
    fh.write(str(n + 1))
sys.exit(1 if n < int(os.environ.get("FAKE_GRAPH_FAILS", "0")) else 0)
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
        self.binary = os.path.join(self.home, "fake-codegraph")
        with open(self.binary, "w") as fh:
            fh.write(FAKE)
        os.chmod(self.binary, 0o755)

    def run_worker(self, fails=0, retries=5):
        env = self.env(extra={
            "FAKE_GRAPH_LOG": self.log,
            "FAKE_GRAPH_COUNTER": self.counter,
            "FAKE_GRAPH_FAILS": str(fails),
            "TEZGAH_INDEX_RETRIES": str(retries),
            "TEZGAH_INDEX_RETRY_DELAY": "0",
        })
        return subprocess.run(
            [sys.executable, WORKER, self.binary, self.repo, self.head,
             self.stamp, self.lock],
            capture_output=True, text=True, env=env, timeout=30)

    def codegraph_index(self):
        """Give the repo the index a project codegraph has already seen carries."""
        path = os.path.join(self.repo, ".codegraph", "codegraph.db")
        os.makedirs(os.path.dirname(path), exist_ok=True)
        open(path, "w").close()

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

    def test_a_project_it_has_not_seen_takes_init(self):
        # `init` is non-interactive because a detached worker cannot answer a
        # prompt, and codegraph has no daemon to warm first.
        proc = self.run_worker()
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(self.calls(), ["init %s -y" % self.repo])

    def test_retries_transient_failures_then_stamps(self):
        proc = self.run_worker(fails=2, retries=5)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertTrue(os.path.exists(self.stamp))
        self.assertEqual(len([c for c in self.calls() if c.startswith("init ")]), 3)

    def test_gives_up_without_stamp_and_leaves_a_failure_marker(self):
        proc = self.run_worker(fails=99, retries=2)
        self.assertEqual(proc.returncode, 1)
        self.assertFalse(os.path.exists(self.stamp))
        self.assertTrue(os.path.exists(self.stamp + ".failed"))
        with open(self.stamp + ".failed") as fh:
            self.assertIn("codegraph index failed after 2 attempt", fh.read())

    def test_success_clears_a_stale_failure_marker(self):
        with open(self.stamp + ".failed", "w") as fh:
            fh.write("old\n")
        proc = self.run_worker()
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertFalse(os.path.exists(self.stamp + ".failed"))

    def test_a_hung_attempt_is_killed_with_its_whole_group(self):
        # The bound has to take the tree, not the child: `subprocess.run(
        # timeout=)` kills the direct process only, so a codegraph that starts a
        # helper and then hangs would leave the helper running and hold this
        # repo's flock past the timeout. The child here is its own session
        # leader, so its pid IS its process group, and the group must be gone.
        pidfile = os.path.join(self.home, "pid")
        rc = worker.run_bounded(
            ["sh", "-c", "echo $$ > %s; sleep 60" % pidfile], timeout=1)
        self.assertNotEqual(rc, 0, "a timed-out attempt must report failure")
        with open(pidfile, encoding="utf-8") as fh:
            pid = int(fh.read().strip())
        with self.assertRaises(ProcessLookupError):
            os.killpg(pid, 0)

    def test_an_attempt_that_finishes_is_not_killed(self):
        self.assertEqual(worker.run_bounded(["true"], timeout=30), 0)

    def test_lock_held_skips_indexing(self):
        os.makedirs(os.path.dirname(self.lock), exist_ok=True)
        held = open(self.lock, "w")
        fcntl.flock(held, fcntl.LOCK_EX | fcntl.LOCK_NB)
        self.addCleanup(held.close)
        proc = self.run_worker()
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertFalse(os.path.exists(self.stamp))
        self.assertEqual(self.calls(), [])  # the CLI was never invoked

    def test_an_indexed_project_takes_the_incremental_sync(self):
        # Same lock, retry and stamp as the first index - only the command
        # differs: codegraph is incremental once the project has an index.
        self.codegraph_index()
        proc = self.run_worker()
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(self.calls(), ["sync %s" % self.repo])


class IndexCli(TempHome):
    """bin/tezgah-index: what every host's SessionStart hook, and the opencode
    plugin, reach autoindex() through. Each case pins the environment so the fake
    codegraph below is the only indexer the hook can find."""

    def setUp(self):
        super().setUp()
        self.log = os.path.join(self.home, "calls.log")
        self.fake = os.path.join(self.home, "fake-codegraph")
        with open(self.fake, "w") as fh:
            fh.write(FAKE)
        os.chmod(self.fake, 0o755)

    def env_for(self, extra=None):
        base = {
            "TEZGAH_CODEGRAPH_BIN": self.fake,
            "FAKE_GRAPH_LOG": self.log,
            "FAKE_GRAPH_COUNTER": os.path.join(self.home, "counter"),
            "FAKE_GRAPH_FAILS": "0",
            "TEZGAH_INDEX_RETRIES": "3",
            "TEZGAH_INDEX_RETRY_DELAY": "0",
        }
        base.update(extra or {})
        return self.env(extra=base)

    def run_cli(self, *args, env=None):
        return subprocess.run([sys.executable, CLI] + list(args),
                              capture_output=True, text=True,
                              env=env or self.env_for(), timeout=30)

    def test_help_prints_usage_and_starts_no_index(self):
        # --help used to be taken as PATH: the run printed the index status and
        # spawned the auto-index worker for a directory that does not exist.
        proc = self.run_cli("--help")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("tezgah-index [PATH]", proc.stdout)
        self.assertFalse(os.path.exists(self.log), "an index worker was spawned anyway")

    def test_outside_roots_is_silent(self):
        proc = self.run_cli(self.home, env=self.env())
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(proc.stdout.strip(), "")

    def test_inside_roots_spawns_the_index(self):
        repo = self.make_repo("proj")
        stamp = os.path.join(self.home, ".cache", "tezgah",
                             support.slug(os.path.realpath(repo)))
        proc = self.run_cli(repo)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        deadline = time.time() + 10
        while time.time() < deadline and not os.path.exists(stamp):
            time.sleep(0.1)
        self.assertTrue(os.path.exists(stamp), "auto-index did not stamp HEAD")

    def test_sandboxed_hook_reports_instead_of_spawning(self):
        # codegraph writes its index INSIDE the repo, so a hook whose workspace
        # is not writable (a sandboxed host, dsh workspace-write) cannot build
        # it: report that, do not spawn a worker that is going to fail.
        repo = self.make_repo("proj")
        os.chmod(repo, 0o555)
        self.addCleanup(os.chmod, repo, 0o755)
        proc = self.run_cli(repo)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("sandboxed", proc.stdout)
        self.assertFalse(os.path.exists(self.log), "a worker was spawned anyway")

    def test_reports_a_previous_failure_then_retries(self):
        repo = self.make_repo("proj")
        stamp = os.path.join(self.home, ".cache", "tezgah",
                             support.slug(os.path.realpath(repo)))
        os.makedirs(os.path.dirname(stamp), exist_ok=True)
        with open(stamp + ".failed", "w") as fh:
            fh.write("boom\n")
        proc = self.run_cli(repo, env=self.env_for({"TEZGAH_INDEX_RETRIES": "1"}))
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("last auto-index failed", proc.stdout)
        # the note exists for whoever has just been told the graph is stale, so
        # the path it names has to be a readable file: the cache dir also holds
        # stamps and locks named after the same slug
        named = re.search(r"\(see ([^)]+)\)", proc.stdout)
        self.assertIsNotNone(named, proc.stdout)
        self.assertTrue(os.path.isfile(named.group(1)),
                        "the note names %s, which is not a file" % named.group(1))

    def test_opencode_plugin_triggers_the_index(self):
        with open(os.path.join(REPO, "hosts", "opencode", "plugins",
                               "tezgah.js")) as fh:
            text = fh.read()
        self.assertIn('"chat.message"', text)
        self.assertIn("tezgah-index", text)


class DshLauncher(TempHome):
    """The dsh launcher warms the graph index before dsh boots, so a repo dsh has
    never seen is already being indexed when its first session starts - the
    auto-index has to run outside dsh's own sandbox."""

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
