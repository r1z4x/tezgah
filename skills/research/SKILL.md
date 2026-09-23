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
| `state.json` | the question, phase, direction, the locked evaluation (`metric`, `baseline`, `locked_at`, optional `environment`, and the optional two-gate pair `capability_tolerance` + `counter_metric`) and the hypothesis list |
| `log.md` | the decision timeline: one line per decision, experiment, dead end or pivot, with the evidence that drove it |
| `findings.md` | `## What we know`, `## Patterns`, `## Lessons`, `## Open questions` |
| `claims.jsonl` | one claim per line: `statement`, `status`, `provenance`, `kind`, `falsification`, `proof`, `dependencies`, `scope` (what the claim's numbers were measured on, and it may not be wider than the rows it rests on), and `supersedes` when the claim replaces an earlier one - recorded with `tezgah-research claim <slug>`, never by editing the file |
| `experiments/<hypothesis>/` | `protocol.md`, `results.jsonl` (one JSON object per row, each carrying its `source`, its `scope` - what the numbers were measured on - and, when that scope is `fixture`, the `fixture` description of the input that was generated), `analysis.md`, and `raw/<runId>.log` for a run read back from the engine |
| `literature/` | one note per source, saved when you read it, not later, and each named by its row in `literature/INDEX.jsonl` |
| `to_human/` | reports for the person paying for the research - `report.md`, whose findings state what the evidence does not show - plus `review.json`, the six-dimension review a concluded line reports |

The tree is worth only what git can see of it. A line whose path is gitignored -
`.gitignore` holds `/.tezgah/`, so this is the default unless the negation is
added - can never show that its protocol predates its results, because the commit
the order rule compares against will never exist, and no later session can read it
at all. `init` prints a TRACKING block naming the pattern that ignores the path
(and the negation lines that undo it); `init --tracked` appends them.

`check` asks the question the order rule means - can the two files it compares be
committed? - by probing each experiment's `protocol.md` and `results.jsonl`
rather than the line's directory, so a line whose ignore rules cover the
directory while the pair is tracked is not reported. For the pair it does report
it prints the command that fixes it, `git add -f <results.jsonl>`, because the
loop that keeps the order decidable is exact: **commit the protocol normally**
(that commit is the prediction), **then add the results by explicit path** - a
plain `git add <results.jsonl>` stages nothing while the path is ignored, and
that silent no-op looks exactly like a commit - and the order is verifiable from
then on. `check --strict` refuses a pair that is still ignored.

Scaffold and check it with the CLI (`~/.config/tezgah/bin/tezgah-research`, or
`bin/tezgah-research` in the checkout):

```sh
~/.config/tezgah/bin/tezgah-research init my-line --question "does X hold under Y?"
~/.config/tezgah/bin/tezgah-research init my-line --tracked   # re-include an ignored path
~/.config/tezgah/bin/tezgah-research check    # 0 clean, 1 broken rule, 2 misuse
~/.config/tezgah/bin/tezgah-research check --strict   # the unprovable becomes a refusal
~/.config/tezgah/bin/tezgah-research check --orx      # the run command registered here
~/.config/tezgah/bin/tezgah-research status
~/.config/tezgah/bin/tezgah-research claim my-line   # one JSON object on stdin
~/.config/tezgah/bin/tezgah-research migrate my-line [--dry-run]
~/.config/tezgah/bin/tezgah-research source my-line <hypothesis> --run <orxRunId> [--command "<cmd>"]
```

`claim` reads that object from stdin and appends it as one line: exit 0,
`claim <id> recorded` (just `claim recorded` when the object carries no `id`);
exit 1 with one `FAIL <slug>: <problem>` line per problem
and nothing written - including when `claims.jsonl` cannot be locked within a
second; exit 2 when the slug is missing or unknown, or stdin is not one JSON
object. It refuses a claim with no `kind`, a proof that names no artifact, and an
`orx:<runId>` with no `raw/<runId>.log` under the line or the repository: those
are the three a reader cannot repair later. It refuses a `supersedes` id no claim
in the line carries too - a relation to nothing is no relation - and it does not
require the field: a claim that corrects nothing simply leaves it out. Record a
claim with the command,
never by editing the file: a hand edit is an unlocked read-modify-write of the
file every claim of the line lives in, while the command appends under an
exclusive lock on that file and refuses rather than writing unlocked.

`migrate` derives what the artifacts already hold, for a line written before a
rule existed: each claim's `kind` from the files its proof names, each results
row's `source` from the fields the row already carries (`log` or `raw` is the
receipt itself, `run` or `id` is the run the row came out of), and the
`literature/INDEX.jsonl` rows from the notes. It rewrites both JSONL files under
the same lock `claim` uses, is idempotent, and prints every field it could not
derive - the row that carries none of the four fields, the id no note carries,
the verification nobody recorded, the inclusion decision only a reader can make -
rather than inventing one. `--dry-run` prints the same report and writes nothing.

