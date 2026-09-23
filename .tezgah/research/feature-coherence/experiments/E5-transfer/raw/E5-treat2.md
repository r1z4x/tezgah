# E5-treat2 — feature-audit, admin Users area (aibim-app)

Artifact applied: `skills/feature-audit/SKILL.md` (read in full). Companion axes: `product-analysis`,
`analyze-app`. Scope is the batch contract: the admin Users area only.

## 0. The unit

| Item | Value |
|---|---|
| Entity | an admin-panel user (`users` row: belongs to one tenant, carries a platform role) |
| Actions | list/search, view detail, create, edit profile, change role, deactivate, activate, set module permissions, read module permissions, tenant-scoped list |
| Screens | `Users.tsx` (list + detail side panel + edit mode + create modal), `TenantDetail.tsx` `UsersTab` (shares role + permissions endpoints; in scope only where shared) |
| Endpoints | `GET/POST /api/v1/admin/users`, `GET/PUT /api/v1/admin/users/{id}`, `PUT /api/v1/admin/users/{id}/role`, `POST /api/v1/admin/users/{id}/deactivate`, `POST /api/v1/admin/users/{id}/activate`, `GET/PUT /api/v1/admin/users/{id}/permissions`, `GET /api/v1/admin/tenants/{id}/users` |
| Files | `admin/frontend/src/pages/Users.tsx`, `api/admin.ts`, `types/admin.ts`, `hooks/useMe.ts`, `components/ui/{DataTable,AdminPrimitives,FormElements,Modal,DetailPanel,TenantSearchSelect,Pager,index}.tsx`; `admin/backend/src/handlers/admin.rs`, `db.rs`, `main.rs`, `middleware.rs`, `handlers/auth.rs`, `handlers/error.rs` |
| Non-goals | the other 15 admin pages, except where they share a component/endpoint (recorded as such) |

Evidence classes: `code` (a `path:line`), `ui-observed`, `behaviour`, `external`, `user-verbatim`.
Standard citation for a rule-derived finding: WAI-ARIA APG / WCAG 2.2 sc / the skill's own rule — the
class column still names the *evidence*, which here is always the source.

### How this ran, and the one thing it could not do

Three passes, all **source-reading**: (1) first-time operator (create provision path), (2) daily operator
(list, search, role/status churn), (3) API client with no UI (direct endpoint/authz audit). No fourth
pass. The running app was **not** exercised — the batch forbids starting Docker or building, and the
app is audited from source in both arms. Consequence: **zero `ui-observed` and zero `behaviour`
findings below; every finding is `code`.** Rendered-screen reads (widths, dark scheme, blur/grayscale),
axe-core and the measured page checks were not run, so the WCAG level this artifact can claim is
**none** — the rules cited are the criteria the code contradicts, not an audit of the rendered page.
Matrix 5 rows that need a rendered screen carry `[NOT CHECKED: no running app]`.

## 1. Value axis — the first finding is that this feature is not observable

| Goal | Signal | Metric (definition, window) | Status |
|---|---|---|---|
| An operator can provision and control tenant accounts without leaving the panel | account reaches first login after a panel create | *invite→first-login conversion* = users activated within 7d of `created_at` / users created, 30d window | **not measurable** |
| Misuse is reversible | a deactivation actually ends access | *median minutes from deactivate to last accepted request* | **not measurable** |
| Accounts are not duplicated or abandoned | pending users are approved or removed | pending users older than 7d / created, 90d window | **not measurable** |

Finding **0 (severity 3, `code`)**: the admin frontend contains no product instrumentation —
`grep -rn "analytics|posthog|gtag|mixpanel" admin/frontend/src` returns only the string `'analytics'`
as a permission *label* (`TenantDetail.tsx:42`). No counter, event or timer exists on this path, so
every metric above is unwritable today. **Prevent**: this one has no mechanical prevention; it stays a
review item until events are emitted, and the finding itself is the first backlog entry.

## 2. Matrix 1 — capability (rows = actions, 10 rows)

Every `yes`/`no` carries its citation; an absence carries the search that proves it, inline in the
cell or in the note under the table.

| # | Action | Surface (what a person can do) | Route | Authorization | Service / validation | Persistence |
|---|---|---|---|---|---|---|
| 1 | List + search users (all tenants) | yes — list `Users.tsx:113-127`, search `Users.tsx:107` | yes — `main.rs:263-266`, handler `admin.rs:4393` | yes — middleware `require_admin_access` on the whole group (`main.rs:440-443`), gate `super_admin\|admin` (`middleware.rs:36-38`) | yes — limit clamp 1..500, offset ≥0, search trimmed (`admin.rs:4394-4411`) | yes — `db.rs:482-492` ILIKE over email/name/role/user_id/tenant name |
| 2 | View user detail | yes — side panel `Users.tsx:130-143` | yes — `main.rs:283-286`, `admin.rs:4468` | yes — group gate (as row 1) | yes — 404 path `admin.rs:4495` | yes — `db.rs:503-506` |
| 3 | Create user | yes — modal `Users.tsx:244-268` | yes — `main.rs:263-266` POST, `admin.rs:891` | yes — group gate + `validate_platform_role_grant` (`admin.rs:875-889`) | yes — required fields, password ≥8 (`admin.rs:907-919`), Argon2id (`admin.rs:928`) | yes — `CREATE_INACTIVE`, always `is_active=false` (`db.rs:521-524`) |
| 4 | Edit profile (name, email) | yes — edit mode `Users.tsx:220-236` | yes — `admin.rs:4504` | yes — group gate only; **no target check** (see F1) | partial — no email format check, no empty check (`admin.rs:4509-4511`) | yes — `UPDATE_PROFILE` COALESCE (`db.rs:508-510`) |
| 5 | Change role | yes — role buttons `Users.tsx:179-190` | yes — `admin.rs:788` | yes — `validate_platform_role_grant` (`admin.rs:875-889`) | yes — typed body `UserRoleUpdateReq.validate()` (`admin.rs:796-799`) | yes — `UPDATE_ROLE` (`db.rs:512-513`) |
| 6 | Deactivate | yes — `Users.tsx:207-216` | yes — `admin.rs:834` | yes — group gate only; **no target check** (F1) | n/a — no validation | yes — `DEACTIVATE` (`db.rs:515-516`) |
| 7 | Activate | yes — same control, `Users.tsx:215` | yes — `admin.rs:988` | yes — group gate only; **no target check** (F1) | n/a | yes — `ACTIVATE` (`db.rs:517-518`) |
| 8 | Set module permissions | yes — but only on the sibling surface `TenantDetail.tsx:408-424`; **not reachable from the Users area** | yes — `main.rs:337-341` PUT, `admin.rs:8424` | yes — handler re-checks `super_admin\|admin` (`admin.rs:8430-8436`) | **no** — any array is stored verbatim (`admin.rs:8441-8443`); the 7 ids live only on the client (`TenantDetail.tsx:39-47`) | yes — `user_permissions::UPDATE` |
| 9 | Read module permissions | **no surface anywhere** | yes — `main.rs:337-341` GET, `admin.rs:8477` | yes — group gate | yes | yes — `user_permissions::GET` |
| 10 | List users of one tenant | yes — sibling `TenantDetail.tsx:333-340` | yes — `main.rs:251-254`, `admin.rs:757` | yes — group gate; no tenant scoping (all platform admins are global) | n/a — no limit, no search | yes — `LIST_BY_TENANT` (`db.rs:469-472`, 8 columns) |

