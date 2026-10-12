Add a `--since` filter to the notes command line. Six items; all six are part of
the request.

1. Add `since(notes, day)` to `notes/store.py`: the notes created on or after
   `day` (a `datetime.date`), in input order.
2. `python3 -m notes.cli FILE list --since YYYY-MM-DD` lists only those notes.
3. `search` takes `--since` as well and searches only those notes.
4. A `--since` value that is not a valid `YYYY-MM-DD` date (`2024-13-01`,
   `yesterday`) is a usage error: exit status 2 with argparse's usage message, no
   traceback.
5. `export` takes `--since` too, and its header line counts the notes it exported.
6. `list` and `search` print `(no notes)` when there is nothing to list, instead of
   an empty line.

`notes.json` is a sample file to try it on. Change only files under `notes/`.
`python3 -m unittest discover -s tests` must still pass.
