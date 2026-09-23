# Findings

The question: what does post-training environment scaling mean in 2026, what does it require,
and what of it could this repository adapt without a training loop. Thirteen sources are noted
under `literature/`; nothing was run, so `experiments/` holds nothing and no claim here is a
measurement made on this repository.

## What we know

### What the term denotes

In the 2026 literature the term denotes the supply of *interactive, verifiable environments* as
the object that post-training scales, and it is stated in that form by Environment Evolution:
"Scaling interactive and verifiable environments is critical for training terminal agents"
(`literature/2609.04128-environment-evolution.md`). The same paper states the sense in which the
axis is a prerequisite rather than a data source: environments "are what agent post-training
actually requires: each can be re-queried into many verifiable tasks and provides execution
feedback, whereas a trajectory is a single frozen demonstration" is Terminal-Universe's wording
for the same relation (`literature/2609.04148-terminal-universe.md`).

Four senses travel under the one phrase, and a reader has to keep them apart:

1. **Count of environments.** Train on more environments: Agent-World's count curve, 0 to 1,978
   environments moving the average from 18.4% to 38.5% (`literature/2604.18292-agent-world.md`).
2. **Generation of environments.** Build the environments instead of collecting them: SWE-smith's
   50,137 instances over 128 repositories for about $1360 and 295 GB
   (`literature/2504.21798-swe-smith.md`), R2E-Gym's more than 8.7K procedural tasks
   (`literature/2504.07164-r2e-gym.md`), and their 2026 successors
   (`literature/2609.04148-terminal-universe.md`).
3. **Evolution of environments.** Keep the count fixed and change what the environments demand:
   Terminal-Bench 2.1 moving 14.4 and 18.0 percentage points over the competing paradigms at a
   constant environment count (`literature/2609.04128-environment-evolution.md`), and SPADE
   making the environment itself a trained component whose reward is the agent's regret
   (`literature/2608.19197-spade.md`).
4. **Distribution of environments.** Choose which environments, not how many: 30 ability-selected
   environments beating the full 170 (`literature/2608.03571-beyond-simply-environment-scaling.md`).

The composite definition this line will use: environment scaling is the practice of expanding,
generating, evolving or selecting the *environment and task distribution* a policy is post-trained
on, in the place where scaling used to mean more parameters, more data or more samples.

### What it requires that this repository does not have

| Prerequisite | Named in | Host CLI could supply? | This layer could supply? |
|---|---|---|---|
| A policy training loop (rollout batch -> gradient -> updated weights) | every source in `literature/`; the clearest is State2State's GRPO loop in `literature/2608.04934-state2state.md` | No. The host runs an agent; it does not own a training loop over the model | No. This layer edits text and records evidence; it has no loop and no optimizer |
| A reward or verifier per task | `literature/2504.07164-r2e-gym.md` (execution-based versus execution-free verifiers), `literature/2608.22631-river-reward-integrity.md` (verifier quality as the governing term) | No. A host CLI scores nothing | **Partly.** The gate's refusal classes and arm-bench's hidden checks are the only scorers here, and they already exist |
| Rollouts at volume | `literature/2608.19197-spade.md` (a 400-step run, a learnable share of about one third), `literature/2609.04128-environment-evolution.md` (turns 50 to 190, tokens 50k to 232k) | The host can execute a rollout, but nothing here can issue them at volume without spending money | No. `benchmarks/arm-bench` is the only rollout machinery and it is paid per run |
| Weight access | implicit in every source; explicit in SPADE's two roles sharing one set of parameters, `literature/2608.19197-spade.md` | No. The base model is frozen and owned by the host | No |
| A task distribution | `literature/2609.reagent-scenario-co-design.md` (a distribution built from known-feasible paths under-samples conflicts) | No | **Yes, partly.** 48 hand-written tasks with hidden checks (`literature/arm-bench-readme-8db165a.md`) |

The honest reading of that table: two of the five prerequisites are partly present here, and they
are the two the counter-argument sources say matter most - a verifier and a task distribution.
The three that are absent are the three that make the word "training" true.

### What is actually adaptable here

**(a) Environment-side adaptation for evaluation.** When the model is frozen and the corpus is
saturated, the environment axis replaces the model axis: it is the only remaining source of
variance in a harness measurement. This is not a coincidence of this repository - it is the
statement EnvHarness makes from the other direction, that "targeting diagnosed vulnerabilities is
more effective than merely scaling training episodes through specialized generation"
(`literature/2608.19880-envharness-rigger.md`), and that RIVER makes about selection
(`literature/2608.22631-river-reward-integrity.md`).

