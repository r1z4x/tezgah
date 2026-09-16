Audit the package in this repository. Report every call site of these three
functions: `calc_total`, `apply_discount`, `parse_quantity`.

Write `ANSWER.md` with exactly one line per call site, in any order:

    <path>:<line> <enclosing> :: <callee>(<arguments>)

- `<path>` is relative to the repository root, e.g. `inventory/report.py`
- `<line>` is the 1-based line number the call expression starts on
- `<enclosing>` is the function that contains the call, `Class.method` for a
  method, and `module` for a call at module level
- `<callee>` is the called name; `<arguments>` is the argument list written the
  way the source spells it, with whitespace collapsed

Rules that decide what counts:

- one entry per call expression, not one per called name: a line that calls two
  of these functions carries two entries;
- an import line is not a call site;
- a call nested inside another call is its own entry, on the same line as the
  call that encloses it;
- a file that only calls a function which in turn calls one of these three does
  not appear.

Do not change any file. `ANSWER.md` is the only file you may write.

Then answer in prose: how many call sites you found, and which ones are easy to
miss.
