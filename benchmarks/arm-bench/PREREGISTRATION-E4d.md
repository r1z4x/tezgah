# Pre-registration: E4d - the wrong-route endpoint, and the Stop fires counted

Status: **frozen before the scored run**. Committed as its own commit on
`fix/arming-from-e4b`, on top of `02d0e21` (the instrument change that makes this
block possible). No E4d run has started.

E4c measured the harness with the hooks armed for the first time and found
nothing on the endpoint it registered: the Stop rule looked inert (19/25 against
19/25 for the one-file-different arm), and the block could not even say whether
the rule fired, because the decision left no record on the tree the runs
executed in. Two things follow, and this block is the pair of them.

- **The endpoint moves to the route.** Which file a run edited separated the
  arms where the pass rate did not: `orx-gate-off` took the wrong (helper) route
  in **0/25** runs, the other three arms in 4-6/25. That column is now a
  first-class per-row fact (`route`, from the task's own `meta.json`), not an
  analyzer's private rule, so the endpoint this block registers is measured by
  the instrument that produced the rows.
- **The Stop fires are countable.** `stop_fires` travels per row, read from the
  run's own session ledger, where the Stop rule writes one `claim` row per
  decision and marks a refusal `blocked: ...`. The secondary endpoint below is
  the count the earlier blocks could not get.

## 1. What this block can and cannot answer

- It measures **one task**, `e01-silent-one-liner`, as E4c did. That is the only
  task in the set that separated arms; `e02` and `e03` were passed 5/5 by every
  arm including the anchor, so runs spent on them buy a negative control and
  nothing else.
- **It cannot generalise to other tasks.** A single-task result is a
  single-task result. In particular a wrong-route rate is not a property of the
  harness: it is a property of (harness, task, model), and it exists at all only
  because this task has exactly two plausible fixes - one line at the call site,
  or rewriting the shared whole-cent helper. A task with one plausible fix has
  no wrong-route rate to measure, and a task whose failure mode is not "edit the
  shared helper and break a suite nobody ran" is not covered by anything here.
- **It cannot generalise to other hosts.** All four arms are omp; the
  opencode/codex/claude arms carry unverified isolation and are not scored.
- **It cannot see an effect smaller than the resolution below.** The
  instrument's noise floor was measured in E4b at 27 points (two arms under
  identical conditions scored 11/15 and 15/15). Arithmetic with
  `E4b-mechanical-off-armed/power.py` (`n_per_arm`, `detectable`, two-sided
  0.05, 80% power):

  | endpoint, per-arm comparison | smallest detectable at k=25 | runs/arm a given gap needs |
  |---|---|---|
  | pass rate (pbar 0.75) | **34 points** | - |
  | wrong route (pbar 0.12) | **26 points** | 29 for the 24-point contrast E4c saw (0.24 vs 0.00); 33 for 0.21 vs 0.00; 41 for a 20-point gap; 115 for 12 points |
  | Stop fires (0.60 vs 0.00) | 36 points | 9 |

  So k=25 resolves a **26-point** difference in the wrong-route rate: E4c's
  observed 24-point contrast sits one arm-size below its own 80%-power
  requirement, and the registered comparisons below are stated as one-sided
  thresholds a k=25 block can actually decide, with the exact binomial
  probability of each threshold under E4c's rates given alongside it.

## 2. Design

Four arms, the same ones as E4c, differing only in the kill switch. The toggles
are what `arms.json` records, read before the run:

| arm | gate | Stop rule |
|---|---|---|
| `omp+tezgah` | on | on |
| `orx-verify-off` | on | off |
| `orx-gate-off` | off | off |
| `omp-bare` | no harness | no harness |

25 runs per arm, 100 runs total, model `openrouter/deepseek/deepseek-v4-flash`,
`k=25` on `e01-silent-one-liner`, executed as 20 pool jobs of 5 consecutive
repeats each (`orx_block.py`), each job invoking `bench.py run`. Each arm
carries `TEZGAH_ROOTS` covering the archive parent, so a run inside the archive
matches a configured root - the arming fix from `fix/arming-from-e4b`.

