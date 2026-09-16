#!/usr/bin/env python3
"""Claude Code PostToolUse / PostToolUseFailure hook: record evidence.

The Stop hook decides whether a "done/tested" turn is allowed to end by looking
at what actually ran, and that record has to be written here, from the tool
result, not from the reply. Inert outside a tezgah root.
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.realpath(__file__)))
from tezgah_integrity import note_tool  # noqa: E402
from tezgah_paths import root_for  # noqa: E402


def main():
    try:
        p = json.load(sys.stdin)
    except Exception:
        return
    if not isinstance(p, dict):
        return
    cwd = p.get("cwd") or os.getcwd()
    if not root_for(cwd):
        return
    note_tool(p.get("session_id"), p.get("tool_name", ""),
              p.get("tool_input") or {},
              failed=p.get("hook_event_name") == "PostToolUseFailure")


main()
