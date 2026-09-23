# Product-analysis structure: spec and design

Deliverable of this research line. Two parts: the **spec** the change is judged
against, and the **design** it implements. Every claim here points at an evidence note
in `../literature/` or a path in the repository.

## The problem, stated as a mechanism

A product question ("ürünümü analiz et", "retention düşüyor", "which feature next")
armed no tezgah rule when this line measured it on 2026-09-19, so the session
answered it from priors. The output was generic
because nothing forced it to be specific: no required evidence class, no named
standard, no falsifiable claim, no artifact. **The change this line designed and
landed arms the rule**; the after-measurement is in `Outcome` below, and the
baseline above is kept because it is the number the change is measured against.

## Named standards

| Axis | Standard | Source | What it settles |
|---|---|---|---|
| PM: is it worth building | HEART + Goals->Signals->Metrics | Rodden, Hutchinson, Fu, CHI 2010 (`literature/01-heart-2010-rodden.md`) | metric must trace to a goal; counts refused, ratios required; explicit in/out per HEART category |
| PM: what to build | Opportunity Solution Tree; opportunity score Importance x (1 - Satisfaction) | Torres, *Continuous Discovery Habits*; Olsen, *Lean Product Playbook* - as carried in `phuryn/pm-skills` (`literature/04-phuryn-pm-skills.md`) | opportunities (needs), not features; one outcome per tree; >=3 solutions compared before choosing |
| PE: does it do what it says | intended vs implemented | `phuryn/pm-skills` `pm-ai-shipping` (`literature/04-phuryn-pm-skills.md`) | a gap is a finding only when the documented intent and the code line are both cited |
| PE: is the system healthy | no single number | the SPACE abstract (Forsgren et al., ACM Queue 2021) as it is held in `literature/02-space-2021-forsgren.md`, beside DORA 2025 (`literature/03-dora-2025.md`) | the abstract's own claim: productivity "cannot be measured by a single metric or dimension", so report a constellation and name its coverage; measure impact, not output. Only the abstract was read - the note records that ACM returned 403, so the five dimensions are `[CITATION NEEDED]` there and nothing in this line enumerates them |

## Evidence classes (every finding carries exactly one)

| Class | Counts as evidence | Does not count |
|---|---|---|
| `user-verbatim` | a quote from an interview, ticket, review or message, with its source | "users want", "users struggle" |
| `behaviour` | a ratio with its definition (numerator/denominator/window), its source and its date | a raw count; a screenshot with no window; a number with no denominator |
| `code` | a `path:line` in this repository, or a graph symbol with its callers | "probably handled upstream"; a comment saying "internal only" |
| `external` | a cited URL or paper read in this session | "best practice"; a framework named without its artifact |
| `none` | - | anything else: this is a question to investigate, not a finding |

## The artifact

Execution goes through the shipped research workspace, not a new one:
`~/.config/tezgah/bin/tezgah-research init <slug> --question "..."`, then
`findings.md`, `literature/`, `claims.jsonl` (one claim per line with `statement`,
`status`, `provenance`, `falsification`, `proof`) and `to_human/`. The product
analysis adds its own required sections on top of what `check` already enforces:

1. The objective, one measurable outcome, with the Goal -> Signal -> Metric chain.
2. Opportunities (needs) with their evidence class, then >=3 candidate solutions with
   the comparison criterion written before the scores.
3. Risks named by class (value, usability, viability, feasibility) and the cheapest
   test that would falsify each.
4. The PE half: for each intended behaviour, the code that implements it, cited.
5. Findings, each with its evidence class and its citation, most severe first.
6. What the analysis did **not** look at, and what would change the recommendation.

## Scorecard (same 1-5 anchors as `skills/research`, so two sessions compare)

| Dimension | The question |
|---|---|
| Evidence relevance | does the cited source actually support what the finding says? |
| Class discipline | is every finding's evidence class named and honoured? |
| Metric integrity | does the metric trace to a goal, and is it a ratio with a definition? |
| Solution plurality | were >=3 solutions compared against a pre-stated criterion? |
| Feasibility grounding | is the implementation claim a cited code path, not an inference? |
| Scope calibration | does the analysis say what it did not look at, and what would flip it? |

