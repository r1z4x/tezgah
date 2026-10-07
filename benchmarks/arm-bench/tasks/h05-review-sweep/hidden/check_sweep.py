#!/usr/bin/env python3
"""One check per finding of the review sweep.

    python3 check_sweep.py discount|pages|cart|validate|quantity|lookup

One check per finding, rather than one check for the sweep, so a row records
*which* findings an arm completed: a row that fails still says how far it got,
and a harness that finishes more of a long task shows up in the data.
"""
import sys

NAME = sys.argv[1] if len(sys.argv) > 1 else ""
sys.path.insert(0, ".")

failures = []


def expect(ok: bool, detail: str) -> None:
    if not ok:
        failures.append(detail)


def discount() -> None:
    from inventory.core import apply_discount
    table = [(9.80, 2.5, 9.55), (10.20, 2.5, 9.94), (0.02, 25, 0.01),
             (1.05, 50, 0.52), (19.99, 33.3, 13.33), (100.0, 10, 90.0)]
    for price, pct, want in table:
        got = apply_discount(price, pct)
        expect(round(got * 100) == round(want * 100),
               "apply_discount(%r, %r) = %r, want %r" % (price, pct, got, want))


def pages() -> None:
    from inventory.paginate import page_bounds, page_count
    expect(page_bounds(10, 3, 1) == (0, 3), "page_bounds(10, 3, 1) = %r, want (0, 3)"
           % (page_bounds(10, 3, 1),))
    expect(page_bounds(10, 3, 2) == (3, 6), "page_bounds(10, 3, 2) = %r, want (3, 6)"
           % (page_bounds(10, 3, 2),))
    expect(page_bounds(10, 3, 4) == (9, 10), "page_bounds(10, 3, 4) = %r, want (9, 10)"
           % (page_bounds(10, 3, 4),))
    expect(page_count(10, 3) == 4, "page_count(10, 3) = %r, want 4" % (page_count(10, 3),))


def cart() -> None:
    from inventory.cart import add_item, make_cart
    first = make_cart()
    second = make_cart()
    add_item(first, "widget", 1.0)
    expect(second["items"] == [], "a cart made later shares state: %r" % (second["items"],))
    seeding = [{"name": "seeded", "price": 2.0}]
    adopted = make_cart(seeding)
    seeding.append({"name": "extra", "price": 3.0})
    expect(len(adopted["items"]) == 1,
           "the list passed in was adopted, not copied: %r" % (adopted["items"],))
    expect(first["items"] == [{"name": "widget", "price": 1.0, "qty": 1}],
           "add_item no longer appends: %r" % (first["items"],))


def validate() -> None:
    from inventory.errors import InventoryError
    from inventory.validate import load_items
    clean = load_items([{"name": "a", "price": 1.5}])
    expect(clean == [{"name": "a", "price": 1.5}], "load_items dropped a valid entry: %r" % (clean,))
    for bad in ([{"name": "a", "price": 0}], [{"name": "a", "price": -1}],
                [{"name": "", "price": 1}], [{"name": 7, "price": 1}],
                [{"name": "a"}], ["not a dict"], [{"name": "a", "price": "1.5"}]):
        try:
            load_items(bad)
            failures.append("load_items(%r) accepted invalid input" % (bad,))
        except InventoryError:
            pass
        except Exception as exc:                            # noqa: BLE001
            failures.append("load_items(%r) raised %r, want InventoryError" % (bad, exc))


def quantity() -> None:
    from inventory.errors import InventoryError
    from inventory.parsing import parse_quantity
    expect(parse_quantity(" 12 ") == 12, "parse_quantity(' 12 ') = %r, want 12"
           % (parse_quantity(" 12 "),))
    for bad in ("12.5", "", "abc", "1e3"):
        try:
            got = parse_quantity(bad)
            failures.append("parse_quantity(%r) returned %r, want InventoryError" % (bad, got))
        except InventoryError as exc:
            want = "invalid quantity: %s" % (bad,)
            expect(str(exc) == want,
                   "parse_quantity(%r) raised %r, want %r" % (bad, str(exc), want))
        except Exception as exc:                            # noqa: BLE001
            failures.append("parse_quantity(%r) raised %r, want InventoryError" % (bad, exc))


def lookup() -> None:
    from inventory.core import find_item
    items = [{"name": "Widget", "price": 1.5}]
    for spelled in ("widget", "WIDGET", "  Widget  "):
        expect(find_item(items, spelled) is items[0],
               "find_item(%r) missed the stored item" % (spelled,))
    expect(find_item(items, "absent") is None, "find_item('absent') returned something")
    expect(items[0]["name"] == "Widget", "find_item rewrote the stored name")


CHECKS = {"discount": discount, "pages": pages, "cart": cart,
          "validate": validate, "quantity": quantity, "lookup": lookup}

if NAME not in CHECKS:
    print("unknown check: %r (known: %s)" % (NAME, ", ".join(sorted(CHECKS))))
    sys.exit(2)
try:
    CHECKS[NAME]()
except ImportError as exc:
    print("cannot import the package: %r" % exc)
    sys.exit(1)
for detail in failures[:8]:
    print(detail)
print("%s: %s" % (NAME, "ok" if not failures else "%d failures" % len(failures)))
sys.exit(1 if failures else 0)
