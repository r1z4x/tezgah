#!/usr/bin/env python3
"""SQLite runtime stores (ADR 021): the connection, the schema, and the import
of the JSON and JSONL files a store replaces. No caller opens a store file
itself.

It holds the taste stores, the evidence ledger and the cache stores:
- `<repo>/.tezgah/taste/taste.db`: the capture signals, the typed decisions,
  the defects, the calibration labels, the injection rows, the benefit gate's
  state, the repository's learnings with their meta, and the learnings each
  session's write notes already showed.
- `~/.config/tezgah/taste/taste.db`: the user-scope learnings with their meta.
- `<cache>/tezgah.db`: the evidence ledger, one `evidence` row per ledger line
  of every session (`tezgah_integrity` writes and reads it, through the
  functions under "the cache database" below, and so does opencode's plugin,
  through node:sqlite or the `evidence` CLI in `main`), and the small stores
  the hooks kept as files beside it before (CACHE_LEGACY): the used-tool
  marks, the turn stamps, the switch baselines, the status marks, the judge's
  last use and down marks, the skill hints, the update check, the lesson-taint
  index, Cursor's marks, the replay and snapshot indexes and the taste-learn
  stamps (the functions under "the cache stores").

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
# how often the WAL switch is retried while another connection holds the file
# (`_wal`)
LOCK_POLL = 0.02

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
    `user_version` is below it, so a hook's open skips the DDL and an older
    install leaves a newer schema alone. Raises OSError or
    sqlite3.Error."""
    os.makedirs(os.path.dirname(path), mode=0o700, exist_ok=True)
    os.close(os.open(path, os.O_RDWR | os.O_CREAT, 0o600))
    conn = sqlite3.connect(path, isolation_level=None)
    try:
        conn.execute("PRAGMA busy_timeout = %d" % BUSY_MS)
        _wal(conn)
        if not version or conn.execute("PRAGMA user_version").fetchone()[0] < version:
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
    """An exclusive flock on `fh` if one is free now, True where flock is
    missing. Never waits: the caller holds the database's write lock."""
    if fcntl is None:
        return True
    try:
        fcntl.flock(fh, fcntl.LOCK_EX | fcntl.LOCK_NB)
        return True
    except OSError:
        return False


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


def _offset(conn, name, fh):
    """(the file's key, the byte offset its import resumes at, whether that
    differs from the recorded one). A file cut below what went in (rewritten in
    place) resumes at its end, so the rows appended after the cut still
    import."""
    st = os.fstat(fh.fileno())
    key = (name, st.st_dev, st.st_ino)
    found = conn.execute("SELECT bytes FROM imported WHERE name = ? AND dev = ? "
                         "AND ino = ?", key).fetchone()
    start = min(found[0], st.st_size) if found else 0
    return key, start, bool(found and found[0] != start)


def _import_rows(conn, name, src, st, put=None, keep=False):
    """The complete lines of `src` past the recorded offset, each handed to
    `put` (a taste table's row by default). With `keep` the file is never
    renamed aside: its writer may still append to it.

    A peek without a transaction comes first: a file with no complete line
    past the offset (nothing new, or a torn fragment its writer has not
    finished) costs no write lock, so a read under a busy writer still answers.
    Then the database's write lock, and the file's flock only if it is free: an
    import that held the flock while it waited on a busy database would hold
    the file's writer for that wait. The offset is read again inside the
    transaction, so two importers cannot both take the same lines, with or
    without a flock."""
    try:
        fh = open(src, "rb")
    except FileNotFoundError:
        return  # another process imported it since the stat
    except OSError:
        _failed(conn, name, st)
        return
    with fh:  # closing it releases the flock
        key, start, cut = _offset(conn, name, fh)
        fh.seek(start)
        raw = fh.read()
        if b"\n" in raw or cut:
            with transaction(conn):
                if not _locked(fh):
                    return  # its writer holds it: the next open takes it
                key, start, cut = _offset(conn, name, fh)
                fh.seek(start)
                raw = fh.read()
                whole = raw[:raw.rfind(b"\n") + 1]
                if whole or cut:
                    put = put or _taste_put(name[:-len(".jsonl")])
                    for line in whole.split(b"\n"):
                        put(conn, line)
                    conn.execute("INSERT OR REPLACE INTO imported (name, dev, ino, bytes) "
                                 "VALUES (?, ?, ?, ?)", key + (start + len(whole),))
        # aside only when every byte went in (no fragment past the last newline)
        # and no writer appended past the read (the old writer appends unlocked
        # once its own wait runs out), under the flock so no writer is inside
        # an append
        if not keep and not raw[raw.rfind(b"\n") + 1:] and _locked(fh):
            now = os.fstat(fh.fileno())
            if now.st_size == start + len(raw):
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