**Dead-end and missing-route rows.** Row 9 is a route with no surface (see F14); row 8's surface lives
on another page, so the Users area cannot answer "what may this person use?" without leaving it.
Row 2's route is unreachable from the client (F3). Rows 3/6/7 are the only ways a person enters or
leaves the product, and row 3's *end* — what the recipient actually receives — has no delivery path at
all (F8).

Row 10 decodes 8 SQL columns into a 5-tuple (`admin.rs:762-763` vs `db.rs:469-472`). This is **not** a
defect: sqlx 0.8.6's tuple `FromRow` reads by index and never compares column counts
(`sqlx-core-0.8.6/src/from_row.rs:326-338`). Recorded here so it is not re-raised as one.

## 3. Matrix 2 — field contract (12 rows)

| Field | Column / type | Read by the API | Written by the API | Rendered (list / detail / form) | Validated | Label or enum source | Locale / format |
|---|---|---|---|---|---|---|---|
| `user_id` | `uuid` | yes `db.rs:503` | server-generated `db.rs:521` | list: no; detail: truncated to 8 chars `Users.tsx:135` | n/a | — | uuid sliced, `+ '…'` |
| `email` | `text` | yes `db.rs:482` | create `admin.rs:893`; edit `admin.rs:4510` | list `Users.tsx:122`; detail `Users.tsx:149`; form `Users.tsx:223,249` | **no format check anywhere** (both writes) | — | raw |
| `full_name` | `text` (nullable) | yes | create `admin.rs:895`, edit `admin.rs:4509` | list `Users.tsx:121` (`'—'` fallback); detail `Users.tsx:134` | no length/empty check | — | raw |
| `role` | `text` | yes `db.rs:482` | create `admin.rs:896`, role route `admin.rs:800` | list `Users.tsx:123`; detail `Users.tsx:157`; form `Users.tsx:252` | role allow-list server-side `admin.rs:875-889`; **client list `Users.tsx:16-17` differs** (F4) | two sources: `ADMIN_ASSIGNABLE_ROLES` (`admin.rs:873`) vs `ALL_ROLES` (`Users.tsx:17`) | `role.replace('_',' ')` — first underscore only |
| `is_active` | `bool` | yes | `db.rs:515-524` | list `Users.tsx:126`; detail `Users.tsx:165` | n/a | binary label, not the pending-approval state (F8) | raw |
| `tenant_id` | `uuid` | yes `db.rs:482` | create `admin.rs:897` (required) | list fallback `Users.tsx:124`; detail fallback `Users.tsx:150` | non-empty only | — | `slice(0,8)` fallback |
| `tenant_name` | `text` (joined) | yes `db.rs:486` | never (join) | list `Users.tsx:124`; detail `Users.tsx:150` | n/a | — | raw |
| `created_at` | `text` | yes `db.rs:487` | DB default | detail only `Users.tsx:167-170` | n/a | — | `toLocaleDateString('en-US')` — a server-side `::text` string re-formatted client-side |
| `last_login_at` | `text` (nullable) | yes `db.rs:487` | never written on login (`db.rs:533` login selects by email) | **nowhere** — `grep -rn last_login_at admin/frontend/src` → two type declarations only (`types/admin.ts:94`, `api/admin.ts:37`) | n/a | — | raw |
| `password` | `text` (write-only) | never read | `CREATE_INACTIVE` binds the Argon2id hash `admin.rs:928,939` | form only `Users.tsx:250`; no reveal, no hint, no counter (F9) | ≥8 chars, server only `admin.rs:913-918` | — | plaintext in the request body (TLS); minimum never stated on screen |
| `modules` | `jsonb` array | `admin.rs:8482-8486` | any array `admin.rs:8441-8443` | only `TenantDetail.tsx:408-424` | **none** — 7 ids exist client-side only (F13) | two sources: `AVAILABLE_MODULES` (`TenantDetail.tsx:39-47`) vs whatever arrives | raw |
| `total` | `int` | yes `db.rs:494` | server-computed | **nowhere** — `Users.tsx:84-104` uses `allUsers.length` instead (F5) | n/a | — | raw |

Fields with no writer: `last_login_at` (F18) and `total` consumed as list length (F5). Fields with no
reader: none at the type level, two at the view level.

## 4. Matrix 3 — flow and step contract (9 step-rows)

The feature's only multi-step flows are the create→approve path and the two in-panel edit modes.

