#!/usr/bin/env python3
"""SQLite runtime stores (ADR 021): the connection, the schema, and the import
of the JSON and JSONL files a store replaces. No caller opens a store file
itself.

It holds the taste stores and the evidence ledger:
- `<repo>/.tezgah/taste/taste.db`: the capture signals, the typed decisions,
  the defects, the calibration labels, the injection rows, the benefit gate's
  state, the repository's learnings with their meta, and the learnings each
  session's write notes already showed.
- `~/.config/tezgah/taste/taste.db`: the user-scope learnings with their meta.
- `<cache>/tezgah.db`: the evidence ledger, one `evidence` row per ledger line
  of every session (`tezgah_integrity` writes and reads it, through the
  functions under "the evidence ledger" below, and so does opencode's plugin,
  through node:sqlite or the `evidence` CLI in `main`).

A row keeps its JSON payload in `row`, so its fields stay what the old files
held; the columns beside it are the fields a query filters on. WAL and a busy
timeout let a hook append while the CLI reads. The directory is made 0700 and
the database file is created 0600 before SQLite opens it; SQLite gives its
`-wal` and `-shm` files the database's mode.
"""
import contextlib
import hashlib
import json
import os
import sqlite3
import subprocess
import sys
import time

try:
    import fcntl
except ImportError:  # Windows: the old writers took no lock there either
    fcntl = None

BUSY_MS = 5000
TASTE_DB = "taste.db"
ERRORS = (OSError, sqlite3.Error)
# how long an import waits for a legacy row file's flock (its old writer,
# `tezgah_integrity._append`, holds it for one row) before leaving the file
# to the next open
LOCK_WAIT, LOCK_POLL = 1.0, 0.02

# Each append-only taste table and the columns a query reads beside its JSON
# row; `n` is the append order.
TASTE_ROWS = {
    "signals": ("session", "kind", "ts"),
    "decisions": ("id", "session", "provider", "day", "at"),
    "defects": ("id", "session", "day"),
    "labels": ("id", "provider", "day"),
    "injected": ("session", "day"),
}
IMPORT_SCHEMA = """
CREATE TABLE IF NOT EXISTS imported (name TEXT NOT NULL, dev INTEGER NOT NULL,
                                     ino INTEGER NOT NULL, bytes INTEGER NOT NULL,
                                     PRIMARY KEY (name, dev, ino));
CREATE TABLE IF NOT EXISTS import_failed (name TEXT PRIMARY KEY, mtime_ns INTEGER NOT NULL,
                                          size INTEGER NOT NULL);
"""
USER_SCHEMA = """
CREATE TABLE IF NOT EXISTS learnings (id TEXT PRIMARY KEY, row TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT NOT NULL);
""" + IMPORT_SCHEMA
REPO_SCHEMA = USER_SCHEMA + "".join(
    "CREATE TABLE IF NOT EXISTS %s (n INTEGER PRIMARY KEY, %s, row TEXT NOT NULL);\n"
    % (table, ", ".join(cols)) for table, cols in TASTE_ROWS.items()) + """
CREATE TABLE IF NOT EXISTS gate (one INTEGER PRIMARY KEY CHECK (one = 1),
                                 stopped INTEGER NOT NULL, report TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS notes_seen (session TEXT NOT NULL, learning TEXT NOT NULL,
                                       PRIMARY KEY (session, learning));
"""
# The files each taste store replaces. A JSON document imports only into the
# tables it names while they are empty; a row file (`<table>.jsonl`) always.
DOC_TABLES = {"ledger.json": ("learnings", "meta"), "gate.json": ("gate",)}
REPO_LEGACY = ("ledger.json", "gate.json") + tuple(t + ".jsonl" for t in TASTE_ROWS)
USER_LEGACY = ("ledger.json",)


