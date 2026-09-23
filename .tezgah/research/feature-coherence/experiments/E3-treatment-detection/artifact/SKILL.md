---
name: feature-audit
description: >
  Audit one feature across the layers it is spread over - the surface a person
  sees, the route that serves it, the authorization that gates it, the service
  that validates it, and the data that stores it - and produce the matrices that
  make a disagreement between those layers a finding. Use when the task is a
  feature, an admin panel, a CRUD screen, a form, a wizard, a search or picker
  control, a bulk action, or a "why does this not work / what is missing here"
  ask about an existing product surface, and when a UI improvement needs a
  capability the system does not have. The unit of analysis is the feature, not
  the screen: a screen-level review cannot see a capability that no surface
  reaches, a contract field that no form renders, or a step whose precondition
  nothing enforces.
---

# feature-audit

A screen review judges what is on the screen. Most of what goes wrong in a real
feature is not on the screen: it is a disagreement between two layers, or a
capability that exists on one side only. This skill names the matrices that make
those visible, so the audit reports them instead of taste.

It does not replace `product-analysis` (value, competition, triage) or
`analyze-app` (reading the running app). It is the layer-coherence pass those two
assume: run it on the one feature in scope, and feed its findings into their
axes.

## The unit

Pick **one feature**: one entity (a person, an order, a record) plus every action
a user can take on it, plus every screen and endpoint that carries those actions.
Write the boundary down: the entity, the actions, the screens, the endpoints, the
files. A feature that cannot be bounded this way is two features.

The surfaces in scope are **every interface element and every data view** - a form
control, a list or table, a detail view, a filter or facet, a picker, a step
indicator, a notification, a bulk action, an empty or error surface. Nothing here
is restricted to form fields: a table is audited to the same depth as an input,
and a data view's states are checked the same way a control's states are.

Everything below is a table. A table row is a claim about a layer, and a claim
carries a citation: `path:line` for code, the tool call and the state read for a
running app, URL and date for an external standard. **An absence needs the search
that proves it** - "no caller exists" must name the query and the paths it
covered, or it is a question, not a finding.

## Matrix 1 - capability

Rows are the entity's actions. Columns are the layers.

| Action | Surface (what a person can do) | Route | Authorization | Service / validation | Persistence |
|---|---|---|---|---|---|

Fill each cell with `yes` + citation, `no` + the search that shows it, or
`n/a` + why. Then read the disagreements:

- **Surface yes, a layer no**: the UI offers an action nothing backs. A dead
  control, or worse, an action enforced only in the browser.
- **A layer yes, surface no**: a capability the server has and no user can reach
  (dead endpoint, missing affordance, a detail view that exists in the contract
  but not in the product).
- **Route yes, authorization no**: a path with no policy on it.
- **Two routes for one action**: which one is dead, and which one carries the
  audit trail the product claims.
- **The layers agree**: record it as a pass row. A matrix that only lists defects
  cannot be told apart from a complaint list.

Read the sibling surfaces while filling this in: the repository's own convention
for the same kind of thing (how its other list pages paginate, how its other
mutations authorize, which framework primitive it uses for a picker) is the
strongest available standard, and a deviation from it is a finding with both
sides cited.

## Matrix 2 - field contract

Rows are fields; columns are the layers a field travels through.

| Field | Column / type | Read by the API | Written by the API | Rendered (list / detail / form) | Validated | Label or enum source | Locale / format |
|---|---|---|---|---|---|---|---|

Findings live in the gaps: a field the contract carries and no surface shows; a
field the form posts and no layer stores; the same enum labelled from two
sources; requiredness that one layer enforces and another does not; a free-text
stand-in for a value that is really a reference to another record; a format the
server localizes and the client re-formats.

## Matrix 3 - flow and step contract

For every multi-step flow (a wizard, a checkout-like sequence, a staged import):

| Step | Precondition (the state it requires) | What it validates | What it writes | How a skip is prevented | Resume / persistence | Back-navigation retention | Where an error lands |
|---|---|---|---|---|---|---|---|

The finding classes, in the order they hurt: a step reachable without its
precondition (by URL, by stored state, by a stale tab); no persistence, so a
reload loses the work; back-navigation that keeps the values it should discard or
discards the ones it should keep; an error mapped to the wrong step, or to the
whole flow rather than the field.

Enforcement location is part of the row: a precondition enforced only in the
client is not enforced. Say which side checks it.

## Matrix 4 - interaction dependency

For every control whose change alters what another control may hold (a search
that repopulates a picker, a selector that narrows a dependent list, a mode that
invalidates fields):

| Trigger | Dependents | Required action on change | Who owns the state | What is announced |
|---|---|---|---|---|

`Required action` is one of *reset*, *recompute*, *revalidate*, *keep*. The
findings, each decidable:

- a dependent value left stale after the set of valid values changed;
- a silent reset of a value the user chose (data lost with no message - the state
  node must say what changed);
- an unannounced change to a region that assistive technology is not watching;
- no cascade where the contract requires one (the server refuses the combination
  the form still offers).

## Matrix 5 - surface pattern: controls and data views

Per surface type - control, data view, or notification - the named pattern and
what its violation looks like. Cite the standard, not a preference: WAI-ARIA APG
for the combobox/listbox/dialog/table patterns, WCAG 2.2 for the criteria named
below, the platform's own design guidance for the rest.

