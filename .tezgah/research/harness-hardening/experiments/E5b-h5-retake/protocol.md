# E5b — H5 re-taken on today's tree (child of E5)

## Why this experiment exists
E5's map read the entry points and the hot-path reads on the tree it was taken on,
and H5 ("every hot-path operation is guarded and bounded") is recorded `refuted`
against that tree only: the guard at seven entry points, the opencode spawn
deadline and the turn-scoped reader all landed afterwards, and a close-out pass
deferred the re-take rather than judging it unnecessary (log.md row 27, the report's
limits section). This is the re-take E5's own protocol names as its child, with the
same instrument and the same scope.

## The change under measurement
None. A read-only map of every entry point and core module, re-read against the
current files, plus one in-process timer over `~/.cache/tezgah/evidence`.

## What it predicts
1. The `guarded` half now holds: every entry point's call into the core is wrapped
   in `hooks/tezgah_guard.safe`, and `hosts/opencode/plugins/tezgah.js` routes every
   awaited core spawn through one `collect` helper that carries a deadline.
2. The `bounded` half fails again at the operation E5 named: `stop_reason` and
   `changed_files` (`hooks/tezgah_integrity.py`) read the whole ledger rather than
   the turn's rows, so H5 stays refuted for today's tree - and the defect is the
   Stop path, not the entry points.
3. The other reads E5 listed keep the shape E5 gave them: `turn_channel` reads
   through `turn_rows`, while `used()` and `_hash_file` stay unbounded by
   construction.

## Falsification
This reading is falsified if any entry point's call into the core is unguarded, if
any awaited core spawn in the opencode plugin has no deadline, or if `stop_reason`
and `changed_files` already read the turn's rows instead of the whole ledger - in
which case H5's refutation does not survive the re-take at all.

## Why this is worth a measurement
H5 is the one hypothesis of this line whose verdict a reader would take as current,
and three of the four defects it names were fixed after the map landed: a refutation
left standing against a tree nobody runs is either a stale warning or a live one, and
only the re-take tells the two apart.

## Method
The same instrument as E5. Read each entry point and the core module behind each
hot-path operation, recording `guard`, `guard_effect`, `bounded` and the `path:line`
that decides it, every row labelled `verified-by-reading`; then one in-process timer
over this machine's own ledger corpus (`~/.cache/tezgah/evidence`) timing the
whole-ledger read `events` against the turn-scoped `turn_rows` on the largest ledger
present. No provider, no network, no cost.

## Reported rows
One row per operation: the eight entry points, the four reads E5 called unbounded,
the one network call, plus the timer's own row. Every row carries `source` and
`scope: real` - the entry points are this repository's own files and the timer reads
this machine's own ledger corpus.
