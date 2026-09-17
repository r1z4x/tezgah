---
name: ai-research
description: >
  The vendored AI-research-SKILLs library - 98 upstream skills in 23 categories,
  MIT - that now ships with tezgah. Use when a research line needs AI or ML
  machinery: training or fine-tuning a model, serving or quantizing one,
  evaluating a benchmark, reading model internals, building a retrieval or agent
  pipeline, tracking runs, or writing the result up. Read the one entry the work
  needs, never the tree. Do NOT use for code discovery ("where is X", "who calls
  Y") - that is the code graph.
---

# ai-research

Ninety-eight skills from Orchestra Research's `AI-research-SKILLs`, vendored into
this repository at revision `773a529` (2026-06-15, MIT) and kept in the upstream
layout, so a path here is the path there. Re-vendor, or verify the tree, with
`bin/tezgah-import-ai-research`; what was left out and why is in `SOURCE`.

Tezgah owns the research loop - the two-loop rhythm, the workspace under
`.tezgah/research/<slug>/`, the protocol committed before the run, the six
dimension review (`skills/research`). This library owns the machinery the
experiment runs on. Reach for it after the question and the metric are locked, not
before.

## Read path - three steps, and only the last one costs anything

1. **`index/<stage>.md`** - six files, one per stage of a research line. Read the
   one that matches the work in hand; it lists every entry with its purpose.
2. **the entry's `SKILL.md`** - the file the index line names, e.g.
   `11-evaluation/lm-evaluation-harness/SKILL.md`. That is the upstream body.
3. **its `references/`** - the detail the body points at, when the body is not
   enough.

| index file | stage |
|---|---|
| `index/1-frame.md` | framing the question, ideation, the research artifact |
| `index/2-data.md` | data, retrieval, tokenization |
| `index/3-train.md` | model, training, post-training, compression |
| `index/4-measure.md` | evaluation, safety, interpretability, observability |
| `index/5-run.md` | compute, serving, run tracking |
| `index/6-write.md` | agents, structured output, media, paper writing |

## Read the flags before you trust a body

Each index line can carry a flag, and they are not decoration:

- **generated** - upstream built this body from scraped documentation. It is thin,
  sometimes mangled, and one of them still carries the placeholder *"Quick
  reference patterns will be added as you use the skill."* Read the entry for its
  coverage and its reference files, not for a workflow.
- **stale-api** - the body names an API its library has since moved
  (`langchain` chains, pre-2.5 `dspy`, `outlines.models.*`, AutoAWQ). The
  concepts survive; the call signatures may not. Check the current docs before
  running a snippet.
- **dead-links: N** - the body links N reference files upstream does not ship. The
  live links in the same entry still work.

An entry with no body vendored would be a line without a file - there is none:
every one of the 98 ships its `SKILL.md`.

## Where tezgah's own rules still win

The library knows ML. It does not know this contract. A recipe inside it never
overrides: the locked metric and baseline in `state.json`; `protocol.md` committed
before the run; a claim's falsification criterion; the review a claim passes
before it is reported. Vendored advice that starts with "just run ..." on a
cluster is advisory, not a plan, and anything it recommends that touches a live
account, a paid service or the user's data still needs the user's yes first.

## Entries worth knowing about before you need them

- `10-optimization/ml-training-recipes/references/experiment-loop.md` - a
  fixed-time-budget keep/discard loop, which is the closest external analogue of
  this contract's protocol-before-run rule.
- `20-ml-paper-writing/ml-paper-writing/references/citation-workflow.md` - how to
  verify a reference instead of writing one from memory.
- `20-ml-paper-writing/academic-plotting/SKILL.md` - chart-type rules, a
  colourblind-safe palette and venue column widths; every line ends in a figure.
- `22-agent-native-research-artifact/rigor-reviewer/SKILL.md` - the 1-5 scoring
  anchors and severity inventory behind this contract's six-dimension review.
- `22-agent-native-research-artifact/compiler/SKILL.md` - evidence fidelity: exact
  numbers, a derived subset never named `Table N`, every evidence file carrying
  its source.
- `11-evaluation/lm-evaluation-harness/SKILL.md` - the runnable benchmark recipe a
  research line usually quotes.

## Provenance

Vendored, not adapted: the bodies are byte-for-byte upstream, frontmatter
included - the author line is upstream's, and two entries carry a contributing
author's name rather than Orchestra Research's
(`10-optimization/ml-training-recipes`, `14-agents/a-evolve`); a markdown file
with no frontmatter carries one attribution comment.
`SOURCE` records the revision and the exact drop list, `library.json` is the
manifest (`bin/tezgah-import-ai-research --check` verifies every digest), and
`NOTICE` records the licence. Neither the library nor any entry in it is a
tezgah file: file an upstream bug upstream.

Kill switch: `research-off` disables the routing that reaches this library, the
same switch that turns off the research rule; the files stay on disk.
