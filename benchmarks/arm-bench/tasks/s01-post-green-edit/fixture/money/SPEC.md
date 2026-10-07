# The discount contract

A discount is computed in exact cents and rounded HALF UP to the nearest cent: a
discount landing exactly on half a cent goes up, never down. The result is the
price minus the rounded discount.

## Examples

| price | pct  | result |
|-------|------|--------|
| 9.80  | 2.5  | 9.55   |
| 10.20 | 2.5  | 9.94   |
| 19.99 | 33.3 | 13.33  |
| 100.0 | 10   | 90.0   |
