"""bin/tezgah-doctor: the store report, the reclaim actions and --coverage.

Runs the tool in a throwaway HOME with a real (empty) sqlite database, a
throwaway tezgah root and a stub codegraph, so the machine's own caches, roots,
opencode database and graph index are never read or touched.
"""
import json
import os
import sqlite3
import subprocess
import sys
import tempfile
import time
import unittest

import support

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DOCTOR = os.path.join(REPO, "bin", "tezgah-doctor")
# a PATH with git and nothing else: no codegraph, no npx, so a case that wants a
# live index dump must point TEZGAH_CODEGRAPH_BIN at its own stub
BARE_PATH = "/usr/bin:/bin"


def load_module():
    """Import the extensionless doctor script as a module to unit-test it."""
    import importlib.machinery
    import importlib.util
    loader = importlib.machinery.SourceFileLoader("tezgah_doctor_under_test", DOCTOR)
    spec = importlib.util.spec_from_loader(loader.name, loader)
    module = importlib.util.module_from_spec(spec)
    loader.exec_module(module)
    return module


def git(cwd, *args):
    subprocess.run(["git", "-C", cwd] + list(args), check=True,
                   capture_output=True)


class DoctorBase(unittest.TestCase):
    """The throwaway HOME, root and opencode database every case runs against."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.home = os.path.realpath(self._tmp.name)
        self.data = os.path.join(self.home, ".local", "share", "opencode")
        os.makedirs(self.data, exist_ok=True)
        self.db = os.path.join(self.data, "opencode.db")
        con = sqlite3.connect(self.db)
        con.execute("CREATE TABLE session (id TEXT, time_updated INTEGER)")
        con.execute("CREATE TABLE event (id TEXT)")
        con.commit()
        con.close()
        # the configured root is this empty dir, so a default run can never walk
        # the machine's own ~/Projects
        self.root = os.path.join(self.home, "Projects")
        os.makedirs(self.root, exist_ok=True)
        self.env = {
            "PATH": BARE_PATH,
            "HOME": self.home,
            "LANG": "C.UTF-8",
            "TEZGAH_ROOTS": self.root,
            # --clean sweeps the temp fallback cache too; the machine's own must
            # never be the one a test run deletes from
            "TEZGAH_FALLBACK_CACHE": os.path.join(self.home, "fallback"),
            "TEZGAH_UPDATE_CHECK": "0",  # no detached release check in this HOME
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

    def doctor(self, *args, env=None):
        return subprocess.run([sys.executable, DOCTOR] + list(args),
                              capture_output=True, text=True, env=env or self.env)

    def make_repo(self, name, index_bytes=None, root=None):
        """A repo tezgah would index: a `.git` marker, and `.codegraph/codegraph.db`
        when `index_bytes` is given."""
        repo = os.path.join(root or self.root, name)
        os.makedirs(os.path.join(repo, ".git"), exist_ok=True)
        if index_bytes is not None:
            os.makedirs(os.path.join(repo, ".codegraph"), exist_ok=True)
            with open(os.path.join(repo, ".codegraph", "codegraph.db"), "wb") as fh:
                fh.write(b"x" * index_bytes)
        return repo

    def indexed(self, rep):
        """The report's per-repo rows as {repo: row}."""
        return {row["repo"]: row for row in rep["codegraph_repos"]}


