`GET /files` has no handler and support keeps asking for the listing. Two things:

1. Add a `list_files` handler to `app/api.py`. It returns every record the caller
   has whose `state` is `active`, newest `uploaded_at` first, as a list of
   `{"id", "name", "uploaded_at"}`. Nothing else is filtered out: a record whose
   bytes are gone is still an active record and belongs in the listing. Register
   it in `ROUTES` as `"list_files"` so `GET /files` serves it.
2. Close the work out in the record `plans/open/003-files-listing.md`: set its
   `status: done` and put a line into its `## State` section saying what changed.

Keep `get_file` working, and don't change anything else. The suite is
`python3 -m unittest discover -s tests`.
