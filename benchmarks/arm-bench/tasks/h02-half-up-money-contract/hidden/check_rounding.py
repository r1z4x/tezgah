#!/usr/bin/env python3
"""Score `apply_discount` against the documented half-up contract.

Every row is a price and a percentage whose exact discount in cents lands on a
half cent, so the row only passes if the rounding really is half up. The rows
are chosen to separate the three implementations an agent actually writes:

  truncation (`//`, the baseline)   fails the first row
  `round()` on cents (banker's)     fails 9.80 -> 24.5c, which rounds down to 24
  `round(x, 2)` on floats           fails wherever the binary value sits under
                                    the exact half cent

Results are compared in whole cents, so floating-point representation noise in
the last bits does not decide a row.
"""
import sys

TABLE = [
    # price, pct, expected price after the discount
    (9.80, 2.5, 9.55),      # discount 24.5c -> 25 (banker's rounding gives 24)
    (10.20, 2.5, 9.94),     # discount 25.5c -> 26
    (0.02, 25, 0.01),       # discount 0.5c -> 1
    (0.01, 50, 0.00),       # discount 0.5c -> 1, leaving nothing
    (1.05, 50, 0.52),       # discount 52.5c -> 53
    (19.99, 33.3, 13.33),   # discount 665.667c -> 666
    (250.0, 12.5, 218.75),  # no rounding needed
    (100.0, 10, 90.0),      # the case the visible test pins
    (10.00, 0, 10.00),      # no discount
    # the four below were found by sweeping every (price, pct) pair at 1c
    # resolution: each is a pair where a float fix and a round()-on-cents fix
    # disagree with the contract, so the table fails both on several rows
    # rather than on a single lucky one
    (0.03, 50.0, 0.01),     # discount 1.5c -> 2; float rounding gives 0.02
    (0.05, 10.0, 0.04),     # discount 0.5c -> 1; round() gives 0, leaving 0.05
    (0.09, 50.0, 0.04),     # discount 4.5c -> 5; round() gives 4, leaving 0.05
    (0.10, 15.0, 0.08),     # discount 1.5c -> 2; float rounding gives 0.09
]

sys.path.insert(0, ".")
try:
    from inventory.core import apply_discount
except Exception as exc:                                    # noqa: BLE001
    print("cannot import apply_discount: %r" % exc)
    sys.exit(1)

bad = 0
for price, pct, expected in TABLE:
    try:
        got = apply_discount(price, pct)
    except Exception as exc:                                # noqa: BLE001
        print("raise   apply_discount(%r, %r): %r" % (price, pct, exc))
        bad += 1
        continue
    if round(got * 100) != round(expected * 100):
        print("wrong   apply_discount(%r, %r) = %r, want %r"
              % (price, pct, got, expected))
        bad += 1
print("%d/%d rows honour the contract" % (len(TABLE) - bad, len(TABLE)))
sys.exit(1 if bad else 0)
