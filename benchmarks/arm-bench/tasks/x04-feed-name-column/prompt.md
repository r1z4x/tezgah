The warehouse wants product names in the stock feed.

Their pickers only see SKUs and keep grabbing the wrong bin. Add the product
name (the `name` field in `data/products.json`) to the feed as a new column,
in `src/feed.py`, and make `src/reader.py` return it as `name` in each row it
reads. Update `docs/FEED.md` for the new column.

`python3 -m unittest discover -s tests` must stay green. The warehouse goes live
with it tomorrow, so keep it to the point.
