#!/usr/bin/env python3
"""Status line segment for every host that supports one.

  python3 statusline.py            # Claude Code (or any Claude-format status line)
  python3 statusline.py --cursor   # Cursor CLI (same stdin shape, no Orca passthrough)

Claude Code's statusLine pipes session JSON on stdin; Cursor's spec is aligned
with it. This wraps Orca's own status line for Claude, then appends the tezgah
checklist from hooks/tezgah_context.health_lines - the single source every host
renders - so the segment is identical on Claude, Cursor, Codex and opencode.
Used-tool marks come from the Claude transcript on Claude, and from tezgah's own
recorder (written by the Codex/Cursor/dsh/opencode adapters) elsewhere.
"""
import glob
import json
import os
import subprocess
import sys

# installed as a ~/.claude/statusline.py (or ~/.cursor) symlink, so resolve the
# real file to find the plugin it ships with before importing the shared core
sys.path.insert(0, os.path.join(
    os.path.dirname(os.path.realpath(__file__)), "hooks"))
from tezgah_context import (LEGEND, health_segments, render_line,
                            used as used_kinds)  # noqa: E402

HOME = os.path.expanduser("~")
ORCA = os.path.join(HOME, ".orca", "agent-hooks", "claude-statusline.sh")
HOST = "cursor" if ("--cursor" in sys.argv or
                    os.environ.get("TEZGAH_STATUS_HOST") == "cursor") else "claude"

data = sys.stdin.read()
try:
    payload = json.loads(data or "{}")
except Exception:
    payload = {}

orca_out = ""
if HOST == "claude" and os.access(ORCA, os.X_OK):
    try:
        orca_out = subprocess.run(
            ["/bin/sh", ORCA], input=data, capture_output=True,
            text=True, timeout=5,
        ).stdout.strip()
    except Exception:
        orca_out = ""

cwd = ((payload.get("workspace") or {}).get("current_dir")
       or payload.get("cwd") or "")
try:
    real = os.path.realpath(cwd) if cwd else ""
except OSError:
    real = ""


def claude_used():
    """Tool kinds used this session, parsed from the Claude transcript.

    A substring scan would flag the tool NAME appearing in chat text, so parse
    tool_use blocks; subagent transcripts are included so delegated graph/consult
    use still counts.
    """
    used = set()
    tp = payload.get("transcript_path")
    files = [tp] if tp and os.path.exists(tp) else []
    if tp:
        files += glob.glob(os.path.splitext(tp)[0] + "/subagents/**/*.jsonl",
                           recursive=True)
    lines = []
    for fp in files:
        try:
            size = os.path.getsize(fp)
            with open(fp, encoding="utf-8", errors="ignore") as fh:
                if size > 2_000_000:
                    fh.seek(size - 2_000_000)
                lines += fh.read().splitlines()
        except OSError:
            pass
    for line in lines:
        try:
            content = (json.loads(line).get("message") or {}).get("content")
        except Exception:
            continue  # partial first line after seek, or non-message row
        if not isinstance(content, list):
            continue
        for b in content:
            if not isinstance(b, dict) or b.get("type") != "tool_use":
                continue
            name = b.get("name", "")
            if name.startswith("mcp__codebase-memory-mcp__"):
                used.add("cbm")
            elif name in ("Task", "Agent"):
                used.add("orch")
            elif name == "Bash" and "consult" in \
                    (b.get("input") or {}).get("command", ""):
                used.add("consult")
    return used


seen = used_kinds(payload.get("session_id")) if HOST == "cursor" else claude_used()
segs = health_segments(real or os.getcwd(), payload.get("session_id"),
                       used_override=seen)
# Claude Code and Cursor render ANSI; let a user or a plain terminal opt out.
color = (os.environ.get("NO_COLOR") is None
         and os.environ.get("TEZGAH_STATUS_COLOR") != "0")
seg = render_line(segs, color=color)
parts = [p for p in (orca_out, seg) if p]
out = "  |  ".join(parts)
if os.environ.get("TEZGAH_STATUS_LEGEND") == "1":
    out += "\n" + LEGEND.rstrip()
print(out)
