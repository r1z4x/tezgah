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

A plan's body is read here too: the acceptance report
(`tezgah-render-table --acceptance`) counts the items that name no command, so
the record the gate reads and the items the report counts have one reader. Two
readers of the body were added beside it and read in the same place - the
`## Acceptance` items a plan cannot enter a writing phase with while any of them
names no command (`acceptance_gap`, the predicate `--strict` refuses on too),
and the spike a plan declares and has not answered (`spike_unanswered`) - for
the same reason: the CLI refuses the phase move and the CI report counts the
same items, and one module keeps them agreeing. The open plans' progress (the
ticked boxes), the plans each one waits on (`after:`) and which ready plans can
run at once (`queue`, `parallel`) are read here for `tezgah-task status`. The
injected open-plans block keeps its own small reader
(`hooks/tezgah_context.py::_plan_row`: id, title, the first `## Next` line).

The `checkpoint:` key is read here for the same reason again: bin/tezgah-task
writes it when the phase moves to `implementation` - the pre-work commit's sha
when the tree was clean, or `pending <sha>` when it was not, `<sha>` being the
`HEAD` the commit the phase waits for has to move off (`checkpoint_sha`, the one
reader of that form). The gate refuses a write in that phase only while the
recorded sha is still HEAD and the tree is still dirty, so the commit its refusal
names clears it by itself.
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


def _list_field(text, key):
    """One frontmatter key's `- item` block as a list of strings, [] when the key
    is absent or carries no block."""
    out = []
    collecting = False
    for line in _frontmatter_lines(text):
        stripped = line.strip()
        if collecting and stripped.startswith("- "):
            out.append(stripped[2:].strip())
            continue
        collecting = (not stripped.startswith("- ") and ":" in stripped
                      and stripped.partition(":")[0].strip() == key)
    return out


def allowed_paths(text):
    """The `allowed_paths:` list as a list of globs, [] when absent."""
    return _list_field(text, "allowed_paths")


def after(text):
    """The plan ids this plan waits on (`after:`), in the order written: the
    `- NNN` block `set_fields` writes, or the inline `after: 012, 015` a person
    types. [] when the plan waits on nothing - which is what lets it run beside
    the others."""
    return (_list_field(text, "after")
            or frontmatter(text).get("after", "").replace(",", " ").split())


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


_ITEM = re.compile(r"^\s*- \[([ xX])\]\s*(.*)$")
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
    (`bin/tezgah-docs`, `hooks/x.py`), the current directory (`.`, `..`) or a
    script (`run.sh`). A bare word is not one, so a backticked phrase is not read
    as a command. `.` counts because it is a path like any other and is what the
    commonest lint invocation ends in (`ruff check .`) - read as a bare word, the
    item that names it was reported as naming no command at all."""
    if len(token) > 1 and token.startswith("-"):
        return True
    if token in (".", ".."):
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
    {"line", "text", "checked", "state"}, plus "reason" when the state is
    "unverifiable". One field and not two - "checkable" (the item names a
    command), "unverifiable" (it says so and why) or "missing" (neither) - so no
    caller can read two answers about one item. "checked" is the box (`- [x]`),
    which is the plan's progress and says nothing about the item's proof.

    An item is one `- [ ]`/`- [x]` line plus the lines it wraps onto, up to the
    next item or a blank line: the format wraps at 79 columns, so an item is more
    than one line in most plans and a reader that counted lines would point at
    the wrong one."""
    out = []
    for number, line in section_lines(text, "Acceptance"):
        found = _ITEM.match(line)
        if found:
            out.append({"line": number, "text": " ".join(found.group(2).split()),
                        "checked": found.group(1) != " ", "state": "missing"})
        elif out and line.strip():
            out[-1]["text"] = " ".join((out[-1]["text"] + " " + line).split())
    for item in out:
        reason = unverifiable_reason(item["text"])
        if reason is not None:
            item["state"], item["reason"] = "unverifiable", reason
        elif names_command(item["text"]):
            item["state"] = "checkable"
    return out


def unproven(items):
    """The items that name no command and declare no `unverifiable` - the one
    predicate both the phase move (`acceptance_gap`) and `render_table
    --acceptance --strict` refuse on, so the two cannot let through different
    plans."""
    return [item for item in items if item["state"] == "missing"]


