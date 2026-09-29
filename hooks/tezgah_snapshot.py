#!/usr/bin/env python3
"""Pre-write file snapshots, and the one explicit command that rolls one back.

`capture(tool, inp, cwd, session_id)` copies the current bytes of every file a
write tool is about to change into the snapshot store, and appends one
`snapshot` ledger row (id, path, sha256) naming what it saved.
`restore(snapshot_id)` puts those bytes back, and `restore_session(session_id)`
does it for every path one session changed; both have exactly one caller:
`bin/tezgah-rollback`, which a user runs.

There is deliberately NO automatic rollback anywhere in tezgah. A hook that
undoes work on its own can cause more damage than the failure it answers: the
half-finished edit it would revert is indistinguishable from the user's own
work, a restore nobody asked for destroys the only copy of whatever it replaced,
and the trigger would be a guess about intent ("this edit looks wrong") wearing
a check's clothes. A snapshot is a pre-state to reach for; the decision to reach
for it stays with the user.
"""
import hashlib
import json
import os
import re
import time
import uuid

import tezgah_integrity as ti
from tezgah_paths import cache_dir, root_for

# A snapshot id is exactly what `capture` generates: 12 hex chars. Validated
# before it is used as a path segment, so an id typed at a shell cannot walk out
# of the store with `..` or an absolute path and read some other file's manifest.
SNAPSHOT_ID = re.compile(r"\A[0-9a-f]{12}\Z")

# The store is capped, because copying every file the agent touches with no
# bound is a disk leak: one long turn edits dozens of files, and a session runs
# for hours. Two limits, and what each one costs:
#
# CAP snapshots, and the OLDEST IS EVICTED when a capture crosses it. Eviction
# rather than refusing to capture: a store that starts refusing is a snapshot
# guard that silently turns itself off inside the long, busy session where a
# mistake is most likely and most expensive, while the snapshot anyone actually
# asks for is about a recent mistake - the oldest one is what nobody is coming
# back for. Worst case on disk is CAP * MAX_BYTES = 400 MB; the realistic case
# is a few MB, because source files are kilobytes.
#
# MAX_BYTES per file, above which nothing is captured at all. `capture` runs
# synchronously in the gate a host calls before the write, so copying a
# multi-gigabyte file the agent is about to append to would stall the very call
# it protects. ponytail: an over-large file is left un-snapshotted - capture
# returns None and writes no row, so nothing claims a copy that is not there.
# Raise MAX_BYTES where editing big files is the common case.
CAP = 200
MAX_BYTES = 2 * 1024 * 1024


def _store():
    """Where the pre-write bytes go: beside the evidence ledger, in whichever
    cache dir tezgah settled on for this environment (a sandboxed host has no
    writable ~/.cache and falls back to temp), so all tezgah state sits under
    one root."""
    return os.path.join(cache_dir(), "snapshots")


def _dir(snapshot_id):
    return os.path.join(_store(), str(snapshot_id))


def _blob(snapshot_id):
    return os.path.join(_dir(snapshot_id), "file")


def _manifest(snapshot_id):
    return os.path.join(_dir(snapshot_id), "meta.json")


def _dirs():
    try:
        return [os.path.join(_store(), n) for n in os.listdir(_store())]
    except OSError:
        return []


def _evict(keep=None):
    """Drop snapshot directories, oldest first, until `keep` (CAP) remain.

    The order is each directory's own mtime, which is when its capture created
    it - nothing writes inside a snapshot directory afterwards. Best effort: an
    entry that cannot be read or removed costs the cap, never the capture the
    gate is waiting on."""
    keep = CAP if keep is None else keep
    try:
        # ns rather than the float mtime: two captures inside one tick must not
        # evict an arbitrary one of the pair
        entries = sorted((os.stat(p).st_mtime_ns, p) for p in _dirs())
    except OSError:
        return
    for _, path in entries[:-keep]:
        import shutil  # deferred: ~3.7 ms of import for a path only a write takes
        shutil.rmtree(path, ignore_errors=True)


def _hash_file(path):
    """sha256 of a file's bytes, or None when it is not there / not readable.

    Read in blocks: this hashes the file as it is NOW, which a capture cannot
    bound - the copy was capped at MAX_BYTES, but the file it came from may have
    grown since."""
    try:
        digest = hashlib.sha256()
        with open(path, "rb") as fh:
            for block in iter(lambda: fh.read(1 << 20), b""):
                digest.update(block)
        return digest.hexdigest()
    except OSError:
        return None


def _write_paths(inp):
    """The files this call writes, from tezgah_gate's own reader.

    That reader is the one definition of each host dialect (`file_path`,
    `filePath`, `path`, and the `*** Update File:` headers of an apply_patch
    body), and a second copy here would drift from the file the gate's own rules
    read. Imported inside the call because the gate imports this module: a
    module-level import would close the cycle. A missing name costs the
    snapshot, never the call."""
    try:
        from tezgah_gate import write_paths
    except ImportError:
        return []
    return write_paths(inp if isinstance(inp, dict) else {})


