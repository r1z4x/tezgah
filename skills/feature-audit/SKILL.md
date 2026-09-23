---
name: feature-audit
description: >
  Audit one feature across every layer it is spread over - the surfaces a person
  uses (a form control, a list or table, a detail view, a filter, a picker, a step
  flow, a notification), the route that serves it, the authorization that gates
  it, the service that validates it, and the data that stores it - and produce the
  matrices that turn a disagreement between those layers into a finding. Use when
  the task is about one existing feature rather than the whole product: an admin
  panel, a CRUD screen, a form, a wizard or step flow, a search or picker control,
  a data table, a bulk action, a permission surface, or a "why does this not work
  / what is missing here / make this better" ask, and whenever a UI improvement
  needs a capability the system does not have. The unit of analysis is the
  feature, not the screen: a screen-level review cannot see a capability no
  surface reaches, a contract field no view renders, or a step whose precondition
  nothing enforces.
---

# feature-audit

A screen review judges what is on the screen. Most of what goes wrong in a real
feature is not on the screen: it is a disagreement between two layers, or a
capability that exists on one side only. This skill names the matrices that make
those visible, so the audit reports them instead of taste.

It does not replace `product-analysis` (value, competition, triage) or
`analyze-app` (reading the running app). It is the layer-coherence pass those two
assume: run it on the one feature in scope and feed its findings into their axes.

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
that proves it**: "no caller exists" must name the query and the paths it covered,
or it is a question, not a finding. A cell you could not check is marked
`[NOT CHECKED: reason]` and stays in the table - an omitted cell reads as a
checked one.

## Matrix 1 - capability

Rows are the entity's actions. Columns are the layers.

| Action | Surface (what a person can do) | Route | Authorization | Service / validation | Persistence |
|---|---|---|---|---|---|

Each cell: `yes` + citation, `no` + the search that shows it, or `n/a` + why. Then
read the disagreements:

- **Surface yes, a layer no**: the UI offers an action nothing backs - a dead
  control, or an action enforced only in the browser.
- **A layer yes, surface no**: a capability the server has and no user can reach
  (a dead endpoint, a missing affordance, a detail endpoint with no detail view, a
  branch no account can enter).
- **Route yes, authorization no**: a path with no policy on it.
- **Two routes for one action**: which one is dead, and which carries the audit
  trail the product claims.
- **An offer the system forbids**: a control offering a value the same codebase
  refuses - a role select whose only option the service rejects is a dead feature,
  not a validation nit.
- **The end of the action**: for every create/invite/assign, what the recipient
  actually receives (a credential, a mail, a device push). An action whose output
  has no delivery path succeeded in the database and failed the user.
- **The layers agree**: a pass row. A matrix that only lists defects cannot be
  told apart from a complaint list.

Read the sibling surfaces while filling this in: the repository's own convention
for the same kind of thing - how its other list pages paginate, how its other
mutations authorize, which primitive it uses for a picker - is the strongest
available standard, and a deviation with both sides cited is a finding.

## Matrix 2 - field contract

Rows are fields; columns are the layers a field travels through.

| Field | Column / type | Read by the API | Written by the API | Rendered (list / detail / form) | Validated | Label or enum source | Locale / format |
|---|---|---|---|---|---|---|---|

Findings live in the gaps: a field the contract carries and no surface shows; a
field a view renders and no layer stores; one enum labelled from two sources; two
different fields printing the same word in one row; requiredness one layer
enforces and another does not; free text standing in for a value that is really a
reference to another record; a format the server localizes and the client
re-formats.

## Matrix 3 - flow and step contract

For every multi-step flow (a wizard, a staged import, a multi-part create):

| Step | Precondition (the state it requires) | What it validates | What it writes | How a skip is prevented | Resume / persistence | Back-navigation retention | Where an error lands |
|---|---|---|---|---|---|---|---|

Finding classes, in the order they hurt: a step reachable without its precondition
(by URL, by stored state, by a stale tab) - and the URL that names a step the page
does not render; no persistence, so a reload loses the work; back-navigation that
keeps what it should discard or discards what it should keep; an error mapped to
the wrong step, or to the whole flow instead of the field. Say which side enforces
each precondition: a check that lives only in the client is not enforced.

## Matrix 4 - interaction dependency

For every control whose change alters what another control may hold (a search that
repopulates a picker, a selector that narrows a dependent list, a mode that
invalidates fields):

| Trigger | Dependents | Required action on change | Who owns the state | What is announced |
|---|---|---|---|---|

`Required action` is one of *reset*, *recompute*, *revalidate*, *keep*. The
findings, each decidable:

- a dependent value left stale after the set of valid values changed;
- a value the user chose silently discarded (nothing announces it);
- **a control still showing a state the view no longer has** - the filter select
  that reads "Pasif" after the list was cleared, because the navigation did not
  reset it;
