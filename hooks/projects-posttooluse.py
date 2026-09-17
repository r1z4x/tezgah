#!/usr/bin/env python3
"""Claude Code PostToolUse / PostToolUseFailure hook: record evidence.

The Stop hook decides whether a "done/tested" turn is allowed to end by looking
at what actually ran, and that record has to be written here, from the tool
result, not from the reply. Inert outside a tezgah root.
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.realpath(__file__)))
from tezgah_integrity import note_tool  # noqa: E402
from tezgah_paths import root_for  # noqa: E402


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
    note_tool(p.get("session_id"), p.get("tool_name", ""),
              p.get("tool_input") or {},
              failed=p.get("hook_event_name") == "PostToolUseFailure",
              out_bytes=result_size(p.get("tool_response",
                                          p.get("tool_result"))),
              error=p.get("error"),
              cwd=cwd)


main()
