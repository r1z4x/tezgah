#!/usr/bin/env python3
"""The active task: one plan file's phase and its path allowlist.

A task is not a second record beside the plan - it IS the plan file under
`.tezgah/plans/open/`, with two optional frontmatter keys that the user's own CLI
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

A plan's body is read here too, and only here: the acceptance report
(`tezgah-render-table --acceptance`) counts the items that name no command, so
the record the gate reads and the items the report counts have one reader.
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


def section_lines(text, heading):
    """The lines of one `## <heading>` section with their 1-based numbers, []
    when the file has no such heading: the lines after the heading up to the next
    `## ` line. A heading is a whole line, so `## Acceptance` and
    `## Acceptance criteria` are two different sections."""
    out = []
    inside = False
    for number, line in enumerate(text.split("\n"), 1):
        if line.lstrip().startswith("## "):
            inside = line.strip() == "## " + heading
        elif inside:
            out.append((number, line))
    return out


_ITEM = re.compile(r"^\s*- \[[ xX]\]\s*(.*)$")
# The word `unverifiable`, as a word: the lookahead is a boundary a hyphen and a
# letter both fail, so `unverifiable-ness` is not a marker.
_MARKER = re.compile(r"unverifiable(?![-\w])", re.I)
# What a declaration puts between the marker and its why. An item that merely
# names the word ("either the command or the word `unverifiable` followed by
# why") has no separator there and is not a declaration.
_SEPARATORS = ":,;(-"
_SPAN = re.compile(r"`([^`\n]+)`")


def _argument(token):
    """One token only a command carries: an option (`--citations`), a path
    (`bin/tezgah-docs`, `hooks/x.py`) or a script (`run.sh`). A bare word is not
    one, so a backticked phrase is not read as a command."""
    if len(token) > 1 and token.startswith("-"):
        return True
    if token.endswith((".py", ".sh", ".js", ".bash")):
        return True
    _, _, tail = token.partition("/")
    return bool(tail) and any(char.isalnum() for char in tail)


def names_command(text):
    """Does this acceptance item name the command that proves it? A command is a
    backticked run of two or more words carrying an option, a path or a script:
    `bin/tezgah-docs --citations`, `python3 -m unittest tests/test_task.py`. A
    citation (`hooks/tezgah_task.py`, `plan:line`) is not one, and an invocation
    with no argument at all is not recognised either - both are reported, which
    is the safe direction for a report a person reads."""
    for span in _SPAN.findall(text):
        tokens = span.split()
        if len(tokens) > 1 and any(_argument(token) for token in tokens[1:]):
            return True
    return False


def unverifiable_reason(text):
    """The why that follows the word `unverifiable`, or None when the item does
    not declare itself unverifiable. Two shapes are declarations: the marker at
    the item's start, and the marker followed by a why after a separator
    (`unverifiable: no fixture exists`, `unverifiable - the file has none`). A
    bare marker has no why, and a sentence that only names the word is not a
    declaration of anything - both are the same gap the report is about."""
    for found in _MARKER.finditer(text):
        head = text[:found.start()].strip(" `")
        tail = text[found.end():].lstrip(" `")
        if head and tail[:1] not in _SEPARATORS:
            continue
        reason = tail.lstrip(_SEPARATORS + " ").strip()
        if reason:
            return reason
    return None


def acceptance_items(text):
    """One plan file's `## Acceptance` items: a list of
    {"line", "text", "state"}, plus "reason" when the state is "unverifiable".
    One field and not two - "checkable" (the item names a command),
    "unverifiable" (it says so and why) or "missing" (neither) - so no caller can
    read two answers about one item.

    An item is one `- [ ]`/`- [x]` line plus the lines it wraps onto, up to the
    next item or a blank line: the format wraps at 79 columns, so an item is more
    than one line in most plans and a reader that counted lines would point at
    the wrong one."""
    out = []
    for number, line in section_lines(text, "Acceptance"):
        found = _ITEM.match(line)
        if found:
            out.append({"line": number, "text": " ".join(found.group(1).split()),
                        "state": "missing"})
        elif out and line.strip():
            out[-1]["text"] = " ".join((out[-1]["text"] + " " + line).split())
    for item in out:
        reason = unverifiable_reason(item["text"])
        if reason is not None:
            item["state"], item["reason"] = "unverifiable", reason
        elif names_command(item["text"]):
            item["state"] = "checkable"
    return out


ACCEPTANCE_DIRS = ("open", "done")


def acceptance_report(root):
    """Every acceptance item of every plan under `<root>/.tezgah/plans/open` and
    `.tezgah/plans/done`: {"plans": how many plan files were read, "items": [item, ...]},
    each item carrying acceptance_items()'s keys plus "plan" - its path relative
    to root, so a row reads `plan:line` and a person can open it.

    The counts are half the answer: a report that read nothing must not read as
    "everything is checkable", so the caller prints them. Never raises - an
    absent directory or an unreadable file is skipped, not refused: this feeds a
    report, not a gate."""
    items = []
    plans = 0
    for sub in ACCEPTANCE_DIRS:
        directory = os.path.join(root, ".tezgah", "plans", sub)
        try:
            names = sorted(os.listdir(directory))
        except OSError:
            continue
        for name in names:
            if not name.endswith(".md"):
                continue
            path = os.path.join(directory, name)
            try:
                with open(path, "r", encoding="utf-8") as fh:
                    text = fh.read()
            except OSError:
                continue
            plans += 1
            for item in acceptance_items(text):
                item["plan"] = ".tezgah/plans/%s/%s" % (sub, name)
                items.append(item)
    return {"plans": plans, "items": items}


def active(cwd, base):
    """The active task as a dict, or None. Scans `<repo_root>/.tezgah/plans/open/*.md`
    sorted by name, first file whose frontmatter carries a valid `phase`.
    Dict: {"id","title","phase","allowed_paths","path"}: id/title are the
    frontmatter values (id falls back to the filename's NNN), path is the file.
    Never raises: an unreadable directory or file means None (readers fail
    open)."""
    directory = os.path.join(repo_root(cwd, base), ".tezgah", "plans", "open")
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
