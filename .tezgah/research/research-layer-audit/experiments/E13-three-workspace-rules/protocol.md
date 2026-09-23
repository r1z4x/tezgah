# E13 protocol — the three new workspace rules, on the six lines

**Ordering disclosed.** These are the acceptance readings of rules a writer
delivered on the parent's spec; the readings were taken after the delivery and are
recorded here rather than predicted. What *was* decided before the work is the
class of each rule, in the spec's amendment table: a rule that would break one of
the six existing lines lands as the warn class, and `--strict` escalates it.

## Question

Do the three rules fire on real artifacts, and does the default path still pass all
six lines?

## Metric

- `bin/tezgah-research check` exit code over the six lines, and the count of the new
  warning classes per line;
- `check --strict` exit code;
- `migrate --dry-run` for the line whose rows carry a derivable source.

## Threshold

Exit 0 with the new classes present as warnings, and no *FAIL* of the new class on
the default path. A rule that fires nothing on six real lines, or one that fails
them, is the finding either way.

## What would falsify

- Any new-class FAIL on the plain path: the back-compat constraint is broken.
- No protocol-prediction warning anywhere although only 17 protocols exist: the
  marker is too generous, which is the other way a rule can be a no-op.
- `migrate` reporting a source it invented rather than derived: the fabricated-
  provenance failure, and the row it came from would show it.
