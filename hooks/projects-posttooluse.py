#!/usr/bin/env python3
"""Claude Code / dsh PostToolUse / PostToolUseFailure hook: record evidence, and
hand the model the provenance of the result it just read.

The Stop hook decides whether a "done/tested" turn is allowed to end by looking
at what actually ran, and that record has to be written here, from the tool
result, not from the reply. Inert outside a tezgah root.

The result is also where the untrusted-content control reaches the model.
`hookSpecificOutput.additionalContext` is read with the tool result - Claude Code
adds it as a system reminder alongside the result, and the dsh claude-code bridge
prepends the same string to the downstream contexts - so a fetched page or an MCP
answer is labelled in place, and an effect made in a turn that has already read
one is marked as such. dsh gets both halves through this file: it runs the same
script from hosts/dsh/hooks.json, and its bridge delivers PostToolUse context.
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.realpath(__file__)))
from tezgah_integrity import note_tool, untrusted_source  # noqa: E402
from tezgah_paths import root_for  # noqa: E402
from tezgah_untrusted import marks  # noqa: E402


def result_size(result):
    """The size of the tool result the host reported, or None when it carries
    none.

    Only a size is kept: the ledger records that a call returned something,
    never what it returned. The reader asks one question - is this non-zero -
    so a container is measured by its top-level length (O(1) for str, bytes,
    list, dict, set) instead of re-serializing it: `json.dumps` on every
    PostToolUse copied the whole tool response and broke plan 012's cost bound
    ("a sha1 over a short string and a few fields; nothing else"). ponytail: a
    dict result therefore reports its field count, not its byte length - the
    host reports no size of its own, and no reader compares the two."""
    if result is None:
        return None
    if isinstance(result, (str, bytes, bytearray, list, tuple, dict, set,
                           frozenset)):
        return len(result)
    return 1


def main():
    try:
        p = json.load(sys.stdin)
    except Exception:
        return
    if not isinstance(p, dict):
        return
    cwd = p.get("cwd") or os.getcwd()
    if not root_for(cwd):
        return
    event = p.get("hook_event_name") or "PostToolUse"
    tool = p.get("tool_name", "")
    inp = p.get("tool_input") or {}
    session_id = p.get("session_id")
    # A failure has no result and made no effect, and both lines assert one
    # ("this result came from ..."), so only PostToolUse shows them. The channel
    # is a property of the call either way, so the row keeps it on both events.
    # Read before this call's row lands: `source` on the row is the taint's own
    # mark, and `marks` answers about the turn the call arrived in.
    if event == "PostToolUse":
        source, notice = marks(tool, inp, session_id)
    else:
        source, notice = untrusted_source(tool, inp), None
    # Whether a successful PostToolUse means the call itself succeeded. Claude
    # splits a call's outcome across two events, so the event name carries it;
    # the dsh bridge collapses both into this one and its payload has no outcome
    # field (dsh's ToolExecutionResult is a success|failure union the bridge drops
    # on the floor), so the dsh manifest declares `none` in the environment and
    # every check there is recorded as one that RAN. A host whose failure is
    # written as a pass arms the Stop rule with the lie the ledger exists to
    # catch, so the declaration is the manifest's, not a guess from the shape of
    # a payload two hosts happen to share.
    if os.environ.get("TEZGAH_CALL_OUTCOME") == "none":
        failed = None
    else:
        failed = event == "PostToolUseFailure"
    note_tool(session_id, tool, inp,
              failed=failed,
              out_bytes=result_size(p.get("tool_response",
                                          p.get("tool_result"))),
              error=p.get("error"),
              cwd=cwd,
              source=source)
    if notice:
        json.dump({"hookSpecificOutput": {
            "hookEventName": event,
            "additionalContext": notice,
        }}, sys.stdout)


main()