`source` files one run as the experiment's receipt: it runs `orx logs <runId>`,
writes the log to `experiments/<hypothesis>/raw/<runId>.log`, and appends the row
`{"source": "orx:<runId>", "log": "raw/<runId>.log"}`. The experiment must already
have its `protocol.md`, so a receipt cannot be filed against a plan that was
never committed. Without orx it exits 2 and says so, and it writes nothing at all
when the run cannot be read.

`check` enforces the rules a session tends to skip: `protocol.md` committed
before `results.jsonl` - decided on the commit graph, so two commits inside the
same second or a rebase do not trip it, while a protocol *edited* after the
results is refused - a protocol that answers both questions it owes, **what it
predicts and what would falsify it** (a prediction word and a falsifier word
anywhere in the file, read as prose and not by shape; a sentence that *disclaims*
one - "this file is the brief, not a prediction", "no prediction is claimed for
it" - does not answer it), a falsification criterion and evidence on every claim,
a provenance tag on every claim, a `kind` on every claim with that kind's proof
rules behind it (`evidence` bound to a run with rows, `literature` to a note under
`literature/`, `code` to an artifact of the repository, `derivation` to something
the line itself holds, and every kind refused a proof that names no artifact at
all), a `supersedes` that names a claim the line does not hold, a results row that
parses and says where it came from, a literature note the index names and an index
row that names a note, the locked evaluation that a phase past `bootstrap`
requires, a session event tagged with where it came from, the `review.json` a
concluded line reports whose findings quote their target verbatim, an analysis for
every experiment, a findings file that answers all four questions, and a
`Patterns` bullet that names the claim, note or run it generalises from. It warns
rather than fails while the results are still uncommitted, because there is no
order to check yet.

Two classes of finding, and `--strict` decides between them. What the checker can
decide is an error and `check` exits 1. What it cannot decide is a warning: an
experiment path that is ignored, so the order rule has nothing to order; a
protocol that is a brief rather than a prediction, or that names no falsifier; a
grey source with no quality note; an evidence claim whose run recorded no row; a
claim written before `kind` existed, a results row written before `source` did, or
one written before `scope` did (what its numbers were measured on, reported once
per file with the count), or a `fixture` row that stops at the class and does not
name what was generated; a claim resting on a fixture row that declares no scope,
one over mixed rows that declares `real`, or one asserting a number its cited
artifacts do not contain; a claim that supersedes another (the relation is
reported, naming both ids, so the older claim is never read as current); an
unsourced `Patterns` bullet; a concluded line with no review,
or whose `report.md` names no limit, or carries a fixture-scoped claim and never
says so, or is not written yet.
Those are the honest state of a line mid-flight, and a session that wants a line
it can defend in a week runs `check --strict`, which refuses every one of them.
`check --orx` adds one more: the run command the orx project registered against
this repository holds, checked against the tree - a command naming a path that is
gone means the project's numbers have no reachable recipe.

Run it before reporting a result, and fix what it names.

### Evidence fidelity

A number that travelled through three summaries is no longer evidence. The same
rules the domain library enforces on a compiled artifact apply here:

- **Exact numbers, never rounded.** `0.8471` is a result; "about 85%" is a memory
  of one. Round only in the sentence aimed at a human, and say what the raw value
  was.
- **A derived view is not the source.** A filtered or merged table is a new file
  named as derived, never presented as the run's own output.
- **Every result row carries its source** in `results.jsonl` - the run id, the
  command or the node - and every recorded fact in `analysis.md` points at the row
  it came from. One row is one JSON object on its own line; a file whose line three
  is prose loads in nothing. When the source is a run the engine owns, file the log
  with `tezgah-research source`, so the row and the receipt are written together
  and the claim's `orx:<runId>` token resolves to something a reader can open.
- **An input is part of the evidence: every row declares its `scope`.** `real` (the
  running system and its corpus), `fixture` (a temp HOME, a generated repository, a
  hand-written sample) or `derived` (a table computed from other rows). `source`
  says where a row came from; `scope` says what its numbers are *about*, and it
  cannot be recovered afterwards - a probe run against a generated repository and a
  measurement of the running system read identically once the run is over, which is
  why the producer declares it and the checker refuses to guess. A fixture row also
  names what was generated in `fixture` - `a temp HOME and a generated repository of
  40 files` - because a class a reader cannot size is not an input they can weigh
  (a row that stops at the class is a warning, and `--strict` refuses it). A claim
  may not declare a wider scope than the rows it rests on (that is an error), a
  claim resting on a fixture row must say `fixture` (that is a warning, and
  `--strict` refuses it), and a claim over rows that mix says `fixture` too, since a
  declaration is a warning to the reader and under-declaring is the safe direction.
  `status` prints the fixture-scoped claims of every line, and the report of a
  concluded line has to name them.
- **A number in a claim is in the artifact it cites.** The claim is the sentence a
  reader keeps; a number in neither the claim's proof nor the claim is the one
  thing a reader cannot check. `check` reports the numbers it cannot find, by count
  (this is a warning, not a refusal: a proportion computed in the sentence is not a
  fabrication, and 80 of this repository's own 82 numeric claims are contained under
  the reading below). What it compares is a measurement: a date is read off the
  statement first, a thousands separator is a rendering, so `20480` and an artifact
  holding `20,480` agree, a comma is never part of a number - `4,2,2,1,1,2` is six
  figures and not three decimals - and a number past the per-file reading window is
  streamed for rather than called missing.
- **Wording cannot outrun the evidence type.** Validation metrics do not support
  a claim about training dynamics; a correlation does not support a causal verb;
  one seed does not support "always".

## The loop

**Bootstrap.** Search the literature with more than one source, save every source
to `literature/` as you go, identify the gap, form testable hypotheses (see
Ideation below), and lock the evaluation before running anything: the metric, the
baseline, the threshold. Write it into `state.json` - a criterion chosen after
seeing results is not a criterion. `check` reads all three: past `bootstrap` a
line with an empty `metric`, `baseline` or `locked_at` is refused, and at
`bootstrap` it is warned about, which is the prompt to lock it rather than a
verdict. Add `environment` beside them when the numbers depend on one - the model,
the prompt, the harness - as an object, because a string records none of them.

**A second gate is available, and it is the one a harness change needs.** Beside
`metric`, `baseline` and `locked_at` you may write `capability_tolerance` - the
band the capability metric has to stay inside before a result counts, as the
sentence you will check it against, "capability metric within 0.02 of the
baseline" - and `counter_metric`, the name of the metric the change is supposed
to move. A candidate then has to pass **both** gates: inside the tolerance *and*
an improvement on the counter-metric, and survivors are compared against each
other on the Pareto frontier instead of by one number's sign. The pair is
optional: a line that locks one metric and no capability band omits both, and
that is what every line in this repository does; `check` refuses a field only
when it is written and names nothing (an empty string, a blank one, or a value of
the wrong type). Lock them at bootstrap with the rest of the criterion, because a
tolerance chosen after seeing the candidates is the same after-the-fact criterion
the missing-metric rule refuses - and state it as a number, not as "no worse",
since a band its own author set wide enough passes everything and the gate stops
being one.

Two things the two-gate form buys, both of them failures this layer has already
paid for. A candidate cannot buy its gain by moving the metric: the capability
tolerance is what stops an "improvement" that raised p95 or dropped accuracy, the
shape a single locked number cannot see. And it keeps the rule itself out of the
reach of the loop it judges: the two fields are read by `check`, which lives in
`hooks/tezgah_research.py`, a module the frozen set forbids a prediction's commit
to touch (`FROZEN_PATHS`) - so the gate a candidate survives is not machinery the
candidate can rewrite. What the fields cannot say is how wide the band may be:
the tolerance is the author's own sentence, and one set wide enough passes every
candidate, so write it as the number you would defend in the review.

Never write a citation from memory. Verify each one against two of Semantic
Scholar, CrossRef (DOI content negotiation), arXiv or OpenAlex, and put
`[CITATION NEEDED]` in the text rather than a plausible-looking reference that
does not exist - hallucinated references are the single most common defect in
agent-written research, and this repository has already shipped three literature
ids quoted in briefs before the notes existed. Then index the note: one
`literature/INDEX.jsonl` row per note and one note per row, with `note`, `id`,
`class`, `source`, `inclusion` and `verified` (the two records you checked it
against), plus `quality` for anything that is not a paper. A source is `formal`
when it is a paper record - a DOI, an arXiv id, a venue's own page - and `grey`
otherwise: a vendor page, a product report, a tool's documentation. The grey
channel is allowed and often the only evidence a practice question has, so it is
labelled and judged (`quality`) rather than skipped, and a row that records it as
verified by fewer than two sources is reported: an unlabelled grey source is how a
marketing claim enters a findings file as a fact. `tezgah-research migrate` writes
the rows it can derive from the notes already saved and tells you which fields
they do not carry.

**Inner loop.** One hypothesis at a time:

1. Write `protocol.md`: what changes, what it predicts, why, and what result would
   falsify it. **Commit it before the run.** That commit is the temporal proof that
   the prediction came first, and `check` verifies it against the commit graph -
   editing the protocol after the results are in is refused, not silently allowed.
   It also reads the file: a protocol that answers neither what it predicts nor
   what would falsify it is reported, and `--strict` refuses it. That is the gap
   the layer's own audit measured (P2: a protocol whose whole body was "run it"
   passed every check), and a work order handed to a read-only agent is the honest
   shape it costs - record what the brief was, and expect the warning.