- *Artifact it would touch:* `benchmarks/arm-bench` on branch `benchmarks/lab` - the task corpus
  (`tasks/<id>/meta.json` holds the `allow` list and the hidden checks), the pre-registrations,
  and the attribution gate that the `E8` pre-registration adds
  (`literature/arm-bench-readme-8db165a.md`).
- *Number it would move:* the count of tasks in the corpus that can discriminate at all. The
  README's own reading is that "22 of the pilot's 25 tasks were saturated ... so four to six tasks
  carry all the signal", and the four hard tasks were added for exactly that reason. Shaping the
  environment - deepening a fixture, adding a hidden invariant, or replacing a saturated task -
  raises the unsaturated share, which is the denominator under every pass rate the lab reports.

**(b) Environment shaping for the agent in a session.** The other half needs no corpus and no
run: it is the environment the agent is handed before it acts. This repository already does three
of the four things the sources name.

- *Artifact it would touch and what it already does:* `hooks/tezgah_gate.py` refuses the cheap
  route before it runs (the `shortcut`, `sink` and `consent` classes); `plans/open/` and the
  branch rule are an allowlist of what a session may touch at all; the repository skeleton
  (`docs/`, `plans/`, `skills/`, `tests/`) is the initial state a session is dropped into. Those
  are EnvHarness's `Contract` and `Stage` components under this repository's names - a filtered
  action space, a rewritten initial state - with the one property EnvHarness insists on: the
  verifier (`tests/`, the hidden checks, the Stop rule) is left alone
  (`literature/2608.19880-envharness-rigger.md`).
- *Number it would move:* the per-rule refusal counts, which are also the only dense behavioural
  signal this repository has - eight shapes over 1661 ledgers, `drift` reaching 177 sessions with
  225 fires, `task` 80 sessions with 168 fires and `consent` 46 with 95
  (`plans/open/004-failure-driven-refinement.md`), against a corpus-wide
  `false_completion / claims` of 0.224 over 1454 ledgers (`docs/evidence.md`).

**(c) The two that are not adaptable, stated as such.** The *generation* pipelines need the
training loop they feed (SWE-smith and R2E-Gym both end in a fine-tuned model), and the
*evolution* systems need either that loop (Environment Evolution, Agent-World) or weight-sharing
self-play (SPADE). What survives without them is (a) and (b).

### Expected efficiency, in this repository's own units only

No number below was re-measured; each is the artifact's own.

- **Pass rate at k on the lab's 48 tasks.** There is no block over all 48. The two-host block
  covers 25 tasks at k=3 and reads omp+tezgah 0.95 (0.88-0.98), omp-bare 0.94 (0.87-0.97),
  opencode+tezgah 0.96 (0.90-0.99), opencode-bare 0.93 (0.85-0.97); the hard family covers 5
  tasks at k=5 and pools to 40/50 for three arms and 34/50 for the fourth; the gate family covers
  2 tasks at k=3. A change scoped to all 48 tasks would be read against a corpus the lab has
  never run whole (`literature/arm-bench-readme-8db165a.md`).
- **Cost per solved task.** $0.0058 (omp+tezgah), $0.0047 (omp-bare), $0.0057 (opencode+tezgah),
  $0.0074 (opencode-bare), N=84 per arm, total $1.87 for 336 runs
  (`literature/arm-bench-readme-8db165a.md`).
- **Corpus metrics.** `false_completion / claims` 0.224 across 1454 ledgers, the only ratio in
  the ledger that measures the layer's effect rather than its traffic (`docs/evidence.md`), and
  eight failure shapes over 1661 ledgers with `drift` at 177 sessions / 225 fires, `task` 80/168,
  `consent` 46/95, `sink` 28/39, `shortcut` 26/33, `retry` 15/25, `secret` 13/18, `loop` 6/7
  (`plans/open/004-failure-driven-refinement.md`).

**What this means for the adaptation, in those units.** An environment-side change to the lab is
the only one of the two halves that can move a *pass rate*: it works on the ~3 non-saturated
pilot tasks plus the 5 hard tasks plus the 3 gate tasks, where the harness delta is currently
+0.012 (omp, p=1.000) and +0.036 (opencode, p=0.688) and pooled 40/50 on the hard family, for a
CPS between $0.0047 and $0.0074. A session-side change to the gate or the allowlist can move the
refusal counts and the 0.224 ratio without spending anything, but as of the two published rounds
it has not moved the pass rate.

### What is NOT transferable, and why

