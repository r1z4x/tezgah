#!/usr/bin/env python3
"""Qwen Code lifecycle hook. Reads Qwen's JSON on stdin and answers in Qwen's own
output shape, onto the shared tezgah core (hooks/).

Qwen Code 0.21.13 fires SessionStart, UserPromptSubmit, PreToolUse, PostToolUse,
PostToolUseFailure, SubagentStart, SubagentStop and Stop here
(`bin/tezgah-setup::QWEN_HOOK_EVENTS`); anything else is ignored. Inert outside
the roots.

The always-on core is the managed block in `~/.qwen/QWEN.md`, which Qwen loads
into every session, so SessionStart repeats it only when that block is missing.
PreToolUse translates Qwen's runtime tool ids into the gate's vocabulary and
denies with `hookSpecificOutput.permissionDecision` on exit 0 - never exit 2,
whose stderr channel carries no reason the ledger and the probe can read. Qwen
fires PostToolUse for a successful call and PostToolUseFailure for a failed one
(a shell exit Qwen counts as an error, `isShellExitError`), so the event is the
call's outcome. Stop blocks a done/tested claim with no successful check behind
it, judged on `last_assistant_message`, the same rule Claude's Stop hook enforces
(hooks/tezgah_integrity.py). The status line is `tezgah-statusline --qwen`, Qwen's
`ui.statusLine` command, so no event here carries it.
"""
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.realpath(__file__))))
sys.path.insert(0, os.path.join(ROOT, "hooks"))
from tezgah_guard import attest_session, import_failed, safe  # noqa: E402
try:
    from tezgah_context import command_text, context_for, record, shell_kind  # noqa: E402
    from tezgah_gate import cross_project_note, decision, graph_advice  # noqa: E402
    from tezgah_integrity import (  # noqa: E402
        SUBAGENT_CHANNEL, bind_session, note, note_tool, ran_nothing, report_bytes,
        stop_reason, untrusted_source)
    from tezgah_paths import HOST_DIRS, off, root_for  # noqa: E402
    from tezgah_taste import write_note  # noqa: E402
    from tezgah_untrusted import marks  # noqa: E402
except Exception as exc:
    import_failed(exc)

# Qwen's runtime tool ids (the `ToolNames` table in the 0.21.13 bundle) -> the
# shared gate's vocabulary. `replace` is the edit tool's id in older builds; the
# 0.21.13 bundle has none, and an unknown id passes the gate untouched. MCP tools
# arrive as `mcp__<server>__<tool>`, the shared shape, and pass through.
# `monitor` runs a shell command too (Qwen's headless deny list pairs it with
# SHELL), and `notebook_edit` writes an .ipynb (review of plan 138).
GATE_TOOLS = {
    "run_shell_command": "Bash",
    "monitor": "Bash",
    "write_file": "Write",
    "edit": "Edit",
    "replace": "Edit",
    "notebook_edit": "NotebookEdit",
    "agent": "Task",
    "grep_search": "Grep",
}


def gate_name(name):
    """The tool name the gate denies under and the ledger row records.

    `call_id` hashes the name it is handed, so both halves map through here: a
    PostToolUse row under the raw id would never match the PreToolUse call and
    the loop guard would never deny (`hosts/codex/hook.py::gate_name`)."""
    return GATE_TOOLS.get(name, name)


def classify(payload):
    """The used-tool kind for a tool payload, or None."""
    name = payload.get("tool_name", "") or ""
    if name.startswith("mcp__") and "codegraph" in name:
        return "graph"
    if name == "agent":
        return "orch"
    if name == "run_shell_command":
        return shell_kind(command_text(payload.get("tool_input")))
    return None


def subagent_id(payload):
    """The subagent id Qwen adds to a hook input run inside a subagent, else None."""
    aid = payload.get("agent_id")
    return aid if isinstance(aid, str) and aid else None


def rules_carry_core():
    """True when `QWEN.md` in Qwen's home holds tezgah-setup's managed block."""
    try:
        with open(os.path.join(HOST_DIRS["qwen"], "QWEN.md"), encoding="utf-8") as fh:
            return "<!-- tezgah:start" in fh.read()
    except OSError:
        return False