2. Run it through the engine.
3. Sanity-check the run before trusting it (converged, no NaN, baseline
   reproduces, the input is what you think it is).
4. Record the raw result in `results.jsonl` with its `source`, then write what it
   means in `analysis.md`. Label each outcome CONFIRMATORY (predicted by the
   protocol) or EXPLORATORY (noticed during the run). A run the engine owns is
   recorded with `tezgah-research source <slug> <hypothesis> --run <orxRunId>`,
   which files the log under `raw/` and appends the row that names it.
5. A negative result is a result: record what it rules out. When the line locked
   the two-gate pair (Bootstrap above), a run is a survivor only when it is inside
   the `capability_tolerance` **and** moves the `counter_metric`, and survivors are
   compared against each other on the Pareto frontier rather than by one number's
   sign - a candidate that bought its gain by moving the capability metric has not
   passed, whatever its headline number did.

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
| Scope calibration | does the claim assert exactly what the evidence covers, no more, no less? Nothing answers this better than the rows' own `scope` field, which is why it is a field and not a reading: a claim reading the same rows as the running system when they say `fixture` is the failure this dimension names. |
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
findings; state plainly what the evidence does not show - in `to_human/report.md`,
because that is the file `check` reads once the phase is `concluded`: a report
that names no limit anywhere warns, one that was never written warns with that
reason, and `--strict` refuses both. Do not soften a null
result, and do not promote an exploratory finding to confirmatory after the fact.

