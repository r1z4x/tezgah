# E13 analysis — three rules that fire on real artifacts and break nothing

Raw: `raw/check.txt`.

The default path still exits 0 over the six lines, and each new rule fired
somewhere real:

- the protocol rule names **five** brief-shaped protocols (all five in this line,
  each one a brief handed to a read-only agent rather than a prediction), which is
  the honest reading of "a protocol must say what it predicts";
- the report rule names the two concluded lines with no `to_human/report.md` at
  all, and the existing review rule keeps naming the four concluded lines with no
  review;
- the tracking probe now prints the exact `git add -f <path>` for a pair that
  cannot be verified, which is what `git add` silently failing needed;
- `migrate` derives a row's `source` from the `id` the row already carries
  (judge-positioning) and reports what it cannot derive.

`--strict` exits 1 with 70 FAILs and none of the new classes entering as a FAIL on
the plain path - the back-compat constraint held, and the spec's amendment table is
what decided each class before the work started.

Rows here are scope: real (this repository's six lines and their artifacts).
