# E1 analysis

## Result

| arm | top-1 | input tokens | per query | latency | per-query latency |
|---|---|---|---|---|---|
| flat Choice over 98 entries | 14/14 = 1.000 | 51,614 | 3,687 | 11,587 ms | 828 ms |
| two-stage (6 stages, then that stage) | 14/14 = 1.000 | 32,098 | 2,293 | not recorded | - |

Measured cost: $0.002168 flat + $0.001348 two-stage = **$0.003516** for 42 live
calls, from the replies' own `usage` at the price `bin/tezgah-triage` prints
($0.042 / 1M input, $0 output).

## Against the predictions

- **P1 (flat top-1 <= 0.65) - REFUTED.** Flat answered 14/14.
- **P2 (two-stage >= 0.80 and >= flat) - half confirmed, half not.** It reached
  1.000, so the floor holds; the "better than flat" half is a tie, so this run
  gives no evidence that two stages is more accurate.
- **P3 (flat >= 3x the two-stage tokens) - REFUTED.** The measured ratio is
  **1.61x** (3,687 vs 2,293 tokens per query). Two stages are cheaper in tokens
  and cost one extra round trip (2 calls vs 1).
- **P4 (no `none` for an in-library query) - CONFIRMED.** No query in either arm
  came back `none`.

## Why the top-1 result is weak evidence, in the direction that matters

Both arms at 14/14 is a **ceiling**, and a ceiling is the wrong instrument for
P1: the query set was written by hand to be unambiguous, so it cannot show where
the flat arm would fail. What this run does establish is bounded and worth
stating exactly:

- The primitive **can** carry a 98-option Choice: the API accepted 98 criteria,
  the reply came back with a single `choice`, and every answer was the label.
- The two-stage shape **buys no accuracy** at this size and saves 1,394 tokens
  per query for one extra round trip - at $0.042/1M that is $0.00006, which is
  not a reason to add a second call or a second code path.
- P1 remains **open** as written, because the instrument cannot test it. A
  falsifying set would need queries whose correct entry is separated from a
  plausible neighbour by something the option clause does not carry - that is a
  later round, and it is named in the open questions rather than claimed here.

## Lesson

A hand-written unambiguous query set measures the ceiling, not the edge. Writing
the falsifier as a floor (0.65) was right; writing the *set* so every item sits
far from its nearest neighbour was the mistake, and it is the same shape as the
skill-routing measurement in `.tezgah/research/typesafe-cost`, where the
independent chooser was at 0 of 20 wrong and the arm had no headroom either.
Rows here are scope: fixture (protocol.md: "14 queries written by hand from skills/ai-research/index/*.md").
