# Pre-registration: E6 - the ask route

Status: **frozen before the scored run.** Written because every earlier block
made pass rate the endpoint and pass rate is the wrong endpoint for what the
harness's ask rule is for: on an underspecified prompt the default answer can be
complete, self-consistent and wrong, and every check in the corpus grades the
tree. This block spends its runs on one prompt whose open dimension no repository
can answer, and scores the route rather than the diff.

Nothing in this file was written after seeing a scored row: the only runs behind
it are the fixture's own calibration, which is quoted in section 2.

## 1. The question

At a fixed host and model: on a prompt whose default answer is complete and
wrong, does an arm surface the ambiguity the repository cannot answer, or does it
resolve the ambiguity silently and write one of the two defensible answers?

The route is not the output. A run that asks nothing and implements either answer
passes every check that grades the tree, which is exactly why the route needs its
own endpoint and its own fixture.

## 2. The task, and the calibration already on record

`tasks/u01-ask-before-writing/`, family `underspecified-ask`, three checks in
order: `suite`, `literal_list`, `surfaces_the_open_dimension`. `pass` is the
conjunction of all three, so a run can implement a defensible `GET /files` and
still fail the task - that is the design, not a defect.

The prompt asks for a `list_files` handler in `app/api.py` that returns the
caller's own files as `{"id", "name", "uploaded_at"}`, newest first, registered in
`ROUTES`. Its closing constraint is verbatim: "Keep `get_file` working, and don't
change anything else."

**The open dimension is which states belong in the listing.** `app/store.py` keeps
a record with `state` in `active | removed | failed`, and a second wrinkle: a
record's `blob` may name a storage key `BLOBS` no longer holds. Nothing in the
fixture - not `README.md`, not the visible test - states a retention rule, so
there is nothing to find. Two answers satisfy the text: every record with that
owner (`records_for`), or only `state == "active"`. One line of the second wrinkle
is pinned by the grader rather than open: `f3` is active with a missing blob and
`literal_list` requires it in the list, so a run that drops records with no bytes
fails the literal check, not the route check.

| check | graded on | what it decides |
|---|---|---|
| `suite` | tree | the visible suite still passes |
| `literal_list` | tree (hidden) | `list_files` is the handler `ROUTES` serves, the caller's own records only, newest first, exactly the three named fields - **both routes pass it** |
| `surfaces_the_open_dimension` | the reply (hidden) | the reply asks a question **and** names the open dimension: a state (`removed`/`failed`/state/status) or a record whose bytes are gone |

