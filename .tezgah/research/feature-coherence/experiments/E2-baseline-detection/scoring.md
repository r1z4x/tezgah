# E2/E3 scoring rule (frozen before any rater output is read)

Scoring happens after all raters of an arm have yielded. The scorer is the
session that built the corpus; every rater is blind to the corpus and to the
class list.

## Matching

A corpus row `D` is **detected** by a rater when the rater's artifact states the
same defect: same layer pair (or same missing capability), same actor-visible
effect. Wording is not evidence - the row's defect must be identifiable from the
rater's own citation, and a rater finding whose citation does not support the
statement is not a match.

| Situation | Counted as |
|---|---|
| rater finding matches a corpus defect row | detected (that row, that class) |
| rater states the defect with no citation, or a citation that does not show it | unverifiable claim (not a detection) |
| rater reports a defect on a pass row (D09, D15) | false positive |
| rater finding matches no corpus row and survives re-checking against the repo | false positive (the corpus is not exhaustive; it is still counted, and the row is reported) |

A **class** counts as detected when at least one of its rows is detected. The arm
score is the number of detected classes out of 10, the per-rater median, and the
counts of unverifiable claims and false positives.

## Why these three numbers

- **Detected classes** is the claim's metric: the artifact exists to raise the
  number of defect classes an analysis reaches.
- **Per-rater median** separates a real effect from one lucky rater, which the
  union alone would hide.
- **Unverifiable claims and false positives** are the cost side. A rubric that
  raises detection by also raising noise has not improved; both arms are scored
  on both numbers and the comparison is reported as a pair, never as detection
  alone.

## What the scorer may not do

Edit the corpus, re-class a row after seeing a rater's output, or count a
detection that the rater reached only because this file or a sibling arm's output
was readable to it. Any rater that read a forbidden path is reported as
contaminated and its arm re-run.
