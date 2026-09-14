#!/usr/bin/env python3
"""Codex lifecycle hook. Reads Codex's JSON on stdin and emits the shared tezgah
context (hooks/tezgah_context.py) plus, where Codex shows it, the tezgah status
segment as `systemMessage`.

Codex fires SessionStart, UserPromptSubmit, PostToolUse, SubagentStart,
PostCompact and Stop; anything else is ignored. Inert outside the roots.

Codex cannot put a custom item in its TUI footer (`tui.status_line` is a closed
built-in enum), so the status segment rides `systemMessage`, which Codex
surfaces in the UI: once at SessionStart and once per turn at Stop. PostToolUse
only records what was used.
"""
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(ROOT, "hooks"))
from tezgah_context import context_for, health_lines, record  # noqa: E402

EVENTS = {
    "SessionStart": "session_start",
    "UserPromptSubmit": "user_prompt",
    "SubagentStart": "subagent_start",
    "PostCompact": "post_compact",
}


def classify(payload):
    """The used-tool kind for a PostToolUse payload, or None."""
    name = payload.get("tool_name", "") or ""
    if name.startswith(("mcp__codebase-memory-mcp__", "mcp__codebase_memory_mcp__")):
        return "cbm"
    if name in ("Task", "Agent", "task", "spawn_agent"):
        return "orch"
    if name in ("Bash", "shell", "Shell", "exec_command"):
        cmd = json.dumps(payload.get("tool_input") or {})
        if "consult" in cmd:
            return "consult"
    return None


def main():
    try:
        payload = json.load(sys.stdin)
    except Exception:
        return
    if not isinstance(payload, dict):
        return
    event = payload.get("hook_event_name") or "SessionStart"
    cwd = payload.get("cwd") or os.getcwd()
    session_id = payload.get("session_id")

    if event == "PostToolUse":
        record(session_id, classify(payload))
        return
    if event == "SubagentStart":
        record(session_id, "orch")
    if event == "Stop":
        seg = health_lines(cwd, session_id)
        if seg:
            print(json.dumps({"systemMessage": "tezgah  " + seg}))
        return
    normalized = EVENTS.get(event)
    if not normalized:
        return
    text = context_for(normalized, cwd, payload)
    out = {}
    if text:
        out["hookSpecificOutput"] = {"hookEventName": event, "additionalContext": text}
    if event == "SessionStart":
        seg = health_lines(cwd, session_id)
        if seg:
            out["systemMessage"] = "tezgah  " + seg
    if out:
        print(json.dumps(out))


main()
