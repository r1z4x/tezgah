#!/usr/bin/env python3
"""Grade `invoice_tax` against invoice/SPEC.md, one clause per argument.

  rounding  rule 2: exact arithmetic, half to even at the cent. 2.50 @ 5 and the
            SPEC's own example row separate half-even from half-up; 5.45 @ 10,
            10.90 @ 5 and 12.25 @ 10 land on an exact half cent whose binary
            float sits above it, so `round(float)` gives the odd cent.
  credit    rule 2's last sentence: a credit line rounds on its magnitude and
            keeps its sign (Decimal ROUND_HALF_UP gives -13 for -12.5c).
  exempt    rule 4: a `None` rate contributes 0, an empty invoice is 0.
  shipping  footnote 1: shipping is taxed at the highest non-exempt goods rate,
            and is exempt when there is none.
"""
import sys

sys.path.insert(0, ".")


def line(amount, rate, kind="goods"):
    return {"amount": amount, "rate": rate, "kind": kind}


CASES = {
    "rounding": [
        ([line("2.50", "5")], 12),
        ([line("2.70", "5")], 14),
        ([line("5.45", "10")], 54),
        ([line("10.90", "5")], 54),
        ([line("12.25", "10")], 122),
        ([line("19.99", "8.25")], 165),          # 164.9175c
    ],
    "credit": [
        ([line("-2.50", "5")], -12),
        ([line("-2.70", "5")], -14),
        ([line("100.00", "5"), line("-2.50", "5")], 488),
    ],
    "exempt": [
        ([line("40.00", None)], 0),
        ([], 0),
        ([line("40.00", None), line("2.50", "5")], 12),
    ],
    "shipping": [
        # goods 500 + 412 (412.5c -> 412); shipping 10.00 at 8.25 = 82.5c -> 82
        ([line("100.00", "5"), line("50.00", "8.25"), line("10.00", "0", "shipping")], 994),
        # the shipping line's own rate is ignored even when it is higher
        ([line("100.00", "5"), line("10.00", "20", "shipping")], 550),
        # no taxable goods line: shipping is exempt
        ([line("40.00", None), line("10.00", "5", "shipping")], 0),
        ([line("10.00", "5", "shipping")], 0),
    ],
}


def main(clause):
    try:
        from invoice.tax import invoice_tax
    except Exception as exc:                                  # noqa: BLE001
        print("cannot import invoice_tax: %r" % exc)
        return 1
    bad = 0
    for lines, want in CASES[clause]:
        try:
            got = invoice_tax(lines)
        except Exception as exc:                              # noqa: BLE001
            print("raise  %r: %r" % (lines, exc))
            bad += 1
            continue
        if got != want:
            print("wrong  %r = %r, want %r" % (lines, got, want))
            bad += 1
    print("%s: %d/%d rows" % (clause, len(CASES[clause]) - bad, len(CASES[clause])))
    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1]))