def connect(path, schema, version=0):
    """An autocommit connection to the database at `path` with `schema`
    applied (idempotent). With `version`, the schema runs only while the file's
    `user_version` is not it, so a hook's open skips the DDL. Raises OSError or
    sqlite3.Error."""
    os.makedirs(os.path.dirname(path), mode=0o700, exist_ok=True)
    os.close(os.open(path, os.O_RDWR | os.O_CREAT, 0o600))
    conn = sqlite3.connect(path, isolation_level=None)
    try:
        conn.execute("PRAGMA busy_timeout = %d" % BUSY_MS)
        _wal(conn)
        if not version or conn.execute("PRAGMA user_version").fetchone()[0] != version:
            # the write lock first, so a second opener waits on the busy
            # timeout instead of failing on SQLite's lock-upgrade deadlock
            conn.executescript("BEGIN IMMEDIATE;\n%s\nPRAGMA user_version = %d;\nCOMMIT;"
                               % (schema, version))
    except sqlite3.Error:
        if conn.in_transaction:
            conn.execute("ROLLBACK")
        conn.close()
        raise
    return conn


def _wal(conn):
    """Switch `conn`'s file to WAL. The switch needs the file to itself and
    SQLite answers "locked" at once instead of waiting, so it is retried for as
    long as the busy timeout would have waited."""
    deadline = time.monotonic() + BUSY_MS / 1000.0
    while True:
        try:
            conn.execute("PRAGMA journal_mode = WAL")
            return
        except sqlite3.OperationalError:
            if time.monotonic() >= deadline:
                raise
            time.sleep(LOCK_POLL)


@contextlib.contextmanager
def transaction(conn):
    """One write transaction, taken at its start so two writers queue on the
    busy timeout instead of failing at commit; rolled back on any failure,
    the commit's own included."""
    conn.execute("BEGIN IMMEDIATE")
    try:
        yield conn
        conn.execute("COMMIT")
    except BaseException:
        if conn.in_transaction:
            conn.execute("ROLLBACK")
        raise


@contextlib.contextmanager
def taste(dirpath, user=False, create=True):
    """The taste database in `dirpath` (the user store when `user`), the legacy
    files there imported first (`_import`). With `create` False it yields None
    instead of creating a database where neither it nor a legacy file exists,
    so a read leaves no file behind."""
    path = os.path.join(dirpath, TASTE_DB)
    legacy = USER_LEGACY if user else REPO_LEGACY
    if not create and not os.path.exists(path) and not any(
            os.path.exists(os.path.join(dirpath, name)) for name in legacy):
        yield None
        return
    conn = connect(path, USER_SCHEMA if user else REPO_SCHEMA)
    try:
        _import(conn, dirpath, legacy)
        yield conn
    finally:
        conn.close()


def _import(conn, dirpath, names):
    """Bring the legacy files present in `dirpath` into their tables. With no
    legacy file, an open costs one stat per name.

    A row file (`<table>.jsonl`) imports on every open that finds it, under
    its old writer's flock. The `imported` table records how many bytes of
    that file (by device and inode) went in, in the same transaction as the
    rows, so the next open takes only what was appended since; a torn last
    line waits for its newline. A JSON document imports only while its tables
    are empty. The rename aside (`_aside`) comes after the commit and is
    tidiness: a process killed before it re-imports nothing. A file that
    cannot be read or parsed is recorded in `import_failed` and skipped,
    before any transaction, until its mtime or size changes."""
    for name in names:
        src = os.path.join(dirpath, name)
        if not os.path.exists(src):
            continue
        try:
            st = os.stat(src)
        except OSError:
            continue
        if conn.execute("SELECT 1 FROM import_failed WHERE name = ? AND mtime_ns = ? "
                        "AND size = ?", (name, st.st_mtime_ns, st.st_size)).fetchone():
            continue
        if name in DOC_TABLES:
            _import_doc(conn, name, src, st)
        else:
            _import_rows(conn, name, src, st)


def _failed(conn, name, st):
    with transaction(conn):
        conn.execute("INSERT OR REPLACE INTO import_failed (name, mtime_ns, size) "
                     "VALUES (?, ?, ?)", (name, st.st_mtime_ns, st.st_size))


def _wanted(conn, name):
    """False for a JSON document whose tables already hold rows."""
    return all(conn.execute("SELECT 1 FROM %s LIMIT 1" % table).fetchone() is None
               for table in DOC_TABLES.get(name, ()))


