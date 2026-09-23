# E2 analysis — the order rule is live, and the prescribed layout is where it dies

Raw: `raw/run.txt` (cells A and B), `raw/cells-c-d.txt` (cells C and D).

## Result

| cell | layout | order rule |
|---|---|---|
| A | line tracked, protocol committed before results | **silent** - the rule passed |
| B | line never committed | warned, exit 0 |
| C | this repository's five lines, 7 experiments with results | warned, exit 0, 7 of 7 |
| D | `git check-ignore` on the prescribed path | `.gitignore:18:/.tezgah/` - ignored; 0 files under `.tezgah/` are tracked |

**CONFIRMATORY.** All four cells matched.

## What it means

The rule works - cell A proves it - and it is unreachable in the layout the
contract prescribes: `<repo>/.tezgah/research/<slug>/` is gitignored in this
repository, `git check-ignore` names the line, and every experiment that has
results in every existing line reports "the protocol order cannot be checked".
The layer's flagship guarantee - the one the skill calls "the temporal proof that
the prediction came first" - has therefore never been exercised for any line this
repository has ever run.

Two consequences worth separating:

- **A tracked line is a better line.** Cell A is the shape that makes the rule
  bite, and nothing in the CLI, the skill or the installer ever writes, suggests
  or scaffolds it. `init` prints "COMMIT it before the run" while every session
  then works in a directory git cannot see; the instruction and the layout
  contradict each other.
- **The warning is not a nudge.** At 7 warnings on 5 lines and exit 0, a session
  reads a clean `check` while the strongest rule in the file never ran. E1's
  result makes the same point from the other side: the rules that do not depend
  on git are not checked either.

Rows here are scope: fixture for cells A, B and the replay (protocol.md: "temp repo, `.tezgah/research/q` tracked"; "temp repo, protocol.md and results.jsonl present but uncommitted") and real for cells C and D (this repository and its `.gitignore`).
