---
name: research
description: >
  Runs an auditable research line in the repository: the two-loop rhythm
  (bootstrap, inner experiment loop, outer synthesis), the workspace that holds
  its state, protocol-before-run so a prediction is provably older than its
  results, a six-dimension review of the claims before they are reported, and a
  provenance record of what the session decided. Use when a task's deliverable is
  evidence rather than a code change: a literature or reference review, a
  hypothesis to test, a comparison of variants, a benchmark or ablation, a
  research report or figure, or when the user says "research", "investigate",
  "araştır", "literatür", "hipotez", "deney", "ablation", "benchmark". Route the
  execution through the OpenResearch CLI when it is installed. Do NOT use for
  code discovery ("where is X", "who calls Y") - that is the code graph.
---

# research

A research task's deliverable is evidence. Everything here exists so that the
evidence survives the session that produced it: the state on disk, the protocol
committed before the run, the claims with their falsification criteria, and the
review that decided what the evidence actually supports.

## The engine: OpenResearch

Execution goes through the `orx` CLI when it is installed, never ad-hoc
scripting, and its cardinal rules are not style preferences - breaking one
silently invalidates the run:

- never edit a node once a run has answered it; branch a child instead,
- the run command and environment are a fixed contract identical on every node,
- vary the committed code/config, never CLI args or env knobs,
- grow the experiment tree downward, not sideways.

Load its manual before driving it: `orx skill`, then the module for the step
(`orx skill experiment-tree`, `orx skill lit-review`, `orx skill evidence`).
Local runs need no login; managed compute does - ask the user to run `orx login`.
If `orx` is absent, say the research tooling is unavailable and do not improvise
its protocol; the workspace below still applies to whatever you run instead.

The contract's research rule is armed by task class; the kill switch is
`research-off`.

## The workspace

One directory per research line, `<repo>/.tezgah/research/<slug>/`:

| Path | What it holds |
|---|---|
| `state.json` | the question, phase, direction, the locked evaluation (metric, baseline) and the hypothesis list |
| `log.md` | the decision timeline: one line per decision, experiment, dead end or pivot, with the evidence that drove it |
| `findings.md` | `## What we know`, `## Patterns`, `## Lessons`, `## Open questions` |
| `claims.jsonl` | one claim per line: `statement`, `status`, `provenance`, `falsification`, `proof`, `dependencies` |
| `experiments/<hypothesis>/` | `protocol.md`, `results.jsonl`, `analysis.md` |
| `literature/` | one note per source, saved when you read it, not later |
| `to_human/` | reports for the person paying for the research |

Scaffold and check it with the CLI (`~/.config/tezgah/bin/tezgah-research`, or
`bin/tezgah-research` in the checkout):

```sh
~/.config/tezgah/bin/tezgah-research init my-line --question "does X hold under Y?"
~/.config/tezgah/bin/tezgah-research check    # 0 clean, 1 broken rule, 2 misuse
~/.config/tezgah/bin/tezgah-research status
```

`check` enforces the rules a session tends to skip: `protocol.md` committed
before `results.jsonl` - decided on the commit graph, so two commits inside the
same second or a rebase do not trip it, while a protocol *edited* after the
results is refused - a falsification criterion and evidence on every claim, a
provenance tag on every claim, an analysis for every experiment, and a findings
file that answers all four questions. It warns rather than fails while the
results are still uncommitted, because there is no order to check yet. Run it
before reporting a result, and fix what it names.

## The loop

**Bootstrap.** Search the literature with more than one source, save every source
to `literature/` as you go, identify the gap, form testable hypotheses (see
Ideation below), and lock the evaluation before running anything: the metric, the
baseline, the threshold. Write it into `state.json` - a criterion chosen after
seeing results is not a criterion.

**Inner loop.** One hypothesis at a time:

1. Write `protocol.md`: what changes, what it predicts, why, and what result would
   falsify it. **Commit it before the run.** That commit is the temporal proof that
   the prediction came first, and `check` verifies it against the commit graph -
   editing the protocol after the results are in is refused, not silently allowed.
2. Run it through the engine.
3. Sanity-check the run before trusting it (converged, no NaN, baseline
   reproduces, the input is what you think it is).
4. Record the raw result in `results.jsonl`, then write what it means in
   `analysis.md`. Label each outcome CONFIRMATORY (predicted by the protocol) or
   EXPLORATORY (noticed during the run).
5. A negative result is a result: record what it rules out.

**Outer loop.** Every few experiments, stop and synthesise: cluster the outcomes,
ask why the successes and failures happened, update `findings.md`, then choose a
direction in `state.json` - `deepen`, `broaden`, `pivot` or `conclude` - and say
why in `log.md`. Non-linearity is normal: return to the literature when results
surprise you, and pivot when the evidence kills the original question.

**Conclude.** Sufficient support for at least one hypothesis (or a coherent set of
negative results), key ablations done, and `findings.md` readable enough that a
human could write the abstract from it.

## Ideation

When the hypotheses are weak or the run is stuck, generate instead of grinding:

- diverge first: list candidate mechanisms and framings without judging them,
- force distance: what would the neighbouring field call this problem, and what
  would it try first,
- combine two known things (bisociation) before inventing a third,
- then converge: keep what is testable with a clear prediction inside the budget,
  drop the rest, and say in `log.md` what was dropped and why.

## Review before reporting

Evidence does not review itself. Before a claim leaves the session, score it on
six dimensions and write the findings, most severe first, each with a **verbatim
quote** from the artifact - a finding that cannot quote its evidence is not a
finding:

| Dimension | The question |
|---|---|
| Evidence relevance | does the cited run actually support what the claim says, in substance? |
| Falsifiability | could an independent person run the stated criterion and get a yes/no? |
| Scope calibration | does the claim assert exactly what the evidence covers, no more, no less? |
| Argument coherence | does the story run observation → gap → insight → solution → claim → evidence? |
| Exploration integrity | are the dead ends and pivots recorded honestly, or does the tree read as post-hoc justification? |
| Methodological rigour | baselines, ablations, variance, runs, and a metric that measures the claim |

Severity: `critical` (the claim cannot stand as written), `major`, `minor`,
`suggestion`. Report the score per dimension and the severity-ranked findings;
state plainly what the evidence does not show. Do not soften a null result, and do
not promote an exploratory finding to confirmatory after the fact.

## Provenance, at the end of the session

Research is a sequence of decisions, and the next session does not remember them.
Before finishing, append to `log.md` and update `state.json.sessions` with the
events of this session, each tagged with where it came from:

| Tag | When |
|---|---|
| `user` | the user stated or confirmed it |
| `ai-suggested` | you inferred it and nobody confirmed it |
| `ai-executed` | you ran it or wrote it |
| `user-revised` | you suggested it and the user corrected it |

Default to `ai-suggested` when unsure - never tag an inference as `user`. Record
decisions, experiments, dead ends, pivots and new claims; skip routine reads,
formatting and installs. A session that ends without this leaves the next one
guessing, which is the failure this whole workspace exists to prevent.

## Where this comes from

The two-loop rhythm, the workspace layout and the six review dimensions adapt the
orchestration layer of Orchestra Research's MIT-licensed `AI-research-SKILLs`
library (its `autoresearch`, `ara-rigor-reviewer` and `ara-research-manager`
skills) to tezgah's contract: the execution engine here is OpenResearch, the
reporting language is the contract's, the checks are `tezgah-research`'s own, and
nothing is copied verbatim.