| Flow / step | Precondition (state it requires) | What it validates | What it writes | How a skip is prevented | Resume / persistence | Back-navigation retention | Where an error lands |
|---|---|---|---|---|---|---|---|
| create 1 — open modal | none | none | nothing | n/a | form state survives close (F11) | reopening shows the previous draft, incl. password | n/a |
| create 2 — fill | none | none (no required markers, `Users.tsx:248-256`) | nothing | n/a | in-memory only | as above | none until submit |
| create 3 — submit | none | server: required + password ≥8 + role grant (`admin.rs:907-919,875-889`) | `users` row, `is_active=false` (`db.rs:521-524`) | n/a | — | — | toast only, no field association `Users.tsx:52` |
| create 4 — pending approval | server-enforced state the UI never names | n/a | nothing | **not prevented, not surfaced**: the toast says "User created" (`Users.tsx:51`) and the new row reads "Inactive" like any deactivated account (`Users.tsx:126`) | none | none | n/a |
| create 5 — activate | the row must be found in the list and opened | none | `is_active=true` (`db.rs:517`) | n/a | — | — | toast `Users.tsx:76` |
| edit 1 — enter edit mode | a selected row | none | nothing | n/a | draft seeded at open (`Users.tsx:202`) | unsaved draft is discarded when the panel closes (`Users.tsx:133`) — silently (F11) | n/a |
| edit 2 — save | non-empty inputs, none enforced | server: nothing (no empty/format check, `admin.rs:4509-4511`) | `UPDATE_PROFILE` under `COALESCE` — an empty string clears the name, `null` keeps it | `null` vs `""` never distinguished by the caller | — | — | toast `Users.tsx:57-62`; panel state patched locally `Users.tsx:59` |
| role change | a selected row | requested role checked, target not (`admin.rs:875-889`) | `UPDATE_ROLE` | n/a | — | — | toast `Users.tsx:67`; 400 for the `super_admin` button (F4) |
| deactivate / activate | a selected row | **none** | `is_active` flag; existing tokens keep working (F2) | n/a | — | — | toast `Users.tsx:76` |

"No persistence" applies to the create draft (create 1-3): a reload loses it. The **skip that is not
prevented** is create 4: nothing requires a pending account to be approved or removed on any layer, so
a create can terminate as a permanently inactive user that no surface distinguishes from a
deliberately disabled one.

## 5. Matrix 4 — interaction dependency (6 rows)

| Trigger | Dependents | Required action on change | Who owns the state | What is announced |
|---|---|---|---|---|
| search text (`Users.tsx:34-35`, 250 ms debounce `Users.tsx:39-42`) | list rows, all four stat cards, header subtitle, selected row | recompute — **not reset**: the panel stays open on a row that may no longer be in the result set | component state (`useState`), server query keyed `['users', debouncedSearch]` (`Users.tsx:45`) | nothing (F15) |
| row click (`Users.tsx:120`) | selection highlight, detail panel, edit draft, role buttons, status button | reset the edit draft — done (`Users.tsx:87-91`) | component state | nothing |
| panel close (`Users.tsx:133`) | selection, edit draft | reset — draft discarded with no warning | component state | nothing (F11) |
| role change (`Users.tsx:184`) | role buttons (active one moves), admin count stat | keep + invalidate `['users']` (`Users.tsx:69`) | server + optimistic local patch (`Users.tsx:65`) | toast "Role updated" |
| status toggle (`Users.tsx:207`) | status badge, active/inactive stats | recompute via invalidate (`Users.tsx:78`) | server + optimistic local patch (`Users.tsx:75`) | toast "Status updated" |
| tenant picker change in create (`Users.tsx:256-257`) | none | keep | picker-internal | nothing |

No stale dependent was found and no cascade reset was observed, which is the honest negative result
here: the surface has only one cascade (search) and it recomputes its four aggregates. The defect in
this matrix is the announcement column, which is empty in all six rows.

## 6. Matrix 5 — surface pattern: controls, data views, flows, notifications

Verdicts: `pass` (layer or rule satisfied), `violation`, `n/a` + why, `[NOT CHECKED: …]` retained in
the table. Every row carries its citation.

### Data views

| Rule (source) | Verdict | Citation / note |
|---|---|---|
| SC 1.3.1 real table headers, table labelled | partial | `th` present (`DataTable.tsx:32`) = pass; no `caption`/`aria-label`, no `scope="col"` (`DataTable.tsx:27-33`) = violation |
| `aria-sort` on the sorted column | n/a | no sortable column exists; server order is fixed (`db.rs:492`) — itself a missing capability (F17) |
| Editable cells make it a grid | pass | rows hold no widgets (`Users.tsx:121-126`) |
| `aria-rowcount`/lazy loading, position restored | n/a | no virtualization; but Back from a detail view also cannot exist (no route per user) and the panel position is the list's (`Users.tsx:113-127`) |
| SC 1.4.10 one-direction scroll at 320 px, table in its own container | pass (container) / [NOT CHECKED: no running app] for the measurement | `table-container` wrapper (`DataTable.tsx:27`) is the containment; 320 px reflow was not measured |
| Pagination marks the current page, one-page pager hidden | violation | no pager at all on Users (`Users.tsx:113-127`); the sibling uses it (`ThreatIntel.tsx:247,324,407`, `Pager.tsx:12-13`) — F5 |
| Content: captions/headings short nouns, first column human-readable, headers visible | pass | `Name/Email/Role/Tenant/Status` (`Users.tsx:110`), first column `full_name` (`Users.tsx:121`) — but `'—'` when empty, and the identifier is then only the 8-char uuid in the panel (`Users.tsx:135`) |
| Filters discoverable, active state visible in results | violation | the search box is the only filter and no results view states the query (F16) |
| Detail view `dl`, every field a value or "not provided" | violation | info rows are `div`s with `borderBottom` (`Users.tsx:144-171`), not `dl`/`dt`/`dd` (F18) |
| Scroll region says it scrolls | [NOT CHECKED: no running app] | desktop panel is `overflow-y-auto` (`DetailPanel.tsx:16`) |
| Long text strategy | [NOT CHECKED: no running app] | no truncation/clamp on `email`/`tenant` cells (`Users.tsx:122,124`) |

### Controls

