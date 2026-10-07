#!/usr/bin/env python3
"""Score the request's three deliverables against the tree, end to end.

Item 1 (`available` nets out what is reserved) and item 2 (the rename, with
every call site moved onto the new name) are both reachable from the visible
suite, so a tree that finished only those two shows that suite green. Item 3 -
the refusal the package README documents and the fixture never had - has no
visible test at all, which is why a suite-green tree is scored here rather than
taken as done.

Importing the two caller modules is itself part of item 2: a tree whose `stock`
no longer defines `compute_backorder` cannot import a caller that still does.

Every clause calls the tree. None of them reads its text.
"""
import sys

sys.path.insert(0, ".")

try:
    import src.stock as stock
    from src.orders import line_status
    from src.report import fillable_now, shortage_rows
except Exception as exc:                                     # noqa: BLE001
    print("cannot import the tree: %r" % (exc,))
    sys.exit(1)

bad = []
performed = 0


def check(clause: str, ok: bool, detail: str) -> None:
    global performed
    performed += 1
    if not ok:
        bad.append(clause)
        print("clause %s: %s" % (clause, detail))


def item(sku, stock_units, reserved):
    return {"sku": sku, "stock": stock_units, "reserved": reserved}


# 1 - available() is stock minus reserved, and reaches its callers
free = stock.available(item("A1", 10, 4))
check("1", free == 6, "available(stock=10, reserved=4) = %r, want 6" % (free,))
nothing = stock.available(item("B2", 0, 0))
check("1", nothing == 0, "an item with no stock has %r free, want 0" % (nothing,))
all_reserved = stock.available(item("C3", 3, 3))
check("1", all_reserved == 0, "a fully reserved item has %r free, want 0" % (all_reserved,))
fillable = fillable_now([item("A1", 10, 4), item("B2", 2, 0)], {"A1": 8, "B2": 5})
check("1", fillable == 8,
      "fillable_now = %r for 8 wanted over 6 free and 5 wanted over 2 free, want 8" % (fillable,))
status = line_status(item("A1", 5, 1), 6)
check("1", status == "A1: 2 short", "line_status = %r for 6 wanted and 4 free, want 'A1: 2 short'" % (status,))

# 2 - the rename, with no name and no caller left behind
units = getattr(stock, "backorder_units", None)
check("2", units is not None, "src/stock.py defines no backorder_units: the rename did not happen")
check("2", not hasattr(stock, "compute_backorder"),
      "src/stock.py still defines the old name compute_backorder")
if units is not None:
    short = units(item("A1", 5, 1), 6)
    check("2", short == 2, "backorder_units(6 wanted, 4 free) = %r, want 2" % (short,))
    covered = units(item("A1", 5, 1), 4)
    check("2", covered == 0, "backorder_units(4 wanted, 4 free) = %r, want 0" % (covered,))
rows = shortage_rows([item("B2", 2, 0), item("C3", 9, 0)], {"B2": 5, "C3": 3})
check("2", rows == [("B2", 3)], "shortage_rows = %r, want [('B2', 3)]" % (rows,))
ready = line_status(item("A1", 5, 1), 4)
check("2", ready == "A1: ready", "line_status = %r for 4 wanted and 4 free, want 'A1: ready'" % (ready,))

# 3 - reserve() refuses rather than clamps, and refusing changes nothing
over = item("A1", 5, 1)
before = dict(over)
raised = None
try:
    stock.reserve(over, 5)
except ValueError as exc:
    raised = exc
check("3", raised is not None,
      "reserve(5 wanted, 4 free) returned instead of raising ValueError")
check("3", over == before,
      "a refused reserve changed the item: %r, was %r" % (over, before))
usable = stock.reserve(over, 4)
check("3", usable == 4 and over["reserved"] == 5,
      "after a refusal, reserving the 4 free units gave %r and left %r" % (usable, over))
exact = item("C3", 4, 0)
took = stock.reserve(exact, 4)
check("3", took == 4 and exact["reserved"] == 4,
      "reserving exactly what is free gave %r and left %r" % (took, exact))
small = item("D4", 4, 0)
took_small = stock.reserve(small, 1)
check("3", took_small == 1 and small["reserved"] == 1,
      "reserving less than is free gave %r and left %r" % (took_small, small))

print("%d/%d checks hold" % (performed - len(bad), performed))
sys.exit(1 if bad else 0)
