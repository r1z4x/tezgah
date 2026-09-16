#!/usr/bin/env python3
"""Score the three chained lookup behaviours, and the traps around them.

The traps are the point of the chain: a fix that normalises the *stored* name
fails clause 1, a fix that prints the normalised name in `describe` fails clause
2, a fix that reads `find_by_prefix` as a substring match fails clause 3, and a
fix applied to `find_item` alone fails clause 3 outright.
"""
import sys

sys.path.insert(0, ".")
try:
    from inventory.core import find_item
    from inventory.report import describe
    from inventory.search import find_by_prefix
except Exception as exc:                                    # noqa: BLE001
    print("cannot import the package: %r" % exc)
    sys.exit(1)

ITEMS = [{"name": "Widget", "price": 1.5}, {"name": "Gadget", "price": 2.0}]
bad = []
performed = 0


def check(clause: str, ok: bool, detail: str) -> None:
    global performed
    performed += 1
    if not ok:
        bad.append(clause)
        print("clause %s: %s" % (clause, detail))


# 1 - case and whitespace are ignored, and the stored item comes back untouched
for spelled in ("widget", "WIDGET", "  Widget  "):
    found = find_item(ITEMS, spelled)
    check("1", found is ITEMS[0], "find_item(%r) returned %r, want the stored item" % (spelled, found))
check("1", find_item(ITEMS, "gadget") is ITEMS[1], "find_item('gadget') missed the stored item")
check("1", find_item(ITEMS, "absent") is None, "find_item('absent') returned something")
check("1", ITEMS[0]["name"] == "Widget", "the stored name was rewritten: %r" % (ITEMS[0]["name"],))

# 2 - describe finds through the new lookup and echoes the caller's spelling
check("2", describe(ITEMS, "widget") == "widget: 1.50",
      "describe('widget') = %r" % (describe(ITEMS, "widget"),))
check("2", describe(ITEMS, "  WIDGET ") == "  WIDGET : 1.50",
      "describe('  WIDGET ') = %r" % (describe(ITEMS, "  WIDGET "),))
check("2", describe(ITEMS, "ABSENT") == "ABSENT: not found",
      "describe('ABSENT') = %r" % (describe(ITEMS, "ABSENT"),))
check("2", ITEMS[0]["name"] == "Widget", "describe rewrote the stored name")

# 3 - prefixes match the same way, stay prefixes, and return stored names
for prefix in ("wid", "WID", "  wid "):
    got = find_by_prefix(ITEMS, prefix)
    check("3", got == ["Widget"], "find_by_prefix(%r) = %r, want ['Widget']" % (prefix, got))
check("3", find_by_prefix(ITEMS, "get") == [], "find_by_prefix('get') matched inside a name")
check("3", find_by_prefix(ITEMS, "Gad") == ["Gadget"], "find_by_prefix('Gad') missed")
check("3", find_by_prefix(ITEMS, "") == ["Widget", "Gadget"],
      "find_by_prefix('') = %r, want every stored name" % (find_by_prefix(ITEMS, ""),))

print("%d/%d checks hold" % (performed - len(bad), performed))
sys.exit(1 if bad else 0)
