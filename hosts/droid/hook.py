#!/usr/bin/env python3
"""Factory Droid lifecycle hook. Reads Droid's JSON on stdin and answers in
Droid's own output shape, onto the shared tezgah core (hooks/).

Droid 0.251.0 fires SessionStart, UserPromptSubmit, PreToolUse, PostToolUse,
SubagentStop and Stop here (`bin/tezgah-setup::DROID_HOOK_EVENTS`); anything
else is ignored. Inert outside the roots.

The always-on core is the managed block in `~/.factory/AGENTS.md`, which Droid
loads as coding guidelines in every session, so SessionStart repeats it only
when that block is missing. PreToolUse translates Droid's tool ids into the
gate's vocabulary and denies with `hookSpecificOutput.permissionDecision` on
exit 0 - never exit 2, whose stderr channel carries no reason the ledger and the
probe can read. Droid has no failure event: PostToolUse fires for every
finished call, so a shell call's outcome is read off its result
(`call_failed`).

Droid's Stop event carries no reply text (`stop_hook_active`,
`tool_execution_count`, `elapsed_time`), so Stop reads the last assistant text
from `transcript_path` (`last_reply`). When that read yields nothing, the turn
end is recorded as a `reply_unread` row and not judged: judging an empty reply
would let any claim through as "no claim". SubagentStop carries the sub-droid's
`task_result` and is judged record-only. Droid has no SubagentStart, so a
delegate gets no brief. The status line is `tezgah-statusline --droid`, Droid's
`statusLine` command, so no event here carries it.
"""
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.realpath(__file__))))
sys.path.insert(0, os.path.join(ROOT, "hooks"))
from tezgah_guard import attest_session, import_failed, safe  # noqa: E402
try:
    from tezgah_context import (  # noqa: E402
        _tail_lines, command_text, context_for, record, shell_kind)
    from tezgah_gate import cross_project_note, decision, graph_advice  # noqa: E402
    from tezgah_integrity import (  # noqa: E402
        SUBAGENT_CHANNEL, bind_session, note, note_tool, ran_nothing, report_bytes,
        stop_reason, untrusted_source)
    from tezgah_paths import HOST_DIRS, off, root_for  # noqa: E402
    from tezgah_taste import write_note  # noqa: E402
    from tezgah_untrusted import marks  # noqa: E402
except Exception as exc:
    import_failed(exc)

# Droid's tool ids (harness/hooks "Common tool matchers", harness/subagents tool
# categories) -> the shared gate's vocabulary. Read, LS, Glob, Grep, Task,
# TodoWrite and WebSearch already carry the gate's names; MCP tools arrive as
# `mcp__<server>__<tool>`, the shared shape, and pass through.
GATE_TOOLS = {
    "Execute": "Bash",
    "Create": "Write",
    "ApplyPatch": "apply_patch",
    "FetchUrl": "WebFetch",
}
# How Droid ends a shell result: the text its transcripts store for an Execute
# call (`[Process exited with code 1]`). The PostToolUse `tool_response` shape is
# undocumented, so this is read wherever the result carries text.
EXIT_LINE = re.compile(r"\[Process exited with code (-?\d+)\]")


def gate_name(name):
    """The tool name the gate denies under and the ledger row records.

    `call_id` hashes the name it is handed, so both halves map through here: a
    PostToolUse row under the raw id would never match the PreToolUse call and
    the loop guard would never deny (`hosts/codex/hook.py::gate_name`)."""
    return GATE_TOOLS.get(name, name)


def gate_input(name, inp):
    """The tool input in the gate's fields. Droid's ApplyPatch sends its patch as
    `input` (the 0.251.0 bundle reads `o.input` as the patch text); the gate
    reads `patch`."""
    inp = inp if isinstance(inp, dict) else {}
    if name == "ApplyPatch" and isinstance(inp.get("input"), str) and "patch" not in inp:
        return dict(inp, patch=inp["input"])
    return inp


def classify(payload):
    """The used-tool kind for a tool payload, or None."""
    name = payload.get("tool_name", "") or ""
    if name.startswith("mcp__") and "codegraph" in name:
        return "graph"
    if name == "Task":
        return "orch"
    if name == "Execute":
        return shell_kind(command_text(payload.get("tool_input")))
    return None


def _texts(value):
    """Every string in a result, depth first."""
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for v in value.values():
            yield from _texts(v)
    elif isinstance(value, list):
        for v in value:
            yield from _texts(v)


def call_failed(payload):
    """The outcome a PostToolUse reports, as `note_tool`'s `failed`: True/False
    from an Execute result's exit code - an integer `exit_code`/`exitCode`, else
    the last `[Process exited with code N]` line - and None when no code is
    read. A call with no code is recorded as one that RAN, never as a pass."""
    if payload.get("tool_name") != "Execute":
        return None
    resp = payload.get("tool_response")
    if isinstance(resp, dict):
        for key in ("exit_code", "exitCode"):
            code = resp.get(key)
            if isinstance(code, int) and not isinstance(code, bool):
                return code != 0
    codes = [m for text in _texts(resp) for m in EXIT_LINE.findall(text)]
    return int(codes[-1]) != 0 if codes else None


