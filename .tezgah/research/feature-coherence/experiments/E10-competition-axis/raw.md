# E10 - competition axis: admin user management

Experiment: `experiments/E10-competition-axis/protocol.md`. Every prior arm of this
line recorded the competition axis as **not produced**. This is the axis.

Read date for every competitor page below: **2026-09-21** (local). Read method: the
product's own documentation page, fetched directly. No live demo was driven and no
account was created on any competitor, so every competitor fact is classed `external`
(documentation) and never `behaviour`/`ui-observed`. Audited-surface facts come from
reading the two repositories and are classed `code`; the two apps were not run in this
experiment.

## Comparison basis (stated once, before comparing)

The thing being compared is **one task**: an operator with administrative rights brings a
person into an organisation and later takes that access away, through the product's own
admin surface. Five axes fix the basis:

| Axis | Definition used here |
|---|---|
| **Grant steps** | The minimum number of distinct operator actions from "operator decides to grant" to "the grantee can authenticate", counting delivery of the credential as a step if the product does it. |
| **Revoke steps** | The minimum number of distinct operator actions from "operator decides to revoke" to "existing sessions/tokens cannot be used". |
| **List feature density** | The controls the user list itself offers: search/filter, pagination, bulk actions, per-row actions, columns shown. |
| **Read/write contract** | The HTTP surface the admin UI calls to read the list and to mutate a membership. |
| **Credential delivery in-product** | Whether the product itself carries the credential or an invitation token to the grantee (email or in-product link), versus leaving the operator to carry it out of band. |

Known limit of the basis: the competitor side is documentation, so a competitor
capability the docs do not state is recorded as `not read`, never as absent. The audited
side is code, so a behaviour not visible in the code read is recorded as unobserved.

## Product table

