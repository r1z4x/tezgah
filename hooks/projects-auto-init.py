#!/usr/bin/env python3
"""Claude Code hook: SessionStart, UserPromptSubmit, SubagentStart, PostCompact.

Emits the shared tezgah context (hooks/tezgah_context.py) for the session's
cwd when it resolves inside a configured root, and prints nothing outside them.
This file is only the Claude envelope; the contract itself lives in the core so
Codex, Cursor, opencode, dsh and omp inject the exact same text.
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from tezgah_context import context_for  # noqa: E402

EVENTS = {
    "SessionStart": "session_start",
    "UserPromptSubmit": "user_prompt",
    "SubagentStart": "subagent_start",
    "PostCompact": "post_compact",
}


def main():
    try:
        payload = json.load(sys.stdin)
    except Exception:
        payload = {}
    event = payload.get("hook_event_name") or "SessionStart"
    cwd = payload.get("cwd") or os.environ.get("CLAUDE_PROJECT_DIR") or os.getcwd()
    text = context_for(EVENTS.get(event, "session_start"), cwd, payload)
    if text:
        json.dump({"hookSpecificOutput": {
            "hookEventName": event,
            "additionalContext": text,
        }}, sys.stdout)
    sys.exit(0)


main()
