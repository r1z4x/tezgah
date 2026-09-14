#!/usr/bin/env python3
"""PreToolUse hook (matcher Agent|Task|Grep|Bash), inert outside the tezgah roots.
1. Deny `subagent_type: Explore` — Explore greps by design and ignores the
   code graph; the reason names the replacement (general-purpose + graph tools).
2. Nudge once per session: the FIRST identifier-shaped search — the Grep tool
   OR a grep/rg inside a Bash command, which is how search actually happens in
   bypass-permissions mode — in a repo whose codebase-memory index exists, is
   denied with a pointer to search_graph / trace_path. Later searches pass.
Kill switch: ~/.claude/pretooluse-off.
"""
import json
import os
import re
import sys

from tezgah_paths import root_for  # same directory as this file

HOME = os.path.expanduser("~")
DB_DIR = os.path.join(HOME, ".cache", "codebase-memory-mcp")
NUDGED = os.path.join(HOME, ".cache", "cbm-autoindex", "nudged")
IDENT = re.compile(r"^[A-Za-z_][A-Za-z0-9_]{2,}$")
# ponytail: flags with a separate value (grep -A 3 foo) shift the token and the
# search passes unnudged; not worth a real argv parser for a once-a-session hint.
BASH_SEARCH = re.compile(r"(?:^|[|;&(]\s*|\s)(?:grep|rg)\s+((?:-\S+\s+)*)(\S+)")


def searched_identifier(tool, inp):
    """The bare identifier this call searches for, or None."""
    if tool == "Grep":
        pat = str(inp.get("pattern", ""))
        return pat if IDENT.match(pat) else None
    if tool == "Bash":
        for m in BASH_SEARCH.finditer(str(inp.get("command", ""))):
            tok = m.group(2).strip("'\"")
            if IDENT.match(tok):
                return tok
    return None


def deny(reason):
    json.dump({"hookSpecificOutput": {
        "hookEventName": "PreToolUse",
        "permissionDecision": "deny",
        "permissionDecisionReason": reason,
    }}, sys.stdout)
    sys.exit(0)


def main():
    if os.path.exists(os.path.join(HOME, ".claude", "pretooluse-off")):
        return
    try:
        p = json.load(sys.stdin)
    except Exception:
        return
    cwd = os.path.realpath(p.get("cwd") or os.getcwd())
    base = root_for(cwd)
    if not base:
        return
    tool = p.get("tool_name", "")
    inp = p.get("tool_input") or {}

    if tool in ("Agent", "Task") and inp.get("subagent_type") == "Explore":
        deny("Explore is not allowed in this tree: it greps by design and ignores the "
             "code graph. Use subagent_type=general-purpose and name the exact "
             "mcp__codebase-memory-mcp__ tools (search_graph, trace_path, search_code) in its prompt, "
             "with the ToolSearch select: line to load them.")

    if searched_identifier(tool, inp):
        # index exists for the enclosing repo? (DB file named after the path slug)
        d = cwd
        slug = None
        while d.startswith(base) and d != base:
            s = re.sub(r"[^A-Za-z0-9]+", "-", d).strip("-")
            if os.path.exists(os.path.join(DB_DIR, s + ".db")):
                slug = s
                break
            d = os.path.dirname(d)
        if not slug:
            return
        sid = p.get("session_id") or "nosession"
        mark = os.path.join(NUDGED, sid)
        if os.path.exists(mark):
            return
        try:
            os.makedirs(NUDGED, exist_ok=True)
            open(mark, "w").close()  # consume the nudge BEFORE denying: later Greps pass
        except OSError:
            return
        deny("Code graph index is ready for this repo (%s). For a definition, its callers or "
             "blast radius use mcp__codebase-memory-mcp__search_graph / trace_path (load via "
             "ToolSearch select:... first). If you need literal text, re-run this search unchanged; "
             "it will pass — this nudge fires once per session." % slug)


main()
