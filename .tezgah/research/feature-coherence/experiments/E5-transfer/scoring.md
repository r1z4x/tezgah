# E5 scoring rule (committed before any rater output is read)

Same rule as E2, applied to the second corpus. Both arms are scored on the same rows,
the same rules and the same environment.

## The denominator

The second corpus has 14 rows: **six defect classes** (C1 capability, C2 field
contract, C3 list convention, C8 smart defaults, C9 destructive confirmation, C10
capability-change slot) and four pass rows inside three classes (C1's A08, C4's A09,
C5's A07) plus one class with no instance on this feature (C6's A11). C7 (data-view
layout) has no row because both arms are code-scope on this repository - the app
needs a Docker build of a Rust and a Node image, and neither arm was allowed to start
it. The reported denominator is **6 defect classes**, and the pass rows are scored
separately as the control.

## Matching

A corpus row is **detected** when a rater's artifact states the same defect: same
layer pair (or same missing capability), same actor-visible effect, with a citation
that supports it.

| Situation | Counted as |
|---|---|
| rater finding matches a defect row | detection (that class) |
| rater states a defect with no citation, or one that does not show it | unverifiable claim |
| rater reports a defect on a pass row (A07, A08, A09, A11) | false positive |
| rater finding matches no row and survives re-checking against the repository | false positive, and the row is reported as a corpus gap |

Arm score: defect classes detected out of 6, per rater and as a union; plus the counts
of unverifiable claims and false positives. Pass rows are reported as
`recorded-agreement` when the rater names them and as false positives when it calls
them defects.

## What the scorer may not do

Edit the corpus, re-class a row after seeing a rater's output, or count a detection a
rater reached only because the corpus or a sibling arm was readable to it. A rater
that read a forbidden path is reported as contaminated and its arm re-run.

## What this arm can and cannot show

It can show whether the **shape** transfers: which classes a screen-level rubric
reaches and which it misses on a second stack, and whether the treatment arm writes
capability-change proposals where the baseline does not. It cannot show the runtime
half (no layout row, no exercised flow), so a difference between the arms that would
depend on running the app is out of reach here and is reported as such.
