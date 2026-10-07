#!/usr/bin/env python3
"""Score `Ledger` against the five clauses of its contract.

Every check is behavioural: the ledger's own storage is never inspected, only
what `total()` says and what `add()` returns or raises. That way a correct
implementation that names its field differently still passes, and the two
defects the fixture ships - a class-level entry list and no validation - fail on
clauses 1 and 4.
"""
import sys

sys.path.insert(0, ".")
try:
    from inventory.ledger import Ledger
except Exception as exc:                                    # noqa: BLE001
    print("cannot import Ledger: %r" % exc)
    sys.exit(1)

bad = []


def fail(clause: str, detail: str) -> None:
    bad.append(clause)
    print("clause %s: %s" % (clause, detail))


# 1 - a fresh ledger is empty, and two ledgers do not share state
first = Ledger()
if first.total() != 0:
    fail("1", "a new ledger totals %r, want 0" % (first.total(),))
second = Ledger()
first.add(5)
if second.total() != 0:
    fail("1", "adding to one ledger changed another: total %r, want 0" % (second.total(),))
if Ledger().total() != 0:
    fail("1", "a ledger constructed after adds is not empty (shared state)")

# 2 - the constructor copies what it is handed
source = [1, 2]
copied = Ledger(source)
source.append(3)
if copied.total() != 3:
    fail("2", "mutating the caller's list changed the ledger: total %r, want 3" % (copied.total(),))

# 3 - add returns the ledger itself
chain = Ledger()
returned = chain.add(1)
if returned is not chain:
    fail("3", "add returned %r, want the ledger itself" % (returned,))

# 4 - a non-positive amount raises the exact message, and changes nothing
for amount in (0, -5, 0.0):
    ledger = Ledger()
    ledger.add(1)
    try:
        ledger.add(amount)
        fail("4", "add(%r) did not raise" % (amount,))
    except ValueError as exc:
        want = "amount must be positive: %s" % (amount,)
        if str(exc) != want:
            fail("4", "add(%r) raised %r, want %r" % (amount, str(exc), want))
    except Exception as exc:                                # noqa: BLE001
        fail("4", "add(%r) raised %r, want ValueError" % (amount, exc))
    if ledger.total() != 1:
        fail("4", "a refused add of %r changed the total to %r, want 1"
             % (amount, ledger.total()))

# 5 - total sums the entries in order
totals = Ledger()
totals.add(1.5)
totals.add(2.25)
if totals.total() != 3.75:
    fail("5", "total is %r, want 3.75" % (totals.total(),))

print("%d clauses hold" % (5 - len(set(bad))))
sys.exit(1 if bad else 0)
