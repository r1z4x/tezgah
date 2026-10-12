#!/usr/bin/env python3
"""The active task: one plan file's phase and its path allowlist.

A task is not a second record beside the plan - it IS the plan file under
`.tezgah/plans/open/`, with two optional frontmatter keys that only its CLI
(bin/tezgah-task, run by the orchestrating session itself) writes:

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

The slice journal lives here too (`open_slice` ... `slice_lines`): one row per
delegated slice in `<main checkout>/.tezgah/slices/slices.db`, written by
the post-tool path on a spawn call and by `tezgah-task slice`, so a parent
crash, an omp `/clear`, a quota stop or a host switch loses no slice. They shell
out to git and read omp transcripts; the Stop rule reads `pending` (fail open).
"""
import contextlib
import os
import re
import shlex

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
# A runner whose test entry point is a bare subcommand: `pnpm test`, `cargo
# test`, `uv run pytest` carry no option and no path, yet each is the command.
# The runner has to be the first word, so `run the tests` stays prose.
_RUNNERS = ("npm", "pnpm", "yarn", "bun", "deno", "cargo", "go", "make", "mix",
            "dotnet", "gradle", "mvn", "poetry", "uv")
_SUBCOMMANDS = ("test", "run")


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
    backticked run of two or more words carrying an option, a path or a script
    (`bin/tezgah-docs --citations`, `python3 -m unittest tests/test_task.py`), or
    a known runner followed by `test` or `run` (`pnpm test`, `npm run test`). A
    citation (`hooks/tezgah_task.py`, `plan:line`) is not one, and any other
    invocation with no argument is not recognised either - both are reported,
    which is the safe direction for a report a person reads."""
    for span in _SPAN.findall(text):
        tokens = span.split()
        if len(tokens) > 1 and (any(_argument(token) for token in tokens[1:]) or
                                (tokens[0] in _RUNNERS and tokens[1] in _SUBCOMMANDS)):
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


def checkpoint_command(path, worktree=None):
    """The one command that makes a plan's boundary real: a commit whose message
    marks where the risky work starts. Named by the CLI's note and by the gate's
    refusal - the same string, from the same caller-visible place - and running it
    is also what clears the refusal: it moves HEAD off the sha the record wrote
    (`checkpoint_sha`). A plan held by its own worktree (`branch_task`) commits
    there, so the command names that checkout."""
    git = "git -C %s" % shlex.quote(worktree) if worktree else "git"
    return '%s add -A && %s commit -m "checkpoint: before %s"' % (git, git, slug(path))


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
    """The active task as a dict, or None. A linked worktree on a `plan/NNN-...`
    branch answers plan NNN when that plan carries a phase (`branch_task`), so
    two plans can run at once, one per worktree. Anywhere else - the main
    checkout, or a worktree on another branch - it reads the main checkout's
    `.tezgah/plans/open/*.md` sorted by name: the first plan carrying a valid
    `phase` that no linked worktree holds (`plan_holders`), else the first plan
    carrying one.
    Dict: {"id","title","phase","allowed_paths","checkpoint","branch","path"}:
    id/title are the frontmatter values (id falls back to the filename's NNN),
    checkpoint is the frontmatter value or None when the plan carries none,
    path is the file.
    Never raises: an unreadable directory or file means None (readers fail
    open)."""
    root = repo_root(cwd, base)
    own = branch_task(root)
    if own:
        return own
    from tezgah_paths import linked_main
    main = linked_main(root) or root
    records = _phased(main)
    if len(records) > 1:
        branches = _worktree_branches(main)
        for record in records:
            if not any(_binds(record["branch"], record["id"], b) for b in branches):
                return record
    return records[0] if records else None


def _phased(root, ident=None):
    """Every open plan under `root` carrying a valid phase - plan `ident` only,
    when one is named - as active()'s dicts, in name order; [] when there is
    none or a plan file cannot be read."""
    directory = os.path.join(root, ".tezgah", "plans", "open")
    try:
        names = sorted(os.listdir(directory))
    except OSError:
        return []
    out = []
    for name in names:
        if not name.endswith(".md"):
            continue
        path = os.path.join(directory, name)
        try:
            with open(path, "r", encoding="utf-8") as fh:
                text = fh.read()
        except OSError:
            return []
        fields = frontmatter(text)
        if fields.get("phase") not in TASK_PHASES:
            continue
        ident_here = fields.get("id") or name.split("-")[0]
        if ident is not None and ident_here != ident:
            continue
        out.append({"id": ident_here,
                    "title": fields.get("title", ""),
                    "phase": fields["phase"],
                    "allowed_paths": allowed_paths(text),
                    # read from the frontmatter already in hand, so the gate's
                    # checkpoint rule costs this module no second read of the plan
                    "checkpoint": fields.get("checkpoint"),
                    "branch": fields.get("branch", ""),
                    "path": path})
    # A plan the repository shipped is data, not the user's task: its phase
    # and allowlist would lock writes in a cloned repo (audit L-16). Only
    # positive evidence turns the rule off - the index tracks `.tezgah` -
    # never a can't-tell, which would switch the user's own guard off in
    # silence (review R2); the answer is cached on the index's stat.
    from tezgah_paths import workspace_tracked
    if out and workspace_tracked(root):
        return []
    return out


_PLAN_BRANCH = re.compile(r"plan/(\d+)(?:-|$)")


def worktree_branch(top):
    """The branch the linked worktree `top` checks out, read from its admin
    `HEAD` without a fork (the gate asks on every write); None for a detached
    HEAD, a plain checkout or anything unreadable."""
    try:
        with open(os.path.join(top, ".git"), encoding="utf-8") as fh:
            admin = fh.readline().strip()[len("gitdir:"):].strip()
        with open(os.path.join(top, admin, "HEAD"), encoding="utf-8") as fh:
            head = fh.readline().strip()
    except (OSError, UnicodeDecodeError):
        return None
    prefix = "ref: refs/heads/"
    return head[len(prefix):] if head.startswith(prefix) else None


def plan_of_branch(branch):
    """The plan id a `plan/NNN-slug` branch names, else None."""
    found = _PLAN_BRANCH.match(branch or "")
    return found.group(1) if found else None


def _binds(declared, ident, branch):
    """Does `branch` hold plan `ident`? It has to name the plan (`plan/NNN-...`)
    and, when the plan declares its `branch:`, be that branch: a worktree on
    `plan/018-anything` must not pick up plan 018's scope."""
    return bool(branch) and plan_of_branch(branch) == ident and (
        not declared or declared == branch)


def _worktree_branches(main):
    """{branch: top} for every linked worktree of the main checkout `main`."""
    from tezgah_paths import worktrees
    out = {}
    for top in worktrees(main)[1:]:
        branch = worktree_branch(top)
        if branch:
            out[branch] = top
    return out


def plan_holders(main):
    """{plan id: worktree top} for every open plan under the main checkout
    `main` whose own branch (`_binds`) a linked worktree has checked out, phase
    or not."""
    branches = _worktree_branches(main)
    out = {}
    if not branches:
        return out
    for name, _, text in _plan_files(main, "open"):
        fields = frontmatter(text)
        ident = _plan_id(fields, name)
        for branch, top in branches.items():
            if _binds(fields.get("branch", ""), ident, branch):
                out[ident] = top
    return out


def branch_task(top):
    """Plan NNN's record (active()'s dict, plus "worktree": `top`, the checkout
    whose HEAD and tree its checkpoint is read against) when `top` is a linked
    worktree on plan NNN's own branch (`_binds`) and plan NNN, open under the
    main checkout, carries a phase. None otherwise - another branch, a plan with
    no phase, an unknown mapping - and the caller reads the main checkout's task
    (plan 093)."""
    branch = worktree_branch(top)
    ident = plan_of_branch(branch)
    if ident is None:
        return None
    from tezgah_paths import linked_main
    main = linked_main(top)
    for record in _phased(main, ident) if main else ():
        if _binds(record["branch"], ident, branch):
            record["worktree"] = top
            return record
    return None


def worktree_task(path, cwd, base):
    """The record a write to `path` is held to when it lands in a sibling linked
    worktree on a plan branch (`branch_task`), else None. A path under cwd's own
    root is active()'s to answer, so it pays one realpath and nothing more."""
    root = repo_root(cwd, base)
    path = os.path.expanduser(path)
    real = os.path.realpath(path if os.path.isabs(path) else os.path.join(cwd, path))
    if _under(real, root):
        return None
    top = _sibling_worktree(real, root)
    return branch_task(top) if top else None


def main_relative(path, cwd, base):
    """`path` (absolute or relative to cwd) as a posix path relative to the main
    checkout of cwd's repository - the checkout that keeps `.tezgah/plans` -
    or None outside it. A session in a linked worktree reads the same records
    as one in the main checkout."""
    from tezgah_paths import linked_main
    root = repo_root(cwd, base)
    main = linked_main(root) or root
    path = os.path.expanduser(path)
    real = os.path.realpath(path if os.path.isabs(path) else os.path.join(cwd, path))
    if real == main or not _under(real, main):
        return None
    return real[len(main) + 1:].replace(os.sep, "/")


def phased_record(root, rel):
    """True when `rel` (relative to the main checkout `root`) is an open plan
    carrying a valid phase - a record only bin/tezgah-task writes, whichever
    plan the main checkout reads as active. Matched without case, since a
    case-insensitive filesystem opens `.TEZGAH/PLANS/open/x.md` as the record."""
    parts = (rel or "").split("/")
    if (len(parts) != 4 or "/".join(parts[:3]).casefold() != ".tezgah/plans/open"
            or not parts[3].casefold().endswith(".md")):
        return False
    for name, _, text in _plan_files(root, "open"):
        if name.casefold() == parts[3].casefold():
            return frontmatter(text).get("phase") in TASK_PHASES
    return False


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


def relative(path, cwd, base, worktrees=False):
    """The realpath of `path` (absolute or relative to cwd) as a posix path
    relative to repo_root(cwd, base), or None when it resolves outside that root
    (so an outside write can never be inside the allowlist).

    With `worktrees`, a linked worktree of the same repository is that
    repository, not outside it: the contract gives every writing slice its own
    worktree, and an allowlist that could not name `hooks/a.py` there refused the
    workflow it prescribes (three slices of plan 077 hit it). A path under such a
    worktree answers relative to the worktree's top. Only the allowlist asks for
    this (`hooks/tezgah_gate.py::task_reason`); the record and workspace rules
    keep the main-root reading, so their decisions do not move. The test is
    fork-free and only a path already outside the root pays for it; a worktree of
    another repository is still outside."""
    root = repo_root(cwd, base)
    path = os.path.expanduser(path)  # a host may spell it `~/...`
    real = os.path.realpath(path if os.path.isabs(path) else os.path.join(cwd, path))
    if real == root or not _under(real, root):
        top = _sibling_worktree(real, root) if worktrees else None
        if top is None or real == top:
            # the root itself is not a path inside the root: an allowlist is
            # about files under it, so this is a None like any other, and every
            # caller fails in the refusing direction
            return None
        root = top
    return real[len(root) + 1:].replace(os.sep, "/")


def _sibling_worktree(real, root):
    """The top of the linked worktree holding `real` when it is a checkout of the
    repository `root` is a checkout of, else None.

    The worktree's admin directory has to point back at it (`<admin>/gitdir` is
    `<top>/.git`, which git always writes): a `.git` file planted anywhere that
    names a real admin directory would otherwise make any directory a sibling."""
    from tezgah_paths import linked_main, worktree_top
    top = worktree_top(real)
    if top is None:
        return None
    main = linked_main(root) or root
    if linked_main(top) != os.path.realpath(main):
        return None
    try:
        with open(os.path.join(top, ".git"), encoding="utf-8") as fh:
            admin = fh.readline().strip()[len("gitdir:"):].strip()
        admin = os.path.normpath(os.path.join(top, admin))
        with open(os.path.join(admin, "gitdir"), encoding="utf-8") as fh:
            back = fh.readline().strip()
    except (OSError, UnicodeDecodeError):
        return None
    back = os.path.normpath(os.path.join(admin, back))
    return top if os.path.realpath(back) == os.path.join(top, ".git") else None


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


def _lines(path):
    with open(path, "r", encoding="utf-8") as fh:
        return fh.read().split("\n")


def _write_lines(path, lines):
    with open(path, "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines))


def set_box(path, line, checked):
    """Set the `- [ ]`/`- [x]` box on 1-based `line` (an acceptance item's
    `line`). Raises OSError."""
    lines = _lines(path)
    lines[line - 1] = re.sub(r"- \[[ xX]\]", "- [x]" if checked else "- [ ]",
                             lines[line - 1], count=1)
    _write_lines(path, lines)


def set_section(path, heading, body):
    """Replace the body of the last `## <heading>` section - the newest, since
    a plan appends a dated `## State (...)` - with `body` and one blank line.
    Returns False, writing nothing, when the plan has no such section. Raises
    OSError."""
    lines = _lines(path)
    heads = [i for i, line in enumerate(lines)
             if re.match(r"## %s(\s|$)" % re.escape(heading), line.strip())]
    if not heads:
        return False
    start = heads[-1] + 1
    end = next((i for i in range(start, len(lines))
                if lines[i].lstrip().startswith("## ")), len(lines))
    lines[start:end] = body.strip("\n").split("\n") + [""]
    _write_lines(path, lines)
    return True


# ---------------------------------------------------------------- slice journal
#
# One row per delegated slice in `<main checkout>/.tezgah/slices/slices.db`,
# so a parent crash, an omp `/clear`, a quota stop or a model or host switch
# loses no slice: the record names the brief, the worktree and branch it works
# in, and how it ended. Written by the post-tool path on a spawn call
# (`note_spawn`) and by `tezgah-task slice`; read by the context line
# (`slice_lines`), the Stop rule and `tezgah-task slice reconcile|resume|stats`.
# Every reader fails open: an unreadable record is skipped, never a refusal.
# These functions shell out to git; none of them is on the gate's write path.

SLICE_KINDS = ("agent", "job")
SLICE_HOSTS = ("omp", "claude", "codex", "cursor", "opencode", "dsh")
# `stale`: no terminal status was observed within SLICE_IDLE_SECONDS - a host
# that reports none (Codex `spawn_agent` returns at once and tezgah sees no child
# event) or a child that died without writing its end. It leaves the pending
# list without being read as finished or as failed.
SLICE_STATUSES = ("open", "done", "stopped", "resumed", "stale")
SLICE_CLOSED = ("done", "stopped", "resumed", "stale")
SLICE_IDLE_SECONDS = 6 * 3600
FAILURES = ("quota", "rate_limit", "aborted", "timeout", "cut_off", "error")
SLICE_BRIEF = 4000
SLICE_LINE = 160
SLICE_TAIL = 64 * 1024
_SLICE_ID = re.compile(r"[^A-Za-z0-9._-]+")
# Failure classes, first match wins, in this order. The table moved here from
# the research line's measure (data/E2-subagent-stops/measure.py::CLASSES) and
# was narrowed to the classes a lever exists for (`tezgah-task slice stats`).
_CLASSES = (
    ("rate_limit", re.compile(r"\b429\b|rate[ _-]?limit", re.I)),
    ("quota", re.compile(r"quota|key limit exceeded|usage limit|"
                         r"\b40[23]\b.*\blimit|\blimit\b.*\b40[23]\b", re.I)),
    ("aborted", re.compile(r"abort|cancell?ed", re.I)),
    ("timeout", re.compile(r"timed out|timeout", re.I)),
    ("cut_off", re.compile(r"max[ _]turns|max_tokens|cut off|context[ _]length",
                           re.I)),
)


def _now():
    import time
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _git(cwd, *args):
    """One git command's stdout in `cwd`, or None when git cannot answer."""
    import subprocess
    try:
        out = subprocess.run(["git", "-C", cwd] + list(args), capture_output=True,
                             text=True, timeout=10)
    except (OSError, subprocess.SubprocessError):
        return None
    return out.stdout.strip() if out.returncode == 0 else None


def _journal_root(root):
    """The main checkout of `root`'s repository: every worktree of one repository
    writes one journal, so a slice opened from a worktree is still found from the
    main checkout the parent session runs in."""
    from tezgah_paths import linked_main
    real = os.path.realpath(root)
    return linked_main(real) or real


def slice_dir(root):
    """`<main checkout>/.tezgah/slices`, the one directory the records live in."""
    return os.path.join(_journal_root(root), ".tezgah", "slices")


def _digest(text):
    import hashlib
    return hashlib.sha1(text.encode("utf-8", "replace")).hexdigest()[:12]


def slice_id(name, brief=""):
    """A record id: `name` cut to [A-Za-z0-9._-] and 80 characters, else the
    first 12 hex digits of the brief's sha1 - so a re-dispatch of the same brief
    re-opens the same record and counts an attempt."""
    sid = _SLICE_ID.sub("-", str(name or "")).strip("-.")[:80]
    return sid or _digest(brief)


# The journal is one SQLite file opened like the taste store
# (`tezgah_store.connect`: WAL, a busy timeout, 0600). One JSON file per record
# piled up a file per subagent in every repository (owner, 2026-10-11). `row`
# is the record as JSON; `parent`, `status` and `updated` are the columns a
# reader filters and sorts on, and `seq` orders two writes in one second.
SLICE_DB = "slices.db"
SLICE_SCHEMA = """
CREATE TABLE IF NOT EXISTS slices (id TEXT PRIMARY KEY, parent TEXT NOT NULL,
                                   status TEXT NOT NULL, updated TEXT NOT NULL,
                                   seq INTEGER NOT NULL, row TEXT NOT NULL);
"""


@contextlib.contextmanager
def _journal(root, create=True):
    """The journal database of `root`'s repository, the `*.json` records an
    older release wrote imported first (`_import_json`). With `create` False it
    yields None where neither the database nor an old record exists, so a read
    leaves no file behind. The directory carries a `.gitignore` of `*`: the
    records are runtime state, never part of the private `.tezgah` history."""
    import glob
    import tezgah_store
    folder = slice_dir(root)
    path = os.path.join(folder, SLICE_DB)
    if not create and not os.path.exists(path) and not glob.glob(
            os.path.join(folder, "*.json")):
        yield None
        return
    os.makedirs(folder, mode=0o700, exist_ok=True)
    ignore = os.path.join(folder, ".gitignore")
    if not os.path.exists(ignore):
        with open(ignore, "w", encoding="utf-8") as fh:
            fh.write("*\n")
    conn = tezgah_store.connect(path, SLICE_SCHEMA, version=1)
    try:
        _import_json(conn, folder)
        yield conn
    finally:
        conn.close()


def _import_json(conn, folder):
    """Bring the one-file-per-record journal into the table, then delete each
    file it took. A file whose `updated` is newer than the row replaces it - an
    older release still running writes files beside the database - and an
    older one leaves the row alone. A file that does not parse, or whose id is
    not a string, stays where it is. With no old file, one glob."""
    import glob
    import json
    for path in glob.glob(os.path.join(folder, "*.json")):
        try:
            with open(path, encoding="utf-8") as fh:
                rec = json.load(fh)
        except (OSError, ValueError):
            continue
        if not isinstance(rec, dict) or not isinstance(rec.get("id"), str) \
                or not rec["id"]:
            continue
        held = conn.execute("SELECT updated FROM slices WHERE id = ?",
                            (rec["id"],)).fetchone()
        if held is None or str(rec.get("updated") or "") > held[0]:
            _put(conn, rec)
        try:
            os.remove(path)
        except OSError:
            pass


def _put(conn, rec):
    """Upsert one record."""
    import json
    conn.execute(
        "INSERT OR REPLACE INTO slices (id, parent, status, updated, seq, row) "
        "VALUES (?, ?, ?, ?, (SELECT COALESCE(MAX(seq), 0) + 1 FROM slices), ?)",
        (rec["id"], str(rec.get("parent") or ""), str(rec.get("status") or ""),
         str(rec.get("updated") or ""), json.dumps(rec, sort_keys=True)))


def _row(text):
    import json
    try:
        rec = json.loads(text)
    except ValueError:
        return None
    return rec if isinstance(rec, dict) and rec.get("id") else None


def _read_record(root, sid):
    """The record `sid`, or None; a journal that cannot be opened reads as none."""
    import tezgah_store
    try:
        with _journal(root, create=False) as db:
            hit = db and db.execute("SELECT row FROM slices WHERE id = ?",
                                    (slice_id(sid),)).fetchone()
    except tezgah_store.ERRORS:
        return None
    return _row(hit[0]) if hit else None


def _write_record(root, rec):
    """Write one record (one upsert statement) and return it. A database that
    cannot be opened or written raises OSError, the error every caller already
    handles (`tezgah-task slice` prints it, the hooks swallow it)."""
    import tezgah_store
    try:
        with _journal(root) as db:
            _put(db, rec)
    except tezgah_store.ERRORS as exc:
        raise OSError("slice journal %s: %s" % (slice_dir(root), exc)) from exc
    return rec


def _own_id(root, base, brief, parent):
    """The record id a spawn of `base` opens: `base` itself, unless another
    session holds that record under another brief. Then it is this session's
    own record of that name, else `base-<digest6>` of the brief, so another
    session's stopped slice stays its owner's (research orchestrator-flow-audit
    S7). A same-brief re-dispatch from another session still re-opens `base`."""
    held = _read_record(root, base)
    if (held is None or not parent or not brief
            or held.get("parent") in ("", None, parent)
            or held.get("brief") == brief):
        return base
    own = next((r["id"] for r in slices(root) if r.get("parent") == parent
                and (r.get("name") or r["id"]) == base), None)
    return own or "%s-%s" % (base, _digest(brief)[:6])


def find_slice(root, ref, session=None):
    """The record `ref` names for `tezgah-task slice done|stop|resume`. An
    exact id answers whatever session owns it: an id is unambiguous, and it is
    what `slice reconcile` and the review guard print, so a crashed session's
    slice stays reachable. A bare spawned `name` is a lookup: with `session`
    (TEZGAH_SESSION), the newest record of that name the session spawned or no
    session owns; without one, the one record of that name. None when nothing
    answers."""
    ref = slice_id(ref)
    recs = slices(root)
    exact = next((r for r in recs if r["id"] == ref), None)
    if exact or session:
        return exact or next((r for r in recs if r.get("name") == ref
                              and r.get("parent") in (session, "", None)), None)
    named = [r for r in recs if r.get("name") == ref]
    return named[0] if len(named) == 1 else None


def _worktree_in(root, *texts):
    """The linked worktree of this repository the first of `texts` that names
    one names, else "": a slice's own task before the batch's shared context
    (which may list every slice's worktree), the one named last in a text, and
    on a tie the longer path, since `.../a` is found inside `.../a-b` at the
    same place. What reconcile, resume, the board and merge-plan read."""
    from tezgah_paths import worktrees
    trees = worktrees(root)[1:]
    for text in texts:
        found = [p for p in trees if text and p in text]
        if found:
            return max(found, key=lambda p: (text.rfind(p), len(p)))
    return ""


def _named_worktree(root, *texts):
    """(worktree, branch) for the linked worktree `_worktree_in` reads off
    `texts`, else ("", "")."""
    top = _worktree_in(root, *texts)
    return (top, _git(top, "symbolic-ref", "-q", "--short", "HEAD") or "") if top else ("", "")


# Where a brief says its slice works: a `Worktree:`, `Checkout` or `Cwd:` line
# opening with an absolute path. A path merely mentioned - a worktree to remove,
# a sibling's tree, a file to read - is no declaration (review of S6, F2). Only
# the main-checkout refusal reads it (`tezgah_gate.lease_reason`).
_DECLARED = re.compile(r"(?im)^[ \t>#*_-]*(?:worktree|checkout|cwd)\b[*_]*[ \t]*:?"
                       r"[*_]*[ \t]*`?(/[^\s`'\"()<>,;]+)")


def _declared_in(root, *texts):
    """The linked worktree of this repository the first of `texts` that
    declares a checkout of it declares, else "": a slice's own task before the
    batch's shared context, the last declaration in a text. A declared main
    checkout is none - an integrator works there."""
    from tezgah_paths import worktrees
    trees = worktrees(root)
    for text in texts:
        found = [os.path.realpath(p.rstrip("/.:")) for p in _DECLARED.findall(text or "")]
        found = [p for p in found if p in trees]
        if found:
            return found[-1] if found[-1] != trees[0] else ""
    return ""


# `Owns:` in a slice's own task: the repository-relative globs only that slice
# writes while its record is open (research orchestrator-flow-audit S6, pick
# V2). The gate refuses a sibling's write into them (`tezgah_gate.lease_reason`).
# The globs follow on the line, split on commas and spaces, or - with nothing
# after the colon - as the `- glob` list items under it. Markdown emphasis and
# backticks are dropped; an absolute glob under the slice's checkout is cut to it.
_OWNS = re.compile(r"(?i)^[ \t>#*_-]*owns[*_]*[ \t]*:[*_]*[ \t]*(.*)$")
_LIST_ITEM = re.compile(r"^[ \t>]*(?:[-*+]|\d+[.)])[ \t]+(.+)$")


def owned_globs(text, tops=()):
    """The `Owns:` globs `text` names, in order, each once."""
    found, lines = [], (text or "").splitlines()
    for i, line in enumerate(lines):
        hit = _OWNS.match(line)
        if not hit:
            continue
        if hit.group(1).strip():
            found.append(hit.group(1))
            continue
        for item in lines[i + 1:]:
            listed = _LIST_ITEM.match(item)
            if not listed:
                break
            found.append(listed.group(1))
    out = []
    for line in found:
        for glob in re.split(r"[\s,]+", line.replace("`", "")):
            glob = glob.rstrip(".;")
            top = next((t for t in tops if t and glob.startswith(t + "/")), "")
            glob = glob[len(top) + 1:] if top else glob
            if glob and glob not in out:
                out.append(glob)
    return out


def slice_of(root, parent, name):
    """The newest record `parent` spawned under `name` - a subagent's own
    record, read from its `spawned` row (`tezgah_integrity.spawn_of`), or from
    Claude's `agent_id`, which a background spawn stores as `child` - else
    None. An exact name or child first; omp names a re-dispatch `<name>-2`, so
    the bare name answers only after that."""
    if not (parent and name):
        return None
    mine = [r for r in slices(root) if r.get("parent") == parent]
    base = re.sub(r"-\d+$", "", name)
    return (next((r for r in mine if (r.get("name") or r["id"]) == name
                  or r.get("child") == name), None)
            or next((r for r in mine if (r.get("name") or r["id"]) == base), None))


def owner_of(root, path, parent, me):
    """The open record of another writing slice `parent` spawned whose `owns`
    matches the repository-relative `path`, else None; `me` is the writing
    slice's id. A reader - an agent named for a read-only role - holds no
    lease, whatever `Owns:` line its task quotes. A hit re-reads after
    `pending`, which closes an omp sibling whose child transcript ended, so a
    finished owner frees its files."""
    def held():
        return next((r for r in slices(root) if parent and r.get("parent") == parent
                     and r.get("status") == "open" and r["id"] != me
                     and not _READ_ONLY_AGENT.search(r.get("agent") or "")
                     and any(match(path, g) for g in r.get("owns") or ())), None)
    if held() is None:
        return None
    pending(root)
    return held()


def close_child(root, parent, child):
    """Close as done the open record `parent` spawned whose `child` is the
    host's id of a background child that just ended (Claude's SubagentStop),
    and return it; None when no record holds it."""
    rec = next((r for r in slices(root) if parent and child and r.get("parent") == parent
                and r.get("child") == child and r.get("status") == "open"), None)
    return close_slice(root, rec["id"], "done") if rec else None


BOARD_LINES = 12


def board(root, parent=None, limit=BOARD_LINES):
    """One bounded line (SLICE_LINE) per open record `parent` spawned - every
    open record without one - newest first, at most `limit` and a count of the
    rest: what each slice owns, where it works and its last commit. A pull
    read: siblings see each other's leases here instead of by message."""
    recs = [r for r in pending(root) if r.get("status") == "open"
            and r.get("kind") != "job" and (parent is None or r.get("parent") == parent)]
    out = []
    for rec in recs[:limit]:
        tree = rec.get("worktree") or ""
        head = _git(tree, "log", "-1", "--format=%h") if tree and os.path.isdir(tree) else None
        out.append(_cut("- %s (%s/%s) owns %s; worktree %s on %s @ %s" % (
            rec.get("name") or rec["id"], rec.get("host") or "?", rec.get("agent") or "?",
            ", ".join(rec.get("owns") or ()) or "nothing declared", tree or "none",
            rec.get("branch") or "?", head or "?")))
    if len(recs) > limit:
        out.append("- %d more open slice(s)" % (len(recs) - limit))
    return out


# An agent whose name reads as a read-only role shares a worktree freely: a
# reviewer panel on one slice's checkout is the allowed case (research
# orchestrator-flow-audit S6, finding 5). A brief with `Owns:` writes whatever
# its agent is called.
_READ_ONLY_AGENT = re.compile(r"review|explor|research|scout|audit|critic|judge", re.I)
SHARED_WORKTREE = (
    "tezgah: writing slices %s all name worktree %s. Every writing slice gets its own "
    "branch and checkout (`orca worktree create` inside Orca, else `git worktree "
    "add`): two slices in one checkout overwrite each other's edits.")


def _writing(agent, owns):
    return bool(owns) or not _READ_ONLY_AGENT.search(agent or "")


def _writes(rec):
    """A writing record: its own task's `Owns:`, else an agent not named for a
    read-only role. A reviewer whose lease came from a shared brief is not one."""
    return _writing(rec.get("agent"), owned_globs(rec.get("task") or ""))


def worktree_clash(root, tool, inp, parent=""):
    """SHARED_WORKTREE when two writing slices - of this spawn call, or this
    call and an open record `parent` spawned - name one worktree, else None.
    Each task's own text decides its worktree; one that names none takes the
    shared context's, which is how ten slices landed in one checkout."""
    main = _journal_root(root)
    seen = {}
    for rec in slices(root):
        if parent and rec.get("parent") == parent and rec.get("status") == "open" \
                and rec.get("worktree") and _writes(rec):
            seen.setdefault(rec["worktree"], set()).add(rec.get("name") or rec["id"])
    context = str(inp.get("context") or "").strip() if isinstance(inp, dict) else ""
    for sid, agent, brief in spawned(tool, inp):
        task = brief[len(context):] if context else brief
        tree = _worktree_in(main, task, brief)
        if tree and _writing(agent, owned_globs(task)):
            seen.setdefault(tree, set()).add(sid)
    clash = sorted((t, sorted(n)) for t, n in seen.items() if len(n) > 1)
    return SHARED_WORKTREE % (", ".join(clash[0][1]), clash[0][0]) if clash else None


# `plan 093` in a brief: the plan a slice works on when its checkout says none
_BRIEF_PLAN = re.compile(r"(?i)\bplan\s+(\d{3})\b")


def open_slice(root, sid, *, kind="agent", host="", agent="", brief="", parent="",
               cwd="", repo="", task="", child=""):
    """Open (or re-open) the record `sid` and return it. The worktree and branch
    are the ones the slice's own task names (else the brief, `_worktree_in`);
    `declared` is the worktree a `Worktree:`/`Checkout`/`Cwd:` line declares
    (`_declared_in`); the base is the main checkout's HEAD, and `owns` holds the
    `Owns:` globs of the task (else the brief, `owned_globs`). A re-open
    of an existing id counts one more attempt, sets the status back to open and
    clears the failure; a field the new call leaves empty keeps its old value.
    A record another session holds under another brief is not re-opened: the
    spawn gets its own id (`_own_id`), and `name` keeps the spawned name.
    `repo` names the repository the slice works in when that is not this
    journal's (`_brief_repo`); `child` is the host's id for the running child
    (Claude's background `agentId`), the key its own writes carry."""
    base = slice_id(sid, brief)
    main = _journal_root(root)
    own = task or brief or ""
    brief = (brief or "")[:SLICE_BRIEF]
    now = _now()
    sid = _own_id(root, base, brief, parent)
    rec = _read_record(root, sid)
    if rec is None:
        rec = {"id": sid, "name": base, "kind": kind if kind in SLICE_KINDS else "agent",
               "host": host, "agent": agent, "brief": brief, "parent": parent,
               "cwd": cwd, "repo": repo, "worktree": "", "branch": "", "attempts": 1,
               "opened": now, "child": child}
    else:
        rec["attempts"] = int(rec.get("attempts") or 0) + 1
        if parent and parent != rec.get("parent"):
            # a re-dispatch from another session (after a /clear, a crash, a
            # resume) writes its child under that session's directory: the old
            # one holds the first run, whose end must not close this record
            rec["transcript_dir"] = ""
        for key, value in (("host", host), ("agent", agent), ("brief", brief),
                           ("parent", parent), ("cwd", cwd), ("repo", repo),
                           ("child", child)):
            if value:
                rec[key] = value
    if task:  # the slice's own task, without a batch's shared context
        rec["task"] = task[:SLICE_BRIEF]
    if brief or not rec.get("worktree"):
        rec["worktree"], rec["branch"] = _named_worktree(main, task, rec.get("brief"))
        rec["declared"] = _declared_in(main, task, rec.get("brief"))
    if own:
        rec["owns"] = owned_globs(own, (rec["worktree"], main))
    if rec.get("host") == "omp" and rec.get("parent") and not rec.get("transcript_dir"):
        # one glob over every omp project at open, so `pending` - run on every
        # prompt and Stop - never globs (40 ms on 1393 project dirs, measured)
        rec["transcript_dir"] = _omp_session_dir(rec["parent"]) or ""
    # the slice's own plan: the review guard reads its own plan's records only.
    # Its worktree's plan branch, else the plan its brief names, else the task
    # the main checkout reads - with two plans running that is only one of them
    named = _BRIEF_PLAN.search(own)
    rec["plan"] = (plan_of_branch(rec.get("branch")) or (named and named.group(1))
                   or (active(main, main) or {}).get("id") or rec.get("plan") or "")
    rec.update(base=_git(main, "rev-parse", "HEAD") or "", status="open",
               failure="", updated=now)
    return _write_record(root, rec)


def close_slice(root, sid, status, failure="", stop=None):
    """Close the record `sid` as done, stopped or resumed; None when it has none.
    A stopped record takes `failure` (a FAILURES class or ""); done and resumed
    keep the class the slice stopped with, so the stats still count the event.
    A quota or rate-limit stop whose message `stop` ({errorMessage, provider,
    model, default}) names its family holds that family down
    (`tezgah_models.note_limit`; a rate limit briefly);
    that push fails open."""
    if status not in SLICE_CLOSED:
        raise ValueError("status %r is not one of %s" % (status, ", ".join(SLICE_CLOSED)))
    rec = _read_record(root, sid)
    if rec is None:
        return None
    if status == "stopped" or failure:
        rec["failure"] = failure if failure in FAILURES else ""
    rec.update(status=status, updated=_now())
    if failure in ("quota", "rate_limit") and isinstance(stop, dict):
        try:
            import tezgah_models
            tezgah_models.note_limit(
                stop.get("errorMessage") or "", stop.get("provider") or "",
                stop.get("model") or "", transient=failure == "rate_limit",
                default=stop.get("default") or "")
        except Exception:  # noqa: BLE001 - health is advice: the close still lands
            pass
    return _write_record(root, rec)


def slices(root):
    """Every readable record, newest `updated` first (the later write first on a
    tie); a row that does not parse, or a journal that cannot be opened, is
    skipped - readers fail open."""
    import tezgah_store
    try:
        with _journal(root, create=False) as db:
            rows = db.execute("SELECT row FROM slices ORDER BY updated DESC, "
                              "seq DESC").fetchall() if db else []
    except tezgah_store.ERRORS:
        return []
    return [rec for rec in (_row(r[0]) for r in rows) if rec]


def classify(text):
    """The failure class of an error or result text: rate_limit, quota, aborted,
    timeout, cut_off, else error for any other non-empty text, "" for none."""
    text = str(text or "").strip()
    if not text:
        return ""
    for name, pattern in _CLASSES:
        if pattern.search(text):
            return name
    return "error"


def _brief(*parts):
    return "\n\n".join(str(p).strip() for p in parts if str(p or "").strip())


def spawned(tool, inp):
    """[(id, agent, brief)] for one spawn call's input, [] for any other tool.
    omp `task` carries a batch ({tasks: [{name, agent, task}], context}, brief =
    context + task); Claude, dsh and Cursor `Agent`/`Task` and opencode `task`
    carry one ({description, prompt, subagent_type}); Codex `spawn_agent` carries
    {task_name, message|prompt, agent_type|agent} - its `task_name` is the id the
    user addresses the child by."""
    if not isinstance(inp, dict):
        return []
    name = str(tool or "").lower()
    out = []
    if name == "task" and isinstance(inp.get("tasks"), list):
        context = inp.get("context") or ""
        for item in inp["tasks"]:
            if not isinstance(item, dict):
                continue
            brief = _brief(context, item.get("task") or "")
            out.append((slice_id(item.get("name"), brief), str(item.get("agent") or ""),
                        brief))
    elif name in ("task", "agent"):
        brief = _brief(inp.get("description") or "", inp.get("prompt") or "")
        out.append((slice_id(inp.get("name"), brief),
                    str(inp.get("subagent_type") or ""), brief))
    elif name == "spawn_agent":
        brief = str(inp.get("message") or inp.get("prompt") or "")
        out.append((slice_id(inp.get("task_name") or inp.get("name"), brief),
                    str(inp.get("agent_type") or inp.get("agent") or ""), brief))
    return [row for row in out if row[2]]


def note_spawn(cwd, session_id, host, tool, inp, failed=None, result_text="",
               child=""):
    """Open one record per slice a spawn call started, and return them. A host
    that runs the subagent synchronously (Claude's PostToolUse on Agent/Task)
    passes `failed` as a bool and the record closes at once: stopped with the
    class of `result_text` (error when it names none), else done. No-op ([])
    under `slices-off` or outside a git checkout. The record stays in cwd's
    journal, the one the owner's Stop rule, resume block and review guard
    read, and names the repository its brief works in as `repo`
    (`_brief_repo`) when that is another one. `child` is the id the host
    returned for a background child (Claude's `agentId`)."""
    from tezgah_paths import _toplevel, off
    if off("slices-off") or not cwd:
        return []
    root = _toplevel(os.path.realpath(cwd))
    if not root:
        return []
    here = _journal_root(root)
    out = []
    context = str(inp.get("context") or "").strip() if isinstance(inp, dict) else ""
    for sid, agent, brief in spawned(tool, inp):
        repo = _brief_repo(brief, here)
        rec = open_slice(root, sid, host=host, agent=agent, brief=brief,
                         parent=session_id or "", cwd=cwd,
                         repo="" if repo == here else repo,
                         task=brief[len(context):].strip() if context else brief,
                         child=child)
        if failed is True:
            # a Claude subagent runs on Anthropic unless its model names another
            # vendor; another host's input may name a model
            stop = {"errorMessage": result_text, "model": str(inp.get("model") or ""),
                    "default": "anthropic" if host == "claude" else ""}
            rec = close_slice(root, rec["id"], "stopped",
                              classify(result_text) or "error", stop)
        elif failed is False:
            rec = close_slice(root, rec["id"], "done")
        out.append(rec)
    return out


# An absolute path in a brief: a slash after a space, a quote or a bracket, up
# to the next space, quote, bracket or separator.
_ABS_PATH = re.compile(r"(?<![\w.~/-])/[^\s'\"`<>()\[\]{},;|*?]+")


def main_repo(path):
    """The main checkout of the repository holding `path`, else None. A path
    under a repository's own `.tezgah` - a private git repository of its own -
    belongs to the repository around it, and a worktree to its main checkout."""
    from tezgah_paths import _toplevel
    top = _toplevel(os.path.realpath(path))
    while top and os.path.basename(top) == ".tezgah":
        top = _toplevel(os.path.dirname(top))
    return _journal_root(top) if top else None


def _brief_repo(brief, root):
    """The main checkout of the one armed repository every absolute path the
    brief names lies in, else `root`. A brief naming two repositories, or none,
    keeps `root` (research orchestrator-flow-audit S7, finding 2)."""
    from tezgah_paths import root_for
    found = set()
    for path in _ABS_PATH.findall(brief or ""):
        top = main_repo(path.rstrip(".:"))
        if top and root_for(top):
            found.add(top)
    return found.pop() if len(found) == 1 else root


def _omp_session_dir(parent):
    """The omp session directory of parent session `parent`
    (`~/.omp/agent/sessions/<project>/<stamp>_<parent>/`, one `<agent id>.jsonl`
    per subagent), or None. One glob over every project, so it runs once per
    record (`open_slice`), never per prompt."""
    import glob
    if not parent or "/" in parent or os.sep in parent:
        return None
    home = os.path.expanduser("~")
    hits = glob.glob(os.path.join(home, ".omp", "agent", "sessions", "*",
                                  "*_" + glob.escape(parent)))
    return hits[0] if hits else None


def _omp_transcript(rec):
    """The newest omp child transcript of the record: omp names a re-dispatch of
    the same agent name in one session `<name>-2.jsonl`, `<name>-3.jsonl`, so the
    highest suffix is the attempt the record now tracks - reading `<name>.jsonl`
    would close a re-opened record with the first run's end. None when the
    record names no session directory or the directory holds no such file. The
    file is named by the spawned `name`, which a record's own id may extend."""
    folder, sid = rec.get("transcript_dir"), rec.get("name") or rec.get("id")
    if not folder or not sid:
        return None
    try:
        names = os.listdir(folder)
    except OSError:
        return None
    best, rank = None, -1
    attempt = re.compile(re.escape(sid) + r"(?:-(\d+))?\.jsonl")
    for name in names:
        hit = attempt.fullmatch(name)
        n = int(hit.group(1) or 1) if hit else -1
        if n > rank:
            best, rank = os.path.join(folder, name), n
    return best


def _transcript_end(path):
    """How an omp child transcript ended, read from its last SLICE_TAIL bytes:
    ("stopped", class) for an error, abort or length stop on the last assistant
    message, an error with that message third (`close_slice`'s `stop`);
    ("done", "") once it yielded, stopped normally or exited; None while
    it may still be running or cannot be read."""
    import json
    try:
        with open(path, "rb") as fh:
            fh.seek(0, os.SEEK_END)
            size = fh.tell()
            fh.seek(max(0, size - SLICE_TAIL))
            data = fh.read().decode("utf-8", "replace")
    except OSError:
        return None
    rows = []
    for line in data.splitlines():
        try:
            row = json.loads(line)
        except ValueError:
            continue  # the first line of a cut tail, or a torn last one
        if isinstance(row, dict):
            rows.append(row)
    exited = yielded = False
    for row in reversed(rows):
        if row.get("type") == "custom" and row.get("customType") == "session_exit":
            exited = True
        msg = row.get("message") if isinstance(row.get("message"), dict) else None
        if not msg:
            continue
        if msg.get("role") == "toolResult" and msg.get("toolName") in ("yield",
                                                                         "submit_result"):
            yielded = True
        if msg.get("role") != "assistant":
            continue
        stop = msg.get("stopReason")
        if stop == "error":
            return "stopped", classify(msg.get("errorMessage")) or "error", msg
        if stop == "aborted":
            return "stopped", "aborted"
        if stop == "length":
            return "stopped", "cut_off"
        if yielded or exited or stop == "stop":
            return "done", ""
        return None
    return ("done", "") if yielded or exited else None


# How long a `job` record stays pending: omp clamps a background call's
# deadline to 3600 s, so a job opened longer ago has ended either way and its
# line would only repeat itself on every prompt. Its result stays in the parent
# transcript the record names, so it closes `stale`, not done.
SLICE_JOB_SECONDS = 3600


def _age(rec):
    """Seconds since the record last changed (`updated`, else `opened`), or None
    when neither reads as a record time."""
    import calendar
    import time
    stamp = str(rec.get("updated") or rec.get("opened") or "")
    try:
        then = calendar.timegm(time.strptime(stamp, "%Y-%m-%dT%H:%M:%SZ"))
    except ValueError:
        return None
    return time.time() - then


def pending(root):
    """The records still owed work - status open or stopped - newest first. An
    omp record still open whose child transcript has ended is closed first:
    stopped with its failure class, or done when it ended normally. An open
    record nothing has moved for SLICE_IDLE_SECONDS (an omp child's transcript
    included) - or a `job` past SLICE_JOB_SECONDS - closes `stale`. One stat and
    at most one SLICE_TAIL read per open omp record."""
    out = []
    for rec in slices(root):
        if rec.get("status") != "open":
            if rec.get("status") == "stopped":
                out.append(rec)
            continue
        idle, limit = _age(rec), SLICE_IDLE_SECONDS
        if rec.get("kind") == "job":
            limit = SLICE_JOB_SECONDS
        elif rec.get("host") == "omp":
            if not rec.get("transcript_dir") and idle is not None and idle < 600:
                # the parent's directory did not exist yet when the record
                # opened: one more glob while the record is young, then kept
                found = _omp_session_dir(rec.get("parent"))
                if found:
                    rec["transcript_dir"] = found
                    _write_record(root, rec)
            path = _omp_transcript(rec)
            end = _transcript_end(path) if path else None
            if end:
                rec = close_slice(root, rec["id"], *end) or rec
            elif path:
                try:
                    import time
                    idle = min(idle if idle is not None else 1e18,
                               time.time() - os.stat(path).st_mtime)
                except OSError:
                    pass
        if rec.get("status") == "open" and idle is not None and idle > limit:
            rec = close_slice(root, rec["id"], "stale") or rec
        if rec.get("status") in ("open", "stopped"):
            out.append(rec)
    return out


def _cut(line, keep=""):
    """`line` + `keep` cut to SLICE_LINE characters, the cut taken from `line` so
    `keep` (the command that acts on the record) survives whole."""
    room = SLICE_LINE - len(keep)
    if len(line) > room:
        line = line[:max(0, room - 3)] + "..."
    return (line + keep)[:SLICE_LINE]


def slice_line(rec):
    """One bounded line (SLICE_LINE characters) for one record."""
    sid = rec.get("id") or ""
    status = rec.get("status") or ""
    if rec.get("kind") == "job":
        return _cut("- job %s %s: %s (parent session %s) - read its result there "
                    "before re-running" % (sid, status,
                                           " ".join(str(rec.get("brief") or "").split())[:60],
                                           rec.get("parent") or "?"))
    head = "- slice %s (%s/%s) %s%s attempts %s" % (
        sid, rec.get("host") or "?", rec.get("agent") or "?", status,
        (" " + rec["failure"]) if rec.get("failure") else "", rec.get("attempts") or 1)
    tree = rec.get("worktree") or ""
    if rec.get("repo"):
        head += " (in %s)" % os.path.basename(rec["repo"])
    if tree and os.path.isdir(tree):
        head += " worktree %s @ %s" % (tree, _git(tree, "rev-parse", "--short", "HEAD") or "?")
    return _cut(head, ": tezgah-task slice resume %s" % sid)


def slice_lines(root, limit=3, session=None, others=False):
    """One line per pending record, newest first, at most `limit` of them; with
    `session`, only the records that session spawned (`parent`) or that no
    session owns (one opened by hand with no `--parent`) - another session's
    slices are its own to resume. With `others`, one closing line counts those
    others, so a new session after a crash or a host switch still learns they
    exist (the resume block asks for it, the per-prompt part does not)."""
    recs = pending(root)
    if session is None:
        return [slice_line(rec) for rec in recs[:limit]]
    mine = [r for r in recs if r.get("parent") in (session, "", None)]
    out = [slice_line(rec) for rec in mine[:limit]]
    if others and len(recs) > len(mine):
        out.append("- %d pending slice(s) of other sessions: tezgah-task slice reconcile"
                   % (len(recs) - len(mine)))
    return out
