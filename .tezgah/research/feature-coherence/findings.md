# Findings - feature coherence

Question: *what makes an AI product/feature analysis miss cross-layer coherence
defects (infrastructure capability <-> data contract <-> UI state <-> flow), and
what artifact plus mechanism closes it?*

Line: `.tezgah/research/feature-coherence/`. Instrument: 15 frozen defect rows in
ten classes on one real feature (`E1-defect-corpus/results.jsonl`, sha256
`70871644e095372e6e9a5faa5fa761d8dee60c87e82eaca33d5dd857a938d1a6`), plus two rows
the runtime pass added (`E1b-runtime-probe/results.jsonl`). One feature means one
stack (Next.js server components + NestJS + Prisma) and one organisation's data:
every number below is about that feature.

## What we know

- **The shipped rubric reaches four of the nine in-scope classes, and the matrices
  reach seven.** Three independent raters ran `product-analysis` plus `analyze-app` over the
  same feature and produced 14, 13 and 14 findings. The union reached C1
  (capability), C3 (list convention), C4 (search, half of it) and C7 (data-view
  layout). Five further raters then ran the feature-audit
  artifact: their union reached seven - adding the field contract (`locale` with no
  surface, the missing `autocomplete` token), the destructive-confirmation class, and
  decisively the capability-change class, where the baseline wrote **0 proposals** and
  the treatment wrote **5**, each naming the seam, a contract delta, a rollout with a
  flag, a verification that fails before and passes after, and an ADR. C6 was out of
  scope for both arms, so the honest denominator is nine classes: 4/9 baseline, 7/9
  treatment. Per-rater classes: 2/3/3 baseline (median 3), 5/6/5/4/4 treatment (median 5).
- **Nine of the thirteen defect rows are invisible from the screen alone.** D01 and
  D02 are a capability the server has and no surface reaches, D03 a contract field
  with no surface, D05/D06/D10 need a sibling convention or the API family read
  before the deviation exists, D14 the absence of an artifact slot. Each requires
  comparing two layers, which is the unit of analysis the rubric never names.
- **Running the app settles some rows and cannot settle others.** E1b confirmed the
  field-contract and announcement rows at runtime (live DOM, live geometry: the
  table is 1140 px wide inside a 242 / 686 / 924 px container at 320 / 768 / 1280)
  and falsified its own prediction that the capability rows were settleable there:
  the admin calls the API from the Next server, so the browser's request log for
  `/users` holds exactly one entry. A capability claim needs the server's log, a
  proxy, or the code.
- **The capability rows are mechanical once two artifacts meet.** Comparing the
  API's committed contract (337 paths) against the surface's call sites reported
  `GET /users/{id}` and `POST /users/{id}/deactivate` as declared-and-unreached, and
  nothing surface-only, in 3.09 s with no credential and no running app (E4b).
- **No rater produced a capability-change proposal.** All three artifacts end in UI
  and copy recommendations for defects whose fix needs a layer that does not exist
  (a server-side search, a paginated list, a detail aggregate, an autocomplete
  convention, a combobox primitive). The artifact list they were following has no
  element for one, which is D14 measured rather than argued.
- **Two raters added classes the corpus did not hold**: an invite whose only
  offered role the service refuses, and an invited account with no usable delivery
  path (a random password, a push to a device that cannot exist yet, the mail
  provider disabled). The corpus is a floor on what is findable, not the truth.

- **The probe is a convenience, not the mechanism.** E4 compared the artifact with and
  without a mandatory contract-vs-call-site probe: arm B (2 raters, probe run in both)
  reached six classes, arm A (5 raters, no probe instruction) seven, and the class the
  probe was expected to add was already reached by every rater in both arms. H4 is not
  supported: the matrices force the comparison, the probe makes the row cheap and
  re-runnable (1.81 s, no credential, exit 0). The one-class gap is rater variance of
  the size the baseline arm already showed within one arm.
- **With enough passes, the artifact leads the pre-wiring rubric on both stacks - thinly
  - and the wiring leads everything.** Six passes on the first feature put the artifact arm
  at 7 defect classes against the pre-wiring rubric's 6 (per-artifact rows 8/7/6 against
  4/6/4, independently scored). On the second stack the same comparison is 6 against 4.
  But the *post-wiring* axis skill alone reaches 6 there, above the artifact's 5, because
  `product-analysis` now carries the coherence pass. So the ordering that survives the
  extra passes is: wiring (a class or two), artifact over the pre-wiring rubric (one
  class), and rater diligence moving any single reading by up to three classes.
- **The proposal slot is a property the artifact requires, and a rubric without the slot
  skips the naming, not the thought.** Every artifact that follows `feature-audit` wrote at
  least one capability-change proposal - 14 of 14, recounted with the count standard and the
  borderlines written down (`experiments/E8-more-passes/proposal-tally.md`) - against 2 of 5
  that followed the pre-wiring rubric under a heading-only reading and 3 of 5 under a content
  reading. `E8-B1` is the case that keeps the claim honest: it proposes the same absent
  layers under a recommendations heading and says why. What the artifact buys is the slot and
  the rejectable artifact the slot demands, not the ability to notice the missing layer.
