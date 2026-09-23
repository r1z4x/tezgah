# E11 - are the two empty evidence classes reachable: result

## What ran

One pass over both audited repositories looking for the sources that would produce the
`behaviour` and `user-verbatim` classes, with `path:line` for each.

## Outcome against the prediction

**Both halves of the prediction are falsified.** The prediction was that both
repositories carry audit logs while analytics is absent from both, so `behaviour` is
reachable only as an audit-derived count and `user-verbatim` from nothing. What the
read found instead:

- **Analytics exists in both repositories and is dark.** Ustam's seam is real and
  wired into the users area (`apps/api/src/observability/api-observability-runtime.ts:13-17`,
  reached from `apps/admin/app/(dashboard)/users/page.tsx:8`), but the sink is a
  `NoopObservabilitySink` (`packages/domain/src/observability.ts:67-70`), the switch
  defaults to `disabled` (`packages/config/src/index.ts:336`), product signals are
  gated on `consent.analytics` which is `false` (`apps/admin/lib/observability.ts:36-39`),
  and the admin client never passes `enabled` outside a test
  (`apps/admin/lib/observability-runtime.ts:9-12`; the only caller that sets it is
  `observability.test.ts:9`). So the users area emits `create.started`,
  `create.completed`, `workflow.transitioned` and `api.request` into a client that
  discards them, and no configuration can turn it on from where it is constructed.
  The defect is **dark instrumentation**, not missing instrumentation - a finding no
  arm of this line had, because every arm reported "no analytics" from the absence of
  a numbers source rather than from reading the seam.
- **A `user-verbatim` source exists in both.** Ustam carries support tickets and
  messages (`apps/api/prisma/schema.prisma:2754-2815`, endpoints in
  `support.controller.ts:41-96`) and a customer-portal free-text request; aibim
  likewise. The class was empty because no arm looked, not because the product has no
  user voice - with the caveat the pass itself records: `SupportMessage.authorUserId`
  is a platform `User`, so a quote's provenance has to be stated carefully.

What the prediction got right: the audit-log table is the behaviour proxy
(`schema.prisma:3432-3447` gives count-per-action-per-actor-per-window), and it cannot
produce a funnel - no session or screen id, no sequence, and no retention job (the
`retentionPolicy` Json field at `schema.prisma:1029` has no reader outside generated
Prisma, and `auditLog.deleteMany` appears only in test cleanup). The one funnel-shaped
counter in the repository is campaign interactions
(`schema.prisma:2987-3008`), and it stops at the click.

## What this changes in the line

- **Two classes stop being "structurally unreachable" and become "looked for the wrong
  way".** Ten arms said "no analytics" and one pass found a wired, disabled seam. The
  correct statement is: `behaviour` is reachable as an audit-derived ratio today, and
  as a funnel only after the consent and sink path is fixed - which is itself a
  capability-change proposal.
- **It adds a finding to the fix's own case**: an instrumentation seam that cannot be
  enabled at its call site is the same defect class the feature-audit matrices exist to
  catch (a layer that exists and nothing reaches), found here on the *measurement* layer
  instead of the product.

## Limits

- Source reading only: no repository was run, so nothing here is `behaviour` or
  `ui-observed`.
- The support-ticket channel's provenance rule (who may author a message) is recorded
  as a question with the check that settles it, not as a claim.