def last_reply(path):
    """The text of the assistant reply that ends the transcript, or "".

    Droid writes one JSON row per message: `{"type": "message", "message":
    {"role": "assistant", "content": [{"type": "text", "text": ...}]}}` (the
    shape its session files carry). The reply is the text of the trailing
    assistant rows; a transcript whose last message is the user's - a tool result
    or a prompt - has no reply written yet, so it answers ""."""
    parts = []
    for raw in reversed(_tail_lines(path)):
        try:
            row = json.loads(raw)
        except ValueError:
            continue
        msg = row.get("message") if isinstance(row, dict) else None
        if not isinstance(msg, dict) or row.get("type") != "message":
            continue
        if msg.get("role") != "assistant":
            break
        content = msg.get("content")
        texts = [b.get("text") for b in content if isinstance(b, dict)
                 and b.get("type") == "text" and isinstance(b.get("text"), str)] \
            if isinstance(content, list) else []
        parts[:0] = texts
    return "\n".join(t for t in parts if t.strip())


def rules_carry_core():
    """True when `AGENTS.md` in Droid's home holds tezgah-setup's managed block."""
    try:
        with open(os.path.join(HOST_DIRS["droid"], "AGENTS.md"), encoding="utf-8") as fh:
            return "<!-- tezgah:start" in fh.read()
    except OSError:
        return False


def result_size(result):
    """The result's top-level length, the Claude-family writer's measure; a value
    with no length counts as non-empty and only a missing result is None."""
    if isinstance(result, (str, bytes, bytearray, list, tuple, dict, set, frozenset)):
        return len(result)
    return 1 if result is not None else None


def post_tool(payload, cwd, session_id):
    """The ledger row for one finished call, and the notice for the model."""
    name = payload.get("tool_name", "") or ""
    tool = gate_name(name)
    inp = gate_input(name, payload.get("tool_input"))
    safe(session_id, record, session_id, classify(payload))
    if not root_for(cwd):
        return None
    result = payload.get("tool_response")
    failed = call_failed(payload)
    # read before this call's row lands: `source` is the taint's own mark
    got = safe(session_id, marks, tool, inp, session_id, result)
    source, notice = got or (None, None)
    safe(session_id, note_tool, session_id, tool, inp, failed=failed,
         source=source, cwd=cwd,
         out_bytes=(report_bytes(result)
                    if untrusted_source(tool, inp) == SUBAGENT_CHANNEL
                    else result_size(result)),
         empty_run=ran_nothing(result))
    advice = safe(session_id, graph_advice, tool, inp, cwd, "droid")
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
        name = payload.get("tool_name", "") or ""
        reason = safe(session_id, decision, gate_name(name),
                      gate_input(name, payload.get("tool_input")), cwd, session_id)
        if reason:
            out = {"hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": "deny",
                "permissionDecisionReason": reason,
            }}
    elif event == "PostToolUse":
        out = context(event, post_tool(payload, cwd, session_id))
    elif event == "SessionStart":
        safe(session_id, attest_session, "droid", session_id, cwd)
        out = context(event, safe(session_id, context_for, "session_start", cwd,
                                  payload, with_core=not rules_carry_core()))
    elif event == "UserPromptSubmit":
        out = context(event, safe(session_id, context_for, "user_prompt", cwd, payload))
    elif event == "SubagentStop":
        # a sub-droid's end is judged record-only (ADR 011): one `subagent_end`
        # row from its `task_result`, never a block
        safe(session_id, record, session_id, "orch")
        if not off("verify-off") and root_for(cwd):
            text = payload.get("task_result")
            safe(session_id, stop_reason, text if isinstance(text, str) else "",
                 session_id, cwd=cwd, subagent=True)
    elif event == "Stop":
        # Droid's Stop takes {"decision": "block", "reason": ...}. The reply
        # after a block is judged again and refused at most once more
        # (tezgah_integrity).
        if not off("verify-off") and root_for(cwd):
            path = payload.get("transcript_path")
            text = safe(session_id, last_reply, path)
            if text:
                reason = safe(session_id, stop_reason, text, session_id, cwd=cwd,
                              after_block=bool(payload.get("stop_hook_active")),
                              mode=payload.get("permission_mode"))
                if reason:
                    out = {"decision": "block", "reason": reason}
            else:
                safe(session_id, note, session_id, "reply_unread",
                     "no assistant text at the end of %s" % path if path
                     else "no transcript_path")
    if out:
        print(json.dumps(out))


main()
