# E10 - the competition axis: result

## What ran

One pass, per the protocol: state the comparison basis first, then read comparable
products' own documentation at first hand, then compare. Seven products were read on
2026-09-21, each with its URL:

| Product | Document read |
|---|---|
| Keycloak 26.7.4 | server administration guide, users |
| ZITADEL | Console users documentation |
| authentik | Invitations |
| Clerk | Invitations |
| WorkOS AuthKit | Invitations |
| Supabase | `admin.inviteUserByEmail` |
| Google Workspace | add an account for a new user |

Two candidate pages returned 404 and are recorded as `not read` rather than
paraphrased (ZITADEL's invite-user guide, authentik's invitation flow example).

## Outcome against the prediction

Both halves hit: seven products were readable at first hand, and all seven deliver an
invitation credential through the product itself.

| Axis | The seven products | The two audited surfaces |
|---|---|---|
| Credential delivery | in-product in all seven (invite mail, invite link, or a one-time code) | **neither**: a random password is hashed and discarded, and no channel carries it |
| Forced first-login change | standard | absent |
| Invitation as a lifecycle object | a record with states (pending/expired/revoked) | absent - the account is created ACTIVE |
| Revocation reaching sessions | tokens/refresh revoked on disable | Ustam revokes sessions and device tokens; aibim does not |
| SCIM provisioning | three of seven document it | absent in both |
| Email verification on accept | standard | absent |

Gaps the other way (where the audited surfaces are ahead or different): Ustam's
transactional session-and-device revoke on deactivate is more thorough than several
of the seven; aibim's two-step create-then-activate is a deliberate difference rather
than a defect.

## Why this matters to the line

The axis is no longer a missing section. It converts one class of finding - the
invitation with no delivery path, which every arm on both features reported at
severity 4 - from an internal inconsistency into a **market gap with external
evidence**, which is what the rubric asks for and what a triage decision needs.

## Limits

- Documentation is not the product: a capability the docs do not state is `not read`,
  never absent, and no demo was driven, so every competitor fact is `external` by
  documentation and none is `behaviour`.
- The comparison basis is a small one (grant/revoke steps, list density, the
  read/write contract, in-product delivery); a different basis would rank the seven
  differently.
- Two protocol candidates (Okta, Azure Entra) were skipped for time and named in the
  artifact's `not looked at` list.
