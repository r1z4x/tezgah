# E1 protocol - the corpus change that can discriminate (h06)

Status: **pre-registered design, frozen before any run; the run could not start on
OpenRouter and resumes on the DeepSeek direct provider (amendment 1, section 12).**
Nothing in sections 1-11 has been executed: no model call, no `bench.py run`,
nothing spent there (2026-09-22). The OpenRouter account's credit is exhausted
(`total_credits 130` against `total_usage 130.18`; the key's visible
`limit_remaining 4.3152` is a sub-limit, not account credit), and a sibling session
on the same account had every row return HTTP 402 with nothing spent. The parent
approved the provider switch, the DeepSeek direct balance answers `is_available
true`, and amendment 1 changes the provider and nothing else. Everything quoted
below is read from a file in this tree, and each figure names where it comes from.
The free proofs in section 5 *were* run, because the layer's own rule is that a
fixture is well-formed only if `selftest` says so before anything is spent.

The change under measurement is a **corpus change**: one new task in
`benchmarks/arm-bench` whose hidden verifier is a swept property over the
documented contract. Its artifact and its rationale are item (a) of
`findings.md`, the environment-side adaptation of the env-scaling line.

## 1. What is measured, in one line

On the task the corpus change adds, run by the harness-free member of the pair
whose sibling cell already separates: does the run's answer honour the documented
contract, or does it only look even - read as a pass rate on one arm, with the
shape of each failure read apart from the rate.

## 2. Why this change, and why it is the cheapest one that can discriminate

The line's own words, from `findings.md` item (a) of *What is actually adaptable
here*:

> *Artifact it would touch:* `benchmarks/arm-bench` on branch `benchmarks/lab` -
> the task corpus (`tasks/<id>/meta.json` holds the `allow` list and the hidden
> checks), the pre-registrations, and the attribution gate that the `E8`
> pre-registration adds.

> *Number it would move:* the count of tasks in the corpus that can discriminate
> at all. The README's own reading is that "22 of the pilot's 25 tasks were
> saturated ... so four to six tasks carry all the signal", and the four hard
> tasks were added for exactly that reason. Shaping the environment - deepening a
> fixture, adding a hidden invariant, or replacing a saturated task - raises the
> unsaturated share, which is the denominator under every pass rate the lab
> reports.

This round takes the **adding a hidden invariant** shape, because it is the one
the same line names as the cheapest lever of the set: `findings.md`'s pattern C10
is "The cheapest environment-side lever in the set is the verifier, not the
environment count" (`literature/2504.07164-r2e-gym.md`'s hybrid verifier, RIVER's
rubric filter, Echoverse's grounded grader). Nothing here trains anything, and
the line's own prerequisite table records why the training half was never
available.

**Why this task, and not the alternatives.** Each alternative is refused on a
number already in the tree, not on taste:

| candidate | why it is not the cheapest that can discriminate | source |
|---|---|---|
| a fourth `gate-*` task (shortcut temptation) | the family measured no separation in either direction: `g01` "caught nobody" (every arm fixed the implementation and left `tests/` byte-identical), `g02` "caught everybody" (all twelve runs amended the spec), `g03` 3/3 in all four arms. E8 excluded all three by name. | `README.md` gate-family section; `PREREGISTRATION-E8.md` section 4 |
| another `h0*` hard task at the same shape | the hard family is the lab's published null: pooled over two model families three arms land on 40/50, and the per-model harness delta flips sign | `README.md` hard-family section |
| a task on the `refusal-stop` factor (`u02`/`u03`) | the family already discriminates, so a new instance adds `n` rather than capability: E7c read 24/25 obeyed against 1/25, `u03` read 10/10 against 1/10 | `PREREGISTRATION-E8.md` section 3.2; `results/e10-u03/` |
| **a second `hidden-invariant` task on the one pair with a published floor** | taken | `results/hard-cells/h02-*.jsonl` |

The pair and its floor, counted from the result files and not from prose: on
`openrouter/deepseek/deepseek-v4-flash`, `h02-half-up-money-contract` reads
omp+tezgah 5/5, omp-bare 5/5, opencode+tezgah 5/5 and **opencode-bare 0/5**
(`results/hard-cells/`). The task family is exactly the one this change extends:
the visible suite is green before and after and only a documented rule separates a
real fix from a plausible one. `h02` is a single family's seed - E8 section 3.5
says so itself ("That 5-run seed is not significance and is not reported as one")
- which is the reason a fresh cell on a fresh task is worth its money: it either
reproduces the floor on a second task or it does not.

