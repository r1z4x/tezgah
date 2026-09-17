#!/usr/bin/env python3
"""Cursor lifecycle hook. Cursor uses its own event names and output schemas,
so this adapter translates them onto the shared tezgah core:

  sessionStart        -> {"additional_context": <shared context>}
  preToolUse          -> {"permission": "allow"|"deny", "agent_message": ...}
                         (the shared gate: grep-only explorer, first identifier
                         grep nudge, attribution and test-skip on the write tools)
  beforeMCPExecution  -> {"permission": "allow"} for the code graph, else {}
  subagentStart       -> {"additional_context": <short contract brief>} for the
                         delegate, or deny for a grep-only explorer
  subagentStop        -> record orch, no followup
  postToolUse         -> record usage; reinforce once per session on graph/consult
  postToolUseFailure  -> record usage; one-line recovery hint
  after*Execution/Edit-> record usage, no output (observers)
  afterAgentResponse  -> remember the reply for the stop decision, no output
  stop                -> block a done/tested claim no check backs
                         ({"decision": "block", "reason": ...}, which Cursor
                         documents as an automatic follow-up - the native
                         spelling is {"followup_message": ...})
  beforeSubmitPrompt  -> {"continue": true}
Everything else answers "{}" and never blocks.

Cursor names its own tools, so `hooks.json` has to name them too: the matcher on
`preToolUse` is a regex over the tool type, and Cursor's edit path is the `Write`
tool (its docs map Claude's `Edit` onto `Write`). The matcher therefore lists
`Write` plus the other spellings an edit tool is known by (`Edit`, `MultiEdit`,
`NotebookEdit`); without them the platform never runs this hook for a file write
and the gate's write branches - a test-skip marker added to a test file, a credit
line inside file content - cannot fire at all. Exactly which name a given Cursor
build sends is not verifiable from this repo, which is why the list is explicit
rather than a wildcard: a miss costs only that half of the gate, and an extra
alternative costs nothing because an unknown name passes the gate untouched.
"""
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.realpath(__file__))))
sys.path.insert(0, os.path.join(ROOT, "hooks"))
from tezgah_context import (  # noqa: E402
    command_text, context_for, record, shell_kind, slug, under)
from tezgah_gate import decision, explored  # noqa: E402
from tezgah_integrity import note, note_tool, stop_reason  # noqa: E402
from tezgah_paths import cache_dir, off  # noqa: E402

ALLOW = {"permission": "allow"}
GRAPH = ("search_graph", "trace_path", "search_code", "get_architecture",
         "detect_changes", "codebase-memory", "codebase_memory")
# Cursor tool names -> the shared gate's vocabulary. Keyed lowercase so a build
# that spells a tool either way maps to the same name; the write tools
# (`Write` and the other edit spellings) pass through unchanged, as the gate
# knows them already.
GATE_TOOLS = {"shell": "Bash", "read": "Read", "grep": "Grep"}


