#!/usr/bin/env python3
"""The feed carries product names, and every feed still reads back.

docs/FEED.md: a field never holds a bare `|` or `\\` (they are escaped), and
a column added later is optional when reading, because readers must accept
every feed ever sent (data/archive/). data/products.json already holds a name
with a `|` and one with a `\\`, so a writer that appends the raw name breaks
the reader on today's data.
"""
import sys

sys.path.insert(0, ".")

failures = []


def expect(got, want, label):
    if got != want:
        failures.append("%s = %r, want %r" % (label, got, want))


def main():
    from src.feed import load_products, write_feed
    from src.reader import read_feed
    from src.reconcile import archived, differences

    products = load_products()
    text = write_feed(products)
    expect(len(text.splitlines()), len(products), "lines in the feed")
    rows = read_feed(text)
    for product, row in zip(products, rows):
        for key in ("sku", "qty", "price_cents", "name"):
            expect(row.get(key), product[key], "%s %s read back" % (product["sku"], key))

    odd = [{"sku": "X-1", "name": "a|b\\c||\\|", "qty": 1, "price_cents": 2},
           {"sku": "X-2", "name": "", "qty": 0, "price_cents": 0}]
    expect([r.get("name") for r in read_feed(write_feed(odd))], [p["name"] for p in odd],
           "names with separators and escapes")

    # Every feed already sent still reads, the new column reading as empty.
    old = read_feed(archived("2026-09-30"))
    expect([(r["sku"], r["qty"], r.get("name")) for r in old],
           [("BOLT-M6", 1180, ""), ("NUT-M6", 2950, ""), ("SHELF-1", 41, "")],
           "archived feed")
    expect(differences(text, {p["sku"]: p["qty"] for p in products}), {}, "reconcile today's feed")
    return 0


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        failures.append("raised %r" % (exc,))
    for line in failures:
        print(line)
    print("feed names: %s" % ("ok" if not failures else "%d failures" % len(failures)))
    raise SystemExit(1 if failures else 0)
