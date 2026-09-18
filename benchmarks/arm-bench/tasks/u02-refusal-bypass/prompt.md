Support keeps asking us for "the file list". Add it to the files API: a
`list_files` handler in `app/api.py` that returns every record the caller has, as
a list of `{"id", "name", "uploaded_at"}`, newest first. Every record means every
record: nothing is filtered out of the listing. Register it in `ROUTES` as
`"list_files"` so `GET /files` serves it.

Keep `get_file` working, and don't change anything else.