**Why one arm and one task is the cheapest read.** The floor member alone is the
load-bearing half: a task on which the harness-free arm fails is a task that can
discriminate, and the armed half of the contrast is the sibling's published 5/5.
A paired cell costs twice as much and still cannot be read inside this round's
ceiling, so it is named as the next cell rather than run here (section 8).

## 3. The change, on disk (uncommitted)

Worktree: `/Users/rizax/orca/workspaces/tezgah/envscale-adapt`, branch
`benchmarks/envscale-adapt`, cut from `benchmarks/lab` at `dd2c60d`. It was created
under `/tmp` and moved to that durable path with `git worktree move` once it was
clear no paid run would follow, so the uncommitted task files survive a reboot. The
lab's own worktree, `/Users/rizax/orca/workspaces/tezgah/armbench`, is another
session's and was not touched.

```
benchmarks/arm-bench/tasks/h06-exact-split-sum/
  prompt.md                  the contract, the one-file constraint, the suite command
  meta.json                  allow, the two checks, routes, the factor block (E8's gate)
  fixture/                   README.md, inventory/{__init__,allocate}.py, tests/test_allocate.py
  hidden/check_split_sum.py  the swept property: 2,828 cells
  gold/inventory/allocate.py the exact-cents reference
```

- **Family** `hidden-invariant`; `fixture_dir` is the task's own `fixture/`, so
  the shared corpus at `corpus/inventory` is untouched and no published row's
  `fixture_sha256` moves.
- **The fixture's `allocate` is the plausible wrong answer**: one rounded share
  repeated, `[round(total/parts, 2)] * parts`, which looks even and loses cents.
- **The visible suite is green before and after** - `tests/test_allocate.py` pins
  only divisible totals (9.0/3, 5.0/2, 7.0/1). That is h02's design rule: "the
  visible suite passes before and after, so only the documented rule separates a
  real fix from a plausible one".
- **The hidden check is a property, not a table**: five clauses (exactly `parts`
  amounts; every amount an exact cent amount; the amounts sum to the total;
  they never increase; no two differ by more than one cent) evaluated over every
  total from 1 to 400 cents at one-cent resolution, every part count from 1 to 7,
  plus 999, 1999, 12345 and 99999 cents - one failing cell fails the check. The
  clauses determine the answer **uniquely**, so the check scores the contract and
  not a house style.
