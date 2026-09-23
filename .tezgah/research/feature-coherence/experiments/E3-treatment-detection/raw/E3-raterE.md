# Feature audit — Ustam admin, `(dashboard)/users` (E3 rater E)

Artifact written by one rater; three passes over one frozen tree — Ustam
`98f985f`, clean working tree, last change to this feature's files at 22:01 today;
admin dev server on :3000, API on :3001. (The `97a7783` in this session's header
was the **tezgah** repo's graph index, not Ustam.) Every citation was re-verified
against `98f985f` after the pass. Nothing in the Ustam tree was modified; no server
was started or stopped; no database write was performed (the one mutation attempted
was refused before any API call — see F1).

## 1. Boundary (the feature)

**Entity:** a panel administrator — a `User` plus its `Membership` in the platform
organisation (the screen is labelled *Yöneticiler* / Administrators,
`lib/admin-surfaces.ts:99-104`).

**Actions a user can take:** list users, read the role catalogue, invite a user,
change a membership's role, change its scope, deactivate it, reactivate it, and
(on mobile) edit it.

**Screens:** `/users` (one route, no detail route, no wizard).

**Endpoints:** `GET /users`, `GET /users/roles`, `GET /users/{id}`,
`POST /users/invite`, `PATCH /users/{id}`, `POST /users/{id}/deactivate`.

**Files:** `apps/admin/app/(dashboard)/users/{page.tsx,actions.ts,user-labels.ts}`,
`apps/admin/components/{AdminModal,AdminActionForm,ConfirmationDialog,MutationNotice,PageHeader}.tsx`,
`apps/admin/lib/{api,mutations,mutation-guard,admin-context,admin-panel-session}.ts`,
`apps/api/src/users/{users.controller,users.service}.ts`,
`apps/api/src/auth/{admin-panel.guard,permissions.guard}.ts`,
`packages/domain/src/users.ts`, `apps/mobile/src/features/users/organization-users-api.ts`.

## 2. Passes run (3, from different entry points)

| # | Entry point | How it ran | What it produced |
|---|---|---|---|
| 1 | First-time user, browser at 1440×1000 | Managed Chromium, `localhost:3000/users`; opened the invite dialog, filled it, submitted, cancelled the confirmation, filtered, emptied the list, resized to 320, forced the dark token set | F1, F3, F5, F9(part), F12; the state coverage in §8 |
| 2 | Daily operator (keyboard + region + error recovery) | Same session: tab order enumeration, `aria-*` and target-size measurements, native-validation burst (empty submit), Escape from the stacked confirmation, focus-outline measurement, axe-core 4.10.3 sweeps (page / dialog / confirmation) | F5, F8, pass rows 4.1.3, 2.4.7, 2.5.8, 1.4.10 |
| 3 | API client with no UI | Read the controller, the service, the OpenAPI document and the mobile client's calls; live unauthenticated probes `GET /users`, `GET /users/roles`, `POST /users/{id}/deactivate` → all `401 AUTH_REQUIRED` | F2, F6, F7, F10, F11 |

Pass 3 was **not** exercised with a credential: the panel's bearer token is
server-owned (`lib/api.ts:104-112`) and no API token is available to this rater, so
pass 3 is a contract reading plus reachability probes, not an authenticated API run.

## 3. Coverage (rows checked / not checked)

| Matrix | Rows | Fully checked | Partially / not checked | What would change the conclusion |
|---|---|---|---|---|
| 1 capability | 10 | 9 | 1: the `POST /users/{id}/deactivate` row is code-only (no client calls it, so there is nothing to exercise) | an authenticated API client run would confirm the two dead endpoints' 204/403 shape |
| 2 field contract | 16 | 15 | 1: `GET /users/{id}`'s live JSON shape `[NOT CHECKED: no API credential]` | a token run confirming `membership.roles` returns objects there and strings in `list` (F7b) |
| 3 flow / step | 6 | 5 | 1: the stale-tab race on the row dialog is reasoned from code, not raced | a two-session race would confirm the error lands as a whole-form alert |
| 4 interaction dependency | 5 | 4 | 1: the two row-dialog rows could not be driven live — the running panel has exactly one user, a `SUPER_ADMIN` whose row deliberately renders no edit control (`page.tsx:205-207`) | a second, non-super-admin membership in the platform org would exercise the row dialog, scope default, and the self-deactivation branch |
| 5 surface pattern | 26 rules evaluated | 22 | 2 `[NOT CHECKED]`: axe in the dark scheme (no media emulation on the managed tab — the dark tokens were probed by attribute instead); the conditionally-revealed-question rule (no such control exists here) | none of the findings rest on those two cells |

The permission-denied surface (`page.tsx:48-56`) and the invitation-permission
absent branch (`page.tsx:130-134`) were **not** exercised: the only available
session holds `user.manage`, and both branches require the permission removed.
They are code-verified only and are marked as such in Matrix 1.

## 4. Matrix 1 — capability

| Action | Surface (what a person can do) | Route | Authorization | Service / validation | Persistence |
|---|---|---|---|---|---|
| List panel users | yes — table `page.tsx:167-284` | yes `GET /users` `controller.ts:34-36` | yes `@RequirePermissions('user.manage')`; surface gate `page.tsx:46-47` on the same key (`lib/mutations.ts` `team.invite/team.update → user.manage`) | yes — org-scoped `findMany`, `status != ARCHIVED`, `users.service.ts:27-33` | `User`, `Membership`, `MembershipRole` read |
| Read the role catalogue for the pickers | yes — both selects, `page.tsx:113-117, 247-254` | yes `GET /users/roles` `controller.ts:42-45` | yes + `@RequireAdminPanel()` | yes — roles of the caller's org only, `users.service.ts:69-75` | `Role` read |
| Invite a panel user | yes — dialog `page.tsx:74-128` | yes `POST /users/invite` (via the server action `actions.ts:62-69`) | yes `requireAdminMutation('team.invite')` + `@RequirePermissions` | **no for the only value the surface offers** — `SUPER_ADMIN` refused at `actions.ts:61` and at `users.service.ts:114,336-338` (**F1**) | would create `User` + `Membership` + `MembershipRole` + audit + outbox `UserInvited` (`users.service.ts:113-176`) — **delivery missing (F6)** |
| Change a membership's role | yes — row dialog `page.tsx:243-257` | yes `PATCH /users/{id}` | yes `requireAdminMutation('team.update')` | yes — replaces every role, refuses `SUPER_ADMIN`, refuses a missing role (`users.service.ts:226-236`) | `MembershipRole` delete+create, audit `user.update` |
| Change a membership's scope | yes — row dialog `page.tsx:258-267` | yes same PATCH | yes | yes `scope` enum `packages/domain/src/users.ts:37` | `Membership.scope` update |
| Deactivate a membership | yes — row dialog's *Üyelik durumu → Pasif* `page.tsx:268-276` (hidden for the caller's own row) | yes same PATCH with `active:false` | yes | yes — `SELF_DEACTIVATE` guard, then revokes sessions/push/devices `users.service.ts:180-183, 205-216, 275-318` | `Membership.active`, `RefreshSession`, `DevicePushToken`, `DeviceActivation`, audit `user.update` |
| Reactivate a membership | yes — dedicated button for an inactive row `page.tsx:208-224` | yes same PATCH, `operation=reactivate` → body `{active:true}` (`actions.ts:79-80`) | yes | yes — reactivation-only rule enforced server-side (`users.service.ts:200-206`); the surface avoids the mixed write by rendering a different control | `Membership.active`, audit |
| Deactivate via the dedicated endpoint | **no client calls it** — `POST /users/{id}/deactivate` exists (`controller.ts:82-93`) and nothing in `apps/admin` or `apps/mobile` posts to it (search `users/\${` over both trees: only `actions.ts:89` PATCH and `organization-users-api.ts:56` PATCH) (**F7a**) | yes | yes `user.manage` (probe: `401 AUTH_REQUIRED`) | yes `setActive(…, false)` `users.service.ts:246-273` | same revocations as the PATCH path |
| Read one user's detail | **no surface** — no detail route exists; `GET /users/{id}` is called by nobody (**F7a**) | yes `controller.ts:49-57` | yes `user.manage` (probe 401) | returns `membership.roles` as `{key,name}` objects, where `list` returns bare keys — one contract, two shapes (**F7b**) | read |
| Edit the global profile (name, locale) | **no surface by design** — the page states it in text `page.tsx:171-172`; the mobile self-service screen owns it | `PATCH /users/{id}` accepts the fields in the schema `packages/domain/src/users.ts:28-29` | — | **no** — the service 403s them (`GLOBAL_PROFILE_SELF_SERVICE_REQUIRED`, `users.service.ts:327-334`) (**F11**) | not written |