The review is an artifact, not a paragraph in the session that wrote it: a
concluded line writes `to_human/review.json` with `dimensions` (the six keys
above, each an integer 1-5) and `findings[]` (each with `severity`, `target` and a
`quote` that occurs **verbatim** in the file it targets). `check` refuses a review
missing a dimension or scoring outside 1-5, because two reviews only compare if
they answer the same six questions on the same scale, and it refuses a finding
whose quote is not in its target - a finding that cannot quote its evidence is not
a finding. It reports a concluded line with no review at all, and `--strict`
refuses it: a review is a judgement, so nothing can migrate one into existence.

Finally, a `## Patterns` bullet names what it generalises from - a claim id, a
`literature/` note or a run - because a pattern is the one finding a reader carries
into other work, and one that names nothing is a guess wearing a finding's
clothes. `check` reports the unsourced bullets of a line by count; `--strict`
refuses them.

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
formatting and installs. Each entry is an object carrying the `date` and the `tag`
beside what happened - `{"date": "2026-09-20", "tag": "ai-executed", "what":
"..."}` - and `check` refuses an entry that is not an object, carries a tag
outside the four above, or records nothing that happened; the older shape that
keeps the entries of one date in an `events` list is read too, and its events must
each carry a tag the same way. A session that ends without this leaves the next
one guessing, which is the failure this whole workspace exists to prevent.

## Where this comes from

The two-loop rhythm, the workspace layout and the six review dimensions adapt the
orchestration layer of Orchestra Research's MIT-licensed `AI-research-SKILLs`
library (its `autoresearch`, `ara-rigor-reviewer` and `ara-research-manager`
skills) to tezgah's contract: the execution engine here is OpenResearch, the
reporting language is the contract's, the checks are `tezgah-research`'s own, and
nothing is copied verbatim. The scoring anchors, the finding record, the citation
workflow and the figure rules come from the same library, which now ships whole
under the `ai-research` skill.
