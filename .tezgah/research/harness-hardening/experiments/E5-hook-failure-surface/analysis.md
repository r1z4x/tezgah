# E5 analysis — the hook failure surface

## What was read
`results.jsonl` (16 rows). Fifteen are the read-only map (each naming its lines);
one is a measurement taken here.

Rows here are scope: real (protocol.md: "Read each entry point and the core
modules it calls"; the one measurement reads this machine's own ledger corpus).

## Against the predictions

| # | prediction | result | verdict |
|---|---|---|---|
| 1 | every entry point guards the core call, except maybe one | **none of the eight guards it**; only the stdin decode is guarded | **missed, in the worse direction** |
| 2 | the hot-path network calls have a timeout and a total failure mode | one call (`judge.ask`), 8.0 s × 2 attempts, failures total — but urllib's timeout is per socket op, not a wall clock | **holds with a caveat the repo knows** |
| 3 | at least one unbounded read sits on the hot path | **four**, and one of them (`turn_channel`) reads the whole ledger on every effectful call | **holds** |

## What the numbers say
- The guard is per host, not per hook. Claude, Codex and Cursor lose one envelope
  and log a hook error; **omp converts one crash or one 10 s timeout into a
  session-wide disable** — gate, ledger and status line off for the rest of the
  session, with the model told not to fix it. That is a stability property with a
  much larger blast radius than the failure that causes it, and it is the one
  place where the design's own sentence ("a hook that raises takes a session
  down") is implemented as policy rather than avoided.
- **opencode is the opposite failure**: `try/catch` everywhere (so a crash fails
  open) but **no timeout on any awaited `spawn("python3", …)`**, so one hung core
  call blocks a tool call indefinitely. Two hosts, two opposite extremes.
- The unbounded read is real but small today: the largest ledger on this machine
  is 199,368 B / 925 rows and a full read+parse of it is **2.928 ms** (0.300 ms
  raw). Scanning **all 1613 ledgers** (7.3 MB) is 68.3 ms. So the growth is
  linear in session length and the present cost is ~7x one gate decision
  (0.43 ms) per effectful call — a latent cost, not a present bottleneck, and the
  cheapest thing to bound since the gate's own ledger read is already bounded.

## What this does not show
- Whether any of these paths has ever actually raised in the field. The map is
  static and no ledger row records a hook crash; the corpus's `unknown` rows
  (101) are unclassified calls, not failures.
- The cost of `stop_reason`'s whole-ledger read on a long session. It is the same
  shape as `turn_channel`'s and would be measured the same way.
