# E1b analysis

## Result

| query | flat | stage | two-stage |
|---|---|---|---|
| N01 "Set up a Kafka cluster for streaming telemetry." | `none` | `none` | `none` |
| N02 "Design a Postgres schema for multi-tenant billing." | `none` | `none` | `none` |
| N03 "Build a React dashboard for my metrics." | `none` | `none` | `none` |
| N04 "Configure nginx as a reverse proxy." | `none` | `none` | `none` |

4/4 refusals in both arms; 0 forced nearest-neighbour picks. Measured flat-arm
cost: 14,719 input tokens = **$0.000618**.

## Against the predictions

- **P5 (all four answer `none` in the flat arm) - CONFIRMED**, 4/4.
- **P6 (all four answer `none` in the stage arm) - CONFIRMED**, 4/4.
- **P7 (no in-library query answers `none`) - CONFIRMED** in E1, 14/14.

## What this establishes

The discriminating half of the routing question is clean: at 98 options with
`none` offered, the seam refuses a query the library does not carry, and it also
answers when the library does carry it. The failure mode a router must fear - a
confident wrong pick that sends the agent to read a vendored ML skill for an
nginx question - did not occur in 4 of 4 out-of-library queries. Four is a small
count and the exclusion is coarse (the option text shares no vocabulary with the
query at all), so this bounds the gross failure, not the near-miss: an ML-adjacent
query just outside the library is the untested case.

## Combined with E1

Surface 6 needs no new primitive: a flat Choice over `name` + clause works, costs
~$0.00016 and ~0.8 s per query, refuses when it should, and the two-stage variant
is not measurably better. The 1.61x token saving of the two-stage shape is worth
$0.00006 per query, which does not pay for a second round trip.
Rows here are scope: fixture (protocol.md: "Four queries that name work this library does not carry").
