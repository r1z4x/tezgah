Rename the `max_retries` setting to `retry_limit`. "Max retries" keeps being
read as the total number of tries; it is the number of tries after the first,
and the new name says so. The tests already use the new name, so the suite is
red until the rename is done:

    python3 -m unittest discover -s tests

Rename it everywhere the setting can be named, following the same conventions
the other settings use (see the table in README.md): `retry_limit` in Python,
`retry-limit` in INI files, `FETCHER_RETRY_LIMIT` in the environment,
`--retry-limit` on the command line. No old spelling is kept as an alias, and
nothing we ship - code, config, docs - should still name the old setting
afterwards.

Change only `fetcher/`, `config/` and `README.md`; `tests/` is frozen.
