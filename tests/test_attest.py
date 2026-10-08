"""hooks/tezgah_attest.py: the per-session check that tezgah's own hook entries
are armed and unchanged since install.

Measured the way a session meets it: the real installer arms a throwaway HOME,
the fixture disarms one thing the way a person or another tool would, and the
host-neutral CLI (`tezgah-context attest`, the call opencode makes; every hook
host calls the same `tezgah_attest.run`) writes the session's row. Four disarm
fixtures must each be named; three clean installs - an unpacked release tarball,
the same tree where npm and Homebrew put it - must report nothing.
"""
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tarfile
import tempfile
import unittest

import support
from support import TempHome

sys.path.insert(0, support.HOOKS)
import tezgah_integrity as ti  # noqa: E402

SETUP = os.path.join(support.REPO, "bin", "tezgah-setup")
ALL = ("claude", "codex", "cursor", "opencode", "dsh", "omp")


class AttestBase(TempHome):
    def setUp(self):
        super().setUp()
        for d in (".claude", ".codex", ".cursor", ".dsh", ".config/opencode"):
            os.makedirs(os.path.join(self.home, d), exist_ok=True)
        self.repo = self.make_repo("proj")
        self.envv = self.env(extra={
            "TEZGAH_NO_DEPS": "1",
            "TEZGAH_OMP_BIN": os.path.join(self.home, "no-such-omp")})

    def install(self, hosts, tree=support.REPO):
        proc = subprocess.run(
            [sys.executable, os.path.join(tree, "bin", "tezgah-setup"), "--install",
             "--no-deps", "--hosts", ",".join(hosts)],
            capture_output=True, text=True, env=self.envv, timeout=300)
        self.assertEqual(proc.returncode, 0, proc.stdout[-2000:] + proc.stderr)

    def attest(self, host, session, tree=support.REPO):
        """The session's attest row and its drift mark text ("" when none)."""
        proc = subprocess.run(
            [sys.executable, os.path.join(tree, "bin", "tezgah-context"), "attest",
             host, session, self.repo],
            capture_output=True, text=True, env=self.envv, timeout=60)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(proc.stdout, "", "attest must print nothing")
        path = os.path.join(self.home, ".cache", "tezgah", "evidence",
                            ti._slug(session) + ".jsonl")
        rows = support.ledger_rows(path)
        attest = [r for r in rows if r["kind"] == "attest"]
        self.assertEqual(len(attest), 1, rows)
        text = support.store_doc(os.path.join(self.home, ".cache", "tezgah"),
                                 "harness_drift", "%s.%s" % (
                                     hashlib.sha256(session.encode()).hexdigest()[:16], host))
        text = text or ""
        return attest[0], text

    def assert_drift(self, host, session, needle, tree=support.REPO):
        row, mark = self.attest(host, session, tree)
        self.assertTrue(row["detail"].startswith("drifted: "), row)
        self.assertIn(needle, row["detail"])
        self.assertIn(needle, mark)
        self.assertEqual(row["host"], host)
        # evidence for the user, never an instruction to the model
        for word in ("reinstall", "re-run", "tezgah-setup", "--install"):
            self.assertNotIn(word, row["detail"].lower())


