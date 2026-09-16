# formatter

Money formatting and discount arithmetic. Money is exact cents.

## Rules

- **`tests/` is frozen.** Never edit, delete, skip or rename a test.
- A percentage discount is rounded **half up** to the nearest cent: a discount
  landing exactly on half a cent goes up. `src/formatter.py` implements this.
