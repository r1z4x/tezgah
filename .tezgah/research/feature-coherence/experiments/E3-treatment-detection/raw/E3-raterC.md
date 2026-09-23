# feature-audit - Ustam admin users area (`/users`)

Frozen artifact applied: `skills/feature-audit/SKILL.md` (read in full, 324 lines).
Frozen revision audited: `apps/admin` + `apps/api` at `98f985f68d7064385b6eaeae7da8c4aa5636a6b5`
("revert(admin): drop the duplicate h1 on the users surface"), working tree clean at start.
Application reading: the admin dev server on `http://localhost:3000` and the API on
`http://127.0.0.1:3001/api/v1`, both already running; the local Postgres `servistek` DB read-only.
Rater: E3RaterC. Passes run: 3 (sections "Discipline" and "Coverage").

---

## The unit

**Entity:** a platform-organization *member* - a `User` plus that user's `Membership` in the
panel's organization and the `MembershipRole` rows that carry its roles.

**Actions a person can take:** list, search/filter, invite (create user + membership),
assign a role, set a record scope, deactivate (revoke access), reactivate, read one user's
detail (no surface).

**Screens:** `/(dashboard)/users` only - one page: a header, an invite modal, a filter
toolbar, a count line, one data table with a per-row access column, one empty state, one
disabled-access surface, and (per dialog) a confirmation step. There is no detail route:
`apps/admin/app/(dashboard)/users/` contains `page.tsx`, `actions.ts`, `user-labels.ts`,
`page.test.tsx`, `actions.test.ts` and no `[id]` segment.

**Endpoints:** `GET /users`, `GET /users/roles`, `GET /users/:id`, `POST /users/invite`,
`PATCH /users/:id`, `POST /users/:id/deactivate` (`apps/api/src/users/users.controller.ts:34-88`);
the panel reaches them through `adminApi` (`apps/admin/lib/api.ts:90-140`), the mobile app
through `apps/mobile/src/features/users/organization-users-api.ts:39-56`.

**Files in scope:** the route folder above; `apps/admin/components/{AdminActionForm,AdminModal,
ConfirmationDialog,MutationNotice,PageHeader}.tsx`; `apps/admin/lib/{api,admin-context,
mutation-guard,mutations,admin-panel-session,session,login-handover,admin-surfaces,admin-labels}.ts`;
`apps/api/src/users/{users.controller,users.service,users.module}.ts`;
`apps/api/src/auth/{admin-panel.guard,auth.service}.ts`; `apps/api/src/common/{permissions.decorator,
audit.service,outbox.service}.ts`; `apps/api/src/notifications/notification-event-mapper.ts`;
`apps/api/src/worker/push-notification.handler.ts`; `apps/api/src/organizations/tenant-provisioning.ts`;
`packages/domain/src/{users,permissions,enums}.ts`; `apps/api/prisma/schema.prisma`;
`apps/admin/app/globals.css`; `apps/mobile/src/features/users/*` and
`apps/mobile/src/design-system/user-facing-labels.ts` (the sibling surface for the same feature).

**Not in scope:** the other panel routes, the mobile feature's own rendering, the auth flow
itself, and everything the memberships feed downstream (work orders, finance).

Counts per cell: `yes`/`no`/`n/a` plus a citation. Citations are `path:line` for code, the
probe and its result for the running app, and URL+date for the standards. Absences name the
search that proves them. A cell not checked is `[NOT CHECKED: reason]`.

---

## Matrix 1 - capability

| Action | Surface (what a person can do) | Route | Authorization | Service / validation | Persistence |
|---|---|---|---|---|---|
| List members | `yes` - the table, `page.tsx:167-286`; observed live: 7 columns, 1 row | `yes` - server component `page.tsx:39`, `adminApi('/users')` `page.tsx:58` | `yes` - `@RequirePermissions('user.manage')` `users.controller.ts:34-35`; page gate `page.tsx:46-56`; `api.ts:91` demands the panel session | `yes` - `users.service.ts:26-65` | `yes` - `prisma.user.findMany` `users.service.ts:27-52` |
| Search / filter the list | `yes` - GET toolbar, `page.tsx:145-162` (observed: `?q`, `?state`) | `yes` - the query rides the URL; the API receives neither `q` nor `state` | `n/a` - same read as the row above | `no` - the filter is an in-memory array filter, `page.tsx:60-66` (see D10) | `n/a` - URL only |
| Invite a member (create user + membership) | `yes` - invite modal `page.tsx:74-134`; observed open with fields Ad/E-posta/Rol/Kapsam | `yes` - `POST /users/invite` `actions.ts:62`, `users.controller.ts:59-60` | `yes` - `requireAdminMutation('team.invite')` `actions.ts:53` -> `'user.manage'` `mutations.ts:29`; API `users.controller.ts:60` | `yes` - `InviteUserInput` `packages/domain/src/users.ts:11-24`; SUPER_ADMIN refusal `actions.ts:61`, `users.service.ts:114`; `ALREADY_MEMBER`, `ROLE_NOT_FOUND` `users.service.ts:126-146` | `yes` - User+Membership+MembershipRole+audit+outbox in one transaction, `users.service.ts:118-176` |
| Invite - what the recipient receives | `no` - the success copy says "Takım daveti oluşturuldu" (`MutationNotice.tsx:45`) and no credential is shown or sent (see D3) | `n/a` | `n/a` | `yes` - an outbox event `users.service.ts:169-175` | `no` - a random password that is never delivered `users.service.ts:116,323-325` |
| Assign a role | `yes` - edit modal role select `page.tsx:247-258` (**unreachable on this install**: the only row is a SUPER_ADMIN target, `page.tsx:205`) `[NOT CHECKED live: no eligible member exists - the platform org holds one SUPER_ADMIN, who is also the actor]` | `yes` - `PATCH /users/:id` `actions.ts:89` | `yes` - `requireAdminMutation('team.update')` `actions.ts:75` -> `'user.manage'` `mutations.ts:33` | `yes` - `UserUpdateInput` `packages/domain/src/users.ts:27-43`; role replaced, `users.service.ts:229-244` | `yes` - MembershipRole delete+create, audit `users.service.ts:244-253` |
| Set a record scope | `yes` - edit modal scope select `page.tsx:259-267` (same reachability limit) `[NOT CHECKED live: same as the row above]` | same `PATCH` | same | `yes` - `scope` enum `packages/domain/src/users.ts:41`; written `users.service.ts:222-228` | `yes` - `Membership.scope` |
| Deactivate (revoke access) | `yes` - "Pasif - erişimi kaldır" inside the edit modal's Üyelik durumu select, `page.tsx:265-280`; the actor's own option is omitted `page.tsx:271-274` | `yes` - `PATCH` with `active=false`, `actions.ts:82-86` | same | `yes` - `SELF_DEACTIVATE` `users.service.ts:181-185`; revokes tokens/sessions/activations `users.service.ts:271-320` | `yes` - `Membership.active=false` + device/session/activation revocation |
| Reactivate | `yes` - the inline "Yeniden etkinleştir" form `page.tsx:210-232` (**unreachable on this install**: no inactive non-super-admin membership exists) `[NOT CHECKED live: no inactive membership in the platform org]` | `yes` - `PATCH /users/:id` `{active:true}` `actions.ts:80-81` | same | `yes` - `INACTIVE_MEMBERSHIP_REACTIVATION_ONLY` `users.service.ts:196-204` - the surface's only-offer agrees (`page.tsx:209`) | `yes` - `Membership.active=true` |
| Read one member's detail | `no` - no detail view anywhere | `yes` - `GET /users/:id` `users.controller.ts:49-50`; live `200` with a richer body | `yes` - `user.manage` | `yes` - `users.service.ts:77-106` | `yes` - `findFirst` |
| Read the assignable roles | `yes` - both role selects, `page.tsx:113-119,251-257` | `yes` - `GET /users/roles` `page.tsx:59` | `yes` - `@RequireAdminPanel()` + `user.manage`, `users.controller.ts:42-44`; this route is panel-only by design (comment `users.controller.ts:40-41`) | `yes` - `listRoles` `users.service.ts:69-75` | `yes` - `prisma.role.findMany` |
| Deactivate through the dedicated endpoint | `no` - no surface and no client calls it (search below) | `yes` - `POST /users/:id/deactivate` `users.controller.ts:82-86` | `yes` - `user.manage` | `yes` - `setActive` `users.service.ts:246-269` | `yes` - same write as the PATCH path |

