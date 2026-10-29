#!/usr/bin/env python3
"""Goose lifecycle hook. Reads Goose's JSON on stdin and answers in its own
output shape, onto the shared tezgah core (hooks/).

tezgah's entries live in its own plugin, `~/.agents/plugins/tezgah/hooks/
hooks.json` (`bin/tezgah-setup::GOOSE_HOOK_EVENTS`): SessionStart,
UserPromptSubmit, PreToolUse, PostToolUse, PostToolUseFailure and Stop (goose
docs guides/context-engineering/hooks); anything else is ignored. The event
name is the payload's `event`, the directory its `working_dir` (sent on tool
events only), else the hook's own cwd. Inert outside the roots. A hook fault is
logged by Goose and the call goes on: `on_failure` is left at its default
`allow`, so the gate fails open (X-D2).

Only PreToolUse and Stop can block. Both deny with `{"decision": "block",
"reason": ...}` on stdout, which must start with `{`, on exit 0. Every other
event is observation only: SessionStart writes the attestation, and
UserPromptSubmit the turn row; no output of theirs reaches the model, so the
always-on core is the managed block in `~/.config/goose/.goosehints` alone.
PostToolUse fires for a call that succeeded and PostToolUseFailure for one that
failed; neither carries the tool's output, so the event is the outcome. Stop
carries the reply as `last_assistant_message` and no count of earlier blocks,
so the turn's own rows bound the re-asks. No status line and no subagent events
(SubagentStart/SubagentStop are not emitted).
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
    from tezgah_integrity import bind_session, note, note_tool, stop_reason  # noqa: E402
    from tezgah_paths import off, root_for  # noqa: E402
    from tezgah_taste import write_note  # noqa: E402
    from tezgah_untrusted import marks  # noqa: E402
except Exception as exc:
    import_failed(exc)

# Goose's built-in developer tools arrive under their bare name (hooks "Tool
# Input Keys"); a subagent tool is not mapped.
GATE_TOOLS = {"shell": "Bash", "write": "Write", "edit": "Edit"}


def gate_name(name):
    """The tool name the gate denies under and the ledger row records; both
    halves map through here so a call hashes to one id. An extension's tool
    arrives as `<extension>__<tool>` and leaves in the shared
    `mcp__<extension>__<tool>` form."""
    if name in GATE_TOOLS:
        return GATE_TOOLS[name]
    if "__" in name.strip("_") and not name.startswith("mcp__"):
        return "mcp__" + name
    return name


def gate_input(name, inp):
    """The tool input in the gate's fields: `write` and `edit` name the file
    `path`, and `edit` its strings `before`/`after`."""
    inp = dict(inp) if isinstance(inp, dict) else {}
    if name in ("write", "edit") and "path" in inp:
        inp.setdefault("file_path", inp["path"])
    if name == "edit":
        for src, dst in (("before", "old_string"), ("after", "new_string")):
            if src in inp:
                inp.setdefault(dst, inp[src])
    return inp


def classify(tool, inp):
    """The used-tool kind for a mapped call, or None."""
    if tool.startswith("mcp__") and "codegraph" in tool:
        return "graph"
    if tool == "Bash":
        return shell_kind(command_text(inp))
    return None


def post_tool(payload, cwd, session_id, failed):
    """The ledger row for one finished call. Goose reads no output of this
    event, so nothing is returned to the model."""
    name = payload.get("tool_name", "") or ""
    tool, inp = gate_name(name), gate_input(name, payload.get("tool_input"))
    safe(session_id, record, session_id, classify(tool, inp))
    if not root_for(cwd):
        return
    # read before this call's row lands: `source` is the taint's own mark
    got = safe(session_id, marks, tool, inp, session_id, None)
    source = (got or (None, None))[0]
    safe(session_id, note_tool, session_id, tool, inp, failed=failed,
         source=source, cwd=cwd)
    safe(session_id, graph_advice, tool, inp, cwd, "goose")
    if not failed:
        safe(session_id, write_note, session_id, inp, cwd, tool)
        safe(session_id, cross_project_note, session_id, tool, inp, cwd)


def main():
    try:
        payload = json.load(sys.stdin)
    except Exception:
        return
    if not isinstance(payload, dict):
        return
    event = payload.get("event") or ""
    cwd = payload.get("working_dir") or os.getcwd()
    session_id = payload.get("session_id")
    safe(session_id, bind_session, session_id)  # the switch latch (tezgah_paths.off)
    out = {}
    if event == "PreToolUse":
        name = payload.get("tool_name", "") or ""
        reason = safe(session_id, decision, gate_name(name),
                      gate_input(name, payload.get("tool_input")), cwd, session_id)
        if reason:
            # Goose returns the reason to the model as a policy denial
            out = {"decision": "block", "reason": reason}
    elif event in ("PostToolUse", "PostToolUseFailure"):
        post_tool(payload, cwd, session_id, event == "PostToolUseFailure")
    elif event == "SessionStart":
        safe(session_id, attest_session, "goose", session_id, cwd)
    elif event == "UserPromptSubmit":
        # the turn row only: Goose ignores this event's output
        safe(session_id, context_for, "user_prompt", cwd, payload)
    elif event == "Stop":
        # a block forces the turn to keep going; Goose caps consecutive blocks
        # (GOOSE_STOP_HOOK_BLOCK_CAP). The payload counts no earlier block, so
        # the turn's refusal rows decide whether the reply may be refused again.
        # The reply is sent only when there is assistant output (X-D5).
        if not off("verify-off") and root_for(cwd):
            text = payload.get("last_assistant_message")
            if isinstance(text, str) and text.strip():
                reason = safe(session_id, stop_reason, text, session_id, cwd=cwd,
                              mode=payload.get("permission_mode"))
                if reason:
                    out = {"decision": "block", "reason": reason}
            else:
                safe(session_id, note, session_id, "reply_unread",
                     "no last_assistant_message")
    if out:
        print(json.dumps(out))


main()
