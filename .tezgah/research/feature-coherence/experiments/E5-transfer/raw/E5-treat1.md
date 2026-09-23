# feature-audit — Admin Users area (aibim-app), treatment arm

Skill applied: `skills/feature-audit/SKILL.md` (read in full, 324 lines, this session).
Repo audited at source only: `/Users/rizax/Projects/aibim-app` (HEAD `452c533`; the
code-graph index is at `74659fa`, i.e. behind — **every citation below is a text/file
citation, none is a graph answer**).

## The unit

Entity: **a panel user** (`users` row). Actions a person can take on it: list, search,
read detail, create (provision), change role, deactivate, activate, edit profile, read
module permissions, write module permissions, list a tenant's users.
Screens: `admin/frontend/src/pages/Users.tsx` (the Users page) and the `UsersTab` of
`admin/frontend/src/pages/TenantDetail.tsx` (same entity, same endpoints).
Endpoints: the 9 user routes in `admin/backend/src/main.rs:251-290, 338-341`.
Files: `main.rs`, `middleware.rs`, `handlers/admin.rs`, `handlers/admin_dto.rs`,
`db.rs`, `frontend/src/api/admin.ts`, `frontend/src/types/admin.ts`,
`frontend/src/pages/Users.tsx`, `components/ui/{DataTable,DetailPanel,Modal,FormElements,AdminPrimitives,TenantSearchSelect,StatusBadge}.tsx`,
`db/migrations/016_user_permissions.sql`.

**Evidence classes available in this arm: `code` only.** No Docker, no build, no
credential and no running instance (arm constraint), so there is no `ui-observed`,
`behaviour` or `user-verbatim` finding here; every UI-shaped claim below is a
source-derived claim carrying a `path:line`, not an observation of the rendered
surface. `external` appears only as the named standard in the rule column.

Passes: **1 rater, 3 passes**, all source-reading, from three entry points —
(1) first-time admin provisioning their first user, (2) the daily operator on the
list/search/tenant detail, (3) an API client with no UI (routes → handlers → SQL →
client). No fourth (running-app) pass exists in this arm.

---

## Matrix 1 — capability

| Action | Surface (what a person can do) | Route | Authorization | Service / validation | Persistence |
|---|---|---|---|---|---|
| List all users (paginated, with tenant name) | yes — table, `Users.tsx:109-128` | yes — `GET /api/v1/admin/users`, `main.rs:264-267` | yes — `require_admin_access` (platform admin only), `main.rs:441-444`, `middleware.rs:59-72` | yes — limit clamped 1..=500, offset ≥0, search trimmed, `admin.rs:4397-4412` | yes — `users::LIST_FILTERED` + `COUNT_FILTERED`, `db.rs:482-501` |
| Search users by name/email/role/id/tenant | yes — `SearchInput`, `Users.tsx:107`, 250 ms debounce `Users.tsx:39-42` | yes — `?search=`, same route | yes — same gate | yes — `ILIKE` on 5 expressions, `db.rs:486-491` | yes — same SQL |
| Read one user's detail | **no** — the panel is fed from the list row, `Users.tsx:87-92, 131-135` | yes — `GET /users/{user_id}`, `main.rs:287-290` | yes — same gate | yes — `admin_get_user`, `admin.rs:4468-4502` | yes — `users::GET_BY_ID`, `db.rs:503-506` |
| Change a user's role | yes — role buttons `Users.tsx:179-206`; also a `<select>` in `TenantDetail.tsx:372-378` | yes — `PUT /users/{user_id}/role`, `main.rs:255-258` | **partial** — actor-role predicate only, and it offers `super_admin` which the same predicate refuses (see F3/F4) | yes — typed body + length validation `admin.rs:795-799`, `admin_dto.rs:129-160` | yes — `users::UPDATE_ROLE`, `db.rs:512-513`; audited `admin.rs:806-816` |
| Deactivate a user | yes — one click, no confirmation `Users.tsx:207-217` | yes — `POST /users/{user_id}/deactivate`, `main.rs:259-262` | **no** — no target-role/self predicate (F4) | yes — `admin.rs:834-865` | yes — `users::DEACTIVATE`, `db.rs:515-516`; audited `admin.rs:852-862` |
| Activate a user (approve) | yes — same toggle, `Users.tsx:207-217` | yes — `POST /users/{user_id}/activate`, `main.rs:268-271` | same as deactivate | yes — `admin.rs:988-1015` | yes — `users::ACTIVATE`, `db.rs:518-519`; audited |
| Edit profile (name, email) | yes — edit mode, `Users.tsx:239-247` | yes — `PUT /users/{user_id}`, `main.rs:287-290` | yes — route gate only; any platform admin may edit any user | **no** — fields are `Option`, both absent ⇒ an UPDATE with no change reports success; email is not validated (F-contract row) | yes — `UPDATE_PROFILE` with `COALESCE`, `db.rs:508-510` |
| Create user (provisioning, inactive) | yes — modal `Users.tsx:243-269` | yes — `POST /api/v1/admin/users`, `main.rs:264-267` | **partial** — same actor-role predicate, `admin.rs:918-920` | yes — required fields, ≥8-char password, Argon2id hash, duplicate-email → 409, `admin.rs:900-963` | yes — `CREATE_INACTIVE` (`is_active=false`), `db.rs:521-524`; audited `admin.rs:926-936` |
| Read a user's module permissions | **no** — no surface, no client function: repo-wide `grep` for `fetchUserPermissions` over `admin/frontend/src` returns nothing, and the only reader of `u.permissions` is `TenantDetail.tsx:393` against a payload that never carries it (F2) | yes — `GET /users/{user_id}/permissions`, `main.rs:338-340` | yes — route gate | yes — `admin.rs:8477-8502` | yes — `user_permissions::GET`, `db.rs:960-961` |
| Write a user's module permissions | yes — checkbox grid `TenantDetail.tsx:406-422` | yes — `PUT /users/{user_id}/permissions`, `main.rs:339-340` | **partial** — `claims.role ∈ {admin, super_admin}`, `admin.rs:8432-8438` | **no** — `body["modules"]` is copied into JSONB verbatim, no slug allow-list, no size bound `admin.rs:8440-8446`; nothing anywhere consumes it (F1) | yes — `user_permissions::UPDATE`, `db.rs:957-958` |
| List a tenant's users | yes — `TenantDetail.tsx:333-338` | yes — `GET /tenants/{id}/users`, `main.rs:251-254` | yes — route gate | **no** — the handler decodes 5 of the 8 selected columns positionally (F5) | yes — `users::LIST_BY_TENANT`, `db.rs:469-472` |

