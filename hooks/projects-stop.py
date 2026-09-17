#!/usr/bin/env python3
"""Claude Code Stop hook: refuse to end a turn on a false claim.

Blocks (decision: "block") when the final message opens by placating, or claims
done/tested/passing in a session whose newest turn changed code and left a check
failing or unproven by a later pass. An explicit "doğrulanmadı" always clears
it, so honest uncertainty is never punished. `stop_hook_active` short-circuits
the loop, and Claude Code overrides the hook after its own consecutive-block
cap, so this can never trap a session. Inert outside a tezgah root or under the
`verify-off` kill switch.
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.realpath(__file__)))
from tezgah_integrity import stop_reason  # noqa: E402
from tezgah_paths import off, root_for  # noqa: E402


def main():
    try:
        p = json.load(sys.stdin)
    except Exception:
        return
    if not isinstance(p, dict) or p.get("stop_hook_active"):
        return
    if off("verify-off"):
        return
    cwd = p.get("cwd") or os.getcwd()
    if not root_for(cwd):
        return
    reason = stop_reason(p.get("last_assistant_message"), p.get("session_id"))
    if reason:
        json.dump({"decision": "block", "reason": reason}, sys.stdout)


main()
