#!/usr/bin/env python3
"""apply_price_list: every price lands, one save, and memoised quotes follow.

src/quotes.py memoises a quote per SKU and drops it only when the catalog
reports the price change through `Catalog.subscribe`; `set_price` does that.
A bulk load that writes the prices straight into the catalog and saves once
leaves every quote that was already computed at the old price.
"""
import sys

sys.path.insert(0, ".")

failures = []


def expect(got, want, label):
    if got != want:
        failures.append("%s = %r, want %r" % (label, got, want))


def main():
    from src.catalog import Catalog
    from src.quotes import QuoteService
    from src.store import Store

    store = Store()
    catalog = Catalog(store)
    quotes = QuoteService(catalog)
    expect(quotes.quote("BOLT-M6"), 144, "quote(BOLT-M6) before")
    expect(quotes.quote("NUT-M6"), 48, "quote(NUT-M6) before")

    catalog.apply_price_list([("BOLT-M6", 200), ("NUT-M6", 50), ("DRILL-8", 1000)])
    expect(catalog.price("BOLT-M6"), 200, "price(BOLT-M6)")
    expect(catalog.price("DRILL-8"), 1000, "price(DRILL-8)")
    expect(store.saves, 1, "Store.save calls for one price list")
    expect(Catalog(store).price("NUT-M6"), 50, "saved price(NUT-M6)")
    # The quotes computed before the load must not survive it.
    expect(quotes.quote("BOLT-M6"), 240, "quote(BOLT-M6) after the price list")
    expect(quotes.quote("NUT-M6"), 60, "quote(NUT-M6) after the price list")
    expect(quotes.quote("DRILL-8"), 1200, "quote(DRILL-8) after the price list")

    # A generator is an iterable of pairs too.
    catalog.apply_price_list((sku, 10) for sku in ["WASHER-M6"])
    expect(catalog.price("WASHER-M6"), 10, "price(WASHER-M6) from a generator")

    # Same rules as set_price for each row.
    for rows, exc in (([("NOPE", 10)], KeyError), ([("BOLT-M6", -5)], ValueError)):
        try:
            catalog.apply_price_list(rows)
        except exc:
            pass
        else:
            failures.append("apply_price_list(%r) did not raise %s" % (rows, exc.__name__))
    return 0


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:  # a missing method is a failure, not a crash
        failures.append("raised %r" % (exc,))
    for line in failures:
        print(line)
    print("price list: %s" % ("ok" if not failures else "%d failures" % len(failures)))
    raise SystemExit(1 if failures else 0)