Agreement rows (the control): route ↔ client path and method agree for all six
mutations and the list, field for field (`api/admin.ts:374-404` vs
`main.rs:251-290` + `338-341`); every write that changes a user is audited
(`audit_admin_action` at `admin.rs:806-816, 852-862, 926-936, 966-976, 8452-8462`);
create→activate closes, i.e. the inactive user the create action makes is reachable
by the same panel's toggle (`Users.tsx:207-217`) — the end of that action still has no
delivery path (F9).

---

## Matrix 2 — field contract

`users` columns are read from `db.rs:469-524`; response shapes from the handlers; the
client type from `types/admin.ts:82-97` and `api/admin.ts:28-38`.

| Field | Column / type | Read by the API | Written by the API | Rendered (list / detail / form) | Validated | Label or enum source | Locale / format |
|---|---|---|---|---|---|---|---|
| `user_id` | `uuid` → text | yes | — (server-generated) | list: no (only the 8-char prefix in the panel subtitle, `Users.tsx:135`) | n/a | — | truncated to 8 chars + `…` |
| `email` | `text` | yes | yes — create `admin.rs:901`, update `admin.rs:4510` | list + detail + edit form (`Users.tsx:122, 156-158, 249`) | create: required + uniqueness via DB error; update: **none** (no format check) | — | verbatim |
| `full_name` | `text`, `NULL`→`''` | yes, `COALESCE` `db.rs:483` | yes | list + detail + form | none | — | `'—'` fallback in the list (`Users.tsx:121`) |
| `role` | 5-value enum, `text` | yes | yes | list badge `Users.tsx:123`, detail badge `:170-173`, buttons `:179-206`, create select `:252-253` | server: `ADMIN_ASSIGNABLE_ROLES` = 4 values, `admin.rs:877`, `888-905`; client offers 5 (`ALL_ROLES`, `Users.tsx:11`) | **two sources**: client `ALL_ROLES`, `Users.tsx:11` and `TenantDetail.tsx:357`; server `ADMIN_ASSIGNABLE_ROLES`, `admin.rs:877` | `role.replace('_',' ')` in the badge and both selects |
| `is_active` | `bool` | yes | only as a side effect of activate/deactivate | list badge `:125`, detail badge `:174-178`, toggle label `:218-221` | n/a | — | boolean → "Active"/"Inactive" |
| `tenant_id` | `uuid` → text, **not** returned by the tenant-users route despite being selected | yes (list, detail) | yes — required at create, `admin.rs:902` | list falls back to its first 8 chars `Users.tsx:124`; detail `:159-161`; create form `:256` | create: non-empty; no existence check before the FK | — | truncated |
| `tenant_name` | joined `tenants.name`, `NULL` allowed | yes (list, detail) | — | list `:124`, detail `:159-161` | n/a | — | `|| '—'` fallback |
| `created_at` | `timestamptz` → text | yes | — | detail only, `Users.tsx:185-191` | n/a | — | `toLocaleDateString('en-US', …)` — server sends ISO, client reformats (skill: "a format the client re-formats"; no locale negotiation) |
| `last_login_at` | `timestamptz` → text, nullable | yes (`LIST_FILTERED`, `GET_BY_ID`, `types/admin.ts:37`) | — (login path only) | **no surface renders it** in the Users area | n/a | — | unformatted, unused |
| `permissions.modules` | `jsonb`, default `{}` | yes — `user_permissions::GET` | yes — `user_permissions::UPDATE` | written by a checkbox grid (`TenantDetail.tsx:406-422`) that **seeds from a field no user-list payload carries** (F2) | **none** — no slug allow-list, no cardinality bound | enum drift: the migration comment and the handler doc name 4 slugs (`db/migrations/016_user_permissions.sql:3`, `admin/backend/src/handlers/admin.rs:8423`), the UI offers 7 (`TenantDetail.tsx:39-47`) | raw strings |
| `password` (create input only) | not stored — Argon2id hash | — | yes `admin.rs:922-931` | form field `Users.tsx:250` | server: ≥8 chars `admin.rs:912-917`; client: none | — | no hint, no counter |
| `password_hash` | `text` | never | yes | never | n/a | — | — |

