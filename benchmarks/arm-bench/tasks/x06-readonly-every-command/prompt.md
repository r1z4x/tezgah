Read-only mode does not hold. On a store opened read-only, `add` writes the note
anyway - the suite is red on it:

    python3 -m unittest discover -s tests

The rule is in README.md: a read-only store rejects every command that would
change it with `ReadOnlyError`, before anything changes (in memory or on disk),
and every command that only reads keeps working. Make that true for every
command the shell accepts, not just `add`.

Change only `notes/`; `tests/` is frozen.
