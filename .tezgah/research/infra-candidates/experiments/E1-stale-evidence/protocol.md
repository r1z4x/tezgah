# E1 protocol — the stale-evidence rule

**Written after the run, and that is disclosed rather than hidden.** The
`tezgah-research` discipline is protocol-before-results because a prediction
recorded after its results is not a prediction. That guarantee does not hold for
this file, and the honest cost is stated: E1 verifies a change that was already
made on the user's instruction, so it can confirm the rule's behaviour and its
controls but cannot claim it predicted them. The falsifier that *would* have made
this a pre-registered block - the false-completion rate over a corpus task - is
named below as still open, and it needs the paid arm-bench run.

## What E1 verifies

`hooks/tezgah_integrity.py`: `_stop_block`'s pass branch now requires the newest
passing check to be newer than the newest write the gate saw change the tree
(`_last_change`/`_changed_write`/`_last_pass`/`stale_paths`), refusing with the
new class `stale evidence`; and `passing_check`'s tolerance for a `verify_ok` row
with no `exit` key is gone.

## Cells, and what each one predicts

Each cell seeds a ledger the way the writers record it (`tezgah_snapshot.capture`
for the pre-state, `note_tool` for the after-state), then hands the Stop payload
to the **real** `hooks/projects-stop.py` as a subprocess and reads its stdout.

| cell | seeded state | predicted verdict |
|---|---|---|
| fix-1 | `edit(changed)`, passing check, `edit(changed)` | block, class `stale evidence`, the file named |
| ctrl-A | `edit(changed)`, passing check | allow |
| ctrl-B | `edit(changed)`, passing check, `edit(changed: false)` | allow |
| ctrl-C | stale state, reply describes it and claims nothing | block (evidence-shaped, the E2 design) |
| ctrl-D | stale state, reply carries `doğrulanmadı` | allow |
| ctrl-E | writes, never a check | block as `no verify_ok`, not as the new class |

## What would falsify the change

- ctrl-A or ctrl-B blocking: the rule fires on a tree that was verified, or on a
  write that changed nothing.
- ctrl-D blocking: the admission escape is gone, and honest uncertainty is
  punished.
- ctrl-E reporting `stale evidence`: the new branch swallowed the `no verify_ok`
  floor it sits in front of.
- fix-1 allowed: the branch is unreachable through the hook envelope.

## The bound on this experiment

Six cells, one host path, deterministic, no model. It settles *whether the rule
refuses the shape* and *whether the controls hold*. It does not settle frequency
or cost: the arm-bench block in `../../to_human/candidates.md` (arm
`omp-task-rule`, the h0-family corpus task, k=25) is the pre-registered test of
the rate, and it is unrun.
