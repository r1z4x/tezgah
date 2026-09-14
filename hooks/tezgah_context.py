#!/usr/bin/env python3
"""The one place that decides what tezgah injects, independent of the host.

Each host adapter normalizes its own event names and output envelope, then
calls context_for() here; the text is identical on Claude, Codex, Cursor and
opencode because it is built once. Stdlib only.
"""
import glob
import json
import os
import re
import subprocess

from tezgah_policy import CORE, PROMPT_REMINDER
from tezgah_paths import (CACHE, cbm_bin, have_consult_key, off, root_for,
                          roots, tool)

# filled in by context_for() once the cwd is known; {ROOT} reads it
ACTIVE_ROOT = [""]


def render(text, root=""):
    """Fill the path placeholders with stable, existing paths."""
    if not text:
        return text
    return (text.replace("{CONSULT_BIN}", tool("consult"))
                .replace("{CODEGEN_BIN}", tool("codegen"))
                .replace("{ROOT}", root or ACTIVE_ROOT[0]
                         or "the configured tezgah roots"))


def under(path):
    return root_for(path) is not None


def git(root, *args):
    try:
        out = subprocess.run(("git", "-C", root) + args, capture_output=True,
                             text=True, timeout=5)
        return out.stdout.strip() if out.returncode == 0 else ""
    except Exception:
        return ""


def repo_root(cwd):
    """The unit of work: the git top-level under a root, else the first path
    component below the root (so a non-git project still gets one slug)."""
    top = git(cwd, "rev-parse", "--show-toplevel")
    if top and under(top):
        return os.path.realpath(top)
    base = root_for(cwd)
    if not base:
        return os.path.realpath(cwd)
    rel = os.path.relpath(os.path.realpath(cwd), base)
    first = rel.split(os.sep)[0]
    if first in (".", "..", ""):
        return os.path.realpath(cwd)
    return os.path.join(base, first)


def slug(path):
    return re.sub(r"[^A-Za-z0-9]+", "-", path).strip("-")


def autoindex(root):
    """Detached incremental index. Returns a one-line status for the context."""
    if root in roots():
        # a root is not a project: indexing it swallows every repo below into
        # one multi-GB graph. Sessions started there get no auto-index.
        return "not indexed: cwd is a configured tezgah root, cd into a repo"
    if os.path.exists(os.path.join(root, ".no-cbm")):
        return "indexing disabled for this repo (.no-cbm present)"
    cbm = cbm_bin()
    if not cbm:
        return "codebase-memory-mcp is not installed on this machine, so there is no graph"
    name = slug(root)
    head = git(root, "rev-parse", "HEAD") or "nogit"
    stamp_path = os.path.join(CACHE, name)
    try:
        os.makedirs(os.path.join(CACHE, "logs"), exist_ok=True)
        with open(stamp_path) as fh:
            stamped = fh.read().strip()
    except OSError:
        stamped = ""
    if stamped == head and head != "nogit":
        return "index current (HEAD unchanged since last index)"
    try:
        log = open(os.path.join(CACHE, "logs", name + ".log"), "ab")
        # stamp HEAD only after the index exits 0: a failed run (daemon lock,
        # concurrent worktree indexing) is retried on the next session start
        subprocess.Popen(
            ["sh", "-c", '"$0" daemon start >/dev/null 2>&1;'  # warm daemon: idempotent, cuts MCP connect time
             ' "$0" cli index_repository --repo-path "$1" --mode fast'
             ' && printf %s "$2" > "$3"', cbm, root, head, stamp_path],
            stdin=subprocess.DEVNULL, stdout=log, stderr=log,
            start_new_session=True, cwd=root,
        )
    except Exception as exc:
        return "auto-index could not start (%s); run index_repository manually" % exc
    verb = "re-indexing" if stamped else "indexing (first time)"
    return "%s in background now" % verb


