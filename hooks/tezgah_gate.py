#!/usr/bin/env python3
"""The tool gate, shared by every host that can block a tool call.

Two rules, both only inside a tezgah root:
  1. a grep-only explorer subagent is refused, with the graph tools named as the
     replacement;
  2. the FIRST identifier-shaped search of a session (Grep tool, or grep/rg run
     through a shell) in a repo whose codebase-memory index exists is nudged
     toward the graph once, then every later search passes.
  3. a git/gh command that writes an artifact carrying an AI/model credit
     (Co-Authored-By, "Generated with", a robot emoji, ...) is refused.
Adapters translate the returned reason into their own permission envelope.
"""
import os
import re

from tezgah_paths import CACHE, off, root_for

DB_DIR = os.path.join(os.path.expanduser("~"), ".cache", "codebase-memory-mcp")
NUDGED = os.path.join(CACHE, "nudged")
IDENT = re.compile(r"^[A-Za-z_][A-Za-z0-9_]{2,}$")
# ponytail: flags with a separate value (grep -A 3 foo) shift the token and the
# search passes unnudged; not worth a real argv parser for a once-a-session hint.
BASH_SEARCH = re.compile(r"(?:^|[|;&(]\s*|\s)(?:grep|rg)\s+((?:-\S+\s+)*)(\S+)")
# the credit forms, not a bare tool name: "OpenAI" in a sentence is fine,
# "Co-Authored-By: ..." or "Generated with ..." is the thing to stop
ATTRIB = re.compile(
    r"co-authored-by\s*:|generated with|made with|built by|assisted by|"
    r"authored by|noreply@anthropic|claude code|\U0001F916", re.I)
WRITE_CMD = re.compile(
    r"(?:^|[|;&]\s*|\s)git\s+(?:commit|merge|tag|notes)\b|"
    r"(?:^|[|;&]\s*|\s)gh\s+(?:pr|issue|release)\s+(?:create|edit|comment|review)\b",
    re.I)

EXPLORE_DENY = (
    "A grep-only explorer subagent is not allowed in this tree: it greps by "
    "design and ignores the code graph. Use the general-purpose agent and name "
    "the exact codebase-memory-mcp tools (search_graph, trace_path, "
    "search_code) in its prompt, with the tool-loading step so they are armed.")

ATTRIB_DENY = (
    "Attribution is banned in every artifact tezgah touches. Remove the "
    "Co-Authored-By / \"Generated with\" / robot-emoji / model-name credit from "
    "the commit, PR, issue or review text and re-run. Naming a tool in order to "
    "use it or describe real behavior is fine; crediting it as author is not.")


def attribution(command):
    """True when a git/gh write command carries an AI/model credit."""
    c = str(command or "")
    return bool(WRITE_CMD.search(c) and ATTRIB.search(c))


def explored(subagent_type):
    """True when a subagent request is the grep-only explorer."""
    return str(subagent_type or "").lower() in ("explore", "explorer")


def searched_identifier(tool, inp):
    """The bare identifier this call searches for, or None. Host tool names
    differ in case (Claude `Grep`/`Bash`, Codex/dsh `bash`), so match lowercased."""
    t = str(tool or "").lower()
    if t == "grep":
        pat = str(inp.get("pattern", ""))
        return pat if IDENT.match(pat) else None
    if t in ("bash", "shell"):
        for m in BASH_SEARCH.finditer(str(inp.get("command", ""))):
            tok = m.group(2).strip("'\"")
            if IDENT.match(tok):
                return tok
    return None


def index_slug(cwd, base):
    """The codebase-memory db slug for the enclosing repo, if an index exists."""
    d = os.path.realpath(cwd)
    base = os.path.realpath(base)
    while d.startswith(base) and d != base:
        s = re.sub(r"[^A-Za-z0-9]+", "-", d).strip("-")
        if os.path.exists(os.path.join(DB_DIR, s + ".db")):
            return s
        d = os.path.dirname(d)
    return None


def first_nudge(session_id):
    """Consume the once-per-session nudge. False when already spent/unwritable."""
    mark = os.path.join(NUDGED, session_id or "nosession")
    if os.path.exists(mark):
        return False
    try:
        os.makedirs(NUDGED, exist_ok=True)
        open(mark, "w").close()  # consume BEFORE denying: later greps pass
        return True
    except OSError:
        return False


def nudge_reason(slug):
    return ("Code graph index is ready for this repo (%s). For a definition, its "
            "callers or blast radius use the codebase-memory-mcp search_graph / "
            "trace_path tools (load them first). If you need literal text, re-run "
            "this search unchanged; it will pass - this nudge fires once per "
            "session." % slug)


def decision(tool, inp, cwd, session_id=None):
    """A deny reason for this call, or None to let it pass."""
    if off("pretooluse-off"):
        return None
    base = root_for(cwd)
    if not base:
        return None
    t = str(tool or "").lower()
    sub = inp.get("subagent_type") or (inp.get("args") or {}).get("subagent_type")
    if t in ("agent", "task", "subagent") and explored(sub):
        return EXPLORE_DENY
    if t in ("bash", "shell") and attribution(inp.get("command")):
        return ATTRIB_DENY
    if searched_identifier(tool, inp):
        slug = index_slug(cwd, base)
        if slug and first_nudge(session_id):
            return nudge_reason(slug)
    return None
