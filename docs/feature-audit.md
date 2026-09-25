# Feature audit: one feature, every layer

Audience: the agent and the maintainer answering "why does this screen do that"
or "make this feature better" on an existing product surface.

A screen review judges what is on the screen. Most of what goes wrong in a real
feature is not on the screen: it is a disagreement between two layers - the surface
a person uses, the route that serves it, the authorization that gates it, the
service that validates it, the data that stores it - or a capability that exists on
one side only. This page is the method that makes those visible, the evidence that
it works, and how to run it.

## What ships

`skills/feature-audit/SKILL.md` is the method: five matrices filled before any
taste judgement, a capability-change proposal required whenever a fix names a layer
that does not exist, a `Prevent` line per finding, and a per-surface rule table
sourced to WAI-ARIA APG and WCAG 2.2.

It is reached the same way `product-analysis` is: the `product` task class arms the
rule (`hooks/tezgah_context.py:67`), whose coherence paragraph
(`hooks/tezgah_policy.py:775-776`) names the feature unit and the matrices, and
`skills/product-analysis/SKILL.md:50` runs the coherence pass before its axes.
`skills/tezgah-contract/SKILL.md:591` carries the long form for a session that
reads the contract.

The unit is the feature, not the screen, and every interface element and every data
view is in scope - a control, a list or table, a detail view, a filter, a picker, a
step flow, a notification. It is not a form-only method.

## The five matrices

| Matrix | Rows | Columns | The defect it exposes |
|---|---|---|---|
| Capability | the entity's actions | surface, route, authorization, service, persistence | an action the UI offers and nothing backs; a capability the server has and no surface reaches; two routes for one action |
| Field contract | the fields | column, API read, API write, rendered, validated, label source, locale | a contract field no view renders; a view field no layer stores; two sources for one enum; two fields printing one word |
| Flow and step | the steps of a multi-step flow | precondition, validation, write, skip prevention, resume, back-navigation, error landing | a step reachable without its precondition; work lost on reload; an error mapped to the wrong step |
| Interaction dependency | the controls whose change alters another's valid set | dependents, required action on change, state owner, announcement | a stale dependent value; a silent reset; a filter showing a state the view no longer has |
| Surface pattern | the controls, data views, flows and notifications | the decidable rule, with its source | a combobox with no expanded state; a results count announced nowhere; a destructive confirmation that hides what it destroys |

## The gate that makes it more than advice

A finding whose fix names a layer that does not exist yet is not a UI finding. It
becomes a capability-change proposal, and the proposal must carry **an artifact
something other than its author can reject**: a contract, permission or schema diff
a checker can fail on, a flag with a type and an expiry, an ADR with a status.
Prose cannot be rejected by a tool, so a proposal without one is not yet a proposal.

Measured, this is mechanical: comparing the API's committed contract against the
surface's call sites reproduced two "declared and unreached" endpoints in one
pipeline, in 3.09 s, with no credential and no running app
(`.tezgah/research/feature-coherence/experiments/E4b-static-probe/results.jsonl`).

## What the evidence says

Measured on a real Next.js admin users area, 15 frozen defect rows across ten
classes, against three independent rater passes of the shipped `product-analysis`
rubric, then three passes of the feature-audit skill:

- the shipped rubric reached **4 of the 9 in-scope classes** (capability, list
  convention, search behaviour partly, table layout); its misses are the
  field-contract, flow/step, interaction-dependency, form-pattern,
  destructive-confirmation and capability-change classes;
- the feature-audit artifact reached **7 of 9**, added the field contract and the
  destructive-confirmation content, and wrote **5 capability-change proposals** where
  the baseline wrote none - the difference that matters most, because it is not about
  detection;
- both arms found, and the matrices name, what a screen review reads as taste: a
  table 1140 px wide inside a 242 px container at 320 CSS px, a search that misses
  Turkish casefolded names, a role select whose only option the service refuses;
- two rows were reachable **only** by running the app, and two others only by
  reading the server side - which is why the method names both, and why the browser
  request log alone is not an instrument for a capability claim
  (`.tezgah/research/feature-coherence/findings.md`);
