# env-scaling — post-training environment scaling: what it is, what it requires, what is adaptable here

## Answer, in one paragraph

It can be adapted in exactly one of its two halves, and only against this repository's own
numbers. The training half is unreachable: every source in this line ends in a trained policy and
this repository has no training loop, no weight access and no reward signal it owns, so none of
their headline figures is available. The evaluation half is available at zero training cost, and
it is the same move the sources that measure quality against count all make: with the model axis
frozen and the corpus saturated, the environment axis is the only remaining source of variance. In
this repository's own units that means working on the tasks that can still discriminate - the
lab's corpus holds 48 task directories, the pilot block's read was 0.95 / 0.94 / 0.96 / 0.93 at
k=3 on 25 tasks with cost per solved task between $0.0047 and $0.0074, and the hard family pools
to 40/50 - so any environment-side change has at most the ~3 non-saturated pilot tasks plus the 5
hard tasks plus the 3 gate tasks to move a pass rate, at the same per-run cost. What it would buy
is not a better model, which no change here can produce; it is a corpus that can resolve a harness
effect at all, and a measured denominator for claims about this layer. Nothing in this paragraph
was measured by this line: each number is the artifact's own, and the artifact names where it
came from.

## What was established

- **The term denotes the environment side of post-training.** Four senses travel under it - count
  (`literature/2604.18292-agent-world.md`), generation (`literature/2504.21798-swe-smith.md`,
  `literature/2504.07164-r2e-gym.md`, `literature/2609.04148-terminal-universe.md`), evolution
  (`literature/2609.04128-environment-evolution.md`, `literature/2608.19197-spade.md`) and
  distribution (`literature/2608.03571-beyond-simply-environment-scaling.md`), with
  `literature/2608.19880-envharness-rigger.md` as the layer that reshapes an existing environment
  while leaving its verifier alone. A reader who keeps only one sentence should keep Environment
  Evolution's: "Scaling interactive and verifiable environments is critical for training terminal
  agents."
- **The count relation is measured, and it saturates.** Agent-World: 0 to 1,978 environments,
  18.4% to 38.5%, gains most pronounced 10 to 100 and 100 to 500, diminishing but positive 500 to
  2,000 (`literature/2604.18292-agent-world.md`). EnvHarness: reshaped environments keep rising
  47.67% to 54.79% while original and generated ones flatten
  (`literature/2608.19880-envharness-rigger.md`).
- **Quality beats count in every source that measured both, and the counter-argument is measured
  rather than editorial.** 30 selected environments against 170
  (`literature/2608.03571-beyond-simply-environment-scaling.md`); fewer than 30% of environments
  giving 106% and 30% larger RL gains, against an audit finding over 60% of a synthetic set
  defective (`literature/2608.22631-river-reward-integrity.md`); one repaired environment lifting
  its model from 16.2% to 38.5%, and shallow versus deep on the same domains 80.0 to 75.0 against
  80.0 to 85.0 (`literature/2607.28074-echoverse.md`).
- **The designer loop the question asked about is closed by rollouts, not by weights.** EnvRigger's
  Validate stage runs fresh rollouts in the reshaped environment and accepts, rejects or refines a
  component on that evidence (`literature/2608.19880-envharness-rigger.md`). That is the one loop
  in the set a repository without training can copy in shape.
- **The corpus's own construction is a bias this repository shares.**
  `literature/2609.reagent-scenario-co-design.md` names the construction-induced selection bias
  toward feasible requests, and this repository's `g02` gate task - all twelve runs amending a
  specification to satisfy a contradictory test - is an instance of the interaction such a corpus
  omits (`literature/arm-bench-readme-8db165a.md`).
- **What the repository already does on the environment side.** `hooks/tezgah_gate.py`'s refusal
  classes are a filtered action space, `plans/open/` and the branch rule are an allowlist, and the
  repository skeleton is the initial state - EnvHarness's `Contract` and `Stage` under local
  names, with the verifier left alone, which is the invariant EnvHarness itself insists on.
- **This repository's own numbers, as the artifact states them.** `false_completion / claims`
  0.224 over 1454 ledgers, the only ratio in the ledger that measures the layer's effect rather
  than its traffic (`docs/evidence.md`); 8 failure shapes over 1661 ledgers, `drift` widest at 177
  sessions and 225 fires, `task` 80 and 168, `consent` 46 and 95
  (`plans/open/004-failure-driven-refinement.md`); the lab's blocks as listed in the answer above
  (`literature/arm-bench-readme-8db165a.md`).
- **The line's artifacts.** 13 literature notes, 13 `literature/INDEX.jsonl` rows, 15 claims
  (12 `literature`, 2 `code`, 1 `derivation`, every row `scope: derived`), `findings.md` answering
  all four sections, and this report. The `experiments/` directory `init` scaffolds was removed
  again because it held nothing: a literature screen has no run command, so nothing was filed and
  no `predictions.jsonl` was created - a prediction row has to name a metric and a value to move,
  and this line moved no number.

## What this line does not show

