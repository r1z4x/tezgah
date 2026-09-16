#!/usr/bin/env python3
"""Cursor lifecycle hook. Cursor uses its own event names and output schemas,
so this adapter translates them onto the shared tezgah core:

  sessionStart        -> {"additional_context": <shared context>}
  preToolUse          -> {"permission": "allow"|"deny", "agent_message": ...}
                         (grep-only explorer + first identifier grep nudge)
  beforeMCPExecution  -> {"permission": "allow"} for the code graph, else {}
  subagentStart       -> deny a grep-only explorer
  subagentStop        -> record orch, no followup
  postToolUse         -> record usage; reinforce once per session on graph/consult
  postToolUseFailure  -> record usage; one-line recovery hint
  after*Execution/Edit-> record usage, no output (observers)
  beforeSubmitPrompt  -> {"continue": true}
Everything else answers "{}" and never blocks.
"""
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(ROOT, "hooks"))
from tezgah_context import context_for, record, slug, under  # noqa: E402
from tezgah_gate import decision, explored  # noqa: E402
from tezgah_integrity import note, note_tool  # noqa: E402
from tezgah_paths import cache_dir, off  # noqa: E402

ALLOW = {"permission": "allow"}
GRAPH = ("search_graph", "trace_path", "search_code", "get_architecture",
         "detect_changes", "codebase-memory", "codebase_memory")

REINFORCE = ("tezgah contract active: keep using the code graph "
             "(search_graph/trace_path) for structure and consult for a "
             "second opinion.")
RECOVERY = ("tezgah: tool call failed. Read the error, fix the cause, then "
            "re-run; prefer search_graph/trace_path over guessing at code.")


def cwd_of(payload):
    return (payload.get("cwd") or (payload.get("workspace_roots") or [None])[0]
            or os.getcwd())


def classify(payload, event=""):
    """The used-tool kind for a tool/observer payload, or None when
    undetectable. Reads every field shape Cursor sends: tool_input, command,
    mcp_server_name."""
    name = payload.get("tool_name", "") or ""
    server = payload.get("mcp_server_name", "") or ""
    blob = " ".join((str(name), str(server),
                     json.dumps(payload.get("tool_input") or {}),
                     str(payload.get("command") or "")))
    low = blob.lower()
    if any(k in low for k in GRAPH):
        return "cbm"
    if name in ("Task", "task"):
        return "orch"
    shell = name.lower() in ("shell", "bash") or event == "afterShellExecution"
    if shell and "consult" in low:
        return "consult"
    if shell and "orx" in low:
        return "research"
    return None


def first_time(session_id, tag):
    """True the first time a tag is seen for a session; fail-open when unwritable."""
    if not session_id:
        return True
    mark = os.path.join(cache_dir(), "reinforced", slug(str(session_id)), tag)
    if os.path.exists(mark):
        return False
    try:
        os.makedirs(os.path.dirname(mark), exist_ok=True)
        open(mark, "w").close()
    except OSError:
        pass
    return True


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
    kind = classify(payload, event)
    quiet = off("reminder-off")

    if event == "sessionStart":
        text = context_for("session_start", cwd, payload)
        out = {"additional_context": text} if text else {}
    elif event == "postToolUse":
        if kind:
            record(session_id, kind)
        note_tool(session_id, payload.get("tool_name", ""),
                  payload.get("tool_input") or {})
        out = {}
        if (kind in ("cbm", "consult") and under(cwd) and not quiet
                and first_time(session_id, "graph")):
            out["additional_context"] = REINFORCE
    elif event == "postToolUseFailure":
        if kind:
            record(session_id, kind)
        note_tool(session_id, payload.get("tool_name", ""),
                  payload.get("tool_input") or {}, failed=True)
        out = {"additional_context": RECOVERY} if under(cwd) and not quiet else {}
    elif event in ("afterShellExecution", "afterMCPExecution", "afterFileEdit"):
        if kind:
            record(session_id, kind)
        if event == "afterFileEdit":
            note(session_id, "edit",
                 payload.get("file_path") or payload.get("path") or "")
        elif event == "afterShellExecution":
            note_tool(session_id, "shell",
                      {"command": payload.get("command")
                       or (payload.get("tool_input") or {}).get("command", "")})
        out = {}
    elif event == "beforeMCPExecution":
        if kind:
            record(session_id, kind)
        # allow the code graph explicitly; defer (no decision) for all other
        # servers so a user policy is never overridden
        out = dict(ALLOW) if kind == "cbm" else {}
    elif event == "subagentStart":
        if explored(payload.get("subagent_type")):
            out = {"permission": "deny", "user_message": "grep-only explorer blocked; use general-purpose with the code graph tools"}
        else:
            record(session_id, "orch")
            out = {"permission": "allow"}
    elif event == "subagentStop":
        record(session_id, "orch")
        out = {}
    elif event == "preToolUse":
        tool = payload.get("tool_name", "")
        gate_tool = {"Shell": "Bash", "Read": "Read", "Grep": "Grep"}.get(tool, tool)
        inp = payload.get("tool_input") or {}
        reason = decision(gate_tool, inp, cwd, session_id)
        out = ({"permission": "deny", "agent_message": reason}
               if reason else dict(ALLOW))
    elif event == "beforeSubmitPrompt":
        # per-turn: the reminder plus whichever conditional rule this prompt's
        # task class arms (context_for classifies the submitted prompt)
        text = context_for("user_prompt", cwd, payload)
        out = {"continue": True}
        if text:
            out["additional_context"] = text
    else:
        out = {}
    print(json.dumps(out))


main()
