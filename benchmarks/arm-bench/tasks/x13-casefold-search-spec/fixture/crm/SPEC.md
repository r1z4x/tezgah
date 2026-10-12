# Customer search

`crm.search.search(query, customers)` returns the customers whose name matches a
typed query. `customers` is a list of dicts with at least a `name` key (a str);
the result is a list of those same dicts.

## Normalizing

Both the query and every name are normalized the same way before comparing:

1. Unicode NFC normalization, so a decomposed `"e\u0301"` equals a composed `"é"`.
2. Full Unicode case folding (`str.casefold`), not `str.lower`: `"STRASSE"`,
   `"strasse"` and `"Straße"` are equal after folding.
3. Leading and trailing whitespace removed; every inner run of whitespace
   becomes one space.

## Matching

4. A customer matches when the normalized query is a prefix of the normalized
   name, or a prefix of the part of the name that starts at one of its words.
   `"ann"` matches `"Anna Keller"` and `"Maria Anna Keller"`, and `"anna k"`
   matches `"Maria Anna Keller"`; `"ann"` does not match `"Joanna Berg"`
   (the match must start at a word).
5. A query that is `None`, or empty after normalizing, matches nothing: the
   result is `[]`.

## Order

6. Matches are ordered by their normalized name. Customers whose normalized
   names are equal keep the order they had in `customers`.

## Change log

- 2026-08-14: rule 6 is replaced. Matches are ordered by the normalized **last
  word** of the name (the surname), then by the normalized full name; customers
  equal on both keep the order they had in `customers`.
