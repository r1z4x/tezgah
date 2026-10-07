#!/usr/bin/env python3
"""The lesson ledger's one reader: `.tezgah/lessons.md` as entries, and the key
each entry is remembered by.

The session block, the per-turn block and the per-turn digest
(`tezgah_context`), the gate and the tidy CLI (`bin/tezgah-lessons`) all read the
ledger here, so they agree on what a lesson is and on its key. A module of its
own because the gate must not import `tezgah_context` (its import cost, and the
rule `hooks/tezgah_task.py::repo_root` states): this one imports only
`tezgah_paths` at load, and `tezgah_gate` lazily, only for a line that names a
gate rule as its enforcer.

Stdlib only."""
import hashlib
import json
import os
import re

from tezgah_paths import cache_dir, off

# A line carries its metadata after its text, never in it: from the first
# `|| check:` or `|| enforced_by:` clause outside a code span to the end of the
# line (in any order), and an `@<sha> <path>` stamp just before those clauses.
# `parse` cuts both off before anything else reads the line, so neither enters
# the 200-character cut, `lesson_key`, the per-turn digest or the ranking. Prose
# keeps the rest: a bare `||` (`pytest || true`), a clause inside backticks
# (`a||check:b`), and an `@<sha>` followed by a word that is not a path (`git
# show @cafebabe1 HEAD` - a path holds a `/` or a `.`). `check` is plan 061's
# compiled check, which nothing reads yet.
SUFFIX = re.compile(r"\s*\|\|\s*(?:check|enforced_by):")
STAMP = re.compile(r"\s+@[0-9a-f]{7,40}\s+\S*[/.]\S*$")
# A line a gate rule or a test already enforces carries `|| enforced_by:
# <slug|test>` and leaves the injected pool while that enforcer is armed: a gate
# rule slug from `tezgah_gate.DENY_RULES`, or a test named from the repository
# root (`tests.test_research.Unfinished`) that this repository still defines. An
# unknown name keeps the line. Read off the tail `parse` cut.
ENFORCED = re.compile(r"\|\|\s*enforced_by:\s*(\S+)\s*(?=\|\||$)")
# A ledger written with markdown bullets must not render as "- - ...".
BULLET = re.compile(r"^[-*+]\s+|^\d+[.)]\s+")


def ledger(root):
    """The ledger's path in the repository at `root`."""
    return os.path.join(root, ".tezgah", "lessons.md")


def lesson_key(line):
    """The short id a lesson is remembered by: the session's turn stamp, the
    `lesson` row and the `lesson_tainted` row."""
    return hashlib.sha1(line.encode("utf-8", "replace")).hexdigest()[:8]


# The top-level class and function names of a test module, per (path, mtime,
# size): a ledger's retired lines name one module many times, and parsing a
# large test file once per line would cost every session start.
_TEST_NAMES = {}


def _test_names(path):
    """The names `unittest` can load from `path` as `module.NAME`: its top-level
    classes and functions, by `ast`, so a nested def or a `class X:` inside a
    string is not one. Empty when the file is missing or does not parse."""
    try:
        st = os.stat(path)
        key = (path, st.st_mtime_ns, st.st_size)
        if key not in _TEST_NAMES:
            import ast  # lazy: only a line retired by a test pays for it
            with open(path, encoding="utf-8", errors="replace") as fh:
                tree = ast.parse(fh.read(), filename=path)
            _TEST_NAMES[key] = frozenset(
                n.name for n in tree.body
                if isinstance(n, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)))
        return _TEST_NAMES[key]
    except (OSError, SyntaxError, ValueError):
        return frozenset()


def _enforced(value, root):
    """Whether the enforcer a retired lesson names is armed now: a test only
    while `<root>/tests/test_x.py` still defines it at top level, a gate rule
    only while neither its own switch nor `pretooluse-off` is set."""
    test = re.match(r"tests\.(test_\w+)\.(\w+)$", value)
    if test:
        return test.group(2) in _test_names(
            os.path.join(root, "tests", test.group(1) + ".py"))
    from tezgah_gate import DENY_RULES  # lazy: only a retired line pays for it
    if value not in DENY_RULES or off("pretooluse-off"):
        return False
    return not (DENY_RULES[value] and off(DENY_RULES[value]))


