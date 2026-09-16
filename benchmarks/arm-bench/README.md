# arm-bench: a runnable harness/factor benchmark

Supersedes the data-only `harness-vs-omp/` round 1-2 layout for all *new* runs.
The old rounds stay published as evidence; this directory holds the runner,
the fixtures and the graders, so a comparison can be re-run and audited instead
of trusted.

```
bench.py        runner, grader, aggregator (stdlib only)
arms.json       one entry per (host, harness) arm: exact command, env, toggle note
PREREGISTRATION.md  the design a number must be read against
tasks/<id>/     meta.json, prompt.md, fixture/, gold/, hidden/
results.jsonl   appended rows, one per (arm, task, repeat)
```

## Usage

```sh
python3 bench.py list                       # tasks and arms
python3 bench.py selftest                   # offline: every fixture fails pre-fix, passes post-fix
python3 bench.py run --arm opencode+tezgah --task t01-discount-rounding \
                    --model <provider/model> --repeat 5
python3 bench.py report                     # pass rate, Wilson CI, cost, CPS, paired McNemar
```

`selftest` makes no model calls and costs nothing; it is the check that the task
set discriminates. `run` spends money - read `PREREGISTRATION.md` first.

## Task format

`fixture/` is the pristine tree handed to the agent. `gold/` holds the same
relative paths with the reference solution. `hidden/` holds checks the agent
never sees; each is executed with the candidate tree as the working directory
and a non-zero exit means failure. `meta.json` declares `allow` (the only paths
the agent may modify - anything else is scored as a collateral edit), the
checks, and the expected baseline.

A task is well-formed only if `selftest` shows `baseline=fail gold=pass`: a
fixture whose checks already pass proves nothing about an agent.

## Accounting

Every row records the exact model, host version, arm command, prompt hash,
fixture hash and timestamp, plus `usage` or `usage_note` when no usage record
could be parsed. Timeouts are never passes and are never zero-cost. See
`PREREGISTRATION.md` section 4 for the rules and why each exists.

## The two-host block

`python3 pilot.py --group N --groups 14 --arms omp+tezgah,omp-bare` ran every
task under both omp arms at k=3, in parallel on 2026-09-16; the opencode rows
come from the pilot block (25 tasks) plus a top-up on the three tasks imported
after it (`results/oc-new.jsonl`), and `results/c04-fixed.jsonl` supplies the
`reporting-language` task for all four arms. `python3 analyze.py
results/pilot-block.jsonl results/oc-new.jsonl 'results/omp-block/*.jsonl'
results/c04-fixed.jsonl` merges them (later files win, so a re-run replaces the
row it re-runs) and prints the pre-registered endpoints:

| arm | n | pass | pass rate (Wilson 95%) | CPS | median cost | median fresh in | median output | median cache read | timeouts |
|---|---|---|---|---|---|---|---|---|---|
| omp+tezgah | 84 | 80 | 0.95 (0.88-0.98) | $0.0058 | $0.0046 | 11,486 | 1,764 | 161,664 | 1 |
| omp-bare | 84 | 79 | 0.94 (0.87-0.97) | $0.0047 | $0.0030 | 3,160 | 1,841 | 133,248 | 0 |
| opencode+tezgah | 84 | 81 | 0.96 (0.90-0.99) | $0.0057 | $0.0048 | 28,258 | 1,012 | 111,232 | 0 |
| opencode-bare | 84 | 78 | 0.93 (0.85-0.97) | $0.0074 | $0.0062 | 36,624 | 835 | 147,712 | 0 |

336 runs, $1.87 spent, one model (`openrouter/deepseek/deepseek-v4-flash`).

1. **Host.** omp+tezgah 0.95 and opencode+tezgah 0.96 have overlapping intervals
   and the same CPS to four decimals ($0.0058 against $0.0057), so the host does
   not move the pass rate at this difficulty. On the bare arms omp is cheaper:
   median $0.0030 against $0.0062, CPS $0.0047 against $0.0074. Standardizing on
   omp therefore costs no quality and less money per run.
2. **Harness.** The per-task delta (tezgah - bare) averages +0.012 on omp (sign
   test p=1.000) and +0.036 on opencode (p=0.688). The corpus cannot resolve it:
   22 of the pilot's 25 tasks were saturated (every arm passed every repeat), so
   four to six tasks carry all the signal.
3. **The one family that isolates a contract rule does separate.** On
   `reporting-language` the tezgah arms score 3/3 (omp) and 2/3 (opencode) while
   both bare arms score 0/3: with the prompt in English, only the contract
   sentence makes the reply Turkish.
