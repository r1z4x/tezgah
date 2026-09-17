# E4 protocol - note on pre-registration

**This block lives under `to_human/blocks/` rather than `experiments/`, and that
placement is the record.** `tezgah-research check` requires every directory under
`experiments/` to carry a `protocol.md` committed before its `results.jsonl`.
This block has no such protocol: the run was registered as an orx node (question,
arms, task set, repeat count, endpoints - all in commit `0ee1036` and the node
description), but the file below was written afterwards. Rather than commit it
first to satisfy the checker, it is filed here as a run record.

**This file was written after the run.** It is committed together with the
results in one commit, and it exists so a reader can see exactly what was
registered before the run and what was not. It is not a prediction made in
advance, and it must not be read as one.

## What was registered before the run

| what | where | committed |
|---|---|---|
| the question | orx node description: "does the gate change the work?" | yes, at node creation (`orx create-experiment`) |
| the four arms | `benchmarks/arm-bench/arms.json` (omp+tezgah, orx-verify-off, orx-gate-off, omp-bare) | yes, commit `0ee1036` |
| the task set | `benchmarks/arm-bench/orx-tasks.txt` (e01, e02, e03) | yes, commit `0ee1036` |
| the repeat count | `orx_block.py` `REPEATS = 5` | yes, commit `0ee1036` |
| the endpoints | orx node description: "hidden-check pass rate and CPS" | yes, at node creation |
| how the arms differ | `arms.json` `verification` field + the kill-switch files themselves | yes, commit `0ee1036` |

## What was NOT registered

- **No numeric prediction.** I did not write down an expected pass rate or an
  expected direction before launching, so this run cannot confirm or refute a
  stated number. It can only report what happened.
- **No pilot of the three new tasks.** The tasks were verified to discriminate a
  fixture from a gold tree (`bench.py selftest`), which is not the same as
  verifying that they discriminate *arms*. E4's result shows the cost of that
  omission.

## Registered design intent, for the record

The three tasks were built to be AP-Acc shaped: e01 (a one-line fix that breaks a
neighbouring case the visible suite covers only if it is run), e02 (a red test
that is cheap to silence and expensive to fix), e03 (a three-item request whose
third item the visible suite cannot see). The intended discriminator per task was
named in the authoring brief: e01 against the Stop rule, e02 against the
PreToolUse gate, e03 against the completion rule.

## Falsification criterion, stated now

An effect is demonstrated only if the arms' Wilson 95% intervals separate, or if
a per-task paired comparison separates at n=5. Overlapping intervals at n=15 per
arm mean the block did not measure an effect; that is a statement about the
instrument, not about the controls.

## Reproduce

```sh
orx exp run 326eb400-9e41-4d11-a920-ebc98127fea4 --backend local
python3 .tezgah/research/agent-failure-controls/experiments/E4-mechanical-off-effect/report.py \
  .tezgah/research/agent-failure-controls/experiments/E4-mechanical-off-effect
```

The paths in that command are the ones the run used; the block was filed
under `to_human/blocks/` afterwards (bd68a36), which is also where its
results live. The command is kept as the record, not rewritten.

