# Host refresh — what it found beyond the refresh itself

Written 2026-09-19, from the refresh run against `d2f0cf4`. The refresh worked: 8
Claude plugin copies rewritten byte-equal to HEAD, omp's managed `RULES.md` and
the generated opencode contract both carry the new clause, and the CLI links still
resolve (`~/.config/tezgah/bin/tezgah-status --counters --all` answered). Two
findings came out of it that are not about the refresh, and both are class (c):
nobody has named them.

## R1 — `--install --hosts <one host>` silently deletes the other hosts' generated agents

- evidence: `bin/tezgah-setup:352` writes the `hosts` key from the `--hosts`
  value, and `hooks/tezgah_agents.py:84` reads that key to decide which hosts get
  the per-repo agent files. Measured: after `--install --no-deps --hosts omp`,
  `bin/tezgah-agents --json` returned `{}` - opencode's generated agents and the
  `.claude`/`.cursor` agent files had been removed, and the install still reported
  success.
- why it matters: the flag is documented as "comma-separated subset of ... to
  arm", so a maintainer refreshing one host's file is not told that the operation
  also *disarms* the others' agent generation. The failure is silent and
  outward-facing: the files are gone from the user's other hosts.
- measurable: yes, k=1 - install with a single-host `--hosts`, then read
  `bin/tezgah-agents --json` and the host dirs. Today: empty.
- sketch: either keep the previous `hosts` list when `--hosts` narrows it and the
  run is not a fresh install, or make the removal it implies an explicit line in
  the report. The first is smaller and matches "an install does not silently
  disarm what it does not mention".
- repaired in this run: the previous `config.json` was written back with tezgah's
  own writer and verified byte-identical, so no user state was left changed.
- status: open. It is a candidate, not a fix, because it needs the maintainer's
  call on which of the two shapes is right.

## R2 — the omp report row cannot see a stale managed file

- evidence: `bin/tezgah-setup:1921` - the omp row checks for `tezgah:start` and
  `Ponytail` in `~/.omp/agent/RULES.md`. Both were present in the stale file, so
  the row read `ok` while the file still carried the pre-change contract.
- why it matters: a report row is the installer's own claim about what is armed,
  and this one is satisfied by a file whose *content* is from an older contract.
  The class is the same one the status-line work just closed elsewhere: a surface
  that reports a state it did not check.
- measurable: yes, k=1 - write a `RULES.md` with the two markers and an old body,
  run `--report`, observe `ok`.
- sketch: check a content hash of the generated block against the generator's
  current text, the way `plugin_copy_current()` already does for the plugin copy,
  instead of two substrings.

## What this does not change

- The refresh itself is verified: the live copy is the 0.9.0 tree, all 8 copies
  compare byte-equal through tezgah's own `plugin_copy_current()`, and the new
  markers are present in the plugin copy, `RULES.md`, and the opencode contract.
- No repo file was written by the refresh; the checkout was clean at `d2f0cf4`
  before and after.
