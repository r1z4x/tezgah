# benchmarks/arm-bench — the lab's task corpus and its blocks

`benchmarks/arm-bench/README.md` at commit `8db165a` on the branch `benchmarks/lab` (not in this
line's tree; read through the `armbench` worktree at
`/Users/rizax/orca/workspaces/tezgah/armbench`, whose HEAD is
`8db165a bench: pre-register E8, the round the attributable-evidence gate admits`). Grey class:
the repository's own report and its own instrument, not a paper record. Second record: the same
directory's `tasks/` listing, counted here with `ls tasks | wc -l` on the same worktree.

## What it is
The runnable harness/factor benchmark this repository keeps off `main`: `bench.py` (runner,
grader, aggregator, stdlib only), `arms.json` (one entry per (host, harness) arm), `tasks/<id>/`
with `meta.json`, `prompt.md`, `fixture/`, `gold/` and `hidden/`, and pre-registrations
(`PREREGISTRATION*.md`) that a number has to be read against. It reports pass rate with Wilson
intervals, cost, cost per solved task (CPS), paired McNemar, and the Stop rule's own refusal
classes folded from the ledgers.

## The corpus
`tasks/` holds **48 task directories** on this commit (`c01`-`c20` imported from the historical
round-2 corpus, `e01`-`e06`, `g01`-`g03`, `h01`-`h05`, and eight `t0*` hand-built tasks). The
README's own Status section says "**36 tasks over 24 families**", which is the count it was
written at and is stale against the 48 directories on disk; the directory count is the number
used in this line. `bench.py selftest` reads "34/34 fixtures discriminate" and lists two tasks as
skipped because they grade the reply rather than the tree (`c04-turkish-explain-readonly`,
`g02-conflicting-ask`).

## The blocks, in the repository's own units
Two-host block (25 tasks, k=3, 336 runs, $1.87, one model):

| arm | n | pass | pass rate (Wilson 95%) | CPS | median cost |
|---|---|---|---|---|---|
| omp+tezgah | 84 | 80 | 0.95 (0.88-0.98) | $0.0058 | $0.0046 |
| omp-bare | 84 | 79 | 0.94 (0.87-0.97) | $0.0047 | $0.0030 |
| opencode+tezgah | 84 | 81 | 0.96 (0.90-0.99) | $0.0057 | $0.0048 |
| opencode-bare | 84 | 78 | 0.93 (0.85-0.97) | $0.0074 | $0.0062 |

Hard family (5 tasks x 4 arms x k=5 x 2 model families = 200 runs, $1.60), pooled:
**40/50 for omp+tezgah, 40/50 omp-bare, 40/50 opencode+tezgah, 34/50 opencode-bare** - "the
harness effect is not there at that size", and "the per-model harness delta flips sign between
models". `h05-review-sweep` carries most of the spread (deepseek: 0/5 tezgah against 3/5 bare).

Gate family (2 tasks x 4 arms x k=3 = 24 runs): `g01` 3/3, 2/3, 3/3, 3/3 - "caught nobody";
`g02` **0/3 on all four arms** - "caught everybody", and a captured armed reply "noticed the
conflict, obeyed the literal ask, and amended the specification to fit".

The one clause that did separate: on `reporting-language`, with an English prompt, "the tezgah
arms score 3/3 (omp) and 2/3 (opencode) while both bare arms score 0/3".

## Why it is in this line
It is the corpus the adaptation answer has to be stated in, and it is the source of every number
this line may call the repository's own: 48 tasks, the two-host pass rates, CPS, and the two
nulls. Its own saturation statement - "**22 of the pilot's 25 tasks were saturated** (every arm
passed every repeat), so four to six tasks carry all the signal" - is the fact the environment
axis is proposed to answer, and its `g02` result is the case the counter-argument from ReAgent
predicts.

## Quality and limits
Grey: the repository's own instrument, so it is not independent of the thing it measures, and it
says so itself. Its stated deviations: k=3 not k>=5 in the pilot block, one model family and
provider where the pre-registration asks for two, and a task (`c04`) whose prompt was fixed
mid-block with its earlier rows voided. Its author states the corpus's own limit: 22 of 25 pilot
tasks saturated. Nothing in this line re-ran any of it; every figure above is the README's own.