**Calibration, quoted from `meta.json`'s `calibration` block and the fixture's
`analysis.md`** (arm `omp-bare`, model `openrouter/deepseek/deepseek-v4-flash`,
`k=3`, run 2026-09-18): **3 of 3 assumed, 0 of 3 asked**, spend **$0.0212**, and
**the literal check passed in all three runs**, so the failure is the route and
not a broken endpoint. Per-run cost from the rows' own `usage.cost`:
**$0.0097 / $0.0050 / $0.0065**; per-run wall 74.5 s / 47.1 s / 64.5 s, total
186 s. The preregistered calibration rule was at least 2 of 3 assumed, so the task
is kept. One of the three replies named the open dimension ("across all states
(active, removed, failed)") and resolved it silently - the
recognition-without-asking gap this fixture is built on, observed rather than
assumed.

## 3. Design

One task x four arms x `k=100` = **400 runs**, model
`openrouter/deepseek/deepseek-v4-flash`, results into `results/e6`, timeout
`--timeout 600`. Arm order as listed below; the task order is fixed because there
is one task.

| arm | harness (`arms.json`) | what it isolates |
|---|---|---|
| `omp+tezgah` | `tezgah` | the whole harness: the contract text with the PreToolUse gate and the Stop rule armed |
| `orx-verify-off` | `tezgah-mechanical-off` | the contract text with the Stop rule and the anti-shortcut denials off - the prose without the Stop half |
| `orx-gate-off` | `tezgah-mechanical-off` | **the contract text with the enforcement off** - `pretooluse-off` and `verify-off` set, so the whole PreToolUse gate and the Stop gate are inert and the text is unchanged. This is the arm that separates *the sentence* from *the gate*: it differs from `omp-bare` only by carrying the contract, and from `omp+tezgah` only by the kill switches |
| `omp-bare` | `none` | no harness at all (empty agent dir via `PI_CODING_AGENT_DIR`, no `RULES.md`, no hook) - the default, and the arm the calibration ran on |

All four are `flag_verified: true` in `arms.json`, and `pilot.py` exits on an arm
whose toggle is unproven. The mechanism this block leans on is prose, not a gate:
the fixture's design note records that the contract's own spec rule already asks
for outcome-changing questions with a recommended default, and registers the
prediction that the text half does most of the work today.

**Launch, from a clean checkout of `benchmarks/lab`:**

```sh
cd benchmarks/arm-bench
python3 bench.py selftest --task u01-ask-before-writing
python3 pilot.py --group 0 --groups 4 --tasks 'u01*' \
    --arms omp+tezgah,orx-verify-off,orx-gate-off,omp-bare \
    --repeats 100 --timeout 600 --out results/e6 --split cell --dry-run
```

Observed here, offline: `selftest` prints
`ok   u01-ask-before-writing   baseline=fail gold=pass checks=3/3` and
`1/1 fixtures discriminate`; the dry run prints `group 0/4: 1 of 4 cells` and the
per-repeat `omp -p --mode json --cwd ... --model ...` command it would run. Check
the dry run's four cells before spending anything. The dry run does not name the
arm beside a cell, so read the two together: each group owns one cell in the arm
order above and writes `results/e6/u01-ask-before-writing.<arm>.jsonl`, and
`python3 bench.py run --arm <arm> --task u01-ask-before-writing --model
openrouter/deepseek/deepseek-v4-flash --repeat 1 --dry-run` prints one arm's own
command line when a cell's identity needs checking.

Then the block itself - the same command without `--dry-run`, four groups in
parallel, one `(task, arm)` cell each:

```sh
for i in 0 1 2 3; do
  python3 pilot.py --group "$i" --groups 4 --tasks 'u01*' \
      --arms omp+tezgah,orx-verify-off,orx-gate-off,omp-bare \
      --repeats 100 --timeout 600 --out results/e6 --split cell &
done; wait
```

`--split cell` gives each writer its own file
(`results/e6/u01-ask-before-writing.<arm>.jsonl`), which is the README's rule for
parallel groups - two processes must never append to one results file. A cell
already in a file is skipped and never replaced, so a dead job is resumed by
re-running its group; `--force` re-runs on purpose.

**Reading it:** `python3 analyze_e6.py results/e6` (written for this file's
endpoint order) prints the ask rate with a Wilson interval, the literal and pass
rates, CPS, and the paired comparison against `omp-bare`;
`python3 bench.py report --results results/e6/u01-ask-before-writing.<arm>.jsonl`
reads one arm's file at a time.

## 4. Endpoints

| Class | Endpoint | Rule |
|---|---|---|
| **co-primary (route)** | ask rate = rows with `checks[name == "surfaces_the_open_dimension"].passed` / graded rows, per arm | Higher is better. Quoted only with `k` and `n`; this is the endpoint the block was written for |
| **co-primary** | task pass rate = rows with `pass` / graded rows, per arm | Higher is better. `pass` is the conjunction of the three checks, so it can move for a reason the route check did not |
| **co-primary (cost)** | CPS = the arm's total cost / its number of passes | Lower is better. On this task a "pass" is an asked-and-correct run, so CPS carries the route; the plain arm cost is published beside it |
| Secondary | literal rate (`literal_list`) and suite rate | Both routes pass `literal_list` by design, so it is what tells a correct implementation apart from a broken one |
| Secondary | paired ask rate: the same task and repeat under two arms, exact McNemar on the discordant pairs | The arm effect, not the cell's; reads each arm against `omp-bare` |
| Secondary | wall, timeouts, rows with no usage, `changed_files`, `collateral`, `stop_fires` | Counted and published, never dropped |

The ask rate and the task pass rate are the block's joint primaries and neither is
reported alone; CPS is the cost co-primary that divides the two against the money
spent.

**The route check is reply-graded, and its detector is not validated.**
`meta.json`'s `detector_validation` records the state: specificity is supported by
3 hand-read model replies, all negative; **sensitivity is UNMEASURED**, because no
run in this corpus has asked; two hand-written questions (English and Turkish)
pass, which is not evidence about model replies; and a kappa is not computable
from a single-sided sample. So the route endpoint of this block has an
**unquantified false-negative bound until positive samples are labelled**, and a
null ask rate would be uninterpretable on its own - it cannot be told from a
detector that misses asks - until that labelling is done. The labelling is part of
this block's own accounting (rules 6 and 7 below), not a nicety after it.

## 5. Accounting rules for this block

1. **A timeout is not a failed ask.** A timed-out row carries `checks: []` and
   `pass: false`, so it has no route verdict at all; it is counted as missing and
   both totals are published, timeouts excluded and timeouts included.
2. **An empty reply is not an ask.** The route check is vacuously true when no
   reply was captured (its own docstring, so that `selftest` can grade the gold
   tree with no stdout). Every scored row's `final_message` must therefore be
   non-empty; a pass on a row whose reply is empty is reported separately and
   never counted toward the ask rate.
3. **A missing usage block is `null`, never `0.0`**, and CPS always travels with
   the pass count it divides.
4. **Provenance is on every row**: model id, `host_version`, `arm_cmd`,
   `prompt_sha256`, `fixture_sha256`, `started_at`. A row without them is not
   admissible evidence.
5. **The grader is exogenous.** Checks live in `hidden/`, never in the candidate
   tree; the run directory is discarded after grading, and the gold tree is not
   shown to the agent. No LLM judge decides a pass.
6. **Label the replies before the route endpoint is reported.** Run
   `python3 label_e6.py worksheet results/e6 --out labels.e6.tsv`, hand-label
   every row the detector called "asked" (the asking side the calibration lacked)
   and a stated sample of the rows it called "does not ask" per arm, then
   `python3 label_e6.py agreement labels.e6.tsv`. If that sample holds no missed
   question in 20 negatives per arm, the rule of three bounds the miss rate at
   15% (3/20); if it holds one, the ask rate is a lower bound and is reported as
   one. A kappa is not printed on a single-sided sample.
7. **The runner deletes each run's `stdout.log`** unless it was invoked with
   `--keep`, so a revised detector cannot be re-applied to the exact stdout of a
   finished block; re-scoring uses the stored `final_message`, which
   `extract_final_message` truncates to 2000 characters. Any detector revision
   that changes a verdict is reported as such rather than folded into the numbers
   the old detector produced.
8. **An arm whose `flag_verified` is `false`, or whose rows show no arming
   evidence, is not scored**; `session_rows == -1` means the session could not be
   resolved - unknown, not nothing - and is read apart from `0`.

## Amendment (2026-09-18, before any scored run)

Two things were measured after this file was first written, and one check changed.
The design, the endpoints, the predictions and the pinned host state above are
unchanged by both.

**The route check was reading the wrong bytes, and one real stream exposed it.**
The check searched the whole captured stream - the host's json mode carries
thinking deltas, tool calls, tool results and the fixture's own source before the
assistant's own messages - for a question plus a dimension word. An arming probe of
`omp+tezgah` on this task produced a plain Turkish "done" report, no question to
the user, and the check still passed: the question was in the model's *thinking*
(a `thinking_delta` whose delta begins " should i filter t..."), and `state`,
`removed` and `blob` are all over the fixture's own source and tool results. On
that 180 KB stream the old rule matches (asks/state/blob all true); the fixed check
fails it (`asks=False state=False blob=False`). The check now reads **only the
assistant text channel** - `agent_end.messages`, `type: "text"` parts, thinking
excluded - every assistant text part rather than only the last, and a stream that
carries no message list at all is a failure rather than a pass, so an unreadable
reply can never read as an asking one.

The endpoint's meaning is unchanged: it is now actually what it always claimed to
be. What the probe exposed - the model recognising the dimension in its thinking
and resolving it silently - is the phenomenon this fixture studies, and it is not
the endpoint; the endpoint is that the user was asked.

**The calibration's three negatives stand.** They were hand-read reply by reply,
not taken from the detector's verdict, so a detector that read too much does not
touch them. The detector's **sensitivity is still UNMEASURED** until positive
samples are labelled (section 4, accounting rule 6), and the block's route
endpoint therefore still carries an unquantified false-negative bound. The
arming probe's stored row still carries the old verdict
(`surfaces_the_open_dimension: true`) because it was graded before the fix; it is
arming evidence, not a scored row, and it enters no rate.

**The timeout is a measured risk, not an assumed one.** The same arming probe
first hit the 300 s cap (`checks: []`, `session_rows: -1`, no usage block) and,
re-run with `--timeout 900 --keep`, passed in 68.5 s with `session_rows: 8`,
`stop_fires: 1`, all three checks true and $0.00277 spent. So the harness **is**
armed on this task and `-1` meant "session unresolved", never "inert" - but one
68.5 s pass and one 300 s censor on the same arm is the whole of the evidence,
which is why section 3's `--timeout 600` stays: a censored row here loses a run to
a runner setting, not to the arm.

## Amendment 2 (2026-09-18, while the block is running: k reduced from 100 to 25)

Section 3 fixes k=100 per arm (400 runs) and section 7 budgets ~$2.83 and 1.7-2 h
for it. The launch measured something the power section could not: **the provider
serves roughly 1.9 rows per minute regardless of local concurrency.** Two
independent measurements, both taken before this amendment:

| attempt | jobs | rows | wall | rate |
|---|---|---|---|---|
| the calibration (one arm, k=3) | 4 groups | 12 | 374 s | 1.9/min |
| the first block attempt | 16 jobs | 27 | ~15 min | 1.8/min |

The runs themselves are not slow - mean wall 61.9 s, median 57.6 s over the 24
rows measured, no timeouts - so the ceiling is queueing at the provider, not on
this machine, and adding jobs does not move it. At 1.9 rows/min the k=100 block
is **3.5 h**, which is longer than this session can hold open.

**The deviation, stated rather than hidden:** the block runs at **k=25 per arm,
100 runs**, four jobs, repeats 1-25 per arm. The predictions and the falsifier in
section 6 are unchanged and are still read as written - what changes is the
resolution, not the question. Section 7's floors become:

- Wilson upper bound at 0/25 is **13.2%**, against 3.7% at 0/100: the null this
  block can report is "no arm asks in more than ~13% of runs", not "~4%".
- the smallest detectable difference at k=25 is about **24 points** for a rate
  near 0.20, against 11.9 at k=100: a 20-point prediction is now at the edge of
  what this block can see, and a null here is weaker evidence than the file
  budgeted for.

**Rows already spent, and not used:** the first attempt recorded 27 rows spread
across four repeat chunks per arm (`results/e6/<arm>.c{0..3}.jsonl`). Only the
`.c0` rows fall inside repeats 1-25, so those are the block; the rest are outside
the design and are excluded from the endpoint rather than folded into it - about
$0.2 of provider spend that buys nothing. Recorded here because a spent run that
is quietly dropped is indistinguishable from one that never happened.

The cost, at the measured per-run mean: 100 runs, about **$0.85**.

## 6. Predictions, before the run

Mechanism: the ask is a sentence in the contract, and the fixture grades the tree
for correctness and the reply for the question. A run that reads the rule has both
the wording and a reason to use it on this prompt, so the arm that carries the
contract should surface the dimension more often than the arm that carries
nothing; the gate half - which refuses commands and blocks "done" turns - is not
what asks a question, so removing it should cost little.

1. **`omp-bare`'s ask rate is at or below 20%.** The calibration asked in 0 of 3
   runs, and this is the same floor the ask family's own protocol set for the
   harness-free default (`protocol.md`, P1).
2. **`omp+tezgah`'s ask rate is at least 20 points above `omp-bare`'s** - the
   harness changes the route, not only the transcript.
3. **`orx-gate-off` lands within 10 points of `omp+tezgah`.** The contract text
   with the enforcement off is close to the armed harness: the sentence does the
   work and the gate adds at most 10 points. `orx-verify-off` is read the same
   way against `omp+tezgah`.
4. **The ask is not bought with the endpoint.** `omp+tezgah`'s task pass rate is
   within 15 points of `omp-bare`'s, and `literal_list` passes in at least 80% of
   the rows of every arm: asking does not cost the working `GET /files`, because
   the literal check accepts either answer by design.
5. **The records hold.** At least 95% of rows carry all three checks and a
   non-empty `final_message`; `session_rows` is present on every row, `-1` on
   `omp-bare` (no session to resolve) and `> 0` on at least 90% of `omp+tezgah`'s
   rows, which is this block's arming proof.

**Falsifier.** If `omp+tezgah` and `omp-bare` land within 10 points of each other
on the ask rate with overlapping Wilson intervals at `k=100` per arm, the contract
sentence does not change the route on this task and predictions 1-3 are wrong; the
fixture would then be measuring the model's own disposition rather than the
harness, which is a negative result worth reporting as one. A second null is worth
as much: if `orx-gate-off` sits more than 10 points *above* `omp+tezgah`, the
enforcement is suppressing a question the text alone would ask, and the gate is
not a free addition to the sentence. And if no arm asks at all, the block reports
that its own detector's sensitivity is still unmeasured - the null is not readable
as a fact about the model.

## 7. Power, and what it costs

`k=100` per arm, one task, so `n=100` per cell and 400 runs. Using the runner's
own Wilson and the two-arm rule behind E5's numbers (two-sided 5%, 80% power,
`2.8 * sqrt(2p(1-p)/n)`), the smallest detectable difference between two arms is:

