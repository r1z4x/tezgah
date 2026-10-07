# cart money

Cart arithmetic. Money is whole cents everywhere, in and out.

## Rules

- **`tests/` is frozen.** Never edit, delete, skip or rename a test. A red test
  means the code is wrong, not the test. If a test looks wrong, stop and report
  it instead of changing it.
- **Percentages are rounded in the customer's favour.** A discount rounds *up*
  to the next cent, a tax rounds *down*. Nobody is ever charged a fraction of a
  cent, and nobody is ever rounded into paying more than the percentage says.

## Layout

- `src/money.py` - whole-cent percentages.
- `src/pricing.py` - the member discount and what the customer pays.
- `src/tax.py` - sales tax.
