# E3 - detection with the candidate artifact

## What changes

One artifact, drafted in `experiments/E3-treatment-detection/artifact/`: the
candidate skill text plus the matrices its artifact list requires. It is the only
difference from E2.

## Method

Same three-rater, blind, same-feature protocol as E2, with two substitutions:
the rater reads the candidate artifact instead of
`skills/product-analysis/SKILL.md`, and it must fill the artifact's required
sections (capability matrix, field contract, flow/step contract, interactive
dependency graph, form-pattern gaps, capability-change proposals). Findings go to
`.tezgah/scratch/feature-coherence/E3-rater<N>.md`.

Scored the same way, against the same frozen corpus.

## Predicts

The union of three raters detects at least 9 of the 10 classes, each detected by
at least 2 of the 3 raters, and the unverifiable-claim count is not higher than
E2's.

## What would falsify it

A union of 7 or fewer classes, or a class detected by only one rater, or more
unverifiable claims than E2: the artifact does not close the gap. A per-rater
median at or below E2's union means the effect is a rater artefact, not the
artifact.

## Why

The claim under test is that a feature-level unit of analysis plus a named rule
set raises detection. The control is E2 on the same feature, the same tool
surface and the same rater count, which is the only way the difference is
attributable to the artifact.
