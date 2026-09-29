"""hooks/tezgah_snapshot.py, bin/tezgah-capture and bin/tezgah-rollback:
pre-write snapshots, the host-facing capture CLI, and the explicit rollback that
consumes one.

capture/restore run in-process with tezgah_paths.CACHE pointed at a temp dir, so
the real ~/.cache is never read or written; both CLIs run in a subprocess with a
throwaway HOME, as every other bin/ test here does.
"""
import hashlib
import json
import os
import subprocess
import sys
import unittest
from unittest import mock

import support
from support import TempHome

sys.path.insert(0, support.HOOKS)
import tezgah_integrity as ti  # noqa: E402
import tezgah_paths as tp  # noqa: E402
import tezgah_snapshot as ts  # noqa: E402

ROLLBACK = os.path.join(support.REPO, "bin", "tezgah-rollback")
CAPTURE = os.path.join(support.REPO, "bin", "tezgah-capture")


class Snap(TempHome):
    """A temp cache and a temp root, which is what both the store and the
    ledger key on. cache_dir() reads tezgah_paths.CACHE at call time, so
    patching it moves the store and the ledger together."""

    session = "s-snap"

    def setUp(self):
        super().setUp()
        self.repo = self.make_repo("proj")
        self.addCleanup(setattr, tp, "CACHE", tp.CACHE)
        tp.CACHE = os.path.join(self.home, ".cache", "tezgah")
        env = mock.patch.dict(os.environ, {"TEZGAH_ROOTS": self.roots})
        env.start()
        self.addCleanup(env.stop)

    def write(self, name, text):
        path = os.path.join(self.repo, name)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w") as fh:
            fh.write(text)
        return path

    def read(self, path):
        with open(path) as fh:
            return fh.read()

    def cap(self, name, text, tool="Edit"):
        self.write(name, text)
        return ts.capture(tool, {"file_path": name}, self.repo, self.session)

    def rows(self, kind=None):
        return [r for r in ti.events(self.session)
                if kind is None or r.get("kind") == kind]

    def store(self):
        d = os.path.join(tp.CACHE, "snapshots")
        return sorted(os.listdir(d)) if os.path.isdir(d) else []

    def blob(self, sid):
        """The stored bytes of a snapshot. The store layout is part of the
        module's own contract: rollback reads it, so a test may too."""
        return os.path.join(tp.CACHE, "snapshots", sid, "file")

    def rollback(self, *args):
        return subprocess.run(
            [sys.executable, ROLLBACK] + list(args), capture_output=True,
            text=True, env=support.base_env(self.home, [self.roots]))


class NothingToCapture(Snap):
    """capture returns None and leaves no row when there is no pre-state."""

    def test_a_non_write_tool_captures_nothing(self):
        self.write("a.py", "x = 1\n")
        for tool in ("Read", "Grep", "Bash", ""):
            self.assertIsNone(ts.capture(tool, {"file_path": "a.py"}, self.repo,
                                         self.session), tool)
        self.assertEqual(self.store(), [])
        self.assertEqual(self.rows(), [])

    def test_a_new_file_captures_nothing(self):
        # the first write of a file has no bytes to lose
        for inp in ({"file_path": "new.py", "content": "x"},
                    {"filePath": "new.py", "content": "x"},
                    {"file_path": "sub/../new.py", "content": "x"}):
            self.assertIsNone(ts.capture("Write", inp, self.repo, self.session))
        self.assertEqual(self.store(), [])

    def test_a_path_that_is_not_a_readable_file_captures_nothing(self):
        os.makedirs(os.path.join(self.repo, "adir"))
        for path in ("adir", "adir/missing.py", ""):
            self.assertIsNone(ts.capture("Edit", {"file_path": path}, self.repo,
                                         self.session), path)
        self.assertEqual(self.store(), [])

    def test_an_over_large_file_captures_nothing(self):
        with open(os.path.join(self.repo, "big.bin"), "wb") as fh:
            fh.write(b"x" * (ts.MAX_BYTES + 1))
        self.assertIsNone(ts.capture("Edit", {"file_path": "big.bin"}, self.repo,
                                     self.session))
        self.assertEqual(self.store(), [])
        self.assertEqual(self.rows(), [])

    def test_no_session_captures_nothing(self):
        self.write("a.py", "x = 1\n")
        for session in (None, ""):
            self.assertIsNone(ts.capture("Edit", {"file_path": "a.py"},
                                         self.repo, session))
        self.assertEqual(self.store(), [])


