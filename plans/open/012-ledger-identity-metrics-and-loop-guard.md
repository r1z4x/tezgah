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
- Acceptance is **relative**, because the baseline is already high:
  `python3 benchmarks/hook-latency/measure.py` on this machine before any change
  measured pretooluse 42.40 ms, posttooluse 41.61 ms, stop 41.66 ms (medians,
  n=20) against a 20.05 ms interpreter floor. Each hook's median must stay within
  **+5 ms** of those figures, and the after-number is committed next to the
  before-number.

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

## Evidence (landed 2026-09-17)

| claim | how it was checked | result |
|---|---|---|
| full suite | `python3 -m unittest discover -s tests` | 458 tests, OK (was 430 before the new tests) |
| loop guard denies the third identical failure | real hook pair, two `PostToolUseFailure` rows then a `PreToolUse` call whose command differs only in whitespace | `permissionDecision: deny` - "attempt 3 of an identical call whose 2 previous attempts exited 1"; the changed command passes; the deny row carries the same `id` and `workspace` |
| ledger identity | the smoke's rows | `{"kind":"verify_fail","id":"2c4914aeb4d1","exit":1,"out_bytes":18,"workspace":...}` |
| metrics surface | `bin/tezgah-status --counters <cwd> <session>` on a live session | `steps 241`, `tool_error_rate 0.0`, `claims 0`, `false_completion 0` |
| latency stays in budget | `benchmarks/hook-latency/measure.py --n 20` before and after | pretooluse 42.40 -> 42.68, posttooluse 41.61 -> 43.22, stop 41.66 -> 43.79 ms (medians; all inside the +5 ms bar) |
| quiet tool did not go blind | `probe.py` corrected and re-run (see the study's E2 analysis) | the probe had never measured the `verified` rows; the hardening made them block 8/10, and legacy rows are tolerated so an open session is not blocked on its own history |

Not done here and named rather than implied: no block has been re-run with the
controls verifiably armed (E4 is void), so the *effect* of any of this on work
quality is still unmeasured.