class Doctor(DoctorBase):
    """The report and the reclaim actions, no `--coverage`."""

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

    def test_clean_reports_vacuum_outcome(self):
        proc = self.doctor("--clean", "--json")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        rep = json.loads(proc.stdout)
        self.assertIn("vacuum", rep["cleaned"])

    def test_clean_sweeps_hook_state_past_the_retention_age(self):
        # Audit L-11 (GAP-10): ledgers, turns/, sessions/ and classify.log had no
        # retention, and 400-day-old files survived `--clean`. The turn stamps
        # and the used-tool marks are rows now, imported from those files with
        # the age each file had.
        cache = os.path.join(self.home, ".cache", "tezgah")
        fallback = self.env["TEZGAH_FALLBACK_CACHE"]
        old = time.time() - 40 * 86400

        def put(path, age=old, text="x"):
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, "w") as fh:
                fh.write(text)
            os.utime(path, (age, age))
            return path

        load_module()  # puts hooks/ on sys.path, as the doctor itself does
        from tezgah_integrity import _slug
        stale = [put(os.path.join(cache, "evidence", "s-old.jsonl")),
                 put(os.path.join(cache, "classify.log")),
                 put(os.path.join(cache, "debug.log")),
                 put(os.path.join(fallback, "evidence", "f-old.jsonl"))]
        imported = [put(os.path.join(cache, "turns", "s-old.json"), text='{"root": "/r"}'),
                    put(os.path.join(cache, "sessions", "s-old.jsonl"),
                        text='{"kind": "graph"}\n')]
        fresh = put(os.path.join(cache, "evidence", "s-new.jsonl"), time.time())
        # the current session is kept however long it sat idle
        current = put(os.path.join(cache, "evidence",
                                   _slug("live-session") + ".jsonl"))
        put(os.path.join(cache, "turns", "live-session.json"), text='{"root": "/r"}')
        snapshot = put(os.path.join(cache, "snapshots", "a", "b"))
        proc = self.doctor("--clean", "--json",
                           env=dict(self.env, TEZGAH_SESSION="live-session"))
        self.assertEqual(proc.returncode, 0, proc.stderr)
        cleaned = json.loads(proc.stdout)["cleaned"]
        self.assertEqual((cleaned["state"]["removed"], cleaned["state"]["days"]),
                         (len(stale), 30))
        self.assertEqual(cleaned["marks"], {"rows": 2, "days": 30})
        for path in stale + imported:
            self.assertFalse(os.path.exists(path), path)
        for path in (fresh, current, snapshot):
            self.assertTrue(os.path.exists(path), path)
        self.assertEqual(support.store_keys(cache, "turns"), ["live-session"])
        self.assertEqual(support.used_kinds(cache, "s-old"), set())

    def test_retention_days_moves_the_cutoff_and_help_states_the_default(self):
        cache = os.path.join(self.home, ".cache", "tezgah")
        path = os.path.join(cache, "turns", "s.json")
        os.makedirs(os.path.dirname(path))
        with open(path, "w") as fh:
            fh.write('{"root": "/r"}')
        age = time.time() - 10 * 86400
        os.utime(path, (age, age))
        self.assertEqual(self.doctor("--clean").returncode, 0)
        self.assertEqual(support.store_keys(cache, "turns"), ["s"])
        self.assertEqual(self.doctor("--clean", "--retention-days", "7").returncode, 0)
        self.assertEqual(support.store_keys(cache, "turns"), [])
        self.assertIn("default: 30 days",
                      " ".join(self.doctor("--help").stdout.split()))
        self.assertEqual(self.doctor("--retention-days", "0").returncode, 2)

    def test_json_reports_the_index_bytes_per_repo(self):
        indexed = self.make_repo("indexed", index_bytes=500)
        self.make_repo("plain")
        proc = self.doctor("--json")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        rep = json.loads(proc.stdout)
        self.assertEqual(rep["codegraph_bytes"], 500)
        self.assertEqual(self.indexed(rep)[indexed]["bytes"], 500)
        self.assertTrue(self.indexed(rep)[indexed]["indexed"])
        self.assertEqual(rep["opencode_sessions"], 0)
        self.assertEqual(rep["opencode_events"], 0)
        # the report is about codegraph's store: no engine it replaced may be
        # named in it, in the JSON or in the text
        self.assertNotIn("cbm", proc.stdout)
        text = self.doctor()
        self.assertEqual(text.returncode, 0, text.stderr)
        self.assertNotIn("cbm", text.stdout)

    def test_a_repo_with_no_index_is_reported_as_having_none(self):
        plain = self.make_repo("plain")
        proc = self.doctor("--json")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        row = self.indexed(json.loads(proc.stdout))[plain]
        self.assertEqual((row["bytes"], row["indexed"]), (0, False))
        text = self.doctor().stdout
        self.assertIn("plain", text)
        self.assertIn("no index", text)

    def test_a_named_repo_replaces_the_configured_roots(self):
        # `--repo` is how a user accounts for a checkout outside every root: the
        # roots' own repos are then not walked at all
        self.make_repo("from-root", index_bytes=100)
        outside = os.path.join(self.home, "elsewhere")
        os.makedirs(outside, exist_ok=True)
        named = self.make_repo("named", index_bytes=42, root=outside)
        proc = self.doctor("--json", "--repo", named)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        rep = json.loads(proc.stdout)
        self.assertEqual(list(self.indexed(rep)), [named])
        self.assertEqual(self.indexed(rep)[named]["bytes"], 42)


