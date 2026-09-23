# E3 analysis - the closure, measured

## Against the predictions

| # | prediction | result | verdict |
|---|---|---|---|
| 1 | 0 of 813 rows declare no scope, 0 fixture rows lack a description | **0 of 822 rows, 0 of 371 fixture rows** (the denominator moved because this line recorded two more result blocks between the prediction and the run) | **holds** |
| 2 | the final containment reading leaves 80 of 82 contained, and the two warned are `harness-hardening` C17 and `typesafe-cost` C5 | **80 of 82**, warning on exactly those two | **holds** |
| 3 | the only warnings left are the by-design classes | protocols that predate the rule (7), supersede relations (5), the two superseded rows' containment warnings (2), one single-index source (1), and the git-tracking warns the commit clears (14) | **holds** |

## What the census establishes
- **The debt E1 opened is closed, and the closure is a declaration by a reader.**
  The pre-pass row records 510 unscoped of 813; the census records 0 of 822 and
  `371` fixture rows each naming what was generated, `0` that do not. Every
  declaration was made against the experiment's own protocol or probe, or the
  row's own `command`, and each experiment carries the basis line in its
  `analysis.md`.
- **The containment rule ends where the evidence says it should.** After six
  refinements made against real artifacts (a directory-walking probe, a comma read
  as a decimal point, a date read as three numbers, a thousands separator read as a
  difference, a bare filename the reader never opened, a file truncated at the
  window), the rule leaves 80 of 82 claims contained. The two warned rows are the
  ones a line superseded because their figures had no artifact behind them, and
  their warning is kept on purpose.

## What it does not show
- **It does not show the declarations are true.** Each is a producer's (here, a
  reader's) statement about an input; the census checks that the statement exists,
  not that it is honest - the class 1b limit, unchanged.
- **It does not show the number is stable.** The denominator is every result row in
  the tree, so it moves whenever any line records another row; 813 and 822 are two
  readings of a growing file set, and the pre-closure row is a recorded
  observation rather than something a later session can re-run.
- **It does not show the rule is a gate's worth of accuracy.** 80 of 82 is measured
  on this repository's claims after they were cleaned, by the same pass that closed
  the debt; a cleaner corpus is not a calibrated rule, and the substring match
  means a pass is not proof.
- **The two permanent classes are untouched by this pass**: seven protocols that
  state no prediction predate the rule, and editing one after its results is what
  the order rule exists to refuse, and one source exists in a single index.
