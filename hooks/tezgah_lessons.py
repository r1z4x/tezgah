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
import os
import re

from tezgah_paths import off

# A line a gate rule or a test already enforces ends `|| enforced_by: <slug|test>`
# and leaves the injected pool while that enforcer is armed: a gate rule slug from
# `tezgah_gate.DENY_RULES`, or a test named from the repository root
# (`tests.test_research.Unfinished`) that this repository still defines. An
# unknown name keeps the line.
ENFORCED = re.compile(r"\s*\|\|\s*enforced_by:\s*(\S+)\s*$")
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


def lines(root, retired=None):
    """The lesson ledger as entries: one per line, markdown bullets stripped.

    The one reader, so every surface agrees on what is a lesson: a line whose
    enforcer is armed (ENFORCED) is left out and appended to `retired` when
    given; one whose enforcer is off comes back without its suffix."""
    try:
        with open(ledger(root), encoding="utf-8", errors="replace") as fh:
            raw = fh.read().splitlines()
    except OSError:
        return []
    out = []
    for ln in raw:
        s = ln.strip()
        if not s or s.startswith("#"):
            continue
        s = BULLET.sub("", s)
        m = ENFORCED.search(s)
        if m and _enforced(m.group(1), root):
            if retired is not None:
                retired.append(s)
            continue
        out.append(s[:m.start()] if m else s)
    return out