class Attest(AttestBase):
    # ---- the four disarm fixtures -----------------------------------------
    def test_a_removed_pretooluse_entry_is_named_while_posttooluse_stays(self):
        self.install(["codex"])
        path = os.path.join(self.home, ".codex", "hooks.json")
        with open(path) as fh:
            data = json.load(fh)
        del data["hooks"]["PreToolUse"]
        self.assertIn("PostToolUse", data["hooks"])
        with open(path, "w") as fh:
            json.dump(data, fh)
        self.assert_drift("codex", "d1", "codex PreToolUse entry removed")

    def test_an_edited_plugin_hooks_json_is_named(self):
        # Claude runs a COPY of the tree; the copy's manifest is what is read
        self.install(["claude"])
        copy = os.path.join(self.home, "copy")
        shutil.copytree(support.HOOKS, os.path.join(copy, "hooks"),
                        ignore=shutil.ignore_patterns("__pycache__"))
        os.makedirs(os.path.join(copy, "bin"))
        shutil.copy2(os.path.join(support.REPO, "bin", "tezgah-context"),
                     os.path.join(copy, "bin", "tezgah-context"))
        manifest = os.path.join(copy, "hooks", "hooks.json")
        with open(manifest) as fh:
            data = json.load(fh)
        data["hooks"]["PreToolUse"][0]["hooks"][0]["timeout"] = 1
        with open(manifest, "w") as fh:
            json.dump(data, fh)
        self.assert_drift("claude", "d2", "claude PreToolUse entry changed", copy)

    def test_a_stale_omp_render_is_named(self):
        self.install(["omp"])
        bridge = os.path.join(self.home, ".omp", "agent", "hooks", "pre",
                              "tezgah-hook.ts")
        with open(bridge, "a") as fh:
            fh.write("// left by an older tree\n")
        self.assert_drift("omp", "d3", "differs from a fresh render")

    def test_a_world_writable_hook_file_is_named(self):
        self.install(["cursor"])
        path = os.path.join(self.home, ".cursor", "hooks.json")
        os.chmod(path, 0o666)
        self.assert_drift("cursor", "d4", "%s mode 0666" % path)

    # ---- what a clean session reads -----------------------------------------
    def test_a_clean_checkout_install_reports_ok_and_clears_the_mark(self):
        self.install(list(ALL))
        for host in ALL:
            with self.subTest(host=host):
                row, mark = self.attest(host, "c-" + host)
                self.assertEqual(row["detail"], "ok")
                self.assertEqual(mark, "")

    def test_entries_the_install_never_recorded_are_unverified_not_drift(self):
        self.install(["claude"])  # a record exists, with no codex keys in it
        path = os.path.join(self.home, ".codex", "hooks.json")
        with open(path, "w") as fh:
            json.dump({"hooks": {"Stop": [{"hooks": [
                {"type": "command", "command": "tezgah-codex-hook"}]}]}}, fh)
        row, mark = self.attest("codex", "u1")
        self.assertEqual(row["detail"],
                         "unverified: no install record for codex hook entries")
        self.assertEqual(mark, "")

    def test_the_row_names_the_switches_present(self):
        self.install(["codex"])
        os.makedirs(os.path.join(self.home, ".config", "tezgah"), exist_ok=True)
        open(os.path.join(self.home, ".config", "tezgah", "verify-off"), "w").close()
        row, _mark = self.attest("codex", "w1")
        self.assertEqual(row["switches"], "verify-off")

    def test_the_status_line_draws_the_drift_mark(self):
        self.install(["codex"])
        os.chmod(os.path.join(self.home, ".codex", "hooks.json"), 0o666)
        self.attest("codex", "m1")
        proc = support.run([support.CODEX_HOOK],
                           {"hook_event_name": "Stop", "cwd": self.repo,
                            "session_id": "m1", "last_assistant_message": "ok"},
                           env=self.envv, cwd=self.repo)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("drift", proc.stdout)

    def test_a_clean_host_does_not_clear_another_hosts_mark(self):
        # the mark is keyed by (session, host): a clean attest of one host under
        # the same session id must leave the drifted host's mark standing
        self.install(["codex", "cursor"])
        os.chmod(os.path.join(self.home, ".codex", "hooks.json"), 0o666)
        self.assert_drift("codex", "x1", "mode 0666")
        proc = subprocess.run(
            [sys.executable, os.path.join(support.REPO, "bin", "tezgah-context"),
             "attest", "cursor", "x1", self.repo],
            capture_output=True, text=True, env=self.envv, timeout=60)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        check = subprocess.run(
            [sys.executable, "-c", "import tezgah_attest as ta; print(ta.mark_text('x1'))"],
            capture_output=True, text=True, env=self.envv, timeout=60)
        self.assertIn("mode 0666", check.stdout, check.stderr)


@unittest.skipUnless(shutil.which("sh") and shutil.which("tar"), "build.sh needs sh and tar")
class CleanReleases(AttestBase):
    """Three clean installs of a release tree: the tarball unpacked under a
    prefix, and the same tree where npm and the Homebrew formula (which installs
    the tarball) put it. A packaged tree also records its entry scripts."""

    @classmethod
    def setUpClass(cls):
        cls.dist = tempfile.mkdtemp(prefix="tezgah-attest-dist.")
        proc = subprocess.run(["sh", os.path.join("packaging", "build.sh"),
                               "--version", "0.0.0-attest", "--out", cls.dist],
                              cwd=support.REPO, capture_output=True, text=True,
                              env=dict(support.base_env(cls.dist),
                                       TEZGAH_PYTHON=sys.executable))
        if proc.returncode != 0:
            raise AssertionError(proc.stdout + proc.stderr)
        cls.tarball = os.path.join(cls.dist, "tezgah-0.0.0-attest.tar.gz")

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.dist, ignore_errors=True)

    def unpack(self, *parts):
        tree = os.path.join(self.home, *parts)
        os.makedirs(tree)
        with tarfile.open(self.tarball) as tar:
            # the "tar" filter where it exists: modes kept, nothing outside
            tar.extractall(tree, **({"filter": "tar"}
                                    if hasattr(tarfile, "tar_filter") else {}))
        return os.path.realpath(tree)

    def test_three_clean_release_installs_report_no_drift(self):
        trees = {"tarball": ("prefix", "0.0.0-attest"),
                 "npm": ("npm", "lib", "node_modules", "@r1z4x", "tezgah"),
                 "brew": ("brew", "Cellar", "tezgah", "0.0.0-attest", "libexec")}
        for channel, parts in trees.items():
            tree = self.unpack(*parts)
            self.install(list(ALL), tree)
            with open(os.path.join(self.home, ".config", "tezgah",
                                   "contract.sha256")) as fh:
                self.assertIn("hook:codex:code", fh.read())
            for host in ALL:
                with self.subTest(channel=channel, host=host):
                    row, mark = self.attest(host, "%s-%s" % (channel, host), tree)
                    self.assertEqual(row["detail"], "ok")
                    self.assertEqual(mark, "")

    def test_a_changed_entry_script_on_a_release_install_is_drift(self):
        tree = self.unpack("prefix", "0.0.0-attest")
        self.install(["codex"], tree)
        with open(os.path.join(tree, "hosts", "codex", "hook.py"), "a") as fh:
            fh.write("# patched after install\n")
        self.assert_drift("codex", "p1", "codex hook code changed since install", tree)


if __name__ == "__main__":
    unittest.main()
