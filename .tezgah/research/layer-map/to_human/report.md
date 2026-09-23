# layer-map — the layer the word `harness` names, and where this line stopped

Line: `.tezgah/research/layer-map/`. Question: *which layer does tezgah sit in, and how is that
boundary drawn against a host, a framework, an SDK, an IDE plugin, an eval harness, an
orchestrator and MCP?*

This is a **literature line**: no experiment ran, no model call was made, and every claim below
cites a note under `literature/` rather than a row this session produced. It is the source-base
half of plan 005, and what plan 005 asked of it - one note and one index row per source, at a
clean `check` - is what it delivered.

## The boundary question, and where its answer lives

The line was opened to settle a collision, not to write the page. Two sources of the same kind
assign the word to opposite layers: UHP defines a *harness* as "a complete agent runtime" and
names Codex, Claude Code and Hermes, which is what this repository's glossary calls the **host**,
while this repository's `harness` is the wrapper tezgah puts *around* a host (C01). The
literature's ruler for that boundary is the definition paper's constitutive definition plus its
inclusion/exclusion test against agent framework, agent SDK, IDE plugin, eval harness and
orchestrator, which the page borrows (C02).

So the question is **answered, and the answer lives on the page**: `docs/layers.md` (165 lines,
35 citations, landed with plan 005) names the four layers - model and MCP transport, agent
framework, agent host runtime, tezgah's policy and evidence layer - and draws each border. This
line's contribution to that answer is the vocabulary and the ruler: the collision stated above
(C01), the contrast list it has to be answered against (C02), the finding that the load-bearing
half of a harness is structural rather than prose (C03), and the two contrast poles - a layer
that wraps the *environment* and leaves its verifier alone (C04), and harness-level repair as
against model-specific accommodation (C05).

Two parts of the question are **explicitly unanswered by this line's sources**:

- **Where MCP falls.** None of the six sources decides it. The page answers it from a different
  argument (the gate sees an MCP call and not its contents), and that argument is not this
  line's; the literature here bounds a harness against a framework and an orchestrator and is
  silent on a tool-transport protocol.
- **Whether any source assigns `harness` to a wrapper around a host**, which is this
  repository's own sense. The five searched papers are all the other direction, so that sense
  stays local to the glossary rather than citable from the literature.

## What was established

- **The word is assigned to opposite layers by two sources of the same kind** (C01): UHP's
  harness is this repository's host, and this repository's harness is the wrapper around it. Both
  statements are about the same two layers with the names swapped.
- **The definition paper supplies the inclusion/exclusion list the page has to answer to** (C02)
  - agent framework, agent SDK, IDE plugin, eval harness, orchestrator - decided by a
  constitutive definition and applied to six real harnesses plus deliberate edge cases. It is a
  conceptual instrument, not a measurement.
- **A harness gain is structural, not prose** (C03): the agentic-harness-engineering ablation
  localizes its improvement to tools, middleware and long-term memory rather than the system
  prompt, so the mechanical half of the layer is what transfers between models.
- **Two of the six sources are environment-side or model-side, and they say so** (C04, C05):
  EnvHarness is a plug-in layer around a static environment that keeps the benchmark's verifier
  untouched; Ecdysis's object is a runtime harness trained against failures, whose premise is
  that one failure cannot say whether model or harness is at fault, so only recurrence across
  instances is evidence for harness-level repair.
- **One source is a vendor's own document and carries its own commercial claim** (C06): UHP is
  Apache-2.0, versioned and readable at first hand, but its cost and latency figures are the
  vendor benchmarking its own product on one task across eight harness and model configurations,
  with its own README noting the winner varies by task.
- **The artifacts**: six notes under `literature/` with one `literature/INDEX.jsonl` row each
  (five `formal`, the UHP row `grey` with its quality judgement), six claims C01-C06, and
  `findings.md` answering all four sections. `experiments/` is empty on purpose: a screening is
  not a run, so no protocol was written and no prediction row exists - inventing one would
  fabricate a prediction nothing tested.

## What the evidence does not show

- **Most of the sources were read at abstract depth.** Four of the six index rows record
  "abstract read in full", one (Ecdysis) an abstract plus the paper's first pages, and only UHP
  was read at first hand from the vendor's repository. A claim about a paper's method or a
  figure beyond its abstract is therefore not supported by this line, and the notes say which
  depth each was read at rather than implying a full read.
- **Nothing here is a measurement.** Every number in a note is the cited source's, quoted with
  the source beside it; no model call, no run and no paid round happened in this line, and the
  definition paper's classification of six harnesses was not re-applied.
- **The screening is one reader, one pass.** Two discovery routes were used (arXiv API, OpenAlex
  by DOI) and no venue was searched systematically, so a source that uses the term differently
  and did not surface is not excluded by anything here.
- **One screened source carries no claim.** `literature/2608.02276-harness-r1-editing-runtime-harnesses.md`
  has a note and an index row, but no claim cites it; its content - harness editing as a learned
  policy judged by the target's task success - does not enter `findings.md` or any claim.
- **One record is verified against a mirror rather than an index.** Ecdysis's OpenAlex lookup
  answered HTTP 404 (the paper is newer than the index) and the second record is the alphaXiv
  mirror; the index row and the note both say so rather than padding the verification.
- **The vendor's benchmark survives nothing here.** UHP's 99.8%-lower-cost and 3.2x-faster
  figures are recorded as the vendor's claim about its own product (C06); they were not
  reproduced and cannot be from this repository.
- **The line did not decide the page's questions.** The MCP boundary and the question of whether
  a wrapper around a host is a harness under the definition paper's test were handed to the page,
  which answers from arguments this line did not assemble.
- **No experiment, no protocol, no prediction.** There is no result to re-run or falsify here:
  the whole line is a rendering of what six sources say, and its falsification criteria name the
  evidence that would overturn each reading rather than a run this line could perform.

## How this line was closed

The evaluation locked for a literature line is the screening discipline the other literature
lines use - one note per source with one index row each (6 notes, 6 rows), at zero refusals from
`bin/tezgah-research check layer-map --strict` - and not a behavioural metric: the line has no
model, no run and no node. It is a deliverable count, recorded as such in `state.json`, so a
reader comparing it with a measured line's evaluation does not read it as a measurement of this
layer. `phase: concluded` / `direction: conclude` records that the source base plan 005 asked
for is delivered and the boundary question is answered on the page, with the two unanswered
parts above named as limits rather than left silent.
