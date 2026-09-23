# E6 - the pre-wiring control E5 could not run

## What changes

Nothing in either repository. This experiment supplies the control arm E5 lacked: the
**pre-wiring rubric**, extracted verbatim from commit `0f452df` into
`product-analysis-pre-wiring.md` in this directory (323 lines, zero occurrences of
"coherence"), against the current `skills/product-analysis/SKILL.md` (345 lines,
carrying the coherence pass at `:50-64` and the matrices in its artifact list).

## Method

Same feature as E5 - the admin Users area of `/Users/rizax/Projects/aibim-app` - and
the same frozen corpus (sha256 `9c72a2d42f2c764d3b7614746f0abb1eabe60ed61e8c5d57c8393f366e505c5a`,
six defect classes after the pass rows are removed).

- **Control (2 raters)**: apply `product-analysis-pre-wiring.md` plus the `research`
  skill. They are told the text is the rubric and are not told it is old.
- **Treatment (2 raters)**: apply the current `product-analysis` plus `feature-audit`.

Both arms: code-scope, blind to the corpus, same environment, same brief shape.

## Predicts

The control arm reaches **at most two of the six defect classes** and writes **no
capability-change proposal**; the treatment arm reaches **at least four** and writes
at least one. The gap between the arms should be at least two classes, matching the
first feature's before/after (4 of 9 against 7 of 9).

## Falsification criterion

A control union at or above the treatment union would falsify the claim that the
wiring is what transfers - and would say the pre-wiring rubric already carried the
method, which the file's own text contradicts. A treatment union below four would
falsify the treatment half on this stack.

## Why

E5 could not run this contrast because the wiring had already replaced the control
inside the tree; the pre-wiring text exists only in history. Extracting it makes the
before/after measurable again, on the second stack, with everything else held
constant.
