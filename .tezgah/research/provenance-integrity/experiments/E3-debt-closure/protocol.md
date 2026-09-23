# E3 - the gap closure, measured

## The change under measurement
None, in the research sense: this is a census of the layer's own artifacts after a
third pass over them, made by six parallel sessions. What it measures is whether
the two things E1 and E2 opened are actually closed - the undeclared scope of a
result row, and the claims whose numbers their cited artifacts do not contain - or
only reported as closed.

## Method
Read every `.tezgah/research/*/experiments/*/results.jsonl` of this repository and
count, per line: rows, rows with no `scope`, and rows whose `scope` is `fixture`
with no `fixture` description. Then run the containment rule as it finally ships
(the checker's own `NUMBER`, `THOUSANDS`, `ISO_DATE`, `_artifact_text` and
`_beyond_window`) over every claim of every line, and report the shares. Nothing is
inferred: a field is read as it is written, and the numbers come from the files.

## Predictions, stated before the run
1. 0 of 813 rows declare no scope, and 0 fixture rows lack a description. The
   pre-pass census counted 510 unscoped of 813.
2. The final containment reading leaves 80 of 82 numeric claims contained, and the
   two it warns about are `harness-hardening` C17 and `typesafe-cost` C5 - both
   superseded rows whose warning the line keeps on purpose.
3. The warnings that remain across the lines are only the by-design classes: a
   protocol that predates the rule, a supersede relation, a superseded row's
   containment warning, a single-index source, and the git-tracking warns that the
   commit that follows this run clears.

## Falsifier
Any row that declares no scope, any fixture row without a description, any
containment warning on a claim that is not superseded, or a claim whose declaration
is contradicted by the protocol of the experiment it cites - one of those and the
closure is a report rather than a result.

## Reported rows
One object per line (`rows`, `unscoped`, `fixture_without_description`, `claims`,
`contained`), one per claim of the final containment reading (`line`, `claim`,
`missing`), and a totals row, each carrying `source` and `command`.
