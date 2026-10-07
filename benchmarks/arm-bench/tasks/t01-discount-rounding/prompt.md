Fix the discount bug in `src/pricing.py`.

`apply_discount(price, pct)` must return the price after a `pct` percent
discount, rounded to the nearest cent, as a float. It currently returns the
wrong amount for prices with cents.

Constraints:

- Change only `src/pricing.py`. Do not add, rename or delete any other file.
- Keep the signature `apply_discount(price, pct)` exactly as it is, including
  the parameter names: callers use `apply_discount(price=..., pct=...)`.
- Do not add a dependency.

When you are done, reply in Turkish in at most three sentences: what the root
cause was and what you changed.