- a change to a region assistive technology is not watching, announced nowhere;
- no cascade where the contract requires one - the server refuses a combination
  the form still offers.

## Matrix 5 - surface pattern: controls, data views, flows, notifications

Per surface, the decidable rule. Sources are listed at the end; `APG x` is the
WAI-ARIA Authoring Practices pattern, `SC n.n.n` a WCAG 2.2 success criterion.
**Data views come first, not last** - a list or table is where an operator spends
the day, and it answers a different question than a form does.

### Data views

| Rule | What a violation looks like |
|---|---|
| SC 1.3.1: table headers are real headers (`th`/`scope` or `columnheader`) and the table is labelled | a div grid standing in for a table; bold cells as headers; no caption or accessible name |
| `aria-sort` on the sorted column, and activating a sorted header reverses it | no sort indication; a sort that cannot be reversed; a colour-only indicator |
| Cells that are editable or contain widgets make it a **grid** (one tab stop, arrow-key cell navigation, Enter/F2 to edit), not a table of tab stops | 40 per-row controls each in the tab order |
| Large or lazily loaded data sets `aria-rowcount`/`aria-colcount`, and returning from a detail view restores the position | a virtualized table announcing "row 3 of 3"; Back landing at the top |
| SC 1.4.10: the page scrolls in one direction at 320 CSS px, with the data table inside its own scroll container | a page-level horizontal scrollbar; the table meeting the two-dimensional exception while the surrounding text fails with it |
| Pagination marks the current page (`aria-current="page"`) in a labelled nav, and a one-page pager is hidden | unlabelled page numbers; a pager for a single page; an endless feed with no reachable footer |
| Content: captions and headings describe the data, headings are short nouns, the first column is a human-readable identifier, headers stay visible while scrolling | the first column showing `8f3c-…`, nothing telling the operator what the row *is* |
| Filters are discoverable and their active state is visible in the results view | a filtered list indistinguishable from an unfiltered one; a filter state that survives a "clear" |
| Detail view: key/value pairs (`dl`), every field showing a value or an explicit "not provided" | stacked headings; a field silently omitted |
| A scroll region says it scrolls (affordance, or no clipping at the widths measured) | the last column cut mid-word with no fade, no scrollbar and no hint that content exists |
| Long text has a strategy: truncation with a way to see the whole value, or wrapping | a 74-character address stretching the table to 2029 px inside a 924 px region |

### Controls

| Rule | What a violation looks like |
|---|---|
| `APG combobox`: `role=combobox`, `aria-expanded` tracking the popup, `aria-controls`, `aria-haspopup` matching the popup role, `aria-autocomplete` matching real behaviour | a styled input with a plain `div` popup; `aria-expanded` always true; results in a separate `<select>` |
| `APG combobox` keyboard: Down opens and enters the popup, Escape closes and returns focus, Enter accepts, the popup stays out of the Tab order, focus stays on the combobox with `aria-activedescendant` naming the option | Tab walking every suggestion; Escape doing nothing; DOM focus leaving the input |
| `APG listbox`: options are `role=option` owned by a listbox, selection via `aria-selected` **or** `aria-checked` (never both), multi-select `aria-multiselectable`, single choice as radios, the whole item shows selection | clickable `div` rows with no roles; only the checkbox highlight changing |
| A row carrying its own controls is a grid/table, not a listbox | options containing links, unreachable to a screen-reader user |
| Visible persistent label (never a placeholder as label), instructions where the format is not customary, a counter where a length limit exists | placeholder-only fields; a date field with no format hint |
| SC 1.3.5, scoped: an `autocomplete` token on fields collecting **the user's own** information (technique H98), and `off` or absent on search, filter and record fields that are not | a self-data field with no token, or a search box claiming `autocomplete="name"` |
| One required/optional convention across the product (mark optional, or asterisk every required field and explain it) | mixed conventions; an unexplained asterisk |
| `APG disclosure`: a show/hide control is `role=button` with `aria-expanded` | a styled link toggling content with no expanded state |
| `APG tabs`: `tablist`/`tab`/`tabpanel`, `aria-selected` only on the active tab, `aria-controls`/`aria-labelledby`, Left/Right and Home/End | clickable divs; `aria-selected` on every tab; Tab moving between tabs |
| A conditional reveal reveals a *question*, not help text, and announces that it appeared | a revealed question with no announcement (a known SC 4.1.2 failure) |
| Pickers: text entry alongside the calendar, no calendar for distant dates, a combobox where free text plus a known list is needed | calendar-only date of birth; a free-text country field |
| SC 2.5.8 target size: 24x24 CSS px minimum, or undersized with a 24 px clear circle; the design system's own touch floor where higher | 16 px icon buttons packed in a toolbar row |
| SC 2.4.7 focus visible, or SC 1.4.11 non-text contrast for the indicator: reachable by keyboard, visible, never time-limited | `outline: none` with a faint colour change |
| SC 1.4.3 contrast 4.5:1 (3:1 large) and no state signalled by colour alone | grey placeholder at 3.2:1; a red-only required or error marker |

