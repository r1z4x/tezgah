"""Shared helpers for the tezgah test suite.

Every test that exercises a hook runs it in a subprocess with an explicit
environment: a throwaway HOME and TEZGAH_ROOTS under tempfile, so the real
~/.claude, ~/.config/tezgah and ~/.cache are never read or written.
"""
import json
import os
import re
import sqlite3
import subprocess
import sys
import tempfile
import unittest

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HOOKS = os.path.join(REPO, "hooks")
TESTS = os.path.dirname(os.path.abspath(__file__))
# the same for the tests that call the status functions in this very process
os.environ.setdefault("TEZGAH_UPDATE_CHECK", "0")

PROBE_PATHS = os.path.join(TESTS, "_probe_paths.py")
PROBE_GATE = os.path.join(TESTS, "_probe_gate.py")
PROBE_CONTEXT = os.path.join(TESTS, "_probe_context.py")
PROBE_AGENTS = os.path.join(TESTS, "_probe_agents.py")
PROBE_INTEGRITY = os.path.join(TESTS, "_probe_integrity.py")
PROBE_POISONED = os.path.join(TESTS, "_probe_poisoned.py")
AUTO_INIT = os.path.join(REPO, "hooks", "projects-auto-init.py")
PRETOOLUSE = os.path.join(REPO, "hooks", "projects-pretooluse.py")
STOP_HOOK = os.path.join(REPO, "hooks", "projects-stop.py")
POSTTOOLUSE = os.path.join(REPO, "hooks", "projects-posttooluse.py")
CODEX_HOOK = os.path.join(REPO, "hosts", "codex", "hook.py")
CURSOR_HOOK = os.path.join(REPO, "hosts", "cursor", "hook.py")
OMP_HOOK = os.path.join(REPO, "hosts", "omp", "hook.py")
OMP_EXTENSION = os.path.join(REPO, "hosts", "omp", "tezgah-hook.ts.in")
OMP_HARNESS = os.path.join(TESTS, "_omp_extension_harness.mjs")
STATUSLINE = os.path.join(REPO, "statusline.py")
OPENCODE_PLUGIN = os.path.join(REPO, "hosts", "opencode", "plugins", "tezgah.js")
OPENCODE_HARNESS = os.path.join(TESTS, "_opencode_plugin_harness.mjs")


def slug(path):
    return re.sub(r"[^A-Za-z0-9]+", "-", path).strip("-")


def ledger_rows(path, raw=False):
    """The rows of the evidence ledger at `path` - `<cache>/evidence/<stem>.jsonl`,
    the path `tezgah_integrity._path` names - oldest first, read from
    `<cache>/tezgah.db`: parsed, or with `raw` their JSON text as stored. [] when
    there is no database. Rows still only in a legacy JSONL file (one opencode's
    plugin wrote and no hook read since) are not here: read that file."""
    db = os.path.join(os.path.dirname(os.path.dirname(path)), "tezgah.db")
    if not os.path.exists(db):
        return []
    conn = sqlite3.connect(db)
    try:
        texts = [t for (t,) in conn.execute(
            "SELECT row FROM evidence WHERE session = ? ORDER BY n",
            (os.path.basename(path)[:-len(".jsonl")],))]
    finally:
        conn.close()
    return texts if raw else [json.loads(t) for t in texts]


def ledger_sessions(cache):
    """The sessions with a row in `<cache>/tezgah.db`, sorted."""
    db = os.path.join(cache, "tezgah.db")
    if not os.path.exists(db):
        return []
    conn = sqlite3.connect(db)
    try:
        return sorted(s for (s,) in conn.execute("SELECT DISTINCT session FROM evidence"))
    finally:
        conn.close()


def all_ledger_rows(cache):
    """Every session's rows in `<cache>/tezgah.db`, session by session."""
    return [row for session in ledger_sessions(cache)
            for row in ledger_rows(os.path.join(cache, "evidence", session + ".jsonl"))]


def forge_row(path, row):
    """`row` inserted into the evidence ledger at `path` by a separate
    interpreter, the way a session forges one outside the hooks; the process."""
    db = os.path.join(os.path.dirname(os.path.dirname(path)), "tezgah.db")
    return run(["-c", "import sqlite3, sys; c = sqlite3.connect(sys.argv[1]); "
                "c.execute('INSERT INTO evidence (session, kind, row) VALUES (?, ?, ?)', "
                "(sys.argv[2], sys.argv[3], sys.argv[4])); c.commit()",
                db, os.path.basename(path)[:-len(".jsonl")], row.get("kind"), json.dumps(row)])


def forge_pass(home, session):
    """A passing `verify_ok` row forged into `session`'s ledger under `home`
    through `python3 -c`, the interpreter route no hook sees (plan 051)."""
    cache = os.path.join(home, ".cache", "tezgah")
    [stem] = [s for s in ledger_sessions(cache) if s.startswith(slug(session) + "-")]
    proc = forge_row(os.path.join(cache, "evidence", stem + ".jsonl"),
                     {"kind": "verify_ok", "detail": "pytest -q", "id": "forged",
                      "exit": 0, "out_bytes": 42, "v": 3})
    assert proc.returncode == 0, proc.stderr


