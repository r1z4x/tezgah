#!/usr/bin/env python3
"""Antigravity CLI (`agy`) lifecycle hook. Reads Antigravity's JSON on stdin and
answers in its own output shape, onto the shared tezgah core (hooks/).

tezgah's entries live under the top-level `tezgah` key of
`~/.gemini/config/hooks.json` (`bin/tezgah-setup::ANTIGRAVITY_HOOK_EVENTS`):
SessionStart, PreInvocation, PreToolUse, PostToolUse and Stop
(antigravity.google/docs/hooks). The payload names no event, so each command
passes it as the first argument; anything else is ignored. Inert outside the
roots. The fields are camelCase: `conversationId` is the session,
`workspacePaths[0]` the cwd, `toolCall.name`/`toolCall.args` the call, with
PascalCase argument names (`gate_input`).

The always-on core is the managed block in `~/.gemini/GEMINI.md`, shared with
Gemini CLI, so SessionStart repeats it as an `injectSteps` system message only
when that block is missing. PreInvocation with `invocationNum` 0 is taken as a
new user turn: it writes the turn row and carries the per-turn reminder as an
`ephemeralMessage`. PreToolUse always answers, since `decision` is required:
`deny` with a reason, else `allow`, which hands the call to the next hook or
the default policy. PostToolUse carries no tool output, only an `error` string
(empty when the call succeeded), and has no output channel, so its notices
reach the ledger only; a shell call never records a pass (`post_tool`).

Stop carries no reply text, so it reads the last assistant text from
`transcriptPath` (`last_reply`); none there is a `reply_unread` row, never
judged. Only a stop with `fullyIdle` and `terminationReason` `model_stop` is
judged; `{"decision": "continue", "reason": ...}` sends the model back into the
loop with the reason as a system message. The status line is
`tezgah-statusline --antigravity`, Antigravity's `statusLine` command.
"""
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.realpath(__file__))))
sys.path.insert(0, os.path.join(ROOT, "hooks"))
from tezgah_guard import attest_session, import_failed, safe  # noqa: E402
try:
    from tezgah_context import (  # noqa: E402
        _tail_lines, command_text, context_for, record, shell_kind)
    from tezgah_gate import cross_project_note, decision, graph_advice  # noqa: E402
    from tezgah_integrity import (  # noqa: E402
        bind_session, events, note, note_tool, stop_reason)
    from tezgah_paths import HOST_DIRS, off, root_for  # noqa: E402
    from tezgah_taste import write_note  # noqa: E402
    from tezgah_untrusted import marks  # noqa: E402
except Exception as exc:
    import_failed(exc)

# Antigravity's tool names (hooks "Supported tools") -> the gate's vocabulary.
# `view_file` maps for the ledger only: the PreToolUse matcher never sends it.
GATE_TOOLS = {
    "run_command": "Bash",
    "write_to_file": "Write",
    "replace_file_content": "Edit",
    "multi_replace_file_content": "MultiEdit",
    "invoke_subagent": "Task",
    "grep_search": "Grep",
    "view_file": "Read",
}
# PascalCase argument -> the gate's field, per tool
ARGS = {
    "run_command": {"CommandLine": "command"},
    "write_to_file": {"TargetFile": "file_path", "CodeContent": "content"},
    "replace_file_content": {"TargetFile": "file_path", "TargetContent": "old_string",
                             "ReplacementContent": "new_string"},
    "multi_replace_file_content": {"TargetFile": "file_path"},
    "grep_search": {"SearchPath": "path", "Query": "pattern"},
    "view_file": {"AbsolutePath": "file_path"},
}
CHUNK = {"TargetContent": "old_string", "ReplacementContent": "new_string",
         "AllowMultiple": "replace_all"}


def gate_name(name):
    """The tool name the gate denies under and the ledger row records; both
    halves map through here so a call hashes to one id."""
    return GATE_TOOLS.get(name, name)


def gate_input(name, args):
    """The tool arguments in the gate's fields. The docs name the arguments of
    `multi_replace_file_content`'s `ReplacementChunks` items nowhere; each is
    read as a `replace_file_content` (TargetContent/ReplacementContent), so an
    unknown chunk shape is judged on the file text beside its strings.
    `invoke_subagent`'s `Subagents` become `tasks` with the `TypeName` as
    `agent`, the batch shape the gate reads a subagent type from."""
    inp = dict(args) if isinstance(args, dict) else {}
    for src, dst in ARGS.get(name, {}).items():
        if src in inp and dst not in inp:
            inp[dst] = inp[src]
    if name == "multi_replace_file_content" and isinstance(inp.get("ReplacementChunks"), list):
        inp["edits"] = [{CHUNK.get(k, k): v for k, v in c.items()} if isinstance(c, dict)
                        else c for c in inp["ReplacementChunks"]]
    elif name == "invoke_subagent" and isinstance(inp.get("Subagents"), list):
        inp["tasks"] = [{"agent": s.get("TypeName"), "prompt": s.get("Prompt")}
                        for s in inp["Subagents"] if isinstance(s, dict)]
    return inp


