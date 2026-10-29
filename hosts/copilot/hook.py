#!/usr/bin/env python3
"""GitHub Copilot CLI lifecycle hook. Reads Copilot's JSON on stdin and answers
in its own output shape, onto the shared tezgah core (hooks/).

tezgah's entries live in their own file, `$COPILOT_HOME/hooks/tezgah.json`
(`bin/tezgah-setup::COPILOT_HOOK_EVENTS`). They use the PascalCase event names,
so the payloads carry snake_case fields and Claude tool names
(docs.github.com hooks-reference "Hook event input payloads"): SessionStart,
UserPromptSubmit, PreToolUse, PostToolUse, PostToolUseFailure, Stop and
SubagentStop. `subagentStart` has no PascalCase form; its camelCase payload
names no event, so its command passes the event as the first argument.
Anything else is ignored. Inert outside the roots.

The always-on core is the managed block in `$COPILOT_HOME/copilot-instructions.md`,
so SessionStart repeats it only when that block is missing. A command hook's
UserPromptSubmit output is dropped by Copilot, so there is no per-turn
reminder; the event still writes the turn row. PreToolUse translates the tool
names into the gate's vocabulary and denies with a top-level
`permissionDecision: deny` on exit 0. Copilot denies the call itself when this
hook crashes, and lets it through when the hook times out.

Copilot fires PostToolUse for a successful call and PostToolUseFailure for a
failed one, so the event is the outcome; a shell result's `exit code N` text
overrides it (`call_failed`). Stop carries no reply text, so it reads the last
`assistant.message` from `transcript_path` (`last_reply`); none there is a
`reply_unread` row, never judged. SubagentStop is judged record-only. The status
line is `tezgah-statusline --copilot`, Copilot's `statusLine` command.
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

# Copilot's tool names -> the gate's vocabulary. A PascalCase PreToolUse
# reports the Claude name (hooks-reference "Claude-format matchers"); the
# runtime spellings map to the same names, since no doc says the other events
# translate theirs.
GATE_TOOLS = {
    "bash": "Bash", "powershell": "Bash",
    "create": "Write",
    "edit": "Edit", "str_replace_editor": "Edit", "apply_patch": "Edit",
    "Agent": "Task", "task": "Task",
    "grep": "Grep", "rg": "Grep",
    "view": "Read",
}
# The result text names no documented exit-code format; the last `exit code N`
# in it is taken.
EXIT_CODE = re.compile(r"(?i)exit code[: ]+(-?\d+)")


def mcp_servers():
    """The server names in `$COPILOT_HOME/mcp-config.json`, sanitized the way
    Copilot builds a tool name (cli-command-reference "MCP tool name
    sanitization"), longest first."""
    try:
        with open(os.path.join(HOST_DIRS["copilot"], "mcp-config.json"),
                  encoding="utf-8") as fh:
            servers = json.load(fh).get("mcpServers")
    except (OSError, ValueError, AttributeError):
        return []
    names = {re.sub(r"[^A-Za-z0-9_-]", "-", s) for s in servers or {}
             if isinstance(s, str)}
    return sorted(names, key=len, reverse=True)


def is_patch(name, inp):
    """An Edit that names no file but carries a patch string: `apply_patch`."""
    if GATE_TOOLS.get(name, name) != "Edit":
        return False
    if isinstance(inp, str):
        return True
    return (isinstance(inp, dict) and not (inp.get("path") or inp.get("file_path"))
            and any(isinstance(inp.get(k), str) for k in ("patch", "input")))


def gate_name(name, inp=None):
    """The tool name the gate denies under and the ledger row records; both
    halves map through here so a call hashes to one id. An MCP tool arrives as
    `<server>-<tool>` and leaves in the shared `mcp__<server>__<tool>` form when
    the server is one `mcp-config.json` names."""
    if is_patch(name, inp):
        return "apply_patch"
    if name in GATE_TOOLS:
        return GATE_TOOLS[name]
    for server in mcp_servers() if "-" in name else ():
        if name.startswith(server + "-") and len(name) > len(server) + 1:
            return "mcp__%s__%s" % (server, name[len(server) + 1:])
    return name


def gate_input(name, inp):
    """The tool input in the gate's fields. The gate already reads Copilot's
    `path`, `file_text`, `old_str` and `new_str`; a patch is handed over as
    `patch`."""
    if is_patch(name, inp):
        if isinstance(inp, str):
            return {"patch": inp}
        return dict(inp, patch=inp["patch"] if isinstance(inp.get("patch"), str)
                    else inp["input"])
    return inp if isinstance(inp, dict) else {}


def classify(tool, inp):
    """The used-tool kind for a mapped call, or None."""
    if tool.startswith("mcp__") and "codegraph" in tool:
        return "graph"
    if tool == "Task":
        return "orch"
    if tool == "Bash":
        return shell_kind(command_text(inp))
    return None


def subagent_id(payload):
    """The subagent id Copilot adds to a hook input fired inside a subagent."""
    aid = payload.get("agent_id")
    return aid if isinstance(aid, str) and aid else None


def result_text(payload):
    """The text the model saw: PostToolUse's `tool_result.text_result_for_llm`,
    PostToolUseFailure's `error`."""
    res = payload.get("tool_result")
    if isinstance(res, dict) and isinstance(res.get("text_result_for_llm"), str):
        return res["text_result_for_llm"]
    err = payload.get("error")
    return err if isinstance(err, str) else None


def call_failed(tool, failed, text):
    """`note_tool`'s `failed`: the event's outcome, unless a shell result names
    an exit code."""
    codes = EXIT_CODE.findall(text) if tool == "Bash" and isinstance(text, str) else []
    return int(codes[-1]) != 0 if codes else failed


def last_reply(path):
    """The reply that ends the transcript, or "".

    Copilot keeps a session's event log as JSONL (`session-state/<id>/events.jsonl`,
    cli-config-dir-reference); an assistant reply is an `assistant.message` event
    whose `data.content` is the text. A transcript whose last message is the
    user's has no reply written yet."""
    for raw in reversed(_tail_lines(path)):
        try:
            row = json.loads(raw)
        except ValueError:
            continue
        kind = row.get("type") if isinstance(row, dict) else None
        if kind == "user.message":
            break
        data = row.get("data") if kind == "assistant.message" else None
        text = data.get("content") if isinstance(data, dict) else None
        if isinstance(text, str) and text.strip():
            return text
    return ""


def rules_carry_core():
    """True when Copilot's personal instructions file holds the managed block."""
    try:
        with open(os.path.join(HOST_DIRS["copilot"], "copilot-instructions.md"),
                  encoding="utf-8") as fh:
            return "<!-- tezgah:start" in fh.read()
    except OSError:
        return False


def post_tool(payload, cwd, session_id, failed):
    """The ledger row for one finished call, and the notice for the model."""
    name = payload.get("tool_name", "") or ""
    raw = payload.get("tool_input")
    tool, inp = gate_name(name, raw), gate_input(name, raw)
    safe(session_id, record, session_id, classify(tool, inp))
    if not root_for(cwd):
        return None
    result = result_text(payload)
    failed = call_failed(tool, failed, result)
    # read before this call's row lands: `source` is the taint's own mark
    got = safe(session_id, marks, tool, inp, session_id, result)
    source, notice = got or (None, None)
    safe(session_id, note_tool, session_id, tool, inp, failed=failed,
         source=source, cwd=cwd,
         out_bytes=(report_bytes(result)
                    if untrusted_source(tool, inp) == SUBAGENT_CHANNEL
                    else len(result) if isinstance(result, str) else None),
         empty_run=ran_nothing(result), agent=subagent_id(payload))
    advice = safe(session_id, graph_advice, tool, inp, cwd, "copilot")
    taste = cross = None
    if not failed:
        taste = safe(session_id, write_note, session_id, inp, cwd, tool)
        cross = safe(session_id, cross_project_note, session_id, tool, inp, cwd)
    return "\n".join(p for p in (notice, advice, taste, cross) if p)


def context(text):
    return {"additionalContext": text} if text else {}


def main():
    try:
        payload = json.load(sys.stdin)
    except Exception:
        return
    if not isinstance(payload, dict):
        return
    event = payload.get("hook_event_name") or (sys.argv[1] if len(sys.argv) > 1 else "")
    cwd = payload.get("cwd") or os.getcwd()
    session_id = payload.get("session_id") or payload.get("sessionId")
    safe(session_id, bind_session, session_id)  # the switch latch (tezgah_paths.off)
    out = {}
    if event == "PreToolUse":
        name = payload.get("tool_name", "") or ""
        raw = payload.get("tool_input")
        reason = safe(session_id, decision, gate_name(name, raw), gate_input(name, raw),
                      cwd, session_id, agent=subagent_id(payload))
        if reason:
            # top level, not wrapped (hooks-reference "preToolUse decision control")
            out = {"permissionDecision": "deny", "permissionDecisionReason": reason}
    elif event in ("PostToolUse", "PostToolUseFailure"):
        out = context(post_tool(payload, cwd, session_id, event == "PostToolUseFailure"))
    elif event == "SessionStart":
        safe(session_id, attest_session, "copilot", session_id, cwd)
        out = context(safe(session_id, context_for, "session_start", cwd, payload,
                           with_core=not rules_carry_core()))
    elif event == "UserPromptSubmit":
        # the turn row only: Copilot drops a command hook's output here
        safe(session_id, context_for, "user_prompt", cwd, payload)
    elif event == "subagentStart":
        # additionalContext is prepended to the subagent's first message
        safe(session_id, record, session_id, "orch")
        out = context(safe(session_id, context_for, "subagent_start", cwd,
                           dict(payload, session_id=session_id)))
    elif event == "SubagentStop":
        # a subagent's end is judged record-only (ADR 011): one `subagent_end`
        # row from its last message, never a block
        safe(session_id, record, session_id, "orch")
        if not off("verify-off") and root_for(cwd):
            text = payload.get("last_assistant_message")
            safe(session_id, stop_reason, text if isinstance(text, str) else "",
                 session_id, cwd=cwd, subagent=True)
    elif event == "Stop":
        # {"decision": "block", "reason": ...} forces another turn; Copilot ends
        # the turn anyway after 8 blocks in a row. The reply after a block is
        # judged again and refused at most once more (tezgah_integrity).
        if not off("verify-off") and root_for(cwd):
            path = payload.get("transcript_path")
            text = safe(session_id, last_reply, path)
            if text:
                reason = safe(session_id, stop_reason, text, session_id, cwd=cwd,
                              after_block=bool(payload.get("stop_hook_active")))
                if reason:
                    out = {"decision": "block", "reason": reason}
            else:
                safe(session_id, note, session_id, "reply_unread",
                     "no assistant.message at the end of %s" % path if path
                     else "no transcript_path")
    if out:
        print(json.dumps(out))


main()
