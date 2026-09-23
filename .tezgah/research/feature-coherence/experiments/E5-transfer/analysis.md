# E5 - the transfer measurement: result

## What ran

Second feature, different stack: the admin **Users** area of `/Users/rizax/Projects/aibim-app`
(Rust edition 2021 + axum 0.8 + sqlx 0.8 + Postgres; React 19 + Vite SPA; routes at
`admin/backend/src/main.rs:230-286`, ten operations under one
`require_admin_access` layer at `:441-442`). Nothing shared with target #1 except
that both are admin CRUD surfaces.

Corpus frozen before any rater ran: 14 rows across nine classes, sha256
`9c72a2d42f2c764d3b7614746f0abb1eabe60ed61e8c5d57c8393f366e505c5a`, of which **six
defect classes** (C1 capability, C2 field contract, C3 list convention, C8 smart
defaults, C9 destructive confirmation, C10 capability-change slot) and four pass rows
(A07, A08, A09, A11). C7 has no row: both arms are code-scope on this repository
(the app needs a Docker build of a Rust and a Node image, and neither arm was allowed
to start it), so the denominator is six and the layout class is out of reach here -
reported, not hidden.

Four rater contexts, two per arm, all reading source, all blind to the corpus:

| Arm | Artifact | Findings | Unit | Matrices | Proposals |
|---|---|---|---|---|---|
| baseline 1 | `E5-base1.md` | 14 | `product-analysis` | coherence pass produced | 0 |
| baseline 2 | `E5-base2.md` | 15 | `product-analysis` | coherence pass produced | 1 |
| treatment 1 | `E5-treat1.md` | 16 | `feature-audit` | five matrices filled | 2 (all 9 headings, the reviewer's five absences checked) |
| treatment 2 | `E5-treat2.md` | 19 | `feature-audit` | five matrices filled | 2 |

## Scoring

Same rule as E2/E5's committed rule; corpus rows by id, judgement model as a
cross-check (it again counted pass rows A08/A09/A11 as detections for every arm, so
the pass rows are adjudicated by hand below).

| Class | Baseline union | Treatment union |
|---|---|---|
| C1 capability | yes (A02; base1 and base2) | yes (A02) |
| C2 field contract | **yes** (A06) | no |
| C3 list convention | yes (A05, A14) | yes (A05, A14) |
| C8 smart defaults | no | no |
| C9 destructive confirmation | yes (A10, base2) | yes (A10) |
| C10 capability-change slot | **yes (1 proposal, base2)** | yes (2 + 2 proposals) |

**Baseline 5 of 6 defect classes; treatment 4 of 6.** The prediction was that the
baseline would land at or below half and the treatment at least two classes above
it; the treatment instead landed one below the baseline. Both directions of the
prediction are falsified, and the result is reported as a non-confirmation rather
than reframed.

Pass rows: both arms left A07, A08, A09 and A11 alone - neither arm reported a defect
where the two sides agree (the judgement model's opposite reading is its own
artefact, recorded rather than used).

## Why the arms came out level, and what it means

**The control arm was no longer the pre-fix method.** Both baseline raters were told
to apply `product-analysis`, and that skill now instructs the coherence pass and names
the four matrices (`skills/product-analysis/SKILL.md:50-64`) - so the baseline arm on
this feature *also* filled the capability, field-contract, flow and dependency
matrices, and one of its two raters wrote a capability-change proposal with a
rejectable artifact. E5 therefore does not compare "before" with "after"; it compares
**the dedicated artifact with the pointer to it**, and the pointer won a class.

That is the transfer finding, and it is the more useful one:

- **The rule and the axis skill are what transfer.** The method reached a second
  stack, a different language and a different UI framework, and changed what the
  analysis looked at - through `product-analysis`, without the rater opening
  `feature-audit` at all.
- **The dedicated skill file's marginal value is unproven.** On this feature it added
  no class and cost nothing; on target #1 it was the arm that reached 7 of 9. The
  honest reading is that the skill carries the depth (the per-surface rule table, the
  hand-check list, the proposal headings) and the pointer carries the trigger, and
  this experiment measured only the second.
- **Two classes resisted both arms.** C8 (the create path's silent defaults and the
  absent validation on both sides) was missed by all four raters on this feature - a
  real gap in the corpus's discoverability, or in what four raters look for without a
  running app.
- **The raters disagreed about one row in opposite directions**: treat1 reported the
  8-column SELECT decoded into a 5-slot tuple as a severity-2 defect, and treat2 read
  sqlx 0.8.6's `FromRow` implementation and recorded that the decode is *not* a defect
  (`from_row.rs:326-338` checks no column count). That is the corpus discipline
  working inside a rater: a claim withdrawn after reading the dependency's source.

## Correction (added after E7)

`corpus-correction.md` withdraws row A13: the create handler does **not** create a
record from defaulted empty fields - it returns 400 (`admin.rs:906-913`) - so C8's row
is replaced by A15 (no client-side guard; the refusal surfaces only as a toast). No
E5 arm reported either version of that path, so **this arm's numbers are unchanged**
by the correction: baseline 5 of 6, treatment 4 of 6. It is recorded because a wrong
row manufactures agreement, and one arm elsewhere in this line did report the
withdrawn mechanism.

## Limits

- Six defect classes, two raters per arm, one feature, code-scope only: this is a
  directional transfer check, not a second measurement of the size of an effect.
- The confound above is structural, not incidental - after the wiring, there is no
  pre-fix control left in the tree to run.
- Both arms named their own gaps (no `ui-observed`, no `behaviour`, no competitor),
  which is what the scorecards penalised; the reports are comparable in what they
  could not reach.
