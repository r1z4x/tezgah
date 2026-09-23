# E3 analysis — the hot-path cost of the gate and the per-turn build

## What was read
`results.jsonl` (20 rows): in-process timers at three corpus sizes, the real
subprocess cost, and `-X importtime`'s attribution.

Rows here are scope: fixture for the in-process timers (protocol.md: "inside a
synthetic root", its cache pointed at 1 and 20 generated ledger files) and real
for the process and import rows (the shipped code measured on this machine).

## Against the predictions

| # | prediction | result | verdict |
|---|---|---|---|
| 1 | `decision()` p50 < 60 ms, p95 < 200 ms | p50 **0.427 ms** (edit), 0.377 ms (bash); p95 0.549 / 1.052 | **holds by two orders of magnitude** |
| 2 | `context_for(user_prompt)` < 300 ms | p50 **1.324 ms** | **holds** |
| 3 | the decision does not grow with the corpus | p50 0.430 ms at 1 ledger, 0.430 ms at 20; the ledger *file* count moves nothing | **holds** |

## What the numbers say
- The rule cascade is free: **0.4 ms**, and adding a rule to it would be
  invisible against the rest of the call.
- **What a host pays is process start plus import: 61.0 ms p50 per gated call**
  (40 reps), against 20.0 ms for a bare interpreter. `import tezgah_gate` alone
  measures 61.4 ms, i.e. identical to the full probe process: the decision adds
  nothing measurable.
- The import pie (`-X importtime`, cumulative): `tezgah_gate` 41.2 ms of which
  its own parse 7.7 ms, `tezgah_integrity` 26.9 ms (own parse 7.7 ms),
  `tezgah_paths` 12.7 ms, `site` 8.3 ms, `tezgah_lang` 2.0 ms,
  `tezgah_snapshot` 1.3 ms.
- **`tezgah_paths` costs 12.7 ms and its own body costs 0.6 ms**: it pulls
  `sqlite3` (4.5 ms), `shutil` (3.9 ms) and `tempfile` (3.7 ms, which pulls
  `random` and `contextlib`) — for capabilities this call may never ask for
  (bin resolution, the temp fallback, the omp `agent.db` read). A control
  measured `import sqlite3` alone at +4.0 ms, so the three stdlib imports are
  ~12 ms of the 41 ms, and the four tezgah modules' own parse is ~16 ms.
- `bin/tezgah-context` — what opencode spawns per prompt — is **88.0 ms p50**,
  against `import tezgah_context` at 86.0 ms.

## What this does not show
- Any comparison against another machine or Python build; every number is
  3.10.14 on darwin-arm64, taken once.
- Whether the 61 ms matters to the user. Per gated call it is 0.5-1% of a model
  turn; it is the *sum* over a long session, and the fact that 12 of those ms buy
  nothing for the call in hand, that makes it the cheapest finding here.
