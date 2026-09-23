# E7 analysis — the implementation's acceptance, item by item

Raw: `raw-results.json` (the runner's own dump), `results.jsonl` (one row per
cell). Protocol frozen before the writers started.

## Result

**29 of 29 cells passed**, including both gate cells:

- `bin/tezgah-research check` (no flags) exits 0 over all six lines in this
  repository (`research: 6 line(s) ok`).
- `bin/tezgah-research check --strict` exits 1 here - the unverifiable class is
  not empty, which is the control that the new flag is doing something.

Per item: I1 4 cells, I2 3, I3 4, I4 5, I5 3, I6 4, I7 3, I8 1, gate 2.

## Three corrections to my own harness, kept in the record

The first run of this runner was 21 of 25, and none of the four failures was a
product defect:

1. **Two cells did not isolate their rule.** They asserted the *first* line of
   `check`'s output, and an unrelated evaluation warning came first - the cells
   would have passed for the wrong reason had the rule been absent. Fixed by a
   `locked()` helper that writes a valid `state.json` before each cell and by
   asserting on the message anywhere in the output.
2. **One cell used the wrong invocation.** `python3 -m unittest tests.test_research`
   cannot work - `tests/` has no `__init__.py`, which is why the repository's own
   docs use `discover -s tests`. (The same brief error reached W2, which found and
   reported it.) The cell now uses the discover form.
3. **One class assertion contradicted a recorded amendment.** I4 expected a
   missing `source` to be a `FAIL`; the writers landed it as warn + strict-FAIL,
   with the measurement that forced it (71 existing rows carry no source and no
   rule may invent one). The spec's amendment table now records it and the cell
   asserts the landed class.

## What this does and does not prove

It proves each item's acceptance sentence, run by a runner written from the spec
before the code existed - not from the code. It does not prove the rules are
*wisely* chosen, and it does not prove the six lines are otherwise unbroken: that
is the full test suite's job, run once at the end of the session.

One cell is weaker than it reads: `I8` asserts that the research suite is green,
not that each new test dies when its behaviour is removed. The mutation evidence
for that is the writers' own runs - 12 mutations, 12 killed for the module tests,
and 5 mutation/drop demonstrations for the three coverage pins - and the parent
did not re-run those mutations independently. That limit is stated in the report
rather than papered over.

Rows here are scope: fixture for items I1-I6 (protocol.md: "on throwaway repositories") and real for I7, I8 and both gate cells (this repository and its six lines).