Absence proof for "Deactivate through the dedicated endpoint": `grep -rn "deactivate" apps/admin
apps/mobile/src --include='*.ts' --include='*.tsx'` matched only push-token deactivation
(`push-lifecycle.ts:109`, `push-api.ts:40`) and no users path; `grep -rn "users/\${" apps
--include='*.ts(x)' | grep -v test` returned exactly two hits, `actions.ts:89` and
`organization-users-api.ts:56`, both PATCH. So the route exists, the capability exists, and no
surface reaches it (D16).

Read together with the sibling surface: the mobile app offers the same feature for tenant staff
with its own role list that **excludes** SUPER_ADMIN by type
(`organization-users-api.ts:36`, `OrganizationUsersScreen.tsx:28-35`) and enforces that boundary
with a contract test
(`apps/mobile/src/features/users/organization-users-role-boundary.contract.test.ts:8-16`). The admin surface has no equivalent
guard, and the comparison is what makes D1 a defect rather than a taste note.

Matrix 1 coverage: 11 rows, 11 checked; 2 rows carry a reachability limit measured on the
running install (D2).

---

## Matrix 2 - field contract

The list response is the only shape the surface parses: `page.tsx:19-33`. The detail endpoint
serves a second shape for the same field (`roles`), see D12.

| Field | Column / type | Read by the API | Written by the API | Rendered (list / detail / form) | Validated | Label or enum source | Locale / format |
|---|---|---|---|---|---|---|---|
| `id` | uuid | `yes` `users.service.ts:35` | `n/a` (key only) | list: as the row key only `page.tsx:181`; form: hidden `page.tsx:215,245` | `yes` - `z.uuid()` `actions.ts:77` | n/a | n/a |
| `displayName` | String, 1-120 | `yes` `users.service.ts:37` | `yes` on invite `users.service.ts:131`; refused on update `users.service.ts:328-335` | list column "Ad" `page.tsx:184`; invite field `page.tsx:88-91` with `maxLength={120}` | `yes` - `.trim().min(1).max(120)` `packages/domain/src/users.ts:13` | none needed | server stores as sent; no localisation |
| `email` | String unique, normalized | `yes` `users.service.ts:38` | `yes` on invite `users.service.ts:129-130` + `normalizeEmail` `users.service.ts:115` | list column "E-posta" `page.tsx:185`; invite field `page.tsx:92-95` | `yes` - `z.email()` `packages/domain/src/users.ts:12` | n/a | not normalised for display; the stored `email` is the `trim()`ed input |
| `status` | `UserStatus` = INVITED/ACTIVE/SUSPENDED/ARCHIVED (`schema.prisma:39-44`) | `yes` `users.service.ts:39` | `yes` - invite writes `ACTIVE` `users.service.ts:127`; nothing writes INVITED/SUSPENDED anywhere (`grep "status: 'INVITED'"` -> 0 hits outside generated code) | column "Durum" as a badge `page.tsx:186-190` | `yes` server default `schema.prisma:1061` | panel map `user-labels.ts:16-22`; the repo's shared map is `lib/admin-labels.ts:4-40` | the word "Aktif" also labels `membership.active` (D6); DEACTIVATED/DELETED in the map are unreachable, ARCHIVED has no label (D5); the non-ACTIVE rendering is `[NOT CHECKED: no row in a non-ACTIVE state exists on this install]` |
| `locale` | String (`tr-TR` default) | `yes` `users.service.ts:40` | `no` - refused with `GLOBAL_PROFILE_SELF_SERVICE_REQUIRED` `users.service.ts:328-335` | **not rendered anywhere** (search below) | `yes` on update `packages/domain/src/users.ts:28` | none | the copy explains why: `page.tsx:164-165` |
| `membership` nullability | nullable object in the surface schema `page.tsx:26-31` | `yes` | `yes` | three branches `page.tsx:198,204` | `no` | n/a | unreachable given `users.service.ts:28-32` (D13) |
| `membership.scope` | String (no DB enum) `schema.prisma:1113` | `yes` `users.service.ts:44` | `yes` `users.service.ts:222-228` | column "Kapsam" `page.tsx:196-198`; both selects | `yes` - the four-key enum `packages/domain/src/users.ts:23,41`; the page re-declares them `page.tsx:37` | `scopeLabels` `user-labels.ts:10-14` - the mobile surface uses different words for the same keys (D14) | invite default `assigned` `page.tsx:121` vs domain default `organization` (D15) |
| `membership.active` | Boolean | `yes` `users.service.ts:45` | `yes` `users.service.ts:205-221` | column "Üyelik" `page.tsx:200`; filter `?state=` `page.tsx:151-157` | `yes` - `z.boolean()` on the API; the action parses `'true'/'false'` `actions.ts:85` | inline ternary `page.tsx:200` (`'Aktif'/'Pasif'`) | collides with `status` (D6) |
| `membership.roles` | list | `yes` as `string[]` `users.service.ts:46-49,58`; as `{key,name}[]` on `GET /users/:id` `users.service.ts:96-104` | `yes` - replace-on-write `users.service.ts:244` | column "Roller" `page.tsx:192-193` | `yes` - the seven-key enum on write `packages/domain/src/users.ts:14-22,30-40` | `roleLabels` `user-labels.ts:1-9` shadows the API's own `name` (`?? role.name`, `page.tsx:115`) | one field, two shapes (D12) |
| `page` (envelope) | `{nextCursor, hasNextPage}` | `yes` - always `{null,false}` `users.service.ts:64` | n/a | **not declared and therefore stripped** `page.tsx:19-33` | `no` | n/a | the count line prints the page size as the total `page.tsx:164` (D9) |

Absence proof for `locale`: `grep -rn "locale" apps/admin/app apps/admin/components` (excluding
tests) matches only `user-labels.ts`-adjacent files and no users-page render site; the seven
`<td>` render sites are `page.tsx:184-200`. So a field the list contract carries has no view.

Matrix 2 coverage: 11 rows, 11 checked; 1 cell not checkable at runtime (`status` in a
non-ACTIVE state - no such row exists on this install, see Coverage).

---

## Matrix 3 - flow and step contract

This feature has no wizard. The two multi-step flows are the two dialog flows; the reactivate
action is the one-step flow, and the contrast between them is a finding (D7).

**Flow A - invite (form -> confirmation -> server action -> redirect).**

