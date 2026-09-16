"""bin/tezgah-doctor: report sizes and reclaim old index logs.

Runs the tool in a throwaway HOME with a fake codebase-memory-mcp cache and a
real (empty) sqlite database, so the machine's own caches are never touched.
"""
import json
import os
import sqlite3
import subprocess
import sys
import tempfile
import time
import unittest

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DOCTOR = os.path.join(REPO, "bin", "tezgah-doctor")


def load_module():
    """Import the extensionless doctor script as a module to unit-test it."""
    import importlib.machinery
    import importlib.util
    loader = importlib.machinery.SourceFileLoader("tezgah_doctor_under_test", DOCTOR)
    spec = importlib.util.spec_from_loader(loader.name, loader)
    module = importlib.util.module_from_spec(spec)
    loader.exec_module(module)
    return module


class Doctor(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.home = os.path.realpath(self._tmp.name)
        self.cbm = os.path.join(self.home, ".cache", "codebase-memory-mcp")
        self.logs = os.path.join(self.cbm, "logs")
        os.makedirs(self.logs, exist_ok=True)
        self.data = os.path.join(self.home, ".local", "share", "opencode")
        os.makedirs(self.data, exist_ok=True)
        self.db = os.path.join(self.data, "opencode.db")
        con = sqlite3.connect(self.db)
        con.execute("CREATE TABLE session (id TEXT, time_updated INTEGER)")
        con.execute("CREATE TABLE event (id TEXT)")
        con.commit()
        con.close()
        self.env = {
            "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
            "HOME": self.home,
            "LANG": "C.UTF-8",
            "TEZGAH_CBM_CACHE": self.cbm,
        }

    def session(self, sid, age_days):
        con = sqlite3.connect(self.db)
        con.execute("INSERT INTO session (id, time_updated) VALUES (?, ?)",
                    (sid, int((time.time() - age_days * 86400) * 1000)))
        con.commit()
        con.close()

    def fake_opencode(self):
        log = os.path.join(self.home, "oc-args.log")
        script = os.path.join(self.home, "fake-opencode")
        with open(script, "w") as fh:
            fh.write('#!/bin/sh\necho "$@" >> "%s"\n' % log)
        os.chmod(script, 0o755)
        return script, log

    def doctor(self, *args):
        return subprocess.run([sys.executable, DOCTOR] + list(args),
                              capture_output=True, text=True, env=self.env)

    def log(self, name, age_days=0, size=10):
        path = os.path.join(self.logs, name)
        with open(path, "w") as fh:
            fh.write("x" * size)
        when = time.time() - age_days * 86400
        os.utime(path, (when, when))
        return path

    def test_prune_sessions_selects_only_old_and_calls_cli(self):
        self.session("ses_old", 10)
        self.session("ses_new", 1)
        script, log = self.fake_opencode()
        mod = load_module()
        mod.OPENCODE_DB = self.db
        mod.OPENCODE_BIN = script
        self.assertEqual(mod.select_old_sessions(7), ["ses_old"])
        self.assertEqual(mod.prune_sessions(7), (1, 0))
        with open(log) as fh:
            calls = fh.read()
        self.assertIn("session delete ses_old", calls)
        self.assertNotIn("ses_new", calls)

    def test_prune_sessions_without_the_cli_counts_nothing_failed(self):
        # no opencode binary => nothing is attempted, so no id may be "failed"
        self.session("ses_old", 10)
        mod = load_module()
        mod.OPENCODE_DB = self.db
        mod.OPENCODE_BIN = None
        self.assertEqual(mod.prune_sessions(7), (0, 0))

    def test_json_report_counts_logs_and_db(self):
        self.log("Users-x-1.log", age_days=0)
        self.log("Users-x-2.log", age_days=10)
        proc = self.doctor("--json")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        rep = json.loads(proc.stdout)
        self.assertEqual(rep["cbm_log_files"], 2)
        self.assertEqual(rep["cbm_db_count"], 0)
        self.assertEqual(rep["opencode_sessions"], 0)
        self.assertEqual(rep["opencode_events"], 0)

    def test_clean_removes_only_old_logs_and_keeps_daemon(self):
        old = self.log("Users-x-old.log", age_days=10)
        fresh = self.log("Users-x-fresh.log", age_days=1)
        daemon = self.log("cbm-daemon.log", age_days=10)
        proc = self.doctor("--clean", "--days", "7", "--json")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        rep = json.loads(proc.stdout)
        self.assertEqual(rep["cleaned"]["cbm_logs_removed"], 1)
        self.assertFalse(os.path.exists(old))
        self.assertTrue(os.path.exists(fresh))
        self.assertTrue(os.path.exists(daemon))
        self.assertEqual(rep["cbm_log_files"], 2)

    def test_clean_reports_vacuum_outcome(self):
        self.log("Users-x-old.log", age_days=10)
        proc = self.doctor("--clean", "--json")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        rep = json.loads(proc.stdout)
        self.assertIn("vacuum", rep["cleaned"])


if __name__ == "__main__":
    unittest.main()