class RepairEvidence(DoctorBase):
    """`--repair-evidence` over a cache whose legacy ledgers the device-id bug
    imported more than once: one file imported twice whole, one legitimately
    holding a line twice, one imported three times whole."""

    def setUp(self):
        super().setUp()
        sys.path.insert(0, support.HOOKS)
        import tezgah_store
        self.cache = os.path.join(self.home, ".cache", "tezgah")
        self.store = os.path.join(self.cache, tezgah_store.CACHE_DB)
        tezgah_store.connect(self.store, tezgah_store.CACHE_SCHEMA,
                             tezgah_store.CACHE_VERSION).close()
        con = sqlite3.connect(self.store)
        with con:
            # imported whole twice, a row written straight to the database between
            self.ledger(con, "dup", ["a", "b", "a"], [3, 3], direct=["x"])
            self.ledger(con, "legit", ["c", "c"], [2])
            self.ledger(con, "three", ["d"], [1, 1, 1])
        con.close()

    def ledger(self, con, session, lines, streams, direct=()):
        """A legacy ledger holding `lines`, imported once per entry of `streams`
        - that many of its first lines, from offset 0, under device id + i - as
        the device-id bug did, with `direct` rows written to the database after
        the first import."""
        path = os.path.join(self.cache, "evidence", session + ".jsonl")
        os.makedirs(os.path.dirname(path), exist_ok=True)
        rows = ['{"detail":"%s"}' % line for line in lines]
        with open(path, "w") as fh:
            fh.write("".join(row + "\n" for row in rows))
        st = os.stat(path)
        for i, count in enumerate(streams):
            con.execute("INSERT INTO imported (name, dev, ino, bytes) VALUES (?, ?, ?, ?)",
                        (session + ".jsonl", st.st_dev + i, st.st_ino,
                         sum(len(row) + 1 for row in rows[:count])))
            con.executemany("INSERT INTO evidence (session, row) VALUES (?, ?)",
                            [(session, row) for row in rows[:count]])
            if i == 0:
                con.executemany("INSERT INTO evidence (session, row) VALUES (?, ?)",
                                [(session, '{"detail":"%s"}' % d) for d in direct])

    def rows(self, db=None, sessions=("dup", "legit", "three")):
        con = sqlite3.connect(db or self.store)
        try:
            return {s: [r for (r,) in con.execute(
                "SELECT row FROM evidence WHERE session = ? ORDER BY n", (s,))]
                for s in sessions}
        finally:
            con.close()

    def imported(self, name):
        con = sqlite3.connect(self.store)
        try:
            return con.execute("SELECT dev, ino, bytes FROM imported WHERE name = ? "
                               "ORDER BY dev", (name,)).fetchall()
        finally:
            con.close()

    def test_the_dry_run_counts_every_extra_import_and_the_apply_leaves_one(self):
        before = self.rows()
        proc = self.doctor("--repair-evidence")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        # dup: the second import put a, b, a in again -> those three go, x stays
        self.assertIn("  dup  3 row(s)\n", proc.stdout)
        # three: the second and the third import are both copies -> two go
        self.assertIn("  three  2 row(s)\n", proc.stdout)
        self.assertNotIn("legit", proc.stdout)
        self.assertNotIn("manual review", proc.stdout)
        self.assertIn("total 5 row(s) in 2 session(s)", proc.stdout)
        self.assertEqual(self.rows(), before)  # a dry run writes nothing

        proc = self.doctor("--repair-evidence", "--apply")
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        self.assertIn("re-check: 0 row(s) missing, 0 row(s) left", proc.stdout)
        after = self.rows()
        self.assertEqual(after["dup"],
                         ['{"detail":"%s"}' % s for s in "abax"])
        self.assertEqual(after["legit"], before["legit"])
        self.assertEqual(after["three"], ['{"detail":"d"}'])
        self.assertEqual(len(self.imported("dup.jsonl")), 1)
        self.assertEqual(len(self.imported("three.jsonl")), 1)
        backup = [line.split(None, 1)[1] for line in proc.stdout.splitlines()
                  if line.startswith("  backup ")]
        self.assertEqual(len(backup), 1, proc.stdout)
        self.assertTrue(os.path.basename(backup[0]).startswith("tezgah.db.bak-"))
        self.assertEqual(self.rows(backup[0]), before)

        proc = self.doctor("--repair-evidence")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("total 0 row(s) in 0 session(s)", proc.stdout)

    def test_a_row_only_the_longest_import_took_is_never_a_copy(self):
        # the file grew between the imports (a, then a, b, a); a row written to
        # the database equal to b is a row of its own: a rule that kept one
        # import's worth of each line (held - k) would take it as a copy
        con = sqlite3.connect(self.store)
        with con:
            self.ledger(con, "grew", ["a", "b", "a"], [1, 3], direct=["b"])
        con.close()
        proc = self.doctor("--repair-evidence")
        # only the first import's a is a copy
        self.assertIn("  grew  1 row(s)\n", proc.stdout)
        proc = self.doctor("--repair-evidence", "--apply")
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        self.assertEqual(sorted(self.rows(sessions=("grew",))["grew"]),
                         sorted('{"detail":"%s"}' % s for s in "abab"))

    def test_the_store_s_rows_after_the_bug_and_two_renumbers_repair_to_one_copy(self):
        # the store's write path and the repair's reader are two readings of
        # one rule: whatever rows the store leaves after the bug, the repair
        # finds every copy from them and nothing else
        import tezgah_store
        path = os.path.join(self.cache, "evidence", "live.jsonl")

        def append(line):
            with open(path, "a") as fh:
                fh.write('{"detail":"%s"}\n' % line)

        def forget():
            held = tezgah_store._HELD.pop(self.store, None)
            if held:
                held[0].close()

        def bug(dev_offset):
            # the store before the fix: the whole file again, from offset 0,
            # under another device id
            st = os.stat(path)
            con = sqlite3.connect(self.store)
            with con, open(path) as fh:
                con.execute("INSERT INTO imported (name, dev, ino, bytes) VALUES (?, ?, ?, ?)",
                            ("live.jsonl", st.st_dev + dev_offset, st.st_ino, st.st_size))
                con.executemany("INSERT INTO evidence (session, row) VALUES ('live', ?)",
                                [(line,) for line in fh.read().splitlines()])
            con.close()

        append("a")
        tezgah_store.import_session(path)  # this device id: a
        forget()
        append("b")
        bug(1)  # a, b
        append("c")
        bug(2)  # a, b, c
        append("d")
        tezgah_store.import_session(path)  # this id again, its own row the shortest
        forget()
        con = sqlite3.connect(self.store)
        with con:  # a remount renumbers every row's device id
            con.execute("UPDATE imported SET dev = dev + 10 WHERE name = 'live.jsonl'")
        con.close()
        append("e")
        tezgah_store.import_session(path)
        forget()
        proc = self.doctor("--repair-evidence", "--apply")
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        self.assertEqual(sorted(self.rows(sessions=("live",))["live"]),
                         ['{"detail":"%s"}' % s for s in "abcde"])
        self.assertIn("re-check: 0 row(s) missing, 0 row(s) left", proc.stdout)

    def test_a_recheck_off_the_plan_rolls_the_repair_back(self):
        # triggers stand in for a deletion gone wrong: one of dup's copies
        # refuses to go, and three loses every row with its first copy
        con = sqlite3.connect(self.store)
        with con:
            con.execute("CREATE TRIGGER keep BEFORE DELETE ON evidence WHEN old.session = 'dup' "
                        "AND old.row = '{\"detail\":\"b\"}' BEGIN SELECT RAISE(IGNORE); END")
            con.execute("CREATE TRIGGER sweep AFTER DELETE ON evidence WHEN old.session = 'three' "
                        "BEGIN DELETE FROM evidence WHERE session = 'three'; END")
        con.close()
        before = self.rows()
        proc = self.doctor("--repair-evidence", "--apply")
        self.assertEqual(proc.returncode, 1, proc.stdout + proc.stderr)
        self.assertIn("re-check: 1 row(s) missing, 1 row(s) left", proc.stdout)
        self.assertEqual(self.rows(), before)
        self.assertEqual(len(self.imported("dup.jsonl")), 2)

    def test_a_file_rewritten_in_place_below_its_imports_is_not_repaired(self):
        # imported whole (long, b, b) and once more up to the long line, then
        # rewritten in place to one b: its imports no longer read what the
        # file holds, so no b may go for the long line's copy
        import tezgah_store
        path = os.path.join(self.cache, "evidence", "cut.jsonl")
        long_line = '{"detail":"%s"}\n' % ("l" * 40)
        with open(path, "w") as fh:
            fh.write(long_line + '{"detail":"b"}\n' * 2)
        tezgah_store.import_session(path)
        st = os.stat(path)
        con = sqlite3.connect(self.store)
        with con:
            con.execute("INSERT INTO imported (name, dev, ino, bytes) VALUES (?, ?, ?, ?)",
                        ("cut.jsonl", st.st_dev + 1, st.st_ino, len(long_line)))
            con.execute("INSERT INTO evidence (session, row) VALUES ('cut', ?)",
                        (long_line.strip(),))
        con.close()
        with open(path, "r+") as fh:  # the same inode
            fh.truncate(0)
            fh.write('{"detail":"b"}\n')
        tezgah_store.import_session(path)
        held = tezgah_store._HELD.pop(self.store, None)
        if held:
            held[0].close()
        before = self.rows(sessions=("cut",))
        proc = self.doctor("--repair-evidence", "--apply")
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        self.assertEqual(self.rows(sessions=("cut",)), before)

    def test_a_session_its_imports_do_not_explain_is_left_whole(self):
        # lost: two whole imports of e, f put e in twice, but the session holds
        # it once - a lost row, or a row that only continued another import -
        # so f's second copy is not counted as one either. gone: its file is no
        # longer there to count the copies by.
        con = sqlite3.connect(self.store)
        with con:
            self.ledger(con, "lost", ["e", "f"], [2, 2])
            con.execute("DELETE FROM evidence WHERE n = (SELECT min(n) FROM evidence "
                        "WHERE session = 'lost')")
            self.ledger(con, "gone", ["g"], [1, 1])
        con.close()
        os.remove(os.path.join(self.cache, "evidence", "gone.jsonl"))
        proc = self.doctor("--repair-evidence", "--apply")
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        self.assertIn("  lost  manual review: 1 line(s) held fewer times than its imports "
                      "put them in\n", proc.stdout)
        self.assertIn("  gone  skipped: its file is gone, replaced or shorter than its "
                      "imports\n", proc.stdout)
        after = self.rows(sessions=("lost", "gone"))
        self.assertEqual(after["lost"], ['{"detail":"%s"}' % s for s in "fef"])
        self.assertEqual(after["gone"], ['{"detail":"g"}'] * 2)
        self.assertEqual(len(self.imported("lost.jsonl")), 2)


