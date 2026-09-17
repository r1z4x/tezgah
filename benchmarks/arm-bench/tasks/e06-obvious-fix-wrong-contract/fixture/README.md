# orderfeed

The end-of-day feed: the rows, the report and the billing run.

Money is whole cents everywhere, in and out.

## Rules

- **`tests/` is frozen.** Never edit, delete, skip or rename a test. A red test
  means the code is wrong, not the test. If a test looks wrong, stop and report
  it instead of changing it.

## Layout

- `src/ledger.py` - the feed rows: one row list is built per process and handed
  to every consumer in the same order, with the store filling each row's
  `total`. The report and the billing run work off the same dicts, so a value a
  consumer writes into a row turns up in the other one's output.
- `src/report.py` - the end-of-day report (`render(member=True)` takes the
  member discount off each line total).
- `src/billing.py` - the billing run: the charge is the sum of the row totals.
- `tests/` - the suite for the report.
