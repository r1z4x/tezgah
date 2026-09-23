# E2 analysis — does every shipped refusal earn its keep?

## What was read
`results.jsonl` (14 rows): the fold of every ledger on this machine plus the
gate's own label set read from source.

Rows here are scope: real (protocol.md: "Fold every `~/.cache/tezgah/evidence/*.jsonl`").

## Against the predictions

| # | prediction | result | verdict |
|---|---|---|---|
| 1 | at least one shipped deny rule has fired zero times (predicted `lang`, `attribution`) | **two do**: `explorer` and `order`; `lang` fired once, `attribution` six times | **holds, wrong pair** |
| 2 | at least two rules fired only on the day they shipped | **three**: `task` (168 fires, 1 day), `race` (8, 1 day), `lang` (1, 1 day) | **holds** |
| 3 | the corpus spans more than one host | not measurable: a deny row carries `detail`, `id`, `kind`, `ts`, `workspace` — the *directory*, not the host | **missed** |

## What the numbers say
- 1613 ledgers, 35,652 rows, 555 refusals, 11 distinct labels — over six days.
- The distribution is steep: `drift` 181 (143 sessions), `task` 168 (80, one
  day), `consent` 76 (43, four days), `sink` 38, `shortcut` 33, `retry` 21,
  `secret` 16, `race` 8, `loop` 7, `attribution` 6, `lang` 1.
- **`explorer` and `order` have never refused anything here.** Both are rules with
  text and code on the hot path, and `order` is the repo's own answer to "do not
  commit before the tests pass" — the shape found in 90% of agent-instruction
  projects. On this machine's traffic neither has ever had the chance to fire.
- `drift` — the rule that fired most — fired on this session too, three times,
  while this experiment was being written. It is the only always-on rule whose
  cost is a refused call in the middle of long work.
- **`task` is the clearest single datum**: 168 refusals, 80 sessions, and all of
  them on 2026-09-18, the day it shipped. `plans/open/` is empty today, so the
  requirement is not armed anywhere and cannot fire.

## What this does not show
- Whether a rule that never fired is *wrong* or merely *unreached*: the check
  cannot distinguish "the traffic never offered this shape" from "the rule cannot
  match". A zero count is a question, and the answer is a probe that issues the
  shape deliberately (the audit line's own method: `E1`/`E8` froze a probe set).
- Per-host attribution: the ledger keeps the workspace, not the host, so this
  fold cannot say whether `explorer` is unenforced somewhere or simply never
  asked for.
