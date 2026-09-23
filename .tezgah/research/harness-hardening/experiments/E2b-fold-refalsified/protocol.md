# E2b — the same fold, with a falsifier a reader can find

## Why this experiment exists
E2's `protocol.md` answers "what would falsify it", and the layer's checker still
reported no falsification criterion: the sentence that denies a prediction is
read as a phrase - a negation, up to four words, then the falsifier word - and
E2's prose put `never running. ## What would falsify it` inside that window, so
the checker cut the answer out as if it were a disclaimer. A protocol is frozen
once its results exist (`check` refuses an edit after the run: "a protocol edited
after the results is not a prediction"), so this is a **child** with a corrected
protocol over the same fold, not an edit of E2's.

## The change under measurement
None. The same fold of the same corpus, with the protocol's falsifier written so
the phrase rule cannot mistake it for a disclaimer.

## What it predicts
The corrected run reaches the same counts as E2: `explorer` and `order` at zero
fires, `drift` the most frequent, and at least two rules confined to a single
day.

## Falsification
This reading is falsified if the fold reports any fire for `explorer` or `order`,
or if no rule is confined to one day, or if the totals differ from E2's by more
than the growth the corpus itself shows between the two runs (E2 read 1613
ledgers; this run may read slightly more).