| # | Product (URL, read 2026-09-21) | How a user is created | How access changes | How it is revoked | What the product says about delivery |
|---|---|---|---|---|---|
| 1 | **Keycloak 26.7.4** Server Admin Guide - <https://www.keycloak.org/docs/latest/server_admin/> | Users → select user → **Credentials** tab → **Set Password**; **Temporary** ON means "the user must change the password at the first login". Users can also be created and imported from LDAP/AD (user federation). | **Role Mappings** tab → **Assign role**; groups inherit role mappings; composite roles. | **Delete** user from the action menu (profile and data deleted); manage user sessions; **Sign out all active sessions**; revocation policies (not-before) per realm/application/user. | Delivery is in-product. **Credential Reset → Update Password → Send Email**: "The sent email contains a link that directs the user to the Update Password window", link validity configurable. **Verify Email** required action. Temporary password + `UPDATE_PASSWORD` required action. SCIM: `not read` (the page documents LDAP/AD federation, not a SCIM endpoint). |
| 2 | **ZITADEL** Console Users - <https://zitadel.com/docs/guides/manage/console/users-overview> | Users → **New** → contact details → **Create**. Three authentication options: setup later / **"Send an invitation E-Mail for authentication setup and E-Mail verification"** / set an initial password. "After a user is created, by default, an initialization mail with a code is sent to the registered email." | Role assignments shown on the user profile; project roles; administrator roles (`ORG_OWNER`, `PROJECT_OWNER`); **External User Grants** invite a user from another organization into yours. | **`not read`** (this page states users cannot move between organizations but does not document a revoke procedure). | Delivery is in-product: initialization mail with a code verified on first login; invitation email; `password_change_required` flag on the create API ("Register and Create User", <https://zitadel.com/docs/guides/manage/user/reg-create-user>); passkey registration link can be sent by email. SCIM: `not read`. |
| 3 | **authentik** Invitations - <https://docs.goauthentik.io/users-sources/user/invitations> | **Directory → Invitations** → invitation wizard (with an existing enrollment flow or a new one). Enrollment happens when the grantee opens the invitation URL; a User Write stage creates the account. | Automatic group assignment via the enrollment flow's **User Write Stage** ("Create users group"); user paths; policy bindings decide who may enroll. | **`not read`** (this page documents invitation expiry and single-use, not user deactivation; a deactivation/offboarding feature appears in the 2026.8 release notes, which were not read). | Delivery is in-product: **Copy Link** or **Send via Email** (To/CC/BCC, template), sent asynchronously by a background worker; link format `…/if/flow/<slug>/?itoken=<uuid>`; **Expires** defaults to 48 h; **Single use** toggle; email must be configured first. SCIM: `not read`. |
| 4 | **Clerk** Inviting users - <https://clerk.com/docs/guides/users/inviting> | Create an invitation in the Dashboard **Invitations** page, or `createInvitation()` / `createInvitationBulk()` (Backend API `POST /v1/invitations`). The invited user signs up through the link. | Invitations are application-scoped; organization roles are a separate mechanism (`not read`). **Invite-only** access mode restricts sign-up to invited users. | **Revoke invitation** (Dashboard or `revokeInvitation()`). Stated caveat: "Revoking an invitation does not prevent the user from signing up on their own" unless invite-only mode is on. | Delivery is in-product: "Clerk sends an email to the invited user with a unique invitation link"; the email is auto-verified on acceptance; invitations expire after **a month**; rate limits 100/h (single) and 25/h (bulk). No forced password change is stated (sign-up is password/OTP based). SCIM: `not read`. |
| 5 | **WorkOS** AuthKit Invitations - <https://workos.com/docs/authkit/invitations> | Invitation API or WorkOS Dashboard; each invitation targets a specific email and (optionally) a specific organization. Accepting the link signs the user up and joins them to the organization. | Accepting an organization invitation adds the user as a member; for an already-signed-in user the invitation code is validated via the Invitation API; the invitee chooses to join (anti-phishing rationale). | **`not read`** (this page does not document revoking an invitation or a member). | Delivery is in-product: "an email is sent to the recipient with a link"; "By default, WorkOS sends these emails, but you can also send the emails yourself". Accepting shortly after send counts as **email verification** (`email_verified`). When signup is disabled, a valid invitation opens registration. Domain rules: consumer domains must match exactly, corporate domains may accept a same-domain address. SCIM: `not read` (WorkOS Directory Sync is a separate product page). |
| 6 | **Supabase Auth** `admin.inviteUserByEmail` - <https://supabase.com/docs/reference/javascript/auth-admin-inviteuserbyemail> | `supabase.auth.admin.inviteUserByEmail('email@example.com')` - one API call; the doc's whole description is "Sends an invite link to an email address". | **`not read`** (this reference page does not cover roles; `admin.createUser`/user-management roles are separate pages). | **`not read`**. | Delivery is in-product: an invite **link** is sent to the email address. No password, expiry, or forced-change statement on this page. SCIM: `not read`. |
| 7 | **Google Workspace** Add an account for a new user - <https://knowledge.workspace.google.com/admin/users/add-an-account-for-a-new-user> (page last updated 2026-09-18 UTC) | Admin console → Directory → Users → **Add new user** (first/last name, primary email, secondary email, optional OU/photo/password) → **Add New User**. Bulk via CSV ("Bulk update users"). | Administrator roles ("Make a user an admin"), organizational units, licensing; privilege definitions gate which controls the operator sees. | Suspend or archive; delete or remove a user (data transfer; restore within 20 days). | Delivery is in-product and explicit at step 6: **Copy Password** or **Preview And Send** (emails complete account details to a secondary/other address). The welcome email "includes a link to reset their password, which expires in **48 hours**". Email-verified variant: **Invite new user → Send invite**; **Pending invites** view with **Cancel invite**. SCIM: `not read` (this page covers CSV bulk, not auto-provisioning). |

## The two audited surfaces on the same basis

### Ustam - Next.js admin `(dashboard)/users` + NestJS `/users`

- **Grant**: one in-panel modal, `apps/admin/app/(dashboard)/users/page.tsx:76-140`
  ("Takım üyesi davet et"; fields Ad, E-posta, Rol, Kapsam). Action
  `apps/admin/app/(dashboard)/users/actions.ts:52-72` → `POST /users/invite`
  `{email, displayName, roleKey, scope}`. Server `apps/api/src/users/users.service.ts:113-176`
  creates the user with `passwordHash = hashPassword(randomInvitePassword())` (line 116;
  `randomInvitePassword` line 323), `status: 'ACTIVE'` (line 127), creates the membership
  and membershipRole, and emits `UserInvited` (line 172).
- **Access change**: `PATCH /users/:id` (`actions.ts:74-97`, `users.controller.ts:70`);
  a chosen role replaces all existing roles (`membershipRole.deleteMany` then create).
- **Revoke**: `active: false` calls `revokeMembershipAccess`
  (`users.service.ts:214/264/275`), which in the same transaction revokes device push
  tokens, refresh sessions (`revokeReason: 'USER_DEACTIVATED'`) and device activations.
  A separate `POST /users/:id/deactivate` exists (`users.controller.ts:82`); reactivation
  is a distinct operation. `SUPER_ADMIN` cannot be assigned from the panel
  (`actions.ts:61`, `users.service.ts:346`).
- **List density**: search `q` + membership `state` filter applied client-side over the
  full organisation list (`page.tsx:58-70`); no pagination in the contract
  (`page: {nextCursor: null, hasNextPage: false}`, `users.service.ts:64`); no bulk
  action; per-row "Erişimi düzenle" modal and a reactivate action.