- on a **second stack** (a Rust axum + React admin users area, code-scope) the
  measurement was repeated twice: once against the current axis skill and once
  against the **pre-wiring rubric extracted from history**, and both pairs came out
  level (5 of 6 against 4, then 4 against 4). Detection moved with the rater, not with
  the artifact, so the class count is not what this file buys;
- what reproduced, on both stacks, is the **proposal slot**: every artifact that follows
  this file wrote at least one capability-change proposal - 14 of 14, recounted in
  `experiments/E8-more-passes/proposal-tally.md` - against 2 of 5 that followed the
  pre-wiring rubric under a heading-only reading (3 of 5 by content, one of them proposing
  the same absent layers under a recommendations heading). The proposal is required here and optional there,
  which is the difference the evidence supports - not that the other rubric's users never
  think of one. There is also a thin detection lead with enough passes: 7 defect classes
  against 6 on the first feature, 6 against 4 on the second. That, plus
  the depth it carries - the per-surface rule table with its sources, the eight
  hand-checks, the proposal headings and their falsifiers - is the claim this page
  makes. The matrices are the unit of analysis, and on this evidence the unit changes
  what an analysis writes down more reliably than it changes what a diligent rater
  finds;
- the second stack was also **run**: after a docker bridge the surface rendered with
  real data and produced 13 `ui-observed` rows plus the layout class - the table clips
  its columns at 320 and, with a long row, at 768, with `overflow-x: hidden` and no rule
  declaring `auto`, so the clipped columns are unreachable rather than scrollable. The
  repository's own `make admin-dev` never reaches that surface: its frontend crash-loops
  on an nginx upstream the dev composition does not start - the same defect class as the
  product findings, found in the tooling;
- the **competition axis** the earlier runs declared missing is now produced: seven
  comparable products read at first hand, all seven delivering an invitation credential
  in-product, which turns the "invitation with no delivery path" finding from an internal
  inconsistency into a market gap with external evidence;
- the two evidence classes every run declared unreachable - `behaviour` and
  `user-verbatim` - were **looked for wrongly, not unreachable**: both products carry a
  wired analytics seam that is dark (noop sink, switch default off, consent false, and in
  the first product no caller ever passes `enabled`), and both carry real user-voice
  sources (support tickets and messages, a customer-portal free-text request);
  `behaviour` is reachable today as an audit-derived ratio and as a funnel only after that
  consent path is fixed;
- one corpus row was **false and is withdrawn**: E7's prompted raters traced the
  create path and showed the handler returns 400 rather than defaulting its way to a
  successful create (`.tezgah/research/feature-coherence/experiments/E5-transfer/corpus-correction.md`).

## Running it

1. Bound the feature: one entity, its actions, the screens and endpoints that carry
   them. Write the boundary down.
2. Fill the five matrices, every cell with its citation and its coverage marker.
   Run the app for the rows a reading cannot settle, and name which rows those were.
3. Turn a disagreement into a finding, most severe first, each with its evidence
   class and its `Prevent` line.
4. For every fix that needs a layer which does not exist, write the proposal and
   the rejectable artifact it carries.
5. Hand the result to the axes in `product-analysis` - the matrices are its
   feasibility evidence, and its surface patterns fill the usability state matrix.

## Source of truth

- `skills/feature-audit/SKILL.md` - the method: the five matrices, the proposal
  gate, the per-surface rule table and the hand-check list
- `skills/product-analysis/SKILL.md` - the coherence pass and the artifact element
  that carries the matrices
- `hooks/tezgah_context.py` - `PROMPT_HINTS`, whose `product` alternation carries
  the feature-surface words that arm the rule
- `hooks/tezgah_policy.py` - the coherence paragraph inside the product rule, and
  `skills/tezgah-contract/SKILL.md` as its long form
- `.tezgah/research/feature-coherence/` - the corpus, the protocols, the
  measurements and `to_human/report.md`
- `tests/test_context.py`, `tests/test_setup.py` - the arming table and the router
  line that pin the wiring