---

## Matrix 3 — flow and step contract

The Users area has one multi-part flow: **provisioning** (create inactive → activate).
It has no URL, no step surface and no persisted state.

| Step | Precondition | What it validates | What it writes | How a skip is prevented | Resume / persistence | Back-navigation retention | Where an error lands |
|---|---|---|---|---|---|---|---|
| 1. Create user (modal) | actor is platform admin (`main.rs:441`) | required email/password/tenant, ≥8 chars, actor may grant the role (`admin.rs:900-920`) | `users` row, `is_active=false`, Argon2id hash (`db.rs:521-524`) | n/a — no skip path | **none** — modal state is React state only (`Users.tsx:31, 34`); a reload or an overlay click (`Modal.tsx:18`) loses the form | n/a | one toast line, not bound to a field (`Users.tsx:52`); the modal stays open |
| 2. Activate (approve) | an inactive user exists | nothing beyond route auth (`admin.rs:988-1015`) | `is_active=true` (`db.rs:518-519`) | **no guard**: the toggle is offered on any user (`Users.tsx:207`) and the route runs for any id | none | n/a | toast, unbound (`Users.tsx:80`) |
| 3. Credential delivery to the created user | [NOT CHECKED: no delivery layer exists to read — see F9/P2] | — | — | — | — | — | — |

The step-3 row is the finding that the flow has no end (F9), not a missing citation.

---

## Matrix 4 — interaction dependency

| Trigger | Dependents | Required action on change | Who owns the state | What is announced |
|---|---|---|---|---|
| `search` change (list) | the users query (`Users.tsx:45-47`) | recompute (debounced 250 ms) | page (`Users.tsx:29-31`) | **nothing** — the count changes with no live region (F-announce) |
| `availableRoles` change (`me.role` resolves/who changes) | the Change-Role buttons `:179`, the create Role select `:252-253` | reset | page | nothing |
| Tenant picker selection (`TenantSearchSelect`) | `form.tenant_id`, tenant query `TenantSearchSelect.tsx:44-47` | keep + recompute the list | the picker (`:31-36`) | nothing; the picker clears its own search text (`:75, 83`) |
| a mutation succeeds (role/status/profile/create) | `selectedUser` (`:68, 77, 59`) and the list query | keep (optimistic patch) + invalidate | page | toast only (`:51, 57, 67, 76`) |
| the list refetches after `invalidateQueries` | `selectedUser` is **not** re-synced from the new payload (`Users.tsx:68, 77` patch locally) | revalidate | page | nothing |
| closing the detail panel / the modal | in-progress `editForm` / `form` | keep | page | nothing — closing discards the edit with no announcement (`Users.tsx:139-146, 243`) |

Finding classes hit: "a value the user chose silently discarded (nothing announces
it)" (detail-panel close with an unsaved edit, `DetailPanel.tsx:15, 33` →
`Users.tsx:139-146`), "a change to a region assistive technology is not watching,
announced nowhere" (search + list refresh: no `aria-live` anywhere in the ui component
set — `grep -n "aria-" components/ui/*.tsx` returns **no match**), and a missing
cascade: the client offers `super_admin` where the server refuses it (F3).

---

## Matrix 5 — surface pattern: controls, data views, flows, notifications

Verdicts are source-derived (`code`). Rules that can only be decided on a running
surface are marked `[NOT CHECKED: no running app in this arm]` rather than assumed.

### Data views — the users table (`Users.tsx:109-128`, `DataTable.tsx:19-66`)

