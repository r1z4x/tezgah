# E2 — could a number-in-the-proof rule be enforced as it stands?

## The change under measurement
None. This measures the *feasibility* of the cheapest control the layer could
carry: **a number a claim asserts must appear in the artifact the claim cites**,
so a figure that came out of nowhere - or out of a different run - cannot pass.

## What it predicts
1. Most claims cite an **experiment directory or a table**, not the row that
   carries the number, so a naive containment rule refuses the majority of
   existing claims. Predicted: fewer than half of the numeric claims have every
   number they assert present in their cited files.
2. The claims that do pass tend to be those quoting a ledger fold or a test
   output verbatim.
3. Therefore the control is viable only in a weaker shape: *the artifact must
   contain the numbers, or the claim must say it is a summary and name the run it
   summarises* - and the measurement decides which.

## Falsification
Viable as-is if at least 90% of the numeric claims have every asserted number
present verbatim in their cited artifacts.

## Method
- For every claim with a proof, read the cited files; extract from the claim's
  `statement` the numbers it asserts (a decimal, an integer, or an `A of B`
  pair); report, per claim, how many of those tokens appear verbatim in the
  concatenated proof text.
- Report the share of claims fully contained, partly contained and uncontained,
  and name the uncontained ones with the token that failed.
- State the false-negative sources: a number restated in prose (`twenty`) and a
  derived percentage computed in the statement are not tokens in the artifact.

## Reported rows
One object per claim (`line`, `claim`, `tokens`, `contained`, `missing`,
`verdict`) plus a totals row, each carrying `source` and `command`.