def _aside(src, read):
    """Rename `src` to `<src>.imported`, or `.imported.N` beside an earlier one,
    when it is still the file the import read (`read`, its fstat): one another
    writer created at that path since was never read and stays. Never over a
    file, so no import's source is ever lost. A failed rename is left for the
    next open, which finds nothing new in the file."""
    try:
        if not os.path.samestat(os.stat(src), read):
            return
    except OSError:
        return
    dst, n = src + ".imported", 0
    while os.path.exists(dst):
        n += 1
        dst = "%s.imported.%d" % (src, n)
    try:
        os.rename(src, dst)
    except OSError:
        pass


def _import_doc(conn, name, src, st):
    if not _wanted(conn, name):
        return
    try:
        with open(src, "rb") as fh:
            read = os.fstat(fh.fileno())
            data = json.loads(fh.read().decode("utf-8"))
    except FileNotFoundError:
        return  # another process imported it since the stat
    except (OSError, ValueError):  # UnicodeDecodeError is a ValueError
        data = None
    if not isinstance(data, dict) or (
            name == "ledger.json" and not isinstance(data.get("learnings"), dict)):
        _failed(conn, name, st)
        return
    with transaction(conn):
        if not _wanted(conn, name):
            return  # another process imported it first
        if name == "ledger.json":
            _write_ledger(conn, data)
        else:
            set_gate(conn, data.get("stopped"), data.get("report") or {})
    _aside(src, read)


def _locked(fh):
    """An exclusive flock on `fh` within LOCK_WAIT, True where flock is missing."""
    if fcntl is None:
        return True
    deadline = time.monotonic() + LOCK_WAIT
    while True:
        try:
            fcntl.flock(fh, fcntl.LOCK_EX | fcntl.LOCK_NB)
            return True
        except OSError:
            if time.monotonic() >= deadline:
                return False
            time.sleep(LOCK_POLL)


def _taste_put(table):
    """The import of one taste row line: a line that is not a UTF-8 JSON object
    is skipped, as the old reader skipped it."""
    def put(conn, line):
        try:
            row = json.loads(line.decode("utf-8"))
        except ValueError:  # UnicodeDecodeError is one
            return
        if isinstance(row, dict):
            append(conn, table, row)
    return put


def _import_rows(conn, name, src, st, put=None, keep=False):
    """The complete lines of `src` past the recorded offset, each handed to
    `put` (a taste table's row by default). With `keep` the file is never
    renamed aside: its writer still reads it."""
    try:
        fh = open(src, "rb")
    except FileNotFoundError:
        return  # another process imported it since the stat
    except OSError:
        _failed(conn, name, st)
        return
    with fh:  # closing it releases the flock
        if not _locked(fh):
            return  # its writer holds it: the next open takes it
        st = os.fstat(fh.fileno())
        key = (name, st.st_dev, st.st_ino)
        found = conn.execute("SELECT bytes FROM imported WHERE name = ? AND dev = ? "
                             "AND ino = ?", key).fetchone()
        # a file cut below what went in (rewritten in place) resumes at its
        # end, so the rows appended after the cut still import
        start = min(found[0], st.st_size) if found else 0
        fh.seek(start)
        raw = fh.read()
        whole = raw[:raw.rfind(b"\n") + 1]
        if whole or (found and found[0] != start):
            put = put or _taste_put(name[:-len(".jsonl")])
            with transaction(conn):
                for line in whole.split(b"\n"):
                    put(conn, line)
                conn.execute("INSERT OR REPLACE INTO imported (name, dev, ino, bytes) "
                             "VALUES (?, ?, ?, ?)", key + (start + len(whole),))
        # aside only when every byte went in and no writer appended past the
        # read (the old writer appends unlocked once its own wait runs out)
        now = os.fstat(fh.fileno())
        if not keep and len(whole) == len(raw) and now.st_size == start + len(raw):
            _aside(src, now)


# --- the taste tables ---------------------------------------------------------------

def _column(value):
    return value if value is None or isinstance(value, (str, int, float)) else None


def append(conn, table, row):
    """One row into an append-only taste table; raises when it is not written."""
    cols = TASTE_ROWS[table]
    conn.execute("INSERT INTO %s (%s, row) VALUES (%s)" % (
        table, ", ".join(cols), ", ".join("?" * (len(cols) + 1))),
        [_column(row.get(c)) for c in cols] + [json.dumps(row, ensure_ascii=False)])


