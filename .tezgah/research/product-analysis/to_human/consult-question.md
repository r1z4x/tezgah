# Design under review (raw artifact)

## Context

`tezgah` is an agent harness that injects a working contract into coding sessions. It
routes task classes to rules at prompt time: `PROMPT_HINTS` in `hooks/tezgah_context.py`
is a list of `(key, regex)` pairs; `classify_prompt(text)` returns the keys a prompt
matches; on that turn only, the matching conditional paragraphs from `CORE` are
appended to the per-turn reminder. The current classes are `spec`, `consult`,
`research`, `cbm`. Each rule also ships as a skill (`skills/<name>/SKILL.md`) that a
host can route to.

## Observed defect (executed on 2026-09-19 against the running code)

| prompt | armed keys |
|---|---|
| `bu ürünü analiz et ve nasıl iyileştirebiliriz` | none |
| `ürünle alakalı analiz istiyorum ürünleri daha iyi hale getirmek istiyorum` | none |
| `product manager seviyesinde analiz yap` | none |
| `retention düşüyor ne yapmalıyız` | none |
| `which feature should we build next` | none |
| `feature önerilerini önceliklendir` | none |
| `bu ekran düzgün çalışsın` | spec |
| `kullanıcı deneyimi raporu` | none |

No shipped skill covers product analysis either. Net effect: a product question is
answered from the model's priors, with no required evidence, no artifact and no
standard, while a UI adjective on the same session arms `spec`.

## Proposed change

1. Add a `product` class to `PROMPT_HINTS` (the only new input surface).
2. Add `product` to `CONDITIONAL_KEYS`, a `product` paragraph to `CORE` with a bold
   label, and a clause to `POINTERS`. (This is the repository's own documented
   procedure for a task-class rule, `docs/contract.md` "Adding a rule".)
3. New skill `skills/product-analysis/SKILL.md`, added to `SKILLS`, which states:
   - two axes: PM (value) and PE (feasibility);
   - named standards: HEART Goals->Signals->Metrics (Rodden/Hutchinson/Fu, CHI 2010)
     with the rule that counts must be normalized to ratios; Opportunity Solution
     Tree + opportunity score (Torres / Olsen); `intended-vs-implemented`
     (both sides of a gap cited) for the feasibility axis;
   - five evidence classes: `user-verbatim`, `behaviour` (ratio + definition +
     window + source), `code` (`path:line` or a graph symbol), `external` (a cited URL
     or paper read in this session), and `none` (not a finding);
   - execution through the existing research workspace (`tezgah-research`), whose
     claims already require a falsification criterion, a provenance tag and a
     resolving proof path;
   - a 6-dimension scorecard with 1-5 anchors, reusing the anchors already shipped in
     `skills/research`, and a required "what this did not look at" section.
4. `research-off` also disarms the product rule.
5. Tests: the classifier arming (positive and negative prompts), the host
   conformance map, the kill-switch label, the ship check, the router-line trigger,
   and the two mirror pairs.

## Acceptance criteria

- AC1: a product-shaped prompt arms the `product` rule; two non-product prompts still
  arm nothing.
- AC2: the paragraph reaches the model on every host.
- AC3: `research-off` removes it.
- AC4/AC5: the skill ships and its router line carries its trigger words.
- AC6: the contract copy and the output-style mirror stay in step.
- AC7: the research line passes `tezgah-research check`.

## Questions

1. Is a new conditional rule plus a new skill the right minimal fix, or is widening
   the existing `research` hint with product words strictly better (fewer moving
   parts, but it hands the model an ML-experiment-flavoured paragraph for a product
   question)?
2. Is the five-class evidence rubric (`user-verbatim` / `behaviour` / `code` /
   `external` / `none`) the right invariant to put in a harness prompt, or is it
   over-specified for text a model reads once per turn? Would fewer classes carry the
   same force?
3. The prior art (`phuryn/pm-skills`, MIT, 69 skills) covers both axes. Should this
   repository vendor selected skills from it, vendor it wholesale (as it does with a
   98-skill AI-research library), or reference it by URL only (the current choice)?

Answer under these five headings: recommendation, key disagreements,
unchecked assumptions, what would change your mind, requested evidence.
