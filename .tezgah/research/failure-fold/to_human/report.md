# failure-fold — the drift refusal's first round, and what it could not see

Line: `.tezgah/research/failure-fold/`. Question: *does removing the `drift`
refusal and delivering the same notice on the tool-result channel drive `drift`
deny rows to zero without raising the real-work blocked-claim rate above its
2026-09-20 value of 0.5345?*

The line is closed at `phase: concluded` because its work is terminal — a
pre-registered protocol, one round, and the corpus folds the protocol asked for
— **not** because the question was answered. Its one hypothesis stays `untested`
and prediction (c) stays undecided; both are named below as limits rather than
dressed as results.

## The verdict in one line

**An untested factor, not a null.** The change's mechanism is verified at the
round's own window — the notice is produced and nothing is refused — but the
round's arms never reached the rule's threshold (`DRIFT_STEPS = 25` work rows in
one turn), so no arm could fire the rule and the round is blind to the change's
effect. The counter-metric is undecided at n=12 and stays on watch.

## What ran, and what it cost

The pair `omp-drift-notice` / `omp-drift-notice-pre` on
`h01-exhaustive-callsite-audit`, `k=25` per arm, one model family
(`openrouter/deepseek/deepseek-v4-flash`), one cell per arm, run 2026-09-20 after
the protocol was committed (`0c794d0`) and the change landed (`d4878ae`).

| cell | rows | pass | `session_rows` per row |
|---|---|---|---|
| `omp-drift-notice` | 25 | 25 | 4..15 |
| `omp-drift-notice-pre` | 25 | 25 | 4..15 |

Cost from the rows' own `usage`: $0.0336 + $0.0379 = $0.0715 for 50 runs
(~$0.0014 per run), against the lab's published $0.0050-$0.0097 per run. Wall
clock 3615 s and 4122 s, the two cells in parallel.

## Prediction by prediction

- **(1) no `drift` refusal is written any more — mechanism verified, effect
  unmeasured.** Over the 30 ledgers modified in the two hours the round ran the
  corpus holds **49 `drift` marker rows and 0 `drift` deny rows**: the notice is
  produced and nothing is refused. But none of those rows belongs to the round's
  own arms — `session_rows` of 4-15 means a run's whole session holds fewer rows
  than the rule's threshold needs in one turn, so the rule could not fire in
  either arm. The pre arm produced no long-turn deny either, which is what makes
  this an untested factor rather than a clean before/after; the 49 markers come
  from real sessions on this machine running the new code.
- **(2) the notice is still produced — floor met at the producer.** 248 of 308
  real-work turns of >= 25 work rows carry a `drift` marker, against the
  pre-registered floor of 200 of ~272. This is a floor on production, not a
  before/after: the marker row existed before the change too, so it says the
  notice keeps being produced at the rate it was, and nothing more.
- **(3) the counter-metric does not move up — undecided.** After the change the
  real-work blocked-claim rate reads 8/12 = 0.6667 against the 0.5345 floor, but
  the 95% interval spans the floor, so n=12 cannot settle it. The pre-change
  comparison reads 124/231 = 0.5368. Prediction (c) is the one that can end the
  change, and it is on watch: re-measure when the after-sample reaches ~50
  claims; a rate still above 0.5345 ends the line — record the null and revert,
  do not explain it.
- **(4) no completion cost — null at this instrument.** 25/25 against 25/25
  with no failed check in either arm (`stop_classes` carries the lab's own
  `no verify_ok` floor on some rows in both), so this cell cannot show a
  completion cost either way.

## What the round established

- The pairing was **armed**: `session_rows` 4-15 in both arms means the bridge,
  the gate and the ledger all loaded, which is the change's first acceptance.
- The change's **mechanism is live in real work**: 49 notices, 0 denials, and the
  marker row moved with the notice to the post-tool path.
- The **cost of the round is measured** ($0.0715 for 50 runs) and the pass rate is
  unmoved at this instrument.
- The **counter-metric is scoped and pre-registered** before it was read, so the
  re-measure is a comparison and not a re-definition.

## What the evidence does not show

- **No effect size, and nothing about delivery.** The line's own assumption, that
  a host shows the model the post-tool field, is read in this repository's code and
  never exercised against a live host here; the marker row is a receipt of
  production and handover, not of a read. The round therefore cannot say the
  notice is better or worse for the work than the refusal was.
- **The instrument this rule needs is not this line's to build.** The task must
  force >= 25 work rows into one turn; this task's sessions are shorter than the
  threshold in both arms, and the protocol already recorded that the lab measures
  bounded tasks and does not measure long-horizon behaviour. The corpus's headroom
  — a task that can reach the threshold — is plan 009's deliverable, so this line
  could not have run the round that would answer its own question.
- **The raw cell files are not in the repository.** Every round row's `source`
  names `results/e9-drift-notice/*.jsonl`, and no such path is in the tree, so a
  reader cannot re-fold the cells from the line's own files; what the line holds
  is the fold's rows in `experiments/drift-notice/results.jsonl` and the analysis
  in `analysis.md`.
- **The line never reached a second round.** One round, one task family, one
  model family: the lab's own result is a null pooled over two families with a
  sign flip between them, so a single family is not evidence for another, and
  prediction (c)'s after-sample is still at n=12.
- **The completion cost is not bounded in real work.** The paid round was the
  only place a cost could appear, and it read 25/25 against 25/25 with no failed
  check, which is a null at an instrument that could not see the factor.
- **The corpus-wide fold is not the metric and was not used as one.** It holds
  the pre-change history and can only decay; every post-change read in this line
  is taken on ledgers dated after the commit or on the round's own window.
- **One prediction row predates the component rule**: `predictions.jsonl`'s first
  row names no `components`, so which component that prediction moves is
  unverified in the file, even though the round's own second row names
  `drift-notice`.

## What now works, and what is on watch

The refusal is gone on the wired hosts and the same text arrives with the tool
result; the marker row still records every turn that drifted. What decides whether
the change stays is prediction (c): re-measured at ~50 after-claims, a rate still
above 0.5345 ends the line with a revert rather than an explanation. Until then the
change stands on its mechanism and on a measured cost of zero at this instrument —
not on a demonstrated improvement.
