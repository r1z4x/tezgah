#!/usr/bin/env python3
"""Claude Code Stop / SubagentStop hook: refuse to end a turn on a false claim.

Blocks (decision: "block") when the final message opens by placating, or claims
done/tested/passing in a session whose newest turn changed code and left a check
failing or unproven by a later pass. An explicit "doğrulanmadı" always clears
it, so honest uncertainty is never punished. With `stop_hook_active` set - the
reply after a block - the reply is judged in record-only mode (an `after_block`
row) and never blocked again, and Claude Code overrides the hook after its own
consecutive-block cap, so this can never trap a session. A subagent's end
(SubagentStop) is judged record-only too: one `subagent_end` row, never a
block (ADR 011). Inert outside a tezgah root or under the `verify-off` kill
switch.
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.realpath(__file__)))
from tezgah_guard import safe  # noqa: E402
from tezgah_integrity import stop_reason  # noqa: E402
from tezgah_paths import off, root_for  # noqa: E402

# How many times one stop chain may be refused: the one-nudge semantics is
# deliberate, and raising it is owner decision 11. Claude says only whether a
# block came before (`stop_hook_active`), so a chain has blocked 0 or 1 times.
STOP_REASKS = 1


def main():
    try:
        p = json.load(sys.stdin)
    except Exception:
        return
    if not isinstance(p, dict):
        return
    if off("verify-off"):
        return
    cwd = p.get("cwd") or os.getcwd()
    if not root_for(cwd):
        return
    session_id = p.get("session_id")
    if p.get("hook_event_name") == "SubagentStop":
        safe(session_id, stop_reason, p.get("last_assistant_message"),
             session_id, cwd=cwd, subagent=True)
        return
    blocked = 1 if p.get("stop_hook_active") else 0
    # a core that cannot answer has refused nothing, so the turn ends: the rule
    # never traps a session, and that holds for its own failure too
    reason = safe(session_id, stop_reason, p.get("last_assistant_message"),
                  session_id, cwd=cwd, record_only=blocked >= STOP_REASKS)
    if reason:
        json.dump({"decision": "block", "reason": reason}, sys.stdout)


main()
