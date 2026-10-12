# stock feed

Every night we send the warehouse a feed of what we sell, and read it back to
reconcile against what they report.

- `docs/FEED.md` - the feed format. The warehouse's own importer follows it too.
- `data/products.json` - the products, as the shop exports them.
- `data/archive/` - feeds already sent, kept for reconciliation.
- `src/feed.py` - writes the feed.
- `src/reader.py` - reads a feed back.
- `src/reconcile.py` - compares a feed with the warehouse's counts.

Run the suite with `python3 -m unittest discover -s tests`.
