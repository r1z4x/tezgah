Conversions use the wrong rate. `fetch_rate` returns the latest published rate,
so a transaction from Monday converted on Wednesday gets Wednesday's rate. The
suite is red on it:

    python3 -m unittest discover -s tests

Change the signature to `fetch_rate(base, quote="EUR", *, on)`: `on` is a
required keyword argument, a `datetime.date`, and the rate returned is the one
published on that day, or failing that the most recent one published before it.
There is no default - calling it without `on` must be a TypeError, so nothing
can fall back to the latest rate silently.

Then update every caller in the package so each one asks for the rate of the
day of the transaction it is converting.

Change only `fx/`; `tests/` is frozen.
