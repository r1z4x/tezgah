# H2 - a register brief against one generic audience line

**Change.** Both arms edit the same drafts. Arm A is told only "Audience: general
professional readers. Write clearly." Arm B is given the register brief for that
item's register - reader, what they want first, the vocabulary that belongs to
them, and a length bound - and is told the draft is checked against it. Both arms
carry the same shipped editing contract, so the brief is the only variable.

**Predicts.** Blind judges score arm B's edits at least 0.5 higher on a 0-5
audience-fit rubric over the twelve register items, with a 95% CI that excludes 0.

**Why.** Naming a persona half-fails while a decomposed, checkable target reaches
81% exact match against 58.3% for a fine-tuned baseline
(literature/thillainathan-controlled-generation.md); register is a measurable
variable rather than a tone word (literature/biber-register-variation.md); and
flattening for the wrong reader is a measurable loss, not a neutral choice
(literature/august-know-your-audience.md). The briefs themselves come from the
register sources in `literature/` - the executive reading budget, the developer
documentation conventions, the Turkish corporate register.

**Falsifies.** No difference, or a native-ness drop that purchases the fit - the
brief turning the draft into a corporate template is the failure this half
watches for.

**Design, to be pinned here before the run.** Items: the six Turkish drafts, two
per register. Briefs: `harness/briefs.json`. Harness: `harness/run.py --track
h2`. Judges see the reader description and the two drafts, blind, both orders.
