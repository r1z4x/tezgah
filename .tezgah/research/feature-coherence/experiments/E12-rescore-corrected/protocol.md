# E12 - re-score the second feature against the corrected corpus

## What changes
Nothing. `E5-transfer/corpus-correction.md` withdrew row A13 (false) and added A15 in
its place after the arms had run. This experiment re-scores every second-feature arm
against the corrected corpus, independently of the session that built it.

## Method
An independent pass re-reads the four E5 artifacts and the four E6 artifacts against
the corrected corpus (A13 withdrawn, A15 in its place, six defect classes) and reports
per arm: defect classes detected, the union, and any claim the corrected corpus now
contradicts. It may not edit the corpus and may not consult the earlier scoring.

## Predicts
The re-score reproduces the session's numbers (E5: baseline 5, treatment 4; E6: 4 and
4) and finds at least one artifact asserting the withdrawn mechanism - which is the
cost of a false row and the reason the correction exists.

## Falsification criterion
A re-score that differs from the session's on any class would mean the scoring was not
reproducible, and the difference is reported per class with the artifact passage that
decides it.