class CaptureStore(Snap):
    """The snapshot the gate takes on the way to a write."""

    def test_the_row_carries_the_id_path_hash_and_size(self):
        text = "one\ntwo\n"
        path = self.write("a.py", text)
        sid = ts.capture("Edit", {"file_path": "a.py"}, self.repo, self.session)
        rows = self.rows("snapshot")
        self.assertEqual(len(rows), 1)
        row = rows[0]
        self.assertEqual(row["id"], sid)
        self.assertEqual(row["detail"], path)
        self.assertEqual(row["hash"], hashlib.sha256(text.encode()).hexdigest())
        self.assertEqual(row["out_bytes"], len(text))
        self.assertEqual(row["workspace"], self.roots)
        self.assertIsInstance(row["ts"], int)
        self.assertEqual(self.read(self.blob(sid)), text)

    def test_a_relative_path_is_resolved_against_cwd(self):
        path = self.write("sub/b.py", "b\n")
        ts.capture("Edit", {"file_path": "sub/b.py"}, self.repo, self.session)
        self.assertEqual(self.rows("snapshot")[-1]["detail"], path)

    def test_each_capture_keeps_its_own_pre_state(self):
        first = self.cap("a.py", "v1\n")
        second = self.cap("a.py", "v2\n")
        self.assertNotEqual(first, second)
        self.assertEqual(self.read(self.blob(first)), "v1\n")
        self.assertEqual(self.read(self.blob(second)), "v2\n")
        self.assertEqual(len(self.rows("snapshot")), 2)

    def test_the_cap_evicts_the_oldest_and_keeps_the_newest(self):
        with mock.patch.object(ts, "CAP", 3):
            ids = [self.cap("f%d.py" % i, "%d\n" % i) for i in range(3)]
            for i, sid in enumerate(ids):  # capture order, made explicit
                stamp = 1000 + i
                os.utime(os.path.join(tp.CACHE, "snapshots", sid),
                         (stamp, stamp))
            newest = self.cap("f3.py", "3\n")
        self.assertEqual(self.store(), sorted([ids[1], ids[2], newest]))
        # the evicted snapshot's row stays on the ledger - evidence is not
        # deleted with the bytes - and a rollback of it refuses by name
        self.assertIn(ids[0], [r["id"] for r in self.rows("snapshot")])
        with self.assertRaises(ts.SnapshotError) as ctx:
            ts.restore(ids[0])
        self.assertIn("unknown snapshot id", str(ctx.exception))


class Restore(Snap):
    """restore(): the explicit rollback and its two refusals.

    The hash check makes the ordinary case a forced one: the file the user is
    rolling back is exactly the file the guarded write changed, so its bytes no
    longer match the capture and the restore has to be confirmed. What the check
    buys is that no rollback ever overwrites bytes nobody said to overwrite."""

    def test_a_snapshot_edited_and_rolled_back_returns_the_captured_bytes(self):
        before = "alpha\nbeta\n"
        path = self.write("a.py", before)
        sid = ts.capture("Edit", {"file_path": "a.py"}, self.repo, self.session)
        self.write("a.py", "changed\n")
        self.assertEqual(ts.restore(sid, force=True), [path])
        self.assertEqual(self.read(path), before)
        self.assertEqual([r["kind"] for r in self.rows()],
                         ["snapshot", "rollback"])
        self.assertEqual(self.rows("rollback")[0]["detail"], path)
        self.assertEqual(self.rows("rollback")[0]["id"], sid)

    def test_an_unchanged_file_restores_without_force(self):
        # putting back the bytes that are already there clobbers nothing
        path = self.write("a.py", "same\n")
        sid = ts.capture("Edit", {"file_path": "a.py"}, self.repo, self.session)
        self.assertEqual(ts.restore(sid), [path])
        self.assertEqual(self.read(path), "same\n")

    def test_a_changed_file_is_refused_and_left_alone(self):
        path = self.write("a.py", "before\n")
        sid = ts.capture("Edit", {"file_path": "a.py"}, self.repo, self.session)
        self.write("a.py", "after\n")
        with self.assertRaises(ts.SnapshotError) as ctx:
            ts.restore(sid)
        self.assertIn("has changed since snapshot", str(ctx.exception))
        self.assertIn("--force", str(ctx.exception))
        self.assertEqual(self.read(path), "after\n")
        self.assertEqual(self.rows("rollback"), [])

    def test_force_restores_over_the_change_and_the_row_says_so(self):
        path = self.write("a.py", "before\n")
        sid = ts.capture("Edit", {"file_path": "a.py"}, self.repo, self.session)
        self.write("a.py", "after\n")
        self.assertEqual(ts.restore(sid, force=True), [path])
        self.assertEqual(self.read(path), "before\n")
        self.assertTrue(self.rows("rollback")[0]["forced"])

    def test_a_deleted_file_needs_force_and_is_recreated(self):
        path = self.write("a.py", "gone\n")
        sid = ts.capture("Edit", {"file_path": "a.py"}, self.repo, self.session)
        os.remove(path)
        with self.assertRaises(ts.SnapshotError) as ctx:
            ts.restore(sid)
        self.assertIn("gone now", str(ctx.exception))
        self.assertEqual(ts.restore(sid, force=True), [path])
        self.assertEqual(self.read(path), "gone\n")

    def test_an_unknown_or_malformed_id_is_refused(self):
        self.write("a.py", "x\n")
        for bad in ("0123456789ab", "", None, "../proj/a.py", "x/y",
                    os.path.join(self.repo, "a.py")):
            with self.assertRaises(ts.SnapshotError) as ctx:
                ts.restore(bad)
            self.assertIn("unknown snapshot id", str(ctx.exception), bad)

    def test_a_snapshot_whose_bytes_do_not_match_its_hash_is_refused(self):
        path = self.write("a.py", "good\n")
        sid = ts.capture("Edit", {"file_path": "a.py"}, self.repo, self.session)
        with open(self.blob(sid), "w") as fh:
            fh.write("corrupt")
        with self.assertRaises(ts.SnapshotError) as ctx:
            ts.restore(sid)
        self.assertIn("damaged", str(ctx.exception))
        self.assertEqual(self.read(path), "good\n")