- **A false row manufactures agreement.** E7 prompted two raters with the create path;
  both traced it and both contradicted the corpus row the C8 class rested on - the
  handler validates and refuses, it does not default its way to a successful create.
  The row was withdrawn and replaced (`E5-transfer/corpus-correction.md`), and the
  class is findable when the path is named.

- **An independent re-score found two errors the session could not see.** It recovered
  the second corpus from git after a results write had overwritten it, and its two-tier
  rule (a finding or a named section, versus that plus a matrix cell) changed two arm
  totals: on the second stack the pre-wiring rubric scores 4 of 6 and the artifact 6,
  and the post-wiring axis skill alone scores 6 against the artifact's 5. So the wiring
  moves detection and the artifact's marginal value is still not established - but the
  transfer is confirmed rather than falsified, which is the opposite of what the
  session's first score said.
- **The two "unreachable" evidence classes were looked for the wrong way.** E11 read
  the source and found a wired, disabled analytics seam in both products (noop sink,
  default-off switch, consent false, and in Ustam's admin no caller ever passes
  `enabled`) plus real user-voice sources (support tickets and messages, a
  customer-portal free-text request). So `behaviour` is reachable as an audit-derived
  ratio today and as a funnel once the consent path is fixed, and `user-verbatim` was
  empty because no arm looked. The empty class was a finding about the analysis, and
  the dark instrumentation is the same defect class the matrices exist to catch -
  a layer that exists and nothing reaches.
- **The competition axis is no longer missing.** Seven comparable products read at
  first hand, all seven delivering an invitation credential in-product: the invitation
  with no delivery path, which every arm on both features rated severity 4, is a market
  gap with external evidence, not only an internal inconsistency.

- **A pass row is hard to leave alone.** Four of six first-feature artifacts reported a
  defect where the UI and the server agree, and the session's own judgement model did the
  same: a corpus of defects cannot show whether an analysis can tell agreement from drift.

## Patterns

- **The unit of analysis decides what is findable** [C01] [literature/existing-audit-art.md] - a method whose unit is the screen
  can still find a screen defect and cannot express a layer disagreement; every
  audit artifact surveyed at one layer boundary each (spec-to-spec, spec-to-store,
  surface-to-rule) is the same limit, and nine of this line's thirteen defect rows
  are invisible from the screen alone.
- **An absence needs the search that proves it** [C04] [literature/infra-change-path.md] - "no caller exists" is a finding
  only with the query and the paths it covered; with a contract document to diff
  against, it becomes a command that reports two declared-and-unreached endpoints.
- **Prose cannot be rejected; an artifact can** [C07] [literature/infra-change-path.md]: every
  mechanism that makes a missing capability a fact - a compatibility checker, a
  typed flag with a lifetime, an ADR with a status - is an artifact some tool other
  than its author can fail, which is why the skill's proposal section requires one.
- **Reading and running are two instruments with different blind spots** [C03] [literature/rule-base.md]: the reading found declared-and-unreached endpoints the browser's request log could
  not see (one entry for `/users`), and the running app found a layout and a
  casefold defect the reading had no reason to doubt.

## Lessons

- **A capability row needs a server-side instrument.** The runtime arm's own
  prediction failed for a reason worth keeping: a server-rendered surface hides its
  outbound calls from the browser, so "the UI does not call it" is unprovable from
  the UI side.
- **Bundled rows resist automated scoring.** A row that names two defects at once
  (a search with no typeahead *and* no diacritic folding) reads as "not detected"
  to a judgement model when a rater found one half. Rows should carry one defect, or
  the scorer must adjudicate the halves by hand.
- **A pass row is part of the instrument.** Two of the fifteen rows record
  agreement between layers (D09's server-side step gate, D15's matching
  platform-owner refusal). They are what lets a reader tell the matrices from a
  complaint list, and the judgement model mis-scored both of them.
- **A second feature does not behave like the first, and that is the finding.** The
  transfer arm missed a class the first feature's arm reached (C8's silent defaults
  went past all four raters) and reached one the corpus did not hold. A class split
  measured once is a hypothesis about a feature, not a property of analysis.
- **A held row is not a frozen row.** The C2 row had to be narrowed after WCAG 2.2
  SC 1.3.5 was read at source: the criterion is scoped to fields collecting *the
  user's own* information, so the finding moved from the invite dialog (a third
  party's data) to the public application form. The correction was committed before
  any rater output was read, and the corpus file itself was never edited.

## Open questions

- Does the matrices arm hold at six of nine on a second feature, or is part of the
  gain specific to this stack? One feature is one data point, and the treatment arm
  ran with two raters rather than the three the method asks for.
- Would a second stack (a server-rendered PHP/Rails admin, a mobile client) hold the
  same class split, or is part of it Next.js-specific?
- Is the `Prevent` line invented here worth its place, or does it duplicate the
  existing test-debt record? Both treatment artifacts wrote one per finding, so the
  cost is measurable and the value is not yet.