Mean >=4.5 with no dimension below 3 = accept; >=3.8 weak accept; >=3.0 revise; below
that, or any dimension at 1, reject.

## Acceptance criteria (checkable)

| # | Criterion | Checked by |
|---|---|---|
| AC1 | a product-shaped prompt arms the `product` rule | new unit test on `classify_prompt`, plus the four prompts in `findings.md` |
| AC2 | the product paragraph reaches the model on every host | `ArmingConformance` prompt map |
| AC3 | `research-off` disarms it like the rule it sits beside | `KillSwitchEnforcement` |
| AC4 | `product-analysis` ships: in `SKILLS`, a readable `SKILL.md` on every host | `tests/test_skills.py` |
| AC5 | the router line carries its trigger words | `tests/test_setup.py` router-line tests |
| AC6 | the contract copy and the output-style mirror stay in step | `ContractParity`, `OutputStyleMirrorsCore` |
| AC7 | no non-product prompt newly arms the rule | `test_suffix_tolerance_does_not_widen_the_hints` plus two added negatives |
| AC8 | the research line itself passes its own checks | `tezgah-research check product-analysis` exits 0 |

## The axes consult, relayed

Second review, `consult --online`, on the five-axis design (full text in
`consult-axes-answer.md`; three models including the referee). Where they landed:

- **Both agreed `ui-observed` is the right fifth class** - forcing a UI finding
  into `code` (inferred) or `behaviour` (a ratio) is the original defect.
- **Both agreed the single-rater limitation must be surfaced, not hidden.** One
  proposed the stronger mechanism: an anchored confidence on every heuristic
  finding, so a one-rater judgement can never read as certain. Adopted: a usability
  finding now says whether it is a `failure` (reproducible - an assertion, a log, a
  measurement) or a `judgement` (a heuristic read in context) and reports its rater
  count.
- **They disagreed on the decomposition**: one argued for three lenses with triage
  as an output of strategy and measurement readiness as a pre-flight gate; the
  other for five parallel axes with triage as a first-class one. Kept five axes,
  because the first run's failure was precisely that nothing forced a keep/cut
  verdict to exist - an output that is merely implied gets dropped, and the gate
  already runs before the axes. The disagreement is recorded rather than resolved
  by argument.
- **Their chief unchecked assumption was verified instead of assumed**: does the
  app-analysis tooling actually supply UX-grade evidence? `analyze-app` reads the
  accessibility / DOM / native view tree, re-reads it after each change, and pulls
  console, network, device logs and crashes - and the caps above fill the three
  gaps that remained. Their own requested evidence (the schema, an example run) is
  covered by the strict handshake and by the evidence map in the skill.

## Outcome (verified in this session)

| Check | Result |
|---|---|
| `python3 -m unittest discover -s tests` | **932** test cases at the landing commit `2a5a29e` - re-derived on 2026-09-22 by loading that revision's tree with the loader `discover` uses (the first run recorded 931, one test short; `2a5a29e^` loads 928 and HEAD today loads 1333, so the count is only meaningful with its date). The run itself reported OK |
| `ruff check .` | All checks passed |
| `python3 -m compileall -q hooks hosts bin statusline.py` | clean |
| `bin/tezgah-docs --citations` | 260 judged, 0 outside the symbol they name |
| `bin/tezgah-context user_prompt` with a product prompt | the paragraph is injected once |
| the same with `add a docstring to parse_quantity` / `deploy to production` | nothing injected |
| `bin/tezgah-context session_start` | nothing injected (the rule is conditional) |
| `bin/tezgah-research check product-analysis` | 1 line ok, exit 0 |

## What this does not show - the headline goal was never measured

**A better product answer was never measured.** The locked metric counts two
things and neither of them reads an answer: how many of the eight fixed product
prompts arm the `product` rule (0 before the change, 8 after), and whether the
shipped skill's scorecard can be applied to a real product question. Both are
*routing and applicability* proxies for the line's goal. What this line therefore
established is that the evidence discipline now **reaches** a product question on
the intended path, carrying a named standard with a falsification criterion - not
that the answers got better. The instrument that would show the goal was never
locked, so no null result is being reported either: the goal is unmeasured, not
measured and flat.

