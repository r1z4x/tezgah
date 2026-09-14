#!/usr/bin/env python3
"""Codex lifecycle hook. Reads Codex's JSON on stdin, prints the shared tezgah
context (hooks/tezgah_context.py) in Codex's hookSpecificOutput envelope.

Codex fires SessionStart, UserPromptSubmit, PostToolUse, SubagentStart and
PostCompact; anything else is ignored. Inert outside the configured roots.
PostToolUse only records what was used (for `tezgah-status`); it injects nothing.
"""
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(ROOT, "hooks"))
from tezgah_context import context_for, record  # noqa: E402

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
    if name in ("Task", "Agent", "task"):
        return "orch"
    if name in ("Bash", "shell", "Shell"):
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
    normalized = EVENTS.get(event)
    if not normalized:
        return
    text = context_for(normalized, cwd, payload)
    if text:
        print(json.dumps({"hookSpecificOutput": {
            "hookEventName": event,
            "additionalContext": text,
        }}))


main()