- **Read/write contract**: `GET /users`, `GET /users/roles`, `GET /users/:id` (declared but
  unreached from the panel), `POST /users/invite`, `PATCH /users/:id`,
  `POST /users/:id/deactivate`.
- **Credential delivery in-product**: **none**. `randomInvitePassword()` is never returned
  or sent. The only invite signal is the outbox event `UserInvited`, mapped to a push
  notification "ServisTek daveti / Hesap ayrıntılarınızı görüntüleyin"
  (`apps/api/src/worker/push-notification.handler.ts:74`) - copy, not a credential. The
  account is created `ACTIVE` with a password no one can learn. The API's only email
  provider is `apps/api/src/auth/password-reset-email.provider.ts` (password reset).

### aibim-app - Rust axum admin backend + React `admin/frontend/src/pages/Users.tsx`

- **Grant**: modal "Create User" with Full Name, Email, **Password**, Role, Tenant
  (`Users.tsx`); `createUser` → `POST /api/v1/admin/users`
  (`admin/frontend/src/api/admin.ts:384`). Handler `admin_create_user`
  (`admin/backend/src/handlers/admin.rs:892`) requires a password the **operator types**
  (min 8, line 918), Argon2id-hashes it, and inserts with `is_active = false`
  (`db.rs:521 CREATE_INACTIVE`), returning "User created (inactive). Activate after
  approval." Activation is a second call, `admin_activate_user` (`admin.rs:989`,
  `POST /users/:id/activate`).
- **Access change**: `PUT /users/:id/role` (`admin.rs:789`) with
  `ADMIN_ASSIGNABLE_ROLES` (`admin.rs:873`); a non-`super_admin` cannot assign `admin`.
  Also `PUT /users/:id/permissions` (module RBAC) and `PUT /users/:id`.
- **Revoke**: `POST /users/:id/deactivate` (`admin.rs:835`); the SQL is
  `UPDATE users SET is_active = false` (`db.rs:515 DEACTIVATE`) - **sessions and tokens
  are not revoked**. The SCIM path (`admin.rs:5526`) is stronger: it also revokes
  delegated admin assignments (`revoke_reason = 'scim_deprovision'`, line 5612) and removes
  group-derived assignments (`scim_group_removed`, line 5810).
- **List density**: search + pagination in the contract
  (`admin_list_all_users`, `admin.rs:4394`, `?search&limit&offset`, `LIST_FILTERED` /
  `COUNT_FILTERED`, `db.rs:482-502`), but the UI calls `fetchUsers({limit: 200})` with no
  pager (`Users.tsx`, `api/admin.ts:374`); no bulk action.
- **Read/write contract**: `GET /api/v1/admin/users` (+`{id}`, `/permissions`),
  `POST /api/v1/admin/users`, `PUT /api/v1/admin/users/{id}[,/role,/permissions]`,
  `POST /api/v1/admin/users/{id}[/activate|/deactivate]`,
  `POST /api/v1/admin/enterprise-accounts/{id}/scim/users` (`main.rs:252-268, 284, 338, 499`).
- **Credential delivery in-product**: **none**. The operator-chosen password is never sent;
  there is no mailer in the admin backend. The SCIM path sets a random `Uuid::new_v4()`
  password that is never disclosed (`admin.rs:5680`). The wider aibim product does
  have self-serve invitations (`db/migrations/104_self_serve_memberships_invitations.sql`),
  but the **audited admin surface does not use it**.

## Gaps, each way

Every line names one evidence class and carries its citation. `external` = competitor
documentation; `code` = the two repositories read above.

### A. What the audited surfaces lack that the competitor baseline documents

1. **In-product invitation credential delivery** - all seven products deliver the grant
   credential or an invite token themselves; both audited surfaces carry none.
   `external` [rows 1-7 above] + `code` [`users.service.ts:116,323`;
   `admin.rs:892,918`; `admin.rs:5679`].
2. **A forced first-login credential change** - Keycloak's `Temporary` toggle forces
   `UPDATE_PASSWORD`; Zitadel exposes `password_change_required`. Ustam instead creates an
   already-`ACTIVE` account with an undisclosed password; aibim creates an inactive account
   with an operator-chosen password and no forced change. `external` + `code`
   [`users.service.ts:127`; `admin.rs:936`; `db.rs:521`].
3. **Invitation as a lifecycle object** - Google Workspace lists **Pending invites** and
   lets the operator **Cancel invite**; Clerk revokes an invitation; authentik gives the
   invitation an **expiry** and a **single-use** flag. Neither audited surface has an
   invitation record to list, expire, or cancel, because neither creates one.
   `external` + `code` [grep for an invitation model in `apps/api/src/users` and
   `admin/backend/src/handlers/admin.rs`: none].
