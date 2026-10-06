#!/usr/bin/env python3
"""Claude Code hook: SessionStart, UserPromptSubmit, SubagentStart, PostCompact.

Emits the shared tezgah context (hooks/tezgah_context.py) for the session's
cwd when it resolves inside a configured root, and prints nothing outside them.
This file is only the Claude envelope; the contract itself lives in the core so
Codex, Cursor, opencode, dsh and omp inject the exact same text.
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.realpath(__file__)))
from tezgah_guard import import_failed, safe  # noqa: E402
try:
    import tezgah_attest  # noqa: E402
    from tezgah_context import context_for, record  # noqa: E402
    from tezgah_paths import HOST_DIRS  # noqa: E402
except Exception as exc:
    import_failed(exc)

EVENTS = {
    "SessionStart": "session_start",
    "UserPromptSubmit": "user_prompt",
    "SubagentStart": "subagent_start",
    "PostCompact": "post_compact",
}

# PostCompact is observed, not answered. A real compaction on Claude Code
# 2.1.283 (2026-09-30) showed what the host does with an envelope on
# this event: it REJECTS it - "Hook JSON output validation failed -
# hookSpecificOutput.hookEventName: expected one of "PreToolUse" |
# "UserPromptSubmit" | ... | "SessionStart" | ..." - reports the hook as failed,
# and prints the raw JSON, context text included, into the transcript the model
# reads next. The post-compaction context reaches the model through SessionStart,
# which fires again as `SessionStart:compact` and whose additionalContext was
# delivered in the same run. So on PostCompact this hook still builds the block -
# that is where `context_for` records the compaction (remember_compaction) - and
# prints nothing. Codex answers PostCompact from hosts/codex/hook.py, which
# prints no context on it either, and dsh's bridge does not carry the event.

# Claude's global memory file, where install_claude writes the always-on core as
# a managed block: the file Claude reads into every session, so the core is
# already in the session's instructions.
CORE_IN_FILE = os.path.join(HOST_DIRS["claude"], "CLAUDE.md")


def core_is_in_a_file():
    """True when the core reaches this session from a file the host keeps, so
    this hook must not pay for the contract a second time in its one message.

    The host declares it in its manifest (`TEZGAH_CORE_IN_FILE`, the same shape
    as the dsh rows' `TEZGAH_CALL_OUTCOME`) rather than this file guessing from
    the payload: dsh runs this very script through its claude-code bridge and has
    no such file, so its session still gets the core from here. The file is read
    as well as assumed - a user who deleted it falls back to the hook."""
    if os.environ.get("TEZGAH_CORE_IN_FILE") != "1":
        return False
    try:
        with open(CORE_IN_FILE, encoding="utf-8", errors="ignore") as fh:
            return "<!-- tezgah:start" in fh.read()
    except OSError:
        return False


def main():
    try:
        payload = json.load(sys.stdin)
    except Exception:
        payload = {}
    event = payload.get("hook_event_name") or "SessionStart"
    cwd = payload.get("cwd") or os.environ.get("CLAUDE_PROJECT_DIR") or os.getcwd()
    if event == "SubagentStart":
        # The status line's orch mark. This file is the only SubagentStart hook
        # tezgah wires, and dsh (which runs it too) has no transcript to derive
        # the kind from, so the store is the only channel its line has.
        safe(payload.get("session_id"), record, payload.get("session_id"), "orch")
    if event == "SessionStart":
        # Claude and dsh run this one script; Claude's manifest declares
        # TEZGAH_CORE_IN_FILE on SessionStart and dsh's does not, so the flag
        # names whose entries to attest. ponytail: a Claude manifest edited to
        # drop the flag is attested as dsh - and still reads as drift there.
        sid = payload.get("session_id")
        host = "claude" if os.environ.get("TEZGAH_CORE_IN_FILE") == "1" else "dsh"
        safe(sid, tezgah_attest.run, host, sid, cwd)
    text = safe(payload.get("session_id"), context_for,
                EVENTS.get(event, "session_start"), cwd, payload,
                # the brief is a subagent's own text, never the file's; every
                # other event drops the core when the host's file carries it
                with_core=(event == "SubagentStart" or not core_is_in_a_file()))
    if text and event != "PostCompact":
        json.dump({"hookSpecificOutput": {
            "hookEventName": event,
            "additionalContext": text,
        }}, sys.stdout)
    sys.exit(0)


main()