| Rule | Verdict |
|---|---|
| SC 1.3.1 real headers, table labelled | **pass (partial)** — real `<table>`/`<thead>`/`<th>` (`DataTable.tsx:20-33`); no `scope`, no caption/accessible name, no `<caption>` in `DataTable` |
| `aria-sort` on the sorted column | **violation (gap)** — the server fixes `ORDER BY created_at DESC` (`db.rs:492`) and no sort affordance or `aria-sort` exists (`DataTable.tsx:29-39`); the operator cannot sort or reverse (F16) |
| editable cells ⇒ grid semantics | n/a — the Users table has no per-row controls (controls live in the panel) |
| `aria-rowcount`/`aria-colcount` for large/lazy sets, position restored on return | **violation** — no virtualization (fine) but no pager and no position restore: Back/tab-switch reloads at offset 0 because no URL state exists (`Users.tsx:29-47`) |
| SC 1.4.10 one-direction scroll at 320 px, table in its own scroll container | [NOT CHECKED: no running app] — `table-container` class is the only containment (`DataTable.tsx:20`) |
| Pagination marks the current page, one-page pager hidden | **violation** — no pager at all while the server returns `total` (F7); a `Pager` primitive exists unused by this page (`components/ui/Pager.tsx`) |
| Captions/headings describe the data, first column is a human identifier | pass — "Name" first (`Users.tsx:110`) |
| Filters discoverable, active state visible in results | pass (partial) — the search box is the only filter and it is visible; the filtered list is otherwise indistinguishable from an unfiltered one (no result count, no chip) |
| Detail view: key/value pairs, every field shows a value or "not provided" | **violation** — the panel is a flex row list, not a `dl`, and omits `last_login_at` entirely (`Users.tsx:152-192`) |
| Long text strategy | **violation (risk)** — email and tenant name are un-truncated `<td>`s (`Users.tsx:122-124`) while the tenant column falls back to a slice only when the name is absent; the 520 px panel truncates nothing either. [NOT CHECKED: measured widths need the running app] |
| Pass rows | loading state and empty state exist with text (`DataTable.tsx:43-61`, `Users.tsx:111` "No users found") — the empty/loading states are present, not missing |

### Controls

| Rule | Verdict |
|---|---|
| Visible persistent label (never a placeholder as label) | **violation** — `SearchInput` has no label, only `placeholder` (`AdminPrimitives.tsx:58-70`); `FormInput`/`FormSelect` render a `<label>` with no `htmlFor` and the input/select has no `id` (`FormElements.tsx:17-25, 44-49`) ⇒ the accessible name is empty for every user-area field (F10) |
| Instructions where the format is not customary; counter where a length limit exists | **violation** — the ≥8-char password rule is server-only (`admin.rs:912-917`) and unstated in the form (`Users.tsx:250`) (F11) |
| One required/optional convention | **violation** — `required` is supported by the primitives (`FormElements.tsx:17`) and passed by nothing in this area, while the API 400s on missing email/password/tenant_id (`admin.rs:900-915`) |
| `autocomplete` token on self-data fields, off/absent on search/filter/record fields | **pass (n/a)** — hand-checked: the create form collects a *third party's* email and name, not the user's own, so technique H98 does not apply; the search box correctly carries no token (`AdminPrimitives.tsx:61-70`) |
| APG combobox: roles, `aria-expanded`, `aria-controls`, `aria-autocomplete` | **violation** — the tenant picker is a clickable `div` with a nested input only while open (`TenantSearchSelect.tsx:79-101`, popup `:150-186`); `grep -n "aria-" components/ui/*.tsx` → no match (F15) |
| APG combobox keyboard (Down opens, Escape closes, focus stays, `aria-activedescendant`) | **violation** — no key handler anywhere in the picker; closing needs a click outside (`TenantSearchSelect.tsx:38-40`), and the options are `<button>`s in the Tab order (`:161-186`) (F15) |
| SC 2.5.8 target size ≥24 px | [NOT CHECKED: no running app] — the role buttons are `px-3 py-1.5 text-[10px]` (`Users.tsx:196-204`), a size that needs measurement, not assumption |
| SC 2.4.7 focus visible / 1.4.11 indicator contrast | [NOT CHECKED: no running app] — the page sets no focus styles; the primitives' inputs carry `outline-none` (`AdminPrimitives.tsx:65`, `TenantSearchSelect.tsx:99`) which makes this the highest-risk unchecked item |
| SC 1.4.3 contrast, no colour-only state | [NOT CHECKED: no running app] — role and status are colour-coded badges with a text label (`Users.tsx:18-24`, `StatusBadge`), so the colour-only risk is low, but the ratio is unmeasured |
| APG disclosure / tabs | n/a — no disclosure or tab in this area (TenantDetail has tabs; out of scope) |

### Validation and errors

| Rule | Verdict |
|---|---|
| Validation on submit, failing values kept, server-side validation present | pass — no blur validation, the modal keeps its state on error (`Users.tsx:49-53`), server validation exists (`admin.rs:900-963`) |
| SC 3.3.1/3.3.3 the item in error is identified and the correction described in text | **violation** — one toast line, no field identification, no summary (`Users.tsx:52, 62, 71, 80`) (F12) |
| Association `aria-describedby`, same wording in summary and beside the field | **violation** — no `aria-describedby` anywhere (`grep` above); `FormInput`'s `error` prop exists (`FormElements.tsx:24-25`) and is never passed by this page |
| Error summary at the top of the form | **violation** — none exists |

### Flows (provisioning)

