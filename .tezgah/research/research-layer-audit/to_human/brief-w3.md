# W3 brief — the remaining unpinned behaviours (wave 2, after W1 stops)

You are the sole writer of `tests/test_research.py` in this wave. W1 has finished
with it; read the file as it now stands before adding anything, and do not change
production code except where a test exposes a real bug - in that case stop and
report it instead of editing a file you do not own.

Read first:
`/Users/rizax/Projects/tezgah/.tezgah/research/research-layer-audit/to_human/implementation-spec.md`
and `.../research-layer-audit/experiments/E6-coverage-gap-list/results.jsonl` -
the 25 rows are the list, each with the code `path:line`, the doc phrase that
promises the behaviour, and why the existing suite cannot see a regression.

## What to build

Pins for the rows of E6 that are **not** covered by W1's new tests (W1 owns the
rows that its own change created or made reachable). At minimum:

- **CLI refusal edges**: `status` with extra arguments (row 12); `repo_root`
  outside a git repository (row 13); `init`'s slug normalization (row 14);
  non-UTF-8 stdin on `claim` (row 15); an unwritable or vanishing line during
  `claim` (row 16); `init`'s printed next-steps and kill-switch line (row 17);
  `append_claim` raising `FileNotFoundError` for a missing line (row 18).
- **Degradation paths**: the no-fcntl refusal by patching `tr.fcntl = None` in
  process (row 2 - note the two existing lock tests `skipTest` when fcntl is
  absent, so this row needs the patched path, not a skip); `is_ancestor`
  returning `None` (row 5); a machine without git via a PATH shim (row 6);
  the last-byte repair when the file already ends in a newline (row 19).
- **`_resolves` forgiveness**: a glob proof and a `ref:path` proof (row 3), and
  `_cited` with a numeric or boolean proof (row 4).
- **The session note**: `post_compact` (row 7), the command hint (row 8), two
  broken lines reported in the right order (row 9).
- **The budget drop order** (row 10, `hooks/tezgah_context.py:689-691`): with a
  patched `CONTEXT_BUDGET`, assert that a drop happens and in which order. This
  is the one row that decides what a long turn loses first - if the assertion
  cannot be made honest, report that instead of writing a tautology.
- **`summary()` vs `failing()`** (row 25): pin the session note's actual call so
  the docstring cannot drift again.

Use `tests/support.py` helpers (`TempHome`, `run`, `run_json`, `PROBE_CONTEXT`,
the `base_env` shim pattern for a missing binary) and the fixtures already in
`tests/test_research.py`. Style: stdlib `unittest`, one behaviour per test, a
docstring naming the failure the test answers - the file already does this.

## Hard constraints

- Every new test must fail when the branch it pins is deleted. Where you can,
  verify that on a scratch copy of the module (never by editing the real file and
  reverting); where you cannot, say so explicitly in the report.
- No test may assert on source text, a docstring, or an implementation detail; the
  target is the observable contract (a return value, an exit code, a written
  file, a printed line the user reads).
- Do not run the full suite, ruff or compileall. Run
  `python3 -m unittest tests.test_research` only.
- Do not commit; do not touch anything outside `tests/test_research.py`.
- No attribution line, no model/vendor name anywhere.

## Acceptance (report with the command and its observed output)

1. `python3 -m unittest tests.test_research` -> count and `OK`.
2. A table: E6 row -> test name -> how you showed it fails before (or why you
   could not).
3. Any row you deliberately did not pin, with the reason (a behaviour that is not
   really promised anywhere is not a gap - say so and drop it).
