#!/usr/bin/env python3
"""SQLite runtime stores (ADR 021): the connection, the schema, and the import
of the JSON and JSONL files a store replaces. No caller opens a store file
itself.

It holds the taste stores so far:
- `<repo>/.tezgah/taste/taste.db`: the capture signals, the typed decisions,
  the defects, the calibration labels, the injection rows, the benefit gate's
  state, the repository's learnings with their meta, and the learnings each
  session's write notes already showed.
- `~/.config/tezgah/taste/taste.db`: the user-scope learnings with their meta.

A row keeps its JSON payload in `row`, so its fields stay what the old files
held; the columns beside it are the fields a query filters on. WAL and a busy
timeout let a hook append while the CLI reads. The directory is made 0700 and
the database file is created 0600 before SQLite opens it; SQLite gives its
`-wal` and `-shm` files the database's mode.
"""
import contextlib
import json
import os
import sqlite3
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
USER_SCHEMA = """
CREATE TABLE IF NOT EXISTS learnings (id TEXT PRIMARY KEY, row TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS imported (name TEXT NOT NULL, dev INTEGER NOT NULL,
                                     ino INTEGER NOT NULL, bytes INTEGER NOT NULL,
                                     PRIMARY KEY (name, dev, ino));
CREATE TABLE IF NOT EXISTS import_failed (name TEXT PRIMARY KEY, mtime_ns INTEGER NOT NULL,
                                          size INTEGER NOT NULL);
"""
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


def connect(path, schema):
    """An autocommit connection to the database at `path` with `schema`
    applied (idempotent). Raises OSError or sqlite3.Error."""
    os.makedirs(os.path.dirname(path), mode=0o700, exist_ok=True)
    os.close(os.open(path, os.O_RDWR | os.O_CREAT, 0o600))
    conn = sqlite3.connect(path, isolation_level=None)
    try:
        conn.execute("PRAGMA busy_timeout = %d" % BUSY_MS)
        conn.execute("PRAGMA journal_mode = WAL")
        conn.executescript(schema)
    except sqlite3.Error:
        conn.close()
        raise
    return conn


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


def _aside(src):
    """Rename `src` to `<src>.imported`, or `.imported.N` beside an earlier one;
    never over a file, so no import's source is ever lost. A failed rename is
    left for the next open, which finds nothing new in the file."""
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
    _aside(src)


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


def _import_rows(conn, name, src, st):
    """The complete lines of `src` past the recorded offset; a line that is not
    a UTF-8 JSON object is skipped, as the old reader skipped it."""
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
        start = found[0] if found else 0
        fh.seek(start)
        raw = fh.read()
        whole = raw[:raw.rfind(b"\n") + 1]
        if whole:
            table = name[:-len(".jsonl")]
            with transaction(conn):
                for line in whole.split(b"\n"):
                    try:
                        row = json.loads(line.decode("utf-8"))
                    except ValueError:  # UnicodeDecodeError is one
                        continue
                    if isinstance(row, dict):
                        append(conn, table, row)
                conn.execute("INSERT OR REPLACE INTO imported (name, dev, ino, bytes) "
                             "VALUES (?, ?, ?, ?)", key + (start + len(whole),))
        # aside only when every byte went in and no writer appended past the
        # read (the old writer appends unlocked once its own wait runs out)
        if len(whole) == len(raw) and os.fstat(fh.fileno()).st_size == start + len(raw):
            _aside(src)


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
