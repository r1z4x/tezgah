"""The cache stores of `<cache>/tezgah.db` (ADR 021, plan 071 phase 3): the
one-time import of the files each store kept before (tezgah_store.CACHE_LEGACY).

Each store group is seeded with the files its hooks wrote, one of them damaged.
The first open of the database takes the rest in and deletes them all; a later
open, as a new process makes it, imports nothing, and removes a file put back
unread."""
import json
import os
import shutil
import sys
import tempfile
import time
import unittest
from unittest import mock

import support

sys.path.insert(0, support.HOOKS)
import tezgah_store as ts  # noqa: E402

NOT_UTF8 = b'{"kind": "x\xff"}\n'


class Import(unittest.TestCase):
    def setUp(self):
        self.cache = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.cache, True)
        self.addCleanup(self.reopen)

    def path(self, rel):
        return os.path.join(self.cache, *rel.split("/"))

    def put(self, rel, data, mtime=None):
        """A legacy file at `rel` under the cache (text or bytes)."""
        path = self.path(rel)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "wb") as fh:
            fh.write(data if isinstance(data, bytes) else data.encode("utf-8"))
        if mtime is not None:
            os.utime(path, (mtime, mtime))
        return path

    def reopen(self):
        """Drop the held connection: the next call opens the database the way
        a new process does."""
        held = ts._HELD.pop(os.path.join(self.cache, ts.CACHE_DB), None)
        if held:
            held[0].close()

    def absent(self, *rels):
        for rel in rels:
            self.assertFalse(os.path.exists(self.path(rel)), rel)

    def done(self):
        """The stores the database records as imported."""
        return sorted(name for (name,) in support.cache_rows(
            self.cache, "SELECT name FROM imported WHERE name LIKE 'legacy:%'"))

    def second_open(self, rel, data, unchanged, stays=False):
        """Put a legacy file back at `rel`, open again: `unchanged()` still
        holds, the file is not read and is removed (kept with `stays`), and
        every store is done once."""
        self.put(rel, data)
        self.reopen()
        unchanged()
        self.assertEqual(os.path.exists(self.path(rel)), stays, rel)
        self.assertEqual(self.done(), sorted("legacy:" + t for t in ts.CACHE_LEGACY))

    def test_documents(self):
        self.put("turns/s1.json", json.dumps({"root": "/a"}), mtime=1000)
        self.put("turns/bad.json", "{not json")
        self.put("switches/s1.json", json.dumps({"start": [], "seen": ["x"]}))
        self.put("harness-drift/abc.claude", "a; b\n")
        self.put("import-crash/abc", "import: ImportError: x\n")
        self.put("judge-last.json", json.dumps({"provider": "p"}))
        self.put("update.json", "{not json")
        self.put("skill-pick/s1.json", json.dumps({"d": "line"}))
        self.put("skill-section-hint/s1.json", json.dumps(["a.md:1"]))
        self.put("answer/s1", "the reply")
        self.put("taste-learn/repo.json", json.dumps({"rows": 3, "at": 1}))
        self.put("taste-learn/repo.log", "kept")

        def imported():
            self.assertEqual(ts.doc("turns", "s1", self.cache), {"root": "/a"})
            self.assertIsNone(ts.doc("turns", "bad", self.cache))
            self.assertEqual(ts.doc("switches", "s1", self.cache), {"start": [], "seen": ["x"]})
            self.assertEqual(ts.doc("harness_drift", "abc.claude", self.cache), "a; b\n")
            self.assertEqual(ts.doc("import_crash", "abc", self.cache), "import: ImportError: x\n")
            self.assertEqual(ts.doc("judge_last", "", self.cache), {"provider": "p"})
            self.assertIsNone(ts.doc("update_check", "", self.cache))
            self.assertEqual(ts.doc("skill_pick", "s1", self.cache), {"d": "line"})
            self.assertEqual(ts.doc("section_hint", "s1", self.cache), ["a.md:1"])
            self.assertEqual(ts.doc("cursor_answer", "s1", self.cache), "the reply")
            self.assertEqual(ts.doc("taste_learn", "repo", self.cache), {"rows": 3, "at": 1})

        imported()
        # `at` is the file's mtime, the age the doctor's sweep reads
        self.assertEqual(support.cache_rows(self.cache, "SELECT at FROM turns WHERE key = 's1'"),
                         [(1000.0,)])
        self.absent("turns", "switches", "harness-drift", "import-crash", "judge-last.json",
                    "update.json", "skill-pick", "skill-section-hint", "answer",
                    "taste-learn/repo.json")
        self.assertEqual(os.listdir(self.path("taste-learn")), ["repo.log"])
        self.second_open("turns/s1.json", json.dumps({"root": "/b"}), imported)

    def test_marks(self):
        self.put("gate-inactive/s1", "")
        # a mark is its name and its mtime: a file nobody can read still counts
        os.chmod(self.put("nudged/abcd", NOT_UTF8), 0)
        self.put("reinforced/s1/tag1", "")
        self.put("reinforced/s1/tag2", "")

        def imported():
            self.assertTrue(ts.marked("gate_inactive", "s1", self.cache))
            self.assertTrue(ts.marked("nudged", "abcd", self.cache))
            self.assertEqual(support.store_keys(self.cache, "cursor_reinforced"),
                             ["s1/tag1", "s1/tag2"])

        imported()
        # an imported mark is spent, as the file was
        self.assertFalse(ts.mark("nudged", "abcd", self.cache))
        self.absent("gate-inactive", "nudged", "reinforced")
        self.second_open("gate-inactive/s2", "",
                         lambda: self.assertFalse(ts.marked("gate_inactive", "s2", self.cache)))

    def test_used(self):
        self.put("sessions/s1.jsonl", '{"kind": "graph"}\n{"kind": "consult"}\n'
                 '{"kind": 5}\n{"kind": "jud', mtime=1000)
        self.put("sessions/s2.jsonl", '{"kind": "judge"}\n', mtime=2000)
        self.put("sessions/bad.jsonl", NOT_UTF8)

        def imported():
            self.assertEqual(ts.used("s1", self.cache), {"graph", "consult"})
            self.assertEqual(ts.used("bad", self.cache), set())
            # the window is the time each session last recorded: the mtime
            self.assertEqual(ts.used_sessions(1, self.cache), ([{"judge"}], 2))

        imported()
        self.absent("sessions")
        self.second_open("sessions/s1.jsonl", '{"kind": "research"}\n', imported)

    def test_judge_down(self):
        now = time.time()
        self.put("judge-down/k1", "", mtime=now - 10)
        os.chmod(self.put("judge-down/k2", NOT_UTF8, mtime=now - 20), 0)

        def imported():
            # a marker was down for DOWN_FOR from its mtime
            self.assertAlmostEqual(ts.down_until("k1", self.cache),
                                   now - 10 + ts.LEGACY_DOWN_FOR, places=3)
            self.assertAlmostEqual(ts.down_until("k2", self.cache),
                                   now - 20 + ts.LEGACY_DOWN_FOR, places=3)
            self.assertIsNone(ts.down_until("k3", self.cache))

        imported()
        self.absent("judge-down")
        self.second_open("judge-down/k3", "", imported)

    def test_lesson_taint(self):
        self.put("lessons/root1.jsonl",
                 '{"key": "k1", "source": "web", "ts": 5}\n'
                 '{"key": "k2", "source": "mail", "ts": 6}\n'
                 '{"key": "k1", "source": "pdf", "ts": 7}\n'
                 '{"no": "key"}\n{"key": "k3", "sour')
        self.put("lessons/bad.jsonl", NOT_UTF8)

        def imported():
            # a later row of a key wins, as the old reader's dict did
            self.assertEqual(ts.taint("root1", self.cache), {"k1": "pdf", "k2": "mail"})
            self.assertEqual(ts.taint("bad", self.cache), {})

        imported()
        self.absent("lessons")
        self.second_open("lessons/root1.jsonl", '{"key": "k9", "source": "x"}\n', imported)

    def test_snapshots(self):
        # capture order is each directory's mtime, not its name
        for sid, at, meta in (("bbbbbbbbbbbb", 1000, json.dumps({"id": "bbbbbbbbbbbb"})),
                              ("aaaaaaaaaaaa", 2000, json.dumps({"id": "aaaaaaaaaaaa"})),
                              ("cccccccccccc", 3000, "{not json")):
            self.put("snapshots/%s/file" % sid, "bytes of " + sid)
            self.put("snapshots/%s/meta.json" % sid, meta)
            os.utime(self.path("snapshots/" + sid), (at, at))

        def imported():
            self.assertEqual([m["id"] for m in ts.snapshots(cache=self.cache)],
                             ["bbbbbbbbbbbb", "aaaaaaaaaaaa"])

        imported()
        # the manifests are rows now; the blobs stay where they were
        self.absent(*("snapshots/%s/meta.json" % sid
                      for sid in ("aaaaaaaaaaaa", "bbbbbbbbbbbb", "cccccccccccc")))
        for sid in ("aaaaaaaaaaaa", "bbbbbbbbbbbb"):
            with open(self.path("snapshots/%s/file" % sid), encoding="utf-8") as fh:
                self.assertEqual(fh.read(), "bytes of " + sid)
        # a done store's manifests are not looked for: one put back stays, and
        # an indexed one goes with its blob at eviction
        self.second_open("snapshots/cccccccccccc/meta.json",
                         json.dumps({"id": "cccccccccccc"}), imported, stays=True)

    def test_replay_runs(self):
        # the run key is the run directory's real path (tezgah_replay)
        runs = [os.path.realpath(self.path("replay/2026100%d-000000" % n)) for n in (1, 2, 3)]
        self.put("replay/20261001-000000/summary.json", json.dumps({"run": runs[0]}))
        self.put("replay/20261002-000000/summary.json", json.dumps({"run": runs[1]}))
        self.put("replay/20261003-000000/summary.json", "{not json")
        for n in (1, 2, 3):
            self.put("replay/2026100%d-000000/corpus.jsonl" % n, "{}\n")
        # `latest` named the first run, not the newest name
        self.put("replay/latest", runs[0] + "\n")

        def imported():
            self.assertEqual(ts.replay_latest(self.cache), runs[0])
            self.assertEqual(ts.replay_summary(runs[1], self.cache), {"run": runs[1]})
            self.assertIsNone(ts.replay_summary(runs[2], self.cache))

        imported()
        self.absent("replay/latest", *("replay/2026100%d-000000/summary.json" % n
                                       for n in (1, 2, 3)))
        # a run's own files stay
        for run in runs:
            self.assertEqual(os.listdir(run), ["corpus.jsonl"])
        self.second_open("replay/latest", runs[1] + "\n", imported)

    def everything(self):
        """One legacy file for every store; the keys it should import under."""
        self.put("sessions/s1.jsonl", '{"kind": "graph"}\n')
        self.put("judge-down/k1", "")
        self.put("lessons/root1.jsonl", '{"key": "k1", "source": "web"}\n')
        self.put("judge-last.json", json.dumps({"provider": "p"}))
        self.put("update.json", json.dumps({"latest": "9.9.9"}))
        self.put("snapshots/aaaaaaaaaaaa/meta.json", json.dumps({"id": "aaaaaaaaaaaa"}))
        self.put("replay/20261001-000000/summary.json", json.dumps({"n": 1}))
        self.put("reinforced/s1/tag", "")
        for table, name in ts.CACHE_LEGACY.items():
            if table in ts.DOC_STORES + ts.MARK_STORES and not os.path.exists(self.path(name)):
                self.put(name + "/k" + (".json" if table in (
                    "turns", "switches", "skill_pick", "section_hint", "taste_learn") else ""),
                    "{}")

    def all_in(self, but=()):
        """Every store but `but` imported and marked done."""
        self.assertEqual(self.done(), sorted("legacy:" + t for t in ts.CACHE_LEGACY
                                             if t not in but))
        self.assertEqual(ts.used("s1", self.cache) == {"graph"}, "used" not in but)
        self.assertEqual(ts.down_until("k1", self.cache) is not None, "judge_down" not in but)
        self.assertEqual(ts.taint("root1", self.cache), {} if "lesson_taint" in but
                         else {"k1": "web"})
        self.assertEqual(ts.doc("update_check", "", self.cache),
                         None if "update_check" in but else {"latest": "9.9.9"})
        self.assertEqual(len(ts.snapshots(cache=self.cache)), 0 if "snapshots" in but else 1)
        for table in ts.DOC_STORES + ts.MARK_STORES:
            if table not in but and table not in ("judge_last", "update_check",
                                                  "cursor_reinforced"):
                self.assertEqual(support.store_keys(self.cache, table), ["k"], table)

    def test_a_stray_file_costs_no_other_store_its_import(self):
        # a `.json` file in the used-kind store's directory was taken for a
        # document and its INSERT failed every store's one transaction
        self.everything()
        self.put("sessions/x.json", "{}")
        self.put("lessons/x.json", "{}")
        ts.used("s1", self.cache)
        self.all_in()
        # not a file of the store: left where it was
        self.assertTrue(os.path.exists(self.path("sessions/x.json")))

    def test_a_store_that_fails_costs_the_others_nothing(self):
        self.everything()
        legacy = ts._legacy

        def broken(cache, table):
            if table == "turns":
                raise UnicodeEncodeError("utf-8", "\udcff", 0, 1, "surrogates not allowed")
            return legacy(cache, table)

        with mock.patch.object(ts, "_legacy", broken):
            ts.used("s1", self.cache)
        self.all_in(but=("turns",))
        self.assertTrue(os.path.exists(self.path("turns/k.json")))
        # the next open takes it
        self.reopen()
        self.assertEqual(ts.doc("turns", "k", self.cache), {})
        self.all_in()

    def test_files_a_killed_import_left_go_on_the_next_open(self):
        # killed between the commit and the removal: the rows are in, the
        # store is done, and the files are still there
        self.everything()
        with mock.patch.object(ts.os, "remove", side_effect=OSError):
            ts.used("s1", self.cache)
        self.assertTrue(os.path.exists(self.path("sessions/s1.jsonl")))
        self.put("sessions/s1.jsonl", '{"kind": "consult"}\n')
        self.reopen()
        self.all_in()
        self.absent("sessions", "judge-down", "lessons", "judge-last.json", "update.json",
                    "reinforced", "replay/20261001-000000/summary.json", "turns/k.json")


if __name__ == "__main__":
    unittest.main()
