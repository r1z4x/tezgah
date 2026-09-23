# E1 analysis - the corpus change, read on one arm

Status: the cell is complete (12 of 12 rows), the probe row is counted apart, and
**both predictions are falsified**. Every number below is read from
`results.jsonl` beside this file, whose `source` names the lab rows it folds
(`benchmarks/arm-bench/results/h06/opencode-bare.jsonl` and
`.../opencode-bare-proof.jsonl`), and the analyzer's own output is quoted where it
computes the endpoint independently.

## Result in one line

`opencode-bare` - the harness-free member of the pre-registered pair - **passed all
12 rows** of `h06-exact-split-sum` on `deepseek/deepseek-v4-flash`, 0 rows carry the
discriminating shape, CPS is $0.006389 and the cell spent $0.076672; the protocol's
own falsifier ("≥ 7 of 12 pass → the new task is not a discriminator") has
therefore fired, and the corpus change did **not** raise the share of tasks that
can discriminate - on this arm, `h06-exact-split-sum` is a saturated task.

## The cell, from the lab's own analyzer

```
$ python3 analyze.py 'results/h06/opencode-bare.jsonl'
rows: 12  cells: {('opencode', 'none'): 12}  model(s): ['deepseek/deepseek-v4-flash']
k = 12 (repeats [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12]), tasks = 1

| arm | n | pass | pass rate (Wilson 95%) | CPS | median cost | median in | median out | median cache | timeouts | no-usage | collateral |
| opencode-bare | 12 | 12 | 1.00 (0.76-1.00) | $0.0064 | $0.0064 | 35037 | 691 | 148032 | 0 | 0 | 0 |
| **total** | 12 | 12 | | **$0.0767** spent | | | | | | | |

per check (passed / run): split_sum 12/12 | suite 12/12
per family (passes / n, mean cost): hidden-invariant 12/12 ($0.0064)
failures (0):
```

## The 12 rows, one by one

The two checks are read apart, as section 3 of the protocol says, because the
"green suite, wrong contract" shape is the one this family exists to produce:

| repeat | pass | split_sum | suite | route | changed_files | wall (s) | cost ($) |
|---|---|---|---|---|---|---|---|
| 1 | pass | pass | pass | code | `inventory/allocate.py` | 13.7 | 0.005901 |
| 2 | pass | pass | pass | code | `inventory/allocate.py` | 17.0 | 0.006512 |
| 3 | pass | pass | pass | code | `inventory/allocate.py` | 15.6 | 0.006148 |
| 4 | pass | pass | pass | code | `inventory/allocate.py` | 18.0 | 0.006481 |
| 5 | pass | pass | pass | code | `inventory/allocate.py` | 15.2 | 0.006034 |
| 6 | pass | pass | pass | code | `inventory/allocate.py` | 18.1 | 0.006607 |
| 7 | pass | pass | pass | code | `inventory/allocate.py` | 15.5 | 0.005855 |
| 8 | pass | pass | pass | code | `inventory/allocate.py` | 19.5 | 0.006979 |
| 9 | pass | pass | pass | code | `inventory/allocate.py` | 15.1 | 0.006566 |
| 10 | pass | pass | pass | code | `inventory/allocate.py` | 18.0 | 0.006352 |
| 11 | pass | pass | pass | code | `inventory/allocate.py` | 20.3 | 0.006733 |
| 12 | pass | pass | pass | code | `inventory/allocate.py` | 17.5 | 0.006504 |

`collateral` is empty on all 12, no row timed out, every row carries `usage`,
`model deepseek/deepseek-v4-flash`, `host_version 1.18.31`, `prompt_sha256` and
`fixture_sha256`; every row's `changed_files` is exactly the one path the prompt
permits. Wall median 17.5 s; per-row cost between $0.005901 and $0.006979.

**The probe row, counted apart.** One row, taken before the cell, in
`results/h06/opencode-bare-proof.jsonl`: also a pass, both checks green, 21.2 s,
$0.006218. It is the path check, not a row of the cell - and it was the first
signal against prediction 1, reported here rather than folded into a threshold
that was already committed.

## The predictions, read against the numbers

| prediction | fixed before the run | observed | verdict |
|---|---|---|---|
| P1 rate | at most 3 of 12 pass | 12 of 12 (Wilson 95% 75.7-100.0) | **falsified** |
| P2 shape | at least 6 of 12 rows show `suite` green + `split_sum` failed + only the allowed file changed | 0 of 12 | **falsified** |
| P3 admissibility | provenance fields complete, no timeout, no collateral | 12 of 12 complete, 0 timeouts, 0 collateral | held |