4. **Failures: 18 of 336 (5.4%)**, in `read-only-impact` (impact precision and
   recall), `root-cause-bug` (one 300 s timeout, counted as a failure and as
   cost), `constraint-compliance` and `reporting-language`.

Deviations from `PREREGISTRATION.md`, stated rather than hidden:

- **k=3, not k>=5.** This is a pilot block: it bounds the pass-rate question,
  not the per-cell cost variance section 2 asks for.
- **One model family and provider**, where section 2 asks for two.
- **`c04` changed mid-block and its earlier rows are void.** A Turkish prompt
  made every arm answer in Turkish, so the check measured the prompt rather
  than the rule; the prompt is now English. The detector also failed a reply
  that was in fact Turkish, because it matched Turkish markers as whole words
  where Turkish is agglutinative (`fonksiyonlari` never matched `fonksiyon`);
  it now matches stems. The twelve replies of the re-run agree with hand labels
  at 1.000 observed and Cohen's kappa 1.000, with the caveat that the labelling
  was not blind. Only `results/c04-fixed.jsonl` counts for this task.

## The hard family

The two-host block above cannot see the harness because the corpus is
saturated: 22 of the pilot's 25 tasks pass under every arm on every repeat.
Four tasks were added on 2026-09-16 for the one thing that block could not do -
separate arms - each aimed at a failure mode the pilot actually showed:

| task | family | what passing takes | why a plausible answer fails |
|---|---|---|---|
| `h01-exhaustive-callsite-audit` | exhaustive-enumeration | every call site of three functions: path, line, enclosing scope, callee | an answer written line by line misses the second callee on `report.py:22` |
| `h02-half-up-money-contract` | hidden-invariant | exact-cents rounding, half up | truncation (the baseline), `round()` on cents, and `round(x, 2)` on floats each fail rows the visible suite never covers - that suite is green before and after |
| `h03-ledger-instance-contract` | exact-contract | five clauses: per-instance entries, copy on construction, chainable `add`, the exact `ValueError`, a refused add changing nothing | no visible test touches `Ledger`, so a green suite says nothing about it |
| `h04-normalized-lookup` | long-horizon | one requirement reaching three files, keeping both the stored name and the caller's spelling | fixing `find_item` alone leaves `find_by_prefix`; normalising the displayed name fails |

Each is scored by hidden checks the agent never sees, and `h02`'s table is
measured rather than guessed: the rows that catch a float fix were found by
sweeping every (price, pct) pair at one-cent resolution, so each wrong
implementation fails several rows instead of one lucky one.

`h05-review-sweep` is the long one: six independent findings across five files,
one check per finding, so a row records how far an arm got rather than only
whether it finished.

### What calibration found

The first sweep run failed all four arms on the same two checks, which is the
signature of a task defect rather than a capability difference, and it was one:
the check required `load_items` to reject an *empty* name while the prompt only
said "a string `name`". The prompt now says non-empty, and the run whose rows
carry the old wording is kept as evidence in
`results/hard-calibration/h05-overstrict-validate.jsonl` instead of being
deleted or mixed into the block. The other failing check, `discount`, is fair:
a correct implementation written three different ways passes all six of its
rows, so those failures are the arms' answers, not the grader's.

### The hard-family block (2026-09-16)

Five tasks x four arms x k=3: 60 runs, $0.39, one model. The file set is
`results/hard-cells/`, one file per (task, arm) cell, merged with `analyze.py`:

| arm | n | pass | pass rate (Wilson 95%) | CPS | median cost |
|---|---|---|---|---|---|
| omp+tezgah | 15 | 12 | 0.80 (0.55-0.93) | $0.0089 | $0.0068 |
| omp-bare | 15 | 14 | 0.93 (0.70-0.99) | $0.0058 | $0.0049 |
| opencode+tezgah | 15 | 13 | 0.87 (0.62-0.96) | $0.0077 | $0.0064 |
| opencode-bare | 15 | 10 | 0.67 (0.42-0.85) | $0.0100 | $0.0064 |

The two-host block on the old corpus read 0.93-0.96 with every interval
overlapping; this one spreads, and the interval for `opencode-bare` now sits
below the one for `omp-bare`. Eleven of sixty runs failed and seven of those
failures are a single check, `discount` - the money rule stated tersely rather
than spelled out, which is what `h05` does on purpose.