def seed_ledger(path, rows, append=False):
    """Write `rows` (dicts) as the evidence ledger at `path` through the store, the
    way `tezgah_integrity._append` stores a row; the session's earlier rows go
    first unless `append`."""
    if HOOKS not in sys.path:
        sys.path.insert(0, HOOKS)
    import tezgah_store
    if not append:
        tezgah_store.forget_session(path)
    for row in rows:
        tezgah_store.append_evidence(path, json.dumps(row))


def store():
    """hooks/tezgah_store, for a test that seeds a cache store the way its hook
    writes it (every function takes the cache dir as `cache`)."""
    if HOOKS not in sys.path:
        sys.path.insert(0, HOOKS)
    import tezgah_store
    return tezgah_store


def cache_rows(cache, sql, args=()):
    """The rows `sql` returns from `<cache>/tezgah.db`, committed (a test sets a
    column the hooks set from the clock); [] without a database."""
    db = os.path.join(cache, "tezgah.db")
    if not os.path.exists(db):
        return []
    conn = sqlite3.connect(db)
    try:
        found = conn.execute(sql, args).fetchall()
        conn.commit()
        return found
    finally:
        conn.close()


def store_doc(cache, table, key):
    """The JSON value a document store of `<cache>/tezgah.db` holds under
    `key` (`tezgah_store.doc`), or None."""
    found = cache_rows(cache, "SELECT doc FROM %s WHERE key = ?" % table, (key,))
    return json.loads(found[0][0]) if found else None


def store_keys(cache, table):
    """The keys of a document or mark store of `<cache>/tezgah.db`, sorted."""
    return sorted(k for (k,) in cache_rows(cache, "SELECT key FROM %s" % table))


def used_kinds(cache, session):
    """The used-tool kinds `<cache>/tezgah.db` holds for `session` (its
    `tezgah_context.slug`), a set."""
    return {k for (k,) in cache_rows(cache, "SELECT kind FROM used WHERE session = ?",
                                     (session,))}


# The variables a Windows process needs to start at all (base_env keeps them).
WINDOWS_ENV = ("SYSTEMROOT", "WINDIR", "COMSPEC", "PATHEXT", "TEMP", "TMP",
               "USERPROFILE", "APPDATA", "LOCALAPPDATA")


def base_env(home, roots=None, extra=None):
    """A minimal environment: temp HOME, optional roots, no real host config."""
    env = {
        "PATH": os.environ.get("PATH", "/usr/bin:/bin:/usr/local/bin"),
        "HOME": home,
        "LANG": "C.UTF-8",
        "PYTHONPATH": HOOKS,
        # a path that does not exist => codegraph_bin() is None => no auto-index
        # runs
        "TEZGAH_CODEGRAPH_BIN": os.path.join(home, "no-such-codegraph"),
        # likewise orx: research routing is off unless a test points it at a real
        # binary, so the machine's own orx cannot leak into the assertions
        "TEZGAH_ORX_BIN": os.path.join(home, "no-such-orx"),
        # likewise claude: `--install` registers the plugin through `claude
        # plugin`, and the developer's real CLI must never run from a test
        "TEZGAH_CLAUDE_BIN": os.path.join(home, "no-such-claude"),
        # likewise the agent CLIs consult can ask: none counts unless a test
        # lists it, so a developer's own omp/claude/codex is not a consult option
        "TEZGAH_CONSULT_CLIS": "",
        # likewise orca: a suite run inside Orca has its CLI on PATH, and the
        # real runtime must not answer a test (tests/test_orca.py fakes one)
        "TEZGAH_ORCA_BIN": os.path.join(home, "no-such-orca"),
        # no release check from a test: a stale cache would start a detached
        # network fetch; tests/test_update.py turns it on where it is the subject
        "TEZGAH_UPDATE_CHECK": "0",
        # an OpenRouter key also resolves the `jev-openrouter` carrier: a test
        # that sets one for the chat fallback must not reach OpenRouter's System
        # One endpoint, so its default is a refused loopback port
        "TEZGAH_JEV_OPENROUTER_URL": "http://127.0.0.1:9/api/v1/systemone",
    }
    if os.name == "nt":
        # a child without these cannot start on Windows: node aborts in its
        # CSPRNG seed (`ncrypto::CSPRNG`, exit 134) and Python loses its temp dir
        env.update((k, os.environ[k]) for k in WINDOWS_ENV if k in os.environ)
    if roots:
        env["TEZGAH_ROOTS"] = os.pathsep.join(roots)
    if extra:
        env.update(extra)
    return env


def linked(script, home, name=None):
    """A ~/.config/tezgah/bin-style symlink to a host hook, as tezgah-setup
    installs it. The hook must still find the repo from the link path."""
    d = os.path.join(home, ".config", "tezgah", "bin")
    os.makedirs(d, exist_ok=True)
    link = os.path.join(d, name or os.path.basename(script))
    if not os.path.exists(link):
        os.symlink(script, link)
    return link


