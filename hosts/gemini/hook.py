#!/usr/bin/env python3
"""Gemini CLI lifecycle hook. Reads Gemini's JSON on stdin and answers in its own
output shape, onto the shared tezgah core (hooks/).

tezgah's entries live in its own extension, `$GEMINI_CLI_HOME/.gemini/extensions/
tezgah/hooks/hooks.json` (`bin/tezgah-setup::GEMINI_HOOK_EVENTS`): SessionStart,
BeforeAgent, BeforeTool, AfterTool and AfterAgent (geminicli hooks reference);
anything else is ignored. Inert outside the roots. A bad exit or bad stdout is a
warning there and the call goes on (fail open).

The always-on core is the managed block in `~/.gemini/GEMINI.md`, the global
context file, so SessionStart repeats it only when that block is missing.
BeforeAgent writes the turn row and carries the per-turn reminder as
`hookSpecificOutput.additionalContext`. BeforeTool translates the tool names
into the gate's vocabulary and denies with a top-level
`{"decision": "deny", "reason": ...}` on exit 0. AfterTool's `tool_response`
holds `llmContent` and an optional `error`; the outcome is read off both
(`call_failed`). AfterAgent carries the reply as `prompt_response` and
`stop_hook_active`, and its deny sends the reason back as a new prompt. Gemini
has no command status line (`ui.footer` is a closed list), so the status
segment rides `systemMessage` at SessionStart and AfterAgent.
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
        TOOL_USE_MEASURES, command_text, context_for, health_lines, record, shell_kind)
    from tezgah_gate import cross_project_note, decision, graph_advice  # noqa: E402
    from tezgah_integrity import (  # noqa: E402
        SUBAGENT_CHANNEL, bind_session, note_tool, ran_nothing, report_bytes,
        stop_reason, untrusted_source)
    from tezgah_paths import HOST_DIRS, off, root_for  # noqa: E402
    from tezgah_taste import write_note  # noqa: E402
    from tezgah_untrusted import marks  # noqa: E402
except Exception as exc:
    import_failed(exc)

# Gemini's tool names (docs reference/tools.md, core/subagents.md) -> the gate's
# vocabulary. A subagent is a tool of its own name; `invoke_agent` is the
# generic one in the source's tool-names.ts. A user's own agents are not mapped.
GATE_TOOLS = {
    "run_shell_command": "Bash",
    "write_file": "Write",
    "replace": "Edit",
    "grep_search": "Grep", "search_file_content": "Grep",
    "codebase_investigator": "Task", "generalist": "Task", "invoke_agent": "Task",
    "read_file": "Read",
}
# The shell tool writes `Output: ...` first, then `Exit Code: N` only for a
# non-zero code, or `Signal: NAME` for a killed process
# (packages/core/src/tools/shell.ts), inside an `<untrusted_context>` wrapper;
# a background or cancelled run has no Output.
RAN = re.compile(r"\A(?:<untrusted_context[^>]*>\n)?Output: ")
EXIT_CODE = re.compile(r"(?m)^Exit Code: (-?\d+)$")
SIGNAL = re.compile(r"(?m)^Signal: ")


def gate_name(name):
    """The tool name the gate denies under and the ledger row records; both
    halves map through here so a call hashes to one id. An MCP tool arrives as
    `mcp_<server>_<tool>`, where nothing marks the boundary, and leaves as
    `mcp__<server>_<tool>`."""
    if name in GATE_TOOLS:
        return GATE_TOOLS[name]
    if name.startswith("mcp_") and not name.startswith("mcp__"):
        return "mcp__" + name[4:]
    return name


def inp_of(payload):
    inp = payload.get("tool_input")
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


def result_text(resp):
    """`tool_response.llmContent` as text: a string, or a list of parts."""
    content = resp.get("llmContent") if isinstance(resp, dict) else None
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "\n".join(p.get("text") if isinstance(p, dict) and isinstance(p.get("text"), str)
                         else p if isinstance(p, str) else "" for p in content)
    return None


def call_failed(tool, resp, text):
    """`note_tool`'s `failed`: an `error` in the response is a failure; a shell
    result names a non-zero exit code or a signal (a killed runner), or ran to
    its end with neither (a pass). None when the response says none of these -
    a call that RAN, never a pass."""
    if isinstance(resp, dict) and resp.get("error"):
        return True
    if tool != "Bash" or not isinstance(text, str):
        return None
    codes = EXIT_CODE.findall(text)
    if codes:
        return int(codes[-1]) != 0
    if SIGNAL.search(text):
        return True
    return False if RAN.match(text) else None


def rules_carry_core():
    """True when Gemini's global GEMINI.md holds tezgah-setup's managed block."""
    try:
        with open(os.path.join(HOST_DIRS["gemini"], "GEMINI.md"), encoding="utf-8") as fh:
            return "<!-- tezgah:start" in fh.read()
    except OSError:
        return False


def post_tool(payload, cwd, session_id):
    """The ledger row for one finished call, and the notice for the model."""
    tool, inp = gate_name(payload.get("tool_name", "") or ""), inp_of(payload)
    safe(session_id, record, session_id, classify(tool, inp))
    if not root_for(cwd):
        return None
    resp = payload.get("tool_response")
    result = result_text(resp)
    failed = call_failed(tool, resp, result)
    # read before this call's row lands: `source` is the taint's own mark
    got = safe(session_id, marks, tool, inp, session_id, result)
    source, notice = got or (None, None)
    safe(session_id, note_tool, session_id, tool, inp, failed=failed,
         source=source, cwd=cwd,
         out_bytes=(report_bytes(result)
                    if untrusted_source(tool, inp) == SUBAGENT_CHANNEL
                    else len(result) if isinstance(result, str) else None),
         empty_run=ran_nothing(result))
    advice = safe(session_id, graph_advice, tool, inp, cwd, "gemini")
    taste = cross = None
    if not failed:
        taste = safe(session_id, write_note, session_id, inp, cwd, tool)
        cross = safe(session_id, cross_project_note, session_id, tool, inp, cwd)
    return "\n".join(p for p in (notice, advice, taste, cross) if p)


def context(event, text):
    return {"hookSpecificOutput": {"hookEventName": event,
                                   "additionalContext": text}} if text else {}


def status(out, cwd, session_id):
    """Add the status segment as `systemMessage`, shown to the user only."""
    seg = safe(session_id, health_lines, cwd, session_id, observable=TOOL_USE_MEASURES)
    if seg:
        out["systemMessage"] = "tezgah  " + seg
    return out


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
    if event == "BeforeTool":
        reason = safe(session_id, decision, gate_name(payload.get("tool_name", "") or ""),
                      inp_of(payload), cwd, session_id)
        if reason:
            # the reason reaches the agent as the tool's error; the turn goes on
            out = {"decision": "deny", "reason": reason}
    elif event == "AfterTool":
        out = context(event, post_tool(payload, cwd, session_id))
    elif event == "SessionStart":
        safe(session_id, attest_session, "gemini", session_id, cwd)
        out = status(context(event, safe(session_id, context_for, "session_start", cwd,
                                         payload, with_core=not rules_carry_core())),
                     cwd, session_id)
    elif event == "BeforeAgent":
        out = context(event, safe(session_id, context_for, "user_prompt", cwd, payload))
    elif event == "AfterAgent":
        # {"decision": "deny", "reason": ...} rejects the reply and sends the
        # reason back as a new prompt; the reply after a block is judged again
        # and refused at most once more (tezgah_integrity).
        if not off("verify-off") and root_for(cwd):
            text = payload.get("prompt_response")
            reason = safe(session_id, stop_reason, text if isinstance(text, str) else "",
                          session_id, cwd=cwd,
                          after_block=bool(payload.get("stop_hook_active")))
            if reason:
                out = {"decision": "deny", "reason": reason}
        out = status(out, cwd, session_id)
    if out:
        print(json.dumps(out))


main()
