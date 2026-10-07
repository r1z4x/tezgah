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
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
import uuid
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))
import bench  # noqa: E402
import make_variants  # noqa: E402

AGENT = Path("/nonexistent-agent-dir")
E4B_ARCHIVE_CWD = (str(Path.home()) + "/.local/share/openresearch/local-runs/"
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

    def test_the_refusal_class_is_recorded_not_only_its_count(self):
        # the count alone left E2's classes to a hand pass over 150 ledgers
        self.ledger([{"kind": "claim", "detail": "blocked: check failed"},
                     {"kind": "claim", "detail": "ok"},
                     {"kind": "claim", "detail": "blocked: no verify_ok"},
                     {"kind": "claim", "detail": "blocked: no verify_ok"}])
        self.assertEqual(bench.stop_classes(self.env(), self.cwd, "omp"),
                         {"check failed": 1, "no verify_ok": 2})
        self.assertEqual(bench.stop_fires(self.env(), self.cwd, "omp"), 3)

    def test_an_unknown_session_is_no_classes_never_an_empty_map(self):
        # -1's counterpart: "could not read the ledger" is not "refused nothing",
        # and a report that shows n/a here must not invent a zero
        self.assertEqual(bench.stop_classes({"PI_CODING_AGENT_DIR": str(AGENT)},
                                            self.cwd, "omp"), None)
        self.assertEqual(bench.stop_classes(self.env(), self.cwd, "opencode"), None)
        self.ledger([{"kind": "edit", "detail": "src/money.py"}])
        self.assertEqual(bench.stop_classes(self.env(), self.cwd, "omp"), {})


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


class ArmingPreflight(unittest.TestCase):
    """The free check that refuses an arm whose agent dir would load no harness.

    The paths are scratch ones, so the test never reads the real ~/.omp/agent:
    what is pinned is the decision - a metadata-only directory refuses, a copied
    bridge with its pin on disk passes, and a hunk outside the declared line is
    reported rather than smoothed over."""

    def setUp(self):
        self.root = Path(tempfile.mkdtemp(prefix="preflight-root-"))
        self.installed = Path(tempfile.mkdtemp(prefix="preflight-installed-"))
        installed = self.installed / bench.BRIDGE
        installed.parent.mkdir(parents=True)
        installed.write_text('const HOOK = "/installed/hosts/omp/hook.py";\n', encoding="utf-8")
        self.hook = Path(tempfile.mkdtemp(prefix="preflight-hook-")) / "hook.py"
        self.hook.write_text("", encoding="utf-8")

    def arm(self, name: str, **extra) -> dict:
        return {"name": name, "host": "omp", "harness": "tezgah",
                "env": {"PI_CODING_AGENT_DIR": str(self.root / "arm")}, **extra}

    def deploy(self, body: str) -> None:
        bridge = self.root / "arm" / bench.BRIDGE
        bridge.parent.mkdir(parents=True, exist_ok=True)
        bridge.write_text(body, encoding="utf-8")

    def test_a_metadata_only_agent_dir_is_refused(self):
        # the E2b shape: PROVENANCE.md and omp's own state, no hooks/
        (self.root / "arm").mkdir(parents=True)
        (self.root / "arm" / "PROVENANCE.md").write_text("", encoding="utf-8")
        ok, lines = bench.preflight(self.arm("omp-stale-rule"), root=self.root,
                                    installed=self.installed)
        self.assertFalse(ok)
        self.assertEqual(len(lines), 1)
        self.assertIn("omp-stale-rule", lines[0])
        self.assertIn("hooks/pre/tezgah-hook.ts", lines[0])
        self.assertIn("PROVENANCE.md", lines[0])

    def test_a_copied_bridge_with_a_live_pin_is_accepted(self):
        self.deploy('const HOOK = "%s";\n' % self.hook)
        ok, lines = bench.preflight(self.arm("omp-task-rule"), root=self.root,
                                    installed=self.installed)
        self.assertTrue(ok)
        self.assertIn(str(self.hook), " ".join(lines))
        self.assertNotIn("DRIFT", " ".join(lines))

    def test_a_pin_that_is_no_longer_on_disk_is_refused(self):
        # a removed worktree leaves the bridge in place and inert
        self.deploy('const HOOK = "%s/gone/hook.py";\n' % self.root)
        ok, lines = bench.preflight(self.arm("omp-task-rule"), root=self.root,
                                    installed=self.installed)
        self.assertFalse(ok)
        self.assertIn("not on disk", lines[0])

    def test_a_hunk_beyond_the_pin_is_named_as_drift(self):
        # the installed copy: the pin, then unchanged code. The arm's copy carries
        # the pin and a block after the unchanged code that the install grew later.
        installed = self.installed / bench.BRIDGE
        installed.write_text('const HOOK = "/installed/hosts/omp/hook.py";\nconst a = 1;\nconst b = 2;\n'
                             'const c = 3;\n', encoding="utf-8")
        self.deploy('const HOOK = "%s";\nconst a = 1;\nconst b = 2;\n'
                    'const grew = "a block the install grew";\n' % self.hook)
        ok, lines = bench.preflight(self.arm("omp-task-rule"), root=self.root,
                                    installed=self.installed)
        self.assertTrue(ok)
        self.assertIn("ARM DRIFT", " ".join(lines))
        self.assertIn("arm 4", " ".join(lines))

    def test_a_declared_harness_free_arm_is_accepted_and_says_so(self):
        ok, lines = bench.preflight(self.arm("omp-bare", harness="none", arming="empty by design"),
                                    root=self.root, installed=self.installed)
        self.assertTrue(ok)
        self.assertIn("harness-free on purpose (empty by design)", lines[0])

    def test_a_host_without_an_agent_dir_is_not_checked(self):
        ok, lines = bench.preflight({"name": "opencode+tezgah", "host": "opencode",
                                     "harness": "tezgah", "env": {}},
                                    root=self.root, installed=self.installed)
        self.assertTrue(ok)
        self.assertIn("omp arms only", lines[0])


class CellUnmeasured(unittest.TestCase):
    """A cell whose every row came back without a session is not that arm's."""

    ARM = {"name": "omp-stale-rule", "host": "omp", "harness": "tezgah", "env": {}}

    def rows(self, *session_rows):
        return [{"session_rows": n} for n in session_rows]

    def test_every_row_inert_is_unmeasured(self):
        why = bench.cell_unmeasured(self.ARM, self.rows(0, 0, 0))
        self.assertIsNotNone(why)
        self.assertIn("expected armed", why)

    def test_one_armed_row_is_a_measurement(self):
        self.assertIsNone(bench.cell_unmeasured(self.ARM, self.rows(0, 7, 0)))

    def test_a_row_without_the_field_is_unknown_not_zero(self):
        self.assertIsNone(bench.cell_unmeasured(self.ARM, [{"session_rows": 0}, {}]))

    def test_a_declared_harness_free_arm_is_measurable_at_zero(self):
        self.assertIsNone(bench.cell_unmeasured({**self.ARM, "harness": "none"}, self.rows(0, 0)))

    def test_an_arm_absent_from_arms_json_is_not_judged(self):
        self.assertIsNone(bench.cell_unmeasured(None, self.rows(0, 0)))


class VariantArms(unittest.TestCase):
    """`make_variants.py` deploys a harness-carrying arm, not a bare RULES.md.

    An arm dir holding the ablated contract and no bridge loads no harness, so
    its rows measure an inert host: the pre-flight refuses it and every row
    would carry `session_rows: 0`. The generator is run as the script it ships
    as, against a scratch `HOME`, so neither the real `~/.omp/agent` nor the
    repository's own `arms/` is read or written."""

    def setUp(self):
        self.home = Path(tempfile.mkdtemp(prefix="variants-home-"))
        self.installed = self.home / ".omp" / "agent"
        (self.installed / bench.BRIDGE).parent.mkdir(parents=True)
        self.hook = self.home / "hosts" / "omp" / "hook.py"
        self.hook.parent.mkdir(parents=True)
        self.hook.write_text("", encoding="utf-8")
        self.bridge = 'const HOOK = "%s";\nconst rest = "unchanged";\n' % self.hook
        (self.installed / bench.BRIDGE).write_text(self.bridge, encoding="utf-8")
        (self.installed / "agents").mkdir()
        (self.installed / "agents" / "tezgah-reviewer.md").write_text("agent\n", encoding="utf-8")
        # per-run state, which the arm must not carry: omp recreates it
        (self.installed / "sessions").mkdir()
        (self.installed / "agent.db").write_text("", encoding="utf-8")
        self.paragraphs = {}
        body = []
        for i, (name, lead) in enumerate(make_variants.CLAUSES.items()):
            self.paragraphs[name] = "%s\n\nclause %d body" % (lead, i)
            body.append(self.paragraphs[name])
        (self.installed / "RULES.md").write_text("\n\n".join(body) + "\n", encoding="utf-8")
        self.bench = self.home / "benchmarks" / "arm-bench"
        self.bench.mkdir(parents=True)
        shutil.copy2(make_variants.__file__, self.bench / "make_variants.py")
        self.generate()

    def generate(self) -> None:
        proc = subprocess.run([sys.executable, str(self.bench / "make_variants.py")],
                              cwd=self.bench, env={**os.environ, "HOME": str(self.home)},
                              capture_output=True, text=True)
        self.assertEqual(proc.returncode, 0, proc.stderr)

    def arm(self, name: str) -> dict:
        return {"name": name, "host": "omp", "harness": "tezgah-minus",
                "env": {"PI_CODING_AGENT_DIR": str(self.bench / "arms" / name)}}

    def test_every_variant_deploys_a_bridge_the_preflight_accepts(self):
        for name in make_variants.CLAUSES:
            ok, lines = bench.preflight(self.arm(name), root=self.bench, installed=self.installed)
            self.assertTrue(ok, "%s refused: %s" % (name, lines[0]))
            self.assertNotIn("DRIFT", " ".join(lines))

    def test_the_deployed_bridge_is_the_installed_byte(self):
        # the arm is defined by the contract alone, so its bridge must not move
        for name in make_variants.CLAUSES:
            self.assertEqual((self.bench / "arms" / name / bench.BRIDGE).read_text(encoding="utf-8"),
                             self.bridge)

    def test_the_contract_is_the_installed_one_minus_that_clause(self):
        for name, paragraph in self.paragraphs.items():
            text = (self.bench / "arms" / name / "RULES.md").read_text(encoding="utf-8")
            self.assertNotIn(paragraph, text)
            for other in self.paragraphs.values():
                if other != paragraph:
                    self.assertIn(other, text)

    def test_the_rest_of_the_arm_is_the_installed_dir(self):
        for name in make_variants.CLAUSES:
            arm = self.bench / "arms" / name
            self.assertEqual((arm / "agents" / "tezgah-reviewer.md").read_text(encoding="utf-8"),
                             "agent\n")
            self.assertFalse((arm / "agent.db").exists())
            self.assertFalse((arm / "sessions").exists())

    def test_regenerating_over_a_deployed_arm_leaves_it_armed(self):
        self.generate()
        for name in make_variants.CLAUSES:
            self.assertTrue(bench.preflight(self.arm(name), root=self.bench,
                                            installed=self.installed)[0])

    def test_a_variant_arm_carries_the_same_arming_condition_as_its_baseline(self):
        # without TEZGAH_ROOTS covering the bench root every hook returns early,
        # so the arm would differ from omp+tezgah in its arming condition too
        arms = {a["name"]: a for a in bench.load_json(bench.ARMS_FILE)}
        baseline = arms["omp+tezgah"]["env"]["TEZGAH_ROOTS"]
        for name in make_variants.CLAUSES:
            self.assertEqual(arms[name]["env"].get("TEZGAH_ROOTS"), baseline)


if __name__ == "__main__":
    unittest.main(verbosity=2)