The smallest action that would move it: one paired run on the same product
prompts with and without the rule, each answer scored against the scorecard in
this report by a reader who does not know which arm it came from. Unrun - it
needs model spend and a session on the branch, and this line closed on routing
evidence (review finding F3, reframed rather than answered).

## The consult, relayed

Two external models answered (`consult --online`, 2026-09-19; full text in
`consult-answer.md`). They agreed on the first two questions: a dedicated
`product` class beats widening `research` (different task classes, and the
research paragraph is experiment-shaped), and the evidence-class rubric is the
load-bearing part. They disagreed on the third: one recommended vendoring a
single-file MIT prior-art skill it named as near-perfect, the other said a URL
reference is sufficient. That repository was fetched before acting on the claim
and exists (one `SKILL.md`, MIT, 1 star); its two transferable rules - the
"source says X, therefore we do Y" citation form and stage calibration - are in
the shipped skill. Vendoring is left to the user. One model's unchecked
assumption was resolved by measurement: the regex is precise enough that a
product prompt arms while `kullanıcı deneyimi raporu` does not.

## Non-goals

- Not vendoring the 69-skill marketplace. The skill references it by URL and licence;
  the vendoring decision is the user's (tradeoff recorded below).
- Not measuring whether the rule improves answers. Stated as an open question.
- Not inventing a rubric where a source exists: the PM and PE axes defer to the
  standards in the table above.

## The decision left to the user

**Decided 2026-09-19: vendor selected skills.** `skills/pm-frameworks` now holds
the two methods this skill defers to - `intended-vs-implemented` and
`opportunity-solution-tree` - byte-for-byte from `phuryn/pm-skills` at revision
`8607e3b077817f89bf4a9b623246219734ac3be0`, with a `SOURCE` manifest, a sha256
check in `tests/test_skills.py` and a `NOTICE` entry. The consult behind the
decision is a transcript of two external models' opinions and not evidence of
anything (`C10` is superseded by `C10c` for exactly that reason); what a reader
can check is the artifact the decision produced - the two bodies, the `SOURCE`
manifest and the hash test - and that is what the surviving claim cites. The
other 67 skills and the plugin manifest are not copied. The options weighed were:

| Option | Cost | Benefit |
|---|---|---|
| Reference by URL | none | the standard is named and reachable; no third-party surface in the repo |
| **Vendor selected skills (chosen)** | a `NOTICE` entry, two vendored bodies, one manifest test | the method text is local and offline |
| Vendor the marketplace wholesale | 9 plugins of surface, a much larger always-on cost | everything, including the parts this repo will not use |

Note: "make products perfect" is not a reachable state, and nothing here claims it.
The reachable property is that every product claim carries its evidence and its
falsification criterion, so the loop converges on the outcome metric instead of on
prose.

## Closing pass (2026-09-22)

The line's own review (`to_human/review.json`) graded it `revise` with four
findings open. Each is closed or reframed here, with the reason:

- **F3 - the metric measures routing only.** Reframed, not answered: the
  evaluation now says so in `state.json` (`evaluation.metric_note`), and the
  section above names the goal as unmeasured and the smallest run that would
  measure it. `methodological_rigour` stays at 3 because the limitation is real.
- **F4 - 931 against 932 tests.** Reconciled against one tree: 932 is the count
  at the commit that landed the change, re-derived on 2026-09-22; 931 is the
  first run's value and sits one test below it. Recorded in all three files with
  its date, and in `log.md`.
- **F5 - the SPACE note was never read.** Read on 2026-09-22 and recorded: the
  note holds the verbatim abstract, says ACM returned 403 for the full text, and
  deliberately omits the five dimensions rather than writing them from memory.
  The named-standards table now cites the abstract it actually used. The note
  itself is left as it stands.
- **F6 - C10 rested on an opinion transcript.** Settled through the CLI:
  `C10c` supersedes `C10` and cites the artifact the decision produced (the two
  vendored bodies, `SOURCE`, the hash test) rather than the models' agreement.

Also settled in this pass: the two bullets in `findings.md` that disagreed about
whether a product prompt arms anything now carry their dates - a dated baseline
(2026-09-19, armed nothing) and its after-measurement (armed).

Still open, and named rather than silent: the goal-level run (F3), and the
layer's own supersession warning - here, that `C10c` supersedes `C10` means a
reader who opens `C10` alone reads the replaced statement, and `check` says so.