def gate_name(name):
    """The tool name the gate denies under and the ledger row records.

    `call_id` hashes the name it is handed, so mapping Cursor's `Shell` onto the
    gate's `Bash` on the PreToolUse side alone gives one call two ids: the
    PostToolUse row keeps the raw name, the loop guard reads a history that never
    matches, and it never denies. Both halves map through here."""
    return GATE_TOOLS.get(str(name or "").lower(), name)


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
    mcp_server_name.

    A shell call is the kind whose program actually ran (shell_kind), never a
    substring of the payload: naming `consult` in an argument is not using it,
    and the status mark turns green only on a real call."""
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
    if shell:
        # `afterShellExecution` carries the command on the event itself, a
        # postToolUse payload inside tool_input.
        return shell_kind(command_text(payload.get("command"))
                          or command_text(payload.get("tool_input")))
    return None


def gate_input(inp):
    """The tool input in the shared gate's vocabulary.

    Cursor's `Write` tool describes its change the way its `afterFileEdit`
    payload does - `edits: [{old_string, new_string}]` - while the gate reads the
    old_string/new_string pair, so fold the list into that shape. Every other
    field is passed through untouched."""
    edits = inp.get("edits")
    if not isinstance(edits, list):
        return inp
    out = dict(inp)
    for key in ("old_string", "new_string"):
        if not out.get(key):
            out[key] = "\n".join(str(e.get(key, "")) for e in edits
                                 if isinstance(e, dict))
    return out


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


def answer_path(session_id):
    """Where the last assistant text of a conversation is kept.

    Cursor's `stop` payload carries only `status`/`loop_count`, so the reply the
    Stop rule has to read arrives on the earlier `afterAgentResponse`, which
    documents `{"text": "<assistant final text>"}`. One file per conversation,
    overwritten."""
    return os.path.join(cache_dir(), "answer", slug(str(session_id or "nosession")))


def remember_answer(session_id, text):
    """Keep the reply `afterAgentResponse` handed over, best effort."""
    if not session_id or not text:
        return
    path = answer_path(session_id)
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w") as fh:
            fh.write(str(text)[-4000:])
    except OSError:
        pass


def last_answer(session_id):
    """The reply remembered for this conversation, or ""."""
    try:
        with open(answer_path(session_id)) as fh:
            return fh.read()
    except OSError:
        return ""


def main():
    try:
        payload = json.load(sys.stdin)
    except Exception:
        payload = {}
    if not isinstance(payload, dict):
        payload = {}
    event = payload.get("hook_event_name", "")
    cwd = cwd_of(payload)
    session_id = (payload.get("conversation_id") or payload.get("session_id")
                  or payload.get("parent_conversation_id"))
    kind = classify(payload, event)
    quiet = off("reminder-off")

    if event == "sessionStart":
        text = context_for("session_start", cwd, payload)
        out = {"additional_context": text} if text else {}
    elif event == "postToolUse":
        if kind:
            record(session_id, kind)
        # failed=None: this event carries no failure signal, so the row records a
        # check that ran - never a fabricated exit 0. The name and the input go
        # through the same mapping the gate saw, so one call hashes to one id.
        note_tool(session_id, gate_name(payload.get("tool_name", "")),
                  gate_input(payload.get("tool_input") or {}), failed=None)
        out = {}
        if (kind in ("cbm", "consult") and under(cwd) and not quiet
                and first_time(session_id, "graph")):
            out["additional_context"] = REINFORCE
    elif event == "postToolUseFailure":
        if kind:
            record(session_id, kind)
        note_tool(session_id, gate_name(payload.get("tool_name", "")),
                  gate_input(payload.get("tool_input") or {}), failed=True)
        out = {"additional_context": RECOVERY} if under(cwd) and not quiet else {}
    elif event in ("afterShellExecution", "afterMCPExecution", "afterFileEdit"):
        if kind:
            record(session_id, kind)
        if event == "afterFileEdit":
            note(session_id, "edit",
                 payload.get("file_path") or payload.get("path") or "")
        elif event == "afterShellExecution":
            # the command rides the event, not tool_input; the name is mapped so
            # this observer's row lands on the same id as the gated call, and
            # failed=None because the event carries no outcome
            note_tool(session_id, gate_name("shell"),
                      {"command": payload.get("command")
                       or (payload.get("tool_input") or {}).get("command", "")},
                      failed=None)
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
            # The delegate is a fresh context that must know the rules exist, so
            # it gets the same short brief every other host hands a subagent.
            # Cursor documents no context field on subagentStart (its output is
            # permission + user_message, which is user-facing and deny-only), so
            # the brief rides `additional_context` - the key Cursor uses for
            # "context to add to the conversation" on sessionStart and
            # postToolUse. Unverified for this event: a build that drops the
            # unknown key leaves the delegate with the session context it already
            # inherits, and the deny path above stays untouched either way.
            brief = context_for("subagent_start", cwd, payload)
            if brief:
                out["additional_context"] = brief
    elif event == "subagentStop":
        record(session_id, "orch")
        out = {}
    elif event == "preToolUse":
        tool = payload.get("tool_name", "")
        inp = payload.get("tool_input") or {}
        reason = decision(gate_name(tool), gate_input(inp), cwd, session_id)
        out = ({"permission": "deny", "agent_message": reason}
               if reason else dict(ALLOW))
    elif event == "afterAgentResponse":
        # the reply is only available here; `stop` reads it back
        remember_answer(session_id, payload.get("text") or "")
        out = {}
    elif event == "stop":
        # Cursor's Stop surface: the platform treats a "block" decision as an
        # automatic follow-up, and the native spelling is `followup_message`.
        # Only a finished turn is nudged - an aborted or errored one has no claim
        # to check - and `loop_count` is the platform's own cap on follow-ups.
        out = {}
        if (payload.get("status") in (None, "completed")
                and not payload.get("stop_hook_active") and not off("verify-off")
                and under(cwd)):
            reason = stop_reason(last_answer(session_id), session_id)
            if reason:
                out = {"decision": "block", "reason": reason}
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