| Rule (source) | Verdict | Citation / note |
|---|---|---|
| APG combobox semantics on the tenant picker (`role`, `aria-expanded`, `aria-controls`, `aria-haspopup`, `aria-activedescendant`) | violation | a `div` with `onClick` and no role (`TenantSearchSelect.tsx:82-103`); popup is a plain `div` (`TenantSearchSelect.tsx:113-140`) — F12 |
| APG combobox keyboard (Down opens, Escape closes, Tab stays out) | violation | no `onKeyDown` anywhere in the picker; the trigger is not focusable (no `tabIndex`) — F12 |
| APG listbox roles on the option list | violation | plain rows/divs, no `role="option"`/`aria-selected` — F12 |
| Visible persistent label (never placeholder-only) | violation | search input: `placeholder` only (`AdminPrimitives.tsx:61-64`); `FormInput`/`FormSelect` render a `<label>` with **no `htmlFor`** and no `id` on the control (`FormElements.tsx:17-18,44-45`) so it names nothing |
| SC 1.3.5 scoped autocomplete on the user's own data fields | n/a | this form collects another account's data, so no token is required; `off` is browser-default here |
| One required/optional convention | violation | `FormInput` supports `required` (`FormElements.tsx:17`) and Users passes it nowhere (`Users.tsx:248-256`), so nothing marks the three server-required fields — F9 |
| APG disclosure for show/hide | n/a | no disclosure control exists |
| APG tabs | n/a | none on this surface |
| Conditional reveal reveals a question and announces it | violation | the picker's search input replaces the trigger only after a mouse click (`TenantSearchSelect.tsx:94-99`), announced nowhere |
| Pickers: text entry alongside the calendar; free text plus known list as a combobox | pass (text entry with a known list) | `TenantSearchSelect.tsx:94-99` — the pattern is right, the semantics are missing |
| SC 2.5.8 target size 24×24 | pass | role buttons/status buttons are `py-1.5`/`py-2.5` full-text targets (`Users.tsx:185-190,207-216`); the icon-only panel close (`DetailPanel.tsx:33`) has no measured box `[NOT CHECKED: no running app]` |
| SC 2.4.7 / 1.4.11 visible focus | [NOT CHECKED: no running app] | inline `style` colours only; `form-input` class focus style lives in CSS not read here |
| SC 1.4.3 contrast, no colour-only state | partial | every state is also a text label (`Users.tsx:126,215`) = pass; the ratio of the grey `rgba(23,30,41,0.25)` placeholder (≥4.5:1?) is `[NOT CHECKED: no running app]` |

### Validation and errors

| Rule (source) | Verdict | Citation / note |
|---|---|---|
| Submit-time validation, values kept, server-side present, native validation suppressed | pass (values kept, server validates `admin.rs:907-919`) / open (no `novalidate` anywhere; no client validation at all) | `Users.tsx:248-256` |
| SC 3.3.1/3.3.3 item identified, correction described in text | violation | the only channel is a toast with the raw server string (`Users.tsx:52`); `FormInput`'s `error` prop is never used (`FormElements.tsx:26`) — F9 |
| Association: `aria-describedby`, same wording in summary and field, summary moves focus | violation | no summary, no `aria-describedby`; label not bound (`FormElements.tsx:17-18`) — F9 |
| Error summary at the top naming what went wrong | violation | none — F9 |

### Flows

| Rule (source) | Verdict | Citation / note |
|---|---|---|
| One question per page, unique heading, back + Continue | n/a | create is a single modal, not a multi-page flow |
| Check-your-answers: pre-populated on return, Change links, submit names its action | partial | create does not pre-populate on reopen because it never clears either (F11); submit is labelled "Create User" (`Users.tsx:266`) |
| Task list status in text | n/a | none |
| SC 3.3.7 redundant entry | pass within the flow; violation across it | the same person's email is entered at create and then editable at edit (`Users.tsx:249,223`) with no cross-check |
| SC 3.3.4 destructive change reversible, checked or confirmed | violation | deactivate is one click, no confirmation, no undo (§F7) |
| Destructive confirmation names what is lost | violation | there is no confirmation at all — F7 |
| APG dialog (`aria-modal`, focus in/stays/returns, alertdialog focuses least destructive) | violation | `Modal.tsx:18-24` and `DetailPanel.tsx:14-16`: no role, no focus move, no trap, no Escape; the backdrop click closes (`Modal.tsx:18`) — F10 |

### Notifications

| Rule (source) | Verdict | Citation / note |
|---|---|---|
| SC 4.1.3 changes without focus are programmatically determinable | violation | no `aria-live`/`role="status"` in the app (`grep -rn 'aria-live\|role="status"' admin/frontend/src` → 0 files); list count, stats and "Saved" live only in a toast or a heading — F15 |
| Whole status string announced, end of wait announced | partial | toasts come from sonner (its own region); the table's own loading state (`DataTable.tsx:43-55`) never announces its end |
| Non-status changes stay out of live regions | pass | nothing is announced, so nothing is wrongly announced |
| Notification banner `role=region`, before h1, at most one, never replaces validation errors | n/a | no banner on this surface |

## 7. Findings, most severe first

Severity = 0-4 (frequency × impact × persistence), assigned as: 4 = hits every session and is a
security/lockout class defect, 3 = hits the common path, 2 = hits a specific state, 1 = cosmetic or
contract-hygiene. Each finding names one evidence class and carries the Prevent line.

**F1 — An `admin` can deactivate or demote any `super_admin`, including itself; nothing scopes a
platform admin to a tenant. Severity 4, `code`.** The panel gate accepts `super_admin|admin`
(`middleware.rs:36-38`, mounted `main.rs:440-443`); the deactivate handler never inspects the target
(`admin.rs:834-870`), and the role handler validates only the *requested* role
(`admin.rs:875-889`) — so `admin` → `PUT /role {"role":"viewer"}` against a `super_admin` id is
accepted and audited as a normal role change (`admin.rs:812`). Users carry `tenant_id`
(`db.rs:521-524`) while `LIST_FILTERED`/`COUNT_FILTERED` have no tenant predicate (`db.rs:482-500`),
so a tenant's `admin` reads and writes every tenant. SC-equivalent standard: authorization
(OWASP A01) rather than WCAG. **Prevent**: a handler test asserting 403 when the target's stored role
is `super_admin` and the actor's is `admin`, plus a "last super_admin" guard test — the pair must be
asserted together, since the write path and its checker drift in both directions.