What this supports, with n=15 per arm and still one model:

- **The ceiling is broken.** This corpus can separate arms where the old one
  could not, which was the point of building it.
- **The harness effect is still not resolvable, and now it points both ways**:
  tezgah is +0.20 against bare on opencode and -0.13 against bare on omp, with
  overlapping intervals. On `h05` specifically the split is tezgah 1/6 and bare
  4/6 pooled over hosts, which is the opposite of the pilot-era direction and is
  the single most interesting number in this file - it is also the smallest
  sample here.
- **The failures are the arms' answers, not the grader's.** A captured
  `omp+tezgah` run implements the fix as `Decimal(str(price)) * (100 - pct)/100`
  quantised to cents: it rounds the *result* to half up instead of the
  *discount*, which turns 9.80 at 2.5% into 9.56 where the contract says 9.55.
  Three correct implementations - `Decimal` on the discount, integer cents, and
  `int(cents * pct / 100 + 0.5)` - pass every row of that table, so the check
  scores the rule rather than a house style.

## Resuming a block

A block is a set of result files; a cell already recorded in one of them is never
re-run:

```sh
python3 pilot.py --group 0 --groups 4 --tasks 'h*' --out results/hard-cells --split cell            # fills only what is missing
python3 pilot.py --group 0 --groups 4 --tasks 'h*' --out results/hard-cells --split cell --dry-run  # what a resume still owes
python3 pilot.py ... --force                                                                        # re-run on purpose
python3 analyze.py 'results/hard-cells/*.jsonl'                                                     # merge any set of blocks
```

`--split cell` changes the unit of parallelism from the task to the
`(task, arm)` cell, one file per cell, so a task that takes minutes does not hold
its other three arms behind it:

```sh
for i in $(seq 0 15); do python3 pilot.py --group "$i" --groups 16 --tasks 'h*' \
    --out results/hard-cells --split cell & done; wait
```

The group slices the cells and never the task list, which a dry run shows before
anything is spent: sixteen groups report `1 of 16 cells` each, and the counts add
up.

A cell is `(arm, task, repeat, model)`: re-running with another model runs the
cell again instead of inheriting a row that model did not produce, and rows are
only ever skipped, never replaced. `analyze.py` merges file sets with later files
winning, so a block can be paused, extended and continued without a row lost.

Two rules keep the data intact. A task whose rows exist is never edited - a
defect found later is fixed by adding a task id, which is why `c04` and its
re-run are separate files rather than one rewritten one. And `results/` is
evidence: nothing in it is regenerated, trimmed or re-scored.

## Status

The runner, the arm table and the task set are new; the pilot, two-host and hard
blocks are the scored runs executed in this directory so far. The arm toggles
marked `flag_verified: false` in `arms.json` must be validated before their rows
are scored.

The task set is **33 tasks over 21 families**: eight hand-built tasks
(`tasks/t0*/`), twenty imported from the historical round-2 corpus (`tasks/c*/`),
and the five hard tasks above (`tasks/h0*/`), sharing one fixture at
`corpus/inventory/` with reference solutions in each task's `gold/`.
`python3 bench.py selftest` reads `32/32 fixtures discriminate`, plus one task
listed as skipped because it grades the reply rather than the tree
(`c04-turkish-explain-readonly`, whose check reads the run's captured transcript
with a published Turkish-marker detector and a stated threshold).

The corpus import restored the historical runner's separate rename check that
the conversion had dropped: `c03` and `c10` grade the rename itself
(`hidden/check_rename.py`) on top of the behavioural hidden test, because a
hidden test that only re-asserts existing behaviour cannot tell a completed
rename from no change at all. The two read-only impact tasks (`c19`, `c20`) score
precision and recall against a call-site set computed from the fixture with an
AST pass, and their prompts state the direct-vs-transitive rule that the
historical exact-equality scoring left ambiguous.

## The pilot block

`python3 pilot.py --group N --groups 10` runs one slice of the pilot: every task
x both opencode arms x 3 repeats, one model, one provider, groups in parallel.
Each group writes `results/<out>/g<N>.jsonl` (default `results/pilot`), so
parallel groups never interleave; `bench.py report --results` reads them. The
opencode half of the two-host block is the 150 rows of
`results/pilot-block.jsonl` plus the three-task top-up in
`results/oc-new.jsonl`. k=3 makes this a **pilot**, not the k>=5 block
`PREREGISTRATION.md` asks for: it bounds the pass-rate question, not the
per-cell cost variance.
