#!/usr/bin/env python3
"""Claude Code PreToolUse hook (matcher Agent|Task|Grep|Bash), inert outside roots.

Claude's envelope around the shared gate (hooks/tezgah_gate.py): refuse the
grep-only explorer subagent, and nudge the first code-symbol search of a
session toward the code graph. Later symbol searches pass with the graph named
beside them (`additionalContext`, which Claude reads with the tool result).
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.realpath(__file__)))
from tezgah_guard import import_failed, safe  # noqa: E402
try:
    from tezgah_gate import decision, graph_advice  # noqa: E402
except Exception as exc:
    import_failed(exc)


def verdict(tool, inp, cwd, session_id, agent):
    """(deny reason, graph line): the line only for a call the gate lets through."""
    reason = decision(tool, inp, cwd, session_id, agent=agent)
    return reason, None if reason else graph_advice(tool, inp, cwd, "claude")


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
    reason, advice = safe(p.get("session_id"), verdict, tool, inp, cwd,
                          p.get("session_id"), p.get("agent_id")) or (None, None)
    if reason:
        json.dump({"hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": reason,
        }}, sys.stdout)
    elif advice:
        json.dump({"hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "additionalContext": advice,
        }}, sys.stdout)


main()