def rows(conn, table, where="", args=()):
    """The rows of one append-only taste table in append order; `where` is a
    clause over its columns."""
    return [json.loads(text) for (text,) in conn.execute(
        "SELECT row FROM %s %s ORDER BY n" % (table, where), args)]


def last(conn, table):
    """The append number of the table's newest row, 0 when it has none."""
    return conn.execute("SELECT coalesce(max(n), 0) FROM %s" % table).fetchone()[0]


def load_ledger(conn):
    """{"v": 1, "learnings": {id: learning}, "meta": {...}}, ids in order."""
    return {"v": 1,
            "learnings": {lid: json.loads(text) for lid, text in conn.execute(
                "SELECT id, row FROM learnings ORDER BY id")},
            "meta": {key: json.loads(value) for key, value in conn.execute(
                "SELECT key, value FROM meta")}}


def _write_ledger(conn, ledger):
    conn.execute("DELETE FROM learnings")
    conn.executemany("INSERT INTO learnings (id, row) VALUES (?, ?)", [
        (lid, json.dumps(learning, ensure_ascii=False, sort_keys=True))
        for lid, learning in ledger["learnings"].items()])
    conn.execute("DELETE FROM meta")
    conn.executemany("INSERT INTO meta (key, value) VALUES (?, ?)", [
        (key, json.dumps(value)) for key, value in (ledger.get("meta") or {}).items()])


def save_ledger(conn, ledger):
    """Replace the learnings and their meta with `ledger`'s, in one transaction:
    a forgotten learning leaves the table with it."""
    with transaction(conn):
        _write_ledger(conn, ledger)


def gate_stopped(conn):
    """True when the benefit gate stopped injection."""
    found = conn.execute("SELECT stopped FROM gate").fetchone()
    return bool(found and found[0])


def set_gate(conn, stopped, report):
    conn.execute("INSERT OR REPLACE INTO gate (one, stopped, report) VALUES (1, ?, ?)",
                 (1 if stopped else 0, json.dumps(report)))


def seen(conn, session):
    """The learning ids a write note already showed in `session`."""
    return {lid for (lid,) in conn.execute(
        "SELECT learning FROM notes_seen WHERE session = ?", (session,))}


def mark_seen(conn, session, ids):
    with transaction(conn):
        conn.executemany("INSERT OR IGNORE INTO notes_seen (session, learning) VALUES (?, ?)",
                         [(session, lid) for lid in ids])


# --- the evidence ledger ------------------------------------------------------------
# One database per cache dir. A caller names a session's ledger by the path its
# JSONL file had, `<cache>/evidence/<session>.jsonl` (`tezgah_integrity._path`):
# the cache is two directories up and the session is the file's stem. A JSONL
# file still at that path is the session's legacy file, written before this
# database (or by an opencode process still running a plugin from before it),
# imported past the bytes already in before every read or write of that session
# and never renamed aside, because that writer may still append to it.
EVIDENCE_DB = "tezgah.db"
EVIDENCE_VERSION = 1
EVIDENCE_SCHEMA = IMPORT_SCHEMA + """
CREATE TABLE IF NOT EXISTS evidence (n INTEGER PRIMARY KEY, session TEXT NOT NULL,
                                     kind TEXT, ts INTEGER, row TEXT NOT NULL);
CREATE INDEX IF NOT EXISTS evidence_session ON evidence (session, n);
CREATE INDEX IF NOT EXISTS evidence_ts ON evidence (ts);
"""
# the bulk import's stamp in the cache dir, and how often session start may
# launch it (`import_later`)
IMPORT_STAMP = "evidence-import.stamp"
IMPORT_EVERY = 86400
# One connection per database per process: db path -> (connection, the file's
# (dev, ino), {legacy path: its (dev, ino, size) once fully imported}). A
# database removed or replaced under the process (doctor, uninstall, a test's
# fresh cache) is reopened on the next call.
_EVIDENCE = {}