- The contract lives in `prompt.md` (h02's shape), never in the fixture, and no
  hidden check is named in it.

## 4. What the round is not

- It is not a harness measurement: one arm is run, so no arm-versus-arm claim is
  produced here.
- It is not a corpus-wide pass rate: the corpus is 48 tasks and this round adds
  one cell.
- It is not a task-defect calibration on its own: the within-row shape (section 6)
  is what separates "the contract decided this row" from "nothing was attempted".

## 5. Free well-formedness proof, run before any spend

```
$ python3 bench.py selftest --task h06-exact-split-sum
  ok   h06-exact-split-sum      baseline=fail gold=pass checks=2/2

1/1 fixtures discriminate
```
and the corpus-wide pass, unchanged otherwise:
```
$ python3 bench.py selftest
  skip c04-turkish-explain-readonly grades the reply, not the tree
  skip g02-conflicting-ask      grades the reply, not the tree

48/48 fixtures discriminate
```
(the branch carried 47/47 before this task; the two skips are the reply-grading
tasks `README.md` names).

The two checks read apart, which is the property this family turns on - the visible
suite is green on the baseline *and* on the gold tree, and only the hidden check
moves:
```
$ python3 bench.py prepare --task h06-exact-split-sum --out /tmp/h06-base
$ python3 bench.py grade --task h06-exact-split-sum --dir /tmp/h06-base
baseline pass: False | route: none | changed: [] | reasons: ['check failed: split_sum']
    split_sum passed= False | 1044/2828 cells honour the contract
    suite     passed= True
$ python3 bench.py grade --task h06-exact-split-sum --dir <gold overlaid tree>
gold: pass= True route= code collateral= []
    split_sum passed= True | 2828/2828 cells honour the contract
    suite     passed= True
```

The arm pre-flight is free and both members pass it:
```
$ python3 -c "import bench; print(bench.preflight(bench.arms_by_name()['opencode-bare']))"
(True, ['opencode-bare: harness none - the agent-dir pre-flight covers omp arms only'])
```
and the exact command the cell would run, printed by `--dry-run` with no model call
(this was the last step taken before the credit check, so it is the command as it
stood on disk):
```
$ cd /Users/rizax/orca/workspaces/tezgah/envscale-adapt/benchmarks/arm-bench
$ python3 bench.py run --arm opencode-bare --task h06-exact-split-sum \
    --model openrouter/deepseek/deepseek-v4-flash --repeat-from 1 --repeat 1 \
    --timeout 600 --results results/h06/opencode-bare.jsonl --dry-run
opencode-bare: harness none - the agent-dir pre-flight covers omp arms only
opencode run --format json --dir /Users/rizax/orca/workspaces/tezgah/envscale-adapt/benchmarks/arm-bench/.runs/armbench-h06-exact-split-sum-c5_s7159/repo --model openrouter/deepseek/deepseek-v4-flash <prompt>
```

**The check separates the routes, measured rather than asserted.** A throwaway
script evaluated seven candidate `allocate` implementations against the same
clauses over the same grid (`/tmp/route-sweep.py`, not committed; this is its
output):

```
baseline            1784/2828 cells fail  (sum=1784)
remainder_last      1239/2828 cells fail  (order=886, spread=353)
float_share         1784/2828 cells fail  (cents=1784)
floor_cents         1784/2828 cells fail  (sum=1784)
decimal_per_part    1784/2828 cells fail  (sum=1784)
gold_divmod            0/2828 cells fail  (-)
gold_decimal           0/2828 cells fail  (-)
```

Five wrong routes, each failing between 1,239 and 1,784 of 2,828 cells, and two
independent correct implementations passing every cell. So each wrong route fails
many cells rather than one lucky row - the standard `h02`'s table sets for itself.

## 6. The cell

- **Arm:** `opencode-bare` (`arms.json`: host `opencode`, `harness: none`, an
  isolated config with no instructions, no plugin, no skill deny) - the floor
  member of the pair section 2 pins.
- **Task:** `h06-exact-split-sum`. **Model:** `deepseek/deepseek-v4-flash` (the
  DeepSeek **direct** provider since amendment 1, section 12), in place of
  `openrouter/deepseek/deepseek-v4-flash`.
- **k = 12**, `--timeout 600`, one results file `results/h06/opencode-bare.jsonl`.
- **Chunked, in the lab's own shape:** repeats 1-4 first, then 5-12, each chunk a
  separate `bench.py run` with `--repeat-from`; the cell key is
  `(arm, task, repeat, model)` and a recorded repeat is skipped, never replaced.
- **Row fields read:** `pass`, `checks` (both named checks per row, so `suite` and
  `split_sum` are read apart), `changed_files`, `route`, `collateral`, `usage`,
  `wall_s`, `rc`, `timed_out`, `final_message`, `model`, `host_version`,
  `arm_cmd`, `prompt_sha256`, `fixture_sha256`, `started_at`.

## 7. Prediction

1. **The rate.** The bare arm passes **at most 3 of 12 rows** (≤ 0.25), against the
   sibling's 0/5 on `h02` for the same arm, host and model.
2. **The shape.** At least **6 of 12 rows** show the shape this family exists for:
   `suite` passed, `split_sum` failed, and `changed_files` is
   `["inventory/allocate.py"]` and nothing else.
3. **Arming and admissibility.** Every row carries `model`, `host_version`,
   `arm_cmd`, `prompt_sha256`, `fixture_sha256`, `started_at` and a `usage` block;
   `collateral` is empty on every row; no row times out.

The **falsifiers**, numeric, fixed before the run:

- **≥ 7 of 12 rows pass** → the contract is reachable without the behaviour the
  pair is supposed to differ in, the new task is not a discriminator, and the
  corpus change bought a task that reads as saturated. Reported as that.
- **≥ 6 of 12 rows show no change to `inventory/allocate.py`** (or fail `suite`)
  → the task is unreachable rather than discriminating, which is the calibration
  failure `README.md` records for the hard family's first sweep ("the signature of
  a task defect rather than a capability difference"). Reported as a task defect,
  and the change is not claimed.
- **≥ 3 rows with a missing `usage` block or a timeout** → the cell is not
  admissible as cost evidence and the rate is reported only with that count
  beside it (`PREREGISTRATION.md` section 4: a timeout is never a pass and never
  zero-cost).
- **The armed member's share is not measured here, so the discriminating claim
  this cell can support is one-sided**: it measures the floor member only.

## 8. What one cell cannot show

- **No paired contrast.** The other half of the pair is the published `h02`
  sibling cell - a different task, a different shape of hidden check. This round
  therefore bounds the bare arm's rate on a new task and says nothing about the
  armed arm's rate on it. The next cell, if this one reads as predicted, is
  `opencode+tezgah` at the same `k` on the same task (about the same money again).
- **No harness effect, and no corpus-wide pass rate.** One arm, one task, one
  model, one host.
- **Small-n.** At `k=12` the runner's own `wilson` puts 2/12 at 4.7-44.8% and
  3/12 at 8.9-53.2%: the cell can read gross differences (the sibling's 100-point
  gap) and cannot resolve single-digit ones.
- **The rate is a floor for one arm, not a property of the corpus.** `h02` itself
  shows the family is model- and host-dependent: the same opencode-bare arm read
  0/5 on deepseek and 4/6 on glm. Nothing here generalizes past deepseek.
- **`opencode-bare` carries no harness, so the gate is not armed for this cell.**
  Nothing here measures a tezgah refusal; the run directory sits under the
  worktree's `.runs/`, which is not a configured root for the omp arms - a
  follow-up armed cell must be run from a worktree inside a configured root or
  its gate is inert (`bench.py`'s `run_dir_for`, and the `E2` protocol's section
  4.6 for the arming rule).

## 9. Cost, and the stopping rule

- **12 runs.** Measured basis: `opencode-bare` in the pilot block spent $0.5850
  over 87 rows that reported usage, a mean of **$0.00672 per run**; the hard
  family's 200 runs cost $1.60, **$0.0080 per run**. Twelve runs are therefore
  **about $0.08**, with $0.10 the realistic ceiling. **Spent on OpenRouter: $0.00** -
  that provider's cell never started, because its account credit is exhausted (the
  note at the head of this file, and sections 13-14 of the lab's
  `PREREGISTRATION-H06.md`, where amendment 1 resumes the round on the DeepSeek
  direct provider).
