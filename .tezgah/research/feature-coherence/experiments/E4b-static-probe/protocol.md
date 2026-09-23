# E4b - the static capability probe

## What changes

Nothing. E4 (the two-arm rater ablation) is reported as not-run: it needs four more
rater contexts, and the mechanism it was meant to isolate can be tested more
cheaply and more directly on the artefact it was invented for.

## Method

The capability matrix's third disagreement class is "a layer yes, surface no" - a
capability the server has and no user can reach. E1's reading answered it by hand
(D01, D02); E1b showed the browser's request log cannot see it at all, because the
admin calls the API from the Next server. This experiment tests whether a **static,
runnable** probe answers it instead, using only artifacts both sides already ship:

1. The API's own contract document: `docs/openapi.json` in the audited repository.
2. The surface's call sites: every literal path the admin app passes to its API
   client (`adminApi(...)` and the fetch wrappers around it).

Then the set difference, in both directions: endpoints no surface reaches, and
surface calls no endpoint declares. The probe is a shell pipeline over the two
artifacts, committed with its output.

## Predicts

The probe reports at least one endpoint under the users entity that no surface
call reaches - the `POST /users/{id}/deactivate` row E1 found by reading - and at
least one surface call that the contract does not declare, or states plainly that
there is none. It runs in under a second and needs no credential, no running app
and no browser.

## What would falsify it

The probe finding no difference at all where E1's reading found both rows: the
static comparison is not sufficient for the capability matrix, and the matrix's
"layer yes, surface no" column must name a server-side probe (a running API with a
credential, or the server's access log) instead.

## Why

The rule this tests is the one the audit's own proposal section carries: a claim
becomes mechanical when it rests on an artifact something other than its author can
reject. A contract document plus a call-site list is such a pair, and it is what
turns "no caller exists" from an assertion into a check anyone can re-run.
