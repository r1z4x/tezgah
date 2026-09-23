# E1 analysis — 22 of the pack's 38 bodies reach the router without a trigger

Raw: `results.jsonl` (131 lines: one header, the 14 shipped skills plus their
summary, the 114 tree rows plus their summary) and `results-upstream.jsonl`
(the upstream rows alone - the same instrument run, partitioned by scope).

## Outcome — CONFIRMATORY for the prediction, and the control holds

Prediction: at least 13 of the upstream 38 return a non-trigger line. Measured:
**22 of 38** (`fallback` 22, `empty` 0, `trigger` 16).

| corpus | scope | rows | trigger | fallback | empty |
|---|---|---|---|---|---|
| `tezgah-shipped` (the 14 names in `SKILLS`) | real | 14 | 14 | 0 | 0 |
| `tezgah-tree` (every `SKILL.md` under `skills/`) | real | 114 | 95 | 19 | 0 |
| upstream at `c55ee46` | fixture | 38 | 16 | 22 | 0 |

The control is what makes the treatment readable: the same extractor over the 14
shipped skills returns 14/14 trigger-bearing, so the 22 are a property of the
pack's descriptions and not of the instrument.

The split follows invocation exactly, and every row now carries it: in
`results-upstream.jsonl` the `class` × `invoked` pairs are `fallback` × `user`
(22) and `trigger` × `model` (16), and nothing else. All 22 fallbacks are
user-invoked skills,
and the 16 that classify `trigger` are the model-invoked ones. That is the
pack's own design working as documented — `.agents/invocation.md` says a
user-invoked skill's description is human-facing and its trigger list is
stripped — meeting a router that selects the trigger sentence
(`bin/tezgah-setup:693-730`, the selection itself at line 717).

Concretely: `wait-what` returns the 5-character line `Stop.`, `implement-spec`
34 characters, `ask-matt` 44. Nine of the 22 return a line at or above 100
characters, so this is not a rule about length — `to-spec` (140) and `wayfinder`
(140) are long and still carry no `Use when …`, because their opening sentence is
a description of the skill rather than a statement of when to reach for it.

## A second corpus, found by the instrument rather than planned

`tezgah-tree` exists because the first run walked `skills/` and read 114 files,
not 14: this repository already vendors 100 `SKILL.md` beside its own 14
(`ai-research` 98 + `pm-frameworks` 2 behind one entry point). 19 of the 114
return a non-trigger line — the same failure mode the pack would bring, already
present, inside a bucket the router collapses to a count line (`docs/skills.md`
names the buckets and `bin/tezgah-setup:740` the always-on pair; no router output
is in this line, so that half is carried by the repository's own documentation
and not by a row here).

That is the honest reading of the deviation: the protocol's control was
"this repository's 14 shipped skills" and the first instrument run measured a
different corpus. The instrument now reports both corpora separately
(amendment 1, `log.md`); neither stands in for the other, and the control claim
is measured on the 14 names alone.

## What this does not show

- It does not show the pack's router lines are wrong for *its* harness. In Claude
  Code or Codex the description is the trigger, and a human-facing one-liner is
  the correct choice there; the number is a cost of moving the pack into a
  router that reads a `Use when …` sentence.
- It says nothing about whether a fallback line is *unusable* — only that it
  carries none of the words the router's own rule selects on. `docs/skills.md`
  records what happened when two shipped skills shipped that way: both were
  unroutable until a trigger sentence was added.