def acceptance_gap(text):
    """The plan's Acceptance items that nothing can check: each one names no
    command and declares no `unverifiable`. [] when every item names its proof,
    and [] when the plan has no Acceptance items at all.

    Any such item is a gap, not only a section made of them: the format asks for
    the proof per item, and the strict report refuses an open plan on one, so a
    phase move that let one through would be refused later by the reader it was
    meant to answer first. A plan with an empty or absent section is a different
    defect - the format asks plan-add to write the items, and the report does not
    gate that case either - so refusing it here would tax every plan that
    predates the rule. Returns the items so a refusal can name them."""
    return unproven(acceptance_items(text))


# The `checkpoint:` values a plan can carry: a commit sha (the tree was clean at
# the phase move, so the boundary is already real), or `pending <sha>` while the
# tree still holds work no commit names - `<sha>` being the `HEAD` the commit the
# gate's refusal names has to move off. The CLI writes both, the gate reads both.
CHECKPOINT_PENDING = "pending"


def checkpoint(text):
    """The plan's `checkpoint:` value: the pre-work commit the phase's work
    branches from, `pending <sha>` while that work is uncommitted, or None when
    the plan carries no such field - a phase started before the field existed,
    which no rule holds to it."""
    return frontmatter(text).get("checkpoint")


def checkpoint_sha(value):
    """The `HEAD` a `pending` checkpoint has to move off, or "" when the value
    names no tree to compare: a plain sha (the boundary is already real), a bare
    `pending` (a record written before the sha was recorded, or a branch with no
    commit to name at all), None, or any other shape. The gate fails open on ""
    because it cannot tell whether the commit landed, and a refusal it cannot
    answer would lock the very phase it guards - the defect this sha exists to
    close."""
    parts = str(value or "").split()
    if len(parts) == 2 and parts[0] == CHECKPOINT_PENDING:
        return parts[1]
    return ""


def slug(path):
    """A plan file's slug: its name without `.md` (`001-add-login`), which
    is the branch's own tail (`plan/NNN-slug`) and what a checkpoint commit names.
    Built here so the CLI's note and the gate's refusal cannot spell it two
    ways."""
    name = os.path.basename(path)
    return name[:-3] if name.endswith(".md") else name


def checkpoint_command(path):
    """The one command that makes a plan's boundary real: a commit whose message
    marks where the risky work starts. Named by the CLI's note and by the gate's
    refusal - the same string, from the same caller-visible place - and running it
    is also what clears the refusal: it moves HEAD off the sha the record wrote
    (`checkpoint_sha`)."""
    return 'git add -A && git commit -m "checkpoint: before %s"' % slug(path)


def spike_unanswered(text):
    """True when the plan runs a spike (`spike:` names its one question) that has
    not answered yet (`spike_recorded:` names nothing), else False.

    The four keys are optional and their absence invents nothing: no `spike:`
    question means no spike, which is how a plan that predates the field is never
    held to it - the fail-open direction every reader here takes. `spike_box:` is
    the time box and `spike_throwaway:` the throwaway contract; nothing reads
    either, because the throwaway half is already enforceable through
    `allowed_paths` (a spike pins its allowlist to a scratch path that is never
    merged) and a second mechanism for one rule is the copy that drifts."""
    fields = frontmatter(text)
    return bool(fields.get("spike")) and not fields.get("spike_recorded")


ACCEPTANCE_DIRS = ("open", "done")
# The `status:` a plan carries in each directory (plan-add's format): a plan
# under open/ is open or blocked, one under done/ is done or discarded.
OPEN_STATUSES = ("open", "blocked")


def _plan_files(root, sub):
    """(name, path, text) for every readable `*.md` under
    `<root>/.tezgah/plans/<sub>`, sorted by name; an absent directory or an
    unreadable file is skipped, so a reader built on it never raises."""
    directory = os.path.join(root, ".tezgah", "plans", sub)
    try:
        names = sorted(os.listdir(directory))
    except OSError:
        return
    for name in names:
        if not name.endswith(".md"):
            continue
        path = os.path.join(directory, name)
        try:
            with open(path, "r", encoding="utf-8") as fh:
                text = fh.read()
        except OSError:
            continue
        yield name, path, text


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
        for name, _, text in _plan_files(root, sub):
            plans += 1
            for item in acceptance_items(text):
                item["plan"] = ".tezgah/plans/%s/%s" % (sub, name)
                items.append(item)
    return {"plans": plans, "items": items}