def result_size(result):
    """The result's top-level length, the Claude-family writer's measure; a value
    with no length counts as non-empty and only a missing result is None."""
    if isinstance(result, (str, bytes, bytearray, list, tuple, dict, set, frozenset)):
        return len(result)
    return 1 if result is not None else None


def inp_of(payload):
    inp = payload.get("tool_input")
    return inp if isinstance(inp, dict) else {}


def post_tool(payload, cwd, session_id, failed):
    """The ledger row for one finished call, and the notice for the model."""
    tool = gate_name(payload.get("tool_name", ""))
    inp = inp_of(payload)
    safe(session_id, record, session_id, classify(payload))
    if not root_for(cwd):
        return None
    result = payload.get("tool_response")
    # read before this call's row lands: `source` is the taint's own mark
    got = safe(session_id, marks, tool, inp, session_id, result)
    source, notice = got or (None, None)
    safe(session_id, note_tool, session_id, tool, inp, failed=failed,
         interrupted=bool(failed and payload.get("is_interrupt") is True),
         source=source, cwd=cwd,
         out_bytes=(report_bytes(result)
                    if untrusted_source(tool, inp) == SUBAGENT_CHANNEL
                    else result_size(result)),
         empty_run=ran_nothing(result), agent=subagent_id(payload))
    advice = safe(session_id, graph_advice, tool, inp, cwd, "qwen")
    taste = cross = None
    if not failed:
        taste = safe(session_id, write_note, session_id, inp, cwd, tool)
        cross = safe(session_id, cross_project_note, session_id, tool, inp, cwd)
    return "\n".join(p for p in (notice, advice, taste, cross) if p)


def context(event, text):
    return {"hookSpecificOutput": {"hookEventName": event,
                                   "additionalContext": text}} if text else {}


def main():
    try:
        payload = json.load(sys.stdin)
    except Exception:
        return
    if not isinstance(payload, dict):
        return
    event = payload.get("hook_event_name") or ""
    cwd = payload.get("cwd") or os.getcwd()
    session_id = payload.get("session_id")
    safe(session_id, bind_session, session_id)  # the switch latch (tezgah_paths.off)
    out = {}
    if event == "PreToolUse":
        reason = safe(session_id, decision, gate_name(payload.get("tool_name", "")),
                      inp_of(payload), cwd, session_id, agent=subagent_id(payload))
        if reason:
            out = {"hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": "deny",
                "permissionDecisionReason": reason,
            }}
    elif event in ("PostToolUse", "PostToolUseFailure"):
        out = context(event, post_tool(payload, cwd, session_id,
                                       event == "PostToolUseFailure"))
    elif event == "SessionStart":
        safe(session_id, attest_session, "qwen", session_id, cwd)
        out = context(event, safe(session_id, context_for, "session_start", cwd,
                                  payload, with_core=not rules_carry_core()))
    elif event == "UserPromptSubmit":
        out = context(event, safe(session_id, context_for, "user_prompt", cwd, payload))
    elif event == "SubagentStart":
        safe(session_id, record, session_id, "orch")
        kind = payload.get("agent_type")
        if subagent_id(payload) and isinstance(kind, str) and root_for(cwd):
            safe(session_id, note, session_id, "subagent_start", kind,
                 agent=subagent_id(payload))
        # the delegate is a fresh context: Qwen documents additionalContext here
        # as the subagent's initial context
        out = context(event, safe(session_id, context_for, "subagent_start", cwd,
                                  payload))
    elif event == "SubagentStop":
        # a subagent's end is judged record-only (ADR 011): one `subagent_end`
        # row from its last message, never a block
        safe(session_id, record, session_id, "orch")
        if not off("verify-off") and root_for(cwd):
            safe(session_id, stop_reason, payload.get("last_assistant_message") or "",
                 session_id, cwd=cwd, subagent=True)
    elif event == "Stop":
        # Qwen's Stop carries `last_assistant_message` and `stop_hook_active`,
        # and takes {"decision": "block", "reason": ...}. The reply after a block
        # is judged again and refused at most once more (tezgah_integrity).
        if not off("verify-off") and root_for(cwd):
            reason = safe(session_id, stop_reason,
                          payload.get("last_assistant_message"), session_id,
                          cwd=cwd, after_block=bool(payload.get("stop_hook_active")))
            if reason:
                out = {"decision": "block", "reason": reason}
    if out:
        print(json.dumps(out))


main()
