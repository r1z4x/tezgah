#!/usr/bin/env python3
"""Grade `search` against crm/SPEC.md, one clause per argument.

  normalize  rules 1-3: NFC, casefold (lower() leaves "ß" and "ﬁ" unfolded),
             whitespace collapsed on both sides.
  words      rule 4: a match starts at a word; a substring inside a word does
             not match.
  empty      rule 5: None, "" and "   " match nothing.
  order      the change log's replacement of rule 6: surname first, then full
             name, ties in input order.

Only `order` compares the sequence; the other clauses compare the set of ids, so
a wrong order is counted once, under `order`.
"""
import sys

sys.path.insert(0, ".")

PEOPLE = [
    {"id": 1, "name": "Gärtnerei Straße"},
    {"id": 2, "name": "anna keller"},
    {"id": 3, "name": "Maria Anna Keller"},
    {"id": 4, "name": "Joanna Berg"},
    {"id": 5, "name": "Ren\u0065\u0301 Zimmer"},       # decomposed é
    {"id": 6, "name": "  Annika   Adler "},
    {"id": 7, "name": "Anna Keller"},                 # equal to id 2 once folded;
                                                      # a raw sort puts it first
    {"id": 8, "name": "Anton Berg"},
    {"id": 9, "name": "ﬁnn Olsen"},                   # U+FB01 ligature, folds to "fi"
]

CASES = {
    "normalize": [
        ("STRASSE", [1]),
        ("straße", [1]),
        ("Ren\u00e9", [5]),                           # composed query, decomposed name
        ("FINN", [9]),
        ("annika adler", [6]),
        ("  anna   KELLER ", [2, 7, 3]),
    ],
    "words": [
        ("ann", [6, 2, 7, 3]),
        ("anna k", [2, 7, 3]),
        ("oanna", []),
        ("keller", [2, 7, 3]),
        ("eller", []),
    ],
    "empty": [
        (None, []),
        ("", []),
        ("   ", []),
    ],
    "order": [
        # surnames: adler, berg, keller x3; among the kellers "anna keller"
        # (ids 2 and 7, input order) before "maria anna keller"; the old
        # full-name rule 6 gives [2, 7, 6, 8, 3]
        ("an", [6, 8, 2, 7, 3]),
        # both surnames are berg: then "anton berg" before "joanna berg"
        ("b", [8, 4]),
    ],
}


def main(clause):
    try:
        from crm.search import search
    except Exception as exc:                                  # noqa: BLE001
        print("cannot import search: %r" % exc)
        return 1
    bad = 0
    for query, want in CASES[clause]:
        try:
            got = [c["id"] for c in search(query, [dict(p) for p in PEOPLE])]
        except Exception as exc:                              # noqa: BLE001
            print("raise  search(%r): %r" % (query, exc))
            bad += 1
            continue
        if (got if clause == "order" else sorted(got)) != (want if clause == "order" else sorted(want)):
            print("wrong  search(%r) = %r, want %r" % (query, got, want))
            bad += 1
    print("%s: %d/%d queries" % (clause, len(CASES[clause]) - bad, len(CASES[clause])))
    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1]))
