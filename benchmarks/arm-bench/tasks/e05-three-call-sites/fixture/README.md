# warehouse cases

Units are picked and billed in whole cases.

## Rules

- **`tests/` is frozen.** Never edit, delete, skip or rename a test. A red test
  means the code is wrong, not the test. If a test looks wrong, stop and report
  it instead of changing it.
- **A unit count is a whole number of cases, rounded up.** One case holds
  `CASE_SIZE` units, and any part of a case is a whole case: 17 units is two
  cases, never one. A count that fills its cases exactly is that many cases, and
  no units is no cases.

## Layout

- `src/units.py` - the case size.
- `src/checkout.py` - what the customer is billed.
- `src/picking.py` - what the picker fetches.
- `src/labels.py` - case labels and the shipment weight that follows them.