class RollbackCli(Snap):
    """bin/tezgah-rollback: the user command, and nothing calls restore but it."""

    def test_it_restores_the_captured_bytes_and_writes_the_row(self):
        path = self.write("a.py", "v1\n")
        sid = ts.capture("Edit", {"file_path": "a.py"}, self.repo, self.session)
        self.write("a.py", "v2\n")
        out = self.rollback(sid, "--force")
        self.assertEqual(out.returncode, 0, out.stderr)
        self.assertIn("restored %s" % path, out.stdout)
        self.assertEqual(self.read(path), "v1\n")
        self.assertEqual(self.rows("rollback")[0]["id"], sid)
        self.assertTrue(self.rows("rollback")[0]["forced"])

    def test_it_refuses_a_file_that_moved_on_and_takes_force(self):
        path = self.write("a.py", "v1\n")
        sid = ts.capture("Edit", {"file_path": "a.py"}, self.repo, self.session)
        self.write("a.py", "v2\n")
        out = self.rollback(sid)
        self.assertEqual(out.returncode, 1)
        self.assertIn("has changed since snapshot", out.stderr)
        self.assertEqual(self.read(path), "v2\n")
        self.assertEqual(self.rows("rollback"), [])
        out = self.rollback(sid, "--force")
        self.assertEqual(out.returncode, 0, out.stderr)
        self.assertEqual(self.read(path), "v1\n")

    def test_it_refuses_an_unknown_id(self):
        out = self.rollback("0123456789ab")
        self.assertEqual(out.returncode, 1)
        self.assertIn("unknown snapshot id", out.stderr)
        self.assertEqual(out.stdout, "")

    def test_usage_and_unknown_options_exit_two(self):
        for args in ([], ["--force"], ["a", "b"], ["--nope", "x"], [""]):
            out = self.rollback(*args)
            self.assertEqual(out.returncode, 2, args)
            self.assertIn("usage:", out.stderr)


