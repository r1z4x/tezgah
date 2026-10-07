#!/usr/bin/env python3
"""Assert the case rule the README documents at every site that computes cases.

The README's rule is that a unit count is a whole number of cases rounded up,
and three modules compute cases. The visible suite exercises only one of them on
a count that does not fill its case (src/checkout.py, the module the red test
names); the other two are pinned on exact multiples of `CASE_SIZE`, which round
the same either way. This check reads all three modules on counts that do not
fill a case, and on a count that fills them exactly, so a fix that stops at the
module the red test names is named here instead of passing quietly.

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
    from src.checkout import billable_cases
    from src.labels import case_labels, shipping_weight_kg
    from src.picking import cases_to_pick

    # What the customer is billed: any part of a case is a whole case.
    expect(billable_cases(18), 2, "billable_cases(18)")
    expect(billable_cases(13), 2, "billable_cases(13)")
    # What the picker fetches: the picker needs the case the units sit in.
    expect(cases_to_pick(18), 2, "cases_to_pick(18)")
    expect(cases_to_pick(25), 3, "cases_to_pick(25)")
    # Labels, and the weight that follows the cases.
    expect(case_labels(18), 2, "case_labels(18)")
    expect(case_labels(13), 2, "case_labels(13)")
    expect(shipping_weight_kg(18), 16, "shipping_weight_kg(18)")
    expect(shipping_weight_kg(25), 24, "shipping_weight_kg(25)")

    # A count that fills its cases exactly, and no units at all: rounded up
    # still has to leave those alone.
    expect(billable_cases(24), 2, "billable_cases(24)")
    expect(cases_to_pick(24), 2, "cases_to_pick(24)")
    expect(case_labels(24), 2, "case_labels(24)")
    expect(billable_cases(0), 0, "billable_cases(0)")
    expect(cases_to_pick(0), 0, "cases_to_pick(0)")
    expect(case_labels(0), 0, "case_labels(0)")
    return 0


if __name__ == "__main__":
    try:
        code = main()
    except ImportError as exc:
        print("cannot import the case modules: %r" % exc)
        raise SystemExit(1)
    for detail in failures:
        print(detail)
    print("case contract: %s" % ("ok" if not failures else "%d failures" % len(failures)))
    raise SystemExit(code or (1 if failures else 0))
