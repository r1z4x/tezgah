# Findings

## What we know

- **The running-app axis was blocked by a wiring default, not by a missing
  capability.** Playwright MCP serves core tools only unless capabilities are
  named, and tezgah's wired command named none - so an analysis could read an
  accessibility tree but could not assert (`testing`), could not reach a logged-in
  surface without attaching to the user's real Chrome (`storage`), and could not
  set the offline state (`network`). The command now carries
  `--caps=testing,storage,network`, and the strict wiring handshake reports
  `playwright` exposing **52** tools instead of about 24, `mobile-mcp` 32. The
  wiring test now requires four of the cap tools, so a silently dropped `--caps`
  fails CI. Mobile MCP has no assertion, mocking or geometry tool at all: a mobile
  UX claim is a judgement unless re-walked, and contrast or tap-target size is not
  claimable without a screenshot. Recorded in `literature/07-app-mcp-surfaces.md`.
- **The fix is in the tree and verified** (the after-measurement; the baseline it
  is measured against is the bullet on `PROMPT_HINTS` below). `classify_prompt`
  now arms `product`
  for the user's verbatim Turkish phrasing, `which feature should we build next`,
  `retention düşüyor`, `product manager seviyesinde analiz` and three more, and
  arms nothing for `deploy to production` or `improve developer productivity`
  (`product(?!ion|ivity|ive)` keeps those code words out). On the real injection
  path, `bin/tezgah-context user_prompt` carries the paragraph once for a product
  prompt and never for the two controls, while `session_start` never carries it,
  because the rule is conditional. Full suite: **932** test cases at the landing
  commit `2a5a29e`, re-derived on 2026-09-22 by loading that revision's tree with
  the same loader `unittest discover` uses (the first run recorded 931, one test
  short of the landing commit; the loader reads 928 at `2a5a29e^` and 1333 at
  HEAD today, so the number is only meaningful with its date); `ruff` clean;
  `compileall` clean; `bin/tezgah-docs --citations` reports 260 judged with 0
  outside the symbol they name.
- **The GitHub packages the user asked about exist, and are worth naming.**
  `phuryn/pm-skills` (26,443 stars at read time, MIT, 69 skills / 42 commands
  across 9 plugins) covers both axes; `Geo1230/product-analysis` (MIT, a single
  ~340-line `SKILL.md`, 1 star) is a stage-aware analysis skill built from 12
  books; `deanpeters/Product-Manager-Skills`, `wdavidturner/product-skills`
  (20 frameworks), `aakashg/pm-claude-skills` and `Digidai/product-manager-skills`
  are the same class of thing. None is vendored here: the skill references
  `phuryn/pm-skills` by URL and the vendoring tradeoff is the user's call.
- **The product prompt was invisible to the router before the change** (baseline,
  measured 2026-09-19; the after-measurement is the bullet above). `PROMPT_HINTS`
  (`hooks/tezgah_context.py:42-66`) carried four classes - `spec`, `consult`,
  `research`, `cbm` - and none of them is product-shaped. Executed against the running
  code on 2026-09-19, every product phrasing armed **nothing**:

  | prompt | armed |
  |---|---|
  | `bu ürünü analiz et ve nasıl iyileştirebiliriz` | none |
  | `ürünle alakalı analiz istiyorum ürünleri daha iyi hale getirmek istiyorum` | none |
  | `product manager seviyesinde analiz yap` | none |
  | `retention düşüyor ne yapmalıyız` | none |
  | `which feature should we build next` | none |
  | `feature önerilerini önceliklendir` | none |
  | `bu ekran düzgün çalışsın` | `spec` |
  | `kullanıcı deneyimi raporu` | none |

  So before the change the evidence discipline never reached the model on a product
  question, while the same session armed `spec` for a UI adjective. The user's
  complaint had a mechanical cause, not a model-quality cause - and the after
  measurement in the first bullet is what closed it.
- **No shipped skill covers product analysis.** `SKILLS`
  (`bin/tezgah-setup:76-78`) ships eleven skills; none of them is a product skill, and
  the `research` skill's trigger sentence (`skills/research/SKILL.md`) carries no
  product word, so even a host that lists it cannot route a product ask to it.