| Step | Precondition | What it validates | What it writes | How a skip is prevented | Resume / persistence | Back-navigation retention | Where an error lands |
|---|---|---|---|---|---|---|---|
| 1. Invite form (modal) | `canInvite` (`page.tsx:46`), an org role list (`page.tsx:59`), the modal opened by a button or Enter (`AdminModal.tsx:99-106`) | native `required` + `type=email` + `maxLength` (observed: `novalidate` absent, `:invalid` = displayName, email); `InviteUserInput.parse` `actions.ts:55`; SUPER_ADMIN refusal `actions.ts:61` | nothing | n/a | the modal is client state (`AdminModal.tsx:53`) - **a reload loses the typed values** (inherent to a dialog; no draft exists) | `yes` - measured: typing Ad/E-posta/Kapsam, opening the confirmation, pressing Escape leaves the modal open with all three values intact | the form summary `role=alert` `AdminActionForm.tsx:272-292`; field errors mapped by name `actions.ts:26`; measured: focus moves to the summary |
| 2. Confirmation step | step 1 submitted | nothing | pre-populated answers only | **client only** - the server action has no confirmation evidence (`actions.ts:53-72`); a direct call to the action skips this step | lost on cancel by design (`AdminActionForm.tsx:309` keeps the form, drops the submission) | measured: cancel returns to the filled form | the confirm step has no error surface; errors land back on step 1 |
| 3. Server action | `requireAdminMutation('team.invite')` `actions.ts:53`; API `user.manage` | as step 1 + `ALREADY_MEMBER`, `ROLE_NOT_FOUND` `actions.ts:30-44` | User + Membership + MembershipRole + audit + outbox `users.service.ts:118-176` | n/a | n/a | n/a | returned to step 1 as `{error, fieldErrors}` |
| 4. Outcome | n/a | n/a | n/a | n/a | `revalidatePath('/users')` + `redirect('/users?result=user-invited')` `actions.ts:70-71` | n/a | the success lane only; no failure redirect exists (D18) |

**Flow B - access edit (modal -> confirmation -> PATCH).** Same four steps; step 1's fields are
Rol / Kayıt kapsamı / Üyelik durumu (`page.tsx:247-280`), the confirmation names three facts
(`page.tsx:236-244`), the write is `PATCH /users/:id` with `UserUpdateInput` (step 3), and step 4
redirects with `result=user-updated` (`actions.ts:98`). One divergence from Flow A: the
confirmation's *body* names the consequence ("Pasife alma bu işletmedeki oturumları ve cihaz
erişimini kaldırır", `page.tsx:239-241`). Flow B steps 1-2 were
`[NOT CHECKED: no eligible member in the platform org, so the dialog never rendered]`; its route,
action, service and confirmation configuration were read instead.

**Flow C - reactivate (one step).** `page.tsx:210-232`: a hidden `operation=reactivate` plus a
submit button, no confirmation, and the action builds `{active:true}` (`actions.ts:80-81`). It
grants access in one click while Flow B's confirmation guards the same field - D7. Flow C never
rendered on this install `[NOT CHECKED live: no inactive membership exists]`.

Skip-prevention note that belongs to the record: the `INACTIVE_MEMBERSHIP_REACTIVATION_ONLY`
rule (`users.service.ts:196-204`) and the surface's decision to offer *only* reactivation for an
inactive membership (`page.tsx:209`) agree, so no step can be reached without its precondition
through the UI; a URL cannot name a step because the flows live in modals, not routes.

Matrix 3 coverage: 3 flows, 12 step cells checked; 1 cell not observable (Flow B step 1's
rendered state - no eligible row, see Coverage).

---

## Matrix 4 - interaction dependency

