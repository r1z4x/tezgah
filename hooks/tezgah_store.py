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

BUSY_MS = 5000
TASTE_DB = "taste.db"
ERRORS = (OSError, sqlite3.Error)

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
    """Bring the legacy files present in `dirpath` into their tables in one
    transaction. A row file is appended on every open that finds it, so one an
    older install wrote after the first import still lands; a JSON document
    only while its tables are empty. Each imported file is renamed aside in the
    same transaction (`_aside`), and renamed back when it rolls back. A file
    that does not read or parse stays in place for the next open. With no
    legacy file, an open costs one stat per name."""
    present = [n for n in names if os.path.exists(os.path.join(dirpath, n))]
    present = [n for n in present if _wanted(conn, n)]
    if not present:
        return
    moved = []
    try:
        with transaction(conn):
            for name in present:
                src = os.path.join(dirpath, name)
                if _import_one(conn, name, src):
                    moved.append((src, _aside(src)))
    except BaseException:
        for src, dst in moved:
            try:
                os.rename(dst, src)
            except OSError:
                pass
        raise


def _wanted(conn, name):
    """False for a JSON document whose tables already hold rows."""
    return all(conn.execute("SELECT 1 FROM %s LIMIT 1" % table).fetchone() is None
               for table in DOC_TABLES.get(name, ()))


def _aside(src):
    """Rename `src` to `<src>.imported`, or `.imported.N` beside an earlier one;
    never over a file, so no import's source is ever lost."""
    dst, n = src + ".imported", 0
    while os.path.exists(dst):
        n += 1
        dst = "%s.imported.%d" % (src, n)
    os.rename(src, dst)
    return dst


def _import_one(conn, name, src):
    """True when `src` was read and its rows went in. A row file's line that is
    not a whole UTF-8 JSON object (a torn tail) is skipped, as the old reader
    skipped it."""
    try:
        with open(src, "rb") as fh:
            raw = fh.read()
    except OSError:
        return False
    if name not in DOC_TABLES:
        table = name[:-len(".jsonl")]
        for line in raw.split(b"\n"):
            try:
                row = json.loads(line.decode("utf-8"))
            except ValueError:  # UnicodeDecodeError is one
                continue
            if isinstance(row, dict):
                append(conn, table, row)
        return True
    try:
        data = json.loads(raw.decode("utf-8"))
    except ValueError:
        return False
    if not isinstance(data, dict) or not _wanted(conn, name):
        return False
    if name == "ledger.json":
        if not isinstance(data.get("learnings"), dict):
            return False
        _write_ledger(conn, data)
    else:
        set_gate(conn, data.get("stopped"), data.get("report") or {})
    return True


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