The route of a run is read from the task's own declaration, not from a path
baked into this document: `tasks/e01-silent-one-liner/meta.json` carries
`"routes": {"call-site": ["src/pricing.py"], "helper": ["src/money.py"]}`, and a
run takes `helper` when its diff touches `src/money.py` alone, `call-site` when
it touches `src/pricing.py` alone, `both`, `none` (no edit) or `other` (an edit
on neither route, e.g. only the frozen tests). The registered endpoint is the
number of runs per arm that took **`helper`** - the wrong one.

**Pinned host state.** The installed omp hook loads `hosts/omp/hook.py` by
absolute path from `/Users/rizax/Projects/tezgah`, so the running rules are
whatever that tree's HEAD is. The HEAD is read before the block and re-read
after; the block is void if it moved. Pinned for this block: `ef950f5`. For E4c that HEAD predated plan 012, which
is why the Stop rule wrote no row there and the fires were unreadable; this
block additionally requires the pinned tree's `hooks/tezgah_integrity.py` to
write the `claim` row from `stop_reason` (`note(session_id, "claim"` present,
`detail` starting `blocked` for a refusal). The change that lands it is on
`fix/stop-decision-row`, commit `ad769d69f6eb02afd32abbe02533d1a92e93ab4d`
(`blocked: no verify_ok` / `blocked: check failed` / `blocked: placating
opener`); the pre-change form is the block prose truncated at 80 characters,
which `startswith("blocked")` also counts, so the field reads either tree but
the *branch that fired* is only named from the post-change one. **If the pinned
tree writes no `claim` row, the secondary endpoint is void rather than zero** -
a zero from a harness that cannot write the row is not a measurement.

## 3. Predictions, before the run

Direction: E4c's only separating column said the arm with everything switched
off is the arm that never takes the wrong route. E4c itself judged that gap
inside the noise and called it a hint worth a pre-registered repeat; this is
that repeat, with the Stop decision now recorded so a rule that never fires and
a rule that fires without effect can be told apart.

**P1 (primary endpoint, wrong-route rate).** `orx-gate-off` takes the `helper`
route in at most 2 of its 25 runs, while the three other arms pooled take it in
at least 12 of their 75. E4c: 0/25 against 16/75. Decidable at k=25: under the
pooled E4c rate the thresholds carry P(X<=2 | n=25, p=0.213) = 0.075 and
P(X>=12 | n=75, p=0.12) = 0.184.

**P2 (primary endpoint, direction).** `orx-gate-off` takes the `helper` route
strictly fewer times than each of the other three arms - it stays the arm with
the fewest wrong-route runs rather than one of a tied group. E4c: 0 against 6,
6 and 4.

**P3 (secondary endpoint, Stop fires).** At least 5 of the 25 `omp+tezgah` rows
record one or more fires, and all 75 rows of the other three arms record zero.
E4c: the Stop-on arm failed 6/25 and all six failures ended on a completion
claim; its Stop rule is off in `orx-verify-off` and `orx-gate-off` and absent in
`omp-bare`. Against a rule that never fires the first threshold has probability
0; against residual firing in a Stop-off arm the second carries P(0 of 75 |
p=0.2) = 5e-8.

**P4 (the fires are a different claim from the effect).** The pass rates of
`omp+tezgah` and `orx-verify-off` stay within 10 points of each other (E4c: 0
points apart, 19/25 against 19/25). This is registered as a replication of
E4c's null, not as a prediction that the rule helps: with the fires counted, P3
and P4 together are readable as "it fires and the outcome does not move".

**P5 (arming, precondition).** At least 90% of the rows in the three harness
arms carry `session_rows > 0`, every `omp-bare` row is `-1`, and the wrong-route
column is present on all 100 rows. E4c: 100% of harness rows armed, `-1` on
25/25 bare rows.

