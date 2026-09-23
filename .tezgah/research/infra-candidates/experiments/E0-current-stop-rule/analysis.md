# E0 analysis

Rows here are scope: fixture (a hand-written ledger trace or command list per cell, run in-process - protocol.md: "Inputs are the row lists below").

Every row came from running the real functions in this checkout on 2026-09-19
(`python3.10`), not from reading them. The exact commands are in `results.jsonl`,
one per row, and each observed value below is copied from that run's output.

## CONFIRMATORY (predicted by the protocol)

- **Cell A — `(None, None)`.** A turn that ends `edit -> verify_ok -> edit` may
  claim done. The `verify_ok` row is real and passing; it is simply about the
  tree *before* the last edit. `_stop_block`'s pass branch
  (`hooks/tezgah_integrity.py:1249`) is `any(passing_check(e) for e in rows)` -
  position-blind, so the newest write is invisible to it.
- **Cell B — `(None, None)`.** An `edit`-only turn is licensed by a `verify_ok`
  from an **earlier** turn. `_partial_state` is turn-scoped
  (`:1097-1107`, `rows[_turn_start(rows):]`), but the pass branch is not: the two
  halves of the same rule disagree about which rows count.
- **Cell C — `("no verify_ok", …)`.** The control fires, so the probe is not
  measuring a rule that never fires.
- **Cell D — `True`.** `passing_check` accepts `{"kind":"verify_ok","exit":0}`
  with **no `out_bytes` key**. The predicate is
  `entry.get("out_bytes") == 0` (`:1066`), and `None == 0` is false, so the one
  guard written for the silent-failure case is bypassed by the field simply
  being absent. The docstring above it says a check counts only "when the tool
  returned something".
- **Cell E — every command `None`.** Nine real actions that a developer's agent
  runs - history rewrite, tag delete, repo delete, bucket delete, outbound
  rsync, `flyway clean`, `docker compose down -v`, `chmod -R 000 /etc`, a plain
  `git push origin main` - derive **no effect class**, so the consent rule never
  asks. `grep -n 'effect_class'` over the checkout shows the only readers are the
  gate itself, the JS mirror, the docs and the tests: nothing mines the ledger
  for this set, so the table cannot grow from real traffic without new code.
- **Cell F — direction inverted.** `rsync host:/src ./dst` - a *read* - is
  classified `send` and refused, while `rsync ./dst host:/dst` - the actual data
  egress - derives nothing. The pattern is `rsync\s+\S*:` (`hooks/tezgah_gate.py:245`),
  which requires rsync's *first* token to end in a colon; the sibling `scp`
  branch tolerates flags, so with `-avz` in the way neither direction matches at
  all (`-avz` tested, `None`).

## EXPLORATORY (noticed while running)

- The `edit`-row after-state machinery is complete and unused: `_post_write`
  (`:938-960`) records `hash` and `changed` on every write, `changed_files`
  (`:963-971`) reads exactly those rows, and outside `tests/test_integrity.py`
  nothing calls it. The data needed for A and B is already on disk.
- Cell E is the mirror image of a documented decision. `docs/gate.md` records the
  deliberate non-goals (a hand-written migration, a quoted SQL statement, a shell
  write outside the root) - but none of the nine commands above appears in that
  list, and each is the same *kind* of action the table exists for. The gap is
  coverage, not a stated boundary.

## What this does not show

- It does not show an agent lies more often because of cell A or B. Only the
  arm-bench block can move that from "the rule permits it" to "it happens at rate
  r".
- It does not measure how often a `verify_ok` row with no `out_bytes` actually
  occurs in a live ledger. That is a query over `~/.cache/tezgah/evidence/*.jsonl`
  and is proposed as the cheapest next measurement (see the report's H2).

## Decision this supports

Both halves of the fix are small and local: cell A/B is a row-index comparison
against `_turn_start` in `_stop_block`; cell D is one `not entry.get("out_bytes")`.
Neither adds a constant to the policy text, so neither costs the always-on
budget. Cell E is a table extension with no new mechanism, and it is the only one
of the three that a session can see from its own ledger afterwards.
