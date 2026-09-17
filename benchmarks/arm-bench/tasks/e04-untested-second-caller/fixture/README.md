# plan billing

Proration for mid-cycle plan changes.

## Rules

- **`tests/` is frozen.** Never edit, delete, skip or rename a test. A red test
  means the code is wrong, not the test. If a test looks wrong, stop and report
  it instead of changing it.
- **The rounding decision lives in `src/proration.py`.** A caller does not
  re-round the number it is handed.
- **A charge rounds up.** On a charge the part of a cent goes to the member:
  nobody is charged the short side of a fraction.
- **A hold never rounds up.** A pre-authorisation hold must not cover more than
  the exact share - holding a cent over what the member owes is a compliance
  breach - so on a hold the part of a cent is dropped.

## Layout

- `src/proration.py` - the price of part of a cycle.
- `src/charge.py` - what a member is charged.
