#!/usr/bin/env python3
"""Command Code lifecycle hook. Reads Command Code's JSON on stdin and answers
in its own output shape, onto the shared tezgah core (hooks/).

Command Code fires four hook events (commandcode.ai/docs/hooks): SessionStart,
PreToolUse, PostToolUse and Stop (`bin/tezgah-setup::COMMANDCODE_HOOK_EVENTS`);
anything else is ignored. Inert outside the roots. Its settings hooks see only
four tools - shell, read, write, edit - so MCP, subagent and web calls never
reach this file, and plan mode skips every hook.

The always-on core is the managed block in `~/.commandcode/AGENTS.md`, the user
memory file Command Code puts in the system prompt, so SessionStart repeats it
only when that block is missing. There is no prompt event: no per-turn reminder
and no turn rows. PreToolUse translates the tool ids and input fields into the
gate's vocabulary (`gate_name`, `gate_input`) and denies with
`hookSpecificOutput.permissionDecision` on exit 0. PostToolUse's `tool_response`
is the text the model sees; a shell call's outcome is read off an `exit code N`
in it (`call_failed`).

Stop carries no reply text (`stop_hook_active` only), so it reads the last
assistant text from `transcript_path` (`last_reply`). When that read yields
nothing the turn end is a `reply_unread` row, never judged. The status segment
rides `systemMessage`, which Command Code shows in the TUI and never to the
model, at SessionStart and Stop (`hosts/codex/hook.py` does the same).
"""
import json
import os
import re
import shlex
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.realpath(__file__))))
sys.path.insert(0, os.path.join(ROOT, "hooks"))
from tezgah_guard import attest_session, import_failed, safe  # noqa: E402
try:
    from tezgah_context import (  # noqa: E402
        TOOL_USE_MEASURES, _tail_lines, command_text, context_for, health_lines,
        record, shell_kind)
    from tezgah_gate import cross_project_note, decision, graph_advice  # noqa: E402
    from tezgah_integrity import (  # noqa: E402
        bind_session, note, note_tool, ran_nothing, stop_reason)
    from tezgah_paths import HOST_DIRS, off, root_for  # noqa: E402
    from tezgah_taste import write_note  # noqa: E402
    from tezgah_untrusted import marks  # noqa: E402
except Exception as exc:
    import_failed(exc)

# Command Code's canonical tool ids (hooks "Tool-call fields") -> the gate's
# vocabulary. `read_file` maps for the ledger only: the PreToolUse matcher never
# sends it here.
GATE_TOOLS = {
    "shell_command": "Bash",
    "write_file": "Write",
    "edit_file": "Edit",
    "read_file": "Read",
}
# The result text names no documented exit-code format; the shell tool reports
# the code to the model, so the last `exit code N` in the text is taken.
EXIT_CODE = re.compile(r"(?i)exit code[: ]+(-?\d+)")


def gate_name(name):
    """The tool name the gate denies under and the ledger row records; both
    halves map through here so a call hashes to one id."""
    return GATE_TOOLS.get(name, name)


def gate_input(name, inp):
    """The tool input in the gate's fields. A shell call may split its command
    into `command` + `args` (Command Code shell-quotes the args itself), and an
    edit names its strings `old_value`/`new_value` in the hooks reference but
    `old_string`/`new_string` in the tools reference, so either is read. `args`
    is dropped once folded in: the gate reads an `args` key as a Task's object."""
    inp = dict(inp) if isinstance(inp, dict) else {}
    if name == "shell_command":
        args = inp.pop("args", None)
        if isinstance(args, list) and args and all(isinstance(a, str) for a in args):
            inp["command"] = ("%s %s" % (inp.get("command") or "", shlex.join(args))).strip()
    elif name == "edit_file":
        for src, dst in (("old_value", "old_string"), ("new_value", "new_string")):
            if src in inp and dst not in inp:
                inp[dst] = inp[src]
    return inp


def classify(payload):
    """The used-tool kind for a tool payload, or None."""
    if payload.get("tool_name") == "shell_command":
        return shell_kind(command_text(gate_input("shell_command", payload.get("tool_input"))))
    return None


def call_failed(payload):
    """`note_tool`'s `failed` for a shell call: the last `exit code N` in the
    result, and None when the result names no code - a call that RAN, never a
    pass."""
    if payload.get("tool_name") != "shell_command":
        return None
    resp = payload.get("tool_response")
    codes = EXIT_CODE.findall(resp) if isinstance(resp, str) else []
    return int(codes[-1]) != 0 if codes else None


def _text(content):
    """The text blocks of a message's content, a string or a block list."""
    if isinstance(content, str):
        return [content]
    if not isinstance(content, list):
        return []
    return [b.get("text") for b in content if isinstance(b, dict)
            and b.get("type") == "text" and isinstance(b.get("text"), str)]


def last_reply(path):
    """The text of the assistant reply that ends the transcript, or "".

    Command Code documents its transcript only as JSONL. Two row shapes are
    read: Claude's `{"type": "assistant", "message": {"content": [...]}}` and a
    bare `{"role": "assistant", "content": ...}`. The reply is the text of the
    trailing assistant rows; a transcript that ends on a user or tool row has
    no reply written yet and answers ""."""
    parts = []
    for raw in reversed(_tail_lines(path)):
        try:
            row = json.loads(raw)
        except ValueError:
            continue
        if not isinstance(row, dict):
            continue
        msg = row.get("message") if isinstance(row.get("message"), dict) else row
        role = row.get("type") if row.get("type") in ("user", "assistant") else msg.get("role")
        if role not in ("user", "assistant", "tool"):
            continue
        if role != "assistant":
            break
        parts[:0] = _text(msg.get("content"))
    return "\n".join(t for t in parts if t.strip())


def rules_carry_core():
    """True when `AGENTS.md` in Command Code's home holds the managed block."""
    try:
        with open(os.path.join(HOST_DIRS["commandcode"], "AGENTS.md"),
                  encoding="utf-8") as fh:
            return "<!-- tezgah:start" in fh.read()
    except OSError:
        return False


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
         out_bytes=len(result) if isinstance(result, str) else None,
         empty_run=ran_nothing(result))
    advice = safe(session_id, graph_advice, tool, inp, cwd, "commandcode")
    taste = cross = None
    if not failed:
        taste = safe(session_id, write_note, session_id, inp, cwd, tool)
        cross = safe(session_id, cross_project_note, session_id, tool, inp, cwd)
    return "\n".join(p for p in (notice, advice, taste, cross) if p)


def context(event, text):
    return {"hookSpecificOutput": {"hookEventName": event,
                                   "additionalContext": text}} if text else {}


def status(out, cwd, session_id):
    """Add the status segment as `systemMessage` (TUI only)."""
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
        safe(session_id, attest_session, "commandcode", session_id, cwd)
        out = status(context(event, safe(session_id, context_for, "session_start", cwd,
                                         payload, with_core=not rules_carry_core())),
                     cwd, session_id)
    elif event == "Stop":
        # {"decision": "block", "reason": ...} retries the turn, at most 3 times
        # (the host's cap); the reply after a block is judged again and refused
        # at most once more (tezgah_integrity).
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
        out = status(out, cwd, session_id)
    if out:
        print(json.dumps(out))


main()
