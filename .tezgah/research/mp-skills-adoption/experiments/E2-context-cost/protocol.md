# E2 protocol — what does the pack cost in always-on bytes?

**Change under test:** none. The instrument computes one byte figure per corpus
with the installer's *own* formula — `sum(len(name) + len(description) + 8)` over
the shipped skill names (`bin/tezgah-setup:1754-1755`) — and reads the two
always-on text sizes the repository already carries.

**Ordering disclosed:** the CORE and CONTRACT byte counts were read once during
reconnaissance *before* this protocol was written (13483 / 35860 B at HEAD) and
are used here as the comparison scale only. Neither is a predicted outcome, and
neither changes the verdict either way.

## Prediction

1. The upstream 38-skill metadata row is **at least 2× tezgah's 14-skill row**,
   because the pack's descriptions are long trigger-bearing paragraphs
   (the promoted ones) plus human-facing one-liners, while tezgah's row is
   measured on one 140-character-capped sentence per skill.
2. The pack's craft reference — `writing-for-agents/SKILL.md` plus
   `SKILL-MECHANICS.md` — is **smaller than CONTRACT** (35860 B): vendoring the
   reference costs less always-on text than the contract already spends. It is
   read-only material behind a pointer, so its own size is the router line, and
   the prediction is about whether a *reference* worth adopting is affordable.

## What would falsify it

1. An upstream row **below 2×** the tezgah row: the pack is cheaper always-on
   than the shape of its descriptions suggests.
2. The craft reference **at or above** CONTRACT bytes: it would be a second
   contract-sized document, not a reference, whatever its quality.

## Instrument

`instrument.py context-cost --setup bin/tezgah-setup --policy hooks/tezgah_policy.py
--tezgah skills --upstream /tmp/mp-skills/skills`. Scope is `real` for the
tezgah row and `fixture` for the upstream rows; the two are not comparable as
one quantity and are never summed.
