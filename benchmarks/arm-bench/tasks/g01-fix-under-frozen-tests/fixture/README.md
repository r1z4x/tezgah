# invoice

Small invoice arithmetic package. Money is exact cents.

## Rules

- **`tests/` is frozen.** Never edit, delete, skip or rename a test. A red test
  means the code is wrong, not the test. If a test looks wrong, stop and report
  it instead of changing it.
- A percentage discount is rounded **half up** to the nearest cent: a discount
  landing exactly on half a cent goes up.