**Pass rows (layers agree).** The surface's per-row `SUPER_ADMIN` branch
(`page.tsx:205-207`) matches `assertGenericUserTarget` (`users.service.ts:340-344`)
and the pre-API refusal in `actions.ts:87-88`: three layers, one rule. The
self-deactivation rule is enforced twice with the same intent (surface hides the
option for the caller's own row, `page.tsx:272`; API `SELF_DEACTIVATE`,
`users.service.ts:181`). The reactivation-only rule is a third: surface control,
service guard. The permission is the same registry key on all five endpoints and on
the surface gate.

## 5. Matrix 2 — field contract

| Field | Column / type | Read by the API | Written by the API | Rendered | Validated | Label / enum source | Locale / format |
|---|---|---|---|---|---|---|---|
| `id` | uuid PK | yes | yes (invite) | hidden input per row | `z.uuid()` `actions.ts:77` | — | — |
| `displayName` | varchar(120) | yes | invite yes; update **403** | list column *Ad*; invite input `page.tsx:97` | `min 1 max 120` both sides | — | no localisation (proper noun) |
| `email` | citext-ish + `normalizedEmail` | yes | invite yes (`normalizeEmail`) | list column *E-posta*; invite input | `z.email()` both sides | — | printed raw |
| `status` | enum (`ACTIVE/INVITED/…`) | yes | only at create (`'ACTIVE'`) | column *Durum*, badge `page.tsx:187` | — | `userStatusLabels` (client map, 5 keys) | Turkish labels |
| `locale` | varchar(10) | yes (`list`, `get`) | never by this feature | **not rendered anywhere** — the client schema carries it (`page.tsx:18`) and drops it; the page explains why in text `page.tsx:171-172` | max 10 | — | `[agreement]` documented self-service |
| `membership.scope` | enum(4) | yes | invite + update | column *Kapsam*, select | `z.enum` both sides | `scopeLabels` client map | Turkish labels |
| `membership.active` | bool | yes | update/reactivate | column *Üyelik*, `Aktif/Pasif` `page.tsx:200` | — | plain ternary, not a map | — |
| `membership.roles` | join rows | yes — strings in `list`, objects in `get` | replaced wholesale on update | column *Roller*, joined | — | `roleLabels` client map **over** the server's `role.name` (**F9c**) | — |
| `page.nextCursor` / `page.hasNextPage` | API envelope | yes `users.service.ts:64` | hardcoded `null`/`false` | **not parsed, not rendered** — the client schema omits `page` (`page.tsx:13-31`) while sibling pages parse it (**F2**) | — | — | — |
| invite `roleKey` | enum(7) | yes | yes | select `page.tsx:105-118` | enum in the shared schema + `SUPER_ADMIN` refusal | `roleLabels[role.key] ?? role.name` | Turkish labels |
| invite `scope` | enum(4), default `organization` | yes | yes | select, default `assigned` `page.tsx:123` | enum | `scopeLabels` | default disagreement (**F10**) |
| invite `email` (2nd user) | same field, other subject | yes | creates the account | confirmation summary *E-posta* | `z.email()` | — | `ALREADY_MEMBER` mapped to a field error `actions.ts:30-36` |
| `active` | bool string in the form | yes | yes | select, own row excluded | `z.enum(['true','false'])` `actions.ts:83` | — | — |
| `operation` | hidden, `reactivate` | no (server action only) | — | hidden input `page.tsx:217` | exact-string branch | — | — |
| update `roleKey` | enum(7), optional | yes | yes | select with an explicit *keep current* option `page.tsx:249-251` | enum + refusal | same map | — |
| role key set | — | `/users/roles` returns the org's roles **only** | — | the surface offers them verbatim | refusal is server-side only (**F1**) | client map > server name (**F9c**) | — |

