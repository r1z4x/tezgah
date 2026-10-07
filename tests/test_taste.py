"""hooks/tezgah_taste.py: the opt-in capture of prompts, edits and the bytes an
edit left behind.

Run in-process with tezgah_paths' kill-switch dirs and cache pointed into a temp
HOME, so the real ~/.config/tezgah and ~/.cache are never read or written; the
opencode entry point runs in a subprocess with that HOME.
"""
import hashlib
import json
import os
import stat
import subprocess
import sys
import types
import unittest
from unittest import mock

import support
from support import TempHome

sys.path.insert(0, support.HOOKS)
import tezgah_integrity as ti  # noqa: E402
import tezgah_paths as tp  # noqa: E402
import tezgah_snapshot as ts  # noqa: E402
import tezgah_store as store  # noqa: E402
import tezgah_taste as tt  # noqa: E402

TOKEN = "ghp_" + "a1B2c3D4e5F6g7H8i9J0k1L2"
SESSION = "s-taste"


class Taste(TempHome):

    def setUp(self):
        super().setUp()
        self.repo = self.make_repo("proj")
        subprocess.run(["git", "init", "-q", self.repo], check=True)
        with open(os.path.join(self.repo, ".gitignore"), "w") as fh:
            fh.write("/.tezgah/\n")
        os.makedirs(os.path.join(self.repo, ".tezgah"))
        self.config_dir = os.path.join(self.home, ".config", "tezgah")
        os.makedirs(self.config_dir)
        for name, value in (("OFF_DIRS", (self.config_dir,)),
                            ("CACHE", os.path.join(self.home, ".cache", "tezgah"))):
            self.addCleanup(setattr, tp, name, getattr(tp, name))
            setattr(tp, name, value)
        env = mock.patch.dict(os.environ, {"TEZGAH_ROOTS": self.roots})
        env.start()
        self.addCleanup(env.stop)
        self.store = os.path.join(self.repo, ".tezgah", "taste")

    def arm(self):
        open(os.path.join(self.config_dir, tt.ARM), "w").close()

    def rows(self, kind=None):
        with store.taste(self.store, create=False) as db:
            rows = store.rows(db, "signals") if db else []
        return [r for r in rows if kind is None or r["kind"] == kind]

    def write(self, name, text):
        path = os.path.join(self.repo, name)
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(text)
        return path

    def edit(self, inp, failed=False):
        ti.note_tool(SESSION, "Edit", inp, failed, cwd=self.repo)

    def test_default_off_writes_nothing_and_keeps_no_blob(self):
        self.write("a.py", "x = 2\n")
        tt.note_prompt(SESSION, "rename it", self.repo)
        self.edit({"file_path": "a.py", "old_string": "x = 1", "new_string": "x = 2"})
        self.assertFalse(os.path.exists(os.path.join(self.repo, ".tezgah", "taste")))
        self.assertFalse(os.path.exists(ts._store()))

    def test_armed_prompt_row_is_redacted_and_owner_only(self):
        self.arm()
        tt.note_prompt(SESSION, "use pathlib, key " + TOKEN, self.repo, host="claude")
        [row] = self.rows()
        self.assertEqual((row["v"], row["kind"], row["session"], row["host"]),
                         (1, "prompt", SESSION, "claude"))
        self.assertNotIn(TOKEN, row["text"])
        self.assertEqual(row["text"], ti.redact("use pathlib, key " + TOKEN))
        self.assertNotIn("cut", row)
        self.assertRegex(row["ts"], r"\A\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ\Z")
        # owner-only: the directory, the database and, while a connection
        # holds them open, its WAL sidecars
        self.assertEqual(stat.S_IMODE(os.stat(self.store).st_mode), 0o700)
        db = os.path.join(self.store, store.TASTE_DB)
        conn = store.connect(db, store.REPO_SCHEMA)
        self.addCleanup(conn.close)
        conn.execute("SELECT count(*) FROM signals").fetchone()
        for path in (db, db + "-wal", db + "-shm"):
            self.assertEqual(stat.S_IMODE(os.stat(path).st_mode), 0o600, path)

    def test_long_prompt_and_edit_are_cut_and_flagged(self):
        self.arm()
        tt.note_prompt(SESSION, "p" * 2500, self.repo)
        tt.note_write(SESSION, "id1", {"file_path": "a.py", "old_string": "o",
                                       "new_string": "n" * 5000}, self.repo)
        prompt, edit = [r for r in self.rows() if r["kind"] != "after"]
        self.assertEqual((len(prompt["text"]), prompt["cut"]), (2000, True))
        self.assertEqual((len(edit["new"]), edit["old"], edit["cut"]), (4000, "o", True))

    def test_no_taste_mark_disables(self):
        self.arm()
        open(os.path.join(self.repo, tt.MARK), "w").close()
        tt.note_prompt(SESSION, "rename it", self.repo)
        self.assertEqual(self.rows(), [])

    def test_missing_workspace_is_never_created(self):
        self.arm()
        os.rmdir(os.path.join(self.repo, ".tezgah"))
        tt.note_prompt(SESSION, "rename it", self.repo)
        self.assertFalse(os.path.exists(os.path.join(self.repo, ".tezgah")))

    def test_repository_provided_workspace_is_skipped(self):
        self.arm()
        os.rmdir(os.path.join(self.repo, ".tezgah"))
        os.makedirs(os.path.join(self.repo, "notes"))
        os.symlink("notes", os.path.join(self.repo, ".tezgah"))
        tt.note_prompt(SESSION, "rename it", self.repo)
        self.assertFalse(os.path.exists(os.path.join(self.repo, "notes", "taste")))

    def test_edit_row_carries_the_ledger_id_and_the_after_blob_bytes(self):
        self.arm()
        path = self.write("a.py", "x = 2\n")
        inp = {"file_path": "a.py", "old_string": "x = 1", "new_string": "x = 2 " + TOKEN}
        self.edit(inp)
        ledger = [r for r in ti.events(SESSION) if r.get("kind") == "edit"]
        [edit] = self.rows("edit")
        [after] = self.rows("after")
        self.assertEqual(edit["id"], ledger[-1]["id"])
        self.assertEqual((edit["path"], edit["old"]), ("a.py", "x = 1"))
        self.assertNotIn(TOKEN, edit["new"])
        with open(path, "rb") as fh:
            disk = fh.read()
        with open(ts._blob(after["snapshot"]), "rb") as fh:
            self.assertEqual(fh.read(), disk)
        self.assertEqual(after["sha"], hashlib.sha256(disk).hexdigest())
        self.assertEqual(after["path"], "a.py")
        # an after blob is no pre-state: no `snapshot` ledger row names it
        self.assertFalse([r for r in ti.events(SESSION) if r.get("kind") == "snapshot"])

    def test_write_and_patch_shapes(self):
        self.arm()
        self.write("w.py", "body\n")
        self.edit({"file_path": "w.py", "content": "body\n"})
        patch = "*** Begin Patch\n*** Update File: w.py\n@@\n-a\n+b\n*** End Patch"
        tt.note_write(SESSION, "id2", {"patch": patch}, self.repo)
        write, applied = self.rows("edit")
        self.assertEqual((write["old"], write["new"]), (None, "body\n"))
        self.assertEqual((applied["path"], applied["old"], applied["new"]),
                         ("w.py", None, patch))

    def test_failed_edit_and_credential_file_record_nothing(self):
        self.arm()
        self.write("a.py", "x\n")
        self.edit({"file_path": "a.py", "old_string": "y", "new_string": "x"}, failed=True)
        self.write(".env", "KEY=v\n")
        self.edit({"file_path": ".env", "content": "KEY=v\n"})
        self.assertEqual(self.rows(), [])
        self.assertFalse(os.path.exists(ts._store()))

    def test_opencode_entry_point_writes_the_same_rows(self):
        self.arm()
        self.write("a.py", "y = 1\n")
        payload = {"session_id": SESSION, "id": "abc123", "cwd": self.repo,
                   "host": "opencode",
                   "input": {"filePath": "a.py", "oldString": "y = 0",
                             "newString": "y = 1"}}
        proc = subprocess.run(
            [sys.executable, os.path.join(support.HOOKS, "tezgah_taste.py"),
             json.dumps(payload)],
            env=self.env(), capture_output=True, text=True, timeout=60)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        edit, after = self.rows()
        self.assertEqual((edit["id"], edit["host"], edit["old"], edit["new"]),
                         ("abc123", "opencode", "y = 0", "y = 1"))
        self.assertEqual(after["kind"], "after")

    def test_write_outside_the_repository_keeps_no_blob(self):
        self.arm()
        outside = os.path.join(self.home, "outside.txt")
        with open(outside, "w") as fh:
            fh.write("elsewhere\n")
        tt.note_write(SESSION, "id3", {"file_path": outside, "content": "elsewhere\n"},
                      self.repo)
        self.assertEqual(self.rows(), [])
        self.assertFalse(os.path.exists(ts._store()))

    def test_view_records_nothing_and_notebook_source_is_the_new_text(self):
        self.arm()
        self.write("n.ipynb", "{}\n")
        tt.note_write(SESSION, "id4", {"command": "view", "path": "n.ipynb"}, self.repo)
        self.assertEqual(self.rows(), [])
        tt.note_write(SESSION, "id5", {"notebook_path": "n.ipynb",
                                       "new_source": "print(1)"}, self.repo)
        [edit] = self.rows("edit")
        self.assertEqual((edit["old"], edit["new"]), (None, "print(1)"))

    def spawns(self, typesafe=True):
        """The (argv, kwargs) `learn_later` starts, recorded instead of run; a
        TypeSafe key resolves unless `typesafe` is False."""
        spawned = []
        # tezgah_taste's own `subprocess` name only: git, which the session start
        # also runs, keeps the real module
        stub = types.SimpleNamespace(DEVNULL=subprocess.DEVNULL,
                                     Popen=lambda argv, **kw: spawned.append((argv, kw)))
        popen = mock.patch.object(tt, "subprocess", stub)
        popen.start()
        self.addCleanup(popen.stop)
        key = mock.patch.dict(os.environ, {"TYPESAFE_API_KEY": "k"} if typesafe else {})
        key.start()
        self.addCleanup(key.stop)
        if not typesafe:
            os.environ.pop("TYPESAFE_API_KEY", None)
        return spawned

    def start(self, event="session_start"):
        """A host's session start, through the one path every host takes."""
        import tezgah_context
        tezgah_context.context_for(event, self.repo, {"session_id": "s-learn"})

    def grow(self):
        with store.taste(self.store) as db:
            store.append(db, "signals", {"kind": "prompt"})

    def stamps(self):
        base = os.path.join(tp.cache_dir(), "taste-learn")
        return [os.path.join(base, n) for n in os.listdir(base)
                if n.endswith(".json")] if os.path.isdir(base) else []

    def age_stamp(self):
        [path] = self.stamps()
        with open(path, encoding="utf-8") as fh:
            stamp = json.load(fh)
        stamp["at"] -= tt.LEARN_EVERY + 1
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(stamp, fh)

    def test_session_start_spawns_a_detached_typed_learn_on_growth_at_most_hourly(self):
        spawned = self.spawns()
        self.arm()
        self.grow()
        self.start()
        [(argv, kw)] = spawned
        self.assertEqual(argv[-4:], ["learn", "--repo", os.path.realpath(self.repo),
                                     "--no-fallback"])
        self.assertTrue(kw["start_new_session"])
        self.assertIs(kw["stdin"], subprocess.DEVNULL)
        self.assertIsNotNone(kw["stdout"])
        self.grow()
        self.start()  # grew, but within the hour
        self.assertEqual(len(spawned), 1)
        self.age_stamp()
        self.start()  # the hour passed and the signals grew since the stamp
        self.assertEqual(len(spawned), 2)
        self.age_stamp()
        self.start()  # the hour passed, the size did not change
        self.assertEqual(len(spawned), 2)

    def test_only_session_start_spawns(self):
        spawned = self.spawns()
        self.arm()
        self.grow()
        for event in ("post_compact", "subagent_start", "user_prompt"):
            self.start(event)
        self.assertEqual(spawned, [])

    def test_no_spawn_unarmed_with_no_taste_or_without_typesafe(self):
        spawned = self.spawns()
        self.grow()
        self.start()
        self.assertEqual((spawned, self.stamps()), ([], []))
        self.arm()
        open(os.path.join(self.repo, tt.MARK), "w").close()
        self.start()
        self.assertEqual(spawned, [])
        os.remove(os.path.join(self.repo, tt.MARK))
        spawned = self.spawns(typesafe=False)
        self.start()
        self.assertEqual((spawned, self.stamps()), ([], []))


if __name__ == "__main__":
    unittest.main()