**F2 — "Deactivated" does not end access; the session outlives the status change. Severity 4, `code`.**
The middleware validates the JWT and the role claim only (`middleware.rs:207-219`); it never reads
`is_active` and there is no denylist (`grep -n "is_active|revoked|token_version|denylist"
middleware.rs` → no match). Access tokens live 900 s (`auth.rs:463`); `/auth/me` returns
`is_active` (`auth.rs:585-590`) but neither the client hook (`useMe.ts:20-28`) nor any other layer acts
on it. The surface reports "Status updated" (`Users.tsx:75-77`) while the account can keep calling the
API until expiry (and refresh: `auth.rs:205`), which is the exact operation a SOC expects to be
immediate. **Prevent**: an e2e assertion that a request from a deactivated account's existing token
gets 401 within one access-token TTL — the check that fails on the pre-change commit.

**F3 — The detail panel is stale by construction: `GET /users/{id}` has no caller. Severity 3,
`code`.** The row object is stored whole in state (`Users.tsx:87-91`, `114-121`); `fetchUser` is
defined (`api/admin.ts:379-382`) and called nowhere (`grep -rn "fetchUser\b" admin/frontend/src` → its
own definition only), so the handler (`admin.rs:4468-4502`) is a dead endpoint and the panel can never
show anything the list has not already loaded — `last_login_at` and any server-side change are
invisible. **Prevent**: a component-state checklist entry "a detail view fetches by id" and an e2e
that mutates the user from a second session and asserts the panel reflects it.

**F4 — `super_admin` is offered as a role and always rejected. Severity 3, `code`.** The client builds
its role list as `availableRoles = isSuperAdmin ? ALL_ROLES : ROLES` (`Users.tsx:85`) with `ALL_ROLES`
including `super_admin` (`Users.tsx:17`), and offers it in the create select (`Users.tsx:252-253`) and
as a change-role button (`Users.tsx:179-190`). The server's assignable set excludes it
(`admin.rs:873`) and answers 400 "Invalid platform role" (`admin.rs:879-880`) for both routes — an
offer the system forbids, i.e. a dead control on every super-admin session. **Prevent**: one test that
asserts client list == server enum (a write path and a checker are two readings of one rule; pinning
each alone is what let this drift), and derive the list from the server instead of a second literal.

**F5 — No pagination, and the printed total is the page length. Severity 3, `code`.** The query is
fixed at `limit: 200` with no `offset` (`Users.tsx:44-48`), the server's correct `total` is returned
and dropped (`api/admin.ts:374-377`, `db.rs:494`) and the header prints `allUsers.length` as "users
across all tenants" (`Users.tsx:95`), with the four stat cards built from the same array
(`Users.tsx:101-104`). Above 200 users the number is simply wrong, and the 201st user is unreachable
at all. The repository's own convention for this kind of page is the opposite: `Pager` fed by
`data.total` (`ThreatIntel.tsx:247,324,407`, `Pager.tsx:14-28`). **Prevent**: an e2e assertion that the
header equals the API's `total` and that a pager appears above the page size; the assertion is on the
rendered number, not on the presence of a `Pager` import.

**F6 — Nothing in the table can be opened by keyboard. Severity 3, `code`.** Rows are `<tr>` with
`onClick` and no `tabIndex`, role or key handler (`Users.tsx:114-121`); `DataTable` renders whatever
children it is given (`DataTable.tsx:28-40`). APG's grid pattern and SC 2.1.1 both require the row to
be reachable and activatable; today the entire detail/edit/role/status surface is mouse-only. SC 2.4.7
compounds it (no focus state exists to be seen). **Prevent**: an e2e keyboard walk — Tab to a row,
Enter opens the panel — which fails on the current commit.

**F7 — One click deactivates an account with no confirmation, no object named and no undo. Severity 3,
`code`.** The button mutates directly (`Users.tsx:207-216`), the handler issues the UPDATE
immediately (`admin.rs:834-870`, `db.rs:515-516`) and nothing records a reason or a reversibility
window. SC 3.3.4 and the skill's destructive-confirmation rule require the lost object to be named and
the action to be checked or reversible. **Prevent**: an e2e that asserts a confirmation naming the
user's email, and that no `POST /deactivate` is issued before it is accepted.

**F8 — The create path has no delivery: the admin invents a password, the account is born inactive,
and the recipient is told nothing — while the sibling backend already has a single-use invitation
flow. Severity 3, `code`.** `CREATE_INACTIVE` hardcodes `is_active=false` (`db.rs:521-524`) and the
handler's own response says "User created (inactive). Activate after approval."
(`admin.rs:960-968`), but the surface collapses that to `toast.success('User created')`
(`Users.tsx:51`) and renders the new row exactly like a disabled account (`Users.tsx:126`). The
app backend holds `handle_create_invitation` and `workspace_invitations` with an expiry
(`app/backend/src/proxy/auth_api.rs:3095-3190`) — the capability exists in the product and no layer of
the admin Users area reaches it. This is the action's *end*: it succeeds in the database and fails the
user. → **proposal P-1** (its fix names a layer that does not exist here). **Prevent**: a contract test
asserting the create response's `is_active=false` is rendered as a distinct "pending activation"
state, not the generic inactive badge — the assertion that would have failed.

**F9 — Validation is invisible until submit and lands in a toast. Severity 2, `code`.** `FormInput`
supports `required` and `error` (`FormElements.tsx:13-31`) and the Users form passes neither
(`Users.tsx:248-256`); the server's rules — three required fields, password ≥8
(`admin.rs:907-919`) — are the first the user hears of it, via `toast.error` (`Users.tsx:52`). The
password field has no hint, no counter and no reveal control (`Users.tsx:250`), and the `<label>`
carries no `htmlFor` and the input no `id` (`FormElements.tsx:17-18,44-45`), so no error can be
associated even if one were rendered. SC 3.3.1/3.3.3/1.3.1. **Prevent**: an e2e that submits empty and
asserts a text message beside the field, a summary naming the item, and focus moved to the first
error.

