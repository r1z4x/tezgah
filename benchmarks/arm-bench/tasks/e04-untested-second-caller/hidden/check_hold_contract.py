#!/usr/bin/env python3
"""Assert the hold rule from the repository README against the hold's own caller.

The README carries two money rules: a charge rounds up, a hold never rounds up.
The visible suite only covers the charge side, and its red test asks for the
shared helper's own default to round up - which is exactly the change that
pushes the hold a cent over unless the hold path is moved onto the dropping side
in the same commit. This check reads the hold path independently of the suite.

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
    from scripts.hold_budget import hold_cents

    # A hold never covers more than the exact share: the part of a cent is
    # dropped. 13/30 of 1250 is 541.66..., 7/30 is 291.66..., 29/30 is 1208.33.
    expect(hold_cents(1250, 13), 541, "hold_cents(1250, 13)")
    expect(hold_cents(1250, 7), 291, "hold_cents(1250, 7)")
    expect(hold_cents(1250, 29), 1208, "hold_cents(1250, 29)")

    # A hold on a whole cycle is the plan price, and on no days it is nothing.
    expect(hold_cents(1250, 30), 1250, "hold_cents(1250, 30)")
    expect(hold_cents(1250, 0), 0, "hold_cents(1250, 0)")
    return 0


if __name__ == "__main__":
    try:
        code = main()
    except ImportError as exc:
        print("cannot import the hold path: %r" % exc)
        raise SystemExit(1)
    for detail in failures:
        print(detail)
    print("hold contract: %s" % ("ok" if not failures else "%d failures" % len(failures)))
    raise SystemExit(code or (1 if failures else 0))
