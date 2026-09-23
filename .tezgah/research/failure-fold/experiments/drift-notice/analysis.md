# drift-notice - what the round measured, and what it could not

Run 2026-09-20, after the protocol in this directory was committed (`0c794d0`)
and the change landed (`d4878ae`). The round is the pair
`omp-drift-notice` / `omp-drift-notice-pre` on `h01-exhaustive-callsite-audit`,
`k=25` per arm, one model family (`openrouter/deepseek/deepseek-v4-flash`),
one cell per arm.

## The verdict in one line

**Untested factor, not a null.** The arms' own sessions never reached the rule's
threshold, so this instrument cannot see the change; what the round does establish
is that the pairing is armed (`session_rows` 4-15 in both arms, so the bridge, the
gate and the ledger all loaded) and that the pass rate is unmoved (25/25 against
25/25, no measured completion cost).

## What ran, and what it cost

| cell | rows | pass | `session_rows` per row |
|---|---|---|---|
| `omp-drift-notice` | 25 | 25 | 4..15 |
| `omp-drift-notice-pre` | 25 | 25 | 4..15 |

Cost, from the rows' own `usage`: **$0.0336 + $0.0379 = $0.0715** for 50 runs
(~$0.0014 per run), against the lab's published $0.0050-$0.0097 per run. Wall
clock: 3615 s and 4122 s, the two cells run in parallel.

## Prediction 1 - the `drift` deny row count reaches 0

Read from the machine's ledgers rather than from a hand-kept file: over the 30
ledgers modified in the two hours the round ran, **49 `drift` marker rows and 0
`drift` deny rows**. The notice is produced and nothing is refused.

**But the round's own arms carry none of them.** `session_rows` of 4-15 means a run's
whole session holds fewer rows than `DRIFT_STEPS` (25) needs in one turn, so the
rule could not fire in either arm: the pre arm produced no `Long turn` deny either,
which is what makes this an untested factor rather than a clean before/after. The
49 markers come from real sessions on this machine running the new code (this
analysis session and its subagents among them), which is the mechanism working -
not a controlled comparison.

`fold_ledgers.py` over both cells agrees: `meas = 0`, `n/a` for every shape column,
`no ledger for <arm> rNN` for all 50 rows - the runs' ledgers are not resolvable
from the results rows for this task, so the fold's outcome variables do not exist
for this cell. That is the instrument's limit, named here rather than papered over.

## Prediction 2 - the notice's reach in real work

**Unmeasured.** It is a fold of the corpus over turns of >= 25 work rows taken after
the change has been in use; the 200-of-~272 floor is pre-registered and this session
has no such population yet.

## Prediction 3 - the completion cost

**Null at this instrument.** 25/25 against 25/25 with no failed check in either arm
(`stop_classes` is `no verify_ok: 1` on some rows in both, the lab's own floor), so
this cell cannot show a completion cost either way. The real-work counter-metric
(blocked claims over `/Users/rizax/Projects` ledgers, floor 0.5345) is unmeasured
for the same reason as prediction 2.

## What this round does not show

- No effect size, and no evidence that the notice is better or worse for the work
  than the refusal was.
- Nothing about a second model family: one family ran.
- Nothing about long-horizon behaviour: this task's sessions are shorter than the
  rule's threshold, so the task was the wrong instrument. A task that forces >= 25
  work rows in one turn is the instrument this rule needs - which is what plan 009
  (the corpus's headroom) exists to author.

## Next

The decision rests on the two corpus folds (predictions 2 and 3), which are free and
need traffic; or on a task from plan 009 that can actually reach the threshold. Until
one of those runs, the change stands on its mechanism (verified: 49 notices, 0
denials, and the unit tests per host) and on a measured cost of zero at this
instrument - not on a demonstrated improvement.

## The two corpus folds, measured 2026-09-20 (free)

Run by the parent over `~/.cache/tezgah/evidence`, real-work ledgers only
(`workspace` under `/Users/rizax/Projects`; 482 ledgers):

| prediction | value | floor | verdict |
|---|---|---|---|
| (b) drift markers over turns with >= 25 work rows | **248 of 308 turns** | >= 200 of ~272 | **met** - the notice is still produced |
| (c) real-work blocked-claim rate, after the change | 8/12 = **0.6667** | <= 0.5345 | **undecided**: n=12, and the 95% interval spans the floor |
| (c) the same, before the change (the comparison) | 124/231 = **0.5368** | - | the baseline the floor was taken from |

Prediction (b) is a floor on the producer, not a before/after: the marker row existed
before the change too (the change moved the delivery, not the marker), so 248 of 308
says the notice keeps being produced at the rate it was.

Prediction (c) is the one that can end the change, and it is on watch: the point
estimate is above the floor on a sample of twelve claims. Re-measure when the
after-sample reaches ~50 claims; a rate still above 0.5345 ends the line - record the
null and revert, do not explain it.
