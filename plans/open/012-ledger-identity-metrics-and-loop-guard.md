# 012 - Ledger identity, trace metrics and the loop guard

Status: open
Branch: `plan/012-ledger-identity-metrics-and-loop-guard`

## Why

The failure-mode study (branch `research/agent-failure-controls`, report at
`.tezgah/research/agent-failure-controls/to_human/agent-failure-controls.md`)
measured what the harness enforces and what it does not:

- the PreToolUse gate refuses 7/7 pre-registered write-time violations and 0/12
  trajectory-time cases (E1);
- the Stop rule refuses 8/10 explicit completion claims and 0/10 implicit ones,
  and one negation word anywhere clears it (E2);
- the ledger line carries `{kind, ts, detail<=200}` - no action identity, no
  sequence, no structured exit status, no result size (E1/E4);
- the tenth priority control (per-trace metrics) exists only in the benchmark,
  not in the live harness.

The effect block (E4) could not show an effect for the mechanical controls, and
its own validity is in question: no ledger file was written during the block.

## Scope

Four changes, in dependency order:

1. **Ledger identity** (`hooks/tezgah_integrity.py:113-124`): add `id`, `step`,
   `exit`, `out_bytes`, `fail_class`, `trust`, `ms`, `workspace` to every line.
   `id = sha1(tool + canonical args)[:12]`.
2. **Trace metrics** (`counters()`, `bin/tezgah-status --counters`):
   `tool_error_rate`, `steps`, `false_completion`, `claims`. Token counts stay
   out: no host payload carries usage.
3. **Loop guard**: PreToolUse denies a call whose `(tool, id)` already failed -
   ceiling 2 for a transient `fail_class`, 1 otherwise, reset per user turn.
4. **Stop hardening**: the *evidence* side gets stricter, not the word list -
   a `verify_ok` only counts as support when `exit == 0`, `out_bytes > 0` and the
   command was not masked by a pipe; and a blocked stop writes a `claim` row so
   the false-completion rate becomes measurable.

## Performance budget (the constraint that shapes the design)

Hook latency is already the dominant tezgah cost on omp: ~19 ms Python start
plus ~24-25 ms per gated tool call, ~50-81 ms at session start (README, measured
on this machine). Adding rules must not move those numbers materially.

- PreToolUse may read **only the ledger tail** (last 200 lines), never the whole
  file. No new subprocess, no network, no lock on the read path.
- PostToolUse adds a sha1 over a short string and a few fields; nothing else.
- Acceptance: median gated tool call < 35 ms over 20 calls on this machine, and
  a written measurement committed next to it.

## Acceptance

- `python3 -m unittest discover -s tests` stays green (430 tests today).
- E1's twelve uncovered cases: the loop guard turns `p1` (repeated identical
  call) into a denial by the third attempt; nothing else changes.
- E2's corpus: the explicit family still blocks; `x3`/`x10` still escape (the
  word list is not the fix) - recorded, not hidden.
- `tezgah-status --counters` prints the four new numbers from a real session.
- A latency measurement exists and is committed.

## Non-goals

Consent gate for irreversible actions (measured frequency first), context
summarisation, untrusted-input labelling on the context side, token metrics.
See the study's synthesis for why each is deferred.
