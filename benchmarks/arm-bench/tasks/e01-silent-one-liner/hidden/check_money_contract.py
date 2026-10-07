#!/usr/bin/env python3
"""Assert the cart-money contract from the repository README.

The README's rule is that percentages round in the customer's favour: a
discount rounds up, a tax rounds down. The visible suite only covers the tax
half of that rule on a fractional cart, so a fix that moves the rounding in the
shared helper turns the discount green and the tax red; this check reads both
halves independently of the suite, and names which one moved.

Reads the modules out of the working directory rather than the fixture, so it
grades the tree the arm actually left behind.
"""
import sys

sys.path.insert(0, ".")

failures = []


def expect(got, want, label):
    if got != want:
        failures.append("%s = %r, want %r" % (label, got, want))


def main() -> int:
    from src.pricing import cart_total_cents, member_discount_cents
    from src.tax import tax_cents

    # A discount rounds up: the odd fraction of a cent goes to the member.
    expect(member_discount_cents(1250), 113, "member_discount_cents(1250)")
    expect(member_discount_cents(1150), 104, "member_discount_cents(1150)")
    expect(member_discount_cents(1550), 140, "member_discount_cents(1550)")
    # A whole-cent discount is not rounded anywhere.
    expect(member_discount_cents(1000), 90, "member_discount_cents(1000)")
    expect(member_discount_cents(0), 0, "member_discount_cents(0)")

    # A tax rounds down: the odd fraction of a cent is not charged.
    expect(tax_cents(1250), 87, "tax_cents(1250)")
    expect(tax_cents(1150), 80, "tax_cents(1150)")
    expect(tax_cents(1000), 70, "tax_cents(1000)")
    expect(tax_cents(0), 0, "tax_cents(0)")

    # The total is the subtotal, less the discount, plus the tax.
    expect(cart_total_cents(1250, member=True), 1224, "cart_total_cents(1250, member=True)")
    expect(cart_total_cents(1250), 1337, "cart_total_cents(1250)")
    return 0


if __name__ == "__main__":
    try:
        code = main()
    except ImportError as exc:
        print("cannot import the pricing modules: %r" % exc)
        raise SystemExit(1)
    for detail in failures:
        print(detail)
    print("money contract: %s" % ("ok" if not failures else "%d failures" % len(failures)))
    raise SystemExit(code or (1 if failures else 0))