4. **Revocation that reaches live sessions** - Keycloak documents **Sign out all active
   sessions** and per-user session revocation alongside disable/delete. aibim's deactivate
   is `is_active = false` only, so existing refresh tokens survive the revoke; Ustam's
   transaction (below) is the counter-example inside the audited pair.
   `external` + `code` [`db.rs:515 DEACTIVATE`; `users.service.ts:275-320`].
5. **SCIM as a documented bulk-provisioning path** - WorkOS Directory Sync and Google
   Workspace auto-provisioning treat SCIM as a first-class grant/revoke path. aibim has a
   SCIM user upsert but only at enterprise-account scope (`admin.rs:5526`), and Ustam has
   none. `external` + `code` [`main.rs:499`].
6. **Email verification as a by-product of accepting the invite** - WorkOS marks
   `email_verified`; Zitadel verifies by code; Clerk auto-verifies. Neither audited surface
   contacts the grantee at all, so no verification is possible. `external` + `code`.

### B. What the audited surfaces have that the competitor pages read do not state

7. **Deactivation that revokes device tokens and refresh sessions in one transaction** -
   Ustam's `revokeMembershipAccess` revokes push tokens, refresh sessions and device
   activations atomically with the membership flip. The Keycloak page documents session
   sign-out and revocation as separate admin actions, not as part of a per-user disable.
   `code` [`users.service.ts:275-320`] + `external` [row 1].
8. **Privileged-role guardrails on the panel** - Ustam refuses `SUPER_ADMIN` assignment
   from the panel and routes it to a provisioning flow; aibim refuses `admin`/`super_admin`
   for a non-`super_admin` and blocks delegated SCIM managers from reactivating a platform
   admin. Keycloak's Role Mappings tab lets the admin assign any role the admin's own
   permissions allow (fine-grained RBAC is out of the read). `code`
   [`users.service.ts:346`; `admin.rs:879`, `admin.rs:5662`] + `external` [row 1].
9. **Two-step grant (create inactive, then activate) as a governance step** - aibim
   requires a second call before the account can log in. The competitor pages read grant on
   create or on invitation acceptance. This is a shape difference, not a defect.
   `code` [`admin.rs:936,989`].
10. **Membership-scoped list rather than tenant-wide** - Ustam lists only the caller's
    organisation memberships and filters client-side; aibim lists every user across all
    tenants. Neither is better; the contracts differ and both matter for the axis. `code`
    [`users.service.ts:29-36`; `admin.rs:4394`].

## Prediction and falsification outcome

The protocol predicted: at least three comparable products readable at first hand, and at
least two delivering an invitation credential in-product. **Hit on both counts** - seven
products were read, seven deliver in-product. The falsification criterion (fewer than
three readable, or none showing a capability the audited surfaces lack) is **not
triggered**. The axis therefore lands as a finding with `external` evidence, not as a
missing section.

## Not looked at

- Candidates named in the protocol but **not read**: Okta admin docs; Azure Entra admin
  docs.
- Other comparable products not read at all: Auth0, Amazon Cognito, Firebase
  Authentication, Stytch, Descope, FusionAuth, Ory Kratos, Better Auth, SuperTokens,
  Casdoor.
- Competitor sub-capabilities left `not read` inside a product that was read: Keycloak
  SCIM extension; Zitadel SCIM API and user deactivation; WorkOS Directory Sync (SCIM);
  Clerk organizations/roles and invite-only mechanics; Supabase `admin.createUser` and
  role model; Google Workspace auto-provisioning (SCIM), privilege definitions, and
  restore/suspend procedures; authentik deactivation/offboarding (release notes).
- Audited-surface areas left unread: Ustam's `apps/mobile/src/features/users` (the second
  surface on the same API) and the password-reset email provider's internals; aibim's
  `GET /users/:id` and `/permissions` handler bodies, and the aibim **product** app's
  invitations (migration 104) which sit outside the audited admin surface.
- No live demo of any product was driven, and neither audited app was run - so no
  `behaviour` or `ui-observed` evidence exists in this axis; every competitor fact is
  documentation-only.

## Pages that could not be read (`not read`, not paraphrased)

| URL | Result |
|---|---|
| <https://zitadel.com/docs/guides/manage/user/invite-user> | HTTP 404 - `not read` |
| <https://docs.goauthentik.io/docs/flow/examples/invitation> | HTTP 404 (redirect target <https://docs.goauthentik.io/add-secure-apps/flows-stages/flow/examples/invitation> also 404) - `not read` |
