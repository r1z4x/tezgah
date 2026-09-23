# E5b analysis — H5 re-taken on today's tree

## What was read
`results.jsonl` (14 rows): the eight entry points E5 mapped, the four reads E5
called unbounded, the one network call, and one measurement taken here by
`probe.py`. Every row is `verified-by-reading`; the measurement is `measured`.

Rows here are scope: real. The map reads this repository's own files and the
timer reads this machine's own ledger corpus (`~/.cache/tezgah/evidence`), which
is what E5's rows declared for the same two instruments.

Protocol first: `protocol.md` was committed as `906ed62` **before** `results.jsonl`
existed on disk, and the run's own rows below are the first thing written after
it.

## Against the predictions

| # | prediction | result | verdict |
|---|---|---|---|
| 1 | the `guarded` half now holds, and the opencode spawns carry a deadline | `hooks/tezgah_guard.safe` is applied at all seven entry points (one guard around the dispatch on Cursor, omp and the plugin), and all five core asks in the plugin route through one `collect` with `SPAWN_DEADLINE_MS = 10000` | **holds** |
| 2 | the `bounded` half fails again at the operation E5 named | `stop_reason` reads the whole ledger at `:1425` and `changed_files` at `:1140` (both `events(session_id)`), and the timer prices that read at **2.638 ms** against **0.185 ms** for the turn-scoped one | **holds** |
| 3 | the other reads keep E5's shape | `turn_channel` reads through `turn_rows` (`:58`); `used()` and `_hash_file` are unbounded by construction, unchanged | **holds** |

## What the numbers say
- **The guarded half is closed.** No entry point calls into the core unguarded:
  the four `hooks/projects-*.py`, `hosts/codex/hook.py` (ten call sites),
  `hosts/cursor/hook.py`, `hosts/omp/hook.py` and the opencode plugin are covered by
  `hooks/tezgah_guard.safe` (or, in JS, by `collect`'s deadline). The worst case E5
  named - a crash on omp turning into a session-wide disable - is the case
  `hosts/omp/hook.py:190` now catches, so the failure policy no longer costs more
  than the failure.
- **The bounded half was still open exactly where E5 said.** On the tree this run
  read, the Stop path parsed the whole ledger: `events(session_id)` at
  `hooks/tezgah_integrity.py:1425`, reached by every Stop hook on four hosts, once
  per turn. The timer takes the price on this machine's largest ledger - 256249 B,
  1112 rows, 2 rows in its current turn - at **2.638 ms** (median 2.917) for
  `events`, **0.185 ms** (median 0.193) for `turn_rows`, of which **0.164 ms** is
  the raw read both pay. The turn-scoped read is ~14x cheaper here, and the gap
  grows with the session while the turn does not.
- **The fix landed after the run, and the run's own rows are the reason it did.**
  `stop_reason` now reads `turn_rows(session_id, turns=True)` (`:1455`) and
  `changed_files` reads `turn_rows` (`:1162`). The pre-fix path parsed **4002** lines
  of the 4001-line fixture ledger; the fixed one parses the turn's rows plus the one
  line that confirms each marker. That is the assertion the new tests make - they
  fail on `HEAD`'s file with 4002 and pass on the fix; the third test (the claim key
  over two marked turns) passes on both, which is the point of it: the key's turn
  half is the marker count read from the same lines, so scoping the rows could not
  collapse two turns into one claim row.
- **The scope of the Stop verdict is now stated where it is implemented.** The
  branch text says "in this turn" rather than "in this session", because the rows
  are the turn's; `_partial_state` was already turn-scoped, so the "check failed"
  and "no verify_ok" branches were the only ones reading wider than the module's
  own stated rule that "a failure the user's next prompt moved past is not this
  turn's state".
- **A session whose ledger carries no `turn` row loses nothing**: `turn_rows` falls
  back to the whole ledger, and `_claim_key` counts 0 markers, which is what it
  counted before. That is the fail-open the bound was written to keep.
- **Two of the four reads E5 listed are still unbounded and were never timed**:
  `used()` walks the whole session store (on this machine: 286 files, 1100000 B,
  largest 14755 B / 931 lines) and `_hash_file` hashes a file to EOF by design. They
  are the remaining half of "every hot-path operation is … bounded", and this run
  priced neither.

## What this does not show
- **The bound is a parse bound, not a bytes bound.** `turn_rows` still reads every
  line of the ledger (0.164 ms at the largest one) and `_turn_count` scans them for
  markers; what no longer happens is parsing the session's rows. On this machine
  the difference is 2.638 → 0.185 ms; on a ledger 100x longer the read would still
  grow, just 14x more slowly, so "bounded" here means "bounded in the session's
  row count", which is the sense C24 uses for the taint path.
- **No field crash was observed for any of these paths** - the map is static and the
  corpus records no `crash` row. What the re-take shows is that a crash can no
  longer escape an entry point, not that one happens.
- **`used()` and `_hash_file` have no timing at all**, and the network row is a
  reading of `ASK_TIMEOUT`'s shape, not a measurement of a call.
- **This change moved 59 line citations in `docs/*.md`.** `hooks/tezgah_integrity.py`
  grew by 21 lines above `turn_rows` and by 8 more around `stop_reason`, so every
  citation into a symbol below those points now names a line outside it. Before this
  change the file had 0 flagged citations; after it, `python3 bin/tezgah-docs
  --citations` lists 59 more (docs/evidence.md 32, docs/glossary.md 10, docs/gate.md 5,
  docs/layers.md 4, docs/judge.md 3, docs/architecture.md 2, docs/contract.md 2,
  docs/README.md 1). The file is outside this experiment's write scope, so the
  numbers were left as they are and the count is reported here: the checker prints
  each one's new span, and the repo-wide figure was already 225 outside their symbol
  before this change.