def _ledger(path):
    """(cache dir, session) for a ledger path."""
    folder, name = os.path.split(path)
    return os.path.dirname(folder), name[:-len(".jsonl")] if name.endswith(".jsonl") else name


def _evidence_db(cache, create=True):
    """The held evidence database of `cache`; None when it does not exist and
    not `create`."""
    path = os.path.join(cache, EVIDENCE_DB)
    try:
        st = os.stat(path)
        here = (st.st_dev, st.st_ino)
    except OSError:
        here = None
    held = _EVIDENCE.get(path)
    if held and held[1] == here:
        return held
    if held:
        del _EVIDENCE[path]
        held[0].close()
    if here is None and not create:
        return None
    conn = connect(path, EVIDENCE_SCHEMA, EVIDENCE_VERSION)
    # no fsync per commit under WAL: a crash can lose the newest rows but never
    # corrupts the file, the durability the JSONL append had
    conn.execute("PRAGMA synchronous = NORMAL")
    st = os.stat(path)
    held = _EVIDENCE[path] = (conn, (st.st_dev, st.st_ino), {})
    return held


def _insert(conn, session, text):
    """One evidence row: `text` verbatim, its `kind` and `ts` beside it when it
    is a JSON object that carries them."""
    try:
        row = json.loads(text)
    except ValueError:
        row = None
    row = row if isinstance(row, dict) else {}
    kind, ts = row.get("kind"), row.get("ts")
    try:
        ts = int(ts) if isinstance(ts, (int, float)) and not isinstance(ts, bool) else None
    except (ValueError, OverflowError):  # NaN, infinity
        ts = None
    conn.execute("INSERT INTO evidence (session, kind, ts, row) VALUES (?, ?, ?, ?)",
                 (session, kind if isinstance(kind, str) else None,
                  ts if ts is not None and -2 ** 63 <= ts < 2 ** 63 else None, text))


def _evidence_put(session):
    """The import of one legacy ledger line: kept as it was written, so a line
    that does not parse stays a line the reader names as damage."""
    def put(conn, line):
        if not line.strip():
            return
        try:
            text = line.decode("utf-8")
        except UnicodeDecodeError:
            # the marker `tezgah_integrity._parse` names as damage, as the
            # file reader's was
            text = "\x00not utf-8 %s" % hashlib.sha1(line).hexdigest()[:12]
        _insert(conn, session, text)
    return put


def _sync(held, path):
    """Import the legacy JSONL at `path` past the bytes already in. Without a
    file, or with nothing new in it, this is one stat (and one lookup the first
    time a process sees it)."""
    try:
        st = os.stat(path)
    except OSError:
        return
    conn, _here, seen = held
    mark = (st.st_dev, st.st_ino, st.st_size)
    if seen.get(path) == mark:
        return
    name = os.path.basename(path)
    found = conn.execute("SELECT bytes FROM imported WHERE name = ? AND dev = ? AND ino = ?",
                         (name, st.st_dev, st.st_ino)).fetchone()
    if found and found[0] == st.st_size:
        seen[path] = mark
        return
    if conn.execute("SELECT 1 FROM import_failed WHERE name = ? AND mtime_ns = ? "
                    "AND size = ?", (name, st.st_mtime_ns, st.st_size)).fetchone():
        return
    _import_rows(conn, name, path, st, _evidence_put(_ledger(path)[1]), keep=True)


def _session(path, create=False):
    """(held database, session) for the ledger at `path`, its legacy file
    imported first; the database is None when neither it nor a legacy file
    exists and not `create`, so a read leaves no file behind."""
    cache, session = _ledger(path)
    held = _evidence_db(cache, create or os.path.exists(path))
    if held:
        _sync(held, path)
    return held, session


def import_session(path):
    """The legacy JSONL at `path` into its cache's database."""
    if os.path.exists(path):
        _session(path)


def append_evidence(path, text):
    """One row (`text`, its JSON) into the ledger at `path`, after its legacy
    file's rows: one INSERT in autocommit, so a row is whole or absent. Raises
    OSError or sqlite3.Error."""
    held, session = _session(path, create=True)
    _insert(held[0], session, text)


