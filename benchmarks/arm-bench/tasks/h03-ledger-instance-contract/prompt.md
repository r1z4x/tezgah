`inventory/ledger.py` does not match the contract the package documents for a
ledger. Make it match. The contract:

1. A ledger owns its entries. Constructing a ledger gives it an empty set of
   entries, and two ledgers never share state: adding to one never changes what
   another totals.
2. `Ledger(entries)` accepts an optional iterable and takes a copy of it - the
   ledger must not change if the caller mutates the list it passed in.
3. `add(amount)` appends the amount and returns the ledger itself, so adds can
   be chained.
4. `add` refuses a non-positive amount by raising a `ValueError` whose message is
   exactly `amount must be positive: <amount>`, where `<amount>` is the value as
   it was passed. A refused add changes nothing.
5. `total()` returns the sum of the entries.

Change only `inventory/ledger.py`. `python3 -m unittest discover -s tests` must
still pass.

Note what the current code does: the entries are not per instance, and any
amount is accepted.
