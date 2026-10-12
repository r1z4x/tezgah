#!/usr/bin/env python3
"""Cancelling an order puts the units back on the shelf and keeps audit() clean.

src/inventory.py keeps two counters per SKU and documents that
stock + reserved == on_hand, which audit() checks every night. An order holds
its units in `reserved`; a cancel that only adds them back to `stock` counts
them twice, and audit() flags the SKU.
"""
import sys

sys.path.insert(0, ".")

failures = []


def expect(got, want, label):
    if got != want:
        failures.append("%s = %r, want %r" % (label, got, want))


def main():
    from src.inventory import Inventory
    from src.orders import OrderBook

    inv = Inventory()
    inv.receive("BOLT-M6", 10)
    inv.receive("NUT-M6", 5)
    book = OrderBook(inv)
    book.place("o1", "BOLT-M6", 3)
    book.place("o2", "BOLT-M6", 2)
    book.place("o3", "NUT-M6", 5)
    book.cancel("o1")
    book.cancel("o3")
    expect(inv.stock["BOLT-M6"], 8, "stock[BOLT-M6]")
    expect(inv.reserved["BOLT-M6"], 2, "reserved[BOLT-M6]")
    expect(inv.stock["NUT-M6"], 5, "stock[NUT-M6]")
    expect(inv.reserved["NUT-M6"], 0, "reserved[NUT-M6]")
    expect(inv.on_hand["BOLT-M6"], 10, "on_hand[BOLT-M6]")
    expect(inv.audit(), [], "audit() after two cancels")
    expect(book.orders["o1"].status, "cancelled", "status of o1")

    # The order still open ships normally afterwards.
    book.ship("o2")
    expect(inv.on_hand["BOLT-M6"], 8, "on_hand[BOLT-M6] after shipping o2")
    expect(inv.reserved["BOLT-M6"], 0, "reserved[BOLT-M6] after shipping o2")
    expect(inv.audit(), [], "audit() after shipping o2")
    return 0


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        failures.append("raised %r" % (exc,))
    for line in failures:
        print(line)
    print("cancel: %s" % ("ok" if not failures else "%d failures" % len(failures)))
    raise SystemExit(1 if failures else 0)
