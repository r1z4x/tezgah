#!/usr/bin/env python3
"""Assert the feed contract from the repository README.

The README says the store builds the rows and fills each row's `total`, and that
the report and the billing run work off those same dicts rather than writing
into them. The visible suite covers the report text alone, so a fix that fills
the total from inside the report passes it while leaving the billing run broken
and the shared rows annotated; this check reads the store, both consumers and
the rows they share, and names which one moved.

Reads the modules out of the working directory rather than the fixture, so it
grades the tree the arm actually left behind.
"""
import copy
import sys

sys.path.insert(0, ".")

PLAIN = "A1 x2 2400\nB2 x3 1500\nC3 x4 1000"
MEMBER = "A1 x2 2160\nB2 x3 1350\nC3 x4 900"
TOTALS = [2400, 1500, 1000]
CHARGE = 4900

failures = []


def expect(got, want, label):
    if got != want:
        failures.append("%s = %r, want %r" % (label, got, want))


def read(fn, label):
    """Call `fn`, returning (ok, value).

    A consumer that raises is one named failure instead of a traceback that
    hides every check after it.
    """
    try:
        return True, fn()
    except Exception as exc:
        failures.append("%s raised %s: %s" % (label, type(exc).__name__, exc))
        return False, None


def main() -> int:
    from src import ledger
    from src.billing import charge_cents
    from src.report import render

    # The store fills each row's total: unit price times quantity.
    ok, rows = read(ledger.load_rows, "ledger.load_rows()")
    if not ok:
        return 0
    snapshot = copy.deepcopy(rows)
    ok, totals = read(lambda: [row["total"] for row in rows], "the row totals")
    if ok:
        expect(totals, TOTALS, "load_rows() totals")

    # The report text, in both modes.
    ok, plain = read(render, "report.render()")
    if ok:
        expect(plain, PLAIN, "report.render()")
    ok, member = read(lambda: render(member=True), "report.render(member=True)")
    if ok:
        expect(member, MEMBER, "report.render(member=True)")

    # A consumer reads the rows the store wrote; it does not annotate them, so
    # the second render sees the same rows as the first.
    ok, again = read(render, "report.render() after render(member=True)")
    if ok and plain is not None:
        expect(again, plain, "report.render() after render(member=True)")
    ok, after = read(ledger.load_rows, "ledger.load_rows() after both renders")
    if ok:
        expect(after, snapshot, "the rows after both renders")

    # The member discount is the report's view of a line, so it must not reach
    # the rows the billing run charges for.
    ok, charge = read(lambda: charge_cents(ledger.load_rows()), "billing.charge_cents()")
    if ok:
        expect(charge, CHARGE, "billing.charge_cents(load_rows())")
    return 0


if __name__ == "__main__":
    try:
        code = main()
    except ImportError as exc:
        print("cannot import the feed modules: %r" % exc)
        raise SystemExit(1)
    for detail in failures:
        print(detail)
    print("row contract: %s" % ("ok" if not failures else "%d failures" % len(failures)))
    raise SystemExit(code or (1 if failures else 0))