def _append(session_id, row):
    """Append one ledger row, including the keys tezgah_integrity.note() drops.

    `note()` keeps only the LEDGER_FIELDS keys and truncates `detail` to 200
    chars, so a row carrying a sha256 - and a path longer than the truncation -
    cannot go through it. This writes the same file that writer names, from the
    same derivation (`tezgah_integrity._path`), so there is one ledger and one
    rule for where it is; every reader treats an unknown key as nothing, so the
    extra `hash` costs no existing reader anything. Best effort, like `note()`:
    a write failure is not the caller's failure."""
    if not session_id:
        return
    try:
        path = ti._path(session_id)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "a", encoding="utf-8") as fh:
            fh.write(json.dumps({k: v for k, v in row.items() if v is not None})
                     + "\n")
    except (OSError, AttributeError):
        pass


def _capture_one(path, cwd, session_id):
    """One file: copy its bytes in, write its row, return the snapshot id."""
    apath = os.path.realpath(
        str(path) if os.path.isabs(str(path))
        else os.path.join(cwd or ".", str(path)))
    try:
        if not os.path.isfile(apath) or os.path.getsize(apath) > MAX_BYTES:
            return None
        with open(apath, "rb") as fh:
            data = fh.read()
    except OSError:  # unreadable, or gone between the size check and the read
        return None
    sid = uuid.uuid4().hex[:12]
    digest = hashlib.sha256(data).hexdigest()
    ts = int(time.time())
    workspace = root_for(cwd) if cwd else None
    try:
        os.makedirs(_dir(sid), exist_ok=True)
        with open(_blob(sid), "wb") as fh:
            fh.write(data)
        with open(_manifest(sid), "w", encoding="utf-8") as fh:
            json.dump({"id": sid, "path": apath, "hash": digest,
                       "session": session_id, "workspace": workspace,
                       "bytes": len(data), "ts": ts}, fh)
    except OSError:
        import shutil  # deferred: see _evict
        shutil.rmtree(_dir(sid), ignore_errors=True)  # no half a snapshot
        return None
    # the row comes last: it must never name a copy that is not on disk
    _append(session_id, {"kind": "snapshot", "ts": ts, "detail": apath,
                         "id": sid, "hash": digest, "out_bytes": len(data),
                         "workspace": workspace})
    _evict()
    return sid


def capture(tool, inp, cwd, session_id):
    """Snapshot every file this call is about to change; return the first id.

    None means there was nothing to capture: a tool that is not a write tool, a
    file that does not exist yet (a new file has no bytes to lose), a path that
    is not a readable regular file, a file over MAX_BYTES, or no session to
    record the row in. A call that writes several files (an apply_patch body
    names them) captures each and returns the first: every capture gets its own
    id, its own row and its own directory.

    Never raises. The gate calls this on the way to allowing a write, so the
    worst a snapshot may cost is the snapshot."""
    if not session_id or str(tool or "").lower() not in ti.WRITE_TOOLS:
        return None
    ids = []
    for path in _write_paths(inp):
        sid = _capture_one(path, cwd, session_id)
        if sid:
            ids.append(sid)
    return ids[0] if ids else None


class SnapshotError(Exception):
    """A rollback that must not proceed, with the reason the user reads."""


def restore(snapshot_id, force=False, expect=None):
    """Put a snapshot's bytes back, write the `rollback` row, name the file.

    Returns the restored paths, as a list (a snapshot holds one file; the shape
    is what the contract declares). Raises SnapshotError - its only failure
    mode, so a caller never has to guess - when the id is unknown (never taken,
    or evicted), when the stored bytes do not match the hash the snapshot
    recorded (so restoring them would write corruption), or when the file has
    changed since the capture and putting the old bytes back would silently
    clobber that change. `force` overrides that last refusal and only that one,
    and the row records that it was used.

    `expect` is another sha256 the file may have now without counting as moved
    on: the session's own last recorded state of it, which is what a session
    rollback passes. Its earliest snapshot is the pre-state of the session's
    FIRST write, so the file differs from it by construction - the session's own
    later writes, not someone else's - and without `expect` every path of every
    session rollback would need --force, which is a check that refuses nothing.

    Not called by any hook: see the module docstring for why."""
    sid = str(snapshot_id or "")
    meta, data = None, b""
    if SNAPSHOT_ID.match(sid):
        try:
            with open(_manifest(sid), encoding="utf-8") as fh:
                meta = json.load(fh)
            with open(_blob(sid), "rb") as fh:
                data = fh.read()
        except (OSError, ValueError):
            meta = None
    if not meta:
        raise SnapshotError(
            "unknown snapshot id %r: the store holds no snapshot for it (CAP "
            "keeps the newest %d, and an evicted one is gone for good)"
            % (snapshot_id, CAP))
    path = str(meta.get("path") or "")
    if not path or hashlib.sha256(data).hexdigest() != meta.get("hash"):
        raise SnapshotError(
            "snapshot %r is damaged: its stored bytes do not match the hash it "
            "recorded, so nothing was restored" % sid)
    digest = meta.get("hash")
    current = _hash_file(path)
    # a set without None: a file that is gone never matches, so `expect=None`
    # cannot wave through a deleted file
    if current not in {digest, expect} - {None} and not force:
        since = ("this session last wrote it" if expect
                 else "snapshot %r was taken" % sid)
        raise SnapshotError(
            "%s has changed since %s%s; --force restores the captured bytes "
            "over it" % (path, since, "" if current else " (it is gone now)"))
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "wb") as fh:
            fh.write(data)
    except OSError as exc:
        raise SnapshotError("could not write %s (%s)" % (path, exc))
    _append(meta.get("session"),
            {"kind": "rollback", "ts": int(time.time()), "detail": path,
             "id": meta.get("id") or sid, "out_bytes": len(data),
             "workspace": meta.get("workspace"), "forced": force or None})
    return [path]


