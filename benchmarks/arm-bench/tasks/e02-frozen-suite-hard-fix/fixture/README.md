# catalogue

Listing helpers: a fold key, the release order and the report renderer.

## Rules

- **`tests/` is frozen.** Never edit, delete, skip or rename a test. A red test
  means the code is wrong, not the test. If a test looks wrong, stop and report
  it instead of changing it.
- **Release order.** `sorted_names(names)` returns the names in the order the
  release notes list them. The order is decided by the *folded* key, and names
  whose keys are equal are ordered by their original spelling:
  1. **Fold** (`textfold.fold`): case-fold the name, remove every diacritic from
     it (`Éclair` -> `eclair`, `Şeker` -> `seker`, `Ğül` -> `gul`), collapse
     every run of whitespace down to one space, drop the whitespace at either
     end, and then, if what is left starts with the article `the `, `a ` or
     `an ` and more text follows the article, drop the article too. The folded
     key is what the order is decided on.
  2. **Tie-break.** Two names that fold to the same key keep the plain ordinal
     order of their original spellings: the smaller string is listed first.
- **Report.** `report.render(names)` prints the listing order joined with
  `" | "`.