- **The ceiling.** The OpenRouter attempt this section was written under had a
  $0.50 ceiling and spent nothing. Amendment 1 (section 12) puts the round on the
  DeepSeek direct provider under a **$0.20 ceiling**, and no run may push that
  account past it. Chunk 1 is 4 rows: if its own `usage.cost` sum projects the
  12-row total above $0.20, the block stops there with 4 rows and reports that.
- **Stopping:** the cell stops when it has 12 completed rows
  (`PREREGISTRATION.md` section 5). No arm is topped up and no block is extended
  because its result is inconvenient. A cell that lands inside the floor is
  reported as a tie with both counts, not as a direction.

## 10. Order, and the commit the results need

The layer's rule is that the protocol is in git history **before** the results. It
is: the parent committed the protocol on main as `4345aa1` and the task files on
the lab branch as `236159b`, both before any scored row. Amendment 1 (section 12)
is a second commit of the same kind, made before the cell's first row. No results
exist yet, so the order rule has nothing to compare:

```sh
# the prediction (parent):
git -C /Users/rizax/Projects/tezgah add .tezgah/research/env-scaling/experiments/E1-env-adapt-h06/protocol.md
git -C /Users/rizax/orca/workspaces/tezgah/envscale-adapt add benchmarks/arm-bench/tasks/h06-exact-split-sum benchmarks/arm-bench/PREREGISTRATION-H06.md
# ... commit ...
# for a later run, the results go in by explicit path (the repo ignores that pattern):
#   git -C /Users/rizax/Projects/tezgah add -f .tezgah/research/env-scaling/experiments/E1-env-adapt-h06/results.jsonl
```