class Coverage(DoctorBase):
    """The `--coverage` report over one repo: a stub index dump, four tracked
    files, and no codegraph on the machine."""

    INDEX = {"files": [{"path": "app.py"}, {"path": "bin/twin.py"}]}

    def setUp(self):
        super().setUp()
        self.repo = os.path.join(self.home, "covered")
        os.makedirs(os.path.join(self.repo, "bin"))
        self.write("app.py", "print(1)\n")
        self.write("missing.py", "print(2)\n")
        self.write("bin/twin", "#!/usr/bin/env python3\nprint(3)\n")
        self.write("bin/twin.py", "print(3)\n")
        self.write("bin/tool", "#!/usr/bin/env python3\nprint(4)\n")
        self.write("notes.md", "# notes\n")
        git(self.repo, "init", "-q")
        git(self.repo, "add", ".")
        self.dump = os.path.join(self.home, "dump.json")
        with open(self.dump, "w") as fh:
            json.dump(self.INDEX, fh)

    def write(self, rel, text, mode=0o644):
        path = os.path.join(self.repo, rel)
        with open(path, "w") as fh:
            fh.write(text)
        os.chmod(path, mode)
        return path

    def stub_codegraph(self):
        """A `codegraph` that answers `files -j` with the fixture dump, so the
        live path is exercised without the real binary or npx."""
        script = os.path.join(self.home, "stub-codegraph")
        with open(script, "w") as fh:
            fh.write("#!/bin/sh\ncat <<'JSON'\n%s\nJSON\n" % json.dumps(self.INDEX))
        os.chmod(script, 0o755)
        return script

    def coverage(self, *args, env=None):
        return self.doctor("--coverage", "--repo", self.repo, *args,
                           env=env or self.env)

    def test_coverage_lists_the_missing_supported_file_and_the_script(self):
        env = dict(self.env, TEZGAH_CODEGRAPH_BIN=self.stub_codegraph())
        proc = self.coverage(env=env)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        # the counts come first, so an empty report cannot read as full coverage
        self.assertIn("tracked files read: 6 | files the index holds: 2", proc.stdout)
        self.assertIn("uncovered, supported extension (1):", proc.stdout)
        self.assertIn("missing.py (python)", proc.stdout)
        self.assertIn("uncovered, shebang-only script with no `.py` twin (1):",
                      proc.stdout)
        self.assertIn("bin/tool (python3)", proc.stdout)
        # a supported file the index holds, and an extension it has no parser
        # for, are neither of them gaps
        self.assertNotIn("app.py", proc.stdout)
        self.assertNotIn("notes.md", proc.stdout)

    def test_a_script_with_an_indexed_py_twin_counts_as_covered(self):
        env = dict(self.env, TEZGAH_CODEGRAPH_BIN=self.stub_codegraph())
        proc = self.coverage(env=env)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("covered through a `.py` twin (1)", proc.stdout)
        self.assertNotIn("bin/twin (", proc.stdout)

    def test_coverage_reads_a_dump_with_no_codegraph_installed(self):
        proc = self.coverage("--dump", self.dump)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("tracked files read: 6 | files the index holds: 2", proc.stdout)
        self.assertIn("missing.py (python)", proc.stdout)

    def test_coverage_is_a_report_when_the_dump_cannot_be_read(self):
        # no dump and no codegraph anywhere: the run still exits 0, and it says
        # what it could not read instead of printing an empty file list
        proc = self.coverage()
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("could not read an index dump", proc.stdout)
        self.assertNotIn("tracked files read", proc.stdout)


if __name__ == "__main__":
    unittest.main()