**Falsifier.** The route endpoint is falsified if `orx-gate-off` takes the
`helper` route in 3 or more of its 25 runs, or if the pooled three take it in
fewer than 12 of 75, or if `orx-gate-off` is not alone at the bottom (P2). Then
E4c's separating column was noise on this task and the gate has no route effect
worth pursuing. The fires endpoint is falsified if fewer than 5 `omp+tezgah`
rows carry a fire - and if any row of the other three arms carries one, which is
an arming failure rather than a result, since two of those arms run with the
Stop rule off and the third with no harness. Falsified is a result to report,
not a failure of the block: E4c's own registered direction was wrong and saying
so was the block's most useful output.

## 4. What is recorded per row

`pass`, **`route`** (`call-site` / `helper` / `both` / `none` / `other`),
**`stop_fires`** (refusals the run's own session recorded; `0` = found and
refused nothing, `-1` = session unknown), `session_rows`, `final_message`,
`changed_files`, `collateral`, `wall_s`, `usage`, and the arm's `toggle`.
`route` is emitted by `grade`, so a graded directory and a recorded row carry
the same value from the same function.

## 5. Execution

Runs execute in a pool of 10 jobs, each holding 5 consecutive repeats, 20 jobs
over the four arms - the same shape the E4c block finished in. Rows land under
`results/orx/<instrument-sha>/`, and `bench.py run` skips repeats already
recorded, so a stopped block resumes instead of re-spending. The block's
instrument commit is `02d0e21` (this repository's branch `fix/arming-from-e4b`);
the analyzer for this block imports `bench.route_of` rather than re-implementing
the route rule, which is the point of moving it into the instrument.

## 6. The old blocks' route column, without re-running anything

The rows of every earlier block already store `changed_files`, and `route_of` is
a pure function of that list plus the task's `routes` declaration, so the column
is re-derived at read time. Nothing was rewritten and nothing was backfilled by
hand; the command below was run against the E4c rows and reproduces E4c's
analyzer exactly:

```
python3 -c "import sys,json,pathlib,collections; sys.path.insert(0,'benchmarks/arm-bench'); import bench;
meta=bench.load_json(bench.task_dir('e01-silent-one-liner')/'meta.json');
rows=[json.loads(l) for f in sorted(pathlib.Path('benchmarks/arm-bench/results/orx/85e690f').glob('*.jsonl')) for l in f.read_text().splitlines() if l.strip()];
print(collections.Counter(bench.route_of(r['changed_files'], meta) for r in rows))"
```

over the 100 scored E4c rows prints
`Counter({'call-site': 66, 'both': 17, 'helper': 16, 'none': 1})` - 16 helper
runs, i.e. the 6/6/0/4 per-arm split of the E4c analysis. Over the 21 rows of
the committed partial run (`results/orx/82e1128`) it prints
`Counter({'both': 6, 'call-site': 10, 'helper': 5})`.

Two consequences, both deliberate. The route column is only as old as the task's
`routes` declaration, so a block whose task declares none reports `null` - for
those, the declaration is the only thing missing, not the runs. And E4c was
scored with the analyzer's private copy of the rule; that copy stays as it was
committed, and agrees with the instrument on every one of the 100 rows.

## 2b. Sizing amendment, written before the run

Section 3 states its thresholds for k=25, and section 1 recordta that E4c's
24-point contrast sits one arm-size below its own 80%-power requirement (29 runs
per arm). The block therefore runs **k=50 per arm, 200 runs**, which resolves an
18-point difference at the same power. The registered comparisons scale with the
run count and their binomial force is unchanged in substance:

- **P1** becomes at most **4 of 50** `helper`-route runs for `orx-gate-off`, and
  at least **24 of the pooled 150** for the other three arms.
- **P3** becomes at least **10 of the 50** `omp+tezgah` rows recording a fire,
  and **zero across the other 150**.
- **P2**, **P4** and **P5** are ratios and need no rescaling; P5's "all 100 rows"
  reads "all 200 rows".

Nothing else changes: same four arms, same task, same model, same endpoints. This
paragraph was written before the block started.
