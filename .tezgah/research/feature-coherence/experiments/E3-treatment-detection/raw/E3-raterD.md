# feature-audit — Ustam admin users area (rater D)

Feature: **the organization-user entity as the platform panel manages it** — every action
an operator can take on a user (list, filter, invite, edit role/scope/membership,
deactivate, reactivate), plus the screens, server actions, endpoints, guards and rows
that carry those actions.

Boundary (files in scope): `apps/admin/app/(dashboard)/users/{page.tsx,actions.ts,user-labels.ts}`,
the components it renders (`AdminModal`, `AdminActionForm`, `ConfirmationDialog`,
`MutationNotice`, `PageHeader`), `apps/admin/lib/{api,admin-context,mutation-guard,mutations,admin-panel-session,admin-surfaces}.ts`,
`apps/api/src/users/{users.controller.ts,users.service.ts}`, `apps/api/src/auth/admin-panel.guard.ts`,
`packages/domain/src/{users.ts,permissions.ts}`, and the generated contract
`packages/api-client/src/generated/schema.ts`. The sibling surface for the same action is
`apps/mobile/src/features/users/` (same endpoints, different UI).

Environment: running app read on 2026-09-20 — panel `http://localhost:3000` (API
`localhost:3001/api/v1`), signed in as the platform owner. The panel reads exactly one
user (`Platform Sahibi` / `platform@servistek.test`, status ACTIVE, membership ACTIVE,
scope organization, role SUPER_ADMIN) and the platform organization's role table holds
exactly one row (`SUPER_ADMIN`). No mutation reached the API: the two submissions made in
this pass were both refused before any call (browser validation; the action's
`SUPER_ADMIN` guard), so nothing was written to the shared database.

## Passes run (3)

1. **First-time operator, browser, 1280 CSS px** — the page walked end to end; the invite
   dialog opened and its control set read.
2. **Daily operator, 320/768/1280 CSS px + control states** — widths measured, reflow
   measured, the invite dialog's two error paths exercised (empty submit; a filled submit
   taken through the confirmation), focus and target sizes measured, screenshots read.
3. **API client with no UI** — the published contract (`schema.ts`) and the controller's
   route/permission pairs read, plus an unauthenticated probe against both endpoints.

Not run: axe-core. No local copy exists and the page could not load a CDN copy, so the
automated half is `[NOT CHECKED]` and every accessibility claim below is a hand-check
(computed styles, measured boxes, read screenshots). Contrast and target size were
measured numerically rather than through `axe`.

## Finding register (most severe first)

Severity is 0–4 on frequency × impact × persistence. Every row names one evidence class:
`behaviour` (a request/response or state transition observed), `ui-observed` (measured or
read off the running screen), `code` (cited source), `external`, `user-verbatim`.