class SessionRollback(Snap):
    """`tezgah-rollback --session <id>`: every path the session's write rows
    changed goes back to the earliest snapshot that session took of it.

    The moved-on check is restore()'s own, fed the session's last recorded
    state of the path: a file still as the session left it has not moved on,
    one somebody changed after the session's last write has."""

    def edit(self, name, text):
        """One write as a host drives it: capture in the gate, the write, the
        PostToolUse row carrying the after-state."""
        path = os.path.join(self.repo, name)
        sid = ts.capture("Edit", {"file_path": path}, self.repo, self.session)
        self.write(name, text)
        ti.note_tool(self.session, "Edit", {"file_path": path}, failed=False,
                     cwd=self.repo)
        return sid

    def two_paths(self):
        a = self.write("a.py", "a1\n")
        b = self.write("sub/b.py", "b1\n")
        first = self.edit("a.py", "a2\n")
        self.edit("a.py", "a3\n")
        b_sid = self.edit("sub/b.py", "b2\n")
        return os.path.realpath(a), os.path.realpath(b), first, b_sid

    def test_an_unreadable_shell_row_makes_a_snapshot_a_listing(self):
        # The ledger keeps a command cut to DETAIL_MAX, so a redirect past the
        # cut names no target: which path that row wrote is unknown rather than
        # absent. The snapshot path must then be listed, not restored - an
        # unknown shell write is the one thing a rollback must not act on - and
        # the file has to survive `restore_session` even under --force, which is
        # where the first version of this plan reverted it.
        out = os.path.join(self.repo, "out.txt")
        self.write("out.txt", "old\n")
        sid = ts.capture("write", {"file_path": out}, self.repo, self.session)
        self.write("out.txt", "new\n")
        ti.note_tool(self.session, "Bash",
                     {"command": "echo %s > out.txt" % ("a" * 240)},
                     failed=False, cwd=self.repo)
        plan = {e["path"]: e for e in ts.session_plan(self.session)}
        self.assertEqual(plan[out]["action"], "list (shell only)")
        self.assertEqual(plan[out]["id"], sid)
        ts.restore_session(self.session, force=True)
        self.assertEqual(self.read(out), "new\n")
        self.assertNotIn(sid, [r["id"] for r in self.rows("rollback")])

    def test_session_restores_the_earliest_snapshot_of_every_changed_path(self):
        a, b, first, b_sid = self.two_paths()
        plan = ts.session_plan(self.session)
        self.assertEqual([(e["path"], e["id"], e["action"]) for e in plan],
                         [(a, first, "restore"), (b, b_sid, "restore")])
        _, refused = ts.restore_session(self.session)
        self.assertEqual(refused, {})
        self.assertEqual(self.read(a), "a1\n")   # not a2: the earliest one
        self.assertEqual(self.read(b), "b1\n")
        self.assertEqual(sorted(r["id"] for r in self.rows("rollback")),
                         sorted([first, b_sid]))

    def test_session_lists_a_shell_only_path_and_never_reverts_it(self):
        a, _, _, _ = self.two_paths()
        out = self.write("out.txt", "old\n")
        # the gate captures a redirect's target as a write (tezgah_gate
        # SHELL_AS_WRITE), so this path HAS a snapshot and is still only listed
        shell_sid = ts.capture("write", {"file_path": out}, self.repo,
                               self.session)
        self.write("out.txt", "new\n")
        ti.note_tool(self.session, "Bash", {"command": "echo new > out.txt"},
                     failed=False, cwd=self.repo)
        new = self.write("made.py", "x\n")   # a write tool's new file
        ti.note_tool(self.session, "Write", {"file_path": new}, failed=False,
                     cwd=self.repo)
        plan = {e["path"]: e for e in ts.session_plan(self.session)}
        self.assertEqual(plan[os.path.realpath(out)]["action"],
                         "list (shell only)")
        self.assertEqual(plan[os.path.realpath(out)]["id"], shell_sid)
        self.assertEqual(plan[os.path.realpath(new)]["action"],
                         "list (no snapshot)")
        self.assertIsNone(plan[os.path.realpath(new)]["id"])
        ts.restore_session(self.session, force=True)
        self.assertEqual(self.read(out), "new\n")
        self.assertEqual(self.read(new), "x\n")
        self.assertEqual(self.read(a), "a1\n")
        self.assertNotIn(shell_sid, [r["id"] for r in self.rows("rollback")])

    def test_session_refuses_a_path_that_moved_on_until_force(self):
        a, b, _, _ = self.two_paths()
        self.write("a.py", "someone else\n")   # after the session's last write
        _, refused = ts.restore_session(self.session)
        self.assertEqual(list(refused), [a])
        self.assertIn("has changed since", refused[a])
        self.assertIn("--force", refused[a])
        self.assertEqual(self.read(a), "someone else\n")
        self.assertEqual(self.read(b), "b1\n")   # the other path still went back
        _, refused = ts.restore_session(self.session, force=True)
        self.assertEqual(refused, {})
        self.assertEqual(self.read(a), "a1\n")

    def test_session_reads_only_its_own_ledger(self):
        self.two_paths()
        c = self.write("c.py", "c1\n")
        ts.capture("Edit", {"file_path": c}, self.repo, "s-other")
        paths = [e["path"] for e in ts.session_plan(self.session)]
        self.assertNotIn(os.path.realpath(c), paths)
        self.assertEqual(ts.session_plan("s-never-ran"), [])

    def test_session_cli_restores_and_exits_zero(self):
        a, b, _, _ = self.two_paths()
        out = self.rollback("--session", self.session)
        self.assertEqual(out.returncode, 0, out.stderr)
        self.assertIn("restored %s" % a, out.stdout)
        self.assertIn("restored %s" % b, out.stdout)
        self.assertEqual(self.read(a), "a1\n")

    def test_session_cli_exits_one_on_any_refusal_and_on_an_empty_session(self):
        a, b, _, _ = self.two_paths()
        self.write("a.py", "moved\n")
        out = self.rollback("--session", self.session)
        self.assertEqual(out.returncode, 1)
        self.assertIn("has changed since", out.stderr)
        self.assertIn("restored %s" % b, out.stdout)
        self.assertEqual(self.read(a), "moved\n")
        out = self.rollback("--session", "s-never-ran")
        self.assertEqual(out.returncode, 1)
        self.assertIn("s-never-ran", out.stderr)

    def test_session_cli_usage_exits_two(self):
        for args in (["--session"], ["--session", ""],
                     ["--session", "s", "0123456789ab"], ["--dry-run", "x"],
                     ["--session", "s", "--nope"]):
            out = self.rollback(*args)
            self.assertEqual(out.returncode, 2, args)
            self.assertIn("usage:", out.stderr)

    def test_dry_run_prints_the_plan_and_writes_nothing(self):
        a, b, first, b_sid = self.two_paths()
        before_rows = self.rows()
        before_store = self.store()
        out = self.rollback("--session", self.session, "--dry-run")
        self.assertEqual(out.returncode, 0, out.stderr)
        self.assertIn("%s\t%s\trestore" % (a, first), out.stdout)
        self.assertIn("%s\t%s\trestore" % (b, b_sid), out.stdout)
        self.assertEqual(self.read(a), "a3\n")
        self.assertEqual(self.read(b), "b2\n")
        self.assertEqual(self.rows(), before_rows)
        self.assertEqual(self.store(), before_store)


