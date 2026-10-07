#!/usr/bin/env python3
"""Claude Code PreToolUse hook (matcher Agent|Task|Grep|Bash), inert outside roots.

Claude's envelope around the shared gate (hooks/tezgah_gate.py): refuse the
grep-only explorer subagent, and nudge the first identifier-shaped search of a
session toward the code graph. Later searches pass.
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.realpath(__file__)))
from tezgah_guard import import_failed, safe  # noqa: E402
try:
    from tezgah_gate import decision  # noqa: E402
except Exception as exc:
    import_failed(exc)


def main():
    try:
        p = json.load(sys.stdin)
    except Exception:
        return
    cwd = os.path.realpath(p.get("cwd") or os.getcwd())
    tool = p.get("tool_name", "")
    inp = p.get("tool_input") or {}
    # `agent_id` is set only when the call comes from a subagent (Claude's hook
    # reference, common input fields): the repeat ceilings key on it
    reason = safe(p.get("session_id"), decision, tool, inp, cwd,
                  p.get("session_id"), agent=p.get("agent_id"))
    if reason:
        json.dump({"hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": reason,
        }}, sys.stdout)


main()
