# files-api

A small JSON API over one table of file records.

- `app/store.py` holds the records and the lookups.
- `app/api.py` holds the handlers. A handler takes the caller as
  `{"user": "u1"}` (plus whatever else its route needs) and returns JSON-able
  data.
- `ROUTES` maps a route name to its handler; the transport serves those names.
- Tests: `python3 -m unittest discover -s tests`.