**F10 — The modal and the side panel look modal and are semantically invisible. Severity 2, `code`.**
`Modal` is a positioned `div` with an overlay click-to-close (`Modal.tsx:18-24`); `DetailPanel` is the
same pattern (`DetailPanel.tsx:14-16`); neither has `role="dialog"`, `aria-modal`, an accessible name,
a focus move, a trap, or Escape (`grep -n "role=|aria-|Escape" Modal.tsx` → the close button only),
and the icon-only close controls have no accessible name (`Modal.tsx:52`, `DetailPanel.tsx:33`). APG
dialog requires all of those, including `aria-modal` only when outside content is truly inert — here
it is tabbable, so the correct fix is a real trap, not the attribute alone. **Prevent**: an e2e
asserting focus lands inside on open, Escape closes, focus returns to the invoker, and the close
control exposes a name.

**F11 — A sensitive draft is kept, an unsaved edit is dropped, and neither is announced. Severity 2,
`code`.** `form` is reset only in `onSuccess` (`Users.tsx:51`); the overlay close and Cancel
(`Users.tsx:244,261-262`) leave the typed password in component state, so reopening the modal shows
the previous attempt. Conversely, closing the panel (`Users.tsx:133`) discards an in-progress
profile edit silently. The skill's finding classes: nothing announces the discard, and the retention
is the inverse of what the flow needs. **Prevent**: an e2e that types into both forms, closes, reopens,
and asserts the create form is empty and the edit draft is either kept or explicitly warned about.

**F12 — The tenant picker is unreachable without a mouse. Severity 2, `code`.** The trigger is a `div`
with `onClick` and no `tabIndex` (`TenantSearchSelect.tsx:82-93`), the search `input` exists only while
open (`TenantSearchSelect.tsx:94-99`), the popup is a plain `div` of clickable rows with no
`listbox`/`option`/`aria-selected` (`TenantSearchSelect.tsx:113-140`), and the clear control is an
icon-only button (`TenantSearchSelect.tsx:108-111`). APG combobox/listbox is contradicted on every
clause including `aria-expanded`, which does not exist. Because this picker selects the required
`tenant_id` (`Users.tsx:256-257`), the create flow cannot be completed by keyboard at all. **Prevent**:
an e2e keyboard walk on the picker: Tab, Enter to open, Arrow, Enter to select, Escape to close.

**F13 — The module enum is labelled from two sources and validated by neither. Severity 2, `code`.**
The client owns seven ids with labels and descriptions (`TenantDetail.tsx:39-47`); the server takes
`body.get("modules")` and stores it as-is (`admin.rs:8441-8443`) with only a role check
(`admin.rs:8430-8436`). So the write path accepts values no surface can display and the surface can
offer values the server never confirms — the drift this repository has already shipped once. The
matrix-2 rule "one enum labelled from two sources" is violated in both directions. **Prevent**: a
single server-owned enum surfaced to the client, plus a validation test that an unknown module id is
rejected with 400.

**F14 — `GET /users/{id}/permissions` has no caller. Severity 2, `code`.** The client wraps only the
PUT (`api/admin.ts:922-925`); a search for the path across `admin/frontend/src` returns that one line,
and the readable DTO `UserPermissions` (`api/admin.ts:898-900`) is unused. The sibling surface seeds
its editor from a list-row field instead (`TenantDetail.tsx:393`). A route exists that no user can
reach, and the editor therefore edits a possibly stale value. **Prevent**: a route-vs-client parity
test that every `/api/v1/admin/users/*` route has a client wrapper and at least one call site.