def evidence_rows(path, tail=None, kind=None):
    """The row texts of the ledger at `path`, oldest first: the last `tail`
    with one, only the rows of `kind` with that."""
    held, session = _session(path)
    if held is None:
        return []
    conn = held[0]
    if kind:
        found = conn.execute("SELECT row FROM evidence WHERE session = ? AND kind = ? "
                             "ORDER BY n", (session, kind))
    elif tail:
        return [text for (text,) in reversed(conn.execute(
            "SELECT row FROM evidence WHERE session = ? ORDER BY n DESC LIMIT ?",
            (session, tail)).fetchall())]
    else:
        found = conn.execute("SELECT row FROM evidence WHERE session = ? ORDER BY n",
                             (session,))
    return [text for (text,) in found]


def evidence_first(path):
    """The first row text of the ledger at `path`, or None."""
    held, session = _session(path)
    found = held and held[0].execute(
        "SELECT row FROM evidence WHERE session = ? ORDER BY n LIMIT 1", (session,)).fetchone()
    return found[0] if found else None


def has_evidence(path):
    """True when the ledger at `path` has a legacy file or a row; creates
    nothing."""
    if os.path.exists(path):
        return True
    cache, session = _ledger(path)
    held = _evidence_db(cache, create=False)
    return bool(held and held[0].execute(
        "SELECT 1 FROM evidence WHERE session = ? LIMIT 1", (session,)).fetchone())


def import_evidence(cache):
    """Every legacy session file under `<cache>/evidence` into the cache's
    database, the least recently written first; the count of files seen.
    Idempotent: a file imports only past the bytes the `imported` table
    already counts for it."""
    found = []
    try:
        for entry in os.scandir(os.path.join(cache, "evidence")):
            if entry.name.endswith(".jsonl"):
                try:
                    found.append((entry.stat().st_mtime, entry.path))
                except OSError:
                    continue
    except OSError:
        return 0
    if found:
        held = _evidence_db(cache)
        for _mtime, path in sorted(found):
            _sync(held, path)
    return len(found)


def sessions(cache):
    """[(session, its newest ts)] of every ledger in `cache`, the one written
    last first, after the bulk import (`import_evidence`)."""
    import_evidence(cache)
    held = _evidence_db(cache, create=False)
    return held[0].execute(
        "SELECT session, max(ts) FROM evidence GROUP BY session "
        "ORDER BY max(ts) DESC, max(n) DESC").fetchall() if held else []


def recent_rows(cache, since, kinds, but):
    """(session, row text) of every row of `kinds` stamped at or after `since`
    in a ledger other than session `but`, oldest first. The legacy files
    written since are imported first; the older ones cannot hold such a row."""
    fresh = []
    try:
        for entry in os.scandir(os.path.join(cache, "evidence")):
            try:
                if entry.name.endswith(".jsonl") and entry.stat().st_mtime >= since:
                    fresh.append(entry.path)
            except OSError:
                continue
    except OSError:
        pass
    held = _evidence_db(cache, create=bool(fresh))
    if held is None:
        return []
    for path in fresh:
        _sync(held, path)
    return held[0].execute(
        "SELECT session, row FROM evidence WHERE ts >= ? AND kind IN (%s) AND session != ? "
        "ORDER BY n" % ", ".join("?" * len(kinds)), (since,) + tuple(kinds) + (but,)).fetchall()


def _forget(conn, cache, session):
    """Delete one session's rows, its import offsets and its legacy file (inside
    the caller's transaction); the count of rows deleted. The offsets go with the
    file: a later file at that name may reuse its inode."""
    rows = conn.execute("DELETE FROM evidence WHERE session = ?", (session,)).rowcount
    conn.execute("DELETE FROM imported WHERE name = ?", (session + ".jsonl",))
    try:
        os.remove(os.path.join(cache, "evidence", session + ".jsonl"))
    except OSError:
        pass
    return rows


def forget_session(path):
    """Delete the ledger at `path`: its rows and its legacy file; the count of
    rows deleted."""
    cache, session = _ledger(path)
    held = _evidence_db(cache, create=False)
    if held is None:
        try:
            os.remove(path)
        except OSError:
            pass
        return 0
    with transaction(held[0]) as conn:
        return _forget(conn, cache, session)


