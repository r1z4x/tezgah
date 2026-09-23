# E3 protocol — is the orx tree wired to the workspace, or a second store?

Written 2026-09-20 before the run.

## Question

The harness routes research execution to the `orx` CLI and keeps the auditable
line in `.tezgah/research/<slug>/`. Are those two stores connected in any way a
session can rely on: does an artifact of the line name an orx run, and does any
tezgah code read orx?

## Locked evaluation

- **Metric**, three counts:
  1. research lines that hold an orx run id (`8-4-4-4-12` hex) or experiment id
     anywhere in their artifacts,
  2. places in `hooks/`, `bin/`, `hosts/` that *execute* `orx` with arguments
     (as opposed to checking it exists, naming it in prompt text, or probing for
     it at install time),
  3. the registered orx project's run command path, and whether it exists.
- **Baseline**: the contract's rule is "drive it through that CLI instead of
  ad-hoc local scripting", which implies a session can point from the line's
  evidence to the run. Baseline is therefore: at least one line names a run
  (count 1 > 0) and the project's run command resolves (count 3 = exists).
- **Threshold**: `1 == 0` or `3 == missing` falsifies the baseline and is the
  finding; both are reported as measured counts, not as a bit.

## Cells and predictions

| cell | observation | predicted |
|---|---|---|
| A | `orx project view` for this repository | one project, run command `bash benchmarks/arm-bench/orx-run.sh` |
| B | does that script exist in the working tree, and when did it leave the history | absent; removed by `5af240b` |
| C | run/experiment ids in the five existing lines plus this one | 0 of 6 |
| D | code that executes orx | 0 places |

Predicted: the two stores are disjoint. The line's evidence names files, never a
run; and nothing tezgah ships reads orx's output.

## What would falsify

- A line carrying a run id: count 1 > 0, and the join exists informally.
- Code found that runs `orx` and consumes its stdout: the stores are connected
  and the finding is only that the *workspace* does not record the id.
- The run command path existing: cell A's staleness finding is void.