class CaptureCli(Snap):
    """bin/tezgah-capture: the path a host that is not Python reaches capture by.

    What is under test is that a shell invocation lands the same row the
    in-process call lands, so the JS side of the ledger cannot drift from the
    Python side: opencode has no way to call the function."""

    def cli(self, *args):
        return subprocess.run(
            [sys.executable, CAPTURE] + list(args), capture_output=True,
            text=True, env=support.base_env(self.home, [self.roots]))

    def payload(self, **over):
        data = {"tool": "Edit", "input": {"file_path": "a.py"},
                "cwd": self.repo, "session_id": self.session}
        data.update(over)
        return json.dumps(data)

    def test_the_cli_row_is_the_row_the_in_process_capture_writes(self):
        self.write("a.py", "x = 1\n")
        inline = ts.capture("Edit", {"file_path": "a.py"}, self.repo, self.session)
        out = self.cli(self.payload())
        self.assertEqual(out.returncode, 0, out.stderr)
        cli_id = out.stdout.strip()
        self.assertTrue(cli_id)
        rows = self.rows("snapshot")
        self.assertEqual([r["id"] for r in rows], [inline, cli_id])
        def keys(row):
            return {k: v for k, v in row.items() if k not in ("id", "ts")}
        self.assertEqual(keys(rows[0]), keys(rows[1]))
        self.assertEqual(self.read(self.blob(inline)),
                         self.read(self.blob(cli_id)))

    def test_nothing_to_capture_prints_nothing_and_exits_zero(self):
        # a read tool, and a file that does not exist yet: both are normal, so
        # the caller gets silence rather than a failure it has to special-case
        for payload in (self.payload(tool="Read"),
                        self.payload(input={"file_path": "new.py"}),
                        self.payload(input={"file_path": "gone.py"})):
            out = self.cli(payload)
            self.assertEqual(out.returncode, 0, out.stderr)
            self.assertEqual(out.stdout, "")
        self.assertEqual(self.store(), [])

    def test_cwd_resolves_a_relative_path_and_defaults_to_the_working_dir(self):
        path = self.write("sub/b.py", "b\n")
        out = self.cli(json.dumps({"tool": "Edit", "session_id": self.session,
                                   "input": {"file_path": "sub/b.py"},
                                   "cwd": self.repo}))
        self.assertEqual(out.returncode, 0, out.stderr)
        self.assertEqual(self.rows("snapshot")[0]["detail"], path)

    def test_misuse_exits_two_and_captures_nothing(self):
        self.write("a.py", "x\n")
        for args in ((), ("" ,), ("not json",), ("[1]",), ("{}",),
                     (json.dumps({"tool": "Edit", "session_id": ""}),),
                     (json.dumps("Edit"),), (self.payload(), "extra")):
            out = self.cli(*args)
            self.assertEqual(out.returncode, 2, args)
            self.assertIn("usage:", out.stderr)
        self.assertEqual(self.store(), [])
        self.assertEqual(self.rows(), [])


if __name__ == "__main__":
    unittest.main()