def sweep_evidence(cache, cutoff, keep=None):
    """Delete every ledger in `cache` whose newest row is older than `cutoff`
    (epoch seconds), all but session `keep`: (sessions, rows) deleted. A
    session is the unit, as the file was: a ledger cut short at its start would
    lose the first row the switch latch reads."""
    import_evidence(cache)
    held = _evidence_db(cache, create=False)
    if held is None:
        return 0, 0
    with transaction(held[0]) as conn:
        idle = [s for (s,) in conn.execute(
            "SELECT session FROM evidence GROUP BY session HAVING max(coalesce(ts, 0)) < ?",
            (cutoff,)).fetchall() if s != keep]
        return len(idle), sum(_forget(conn, cache, s) for s in idle)


def import_later(cache):
    """Start `import-evidence` for `cache` detached, while legacy files exist
    and at most once per IMPORT_EVERY (the stamp's mtime, written before the
    start, so a failed start waits a day). Total."""
    try:
        if not os.path.isdir(os.path.join(cache, "evidence")):
            return
        stamp = os.path.join(cache, IMPORT_STAMP)
        try:
            if time.time() - os.path.getmtime(stamp) < IMPORT_EVERY:
                return
        except OSError:
            pass
        with open(stamp, "wb"):
            pass
        subprocess.Popen([sys.executable, os.path.abspath(__file__), "import-evidence", cache],
                         stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                         stderr=subprocess.DEVNULL, start_new_session=True)
    except (OSError, ValueError):
        pass


# `evidence VERB LEDGER [ARG]`: the ledger reads and writes for a caller that
# cannot open the database itself (opencode's plugin on a runtime without
# node:sqlite), each verb with the count of arguments it takes after LEDGER.
EVIDENCE_VERBS = {"append": 1, "tail": 1, "first": 0, "kind": 1, "import": 0}
EVIDENCE_USAGE = ("usage: tezgah_store.py evidence append LEDGER JSON | tail LEDGER N"
                  " | first LEDGER | kind LEDGER KIND | import LEDGER")


def _evidence_cli(args):
    """One verb on the ledger at args[1]: `append` stores JSON as a row,
    `import` brings its legacy file in, and a read prints row texts one per
    line, oldest first - the last N (`tail`), the first (`first`), or the rows
    of KIND (`kind`)."""
    verb = args[0] if args else None
    if EVIDENCE_VERBS.get(verb) != len(args) - 2:
        print(EVIDENCE_USAGE, file=sys.stderr)
        return 2
    path, rest = args[1], args[2:]
    try:
        if verb == "append":
            append_evidence(path, rest[0])
            return 0
        if verb == "import":
            import_session(path)
            return 0
        if verb == "first":
            found = [evidence_first(path)]
        elif verb == "kind":
            found = evidence_rows(path, kind=rest[0])
        else:
            try:
                tail = int(rest[0])
            except ValueError:
                print(EVIDENCE_USAGE, file=sys.stderr)
                return 2
            found = evidence_rows(path, tail=max(tail, 1))
    except ERRORS as exc:
        print("tezgah_store: %s" % exc, file=sys.stderr)
        return 1
    sys.stdout.buffer.write("".join(text + "\n" for text in found if text is not None)
                            .encode("utf-8", "surrogatepass"))
    return 0


def main(argv):
    """`import-evidence [CACHE...]`: the bulk import, for the given cache dirs
    or for the cache and its temp fallback. `evidence ...`: `_evidence_cli`."""
    if argv[1:2] == ["evidence"]:
        return _evidence_cli(argv[2:])
    if argv[1:2] != ["import-evidence"]:
        print("usage: tezgah_store.py import-evidence [CACHE_DIR...]\n" + EVIDENCE_USAGE,
              file=sys.stderr)
        return 2
    caches = argv[2:]
    if not caches:
        import tezgah_paths as tp
        caches = list(dict.fromkeys((tp.CACHE, tp.fallback_cache())))
    for cache in caches:
        try:
            print("%s: %d legacy ledger file(s) imported" % (cache, import_evidence(cache)))
        except ERRORS as exc:
            print("%s: import failed: %s" % (cache, exc), file=sys.stderr)
            return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