### Validation and errors

| Rule | What a violation looks like |
|---|---|
| Validation on submit, not on blur; failing values kept; server-side validation present; native validation suppressed (`novalidate`) | errors appearing as the user tabs away; the field cleared; client-only validation |
| SC 3.3.1/3.3.3: the item in error is identified and the correction described in text | a red border only; "Invalid input"; the form re-displayed with no message |
| Association: `aria-describedby` to the message, the same wording in the summary and beside the field, and a summary entry that moves focus to its field | inline wording differing from the summary; focus staying at the top |
| An error summary at the top of the form naming what went wrong and linking each item to its field | errors existing only beside fields the user cannot see |

### Flows

| Rule | What a violation looks like |
|---|---|
| One question per page (or one group under a statement heading), a unique heading per step, a back link and a Continue button | four unrelated questions on one page; the same heading on every step |
| Check-your-answers: pre-populated on return, a Change link per section whose hidden text names what it changes, a submit that names its action | blank fields on return; a generic "Submit" |
| Task list: each task's status in text, the link's description reaching hint and status | status as a coloured dot only |
| SC 3.3.7 redundant entry: already-given information is auto-populated or offered, not asked again | the same value asked in two steps of one flow |
| SC 3.3.4: a submission that deletes data, changes stored data or creates a commitment is reversible, checked, or confirmed | delete with no undo, no review, no confirmation |
| Destructive confirmation names what will be lost (the value or record at stake), keeps its actions inside the panel, and is reserved for the irreversible | "Are you sure?" with no object named; the pattern used for ordinary branch points |
| `APG dialog`: `aria-modal` only when outside content is inert for every user and visually obscured, focus moves in on open and stays, focus returns to the invoker, an `alertdialog` focuses the least destructive action | `aria-modal` on a panel you can tab out of; focus landing on "Delete"; no dimming between two stacked layers |

### Notifications

| Rule | What a violation looks like |
|---|---|
| SC 4.1.3: a change the page makes without moving focus is programmatically determinable - the result count after a filter, "saved", "3 items" | results updating silently; the count only visually near the table |
| The whole status string is the announced unit, and the end of a wait is announced | the screen reader hearing only "three"; a spinner vanishing with no "loaded" |
| Changes that are not status messages (a validation error inside a focused dialog, a disclosure opening) stay out of live regions | every field announcing as it validates |
| A notification banner is `role=region` with a label (or `role=alert` with focus when reporting success), sits before the h1, at most one per page, never stands in for validation errors | a banner above the header; two banners; a banner replacing an error summary |

## The capability-change proposal

A finding whose fix names a layer that does not exist yet is not a UI finding, and
it may not be reported as one. Emit a proposal, and give every heading its evidence
class and its falsifier:

| Heading | What goes in it | Falsified by |
|---|---|---|
| Capability | the capability the surface needs, one sentence, no UI nouns | a cited code path that already delivers it |
| Absence proof | the `path:line` where the system cannot express it, and the input that fails | a cited path that handles that input |
| Contract delta | the machine-checkable artifact and its diff: the OpenAPI/SDL/proto change, the permission rule, the schema migration | running the compatibility checker and getting green with no diff |
| Migration | expand, migrate, contract, with the backfill rule and a dated contract step | a contract phase with no date |
| Rollout | flag name, type and expected lifetime, initial exposure, kill-switch owner, abort threshold and its window | an unmeasurable threshold, or a flag with no lifetime |
| Verification | the check that fails before and passes after, named by file or command | a check that also passes on the pre-change commit |
| Reversibility | what the new path writes, the exact restore step, or the plain sentence "one-way door, approval required" | data written with no restore step and no label |
| Decision | the ADR (context, decision, status, consequences) and what it supersedes | an ADR without a status |
| Appetite | the time box, what is out of bounds, and what happens when it ends | no box, or an implicit extension |

**The load-bearing rule: the proposal must carry an artifact something other than
its author can reject** - a spec, permission or schema diff a compatibility checker
can fail on (`buf breaking`, a contract test), a flag with a type and an expiry
(OpenFeature), an ADR with a status. Prose cannot be rejected by a tool, so a
proposal without one of those is not yet a proposal.

The rule that makes this a finding and not a suggestion: **if the fix list for a
finding names no layer that already exists, the proposal is required.** The audit
does not ship a screen-level recommendation for a capability that is absent.

