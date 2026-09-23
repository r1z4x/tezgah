# To the human: the two calls this analysis cannot make

Everything measured is in `../findings.md`. Two decisions are yours because both
change tezgah's posture, not just its behaviour.

## 1. Where does the TypeSafe key come from?

The key is in omp's private store (`~/.omp/agent/agent.db`,
`auth_credentials.data`). `TYPESAFE_API_KEY` is not exported in this shell.

| Option | Consequence |
|---|---|
| (a) export `TYPESAFE_API_KEY` in the shell profile | recommended: the SDK, the docs and omp all read it; no new code, no second key to rotate |
| (b) tezgah reads omp's store | rejected: another tool's private credential blob, and it is omp's to change |
| (c) a tezgah-owned key file + reader | independent of omp, but a second key to rotate and a second place a secret lives |

## 2. May a hook touch the network?

Today `hooks/` has no HTTP client at all, and the suite is hermetic. A TypeSafe
call is the first network dependency on that path.

Recommendation: **on-demand paths only** - `tezgah-docs`, the app-analysis loop,
and a prompt-time skill suggestion - always with a no-key fallback to today's
deterministic behaviour, and **never** in the gate, the shortcut parser, the Stop
rule or the consent path. Those refusals must stay reproducible, and they are on
the hot path of every tool call.

## 3. What the first implementation should be, if you approve

Ranked by (saving x ease), from `../findings.md` 4:

1. **a prompt-time skill suggestion** - deletes most of the 2.0k-token roster
   from the always-on text, and TypeSafe's own measurement says wrong loads drop
   by more than half;
2. **an app-analysis tree triage** - one screen is 3,701 tokens measured, and
   the unselected lines never reach the expensive model;
3. **a batched state-matrix pass** - what makes the component x state depth
   affordable.

Each needs the key from decision 1 to be verified at all; without it the honest
status of P1-P4 stays "untested".

**What the measurements did to this list (2026-09-22).** Recommendation 1 is
built but had no headroom here: the independent chooser was already at 0/20 wrong
loads without a hint, so the always-on roster was *not* shrunk to pay for it and
the picker ships opt-in (`hooks/tezgah_skill_pick.py`, `skill-suggest-on`).
Recommendation 2 is built (`bin/tezgah-triage`) with a different shape than this
line assumed: one judgement per repeating unit, not per line, because the
per-line shape recalled 69.9% of the control lines. It keeps 100% of them at a
94% read, so the win is coverage that can be trusted rather than lines skipped -
the screen's own structure floors the read at 76% when the task names a repeated
control. Recommendation 3 is built as `tezgah-triage --states`. The
credential and network questions are answered in code: env var then tezgah's key
file, on-demand only, never the gate.
