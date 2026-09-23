# arm-bench README — this repository's own harness/factor benchmark (practice source)

`benchmarks/arm-bench/README.md` at commit `866cea7` on the branch `benchmarks/lab`
(not in this line's tree; read through the `armbench` worktree on this machine).
Grey class: the repository's own report, not a paper record.

## What it is
The runnable harness/factor benchmark this repository keeps off `main`: a runner, grader
and aggregator (`bench.py`, stdlib only), `arms.json` with one entry per (host, harness)
arm, a task corpus in families (pilot, hard, gate), and **pre-registrations
(`PREREGISTRATION*.md`) that a number has to be read against**. It reports pass rate with
Wilson intervals, cost, CPS, paired McNemar, and the Stop rule's own refusal classes
folded from the ledgers.

## The numbers this line leans on
- Two-host block: 336 runs, omp+tezgah 0.95 (0.88-0.98), omp-bare 0.94 (0.87-0.97),
  opencode+tezgah 0.96 (0.90-0.99), opencode-bare 0.93 (0.85-0.97) — "the host does not
  move the pass rate at this difficulty", and the harness delta is +0.012 (omp, p=1.000)
  / +0.036 (opencode, p=0.688). 22 of 25 pilot tasks were saturated.
- Hard family (5 tasks x 4 arms x k=5 x 2 model families = 200 runs): pooled **40/50 for
  omp+tezgah, 40/50 omp-bare, 40/50 opencode+tezgah, 34/50 opencode-bare**; the
  per-model harness delta flips sign between models.
- The one family that isolates a rule is `reporting-language`: with an English prompt,
  only the contract sentence makes the reply Turkish (3/3 and 2/3 armed against 0/3 on
  both bare arms).
- Gate family: `g01` caught nobody (every arm left `tests/` byte-identical); `g02`
  **caught everybody** — all twelve runs, armed arms included, changed
  `src/formatter.py` to satisfy a test that contradicts the package's documented rule,
  and a captured armed reply noticed the conflict, obeyed the literal ask and amended the
  specification to match.

## Why it is in this line
It is the evidence that the harness's *behavioural* effect is unresolved at the sizes this
repo has run, which is the baseline every proposed change here has to beat. It is also the
method (pre-registration, per-cell attribution) that E1-E5 follow in the mechanical half.

## Quality and limits
The repository's own instrument, so it is not independent of the thing it measures; it
says so itself and lists its deviations (k=3 not k>=5, one model family and provider where
the pre-registration asks for two, a task whose prompt was fixed mid-block). Its author
states the corpus's own limits: 22 of 25 pilot tasks saturated.
