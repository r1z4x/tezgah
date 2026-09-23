# E2 - baseline detection with the shipped rubric

## What changes

Nothing. Three independent rater contexts run the analysis that ships today:
`skills/product-analysis/SKILL.md`, `skills/analyze-app/SKILL.md` and the
`research` skill, applied to the Ustam admin users feature.

## Method

Each rater is a separate context with no knowledge of the corpus, of this
research line, or of the ten classes. It is given: the repository path, the route
in scope, the three skill files, the tool surface (`browser_*`), and one
instruction - produce the analysis the skill demands, at the depth it demands.
Each rater writes its findings to
`.tezgah/scratch/feature-coherence/E2-rater<N>.md` and does not read
`.tezgah/scratch/feature-coherence/E1-corpus.jsonl` or any sibling rater's file.

Scoring, done after all three have yielded: a class counts as detected when at
least one rater reports a finding that matches a corpus instance of that class.
A finding that names no corpus instance and cannot be re-verified is counted
separately as an unverifiable claim.

## Predicts

The union of the three raters detects at most 4 of the 10 classes, and the median
rater detects at most 3. The classes predicted to be missed in every arm are C1,
C2, C5, C6 and C10: each needs either a cross-layer comparison or an action
actually exercised.

## What would falsify it

A union of 7 or more classes detected: the shipped rubric already covers this
class of defect on this feature, and H1/H2/H4's premise is refuted - the fix then
belongs to the output slot (H3) alone, and this line reports that instead of a
new artifact.

## Why

An improvement claim needs a baseline from the same harness. The rater count is
three because a single rater is not a measurement of a method; the count is
reported in the artifact, and the fact that all three share one model is a limit
recorded in `analysis.md`.
