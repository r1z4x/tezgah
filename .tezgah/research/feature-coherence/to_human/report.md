# Feature coherence: why a feature-level analysis misses, and what closes it

**Answer.** The shipped analysis reaches **4 of 9 in-scope cross-layer defect
classes** on one real admin feature; the feature-audit artifact reaches **7 of 9** with
three passes per arm, and 14 of 14 artifacts following it wrote the capability-change
proposal the baseline wrote in 2 of the 8 pre-wiring artifacts (E2's three, E6's two and E8's three; the tally is `experiments/E8-more-passes/proposal-tally.md`). The six classes the baseline misses need a second
artifact in view - the field contract, the flow prerequisites, the interaction
dependency, the form patterns, the destructive-confirmation content, and the slot in
which an infrastructure change would be proposed at all. The fix is shipped:
`skills/feature-audit/SKILL.md` names the feature (not the screen) as the unit, requires
five matrices to be filled before any taste judgement, requires a capability-change
proposal whenever a fix names a layer that does not exist, and carries a per-surface
rule table sourced to WAI-ARIA APG and WCAG 2.2. The `product` rule arms it,
`skills/product-analysis/SKILL.md:50` runs it before its axes, and
`docs/feature-audit.md` is the durable page.

The final ordering, after the completeness experiments: **the wiring does the most** (the
post-wiring `product-analysis` skill alone reaches 6 classes on the second stack, above
the artifact's 5), **the artifact leads the pre-wiring rubric by one class** with enough
passes (7 against 6 on the first feature, 6 against 4 on the second), and **rater
diligence moves a single reading by up to three classes** - which is why the artifact is
shipped as a required structure rather than as a better prompt.

## The measurement

| Experiment | What it did | Result |
|---|---|---|
| E1 corpus | read one real feature end to end (Ustam admin users) and froze 15 defect rows in 10 classes | 10/10 classes present; 9 of 13 defect rows invisible from the screen alone |
| E1b runtime | drove the running app (3 widths, empty state, dialog, wizard URLs) | confirmed 3 rows at runtime, added 2 the reading missed; **falsified** its own prediction that the capability rows were runtime-settleable - a server-rendered surface hides its API calls from the browser's log |
| E2 baseline | 3 independent blind raters ran the shipped rubric | **union 4/9 classes, median 3**; 14 findings each; every rater named its own scorecard; no rater produced a capability-change proposal |
| E4b probe | diffed the API's committed contract against the surface's call sites | two declared-and-unreached endpoints (`GET /users/{id}`, `POST /users/{id}/deactivate`) in 3.09 s, no credential, no app |
| E10 competition | 7 comparable products read at first hand (URL + date), comparison basis stated first | all seven deliver an invitation credential in-product; the axis lands as a two-way gap |
| E11 sources | source read for the two empty evidence classes in both repositories | **both predictions falsified**: analytics exists but is dark (noop sink, default off, `enabled` never passed), and user-voice sources exist |
| E12 re-score | independent re-score of the eight second-feature artifacts against the corrected corpus | found the frozen corpus **overwritten** by a results write (restored) and under-counted arms (E6: control 4, treatment 6) |
| E6 pre-wiring control | the pre-wiring rubric (extracted from `0f452df`) against the current one, 2 raters per arm, on the second stack | 2 vs 2 passes: level; the independent re-score of the same eight artifacts reads it as **control 4, treatment 6** |
| E7 discoverability | 2 raters prompted with the create path's empty-submit question | both contradicted the corpus: the handler returns 400, so **row A13 was false** and was replaced by A15 |
| E8 distribution | three passes per arm on the first feature, independently scored | **artifact 7 classes, pre-wiring rubric 6** (per-artifact 8/7/6 against 4/6/4); proposals 14/14 vs 3/5 (content) across both features |
| E9 runtime | `make admin-dev` on the second stack, then a bridge | the repo's own dev target never reaches its users surface (nginx upstream missing); after the bridge 13 `ui-observed` rows and the layout class: clipped columns, unreachable, at 320 and (long row) 768 |
| E4 ablation | 2 further raters ran the artifact with a mandatory probe, against the E3 arm | **arm B 6/9 vs arm A 7/9**: the probe added no class - H4 not supported; it makes the capability row cheap and re-runnable (1.81 s, exit 0) |
| E5 transfer | same shape repeated on a second stack (Rust axum + React admin users), 2 raters per arm, code-scope | **baseline 5/6 defect classes, treatment 4/6** - the prediction is falsified and the control won a class, because `product-analysis` now carries the coherence pass |
| E3 treatment | 5 independent blind raters ran the new artifact | **union 7/9, 5 capability-change proposals** (baseline: 0); 5 matrices filled per rater; every finding carries a Prevent line; the classes the treatment adds are the field contract, the destructive-confirmation content and the capability-change slot |

The corpus is frozen (sha256 `70871644e095372e6e9a5faa5fa761d8dee60c87e82eaca33d5dd857a938d1a6`)
and the scoring rule was committed before any rater output was read, including a
correction that narrowed a row after WCAG 2.2 SC 1.3.5 was read at source. Both arms
are scored on the same rows and rules; C6's rows live on a different route, so it was
out of scope for every rater in both arms and the denominator is nine.

## Why the six classes are missed

- **The unit of analysis.** A screen-level method cannot express "the UI offers an
  action no layer backs" or "the contract carries a field no view renders" - those
  are comparisons, and the rubric's unit is one screen.
- **No required matrix.** The raters found cross-layer defects when they happened to
  compare (one found the unused endpoint; another the whole-org fetch), so the
  ceiling is the rater's hunch, and three raters produced three subsets.
- **No output slot.** Every artifact ended in UI and copy recommendations for
  defects whose fix needs a server-side search, a paginated list, a detail
  aggregate, an autocomplete convention or a combobox primitive. Nothing in the
  artifact list asked for one, so none was written.

## What the research said about existing art

Surveyed at source: agent skills for UI audit exist and are good
(`EnchStyle/ui-ux-audit-skill` ships 15 categories, a severity rubric and a
"durable fix" per finding), spec-driven kits exist and are strong
(`github/spec-kit`'s templates force clarification markers and phase gates), and
drift tools exist (`schema_shift`, `driftspec`, the audited repository's own
`verify-api-contract.mjs` + `docs/openapi.json`). Every one of them automates
**one layer boundary**: spec-to-spec, spec-to-store, or surface-to-rule. None
carries the feature's whole path, which is why the matrices are tables a person or
an agent fills rather than a tool that runs. The audited repository's own CRUD
registry (`admin-crud-coverage.ts`) does not list `/users`, so the surface this line
audited sits outside the repository's own capability check.

## Limits

What the evidence does not show, stated before the findings are reused:

- Two features on two stacks (Next.js server components + NestJS + Prisma; Rust axum +
  React), one organisation's data each, one model family for every rater. The class split
  is evidence about these features; the *method* is what is claimed to transfer, and the
  transfer is thin: one class on the first feature, two on the second, with the post-wiring
  axis skill alone ahead of the artifact there.
- No arm has been scored on a pass row it had to leave alone: the corpus carries defects,
  and four of the six first-feature artifacts (and the session's own judgement model)
  reported a defect where the surface and the server agree.
- E4 ran and **H4 is not supported**: with a mandatory probe the arm reached 6 classes
  against the other arm's 7, and the class the probe was expected to add was already
  reached by every rater in both arms. The probe's value is that it makes the capability
  row cheap and re-runnable (1.81 s, exit 0), not that it finds more.
- The corpus is a floor: raters found defects it did not hold, so the baseline's 4 of 9
  is a lower bound on this feature.
- `tezgah-research check` warns on two conditions this line carries openly, and both
  are stated as limits rather than repaired by rewriting a committed artifact. The
  E4b protocol is reported as stating no falsification criterion, and that reading is
  a limitation of the checker rather than of the protocol: the criterion is there
  under `## What would falsify it`, and the checker's denial test reads the sentence
  "needs no credential, no running app and no browser." across the heading boundary as
  a disclaimer that swallows it. The protocol cannot be edited to dodge that - the
  order rule is what makes a prediction older than its results, and E4b's own P03
  pins the committed text by hash - so the warn stands and is recorded here. The
  literature index's three rows record one record per source: they are primary
  documents (a standard, a vendor's documentation, repositories) with no second
  bibliographic record to check them against, and a mirror of the same document is
  not counted as one; each row's `quality` field now says so.
- Automated scoring was a cross-check only, and it was wrong in both directions: the
  judgement model mis-read one bundled row and one pass row, and the second independent
  re-score found the first re-score's rule had counted findings but not matrix cells. Both
  are reported, and the rule is committed beside the score.

## What would change the conclusion

- E3's matrices failing to beat 4 of 9 on this feature, or beating it only by adding
  false positives - or a fourth rater per arm inverting the artifact-versus-rubric ordering
  that three passes per arm now show.
- A second feature or stack where the same classes are found by the unmatrixed
  method.
- A repository where a capability registry (a `admin-crud-coverage`-shaped artifact)
  already covers the surface, which would make the capability matrix redundant
  there.
