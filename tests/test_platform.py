"""The two shipped files that used to assume the host and the tree they run on.

`hooks/tezgah_index.py` imported `fcntl` at module level - the one hard POSIX
import left in shipped code - and `bin/tezgah-doctor` loaded the bench spike
unconditionally, so a tree that lost `benchmarks/` answered `--coverage` with a
traceback instead of a report. Each test reproduces the host that lacks the
thing: `fcntl` hidden from the import system, and a tree copied without
`benchmarks/`. Neither file may answer a missing capability with a traceback, and
the worker may not lose the work it can still do without a lock.
"""
import os
import shutil
import subprocess
import sys
import unittest

# `python3 -m unittest tests/test_platform.py` runs this file as `tests.<name>`
# and puts the *repository root* on sys.path, not tests/, so `support` - the
# suite's shared fixture - is only importable if its own directory is added. The
# suite is otherwise run with `discover -s tests`, where this is already true and
# the insert is a no-op.
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import support  # noqa: E402
from support import TempHome  # noqa: E402

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WORKER = os.path.join(REPO, "hooks", "tezgah_index.py")
DOCTOR = os.path.join(REPO, "bin", "tezgah-doctor")
HOOKS = os.path.join(REPO, "hooks")
# codegraph, and npx with it, are off PATH: a run that does reach the coverage
# rules still reports "could not read an index dump" instead of asking npm for a
# package over the network
BARE_PATH = "/usr/bin:/bin"

# Run the real worker with `fcntl` unimportable. `sys.modules[name] = None` is
# the import system's own "this module is not here" - `import fcntl` raises
# ImportError from it - so the worker's guard is what answers, with no mock of the
# module and no copy of the file under test.
HIDE_FCNTL = """\
import runpy, sys
worker = sys.argv[1]
sys.argv = sys.argv[1:]
sys.modules["fcntl"] = None
runpy.run_path(worker, run_name="__main__")
"""


class IndexLock(TempHome):
    """The worker's lock: exclusive where `fcntl` exists, named-and-unlocked
    where it does not."""

    # stands in for codegraph: exits 0 and records the argv it was asked to run,
    # so "it still indexed" is a call that happened and not only a stamp file
    STUB = '#!/bin/sh\nprintf "%s\\n" "$*" >> "$FAKE_GRAPH_LOG"\n'

    def setUp(self):
        super().setUp()
        self.repo = self.make_repo("proj")
        self.head = "abc123"
        self.stamp = os.path.join(self.home, "stamp")
        self.lock = os.path.join(self.home, "locks", "proj.lock")
        self.log = os.path.join(self.home, "calls.log")
        self.binary = os.path.join(self.home, "stub-codegraph")
        with open(self.binary, "w") as fh:
            fh.write(self.STUB)
        os.chmod(self.binary, 0o755)

    def run_worker(self, hide_fcntl):
        env = self.env(extra={"FAKE_GRAPH_LOG": self.log,
                              "TEZGAH_INDEX_RETRIES": "1",
                              "TEZGAH_INDEX_RETRY_DELAY": "0"})
        prefix = [sys.executable, "-c", HIDE_FCNTL] if hide_fcntl else [sys.executable]
        return subprocess.run(
            prefix + [WORKER, self.binary, self.repo, self.head, self.stamp,
                      self.lock],
            capture_output=True, text=True, env=env, timeout=30)

    def calls(self):
        with open(self.log) as fh:
            return fh.read().splitlines()

    def test_without_fcntl_it_indexes_unlocked_and_says_so(self):
        proc = self.run_worker(hide_fcntl=True)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        # the message names the repo and the condition, on the stream the parent
        # sends to the index log a session reports
        self.assertIn("no fcntl on this host", proc.stderr)
        self.assertIn(self.repo, proc.stderr)
        # and it is not a refusal: the run still indexed and stamped HEAD
        self.assertEqual(self.calls(), ["init %s -y" % self.repo])
        with open(self.stamp) as fh:
            self.assertEqual(fh.read(), self.head)

    def test_with_fcntl_the_worker_never_mentions_the_lock(self):
        proc = self.run_worker(hide_fcntl=False)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(proc.stderr, "")
        with open(self.stamp) as fh:
            self.assertEqual(fh.read(), self.head)


class CoverageWithoutBenchmarks(TempHome):
    """`--coverage` in a tree that lost its rules: the runtime tree with no
    `benchmarks/` beside it - a hand-stripped copy, or a repack that dropped it.
    The release artifact is not that tree (packaging/build.sh ships MANIFEST
    verbatim and the probe is in it), so this is the degraded case, not the
    installed one.

    The copy is real rather than mocked, because the doctor resolves both its
    hooks import and its probe path from `realpath(__file__)`: a tree assembled by
    copying those two things is the only faithful stand-in for an unpacked
    release.
    """

    def setUp(self):
        super().setUp()
        self.tree = os.path.join(self.home, "install", "0.0.0")
        os.makedirs(os.path.join(self.tree, "bin"))
        shutil.copy2(DOCTOR, os.path.join(self.tree, "bin", "tezgah-doctor"))
        shutil.copytree(HOOKS, os.path.join(self.tree, "hooks"),
                        ignore=shutil.ignore_patterns("__pycache__"))
        self.repo = os.path.join(self.home, "not-indexed")
        os.makedirs(self.repo)

    def ship_the_probe(self):
        """The same tree plus the one directory the artifact leaves out."""
        shutil.copytree(
            os.path.join(REPO, "benchmarks", "codegraph-bench"),
            os.path.join(self.tree, "benchmarks", "codegraph-bench"),
            ignore=shutil.ignore_patterns("__pycache__"))

    def coverage(self):
        return subprocess.run(
            [sys.executable, os.path.join(self.tree, "bin", "tezgah-doctor"),
             "--coverage", "--repo", self.repo],
            capture_output=True, text=True, timeout=60,
            env=support.base_env(self.home, extra={"PATH": BARE_PATH}))

    def test_a_tree_without_the_probe_names_it_instead_of_raising(self):
        proc = self.coverage()
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertNotIn("Traceback", proc.stdout + proc.stderr)
        self.assertIn("coverage probe unavailable: %s"
                      % os.path.join(self.tree, "benchmarks", "codegraph-bench",
                                     "probe.py"),
                      proc.stdout)
        # the rules being absent is not the index being unreadable: reporting it
        # as an unreadable dump would send the reader after the wrong thing
        self.assertNotIn("could not read an index dump", proc.stdout)

    def test_the_same_tree_with_the_probe_reads_the_coverage_rules(self):
        # one directory apart from the case above: what changes the answer is the
        # file, so that refusal cannot be a path that never resolves at all
        self.ship_the_probe()
        proc = self.coverage()
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertNotIn("coverage probe unavailable", proc.stdout)
        self.assertIn("could not read an index dump", proc.stdout)


if __name__ == "__main__":
    unittest.main()
