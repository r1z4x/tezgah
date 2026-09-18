#!/usr/bin/env python3
"""The active task: one plan file's phase and its path allowlist.

A task is not a second record beside the plan - it IS the plan file under
`plans/open/`, with two optional frontmatter keys that the user's own CLI
(bin/tezgah-task) writes and no agent ever does:

    phase: implementation        # discovery | implementation | verification
    allowed_paths:               # globs, relative to the repo root
      - hooks/**

`phase` is the activation key: the first open plan carrying a valid one is the
active task, and `allowed_paths` is read only then. A plan whose phase is not
one of the three is ignored by every reader rather than refused - a reader that
failed closed on a typo would block work the user never restricted, while the
absence of a task must never be read as a requirement.

The gate, the per-turn context line and the opencode plugin's path to both read
the record from here (through bin/tezgah-gate), so the phase that stops a write
before it happens is decided once. This module is on the gate's hot path for
every write, so it imports nothing from tezgah_context and shells out to
nothing.
"""
import os
import re

TASK_PHASES = ("discovery", "implementation", "verification")
WRITE_PHASES = ("implementation", "verification")


def repo_root(cwd, base):
    """The git top-level at or above cwd and under base, else the first path
    component below base. Walks up for a `.git` entry (dir or file: a worktree's
    is a file); no subprocess. Same answer as tezgah_context.repo_root without
    importing the context module into the gate's hot path."""
    cwd = os.path.realpath(cwd)
    inside = os.path.realpath(base) if base else None
    cur = cwd
    while True:
        if os.path.exists(os.path.join(cur, ".git")):
            if inside and _under(cur, inside):
                return cur
            break
        parent = os.path.dirname(cur)
        if parent == cur:
            break
        cur = parent
    if not inside:
        return cwd
    first = os.path.relpath(cwd, inside).split(os.sep)[0]
    if first in (".", "..", ""):
        return cwd
    return os.path.join(inside, first)


def _under(path, base):
    return path == base or path.startswith(base + os.sep)


def _frontmatter_lines(text):
    """The lines between the first two `---` lines, [] when the file has none.
    An unclosed block is not frontmatter: the markers are its boundary, and half
    of one leaves every `key: value` line in the body's hands."""
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return []
    for i in range(1, len(lines)):
        if lines[i].strip() == "---":
            return lines[1:i]
    return []


def frontmatter(text):
    """The plan file's frontmatter as a dict of str -> str (the text between the
    first two `---` lines, `key: value` lines only). {} when there is none."""
    out = {}
    for line in _frontmatter_lines(text):
        if line.lstrip().startswith("- "):
            continue
        key, sep, value = line.partition(":")
        if sep and key.strip():
            out[key.strip()] = value.strip()
    return out


def allowed_paths(text):
    """The `allowed_paths:` list as a list of globs, [] when absent."""
    out = []
    collecting = False
    for line in _frontmatter_lines(text):
        stripped = line.strip()
        if collecting and stripped.startswith("- "):
            out.append(stripped[2:].strip())
            continue
        collecting = (not stripped.startswith("- ") and ":" in stripped
                      and stripped.partition(":")[0].strip() == "allowed_paths")
    return out


def active(cwd, base):
    """The active task as a dict, or None. Scans `<repo_root>/plans/open/*.md`
    sorted by name, first file whose frontmatter carries a valid `phase`.
    Dict: {"id","title","phase","allowed_paths","path"}: id/title are the
    frontmatter values (id falls back to the filename's NNN), path is the file.
    Never raises: an unreadable directory or file means None (readers fail
    open)."""
    directory = os.path.join(repo_root(cwd, base), "plans", "open")
    try:
        names = sorted(os.listdir(directory))
    except OSError:
        return None
    for name in names:
        if not name.endswith(".md"):
            continue
        path = os.path.join(directory, name)
        try:
            with open(path, "r", encoding="utf-8") as fh:
                text = fh.read()
        except OSError:
            return None
        fields = frontmatter(text)
        if fields.get("phase") not in TASK_PHASES:
            continue
        return {"id": fields.get("id") or name.split("-")[0],
                "title": fields.get("title", ""),
                "phase": fields["phase"],
                "allowed_paths": allowed_paths(text),
                "path": path}
    return None


def match(rel, pattern):
    """Glob match for one allowlist pattern against a repo-relative posix path.
    `**` crosses separators, `*` does not, everything else is literal."""
    out = []
    i = 0
    while i < len(pattern):
        if pattern.startswith("**/", i):
            # `**` glued to a `/` also stands for no directory at all, so
            # `**/tests/**` covers a `tests/x.py` at the root as a reader expects
            out.append("(?:.*/)?")
            i += 3
        elif pattern.startswith("**", i):
            out.append(".*")
            i += 2
        elif pattern[i] == "*":
            out.append("[^/]*")
            i += 1
        else:
            out.append(re.escape(pattern[i]))
            i += 1
    return re.fullmatch("".join(out), rel) is not None


def relative(path, cwd, base):
    """The realpath of `path` (absolute or relative to cwd) as a posix path
    relative to repo_root(cwd, base), or None when it resolves outside that root
    (so an outside write can never be inside the allowlist)."""
    root = repo_root(cwd, base)
    real = os.path.realpath(path if os.path.isabs(path) else os.path.join(cwd, path))
    if real == root or not _under(real, root):
        # the root itself is not a path inside the root: an allowlist is about
        # files under it, so this is a None like any other, and every caller
        # fails in the refusing direction
        return None
    return real[len(root) + 1:].replace(os.sep, "/")


def set_fields(path, **fields):
    """Rewrite these frontmatter keys in the plan file in place: replace the
    `key: value` line when present, insert it before the closing `---` when not.
    `allowed_paths` takes a list and is written as a `- item` block, replacing an
    existing block. `updated` is not special-cased here: the CLI passes today's
    date under it, as it does for a research line's `created:`, so this module
    needs no clock of its own. Raises OSError."""
    with open(path, "r", encoding="utf-8") as fh:
        lines = fh.read().split("\n")
    if not lines or lines[0].strip() != "---":
        lines = ["---", "---"] + lines
    close = next((i for i in range(1, len(lines)) if lines[i].strip() == "---"), None)
    if close is None:
        lines.insert(1, "---")
        close = 1
    block = lines[1:close]
    for key, value in fields.items():
        fresh = _field_lines(key, value)
        head = next((i for i, line in enumerate(block)
                     if not line.lstrip().startswith("- ")
                     and line.partition(":")[0].strip() == key), None)
        if head is None:
            block += fresh
            continue
        end = head + 1
        while end < len(block) and block[end].lstrip().startswith("- "):
            end += 1
        block[head:end] = fresh
    lines[1:close] = block
    with open(path, "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines))


def _field_lines(key, value):
    """The frontmatter lines for one key: a `- item` block for a list (the form
    `allowed_paths` uses, indented so the block reads as one value), a bare
    `key:` for an empty value - which is how a phase is cleared - else
    `key: value`."""
    if isinstance(value, (list, tuple)):
        return [key + ":"] + ["  - %s" % item for item in value]
    if value is None or value == "":
        return [key + ":"]
    return ["%s: %s" % (key, value)]
