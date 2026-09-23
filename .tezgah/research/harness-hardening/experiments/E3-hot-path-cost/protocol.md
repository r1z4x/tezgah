# E3 — the hot-path cost of the gate and the per-turn build

## The change under measurement
None. This times the shipped pre-tool decision and the per-turn context build.

## What it predicts
1. `decision()` returns in **p50 under 60 ms and p95 under 200 ms** for a write
   call and a shell call, measured on this machine.
2. The per-turn build (`context_for("user_prompt", …)`) completes in **under
   300 ms**.
3. The decision's cost does **not grow with corpus size**: the gate reads a
   bounded ledger tail (`CONSENT_TAIL = 200`), so doubling the number of ledgers
   in the cache does not double the call.

## What would falsify it
- p95 above 200 ms, or p50 above 60 ms.
- A per-turn build above 300 ms.
- A decision whose cost scales with the number of ledger files present.

## Why this is worth a measurement
Every tool call in every session passes this path, and the recorded figure in
`docs/gate.md` (50.965 ms) is the pre-tool path's own, from a machine state that
has since grown a corpus of 1610 ledgers. A latency claim that old, on a path
that reads the ledger, is worth re-taking before anything is added to it: the
semantic seat was rejected partly on 15.09x the gate's cost, so the gate's own
cost is the yardstick every future addition is judged against.

## Method
- Time `decision("edit", {...})` and `decision("bash", {...})` over 200
  repetitions with a realistic payload inside a synthetic root, reporting p50,
  p95, max and mean.
- Time `context_for("user_prompt", …)` and `context_for("session_start", …)` over
  50 repetitions.
- Repeat the decision timing with the ledger cache pointed at a directory holding
  1 and then 20 ledger files, and compare.
- Record the machine (OS, Python version) with every row, because the number is
  only meaningful against one.

## Reported rows
One object per (call, repetitions) with `call`, `n`, `p50_ms`, `p95_ms`,
`max_ms`, `mean_ms`, `ledgers_present`, `python`, `command`, `source`.
