# E1 - defect corpus (the measuring instrument)

## What changes

Nothing in the repository. This experiment builds and freezes the instrument every
later experiment is scored against: a list of defect instances that actually exist
on one real feature, each tagged with one of ten classes.

Feature: the users area of `/Users/rizax/Projects/Ustam`, app `apps/admin`, route
`(dashboard)/users`. Read at HEAD, and driven at runtime where the app can be
started.

## Method

1. Read the feature end to end: the route and its components, the server
   actions / API routes they call, the authorization layer those routes consult,
   and the database schema behind them. Every claim carries a `path:line`.
2. Drive the running app: enumerate the actions the UI offers, attempt the ones a
   non-privileged actor should be denied, exercise the search/typeahead control,
   and walk any multi-step flow to its last step. Where a step cannot be driven
   because the app cannot be started or no credential exists, that is recorded as
   not-driven rather than as a pass.
3. Emit one corpus row per defect: `id`, `class`, `where` (screen/endpoint/field),
   `statement`, `evidence` (`code` with `path:line`, or `ui-observed` with the
   tool call and the state read), `kind` (`failure` | `judgement`).
4. The ten classes are the ten the user reported (user-verbatim, 2026-09-20):
   C1 capability/CRUD permission not checked, C2 field-existence contract not
   checked, C3 list/detail/form inconsistency, C4 search/typeahead dropdown not
   checked, C5 state of other active fields after a search selection not checked,
   C6 wizard step prerequisites not checked, C7 an illogical form/infra structure
   never redesigned, C8 modern/smart form patterns never applied, C9 user-benefit
   UX not applied, C10 infrastructure never changed when the UI needs it.
5. Freeze: after this experiment the corpus file is not edited; `analysis.md`
   records its sha256.

## Predicts

Between 8 and 10 of the 10 classes yield at least one real defect instance on this
feature, and the corpus holds 12-30 instances, at least 6 of them evidenced by
running the app (`ui-observed`) rather than by reading source.

## What would falsify it

Fewer than 7 of the 10 classes yield an instance on this feature: the instrument is
too thin to measure the claim, and E2/E3 are then scored on a reduced class set
with that reduction reported. If the app cannot be started, the corpus is
code-scope only; that is recorded as a scope reduction, not as a falsification.

## Why

A detection claim needs a baseline from the same harness, and the harness is a
frozen corpus. Building it first, and freezing it, is what stops the later
comparison from being scored against classes invented after seeing the results.