**Data views come first, not last.** A list or table is where an operator spends
the day, and it answers a different question than a form does: does this view
survive the data it will actually hold? Fill one row per data view with every
state, and a state that does not exist is a finding:

| Data view | empty | loading / skeleton | error | permission-denied | many rows / pagination boundary | long or truncated text | partial / stale | offline |
|---|---|---|---|---|---|---|---|---|

Then the rows that a form-only audit never reaches:

| Surface | The pattern | Violation (examples from real audits) |
|---|---|---|
| List / table | the row's identity, its column set, and the same entity rendered consistently across list, detail and form | an in-memory filter over a fetched page presented as search; a service that returns a pagination envelope it never computes; a column the API carries and the table never shows; a second status field contradicting the first |
| Selection / bulk action | the selection survives the filter, the scope of the action is stated, the count is announced | a bulk action whose target set changes silently when the filter changes |
| Data view chrome | sort, pagination, sticky header, dense rows, focus order, reflow at 320px | a table that cannot be read without horizontal scrolling at 320 CSS px (WCAG 2.2 SC 1.4.10) |
| Notification / status | one live region per outcome, `role=status` for progress and `role=alert` for failure, never both | a change announced nowhere, so assistive technology never learns the action had an effect |
| Step indicator | current step exposed programmatically, unavailable steps explained | a disabled step with no reason, reachable only by guessing |
| Detail view | every field the contract holds has a home, and its history/audit is reachable | a record detail endpoint with no screen, so the list row is the only surface |
| Combobox / typeahead | APG combobox: `role=combobox`, `aria-expanded`, `aria-controls`, `aria-activedescendant`, arrow-key navigation, a listbox popup, a live result count, a no-results message | results rendered as a separate `<select>`; no expanded state; no count announced; keyboard cannot reach a result |
| Text input collecting a person's own data | WCAG 2.2 SC 1.3.5: an `autocomplete` token | no token, while a sibling form in the same app sets one |
| Search / filter | the count is announced; the query is server-side when the list is paginated, or the limitation is stated | in-memory filtering of a fetched page presented as search; Turkish-lowercasing only, no diacritic folding |
| Destructive action | the confirmation names what will be lost, not only what will be set | "replace all roles" confirmed with the new role visible and the removed roles invisible |
| Default value | a default that grants access or spends money is called out and chosen, not inherited from the first list item | a role preselected because it happens to be assignable |
| Structured value | a value with a known set is a selector, not free text | categories typed as a comma-separated string, validated only as non-empty |
| Error handling | WCAG 2.2 SC 3.3.1/3.3.3: an error summary, the message beside the field, and the field's programmatic association | computed validation text never rendered (or rendered with no `aria-describedby`) |
| Redundant entry | WCAG 2.2 SC 3.3.7: do not ask twice | the same value asked in two steps of one flow |

A violated pattern is a finding only with its context and the alternative named:
the same source says a violated heuristic is not automatically a problem.

## The capability-change proposal

A finding whose fix names a layer that does not exist yet is not a UI finding,
and it may not be reported as one. Emit a proposal:

| Field | What goes in it |
|---|---|
| Capability | the thing the surface needs, in one sentence |
| Serves | the finding id it answers |
| Missing seam | endpoint / query shape / policy key / column / index / validation / shared primitive - the specific layer and the file that would host it |
| Mechanism | how it is added: a new route, a new query parameter, an expand/contract migration, a backfill, a design-system primitive |
| Rollout | flag or phase, what is behind it, the rollback |
| Data | what existing rows need, and what happens to rows that fail the new rule |
| Verification | the check that proves it works - a request and its expected status, a rendered state, a test |
| Owner | who decides, and the metric that says it worked |

The rule that makes this a finding and not a suggestion: **if the fix list for a
finding names no layer that already exists, the proposal is required** - the audit
does not ship a screen-level recommendation for a capability that is absent.

## Coverage, not just findings

The artifact states, per matrix, how many rows were checked and how many could
not be (no credential, no running app, no data in that state), and what would
change the conclusion. A matrix section that is silently missing reads as a
covered one - the same defect as a screenshot saved and never read.

## Discipline

- **Three passes minimum, from different entry points** (a first-time user of the
  admin, the operator who does it daily, the API client with no UI). One rater is
  never a measurement; report how many passes ran.
- **Read the running app where it runs.** Source reading proves a layer exists; it
  does not prove the surface behaves. State which findings came from a reading
  and which from an exercised action.
- **Pass rows are part of the result.** Agreement between layers is the control
  that shows the matrix was filled honestly.
- **No finding without a named standard or a cross-layer disagreement.** "This
  feels cluttered" is a question.
- **Nothing here is a UI opinion**: the deliverable is the matrices, the
  disagreements, and the proposals, most severe first.

## Where this comes from

The matrices are the method; the standards they check against are cited in the
table above (WAI-ARIA APG, WCAG 2.2, the platform guidance). The related skills:
`product-analysis` (the five axes this feeds), `analyze-app` (how a running
surface is read), `research` (where the artifact lives), `intended-vs-implemented`
(documentation against code - this skill compares code against code).