| Rule | Verdict |
|---|---|
| One question per page, unique heading, back link + Continue | **n/a → gap** — the flow is one modal with 5 fields and no steps (`Users.tsx:243-269`); there is no step indicator and no check-your-answers, so a mistyped email is written on the first submit |
| Check-your-answers: pre-populated on return, Change link, submit names its action | **violation (family)** — nothing is pre-populated on return (no persistence), and the submit says "Create User" while the result is an *inactive* user (`Users.tsx:266-268` vs `admin.rs:936`) |
| SC 3.3.7 redundant entry | pass — the tenant is chosen once |
| SC 3.3.4 destructive change checked or confirmed | **violation** — deactivation writes immediately on one click (`Users.tsx:207`), no confirmation, no undo (F8) |
| Destructive confirmation names what will be lost | **violation** — there is no confirmation at all (F8) |
| `APG dialog`: `aria-modal` only when justified, focus moves in/stays/returns | **violation** — neither `Modal` (`Modal.tsx:18-28`) nor `DetailPanel` (`DetailPanel.tsx:14-16`) has `role="dialog"`, `aria-modal`, a label, a focus move, an Escape handler or a focus return; the overlay click closes both (F13) |

### Notifications

| Rule | Verdict |
|---|---|
| SC 4.1.3 a change the page makes without moving focus is programmatically determinable | **violation (unverified mechanism)** — the result count after a filter and the mutation results are toasts; `sonner` is imported at `Users.tsx:4` and whether its container is a live region was [NOT CHECKED: `App.tsx` mount not read in this arm]; the requirement that the *whole* status string be the announced unit ("User created") is not met with or without sonner, because the status omits the created user and the inactive state |
| Changes that are not status messages stay out of live regions | pass — no live regions exist |
| Banner is `role=region`/`alert`, one per page, never replaces validation errors | n/a — no banner in this area |

---

## Findings, most severe first

Every finding names one evidence class (`code` here), a citation, and a Prevent line.
Severity is the 0–4 scale (frequency × impact × persistence).

**F1 · sev 4 · `code` · the module-permission surface grants nothing and is enforced
nowhere.** Read + write routes (`main.rs:338-341`), storage (`db.rs:956-962`,
`016_user_permissions.sql:7`), and a write path that copies `modules` verbatim
(`admin.rs:8440-8446`). Absence proof: `grep -rn "users.permissions\|user_permissions\|u.permissions"`
over the repository returns only the admin writer, the migration comment and the
route registration — no middleware, guard or query in `app/backend` reads the column.
Matrix-1 disagreement: surface yes / route yes / authorization **no** / service **no** /
persistence yes.
*Prevent:* one contract test that fails today — a user with `permissions={"modules":[]}`
must be refused on a module-gated route — plus a CI gate that rejects a JSONB
permission column with no reader symbol. This is a required proposal: see **P1**.

**F2 · sev 4 · `code` · the permission editor seeds from a field the user-list payload
never carries, then saves the empty set.** Read the seed: `TenantDetail.tsx:393`
(`u.permissions?.modules ?? []`) where `u` comes from `fetchTenantUsers`
(`api/admin.ts:364-370`) → `admin_tenant_users` emits only
`user_id/email/full_name/role/is_active` (`admin.rs:781-785`) although the SQL selects
`permissions`-adjacent `created_at`/`last_login_at` and nothing more. Write:
`TenantDetail.tsx:347` → `api/admin.ts:922-925` → `db.rs:957-958` overwrites the whole
JSONB with the empty array the UI just built. Every "Manage → Save" on a user who has
permissions **silently wipes them**, and nothing announces it. (Same family as this
repo's own lesson: the write path and the checker are two readings of one rule; here the
reader of the rule does not exist at all.)
*Prevent:* a contract test pinning response-field parity — for every field
`PUT /users/{id}/permissions` accepts, the tenant-users list response must carry the
current value; e2e: seed `["proxy"]`, open Manage, save untouched, assert the stored
value is still `["proxy"]`.

**F3 · sev 3 · `code` · the UI offers a role the server always refuses.** Client
`ALL_ROLES` includes `super_admin` (`Users.tsx:11`), used for the Change-Role buttons
(`:85, :179`) and the create Role select (`:252-253`), and again in
`TenantDetail.tsx:357`; the server's `ADMIN_ASSIGNABLE_ROLES` excludes it
(`admin.rs:877`) and `validate_platform_role_grant` returns 400 "Invalid platform role"
(`admin.rs:888-892`). The affordance is dead for every actor, including the
super_admin the button is shown to.
*Prevent:* a parameterised API test over the offered role list asserting the create and
role-update responses are never 400; generate the client's list from the server constant.

**F4 · sev 4 · `code` · one platform admin can demote or deactivate a peer, a
super_admin, or themselves.** Documented intent: "Admin can assign operator/viewer/
api_user. Only super_admin can assign admin/super_admin" (`admin.rs:787-789`).
Implemented predicate (`admin.rs:888-905`) only blocks *granting* `admin`;
`UPDATE_ROLE` (`db.rs:512-513`) and `DEACTIVATE` (`db.rs:515-516`) carry no target
predicate, so `PUT /users/{super_admin}/role {"role":"viewer"}` and
`POST /users/{super_admin}/deactivate` succeed for any `admin`, and the same actor can
deactivate themselves. Recovery needs a `super_admin`, which this panel cannot create
(`admin.rs:876`: "super_admin can only be created via the CLI tool").
*Prevent:* two handler tests that fail today — admin→super_admin role change returns
403, self/last-super-admin deactivation returns 409 — plus extending
`validate_platform_role_grant` to a (actor, target) predicate.

