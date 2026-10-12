#!/usr/bin/env python3
"""Every place billing turns an amount into cents rounds it half up.

README.md: charged, refunded, stored or printed, a float amount becomes integer
cents through money.to_cents. Each value below is one where truncation,
floor or Python's round-half-even lands on a different cent than half up.
"""
import sys

sys.path.insert(0, ".")

failures = []


def expect(got, want, label):
    if got != want:
        failures.append("%s = %r, want %r" % (label, got, want))


def main():
    from billing.deposits import deposit_cents
    from billing.discount import discount_cents
    from billing.invoice import line_total_cents
    from billing.receipt import receipt_line
    from billing.refunds import refund_cents
    from billing.shipping import shipping_cents
    from billing.tax import tax_cents

    expect(line_total_cents(4.35, 2), 870, "line_total_cents(4.35, 2)")
    expect(line_total_cents(1.15, 1), 115, "line_total_cents(1.15, 1)")
    expect(line_total_cents(0.29, 3), 87, "line_total_cents(0.29, 3)")
    expect(tax_cents(1.45), 29, "tax_cents(1.45)")
    expect(tax_cents(2.5, 0.05), 13, "tax_cents(2.5, 0.05)")
    expect(shipping_cents("standard"), 435, "shipping_cents(standard)")
    expect(shipping_cents("express"), 995, "shipping_cents(express)")
    expect(refund_cents(0.57), 57, "refund_cents(0.57)")
    expect(refund_cents(0.125), 13, "refund_cents(0.125)")
    expect(deposit_cents(2.5), 63, "deposit_cents(2.5)")
    expect(deposit_cents(4.5), 113, "deposit_cents(4.5)")
    expect(receipt_line("Tea", 1.15).split()[-1], "115", "receipt_line(Tea, 1.15)")
    expect(receipt_line("Tea", 0.125).split()[-1], "13", "receipt_line(Tea, 0.125)")
    expect(discount_cents(4.35, 10), 44, "discount_cents(4.35, 10)")
    # Whole amounts stay whole.
    expect(line_total_cents(2.0, 3), 600, "line_total_cents(2.0, 3)")
    expect(shipping_cents("pickup"), 0, "shipping_cents(pickup)")
    expect(refund_cents(10), 1000, "refund_cents(10)")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        failures.append("raised %r" % exc)
    for detail in failures:
        print(detail)
    print("cents: %s" % ("ok" if not failures else "%d failures" % len(failures)))
    raise SystemExit(1 if failures else 0)
