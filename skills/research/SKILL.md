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
| `claims.jsonl` | one claim per line: `statement`, `status`, `provenance`, `falsification`, `proof`, `dependencies` - recorded with `tezgah-research claim <slug>`, never by editing the file |
| `experiments/<hypothesis>/` | `protocol.md`, `results.jsonl`, `analysis.md` |
| `literature/` | one note per source, saved when you read it, not later |
| `to_human/` | reports for the person paying for the research |

Scaffold and check it with the CLI (`~/.config/tezgah/bin/tezgah-research`, or
`bin/tezgah-research` in the checkout):

```sh
~/.config/tezgah/bin/tezgah-research init my-line --question "does X hold under Y?"
~/.config/tezgah/bin/tezgah-research check    # 0 clean, 1 broken rule, 2 misuse
~/.config/tezgah/bin/tezgah-research status
~/.config/tezgah/bin/tezgah-research claim my-line   # one JSON object on stdin
```

`claim` reads that object from stdin and appends it as one line: exit 0,
`claim <id> recorded`; exit 1 with one `FAIL <slug>: <problem>` line per problem
and nothing written - including when `claims.jsonl` cannot be locked within a
second; exit 2 when the slug is missing or unknown, or stdin is not one JSON
object. Record a claim with the command, never by editing the file: a hand edit
is an unlocked read-modify-write of the file every claim of the line lives in,
while the command appends under an exclusive lock on that file and refuses rather
than writing unlocked.

`check` enforces the rules a session tends to skip: `protocol.md` committed
before `results.jsonl` - decided on the commit graph, so two commits inside the
same second or a rebase do not trip it, while a protocol *edited* after the
results is refused - a falsification criterion and evidence on every claim, a
provenance tag on every claim, an analysis for every experiment, a findings file
that answers all four questions, and a claim's `proof` resolving to an experiment
directory that actually has results. It warns rather than fails while the results
are still uncommitted, because there is no order to check yet. Run it before
reporting a result, and fix what it names.

### Evidence fidelity

A number that travelled through three summaries is no longer evidence. The same
rules the domain library enforces on a compiled artifact apply here:

- **Exact numbers, never rounded.** `0.8471` is a result; "about 85%" is a memory
  of one. Round only in the sentence aimed at a human, and say what the raw value
  was.
- **A derived view is not the source.** A filtered or merged table is a new file
  named as derived, never presented as the run's own output.
- **Every result row carries its source** in `results.jsonl` (the run id, command
  or node) and every recorded fact in `analysis.md` points at the row it came
  from.
- **Wording cannot outrun the evidence type.** Validation metrics do not support
  a claim about training dynamics; a correlation does not support a causal verb;
  one seed does not support "always".

## The loop

**Bootstrap.** Search the literature with more than one source, save every source
to `literature/` as you go, identify the gap, form testable hypotheses (see
Ideation below), and lock the evaluation before running anything: the metric, the
baseline, the threshold. Write it into `state.json` - a criterion chosen after
seeing results is not a criterion.

Never write a citation from memory. Verify each one against two of Semantic
Scholar, CrossRef (DOI content negotiation), arXiv or OpenAlex, and put
`[CITATION NEEDED]` in the text rather than a plausible-looking reference that
does not exist - hallucinated references are the single most common defect in
agent-written research, and this repository has already shipped three literature
ids quoted in briefs before the notes existed.

**Inner loop.** One hypothesis at a time:

1. Write `protocol.md`: what changes, what it predicts, why, and what result would
   falsify it. **Commit it before the run.** That commit is the temporal proof that
   the prediction came first, and `check` verifies it against the commit graph -
   editing the protocol after the results are in is refused, not silently allowed.
2. Run it through the engine.
3. Sanity-check the run before trusting it (converged, no NaN, baseline
   reproduces, the input is what you think it is).
4. Record the raw result in `results.jsonl` with its source, then write what it
   means in `analysis.md`. Label each outcome CONFIRMATORY (predicted by the
   protocol) or EXPLORATORY (noticed during the run).
5. A negative result is a result: record what it rules out.

**Outer loop.** Every few experiments, stop and synthesise: cluster the outcomes,
ask why the successes and failures happened, update `findings.md`, then choose a
direction in `state.json` - `deepen`, `broaden`, `pivot` or `conclude` - and say
why in `log.md`. Non-linearity is normal: return to the literature when results
surprise you, and pivot when the evidence kills the original question.

**Conclude.** Sufficient support for at least one hypothesis (or a coherent set of
negative results), key ablations done, and `findings.md` readable enough that a
human could write the abstract from it.

