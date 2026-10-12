Supplier price lists are too slow to load.

We get a new price list from the supplier every Monday: a few thousand
`(sku, cents)` rows. Today ops loads it by calling `Catalog.set_price` once per
row, and every call rewrites the whole catalog through `Store.save`, so a load
takes most of the morning.

Add `Catalog.apply_price_list(rows)` in `src/catalog.py`: it takes an iterable
of `(sku, cents)` pairs, applies every price, and saves the catalog once at the
end instead of once per row. Same rules as `set_price` for each row.

`python3 -m unittest discover -s tests` has to stay green. Keep it small, ops
wants to use it on Monday.