def open_plans(root):
    """Max 3 open plans (plans/open/*.md, lowest id first) as a context block, or ""."""
    paths = sorted(glob.glob(os.path.join(root, "plans", "open", "*.md")))
    lines = []
    for path in paths[:3]:
        try:
            with open(path) as fh:
                text = fh.read().splitlines()
        except OSError:
            continue
        pid, title, nxt, fences, in_next = "", "", "", 0, False
        for line in text:
            if line.strip() == "---":
                fences += 1
                continue
            if fences < 2:
                key, _, val = line.partition(":")
                if key.strip() == "id":
                    pid = val.strip()
                elif key.strip() == "title":
                    title = val.strip()
            elif line.startswith("## "):
                in_next = line.strip() == "## Next"
            elif in_next and line.strip() and not nxt:
                nxt = line.strip()[:80]
        lines.append("- %s %s -> %s" % (pid, title, nxt))
    if not lines:
        return ""
    if len(paths) > 3:
        lines.append("(+%d more)" % (len(paths) - 3))
    return ("## Open plans in this repo (plans/open)\n%s\n"
            "Run the plan-status skill for the full table before starting work; "
            "open plan work happens on its `plan/NNN-slug` branch." % "\n".join(lines))


def context_for(event, cwd, payload=None):
    """The context block for a normalized event, or None when out of scope.

    event: session_start | user_prompt | subagent_start | post_compact
    """
    if not under(cwd):
        return None
    root = repo_root(cwd)
    ACTIVE_ROOT[0] = root_for(cwd) or ""
    if event == "user_prompt":
        # per-turn nudge: openers decay over long sessions. Kept short because
        # it is paid every turn, and on Claude the output style already carries
        # the same rules on every response.
        if off("reminder-off"):
            return None
        return render(PROMPT_REMINDER.strip())
    # session_start / post_compact / subagent_start: the compact always-on core
    # plus live index/consult state. The deep orchestration/exec detail moved
    # out of the every-session payload into the tezgah-contract skill, which
    # the last line tells the model to load on demand.
    parts = [CORE]
    if cbm_bin():
        # SubagentStart fires once per delegated agent: a fan-out would race
        # indexers on the same repo, so only the parent session triggers one.
        status = (autoindex(root) if event != "subagent_start"
                  else "index handled by the parent session")
        parts.append("Graph index: %s (project %s)." % (status, slug(root)))
    else:
        parts.append("Graph: codebase-memory-mcp is not installed, so use "
                     "grep/find and say the answer came from text search; never "
                     "claim the index answered.")
    if not off("consult-off") and not have_consult_key():
        parts.append("Consult: no OpenRouter key, so the second opinion cannot "
                     "run; on a non-trivial call say it was skipped and why.")
    if event in ("session_start", "post_compact"):
        plans = open_plans(root)
        if plans:
            parts.append(plans)
    if event == "subagent_start":
        parts.append("You are a subagent: execute the briefing and report "
                     "evidence back to the router; do not orchestrate or spawn "
                     "subagents. Full rules: the `tezgah-contract` skill.")
    else:
        parts.append("Deep orchestration, codegen, consult detail and the exact "
                     "kill switches: load the `tezgah-contract` skill.")
    return render("\n\n".join(p.strip() for p in parts))


def record(session_id, kind):
    """Append a used-tool kind for the status line (any host, best effort)."""
    if not session_id:
        return
    try:
        d = os.path.join(CACHE, "sessions")
        os.makedirs(d, exist_ok=True)
        with open(os.path.join(d, slug(session_id) + ".jsonl"), "a") as fh:
            fh.write(json.dumps({"kind": kind}) + "\n")
    except OSError:
        pass


def used(session_id):
    if not session_id:
        return set()
    out = set()
    try:
        with open(os.path.join(CACHE, "sessions", slug(session_id) + ".jsonl")) as fh:
            for line in fh:
                try:
                    out.add(json.loads(line)["kind"])
                except (ValueError, KeyError):
                    pass
    except OSError:
        pass
    return out