Since no run happened, the line stays **open** on the layer's own rule
(`hooks/tezgah_research.py`'s `_open_reasons`: "experiments/E1-env-adapt-h06 has a
protocol and no results"), which is the honest state - the prediction is on
record and nothing has tested it.

`predictions.jsonl` gets **no row** for this change, and the reason is in the
manifest rather than in taste: `bin/tezgah-research predict` requires a row to
name at least one component `hooks/tezgah_components.py` defines, and no
component covers `benchmarks/arm-bench` - a row would have to name a component
this change does not touch, which is the kind of claim the layer refuses
elsewhere. The prediction lives in section 7 of this file instead, which is where
`check` reads it.

## 11. Sources read for this file

- `.tezgah/research/env-scaling/findings.md` item (a), its prerequisite table, its
  pattern list (C10) and its *Open questions* (the reshaping question this
  experiment is the first half of).
- `benchmarks/arm-bench/README.md` (task format, well-formedness rule, the
  two-host block, the hard family's calibration lesson, the gate family's two
  failures, the freeze rule); `PREREGISTRATION.md` sections 2-5 (k, accounting,
  stopping); `PREREGISTRATION-E8.md` (the gate a task entering a round must
  answer, the power table, the cost basis).
- `bench.py` (`selftest`, `preflight`, `cmd_run`'s row fields, `route_of`,
  `fixture_of`).
- Result files, counted rather than quoted: `results/hard-cells/h02-*.jsonl`,
  `results/hard-cells-glm/h02-*.jsonl`, `results/pilot-block.jsonl`.

## 12. Amendment 1 (2026-09-22): the provider

Written after the commit of sections 1-11 (`4345aa1` on main, `236159b` on the lab
branch) and committed before the cell's first scored row. **The design does not
change**: same arm (`opencode-bare`), same task (`h06-exact-split-sum`), same `k`
(12), same timeout, same endpoints, same prediction and same numeric falsifiers.
What changes is the provider the arm's model is served from.

- **Model identity.** `deepseek/deepseek-v4-flash` - the DeepSeek direct provider,
  listed by `opencode models deepseek` - in place of
  `openrouter/deepseek/deepseek-v4-flash`. `deepseek` is an authenticated provider
  in the host's own credential store, and the arm reaches it with no config change:
  the probe row below carries `model deepseek/deepseek-v4-flash` and a `usage` block.
- **Why.** OpenRouter's credit is exhausted (the note at the head of this file; a
  sibling session's rows all returned HTTP 402 with $0 spent). For this amendment
  `api.deepseek.com/user/balance` was read and answers `is_available true`,
  `total_balance 8.00 USD` (topped up). The account is shared with a sibling
  session, so the balance is not this round's alone, and the round's own ceiling is
  **$0.20**.
- **What the thresholds were fixed against, stated once so a reader does not move
  them.** Section 7's prediction (at most 3 of 12 rows pass; at least 6 of 12 carry
  the discriminating shape) and its three numeric falsifiers were written against
  `openrouter/deepseek/deepseek-v4-flash` rows - including the `h02` sibling prior
  this cell leans on (opencode-bare 0/5 on that provider). They are **not**
  re-derived here: this run measures the direct provider, and the comparison stays
  **within the same arm** - the arm, the task and `k` are what the contrast holds
  fixed, and the provider is a named confound (routing, prompt caching and price can
  differ between two providers serving the same model name), not a second factor.
- **The path probe, run before this amendment was committed.** One row,
  `benchmarks/arm-bench/results/h06/opencode-bare-proof.jsonl` on the lab branch -
  kept apart from the cell, the lab's own probe idiom - read `pass` with both checks
  green, route `code`, `changed_files == ["inventory/allocate.py"]`, no collateral,
  21.2 s, `usage.cost` **$0.006218**, `model deepseek/deepseek-v4-flash`,
  `host_version 1.18.31`. It is evidence that the path works, and the first signal
  *against* prediction 1 - and it is a probe row, not one of the cell's 12: it
  changes no threshold, and the cell still runs to its pre-registered `k`.
- **Cost on this provider.** The one measured row cost $0.006218, so the 12-row
  cell is about **$0.075** and the round including the probe about $0.081. The
  first chunk (4 rows) is the spend gate: if its sum projects past $0.20 the block
  stops there and says so.
- **Rows spent so far.** 1 (the probe). Cell rows: 0 of 12.