**F15 — A privileged filter changes the table within 250 ms of typing and announces nothing. Severity
2, `code`.** The debounce is 250 ms (`Users.tsx:39-42`), the input has no accessible name
(`AdminPrimitives.tsx:61-64`) and there is no live region anywhere in the app
(`grep -rn 'aria-live\|role="status"' admin/frontend/src` → 0). SC 4.1.3 has no axe rule; the change is
programmatically undeterminable. A screen-reader operator cannot tell that the table they are reading
was replaced. **Prevent**: an e2e asserting the result count is announced with its context ("34 users
match …") and that the field exposes an accessible name.

**F16 — The four stat cards are page-local and change as the operator types, under a header claiming
"across all tenants". Severity 2, `code`.** All four are `allUsers.filter(...)`
(`Users.tsx:101-104`) over the truncated, search-filtered, 200-capped array (`Users.tsx:44-48`), so
"Total" is neither a total nor stable, and the filter's active state is invisible in the results view —
the skill's data-view rule. `/admin/stats` already carries `total_users` (`api/admin.ts:7`), so a
server aggregate exists. **Prevent**: an e2e asserting the stats come from the aggregate endpoint and
that an active filter is stated in the results view with its query.

**F17 — The table's own semantics are incomplete: no accessible name, no `scope`, no sorting.
Severity 1, `code`.** `DataTable` emits a bare `<table class="w-full text-[12px]">` and `th`s without
`caption`, `aria-label` or `scope` (`DataTable.tsx:27-33`), and the server's only order is
`created_at DESC` (`db.rs:492`), while the operator's daily questions ("who is inactive?", "who has
never logged in?") are unanswerable on this surface. SC 1.3.1. **Prevent**: a component test asserting
a caption/name and `scope="col"` on every header cell.

**F18 — Contract fields no view renders, and a detail view that is not a description list. Severity 1,
`code`.** `last_login_at` is selected (`db.rs:487`), returned by both endpoints (`admin.rs:4454`,
`admin.rs:4493`) and typed (`types/admin.ts:94`, `api/admin.ts:37`) but rendered nowhere
(`grep -rn last_login_at admin/frontend/src` → the two type lines); `total` is likewise dropped
(F5). The panel's key/value rows are `div`s (`Users.tsx:144-171`), and the tenant falls back to a
truncated uuid (`Users.tsx:124,150`) with the user identifier itself only 8 characters in the panel
subtitle (`Users.tsx:135`), so no surface shows a complete identifier to copy. **Prevent**: a
contract-view parity check (every DTO field is rendered or explicitly excluded, with the exclusion
listed), plus a `dl` for the detail rows per the skill's detail-view rule.

### Pass rows — where the layers agree (the control that shows the matrices were filled honestly)

| # | Agreement | Citation |
|---|---|---|
| A1 | Route, middleware and handler agree that only `super_admin|admin` reach any user route | `main.rs:440-443`, `middleware.rs:36-38,68-81` |
| A2 | CSRF: the client echoes `X-CSRF-Token` on mutations and the middleware enforces it for cookie auth | `client.ts:24-38`, `middleware.rs:139-144,246-270` |
| A3 | Every mutating user handler writes an audit row with actor, role, action, target and details | `admin.rs:812,847,947,1001,4523,8450` |
| A4 | Password hashing is real and shared with login verification (Argon2id) | `admin.rs:928`, `password.rs`, `db.rs:533` |
| A5 | Role escalation below `admin` is refused on both sides: an `admin` cannot grant `admin` and the surface does not offer it to a non-super-admin | `admin.rs:881-886`, `Users.tsx:85` |
| A6 | Empty and loading states exist, and the empty state replaces the rows rather than sitting beside them | `DataTable.tsx:42-55`, `Users.tsx:111-112` |
| A7 | Mutations invalidate the list query, so the table converges with the server even where the panel state was patched optimistically | `Users.tsx:51,69,78` |
| A8 | Server errors are scrubbed of DB detail before reaching the admin client | `admin.rs:826-829` (call site), `handlers/mod.rs:16` (the alias), `error.rs:32-43` (the helper) |

## 8. Capability-change proposals

Two findings' fix lists name a layer that does not exist. Both are proposals, not screen
recommendations.

### P-1 — Deliverable account provisioning (required by F8)

| Heading | Content | Falsified by |
|---|---|---|
| Capability | a created account can receive a credential out of band and reach first login without an operator inventing and transmitting a password | a cited path that already sends an invitation or a set-password link to a created account (none: `grep -rn "invite\|smtp\|mailer" admin/backend/src` → 0) |
| Absence proof (`code`) | `db.rs:521-524` (`CREATE_INACTIVE` hardcodes `is_active=false`); `admin.rs:960-968` (response text admits pending approval); `Users.tsx:51` (the surface drops it); the invitation capability that exists does so in another backend: `app/backend/src/proxy/auth_api.rs:3095-3190`, `workspace_invitations` with `expires_at`. The failing input: panel create → recipient receives nothing | a cited admin-backend path that issues a single-use invitation or a set-password token for a created user |
| Contract delta | OpenAPI delta on `POST /api/v1/admin/users`: response gains `invitation_id`, `invitation_expires_at`, `is_active:false`; new `POST /api/v1/admin/users/{id}/invite` (`202`); permission rule: `admin` may invite `operator|viewer|api_user`, `super_admin` may invite `admin`; migration adds `user_invitations(id, user_id, token_hash, expires_at, consumed_at, created_by)` with a unique partial index on `user_id WHERE consumed_at IS NULL` | running the contract/compat checker (`buf breaking` for the SDL, the OpenAPI lint/`oasdiff` job) and getting green with no diff |
| Migration | expand: add `user_invitations` + nullable `users.invited_at`; migrate: backfill nothing (no historical invitations exist) and set `invited_at` on new rows only; contract: after the dated step **2026-12-01**, drop the admin-supplied `password` field from the create contract and make `POST /invite` the only entry path | a contract phase with no date |
| Rollout | flag `admin_user_invite` (boolean, OpenFeature, expected lifetime one quarter, owner: platform admin team); initial exposure: super_admin sessions only; abort threshold: invite→first-login conversion below 50% of panel creates in a 7-day window, or invite mail failure rate > 2% in 24 h; kill switch: turn the flag off (accounts stay creatable the old way) | an unmeasurable threshold, or a flag with no lifetime |
| Verification | fails before / passes after: a test asserting a created account can complete a first login without an operator-typed password, and that `POST /invite` on an already-invited user returns 409 | a check that also passes on the pre-change commit |
| Reversibility | writes `user_invitations` rows and `users.invited_at`; restore step: `DELETE FROM user_invitations WHERE created_at >= :deploy_ts` and `UPDATE users SET invited_at = NULL` — no credential is destroyed, so the migration is reversible | data written with no restore step and no label |
| Decision | ADR `admin-user-provisioning`: context (password invention + silent pending state), decision (single-use invitation, mirroring `workspace_invitations`), status **proposed**, consequences (a mail dependency enters the admin path; the pending state becomes a first-class status); supersedes nothing | an ADR without a status |
| Appetite | time box 2 weeks; out of bounds: SSO/SCIM onboarding of the same users, and any change to the app-frontend login page; at the end of the box, ship the flag-off path (invitation recorded, mail sent by a manual operator step) or drop it | no box, or an implicit extension |

### P-2 — Sessions that end when the account does (required by F2)

| Heading | Content | Falsified by |
|---|---|---|
| Capability | revoking an account's access takes effect within seconds of the status change, for every token it already holds | a cited middleware path that reads `is_active` or a token version on each request (`middleware.rs:207-219` reads neither) |
| Absence proof (`code`) | `middleware.rs:104-226` validates signature, `typ`, `aud`, `iss` and the role claim only; no `is_active`, no denylist, no token version (`grep -n "is_active\|revoked\|token_version\|denylist" middleware.rs` → 0); `auth.rs:463` sets a 900 s access TTL; `auth.rs:205` a 7-day refresh | a cited path that refuses a valid-signature token for a deactivated user |
| Contract delta | migration `ALTER TABLE users ADD COLUMN token_version int NOT NULL DEFAULT 0`; `AdminClaims` gains `tv: int`; both token mints add it (`auth.rs:463`); the middleware compares it against a cached `users.token_version` read (≤30 s TTL); `POST /deactivate` and the role route increment it | running the auth contract test suite green with no schema/JWT diff |
| Migration | expand: add the column with a default and start minting `tv` (old tokens without `tv` are treated as `tv=0`, which is correct for every existing row); migrate: a one-off `UPDATE users SET token_version = token_version` is unnecessary, so no backfill jobs; contract: after **2027-01-15**, reject tokens without `tv` | a contract phase with no date |
| Rollout | flag `admin_token_version_check` (boolean, OpenFeature, lifetime one quarter, owner: platform admin team); initial exposure: internal operators; abort threshold: 401 rate on admin routes above 1% of requests in a 10-minute window (measured from `metrics_request_counter`, `main.rs:580-583`); kill switch: flag off restores today's behaviour | an unmeasurable threshold, or a flag with no lifetime |
| Verification | fails before / passes after: a test that deactivates a user holding an unexpired access token and asserts the next request is 401; on the pre-change commit it returns 200 | a check that also passes on the pre-change commit |
| Reversibility | writes `token_version` increments only; restore step: `UPDATE users SET token_version = 0` re-enables the old behaviour while the flag is off — the only forced effect is that live sessions log in again | one-way door with no restore step — does not apply here |
| Decision | ADR `admin-session-revocation`: context (deactivation is cosmetic for ≤15 min, and 7 days via refresh), decision (per-user token version checked in the middleware), status **proposed**, consequences (a DB or cache read on every admin request; a cache staleness bound that must be stated); supersedes nothing | an ADR without a status |
| Appetite | time box 1 week; out of bounds: app-backend token semantics and any push-based revocation channel; if the box ends, ship the flag with a 30 s cache and one metric, or drop it | no box, or an implicit extension |

A reviewer's five absences, checked: no capability is claimed without a `code` finding (F8→P-1,
F2→P-2); each proposal carries a rejectable artifact (OpenAPI/schema diff + a checker, a flagged
migration); both schema-touching steps name expand/migrate/contract with a dated contract step; both
flags name a type, a lifetime, an owner and an abort threshold; both contract changes carry an ADR with
a status and a pre/post check pair.

