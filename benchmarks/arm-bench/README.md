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

## Status

The runner, the arm table and the task set are new; no scored run has been
executed in this directory yet. The arm toggles marked `flag_verified: false`
in `arms.json` must be validated before their rows are scored.

The task set is **28 tasks over 19 families**: eight hand-built tasks
(`tasks/t0*/`) and all twenty imported from the historical round-2 corpus
(`tasks/c*/`), sharing one fixture at `corpus/inventory/` with reference
solutions in each task's `gold/`. `python3 bench.py selftest` reads
`27/27 fixtures discriminate`, plus one task listed as skipped because it grades
the reply rather than the tree (`c04-turkish-explain-readonly`, whose check reads
the run's captured transcript with a published Turkish-marker detector and a
stated threshold).

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
Results land in `results/pilot/g<N>.jsonl`; `bench.py report --results` reads
them. k=3 makes this a **pilot**, not the k>=5 block `PREREGISTRATION.md` asks
for: it bounds the pass-rate question, not the per-cell cost variance.
