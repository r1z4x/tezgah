# feature-audit — Ustam admin, the users area (one feature, five layers)

Rater: `E3-raterA`. Artifact applied as written: `tezgah/skills/feature-audit/SKILL.md`
(read in full, including "The capability-change proposal", "Every finding carries a Prevent
line", "Coverage, not just findings", "Discipline", "What cannot be checked mechanically").

- Target: `/Users/rizax/Projects/Ustam`, commit `98f985f68d7064385b6eaeae7da8c4aa5636a6b5`,
  working tree clean. `path:line` citations are relative to that repo root, except that these
  short forms are used and each resolves under one fixed base:
  `page.tsx`, `actions.ts`, `user-labels.ts`, `page.test.tsx`, `actions.test.ts` →
  `apps/admin/app/(dashboard)/users/`; `components/*`, `lib/*`, `app/globals.css`,
  `app/(dashboard)/*.tsx` → `apps/admin/`; `users.controller.ts`, `users.service.ts`,
  `auth/*`, `common/*`, `devices/*`, `worker/*`, `notifications/*` → `apps/api/src/`;
  `prisma/*` → `apps/api/prisma/`; `domain/*` → `packages/domain/src/`; `OrganizationUsersScreen.tsx`,
  `organization-users-api.ts` → `apps/mobile/src/features/users/`. Every other citation is
  written in full. Every citation above was re-resolved against the tree after this document was written:
  each one names an existing file, and each line or range is inside that file (0 unresolved, 0
  out of range).
- Passes run: **5** (the artifact's minimum is 3) — see §0.4.
- No sibling rater artifact was read; no `E2-rater*`, `E3-rater*`, `.tezgah/research/`,
  Ustam `.tezgah/`, `docs/design/` or `plans/` content was opened. Screenshots exist in the
  scratch directory from other raters; none was opened, and no number below comes from one.
- One peer rater (`E3RaterB`) sent two signals after my first reading: a filter-state repro and a
  route to a live API pass. Both are labelled where they appear (F19, §0.4 pass 3) and both were
  reproduced here before being written down; the peer's screenshot is not cited and no number of
  theirs is reused. Their repro falsified a pass row I had already published in this document —
  the correction is recorded in F19 and §9 rather than silently applied.
- Nothing in the Ustam repository was modified. One running-app mutation attempt was made
  and it wrote nothing (verified against the database, §0.4 pass 2).

---

## 0. The unit

**Entity.** A *user of the platform organization* — the `User` row plus its one
`Membership` in the organization the panel session belongs to, plus that membership's
`MembershipRole` rows. (The surface calls this area "Yöneticiler" / *Administrators*;
`lib/admin-surfaces.ts:102-107`, `disposition: 'platform'`.)

**Actions a user can take on it** (the rows of Matrix 1): see the list; search it; filter it
by membership state; invite a person into the organization; change a member's role; change a
member's record scope; deactivate a membership; reactivate a membership; open the detail of
one user; deactivate through the dedicated endpoint; change the person's own name or locale.

**Screens / surfaces in scope.**
| Surface | Where | Kind |
|---|---|---|
| `/users` list + toolbar + count + empty surface | `app/(dashboard)/users/page.tsx` | data view + controls |
| "Kullanıcı listesi" scroll region + `<table>` | same, `page.tsx:167-291` | data view |
| Invite dialog (4 fields, submit) | same, `page.tsx:74-136` via `components/AdminModal.tsx` | step flow |
| Invite confirmation dialog | `components/ConfirmationDialog.tsx` (via `AdminActionForm` `confirmation`) | dialog |
| Per-row access dialog (role / scope / membership) | `page.tsx:222-279` | step flow |
| Per-row reactivate form | `page.tsx:204-221` | control |
| "Platform sahibi erişimi bu ekrandan değiştirilmez." cell | `page.tsx:206` | text state |
| Permission-denied surfaces (2) | `page.tsx:49-56`, `page.tsx:137-142` | permission state |
| Result notice after redirect | `components/MutationNotice.tsx` | notification |
| Loading frame for the segment | `app/(dashboard)/loading.tsx` | loading state |
| Error frame for the segment | `app/(dashboard)/error.tsx` | error state |

**Endpoints.** `GET /users`, `GET /users/roles`, `GET /users/:id`, `POST /users/invite`,
`PATCH /users/:id`, `POST /users/:id/deactivate` — `apps/api/src/users/users.controller.ts:34-88`;
all six are published in `docs/openapi.json` (operationIds `users-list`, `users-roles`,
`users-get`, `users-invite`, `users-update`, `users-deactivate`).

**Files (the feature's blast radius).**
`app/(dashboard)/users/{page.tsx,actions.ts,user-labels.ts}`, `components/{AdminActionForm,AdminModal,ConfirmationDialog,MutationNotice,PageHeader}.tsx`, `lib/{api,admin-context,mutations,mutation-guard,admin-error,admin-surfaces}.ts`, `app/globals.css`,
`apps/api/src/users/{users.controller.ts,users.service.ts,users.module.ts}`,
`apps/api/src/auth/admin-panel.guard.ts`, `apps/api/src/notifications/notification-event-mapper.ts`,
`apps/api/src/worker/push-notification.handler.ts`, `apps/api/src/auth/password-reset-email.provider.ts`,
`packages/domain/src/users.ts`, `apps/api/prisma/schema.prisma`, `apps/api/prisma/seed-role-permissions.ts`,
`docs/openapi.json`. Two sibling surfaces reach the same endpoints: `apps/mobile/src/features/users/*`
(a second, working surface for the same actions) and `apps/api/scripts/run-admin-playwright-e2e.mjs`
(the only end-to-end coverage).

### 0.1 The one configuration fact that decides most of this audit

The panel session is pinned to the **platform organization**
(`apps/api/src/auth/admin-panel.guard.ts:32-40`: membership in an organization with
`kind = 'PLATFORM'`, `status = 'ACTIVE'`, holding `SUPER_ADMIN`). `GET /users` and
`GET /users/roles` scope to `auth.organizationId` (`users.service.ts:26-33`, `:69-75`), so
the panel lists and offers **that organization's** members and roles only.

The shipped seed gives the platform organization exactly **one** role:

- `apps/api/prisma/seed-role-permissions.ts:66-71` — the only row with
  `organizationId: ids.platformOrganization` is `{ key: 'SUPER_ADMIN', name: 'Platform Sahibi' }`.
- Live database (`psql` against `apps/api/.env` `DATABASE_URL`):
  `select r.key, r.name from roles r join organizations o on o.id=r.organization_id where o.kind='PLATFORM'`
  → one row: `SUPER_ADMIN | Platform Sahibi`.
- Live database: `organizations.kind='PLATFORM'` has **1** membership, and `/users` returns
  **1** row in the running panel.

And that single role is refused by three separate layers (F1, §1.2).

### 0.2 Evidence classes and their sources in this run

| Class | What produced it here |
|---|---|
| `behaviour` | Actions driven in the running app (headless Chromium against the live dev stack on `localhost:3000` + `localhost:3001`) and their observed results |
| `ui-observed` | Rendered geometry, computed styles, focus order and contrast measured in that running document |
| `code` | `path:line` reads, the checked-in OpenAPI contract, and absence searches whose command is quoted |
| `external` | W3C APG / WCAG 2.2 Understanding / GOV.UK Design System, read at source 2026-09-20 (`SKILL.md` "Sources") |
| `user-verbatim` | **none available** — no user statement about this feature was in scope for this rater, so no finding carries this class |

### 0.3 What the automated sweep said

`axe-core 4.10.3` injected into the live `/users` document (the file
`.tezgah/scratch/feature-coherence/axe-4.10.3.min.js` was injected with
`page.evaluate((code) => (0, eval)(code))` and run with
`axe.run(document, { resultTypes: ['violations'], rules: { 'target-size': { enabled: true } } })`,
`target-size` enabled explicitly because it is off by default):

| State | Violations | Incomplete |
|---|---|---|
| settled list, light, 1440 | **0** | `color-contrast` |
| invite dialog open | **0** | `color-contrast` |
| confirmation dialog open (2 dialogs) | **0** | — |
| dark (`prefers-color-scheme: dark`) | **0** | `color-contrast` |
| 320 CSS px wide | **0** | `color-contrast` |
| empty result (`?q=zzz`) | **0** | `color-contrast`, `th-has-data-cells` |

So the surface is mechanically clean: **every finding below is a cross-layer disagreement,
not an axe hit.** `color-contrast` is incomplete because the tinted backgrounds are
`color-mix()` values axe cannot resolve — which is why the contrast cells in Matrix 5 were
hand-computed (§5.3).

### 0.4 The five passes

| # | Entry point | What it produced |
|---|---|---|
| 1 | First-time operator, browser, light, 1440×1000 | The screen as a stranger meets it: h1 `Yöneticiler`, 1 row, 7 columns; the invite dialog and **its only role option**; the filter controls; the count sentence |
| 2 | Daily operator, browser, keyboard + state churn by **click** (1440 and 320) | Tab order, dialog trap, Escape behaviour, filter combinations, empty state, a live invite attempt (no write), a bookmarked deep link that opens nothing, and the stale select after "Filtreleri temizle" (F19, two runs) |
| 3 | API client with no UI | **Live, at the API.** An `ADMIN` token was minted from a page on `localhost:3000` with `POST /api/v1/auth/admin/sign-in` (CORS-allowed, `bootstrap.ts:103`), then ten requests were issued from that page against `localhost:3001/api/v1`: `/me`, `GET /users`, `GET /users/roles`, `GET /users/{id}`, `GET /users/{unknown}`, `POST /users/invite` ×3, `POST /users/{unknown}/deactivate`, `GET /users`. Results: `me` 200 (50 permissions, `user.manage` included), `users` 200 with **1 row** and `page={"nextCursor":null,"hasNextPage":false}`, `users/roles` 200 = **`[{"key":"SUPER_ADMIN","name":"Platform Sahibi"}]`**, `users/{id}` 200 with `membership.roles=[{key,name}]`, `users/{unknown}` 404, invite `SUPER_ADMIN` → **403 `SUPER_ADMIN_PROVISIONING_REQUIRED`**, invite `TECHNICIAN` → **400 `ROLE_NOT_FOUND`**, invite an existing member → **400 `ALREADY_MEMBER`**, deactivate an unknown id → **404 `RESOURCE_NOT_FOUND`** (route mounted), and the list was **1 row before and 1 row after** (verified again in the database: 56 users, 0 rows for the probe addresses, 0 new memberships, 0 new audit rows — the invite transaction rolled back). **Correction to this document's first reading:** it claimed this pass was unreachable; that was wrong, and the corrected method is the one above |
| 4 | Measurement pass | Geometry at 1440 / 320 / dark, contrast ratios, target sizes, focus ring, axe at six states |
| 5 | Cross-layer read | page ↔ action ↔ controller ↔ service ↔ schema ↔ seed ↔ e2e fixture — this is where F2, F3, F4 and F8 came from |

Pass 2's mutation attempt: the invite dialog's only role (`SUPER_ADMIN`) was confirmed for
real. Result: the dialog rendered `role="alert"` with `Platform sahibi bu ekrandan atanamaz.`,
the URL stayed `/users` (no `?result=` redirect), and the database showed **56 users before
and 56 after**, with **0** rows matching the typed address — the action returned before any
API call, exactly as `actions.ts:61` says. No repository or application data was changed.

---

## 1. Matrix 1 — capability

Rows are the entity's actions; columns are the layers. `yes`/`no` each carry a citation;
`n/a` carries the reason.

| Action | Surface (what a person can do) | Route | Authorization | Service / validation | Persistence |
|---|---|---|---|---|---|
| List the organization's users | `yes` — one `<table>`, `page.tsx:167-291` (rendered: 1 row) | `yes` — `GET /users`, `users.controller.ts:34`; called at `page.tsx:58` | `yes` — `user.manage` (`users.controller.ts:35`) + panel session (`admin-panel.guard.ts`) + page gate `page.tsx:46-48` | `yes` — scoped to `auth.organizationId`, excludes `ARCHIVED` (`users.service.ts:26-33`) | `yes` — `prisma.user.findMany`, `users.service.ts:26-58` |
| Search the list by name/e-mail | `yes` — `name="q"` text input, `page.tsx:146-149` | **`no`** — `GET /users` declares `"parameters": []` in `docs/openapi.json`; no query string exists | `n/a` — no request is made; the filter runs in the page | `yes`(client) — `toLocaleLowerCase('tr-TR')` compare, `page.tsx:60-67` | `n/a` — nothing is written |
| Filter the list by membership state | `yes` — `name="state"` select, `page.tsx:151-158` | **`no`** — same: no contract parameter | `n/a` | `yes`(client) — `membership.active` predicate, `page.tsx:64-67` | `n/a` |
| Invite a person into the organization | `yes` — dialog `page.tsx:74-136`; **observed to fail**: its only role option is refused, and the API refuses every other key too (live: 403 for `SUPER_ADMIN`, 400 `ROLE_NOT_FOUND` for `TECHNICIAN`) | `yes` — `POST /users/invite`, `actions.ts:62`; live 403/400 responses | `yes` — `requireAdminMutation('team.invite')` → `user.manage` (`mutation-guard.ts`, `mutations.ts:29`), action-level `actions.ts:53` | `yes` — zod `InviteUserInput` in `actions.ts:55` and again in the pipe (`users.controller.ts:65`); service refuses `SUPER_ADMIN` (`users.service.ts:336-338`) | `yes` — user + membership + membershipRole in one transaction (`users.service.ts:118-159`); **unreachable with the shipped role set** |
| Change a member's role | `yes` for a normal member — `page.tsx:249-257`; not rendered for the only real row (`page.tsx:201-206`) | `yes` — `PATCH /users/:id`, `actions.ts:89` | `yes` — `team.update` → `user.manage` (`mutations.ts:33`) | `yes` — replaces every role row (`users.service.ts:223-232`), refuses `SUPER_ADMIN` targets | `yes` — `membershipRole.deleteMany` + `create` |
| Change a member's record scope | `yes` — same dialog, `page.tsx:259-270` | `yes` — same PATCH | `yes` — same | `yes` — zod enum (`packages/domain/src/users.ts:29`) | `yes` — `membership.update`, `users.service.ts:216-223` |
| Deactivate a membership | `yes` — "Pasif — erişimi kaldır" option, `page.tsx:271-277` | `yes` — `PATCH /users/:id {active:false}` | `yes` — same; service also refuses self (`users.service.ts:181-186`) | `yes` — must be the only field on an inactive membership (`users.service.ts:199-206`) | `yes` — writes `active:false`, then revokes sessions, device activations and push tokens (`users.service.ts:214`, `:275-305`) |
| Reactivate a membership | `yes` — "Yeniden etkinleştir", `page.tsx:207-221` | `yes` — `PATCH /users/:id {active:true}`, `actions.ts:80-82` | `yes` — same | `yes` — the reactivation-only rule makes exactly `{active:true}` legal | `yes` — `users.service.ts:206-213` |
| Deactivate through the dedicated endpoint | **`no`** — no caller anywhere (search below) | `yes` — `POST /users/:id/deactivate`, `users.controller.ts:82-88`; published as `users-deactivate`; **live 404** `RESOURCE_NOT_FOUND` for an unknown id, so the route is mounted and would act on a real one | `yes` — `user.manage` | `yes` — `setActive()`, `users.service.ts:246-273` | `yes` — same write as PATCH, plus a distinct audit action |
| Read one user's detail | **`no`** — no caller (search below); the list is the only data view | `yes` — `GET /users/:id`, `users.controller.ts:49-52`; published as `users-get`; **live 200** with `membership.roles=[{key,name}]` | `yes` — `user.manage` | `yes` — 404 when no membership (`users.service.ts:91-94`) | `n/a` — read only |
| Change the person's own name or locale | **`no`** — no control; the page states they are self-service (`page.tsx:164-165`) | `yes` in schema, refused on use (`packages/domain/src/users.ts:27-35`) | `yes` | **`no`** — `assertMembershipOnlyUpdate` always throws `GLOBAL_PROFILE_SELF_SERVICE_REQUIRED` (`users.service.ts:327-334`) | `no` — the request never reaches a write |
| Sort the list | **`no`** — no header control, no `aria-sort` (measured: 7 headers, `aria-sort` all `null`, 0 header buttons) | **`no`** — no sort parameter | `n/a` | `yes`(fixed) — server order `displayName asc`, `users.service.ts:47` | `n/a` |
| Page the list | **`no`** — the page does not even parse the envelope (`page.tsx:13-30` has no `page` key); **live** the response carries `page={"nextCursor":null,"hasNextPage":false}` for a 1-row organization, i.e. the surface cannot act on it either way | **`no`** — no cursor parameter | `n/a` | `yes`(fixed) — the envelope is a literal: `page: { nextCursor: null, hasNextPage: false }`, `users.service.ts:64` | `n/a` |

### 1.1 The absence searches (an absence needs the search that proves it)

1. **`POST /users/:id/deactivate` has no caller.**
   `grep -rn "users/[^\"]*deactivate\|/deactivate" --include=*.ts --include=*.tsx --include=*.mjs apps/admin apps/mobile apps/api/src packages scripts` (excluding `node_modules`, `generated`, `.next`, and the unrelated `push-token`/`devices` paths)
   → **one** hit: `apps/api/src/users/users.controller.ts:82` — the route's own decorator. No
   admin page, no mobile screen, no e2e file, no script calls it.
2. **`GET /users/:id` has no caller.** `grep -rn "adminApi(\`/users\|request(\`/users\|request('/users\|adminApi('/users" --include=*.ts --include=*.tsx apps`
   → 6 hits, all list/invite/PATCH: `page.tsx:58,59`, `actions.ts:62,89`,
   `organization-users-api.ts:39,47,56`. Nothing issues a GET of `/users/{id}`.
3. **Related surfaces agree on the same search**: the mobile client's only user calls are
   `/users`, `/users/invite` and `PATCH /users/:id` (`organization-users-api.ts:39-57`), and
   its role list is hardcoded, not fetched (`OrganizationUsersScreen.tsx:27-37`) — see F17.

### 1.2 Disagreements found in Matrix 1

Findings are numbered once here and ranked together with the other matrices in §6. Evidence
class, citation and Prevent line per finding.

#### F1 — the panel's only user-administration capability cannot complete, in any account
- **Evidence class:** `behaviour` (observed) with `code` citations.
- **Severity:** 4 (every operator, on the surface's main action, permanent until the data changes).
- **The disagreement.** Surface *yes* × Service *no* × Authorization *no* — the skill's "an
  offer the system forbids". `page.tsx:104-121` builds the role select from
  `GET /users/roles` (`page.tsx:59`), which is scoped to the session organization
  (`users.service.ts:69-75`) — the platform organization, whose only seeded role is
  `SUPER_ADMIN` (`prisma/seed-role-permissions.ts:63-71`; live `psql`: one row). `page.tsx:108-112`
  then defaults the select to `TECHNICIAN` if present, else the first role — i.e. to
  `SUPER_ADMIN`.
  Observed in the running app: the invite dialog's role select contains exactly one option,
  `SUPER_ADMIN | Platform sahibi`; confirming returns
  `Platform sahibi bu ekrandan atanamaz.` in a `role="alert"` region
  (`actions.ts:61` — before any API call). **All four layers were then exercised live** (§0.4
  pass 3): `GET /users/roles` answers `[{"key":"SUPER_ADMIN","name":"Platform Sahibi"}]`, so
  that one option is the whole offerable set; `POST /users/invite` with `SUPER_ADMIN` answers
  **403 `SUPER_ADMIN_PROVISIONING_REQUIRED`** (`users.service.ts:336-338`); and with a key the
  organization does not define (`TECHNICIAN`) it answers **400 `ROLE_NOT_FOUND`**
  (`users.service.ts:146-149`). **The invite's accepted input set is therefore empty**: the one
  role the panel can offer is refused, and every role the API would accept is one the
  organization does not define. The only input that gets a different answer is an address that
  is already a member (400 `ALREADY_MEMBER`), which is not a create.
  The same wall closes the second capability: the list's only row is a `SUPER_ADMIN`, and
  `page.tsx:206` replaces its edit control with a sentence, backed by
  `users.service.ts:340-342`. Search, filter and reactivate work; **create and update do not
  exist for any account on the shipped data.**
- **Contrast with the sibling surface:** the mobile app performs the *same* actions for a
  tenant organization and does work (`organization-users-api.ts:44-57`), because a tenant
  organization has assignable roles.
- **Prevent.** A unit/e2e assertion that the panel's **offerable role set, minus the roles
  the action and the service refuse, is non-empty** — run against the shipped seed, not the
  e2e fixture that rewrites the data (F2). This is the check that would have failed. A second
  half to the same assertion: every option value rendered by `page.tsx`'s role select must be
  accepted by `InviteUserInput` **and** not be refused by `actions.ts:61`. **This fix names a
  capability that does not exist** (an authorised path that can provision a platform
  administrator) → capability-change proposal **P1** (§7); the audit does not ship a
  screen-level recommendation for it.

#### F2 — the end-to-end coverage of this flow runs in a world the product never presents
- **Evidence class:** `code` (the fixture's own text).
- **Severity:** 4 (it hides F1; it is the reason F1 shipped green).
- **The disagreement.** `apps/api/scripts/run-admin-playwright-e2e.mjs:110-118` runs
  `UPDATE "organizations" SET "kind" = 'PLATFORM' WHERE "id" = '10000000-0000-4000-8000-000000000001'`
  — the **demo tenant** — with the fixture's own comment: "*the demo tenant also takes on the
  platform organization role in this fixture … the seed's own platform organization has no
  such data*". It then inserts a second `SUPER_ADMIN` role for that organization
  (`:119-126`, key `SUPER_ADMIN`, name `Platform Yöneticisi`). The demo tenant's seeded roles
  are `ORG_ADMIN` and `TECHNICIAN` (`prisma/seed-role-permissions.ts:40-52`; live `psql`
  confirms both), so in the e2e world the invite form offers `İşletme yöneticisi` and
  `Teknisyen` — and `e2e/admin-core-recovery.e2e.ts:20-34` selects `Teknisyen` by label and
  completes an invitation. **That journey cannot pass against the shipped configuration.**
  I did not run that suite (it builds an isolated database and a fault proxy; the shared dev
  API was in use by other raters) — the claim is about the fixture's content, which I read,
  plus the seed, which I read and queried.
- **Prevent.** A seed-parity contract test: assert that for the organization the panel
  session binds to, the assignable role set is non-empty and that the admin e2e fixture does
  not widen it (compare the fixture's role rows against the seed's for the same organization
  id). Cheapest mechanical form: a test over `prisma/seed-role-permissions.ts` +
  `run-admin-playwright-e2e.mjs`'s SQL asserting that no fixture adds a `kind` change or a
  role row to an organization the seed already defines.

#### F3 — the invitation's output has no delivery path: the person is never told
- **Evidence class:** `code`.
- **Severity:** 4 (the action's end, per the skill: "succeeded in the database and failed the user").
- **The disagreement.** `invite()` creates a user with a **random password hash the inviter
  never sees** (`users.service.ts:116`, `:323-325`) and emits
  `UserInvited` (`users.service.ts:168-174`). The event's only consumer is the push
  notification handler (`notifications/notification-event-mapper.ts:684-690`;
  `worker/push-notification.handler.ts:74,135`), whose recipient is the invited user's own
  device tokens — which a person who has just been created cannot have. There is no
  invitation e-mail: the repository's only outbound mail path is the *password reset*
  provider (`auth/password-reset-email.provider.ts:11-33`, Resend over `fetch`), it is
  restricted to `PASSWORD_RESET_EMAIL_PROVIDER === 'resend'` (`:9-11`), that setting defaults
  to `'disabled'` (`packages/config/src/index.ts:262`) and appears in no `.env` in the repo
  (only `.env.example`). The invitee cannot even know to use "forgot password", and the
  in-app consequence is the observed empty-state copy recommending this very action:
  `Eşleşen kullanıcı yok. Filtreleri temizleyin veya yeni takım üyesi davet edin.`
  (`page.tsx:289`, observed live).
- **Prevent.** An integration test asserting that `POST /users/invite` produces a delivery
  attempt for a user with **no** device tokens — i.e. that the outbox event has a
  recipient-independent path (the test fails today, because the only path is device-keyed).
  **This fix names a layer that does not exist** (an invitation delivery path) →
  capability-change proposal **P3** (§7).

#### F4 — two routes for one action; the dead one carries the audit name the live one loses
- **Evidence class:** `code` (the search that proves the absence in §1.1; corroborated live: the route answered 404 `RESOURCE_NOT_FOUND` for an unknown id, so it is mounted).
- **Severity:** 3 (the auditability of a security-relevant act, permanent).
- **The disagreement.** `PATCH /users/:id {active:false}` — the route the UI uses — records
  `action: 'user.update'` with `redactedDiff: { changed: ['active'] }`
  (`users.service.ts:234-241`). `POST /users/:id/deactivate` records
  `'user.deactivate'`/`'user.activate'` (`users.service.ts:265-271`) but has no caller in the
  repository (search 1 in §1.1). So the audit trail cannot answer *"who deactivated this
  member"* by action name — the fact is only inside a diff key list. Live database confirms
  the live path's naming: `select action, count(*) from audit_logs where action like 'user.%'`
  → `user.invite | 1`, `user.update | 1`, and **no** `user.deactivate` row.
- **Prevent.** A contract test over the service: deactivating a membership through
  `update()` must record `user.deactivate` (or the dead route must be removed and the
  naming fixed on the live one) — one assertion, both outcomes rejected by it. Cheap and
  mechanical: assert the audit action for each of deactivate/reactivate/role-change on the
  PATCH path.

#### F5 — the search and the filters are computed in the page; the contract cannot express them, and the list ignores the envelope its siblings honour
- **Evidence class:** `code`.
- **Severity:** 3 (every operator, grows with the organization, permanent).
- **The disagreement.** Three layers disagree about how a list is queried:
  `docs/openapi.json` `/api/v1/users` has `"parameters": []`; `page.tsx:58` fetches the whole
  collection and filters it in memory (`:60-67`); the response envelope says
  `{ nextCursor: null, hasNextPage: false }` as a **literal** (`users.service.ts:64`), i.e. the
  server reports "no next page" without asking the database; and `page.tsx:13-30` does not
  even parse `page`, so the envelope is not rendered. The repository's own convention for
  list surfaces is the opposite and is consistent: `work-orders/page.tsx:40,404-410`,
  `quotes/page.tsx:38,430-434` and `customers/page.tsx:34,97,402` all parse the envelope and
  render a cursor link. The sibling surfaces therefore also fix the *sample*: they paginate;
  this one cannot. Measured today the cost is invisible (1 row); the disagreement is in the
  layers, not in the pixel count.
- **Prevent.** A contract test that every list surface's response schema parses the `page`
  envelope **and** renders a control for `hasNextPage` (the users surface fails it today), plus
  an API test that `hasNextPage` is computed from a `take`/`count` rather than a literal.
  **The fix names layers that do not exist** (query parameters on the endpoint, a filter input
  in the service) → proposal **P2** (§7).

#### F6 — the row prints the same two words for two different fields, so one row can contradict itself
- **Evidence class:** `code` (with the live row's text as the shape being described).
- **Severity:** 3 (every operator, every row, permanent).
- **The disagreement.** Column *Durum* renders `userStatusLabels[user.status]`
  (`page.tsx:186-189`, `ACTIVE → 'Aktif'`), column *Üyelik* renders `membership.active ? 'Aktif' : 'Pasif'`
  (`page.tsx:200`), and the toolbar's *Üyelik durumu* select offers exactly `Aktif`/`Pasif`
  for `membership.active` (`page.tsx:61-67`, `:151-158`). Nothing in this feature ever writes
  `user.status` — deactivation writes only `membership.active`
  (`users.service.ts:206-213`) — so after "Pasif — erişimi kaldır" the row reads
  `Durum: Aktif` and `Üyelik: Pasif`. Live row text observed: `Platform Sahibi | platform@servistek.test | Aktif | … | Aktif`.
  A live database check shows the two fields are genuinely independent and currently
  divergent-capable: all 56 users are `status='ACTIVE'` while `memberships.active=false` is
  simply not yet represented (0 rows) — i.e. the contradiction needs no new code, only data.
- **Prevent.** One word per concept, mechanically held: a render test asserting that the
  *Durum* column's vocabulary is disjoint from the *Üyelik* column's (rename one of them —
  e.g. *Erişim* for the membership), or drop `user.status` from the row so only one status
  word can appear. The check that would have failed: assert the rendered row never contains
  two different status words for one user.

#### F7 — `userStatusLabels` labels a different enum than the API returns
- **Evidence class:** `code`.
- **Severity:** 2 (a wrong label map, one surface, latent).
- **The disagreement.** `app/(dashboard)/users/user-labels.ts:15-21` carries
  `ACTIVE, INVITED, SUSPENDED, DEACTIVATED, DELETED`. The database enum is
  `INVITED, ACTIVE, SUSPENDED, ARCHIVED` (`apps/api/prisma/schema.prisma:39-44`), and the list
  query excludes `ARCHIVED` (`users.service.ts:29`). So **two labels can never render**
  (`DEACTIVATED`, `DELETED`) and **the reachable enum member has no label** (it would print
  `ARCHIVED` through the `?? user.status` fallback if the exclusion were lifted). The private
  map also duplicates a job the shared module owns: `lib/admin-labels.ts` is imported by seven
  other surfaces, while `user-labels.ts` sits inside the users route folder and is imported
  **out of it** by two unrelated surfaces (`membership/page.tsx:7`, `announcements/campaign-model.ts:2`).
- **Prevent.** Type the map against the generated enum — `const userStatusLabels: Record<UserStatus, string>`
  — so an extra or missing key is a compile error, and move it to `lib/` beside `admin-labels.ts`.
  The check that would have failed: `tsc` on the current map (it cannot be typed as `Record<UserStatus,string>`
  without change).

#### F8 — a capability the server has and no surface reaches: the user detail
- **Evidence class:** `code` (the absence of a caller, §1.1 search 2; corroborated live: 200, with the shape below).
- **Severity:** 2 (dead capability, no user impact today, permanent until someone calls it).
- **The disagreement.** `GET /users/:id` is live, permission-guarded and published in the
  contract (`users.controller.ts:49-52`, `docs/openapi.json` `users-get`), returns roles as
  `{key,name}` objects and a 404 for a non-member (`users.service.ts:77-99`) — **exercised live,
  200 with `membership.roles=[{"key":"SUPER_ADMIN","name":"Platform Sahibi"}]`, 404 for an
  unknown id** — and no surface calls it (§1.1 search 2: 6 `/users` call sites, none a detail GET). There is no detail view
  in the admin app at all, and no dynamic admin route except the customer-portal token route
  (`find app -type d -name '[*]'` → `app/musteri/[token]` only), so this is not a repo-wide
  convention being followed elsewhere. Combined with the list rendering 6 of the response's
  fields (Matrix 2), the entity has a shape the panel never shows: `locale`, and the role
  **names** the server already sends.
- **Prevent.** Either render it (the fix lives entirely in layers that exist — the endpoint
  plus a section in `page.tsx`) or delete the operation and its contract entry; a contract
  test that every published operation has a caller in `apps/` (or a documented exemption)
  keeps the family from returning. No proposal is required: the fix names no missing layer.

#### F9 — the list is sorted with no indication and cannot be reversed
- **Evidence class:** `ui-observed` (running app) with `code` for the cause.
- **Severity:** 2 (every operator; grows with rows).
- **The disagreement.** The server orders by `displayName asc` (`users.service.ts:47`) and
  the surface renders plain `<th scope="col">` cells: measured on the live page, 7 headers
  with `aria-sort` all `null` and **0** header buttons or links. APG's table pattern and the
  artifact's own rule ("`aria-sort` on the sorted column, and activating a sorted header
  reverses it") both want the sort state exposed and reversible. The repository offers no
  sort anywhere in the admin app (`grep -rn "aria-sort" app components` → no match), so this
  is a product gap rather than a deviation from a sibling — stated as such.
- **Prevent.** A render test asserting an `aria-sort` value on the column the server orders by
  (it fails today), or add a sort control and the same assertion. Pick one; the assertion is
  the part that keeps it.

#### F10 — the permission-denied surfaces of this feature are unreachable by any account
- **Evidence class:** `code`.
- **Severity:** 1 (no user impact; a maintained branch that cannot run).
- **The disagreement.** Both locked surfaces (`page.tsx:49-56` for no permission at all,
  `page.tsx:137-142` for read-only) depend on `context.permissions` **not** containing
  `user.manage` (`page.tsx:46-48`, mapped from the same registry at `mutations.ts:29,33`). But
  the panel session proof requires a `SUPER_ADMIN` role and a `PLATFORM` organization
  (`lib/admin-panel-session.ts:8-14`, `admin-panel.guard.ts:32-40`), and `SUPER_ADMIN` holds
  every permission (`packages/domain/src/permissions.ts:88`: `SUPER_ADMIN: permissions`).
  So no account that can open the page can reach either branch — they exist only in unit
  fixtures (`page.test.tsx:76-104` mocks a permission set). `ORG_ADMIN` does hold
  `user.manage`, but an `ORG_ADMIN` can never hold a panel session.
- **Prevent.** Say which of the two it is: if the branch is future-proofing for a narrower
  panel role, assert the premise explicitly (a test that a panel session always holds
  `user.manage`, which fails the day that changes and thereby earns the branch); otherwise
  delete it. Leaving it unstated is what makes it weightless.

#### F11 — typed values are lost when the session expires mid-submit, and the 401 path says nothing
- **Evidence class:** `code`.
- **Severity:** 2 (rare but total for the operator in the dialog).
- **The disagreement.** `adminApi` turns a 401 into a redirect (`lib/api.ts:130-131`), and the
  server action rethrows it (`actions.ts:19` `unstable_rethrow` before the failure mapping).
  The dialog's values live only in the client form, so the operator is sent to session
  recovery with an empty dialog and no message; the form's own guard covers in-page failure
  (`components/AdminActionForm.tsx:198-206` renders the failure copy, its
  `beforeunload` guard at `:141-148` covers the tab, and neither covers a server-driven
  navigation). The product's copy claims otherwise for the in-page case only —
  `Bilgileriniz korundu` (`actions.ts:44-49`) — which is exactly the path that is not taken here.
- **Prevent.** An e2e assertion that a 401 raised while the invite dialog is filled preserves
  the entered values (or shows the failure copy) after the recovery hop. The fix uses layers
  that already exist (the form's own state), so no proposal is required, and the honest
  alternative is to accept the loss and say so in one line of copy.

#### F12 — the update contract offers two fields the service always refuses
- **Evidence class:** `code`.
- **Severity:** 2 (a published contract that cannot succeed).
- **The disagreement.** `UserUpdateInput` carries `displayName` and `locale`
  (`packages/domain/src/users.ts:27-35`), `PATCH /users/:id` validates them
  (`users.controller.ts:72-79`) and `update()` unconditionally throws
  `GLOBAL_PROFILE_SELF_SERVICE_REQUIRED` when either is present (`users.service.ts:327-334`).
  The panel page even explains the policy to the operator (`page.tsx:164-165`). Layers: route
  *yes*, service *no* — the mirror image of F1, and the same skill rule ("an offer the system
  forbids": here the offer is in the contract, not the screen).
- **Prevent.** Remove the two fields from `UserUpdateInput` (they are unreachable) and let the
  self-service endpoint own them, or gate them on the actor; the rejectable artifact is the
  contract itself — `pnpm test:api-contract` / `scripts/verify-api-contract.mjs`
  plus a test asserting every field of an input schema is accepted by its own service path.

#### F13 — a bookmarked deep link to another user's access dialog silently does nothing
- **Evidence class:** `ui-observed`.
- **Severity:** 1 (only for a bookmarked/shared URL).
- **The disagreement.** The per-row dialog publishes an anchor id
  (`page.tsx:225` `id={\`user-access-${user.id}\`}`) and `AdminModal` opens on a matching
  `location.hash` (`components/AdminModal.tsx:70-91`), which is a real, documented contract
  ("*Empty states and cross-page buttons still deep-link to a create action by anchor*",
  `AdminModal.tsx:68-74`). Observed: `GET /users#user-access-20000000-0000-4000-8000-000000000005`
  opened **0** dialogs and said nothing — the URL names a step the page does not render,
  because that row is the `SUPER_ADMIN` protected one (F1's second half).
- **Prevent.** No honest mechanical prevention exists today (there is nothing to assert while
  the row offers no action): this stays a **review item**. It becomes assertable the moment
  F1's proposal lands — then: for every rendered `#<id>` trigger, the hash opens that dialog,
  and a hash with no target produces a stated refusal rather than silence.

#### F14 — the surface's own accessibility evidence is not reproducible from the repository
- **Evidence class:** `code`.
- **Severity:** 2 (the verification layer, not the surface).
- **The disagreement.** Commit `0296a49` ("fix(admin): add missing h1 to the users surface")
  states "*axe-core scan after the change reports zero violations on /technical, /training,
  /announcements, /customers and /users*". There is no axe-core in the repository:
  `grep -rn "axe" --include=package.json .` (excluding `node_modules`, `.next`) → no match;
  `grep -c "axe-core" pnpm-lock.yaml` → **0**; no test file imports or runs it; and no
  accessibility e2e file mentions `/users` (`grep -rn "users" apps/admin/e2e/*.ts` → only
  `admin-core-recovery.e2e.ts` and `admin-state-recovery.e2e.ts`, neither an a11y assertion).
  My own run above had to borrow a copy of axe from another rater's scratch file. The claim
  is therefore true-or-not about a tool the repository cannot run, and the five surfaces it
  covers have no mechanical accessibility stop in CI. (The commits also show the surface's
  h1 being added and then reverted the same evening, `0296a49` → `98f985f`; the running page
  has exactly one `h1`, `Yöneticiler`, which is correct.)
- **Prevent.** Add the scanner as a dev dependency with a spec that runs it on the five
  surfaces (then the commit's claim is a command), or stop asserting the scan in commit
  messages. This is the one finding whose fix is a one-line dependency plus a test file.

#### F15 — the dialog's close control is below the design system's own touch floor
- **Evidence class:** `ui-observed`.
- **Severity:** 1 (frequent, tiny, permanent).
- **The disagreement.** Measured inside the open dialog: `.adminModalClose` is **36×36** CSS px
  with `aria-label="Pencereyi kapat"`. WCAG 2.2 SC 2.5.8 (level AA, 24×24) is **met** — axe's
  `target-size` rule, enabled explicitly for this run, reported no violation. The repository's
  own floor is higher: `.button { min-height: 44px }` (`app/globals.css:193-194`) and the
  panel's inputs are 44 px (`:553-555`). The artifact's rule is "the design system's own touch
  floor where higher".
- **Prevent.** A component-state checklist entry for `AdminModal`'s close control (the same
  component appears on every modal surface), or a token the close button shares with
  `.button`; an assertion in the component test that `.adminModalClose` meets the project's
  minimum control height.

#### F16 — one enum, two label sources: the panel and the mobile app name the same values differently
- **Evidence class:** `code`.
- **Severity:** 1 (an operator moving between the two surfaces).
- **The disagreement.** For the same enum keys: `organization` is `İşletmedeki kayıtlar` in
  the panel (`user-labels.ts:9-14`) and `Tüm organizasyon` in the mobile app
  (`OrganizationUsersScreen.tsx:36-40`); `ORG_ADMIN` is `İşletme yöneticisi` in the panel
  (`user-labels.ts:2`) and `Yönetici` through the mobile's shared map
  (`design-system/user-facing-labels.ts`, `userFacingLabel`); `ACTIVE` is `Aktif` in the panel
  and `Etkin` in the mobile map. The panel's role labels also overrule the server's own
  `role.name` when a key is known (`page.tsx:117`, `?? role.name` fallback), so the server's
  name ("Platform Sahibi") is replaced by the client's word ("Platform sahibi") in one place
  and not in another. Also in this matrix: the invite form's default scope is `assigned`
  (`page.tsx:122`) while the contract's default is `organization`
  (`packages/domain/src/users.ts:23`), so the contract default is dead code.
- **Prevent.** One label source per concept: have both clients label enums from
  `packages/domain` (or from the server's `name`), and assert in a contract test that the
  panel's and the mobile's label maps agree key-for-key on the shared enums. The check that
  would have failed: a diff of the two maps.

#### F19 — after "Filtreleri temizle", the membership-state select still shows the filter the view no longer has

- **Evidence class:** `ui-observed` (two click-driven runs in the running document; reported first by a
  peer rater, reproduced here before being recorded).
- **Severity:** 2 (every operator who filters and then clears; the stale value is silent and reads as
  an active filter).
- **The disagreement.** The clear control is a client-side `<Link href="/users">` (`page.tsx:159-161`)
  and the select is uncontrolled with `defaultValue={input.state ?? ''}` (`page.tsx:151-158`). React
  reuses the same `<select>` DOM node across a client-side navigation, so its DOM value survives the
  re-render while the URL, the rows and the count are all unfiltered. Two runs, real mouse clicks on
  the link, raw readings:
  - `/users?q=x&state=active` → after the click: URL `/users`, rows 1, count `1 kullanıcıdan 1 kayıt
    gösteriliyor`, `q` reset to `""`, **select value `active`, label `Aktif`**.
  - `/users?state=inactive` → after the click: URL `/users`, rows 1, **select value `inactive`, label
    `Pasif`**.
  A full page load clears it (the node remounts and `defaultValue` applies) — which is exactly why my
  first filter pass, driven by address rather than by interaction, read this as a pass. The search
  input does reset, so the surface is inconsistent with itself, not uniformly stale.
- **Prevent.** The assertion has to be the one that would have failed: after clicking the clear link,
  assert `document.querySelector('[name="state"]').value === ''` **and** that the rendered rows equal
  the unfiltered set — asserting the URL alone passes while the control is stale. The fix lives in
  existing layers: key the select on the URL (`key={input.state ?? ''}`) so React remounts it, or bind
  it to a controlled value derived from the query. No proposal is required.

### 1.3 The layers agree (pass rows — the control that shows the matrices were filled honestly)

| Agreement | Both sides cited |
|---|---|
| Authorization is one registry, three enforcement points | `mutations.ts:29,33` (`team.invite`/`team.update` → `user.manage`); page gate `page.tsx:46-48`; action gate `actions.ts:53,75` via `mutation-guard.ts`; API gate `users.controller.ts:35,44,50,60,71,84` |
| Self-deactivation is refused in both layers | UI removes the option for the caller's own row `page.tsx:271-277` (`user.id !== context.id`); service throws `SELF_DEACTIVATE` `users.service.ts:181-186` and `:247-252`; the unit test pins the UI half (`page.test.tsx:105-135`, `value="false"` only when removable) |
| `SUPER_ADMIN` protection is consistent | Row states it and offers no control `page.tsx:206`; action refuses `actions.ts:61,87-88`; service refuses both the role and the target `users.service.ts:336-342`; live observation of the middle layer |
| Reactivation is a separate operation in three places | UI sends hidden `operation=reactivate` `page.tsx:217`; action builds exactly `{active: true}` `actions.ts:80-82`; service accepts reactivation-only `users.service.ts:199-206`; unit test `actions.test.ts:55-61` asserts the body is exactly `{active:true}` |
| Deactivation's blast radius is written and told truthfully | Service revokes sessions, device activations and push tokens `users.service.ts:275-305`; the confirmation names it: "*Pasife alma bu işletmedeki oturumları ve cihaz erişimini kaldırır*" `page.tsx:237`; observed in the confirmation dialog |
| Role replacement is announced before it happens | Dialog description `page.tsx:228`, confirmation body `page.tsx:237`, summary pair `Rol → <label>` (observed), server semantics `users.service.ts:223-232` |
| Turkish case-folding is handled on both sides | Page `page.tsx:60`, seed `prisma/seed.ts:181` (`normalizedEmail`); observed: `?q=SAHİBİ` and `?q=sahibi` both return the row, `?q=zzz` returns none |
| The filter's active state is visible on arrival | Observed: `q` and `state` re-rendered into the controls on every URL-driven load, count sentence `1 kullanıcıdan 1 kayıt gösteriliyor` (`page.tsx:164`). **The reset half is not an agreement — it is F19** (the search input resets on the clear click, the state select does not) |
| The empty state exists and is truthful | Observed with `?q=zzz` and `?state=inactive`; `page.tsx:288-291` |
| "No membership" and "no roles" have their own wording | `page.tsx:198` (`Üyelik yok`), `:192-194` (`?? '—'`), `:203-205` |
| A stale role set surfaces as a field error, not a dead end | `actions.ts:37-41` maps `ROLE_NOT_FOUND` to the `roleKey` field; unit test `actions.test.ts:73-84` |
| The dialog is a real modal with a working trap and a proper return | `AdminModal.tsx:56` (`showModal`), `:100-154` (trigger + dialog, `aria-haspopup="dialog"`, `aria-labelledby`); observed: `:modal` true, Tab cycles inside and wraps, Escape closes, focus returns to the trigger (verified with a real mouse click; a synthetic `.click()` does not focus the trigger and produced a misleading first result, which I discarded) |
| The confirmation is portalled, so Escape cannot take the guarded form with it | `ConfirmationDialog.tsx:49-50` (portal to `body`), `:38-48` (Escape captured and stopped); observed: Escape closed only the confirmation, the invite dialog kept both field values |
| Initial focus in dialogs lands on the least destructive action | `ConfirmationDialog.tsx:29-31` (`cancel.current?.focus()`); observed: `Vazgeç` focused in the confirmation, `✕` in the invite dialog (browser default) |
| The confirmation names what is at stake | Observed `<dl>` pairs `Ad / E-posta / Rol / Kapsam` built from live control values (`AdminActionForm.tsx:232-250`), hidden controls rendered as `—` (`:238-240`) |
| Validation happens on submit and is server-side too | `AdminActionForm.tsx:113-140` (`invalid` capture → one summary pass), `:98-112` (each error linked to its control by `aria-describedby`), `:278-306` (alert/status + focus); zod in the action `actions.ts:55,82`; zod in the API pipe `users.controller.ts:64,76` |
| The table is a real table | `<caption>` present and visually hidden by `clipPath: inset(50%)` (observed), `th scope="col"` ×7, `page.tsx:169-179` |
| The scroll region announces itself and is reachable by keyboard | `page.tsx:167` (`tabIndex=0`, `role="region"`, `aria-label="Kullanıcı listesi"`); observed as the last tab stop in `<main>` |
| Focus visibility and target size pass | Observed: `:focus-visible` ring 3 px solid `rgb(20,95,192)` = **6.13:1** against the field background (`globals.css:144-147` + `:focus-ring`); input/select ≥ 44 px; the invite trigger is 1126×44 at 1440; close 36×36 (F15) |
| Forms are labelled and need no placeholder, and no wrong `autocomplete` token is present | Visible `<span>` labels for all four invite controls and both filters (`page.tsx:92-134`, `:145-157`); `autocomplete` absent on all six — correct, since these collect another person's data and are search/filter fields (`autocomplete="off"` or absent per SC 1.3.5 scoping) |
| axe-core agrees with the hand-checks where it can see | six states, 0 violations (§0.3); `color-contrast` incomplete on the `color-mix` backgrounds, which is why §5.3 computes them by hand |

---

## 2. Matrix 2 — field contract

| Field | Column / type | Read by the API | Written by the API | Rendered (list / detail / form) | Validated | Label or enum source | Locale / format |
|---|---|---|---|---|---|---|---|
| `id` | `uuid` PK | `yes` — list/get, and the PATCH path (`ParseUUIDPipe`) | `no` | hidden input `page.tsx:218,246`; not shown in any view | `yes` — `z.uuid()` `actions.ts:77` + pipe | `n/a` | `n/a` |
| `displayName` | `text` (max 120) | `yes` — `users.service.ts:38` | create only (`invite`, `:120-127`); **refused** on update (`:327-334`) | list col 1; dialog field (`page.tsx:95-98`); in the confirmation summary | `yes` — `min(1).max(120)` (`domain/users.ts:7`), `maxLength={120}` on the control | free text | `n/a` |
| `email` | `text` unique + `normalizedEmail` | `yes` — `:39` | create only; normalized with `tr-TR` lower-casing (`common/normalization.ts`, and the same rule in the seed) | list col 2; dialog field (`page.tsx:99-102`); in the summary | `yes` — `z.email()` (`domain/users.ts:6`) | free text | server lower-cases for lookup; the panel prints the stored form |
| `status` | enum `UserStatus` = INVITED/ACTIVE/SUSPENDED/ARCHIVED (`schema.prisma:39-44`) | `yes` — `:40` (list, detail) | **`no`** — this feature never writes it (`update()` writes only membership fields, `:206-232`) | list col *Durum* badge (`page.tsx:186-190`) | `n/a` | `userStatusLabels` — **wrong enum** (F7) | `n/a` |
| `locale` | `text` (`schema.prisma`) | `yes` — `:41`; also `GET /me` | **`no`** in this feature | **not rendered anywhere** (list, dialog, summary) | shape only (`max(10)`) | none | the page tells the operator it is self-service (`page.tsx:164-165`) |
| `membership.scope` | `text` default `organization` (`schema.prisma:1113`) | `yes` — `:44` | `yes` — invite `:150-158`, update `:216-223` | list col *Kapsam*; both dialogs; summary | `yes` — enum (`domain/users.ts:24,29`) | `scopeLabels` (panel) vs the mobile's own literals (`OrganizationUsersScreen.tsx:36-40`) — **two sources** (F16) | `?? user.membership.scope` fallback prints the raw key (`page.tsx:197`) |
| `membership.active` | `boolean` default `true` | `yes` — `:45` | `yes` — `:206-213` | list col *Üyelik*; reactivate form; edit dialog; filter select | `yes` — `z.boolean()` / `z.enum(['true','false'])` (`actions.ts:85`) | inline string literals in the JSX, not a label map (`page.tsx:200`) | **collides with `status`'s words** (F6) |
| `membership.roles` | relation → role keys | `yes` — `:46-48` | `yes` — delete-all + insert one (`:226-232`) | list col *Roller* (keys → labels) (`page.tsx:192-194`) | `yes` — role-key enum + "role exists in this organization" (`:146-149`, `:227-232`) | `roleLabels` (panel) vs `userFacingLabel` (mobile) — **two sources** (F16) | joined with `, ` |
| `roleKey` (request) | enum of 7 keys (`domain/users.ts:14-22`) | `no` | `yes` (invite/update) | invite select, edit select, confirmation summary | `yes` — zod enum; service refuses `SUPER_ADMIN` (`:336-338`); `ROLE_NOT_FOUND` when the org lacks the key | panel shows `roleLabels[key] ?? role.name` — the client's word wins | `n/a` |
| `operation=reactivate` (request) | hidden string | `no` | it *selects* the write (`{active:true}`) | hidden input `page.tsx:217` | `yes` — string compare `actions.ts:80` | literal | `n/a` |
| `phoneE164` | `text?` unique (`schema.prisma:1057`) | `no` | `no` | not rendered | `n/a` — outside this contract | none | `n/a` |
| `passwordHash` / `normalizedEmail` | server-only | `no` | create only (`:116`) | not rendered | `n/a` | none | `pwd` is random per invite (`:323-325`) |

**Matrix 2 disagreements.** F7 (label/enum), F16 (two label sources, dead contract default),
F6 (two fields, one word), and the `locale` row: a field the contract carries and **no**
surface shows — folded into F8 (the missing detail view) rather than counted twice.

---

## 3. Matrix 3 — flow and step contract

The feature has three flows. There is no wizard; the "steps" are the dialog, the confirmation
and the server round trip, plus the URL query the redirect produces.

### 3.1 Invite (open → fill → confirm → submit → redirect)

| Step | Precondition | What it validates | What it writes | How a skip is prevented | Resume / persistence | Back-navigation retention | Where an error lands |
|---|---|---|---|---|---|---|---|
| 1 Open the dialog | `user.manage` (server-side page gate `page.tsx:46-48`) | nothing | nothing | the trigger is only rendered under `canInvite` (`page.tsx:74`); a panel session always has it (F10) | no state; a reload re-renders the page empty | Back from `/users?result=…` returns the list, not the dialog | `n/a` |
| 2 Fill 4 fields | role list fetched in step 1 (`page.tsx:59`) | on submit: native `required`/`type=email` (`page.tsx:93,98`), then zod in the action (`actions.ts:55`) | nothing | native validation blocks the submit before the confirmation is built | **none** — a reload loses everything; the only guard is `beforeunload` while dirty (`AdminActionForm.tsx:141-148`) | values survive the confirmation's Escape (`ConfirmationDialog` keeps the form; observed) | summary at the top of the dialog with per-field entries, `aria-describedby` wired back (`AdminActionForm.tsx:98-112`, `:278-306`) |
| 3 Confirm | the summary is built from live control values (`AdminActionForm.tsx:232-250`) | nothing new | nothing | the confirmation is client-side only — a scripted POST skips it (the API is the real gate) | the confirmation has no state of its own; Escape returns to step 2 with values intact (observed) | `n/a` | `n/a` |
| 4 Submit | `requireAdminMutation('team.invite')` (`actions.ts:53`) | `body.roleKey !== 'SUPER_ADMIN'` (`actions.ts:61`) — **this is where the flow dies today** | a user + membership + membershipRole in one transaction; an audit row; an outbox event (`users.service.ts:118-174`) | the API re-checks the permission (`users.controller.ts:60`) and the service re-refuses `SUPER_ADMIN` (`:336-338`) | rollback on any throw (single `$transaction`) | `revalidatePath('/users')` then `redirect('/users?result=user-invited')` (`actions.ts:70-71`) | server failures: `ALREADY_MEMBER` → the `email` field, `ROLE_NOT_FOUND` → the `roleKey` field, zod → per-field help text, anything else → one generic line (`actions.ts:18-49`) |
| 5 Result | — | — | nothing | — | `revalidatePath` `actions.ts:70` | the redirect replaces the page; the success notice is `role="status"` (`MutationNotice.tsx`) | observed today: the refusal lands in the dialog as `role="alert"` and the URL stays `/users` |

Finding: **F11** (a 401 at step 4 discards steps 2-3 with no message).

### 3.2 Edit access (row → dialog → confirm → submit)

| Step | Precondition | What it validates | What it writes | How a skip is prevented | Resume / persistence | Back-navigation retention | Where an error lands |
|---|---|---|---|---|---|---|---|
| 1 Open the row's dialog | row is editable: membership exists, not `SUPER_ADMIN`, membership active (`page.tsx:202-206`) | nothing | nothing | the trigger is not rendered in the three other cases (`page.tsx:203-221`) | none | Back → list | `n/a` |
| 2 Choose role / scope / membership | role list from step 1; scope defaulted from the row (`page.tsx:261-267`) | on submit: zod (`actions.ts:82-86`), `active` must be `'true'`/`'false'` | nothing | native validation on no field (all three are selects) | none | values survive Escape on the confirmation (same mechanism) | summary + linked fields |
| 3 Confirm | summary pairs `Yeni rol / Kapsam / Üyelik` (`page.tsx:239-244`) | nothing | nothing | client-side only | none | — | — |
| 4 Submit | `requireAdminMutation('team.update')` (`actions.ts:75`) | service: self-deactivation (`:181-186`), name/locale refused (`:180`), `SUPER_ADMIN` target refused (`:198`), reactivation-only rule (`:199-206`), `ROLE_NOT_FOUND` (`:230`) | `membership.active`, `membership.active=false` side effects (revoke), `membership.scope`, role replacement; audit `user.update` | permission re-checked at the API (`users.controller.ts:71`); service guards above | single transaction | `revalidatePath` + `redirect('/users?result=user-updated')` (`actions.ts:97-98`) | as 3.1 step 4; the two service codes the UI cannot pre-empt (`INACTIVE_MEMBERSHIP_REACTIVATION_ONLY`, `SELF_DEACTIVATE`) fall to the generic line |
| 5 Result | — | — | — | — | — | — | — |

**Not observable in the running app**: steps 1-3. The only row is `SUPER_ADMIN`-protected, so
the dialog never renders. Cells above come from `code`; the state set is a `[NOT CHECKED]` gap
recorded in §8.

### 3.3 Reactivate (row → inline form → confirm → submit)

| Step | Precondition | What it validates | What it writes | How a skip is prevented | Resume / persistence | Back-navigation retention | Where an error lands |
|---|---|---|---|---|---|---|---|
| 1 Form | `membership.active === false` (`page.tsx:203`) | nothing | nothing | rendered only in that state | none | — | — |
| 2 Submit | `team.update` + a hidden `operation=reactivate` (`page.tsx:217`) | the action builds exactly `{active:true}` (`actions.ts:80-82`), which the service's reactivation-only rule expects | `membership.active = true` and nothing else (`:206-213`) | the service refuses any other field on an inactive membership (`:199-206`) | the form is collapsed after the redirect | — | generic line (no field errors are possible) |

Agreement: the "reactivation-only" rule is the strictest of the three layers, and the UI
happens to satisfy it by construction (pass row in §1.3). A revoked session/device activation
is **not** un-revoked (only `membership.active` is written), which is consistent with the
model — a fresh sign-in creates a new session and device activation
(`auth/auth.service.ts:381`, `devices/devices.service.ts:281`) — so the confirmation's claim
"*işletmeye yeniden erişebilir*" (`page.tsx:212`) holds after a sign-in. No finding.

### 3.4 Filter / search (URL → server render → list)

| Step | Precondition | What it validates | What it writes | How a skip is prevented | Resume / persistence | Back-navigation retention | Where an error lands |
|---|---|---|---|---|---|---|---|
| 1 Submit the toolbar | none (get form, `page.tsx:143-162`) | nothing | nothing | `n/a` | **URL is the persistence** — `q`/`state` survive a reload (observed) | Back returns the previous query (observed) | an unknown `state` value silently falls back to `Tümü` while the URL keeps it (observed `?state=zzz`: 1 row, select shows `Tümü`) |

Agreement: the filter state is fully carried in the URL, restated in the controls and in the
count sentence. Minor, stated for completeness: two representations of one state now exist
(the URL and the select), and they disagree for a value the select does not offer
(`?state=zzz`); the result set is the unfiltered one, which is the truthful outcome.

---

## 4. Matrix 4 — interaction dependency

| Trigger | Dependents | Required action on change | Who owns the state | What is announced |
|---|---|---|---|---|
| `q` (search) | the list rows, the count sentence | *recompute* | URL query → server-rendered page (`page.tsx:60-67`) | the count sentence (`page.tsx:164`) is a plain `<p class="muted">` (`role: null`, measured) — no live region; the change arrives as a full page render, so nothing needs to be announced |
| `state` (membership filter) | the list rows, the count sentence | *recompute* | same | same |
| "Filtreleri temizle" | `q` and `state`, then the list | *reset* | navigation to `/users` (`page.tsx:159-161`) | the controls re-render empty and the count returns to the full set (observed) |
| `roleKey` in the edit dialog | the confirmation summary line `Yeni rol`; and, on submit, **every** existing role row | *recompute* (summary) + announce | form-local; server semantics at `users.service.ts:223-232` | the dialog description `Rol seçilirse kullanıcının mevcut tüm rolleri değiştirilir.` (`page.tsx:228`) and the confirmation body (`page.tsx:237`); `Mevcut rolleri koru` (`page.tsx:250`) states the no-op case |
| `active` in the edit dialog | sessions, device activations, push tokens of that member | *keep* (nothing else in the form depends on it) + announce | server-side revocation (`users.service.ts:214`, `:275-305`) | the confirmation body names the effect (`page.tsx:237`); **observed in the live confirmation text** |
| the caller's own row (`user.id === context.id`) | the `active` select's option set | *reset* (the `Pasif` option is removed) | render-time comparison (`page.tsx:271-277`) | nothing announces it — the option is simply absent. Server-side twin: `SELF_DEACTIVATE` (`users.service.ts:181-186`). Agreement; a missing option is not a stale value, so no finding |
| the role list from step 1 | both role selects, in every row's dialog | *keep* (page-load snapshot; no invalidation exists) | `page.tsx:59` | nothing announces a change — and none is possible while the page is open. If another surface changes the organization's roles meanwhile, the stale option is caught by the server (`ROLE_NOT_FOUND` → the `roleKey` field, `actions.ts:37-41`) — the pair (stale option, mapped error) is the honest design here |
| the toolbar `state` select after a filtered navigation | the select's own value | *keep* — and this is the defect | URL → `defaultValue` (`page.tsx:152`) | **F19**: clicking "Filtreleri temizle" leaves the select reading `Aktif`/`Pasif` while the URL, the rows and the count are unfiltered (two runs). The failure class the artifact names for this matrix — *a control still showing a state the view no longer has* — is present here |

No stale-dependent-value finding survives here: the one cascade that could be silent (a role
removed on another surface) is caught by a server code that maps to the right field.

---

## 5. Matrix 5 — surface pattern

Order follows the artifact: data views first. Each row is `pass` or a finding id. WCAG level
claimed per row: the panel targets **AA** (`SC 2.5.8` is AA in 2.2; the surface's own
readiness registry requires four states, `lib/admin-readiness-coverage.ts:13-22`).

### 5.1 Data views

| Rule | Result | Evidence |
|---|---|---|
| SC 1.3.1: real headers and a table label | **pass** — `<caption>Kullanıcı listesi` (visually hidden by `clipPath: inset(50%)`, measured) and 7 × `<th scope="col">` | observed + `page.tsx:169-179` |
| `aria-sort` on the sorted column, reversible | **F9** — sorted by `displayName asc` server-side, `aria-sort` all `null`, 0 sortable headers | observed + `users.service.ts:47` |
| Editable cells / widgets make it a grid | **pass** — cells are text; the only in-row control (for a normal row) is one modal trigger, so the table stays a table, as the code comment intends (`page.tsx:223`) | `code` |
| Large/lazy sets announce `aria-rowcount`, restore position | **n/a today, F5 for the contract**: no pagination exists (1 page), so there is nothing to announce; the envelope that would carry it is a literal and the page ignores it | `users.service.ts:64`, `page.tsx:13-30` |
| SC 1.4.10: one-direction page scroll at 320, table in its own container | **pass, measured** — `document.documentElement.scrollWidth === 320 === innerWidth`; the table (1140 px) sits inside `.tableWrap` (242 px, `overflow-x: auto`), i.e. the two-dimensional exception is contained | observed; `globals.css:561-563` |
| Pagination marks the current page; a one-page pager is hidden | **pass by construction** — no pager at all (F5 is the contract side of this) | observed |
| Content: caption/heading describes the data, short noun headers, human-readable first column | **pass** — h1 from the registry (`Yöneticiler`), headers `Ad / E-posta / Durum / Roller / Kapsam / Üyelik`, first column a person's name | observed; `components/PageHeader.tsx:19-24` |
| Filters discoverable, active state visible | **pass** — labelled toolbar (`aria-label="Kullanıcı filtreleri"`), both values restated in the controls, count sentence names the subset | observed |
| Long text has a strategy (truncate with a way to see, or wrap) | **F18** — `th,td { white-space: nowrap }` (`globals.css:573`) with `text-overflow: clip` (measured) and no truncation affordance; injecting a long name/company/e-mail/role list (fixture) grew the table from **1140 px to 2311 px** at both 1440 and 320 | observed on the live document with an injected value (fixture, not seeded data) |
| A scroll region says it scrolls | **F18 (second half)** — `role="region"` + label + `tabIndex=0` are present and correct, but there is no visual affordance: the wrapper's `offsetWidth - clientWidth` is **0** (macOS overlay scrollbars leave no gutter), and no fade/shadow/scrollbar styling exists. At 1440 the table already overflows its wrapper by 56 px, so content is clipped on a desktop viewport | measured at 1440 (`1084 / 1140`) and 320 (`242 / 1140`) |
| Detail view: `dl` key/value pairs, every field shown or explicitly absent | **F8 / `[NOT CHECKED]`** — there is no detail view to check; the confirmation dialog's summary is a `<dl>` and does show every named field (observed) | observed + §1.1 search 2 |

### 5.2 Controls

| Rule | Result | Evidence |
|---|---|---|
| APG combobox roles/keyboard | **n/a** — no combobox; the role/scope pickers are native `<select>` (correct choice for a known short list) | observed |
| APG listbox rules | **n/a** — none | not applicable: no listbox exists on this feature |
| A row carrying its own controls is not a listbox | **pass** — it is a table | observed |
| Visible persistent label, format hints where unusual, counter where a limit exists | **pass with one note** — all six labelled by `<span>`; `maxLength={120}` exists on the name field (`page.tsx:93`) with **no visible counter**, which the rule asks for where a limit exists. Not raised as a finding: the limit is 120 characters on a person's name, and the native `tooLong` message is surfaced on submit | observed + `page.tsx:92-95` |
| SC 1.3.5 scoped: `autocomplete` on self-data, `off`/absent on search and record fields | **pass** — all six controls collect another person's data or filter: `autocomplete` absent (`ac=null` measured on each) | observed |
| One required/optional convention | **pass within this surface** — required is expressed by the native `required` attribute and no asterisk convention is mixed in; nothing in the dialog is optional-but-unmarked (all four fields are always sent) | observed + `page.tsx:93,98` |
| APG disclosure / tabs | **n/a** — none on this feature | not applicable: no disclosure and no tablist in `page.tsx` |
| A conditional reveal reveals a question and announces it | **n/a** — the edit dialog has no conditional reveal (role, scope and membership are always shown) | observed (dialog contents) + `page.tsx:249-276` |
| Pickers: text entry beside the calendar, no calendar for distant dates | **n/a** — no date control | observed: no `type="date"` on this surface |
| SC 2.5.8 target size 24×24, or the design system's floor | **F15** — close control 36×36 (axe `target-size` enabled: no violation, so AA is met); `.button`'s floor is 44 px | observed + `globals.css:193-194` |
| SC 2.4.7 / 1.4.11 focus visible and contrasted | **pass, measured** — 3 px ring, `rgb(20,95,192)`, **6.13:1** against the field's white background; keyboard reachable (tab stops enumerated: trigger → q → state → Filtrele → temizle → list region) | observed; `globals.css:144-147` |
| SC 1.4.3 contrast 4.5:1 (3:1 large), no colour-only state | **pass, computed** — see §5.3; no state is signalled by colour alone (status is a word in a badge, membership is a word) | observed + §5.3 |

### 5.3 Contrast (hand-checked, because axe's `color-contrast` came back `incomplete` on the `color-mix` backgrounds)

| Element | Light scheme | Dark scheme |
|---|---|---|
| muted paragraph (`p.muted`) | `#60675f` on `#f7f8f6` → **5.47:1** | `#a6b1aa` on `#0c1210` → **8.55:1** |
| column header (`th`, colour `var(--muted)`, 13 px) | 5.47:1 (same token) | **7.60:1** |
| status badge, plain (`ACTIVE`) | `#19201a` on `#eef0ec` → **14.50:1** | **12.21:1** |
| row text (`td`) | 14.29:1 (`#19201a` on the surface) | 14.29:1 |
| badge variants — **fixture**: the class was forced, because no non-`ACTIVE` user exists in the organization | `badgeWarn` `#875000` on `#f4e7d6` → **5.44:1**; `badgeDanger` `#a82f2f` on `#f7e3e3` → **5.49:1**; `badgeSuccess` `#0b5238` on `#deeae6` → **7.47:1** | `badgeWarn` → **9.62:1** |

All above the 4.5:1 AA floor for 12-16 px text. **Discipline note:** my first pass reported
3.16:1 for `badgeWarn`; that was my parser reading `color(srgb 0.95 …)` values as 0-255. The
correct figure is 5.44:1 and there is no contrast finding. The corrected numbers are the ones
in the table.

### 5.4 Validation and errors

| Rule | Result | Evidence |
|---|---|---|
| Validation on submit not blur, values kept, server-side validation present, native validation suppressed | **pass with a stated deviation** — no control validates on blur; failing values are kept (the form never resets, `AdminActionForm.tsx:150-220`); server-side zod exists in the action **and** in the API pipe. Native validation is **not** suppressed (no `novalidate`), which the artifact's wording asks for — but its messages are routed into the same in-form summary through a capture-phase `invalid` listener (`AdminActionForm.tsx:113-140`), so the outcome the rule protects (one submit-time, identified, described error) holds. Named alternative: `novalidate` + server messages only, which would drop the pre-submit hint but remove the two-vocabulary situation (native `Bu alanı doldurun.` vs the action's `1–120 karakter arasında bir ad girin.`) — both are actionable, so this stays a pass with the alternative on record | `code` + observed (the native `invalid` path fired live and produced the summary) |
| SC 3.3.1/3.3.3: the item in error is identified and the correction described in text | **pass** — the summary names each field's correction (`actions.ts:11-16`), and the controls are marked `aria-invalid`/`aria-describedby` for as long as the result stands (`AdminActionForm.tsx:96-110`) | observed live (native path) + `code` |
| Association: `aria-describedby` to the message, same wording in summary and beside the field, a summary entry that moves focus to its field | **pass** — the summary's entries are buttons that focus the control (`AdminActionForm.tsx:283-300`); there is no second wording beside the field, so no divergence is possible | `code` |
| An error summary at the top of the form | **pass** — the summary is the form's first feedback element and receives focus (`AdminActionForm.tsx:90-93`), observed to become `document.activeElement` after a blocked submit | observed |

### 5.5 Flows

| Rule | Result | Evidence |
|---|---|---|
| One question per page / unique headings / back + continue | **pass for a dialog flow** — the dialog has one heading, one job, one submit; no multi-step page exists | observed |
| Check-your-answers pre-populated on return, a Change link naming what it changes, a submit that names its action | **partial, no finding** — the confirmation is a live summary of the current values (observed `<dl>`), the `.button` submits are named (`Davet oluştur`, `Erişimi kaydet`, `Üyeliği etkinleştir`), and there is no return-to-summary step to pre-populate because the confirmation is not a page | observed |
| Task list statuses in text | **n/a** | not applicable: no task list in this feature |
| SC 3.3.7 redundant entry | **pass** — no value is asked twice in a flow; the edit dialog re-uses the row's values as defaults (`page.tsx:261-267`) | `code` |
| SC 3.3.4: a submission that creates a commitment is reversible, checked or confirmed | **pass** — every mutation on this feature is confirmed, and the confirmations name the commitment (`page.tsx:83-93`, `:210-214`, `:235-244`); none is irreversible (deactivate is reversible by reactivate) | `code` + observed (the confirmation was opened live) |
| Destructive confirmation names what is lost, actions inside the panel, reserved for the irreversible | **pass with a caveat** — the confirmation names the person and the effect (`page.tsx:237`), both actions are inside the dialog, and it is used for a non-destructive edit too. The artifact reserves the pattern for the irreversible; here it is applied uniformly. Named context: a 4-field access change with an all-roles-replaced semantic is worth confirming, and the alternative (no confirmation on the reversible edit) would remove the only place the destructive sentence appears | observed (the live confirmation text) + `page.tsx:237` |
| APG dialog: `aria-modal` only when outside content is inert, focus in on open and stays, returns to the invoker, `alertdialog` focuses the least destructive action | **pass** — native `<dialog>` + `showModal()` (`:modal` true, measured); `aria-modal` is correctly absent because the native modality does it; focus moves in (the close control, browser default), Tab cycles inside and wraps, Escape returns focus to the trigger (verified with a real mouse click), the confirmation's initial focus is `Vazgeç` | observed; `AdminModal.tsx:56`, `ConfirmationDialog.tsx:29-31` |

### 5.6 Notifications

| Rule | Result | Evidence |
|---|---|---|
| SC 4.1.3: a change the page makes without moving focus is programmatically determinable | **pass for the in-page cases** — the form's result region is `role="alert"`/`role="status"` and takes focus on a failure (`AdminActionForm.tsx:277-279`, observed); the pending state is `role="status"` with `aria-busy` (`:262-270`); the post-redirect notice is a `role="status"` paragraph (`MutationNotice.tsx`) rendered by a **full page render**, so it is in the reading order rather than announced as a live change — the honest limit of the mechanism | observed + `code` |
| The whole status string is the announced unit, and the end of a wait is announced | **pass** — `İşlem kaydediliyor…` names the wait (`AdminActionForm.tsx:70`) and `Sayfa yükleniyor…` covers the segment (`app/(dashboard)/loading.tsx:2-6`) | `code` |
| Non-status changes stay out of live regions | **pass** — no other live region exists on the surface; the count sentence and the empty surface have no role (measured: `role: null`) | observed |
| A notification banner is a labelled region, sits before the h1, at most one per page, never replaces the error summary | **pass by absence** — there is no banner; the `MutationNotice` sits after the `PageHeader` and never substitutes for field errors (field errors live inside the form dialog) | observed + `page.tsx:72-73` |

---

## 6. Findings, ranked most severe first

| # | Finding | Evidence class | Severity | Prevent line (short form; full text above) |
|---|---|---|---|---|
| F1 | The panel's only user-administration capability cannot complete for any account: the one offerable role is refused by the action and the service | `behaviour` | 4 | assert the offerable-minus-refused role set is non-empty against the shipped seed → **P1** |
| F2 | The e2e coverage of this flow runs against a fixture that rewrites a tenant into the platform organization, so the journey cannot pass against the shipped configuration | `code` | 4 | seed-parity contract test over the fixture's SQL vs the seed → **P1** |
| F3 | The invitation has no delivery path: random password hash, no mail in the repo, and the only carrier targets the invitee's own device tokens | `code` | 4 | assert a delivery attempt for an invitee with no device tokens → **P3** |
| F4 | Two routes for deactivation: the dead one carries `user.deactivate`, the live one records `user.update` | `code` | 3 | audit-action assertion per operation on the PATCH path |
| F5 | Search and filters are in-page, the contract has no parameters, the envelope is a literal, and this is the only list surface that ignores it | `code` | 3 | contract test that every list surface parses `page` and renders `hasNextPage` → **P2** |
| F6 | *Durum* and *Üyelik* print the same words for two different fields, so a deactivated member reads `Aktif` beside `Pasif` | `code` | 3 | assert one status vocabulary per row |
| F7 | `userStatusLabels` labels a different enum than the API returns (two labels impossible, the reachable one missing) | `code` | 2 | type the map against the generated enum |
| F8 | `GET /users/:id` is live and published, and no surface reaches it; the entity has a shape the panel never shows | `code` | 2 | render it or delete it; contract test that published operations have callers |
| F9 | The list is sorted with no `aria-sort` and cannot be reversed | `ui-observed` | 2 | render test asserting `aria-sort` on the ordered column |
| F11 | A 401 mid-submit discards the dialog's typed values and says nothing | `code` | 2 | e2e assertion that values survive (or are reported lost) across the recovery hop |
| F12 | `UserUpdateInput` offers `displayName`/`locale`, which the service always refuses | `code` | 2 | trim the contract; test that every input field is accepted by its own path |
| F14 | The surface's own axe claim is not reproducible: no axe-core in the repo, no a11y e2e for `/users` | `code` | 2 | add the scanner + spec, or stop claiming the scan |
| F17 | (mobile sibling, same feature) the tenant surface hardcodes the role list because `/users/roles` is panel-only, so it can offer a role the organization does not define | `code` | 2 | audience-scoped role list → **P4** |
| F18 | The table's overflow has no affordance and no long-text strategy: 1140 px inside 1084 px at desktop, 2311 px with a long value, `nowrap`+`clip`, zero scrollbar gutter | `ui-observed` | 2 | measure the cell/container pair, not the document |
| F19 | After "Filtreleri temizle" the membership-state select keeps showing the filter the view no longer has (URL, rows and count are unfiltered; `q` does reset) | `ui-observed` | 2 | e2e assertion on the **select's value** (and the rendered rows) after the clear click, not on the URL |
| F10 | Both permission-denied surfaces are unreachable by any account that can open the page | `code` | 1 | assert the panel session's premise, or delete the branches |
| F13 | A bookmarked `#user-access-<id>` deep link opens nothing and says nothing | `ui-observed` | 1 | **no mechanical prevention today** — review item |
| F15 | The dialog's close control is 36×36 against the design system's own 44 px floor | `ui-observed` | 1 | component-state checklist entry / shared token |
| F16 | One enum, two label sources: the panel and the mobile name the same keys differently; the contract's scope default is dead | `code` | 1 | one label source per concept; assert the two maps agree |

**Findings per evidence class** (one class per finding): `behaviour` 1 (F1 — exercised live through
all four layers) · `ui-observed` 5 (F9, F13, F15, F18, F19) · `code` 13 (F2-F8, F10-F12, F14, F16,
F17) · `external` 0 (external sources are cited inside rules, not as findings) · `user-verbatim` 0.
**Total 19.** Live API corroboration appears inside the prose of F4, F5 and F8 without changing
their class.

---

## 7. Capability-change proposals

Four findings have a fix that names a layer **which does not exist yet**, so they are emitted
as proposals and not as screen recommendations. Each carries the artifact's nine headings and
its falsifier. The load-bearing artifact in every case already exists in this repository and
can reject the change mechanically.

### P1 — authorised provisioning of a platform administrator (from F1, F2)

| Heading | Content | Falsified by |
|---|---|---|
| Capability | A platform organization can gain a second administrator through an authorised, audited path, while generic membership edits stay unable to grant `SUPER_ADMIN` | a cited route + permission that already provisions a platform administrator — `grep -rn "superAdminProvisioningOnly\|SUPER_ADMIN_PROVISIONING_REQUIRED" --include=*.ts --include=*.tsx apps packages` returns 7 hits: the two refusal sites and the guard (`users.service.ts:337,341,344-348`) and their own tests (`users/users.service.test.ts:72,82,96`), and nothing that grants it |
| Absence proof | `apps/api/src/users/users.service.ts:336-338` (`assertGenericRoleAssignment` → `superAdminProvisioningOnly`) and `apps/admin/app/(dashboard)/users/actions.ts:61`; the failing input is the only one the running form offers: `roleKey=SUPER_ADMIN` to `POST /api/v1/users/invite` → 403 `SUPER_ADMIN_PROVISIONING_REQUIRED`; observed live: one role option, refusal rendered, database unchanged | a cited path that accepts `roleKey=SUPER_ADMIN` from the panel |
| Contract delta | `docs/openapi.json`: a new operation (e.g. `POST /api/v1/platform/administrators`, operationId `platform-administrators-provision`) plus a new permission key `platform.admin.manage` in `packages/domain/src/permissions.ts` and its role-permission diff (SUPER_ADMIN; **not** ORG_ADMIN — it is a platform capability, per the file's own exclusion list). Rejectable: `pnpm test:api-contract` + `node scripts/verify-api-contract.mjs` (both exist, `package.json` `api:contract:verify`) | running the compatibility checker and getting green with no diff |
| Migration | expand: add the permission row and the operation; the schema already expresses the target (`memberships`, `membership_roles`, `roles` need no change). migrate: nothing to backfill — the platform organization's single membership is already correct. contract: remove `SUPER_ADMIN` from the panel's offerable set in `page.tsx:104-121` and drop the `actions.ts:61` guard, **dated 2026-10-20** | a contract phase with no date |
| Rollout | flag `platform.admin.platformAdminProvisioning`, type boolean, expected lifetime 2 releases; initial exposure: the platform organization only; kill-switch owner: the platform owner; abort threshold: any 4xx from the new operation above 0 on a 24 h window, or more than one new `SUPER_ADMIN` membership in that window | a threshold that cannot be measured from `audit_logs`, or a flag with no lifetime |
| Verification | fails today, passes after: an API integration test that provisions a second platform administrator in the platform organization and asserts the generic invite still refuses `SUPER_ADMIN`; and the F2 seed-parity assertion, which fails on the current commit | a check that also passes on the pre-change commit |
| Reversibility | writes one `membership_roles` row (+ audit). Restore: delete that row (reversible; no data destroyed) | data written with no restore step |
| Decision | ADR "Platform administrator provisioning is a separate, permissioned operation" — context: F1/F2; decision: a dedicated operation + `platform.admin.manage`; status: **Proposed**; consequences: the panel's generic invite stops being the place platform administrators are made, and the e2e fixture's `kind` rewrite is retired | an ADR without a status |
| Appetite | 1 week. Out of bounds: changing the `SUPER_ADMIN` guard itself, adding role keys, touching tenant-role assignment. When it ends: ship the ADR + the operation behind the flag, or abandon the flag and leave the surface read-only with an explicit sentence | no time box |

### P2 — server-side query for the user list (from F5)

| Heading | Content | Falsified by |
|---|---|---|
| Capability | The user list can be searched, filtered and paged by the server, so the panel holds one page of the organization's members rather than all of them | a cited query path in `users.service.ts:26-58` — there is none: the only `where` is organization + status |
| Absence proof | `docs/openapi.json` `/api/v1/users` `"parameters": []`; `users.service.ts:64` returns `{ nextCursor: null, hasNextPage: false }` as a literal, and `page.tsx:58-67` filters in memory; the failing input is any `q=`, `state=`, `cursor=` or `page=` parameter — the route ignores all four | a cited handler that reads a list query |
| Contract delta | `docs/openapi.json`: `GET /api/v1/users` gains `q` (string, max 120), `state` (`active`\|`inactive`), `cursor` (string), `limit` (integer, default 50, max 200); the response keeps `page.nextCursor`/`hasNextPage` with real values. Rejectable by `pnpm test:api-contract` + the client generator (`packages/openapi-generator`) | green compatibility check with no diff |
| Migration | expand: add the parameters and compute the envelope with `take: limit + 1` (the pattern `work-orders` already uses); migrate: nothing to backfill; contract: after all callers send `limit`, remove the unbounded path — **dated 2026-10-27** | a contract phase with no date |
| Rollout | flag `users.list.serverQuery`, boolean, 2 releases; initial exposure: 10 % of panel sessions via the existing flag mechanism; kill-switch owner: the panel maintainer; abort threshold: an error rate on `GET /users` above 1 % or any page whose rendered count disagrees with `page.hasNextPage` in a 24 h window | an unmeasurable threshold |
| Verification | an API test that `hasNextPage` is `true` for an organization with 51 members and `q`/`state` narrow the set, plus an admin render test that the toolbar round-trips the cursor; both fail on the current commit | a check that passes pre-change |
| Reversibility | writes nothing; the restore step is flipping the flag off (the unbounded read remains until the contract phase) | no restore step for a data write — n/a, stated explicitly |
| Decision | ADR "The user list is queried server-side; the panel no longer filters a full collection" — status **Proposed**; supersedes the in-memory filter (`page.tsx:60-67`) | an ADR without a status |
| Appetite | 3 days. Out of bounds: changing the surface's copy, the Turkish case-folding rule, or the role list. When it ends: the ADR + the endpoint in the same window, or the flag is dropped | no box |

### P3 — an invitation delivery path (from F3)

| Heading | Content | Falsified by |
|---|---|---|
| Capability | A person invited into the organization receives, outside the product, the means to set a password and sign in | a cited delivery path for an invitee who has never signed in — `users.service.ts:168-174` emits an event whose only consumer is device-keyed |
| Absence proof | `users.service.ts:116,323-325` (random hash never shown); `notifications/notification-event-mapper.ts:684-690` + `worker/push-notification.handler.ts:135` (recipient = the invitee's own push tokens); `auth/password-reset-email.provider.ts:9-11` is the repository's only mail path and is `PASSWORD_RESET_EMAIL_PROVIDER`-gated with the default `'disabled'` (`packages/config/src/index.ts:262`). Failing input: `POST /users/invite` for an address with no device — nothing is delivered | a cited send for any invite-only user |
| Contract delta | schema migration: an `invitations` table (token hash, `user_id`, `organization_id`, `expires_at`, `consumed_at`) + a new outbox event `InvitationIssued` (payload `{ membershipId, invitationId }`) + a permission-free acceptance route (`POST /api/v1/invitations/accept`) — `apps/admin/app/davet/page.tsx` exists but is the *referral* landing today (it deep-links into the mobile app with a referral token, `davet/page.tsx:13-19`), so an invitation-acceptance page is new. Rejectable: the generated Prisma migration + `pnpm test:api-contract` | a migration that adds no token/expiry column |
| Migration | expand: add the table, the event and the sender (both transports: Resend when configured, otherwise the audit log records `INVITATION_UNDELIVERED`); migrate: backfill nothing (invitations are forward-only); contract: after 30 days, refuse to create an invite whose delivery failed — **dated 2026-11-15** | a contract phase with no date |
| Rollout | flag `user.invitation.delivery`, type boolean, 1 release; initial exposure: off until `PASSWORD_RESET_EMAIL_PROVIDER` is configured in the environment (the same key gates both); kill-switch owner: the platform owner; abort threshold: any invitation whose acceptance token is used more than once, or a send failure rate above 2 % in 24 h | an unmeasurable threshold |
| Verification | an integration test asserting that `POST /users/invite` writes exactly one `invitations` row and issues exactly one delivery attempt for a user with **no** push tokens; fails on the current commit (no such row exists) | a check that passes pre-change |
| Reversibility | writes a token row + an audit record. Restore: revoke by setting `consumed_at` (one-way only in the sense that a delivered e-mail cannot be recalled) — stated plainly: the *record* is reversible, the message is not, so the operation must go through the ADR and the flag | a data write with no restore step and no label |
| Decision | ADR "Invitations are delivered out of band, with a single-use expiring token" — status **Proposed**; supersedes the assumption that an invited account is usable without a credential | an ADR without a status |
| Appetite | 1 week. Out of bounds: changing the password-reset provider, adding an SMS transport, touching the audit redaction rules. When it ends: ship the table + the sender + the acceptance page, or make the invite surface say plainly that no credential is delivered | no time box |

### P4 — an audience-scoped role list for a tenant surface (from F17)

| Heading | Content | Falsified by |
|---|---|---|
| Capability | A tenant surface can ask which roles the *caller's organization* defines, without holding a platform panel session | a cited non-panel route returning an organization's roles — `/users/roles` is the only one and it carries `@RequireAdminPanel()` (`users.controller.ts:43`) |
| Absence proof | `users.controller.ts:42-46` (panel-only) plus the mobile client's workaround: a hardcoded list of six keys (`OrganizationUsersScreen.tsx:27-37`), which can offer a role the organization does not define → the API answers `ROLE_NOT_FOUND` (`users.service.ts:146-149`). Failing input: a tenant organization that defines only `ORG_ADMIN` and `TECHNICIAN` (live `psql` shows exactly that for the demo tenant) receiving an invite for `VIEWER` from the mobile app | a cited route or client list that already matches the organization's rows |
| Contract delta | `docs/openapi.json`: either relax `@RequireAdminPanel()` on `/users/roles` to `user.manage` (the endpoint already scopes by `auth.organizationId`, `users.service.ts:69-75`) or add `GET /organizations/roles`; the mobile client then drops its literal. Rejectable by the contract verifier and by a mobile contract test asserting the client no longer hardcodes role keys | green compatibility check with no diff |
| Migration | expand: serve both paths; migrate: nothing to backfill; contract: remove the hardcoded list from the mobile client — **dated 2026-11-01** | a contract phase with no date |
| Rollout | flag `users.roles.audienceScoped`, boolean, 1 release; initial exposure: the mobile app's next release; kill-switch owner: the mobile maintainer; abort threshold: any `ROLE_NOT_FOUND` from a mobile invite in a 24 h window | unmeasurable threshold |
| Verification | a mobile test asserting the offered role keys equal the organization's role rows (fails today against a two-role organization) | passes pre-change |
| Reversibility | reads only; restore step n/a | — |
| Decision | ADR "Role lists are read from the caller's organization, not from a client constant" — status **Proposed** | ADR without a status |
| Appetite | 2 days. Out of bounds: the platform panel's role list. When it ends: ship the relaxed guard, or leave the mobile literal and add the missing-role error path it already has | no box |

**Reviewer's five absences, checked against my own proposals:** a capability claimed with no
`code` finding behind it (none — P1←F1/F2, P2←F5, P3←F3, P4←F17); a proposal with no
rejectable artifact (none — each names the contract verifier, a migration, or a flag schema);
a schema-touching step with no migration phases (P3 is the only one, and it has expand /
migrate / dated contract); a flag with no lifetime or owner (none — each flag has a type, a
lifetime and a named owner); a contract change with no ADR and no pre/post check pair (none).

---

## 8. Coverage — what was checked, what was not, and what would change the conclusion

Counts are rows per matrix; `[NOT CHECKED]` rows stay in the tables above.

| Matrix | Rows checked | Not checkable here | What would change the conclusion |
|---|---|---|---|
| 1 — capability | 14 of 14 rows cited at every cell, and the **read paths exercised live at the API** (§0.4 pass 3); 2 cells remain `[NOT CHECKED]`: the invite row's and the edit row's persistence — no accepted input exists to reach either write | the two write paths' end state in the running app: the API refuses every role key, so no invitation can be created to observe, and the only row is `SUPER_ADMIN`-protected | an organization with ≥2 assignable roles in the panel's organization would let both write rows be exercised end to end; a tenant-sized user set (51+) would make F5 observable as truncation |
| 2 — field contract | 12 of 12 fields, each across 8 columns | none | nothing — this matrix is complete |
| 3 — flow and step | 3 flows; invite: 5 steps × 8 columns; edit: 5 steps (`[NOT CHECKED]` for steps 1-3 in the running app, cited from code); reactivate: 2 steps; filter: 1 step | the edit dialog's rendered states (the row it belongs to cannot be rendered); the error frame (reaching it needs the API to fail, which I would not do to a stack other raters were using) | a non-`SUPER_ADMIN` member in the panel's organization, or a stopped API in an isolated environment, would close both gaps |
| 4 — interaction dependency | 7 chains, all cited; one of them (the filter reset) is a finding, F19, confirmed by two click-driven runs | none | — |
| 5 — surface pattern | data views 12 rules (11 pass/finding, 1 `[NOT CHECKED]` for the detail view), controls 11 (7 pass, 1 finding, 3 n/a), validation 4, flows 6, notifications 4, contrast 7 elements across 2 schemes | the *loading* and *error* frames of this segment: loading is shared (`app/(dashboard)/loading.tsx`) and was not observed mid-flight; the error frame was not triggered (it needs the API to fail) | a throttled network or a fault proxy would let both be read; a longer `?q=zzz`-style state set with non-`ACTIVE` data would exercise the warning badge for real |
| axe sweep | 6 states, `target-size` explicitly enabled | axe has **no rule** for SC 1.4.10, 2.4.7, 3.3.1, 3.3.3, 4.1.3 (its own published rule set) | nothing — those five are hand-checked above (§5.1, §5.2, §5.4, §5.6) |

**States of a data view / control that do not exist and are therefore findings or gaps, not
silences:** a *cleared filter* state (F19: the control keeps the old value); a *detail* state (F8, absent by construction); a *long-text* state (F18, absent
strategy); a *non-`ACTIVE` status* rendering path (exists in code, unobservable with the
shipped data — the badge class was measured as a fixture, §5.3); a *sort* state (F9, absent);
a *pagination* state (F5, absent); a *reply to the invitee* state (F3, absent).

**What did not change:** the application's data. One mutation was attempted (the invite) and
wrote nothing: `select count(*) from users` = 56 before and after, `0` rows matching the typed
address, and the action returned before its API call.

---

## 9. Discipline — passes, entry points, readings vs exercised actions

- **Three passes minimum, from different entry points:** five ran (§0.4). One rater is never a
  measurement; the pass count is stated per claim where it matters (F1 from a driven action;
  F2/F4/F5/F8 from the cross-layer read).
- **Read the running app where it runs, and say what was read vs exercised.** Exercised
  (driven): the invite dialog's contents, its native validation path, its confirmation, the
  Escape/focus behaviour, the filter/search/empty states, the deep link, the tab order, six
  axe states, and ten requests against the live API with a real `ADMIN` token.
- **Where the first reading was wrong, and why.** Two corrections are recorded in place rather
  than quietly applied. (1) My filter pass drove each state by **loading a URL**, which forces a
  fresh mount, so the uncontrolled `state` select looked correct; the same check driven by a
  **click** on "Filtreleri temizle" exposes a stale value (F19). A URL-driven check cannot see
  uncontrolled-input staleness, and any future pass on this surface must churn state by
  interaction, not by address. A peer rater reported this defect after my first reading; I
  reproduced it twice before writing it down, and the pass row it falsified (§1.3, Matrix 4) was
  amended, not deleted. (2) I wrote that live API probing was unreachable; that was wrong —
  `POST /api/v1/auth/admin/sign-in` is CORS-reachable from a page on the panel's own origin and
  yields an `ADMIN` token, which is how pass 3 now runs. Read only (`code`): both write paths' persistence, the audit and outbox writers,
  the dead routes, the envelope, the e2e fixture, the seed's role rows, the contract.
  **The known limit applies and is why the capability rows lean on code:** the panel's pages
  are server-rendered, so the API calls this feature makes are invisible to the browser's
  request log; I read them in the server's own code, and the one call I could observe from the
  browser was the one that never happens (the refusal).
- **A screenshot is read, not saved.** None was viewed by me — a vision pass needs an image
  file, and this rater was restricted to writing one artifact file, so nothing was written
  outside it. What the image would have carried (hierarchy, rhythm, colour) was taken instead
  from the rendered geometry and computed styles of the live document: the widths measured, the
  computed colours and their ratios, the target boxes, and the computed-style values of the
  text that the tree cannot answer (colour, size, `white-space`, `overflow`). The tree and the
  DOM answered structure and roles. Widths: **1440×1000** and **320×900**, plus a dark-scheme
  emulation (`prefers-color-scheme: dark`, colours confirmed changed). This is a stated
  limitation, not a substitute claim.
- **Pass rows are part of the result:** §1.3 lists 21 agreements with both sides cited. The
  surface's a11y mechanics are genuinely good — that is what makes F1's dead capability and
  F2's fixture the interesting findings, exactly as the artifact's closing measurement claims.
- **No finding without a named standard or a cross-layer disagreement:** every finding above
  names either a WCAG SC / APG pattern or two layers that disagree, and the two that rest on
  the repository's own convention (F5, F15) cite the sibling files that set it.
- **Nothing is a UI opinion:** the deliverable is the matrices, the disagreements and the
  proposals, ranked most severe first (§6).

---

## 10. The eight hand-checks (axe cannot see them)

| # | Hand-check | Result |
|---|---|---|
| 1 | Does the error text identify the error and suggest the fix (3.3.1/3.3.3)? | **Yes** — `1–120 karakter arasında bir ad girin.` / `Geçerli bir e-posta adresi girin.` / `Listeden geçerli bir rol seçin.` (`actions.ts:11-16`), rendered in the summary and linked to the field; the native path's wording differs but is equally actionable (§5.4) |
| 2 | Does a destructive confirmation name what is lost? | **Yes** — the person's name *and* the effect: "*Pasife alma bu işletmedeki oturumları ve cihaz erişimini kaldırır*" (`page.tsx:237`), observed in the live confirmation; the reactivate copy names the person (`:212`) |
| 3 | Does a status message carry enough context, and is the end of a wait announced? | **Mostly** — `İşlem kaydediliyor…` and `Sayfa yükleniyor…` name the wait; the refusal names the cause; the post-redirect notice is a full page render (`role="status"`, not a live change), which most ATs read in document order rather than announce — recorded as the mechanism's honest limit, not a defect I can measure |
| 4 | Is the focus indicator visible on the real background (2.4.7)? | **Yes, measured** — 3 px `rgb(20,95,192)` at 6.13:1 on the field background, 2 px offset |
| 5 | Does the page really reflow at 320 px with the table exception contained (1.4.10)? | **Yes, measured** — `scrollWidth === 320`; the table's 1140 px lives inside a 242 px scroll container (the exception), and the *affordance* gap is F18 |
| 6 | Does an `autocomplete` token fit the field, and does the field collect the user's own information? | **No token needed** — all four invite controls collect another person's data and the two filter controls are search/filter fields; absence is correct, and no wrong token is claimed (§5.2) |
| 7 | Does an `aria-modal` dialog meet both preconditions, and where does initial focus land? | **Yes / native** — `aria-modal` is absent because `<dialog showModal()>` supplies real modality (`:modal` true); focus lands on the close control in the invite dialog and on `Vazgeç` in the confirmation |
| 8 | Is a conditionally revealed question announced when it appears? | **n/a** — no conditional reveal exists on this feature |

---

## 11. One-paragraph summary for the axis owners

The users area is mechanically clean (six axe states, zero violations) and its dialog,
validation and labelling mechanics are better than most admin surfaces: native modality with a
working trap and a correct focus return, submit-time validation with a linked error summary,
confirmations that name the person and the effect, Turkish case-folding done right, and
contrast that clears AA in both colour schemes. It fails at the layer seams, and the failures
are not cosmetic: **the surface's only two mutating capabilities cannot complete for any
account** in the configuration the product ships (F1), the end-to-end suite that would have
caught it passes only because its fixture rewrites a demo tenant into the platform
organization (F2), the invitation reaches nobody (F3), the audit trail loses the word
"deactivate" on the route the UI actually uses (F4), the list contract cannot express the
search the surface performs and this is the only list surface that ignores the pagination
envelope its siblings honour (F5), and a deactivated member's row will read `Aktif` beside
`Pasif` the first time the data contains one (F6). The interaction layer adds one more of exactly
the class the method exists to find: a control still showing a state the view no longer has —
after "Filtreleri temizle" the membership select keeps reading the filter that was just cleared
(F19), and a URL-driven check cannot see it. Three of those need capabilities that do
not exist yet (P1, P2, P3) and one needs an audience-scoped role list (P4); none of them is
fixable by editing a screen.
