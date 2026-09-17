# E5 analysis - census of the live ledgers

Run: 2026-09-17, `census.py` over `~/.cache/tezgah/evidence` on this machine.
Raw output: `results.json`. Not a pre-registered experiment - this is a census
taken to answer three design questions that had been answered by assertion.

## 1. Is the loop guard's 200-row window big enough?

| quantity | value |
|---|---|
| sessions on disk | 217 |
| rows | 6,771 |
| session length | median **8**, p95 **100**, max **927** |
| rows carrying an `id` | 140 (the field is new) |
| gap between two attempts of one `id` | median **1**, p95 **1**, max **21** (n=39) |

Two readings, and they point the same way:

- **The window is rarely binding at all.** The median session is 8 rows and the
  95th percentile is 100, so for 95% of sessions the 200-row tail *is* the whole
  ledger. The guard's window only constrains the handful of sessions longer than
  that.
- **Where repeats exist they are adjacent.** The largest observed gap between two
  attempts of the same action is 21 rows - a tenth of the window - and the median
  is 1 (the agent retrying immediately).

So the number is defensible, but it was chosen before this measurement existed:
the first version of the rule said "last 200 lines" because that is what I wrote
in the task brief, not because anything had been counted. It is recorded here as
provisional: correct for the workload on this machine, unverified on a workload
with long autonomous runs, where a loop can span thousands of calls and the
window would silently stop counting.

**The window's real ceiling is not the row count, it is that nothing reports when
it truncates.** A guard that stops seeing the first attempt of a loop should say
so. That is the smallest fix this census argues for, and it is not in the code
today.

## 2. How often is an irreversible action actually attempted?

| shape | count |
|---|---|
| `rm -rf` | 63 |
| `git reset --hard` | 1 |
| `git branch -D` | 1 |
| **total, across 6,771 rows / 217 sessions** | **65** |

The study deferred the consent gate (priority control 3) with the reasoning that
the measured frequency was zero. That was wrong: it was never measured, and the
true figure is 65 attempts. What the census cannot say is whether any of them
lacked consent - `detail` holds a 200-character command, not the turn's intent -
but the premise for deferral is gone. The frequency is low enough that a
mis-tuned consent rule would still cost more than it saves, which is what the
deferral now rests on, and that is a much narrower claim than "it never happens".

## Limits

- One machine, one user, 217 sessions, and the `id` field only exists in the last
  two of them, so the gap distribution rests on 39 repeats.
- `rm -rf` covers `rm -rf build/` as well as anything dangerous; the census counts
  the shape, not the risk.
- The census cannot see actions taken outside a tool call (a script a human ran),
  and it counts a command in `detail`, which is truncated at 200 characters.
