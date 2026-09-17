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
import json
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


class StopFires(unittest.TestCase):
    """Stop-rule refusals are read from the run's own ledger, not inferred."""

    def setUp(self):
        self.agent = Path(tempfile.mkdtemp(prefix="arming-agent-"))
        self.cwd = Path.home() / "Projects" / "tezgah"
        self.session_id = uuid.uuid4().hex
        self.ledger_dir = Path(tempfile.mkdtemp(prefix="arming-ledger-"))
        # the real evidence directory is where the running harness writes; a
        # test must not put rows into it, so `_path` is redirected
        patcher = mock.patch.object(
            bench, "ledger_path",
            lambda session_id: str(self.ledger_dir / (session_id + ".jsonl")))
        patcher.start()
        self.addCleanup(patcher.stop)
        directory = bench.omp_session_dir(self.cwd, self.agent)
        directory.mkdir(parents=True)
        (directory / f"2026-01-01T00-00-00-000Z_{self.session_id}.jsonl").write_text(
            "{}", encoding="utf-8")

    def env(self):
        return {"PI_CODING_AGENT_DIR": str(self.agent)}

    def ledger(self, rows: list[dict]):
        path = self.ledger_dir / (self.session_id + ".jsonl")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")

    def test_a_session_with_no_decision_is_zero_fires_not_unknown(self):
        self.ledger([{"kind": "edit", "detail": "src/money.py"}])
        self.assertEqual(bench.stop_fires(self.env(), self.cwd, "omp"), 0)

    def test_a_blocked_stop_is_counted_and_an_allowed_claim_is_not(self):
        self.ledger([{"kind": "claim", "detail": "blocked: A check failed in this session"},
                     {"kind": "claim", "detail": "ok"},
                     {"kind": "claim", "detail": "blocked: no check ran"}])
        self.assertEqual(bench.stop_fires(self.env(), self.cwd, "omp"), 2)

    def test_no_session_is_minus_one_never_zero_fires(self):
        self.assertEqual(bench.stop_fires({"PI_CODING_AGENT_DIR": str(AGENT)},
                                          self.cwd, "omp"), -1)
        self.assertEqual(bench.stop_fires(self.env(), self.cwd, "opencode"), -1)


class RouteOfDiff(unittest.TestCase):
    """The route column: which of the task's declared routes a diff took."""

    META = {"routes": {"call-site": ["src/pricing.py"], "helper": ["src/money.py"]}}

    def route(self, *changed: str) -> str:
        return bench.route_of(list(changed), self.META)

    def test_the_call_site_alone_is_the_right_route(self):
        self.assertEqual(self.route("src/pricing.py"), "call-site")

    def test_the_shared_helper_alone_is_the_wrong_route(self):
        self.assertEqual(self.route("src/money.py"), "helper")

    def test_rewriting_both_is_its_own_value(self):
        self.assertEqual(self.route("src/money.py", "src/pricing.py"), "both")

    def test_an_edit_off_both_routes_is_other_not_a_route(self):
        # an e01 run that rewrites the test suite is neither route
        self.assertEqual(self.route("tests/test_pricing.py", "README.md"), "other")

    def test_a_run_that_edited_nothing_is_none(self):
        self.assertEqual(self.route(), "none")

    def test_a_task_without_declared_routes_reports_no_route(self):
        # most tasks have one obvious fix; the field must not invent a value
        self.assertIsNone(bench.route_of(["src/anything.py"], {}))

    def test_a_declared_route_may_be_a_directory(self):
        self.assertEqual(bench.route_of(["src/money.py"],
                                        {"routes": {"helper": ["src/"]}}), "helper")

    def test_the_shipped_e01_task_declares_the_two_routes(self):
        meta = bench.load_json(bench.task_dir("e01-silent-one-liner") / "meta.json")
        self.assertEqual(sorted(meta["routes"]), ["call-site", "helper"])
        self.assertEqual(bench.route_of(["src/money.py"], meta), "helper")
        self.assertEqual(bench.route_of(["src/pricing.py"], meta), "call-site")


if __name__ == "__main__":
    unittest.main(verbosity=2)
