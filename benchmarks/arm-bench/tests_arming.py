#!/usr/bin/env python3
"""The arming proof's host contract, checked without spending a model call.

Two things can make a row lie about arming, and both are pinned here: the name
omp gives a session directory (a wrong name resolves no session, so an armed run
answers -1) and the difference between "-1: no session found" and "0: the
session was found and the harness wrote nothing". The names asserted below are
the ones omp itself wrote under ~/.omp/agent/sessions for the runs of the E4b
block, so they are the host's rule rather than this file's.

    python3 benchmarks/arm-bench/tests_arming.py
"""
import sys
import tempfile
import unittest
import uuid
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))
import bench  # noqa: E402

AGENT = Path("/nonexistent-agent-dir")
E4B_ARCHIVE_CWD = ("/Users/rizax/.local/share/openresearch/local-runs/"
                   "317fa1ea-d7bd-4b2a-9cc1-6faaca347eaa/repo/benchmarks/arm-bench/"
                   ".runs/armbench-e01-silent-one-liner-516q7l84/repo")


class OmpSessionDir(unittest.TestCase):
    def name(self, cwd: str) -> str:
        return bench.omp_session_dir(cwd, AGENT).name

    def test_a_run_under_home_is_named_after_its_home_relative_path(self):
        home = Path.home()
        self.assertEqual(self.name(str(home / "Projects" / "tezgah")), "-Projects-tezgah")
        self.assertEqual(self.name(str(home / "Projects" / "tezgah" / "benchmarks" / "arm-bench")),
                         "-Projects-tezgah-benchmarks-arm-bench")

    def test_a_run_in_the_orx_archive_is_named_after_the_archive_path(self):
        # the name omp created for the E4b run directories
        self.assertEqual(self.name(E4B_ARCHIVE_CWD),
                         "-.local-share-openresearch-local-runs-317fa1ea-d7bd-4b2a-9cc1-6faaca347eaa"
                         "-repo-benchmarks-arm-bench-.runs-armbench-e01-silent-one-liner-516q7l84-repo")

    def test_home_itself_is_a_single_dash(self):
        self.assertEqual(self.name(str(Path.home())), "-")

    def test_a_run_under_the_temp_dir_is_named_after_its_relative_path(self):
        with mock.patch.object(tempfile, "gettempdir", lambda: "/tmp"):
            # /tmp is a symlink to /private/tmp on Darwin, and omp canonicalises
            # both sides, so either spelling of the cwd gives the same name - the
            # one the block's temp-directory runs were filed under
            expected = "-tmp-armbench-c01-root-cause-discount-azllj3u9-repo"
            self.assertEqual(self.name("/tmp/armbench-c01-root-cause-discount-azllj3u9/repo"), expected)
            self.assertEqual(self.name("/private/tmp/armbench-c01-root-cause-discount-azllj3u9/repo"),
                             expected)

    def test_a_run_outside_home_and_temp_is_named_after_its_absolute_path(self):
        self.assertEqual(self.name("/opt/verify/one"), "--opt-verify-one--")


class SessionRows(unittest.TestCase):
    def setUp(self):
        self.agent = Path(tempfile.mkdtemp(prefix="arming-agent-"))
        self.cwd = Path.home() / "Projects" / "tezgah"

    def env(self):
        return {"PI_CODING_AGENT_DIR": str(self.agent)}

    def test_an_unknown_session_is_minus_one_not_zero(self):
        self.assertEqual(bench.session_rows(self.env(), self.cwd, "omp"), -1)

    def test_a_session_that_wrote_no_ledger_row_is_zero(self):
        directory = bench.omp_session_dir(self.cwd, self.agent)
        directory.mkdir(parents=True)
        (directory / f"2026-01-01T00-00-00-000Z_{uuid.uuid4()}.jsonl").write_text("{}", encoding="utf-8")
        self.assertEqual(bench.session_rows(self.env(), self.cwd, "omp"), 0)

    def test_a_host_without_a_session_reader_is_minus_one(self):
        self.assertEqual(bench.session_rows(self.env(), self.cwd, "opencode"), -1)


if __name__ == "__main__":
    unittest.main(verbosity=2)
