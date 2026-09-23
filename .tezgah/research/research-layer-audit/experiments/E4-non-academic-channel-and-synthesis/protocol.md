# E4 protocol — the non-academic channel and cross-source synthesis

Written 2026-09-20 before the run. Predictions from reading
`skills/research/SKILL.md`, the RESEARCH paragraph in `hooks/tezgah_policy.py`,
and the five existing lines under `.tezgah/research/`.

## Question

Two halves of the bootstrap step, measured as they exist:

1. **The non-academic channel.** A practical or engineering question ("should
   this rule exist", "which harness shape wins") is answered by blogs, vendor
   docs, release notes, issue threads and practitioner reports as much as by
   papers. Does the layer name a channel for those, and do the lines hold any?
2. **Synthesis across sources.** The skill demands "more than one source" and an
   outer loop that "clusters the outcomes". Is there an artifact where two or
   more sources are compared against each other, or is every note a per-source
   summary?

## Locked evaluation

- **C1 channel named**: occurrences of a non-academic retrieval instruction in
  `skills/research/SKILL.md` and in the RESEARCH paragraph (`hooks/tezgah_policy.py:379-423`).
  Baseline `> 0`; predicted `0`.
- **C2 channel used**: literature notes in the five existing lines whose source
  is not a paper record - classified by the note's `url`/`id` host
  (`arxiv.org`, `alphaxiv.org`, `doi.org`, a publisher domain = formal; anything
  else, including a bare repository or a blog = grey). Baseline `> 0`; predicted
  `0`.
- **C3 synthesis artifact**: a file that compares two or more sources in one
  place (`literature/INDEX.md`, `synthesis.md`, `comparison*.md`, or a row
  naming two source ids). Baseline `> 0`; predicted `0`.
- **C4 synthesis inside findings**: `## Patterns` bullets in the five
  `findings.md` that name two or more distinct sources. Baseline `> 0`;
  predicted `> 0` for `infra-candidates` (its Patterns section cites ActPlane,
  FAVA, a measurement) and `0` for the other four.

## Threshold

The finding is the measured count, not a bit. A zero on C2 or C3 is a gap in the
layer's capability, not a criticism of any one line: nothing in the workspace
schema or `check` asks for either.

## What would falsify

- C1 `> 0`: the channel exists in the text and the gap is only in the lines.
- C2 `> 0` with a formal-looking host: my classifier is wrong; the raw host list
  is in the results and is the evidence either way.
- C3 `> 0`: a comparison artifact exists and the synthesis gap closes; the file
  is named in `results.jsonl`.
- C4 `0` for `infra-candidates`: the line that has the most literature does not
  compare it either, and the predicted/produced split disappears.

## Out of scope

Whether the layer *should* prefer grey sources is a standards question -
`literature/1707.02553-garousi-mlr-guidelines.md` carries the MLR guidance for
that, and `literature/2609.05505-scolitbench-design-principles.md` the screening
evidence.