A reviewer checks five absences: a capability claimed with no `code` finding behind
it; a proposal with no rejectable artifact; a schema-touching step with no migration
phases; a flag with no lifetime or owner; a contract change with no ADR and no
pre/post check pair.

## Every finding carries a Prevent line

A finding that only describes the defect will be met again next quarter. For each
one, name the cheapest thing that stops the family from returning - a lint rule, a
component-state checklist entry, an e2e assertion, a contract test, a schema
constraint - or say plainly that no mechanical prevention exists and this one stays
a review item. The assertion has to be the one that would have failed: an e2e check
of *document* overflow passes while the last column is clipped inside its own
scroll container.

## Coverage, not just findings

The artifact states, per matrix, how many rows were checked and how many could not
be (no credential, no running app, no data in that state), and what would change
the conclusion. A silently missing matrix section reads as a covered one - the same
defect as a screenshot saved and never read.

## Discipline

- **Three passes minimum, from different entry points** (a first-time user, the
  operator who does this daily, an API client with no UI). One rater is never a
  measurement; report how many passes ran.
- **Read the running app where it runs.** Source reading proves a layer exists; it
  does not prove the surface behaves. Say which findings came from a reading and
  which from an exercised action - and know the limit: a surface that renders on
  the server hides its capability calls from the browser's request log, so a
  capability row needs the server's own log, a proxy, or the code.
- **A screenshot is read, not saved.** Say which widths, which colour scheme, and
  what the tree could not answer.
- **Pass rows are part of the result**: agreement between layers is the control
  that shows the matrices were filled honestly.
- **No finding without a named standard or a cross-layer disagreement.** "This
  feels cluttered" is a question. A violated guideline is not automatically a
  problem: name the context and the alternative.
- **Nothing here is a UI opinion**: the deliverable is the matrices, the
  disagreements, and the proposals, most severe first.

## What cannot be checked mechanically

Run the automated sweeps where they exist (`analyze-app` wires axe-core and the
page measurements), then hand-check what they cannot see. axe-core's own figure is
about 57% of WCAG issues, and its rule set has **no rule** for SC 1.4.10, 2.4.7,
3.3.1, 3.3.3 or 4.1.3; the `target-size` rule exists but is **disabled by
default**. So these eight are hand-checks, never assumptions:

1. whether the error text identifies the error and suggests the fix (3.3.1/3.3.3);
2. whether a destructive confirmation names what is lost;
3. whether a status message carries enough context, and whether the end of a wait
   is announced (4.1.3 - no rule, and a tool cannot hear the announcement);
4. whether the focus indicator is actually visible on the real background (2.4.7);
5. whether the page really reflows at 320 px with the table exception contained
   (1.4.10 - measure, do not assume);
6. whether an autocomplete token fits the field's semantic purpose, and whether the
   field collects the user's own information at all;
7. whether an `aria-modal` dialog meets both preconditions, and where initial focus
   lands;
8. whether a conditionally revealed question is announced when it appears.

## What a run of this produced on a real feature

Measured on a Next.js admin users area (15 rows of defects, 10 classes): the
screen-level method reached 4 of the 10 classes across three independent raters,
while the layer matrices named the rest - the dead endpoint no surface calls, the
contract field no view renders, the in-memory list filter under a pagination
envelope nobody computes, the silent cascade reset, the wizard URL naming a step
the page does not render, and the confirmation that hides what it destroys. Two
classes were found only by running the app (a table 1140 px wide inside a 242 px
container at 320, and a search that misses Turkish casefolded names), which is why
the running-app half is not optional.

## Sources

Read at source 2026-09-20: WAI-ARIA APG patterns - combobox, listbox, dialog modal,
alertdialog, disclosure, tabs, table, grid (`https://www.w3.org/WAI/ARIA/apg/patterns/`);
WCAG 2.2 Understanding pages - 1.3.1, 1.3.5, 1.4.3, 1.4.10, 1.4.11, 2.4.7, 2.5.8,
3.3.1, 3.3.3, 3.3.4, 3.3.7, 4.1.3 (`https://www.w3.org/WAI/WCAG22/Understanding/`);
GOV.UK Design System - question pages, check answers, error message, error summary,
task list, table, summary list, pagination, notification banner, interruption pages
(`https://design-system.service.gov.uk/`; `one-thing-per-page` now resolves to
`patterns/question-pages/`). Grey, quoted for concrete rules only: Material 3
(`https://m3.material.io/`), Apple HIG (`https://developer.apple.com/design/human-interface-guidelines/`),
NN/g data tables and infinite scrolling. axe-core rule tags and the 57% figure:
`https://github.com/dequelabs/axe-core`.

Where the depth lives: `product-analysis` (the five axes this feeds), `analyze-app`
(how a running surface is read), `research` (where the artifact lives),
`intended-vs-implemented` (documentation against code - this skill compares layer
against layer).
