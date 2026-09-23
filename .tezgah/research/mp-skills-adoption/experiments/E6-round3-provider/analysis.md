# E6 analysis — round 3 ran, and the clause changed nothing measurable

Raw: `raw/3eb8b9f8-….log` (the run's own log, filed as the receipt) and the rows
under `…/local-runs/3eb8b9f8-…/repo/benchmarks/arm-bench/results/orx/nogit/*.jsonl`,
folded with the lab's own `bench.py report`.

Round 3 is the first round that asked the question of a model: 300 rows, three arms,
**zero-usage 0 / 300**, no `not armed` line, total cost **$1.0997**.

## Verdicts, by the protocol's own words

| | prediction | outcome |
|---|---|---|
| **P1** | all three arms write 100 rows and every row carries non-zero usage | **CONFIRMED** — 100/100/100 rows, 0 zero-usage rows |
| **P2** | the treatment's false-completion share is below the armed control's | **FALSIFIED** — both are 1.000 |
| **P3** | the treatment's timeout-excluded pass rate is not below the control's | **CONFIRMED** — 94.0% against 89.0% |

## The numbers

| arm | runs | pass | pass% (Wilson) | timeouts | median wall | cost | cost/pass | refusals |
|---|---|---|---|---|---|---|---|---|
| `omp+tezgah` (armed control) | 100 | 89 | 89.0 (81.4-93.7) | 10 | 50 s | $0.4498 | $0.00505 | 74 (73 `no verify_ok`, 1 `check failed`) |
| `omp-bare` (anchor) | 100 | 93 | 93.0 (86.3-96.6) | 0 | 17 s | $0.2788 | $0.00300 | 0 (no session) |
| `orx-mp-prove` (treatment) | 100 | **94** | **94.0 (87.5-97.2)** | 5 | 51 s | $0.3711 | $0.00395 | **74** (74 `no verify_ok`) |

Per task: `e01-silent-one-liner` 47 / 43 / 44; `e05-three-call-sites` 42 / 50 / 50.
Paired against the anchor: the control **−0.040**, the treatment **+0.010**.

False completion, the lab's own metric (`bench.py:885`, `claims` from
`hooks/tezgah_integrity.py`, over failed runs that produced a final message):
**1.000 / 1.000 / 1.000** — and that is the finding about the metric, not the clause.
The denominators are **1, 7 and 1**: six of the treatment's six failed runs and ten
of the control's eleven wrote no final message at all, so the share is computed over
one run per armed arm. A metric whose denominator is 1 cannot separate two arms, and
P2's falsification is therefore **a tie on denominators that could not have shown a
difference** — reported as the falsification the protocol asked for, with the reason
it is thin.

## What the round does establish

- **The clause does not cost passes.** 94.0% against 89.0%, on 100 repeats each; the
  intervals overlap (87.5-97.2 against 81.4-93.7), so this is "not worse", not
  "better" — which is exactly what P3 asked.
- **The clause does not change the harness's refusal behaviour.** Both armed arms
  fired the Stop rule **74** times; the treatment's class map is the cleaner one
  (74 `no verify_ok`, no `check failed`), the control's carries one `check failed`.
  A clause about proving a check would show up here first, and it does not.
- **The route change is not cosmetic, and the rounds are not comparable.** The
  anchor passed 93 of 100 here against 25 of 100 in round 1, and the median run is
  17-51 s against 267.7 s. Round 3's absolute numbers live in their own space, as
  its protocol says; what round 3 answers is the **within-run** contrast, which is
  what the clause's question needed.
- **The harness costs what the pilot measured.** Cost per solved task: $0.00505
  (control) and $0.00395 (treatment) against the bare anchor's $0.00300.

## What this does not show

- **Six of seven predictions' worth of headroom is gone.** E4 measured the rule
  absent from the contract; round 3 measures that adding it moves nothing this
  instrument can see. Neither says the clause is useless — it says this corpus
  (two tasks, one model route) cannot price it.
- **The false-completion metric is not usable at this label rate.** 17 of 24 failed
  armed runs across the two armed arms wrote no final message; until the runner
  captures replies for them, that column measures the capture, not the behaviour.
- **Nothing here is comparable to rounds 1-2** (different route, and round 1's
  ceiling), and nothing here revises them.
