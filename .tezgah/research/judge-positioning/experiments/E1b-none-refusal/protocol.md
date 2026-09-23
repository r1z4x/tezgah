# E1b - does the 98-option Choice refuse when nothing matches?

Status: protocol written before the run.

## What the change is

E1 measured the 98-option flat Choice at 14/14 on in-library queries, which is a
ceiling and therefore proves little. The failure that matters for a router is the
opposite one: a query no entry covers. A Choice with `none` offered is supposed
to answer `none`; a forced nearest-neighbour pick would send the agent to read a
vendored ML skill for a question about nginx.

## What it predicts

- P5: all four out-of-library queries answer `none` in the flat arm. Falsified by
  any entry named.
- P6: the same four answer `none` in the stage arm too (the stage list is even
  less likely to contain them). Falsified by any stage named.
- P7: no in-library query from E1 answers `none` (already observed, restated
  here so the two halves are one claim).

## Method

Four queries that name work this library does not carry - an infrastructure
topic, a database schema, front-end work, and a web-server config - each asked
in the same two shapes as E1. If the flat arm picks an entry for one of them,
the surface needs a guard the seam does not have (the caller must not treat a
named entry as coverage).

## Why the money is worth it

A routing surface that never says "not mine" is worse than no surface: it costs a
call and then costs the agent a wrong read. `bin/tezgah-docs` already refuses this
way (`none` is an option for exactly this reason), so the question is whether the
primitive holds at 98 options as it does at 10 pages.