**F5 · sev 3 · `code` · an 8-column SELECT decoded into a 5-slot tuple, positionally.**
`admin.rs:759-768` declares `(String, String, String, String, bool)` for
`users::LIST_BY_TENANT`, which returns 8 columns
(`db.rs:469-472`: user_id, email, full_name, role, is_active, tenant_id, created_at,
last_login_at). sqlx 0.8's tuple `FromRow` reads indices 0..N with **no length check**
(`~/.cargo/registry/src/index.crates.io-1949cf8c6b5b557f/sqlx-core-0.8.6/src/from_row.rs:326-345`),
so three selected columns are fetched and dropped, and any reorder of the SQL silently
re-labels the fields with no compile-time or runtime signal. The same file gets it
right twice — `GET_BY_ID` 8↔8 (`admin.rs:4469-4490`), `LIST_FILTERED` 9↔9
(`admin.rs:4394-4420`) — so this is a deviation from the repo's own convention.
*Prevent:* a response-shape contract test on `admin_tenant_users` asserting its keys
equal the `LIST_BY_TENANT` column set; convert the positional tuples to
`#[derive(sqlx::FromRow)]` structs (name-based, fails loudly).

**F6 · sev 3 · `code` · a route and a client function no surface calls, while the panel
reads a stale row.** `GET /api/v1/admin/users/{user_id}` (`main.rs:287-290`), handler
`admin_get_user` (`admin.rs:4468-4502`), client `fetchUser`
(`api/admin.ts:379-382`). Absence proof: `grep -n "fetchUser\(" admin/frontend/src`
matches only the definition. The panel therefore shows whatever the list row held —
after a mutation it patches the local object (`Users.tsx:68, 77, 59`), so a concurrent
change by another admin is invisible until a full refetch.
*Prevent:* a dead-export gate (knip/ts-prune) in CI, or make the panel call `fetchUser`
and assert in the e2e that the detail request fires on row click.

**F7 · sev 3 · `code` · the count is the page's, not the server's, and the overflow is
unreachable.** `fetchUsers({ search, limit: 200 })` (`Users.tsx:46`) never sends
`offset`; the server clamps 1..=500 and returns `total` in the envelope
(`admin.rs:4397-4404, 4444`); the page derives the header, the subtitle and the four
stat cards from `allUsers.length` (`Users.tsx:83, 95, 101-104`). With 201+ users the
page states "200 users across all tenants" and nothing reaches the rest; a `Pager`
primitive exists (`components/ui/Pager.tsx`) and other admin pages use it.
*Prevent:* a route test (`total=201, limit=200` ⇒ pager required) and a UI assertion
that the header count comes from the envelope, not from `rows.length`.

**F8 · sev 3 · `code` · deactivation and role change are one-click, unconfirmed and
un-undoable (SC 3.3.4).** `Users.tsx:207-217` (toggle) and `:196-204` (role buttons)
call the mutation on click; no confirmation, no undo, and the toast says only "Status
updated"/"Role updated" (`:76, :67`) — it does not name the user, the previous value, or
the live sessions cut. `DELETE`/restore does not exist for users.
*Prevent:* an e2e assertion that the first click opens a confirmation naming the target
(the mutation must not be issued), plus a session-revocation test for deactivate.

**F9 · sev 3 · `code` · the create action has no delivery path to the person it
creates.** The admin types the password (`Users.tsx:250`), the row is created inactive
(`db.rs:521-524`, response "User created (inactive). Activate after approval."
`admin.rs:936-940`), and the only user-visible outcome is the toast "User created"
(`Users.tsx:51`). The repository's notification path states its own absence:
`app/backend/src/proxy/notification_dispatcher.rs:638` — "email_notification_pending —
SMTP not configured (requires lettre crate)". So the credential never reaches the
invitee and the product's own claim that a created user is provisioned is only half
delivered.
*Prevent:* an e2e that passes only when the created user has a delivery record in the
outbox, plus an audit event naming the delivery attempt. Required proposal: **P2**.

**F10 · sev 2 · `code` · no accessible name on any user-area field, and no required
convention.** `FormInput`/`FormSelect` render `<label>` without `htmlFor` and the
control without `id` (`FormElements.tsx:17-25, 44-49`); `SearchInput` has a placeholder
and no label (`AdminPrimitives.tsx:58-70`); the create form passes `required` to nothing
(`Users.tsx:248-266`) while the API requires email, password and tenant_id
(`admin.rs:900-915`). SC 1.3.1/3.3.2 and the placeholder-as-label rule.
*Prevent:* axe-core in the page's e2e (rules `label`, `form-field-multiple-labels`) and
one checklist entry for the required convention, which axe cannot see.

**F11 · sev 2 · `code` · a length rule the UI never states and an error that arrives
only as a toast.** ≥8 chars at `admin.rs:912-917`; the field is a bare
`type="password"` (`Users.tsx:250`); the 400 surfaces as `toast.error`
(`Users.tsx:52`). SC 3.3.3 (no correction text) and the "format hint where not
customary" rule.
*Prevent:* an e2e that submits 7 characters and asserts the message appears beside the
field with `aria-describedby`, not only in the toast.