`[agreement]` row: `locale` is read, carried by the client schema and never shown,
with the reason printed on the page — documented intent and code agree.

## 6. Matrix 3 — flow and step contract

The invite is a two-step flow (form → confirmation) inside one native dialog; the
row dialog reuses it.

| Step | Precondition | What it validates | What it writes | How a skip is prevented | Resume / persistence | Back-navigation retention | Where an error lands |
|---|---|---|---|---|---|---|---|
| Open (trigger) | `canInvite` (`user.manage`) | — | — | the trigger is not rendered without the permission `page.tsx:74` | no persistence | closing keeps nothing (nothing entered) | — |
| Form (invite) | dialog open; `displayName`,`email` required | native `required`/`type=email` on submit (`AdminActionForm` listens to the `invalid` burst), then `InviteUserInput` server-side | nothing until submit | submit with JS disabled does nothing (`action` is React's `javascript:throw` marker) | **none** — a reload loses all four values; the dialog is not in the URL (no `id` on this modal, **F8b**) | not applicable | whole-form `role=alert` inside the dialog, focus moved to it, values kept (observed) |
| Confirm | confirmation state after a valid submit | nothing new; builds a summary from the live controls | nothing | Escape (observed) and *Vazgeç* both return to the form | **none** — a reload loses the confirmation | observed: Escape/cancel kept both typed values (*Probe Ad*, *probe@example.test*) | confirmation errors cannot land here; the confirmation is never posted |
| Submit (confirm → action) | all above | `InviteUserInput` + `SUPER_ADMIN` refusal `actions.ts:55-61` | `User`+`Membership`+`MembershipRole`+audit+outbox | — | — | — | API failures land as the whole-form alert; `ALREADY_MEMBER`/`ROLE_NOT_FOUND` map to field errors, the `SUPER_ADMIN` refusal does not (**F1b**) |
| Row dialog (open) | `canUpdate` and a non-super-admin, active membership row | — | — | the surface substitutes a paragraph for a super-admin row and a button for an inactive one `page.tsx:204-242` | deep-linkable by hash `#user-access-<id>` → `AdminModal` `id` | — | — |
| Row dialog (submit) | role/scope/active chosen | `UserUpdateInput`, uuid id | PATCH | mixed writes on an inactive membership are refused by the API; the surface never offers that combination | none | not exercised live (`[NOT CHECKED: only a SUPER_ADMIN user exists]`) | whole-form alert; a stale-tab refusal (`INACTIVE_MEMBERSHIP_REACTIVATION_ONLY`) names no control |

One question per surface step: the invite groups all four fields under one heading
and one dialog — the GOV.UK *one thing per page* rule is not satisfied literally,
but the dialog is a single task with a single submit; recorded as **not a
violation** with the context named (a dialog is not a page).

## 7. Matrix 4 — interaction dependency

| Trigger | Dependents | Required action on change | Who owns the state | What is announced |
|---|---|---|---|---|
| `state` filter select (*Üyelik durumu*) | the row set and the count line | recompute | URL (`?state=`), server-rendered `page.tsx:61-66` | a full navigation; the new count line is in the rendered document (observed) |
| `q` search input | the row set and the count line | recompute | URL (`?q=`) | same |
| *Filtreleri temizle* | both filter controls | reset | the link's href `/users` (observed: `state` back to *Tümü*, `q` empty) | the navigation |
| invite `roleKey` select | nothing — and that is the defect | the surface should expose only assignable roles; the server refuses one it still offers (**F1**) | server (`/users/roles`), but the surface does not filter | the refusal only after submit, as a whole-form alert |
| row dialog `active` select (*Pasif*) | `roleKey`, `scope` (the API refuses a mixed write on an inactive membership) | in the fresh case: keep — the API accepts scope+active together (`users.service.ts:207-224`); in the stale case: revalidate | server rule, surface unaware | nothing — the stale refusal is a whole-form alert that names no field (**F1b**, same family) |
| row dialog `active` select (own row) | its own option list | recompute | the surface, from `context.id` `page.tsx:272` | nothing announced (an option that is simply absent) — recorded, no rule violated: the API `SELF_DEACTIVATE` guard agrees |

## 8. Matrix 5 — surface pattern (controls, data views, flows, notifications)

Sources: WAI-ARIA APG patterns, WCAG 2.2 Understanding, GOV.UK Design System
(read 2026-09-20). Level claimed for the hand-checks: **WCAG 2.2 AA**; axe-core
covers ≈57% of it and has no rule for 1.4.10, 2.4.7, 3.3.1, 3.3.3, 4.1.3, so those
are hand-checked below.

### Data views (the table)

| Rule | Verdict |
|---|---|
| Real headers + a labelled table (SC 1.3.1) | **pass** — `<caption class="srOnly">Kullanıcı listesi</caption>` `page.tsx:169`, `<th scope="col">` ×6/7 `page.tsx:172-178` |
| `aria-sort` on the sorted column | **violation, severity 1** — the API sorts by `displayName` (`users.service.ts:55-56`) with no `aria-sort` cell and no sort control (**F9a**) |
| Editable cells → grid | **n/a** — the only widget is a per-row dialog trigger; a button in a table cell is not an editable cell |
| `aria-rowcount` / virtualisation / position restore | **n/a** (no virtualisation) — but see F2: the list is unbounded |
| Pagination marks the current page; a one-page pager is hidden | **violation, severity 3** — there is no pager at all and no page size; the envelope is hardcoded (**F2**) |
| SC 1.4.10: single-direction page scroll at 320 px, table inside its own scroll container | **pass** — at 320 px `documentElement.scrollWidth == 320`, the 1140 px table sits in a 242 px `overflow-x:auto` region (`page.tsx:167`, measured live) |
| First column a human-readable identifier; headers survive scrolling | identifier **pass** (*Platform Sahibi*); sticky header **violation, severity 1** — `position: static` (measured) (**F9b**) |
| Filters discoverable, active state visible, a clear that really clears | **pass** — labelled toolbar `page.tsx:145`, the selects keep the submitted value, the clear link resets both (observed) |
| Empty state | **violation, severity 1** — the message renders after an empty `<table>` inside the labelled scroll region and names an action with no affordance (**F8a**) |
| A scroll region says it scrolls | **violation, severity 3** — the last column is clipped mid-word at both 1440 (1084 px container) and 320 (242 px container) with no visible scrollbar or fade (**F3**) |

### Controls

| Rule | Verdict |
|---|---|
| APG combobox / listbox / tabs / disclosure | **n/a** — every picker is a native `<select>`, every toggle a `<button>` with text; no custom widget exists |
| Visible persistent label; never a placeholder as label | **pass** — all labels are wrapping `<label><span>` (observed); no placeholder attribute on this page |
| Required/optional convention stated once (GOV.UK) | **violation, severity 1** — the invite's two required fields carry no marker and no optional marker exists anywhere on the page (observed `pageRequiredMarkers: []`); `components/FormField.tsx:26` implements an asterisk convention that no page imports (**F9d**) |
| SC 1.3.5 scoped: `autocomplete` tokens | **pass (n/a)** — the form collects another person's details and a search string, not the operator's own data; no token is required |
| APG dialog: initial focus, focus containment, focus return, least destructive default | **pass, exercised** — native `<dialog>.showModal()`; a real Escape closed the modal and returned focus to its trigger (`activeElement ===` the trigger button); the confirmation focuses *Vazgeç* (observed) and its own Escape handler closes only itself, leaving the guarded form open with both typed values; Tab is wrapped in both. Observation, not a violation: the modal's initial focus lands on the close button (the first focusable element) rather than the first field |
| SC 2.5.8 target size ≥24×24 | **pass** — measured 36×36 (close), 44 px (select, buttons), 67 px (filter button) |
| SC 2.4.7 focus visible | **pass, hand-checked** — focused summary element computed `outline: rgb(20,95,192) solid 3px` in light; the dark screenshot shows the same ring (`--focus-ring: #6fb3f0` from `globals.css:86-96`) |
| SC 1.4.3 contrast, no colour-only state | **pass, hand-checked** — axe's 19 `color-contrast` *incomplete* nodes were resolved by hand: body/muted 5.47–5.83:1, error link 5.23:1, table cells 16.63:1 (light); dark probes 7.6–14.6:1. `badgeWarn` is a colour **plus** a text label |

### Validation and errors

| Rule | Verdict |
|---|---|
| Validation on submit, values kept, server-side validation present | **pass** — native validation fires on submit (`AdminActionForm`'s `invalid` burst), the server re-validates with the shared schema, values were retained after the F1 refusal (observed) |
| SC 3.3.1/3.3.3 the item is identified and the correction described | **violation, severity 2, hand-checked** — two empty required fields produced two identical summary entries *Bu alanı doldurun.*, naming neither field (**F5**) |
| Association: `aria-describedby` → the message; summary entry focuses its field | **pass** — `AdminActionForm.tsx:118-155` wires `aria-invalid`/`aria-describedby` per field and each summary entry is a button that focuses its control |
| An error summary at the top of the form | **pass** — the summary is the first element of the dialog's feedback block, focused on appearance |
| SC 3.3.4 confirmation of a destructive/commitment change, naming what is at stake | **pass** — the confirmation names the person and the consequence (*"rol seçilirse mevcut rollerin tamamının yerini alır. Pasife alma bu işletmedeki oturumları ve cihaz erişimini kaldırır."*) and the actions stay inside the panel |

### Flows

| Rule | Verdict |
|---|---|
| Unique heading per step; back link | **pass** — dialog heading, description and confirmation heading differ |
| Check-your-answers pre-populated on return, a Change path, a submit that names its action | **partial** — the summary is built from the live controls and the confirm button names its action (*Daveti oluştur*); there is no *Change* link per section, only *Vazgeç* back to the intact form (acceptable for a two-step dialog) |
| SC 3.3.7 redundant entry | **pass** — no value is asked twice |
| Notification banner before the h1, at most one, never standing in for errors | **deviation, severity 1** — `role="status"` with a complete sentence and no duplication, but it renders after the h1 (`page.tsx:73`, measured `beforeH1:false`) (**F12**) |

### Notifications

| Rule | Verdict |
|---|---|
| SC 4.1.3 result count / "saved" determinable | **pass with a note** — the count line is plain text, but filters navigate, so the new value is part of the loaded document; form feedback uses `role=status`/`role=alert` and receives focus |
| The whole status string is the announced unit; the end of a wait is announced | **pass** — the pending label *İşlem kaydediliyor…* is a `role=status` paragraph; success closes the dialog and the redirect lands on a `role=status` banner |
| Non-status changes stay out of live regions | **pass** — validation inside the dialog is not a live region; the disclosure-free surface has none |

### States that exist vs states that do not

| Surface | default | hover/focus | disabled | loading | empty | error | permission-denied | partial/long text |
|---|---|---|---|---|---|---|---|---|
| `/users` page | ✓ | ✓ (`:hover`,`:focus-visible`) | n/a | ✓ `(dashboard)/loading.tsx` (`aria-busy`, `role=status`) | ✓ | ✓ `(dashboard)/error.tsx` | ✓ code-only (`page.tsx:48-56`) `[NOT CHECKED live]` | ✓ clipped column (F3) |
| Users table | ✓ | n/a | n/a | ✓ skeleton | ✓ (F8a) | ✓ | ✓ column omitted | ✗ no long-text strategy (**F9e**) |
| Invite dialog | ✓ | ✓ | ✓ the fieldset disables every control while pending (`AdminActionForm.tsx:228-233`) | ✓ | n/a | ✓ | n/a | n/a (no length limit to exceed) |
| Row dialog | ✓ (not exercised live) | ✓ | ✗ no disabled state for a pending row mutation | ✓ | n/a | ✓ | ✓ substituted paragraph | n/a |

## 9. Findings (most severe first)

Severity is the 0–4 scale (frequency × impact × persistence). Every finding names
one evidence class and one Prevent line; `ui-observed` means the rendered screen or
a measurement in the running app, `behaviour` a response to an action I performed,
`code` a cited path.

**F1 — the invite control can only fail (severity 3, `behaviour`)**
`GET /users/roles` returns the platform organisation's role set; in the running
environment that set is exactly one role, `SUPER_ADMIN` (observed: the invite
select's only option is `SUPER_ADMIN=Platform sahibi`, and it is the default,
`page.tsx:107-111` falls back to `roles[0].key`). The server action refuses that
value at `actions.ts:61` before any API call and the API refuses it too
(`users.service.ts:114,336-338`), so the single reachable outcome of the invite
flow is the alert *Platform sahibi bu ekrandan atanamaz.* (observed). The mobile
client does not have this defect because it excludes `SUPER_ADMIN` from the offered
set (`OrganizationUsersScreen.tsx:28-35`, `organization-users-api.ts:34`).
*Citation:* live tab (roleOptions), `apps/admin/app/(dashboard)/users/actions.ts:61`,
`apps/api/src/users/users.service.ts:336-338`, `apps/mobile/src/features/users/OrganizationUsersScreen.tsx:28-35`.
*Sub-finding F1b:* the refusal is a whole-form alert that marks no control
(`aria-invalid` stayed absent, observed), though `roleKey` is the offending field.
*Prevent:* `page.test.tsx:158` already asserts the offered options equal the
returned roles, so it stays green while the set is refuse-only; add the missing
assertion — the assignable subset of the offered roles is non-empty — and make the
invite action map its `SUPER_ADMIN` refusal to `fieldErrors.roleKey`.

**F2 — the pagination envelope exists in the contract and nowhere else (severity 3, `code`)**
`users.service.ts:26-64` reads every matching row with no `take`/`cursor` and
returns a hardcoded `page: { nextCursor: null, hasNextPage: false }`; the panel's
client schema omits `page` entirely (`page.tsx:13-31`) and renders no pager, so
every user of the platform organisation renders in one table. Every sibling list
page parses and consumes the envelope (`work-orders/page.tsx:40,404-409`,
`quotes/page.tsx:38,430-433`, `customers/page.tsx:34,402-403`), and the API has a
cursor helper in use elsewhere (`work-orders/list-cursor.ts`).
*Citation:* `apps/api/src/users/users.service.ts:26-64`,
`apps/admin/app/(dashboard)/users/page.tsx:13-31`,
`apps/admin/app/(dashboard)/work-orders/page.tsx:40,404`.
*Prevent:* an API service test that seeds `limit + 1` memberships and asserts a
non-null `nextCursor`; it fails today because the envelope is a literal.

**F3 — the table is wider than its container at every width I measured, with the
last column clipped and no visual affordance (severity 3, `ui-observed`)**
Measured: at 1440 × 1000 the table is 1140 px inside a 1084 px `overflow-x:auto`
region (56 px of clipping; the *Yetki güncelle* cell is cut mid-word in the
screenshot); at 320 px the same 1140 px table sits in a 242 px region, and the
screenshot shows the e-mail column cut mid-word with no scrollbar, fade or hint.
The region is a labelled, focusable scroll region (`page.tsx:167`), so keyboard and
screen-reader users can reach the hidden columns; a pointer user with overlay
scrollbars has no signal that content exists.
*Citation:* live measurements at 1440 (table 1140 / wrap client 1084) and 320
(table 1140 / wrap client 242); screenshots `E3RaterE-1440.webp`, `E3RaterE-320.webp`.
*Prevent:* an e2e assertion comparing the last cell's right edge with the wrapper's
client width **and** requiring a scroll affordance — note that a document-overflow
check passes here (`documentElement.scrollWidth == 1440`) while the column is
clipped, which is the failure mode this rule is written against.

**F4 — one row prints two different fields with the same word (severity 2, `code`)**
Column *Durum* prints `user.status` (`page.tsx:186-189`) and column *Üyelik* prints
`membership.active` (`page.tsx:200`). Deactivation only ever writes the membership
(`users.service.ts:205-216`, `246-273`) — `User.status` is set once, to `ACTIVE`,
at invite (`users.service.ts:120-127`) — so a deactivated member's row reads
*Aktif | Pasif*, and nothing in this panel can change `status`, which also drives
the `badgeWarn` branch. The live row shows both columns as *Aktif*, so the mismatch
itself was not exercised.
*Citation:* `apps/admin/app/(dashboard)/users/page.tsx:186-189,200`;
`apps/api/src/users/users.service.ts:120-127,205-216,246-273`.
*Prevent:* a page test asserting the two columns never render the same word for a
`membership.active === false` row (which today fails), or drop the column the
surface cannot influence.

**F5 — the error summary identifies neither field (severity 2, `ui-observed`, hand-checked SC 3.3.1/3.3.3)**
Submitting the invite form with both required fields empty produced a summary with
two identical entries, *Bu alanı doldurun.*, one per field, with no field name in
the text (observed and visible in the dark screenshot). The field is a button that
focuses the right control, so the association is recoverable by trial, but the
message does not identify the item in error or describe the correction. axe-core
has no rule for 3.3.1/3.3.3, hence the hand-check.
*Citation:* `apps/admin/components/AdminActionForm.tsx:60-72` (`nativeFieldMessage`
returns one message per validity type, with no label) and `:118-155`.
*Prevent:* prefix each entry with the control's label in `nativeFieldMessage`'s
caller, and assert in `AdminActionForm.test.tsx` that two invalid fields yield two
distinct messages.

**F6 — the invitation ends with no delivery to the invited person (severity 2, `code`)**
`invite` creates the account with `status: 'ACTIVE'` and a hash of
`randomInvitePassword()` that is returned to nobody (`users.service.ts:113-127,
323-325`); it emits `UserInvited` with `{ membershipId }` (`:168-173`), whose only
delivery path is the push handler, which addresses the event to the invited user's
own devices (`push-notification.handler.ts:74,135`) — devices a brand-new account
has never registered. There is no invite e-mail: the only mail provider in the tree
is `PasswordResetEmailProvider`, used by the self-service reset flow and gated on
`PASSWORD_RESET_EMAIL_PROVIDER === 'resend'` (`password-reset-email.provider.ts:9-11`),
and nothing in `users/` calls it (search: no reference). The action therefore
succeeds in the database and fails the person.
*Citation:* `apps/api/src/users/users.service.ts:113-127,168-173,323-325`;
`apps/api/src/worker/push-notification.handler.ts:74,135`;
`apps/api/src/auth/password-reset-email.provider.ts:9-11`.
The email gate's value in this environment is `[NOT CHECKED: no API credential, and
probing the reset endpoint would write a challenge row]`.
*Prevent:* an outbox/delivery contract test asserting every invite carries a
delivery to a recipient with zero registered devices (i.e. an e-mail or a
documented exception); it fails on today's payload. This is also proposal **P2**.

**F7 — two endpoints exist that no surface calls (severity 1, `code`)**
(a) `GET /users/{id}` (`controller.ts:49-57`) and `POST /users/{id}/deactivate`
(`controller.ts:82-93`) have no caller: searching `users/\${` across `apps/admin`
and `apps/mobile` returns only the PATCH call sites (`actions.ts:89`,
`organization-users-api.ts:56`), and the generated client's entries
(`packages/api-client/src/generated/schema.ts:2729,2761`) are unused. Both are
reachable and guarded (live probe: `401 AUTH_REQUIRED` on both).
(b) `get` returns `membership.roles` as `{ key, name }` objects while `list` returns
bare keys for the same field (`users.service.ts:89-96` vs `:56-60`) — one contract,
two shapes, and the client schema parses only the array form (`page.tsx:21-27`), so
the detail endpoint's shape would be rejected by the panel's own parser.
*Citation:* `apps/api/src/users/users.controller.ts:49-57,82-93`;
`apps/api/src/users/users.service.ts:56-60,89-96`;
search `grep -rn "users/\${" apps/admin apps/mobile`.
*Prevent:* if the endpoints stay, add a shared response schema test that both
shapes satisfy (a contract test would fail on 7b today); if they go, an
unreferenced-endpoint allowance list in the OpenAPI snapshot test keeps them from
returning unnoticed.

**F8 — the empty state instructs an action it does not offer, and the invite dialog
cannot be deep-linked (severity 1, `ui-observed`)**
(a) With a filter that matches nothing, the table renders headers with no rows and
the message *"Eşleşen kullanıcı yok. Filtreleri temizleyin veya yeni takım üyesi
davet edin."* appears inside the labelled scroll region, after the empty table
(`page.tsx:286-291`, observed); it mentions inviting but carries no control.
(b) The invite modal passes no `id` (`page.tsx:75-79`) although `AdminModal`
supports hash deep-linking and the row dialogs in the same file use it
(`page.tsx:219`), so no link can open the invite dialog — which is also why (a)
cannot link to it.
*Citation:* `apps/admin/app/(dashboard)/users/page.tsx:75-79,219,286-291`;
`apps/admin/components/AdminModal.tsx:70-95`.
*Prevent:* a page test asserting the empty surface contains a control that opens
the invite dialog (it fails today: only text is rendered).

**F9 — data-view detail rules (severity 1 each, `ui-observed` unless noted)**
(a) No `aria-sort` on the server-sorted *Ad* column and no sort control (measured
`th[aria-sort]` absent; sort is `orderBy: { displayName: 'asc' }`,
`users.service.ts:55-56`).
(b) The header row is not sticky (`position: static`, measured) while the table is
unbounded (F2), so the header scrolls away in a long list.
(c) Role labels come from the client map first and the server's `role.name` second
(`page.tsx:115,192`; `user-labels.ts:1-9`) — two sources for one enum.
(d) The product's own required-marker convention
(`components/FormField.tsx:26`, an asterisk) is imported by no page, and the users
form marks nothing, so *required* is visible only through the browser's own
refusal.
(e) No long-text strategy: `1.4.10`-adjacent clipping aside, a 120-character name
has no truncation or wrap rule of its own, and the columns are fixed-width.
*Citation:* as quoted per item; measurements from the 1440 pass.
*Prevent:* (a) an assertion that the sorted header carries `aria-sort`;
(b) `th { position: sticky }` in `globals.css` is mechanical and testable by
measurement; (c) delete the client map and render the server's `name`;
(d) make every admin label go through `FormField`; (e) a `max-width` + truncation
rule with a title or tooltip.

**F10 — two defaults for one field (severity 1, `code`)**
`InviteUserInput.scope` defaults to `organization` (`packages/domain/src/users.ts:23`)
while both surfaces default the select to `assigned` (`page.tsx:123`,
`OrganizationUsersScreen.tsx:55`), and both always submit a value — so the
contract's default is unreachable and states a different intent than the product.
*Citation:* `packages/domain/src/users.ts:23`,
`apps/admin/app/(dashboard)/users/page.tsx:123`.
*Prevent:* make the schema default `assigned` (one line) or drop it, and let the
contract test pin the pair.

**F11 — the update contract advertises fields its own write path forbids (severity 1, `code`)**
`UserUpdateInput` carries `displayName` and `locale` (`packages/domain/src/users.ts:28-29`)
and the service answers `403 GLOBAL_PROFILE_SELF_SERVICE_REQUIRED`
(`users.service.ts:327-334`). Both clients happen to avoid them
(`actions.ts:78-85` sends neither; mobile's `updateOrganizationUser` type omits
them), so this is a latent contract/validator disagreement rather than a live bug —
and it is the shape the repo's own lessons ledger warns about.
*Citation:* `packages/domain/src/users.ts:27-44`,
`apps/api/src/users/users.service.ts:327-334`.
*Prevent:* remove the two fields from the shared update schema; the API contract
test then fails if any client sends them.

**F12 — the status banner renders after the h1 (severity 1, `ui-observed`)**
`MutationNotice` is rendered after `PageHeader` (`page.tsx:69-73`); measured, the
banner follows the h1. It is `role="status"`, a single instance, with a complete
sentence (*Takım daveti oluşturuldu.*), so nothing else in the GOV.UK notification
rule is violated — the deviation is position only.
*Citation:* `apps/admin/app/(dashboard)/users/page.tsx:69-73`, live measurement
(`beforeH1: false`, `role=status`).
*Prevent:* no mechanical prevention worth its cost; keep as a review item (moving
it above the header is the only fix and needs no test).

## 10. Capability-change proposals

Two findings need a layer that does not exist; the rest are fixes that name layers
already in the tree (the role-filter fix can copy the mobile client's exclusion; the
pagination fix can reuse `list-cursor`; the delivery fix in **F6** is different —
it needs a capability, hence P2). Each proposal carries a rejectable artifact.

### P1 — the role catalogue must say which roles the caller may assign

| Heading | Content | Falsified by |
|---|---|---|
| Capability | The panel can ask the server which roles the current caller may assign, instead of offering every role the organisation defines and learning by refusal | a cited code path that already returns assignability |
| Absence proof | `users.service.ts:69-75` selects `{ key, name }` only; `controller.ts:42-45` returns it verbatim; the panel refuses `SUPER_ADMIN` in two hardcoded places (`actions.ts:61,87`) plus the API's own 403 — the input that fails is the invite select's only value in this environment (F1) | a path returning `assignable` |
| Contract delta | `docs/openapi.json` `GET /api/v1/users/roles` → item gains `assignable: boolean`; `packages/domain` gains a shared `RoleOption` schema; response schema test `apps/api/src/users/users.service.test.ts` extended. `buf breaking`/contract-test analogue: `scripts/api-contract-verifier.mjs` (additive change, expected green) | a compatibility run that is green with no diff |
| Migration | additive only: expand (add the field) → migrate (no backfill; computed per request) → contract (remove nothing before 2026-12-31) | a contract phase with no date |
| Rollout | flag `admin.role-assignability` (boolean, expected lifetime 2 weeks, initial exposure: platform panel only), kill-switch owner: platform owner; abort threshold: invite refusals do not reach zero within 7 days of full exposure | an unmeasurable threshold or a flag with no lifetime |
| Verification | `apps/admin/app/(dashboard)/users/page.test.tsx`: offered options contain no `assignable === false` entry, and the invite submit is reachable; fails on the pre-change commit (the only option is `SUPER_ADMIN`) | a check that passes pre-change |
| Reversibility | reads only; restore = revert the deploy, no data written | data written with no restore step |
| Decision | ADR, status *Proposed*: context (F1), decision (server-declared assignability), consequences (the mobile client's hardcoded exclusion is superseded) | an ADR without a status |
| Appetite | 1 week; out of bounds: the role model, permission names, the mobile screen; when the box ends the change is reverted to the client-side filter as a stop-gap | no box, or an implicit extension |

### P2 — an invitation must reach a person who has no device and no password

| Heading | Content | Falsified by |
|---|---|---|
| Capability | An invite delivers a credential-bearing message to the invited address | a cited path that already does |
| Absence proof | `users.service.ts:116,323-325` hashes a random password that is returned to nobody; `:168-173` emits `UserInvited` with `{membershipId}` only; `push-notification.handler.ts:74,135` routes it to the invitee's own devices; no provider call exists in `users/` | a path sending an invite credential to an address |
| Contract delta | `POST /api/v1/users/invite` response gains `delivery: 'EMAIL' \| 'PUSH' \| 'NONE'` (and the challenge reuse is stated in the OpenAPI description); permission rule unchanged (`user.manage`) | a compatibility run green with no diff |
| Migration | expand (response field, deployed tolerantly) → migrate (existing pending invites get a resend route) → contract (the field becomes required) before 2026-12-31; no schema migration if the reset-challenge table is reused (`password-reset.service.ts:35-104`) | a contract phase with no date |
| Rollout | flag `admin.invite-delivery` (enum `email\|none`, expected lifetime 4 weeks), exposure: platform panel first, then tenant panels; kill-switch owner: platform owner; abort threshold: invite→first-login within 7 days does not improve over the measured baseline (baseline itself `[NOT CHECKED: unobservable today — no delivery is recorded, which is the first finding of the class]`) | an unmeasurable threshold, or a flag with no lifetime |
| Verification | an integration test beside `apps/api/src/integration/team-api-lifecycle.test.ts` asserting the invite path calls the mail provider with the invited address or records `delivery: 'NONE'`; fails pre-change | a check that passes pre-change |
| Reversibility | writes one password-reset challenge row (and, if configured, one outbound mail, which cannot be recalled); restore = mark the challenge consumed and delete it by id; the e-mail is a **one-way door** → requires owner approval before first production send | data written with no restore step and no label |
| Decision | ADR, status *Proposed*, superseding the "invite = push only" assumption in `notification-event-mapper.ts:226-230` | an ADR without a status |
| Appetite | 1 week; out of bounds: the reset flow's own UX, the push pipeline; when the box ends, deliver a manual-credential path in the panel and keep the invitation transactional | no box, or an implicit extension |

Reviewer's five absences, self-checked: both proposals cite a `code` finding behind
them (F1, F6); both carry a rejectable artifact (an OpenAPI/permission diff plus a
contract test, and a response-schema field); neither schema-touching step lacks
migration phases (P2 reuses the challenge table); both flags carry a lifetime and an
owner; both carry an ADR with a status and a pre/post check pair.

## 11. Automated sweeps and hand-checks

- **axe-core 4.10.3**, chromedriver-supplied build from this scratch directory,
  run on the settled page at 1440: **0 violations** with the modal closed, **0** with
  the invite dialog open, **0** with the stacked confirmation open. `color-contrast`
  was reported *incomplete* for 19 nodes (page) and 1 node (dialog) because of the
  gradient backgrounds; resolved by hand in §8 (light 5.23–16.63:1, dark 7.6–14.6:1).
  Not run in the dark scheme — `[NOT CHECKED: the managed tab exposes no
  `prefers-color-scheme` emulation]`; the dark token set was instead applied by
  setting `data-theme="dark"` on `.shell` (the same switch `globals.css:86-96`
  reads) and the page re-measured and screenshotted.
- **Screenshots read (not merely saved):** `E3RaterE-1440.webp` (light, full page),
  `E3RaterE-320.webp` (light, 320 px), `E3RaterE-dark-1440.webp` (dark tokens, invite
  dialog with the empty-field error summary). The tree could not answer: the visual
  clipping of the last column at 1440, the absence of any scroll affordance, the
  summary's two identical messages, and the focus ring's visibility.
- **Hand-checks from the eight that no rule covers:** 3.3.1/3.3.3 → F5; the
  destructive-confirmation wording → pass (it names person and consequence); 4.1.3
  → pass with the navigation note; 2.4.7 → pass (3 px ring measured in light,
  visible in the dark screenshot); 1.4.10 → pass, measured at 320 px; `autocomplete`
  semantics → n/a; `aria-modal` preconditions → pass (native `showModal`, no manual
  `aria-modal`, background inert); a revealed question's announcement → n/a.
- **What the automated half could not see at all:** F1 (a role set that is
  refuse-only), F2 (an envelope nobody computes), F4 (two columns, one word),
  F6 (a missing delivery), F7 (two dead endpoints).

## 12. What could not be produced

- **A live run of the row dialog states** (role replacement, scope change,
  deactivation, reactivation): the running platform organisation has exactly one
  user and it is a `SUPER_ADMIN`, whose row deliberately renders a paragraph
  instead of a control (`page.tsx:205-207`). Exercising them needs a second,
  non-super-admin membership, which would mean writing to the shared database — out
  of bounds for this pass. The row-dialog rows are therefore `code`-verified and
  marked in matrices 3 and 4.
- **An authenticated API-client pass.** No API token is reachable from this
  session (the panel's bearer is resolved server-side, `lib/api.ts:104-112`); the
  live probes are unauthenticated (`401 AUTH_REQUIRED`), so the API half of
  pass 3 is a contract reading.
- **The permission-denied branches** of the page and of the invite panel: the only
  session holds `user.manage`. Code-verified, `[NOT CHECKED live]`.
- **The measured invite→first-login baseline** that P2's abort threshold wants:
  the system records no delivery and no login correlation for invitations, which is
  itself the first finding of that class (F6).
- **axe in the dark scheme** and the **`prefers-color-scheme` path** of the theme
  resolution (only the explicit `data-theme` switch was exercised).