def run(args, payload=None, env=None, cwd=None):
    data = None if payload is None else json.dumps(payload)
    return subprocess.run(
        [sys.executable] + args, input=data, capture_output=True, text=True,
        env=env, cwd=cwd, timeout=60,
    )


def run_json(args, payload=None, env=None, cwd=None):
    proc = run(args, payload, env, cwd)
    out = proc.stdout.strip()
    return (json.loads(out) if out else None), proc


# The gate's scratch exemption is `$TMPDIR or /tmp`, realpath'd, and it is read
# in the hook process; `tempfile` honours THIS process's TMPDIR. A runner that
# sets none (CI) therefore puts the fixture HOME under /tmp, where a `rm -rf`
# beside the repo is the session's own scratch and is held to no ask - which
# inverts the two directory-scope tests that need a delete outside the run
# directory to be an effect (`test_gate.Gate`, `test_opencode_plugin`'s lease).
# /var/tmp is neither root, so the fixture is not scratch by accident, the way a
# developer's checkout is not.
FIXTURE_PARENT = ("/var/tmp"
                  if os.path.isdir("/var/tmp") and os.access("/var/tmp", os.W_OK)
                  else None)

# This process too: a test that calls a hook in-process, or hands a child
# `os.environ`, wrote to the real ~/.cache/tezgah ledger under the session that
# ran the suite. tezgah_paths fixes HOME and CACHE at import, so this runs before
# any hooks/ import a test module makes after `import support`.
_SUITE_HOME = tempfile.TemporaryDirectory(prefix="tezgah-suite-home-", dir=FIXTURE_PARENT,
                                          ignore_cleanup_errors=True)
os.environ["HOME"] = _SUITE_HOME.name
# an in-process install must not reach the developer's real `claude` either
os.environ["TEZGAH_CLAUDE_BIN"] = os.path.join(_SUITE_HOME.name, "no-such-claude")
# A host dir or XDG base the developer exported points at their real config:
# with CODEX_HOME set, a test that wrote and removed `<CODEX_HOME>/config.toml`
# deleted the developer's own Codex config (2026-10-06).
# Orca's markers likewise: a suite run from an Orca terminal would tell every
# in-process session it runs in Orca (hooks/tezgah_orca.py::session).
# The session markers (OMPCODE, CLAUDECODE, OPENCODE, CURSOR_AGENT,
# CURSOR_VERSION, CODEX_THREAD_ID) and the TEZGAH_JUDGE_CLI pick name the CLI
# the judgement seam asks first, so a suite started inside a host would run the
# developer's real CLI on their tokens.
for _name in ("TEZGAH_SESSION", "XDG_CONFIG_HOME", "XDG_CACHE_HOME", "XDG_DATA_HOME",
              "CODEX_HOME", "DSH_HOME", "TEZGAH_OPENCODE_DATA", "ORCA_WORKTREE_ID",
              "ORCA_TERMINAL_HANDLE", "ORCA_PANE_KEY", "ORCA_CLI_COMMAND",
              "ORCA_CLI_BIN_DIR", "OMPCODE", "CLAUDECODE", "OPENCODE", "CURSOR_AGENT",
              "CURSOR_VERSION", "CODEX_THREAD_ID", "TEZGAH_JUDGE_CLI"):
    os.environ.pop(_name, None)
if os.environ.get("TERM_PROGRAM") == "Orca":
    del os.environ["TERM_PROGRAM"]
os.environ["TEZGAH_ORCA_BIN"] = os.path.join(_SUITE_HOME.name, "no-such-orca")


class TempHome(unittest.TestCase):
    """A test with a fresh temp HOME and a Projects root inside it."""

    def setUp(self):
        # a fixture-spawned process can create a file between the cleanup's
        # listdir and its rmdir; a temp dir that fails to clean is not a test
        # outcome, and the failure landed on an unrelated test's teardown in CI
        # (2026-10-01, OSError: Directory not empty, test_agents)
        self._tmp = tempfile.TemporaryDirectory(dir=FIXTURE_PARENT,
                                               ignore_cleanup_errors=True)
        self.addCleanup(self._tmp.cleanup)
        self.home = os.path.realpath(self._tmp.name)
        self.roots = os.path.join(self.home, "Projects")
        os.makedirs(self.roots, exist_ok=True)

    def env(self, roots=None, extra=None):
        return base_env(self.home, roots or [self.roots], extra)

    def make_repo(self, name="repo"):
        path = os.path.join(self.roots, name)
        os.makedirs(path, exist_ok=True)
        return os.path.realpath(path)

    def config(self, data):
        path = os.path.join(self.home, ".config", "tezgah", "config.json")
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w") as fh:
            json.dump(data, fh)

    def touch(self, path):
        os.makedirs(os.path.dirname(path), exist_ok=True)
        open(path, "w").close()
