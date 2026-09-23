# feature-audit — the users area of the Ustam admin panel

Rater: E3-raterB. Artifact applied: `skills/feature-audit/SKILL.md` (read in full, 324 lines).
Target repository state: `Ustam` at the working tree of 2026-09-20 23:0x–23:5x local, admin dev server
`http://localhost:3000`, API `http://localhost:3001/api/v1`, Postgres `servistek` — all live and shared.
Nothing in the Ustam repository was modified; no row was written to its database (verified below).

## 1. The unit

**One feature: administering the people who may use the panel** — one entity (`User` + its `Membership`
in the caller's organisation), every action a user can take on it, every surface and endpoint that
carries those actions.

- Entity: `User` (id, displayName, email, status, locale) x `Membership` (scope, active) x
  `MembershipRole` x `Role`.
- Actions: list, read one, read the assignable role list, invite, set role/scope/active, reactivate,
  deactivate, deliver the invitation.
- Surfaces: the panel route `app/(dashboard)/users` (table + toolbar + invite modal + row edit modal +
  the confirmation dialog), and the mobile screen `apps/mobile/src/features/users/OrganizationUsersScreen.tsx`
  (the same endpoints, a different surface — read only to establish the sibling convention, not audited).
- Endpoints: `GET /users`, `GET /users/roles`, `GET /users/:id`, `POST /users/invite`,
  `PATCH /users/:id`, `POST /users/:id/deactivate`.
- Files: `apps/admin/app/(dashboard)/users/{page.tsx,actions.ts,user-labels.ts}`,
  `apps/admin/components/{AdminActionForm,AdminModal,ConfirmationDialog,MutationNotice,Table}.tsx`,
  `apps/admin/lib/{mutations,mutation-guard,admin-context,api,admin-surfaces,login-handover}.ts`,
  `apps/api/src/users/{users.controller,users.service}.ts`, `apps/api/src/auth/{jwt-auth,permissions,admin-panel}.guard.ts`,
  `packages/domain/src/users.ts`, `apps/api/src/common/normalization.ts`,
  `apps/api/src/worker/push-notification.handler.ts`, `docs/api-contract.md`.

Reading the boundary also settled a fact that drives three findings: **the panel signs in only a
`SUPER_ADMIN` of a `kind = PLATFORM` organisation** (`apps/api/src/auth/auth.service.ts:33-42`,
`apps/api/src/auth/admin-panel.guard.ts:30-41`), and that organisation's role catalogue is exactly
`[SUPER_ADMIN]` (`apps/api/src/ops/super-admin-provisioning.ts:230-236`; observed live below).

## 2. Matrix 1 — capability

| Action | Surface (what a person can do) | Route | Authorization | Service / validation | Persistence |
|---|---|---|---|---|---|
| List the organisation's users | yes — table, `page.tsx:167-292` (ui-observed) | yes — `GET /users`, `users.controller.ts:34` | yes — `user.manage` (`users.controller.ts:35`) + page gate `canUseAdminMutation('team.invite'\|'team.update')` = same permission, `page.tsx:46-48` | `list()`, `users.service.ts:26-66`; no validation input; **no `limit`/`cursor`/`sort`/`q`/`state` argument** | `user.findMany` where `memberships.some{organizationId}` and `status != ARCHIVED`, `users.service.ts:28-31` |
| Read one user | **no** — the row is not a link and no detail view exists (search: `grep -n "users/\$\{" apps/admin/app` → only `actions.ts:89` PATCH; aria tree of `/users` has no link per row) | yes — `GET /users/:id`, `users.controller.ts:49` | yes — `user.manage` | `get()`, `users.service.ts:77-110` | `user.findFirst` scoped to `auth.organizationId` |
| Read the assignable role list | yes — two `<select name="roleKey">`, `page.tsx:105-121`, `page.tsx:249-257` (ui-observed: one option) | yes — `GET /users/roles`, `users.controller.ts:42` | yes — `RequireAdminPanel()` + `user.manage`, `users.controller.ts:43-44` | `listRoles()`, `users.service.ts:69-73` | `role.findMany where organizationId = caller's org` |
| Invite a user | **surface yes, but refused** — the modal's only possible value is rejected; exercised and refused (`Platform sahibi bu ekrandan atanamaz.`, role=alert) | yes — `inviteUserAction` (`page.tsx:74-140`) → `POST /users/invite`, `actions.ts:62`, `users.controller.ts:59` | yes — `requireAdminMutation('team.invite')` → `user.manage`, `actions.ts:50` | Zod `InviteUserInput` (`packages/domain/src/users.ts:11-25`) + `assertGenericRoleAssignment` (`users.service.ts:114,336-338`) | `user.create` + `membership.create` + `membershipRole.create` + audit + outbox, `users.service.ts:120-175` |
| Set a user's role | surface yes (`page.tsx:249-257`) but **no reachable row** (every row is SUPER_ADMIN → static note, `page.tsx:203-205`) | yes — `PATCH /users/:id`, `actions.ts:89`, `users.controller.ts:70` | yes — `team.update` → `user.manage` | `UserUpdateInput` (`domain:27-44`) + `assertMembershipOnlyUpdate` (`service:327-334`) + `assertGenericRoleAssignment` (`service:187`) + `assertGenericUserTarget` (`service:340-342`) | `membershipRole.deleteMany` + `create`, `service:225-233`; audit `user.update` |
| Set a user's scope | same as above (`page.tsx:260-267`) | same | same | same | `membership.update{scope}`, `service:217-222` |
| Deactivate a user (membership) | surface yes (`page.tsx:270-274`, the `false` option is omitted for your own row) — **unreachable** | `PATCH {active:false}` yes; **`POST /users/:id/deactivate` has no caller** (`users.controller.ts:82`; search over `apps/admin/app`, `apps/admin/lib`, `apps/mobile/src`, `packages` returned only the controller itself) | yes — `user.manage` | `update()` + `revokeMembershipAccess` (`service:206-215, 275-320`); `SELF_DEACTIVATE` (`service:182-186`) | `membership.update` + push tokens, refresh sessions, device activations revoked (`service:275-320`) |
| Reactivate a membership | surface yes (`page.tsx:206-235`) — **unreachable** | yes — `PATCH {active:true}`, `actions.ts:82-84` | yes — `team.update` → `user.manage` | reactivation-only branch, `service:201-206` (`INACTIVE_MEMBERSHIP_REACTIVATION_ONLY`) | `membership.update{active:true}` + audit |
| Deliver the invitation to the person | **surface: nothing** — the confirmation promises nothing; the notification copy says “Hesap ayrıntılarınızı görüntüleyin.” (`push-notification.handler.ts:74`) | outbox `UserInvited` → notification mapper + push worker, `users.service.ts:171-174` | n/a | push fan-out needs an **active device token** (`push-notification.handler.ts:339-350`); a newly invited user has none | in-app notification row only; the password is `randomInvitePassword()` hashed and discarded (`service:116,323-325`) |
| Filter/search the list | yes — toolbar form, `page.tsx:145-162` | yes, but the same unfiltered `GET /users`: the filter runs in the page over the full list (`page.tsx:60-67`); the API has no `q`/`state` | as the list row | in-page `toLocaleLowerCase('tr-TR')` substring over `displayName + email` (`page.tsx:63`) | none — not persisted, not in the URL state of the server |
| Clear the filters | yes — `<Link href="/users">`, `page.tsx:159-161` | n/a | n/a | resets `q` and `state` | n/a — **but leaves the select stale, finding F-04** |
| Reach the permission-denied surface | **no account can reach it** — the branch needs a panel session without `user.manage` (`page.tsx:48-57`), and the only panel-reachable role carries `user.manage` (50 permissions, observed live) | n/a | n/a | n/a | n/a |

Disagreement classes read out of this matrix:

- **Surface yes, a layer no / an offer the system forbids** — invite (F-01).
- **A layer yes, surface no** — `GET /users/:id` (no detail view), `POST /users/:id/deactivate` (no caller),
  the whole edit/reactivate capability (F-02, F-08).
- **Two routes for one action** — deactivate: the `PATCH` path writes `audit(user.update)`; the dedicated
  endpoint writes `audit(user.deactivate)` (`service:255-273`). The endpoint with the better audit trail is
  the one nothing calls (F-08).
- **Route yes, authorization no** — none. Every route carries `user.manage`; `/users/roles` additionally
  carries the panel proof (`users.controller.ts:43`), and a mismatched `X-Organization-Id` is refused
  (`apps/api/src/auth/jwt-auth.guard.ts:36-38`; observed: cross-org header → `401 AUTH_REQUIRED`).
- **The layers agree** — the list: surface, route, authorization, service and persistence agree on the
  scope rule (organization membership, non-archived), and the panel does not even call the API when the
  permission is missing (`page.test.tsx:150-155`, re-read as code).

Sibling surfaces read for the same kind of thing: every other panel list page parses the `page` envelope
and renders a cursor pager (`audit/page.tsx:24,205-209`; `customers/page.tsx:34,402-405`;
`dispatch/page.tsx:34,264-271`; `maintenance/page.tsx:38,356-362`; `organizations/organizations-model.ts:50`).
The users page is the only list that drops `page` (F-06). `components/Table.tsx` exists with
`sortable`/`sorted` props and is imported by **no** page (search over `apps/admin/app`, `apps/admin/components`,
`apps/admin/lib`: only its own definition and the barrel `components/index.ts:8`) — a primitive with no surface (F-06).

## 3. Matrix 2 — field contract

| Field | Column / type | Read by the API | Written by the API | Rendered (list / detail / form) | Validated | Label or enum source | Locale / format |
|---|---|---|---|---|---|---|---|
| `User.id` | `uuid` | yes (list select, detail) | server-generated | list: hidden `input[name=id]` in the row form (`page.tsx:220`, `page.tsx:258`); never shown | `z.uuid()` in `updateUserAction` (`actions.ts:77`) | n/a | n/a |
| `displayName` | `text` | yes | invite: written; update: **refused** (`GLOBAL_PROFILE_SELF_SERVICE_REQUIRED`, `service:327-334`) | list col “Ad”; form (invite, `maxLength=120`) | `min(1).max(120)` (`domain:13`) + native `required`/`maxLength` | n/a | tr-TR text, no transform |
| `email` | `text` (unique `normalized_email`) | yes | invite: written `status: 'ACTIVE'` | list col “E-posta” (143 px, clipped at 320) | `z.email()` (`domain:12`); native `type=email` | n/a | **`normalizeEmail` = `toLocaleLowerCase('tr-TR')`** (`normalization.ts:1`) → F-11 |
| `User.status` | `enum UserStatus {INVITED, ACTIVE, SUSPENDED, ARCHIVED}` (`apps/api/prisma/schema.prisma`) | yes | invite writes `ACTIVE` (`service:127`); nothing in `apps/api/src`, `apps/mobile/src`, `packages/domain` writes `INVITED` (search) | list col “Durum” as a badge (`page.tsx:186-189`) — the **only** surface | string, not an enum (the page's Zod says `z.string()`, `page.tsx:19`) | panel map has 5 keys `{ACTIVE, INVITED, SUSPENDED, DEACTIVATED, DELETED}` (`user-labels.ts:17-23`): 2 impossible in the DB, `ARCHIVED` missing, `INVITED` unreachable → F-07 | n/a |
| `Membership.active` | `boolean` | yes | invite `true`; `PATCH` toggles | list col “Üyelik” → `Aktif`/`Pasif` (`page.tsx:199`) | boolean | inline literals `'Aktif'`/`'Pasif'` — a **second** source of the same two words as `UserStatus` → F-07 | n/a |
| `Membership.scope` | `enum {organization, team, assigned, own}` | yes | invite + `PATCH` | list col “Kapsam”; both forms | `z.enum` (`domain:24,38`); schema default `organization` vs the invite form's default `assigned` → F-12 | panel `scopeLabels` (`user-labels.ts:9-14`) vs mobile `Tüm organizasyon` (`OrganizationUsersScreen.tsx:36-41`) → F-13 | n/a |
| `Membership.roles[].key` | `Role.key` | yes | invite replaces all roles on `roleKey`; `deleteMany`+`create` | list col “Roller” joined by comma (`page.tsx:192`) | `z.enum` of 7 keys (`domain:27-37`) | panel `roleLabels` map (`user-labels.ts:1-8`) → `roleLabels[key] ?? role.name`; the server's own `name` differs (“Platform Sahibi” vs “Platform sahibi”) → F-13 | n/a |
| `Role.key` / `Role.name` (from `/users/roles`) | `text` | yes | not by this feature | feeds both role selects | `z.string()` | **the only org-scoped source** — correct for this org; the mobile hardcodes 6 of 7 keys (`OrganizationUsersScreen.tsx:28-35`) | n/a |
| `User.locale` | `text` (`tr-TR`) | yes (list + detail) | **not writable here** (self-service only, `service:327-334`) | **rendered nowhere** — not a column, no detail view; the page even explains it cannot be edited (`page.tsx:164-166`) → F-09 | `z.string()` | n/a | stored as `tr-TR`; no surface formats or shows it |
| `page` envelope (`nextCursor`, `hasNextPage`) | object | yes — the API returns it | n/a | **not in the page's Zod at all** (`page.tsx:13-29`) → F-06 | n/a | documented in `docs/api-contract.md:19,176-181` | n/a |
| error/result codes | `?error=` / `?result=` | yes — `MutationNotice` reads both (`page.tsx:73`) | `result` produced by both actions; **`error` has no producer in this feature** (search over `apps/admin/app` for `redirect(...,'?error=')`: only announcements, registration, apply) | banner | no | `MutationNotice.tsx:12-111` | n/a |

## 4. Matrix 3 — flow and step contract

Two multi-step flows exist on this surface: the invite (form → confirmation → action) and the row edit
(form → confirmation → action). The reactivate row form has no confirmation step.

| Step | Precondition (the state it requires) | What it validates | What it writes | How a skip is prevented | Resume / persistence | Back-navigation retention | Where an error lands |
|---|---|---|---|---|---|---|---|
| Invite 1 — form inside `AdminModal` (`page.tsx:74-140`) | `team.invite` (`user.manage`), enforced on the server action (`actions.ts:50`) — client-side only for rendering | native `required`, `maxLength=120`, `type=email`; nothing on `blur` (validation on submit only, `AdminActionForm.tsx` `invalid` collector) | nothing | the dialog can only be opened by its trigger — it has **no `id`**, so no `#hash` can name this step (unlike the row modals, `page.tsx:222`) | none: the page is a server component, a reload loses typed values; `beforeunload` warns while dirty (observed: a real dialog during my own probe) | reopening loses the values (observed: after the refusal the values are still in the DOM because the dialog stayed open) | the form's feedback block, `role=alert`, focus moved to it (`page.tsx` via `AdminActionForm`) |
| Invite 2 — confirmation (`AdminActionForm` `confirmation`, `page.tsx:83-93`) | a submitted form | nothing of its own; it recomputes the summary at submit (`AdminActionForm` `onSubmit`→`setSummary`) | nothing | not skippable; Escape closes only the confirmation (`ConfirmationDialog.tsx` key handlers) | the `FormData` is held in a ref; cancelling returns to step 1 with values intact (code) | n/a | n/a |
| Invite 3 — `inviteUserAction` → API | step 2 confirmed | `InviteUserInput` (server) + the SUPER_ADMIN refusal (`actions.ts:61`) + API role lookup | user/membership/role/audit/outbox rows | permission re-checked server-side (`actions.ts:50`) | n/a | n/a | a whole-form error for a **field-level** problem (F-10); the API's own `ROLE_NOT_FOUND` *is* mapped to `roleKey` (`actions.ts:30-34`) |
| Row edit 1 — form in the row's dialog (`page.tsx:236-277`) | `team.update`; a non-SUPER_ADMIN, existing membership — **never true in this deployment** | `select` values only; `id` as a hidden input | nothing | the trigger renders the static note instead for SUPER_ADMIN rows (`page.tsx:203-205`) | none (server component) | n/a | n/a |
| Row edit 2 — confirmation (`page.tsx:235-245`) | a submitted form | nothing | nothing | not skippable | `FormData` in a ref | n/a | n/a |
| Reactivate — single-step row form (`page.tsx:206-235`) | an inactive membership; **never true in this deployment** | nothing beyond the hidden `operation=reactivate` | `{active:true}` only (`actions.ts:82-84`) | the control is only rendered for `!membership.active` | n/a | n/a | whole-form error |

Flow finding classes present: an error mapped to the whole flow instead of the field (F-10); no persistence,
so a reload loses work (a pass-by-design for a 4-field form, but it is why `beforeunload` exists);
one step (the invite dialog) is not addressable by URL while its sibling row dialogs are — the artifact's
“the URL that names a step the page does not render” has no instance here, the inverse does.

## 5. Matrix 4 — interaction dependency

| Trigger | Dependents | Required action on change | Who owns the state | What is announced |
|---|---|---|---|---|
| `q` / `state` filter submit (`page.tsx:145-162`) | the rendered rows and the count line (`page.tsx:164-166`) | recompute | the URL (a GET form; a full navigation observed) | the document load itself; no live region — acceptable because the change is a navigation (pass) |
| “Filtreleri temizle” link (`page.tsx:159`) | both filter controls and the rows | reset | the URL, but the controls are **uncontrolled with `defaultValue`** | **nothing, and the reset does not happen for the select**: after the click the URL is `/users` and `q` is empty while `state` still reads `Aktif` (reproduced twice; a reload shows `Tümü`) → **F-04** |
| `roleKey` select (invite) | none (no scope cascade) | keep | uncontrolled native select, seeded server-side from `/users/roles` | n/a |
| `roleKey` select (row edit) | the confirmation summary | recompute (summary built at submit) | uncontrolled; the `""` option means “keep current roles” (`page.tsx:249-251`) | nothing; the modal's `description` states the replace-all semantics (`page.tsx:229`) |
| `active` select offers `Pasif` only when `user.id !== context.id` (`page.tsx:270-274`) | the option set itself | n/a | server render (`context.id`) | nothing — the self-protection is a silently absent option with no explanation, while the API also refuses it (`SELF_DEACTIVATE`, `service:182-186`); the same rule is expressed twice, differently → F-15 |
| Opening a row's dialog by `#user-access-<uuid>` (`AdminModal` hash listener) | the dialog state | keep | the client component | nothing; the hash change is not announced (class: “a change to a region AT is not watching, announced nowhere”) — no row in this deployment renders one, so [NOT CHECKED: no editable row exists] |

## 6. Matrix 5 — surface pattern: controls, data views, flows, notifications

Sources: APG patterns, WCAG 2.2 as listed in the artifact; axe-core 4.10.3 run below. Read from the
**running app**, not from source, unless marked `code`.

### Data views (checked first)

| Rule | Verdict | Evidence |
|---|---|---|
| SC 1.3.1 real headers + a labelled table | pass | a11y tree: `region "Kullanıcı listesi"` → `table "Kullanıcı listesi"` with `caption` and seven `columnheader`s (observed) |
| `aria-sort` on the sorted column, reversible | **violation** | the API sorts by `displayName asc` (`users.service.ts:47`); the aria tree has no `aria-sort`, no sortable header and no reverse affordance; `components/Table.tsx:16-38` would render a glyph, and is unused → F-06 |
| Editable/widget cells make it a grid | latent; not triggered by today's data (the only row's control cell is a static paragraph) | observed row 1 of 1; `page.tsx:178,200-286` |
| `aria-rowcount`/`aria-colcount` for large or lazy sets | n/a — nothing is virtualized; the whole list is server-rendered (`page.tsx:58`) | code |
| SC 1.4.10 one-direction scroll at 320 with the table inside its own container | **page passes, region fails the affordance rule** | measured at 320: `documentElement.scrollWidth === clientWidth === 320`; `.tableWrap` client 242 vs scroll 1140, `overflow-x:auto`; 5 of 7 columns off-screen, last visible column (`E-posta`) clipped mid-word in the screenshot → F-05 |
| Pagination marks the current page; a one-page pager is hidden | n/a by absence: there is no pager at all, and the API's envelope is constant (`page: {null,false}`, observed) | F-06 |
| Content: headings, human-readable first column, headers stay visible | pass | first column is `displayName`; `<h2>Kullanıcılar</h2>`; `<caption>` present (`srOnly`) |
| Filters discoverable; active state visible in the results view | **violation (one control)** | `q` and the results agree; the `state` select disagrees with the view after a clear (F-04) |
| Detail view: key/value pairs, every field showing a value or “not provided” | n/a — no detail view exists (F-08, F-09) | observed |
| A scroll region says it scrolls | **violation** | 1140 px inside 242 px at 320 and inside 1084 px at 1440 with no fade, no hint and no visible scrollbar; `.tableWrap { overflow-x: auto }` only (`globals.css:561-563`); the sidebar next to it does style its scrollbar (`globals.css:289-290`) → F-05 |
| Long text has a strategy | **violation at desktop too** | at 1440 the last column (379 px) is cut mid-word (“…değiştir” for “değiştirilmez.”), measured `scrollWidth 1140 > clientWidth 1084`, and read in the light/dark/grayscale screenshots → F-05 |

### Controls

| Rule | Verdict | Evidence |
|---|---|---|
| Visible persistent label, never a placeholder | pass | every control is wrapped in `<label><span>` (`page.tsx:96-104,146-157`) |
| Instructions where the format is not customary; a counter where a limit exists | **minor gap** | `maxLength=120` with no counter or hint (the server message mentions “1–120 karakter” only after a failure, `actions.ts:9`) |
| SC 1.3.5 `autocomplete` tokens scoped | pass | the invite fields collect a **third party's** name/email, so no self-data token is due; the search/filter controls correctly carry none; observed attributes are null |
| One required/optional convention | pass | two required fields marked `required` (native) with no asterisk convention in use anywhere on this surface |
| SC 2.5.8 target size | pass | axe `target-size` (enabled, off by default) reported 0; measured `.badge` 25 px high, filter button 67 x 92 px, skip link/close button >= 24 px |
| SC 2.4.7 / 1.4.11 focus visible | pass (hand-check) | 20 keyboard stops: `outline: solid 3px rgb(20,95,192)` on the light surface, `rgb(166,214,255)` on the dark sidebar, never time-limited; the `.tableWrap` region gets the same ring |
| SC 1.4.3 contrast, no colour-only state | pass | badge measured `rgb(25,32,26)` on `rgb(238,240,236)` = **14.5:1**; grayscale read shows the status is carried by text (“Aktif”), not colour only; axe clean in both schemes |
| Conditional reveal announces itself | n/a — the only conditional reveal is the omit-an-option case (F-15) | observed |
| APG dialog / `aria-modal` preconditions | pass | native `showModal()` (no `aria-modal` attribute), background inert by the platform, initial focus lands on the close button (first focusable), focus returns to the trigger (`AdminModal` `onClose`), the confirmation focuses “Vazgeç” (observed) |
| Destructive confirmation names what will be lost | **partial** | the invite confirmation lists the four new values (observed); the row-edit confirmation names the user and states that all roles are replaced and that sessions/devices go away, but shows **no current role, no scope and no count of sessions/devices** (`page.tsx:235-245`) — [NOT CHECKED live: no editable row exists in this deployment] |

### Validation and errors

| Rule | Verdict | Evidence |
|---|---|---|
| Validate on submit, keep failing values, server-side validation present | pass | the `invalid` collector runs once per submit burst; the refused invite left its values in place (observed); Zod on the server action (`actions.ts:52-57`) |
| SC 3.3.1/3.3.3 identify the item and describe the correction | **partial** | field messages name the fix (“Bu e-posta bu işletmede zaten kayıtlı. Kullanıcı listesinden erişimini düzenleyin.”, `actions.ts:31-33`), but the app-layer refusal for `roleKey` says only “Platform sahibi bu ekrandan atanamaz.” with no remedy and no field association (F-10) |
| Association: `aria-describedby`, same wording in summary and field, focus moves to the field | pass | `AdminActionForm` sets `aria-invalid` + `aria-describedby` per failing field and renders each message as a button that focuses its control |
| Error summary at the top of the form | pass | the feedback block is focusable, `role=alert`, and holds the list |

### Flows

| Rule | Verdict | Evidence |
|---|---|---|
| One question per page/step, unique heading, back + continue | pass | the invite dialog has one heading and 4 fields; the confirmation has its own heading (`Davet oluşturulsun mu?`) |
| Check-your-answers pre-populated, submit names its action | pass | the summary is rebuilt from the form at submit and the button names the action (“Daveti oluştur”, “Erişimi kaydet”) |
| SC 3.3.4/3.3.7 reversibility and redundant entry | **gap** | the role change is confirmed but not reversible and is a replace-all with no “before” value shown; the email/name are asked for a person the operator may already have listed (no reuse offer) — the panel cannot even see an existing person before inviting, since `/users` only lists the caller's own organisation |
| Destructive confirmation reserved for the irreversible, actions inside the panel | pass | the confirmation is portalled into its own `<dialog>` above the modal (observed: two open dialogs, Escape scoped to the top one) |

### Notifications

| Rule | Verdict | Evidence |
|---|---|---|
| SC 4.1.3 changes the page makes without moving focus are determinable | pass by construction | every state change on this surface is a navigation or a focused dialog; the row count is rendered server-side after a GET form submit (`page.tsx:164`) and no client-side recount exists |
| The whole status string is the announced unit; the end of a wait is announced | pass (`code` + partial observation) | pending state is `role=status` “İşlem kaydediliyor…”; success is announced through the modal's DOM event and `MutationNotice` `role=status`; a screen reader was not available to hear it |
| Validation errors stay out of live regions when inside a focused dialog | pass | field errors render inside the form's own feedback block, not in a global live region (`AdminActionForm`) |
| A notification banner sits before the h1, at most one, never stands in for validation errors | pass | `MutationNotice` renders in the content flow before `<h2>` and is not used for field errors (`MutationNotice.tsx:113-138`) |

## 7. Findings, most severe first

Severity is the artifact's / the harness scale (frequency x impact x persistence, 0-4). Every finding
names exactly one evidence class.

**F-01 — The invite is a control whose only possible value the system refuses. (severity 4, `behaviour`)**
Exercised: filled the modal (the role select offered exactly `SUPER_ADMIN` = “Platform sahibi”,
`page.tsx:105-121` + `/users/roles`), confirmed “Daveti oluştur”, and the form returned
`Platform sahibi bu ekrandan atanamaz.` in `role=alert`, values kept, no row written. Layer below:
`POST /users/invite` with `roleKey: SUPER_ADMIN` → **403 `SUPER_ADMIN_PROVISIONING_REQUIRED`**
(`users.service.ts:114,336-338`); with `roleKey: TECHNICIAN` → **400 `ROLE_NOT_FOUND`**
(`users.service.ts:138-143`). The role list is org-scoped (`users.service.ts:69-73`) and the panel's
organisation has exactly one role (observed: `GET /users/roles` → `[{key:SUPER_ADMIN,name:"Platform Sahibi"}]`),
which the app-layer guard also refuses (`actions.ts:61`). So *every* submission the surface can produce is
refused, at three different layers.
*Prevent:* the assertion that would have failed is “the panel's offered role set minus the refused set is
non-empty, and one offered role completes an invite against a seeded PLATFORM org”. Add it where the repo
already pins this shape — `apps/admin/lib/visible-action-consumers.contract.test.ts:10-40` walks `(dashboard)/<route>`
sources for orphan actions; the users route needs the reachability half, not just the orphan half. The
existing `page.test.tsx` fixture (ORG_ADMIN/TECHNICIAN/VIEWER) is what hides this today.

**F-02 — No editable row can exist in the panel, so the whole access-editing capability is unreachable. (severity 4, `behaviour`)**
The only rendered row carries `roles: ["SUPER_ADMIN"]` (observed in the aria tree, the screenshot and
`GET /users`), and the page replaces its control cell with a static paragraph (`page.tsx:203-205`). The
service refuses a SUPER_ADMIN target outright (`users.service.ts:340-342`) and refuses a SUPER_ADMIN
assignment (`:336-338`), while the panel's org can hold no other role
(`super-admin-provisioning.ts:230-236` creates one role; `tenant-provisioning.ts:18-21` is the only path
that creates ORG_ADMIN/TECHNICIAN and it belongs to tenant orgs, which cannot open a panel session —
`auth.service.ts:33-42`). Net: the “Yetki güncelle” column is a constant string; the row dialog, the
reactivate form and the `active` select are dead surface.
*Prevent:* assert that `PATCH /users/:id` is reachable from the panel's own data: seed one non-super-admin
membership in a PLATFORM org in the admin e2e fixture and assert the row control renders. Fails today.
(The root cause is shared with F-01: the panel org's role catalogue.)

**F-03 — The invitation's end has no delivery path: the recipient gets no credential. (severity 3, `code`)**
`invite()` hashes `randomInvitePassword()` and discards the plaintext (`users.service.ts:116,323-325`),
sends no mail (no provider is consulted on this path), and emits `UserInvited`
(`users.service.ts:171-174`) whose only transport is: an in-app notification row
(`notification-event-mapper.ts:226-229,684-688`) and a push fan-out that requires an **active device
token** (`push-notification.handler.ts:339-350`) — impossible for someone who has never signed in. The
copy says “Hesap ayrıntılarınızı görüntüleyin.” (`push-notification.handler.ts:74`). The repository's own
convention for the same kind of event shows a one-time login sentence to the operator
(`lib/login-handover.ts:11-22`, used at `organizations/actions.ts:44`); the users invite has no equivalent.
*Prevent:* a contract test asserting that every account-creating path either returns a one-time credential
payload or names a configured delivery transport — modelled on `login-handover`, failing on `invite` today.

**F-04 — After “Filtreleri temizle” the state select shows a filter the view no longer has. (severity 3, `ui-observed`)**
Reproduced twice: from `/users?q=platform&state=active`, clicking the clear link (`page.tsx:159-161`)
leaves `location.href = /users` with `q = ""` but `select[name=state].value === "active"` and “Aktif”
selected, while a reload of that same URL renders “Tümü”. The control is uncontrolled
(`defaultValue={input.state ?? ''}`, `page.tsx:152`) so the route change does not reset it. Nothing is
announced. The artifact names this class exactly; the operator with a large list would read an unfiltered
result set as filtered.
*Prevent:* an e2e assertion on the *control* (not the URL): after clicking the clear link, every filter
control reports its empty value and the returned rows equal the unfiltered count. Keyset the select off
`searchParams` (controlled) or add `autoComplete="off"` to the toolbar form.

**F-05 — The data view is clipped at every width measured and says nothing about scrolling. (severity 3, `ui-observed`)**
Measured (viewport width → `.tableWrap` client / table scroll): **320 → 242 / 1140** (5 of 7 columns
off-screen), **1440 → 1084 / 1140** (the last column's sentence cut mid-word). Read in the 1440 light,
1440 dark and 1440 grayscale screenshots and the 320 screenshot. `.tableWrap` has `overflow-x: auto` and
nothing else (`globals.css:561-563`); the sidebar in the same app styles its scrollbar
(`globals.css:289-290`). The page itself reflows correctly (no page-level horizontal scrollbar), so this
is the artifact's region-affordance rule, not SC 1.4.10 at page level.
*Prevent:* an e2e assertion that `.tableWrap.scrollWidth <= .tableWrap.clientWidth` at 1280 and 1440 — the
document-overflow check passes while the column is clipped, so it would not have caught this.

**F-06 — The users collection contradicts the documented collection contract and every sibling page. (severity 2, `external`)**
`docs/api-contract.md:11` (“collection endpoints use cursor pagination, explicit sort allow-lists, and
server-side filters”) and `:176-181` (limit default 30/max 100, `sort=field:asc`, cursors bound to
filters) versus `list()`: no arguments at all, `orderBy displayName asc`, and a hard-coded
`page: { nextCursor: null, hasNextPage: false }` (`users.service.ts:26-66`) — observed as the live
response. The page's response schema does not even carry `page` (`page.tsx:13-29`), while
`audit`, `customers`, `dispatch`, `maintenance`, `finance` and `organizations` all parse it and render a
“Sonraki sayfa” cursor link; `components/Table.tsx`'s `sortable`/`sorted` props are used by no page.
Filtering is done in memory over the full list (`page.tsx:60-67`) under an envelope nobody computes.
*Prevent:* the sibling test shape — `audit/page.test.tsx:105-113` (“links the next page by cursor and
offers the first page again”) copied to the users page with `page.hasNextPage: true`; today it would fail.

**F-07 — Two fields print the same word in one row, and the status vocabulary has two sources. (severity 2, `ui-observed`)**
The rendered row reads `… | Aktif | Platform sahibi | İşletmedeki kayıtlar | Aktif | …`: “Durum” is
`User.status` (`page.tsx:186-189`) and “Üyelik” is `Membership.active` (`page.tsx:199`). Only membership
is filterable (the toolbar's “Üyelik durumu”), so the similarly-labelled “Durum” has no filter and no
vocabulary guarantee: the label map carries `DEACTIVATED` and `DELETED`, which the DB enum cannot produce,
and `INVITED`, which no code writes (`user-labels.ts:17-23` vs `schema.prisma` `enum UserStatus`), while
`ARCHIVED` has no label.
*Prevent:* a contract test that compares the label map's keys to the Prisma enum (fails today on three
keys), plus distinct column labels so the two fields are not one word twice.

**F-08 — Dead routes and a dead query parameter. (severity 2, `code`)**
`POST /users/:id/deactivate` (`users.controller.ts:82-90`) has no caller: the panel and the mobile app both
use `PATCH {active:false}` (`actions.ts:89`, `organization-users-api.ts:56`); search covered
`apps/api/src`, `apps/admin/app`, `apps/admin/lib`, `apps/mobile/src`, `packages` and returned only the
controller. It also carries the better audit action (`user.deactivate` vs `user.update`,
`users.service.ts:255-273`). `GET /users/:id` (`users.controller.ts:49`) has no caller either while
returning a payload no surface renders. `?error=` on `MutationNotice` (`page.tsx:73`) has no producer in
this feature (other features do produce it, e.g. `announcements/actions.ts:38`).
*Prevent:* extend the repo's own orphan hunt to API routes — `visible-action-consumers.contract.test.ts`
already proves the pattern for server actions; a route-with-no-caller list that must be empty (or an
explicit allow-list) would have caught both endpoints.

**F-09 — `locale` is carried by the contract and shown nowhere. (severity 2, `behaviour`)**
Observed in the live list and detail responses (`"locale": "tr-TR"`). No column, no detail view, no form
control; the page only explains that it is not editable here (`page.tsx:164-166`). An operator cannot
answer “which language is this account in?” from the panel.
*Prevent:* a schema-to-surface test asserting every field of the list/detail response appears in a
rendered surface (or delete the field from the select).

**F-10 — One rule, two error mappings. (severity 2, `behaviour`)**
The app-layer refusal of a SUPER_ADMIN assignment returns a whole-form error with no field association
(`actions.ts:61`), while the API's same-class refusal (`ROLE_NOT_FOUND`) is mapped to the `roleKey` field
with a correction (`actions.ts:30-34`). Observed live: the refusal appeared as a banner-level `role=alert`
with no `aria-invalid` on the select, at the newest layer of an already-dead path.
*Prevent:* assert that every refusal which names a `roleKey`/`email` rule attaches a `fieldErrors` entry —
the existing `actions.test.ts` already has the counterpart test for `ROLE_NOT_FOUND`; add the guard case.

**F-11 — Turkish casefold applied to an email address. (severity 1, `behaviour`)**
`normalizeEmail` = `email.trim().toLocaleLowerCase('tr-TR')` (`apps/api/src/common/normalization.ts:1`).
Run on this machine: `"ILKNUR@X.TEST" → "ılknur@x.test"` (dotless ı) while `"ilknur@x.test" → "ilknur@x.test"`,
and `"İLK@X.TEST" → "ilk@x.test"` while `"ILK@x.test" → "ılk@x.test"`. `users.normalized_email` carries a
**unique** index (observed in the live database), so one mailbox can hold two accounts and the
`ALREADY_MEMBER` check (`users.service.ts:120-136`) misses the ASCII upper-case spelling. Reachable from the
users feature through `invite()`; not reachable from the panel's invite today (F-01) but reachable from the
mobile surface that shares this endpoint.
*Prevent:* a unit test on `normalizeEmail` asserting ASCII case variants collapse and Turkish letters are
not folded (`ILKNUR@` ≡ `ilknur@`, `İLK@` ≠ `ILK@`). The locale-aware fold is correct for names
(`normalizeTurkishSearch`) and wrong for addresses.

**F-12 — The scope default has two sources. (severity 1, `code`)**
The invite form's `defaultValue="assigned"` (`page.tsx:122`) versus the domain schema's
`.default('organization')` (`packages/domain/src/users.ts:24`). The action always sends a scope, so the
schema default is unreachable from this surface; any other caller that omits `scope` gets a different
default than the panel shows.
*Prevent:* derive the form default from the parsed schema, asserted by one test on the pair.

**F-13 — One enum, three label sources. (severity 1, `code`)**
Panel `roleLabels` maps `SUPER_ADMIN → 'Platform sahibi'` (`user-labels.ts:2`) while the server's role
`name` is `'Platform Sahibi'` (observed) and the mobile uses `userFacingLabel`
(`OrganizationUsersScreen.tsx:28-35`); `scope: organization` is “İşletmedeki kayıtlar” in the panel and
“Tüm organizasyon” on mobile. The panel prefers its own map (`page.tsx:115,253`), the mobile hardcodes a
6-key list, and the tenant provisioning path creates 2 roles (`tenant-provisioning.ts:18-21`) while the
domain enum allows 7.
*Prevent:* one label source per enum published beside the domain schema, with a contract test that the
panel and mobile label maps agree key-for-key.

**F-14 — A branch no account can enter. (severity 1, `code`)**
The permission-denied surface (`page.tsx:48-57`) and the read-only variant (`page.tsx:126-131`) require a
panel session whose permissions lack `user.manage`; the only panel-reachable role (`SUPER_ADMIN` of a
PLATFORM org) carries `user.manage` (observed live: 50 permissions including `user.manage`; the
provisioning path grants the canonical set, `super-admin-provisioning.ts:168-171`). `canInvite` and
`canUpdate` derive from the same permission (`page.tsx:46-47`), so the two branches cannot diverge either.
*Prevent:* a reachability test over the panel's role/permission fixtures that every permission-gated branch
has at least one account able to enter it, or delete the branch.

**F-15 — Self-protection expressed twice, once silently. (severity 1, `ui-observed`)**
The “Pasif” option is omitted for your own row (`page.tsx:270-274`) while the API refuses the same action
with `SELF_DEACTIVATE` (`users.service.ts:182-186`). The surface gives no reason and no announcement for the
missing option. Tied to this: an editable row would put one modal trigger per row plus one `<dialog>` per
row into the DOM (`page.tsx:236-277`), making the table a table of tab stops at N rows — the artifact's grid
rule — which cannot be observed here because no editable row exists. `[NOT CHECKED live: no editable row]`
*Prevent:* render the option disabled with the reason from a single shared rule, and an e2e assertion that
the table's tab-stop count equals one region plus one control per editable row.

### Pass rows (agreement between layers — the control that shows the matrices were filled honestly)

1. Authorization holds at the tenant boundary: `X-Organization-Id` mismatched → `401 AUTH_REQUIRED`
   (observed), enforced at `jwt-auth.guard.ts:36-38`.
2. `/users/roles` is the only users route with the ADMIN-panel proof, and the contract test pins the
   deliberate mobile sharing of the others (`admin-panel-routes.contract.test.ts:125-133`).
3. The page fetches nothing without `user.manage` (`page.test.tsx:150-155`).
4. Real table semantics: caption, `scope=col` headers, a labelled focusable region (aria tree).
5. Keyboard: skip link first, one tab stop per control, no per-row stop in the current data, a complete
   focus cycle, a visible 3 px focus indicator on every stop (20 stops observed).
6. Closed dialogs are out of the tab order and out of the accessibility tree (`display:none`, 0 client
   rects — observed).
7. Error handling of the refused mutation: `role=alert`, focus moved to the feedback block, values preserved.
8. The confirmation dialog is portalled above its modal, focuses the least destructive action (“Vazgeç”)
   and scopes Escape to itself (observed + `ConfirmationDialog.tsx`).
9. axe-core 4.10.3 over `wcag2a, wcag2aa, wcag21aa, wcag22aa`: **0 violations** in three states — 1440
   light, 1440 dark, and the invite dialog with its error banner; with `best-practice` and the
   default-disabled `target-size` rule enabled: 0. (axe sees about 57% of WCAG; the eight hand-checks are
   reported in section 6 and below.)
10. Empty state: message plus the count line, on a real navigation, with `q` preserved (`?q=zzz` observed).
11. Contrast and non-colour signalling: badge 14.5:1; the grayscale read keeps every status readable.
12. Loading and error surfaces exist and are inherited by this route (`app/(dashboard)/loading.tsx`,
    `app/(dashboard)/error.tsx` → `AdminSurfaceErrorView`).
13. No write reached the database during the audit: probe emails `e3b.probe*@servistek.test` and
    `e3rb.davet@servistek.test` returned 0 rows after the probes.

## 8. Capability-change proposals

Only two findings have fixes that name a layer the system does not have.

### P-01 — An invited person can obtain a usable credential

| Heading | Content | Falsified by |
|---|---|---|
| Capability | An invited member can obtain a first credential without the operator relaying it out of band. | a cited code path that already delivers one (none today: `users.service.ts:116,323-325` discards the plaintext) |
| Absence proof | `apps/api/src/users/users.service.ts:116` (password hashed, never returned) and `:171-174` (outbox payload `{membershipId}` with no credential); the input that fails: any accepted `POST /users/invite`. | a cited path that returns a credential or sends one |
| Contract delta | `POST /users/invite` response gains `data.login: {email, displayName, temporaryPassword}` mirroring `OrganizationCreateResponse.login` (`organizations/organizations-model.ts`), or an `InvitationIssued` event gains a transport; OpenAPI diff + the existing `apps/api/scripts/api-contract-verifier.mjs` run green with the diff. Evidence class `code`. | the compatibility checker passing with no diff |
| Migration | expand (add the field and a nullable `invitation_delivery_state` column) → migrate (backfill `NULL` = already-active accounts) → contract (drop the legacy notification-only path, dated step in the ADR) | a contract phase with no date |
| Rollout | flag `users.invite-delivery`, type `enum{handover,email}`, expected lifetime 2 releases, initial exposure = platform staff only, kill-switch owner = platform on-call, abort threshold = >2% of invites ending without a credential handover over a 7-day window | an unmeasurable threshold, or a flag with no lifetime |
| Verification | a test that fails before and passes after: `apps/api/src/users/users.service.test.ts` asserting `invite()` returns a credential payload (or that the configured transport was invoked) — today it returns `{data:{id,displayName}}` | a check that also passes on the pre-change commit |
| Reversibility | writes one additive response field; restore = stop reading it; no data migration is one-way | data written with no restore step and no label |
| Decision | ADR “Invitation credential handover” (context: invites create accounts nobody can sign into; decision; status: proposed; consequences: a one-time secret leaves the API boundary, so the audit redaction rule must cover it) superseding the current implicit “operator relays nothing” behaviour | an ADR without a status |
| Appetite | 1 week, out of bounds: changing the mobile invite flow; when the box ends: ship the `handover` variant only and record the email variant as a follow-up plan | no box, or an implicit extension |

### P-02 — The panel can grant a role other than its own

| Heading | Content | Falsified by |
|---|---|---|
| Capability | A platform-owner organisation can hold and assign a role other than the platform-owner role. | a cited code path that already creates such a role (none: `super-admin-provisioning.ts:230-236` creates one role; `tenant-provisioning.ts:18-21` only for tenant orgs) |
| Absence proof | `apps/api/src/users/users.service.ts:69-73` scopes the role catalogue to the caller's org, and the panel's org has one role (observed `GET /users/roles` → `[SUPER_ADMIN]`); the input that fails: `POST /users/invite {roleKey: TECHNICIAN}` → `400 ROLE_NOT_FOUND` (observed) | a cited path that creates a second role in a PLATFORM org |
| Contract delta | a `Role` provisioning rule for PLATFORM orgs (which keys, which permissions) as a seed/migration plus the permission rule “which roles may a panel caller assign”; schema diff = the new `roles` rows; the artifact other than the author can reject = the seeded-role contract test | the compatibility checker green with no diff |
| Migration | expand (seed the new roles for existing PLATFORM orgs) → migrate (re-point the invite default) → contract (remove the SINGLE-ROLE assumption from the panel fixture, dated) | a contract phase with no date |
| Rollout | flag `panel.role-catalogue`, type `enum{single,extended}`, lifetime until the next major, exposure = platform staff, kill-switch owner = platform on-call, abort threshold = any invite producing an unexpected permission set in the audit log over 7 days | an unmeasurable threshold, or a flag with no lifetime |
| Verification | the assertion in F-01's Prevent line: a seeded PLATFORM org where an offered role completes an invite end-to-end | a check that also passes on the pre-change commit |
| Reversibility | writes role rows and membership rows (one-way for existing memberships); restore step = deactivate the memberships created under the new roles, documented in the ADR | data written with no restore step and no label |
| Decision | ADR “Assignable roles in a platform organisation” (status: proposed), superseding the implicit “one role per PLATFORM org” assumption encoded in `super-admin-provisioning` and in `page.test.tsx`'s tenant-shaped fixture | an ADR without a status |
| Appetite | 2 weeks, out of bounds: a general role-management UI; when the box ends: keep the seeded catalogue and drop the UI | no box, or an implicit extension |

## 9. Coverage

Passes run: **3**, from three entry points, on one frozen artifact and one frozen target.
- Pass 1, first-time user: signed in as the panel's only account, opened `/users`, opened the invite
  modal, filled it, confirmed it, read the refusal (exercised actions).
- Pass 2, daily operator: keyboard-only walk of all 20 stops, filter round-trips and the clear link,
  empty state, 320/768/1440 measurements, light/dark/grayscale reads, axe sweeps (exercised + measured).
- Pass 3, API client with no UI: minted an ADMIN token through the API's own sign-in, then `GET /users`,
  `GET /users/roles`, `GET /users/:id`, `GET /me`, `POST /users/invite` x2 (both refused, no write),
  a cross-org header probe, and a header-less probe (exercised, read-only).

Readings versus exercised actions: everything marked `ui-observed` or `behaviour` was exercised against the
running app; everything marked `code` is a source reading; `external` is `docs/api-contract.md`. The panel
renders on the server, so the browser's request log cannot prove a capability call — the API pass above is
what covers that, not the page.

Per matrix:

| Matrix | Rows checked | Rows not checked |
|---|---|---|
| 1 capability | 12 rows x 5 columns = 60 cells; 57 filled from observation/code | 3 cells: the *mobile* surface of invite/update/deactivate was read from code only (the mobile app was not run) |
| 2 field contract | 11 rows x 8 columns = 88 cells; 4 of them `n/a` (no locale/format transform on most fields) | the mobile label source (`userFacingLabel`) was read, not rendered |
| 3 flow and step | 6 steps x 8 columns = 48 cells | the two row-edit steps: `[NOT CHECKED live: no editable row exists in this deployment]` (12 cells) |
| 4 interaction dependency | 6 rows x 5 columns = 30 cells | 1 row (the deep-linked row dialog) `[NOT CHECKED: no editable row exists]` |
| 5 surface pattern | 33 rules across the five tables: 20 pass (incl. the page-level 1.4.10), 4 violation, 2 partial, 1 latent, 1 minor, 1 gap, 4 `n/a` by absence | the destructive-confirmation **content** for the edit flow (`code` read only) |

What could not be checked, and what would change the conclusion:

- **No credential to enter a tenant-shaped panel state.** The panel opens only for a `SUPER_ADMIN` of a
  PLATFORM org, whose only role and only member are the platform owner. A tenant-org fixture (a
  non-super-admin member, an inactive membership, several roles) would let me observe the row edit modal,
  the reactivate control, the destructive confirmation's content and the multi-role rendering; it would not
  change F-01/F-02 (the panel cannot reach those states) but it could add or refute findings about those
  controls.
- **No API-down run of this route.** `loading.tsx`/`error.tsx` are cited from code; the error and skeleton
  states of this data view were not observed because the API is shared with other raters and I would not
  take it down.
- **No screen reader.** SC 4.1.3 and the dialog announcements are hand-checked from the DOM and the code;
  a real AT pass could still refute the "announced as a whole string" claim.
- **Axe's blind spots** (no rules for 1.4.10, 2.4.7, 3.3.1/3.3.3, 4.1.3; `target-size` off by default) were
  hand-checked as reported in section 6; a clean axe run is not a clean surface.
- **The search-miss question** the artifact raises for Turkish casefolded names does **not** reproduce on
  this surface, and I am recording it as a negative result rather than a finding: the page folds both sides
  with `toLocaleLowerCase('tr-TR')` (`page.tsx:60,63`), so `İLKNUR` matches `İlknur` and `ILKNUR` does not
  match it (correct Turkish), and the email-search weakness is the same locale-fold defect reported as F-11
  at the writer, not at the searcher. Only one row exists, so a name-matching claim cannot be settled
  against live data.
- **Row counts are honest but thin:** one user, one role, two error codes. Frequency judgements (F-01/F-02
  severity 4) rest on "the surface can never do this" rather than on a large sample; the platform org could
  in principle hold more members, which would multiply the same dead states rather than change them.
- **One-way actions taken:** one POST to `/auth/admin/sign-in` (creates a refresh-session row, as the panel
  itself does) and two refused invites; the accidental click on “Çıkış” during probing signed the shared
  browser session out and it was signed back in immediately — no user, membership or role row was written
  (verified: 0 rows matching both probe emails).

## 10. Discipline notes

- The artifact's element list is produced in its own order: unit, five matrices, findings ranked by
  severity, proposals, Prevent line per finding, coverage. The confirmation dialog is reported as a **pass**
  for naming the record and focusing the least destructive action, and as a **partial** for not naming what
  is lost — both sides cited.
- Findings came from three different instruments: **8** from the running app (F-01, F-02, F-04, F-05,
  F-07, F-09, F-10, F-15), **1** from running the writer's own expression outside the app (F-11), and
  **6** from the layer comparison the matrices force (F-03, F-06, F-08, F-12, F-13, F-14).
- No finding is a taste judgement; each names a violated rule from the artifact's own tables or a
  disagreement between two cited layers. Where a fix would need a layer that does not exist, it is a
  proposal, not a screen recommendation (P-01, P-02); where the layer does exist (pagination, detail view,
  table affordance, focus reset) it is a fix, and I say which.
- Screenshots are read, not saved: 1440 light (full page), 1440 dark (full page), 1440 grayscale,
  320 (viewport and full page), 768, the invite modal with its error banner, the stale-filter crop. What
  the tree could not answer and the image could: the mid-word clipping of the last column at **both** 320
  and 1440, the missing scroll affordance, and the grayscale legibility.