**F12 · sev 2 · `code` · the error contract is one prose line per toast with no field
identification (SC 3.3.1/3.3.3).** `e?.response?.data?.error` (`Users.tsx:52, 62, 71,
80`) — for a 400 nothing marks the offending field, no summary exists, and focus stays
where it was. The primitives already support `error` beside the field
(`FormElements.tsx:24-25`) and the page never uses it.
*Prevent:* an e2e that asserts an error summary region exists after a failing submit and
that the message text is identical to the field-level text.

**F13 · sev 3 · `code` · the modal and the detail panel are divs, not dialogs.**
`Modal.tsx:18-28` and `DetailPanel.tsx:14-16`: no `role="dialog"`, no accessible name,
no `aria-modal`, no initial focus, no focus containment, no Escape, no focus return; both
close on an overlay click and the detail panel thereby discards an in-progress edit
(`Users.tsx:139-146, 243`). APG dialog/alertdialog and SC 4.1.2.
*Prevent:* an e2e focus assertion (focus inside on open, returns to the invoker on
close, Escape closes) plus an axe run; then one shared dialog primitive so the fix is
not per-page.

**F14 · sev 2 · `code` · the only way into the detail panel is a mouse click.** The
row is a `<tr onClick>` with no `tabIndex`, no role and no key handler
(`Users.tsx:114-120`); nothing else opens the panel.
*Prevent:* an accessibility test asserting every action reachable on this page is
reachable by Tab+Enter (checklist entry; axe has no rule for a clickable row).

**F15 · sev 2 · `code` · the tenant picker is a div combobox.** Trigger div + input
only while open (`TenantSearchSelect.tsx:79-101`), popup of `<button>` options without
listbox/option roles or `aria-expanded`/`aria-controls` (`:150-186`), no Escape, no
`aria-activedescendant`; `grep -n "aria-" components/ui/*.tsx` → **no match**.
Pass rows it does have: an explicit loading line and a no-match line (`:145-158`).
*Prevent:* axe (`aria-required-children`, `aria-expanded`) plus a keyboard e2e
(Down opens, Escape closes, focus stays on the combobox).

**F16 · sev 1 · `code` · the list cannot be sorted, and the fixed order is invisible.**
`ORDER BY u.created_at DESC` (`db.rs:492`) with no `aria-sort`, no header activation and
no sort parameter (`DataTable.tsx:29-39`, `Users.tsx:110`).
*Prevent:* if a sort affordance is added, an e2e that toggles direction and asserts
`aria-sort`; until then, a documented decision, not a silent default.

### Questions, not findings (no evidence class reachable in this arm)

- `useMe` compares `me?.role === 'super_admin'` (`Users.tsx:27-28`) while the backend
  normalizes the legacy alias `superadmin` (`middleware.rs:23-27`). If `/auth/me`
  returns the alias, `isSuperAdmin` is false and the role set silently collapses to the
  3-role list — which incidentally hides F3's dead button. The check that settles it:
  read a real `/api/v1/auth/me` body (or `handlers/auth.rs::handle_me`) and confirm the
  literal. Not claimed either way here.
- Whether `sonner`'s container is a live region (`Users.tsx:4`; mount not read).

---

## Proposals (capability-change; required because the fix names a layer that does not exist)

### P1 — enforce module permissions in the request path

| Heading | Content | Falsified by |
|---|---|---|
| Capability | a request carrying a user identity is refused when the identity's `permissions.modules` does not contain the module that owns the route | a cited code path that already consults `users.permissions` |
| Absence proof | `admin/backend/src/handlers/admin.rs:8440-8446` writes the JSONB; `grep -rn "user_permissions\|users.permissions" .` finds no reader; failing input: any authenticated non-admin user hitting a module route today | a cited path that handles that input |
| Contract delta | extend the admin OpenAPI/route table with an `x-required-module` tag per admin route and a permission schema `{modules: enum[proxy,detection,analytics,governance,compliance,benchmarks,threat_intel]}` (the 7 the UI writes, `TenantDetail.tsx:39-47`), replacing free strings | running the contract checker and getting green with no diff |
| Migration | expand: add the enum check as a `CHECK (permissions->'modules' <@ …)` NOT VALID; migrate: backfill known slugs and delete unknown ones (report count); contract: validate the constraint (dated step: at least one release after the backfill) | a contract phase with no date |
| Rollout | flag `admin.module_permissions.enforce` (`bool`, expected lifetime ≤ 2 releases, initial exposure 0%, kill-switch owner: platform admin on-call, abort threshold: > 5 refusals/hour for a module that is enabled for > 50% of users, window 24 h) | an unmeasurable threshold, or a flag with no lifetime |
| Verification | `admin/backend/tests/user_permissions_enforcement.rs` — fails on the pre-change commit (no gate exists), passes after | a check that also passes on the pre-change commit |
| Reversibility | the gate writes nothing; restore = unset `admin.module_permissions.enforce` (enforcement off, data untouched). The *migration* is the one-way part: dropping a slug from JSONB has no restore, so it is applied only to unknown slugs, with the removed values written to the audit log first | data written with no restore step and no label |
| Decision | ADR "Module permissions are enforced at the route layer, not the UI", status Proposed; supersedes the implicit assumption in `016_user_permissions.sql:7` that storing is enforcing | an ADR without a status |
| Appetite | 3 days; out of bounds: the 15 other admin pages' routes; on expiry the flag stays 0% and the ADR moves to Rejected | no box, or an implicit extension |

