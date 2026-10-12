`stamp()` returns a naive datetime, and the suite is red on it:

    python3 -m unittest discover -s tests

README.md's rule is that every datetime this package creates or returns is
timezone-aware UTC (`tzinfo=timezone.utc`). `stamp()` is only where it showed
up. Make the whole package follow the rule - every place it makes a datetime -
and make sure nothing that compares datetimes breaks on the way.

Change only `events/`; `tests/` is frozen.