def parse(line):
    """(text, tail) for one ledger line - the lesson as every reader sees it, and
    the clauses cut off its end - or None for a blank line or a `#` heading."""
    s = line.strip()
    if not s or s.startswith("#"):
        return None
    s = BULLET.sub("", s)
    m = next((m for m in SUFFIX.finditer(s)
              if s.count("`", 0, m.start()) % 2 == 0), None)
    text, tail = (s[:m.start()], s[m.start():]) if m else (s, "")
    return STAMP.sub("", text), tail


def entries(text):
    """The lessons a text holds, each as `lines` returns it: what a write adds
    to the ledger, read the way the ledger will be read."""
    return [got[0] for got in map(parse, text.splitlines()) if got and got[0]]


def is_ledger(path):
    """True when the absolute, unresolved `path` names a repository's ledger."""
    return (os.path.basename(path) == "lessons.md"
            and os.path.basename(os.path.dirname(path)) == ".tezgah")


def taint_path(root):
    """The `lesson_tainted` index of the repository at `root`: the gate keeps
    each keyed row here as well as in the session's ledger, so the context of a
    later session reads one small file for the per-line label instead of every
    ledger on the machine (3173 files, 30 MB on the measuring machine,
    2026-10-07)."""
    name = hashlib.sha1(os.path.realpath(root).encode("utf-8", "replace"))
    return os.path.join(cache_dir(), "lessons", name.hexdigest()[:16] + ".jsonl")


def _index_rows(path):
    """The parseable keyed rows of an index file, oldest first; [] without one.
    A damaged line costs only itself."""
    rows = []
    try:
        with open(path, encoding="utf-8", errors="replace") as fh:
            for ln in fh:
                try:
                    row = json.loads(ln)
                except ValueError:
                    continue
                if isinstance(row, dict) and row.get("key"):
                    rows.append(row)
    except OSError:
        pass
    return rows


def write_taint(root, keep, rows):
    """Rewrite the index of the repository at `root`: the rows it holds whose key
    is in `keep` (the ledger's lines plus the write's new ones), then `rows`. So
    the file never outgrows the ledger it labels. Best effort, like a ledger row.
    ponytail: two sessions rewriting one index in the same instant can lose one
    row (one label); the session ledger keeps its own copy of every row."""
    path = taint_path(root)
    kept = [r for r in _index_rows(path) if r["key"] in keep] + rows
    tmp = "%s.%d.tmp" % (path, os.getpid())
    try:
        os.makedirs(os.path.dirname(path), mode=0o700, exist_ok=True)
        fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write("".join(json.dumps(r) + "\n" for r in kept))
        os.replace(tmp, path)
    except OSError:
        pass


# The index as last read, per (path, mtime, size): the session block, the
# per-turn block and the digest of one prompt each ask for it, and a hook
# process serves one prompt.
_TAINTED = {}


def tainted(root):
    """{key: source} for the lessons of the repository at `root` that a gate
    recorded as written in a turn that had read untrusted text (`taint_path`);
    {} when there is none. Read once while the file is unchanged."""
    path = taint_path(root)
    try:
        st = os.stat(path)
    except OSError:
        return {}
    key = (path, st.st_mtime_ns, st.st_size)
    if key not in _TAINTED:
        _TAINTED[key] = {str(r["key"]): str(r.get("source") or "")
                         for r in _index_rows(path)}
    return _TAINTED[key]


def lines(root, retired=None):
    """The lesson ledger as entries: one per line, markdown bullets, the clause
    tail and the stamp stripped (`parse`).

    The one reader, so every surface agrees on what is a lesson: a line whose
    enforcer is armed (ENFORCED) is left out and appended to `retired` when
    given; one whose enforcer is off comes back without its tail."""
    try:
        with open(ledger(root), encoding="utf-8", errors="replace") as fh:
            raw = fh.read().splitlines()
    except OSError:
        return []
    out = []
    for ln in raw:
        got = parse(ln)
        if not got or not got[0]:
            continue
        text, tail = got
        m = ENFORCED.search(tail)
        if m and _enforced(m.group(1), root):
            if retired is not None:
                retired.append(text)
            continue
        out.append(text)
    return out