# --- the cache database -------------------------------------------------------------
# One database per cache dir, `<cache>/tezgah.db`: the evidence ledger and the
# small cache stores below it (CACHE_SCHEMA).
#
# The evidence ledger: a caller names a session's ledger by the path its JSONL
# file had, `<cache>/evidence/<session>.jsonl` (`tezgah_integrity._path`): the
# cache is two directories up and the session is the file's stem. A JSONL file
# still at that path is the session's legacy file, written before this database
# (or by an opencode process still running a plugin from before it), imported
# past the bytes already in before every read or write of that session and
# never renamed aside, because that writer may still append to it.
CACHE_DB = "tezgah.db"
CACHE_VERSION = 2
EVIDENCE_SCHEMA = IMPORT_SCHEMA + """
CREATE TABLE IF NOT EXISTS evidence (n INTEGER PRIMARY KEY, session TEXT NOT NULL,
                                     kind TEXT, ts INTEGER, row TEXT NOT NULL);
CREATE INDEX IF NOT EXISTS evidence_session ON evidence (session, n);
CREATE INDEX IF NOT EXISTS evidence_ts ON evidence (ts);
"""
# The cache stores, each the table of one kind of file the hooks wrote before
# (CACHE_LEGACY). A document store keeps one JSON `doc` per `key`, a mark store
# only the key; `at` is the epoch second of the last write, the mtime the file
# had. The key is the name the file had, so a legacy file imports under it.
DOC_STORES = ("turns", "switches", "harness_drift", "import_crash", "judge_last",
              "skill_pick", "section_hint", "update_check", "cursor_answer",
              "taste_learn")
MARK_STORES = ("gate_inactive", "nudged", "cursor_reinforced")
CACHE_SCHEMA = EVIDENCE_SCHEMA + "".join(
    "CREATE TABLE IF NOT EXISTS %s (key TEXT PRIMARY KEY, at REAL NOT NULL, doc TEXT NOT NULL);\n"
    % table for table in DOC_STORES) + "".join(
    "CREATE TABLE IF NOT EXISTS %s (key TEXT PRIMARY KEY, at REAL NOT NULL);\n"
    % table for table in MARK_STORES) + """
CREATE TABLE IF NOT EXISTS used (session TEXT NOT NULL, kind TEXT NOT NULL, at REAL NOT NULL,
                                 PRIMARY KEY (session, kind));
CREATE TABLE IF NOT EXISTS judge_down (key TEXT PRIMARY KEY, until REAL NOT NULL);
CREATE TABLE IF NOT EXISTS lesson_taint (root TEXT NOT NULL, key TEXT NOT NULL,
                                         source TEXT, ts INTEGER, PRIMARY KEY (root, key));
CREATE TABLE IF NOT EXISTS snapshots (n INTEGER PRIMARY KEY, id TEXT NOT NULL UNIQUE,
                                      meta TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS replay_runs (n INTEGER PRIMARY KEY, run TEXT NOT NULL UNIQUE,
                                        summary TEXT NOT NULL);
"""
# Where each cache store's files were, under the cache dir (`_import_cache`).
CACHE_LEGACY = {
    "used": "sessions", "turns": "turns", "switches": "switches",
    "gate_inactive": "gate-inactive", "nudged": "nudged", "harness_drift": "harness-drift",
    "import_crash": "import-crash", "judge_down": "judge-down",
    "judge_last": "judge-last.json", "skill_pick": "skill-pick",
    "section_hint": "skill-section-hint", "update_check": "update.json",
    "lesson_taint": "lessons", "cursor_reinforced": "reinforced", "cursor_answer": "answer",
    "replay_runs": "replay", "snapshots": "snapshots", "taste_learn": "taste-learn",
}
# tezgah_judge.DOWN_FOR when the judge-down markers were files: a marker's
# mtime plus this is the expiry it imports with
LEGACY_DOWN_FOR = 300
# the bulk import's stamp in the cache dir, and how often session start may
# launch it (`import_later`)
IMPORT_STAMP = "evidence-import.stamp"
IMPORT_EVERY = 86400
# One connection per database per process: db path -> (connection, the file's
# (dev, ino), {legacy path: its (dev, ino, size) once fully imported}). A
# database removed or replaced under the process (doctor, uninstall, a test's
# fresh cache) is reopened on the next call.
_HELD = {}


