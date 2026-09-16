#!/usr/bin/env python3
"""omp (oh-my-pi) lifecycle hook: the python half of the omp extension.

omp's extension API is TypeScript, so `hosts/omp/tezgah-hook.ts` forwards each
event here as one JSON payload on stdin and puts the answer back into the host.
The envelope is omp's own - its event fields are not Claude's - but the contract,
the gate and the evidence ledger underneath are the shared core in `hooks/`,
the same code every other host runs.

    {"event": "session_start", "cwd": ..., "session_id": ...}
        -> {"context": <this repo's live state>, "status": "pony✓ ..."}
    {"event": "status", "cwd": ..., "session_id": ...}
        -> {"status": "pony✓ ..."}
    {"event": "user_prompt", "cwd": ..., "prompt": ...}
        -> {"context": <reminder + the rules this prompt arms>}
    {"event": "pre_tool_use", "cwd": ..., "tool": ..., "input": {...}}
        -> {"deny": reason}
    {"event": "post_tool_use", "cwd": ..., "tool": ..., "input": {...}, "failed": bool}
        -> {} (records the evidence the Stop rule reads)
    {"event": "stop", "last_assistant_message": ..., "stop_hook_active": bool}
        -> {"decision": "block", "reason": reason}

The status line is the one signal that is not root-scoped - tezgah ships as a
globally loaded rules file, so the indicator must not go silent off-root - and
`status` therefore answers anywhere. Every other event is inert outside a
configured root.
"""
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.realpath(__file__))))
sys.path.insert(0, os.path.join(ROOT, "hooks"))
from tezgah_context import context_for, health_lines, record  # noqa: E402
from tezgah_gate import decision  # noqa: E402
from tezgah_integrity import note_tool, stop_reason  # noqa: E402
from tezgah_paths import off, root_for  # noqa: E402


def classify(tool, inp):
    """The used-tool kind for one omp tool call, or None.

    omp names MCP tools `mcp__<server>_<tool>` (it also accepts Claude Code's
    doubled separator), so the server is matched by substring rather than by an
    exact prefix. Same kinds as the other hosts: cbm, orch, consult, research.
    """
    name = str(tool or "")
    if name.startswith("mcp__") and "codebase" in name:
        return "cbm"
    low = name.lower()
    if low in ("task", "agent", "spawn_agent"):
        return "orch"
    if low in ("bash", "shell", "command"):
        cmd = json.dumps(inp if isinstance(inp, dict) else {})
        if "consult" in cmd:
            return "consult"
        if "orx" in cmd:
            return "research"
    return None


def handle(payload):
    event = payload.get("event") or ""
    cwd = payload.get("cwd") or os.getcwd()
    session_id = payload.get("session_id")
    if event == "status":
        line = health_lines(cwd, session_id)
        return {"status": line} if line else {}
    if event == "pre_tool_use":
        reason = decision(payload.get("tool", ""), payload.get("input") or {},
                          cwd, session_id)
        return {"deny": reason} if reason else {}
    if not root_for(cwd):
        return {}
    if event == "session_start":
        # omp's always-on RULES.md already carries the core contract, so the
        # session payload is the part a static file cannot know: this repo's
        # index, its open plans, its lessons and the live kill switches.
        out = {}
        context = context_for("session_start", cwd, payload, with_core=False)
        if context:
            out["context"] = context
        line = health_lines(cwd, session_id)
        if line:
            out["status"] = line
        return out
    if event == "user_prompt":
        context = context_for("user_prompt", cwd, payload)
        return {"context": context} if context else {}
    if event == "post_tool_use":
        tool = payload.get("tool", "")
        inp = payload.get("input") if isinstance(payload.get("input"), dict) else {}
        failed = payload.get("failed")
        record(session_id, classify(tool, inp))
        # failed is tri-state on purpose: None means omp reported no outcome,
        # and the ledger then records a check that ran, never one that passed.
        note_tool(session_id, tool, inp,
                  failed=failed if isinstance(failed, bool) else None)
        # the call is already paid for, so the status line's used marks are
        # refreshed from the same answer instead of a second subprocess
        line = health_lines(cwd, session_id)
        return {"status": line} if line else {}
    if event == "stop":
        if payload.get("stop_hook_active") or off("verify-off"):
            return {}
        reason = stop_reason(payload.get("last_assistant_message"), session_id)
        return {"decision": "block", "reason": reason} if reason else {}
    return {}


def main():
    try:
        payload = json.load(sys.stdin)
    except Exception:
        return
    if not isinstance(payload, dict):
        return
    out = handle(payload)
    if out:
        print(json.dumps(out))


main()
