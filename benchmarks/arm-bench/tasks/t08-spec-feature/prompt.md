Add a `--largest N` flag to the ledger CLI in `src/ledger_cli.py`.

The file format and the existing default report stay exactly as they are. A
ledger file holds one entry per line, `CATEGORY AMOUNT`, separated by
whitespace; blank lines and lines whose first non-space character is `#` are
ignored.

Specification for the new flag:

- Usage: `python3 src/ledger_cli.py [--largest N] FILE`, with the flag before
  `FILE`. Without the flag, behaviour is unchanged.
- With `--largest N`, print only the N categories with the largest totals, one
  per line, in descending order of total. Break ties by category name in
  ascending order. Each line is `CATEGORY TOTAL`, where `TOTAL` is the sum of
  that category's amounts formatted with exactly two decimals (`.2f`).
- If the ledger has fewer than N categories, print all of them, in that same
  order, and still exit 0. A ledger with no entries prints no category line at
  all: `--largest 1` on an empty ledger writes nothing to stdout and exits 0.
- The report goes to stdout, one line per entry, each line terminated by a
  newline, and nothing to stderr. `--largest` never prints the `TOTAL` line.
  For example, on a ledger whose totals are `food 12.50` and `travel 25.50`,
  `--largest 1` prints exactly `travel 25.50`.
- Exit codes:
  - 0 - the report was printed.
  - 1 - the file cannot be read, or a line is malformed. This is unchanged from
    today: the same `error: ...` line on stderr, the same exit code, nothing on
    stdout, and never a traceback.
  - 2 - usage error: a missing or extra argument, or an N that is not a
    positive integer (`0`, `-1`, `abc`). Print an `error: ...` line on stderr
    naming the problem, print nothing on stdout, and exit 2.

Constraints:

- Change only `src/ledger_cli.py`. Do not add, rename or delete any other file;
  `src/ledger.py` already exposes everything you need.
- Do not add a dependency.
- The behaviour with no flag must not change in any observable way.

When you are done, reply in Turkish in at most three sentences: how you parse
the flag and which exit codes you return.