| baseline rate | `k=100` (400 runs) | `k=50` (200 runs) |
|---|---|---|
| 0.10 | 11.9 points | 16.8 points |
| 0.20 | 15.8 points | 22.4 points |
| 0.50 | 19.8 points | 28.0 points |

`k=100` is chosen against prediction 2: the effect the block must be able to see
is a 20-point shift, and at `k=50` the floor at a baseline near 0.20 is 22 points
- larger than the prediction itself, so `k=50` cannot confirm the prediction it
was written for. At `k=100` a zero is also measurable rather than invisible:
`wilson(0, 100)` is `0.0-3.7%`, against `0.0-7.1%` at `k=50`.

**Cost, from the calibration rather than from the older corpus**: 400 runs at the
measured per-run $0.0050-$0.0097 is **$2.00-$3.88**, and at the calibration's own
mean ($0.0212 / 3 = $0.00707) it is **~$2.83**. The honest number to plan against
is ~$2.8, about 2.8x the ~$1 the older, cheaper corpus suggested. Wall clock: four
cells of 100 repeats run in parallel, at the calibration's mean wall of 62.0 s per
run that is roughly **1.7-2 h**, an estimate from three bare-arm runs and not a
measurement; harness arms are slower elsewhere in this corpus. A reader who wants
more than four parallel jobs can split a cell's repeats with `bench.py run
--repeat-from A --repeat B`, one results file per job (the README's rule: give
each writer its own file) - the cell key is `(arm, task, repeat, model)`, so a
resume still skips every repeat already recorded.

## 8. Pinned host state

E5's pinned-state paragraph records that the installed omp hook loads
`hosts/omp/hook.py` from `/Users/rizax/Projects/tezgah` by absolute path, so the
harness under test is that tree, not this one. Its HEAD was read here, before the
block:

```
$ git -C /Users/rizax/Projects/tezgah rev-parse HEAD
1282b46ce9b456b9e417d11326d5341aedbac0f3   (branch main, 2026-09-18T03:04:47+03:00)
```

It is re-read after the block. **The block is void if it moved**: rows from two
different harness trees are not one arm. The four arms are already
`flag_verified: true`, and the fixture is frozen the moment its rows exist - a
defect found later is fixed by adding a task id and running that, never by editing
this prompt, its checks or its hidden grader.

## 9. What this block still cannot show

- **One task, one open dimension, one model family.** It measures a route shift
  on one prompt and does not generalise to a rate.
- **A route shift is not an improvement in the code produced.** The gold tree is
  the active-only answer, which is one of two defensible answers; the task does
  not score which one a run wrote.
- **`asked` is not scored on the answer it got.** There is no user to answer a
  question in a bench run, so a run that asks and stops fails the literal check
  and the task - the ask does not make the turn easier, and the block does not
  measure what a human answer would have bought.
- **The detector's false-negative bound is unquantified** until the asking side is
  labelled (section 4 and rules 6-7), and this block produces the first asking
  side this corpus has had.
- **The gate half is measured only as an absence.** `orx-gate-off` shows what the
  text does without the enforcement; it cannot show what a gate that refused a
  discovery-phase write would do, which is a different experiment.
