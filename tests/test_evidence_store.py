"""The evidence ledger in the cache's SQLite store (ADR 021, plan 071 phase 2a):
the legacy JSONL import, its bulk run, concurrent writers and the twin cache."""
import fcntl
import hashlib
import json
import os
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import threading
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


class RefusedRow(Cache):
    def test_a_row_the_database_refuses_lands_in_the_legacy_file_marked_unlocked(self):
        # a busy or damaged database must not lose a `began` row: the honest
        # pass behind it would read as an orphan
        path = self.ledger("s")
        busy = sqlite3.OperationalError("database is locked")
        with mock.patch.object(ts, "append_evidence", side_effect=busy):
            ti.note_path(path, ti.BEGAN_KIND, "pytest -q", id="x", check=1)
        with open(path) as fh:
            self.assertEqual(json.loads(fh.read()).get(ti.UNLOCKED), 1)
        rows = ti.events_path(path)
        self.assertEqual([(r["kind"], r.get(ti.UNLOCKED)) for r in rows],
                         [(ti.BEGAN_KIND, 1)])

    def test_the_fallback_cuts_a_torn_tail_before_its_row(self):
        # the fallback row must not be merged into a fragment a killed writer
        # left: merged, the two would be one line no reader can parse
        path = self.legacy("s", [{"kind": "run", "ts": 1, "detail": "ls"}])
        with open(path, "ab") as fh:
            fh.write(b'{"kind": "run", "det')
        busy = sqlite3.OperationalError("database is locked")
        with mock.patch.object(ts, "append_evidence", side_effect=busy):
            ti.note_path(path, "run", "pwd")
        with open(path, "rb") as fh:
            self.assertEqual([json.loads(line)["detail"] for line in fh.read().splitlines()],
                             ["ls", "pwd"])
        self.assertEqual([(r["detail"], r.get(ti.UNLOCKED)) for r in ti.events_path(path)],
                         [("ls", None), ("pwd", 1)])


class ImportLocks(Cache):
    def test_an_import_waiting_on_the_database_leaves_the_file_unlocked(self):
        # the file's writer and readers must not wait on the database's lock
        path = self.legacy("s", [{"kind": "run", "ts": 1, "detail": "ls"}])
        db = os.path.join(self.cache, ts.EVIDENCE_DB)
        ts.connect(db, ts.EVIDENCE_SCHEMA, ts.EVIDENCE_VERSION).close()
        holder = sqlite3.connect(db, isolation_level=None)
        self.addCleanup(holder.close)
        holder.execute("BEGIN IMMEDIATE")
        importer = threading.Thread(target=ts.import_session, args=(path,))
        importer.start()
        try:
            time.sleep(0.3)
            with open(path, "rb") as fh:
                fcntl.flock(fh, fcntl.LOCK_EX | fcntl.LOCK_NB)  # raises when held
        finally:
            holder.execute("COMMIT")
            importer.join(timeout=30)
        self.assertEqual([r["detail"] for r in support.ledger_rows(path)], ["ls"])

    def test_a_torn_tail_costs_a_reader_no_write_lock(self):
        # a fragment past the imported lines is not a line yet: a read must
        # not wait on (and, past the busy timeout, fail on) the write lock
        path = self.legacy("s", [{"kind": "run", "ts": 1, "detail": "ls"}])
        self.assertEqual(len(ts.evidence_rows(path)), 1)
        with open(path, "ab") as fh:
            fh.write(b'{"kind": "run", "det')
        holder = sqlite3.connect(os.path.join(self.cache, ts.EVIDENCE_DB),
                                 isolation_level=None)
        self.addCleanup(holder.close)
        holder.execute("BEGIN IMMEDIATE")
        try:
            started = time.monotonic()
            rows = ts.evidence_rows(path)
            waited = time.monotonic() - started
        finally:
            holder.execute("COMMIT")
        self.assertEqual([json.loads(text)["detail"] for text in rows], ["ls"])
        self.assertLess(waited, 1.0)

    def test_a_line_that_is_not_utf_8_is_named_by_the_old_readers_hash(self):
        # the marker hashes the line with its newline, as the file reader did,
        # so a damage row that reader wrote still names the same line
        path = self.ledger("s")
        os.makedirs(os.path.dirname(path))
        with open(path, "wb") as fh:
            fh.write(b'{"kind": "x\xff"}\n')
        ti.events_path(path)
        self.assertEqual(support.ledger_rows(path, raw=True)[0], "\x00not utf-8 %s"
                         % hashlib.sha1(b'{"kind": "x\xff"}\n').hexdigest()[:12])


class Versions(Cache):
    def test_an_older_install_leaves_a_newer_schema_alone(self):
        db = os.path.join(self.cache, ts.EVIDENCE_DB)
        conn = sqlite3.connect(db)
        conn.execute("PRAGMA user_version = %d" % (ts.EVIDENCE_VERSION + 1))
        conn.close()
        ts.connect(db, ts.EVIDENCE_SCHEMA, ts.EVIDENCE_VERSION).close()
        conn = sqlite3.connect(db)
        self.addCleanup(conn.close)
        self.assertEqual(conn.execute("PRAGMA user_version").fetchone()[0],
                         ts.EVIDENCE_VERSION + 1)

    def test_the_bulk_import_starts_only_while_a_legacy_file_exists(self):
        os.makedirs(os.path.join(self.cache, "evidence"))
        with mock.patch.object(subprocess, "Popen") as spawn:
            ts.import_later(self.cache)
            self.assertFalse(spawn.called)
            self.legacy("s", [{"kind": "run", "ts": 1, "detail": "ls"}])
            ts.import_later(self.cache)
            self.assertTrue(spawn.called)


if __name__ == "__main__":
    unittest.main()