def tool_call(payload):
    call = payload.get("toolCall")
    call = call if isinstance(call, dict) else {}
    name = call.get("name") if isinstance(call.get("name"), str) else ""
    return name, gate_input(name, call.get("args"))


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

    Antigravity documents `transcript.jsonl` only by its path. The parser is
    Command Code's (`hosts/commandcode/hook.py::last_reply`): Claude's
    `{"type": "assistant", "message": {"content": [...]}}` rows and bare
    `{"role": "assistant", "content": ...}` rows; a transcript that ends on a
    user or tool row has no reply written yet and answers ""."""
    parts = []
    for raw in reversed(_tail_lines(os.path.expanduser(path)) if path else []):
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
    """True when the global `~/.gemini/GEMINI.md` holds the managed block."""
    try:
        with open(os.path.join(os.path.dirname(HOST_DIRS["antigravity"]), "GEMINI.md"),
                  encoding="utf-8") as fh:
            return "<!-- tezgah:start" in fh.read()
    except OSError:
        return False


def reentered(session_id):
    """True when the ledger's last row is a Stop refusal: this invocation is the
    loop a `continue` re-entered, not a new user turn, so it writes no turn row
    and the refusal budget keeps counting in the refused turn.

    ponytail: whether `invocationNum` restarts at 0 on that re-entry is not
    documented; a user prompt sent right after a refusal (an interrupted loop)
    joins the refused turn, which can only refuse less."""
    rows = events(session_id, tail=1) if session_id else []
    return bool(rows and rows[-1].get("reask"))


def post_tool(payload, cwd, session_id):
    """The ledger row for one finished call. `error` is the runtime error, empty
    when the call succeeded (hooks "PostToolUse"); there is no output text.
    A shell call with an empty `error` is None (ran, never a pass): a command
    handed to the background (`WaitMsBeforeAsync`) also ends with no error, and
    nothing else tells the two apart, so Antigravity never records a pass."""
    name, inp = tool_call(payload)
    tool = gate_name(name)
    safe(session_id, record, session_id,
         "orch" if tool == "Task" else
         shell_kind(command_text(inp)) if tool == "Bash" else None)
    if not root_for(cwd):
        return
    failed = bool(payload.get("error"))
    if tool == "Bash" and not failed:
        failed = None
    got = safe(session_id, marks, tool, inp, session_id, None)
    source = (got or (None, None))[0]
    safe(session_id, note_tool, session_id, tool, inp, failed=failed,
         source=source, cwd=cwd)
    safe(session_id, graph_advice, tool, inp, cwd, "antigravity")
    if not failed:
        safe(session_id, write_note, session_id, inp, cwd, tool)
        safe(session_id, cross_project_note, session_id, tool, inp, cwd)


def inject(kind, text):
    """`injectSteps` with one step, or {} when there is nothing to say."""
    if not text:
        return {}
    step = {"systemMessage": {"systemMessage": text}} if kind == "system" \
        else {"ephemeralMessage": text}
    return {"injectSteps": [step]}


def main():
    try:
        payload = json.load(sys.stdin)
    except Exception:
        return
    if not isinstance(payload, dict):
        return
    event = sys.argv[1] if len(sys.argv) > 1 else ""
    paths = payload.get("workspacePaths")
    first = paths[0] if isinstance(paths, list) and paths else None
    cwd = first if isinstance(first, str) and first else os.getcwd()
    session_id = payload.get("conversationId")
    safe(session_id, bind_session, session_id)  # the switch latch (tezgah_paths.off)
    # the core's own field names; transcriptPath is left out: its format is not
    # the one the disarmed-gate counter reads (`tezgah_context.gate_inactive`)
    norm = {"session_id": session_id, "cwd": cwd}
    out = {}
    if event == "PreToolUse":
        name, inp = tool_call(payload)
        reason = safe(session_id, decision, gate_name(name), inp, cwd, session_id)
        # `decision` is required; `allow` hands the call on to the default policy
        out = {"decision": "deny", "reason": reason} if reason else {"decision": "allow"}
    elif event == "PostToolUse":
        post_tool(payload, cwd, session_id)
    elif event == "SessionStart":
        safe(session_id, attest_session, "antigravity", session_id, cwd)
        out = inject("system", safe(session_id, context_for, "session_start", cwd, norm,
                                    with_core=not rules_carry_core()))
    elif event == "PreInvocation":
        if payload.get("invocationNum") == 0 and not safe(session_id, reentered, session_id):
            out = inject("ephemeral", safe(session_id, context_for, "user_prompt", cwd, norm))
    elif event == "Stop":
        # `decision` is required; any value but `continue` lets the stop through
        out = {"decision": "allow"}
        if (payload.get("fullyIdle") is True and payload.get("terminationReason") == "model_stop"
                and not off("verify-off") and root_for(cwd)):
            path = payload.get("transcriptPath")
            text = safe(session_id, last_reply, path)
            if text:
                # Antigravity has no block counter; the turn's refusal rows
                # bound the re-asks (tezgah_integrity._record_only)
                reason = safe(session_id, stop_reason, text, session_id, cwd=cwd)
                if reason:
                    out = {"decision": "continue", "reason": reason}
            else:
                safe(session_id, note, session_id, "reply_unread",
                     "no assistant text at the end of %s" % path if path
                     else "no transcriptPath")
    else:
        return
    print(json.dumps(out))


main()