## Domain execution: the shipped library

The contract ships the domain knowledge this loop needs, vendored from Orchestra
Research's `AI-research-SKILLs` as one tezgah skill: `skills/ai-research/`. Read
its `index/<stage>.md` - `1-frame`, `2-data`, `3-train`, `4-measure`, `5-run`,
`6-write` - then the single entry the work needs, then that entry's
`references/`. Never read the tree.

Reach for it when the experiment needs ML machinery: training or fine-tuning,
serving or quantizing, a benchmark harness, model internals, retrieval or agent
pipelines, run tracking, or writing the result up. The index flags say which
bodies upstream generated from scraped docs (**generated**: thin, do not treat as
a workflow) or left naming a superseded API (**stale-api**).

The library is domain advice, never a substitute for this loop: its recipes do not
override the locked metric, the committed protocol, a claim's falsification
criterion, or the review below. Anything it recommends that touches a paid
account, a cluster or the user's data still needs the user's yes first.

## Ideation

When the hypotheses are weak or the run is stuck, generate instead of grinding.
Pick the move that matches the state you are in:

| State | Move |
|---|---|
| "I don't know what to look at" | hunt tensions: where do two results, papers or constraints contradict each other? |
| "I have an idea, is it good?" | apply the kill criteria below before spending a run on it |
| "the run is stuck" | name the hidden constraint and drop it (see below) |
| "the results are surprising" | re-derive the assumption they break, then go back to the literature |

- **Diverge first**: list candidate mechanisms and framings without judging them.
- **Expose a hidden constraint**: list the constraints of the current approach and
  classify them hard (physically necessary), soft (convention) or hidden (never
  stated). The most productive move in the library's whole ideation set is
  dropping a *hidden* one - "training needs labels", "inference is one pass",
  "the metric must be a scalar".
- **Force distance**: what would the neighbouring field call this problem, and
  what would it try first? Keep the mapping structural (mechanisms transfer), not
  verbal (labels transfer).
- **Bisociate**: combine two known things before inventing a third, then check
  that the combination predicts something testable.
- **Kill criteria**, applied before a run is spent: cannot be explained in two
  sentences; the problem is not the one being solved; it needs machinery the line
  does not have; no result would change anyone's mind; the answer would only
  confirm what is already known.
- **Converge**: keep what is testable with a clear prediction inside the budget,
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

**Score each dimension 1-5** and report the mean, with the anchors, so two
sessions' reviews are comparable rather than two private opinions:

| Score | Meaning |
|---|---|
| 5 | nothing material missing for this dimension |
| 4 | strong, one minor gap |
| 3 | adequate, with a gap a reviewer would raise |
| 2 | significant gap that undermines a claim |
| 1 | the dimension is not addressed at all |

Mean ≥4.5 with no dimension below 3 reads as accept; ≥3.8 as weak accept; ≥3.0 as
revise; below that, or any dimension at 1, as reject. The grade is the summary,
never the finding: a claim with a critical finding does not ship because the mean
is high, and a null result is not softened to improve the mean.

For every claim, the type decides what evidence it needs: a **causal** claim
("X causes Y") needs an isolating ablation, a **generalization** claim needs
heterogeneous conditions, an **improvement** claim needs a baseline from the same
harness, a **descriptive** claim needs representative sampling, and a **scoping**
claim needs declared bounds. A mismatch there is a finding even when the cited run
is real.

Severity: `critical` (the claim cannot stand as written), `major`, `minor`,
`suggestion`. Write each finding with the file it targets, the entity it targets
(`C03`, run id, node), the verbatim span, then what you observed, why it matters,
and what would fix it. Report the per-dimension score and the severity-ranked
findings; state plainly what the evidence does not show. Do not soften a null
result, and do not promote an exploratory finding to confirmatory after the fact.

## Figures and reports

`to_human/` is for the person paying for the research; it is a report, not a log
dump. One insight per section, the trajectory chart early (metric against run
number, baseline drawn as a horizontal line, jumps annotated with what changed),
and axes labelled with units. For a figure: a step axis is a line chart, N methods
across M benchmarks is a grouped bar, a matrix is a heatmap, and a pie chart is
almost never the answer. Export PDF for anything with numerical axes (vector, and
it survives a zoom), PNG only for a generated diagram; use a colourblind-safe
palette rather than the default cycle; and size for the venue's column width when
the figure is headed into a paper. The library's `index/6-write.md` entries carry
the full rules when a line reaches that stage.

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
nothing is copied verbatim. The scoring anchors, the finding record, the citation
workflow and the figure rules come from the same library, which now ships whole
under the `ai-research` skill.