The falsifier fixed for this outcome - "≥ 7 of 12 rows pass → the contract is
reachable without the behaviour the pair is supposed to differ in, the new task is
not a discriminator, and the corpus change bought a task that reads as saturated" -
has fired, and this file reports it as that rather than as a surprise. Prediction 2
failing at 0 of 12 is the same statement from the other side: not one row took the
plausible float route the fixture ships and the swept check catches.

## The sibling prior did not transfer - and the reason is not attributable here

The cell was spent on one number: `h02-half-up-money-contract` reads
opencode-bare **0/5** on `openrouter/deepseek/deepseek-v4-flash`
(`results/hard-cells/`). The same arm reads **12/12** on `h06` on the direct
provider. Three differences travel together and this cell cannot separate them:

- **The task's contract.** `h02`'s rule is a rounding rule whose plausible routes
  (float division then `round`, `round()` on cents) sit very close to the correct
  one; `h06`'s rule is a conservation property whose clauses - exact cents, sum
  exact, never increasing, spread at most one cent - name the implementation
  directly, so an agent that reads the prompt can write `divmod` on cents in one
  step. That is the likeliest reading, and it is a statement about the *task design*
  this line wrote, not about the arms.
- **The provider.** `deepseek/deepseek-v4-flash` served directly against the
  OpenRouter route of the same model name: routing, price and prompt caching can all
  differ, and the cell's own rows show a warm prefix (median 148,032 cache-read
  tokens against 691 output tokens). Named as a confound, not resolved.
- **The seed.** `h02`'s floor on that arm is five rows deep, and E8 section 3.5
  already says of it: "That 5-run seed is not significance and is not reported as
  one." This cell is what a fresh task says about it, and what it says is that the
  seed does not generalize to a second contract task on this arm.

So the honest reading is **two-sided and named that way**: the pre-registered
instrument did not discriminate where the seed said it would, and the reason cannot
be pinned to the task or to the provider by a single cell.

## Cost, and the ceiling

| item | number |
|---|---|
| cell rows | 12 |
| cell spend | **$0.076672** |
| probe row | 1 row, $0.006218 |
| **round spend** | **$0.082890** (13 rows) |
| CPS | $0.006389 (cell spend / 12 passes) |
| ceiling | $0.20 - under it by $0.117110 |

The figure is the sum of the rows' own `usage.cost`, which is what the host reported
per run. Cross-check, and its limit: the provider balance read before the round was
8.00 USD and reads 7.68 USD after it, a move of $0.32 - **the account is shared with
a sibling session** running its own block on the same credential, so the balance
delta is not this round's spend and the row sum is the number to quote.

## What this means for the adaptation, and what it does not

- **The corpus change did not move the number it was aimed at.** The line's claim
  C15 says the environment-side move acts on "the count of tasks in the corpus that
  can discriminate at all"; on this arm the new task is saturated, so that count is
  where it was. What the round bought is that fact, for $0.082890 - the alternative
  was a task sitting in the corpus looking discriminating because the fixture's
  hidden check separates five implementations (`selftest` cannot see the arm).
- **It does not show the harness has no effect.** One arm was run; the armed member
  of the pair was not, and nothing here bounds what an armed arm does on `h06`.
- **It does not refute the sibling.** `h02`'s 0/5 is a different task on a different
  provider; this cell neither replicates nor refutes it.
- **The task is not deleted or edited.** The lab's freeze rule is that rows exist,
  so a defect found later is fixed by adding a task id; `h06` stands as the record
  of what the sweep separates on the fixture side and of what the arm did with it.
  A harder sibling - a second clause the swept table separates, written as a new
  task id - is the next instrument this line would need before any arm-side claim
  about the corpus's headroom is worth making.

## Limits, in the layer's own terms

- **One arm, one task, one model, one provider, `k=12`.** The Wilson interval is
  75.7-100.0%: the cell bounds the rate from below, it does not establish a ceiling
  - a true rate of 0.75 sits inside it.
- **The armed half is unmeasured.** `opencode+tezgah` was never run on `h06`.
- **The probe row is one row and is counted apart**, so the 13-row file is not a
  13-row cell.
- **Scope.** The 13 rows declare `scope: real` - a paid run against a real provider
  at a real cost - while the environment they ran in is this line's own generated
  task fixture. The sibling experiment E2 declared the same kind of rows `fixture`
  for exactly that reason; both readings are defensible, the choice is named here,
  and a reader comparing the two lines should read them as the same kind of
  evidence, not two.
- **No human answers anything.** The bench grades the run's last tree; `h06` has no
  route that asks the user anything, so no row is a stop that a person would have
  answered.
