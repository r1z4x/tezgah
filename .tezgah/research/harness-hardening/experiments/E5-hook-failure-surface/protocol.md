# E5 — the hook failure surface (discovery)

## The change under measurement
None. A read-only map of where a hot-path hook can raise or stall a session.

## What it predicts
1. Every entry point wraps the core call in a guard, so a core failure degrades a
   feature rather than killing the turn - **except** for at least one path, which
   is the finding if it exists.
2. The network calls on the hot path are the judgement seam's, and each has a
   timeout and a total failure mode (a value, not an exception).
3. At least one unbounded read or scan sits on the hot path (a ledger fold, a
   directory listing, a `plan` scan) - the gate reads a bounded tail, but the
   context builder's live-state half reads the repository.

## What would falsify it
- Every hot-path operation is guarded and bounded, with no unbounded read.

## Why this is worth a measurement
A harness that runs on every turn in six hosts is only as stable as its worst
unguarded path, and the cost of one is not a degraded feature but a broken
session. The layer's design says the same in one line: "a hook that raises takes a
session down". Nothing in the repository counts those paths.

## Method
Read each entry point and the core modules it calls; for every file read/write,
`json.loads`, `subprocess.run`, `os.*` and network call on the hot path, record
whether a failure becomes a value or can escape, with `path:line`. Label each
finding `verified-by-reading` or `inferred`.

## Reported rows
One row per operation: `op`, `file`, `guard`, `guard_effect`, `bounded`,
`verification`, `source`. Plus one worst-case row.