def _plan_id(fields, name):
    return fields.get("id") or name.split("-")[0]


def _prefix(glob):
    """The literal head of a glob: everything before its first `*`."""
    return glob.split("*", 1)[0]


def scopes_overlap(first, second):
    """Could two allowlists name one file? An empty list is every path, and two
    globs can only meet when one literal head is a prefix of the other's - so
    `hooks/a*.py` and `hooks/b*.py` never do, and `**/x` meets everything.
    ponytail: prefix test, not glob intersection - it says "overlap" for
    `hooks/*.py` against `hooks/x/y.md`, which only costs a missed pairing."""
    if not first or not second:
        return True
    return any(a.startswith(b) or b.startswith(a)
               for a in map(_prefix, first) for b in map(_prefix, second))


def queue(root):
    """Every open plan as a row: {"id", "status", "path", "checked", "items" (the
    Acceptance boxes ticked, and their count), "after" ([id, state] per plan it
    waits on: `done`, `discarded`, `open` or `missing` when no plan carries the
    id), "ready" (not blocked, and everything it waits on is done), "overlaps"
    (the other open plans whose allowed_paths can name one of its files)}.

    The plans' progress and order had no reader: the boxes were counted nowhere
    and nothing said which plans could run beside each other. Never raises."""
    state = {}
    for name, _, text in _plan_files(root, "done"):
        fields = frontmatter(text)
        state[_plan_id(fields, name)] = ("discarded" if fields.get("status") == "discarded"
                                         else "done")
    rows = []
    scopes = {}
    for name, path, text in _plan_files(root, "open"):
        fields = frontmatter(text)
        ident = _plan_id(fields, name)
        state[ident] = "open"
        items = acceptance_items(text)
        scopes[ident] = allowed_paths(text)
        rows.append({"id": ident, "status": fields.get("status", ""), "path": path,
                     "checked": sum(1 for item in items if item["checked"]),
                     "items": len(items), "after": after(text)})
    for row in rows:
        row["after"] = [[ident, state.get(ident, "missing")] for ident in row["after"]]
        row["ready"] = (row["status"] != "blocked"
                        and all(dep == "done" for _, dep in row["after"]))
        row["overlaps"] = [other["id"] for other in rows if other is not row
                           and scopes_overlap(scopes[row["id"]], scopes[other["id"]])]
    return rows


def parallel(rows):
    """The ready plans that can run at once, in id order: each one shares no
    allowed_paths prefix with any other picked (greedy, first id first). [] when
    fewer than two qualify - one plan is not a fan-out."""
    picked = []
    for row in rows:
        if row["ready"] and not any(other in row["overlaps"] for other in picked):
            picked.append(row["id"])
    return picked if len(picked) > 1 else []


def active(cwd, base):
    """The active task as a dict, or None. Scans `<repo_root>/.tezgah/plans/open/*.md`
    sorted by name, first file whose frontmatter carries a valid `phase`.
    Dict: {"id","title","phase","allowed_paths","checkpoint","path"}: id/title are
    the frontmatter values (id falls back to the filename's NNN), checkpoint is
    the frontmatter value or None when the plan carries none, path is the file.
    Never raises: an unreadable directory or file means None (readers fail
    open)."""
    root = repo_root(cwd, base)
    directory = os.path.join(root, ".tezgah", "plans", "open")
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
        # A plan the repository shipped is data, not the user's task: its phase
        # and allowlist would lock writes in a cloned repo (audit L-16). Only
        # positive evidence turns the rule off - the index tracks `.tezgah` -
        # never a can't-tell, which would switch the user's own guard off in
        # silence (review R2); the answer is cached on the index's stat.
        from tezgah_paths import workspace_tracked
        if workspace_tracked(root):
            return None
        return {"id": fields.get("id") or name.split("-")[0],
                "title": fields.get("title", ""),
                "phase": fields["phase"],
                "allowed_paths": allowed_paths(text),
                # read from the frontmatter already in hand, so the gate's
                # checkpoint rule costs this module no second read of the plan
                "checkpoint": fields.get("checkpoint"),
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