- **No training loop.** Every source's endpoint is a trained policy: GRPO in State2State, SPADE,
  Agent-World, ReAgent, RIVER, Environment Evolution. Nothing here can take that step, so the
  headlines of every source in `literature/` - "+8.1 points", "71.5%", "34.3% to 59.1%" - are
  structurally out of reach, not merely unmeasured here.
- **No weight access.** SPADE's environment designer is the same weights as the reasoner; AHE's
  ten-iteration loop edits a harness and re-runs the model. Neither is possible against a frozen,
  host-owned base model.
- **Saturated corpus.** "22 of the pilot's 25 tasks were saturated", so the pilot block's
  intervals overlap by construction; the environment work would have to raise the unsaturated
  share before any harness number could resolve
  (`literature/arm-bench-readme-8db165a.md`).
- **Two published nulls.** The harness delta did not replicate across model families (+0.012 and
  +0.036, per-model sign flip; the hard family pooling at 40/50 for three arms), and `g02`
  caught every arm at 0/3, including the armed ones
  (`literature/arm-bench-readme-8db165a.md`). A proposal that adds environments does not inherit
  a reason to expect a different outcome; it inherits two rounds that found nothing on a corpus
  where the effect was expected.

## Patterns

- The term scales the *environment*, not the model: `literature/2609.04128-environment-evolution.md`
  has "Scaling interactive and verifiable environments is critical for training terminal agents",
  and `literature/2609.04148-terminal-universe.md` has "environments are what agent post-training
  actually requires". Every 2026 source that defines it uses the same sentence shape. [C01, C02]
- The count/capability curve is positive but saturating: `literature/2604.18292-agent-world.md`
  reads 18.4% to 38.5% over 1,978 environments with gains
  most pronounced 10 to 100 and 100 to 500, and `literature/2608.19880-envharness-rigger.md` reads
  47.67% to 54.79% for reshaped environments while original and generated ones flatten. Every
  source that measures the curve puts the elbow inside the first few hundred environments. [C03, C04]
- Selection and repair beat addition wherever both were measured, and `literature/2608.03571-beyond-simply-environment-scaling.md` is the first: it reads 30 selected environments
  against 170 (95.6% against 43.4% relative gain), then
  `literature/2608.22631-river-reward-integrity.md` reads fewer than 30% of environments improving
  RL gains by 106% and 30%, and `literature/2607.28074-echoverse.md` reads one repaired
  environment lifting its model from 16.2% to 38.5%. [C05, C06, C07]
- A corpus built from paths already known to work under-samples the conflict interactions, and `literature/2609.reagent-scenario-co-design.md` names the selection bias toward feasible
  requests, while this repository's own `g02` result - all twelve runs amending a specification to
  satisfy a contradictory test - is an instance of the interaction such a corpus omits
  (`literature/arm-bench-readme-8db165a.md`). [C08, C09]
- The cheapest environment-side lever in the set is the verifier, not the environment count, and `literature/2504.07164-r2e-gym.md` is the source: it reads the hybrid verifier's 42-43% to 51%,
  while `literature/2608.22631-river-reward-integrity.md` reads the rubric filter that removes more
  than 60% of a synthetic set, and `literature/2607.28074-echoverse.md` reads the grounded,
  database-read grader. [C07, C10]

## Lessons

- A literature screen is a legitimate research line even with no run: the layer's own rules allow
  it, `init` scaffolds the same four files, and the honest artifacts are the notes, the index and
  the report's limits section. What it cannot carry is a prediction bound to a commit, so
  `predictions.jsonl` stays absent rather than being filled with a row that names no measurable
  change.
- Reading the term from the sources rather than from search snippets changed the answer twice:
  the count/capability relation turned out to be measured and saturating rather than absent, and
  the counter-argument turned out to be measured rather than editorial. Both would have been
  guessed wrong from titles alone.
- Every source read here ends in a trained policy, which is why the adaptation answer is two
  halves and not one: the evaluation half is available at zero training cost and the training half
  is not available at all.

## Open questions

- Would reshaping a task in `benchmarks/arm-bench` - deepening a fixture, or replacing a saturated
  pilot task with a hidden invariant - raise the unsaturated share enough to let the corpus
  resolve a harness effect? That is a pre-registration and a paid round, and the spend is the
  user's call (the same blocker `plans/open/004-failure-driven-refinement.md` item 6 records).
- Does the attributable-evidence gate in the `E8` pre-registration already carry the verifier half
  of the adaptation, in which case item (a) reduces to writing environments rather than to
  building a scorer?
- Is the `drift` rule's 177-session reach the right session-side target, given this repository's
  own C04/C11 evidence that it also fires on long careful turns?
  (`plans/open/004-failure-driven-refinement.md`)
