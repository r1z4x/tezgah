#!/usr/bin/env python3
"""Cursor lifecycle hook. Cursor uses its own event names and output schemas,
so this adapter translates them onto the shared tezgah core:

  sessionStart        -> {"additional_context": <shared context>}
  postToolUse/Failure -> record usage, inject nothing
  preToolUse          -> {"permission": "allow"|"deny", "agent_message": ...}
                         (grep-only explorer + first identifier grep nudge)
  subagentStart       -> deny a grep-only explorer
  beforeSubmitPrompt  -> {"continue": true}
Everything else answers "{}" and never blocks.
"""
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(ROOT, "hooks"))
from tezgah_context import context_for, record  # noqa: E402
from tezgah_gate import decision, explored  # noqa: E402

ALLOW = {"permission": "allow"}


def cwd_of(payload):
    return (payload.get("cwd") or (payload.get("workspace_roots") or [None])[0]
            or os.getcwd())


def classify(payload):
    name = payload.get("tool_name", "") or ""
    blob = name + " " + json.dumps(payload.get("tool_input") or {})
    if any(k in blob for k in ("search_graph", "trace_path", "search_code",
                               "get_architecture", "detect_changes",
                               "codebase-memory", "codebase_memory")):
        return "cbm"
    if name in ("Task", "task"):
        return "orch"
    if name in ("Shell", "Bash", "shell", "bash") and "consult" in blob:
        return "consult"
    return None


def main():
    try:
        payload = json.load(sys.stdin)
    except Exception:
        payload = {}
    if not isinstance(payload, dict):
        payload = {}
    event = payload.get("hook_event_name", "")
    cwd = cwd_of(payload)
    session_id = payload.get("conversation_id")

    if event == "sessionStart":
        text = context_for("session_start", cwd, payload)
        out = {"additional_context": text} if text else {}
    elif event in ("postToolUse", "postToolUseFailure", "afterShellExecution",
                   "afterMCPExecution", "afterFileEdit"):
        record(session_id, classify(payload))
        out = {}
    elif event == "subagentStart":
        if explored(payload.get("subagent_type")):
            out = {"permission": "deny", "user_message": "grep-only explorer blocked; use general-purpose with the code graph tools"}
        else:
            record(session_id, "orch")
            out = {"permission": "allow"}
    elif event == "preToolUse":
        tool = payload.get("tool_name", "")
        gate_tool = {"Shell": "Bash", "Read": "Read", "Grep": "Grep"}.get(tool, tool)
        inp = payload.get("tool_input") or {}
        reason = decision(gate_tool, inp, cwd, session_id)
        out = ({"permission": "deny", "agent_message": reason}
               if reason else dict(ALLOW))
    elif event == "beforeSubmitPrompt":
        out = {"continue": True}
    else:
        out = {}
    print(json.dumps(out))


main()
