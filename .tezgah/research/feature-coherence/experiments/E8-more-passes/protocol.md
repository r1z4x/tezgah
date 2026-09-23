# E8 - more passes per arm, so a class count is a distribution

## What changes
Nothing. E3 (5 raters, artifact) and E6 (2 raters, pre-wiring rubric) produced
class counts whose spread the line has been reporting as rater variance. This
experiment adds three raters per arm on the **first** feature, so both arms have a
distribution rather than a pair.

## Method
- Arm A: three more contexts apply `skills/feature-audit/SKILL.md` to the Ustam admin
  users area; same blindness rules as E3 (no corpus, no sibling artifact).
- Arm B: three contexts apply the pre-wiring rubric
  (`E6-pre-wiring-control/product-analysis-pre-wiring.md`) to the same feature, same
  rules. This is the half E6 ran on the second stack only.
Scored against the first corpus (15 rows) with the E2 rule.

## Predicts
Arm A's median classes across eight passes sits at or above the E3 median of five,
and its union stays at seven; arm B's union lands **below** arm A's, because the
pre-wiring text does not carry the matrices or the proposal slot.

## Falsification criterion
An arm B union at or above arm A's union would falsify the artifact's contribution on
the first feature, as it already did on the second. An arm A median below five would
put E3's 7-of-9 result at the high end of its own distribution and the line would say
so.
