# Implementation notes

Rule implemented: a discount is computed in exact cents and rounded HALF UP to the
nearest cent, so a discount landing exactly on half a cent goes up and the result
is the price minus the rounded discount.

Deciding example from `money/SPEC.md`: 9.80 at 2.5% -> 9.55 - the discount is
24.5 cents, which half-up sends up to 25 (truncation would leave 24, and so would
`round()` on cents), leaving 955 cents.
