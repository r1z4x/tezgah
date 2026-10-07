"""The evidence ledger in the cache's SQLite store (ADR 021, plan 071 phase 2a):
the legacy JSONL import, its bulk run, concurrent writers and the twin cache."""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import unittest
from unittest import mock

import support

sys.path.insert(0, support.HOOKS)
import tezgah_integrity as ti  # noqa: E402
import tezgah_paths as tp  # noqa: E402
import tezgah_store as ts  # noqa: E402


class Cache(unittest.TestCase):
    def setUp(self):
        self.cache = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.cache, True)

    def ledger(self, session):
        return os.path.join(self.cache, "evidence", session + ".jsonl")

    def legacy(self, session, rows):
        """Rows appended to a session's JSONL file the way opencode's plugin
        writes them: one JSON.stringify line each, no lock."""
        path = self.ledger(session)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "a", encoding="utf-8") as fh:
            for row in rows:
                fh.write(json.dumps(row, separators=(",", ":")) + "\n")
        return path


class LegacyImport(Cache):
    def test_a_legacy_file_is_imported_on_first_touch_and_its_later_rows_too(self):
        path = self.legacy("s", [{"kind": "turn", "ts": 1, "detail": "a"},
                                 {"kind": "run", "ts": 2, "detail": "ls"}])
        self.assertEqual(support.ledger_rows(path), [])
        self.assertEqual([r["detail"] for r in ti.events_path(path)], ["a", "ls"])
        self.assertEqual(len(support.ledger_rows(path)), 2)
        # the plugin keeps appending to the same file, and reads it: the file
        # stays where it is and only the new line goes in
        self.legacy("s", [{"kind": "verify_ok", "ts": 3, "detail": "pytest"}])
        self.assertTrue(os.path.exists(path))
        self.assertEqual([r["detail"] for r in ti.events_path(path)],
                         ["a", "ls", "pytest"])
        self.assertEqual([r["detail"] for r in support.ledger_rows(path)],
                         ["a", "ls", "pytest"])
        # a row written as JSON is stored byte for byte as the plugin wrote it
        self.assertEqual(support.ledger_rows(path, raw=True)[-1],
                         '{"kind":"verify_ok","ts":3,"detail":"pytest"}')

    def test_the_bulk_import_is_idempotent(self):
        a = self.legacy("a", [{"kind": "run", "ts": 1, "detail": "x"}])
        b = self.legacy("b", [{"kind": "run", "ts": 2, "detail": "y"},
                              {"kind": "run", "ts": 3, "detail": "z"}])
        self.assertEqual(ts.import_evidence(self.cache), 2)
        first = (support.ledger_rows(a), support.ledger_rows(b))
        self.assertEqual((len(first[0]), len(first[1])), (1, 2))
        self.assertEqual(ts.import_evidence(self.cache), 2)
        proc = subprocess.run([sys.executable, os.path.join(support.HOOKS, "tezgah_store.py"),
                               "import-evidence", self.cache],
                              capture_output=True, text=True, timeout=60)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual((support.ledger_rows(a), support.ledger_rows(b)), first)


class Concurrency(Cache):
    WRITES = 150

    def test_two_processes_appending_at_once_lose_no_row(self):
        path = self.ledger("busy")
        code = ("import sys; sys.path.insert(0, %r)\n"
                "import tezgah_integrity as ti\n"
                "for i in range(%d):\n"
                "    ti.note_path(sys.argv[1], 'run', sys.argv[2] + str(i))\n"
                % (support.HOOKS, self.WRITES))
        procs = [subprocess.Popen([sys.executable, "-c", code, path, name],
                                  stderr=subprocess.PIPE, text=True)
                 for name in ("a", "b")]
        for proc in procs:
            self.assertEqual(proc.wait(timeout=120), 0, proc.stderr.read())
        details = [r["detail"] for r in support.ledger_rows(path)]
        self.assertEqual(sorted(details), sorted(
            "%s%d" % (name, i) for name in ("a", "b") for i in range(self.WRITES)))


class TwinCache(unittest.TestCase):
    """A sandboxed host splits one session over the cache and its temp fallback:
    a session with rows in the other cache's database is exempt from the
    orphan mark, and asking creates no database there."""

    def test_rows_in_the_other_cache_make_the_ledger_a_twin(self):
        fallback = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, fallback, True)
        session = "twin-%d" % os.getpid()
        here = os.path.join(tp.CACHE, "evidence", session + ".jsonl")
        twin = os.path.join(fallback, "evidence", session + ".jsonl")
        with mock.patch.dict(os.environ, {"TEZGAH_FALLBACK_CACHE": fallback}), \
                mock.patch.object(ti, "off", lambda *a: False):
            self.assertFalse(ti._unpaired_exempt(here, []))
            self.assertFalse(os.path.exists(os.path.join(fallback, "tezgah.db")))
            ti.note_path(twin, ti.BEGAN_KIND, "pytest -q", id="x")
            self.assertTrue(ti._unpaired_exempt(here, []))


class Retention(Cache):
    def test_the_sweep_deletes_idle_sessions_whole_and_keeps_the_current_one(self):
        now = int(time.time())
        old = now - 40 * 86400
        for session, stamp in (("old", old), ("live", old), ("new", now)):
            support.seed_ledger(self.ledger(session),
                                [{"kind": "run", "ts": stamp, "detail": session}])
        legacy = self.legacy("legacy-old", [{"kind": "run", "ts": old, "detail": "x"}])
        swept = ts.sweep_evidence(self.cache, now - 30 * 86400, keep="live")
        self.assertEqual(swept, (2, 2))
        self.assertEqual(support.ledger_sessions(self.cache), ["live", "new"])
        self.assertFalse(os.path.exists(legacy))


if __name__ == "__main__":
    unittest.main()
