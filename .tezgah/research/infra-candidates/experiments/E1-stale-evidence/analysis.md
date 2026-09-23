# E1 analysis

Rows here are scope: fixture (a seeded session ledger over the smoke tree - protocol.md: "Each cell seeds a ledger the way the writers record it"), except fix-1-ledger, derived from fix-1's ledger.

CONFIRMATORY (the change was made for this): cell `fix-1` blocks, with the new
reason class, naming the file written after the check, through the real hook. The
claim row carries `blocked: stale evidence`, so the refusal is readable from the
ledger without parsing the text.

CONFIRMATORY (no collateral): ctrl-A (verified tree) and ctrl-B (a write that
changed nothing) are allowed, so the rule is about *tree change*, not about
writes happening at all. ctrl-D shows the admission escape still works. ctrl-E
shows the old `no verify_ok` floor still owns its own case - the new branch did
not swallow it.

EXPLORATORY: ctrl-C. A reply that describes the state accurately without claiming
completion is still refused. That is the pre-existing design of trigger 4, which
E2 measured as evidence-shaped on purpose ("the same unfounded state stated as a
description"), and the escape is the same admission ctrl-D uses. Recorded rather
than changed: narrowing it to claim vocabulary would re-open the hole E2 closed.

Second run, same day: the branch was exercised through the other three blocking
adapters as well, because "four hosts block on it" is a claim about reachability
and one host's envelope does not prove it. The same seeded stale state was handed
to each adapter's own Stop payload:

| adapter | invocation | observed |
|---|---|---|
| `hooks/projects-stop.py` | Claude/dsh envelope | block, `Stale evidence` |
| `hosts/omp/hook.py` | `{"event": "stop", …}` | block, `Stale evidence` |
| `hosts/codex/hook.py` | `{"hook_event_name": "Stop", …}` | block, `Stale evidence` |
| `hosts/cursor/hook.py` | `afterAgentResponse` then `stop` | block on `stop`, `Stale evidence` |

Cursor needed two payloads because its Stop reads the reply remembered from
`afterAgentResponse`; the first call answered `{}` and the second blocked, which
is the adapter's documented flow, not a miss.


Coverage note: the JS mirror needs no change - opencode has no end-of-turn
surface, so the Stop rule exists once. `tests/test_integrity.py:StaleEvidence`
pins the four shapes in-process; the run itself went through the real hook, which
is what makes this more than a unit test.

Residual risk, named: ctrl-B depends on `changed: false` being recorded. A host
that reports no result, or a target that cannot be read, leaves the row with
neither `hash` nor `changed` (`_changed_write` returns False), so the rule fails
open there - deliberately, the same way `partial_state` refuses nothing on a
state it could not establish.
