# E3 analysis — two stores, no join

Raw: `raw/run.txt`.

## Result

| cell | measured | predicted |
|---|---|---|
| A | one registered project (`tezgah-harness-research`), 12 nodes, 11 runs, run command `bash benchmarks/arm-bench/orx-run.sh` | one project - **hit** |
| A2/B | that script is gone; `benchmarks/` is untracked and absent at HEAD, removed by `5af240b` | absent - **hit** |
| C | 0 of 75 claims cite an orx run or experiment id | 0 - **hit** |
| D | 0 places in `hooks/`, `bin/`, `hosts/` execute orx and consume its output | 0 - **hit** |

**CONFIRMATORY**, all four cells.

## What it means

The research rule tells every session to drive execution through orx and to keep
the auditable line in `.tezgah/research/<slug>/`. Measured: the two have no
mechanical connection. The workspace cannot name a run (nothing in `results.jsonl`,
`claims.jsonl` or `state.json` has a field for one, and no token type is
recognised by `_cited`), and no tezgah code reads orx - it checks that the binary
exists, tells the model about it, renders its skill shims at install time, and
stops there. The `research` status mark is measured on the same surface: it lights
from the session ledger when a shell command ran `orx`, never from the line.

So the evidence chain crosses a human: the model runs orx, reads a log, writes a
number into `results.jsonl`, and the only record that the number came from run
`317fa1ea…` is the trustworthiness of that transcription. That is exactly the
link the evidence literature calls a receipt, and the workspace has none.

Cell B is a second, operational finding: the repository's registered project is
broken. Its run command names a script that the tree no longer holds, so the
tree cannot be resumed as registered - and nothing in tezgah reports that,
because the `research` mark and the session note never look at orx's state.

Rows here are scope: real (this repository, its registered orx project and its five pre-existing lines).