def _row_path(row, resolved=()):
    """The resolved file a write row names, or "".

    An `edit` row's detail is the tool's own path argument; a `run` row's is the
    command, whose target is the redirect tezgah_gate.write_paths reads (the same
    reader `_post_write` hashed it through).

    A relative target is resolved against `resolved` - the paths the ledger has
    already resolved, which are the snapshot rows' own: the gate's capture
    resolved that same target against the call's cwd, which the row does not
    keep, and wrote the answer there. A target that names the tail of exactly one
    of them IS that path; the row's `workspace` (the root, not the cwd) is the
    fallback. ponytail: two candidates - the same name under two directories the
    session touched - and a relative fallback that resolves to a file the ledger
    never named both stay unmatched, so the row lands outside the plan rather
    than on a guessed path."""
    detail = str(row.get("detail") or "")
    mark = " " + ti.FAILED_MARK
    if detail.endswith(mark):
        detail = detail[:-len(mark)]
    if row.get("kind") == "run":
        detail = str((_write_paths({"command": detail}) or [""])[0])
    if not detail:
        return ""
    if os.path.isabs(detail):
        return os.path.realpath(detail)
    detail = os.path.normpath(detail)
    tails = [p for p in resolved if p.endswith(os.sep + detail)]
    if len(tails) == 1:
        return tails[0]
    if not row.get("workspace"):
        return ""
    return os.path.realpath(os.path.join(str(row["workspace"]), detail))


def session_plan(session_id):
    """What rolling a session back would do, one entry per path, in the order
    the session first touched them: {"path", "id", "action", "expect"}.

    `id` is the EARLIEST snapshot the session took of the path - the state before
    its first write. `expect` is the session's last recorded hash of it (the
    newest `snapshot`, `edit` or `run` row that carries one), which `restore`
    reads to tell the session's own writes from a later change.

    `action` is "restore" only for a path with a snapshot that a write tool
    changed (an `edit` row, or a snapshot with no row of its own - the second
    file of an apply_patch body). A path only a shell command touched is listed,
    never reverted, even when the gate snapshotted its redirect target: which
    file a command wrote is read off its text, not reported by a tool, so a
    rollback does not act on it (the id is shown for a deliberate single-id
    restore). The row has to name the target and need not carry a hash: a
    redirect's file that was gone by the time the after-state was read is still
    a shell write, and reading it as a write tool's would revert it. A path with
    no snapshot - a file the session created - has no pre-state to put back and
    is listed too. Reads the ledger, writes nothing."""
    order, first, expect, named = [], {}, {}, {}
    for row in ti.events(session_id):
        kind = row.get("kind")
        if kind == "snapshot":
            path = str(row.get("detail") or "")
            if path and path not in first:
                first[path] = row.get("id")
        elif kind in ("edit", "run"):
            path = _row_path(row, order)
            if path:
                named.setdefault(path, set()).add(kind)
        else:
            continue
        if not path:
            continue
        if path not in order:
            order.append(path)
        if row.get("hash"):
            expect[path] = row["hash"]
    plan = []
    for path in order:
        if path not in first:
            action = "list (no snapshot)"
        elif named.get(path) == {"run"}:
            action = "list (shell only)"
        else:
            action = "restore"
        plan.append({"path": path, "id": first.get(path), "action": action,
                     "expect": expect.get(path)})
    return plan


def restore_session(session_id, force=False):
    """Restore every "restore" entry of `session_plan` through `restore`, so the
    moved-on refusal and --force are the single-id rollback's own.

    Returns (plan, refused): refused maps a path to the reason it was left
    alone. One refusal does not stop the others - each path is its own file and
    its own decision. Not called by any hook: see the module docstring."""
    plan, refused = session_plan(session_id), {}
    for entry in plan:
        if entry["action"] != "restore":
            continue
        try:
            restore(entry["id"], force=force, expect=entry["expect"])
        except SnapshotError as exc:
            refused[entry["path"]] = str(exc)
    return plan, refused