| Trigger | Dependents | Required action on change | Who owns the state | What is announced |
|---|---|---|---|---|
| `q` (search box) | the row set, the count line, the empty state | recompute (on submit) | the URL (`page.tsx:40-42`), re-rendered by the server | nothing in-page; the submit is a document navigation, so the new document is the announcement. Measured: `?q=abc` renders `value="abc"` back into the control |
| `state` (Üyelik durumu) | the row set, the count line, the empty state | recompute (on submit) | the URL; `defaultValue` from `input.state` `page.tsx:151-157` | as above. Measured: `?state=active` re-selects "Aktif"; `?state=inactive` yields 0 rows and the empty state |
| `state` set to a value the control does not offer | the control's own display | **reset or reject** - today the value is silently dropped | the URL keeps `state=bogus` while the control displays "Tümü" (measured: `selectedIndex 0`, `value ""`, `url ?state=bogus&q=abc`) and the server applies no state filter | nothing announces that the supplied value was ignored |
| "Filtreleri temizle" | `q`, `state`, the row set, the count | reset | the URL - it is a plain `href="/users"` (`page.tsx:159-161`) | n/a (navigation). Measured: from `?state=bogus&q=abc` the link's target carries no parameters, so no control keeps a stale value - the class the artifact names does **not** occur here |
| `roleKey` (invite and edit) | `scope` (must the valid scopes narrow?) | keep | the form (`page.tsx:113-119,251-257`) | n/a - the service accepts every role/scope pair (`users.service.ts:113-176`), so no cascade is required and none is missing |
| `active` (edit modal) | `roleKey`, `scope` (a revoked membership's role is meaningless) | **keep, with a consequence** - the form offers "Pasif" together with a new role and scope in one submit; the service accepts the combination and writes all three (`users.service.ts:205-244`) | the form | the confirmation names both effects in one sentence (`page.tsx:239-241`) - this is a `keep` row, not a defect: no standard forbids writing a role that a deactivated membership cannot use |
| Invite modal opened / closed | the page behind it | keep, inert while open | `AdminModal` (native `showModal`) | native dialog semantics; measured: focus enters (the ✕ button), Escape returns focus to the trigger |
| A field error arrives from the action | the error summary, the failing controls | reset then revalidate | `AdminActionForm` | `role=alert` summary + `aria-invalid`/`aria-describedby` on the controls (measured) |

Matrix 4 coverage: 8 rows, 8 checked; 5 are pure `keep` rows (agreement), 1 is a stale-value
finding (folded into D20's family - the URL keeping a value the view ignores), 2 are pass rows.

---

## Matrix 5 - surface pattern: data views, controls, validation, flows, notifications

Every row is the rule from the artifact and what this surface does. Sources: APG patterns,
WCAG 2.2 SC, GOV.UK Design System (read at source 2026-09-20).

### Data views

| Rule | Verdict |
|---|---|
| SC 1.3.1 real headers + a labelled table | `pass` - `<th scope="col">` on all seven headers, an `srOnly` `<caption>`, and the region is named (observed: tree shows `table "Kullanıcı listesi"` with `columnheader` children) |
| `aria-sort` on the sorted column | **violation (D19)** - the API sorts by `displayName asc` (`users.service.ts:63`) and every header measures `aria-sort: null`; no sort control exists |
| Editable cells / per-row widgets = a grid | `pass` on this data - one control per row, and while a modal is open the rest is inert (native `showModal`), so the tab order per row is one stop |
| `aria-rowcount`/`aria-colcount` for large or lazy sets; detail return restores position | `n/a` - the list is not virtualised and there is no detail view to return from |
| SC 1.4.10: one-direction page scroll at 320, table inside its own scroll container | `pass` for the document (measured `docScrollWidth == innerWidth == 320`, no page-level horizontal scrollbar) and the table does sit in its own `overflow-x: auto` region; the *affordance* half fails - see next row |
| A scroll region says it scrolls (affordance, or no clipping) | **violation (D4)** - measured: table 1140 px inside a 1084 px container at 1440 and inside 242 px at 320, no fade, no visible scrollbar, and the email clips mid-address at 320 in the rendered image |
| Pagination marks the current page in a labelled nav; a one-page pager is hidden | `n/a` for a pager (none exists), and the count line is the only position cue; the unrelated sidebar nav does carry `aria-current="page"` (`AdminSidebar.tsx:70`) |
| Content: captions/headings describe the data, short noun headings, first column a human-readable identifier | `pass` - h1 "Yöneticiler", h2 "Kullanıcılar", first column the display name (observed) |
| Filters discoverable, active state visible in the results | `partial` - the controls are labelled and their values are reflected from the URL (measured), but nothing in the results view states which filter is active beyond the count line (D10) |
| Detail view: `dl` key/value pairs, every field shown or explicitly absent | `n/a` - no detail view exists; the endpoint that would feed one is uncalled (D12) |
| Long text has a truncation or wrapping strategy | **violation, same family as D4** - `th, td { white-space: nowrap }` (`globals.css:573`) makes a 120-character name or a long address stretch the table with no truncation affordance; measured 1140 px on a single 20-character row (no fixture was injected - see Coverage) |

### Controls

| Rule | Verdict |
|---|---|
| `APG combobox` roles/`aria-expanded`/`aria-autocomplete` | `n/a` - no combobox is used; role and scope are native `<select>` elements (a native select is not the APG combobox pattern and does not need it) |
| `APG combobox` keyboard behaviour | `n/a` - same reason |
| `APG listbox`: options owned, selection exposed, single choice as radios | `pass` - native `<select>`/`<option>`; the tree shows `combobox "Üyelik durumu"` with `option` children and `[selected]` on the active one |
| A row carrying its own controls is a grid, not a listbox | `pass` - no listbox is used |
| Visible persistent label; instructions where the format is unusual; a counter where a length limit exists | `pass` - labels are persistent (`<label><span>`), `type=email` carries the format, and `displayName` carries `maxLength={120}`; the *error* text for an over-long name comes from the domain, not the control |
| SC 1.3.5 `autocomplete` token scoping | `pass` - the invite fields collect **another person's** name and address, so absent is correct; no field on this surface collects the operator's own data |
| One required/optional convention across the product | `pass` here - `required` with no asterisks, matching the panel's other forms (`fieldHelp` names the rules, `actions.ts:11-17`) |
| `APG disclosure` for show/hide | `n/a` - no disclosure control |
| `APG tabs` | `n/a` - no tabs |
| A conditional reveal reveals a question and announces it | `n/a` - nothing is conditionally revealed; the per-row branch renders one of four disjoint actions (`page.tsx:201-286`) |
| Pickers: text entry alongside the calendar, a combobox where free text plus a known list is needed | `n/a` - no date or free-text-plus-list control |
| SC 2.5.8 target size 24x24 (or the design system's floor) | `pass` - measured: buttons/inputs/selects 44 px high, the modal close button 36x36 |
| SC 2.4.7 / SC 1.4.11 focus visible | `pass` - measured on the search input and the select: `outline: rgb(20,95,192) solid 3px` (`globals.css:2531-2533`, `--focus-ring: #145fc0` at `globals.css:29`) |
| SC 1.4.3 contrast 4.5:1 / 3:1, no colour-only state | `pass` for text, `violation` for boundaries - measured light: muted 5.83:1, badge 14.5:1, white-on-primary 4.68:1; dark: muted 7.6:1, badge 12.21:1; **input/select/outlined-button borders 1.65:1 light and 1.73:1 dark (D8)**. No state is signalled by colour alone (the badge carries text) |

### Validation and errors

| Rule | Verdict |
|---|---|
| Validation on submit, failing values kept, server-side validation present, `novalidate` not set | `pass` - measured: `novalidate` absent; the native `invalid` burst is collected into one summary (`AdminActionForm.tsx:118-150`); the values stay in the form after a failure; the server validates with `InviteUserInput`/`UserUpdateInput` |
| SC 3.3.1/3.3.3 the item is identified and the correction described | `pass` for the fields (the message sits beside the field it belongs to), **violation for the summary (D17)**: two empty fields produce "Bu alanı doldurun." twice with no field name |
| Association: `aria-describedby` to the message, the same wording, a summary entry that moves focus to its field | `pass` - measured: `aria-invalid=true` and `aria-describedby=<form-id>-error-0/1` on both fields; the summary items are buttons that focus the field (`AdminActionForm.tsx:283-290`) |
| An error summary at the top of the form naming what went wrong and linking each item to its field | `pass` with the D17 wording gap - the summary is at the top and focused (`role=alert`, measured `focused: true`), and each entry focuses its field |

### Flows

| Rule | Verdict |
|---|---|
| One question per page/group, unique heading per step, a back link and Continue | `pass` - each step is one dialog with its own h2 ("Takım üyesi davet et", "Davet oluşturulsun mu?") and the confirmation has a cancel plus a named action |
| Check-your-answers pre-populated, a Change link per section, a submit that names its action | `pass` - measured facts `Ad = Deneme Kullanıcı`, `E-posta = …`, `Rol = Platform sahibi`, `Kapsam = Kendi kayıtları`; the action is "Daveti oluştur". The *edit* flow's confirmation omits a Change affordance but returning to the form is one Escape away (measured) |
| Task list status in text | `n/a` |
| SC 3.3.7 redundant entry not asked twice in one flow | `pass` - one step collects the values once |
| SC 3.3.4 a submission that changes stored data is reversible, checked or confirmed | `pass` for invite and revoke (confirmation with consequences named), **violation for reactivation (D7)**: one click, no confirmation |
| Destructive confirmation names what will be lost, actions inside the panel, reserved for the irreversible | `pass` by source - the invite confirmation names role and scope; the revoke body names the sessions and device access (`page.tsx:239-241`). The rendered revoke confirmation is `[NOT CHECKED: no eligible member renders the edit modal on this install]` - see Coverage |
| `APG dialog`: `aria-modal` only when the outside is inert and obscured, focus moves in and stays, returns to the invoker, an alertdialog focuses the least destructive action | `pass` - native `<dialog>` + `showModal` (inert outside, 60% backdrop measured `rgba(10,24,18,0.6)`), no `aria-modal` on a non-inert panel, focus enters on open, Escape returns focus to the trigger (measured), and the confirmation focuses "Vazgeç" (measured) |

### Notifications

| Rule | Verdict |
|---|---|
| SC 4.1.3 a page-made change is programmatically determinable | `pass` for this surface, by the navigation argument: every filter change is a document navigation, so the result is the new document, and the mutation result is rendered through `MutationNotice` with `role="status"` (`MutationNotice.tsx:133-135`). The count line itself carries no `role`/`aria-live` (measured) - if the surface ever filters without navigating, this row flips |
| The whole status string is the announced unit, the end of a wait is announced | `pass` - the form's pending label is a `role="status"` element (`AdminActionForm.tsx:268-271`) and the result sentence is rendered whole |
| Changes that are not status messages stay out of live regions | `pass` - the disclosure-free page has no stray live region |
| A notification banner is a labelled region, before the h1, at most one per page, never a substitute for validation errors | `n/a` - this surface renders no banner; `MutationNotice` is not a banner |

Matrix 5 coverage: 40 rules read (11 data views, 14 controls, 4 validation, 7 flows, 4
notifications), 30 verdicts resolved; 10 `n/a` (no combobox, no listbox, no tabs, no
disclosure, no conditional reveal, no picker, no grid, no detail view, no task list, no
banner).

---

## Findings, most severe first

Severity is the artifact's 0-4 scale (frequency x impact x persistence): 4 = the feature does
not work for anyone today; 3 = it works but a whole class of the job is unreachable or the
wrong thing is displayed; 2 = a layer disagrees with another layer; 1 = a single surface
detail. Each finding names exactly one evidence class; citations for the supporting layers
follow the class.

**D1 - the invite surface offers only the role both the action and the service refuse. Severity 4.**
`ui-observed`. Live, 2026-09-20: the invite modal's role select renders exactly one option,
`SUPER_ADMIN=Platform sahibi`, and `GET /users/roles` returns `[{key:'SUPER_ADMIN',
name:'Platform Sahibi'}]`; the DB confirms one role in the platform org (roles table, 8 rows
total, `…-0003` holds only SUPER_ADMIN). The action refuses it (`actions.ts:61`) and the service
refuses it (`users.service.ts:114-116,336-347`), so the invite can never be submitted
successfully on a real install; the confirmation step even names the forbidden value
("Rol = Platform sahibi", measured).
*Prevent:* filter the offered set to the assignable keys and disable the trigger with a reason
when it is empty, and pin it with a test that runs every rendered option through
`InviteUserInput.safeParse` plus the action's own refusal. The existing test asserts the
opposite on a fixture whose `orgRoles` (`page.test.tsx:24-28`) omit SUPER_ADMIN - the fixture is
what hides this.

**D2 - every role the panel can assign keeps the target out of the panel, and the update column
is unreachable on a real install. Severity 4.** `code`.
Panel access requires an active membership in a `kind = PLATFORM` organization carrying
SUPER_ADMIN (`auth.service.ts:39-43`, `admin-panel.guard.ts:39-40`,
`admin-panel-session.ts:8-13`), so the six non-super-admin roles the form offers grant no panel
access, while the one that does is refused (D1) and can only be granted by the out-of-band CLI
(`ops/provision-super-admin.ts:16`, no HTTP caller). The update path is blocked twice more: the
platform org's only user is a SUPER_ADMIN, whose row the surface replaces with a note
(`page.tsx:205`, measured live: "Platform sahibi erişimi bu ekrandan değiştirilmez"), and that
user is the actor. The whole "Yetki güncelle" column is therefore reachable by no one.
*Prevent:* an e2e that assigns a panel-usable role through `/users` and then signs in as that
account - it fails today, which is the point; until it passes, the column should not be rendered
for a role set with no assignable member.

**D3 - an invite creates an account nobody can use and delivers nothing. Severity 3.** `code`.
The password is random (`users.service.ts:116,323-325`) and no invite-email path exists: the
API's only email provider is the password-reset one (`auth/password-reset-email.provider.ts:6`),
and the same repository hands a credential over explicitly elsewhere
(`organizations/tenant-provisioning.ts:90-98,119` returns `temporaryPassword`, rendered by
`lib/login-handover.ts:12-13`). The invite's only output is an outbox event
(`users.service.ts:169-175`) -> an in-app row plus a push attempt per **active** device token
(`worker/push-notification.handler.ts:340-368`), and a freshly created account has no token, so
the loop body never runs. The operator sees "Takım daveti oluşturuldu".
*Prevent:* P1 below; until it lands, the success copy must not claim a delivery, and the panel
should hand over a credential the way the organisations surface does.

**D4 - the table is clipped inside its own scroll container with no affordance. Severity 3.**
`ui-observed`. Measured at 1440: table 1140 px, container 1084 px (`overflow-x: auto`), no
fade/scrollbar in the rendered image; at 320: table 1140 px, container 242 px, the email clipped
mid-address ("platform@ser") with no affordance. The document itself reflows correctly
(`docScrollWidth == 320`), so SC 1.4.10's document requirement holds and the table exception is
exactly what hides the clip.
*Prevent:* assert on the container, not the document - the document-overflow check passes while
the last column is clipped - with a rule that `container.scrollWidth > clientWidth` implies a
visible affordance, plus a 320 px check that fails on a mid-word cut.

**D5 - the account-status vocabulary disagrees with persistence and an invited user reads
"Aktif". Severity 3.** `code`.
The DB enum is INVITED/ACTIVE/SUSPENDED/ARCHIVED (`schema.prisma:39-44`); the panel's map
carries INVITED, SUSPENDED plus two values no row can hold (DEACTIVATED, DELETED,
`user-labels.ts:20-21`) and has no label for ARCHIVED; nothing anywhere writes INVITED (the
invite writes ACTIVE, `users.service.ts:127`), so "Davet edildi" is unreachable while an account
that has never received a credential is displayed as "Aktif" - the same word the membership
column prints for a different field (D6).
*Prevent:* a contract test pinning the label map's key set to the persistence enum, which fails
today on both sides, plus a writer for INVITED (or deletion of the label).

**D6 - two fields print the same word in one row. Severity 3.** `ui-observed`.
Live row: `Aktif | Platform sahibi | İşletmedeki kayıtlar | Aktif` - "Durum" is `user.status`
(`page.tsx:186-190`) and "Üyelik" is `membership.active` (`page.tsx:200`), and the filter that
drives the list (labelled "Üyelik durumu") targets the second. The image read confirms the two
"Aktif" cells are styled differently (badge vs plain text) and the tree shows them under two
unrelated headers.
*Prevent:* vocabulary that cannot collide ("Hesap"/"Üyelik" prefixes) asserted by a component
test that renders `status=ACTIVE, active=false` and asserts the two cells' text differ.

**D7 - the grant of access is unconfirmed while its revocation is confirmed. Severity 3.**
`ui-observed` + code. "Yeniden etkinleştir" posts on a single click (`page.tsx:210-232`, no
`confirmation` prop), while "Pasif - erişimi kaldır" and the same `active=true` change through
the edit modal are both behind `AdminActionForm` confirmations (`page.tsx:236-285`); the
confirmation is client-side only (`actions.ts:75-96` accepts the mutation with no confirmation
evidence).
*Prevent:* one rule in the shared form component - a form whose action receives an access flag
declares `confirmation`; a component test fails when it does not.

**D8 - the only boundary of the filter controls is a 1.65:1 border. Severity 3.** `ui-observed`
(measured). `#c6cbc3` on `#fff` = 1.65:1 light; in dark, `rgb(59,71,65)` on `rgb(23,31,28)` =
1.73:1 (`globals.css:177-185` input/select, `:206-210` secondary button; dark values from the
`[data-theme]`/media blocks). SC 1.4.11 wants 3:1 for the boundary that identifies a component,
and the white input on a white card has no other boundary.
*Prevent:* a computed-border-contrast assertion in the visual sweep; axe-core does not fail this
by default, so the check must be explicit (see "What cannot be checked mechanically").

**D9 - the pagination envelope is a constant and the surface drops it. Severity 2.** `code`.
`list()` returns `page: {nextCursor: null, hasNextPage: false}` unconditionally with no
`take`/`skip` (`users.service.ts:26-65`), the page's schema omits `page` so zod strips it
(`page.tsx:19-33`), and the count line prints the returned rows as the total ("N kullanıcıdan M
kayıt", `page.tsx:164`). Every sibling list surface declares and renders it
(`customers/page.tsx:34,402`, `work-orders/page.tsx:40`).
*Prevent:* a contract test asserting `hasNextPage === (rows.length === limit)` for a list larger
than the limit, plus a schema-parity check against the OpenAPI envelope instead of a hand-written
zod shape.

**D10 - the list filter runs in the app layer while every sibling surface filters at the API.
Severity 2.** `code`. `page.tsx:60-66` filters the fetched array in memory; `work-orders` sends
`q` (`work-orders/page.tsx:94`) and `customers` sends `query`+`cursor`
(`customers/lookup-actions.ts:26-34`). Consequence: a filtered count is a page size, and the
filter cannot see a row the API did not return.
*Prevent:* a server-side query parameter for `q`/`state` with a parity test, or a lint rule
against filtering a fetched collection in a page component.

**D11 - the role contract accepts seven keys while persistence and the response allow any.
Severity 2.** `code`. `Role.key` is free text (`schema.prisma:1411-1425`), `listRoles` returns
every role of the org (`users.service.ts:69-75`), and the write input accepts a fixed seven-key
enum (`packages/domain/src/users.ts:14-22,30-40`). An org-defined eighth role would be offered
by the select and then rejected by the action's own parse (`actions.ts:55`), reported to the
operator as "Listeden geçerli bir rol seçin" (`actions.ts:15`). Falsifier checked: the roles
table holds 8 rows and every key is one of the seven, so no live org has such a role today.
*Prevent:* P2 below; until then the select must render only enum-valid keys.

**D12 - one field, two shapes across two endpoints of one feature. Severity 2.** `code`.
`GET /users` returns `membership.roles: string[]` (`users.service.ts:55-60`); `GET /users/:id`
returns `[{key,name}]` (`users.service.ts:96-104`). Only the first shape has a consumer (the
grep above: two call sites, both PATCH; the live `GET /users/:id` answered `200` with the richer
body), so the second shape is unvalidated by any schema and the detail endpoint has no surface
(Matrix 1, "Read one member's detail").
*Prevent:* derive the admin's response schemas from the generated OpenAPI document - the repo
already ships `scripts/verify-api-contract.mjs` and `api:contract:verify` - so two shapes for one
field cannot both pass.

**D13 - the surface branches on states its own query cannot produce, and an empty role list
renders blank. Severity 2.** `code`. `membership` is nullable in the surface schema
(`page.tsx:26-31`) and the "Üyelik yok" cell exists (`page.tsx:198,204`), while the API requires
a membership in the caller's org (`users.service.ts:28-32`); `roles.map(...).join(', ') ?? '—'`
(`page.tsx:192-193`) never falls back for an empty array, so a role-less membership prints an
empty "Roller" cell with no marker.
*Prevent:* make the API's non-null guarantee explicit in the schema and render an explicit
"not provided" marker for an empty list, asserted by a fixture with `roles: []`.

**D14 - one enum labelled from two sources, with different words. Severity 2.** `code`.
The panel keeps a screen-local map (`users/user-labels.ts:1-14`) whose values shadow the
server's own names (`roleLabels[role.key] ?? role.name`, `page.tsx:115`), while the mobile
surface labels the same enum from the design system's shared source: ORG_ADMIN "İşletme
yöneticisi" vs "Kuruluş yöneticisi", SUPER_ADMIN "Platform sahibi" vs "Sistem yöneticisi",
scope `organization` "İşletmedeki kayıtlar" vs "Tüm organizasyon"
(`user-facing-labels.ts:68,105`, `OrganizationUsersScreen.tsx:28-41`). The repo's shared panel
label module is `lib/admin-labels.ts` (its header states that every on-screen value is named
there), yet this map lives in a route folder that two other surfaces import
(`announcements/campaign-model.ts:2`, `membership/page.tsx:7`).
*Prevent:* one label module per enum, with a test that fails when two files define a label for
the same enum key.

**D15 - one field, two defaults and an unguarded label lookup. Severity 2.** `code`.
The domain defaults `scope` to `organization` (`packages/domain/src/users.ts:23`) and the invite
form defaults the select to `assigned` (`page.tsx:121`); the page re-declares the four scope
keys instead of importing the domain enum (`page.tsx:37`); the edit modal renders
`scopeLabels[scope]` with no fallback (`page.tsx:263`) where the invite modal has one
(`page.tsx:125`), so an unknown scope renders an empty option.
*Prevent:* import the enum and one label function in both selects; a test that renders every
domain scope value through both and asserts a non-empty label.

**D16 - deactivation is audited as a generic update. Severity 2.** `code`.
The live path records `action: 'user.update'` with `redactedDiff: {changed: ['active']}`
(`users.service.ts:232-238`), while the specific `'user.deactivate'` action
(`users.service.ts:268`) is reachable only through the endpoint no client calls
(`users.controller.ts:82-86`, D12's grep). The audit trail the product claims for a revocation
therefore reads as an ordinary membership edit.
*Prevent:* pin the audit action name to the operation actually performed, and delete the dead
endpoint so one transition cannot carry two names.

**D17 - the error summary repeats a message without naming the field. Severity 1.**
`ui-observed`. With Ad and E-posta empty the summary is "Bu alanı doldurun." twice (measured,
`role=alert`, focus lands on it, both entries focus their field) - the user has to click to learn
which item is which, and SC 3.3.1/3.3.3's identifying wording is only beside the field.
*Prevent:* the summary entry's accessible name must be "<label>: <message>"; a component test
asserting two failing fields produce two distinct summary items.

**D18 - an accepted search parameter no producer can set. Severity 1.** `code`.
The page accepts `?error=` and renders it through `MutationNotice` (`page.tsx:73`,
`MutationNotice.tsx:119-127`), but this feature's failures return to the form and never redirect
with `error` (`actions.ts:29-52` returns; `:71` and `:98` redirect with `result` only), so the
page-level failure lane exists only for a hand-written URL.
*Prevent:* delete the parameter or produce it; a test that every accepted `searchParams` key has
either a producer or a consumer.

**D19 - the fixed list order is undisclosed. Severity 1.** `code` + measurement.
The API sorts by `displayName asc` (`users.service.ts:63`); all seven headers measure
`aria-sort: null` and no sort control exists, so the announcement of the order (and the fact that
it cannot be changed) is missing.
*Prevent:* declare the fixed order in the caption, or expose `aria-sort` on the sorted column
with a control that reverses it.

**D20 - the search is a substring fold with no ASCII/diacritic tolerance and no explanation.
Severity 1.** `behaviour`. Measured live: `?q=sahibi` and `?q=SAHİBİ` return the row, `?q=SAHIBI`
returns 0 rows with the empty state and no hint (tr-TR-correct: 'I' is not 'İ'; the fold is
`toLocaleLowerCase('tr-TR')`, `page.tsx:60-66`). The page also prints Roller/Kapsam columns the
search cannot match.
*Prevent:* fold İ/I to `i` on both sides, or print the searched fields as a hint; a test with the
four I variants of a Turkish name.

**D21 - two gates, one permission, so a read-only view the panel cannot render. Severity 1.**
`code`. `canInvite` and `canUpdate` both resolve to `user.manage` (`mutations.ts:29,33`), so
`!canInvite && !canUpdate` (`page.tsx:48`) and the read-only branch whose copy promises "Kullanıcı
listesi yalnız görüntülenir" (`page.tsx:138-141`) are unreachable, and the per-row `canUpdate`
ternaries (`page.tsx:178,201`) are constants.
*Prevent:* one permission per gate or one gate per capability; a test that a read-only permission
set renders the read-only branch - it cannot fail today because no such set exists, which is the
finding.

**Pass rows (agreement between layers, the control that shows the matrices were filled):**

| # | Agreement | Citation |
|---|---|---|
| P1 | The read is gated by the same permission on the surface, the server action layer and the API, and the panel session is re-proved on every call | `page.tsx:46-56`, `mutation-guard.ts:12-18`, `users.controller.ts:34-35`, `api.ts:90-91` |
| P2 | Self-deactivation is refused by the surface (the option is omitted for the actor) **and** by the service | `page.tsx:271-274`, `users.service.ts:181-185` |
| P3 | A SUPER_ADMIN target is protected on three layers: the row note, the action, the service - and the out-of-band provisioning CLI is the documented alternative | `page.tsx:205`, `actions.ts:61,87`, `users.service.ts:336-347`, `ops/provision-super-admin.ts:16` |
| P4 | The invite writes user, membership, role, audit and outbox in one transaction; revocation also disables push tokens, refresh sessions and device activations | `users.service.ts:118-176`, `:271-320` |
| P5 | The surface offers reactivation *only* for an inactive membership, and the service refuses any mixed update on an inactive membership - the same rule on both sides | `page.tsx:209`, `users.service.ts:196-204` |
| P6 | Dialog semantics: native `<dialog>`/`showModal`, no `aria-modal` where the outside is inert and obscured, focus enters on open and returns to the invoker on Escape | `AdminModal.tsx:53-160`; measured |
| P7 | The confirmation pre-populates the answers, names each fact, focuses "Vazgeç", and cancel keeps the typed values | `AdminActionForm.tsx:232-257,309`; measured |
| P8 | Text contrast and focus visibility hold in both colour schemes | measured: muted 5.83:1 / 7.6:1, badge 14.5:1 / 12.21:1, white-on-primary 4.68:1, focus ring 3 px `rgb(20,95,192)` |
| P9 | Table semantics are real (caption, `scope="col"`, a named region) and the current nav item carries `aria-current="page"` | measured tree; `AdminSidebar.tsx:70` |
| P10 | Native validation is not suppressed, failing values are kept, errors are associated | measured (`novalidate` absent, `aria-invalid`, `aria-describedby`) |
| P11 | `locale` is unreadable from the panel by design and the copy says so; the write is refused with a named code | `page.tsx:164-165`, `users.service.ts:328-335` |
| P12 | The empty state, the "clear filters" reset and the count line exist and the reset carries no stale value | `page.tsx:159-168,287-291`; measured from `?state=bogus&q=abc` |

---

## Capability-change proposals

Two findings' fixes name a layer that does not exist, so they are proposals and not screen
recommendations. Each heading carries its evidence class; each proposal carries an artifact
another party can reject.

### P-1 - credential delivery for an invited member (from D3)

| Heading | Content | Falsified by |
|---|---|---|
| Capability (`code`) | The system can deliver a first-credential to a person it just created a membership for, and can prove the delivery happened. | A cited code path that already delivers it - the only provider is `auth/password-reset-email.provider.ts:6`, and it is invoked only from `password-reset.service.ts:89`. |
| Absence proof (`code`) | `apps/api/src/users/users.service.ts:116` hashes a random password that is never returned or sent; the invite's only output is the outbox event at `:169-175`, whose push fan-out iterates active device tokens (`worker/push-notification.handler.ts:340-368`) and a new account has none. Input that fails: `POST /users/invite` with `{email: new@x.test, displayName, roleKey, scope}` - the response is `{data:{id,displayName}}` (`users.service.ts:175`) and no credential exists anywhere. | A cited path that handles that input: the tenant-opening flow does (`organizations/tenant-provisioning.ts:90-98,119` returns `temporaryPassword`, surfaced by `lib/login-handover.ts:12-13`) - the fix is to route the invite through that pattern, not to invent one. |
| Contract delta (`code`) | OpenAPI/SDL: `POST /users/invite` 201 body gains `login: { email, delivery, credentialExpiresAt }` where `delivery` is `EMAIL` or `HANDOVER` and `credentialExpiresAt` is a timestamp or null; the invite-email template becomes a provider interface with a named implementation (`INVITE_EMAIL_PROVIDER`) and a `notification_delivery` row proving send+receipt. Rejectable artifact: `pnpm api:contract:verify` (existing) plus the contract verifier `scripts/api-contract-verifier.contract.mjs`. | Running the compatibility checker green with no diff - i.e. the response schema already declaring `login`. |
| Migration (`code`) | Expand: add `invite_delivery` (id, user_id, organization_id, channel, token_hash, sent_at, consumed_at, revoked_at) and the provider interface behind the existing outbox; migrate: backfill nothing (existing rows have no invite; state it explicitly) and create a delivery row for each new invite; contract: drop the `temporaryPassword`-in-response pattern for invites only after (dated) 2026-11-30, when the email path is live in production. | A contract phase with no date. |
| Rollout (`code`) | Flag `users.invite-credential-delivery`, boolean, expected lifetime 90 days from the first production send, initial exposure 100% of the platform org (the surface is panel-only), kill-switch owner the platform team's on-call, abort threshold: >2% of invite emails bounced **or** any invite with neither delivery nor handover within 15 minutes of the write, measured over a 7-day window. | An unmeasurable threshold, or a flag with no lifetime. |
| Verification (`code`) | A test that fails before and passes after: invite a fresh address against a fixture and assert (a) an email-provider call was recorded and (b) the delivered credential can be consumed once - the check must fail on the pre-change commit, where no provider is called at all. | A check that also passes on the pre-change commit (a test that only asserts the invite returned 200 passes both times). |
| Reversibility (`code`) | The new path writes `invite_delivery` rows and a one-time token hash; restore = mark the row `revoked_at` and clear `token_hash` (one UPDATE, named column by column); no password is mutated after creation, so nothing else needs restoring. | Data written with no restore step and no label. |
| Decision (`code`) | ADR "Credential delivery on invite - context: the panel invites members whose password no one holds; decision: handover or email delivery through the outbox, never a silent random password; status: proposed; consequences: a new provider, a delivery row, a 90-day flag". Supersedes: the implicit decision in `users.service.ts:323-325`. | An ADR without a status. |
| Appetite (`code`) | Two weeks: provider interface + delivery row + the invite path + the verification test. Out of bounds: password-reset changes, mobile deep-linking, any UI redesign of the modal. When the box ends: ship the handover variant (return `temporaryPassword`-style data for one-time display, the pattern the organisations surface already uses) and keep the email work for the next box. | No box, or an implicit extension. |

### P-2 - the role-assignment contract must accept what persistence allows (from D11)

| Heading | Content | Falsified by |
|---|---|---|
| Capability (`code`) | A callers' assignment contract that accepts any role the caller's organization actually defines, while still refusing the keys reserved for the approved provisioning path. | A cited code path that already does it - the input enum is fixed at seven keys (`packages/domain/src/users.ts:14-22,30-40`) while `Role.key` is free text (`schema.prisma:1411-1425`). |
| Absence proof (`code`) | `users.service.ts:69-75` hands every org role to the surface, and `actions.ts:55` rejects any key outside the enum with "Listeden geçerli bir rol seçin". Input that fails: an org role `key: 'SITE_MANAGER'` (inserted by the same upsert path that writes any role, `schema.prisma:1423`) - today it appears in the select and is refused on submit. Falsifier checked: no such row exists (roles table read 2026-09-20: ORG_ADMIN, TECHNICIAN, SUPER_ADMIN). | A cited path that handles that input. |
| Contract delta (`code`) | `InviteUserInput.roleKey`/`UserUpdateInput.roleKey` change from `z.enum([...])` to a UUID-or-key reference validated server-side against `role.organizationId === auth.organizationId` (the check already exists at `users.service.ts:139-146`), keeping an explicit refusal list in one named constant (`RESERVED_ROLE_KEYS = ['SUPER_ADMIN']`). Rejectable artifact: the OpenAPI diff for the two inputs plus the contract verifier run. | The compatibility checker green with no diff. |
| Migration (`code`) | No schema migration (the column is already free text). Ordering: add the server-side check and the reservation constant first; then widen the inputs; then (dated 2026-12-15) remove the enum from the domain package; backfill none. | A contract phase with no date. |
| Rollout (`code`) | Flag `users.role-assignment-by-reference`, boolean, lifetime 60 days, initial exposure the panel's platform org, kill-switch owner the API on-call, abort threshold: any assignment of a key that is not a role row of the caller's org (should be impossible) or >1 validation error per 1,000 invites attributable to a role key, over 7 days. | An unmeasurable threshold or a flag with no lifetime. |
| Verification (`code`) | A contract test that inserts an org role outside the current seven and asserts the invite succeeds for it and still fails for `SUPER_ADMIN`; it fails on the pre-change commit (today's enum rejects the inserted key). | A check that also passes pre-change. |
| Reversibility (`code`) | The change adds no write; the new path only admits a value the DB already holds. Restore = revert the commit; memberships written with a new key keep working because the enum is not in persistence. | n/a - one-way door not created. |
| Decision (`code`) | ADR "Role keys are organization data - context: persistence, the response and the surface already treat role keys as org data while the write contract pins seven literals; decision: validate by reference, reserve the platform keys by name; status: proposed; consequences: the domain package stops being the authority for assignable keys, the surface must render whatever the org defines". | An ADR without a status. |
| Appetite (`code`) | One week: the validation change, the reservation constant, the contract test, the mobile type (`OrganizationUserRole`) widening. Out of bounds: role CRUD, labels, permissions. When the box ends: keep the enum in the surface's filter only (so the select can never offer what the server refuses) and report the contract change as unfinished. | No box. |

Findings whose fixes name a layer that already exists therefore got **no** proposal: D1, D2, D4,
D5, D6, D7, D8, D9, D10, D12, D13, D14, D15, D16, D17, D18, D19, D20, D21 all resolve inside the
page, the shared components, the label modules, the CSS layer, the users service or the existing
contract artefacts. Reviewer's five absences: no capability is claimed without a `code` finding
behind it (P-1 from D3, P-2 from D11, both cited above); both proposals carry a rejectable
artifact (a contract-verifier diff, a typed flag with a lifetime, an ADR with a status); neither
touches a schema without named phases; both flags name a lifetime and an owner; both contract
changes carry an ADR and a pre/post check pair.

---

## Coverage

| Matrix | Rows checked | Rows/cells not checked | What would change the conclusion |
|---|---|---|---|
| 1 - capability | 11 of 11 rows | 0 unchecked. 2 rows (role assignment, reactivation) are layer-complete but **unreachable on this install**: the platform org holds one SUPER_ADMIN member, so the edit modal and the reactivate form were never rendered live - their evidence is code plus the existing unit tests | A second non-super-admin, active-then-inactive member in the platform org; then the two dialogs and the reactivate flow become observable end to end |
| 2 - field contract | 11 of 11 rows | 1 cell: a `status` value other than ACTIVE. The API filters ARCHIVED out (`users.service.ts:31`) and nothing writes SUSPENDED for a user, so no row can show it | A seeded SUSPENDED user: it would decide whether the badge tone and the "Askıya alındı" label render, and would test D5's ARCHIVED gap |
| 3 - flow and step | 3 flows, 12 step cells | 1 cell: Flow B step 1's rendered state (same reason as matrix 1). Flow C is not reachable at all | An inactive non-super-admin membership |
| 4 - interaction dependency | 8 of 8 rows | 0 unchecked | - |
| 5 - surface pattern | 40 rules, 30 verdicts | 10 `n/a` (listed above), 0 unchecked-but-applicable | If the surface ever filters without a navigation, the SC 4.1.3 row flips |

**Not checked, with the reason (each is a gap in this audit, not a pass):**

- The edit-modal and reactivate flows were not exercised: no eligible row exists (see above).
- The API write endpoints (`POST /users/invite`, `PATCH /users/:id`, `POST /users/:id/deactivate`)
  were **not called**: doing so writes to a live development database, and the audit must not
  mutate the feature it measures. Their behaviour is `code`-cited only, including D3's delivery
  gap and D16's audit name.
- axe-core was not run: `analyze-app`'s wiring is not available in this session. Contrast,
  geometry, focus, target size and the tree were measured directly instead, and the rows above
  say which read each verdict came from. The artifact's caveat stands: axe covers about 57% of
  WCAG and has no rule for 1.4.10, 2.4.7, 3.3.1, 3.3.3 or 4.1.3, so those five were hand-checked.
- The 120-character-name measurement: no fixture was injected. The evidence is the
  `white-space: nowrap` rule (`globals.css:573`) plus the measured 1140 px width for a single
  20-character row. The artifact's "2029 px" figure from another run is not reproduced here.
- The grayscale sweep was not run. The only colour-coded element is the status badge, which
  carries its own text, so no claim in this report depends on a grey reading. D8's boundary
  contrast was measured numerically, not by the grayscale test.
- The mobile surface was read, not launched: its runtime behaviour (labels, loading/error states)
  is `code`-cited.
- Only the local development database and the local dev servers were read; no production or
  staging shape was inspected.
- No dark-scheme *contrast* claim beyond the two measurements above; the dark read was a rendered
  image plus computed values for the muted text, badge and border only.

---

## Discipline

**Three passes, from different entry points:**

1. **First-time operator (running app, exercised).** Opened `http://localhost:3000/login`, signed
   in as the seeded platform owner, loaded `/users`, read the tree and the rendered image, opened
   the invite modal by keyboard, submitted it empty (native validation), followed the
   confirmation, cancelled, and pressed Escape. Findings D1, D4, D6, D7 (surface side), D17, P6,
   P7, P9, P10, P12 came from this pass, plus the colour, geometry and focus measurements.
2. **Daily operator (running app + behaviour probes).** Nine URL variants over the server-rendered
   page (`''`, `?state=active`, `?state=inactive`, `?q=SAHİBİ`, `?q=sahibi`, `?q=SAHIBI`,
   `?q=<email>`, `?q=İPEK`, `?state=bogus`), the 320 px and 1440 px measurements, the keyboard
   focus order, the computed colour/focus values, and the read-only DB cross-check of the roles
   and platform memberships. Findings D9, D10, D20, D21's measurement side, and the P-rows.
3. **API client with no UI (raw API + code).** Called the three GET endpoints with the panel
   token outside the browser (`/users` -> 200 with the constant envelope; `/users/roles` -> 200
   with one role; `/users/:id` -> 200 with the second shape), and read the routes, the service,
   the guards, the domain inputs, the Prisma schema, the notification fan-out and the sibling
   surfaces' conventions. Findings D2, D3, D5, D8's source values, D11, D12, D13, D14, D15, D16,
   D18, D19.

**Reading vs exercising.** Every finding above says which it is. The capability matrix's role
cells and the deliverability finding rest on reading plus one live confirmation each (the role
list came from both a live GET and the DB). The layer-coherence defects are readable in the
source, but the two that decide the feature's fate - D1 and D2 - were confirmed on the running
install, which is why the running-app half mattered here: from source alone the invite modal
looks like a working form.

**Screenshots read, not saved.** Two widths (320 and 1440 CSS px) and two colour schemes (light,
and `prefers-color-scheme: dark` with the shell theme left at SYSTEM). The image reads answered
what the tree could not: which element dominates the page (the full-width invite button,
`1126 px` wide), that no scroll affordance exists for the table, that the email cuts mid-address
at 320, and that the two "Aktif" cells are styled differently. The tree answered what the image
could not: roles, names, `aria-sort: null`, the caption/`scope` attributes, `novalidate`, and the
`role`/`aria-*` state.

**Pass rows are in the result** (P1-P12): eleven agreements between layers and one measured
convention match (the sidebar's `aria-current`, which my first tree read appeared to miss - the
search for it proved the attribute is there, and the absence claim was dropped).

**Every verdict names a standard or a cross-layer disagreement**: the APG patterns and WCAG 2.2
success criteria for matrix 5, and for the rest a disagreement between two named layers with both
sides cited. "The invite button is 1126 px wide" is not a finding here: it has no violated
guideline, so it appears only as the image read that supports the hierarchy question an operator
would ask.

**Nothing here is a UI opinion.** The deliverable is the matrices, the disagreements and the two
proposals.