- **None of it was measured on this repository.** Every number above is the cited artifact's own.
  No model call, no arm-bench run and no paid round happened in this line; the repository's own
  figures are quoted from `docs/evidence.md`, `plans/open/004-failure-driven-refinement.md` and
  the arm-bench README at `8db165a`, not re-measured. A reader who wants one of these numbers to
  be a fact about this layer has to run the round that produces it.
- **No transfer is claimed from any source to this repository.** The sources' policies are
  post-trained on their own environments with their own verifiers and their own benchmarks; the
  direction of the argument here is that their *shape* is copyable, not that their effect size is.
  The paper headings in `findings.md` are marked as the sources' own precisely so they are not
  read as this repository's.
- **The adaptation's own effect size is unmeasured and unpredictable.** The claim that raising the
  unsaturated share would let the corpus resolve a harness effect is an argument, not a
  measurement, and it is contradicted by the two published nulls until a round says otherwise: the
  harness delta of +0.012 and +0.036 with per-model sign flip, and the hard family pooling at
  40/50 for three arms (`literature/arm-bench-readme-8db165a.md`).
- **The adaptation half has now been run, and it did not move the number it was aimed at.** The
  corpus change (`tasks/h06-exact-split-sum`, a swept hidden verifier over the documented split
  contract) was built and proved well-formed for free (selftest `48/48`; five plausible wrong
  implementations fail 1,239-1,784 of 2,828 cells while two correct ones pass every cell), then
  measured on the one pre-registered cell: `opencode-bare` passed **12 of 12** rows on
  `deepseek/deepseek-v4-flash` (Wilson 95% 75.7-100.0), **0 rows** carried the shape this family
  exists to produce (visible suite green, hidden invariant failed), CPS $0.006389, $0.082890 spent
  for the 13 rows filed - so both of the protocol's predictions were falsified and the count of
  corpus tasks that can discriminate (C15's first half) is where C15 left it, because on this arm
  the new task is saturated (`experiments/E1-env-adapt-h06/analysis.md`, C17). The floor the cell
  was spent on - a 0/5 `h02` opencode-bare seed on OpenRouter - did not transfer to a second
  contract task, and the task's own contract shape and the provider change are confounded in that
  comparison rather than separated by it. The rows declare `scope: real` (a paid run against a real
  provider) over this line's generated task fixture, which is the same pair of facts the sibling
  experiment E2 labelled `fixture`; the note is here so neither reading is read as the other.
- **Why the round needed a second provider.** The first attempt was blocked by account credit
  (`total_credits 130` against `total_usage 130.18`, with a sibling session's rows all returning
  HTTP 402), recorded in the protocol's head note and the lab's `PREREGISTRATION-H06.md` sections
  13-14; amendment 1 moved the cell to the DeepSeek direct provider and changed no arm, task, `k`
  or threshold.
- **The adaptation half was never run, and could not be from this branch.** Both halves of the
  answer are design, not execution: when this bullet was written no model call, no arm-bench round
  and no corpus change had happened in this line (the bullet above records the corpus change that
  was written afterwards, uncommitted, on a worktree branch of its own). The environment half's
  target, `benchmarks/arm-bench`, is not in this tree - it
  lives on branch `benchmarks/lab`, and the branch this line was written on holds only
  `benchmarks/codegraph-bench` - so the task corpus, its pre-registrations and its attribution gate
  are absent here and the environment-side move (C15's first half) has no artifact to act on. The
  session-side half (C15's second half) is reachable without a run, since it touches
  `hooks/tezgah_gate.py` and `plans/open/`, and it too was not exercised in this line. What is
  stated above is therefore a feasibility split read off the cited artifacts, not a change that was
  made: a reader who wants the adaptation's effect size has to run the round on the branch that
  holds the corpus.
- **The corpus size is disputed inside its own artifact.** The line uses 48, the number of task
  directories on the branch; the README's own Status section says "36 tasks over 24 families".
  Both are stated, and this line chose the directory count.
- **One source is not independently recorded.** `literature/2609.reagent-scenario-co-design.md`
  has no arXiv id, no OpenAlex record and no venue; its second record is a preprints.org listing
  surfaced by web search, because the page itself returned HTTP 403 from this machine.
- **The screening is not exhaustive and not double-read.** Two discovery routes were used
  (alphaXiv keyword search, and OpenAlex, which produced nothing usable for this term in 2026), a
  single reader screened them, and no search was systematic across venues. A source that uses the
  term differently and did not surface is not excluded by anything here.
- **Four limitations the sources state about themselves, carried forward rather than resolved:**
  EnvHarness's scaling curve has no seed count; Echoverse's and Environment Evolution's comparisons
  are against their own re-implementations; Agent-World's environment-count curve is over its own
  generated environments and task suite; and RIVER's 60%/40% corpus split is measured by its own
  rubrics on one collection.
- **What would falsify the answer.** An arm-bench block over all 48 tasks, or a paid round in which
  an environment-side change moves a pass rate, would move claim C15 from `supported` to
  `revised`; a source defining environment scaling as model-side scaling would falsify C01. Both
  are named in `claims.jsonl` with their own falsification criteria.