- **The existing evidence machinery is the right engine but the wrong rubric.** The
  research workspace (`hooks/tezgah_research.py`, `bin/tezgah-research`) already
  enforces claims with a falsification criterion, a provenance tag and cited evidence,
  and `skills/research` already scores claims on six anchored dimensions. Its evidence
  rules, though, are ML-shaped ("a correlation does not support a causal verb"; "one
  seed does not support always"), and it has no class for a user quote, a funnel
  ratio, a code path or a competitor fact.
- **The prior art exists and is MIT, and it splits exactly along PM / PE.**
  `phuryn/pm-skills` (26,443 stars at read time) ships `pm-product-discovery`
  (Opportunity Solution Tree; Torres), `pm-data-analytics` (cohort, A/B), and
  `pm-ai-shipping` (`intended-vs-implemented`, security and performance audits).
- **The named standard for the measurement half is a 2010 CHI paper, not folklore.**
  HEART (Rodden, Hutchinson, Fu, CHI 2010) supplies the process - Goals -> Signals ->
  Metrics - and the invariant that matters most here: "Raw counts will go up as your
  user base grows, and need to be normalized; ratios, percentages, or averages per
  user are often more useful."
- **The named standard for the feasibility half is a cited-both-sides rule.** From the
  marketplace's `intended-vs-implemented`: intent is a documented claim, evidence is "a
  cited file and line", and "If you cannot cite both sides of the gap, it is a question
  to investigate, not a finding to report."
- **The harness class is the wrong place to look for a fix.** DORA 2025: "AI's primary
  role is as an amplifier, magnifying an organization's existing strengths and
  weaknesses", and the named failure mode is the verification tax - "30% of developers
  currently report little to no trust in the code generated by AI". A harness that
  emits plausible prose about a product is amplifying the weakness, not the strength.
- **The repository documents how to close exactly this kind of gap.** `docs/contract.md`
  ("Adding a rule") is the house procedure for a task-class rule: a `CONDITIONAL_KEYS`
  entry, a `PROMPT_HINTS` pattern, a `POINTERS` line, a `CORE` paragraph with a bold
  label, and the pinned tests.

## Patterns

- Every failure above is a **routing or evidence-class gap**, not a capability gap. ([C1], [C2], [C3], [C13])
  The model can already read a repo, drive an app, search the web, and run a research
  workspace; what it never gets told is *that a product question deserves that
  treatment* and *what counts as evidence for one*.
- The repository already solves the same shape twice ([C1], [C2], [C8]): a task class
  arms a rule (`spec`, `consult`, `research`, `cbm`), and a skill carries the long form
  behind it. The product gap is the same shape, unfilled.
- Both verified standards collapse to the same invariant from opposite sides ([C4],
  [C6]): no metric without a goal above it; no finding without both sides cited. One
  rule per axis, not a framework list.

## Lessons

- A multi-part edit whose first part fails the match can silently drop the rest:
  the `CONDITIONAL_KEYS` change rode an edit that was rejected and re-issued in a
  different shape, so it never landed while the other four parts did. The symptom
  was a paragraph that injected always-on while the classifier armed nothing -
  two failing tests with one cause. Re-check every part of a rejected batch.
- Shifting `path:line` citations after an insertion is not a find-and-replace: a
  script that keeps per-file anchor state across the whole document, or whose line
  map omits changed lines, mis-shifts correct citations into wrong ones silently.
  Run `bin/tezgah-docs --citations` and require zero before believing the shift.
- A missing hint is silent by nature: `classify_prompt` returns the empty set and
  the session looks normal. `audit_classification` (`hooks/tezgah_context.py`) writes only
  counts to `cache/classify.log`, so false negatives are invisible unless someone runs
  the prompts by hand - which is how this one was found.
- Reading the repository's own documented procedure (`docs/contract.md`, "Adding a
  rule") before designing the change turned a from-scratch design into a checklist:
  five edits, each with an existing test that fails when only one half moves.

## Open questions

- Does a product rule actually improve a product answer? Unmeasured here; the DORA
  finding is about the class of change, not this one. The measurement would be a
  paired run on product prompts with and without the rule, scored against the rubric
  in `to_human/report.md`. The locked metric is a routing and applicability proxy
  for this question, not an instrument for it - `state.json`'s
  `evaluation.metric_note` says so, and the report's limits section names the run
  that would answer it.
- Should the marketplace be vendored as a skill library (as `ai-research` is), or
  referenced by URL only? Undecided; the tradeoff is recorded in the report.
