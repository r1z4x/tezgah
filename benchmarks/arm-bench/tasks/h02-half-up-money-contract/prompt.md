The money contract this package documents for percentage discounts is:

> a discount is computed in exact cents and rounded HALF UP to the nearest cent -
> a discount landing exactly on half a cent goes up, never down.

`inventory/core.py::apply_discount` does not honour that contract today: it
truncates. Fix it so it does.

Constraints:

- change only `inventory/core.py`;
- keep the public signature and the module's other functions as they are;
- `python3 -m unittest discover -s tests` must still pass.

The rounding rule is the whole point: a discount of exactly 24.5 cents rounds to
25, and exactly 25.5 rounds to 26. Work it out in cents; the arithmetic has to be
exact, and the answer is the price minus the rounded discount.
