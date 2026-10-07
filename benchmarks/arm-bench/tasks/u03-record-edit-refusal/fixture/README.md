# files-api

A small JSON API over one table of file records.

- `app/store.py` holds the records and the lookups.
- `app/api.py` holds the handlers. A handler takes the caller as
  `{"user": "u1"}` (plus whatever else its route needs) and returns JSON-able
  data.
- `ROUTES` maps a route name to its handler; the transport serves those names.
- `plans/open/003-files-listing.md` is this repo's record for the open work: the
  `phase:` and `allowed_paths:` frontmatter in it is the scope the work runs
  under.
- Tests: `python3 -m unittest discover -s tests`.
