#!/usr/bin/env python3
"""Claude Code Stop / SubagentStop hook: refuse to end a turn on a false claim.

Blocks (decision: "block") when the final message opens by placating, claims
done/tested/passing in a session whose newest turn changed code and left a check
failing or unproven by a later pass, or ends a turn that did work on a list of
what is left with an item no blocker accounts for (`residual work`). An explicit
"doğrulanmadı" clears only a claim whose repair is a check, and only after a
check that ran and failed since the newest change: the word alone used to clear
every refusal, so writing it was cheaper than verifying (plan 080). With
`stop_hook_active` set - the reply after a block - the reply is judged again:
it is refused once more only for a reason class this turn was not refused for
yet, at most two refusals per turn (`tezgah_integrity._record_only`, counted
from the ledger), and otherwise recorded as an `after_block` row. Claude Code
also overrides the hook after its own consecutive-block cap, so this can never
trap a session. A subagent's end (SubagentStop) is judged record-only: one
`subagent_end` row, never a block (ADR 011). Inert outside a tezgah root or
under the `verify-off` kill switch.
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.realpath(__file__)))
from tezgah_guard import import_failed, safe  # noqa: E402
try:
    from tezgah_integrity import bind_session, stop_reason  # noqa: E402
    from tezgah_paths import off, root_for  # noqa: E402
except Exception as exc:
    import_failed(exc)


def main():
    try:
        p = json.load(sys.stdin)
    except Exception:
        return
    if not isinstance(p, dict):
        return
    session_id = p.get("session_id")
    safe(session_id, bind_session, session_id)  # the switch latch (tezgah_paths.off)
    if off("verify-off"):
        return
    cwd = p.get("cwd") or os.getcwd()
    if not root_for(cwd):
        return
    if p.get("hook_event_name") == "SubagentStop":
        safe(session_id, stop_reason, p.get("last_assistant_message"),
             session_id, cwd=cwd, subagent=True, agent=p.get("agent_id"))
        return
    # a core that cannot answer has refused nothing, so the turn ends: the rule
    # never traps a session, and that holds for its own failure too
    reason = safe(session_id, stop_reason, p.get("last_assistant_message"),
                  session_id, cwd=cwd, after_block=bool(p.get("stop_hook_active")))
    if reason:
        json.dump({"decision": "block", "reason": reason}, sys.stdout)


main()