def _ledger(path):
    """(cache dir, session) for a ledger path."""
    folder, name = os.path.split(path)
    return os.path.dirname(folder), name[:-len(".jsonl")] if name.endswith(".jsonl") else name


def _cache_db(cache, create=True):
    """The held database of `cache`, the cache stores' legacy files imported
    on its open (`_import_cache`); None when it does not exist and not
    `create`."""
    path = os.path.join(cache, CACHE_DB)
    try:
        st = os.stat(path)
        here = (st.st_dev, st.st_ino)
    except OSError:
        here = None
    held = _HELD.get(path)
    if held and held[1] == here:
        return held
    if held:
        del _HELD[path]
        held[0].close()
    if here is None and not create:
        return None
    conn = connect(path, CACHE_SCHEMA, CACHE_VERSION)
    # no fsync per commit under WAL: a crash can lose the newest rows but never
    # corrupts the file, the durability the JSONL append had
    conn.execute("PRAGMA synchronous = NORMAL")
    st = os.stat(path)
    held = _HELD[path] = (conn, (st.st_dev, st.st_ino), {})
    _import_cache(conn, cache)
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
            # the marker `tezgah_integrity._parse` names as damage, hashed
            # over the line with its newline as the file reader hashed it, so
            # a damage row it wrote still names the same line
            text = "\x00not utf-8 %s" % hashlib.sha1(line + b"\n").hexdigest()[:12]
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
    held = _cache_db(cache, create or os.path.exists(path))
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
    held = _cache_db(cache, create=False)
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
        held = _cache_db(cache)
        for _mtime, path in sorted(found):
            _sync(held, path)
    return len(found)


def sessions(cache):
    """[(session, its newest ts)] of every ledger in `cache`, the one written
    last first, after the bulk import (`import_evidence`)."""
    import_evidence(cache)
    held = _cache_db(cache, create=False)
    return held[0].execute(
        "SELECT session, max(ts) FROM evidence GROUP BY session "
        "ORDER BY max(ts) DESC, max(n) DESC").fetchall() if held else []