### P2 — credential delivery for admin-created users

| Heading | Content | Falsified by |
|---|---|---|
| Capability | a user created by an admin receives a single-use activation credential out of band, without the admin transmitting a password | a cited path that already delivers a credential to a created user |
| Absence proof | `admin/backend/src/handlers/admin.rs:900-940` requires an admin-chosen password and returns only a message; `app/backend/src/proxy/notification_dispatcher.rs:638` states "SMTP not configured (requires lettre crate)"; failing input: create a user with no password | a cited path that handles that input |
| Contract delta | `api/admin` OpenAPI: `POST /api/v1/admin/users` drops `password` from the request and adds `invite: {expires_at, delivery: "email"|"link"}` to the response; migration adds `user_invites(token_hash, user_id, expires_at, used_at, created_by)`; a contract test asserts the password field is rejected | running the compatibility checker and getting green with no diff |
| Migration | expand: add `user_invites` (nullable, no readers); migrate: backfill nothing (no historical invites) and keep the password path behind a flag for CLI callers; contract: drop `password` from the panel request once the invite path is live (dated step) | a contract phase with no date |
| Rollout | flag `admin.user_invites` (`bool`, lifetime ≤ 2 releases, initial exposure: internal tenants only, kill-switch owner: platform admin on-call, abort threshold: > 2% of invites undelivered in any 6 h window) | an unmeasurable threshold, or a flag with no lifetime |
| Verification | `admin/backend/tests/user_invite_delivery.rs` + a UI assertion that the create modal no longer has a password field; both fail pre-change | a check that also passes on the pre-change commit |
| Reversibility | writes `user_invites` rows plus an outbox record; restore = delete invites by `created_by`+window, revoke the delivered tokens (`used_at` untouched rows), and re-enable the password path via the flag | data written with no restore step and no label |
| Decision | ADR "Provisioning is invite-based; the admin never sees or sets a password", status Proposed | an ADR without a status |
| Appetite | 1 week (delivery channel is the unknown); out of bounds: SSO/OIDC onboarding; on expiry the invite path ships behind a 0% flag and the ADR moves to Rejected | no box, or an implicit extension |

Reviewer's five absences, checked against this artifact: every capability claim has a
`code` finding behind it (F1→P1, F9→P2); both proposals carry a rejectable artifact
(constraint/contract test, flag with lifetime, ADR with status); P2's schema step has
named migration phases; every flag carries a lifetime and an owner; both contract
changes carry an ADR and a pre/post check pair.

---

## Coverage

| Matrix | Rows | Checked from source | Not checkable in this arm | What would change the conclusion |
|---|---|---|---|---|
| 1 capability | 11 | 11 | 0 — but "surface" columns are source-derived, not observed | a running app to confirm the buttons render and the mutations fire |
| 2 field contract | 12 | 12 | 0 | one seeded row with a non-empty `permissions.modules` (F2's wipe is a code reading, not a reproduced data loss) |
| 3 flow / step | 3 | 2 | 1 (`[NOT CHECKED: no delivery layer exists]`, F9) | a mail/outbox layer appearing |
| 4 interaction dependency | 6 | 6 | 0 | a running app to see the announcements (F-announce is a source reading) |
| 5 surface pattern | 34 rules | 29 decided | 5 `[NOT CHECKED: no running app]` — SC 1.4.10 reflow, SC 2.5.8 target size, SC 2.4.7/1.4.11 focus, SC 1.4.3 contrast, and the `sonner` live-region mount | axe-core + manual measurements at 320/1440 px, dark scheme, and a focus/keyboard pass |

Not looked at, on purpose: the other fifteen admin pages except the components sharing
`Table`/`Form`/`Modal` primitives, `TenantDetail` beyond its Users tab (its tab set,
proxies and API keys are out of the Users boundary), the login/registration-request
approval path (it also creates users but through another feature's surface), the
app-backend's own user endpoints, and every runtime property of the deployed system
(no running app, no database session, no credential in this arm).

Hand-checks the automated sweeps cannot do, and what happened to each in this arm:
3.3.1/3.3.3 error text (F12, source-derived), destructive-confirmation wording (F8,
source-derived), 4.1.3 announcement (uncheckable without a running app), 2.4.7 focus
visibility (uncheckable), 1.4.10 320 px reflow (uncheckable), autocomplete token fit
(skill's own hand-check item — the create form collects a third party's email, so no
token applies, recorded above), `aria-modal` preconditions (F13, source-derived),
conditionally revealed question announced (n/a — no conditional reveal in this area).