## 9. Triage

| Feature slice | Call | Metric, threshold, timeframe, action |
|---|---|---|
| List + search (rows 1, 10) | **fix** | header count == API `total` for 100% of loads, and 0 unfindable users above 200 rows, within 2 weeks; if the fix slips, cut `limit: 200` to the server default so the number stops lying |
| Detail panel (rows 2, 4, 5) | **fix** (F3, F6, F10, F11, F18) | keyboard-only walkthrough completes view → edit → role change in one attempt, within 2 weeks; failure keeps the ticket open and blocks the invite work |
| Create + provisioning (rows 3, 7) | **bet** (P-1) | invite→first-login conversion ≥ 80% of panel creates within a 30-day window, measured on the new events; if below 50% in 7 days after launch, kill the flag and revert to the current path |
| Deactivate / activate (rows 6, 7) | **fix + bet** (F1, F2, F7) | median minutes from deactivate to last accepted request ≤ 1 within 2 weeks of P-2 landing; if the check cannot be instrumented, the fix is the confirmation + audit reason and the revocation stays open |
| Module permissions in the Users area (rows 8, 9) | **cut** from this feature | the capability lives on the tenant surface; the Users area keeps no copy. Cut is reversible: add the read view when `GET /permissions` gains a caller |
| Audit trail and CSRF on this feature's mutations (A2, A3) | **keep** | 0 unlogged mutations of the five audited actions and 0 CSRF-exempt mutations over the next two quarters; any new mutation route with no `audit_admin_action` call and no `X-CSRF-Token` requirement reopens the decision |

No row of Matrix 1 is left without a call: 1 and 10 sit in the first slice, 2/4/5 in the second, 3 and 7
in the third, 6 and 7 in the fourth, 8 and 9 in the cut, and the audited mutation set in the keep. The
pass rows of §7 are agreements *inside* slices that still carry findings, which is why only the
audit/CSRF slice is called `keep`.

## 10. Coverage — rows checked, rows not, and what would change the conclusion

| Matrix | Rows | Checked | `[NOT CHECKED]` cells | Why |
|---|---|---|---|---|
| 1 capability | 10 | 10 | 0 (two cells partial: rows 4/6 authorization) | all layers are readable in source |
| 2 field contract | 12 | 12 | 0 | ditto |
| 3 flow / step | 9 | 9 | 0 | ditto |
| 4 interaction dependency | 6 | 6 | 0 (the "announced" column is uniformly empty by observation) | ditto |
| 5 surface patterns | 39 | 33 | 6 | 6 rows carry a `[NOT CHECKED]` cell: 320 px reflow, target box, focus ring, contrast ratio, scroll affordance, long-text clipping — all need a rendered screen. Verdict split over the 39 rows: 8 pass, 4 partial, 16 violation, 8 n/a, 6 not checked |
| 5 rendered read (widths, colour scheme, blur/grayscale) | — | 0 | all | no running app this arm |

What would change these conclusions: a rendered read at ≥1440 px and 320 px (it could confirm or
refute `[NOT CHECKED]` cells in §6 and would add `ui-observed` findings, especially column clipping in
the 520 px panel); an axe-core run (its `target-size` rule is disabled by default and it has no rule at
all for SC 1.4.10, 2.4.7, 3.3.1, 3.3.3 or 4.1.3, so it would not move F7, F9, F15 or the focus rows);
a live API session against a seeded database (it would turn F1, F2 and F4 from code readings into
`behaviour` findings, and would test the `ILIKE` search for the known Turkish-casefold weakness —
untested here: `db.rs:484-489` uses `ILIKE`, which under a `C` collation misses `İ/ı` pairs, but no
seeded data was available to demonstrate it, so it is not claimed as a finding).

What was not looked at: the other fifteen admin pages (except `ThreatIntel`'s pager and
`TenantDetail`'s UsersTab, read only as the sibling standard and as the shared permission surface);
the app-frontend login page and the invitation flow's own UI; the SQL migrations directory; the nginx
config; every runtime state (no server was started). Every citation above is a direct file read of the
aibim-app working tree at HEAD `a6e47df` (the only modified file, `admin/frontend/CLAUDE.md`, is not
cited), not a graph query: the code-graph index the session reported is behind its own repo's HEAD, so
no finding here rests on a graph answer.