def recent_rows(cache, since, kinds, but):
    """(session, ts, row text) of every row of `kinds` stamped at or after `since`
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
    held = _cache_db(cache, create=bool(fresh))
    if held is None:
        return []
    for path in fresh:
        _sync(held, path)
    return held[0].execute(
        "SELECT session, ts, row FROM evidence WHERE ts >= ? AND kind IN (%s) AND session != ? "
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
    held = _cache_db(cache, create=False)
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
    held = _cache_db(cache, create=False)
    if held is None:
        return 0, 0
    with transaction(held[0]) as conn:
        idle = [s for (s,) in conn.execute(
            "SELECT session FROM evidence GROUP BY session HAVING max(coalesce(ts, 0)) < ?",
            (cutoff,)).fetchall() if s != keep]
        return len(idle), sum(_forget(conn, cache, s) for s in idle)


def import_later(cache):
    """Start `import-evidence` for `cache` detached, while a legacy file exists
    and at most once per IMPORT_EVERY (the stamp's mtime, written before the
    start, so a failed start waits a day). Total."""
    try:
        with os.scandir(os.path.join(cache, "evidence")) as found:
            if not any(entry.name.endswith(".jsonl") for entry in found):
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


# --- the cache stores ---------------------------------------------------------------
# Each function takes the cache dir as `cache`, `tezgah_paths.cache_dir()` when
# it is None. A read never creates the database: with neither it nor the
# store's legacy files there, it answers as an empty store.

def _cache_dir():
    import tezgah_paths
    return tezgah_paths.cache_dir()


def _store(cache, table, create):
    """The connection of the database holding `table`, or None when it does
    not exist, the store has no legacy file to import, and not `create`."""
    cache = cache or _cache_dir()
    held = _cache_db(cache, create=False) or (
        (create or os.path.exists(os.path.join(cache, CACHE_LEGACY[table])))
        and _cache_db(cache))
    return held[0] if held else None


def doc(table, key, cache=None):
    """The JSON value a document store holds under `key`, or None: none
    stored, or the database cannot be read."""
    try:
        conn = _store(cache, table, False)
        found = conn and conn.execute("SELECT doc FROM %s WHERE key = ?" % table,
                                      (key,)).fetchone()
        return json.loads(found[0]) if found else None
    except ERRORS + (ValueError,):
        return None


def put_doc(table, key, value, cache=None):
    """`value` (JSON) under `key` in a document store; False when it was not
    written."""
    try:
        _store(cache, table, True).execute(
            "INSERT OR REPLACE INTO %s (key, at, doc) VALUES (?, ?, ?)" % table,
            (key, time.time(), json.dumps(value)))
        return True
    except ERRORS + (TypeError, ValueError):
        return False


def drop(table, key, cache=None):
    """`key` out of a document or mark store. Total."""
    try:
        conn = _store(cache, table, False)
        if conn:
            conn.execute("DELETE FROM %s WHERE key = ?" % table, (key,))
    except ERRORS:
        pass


def mark(table, key, cache=None):
    """Set `key` in a mark store: True when this call set it, False when it
    was set already. One INSERT, so of two callers exactly one gets True.
    Raises ERRORS."""
    return _store(cache, table, True).execute(
        "INSERT OR IGNORE INTO %s (key, at) VALUES (?, ?)" % table,
        (key, time.time())).rowcount == 1


def marked(table, key, cache=None):
    """True when a mark store holds `key`. Total: an unreadable store is
    unmarked."""
    try:
        conn = _store(cache, table, False)
        return bool(conn and conn.execute("SELECT 1 FROM %s WHERE key = ?" % table,
                                          (key,)).fetchone())
    except ERRORS:
        return False


def use(session, kind, cache=None):
    """Record that `session` used `kind`, stamped now. Raises ERRORS."""
    _store(cache, "used", True).execute(
        "INSERT OR REPLACE INTO used (session, kind, at) VALUES (?, ?, ?)",
        (session, kind, time.time()))


def used(session, cache=None):
    """The kinds `session` used, a set. Total."""
    try:
        conn = _store(cache, "used", False)
        return {kind for (kind,) in conn.execute(
            "SELECT kind FROM used WHERE session = ?", (session,))} if conn else set()
    except ERRORS:
        return set()


def used_sessions(window, cache=None):
    """(the kind sets of the `window` sessions that recorded last, newest
    first; the count of sessions recorded). Total."""
    try:
        conn = _store(cache, "used", False)
        if not conn:
            return [], 0
        newest = [s for (s,) in conn.execute(
            "SELECT session FROM used GROUP BY session ORDER BY max(at) DESC LIMIT ?",
            (window,))]
        total = conn.execute("SELECT count(DISTINCT session) FROM used").fetchone()[0]
        return [used(s, cache) for s in newest], total
    except ERRORS:
        return [], 0


def down_until(key, cache=None):
    """The epoch second the judge-down mark `key` expires at, or None. Total."""
    try:
        conn = _store(cache, "judge_down", False)
        found = conn and conn.execute("SELECT until FROM judge_down WHERE key = ?",
                                      (key,)).fetchone()
        return found[0] if found else None
    except ERRORS:
        return None


def set_down(key, until, cache=None):
    """Mark `key` down until the epoch second `until`. Total."""
    try:
        _store(cache, "judge_down", True).execute(
            "INSERT OR REPLACE INTO judge_down (key, until) VALUES (?, ?)", (key, until))
    except ERRORS:
        pass


def taint(root, cache=None):
    """{lesson key: source} of the lesson-taint rows of `root` (a key the
    caller derives from the repository). Total."""
    try:
        conn = _store(cache, "lesson_taint", False)
        return {key: source or "" for key, source in conn.execute(
            "SELECT key, source FROM lesson_taint WHERE root = ?", (root,))} if conn else {}
    except ERRORS:
        return {}


def write_taint(root, keep, rows, cache=None):
    """In one transaction: drop the rows of `root` whose key is not in `keep`,
    then store `rows` ({key, source, ts}), a later row over an earlier one of
    its key. Total."""
    try:
        conn = _store(cache, "lesson_taint", True)
        with transaction(conn):
            gone = [(root, key) for (key,) in conn.execute(
                "SELECT key FROM lesson_taint WHERE root = ?", (root,)) if key not in keep]
            conn.executemany("DELETE FROM lesson_taint WHERE root = ? AND key = ?", gone)
            conn.executemany(
                "INSERT OR REPLACE INTO lesson_taint (root, key, source, ts) VALUES (?, ?, ?, ?)",
                [(root, str(r["key"]), _column(r.get("source")), _column(r.get("ts")))
                 for r in rows])
    except ERRORS:
        pass


def add_snapshot(sid, meta, cap, cache=None):
    """Index snapshot `sid` (its manifest `meta`) and drop the oldest rows past
    `cap`, in one transaction; the ids dropped, whose blobs the caller removes.
    Raises ERRORS."""
    conn = _store(cache, "snapshots", True)
    with transaction(conn):
        conn.execute("INSERT INTO snapshots (id, meta) VALUES (?, ?)", (sid, json.dumps(meta)))
        old = [i for (i,) in conn.execute(
            "SELECT id FROM snapshots ORDER BY n DESC LIMIT -1 OFFSET ?", (cap,))]
        conn.executemany("DELETE FROM snapshots WHERE id = ?", [(i,) for i in old])
    return old


def snapshots(sid=None, cache=None):
    """The snapshot manifests, oldest first, or the one of `sid`. Total."""
    try:
        conn = _store(cache, "snapshots", False)
        found = [] if conn is None else conn.execute(
            "SELECT meta FROM snapshots %s ORDER BY n" % ("WHERE id = ?" if sid else ""),
            (sid,) if sid else ())
        return [json.loads(meta) for (meta,) in found]
    except ERRORS + (ValueError,):
        return []


def add_replay(run, summary, cache=None):
    """Index replay run `run` (its directory) with its summary; the newest
    indexed run is the latest. Raises ERRORS."""
    _store(cache, "replay_runs", True).execute(
        "INSERT OR REPLACE INTO replay_runs (run, summary) VALUES (?, ?)",
        (run, json.dumps(summary)))


def replay_latest(cache=None):
    """The directory of the latest replay run, or None. Total."""
    try:
        conn = _store(cache, "replay_runs", False)
        found = conn and conn.execute(
            "SELECT run FROM replay_runs ORDER BY n DESC LIMIT 1").fetchone()
        return found[0] if found else None
    except ERRORS:
        return None


def replay_summary(run, cache=None):
    """The summary replay run `run` was indexed with, or None. Total."""
    try:
        conn = _store(cache, "replay_runs", False)
        found = conn and conn.execute("SELECT summary FROM replay_runs WHERE run = ?",
                                      (run,)).fetchone()
        return json.loads(found[0]) if found else None
    except ERRORS + (ValueError,):
        return None


def sweep_cache(cache, cutoff, keep=None):
    """Delete the turn stamps and the used-kind sessions of `cache` last
    written before `cutoff` (epoch seconds), all but session `keep` (its
    `tezgah_context.slug`), after importing their legacy files; the count of
    rows deleted. The two stores the doctor swept as files. Raises ERRORS."""
    conn = _store(cache, "turns", False) or _store(cache, "used", False)
    if conn is None:
        return 0
    with transaction(conn):
        rows = conn.execute("DELETE FROM turns WHERE at < ? AND key IS NOT ?",
                            (cutoff, keep)).rowcount
        return rows + conn.execute(
            "DELETE FROM used WHERE session IN (SELECT session FROM used GROUP BY session "
            "HAVING max(at) < ?) AND session IS NOT ?", (cutoff, keep)).rowcount


def _files(folder):
    """[(name, path, mtime)] of the regular files directly in `folder`."""
    out = []
    try:
        with os.scandir(folder) as found:
            for entry in found:
                try:
                    if entry.is_file(follow_symlinks=False):
                        out.append((entry.name, entry.path, entry.stat().st_mtime))
                except OSError:
                    continue
    except OSError:
        pass
    return out


def _dirs(folder):
    """[(mtime_ns, name, path)] of the directories directly in `folder`, oldest
    first."""
    out = []
    try:
        with os.scandir(folder) as found:
            for entry in found:
                try:
                    if entry.is_dir(follow_symlinks=False):
                        out.append((entry.stat().st_mtime_ns, entry.name, entry.path))
                except OSError:
                    continue
    except OSError:
        pass
    return sorted(out)


def _read_text(path):
    try:
        with open(path, encoding="utf-8") as fh:
            return fh.read()
    except (OSError, ValueError):  # UnicodeDecodeError is a ValueError
        return None


def _read_json(path):
    try:
        return json.loads(_read_text(path) or "")
    except ValueError:
        return None


DOC_SQL = "INSERT OR IGNORE INTO %s (key, at, doc) VALUES (?, ?, ?)"
MARK_SQL = "INSERT OR IGNORE INTO %s (key, at) VALUES (?, ?)"


def _legacy(cache, table):
    """(the INSERTs, the files) of one cache store's legacy files under
    `cache`. A file that cannot be read or parsed brings no row, as its old
    reader read nothing from it, and goes with the rest."""
    src = os.path.join(cache, CACHE_LEGACY[table])
    put, gone = [], []
    if table in ("judge_last", "update_check"):
        if os.path.isfile(src):
            value = _read_json(src)
            if isinstance(value, dict):
                put.append((DOC_SQL % table, ("", os.path.getmtime(src), json.dumps(value))))
            gone.append(src)
    elif table == "snapshots":
        # the capture order is each directory's mtime; the blob stays
        for _ns, name, path in _dirs(src):
            meta = os.path.join(path, "meta.json")
            value = _read_json(meta)
            if isinstance(value, dict):
                put.append(("INSERT OR IGNORE INTO snapshots (id, meta) VALUES (?, ?)",
                            (name, json.dumps(value))))
            if os.path.exists(meta):
                gone.append(meta)
    elif table == "replay_runs":
        latest = (_read_text(os.path.join(src, "latest")) or "").strip()
        # by name (the run's start time), the one `latest` named last
        for _ns, _name, path in sorted(_dirs(src), key=lambda d: (d[2] == latest, d[1])):
            summary = os.path.join(path, "summary.json")
            value = _read_json(summary)
            if isinstance(value, dict):
                put.append(("INSERT OR IGNORE INTO replay_runs (run, summary) VALUES (?, ?)",
                            (path, json.dumps(value))))
            if os.path.exists(summary):
                gone.append(summary)
        if os.path.exists(os.path.join(src, "latest")):
            gone.append(os.path.join(src, "latest"))
    elif table == "cursor_reinforced":
        for _ns, session, folder in _dirs(src):
            for name, path, at in _files(folder):
                put.append((MARK_SQL % table, (session + "/" + name, at)))
                gone.append(path)
    else:
        for name, path, at in _files(src):
            if table == "used" and name.endswith(".jsonl"):
                for line in (_read_text(path) or "").splitlines():
                    try:
                        kind = json.loads(line)["kind"]
                    except (ValueError, KeyError, TypeError):
                        continue
                    if isinstance(kind, str):
                        put.append(("INSERT OR IGNORE INTO used (session, kind, at) "
                                    "VALUES (?, ?, ?)", (name[:-len(".jsonl")], kind, at)))
            elif table == "lesson_taint" and name.endswith(".jsonl"):
                for line in (_read_text(path) or "").splitlines():
                    try:
                        row = json.loads(line)
                    except ValueError:
                        continue
                    if isinstance(row, dict) and row.get("key"):
                        put.append(("INSERT OR REPLACE INTO lesson_taint (root, key, source, "
                                    "ts) VALUES (?, ?, ?, ?)",
                                    (name[:-len(".jsonl")], str(row["key"]),
                                     _column(row.get("source")), _column(row.get("ts")))))
            elif table == "judge_down":
                put.append(("INSERT OR IGNORE INTO judge_down (key, until) VALUES (?, ?)",
                            (name, at + LEGACY_DOWN_FOR)))
            elif table in MARK_STORES:
                put.append((MARK_SQL % table, (name, at)))
            elif table in ("harness_drift", "import_crash", "cursor_answer"):
                text = _read_text(path)
                if text is not None:
                    put.append((DOC_SQL % table, (name, at, json.dumps(text))))
            elif name.endswith(".json"):  # taste-learn keeps its logs beside them
                value = _read_json(path)
                if value is not None:
                    put.append((DOC_SQL % table, (name[:-len(".json")], at, json.dumps(value))))
            else:
                continue
            gone.append(path)
    return put, gone


def _legacy_done(conn):
    return {name[len("legacy:"):] for (name,) in conn.execute(
        "SELECT name FROM imported WHERE name >= 'legacy:' AND name < 'legacy;'")}


def _import_cache(conn, cache):
    """Bring each cache store's legacy files (CACHE_LEGACY) in, once per
    database: a store is done when `imported` holds its `legacy:<table>` row,
    written in the transaction that takes its rows. The files are read before
    that transaction and removed after it commits, so a process killed in
    between imports them again into rows that ignore a second copy. With every
    store done this is one indexed lookup per open. ponytail: a file a writer
    from before this release adds after the import is never read (an opencode
    plugin started before the upgrade, until it restarts). Total: a failure
    leaves the store for the next open."""
    try:
        todo = [table for table in CACHE_LEGACY if table not in _legacy_done(conn)]
        if not todo:
            return
        work = {table: _legacy(cache, table) for table in todo}
        with transaction(conn):
            mine = [table for table in todo if table not in _legacy_done(conn)]
            for table in mine:
                for sql, args in work[table][0]:
                    conn.execute(sql, args)
                conn.execute("INSERT OR IGNORE INTO imported (name, dev, ino, bytes) "
                             "VALUES (?, 0, 0, 0)", ("legacy:" + table,))
    except ERRORS:
        return
    for table in mine:
        for path in work[table][1]:
            try:
                os.remove(path)
            except OSError:
                pass
        folder = os.path.join(cache, CACHE_LEGACY[table])
        for _ns, _name, path in _dirs(folder) if table == "cursor_reinforced" else ():
            try:
                os.rmdir(path)
            except OSError:
                pass
        try:
            os.rmdir(folder)  # only an emptied one: blobs, runs and logs stay
        except OSError:
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


# `mark CACHE TABLE KEY` and `use CACHE SESSION KIND`: the two cache-store
# writes opencode's plugin makes (the once-per-session nudge and the used-kind
# marks), for the same caller as `evidence`. `mark` prints 1 when it set the
# mark and 0 when it was set already.
STORE_USAGE = "usage: tezgah_store.py mark CACHE TABLE KEY | use CACHE SESSION KIND"


def _store_cli(args):
    if len(args) != 4 or args[0] not in ("mark", "use") or (
            args[0] == "mark" and args[2] not in MARK_STORES):
        print(STORE_USAGE, file=sys.stderr)
        return 2
    verb, cache, name, value = args
    try:
        if verb == "use":
            use(name, value, cache)
        else:
            print(1 if mark(name, value, cache) else 0)
    except ERRORS as exc:
        print("tezgah_store: %s" % exc, file=sys.stderr)
        return 1
    return 0


def main(argv):
    """`import-evidence [CACHE...]`: the bulk import, for the given cache dirs
    or for the cache and its temp fallback. `evidence ...`: `_evidence_cli`;
    `mark ...` and `use ...`: `_store_cli`."""
    if argv[1:2] == ["evidence"]:
        return _evidence_cli(argv[2:])
    if argv[1:2] in (["mark"], ["use"]):
        return _store_cli(argv[1:])
    if argv[1:2] != ["import-evidence"]:
        print("usage: tezgah_store.py import-evidence [CACHE_DIR...]\n" + EVIDENCE_USAGE
              + "\n" + STORE_USAGE, file=sys.stderr)
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
