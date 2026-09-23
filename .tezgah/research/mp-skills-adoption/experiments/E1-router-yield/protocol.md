# E1 protocol — does the pack's frontmatter survive tezgah's trigger-line extractor?

**Change under test:** none to the repository. The instrument runs the *shipped*
extractor (`bin/tezgah-setup:693-730`, `skill_description`) over two corpora and
classifies what it returns.

- control, scope `real`: this repository's 14 shipped skills, read off disk as
  the installer reads them.
- treatment, scope `fixture`: the upstream clone at
  `c55ee46073ed923f86ce59a5eb3b6d895095d1b7`, 38 `SKILL.md`.

The classifier is the extractor's own rule, not a new one: a returned line is
`trigger` when it matches `^(Also )?[Uu]se\b` — the sentence the extractor
selects by that very pattern (`bin/tezgah-setup:717`) — `fallback` when the
extractor returned the opening sentence instead, and `empty` when it returned
nothing. An empty or fallback line reaches the router as a line with no trigger
words.

## Prediction

Of the 38 upstream `SKILL.md`, **at least 13 return a non-trigger line** (the
22 user-invoked skills carry a human-facing one-liner by design —
`.agents/invocation.md`, "Strip trigger lists ('Use when the user says…')" — and
the extractor's fallback is the opening sentence). The control is expected at
**14 of 14 trigger-bearing**.

**Why this matters:** a router line without a trigger sentence is the exact
failure `docs/skills.md` records for `tezgah-contract` and `ponytail` — "stripped
… of every word a session matches on, leaving both unroutable" — and the repo's
fix was to make the description carry a later `Use when …` sentence.

## What would falsify it

- **Fewer than 13** upstream lines classify `fallback` or `empty`: the pack's
  descriptions are trigger-shaped after all and the prediction is wrong.
- **Fewer than 14** tezgah lines classify `trigger`: the instrument (or the
  extractor it calls) is broken, and the treatment number says nothing about the
  pack.

## Instrument

`instrument.py router-yield --setup bin/tezgah-setup --tezgah skills
--upstream /tmp/mp-skills/skills`, one JSON row per skill plus a summary row per
corpus.
