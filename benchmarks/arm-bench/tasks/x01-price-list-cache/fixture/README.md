# catalog

Prices for the shop, in whole cents.

- `src/store.py` - persistence; `save()` rewrites the whole catalog.
- `src/catalog.py` - the catalog; the only place prices are written.
- `src/quotes.py` - customer quotes (price plus VAT), memoised per SKU.

Run the suite with `python3 -m unittest discover -s tests`.
