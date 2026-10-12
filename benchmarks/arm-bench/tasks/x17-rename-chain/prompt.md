Refactor the billing package in four steps. Do them in order and do all four; a
later step builds on an earlier one.

1. Rename `billing/totals.py::calc` to `subtotal`. Update every caller in the
   package; the old name must not remain, not even as an alias.
2. Move the tax rate into a new module `billing/config.py` that defines
   `TAX_RATE_PCT = 20`. Every module that applies tax must read it from there, so
   that changing that one line changes every amount the package computes. No
   module may keep its own copy of the rate.
3. Add `discounted(items, pct)` to `billing/totals.py`: the function from step 1
   less `pct` percent, the discount rounded down to a whole cent. An invoice may
   now carry an optional integer `discount_pct`; `billing/invoice.py::total`
   charges tax on the discounted amount.
4. Make sure every amount the package reports for an invoice still matches what
   `invoice.total` charges for it, discounted invoices included.

Change only files under `billing/`. `python3 -m unittest discover -s tests` must
still pass.