| # | Sev | Finding | Evidence class | Citation | Prevent |
|---|---|---|---|---|---|
| F1 | 4 | **The invite offers only the one role both guards refuse, so no invite can be completed from the panel.** The role select is built from `/users/roles` unfiltered; the panel session pins the caller to the PLATFORM organization, and the platform organization's role table contains exactly one row, `SUPER_ADMIN`; the action then refuses exactly that value before calling the API. Live: the select rendered one option, `SUPER_ADMIN`, selected by default. | `ui-observed` (the single-option select, read in the running dialog) + `code` | `apps/admin/app/(dashboard)/users/page.tsx:107-119` (`roles.map` unfiltered; default `roles[0]?.key`), `apps/api/prisma/seed-role-permissions.ts:66-68` (the platform org's only seeded role is `SUPER_ADMIN`), `apps/api/src/auth/admin-panel.guard.ts:32-40` (session = PLATFORM org + SUPER_ADMIN), `apps/admin/app/(dashboard)/users/actions.ts:61` (refusal) | An assertion that every `<option>` the invite form renders is accepted by the action's guard: render the page for an org whose role list is exactly `[SUPER_ADMIN]` and assert the rendered option set contains no value in the refused set. Fails today. |
| F2 | 4 | **An invite reaches nobody: no mail, no link, no token — only a push to a device the new user cannot own.** `invite` creates the user, membership and role, records an outbox event whose payload is `{membershipId}`, and returns. The only consumer of `UserInvited` is the push handler, addressed to the invited user's own id; a freshly created user has no device token. There is no mail provider call anywhere in `apps/api/src` (grep `nodemailer\|sendMail\|MailService\|EmailService`: 0 hits), and the `/davet?token=` link belongs to the growth referral feature, not to team invites. The recipient gets an ACTIVE account whose password is a random string nobody ever sees. | `code` | `apps/api/src/users/users.service.ts:113-176` (create + `UserInvited` payload), `apps/api/src/worker/push-notification.handler.ts:74,135` (only consumer, recipient = `aggregateId`), `apps/api/src/growth/growth.service.ts:266-267` (the `/davet` link is the referral flow), `packages/domain/src/notifications.ts:26` | A contract test asserting `UserInvited` has a consumer whose channel the recipient can reach before having a device (a mail-task or an invite-token consumer). Fails today: the push handler is the only one. Proposal **P1** covers the fuller fix. |
| F3 | 3 | **`User.status = INVITED` is never written, and the label map does not match the enum.** `invite` creates the account with `status: 'ACTIVE'`. The panel carries a badge and a label for `INVITED` (unreachable) and two labels — `DEACTIVATED`, `DELETED` — that are not members of `UserStatus` at all, while the reachable-but-never-listed `ARCHIVED` has no label and would print its raw key. | `code` | `apps/api/src/users/users.service.ts:127`, `apps/api/prisma/schema.prisma:39-44` (`INVITED\|ACTIVE\|SUSPENDED\|ARCHIVED`), `apps/admin/app/(dashboard)/users/user-labels.ts:17-22`, `apps/api/src/users/users.service.ts:29` (list drops `ARCHIVED`) | A test asserting `Object.keys(userStatusLabels)` equals the `UserStatus` enum members. Fails today (2 extra keys, 1 missing). |
| F4 | 3 | **Two routes for one action, and the dead one owns the audit vocabulary.** `POST /users/{id}/deactivate` exists, is published in the generated contract, and no client calls it. The panel deactivates through `PATCH /users/{id}` `{active:false}`, which records `user.update` with `{changed:['active']}`; the audit actions `user.activate` / `user.deactivate` are produced only by the unreachable `setActive`. Absence proof: `grep -rn "users/" --include=*.ts --include=*.tsx --include=*.mjs apps packages/sdk packages/api-client/src`, excluding `node_modules`, `generated/`, `.next*` and `*.test.*` → the only call sites are `/users/invite` POST (admin + mobile), `/users/{id}` PATCH (admin + mobile) and `/users/roles` GET (admin). | `code` | Callers: `apps/admin/app/(dashboard)/users/actions.ts:62,89`, `apps/admin/app/(dashboard)/users/page.tsx:59`, `apps/mobile/src/features/users/organization-users-api.ts:47,56`. Route: `apps/api/src/users/users.controller.ts:82-91`; contract `packages/api-client/src/generated/schema.ts:2761`; audit `apps/api/src/users/users.service.ts:268` vs `:217` | A route-coverage check in the API contract suite: every operation in the generated schema must have at least one non-test caller. Fails today for `users-deactivate`. |
| F5 | 2 | **A detail endpoint with no detail view and no caller.** `GET /users/{id}` is documented (`users-get`), permission-gated, returns a rich shape (`roles: [{key,name}]`) that no surface renders and no client requests — the mobile client only PATCHes this path (same absence proof as F4). | `code` | `apps/api/src/users/users.controller.ts:49-57`, `apps/api/src/users/users.service.ts:77-110`, `packages/api-client/src/generated/schema.ts:2729-2743,9329` | Same route-coverage check as F4: `users-get` fails it today. |
| F6 | 3 | **The pagination envelope is hardcoded false and the list is unbounded.** `list()` returns `page: { nextCursor: null, hasNextPage: false }` with no `take` and no cursor, while the panel loads every user and filters in memory; the count line reports "N kullanıcıdan M kayıt gösteriliyor" with no pager. The repo's own convention is real cursor paging (`paging.next`) in at least six sibling list services, and six sibling panel pages render a pager. | `code` | `apps/api/src/users/users.service.ts:26-64`, `apps/admin/app/(dashboard)/users/page.tsx:58-68,163-165`, convention: `apps/api/src/work-orders/work-orders.service.ts:131`, `apps/api/src/quotes/quotes.service.ts:86`, `apps/api/src/customers/customers.service.ts:130`, `apps/api/src/appointments/appointments.service.ts:103`, `apps/api/src/audit-logs/audit-logs.service.ts:52`; pager use: `apps/admin/app/(dashboard)/customers/page.tsx`, `…/work-orders/page.tsx`, `…/dispatch/page.tsx`, `…/audit/page.tsx` | A contract test over every list service: a response whose `page.hasNextPage === false` must come from a query that passed a limit. Fails today; plus a seeded two-page e2e. |
| F13 | 3 | **The last column is clipped with no scroll affordance.** Measured: the table is 1140 px wide inside a 924 px region at 1280, 686 px at 768 and 242 px at 320; the document itself never scrolls horizontally (`documentElement.scrollWidth === innerWidth` at all three widths, so SC 1.4.10's document requirement and the table exception both hold). The rendered screen shows the last column cut mid-word — "Platform sahibi erişin" at 1280, "platform@ser" at 320 — with no fade, no visible scrollbar (overlay scrollbars) and no hint. The region is keyboard-reachable and labelled (`tabIndex=0`, `role=region`, `aria-label="Kullanıcı listesi"`), which is the only signal it scrolls. | `ui-observed` (measured boxes; two screenshots read) | `apps/admin/app/(dashboard)/users/page.tsx:167-178`; measurement above | A measured e2e assertion: when `wrap.scrollWidth > wrap.clientWidth` the region exposes an affordance (a sticky first column or an edge shadow). An assertion of *document* overflow passes while the column is clipped, so the assertion must be on the region, and the screenshot must be read. |
| F7 | 2 | **Two different fields print the same word in one row.** For the platform owner the row reads `Durum: Aktif` and `Üyelik: Aktif` — an account status and a membership flag, distinguishable by no operator, and able to diverge (`SUSPENDED` account + active membership, or `ACTIVE` account + inactive membership, which the "Pasif" filter then hides). | `ui-observed` (the live row) + `code` | `apps/admin/app/(dashboard)/users/page.tsx:185-199`, `apps/api/src/users/users.service.ts:50-62` | A rendering test asserting no two cells of one row carry the same accessible text for different fields. Fails today. |
| F8 | 2 | **The permission gate is unreachable, so its states and its conditional column are dead.** The page can only render behind `requireSuperAdminPanelSession`, whose proof requires the `SUPER_ADMIN` role; `SUPER_ADMIN` holds the whole permission list, so `canInvite`/`canUpdate` are always true. Both `lockedSurface` branches never render and the `canUpdate ?` column is unconditional. The non-super-admin path could not be exercised live. | `code` | `apps/admin/lib/admin-panel-session.ts:11-16`, `packages/domain/src/permissions.ts:88`, `apps/admin/app/(dashboard)/users/page.tsx:46-57,137-142,178,201`, `apps/api/src/auth/admin-panel.guard.ts:32-40` | An assertion that every branch of the page is reachable for at least one admitted caller: render the page for the minimum permission set the session guard admits and assert no read-only notice appears. Fails today (the branch is dead, so it is asserted only by a fixture). |
| F9 | 2 | **One enum, three label sources, two of them disagreeing across surfaces.** Panel `roleLabels`/`scopeLabels` (also reused by `announcements/campaign-model.ts:142` and `membership/page.tsx:7`) versus mobile `userFacingLabel`: `DISPATCHER` = "Operasyon sorumlusu" vs "Operasyon planlayıcı"; `ORG_ADMIN` = "İşletme yöneticisi" vs "Kuruluş yöneticisi"; scope `organization` = "İşletmedeki kayıtlar" vs "Tüm organizasyon"; `team` = "Takım kayıtları" vs "Takımı". The API's own `role.name` is a third source used only as a fallback that can never fire, so an organization's chosen role name is never displayed. | `code` | `apps/admin/app/(dashboard)/users/user-labels.ts:1-16`, `apps/admin/app/(dashboard)/users/page.tsx:115,253`, `apps/mobile/src/design-system/user-facing-labels.ts:42,68`, `apps/mobile/src/features/users/OrganizationUsersScreen.tsx:36-41`, `apps/api/src/users/users.service.ts:69-75` | One label map per enum in `packages/domain`, with a test asserting the panel and the mobile design system resolve the same enum member to the same string. Fails today. |
| F11 | 2 | **A field-level refusal is delivered as a form-level error.** The `SUPER_ADMIN` refusal returns `{ error }` with no `fieldErrors`, so it renders in the form summary instead of beside the role select, which is left unmarked. Live: after confirming, the message appeared as a whole-form alert with `aria-invalid` absent from the select. The action's own `failure()` already maps `ALREADY_MEMBER` and `ROLE_NOT_FOUND` to `fieldErrors`, so the convention exists one function away. | `ui-observed` (the exercised path) + `code` | `apps/admin/app/(dashboard)/users/actions.ts:61,87-88`, `:18-50` (`failure`), `apps/admin/components/AdminActionForm.tsx:95-108` (the association mechanism) | A test over the action's refusal table asserting every refusal that names a control returns `fieldErrors` for it. |
| F16 | 2 | **The same field has three shapes across layers.** `roles` is `string[]` from `list`, `{key,name}[]` from `get`, `name` is selected by `list` and dropped by the panel, `string[]` in the panel's Response schema, and a strict enum array in the mobile schema. An API client that moves between the list and the detail endpoint gets a different type for one field name. | `code` | `apps/api/src/users/users.service.ts:39-45` (list) vs `:95-105` (get), `apps/admin/app/(dashboard)/users/page.tsx:13-30`, `apps/mobile/src/features/users/organization-users-api.ts:15-27` | A generated-contract test asserting one schema per field name across the `users` operations. Fails today. |
| F17 | 2 | **The list is sorted with no indication and no control.** `orderBy: { displayName: 'asc' }` is applied server-side; no header carries `aria-sort`, the sort direction is invisible and cannot be reversed. The repo's shared `Table` primitive exposes `TableHeader sortable/sorted` (with a text arrow, itself without `aria-sort`), and no page in the app imports it. | `code` + `ui-observed` (no `aria-sort` in the rendered table) | `apps/api/src/users/users.service.ts:47`, `apps/admin/app/(dashboard)/users/page.tsx:170-178`, `apps/admin/components/Table.tsx:21-37` | Assert on the rendered header row: the column whose value the server sorts by carries `aria-sort` (or the table renders no sorted column). Fails today. |
| F12 | 1 | **A stale error summary survives a corrected retry.** Live: after the empty submit produced "İşaretli alanları düzeltin.", filling both fields and opening the confirmation left the same alert visible under a form that now validates (`result` is cleared only inside `send()`, after confirmation). | `ui-observed` | `apps/admin/components/AdminActionForm.tsx:222-257` (`onSubmit` opens the confirmation without clearing `result`), `:150-158` (`setResult({})` runs only in `send`) | An e2e assertion that opening the confirmation leaves no `[role=alert]` inside the form. |
| F14 | 1 | **The empty state is nested inside the table's scroll region, after the header row.** With `?q=zzz` and with `?state=inactive` the page keeps the 7-column `thead` and appends the message inside `.tableWrap`, so the message also lives in the 242 px scroll region at 320. | `ui-observed` (`?q=zzz`, `?state=inactive`) + `code` | `apps/admin/app/(dashboard)/users/page.tsx:167-170,288-291` | An e2e assertion that a zero-row result renders no `thead` (the empty state replaces the table). |
| F18 | 1 | **The locked surface bypasses the app's permission-notice primitive.** The users page hand-rolls `section.lockedSurface` with `role="alert"`; ten sibling surfaces render `AdminPermissionNotice`, which carries the permission key in `data-required-permission` for support and never leaks it into the visible text. The hand-rolled branch is also the dead one (F8). | `code` | `apps/admin/app/(dashboard)/users/page.tsx:52-56,138-142`, `apps/admin/components/AdminPermissionNotice.tsx:1-30`, used by `apps/admin/app/(dashboard)/{customers,organizations,registration,work-orders,quotes,training,rewards,announcements,support,ai-governance}/page.tsx` | A lint/test assertion that a page rendering a permission barrier uses `AdminPermissionNotice`. Concrete today: no `data-required-permission` exists for this surface, so support cannot name the missing permission. |
| F10 | 1 | **A transported field no view renders.** `locale` is selected by the API, declared in the panel's Response schema and never rendered; the page's own copy points at it ("Ad ve dil değişikliklerini kullanıcı kendi profilinden yapar") while the write path refuses it. `role.name` (F9) and the whole `users-get` shape (F5) are in the same class. | `code` | `apps/api/src/users/users.service.ts:37,43`, `apps/admin/app/(dashboard)/users/page.tsx:20,164-165`, `apps/api/src/users/users.service.ts:327-332` | No mechanical prevention exists for "transported and never rendered": a schema test passes and a render test needs the field named by hand. This stays a review item. |
| F15 | 1 | **One field's default disagrees across layers.** The contract defaults `scope` to `organization`; both surfaces default it to `assigned`, so the contract default is dead code. | `code` | `packages/domain/src/users.ts:8`, `apps/admin/app/(dashboard)/users/page.tsx:122`, `apps/mobile/src/features/users/OrganizationUsersScreen.tsx:55` | A contract test asserting a field both surfaces always send has the same default in the schema as on the surfaces. |

Pass rows (agreement between layers — the control that shows the matrices were filled
honestly): see each matrix's "pass rows" line.

## Matrix 1 — capability

| Action | Surface | Route | Authorization | Service / validation | Persistence | Verdict |
|---|---|---|---|---|---|---|
| List users | yes — table renders 1 row (`page.tsx:167-292`) | yes — `GET /users` (`controller.ts:34-38`) | yes — `@RequirePermissions('user.manage')` + panel session; unauthenticated probe → 401 | yes — `list()` (`service.ts:26`) | yes — `prisma.user.findMany` scoped by `organizationId` | pass |
| Filter / search | yes — GET form, `q` + `state` (`page.tsx:145-162`) | no — the route takes no query (`controller.ts:34`) | n/a | no — filtering is in-memory in the server component (`page.tsx:60-68`) | n/a | pass, with F6: no server-side filter and no page window, so the filter can only ever see the rows one unpaged response carried. Turkish casefold **works** (`?q=SAHİBİ` → 1 row, `?q=sahibi` → 1 row, live) |
| Invite a member | yes — dialog trigger + form (`page.tsx:74-136`) | yes — `POST /users/invite` (`controller.ts:59-68`) | yes — `team.invite` → `user.manage` (`mutations.ts:29`, `actions.ts:53`) | yes — `InviteUserInput` zod + `assertGenericRoleAssignment` | yes — user + membership + membershipRole in one transaction | **F1** (the surface can offer no assignable role), **F2** (no delivery), **F3** (no INVITED state) |
| Edit role / scope | yes — per-row modal (`page.tsx:231-267`) | yes — `PATCH /users/{id}` (`controller.ts:70-80`) | yes — `team.update` → `user.manage` | yes — `UserUpdateInput`, `ROLE_NOT_FOUND`, SUPER_ADMIN refusal | yes — membershipRole replaced wholesale | pass, with F9 (labels), F16 (`roles` shape) |
| Deactivate membership | yes — the `Üyelik` select's "Pasif" option, hidden for self (`page.tsx:269-276`) | yes — `PATCH` `{active:false}` | yes | yes — `SELF_DEACTIVATE` refusal server-side (`service.ts:181-187`); the client hides the option but does not enforce it | yes — plus `revokeMembershipAccess` revoking push tokens, sessions and device activations (`service.ts:275-320`) | pass on enforcement (both sides hold); **F4** on the dead second route and the lost `user.deactivate` audit action |
| Reactivate membership | yes — dedicated form per inactive row (`page.tsx:208-230`) | yes — `PATCH` `{active:true}` | yes | yes — `INACTIVE_MEMBERSHIP_REACTIVATION_ONLY` (`service.ts:199-205`); the panel sends exactly `{active:true}` | yes | pass — the service's precondition and the surface's single-purpose form agree |
| View a user's detail | **no** — no detail view exists | yes — `GET /users/{id}` (`controller.ts:49-57`), published as `users-get` | yes | yes | read-only | **F5**: a layer yes / surface no, and no client calls it |
| Deactivate (dedicated route) | no surface calls it | yes — `POST /users/{id}/deactivate` (`controller.ts:82-91`), published as `users-deactivate` | yes | yes — `setActive` | yes | **F4**: two routes for one action; the dead one carries the audit action |
| Assign the platform-owner role | no — the panel's refusal path (`actions.ts:61`) | — | — | yes — `SUPER_ADMIN_PROVISIONING_REQUIRED` (`service.ts:344-349`) | — | pass: the product forbids it everywhere (`page.tsx:206`, `:87-88`), but see **F1** — the refusal is what makes the form unusable in the panel's own tenant |
| Change name / locale | no — the page says self-service (`page.tsx:164-165`) | route exists and accepts the fields (`users.ts:28-29`) | yes | yes — always `403 GLOBAL_PROFILE_SELF_SERVICE_REQUIRED` (`service.ts:327-332`) | — | pass on outcome, **F10** on the contract carrying two fields no caller may write |
| Archive a user | no surface, no route | no | — | no | `UserStatus.ARCHIVED` exists and `list` filters it (`service.ts:29`) | **F3** — an enum member with a read path and no write path |

Sibling-convention readings used: mobile offers a fixed 6-role list excluding
`SUPER_ADMIN` (`OrganizationUsersScreen.tsx:28-37`) where the panel offers the org's role
table unfiltered; mobile's invite and edit call the same two endpoints, so the panel is not
a second implementation of a different contract.

## Matrix 2 — field contract

| Field | Column / type | Read by the API | Written by the API | Rendered (list / detail / form) | Validated | Label or enum source | Locale / format |
|---|---|---|---|---|---|---|---|
| `id` | `String @id` | yes (`list`/`get`) | never | not rendered; used as `key` and as a hidden form field | `z.uuid()` (`actions.ts:76`) | — | n/a |
| `displayName` | `String` | yes | **create only** — `UserUpdateInput` accepts it, the service always refuses it | list ✓ ("Ad"), form ✓ (invite) | `min(1).max(120)` in the contract; `required maxLength=120` on the surface | none needed | renders raw — pass |
| `email` | `String` + `normalizedEmail` | yes | create only, normalized (`normalizeEmail`) | list ✓, form ✓, never edit | `z.email()` + `required type=email` | none needed | audit stores a redacted form (`service.ts:352-355`) — pass |
| `status` | `UserStatus` | yes | create sets `ACTIVE`; `INVITED`/`SUSPENDED`/`ARCHIVED` unwritten | list ✓ as a badge | enum | panel map vs enum mismatch — **F3** | label map has 2 dead and 1 missing member — **F3** |
| `locale` | `String` | yes | never by this feature | **never rendered** | `max(10)` | — | — **F10** |
| `membership.scope` | `ResourceScope` | yes | yes (invite + PATCH) | list ✓, edit form ✓ | `z.enum` of 4 | panel map vs mobile map disagree — **F9**; default disagrees — **F15** | pass |
| `membership.active` | `Boolean` | yes | yes | list as "Aktif/Pasif" AND the edit form's select | client hides self-deactivation, server enforces `SELF_DEACTIVATE` | — | **F7** (same word as `status`) |
| `membership.roles` | `MembershipRole[]` | yes | yes — replaced wholesale | list ✓ (joined keys); read as N, written as 1 | `roleKey` enum (7 values incl. `SUPER_ADMIN`) | 3 sources — **F9**, shape differs per endpoint — **F16** | pass |
| `role.name` | `String` (org-scoped) | selected by `list` and by `/users/roles` | — | never rendered (the fallback cannot fire) | — | third label source — **F9** | — |

## Matrix 3 — flow and step contract

The invite is the only multi-part flow: **form → confirmation → submit → redirect
notice.** One step, so the row is read as the whole flow.

| Step | Precondition | What it validates | What it writes | How a skip is prevented | Resume / persistence | Back-navigation retention | Where an error lands |
|---|---|---|---|---|---|---|---|
| Invite form | `team.invite` permission + panel session (F8: always true) | `required` on Ad/E-posta (native), zod on the server, `assertGenericRoleAssignment` for the role | user + membership + membershipRole + audit + outbox | no skip exists; the dialog is the only entry | none — a reload loses the values (a `beforeunload` guard exists, `AdminActionForm.tsx:139-148`) | identical to persistence: values live in the DOM only | client `invalid` → the form's own alert summary with focus-to-field (live); server zod → `fieldErrors`; `SUPER_ADMIN` refusal and `AdminApiError` → form-level alert (**F11**) |
| Confirmation | form filled | nothing (summary only) | nothing | n/a | n/a | n/a | reopens with a stale error visible (**F12**) |
| Submit | confirmation accepted | the action's guard, then the API's zod | as above | double-submit locked (`locked.current`) | `revalidatePath('/users')` + `redirect('/users?result=…')` — **the filter's `q`/`state` are dropped by the redirect and nothing announces the loss** | n/a | success notice via `MutationNotice` (`resultMessages['user-invited']`) |

Live measured: the native validation is **not** suppressed (`novalidate` absent) — the
browser's own invalid handling runs, its focus moves to the first invalid control, and the
component's `invalid` listener mirrors the result into a `role=alert` summary. The skill's
rule asks for `novalidate` with one mechanism; this build keeps both, and the measured
result is a summary whose items are not associated with their fields (`aria-invalid` and
`aria-describedby` were absent on `displayName` at the moment measured) — recorded as a
hand-check observation under Matrix 5 rather than a separate finding, because the code
intends the association (`AdminActionForm.tsx:96-115`) and I could not settle whether the
attribute is removed by the effect's cleanup or never applied.

## Matrix 4 — interaction dependency

| Trigger | Dependents | Required action on change | Who owns the state | What is announced | Verdict |
|---|---|---|---|---|---|
| `q` / `state` filter submit | the result set, the count line | recompute | the server (GET form, full navigation) | a page load — the count is not a live region, which is correct for a navigation | pass (live: `?q=zzz` → 0 rows, count "1 kullanıcıdan 0 kayıt", `?state=inactive` → 0 rows) |
| Successful invite / update (`redirect('/users?result=…')`) | the `q` value, the `state` value | reset | the URL | nothing: the notice names the mutation, not the discarded filter | **finding** — a value the operator chose is discarded silently when the redirect drops `q`/`state` (sev 2, `ui-observed` by the redirect target in `actions.ts:71,98` + the live URL after the exercised submit) — Prevent: carry the filter into the redirect or state in the notice that the filter was cleared; assert it in an e2e |
| Invite dialog: role select | scope, membership | keep (no server rule couples them) | the form | n/a | pass |
| Edit dialog: `active` → "Pasif — erişimi kaldır" | `roleKey`, `scope` | keep — the service applies all three in one transaction (`service.ts:206-232`) | the form | the confirmation body names the consequences (sessions and device access removed) | pass |
| Edit dialog: `active` select for one's own row | the "Pasif" option | — | — | — | pass: the option is not rendered for self (`page.tsx:271-275`) and the service refuses it independently (`service.ts:181-187`) — a client+server pair that agrees |
| "Filtreleri temizle" link | `q`, `state` | reset | the URL | the controls reset with the page | pass (live: both values cleared) |
| Role select change | nothing | keep | — | — | pass — but see **F1**: the *only* option is refused, so the cascade that matters is missing at the data layer, not the UI layer |

## Matrix 5 — surface pattern

### Data views

| Rule | Verdict |
|---|---|
| SC 1.3.1 real headers + labelled table | **pass** — `<th scope="col">` ×7, `<caption class="srOnly">`, region `aria-label="Kullanıcı listesi"` (`page.tsx:167-178`) |
| `aria-sort` on the sorted column, reversible | **violation — F17** (sorted by `displayName asc`, no `aria-sort`, no control) |
| Editable cells make it a grid | n/a — cells are not editable; each row carries one trigger button. The large-N tab-stop cost could not be measured (one-row data) — `[NOT CHECKED: single row]` |
| `aria-rowcount`/`aria-colcount` for lazy data; position restored from detail | n/a — not virtualized, and no detail view exists (F5) |
| SC 1.4.10 one-direction scroll at 320, table inside its own container | **pass, measured** — `documentElement.scrollWidth === innerWidth` at 320/768/1280; the table scrolls inside `.tableWrap` (`overflow-x: auto`) |
| Pagination: `aria-current`, labelled nav, one-page pager hidden | n/a — no pager exists at all (**F6**) |
| Content: captions/headings describe the data, first column is a human identifier, headers stay visible | pass — "Kullanıcı listesi", first column `Ad` = the person's name; headers are not sticky, and the five headings are short nouns |
| Filters discoverable and their active state visible in the results | **partial** — the controls keep their values (`q=zzz` stayed in the input) but nothing on the result region says it is filtered (**finding**, sev 1, `ui-observed`: the `?q=zzz` render is indistinguishable from an unfiltered empty list except by the input's value) — Prevent: render the active filter on the region or a "filters applied" status |
| Detail view: `dl` key/value, every field a value or "not provided" | n/a — no detail view (**F5**) |
| A scroll region says it scrolls | **violation — F13** |
| Long text has a strategy | **violation, same evidence as F13** — at 320 the email value is cut mid-string ("platform@ser") inside the region with no truncation affordance and no title. Longer values could not be tested: `[NOT CHECKED: the tenant holds one user, no long values]` |

### Controls

| Rule | Verdict |
|---|---|
| Visible persistent labels (never a placeholder as label) | pass — every control is wrapped in a `<label className="field">` with a `<span>`; measured placeholders are not lightened (`::placeholder` = `rgb(25,32,26)`) and none is used as a label |
| SC 1.3.5 scoped: an `autocomplete` token on self-data fields, `off`/absent on search and record fields | pass — the only free-text fields are the search box (no token, correct) and another person's name/e-mail (no token, correct) |
| One required/optional convention | pass, with a note: `required` is on the two text inputs and not on the two selects, which cannot be empty because they carry defaults — the convention is consistent with what can fail |
| `APG disclosure` for show/hide | pass — the modal is a button with `aria-haspopup="dialog"`, not a link toggling content (`AdminModal.tsx:98-115`) |
| `APG tabs` | n/a — none |
| A conditional reveal reveals a question and announces it | n/a — the dialog reveals the whole form on open, which is a dialog, not a conditional reveal |
| Pickers: text entry plus a known list for a combobox | n/a — role and scope are native `<select>`s; the date-picker rules do not apply |
| SC 2.5.8 target size ≥24×24, design floor where higher | **pass, measured** — invite trigger 966×44, search 201×44, state select 100×44, Filtrele 93×67, Filtreleri temizle 165×67, dialog close 36×36, dialog submit 141×44; nav items 214×44 |
| SC 2.4.7 / 1.4.11 focus visible | **pass, measured** — the focused trigger reports `outline: solid 3px rgb(20,95,192)` with `:focus-visible` matching, on the real background |
| SC 1.4.3 contrast 4.5:1 and no colour-only signalling | **pass, measured** — status badge 14.5:1 (12 px), muted count line 5.83:1, table header 5.83:1, h1 15.61:1; status is text, not colour alone (the badge class varies but the text carries the state) |

### Validation and errors

| Rule | Verdict |
|---|---|
| Validation on submit, failing values kept, server validation present, native validation suppressed | **partial** — submit-time and both layers present, values kept (uncontrolled inputs), but native validation is not suppressed (`novalidate` absent) and both mechanisms fire; live: the browser focused `displayName` while the component also wrote a summary |
| SC 3.3.1/3.3.3 the item in error is identified and the correction described in text | **partial** — the summary names the field ("Bu alanı doldurun." is generic; the server's `fieldHelp` map is specific, e.g. "1–120 karakter arasında bir ad girin.") and the form is never re-displayed blank; the client-side message does not say what to correct |
| Association: `aria-describedby` to the message, same wording in summary and beside the field, focus moving to the field | **partial, hand-checked** — the summary entry is a button that focuses the field (pass), but at the moment measured the field carried no `aria-invalid`/`aria-describedby`; there is no beside-the-field message at all, so the summary is the only surface. `[NOT CHECKED: whether the attribute is applied-then-cleared or never applied — one measurement showed absent]` |
| An error summary at the top of the form naming each item | pass — one `role=alert` block, focused on appearance, listing each failing field with its own focus button; its wording is Turkish and does not leak a status code |

### Flows

| Rule | Verdict |
|---|---|
| One question per page, unique heading, back link and Continue | n/a — one-step dialog |
| Check-your-answers: pre-populated, Change link naming what it changes, submit naming its action | pass in substance — the confirmation prints each field's label and current value (hidden controls printed as "—") and the confirm button names its action ("Daveti oluştur" / "Erişimi güncelle"); there is no Change link because the form is directly behind the confirmation |
| SC 3.3.7 redundant entry | pass — nothing is asked twice |
| SC 3.3.4 irreversible change confirmed, with a named object | **pass** — the confirmation names the person and states what is lost ("Pasife alma bu işletmedeki oturumları ve cihaz erişimini kaldırır"), which is the value at stake; deactivation is revocable by reactivation, so an undo path exists |
| Destructive confirmation names what is lost, keeps actions inside the panel, reserved for the irreversible | pass as above; the confirmation is a portalled `showModal` dialog so its actions are inside it |
| `APG dialog`: modality real, focus in on open and stays, returns to the invoker, `alertdialog` focuses the least destructive action | **pass, measured** — native `showModal()` supplies inertness; focus moved in (measured landing on the dialog's close control) and the confirmation focuses "Vazgeç" (`ConfirmationDialog.tsx:30-31`); the modal traps Tab manually because Safari leaks it (`AdminModal.tsx:123-152`) |

### Notifications

| Rule | Verdict |
|---|---|
| SC 4.1.3 changes without focus movement are programmatically determinable | pass where it applies — the mutation notices are `role="status"` / `role="alert"` (`MutationNotice.tsx:119,133`; `AdminActionForm.tsx:268-279`); the filter is a full-page GET navigation, so the count change rides a page load |
| The whole status string is the announced unit; the end of a wait is announced | pass — one sentence per notice; the pending label is a single `role="status"` string ("İşlem kaydediliyor…") and it is replaced by the result |
| Non-status changes stay out of live regions | pass — the field-error summary uses `role="alert"` only on failure and the disclosure force focuses it rather than announcing |
| A banner is `role=region` with a label, before the h1, at most one, never standing in for validation errors | pass — the notice renders after `PageHeader`'s h1 and is not used for validation (the form owns its own errors) |

## Capability-change proposal

### P1 — Invitation delivery and state (`code`; the only finding whose fix names layers that do not exist)

Required by **F2** and **F3**: the surface offers "Takım üyesi davet et", records
"Takım daveti oluşturuldu", and the page's copy calls the result a davet (invitation) —
while the system has no invitation as a first-class thing. Two layers are absent: nothing
mints a verifiable invitation, and nothing can deliver one to a person who has no account
yet. A screen-level fix cannot produce either, so this is a proposal, not a UI finding.

| Heading | Content | Falsified by |
|---|---|---|
| Capability | A person who has been invited to an organization can accept that invitation and sign in, without an operator transmitting a secret out of band | a cited code path that already delivers an invitation or a credential to the invited address |
| Absence proof | `apps/api/src/users/users.service.ts:113-176` writes the account, membership and role and emits `{membershipId}`; the only consumer of that event is `apps/api/src/worker/push-notification.handler.ts:74,135`, addressed to the new user's own device; no mail call exists in `apps/api/src` (grep `nodemailer\|sendMail\|MailService\|EmailService` → 0), and no `INVITED` write exists (grep `status: 'INVITED'` outside tests → 0). The input that fails: an invitation created for an address with no account and no device | a cited path that delivers a token or a credential to the invited address, or that writes `User.status = INVITED` |
| Contract delta | (a) Prisma migration: new `MembershipInvitation` model — `id`, `organizationId`, `userId`, `tokenHash`, `expiresAt`, `consumedAt`, `createdByUserId`; `UserStatus` already carries `INVITED` so no enum change; (b) `packages/domain/src/users.ts`: `AcceptInvitationInput = z.object({ token: z.string().min(32).max(1024), password: z.string().min(12) })`; (c) two operations in the generated schema: `POST /users/invitations/{id}/reissue` and `POST /auth/invitations/accept`; (d) the permission rule is unchanged (`user.manage`) | running the contract generator and the migration diff and getting green with no diff, or a compatibility checker failing on an intended break |
| Migration | expand: add the table and a nullable `invitedAt` on `Membership`, both unused by existing rows; migrate: backfill nothing (tokens are only minted going forward; existing ACTIVE accounts keep their current password path); contract: drop the now-unused random-password branch — dated step, no earlier than two releases after expand, only after no invitation row has an `invitedAt` older than one token lifetime | a contract phase with no date and no "no live rows" precondition |
| Rollout | flag `user.invite.delivery` (boolean, lifetime: until the migration's contract phase completes, then deleted), initial exposure: the panel organization's own operators (it has one member, so one operator — deliberately the smallest blast radius), kill-switch owner: the panel operator, abort threshold: >5% of `UserInvited` events ending in delivery failure over a 24-hour window after ≥20 invitations | an unmeasurable threshold, or a flag with no lifetime |
| Verification | (1) a new assertion in `apps/api/src/users/users.service.test.ts` that `invite` emits an outbox payload carrying an invitation handle and that `MembershipInvitation.tokenHash` is set — fails before, passes after; (2) an e2e step in `apps/api/scripts/run-admin-playwright-e2e.mjs` that creates an invitation, reads the emitted link from the outbox/mail sink, opens it and completes a sign-in — fails before, passes after | a check that also passes on the pre-change commit |
| Reversibility | The new path writes invitation rows and, on acceptance, a password hash plus a consumed status. One-way door for the accepted password only: restore = revoke the membership and re-issue a reset, both existing actions; the invitation table itself is droppable with no user-visible loss. Labelled here because the acceptance write is not reversible by dropping the flag alone | data written with no restore step and no label |
| Decision | ADR `invitation-delivery` — context: the panel announces an invitation the system cannot deliver (F2, F3); decision: a hashed, expiring token delivered by mail, `INVITED` as the pre-acceptance status; status: proposed; consequences: one new table, a mail template, a token lifetime to operate; supersedes the implicit decision that a randomly-passed account is an invitation | an ADR without a status |
| Appetite | Time box: two weeks of one developer. Out of bounds: the growth referral token (`apps/api/src/growth/growth.service.ts`) must not be reused or generalized — it carries a different payload and a different trust boundary; the mobile `davet` route stays untouched. When the box ends: ship the existing-layer fallback instead — call the existing `PasswordResetService.request('MOBILE', { email })` from `invite` so the new account receives a real credential-mail through a path already in production — which closes F2 without any of the above | no box, or an implicit extension |

No other finding requires a proposal. Each remaining fix names a layer that already
exists: F1 filters a list the surface already fetches; F3 corrects an existing label map
against the existing Prisma enum; F4/F5 delete or cover routes that exist (or the
route-coverage check that names them); F6 uses the existing `paging` helper and an
existing pager pattern from four sibling pages; F7/F9/F10/F16 are labels, schemas and
renders inside existing files; F8 removes unreachable branches or relaxes an existing
guard; F11 returns `fieldErrors` through an existing mechanism; F12/F13/F14/F17/F18 are
changes inside `AdminActionForm` and `globals.css`. None of them needs a flag, a
migration or a contract that does not yet exist, so none of them is a capability change.

## Coverage

| Matrix | Rows checked | Rows not checkable | What would change the conclusion |
|---|---|---|---|
| 1 Capability | 12 actions × 5 layers | The archive action has no surface and no route (checked by absence, not by execution). The non-super-admin caller could not be exercised: `[NOT CHECKED: no credential for a non-`SUPER_ADMIN` user; every such request is redirected to `/login?forbidden=1` by `admin-panel-session.ts:26]` | Two or more users in the platform organization with a non-`SUPER_ADMIN` role available: that would make F1 disappear for that tenant, but not for the platform tenant the panel is pinned to. A second organization kind mounting the panel would revive F8's dead branches |
| 2 Field contract | 9 fields × 8 columns | Nothing structural was unreadable; `role.name`'s rendering was settled by reading the fallback expression. | An organization that renames a role (F9's fallback would still not fire, because all seven keys are in the panel map) |
| 3 Flow / step | 1 flow × 3 steps, 7 columns | The success path of the invite was **not** executed (it would write to the shared database); every step up to the refusal was exercised live, so the redirect and the success notice are read from `actions.ts:71,98` and `MutationNotice`'s table, not observed. | A permitted role (F1) would let the success path be observed; a mail sink would let F2's fix be verified |
| 4 Interaction dependency | 7 triggers | Nothing was unreadable. The filter-cleared-on-redirect finding is read from the redirect target in code plus the live post-submit URL, not from a completed mutation. | A completed mutation would show the filter loss in the browser history |
| 5 Surface pattern | 38 rule rows across 5 sub-tables | `axe-core` did not run (`[NOT CHECKED: no local copy; the page could not fetch the CDN]`), so contrast, target size and focus were hand-measured rather than swept; the 43% axe cannot see was hand-checked as the skill requires. `[NOT CHECKED: `aria-invalid`/`aria-describedby` on a field in error — one measurement showed absent, and I did not settle whether the component's effect applies then clears it]` `[NOT CHECKED: large-N tab order and long-text behaviour — the tenant holds one short-valued user]` | A signed-in non-super-admin (no credential), a second seeded user with a long display name and an inactive membership, and an axe-core copy would each extend this |

What this pass did not look at: the audit page's rendering of `user.update` rows, the
mobile invite/edit screens beyond their API defaults and label maps, `/membership`'s use of
`scopeLabels`, the Resend provider's configuration (`PASSWORD_RESET_EMAIL_PROVIDER`'s value
in this environment is unread — the invite finding rests on the absence of any call, not on
the provider being off), and no competitor comparison was attempted (the ask is one
feature, not the product).

## What could not be produced

- No capability-change proposal beyond P1, because no other fix names an absent layer (stated per finding above, which is the check a reviewer would run).
- No axe-core sweep, no recorded video, no session log of the API's own requests: the pages are server-rendered, so the capability rows were read from the code plus the API's guard, exactly the limit the skill names for a server-rendered surface.
- The invite's success path and any multi-user state (inactive membership, multi-role user, `SUSPENDED`, second page of results) could not be observed, because observing them requires writing to the shared database.