def repo_marks(cwd):
    """The per-repo opt-out flags (.no-ponytail/.no-cbm) walking up to the
    enclosing root, and that root. Outside every root: empty set, root None."""
    marks = set()
    base = root_for(cwd)
    p = os.path.realpath(cwd)
    while base and p.startswith(base):
        for f in (".no-ponytail", ".no-cbm"):
            if os.path.exists(os.path.join(p, f)):
                marks.add(f)
        if p == base:
            break
        p = os.path.dirname(p)
    return base, marks


def index_mark(cwd, base):
    """Code-graph readiness for the enclosing repo.

    ✓ indexed, ↻ indexed but HEAD moved since the stamp, ✗ not indexed yet,
    – not applicable (outside a root, codebase-memory-mcp absent, or .no-cbm)."""
    if not base or not cbm_bin():
        return "–"
    p = os.path.realpath(cwd)
    while p.startswith(base):
        if os.path.exists(os.path.join(p, ".no-cbm")):
            return "–"
        if p == base:
            break
        p = os.path.dirname(p)
    from tezgah_gate import index_slug  # lazy: keep hook import cost minimal
    slug = index_slug(cwd, base)
    if not slug:
        return "✗"
    try:
        head = git(repo_root(cwd), "rev-parse", "HEAD")
        with open(os.path.join(CACHE, slug)) as fh:
            stamped = fh.read().strip()
        if head and stamped and stamped != head:
            return "↻"
    except OSError:
        pass
    return "✓"


def plan_mark(cwd, base):
    """`plans N` (+ `(M blk)`) for the enclosing repo, or None."""
    if not base:
        return None
    p = os.path.realpath(cwd)
    while p.startswith(base):
        plans = glob.glob(os.path.join(p, "plans", "open", "*.md"))
        if plans:
            blocked = 0
            for f in plans:
                try:
                    with open(f) as fh:
                        blocked += "status: blocked" in fh.read(400)
                except OSError:
                    pass
            return "plans %d" % len(plans) + (" (%d blk)" % blocked if blocked else "")
        if p == base:
            break
        p = os.path.dirname(p)
    return None


def health_lines(cwd, session_id=None, used_override=None):
    """The armed/used checklist, host-neutral, for `tezgah-status`.

    The single source every host renders (opencode TUI, Codex systemMessage,
    Claude/Cursor statusline), so they cannot drift.

    Global, not root-scoped: tezgah ships as a globally loaded instructions
    file on opencode (and the CLI is used outside repos), so the indicator must
    not go silent off-root. The per-repo additions - the .no-* marks, `idx` graph
    readiness and the `plans` count - appear only when cwd is inside a root.

    used_override: the tool kinds a host already resolved from its own record
    (e.g. Claude parses the transcript because it does not write tezgah's
    recorder); None falls back to tezgah's recorder for session_id."""
    base, marks = repo_marks(cwd)
    seen = set(used_override) if used_override is not None else used(session_id)
    flags = [
        ("pony", not off("ponytail-auto.off") and ".no-ponytail" not in marks, None),
        ("exec", not off("exec-mode.off"), None),
        ("consult", not off("consult-off") and have_consult_key(), "consult"),
        ("cbm", ".no-cbm" not in marks, "cbm"),
        ("orch", not off("orchestrate-off"), "orch"),
    ]
    out = []
    for name, on, meas in flags:
        if not on:
            out.append(name + "✗")
        elif meas is None or meas in seen:
            out.append(name + "✓")
        else:
            out.append(name + "○")
    line = " ".join(out[:2]) + "  ·  " + " ".join(out[2:])
    extra = []
    if base:
        extra.append("idx" + index_mark(cwd, base))
        plan = plan_mark(cwd, base)
        if plan:
            extra.append(plan)
    if extra:
        line += "  ·  " + "  ·  ".join(extra)
    return line
