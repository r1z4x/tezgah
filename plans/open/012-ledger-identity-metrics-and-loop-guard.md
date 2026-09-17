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

1. **Ledger identity** (`note()` / `note_tool()` in
   `hooks/tezgah_integrity.py`): add `id`, `exit`,
   `out_bytes`, `fail_class`, `workspace` to every line.
   `id = sha1(tool + canonical args)[:12]`. `step` and `ms` are dropped with a
   reasoned docstring. **`trust` is struck from this list and deferred**, with
   its reason: it labels the provenance of the *content* a row is about (the
   study's P5, `user` / `tool` / `doc`), and no writer classifies content today,
   so shipping it now would mean guessing a label into the field the metrics
   then trust. The study keeps the primitive; the plan carries it as deferred
   until there is a writer that knows the answer.
2. **Trace metrics** (`counters()`, `bin/tezgah-status --counters`):
   `tool_error_rate`, `steps`, `false_completion`, `claims`. Token counts stay
   out: no host payload carries usage.
3. **Loop guard**: PreToolUse denies the third identical call whose previous
   attempts failed - one ceiling for every `fail_class`: the first two attempts
   pass, the third is refused, and the window resets per user turn.
   `fail_class` stays on the row as a metric and no longer gates the ceiling.
   Not ported to the opencode plugin, which writes the rows the guard reads but
   has no PreToolUse half: the plugin header and the README host table name that
   gap.
4. **Stop hardening**: the *evidence* side gets stricter, not the word list -
   a `verify_ok` only counts as support when `exit == 0`, the command was not
   masked by a pipe, and - when the host supplies a result size - that size is
   non-zero; and a blocked stop writes a `claim` row so the false-completion
   rate becomes measurable.

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
  before-number (`benchmarks/hook-latency/plan012-after.json`).

## Acceptance

- `python3 -m unittest discover -s tests` stays green (430 tests today).
- E1's twelve uncovered cases: the loop guard turns `p1` (repeated identical
  call) into a denial by the third attempt; nothing else changes.
- E2's corpus: the explicit family still blocks; `x3`/`x10` still escape (the
  word list is not the fix) - recorded, not hidden.
- `tezgah-status --counters` prints the four new numbers from a real session.
- A latency measurement exists and is committed
  (`benchmarks/hook-latency/plan012-after.json`, next to the baseline).

## Non-goals

Consent gate for irreversible actions, context summarisation, untrusted-input
labelling on the context side, token metrics. The study's synthesis carries the
reasoning, with one correction the census forced: the consent gate was deferred
on the belief that irreversible commands never happen, and the ledger census
found 65 of them in 6,771 rows (`to_human/blocks/E5-ledger-census/`). It stays
deferred because 63 of the 65 are `rm -rf` shapes whose context a 200-character
command cannot show, not because the frequency is zero.

## Evidence (landed 2026-09-17)

| claim | how it was checked | result |
|---|---|---|
| full suite | `python3 -m unittest discover -s tests`, run by the router after the review fixes | **482 tests, OK** (430 before plan 012, 458 after the first pass, 482 after the fixes) |
| loop guard denies the third identical failure | real hook pair, two `PostToolUseFailure` rows then a `PreToolUse` call whose command differs only in whitespace | `permissionDecision: deny` - "attempt 3 of an identical call whose 2 previous attempts exited 1"; the changed command passes; the deny row carries the same `id` and `workspace` |
| ledger identity | the smoke's rows | `{"kind":"verify_fail","id":"2c4914aeb4d1","exit":1,"out_bytes":18,"workspace":...}` |
| metrics surface | `bin/tezgah-status --counters <cwd> probe-hook-latency` over the ledger the latency probe's own hook runs wrote (24 rows, 23 `run` + 1 `claim`) | `steps 23` (the `run` rows; the `claim` row is not a step), `tool_error_rate 0.0`, `claims 1`, `false_completion 1` - the session's 23 identical Stop evaluations produced one `claim` row, not twenty-three |
| latency stays in budget | `python3 benchmarks/hook-latency/measure.py --n 20 --label plan012-after --out benchmarks/hook-latency/plan012-after.json` | pretooluse 42.40 -> 43.31, posttooluse 41.61 -> 42.59, stop 41.66 -> 42.13 ms (medians, n=20, against `baseline-plan012.json`; the largest move is 0.98 ms, inside the +5 ms bar) |
| quiet tool did not go blind | `probe.py` corrected and re-run (see the study's E2 analysis) | the probe had never measured the `verified` rows; the hardening made them block 8/10, and legacy rows are tolerated so an open session is not blocked on its own history |

Not done here and named rather than implied: no block has been re-run with the
controls verifiably armed (E4 is void), so the *effect* of any of this on work
quality is still unmeasured.

## Review fixes (2026-09-17)

An independent read-only review of this branch (`agent://FreshPlanReview`, 15
findings) changed the plan text itself where the scope and the prose had outrun
the code. Each line names the finding it answers:

| finding | change here |
|---|---|
| 2 - the ceiling is not the one README promised | one ceiling for every `fail_class`: the first two attempts pass, the third identical call whose previous attempts failed is refused, reset per user turn; `fail_class` is a metric only (Scope 3) |
| 4 - `out_bytes > 0` is not implemented and cannot be on the hosts that reach the Stop rule | the rule is "when the host supplies a result size, it must be non-zero" (Scope 4); the code keeps `!= 0`, and the E2 analysis sentence that claimed otherwise is corrected |
| 6 - `trust` from the field list appears nowhere | struck from Scope 1 and deferred with its reason (it labels content provenance and no writer classifies content), rather than written as a guess; the study's P5 keeps the primitive |
| 10 - the loop guard has no opencode half | stated as a gap in the plugin header and in the README host table (Scope 3) |
| 13 - the after-number was never committed | `benchmarks/hook-latency/plan012-after.json`, written by `measure.py --out` |
| 14, 8, 9 - three of the four counter descriptions were wrong | `steps` counts the work rows (`run`/`edit`/`verify*`), `tool_error_rate` is over the rows that carry an `exit` rather than over an exit of 0 or 1, and a `claim` row is keyed to the turn and the reply text so repeated Stop evaluations count once; the README says what each of the four counts |
| 15 - the two writers' ids can fork | the plugin's shell-tool set and number formatting are frozen to Python's, pinned by tests in `tests/test_opencode_plugin.py` |
