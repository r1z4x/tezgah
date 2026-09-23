# Admin Users area — feature coherence audit (E5, baseline arm)

Repo: `/Users/rizax/Projects/aibim-app` (Rust axum + sqlx backend `admin/backend`, React 19 + Vite SPA
`admin/frontend`). Scope: the admin Users area — routes, handlers, authorization, queries, and the
React page + API client. Non-goals: the other fifteen admin pages, except where they share a
component or a route family with users (TenantDetail's user table shares the permissions route family
and the `updateUserRole` client function; that sharing is in scope).
Method: source-only audit, plus the coherence pass (`feature-audit` matrices) required when the ask is
one feature. No build, no Docker, no app launch — the contract fixes the evidence surface to source.
Rater count: **1**. Every finding below carries exactly one evidence class and one citation.

---

## 1. Measurement readiness — can we see this at all?

Partly. One of the five axes is observable from source, one is observable only in principle, three are not:

| Surface | Observable? | Evidence |
|---|---|---|
| Product behaviour (ratios over time) | **No.** No analytics, no event stream for the Users area. `/metrics` exists but has no user-management counter at all — `AdminMetrics` holds `login_attempts_total`, `login_failures_total`, `api_key_*`, `tenant_created_total`, `audit_write_failed_total`, `http_requests_total` and nothing else (`admin/backend/src/metrics.rs:45-78`). | `code` |
| Admin mutations (audit trail) | **Yes, in the DB.** All six mutating user handlers call `audit_admin_action` (`handlers/admin.rs:54`; call sites `:801`, `:846`, `:952`, `:990`, `:4517`, `:8447`). The *ratio* audited/mutations is a `behaviour` metric I could not compute — no DB access, no running system. | `code` |
| Running UI (usability axis) | **No.** The contract forbids starting the app; no `ui-observed` class is claimed anywhere in this artifact. Everything in §6 is a source-read state-matrix gap, not a screen reading. | — |
| Intended-vs-implemented | **Yes**, both sides cited, §7. | `code` |
| Competitor artifacts | **No.** Not produced, §8. | — |

First finding: **the Users feature is only observable through one surface (audit rows), and only if the
auditor can read the database.** "We cannot see the success of this feature from outside" (F13).

## 2. Objective and the Goal → Signal → Metric chain

Goal: an admin can manage platform accounts without being able to lock the platform out.
Signal: every user mutation is authorized against actor *and* target, and is audited.
Metric (defined but **unmeasurable today**): `authorized_mutations / attempted_mutations`, window =
all-time, numerator/denominator both from the audit table. It is not derivable from `/metrics`.
Raw counts are refused; a `behaviour` row cannot be written from this source-only read, and none is.

## 3. Opportunities (needs, not features) and candidate solutions

O1 *(need)* "When I demote or disable one account I must not be able to remove the last admin."
O2 *(need)* "When a control is offered to me it must be one the server will accept."
O3 *(need)* "When a list is truncated I must be able to tell, and get the rest."

Candidate solutions per opportunity, against the pre-stated criterion *"the change closes the need at
the layer that owns the rule, with no new layer"*:

| Opportunity | S1 | S2 | S3 | Winner on the criterion |
|---|---|---|---|---|
| O1 | target-side guard in the handler (`admin_user_role`/`admin_user_deactivate`) | guard in SQL (`UPDATE_ROLE ... WHERE role <> 'super_admin'`) | guard in the UI (hide the button) | S1 — the route layer already reads `claims` and the target; the DB stays a dumb writer, and the UI layer cannot be trusted for authorization |
| O2 | single role list served by the API | client list narrowed to `ADMIN_ASSIGNABLE_ROLES` | per-actor list computed and compared server-side | S2 is the minimum that removes the false affordance; S1 is the durable one (a second reading of the rule cannot drift if there is only one) |
| O3 | render `total` + a pager (client change only) | cursor pagination (route + SQL + client) | raise `limit` to 500 | S1 — `total` is already returned (`admin.rs:4447`); the need is disclosure, not capacity |

## 4. Risks, each with the cheapest falsifying test

| Class | Risk | Cheapest test |
|---|---|---|
| Feasibility | an `admin` demotes a `super_admin` and the platform loses its last one (F2) | one handler test: actor `admin`, target a row with `role='super_admin'`, assert 403 |
| Feasibility | the role UI offers `super_admin` and always 400s (F3) | one UI-state assertion on `availableRoles` for a `super_admin` session |
| Value | we cannot tell whether admin user operations work (F13) | read the audit table for two weeks and compare against `http_requests_total` for the same routes |
| Usability | a 403 and an empty tenant look identical (F1, F7) | `browser_route` the list to 403 and re-read the tree (blocked by the contract's no-launch rule) |
| Viability | `admin_get_user_permissions` has no client caller (F10 note) | grep the SPA for the route — already done, no caller |

## 5. Coherence pass — matrices

### 5a. Capability matrix (action × layer)

| Action | SQL layer | Route layer | UI layer | Verdict |
|---|---|---|---|---|
| list + search | `LIST_FILTERED` `db.rs:482-492` | `GET /users` accepts `limit/offset/search`, `admin.rs:4394-4408` | search box `Users.tsx:107`, `limit` pinned at 200 `Users.tsx:46` | **disagreement** — offset exists, no UI uses it (F6) |
| count | `COUNT_FILTERED` `db.rs:494-501` | returned as `total`, `admin.rs:4447` | **dropped**, `Users.tsx:83,101-104` | **disagreement** (F6) |
| create | `CREATE_INACTIVE` `db.rs:521-524` | `POST /users`, validates required + ≥8, `admin.rs:892-926` | modal, no client validation, `Users.tsx:244-266` | **disagreement** (F8) |
| edit profile | `UPDATE_PROFILE` `db.rs:508-510` | `PUT /users/{id}`, **unvalidated** `admin.rs:4505-4515` | edit mode, `Users.tsx:221-236` | **disagreement** (F4) |
| change role | `UPDATE_ROLE` `db.rs:512-513` | `PUT /users/{id}/role`, validated + role-gated `admin.rs:789-802` | role buttons, `Users.tsx:196-215` | **disagreement** on the offered set (F3) |
| activate / deactivate | `ACTIVATE`/`DEACTIVATE` `db.rs:515-519` | `POST …/activate`, `…/deactivate` `admin.rs:835`, `:989` | toggle button, no confirm, `Users.tsx:207-216` | **disagreement** — no self/target guard, no confirmation (F2, F9) |
| module permissions | `user_permissions::UPDATE/GET` | `GET`+`PUT /users/{id}/permissions` `main.rs:337-341` | **only on TenantDetail** `TenantDetail.tsx:405-428`; GET has no client caller | **capability-change proposal**, not a screen fix: the Users feature owns the route but not the surface (F10) |
| delete user | none | none | none | absent at every layer — a cut, not a defect (see §9) |

### 5b. Field-contract matrix

| Field | DB | API in | API out | UI | Verdict |
|---|---|---|---|---|---|
| `email` | `users.email` | create: required; update: optional, **no format check** `admin.rs:4505-4511` | list + get (`:4440`, `:4478`) | create `:249`, edit `:223` | **drift** — `''` is accepted and written (F4) |
| `password` | `password_hash` Argon2id `admin.rs:929` | create only, ≥8 bytes `admin.rs:918-924` | never | create `:250`, no confirmation field | agreement (one UI field, one rule) |
| `full_name` | COALESCE on read `db.rs:483` | create + update | list + get | `:121` renders `—` when empty | agreement |
| `role` | `users.role` | `ADMIN_ASSIGNABLE_ROLES` = 4 `admin.rs:876` | list + get | `ALL_ROLES` = 5 `Users.tsx:11` | **drift** (F3) — three readings of one rule |
| `tenant_id` | `$5::uuid` | create: required `admin.rs:909` | in list + get | `TenantSearchSelect` emits an id or `''` `:256` | **drift on one route**: `/tenants/{id}/users` selects `tenant_id` and the handler reads a 5-tuple, dropping it (F12) |
| `is_active` | column | never set directly; `ACTIVATE`/`DEACTIVATE` only | list + get | badge + toggle | agreement |
| `created_at` | `::text` | — | list + get | rendered `:169` | agreement |
| `last_login_at` | `::text` | — | list + get `admin.rs:4441,4486` | typed `api/admin.ts:37`, **rendered nowhere** | **dead field in the view** (F12) |
| `permissions.modules` | JSON blob | `body["modules"]` stored as-is `admin.rs:8438-8440` | get | client vocabulary of 4 `TenantDetail.tsx:39-42` | **drift** — unvalidated write path (F10) |

### 5c. Flow / step matrix (cognitive walkthrough, source-read)

| Step | Q1 right effect | Q2 notice | Q3 associate | Q4 progress | Finding |
|---|---|---|---|---|---|
| find a user | yes | yes (`SearchInput`) | yes | yes (250 ms debounce, table) | none — walkthrough pass 1 clean |
| create a user | yes | yes | yes | **no** — no required markers; failure arrives as a toast after submit `Users.tsx:248-266`, `:52` | F8 |
| deactivate a user | yes | yes | yes | **no** — no confirmation for an audited destructive action, unlike `TenantDetail.tsx:319` which confirms a key revocation | F9 |

### 5d. Interaction-dependency matrix

| Interaction | Depends on | Same layer? | Verdict |
|---|---|---|---|
| role buttons shown | `me.role` read through `useMe`, 5-minute staleTime (`hooks/useMe.ts:26`) | yes, but stale | a role changed by another admin leaves the wider button set on screen for up to 5 min (F3 amplifier) |
| role buttons disabled | `active \|\| roleMut.isPending` `:212` | yes | agreement |
| toggle button disabled | `toggleMut.isPending` `:208` | yes | agreement — no double-fire |
| detail panel after a mutation | local `setSelectedUser` patch `:57-60, 66-70, 76-79`, never re-read from the refetched list | yes | judgement, low: panel and table can diverge if the server ever normalizes a write |
| nav item visibility | static `NAV_SECTIONS` `AdminLayout.tsx:19-45`; `isSuperAdmin` computed at `:75` and not used for nav | **no** | **disagreement** (F1) |

### 5e. Surface state matrix (source-read; `ui-observed` NOT claimed)

| Component | States that exist | States that do not exist |
|---|---|---|
| list request | loading (`DataTable isLoading` `:111`), empty (`isEmpty`/`emptyText` `:111`) | **error**, **permission-denied**, offline, partial — `useQuery` destructures only `{data, isLoading}` `:44` (F7) |
| table | default, row-hover, row-selected `:118` | skeleton, long-text/overflow policy for a long email or tenant name |
| create modal | open, submitting (`Creating…` `:266`) | field-level error, invalid state, disabled-until-valid (F8) |
| edit mode | default, saving (`Saving…` `:229`) | field-level error |
| role buttons | default, active, disabled, pending | — |
| activate/deactivate | default, pending (`Updating…` `:215`) | confirmation, error-undo |
| search input | default, debounced | no results message is the table's `emptyText` only |
| pagination | **absent at every state** | all (F6) |

## 6. Usability axis

Not produced as specified. The method requires the running app through `analyze-app` (view tree, then
the rendered screen, blur and grayscale tests, breakpoints, dark mode, a pinned axe-core sweep) and 3-5
independent raters; the contract for this measurement fixes evidence to source and forbids launching
the app. Consequences, stated in the method's own terms:

- No `ui-observed` finding exists in this artifact. The §5e state matrix is read from source, so it
  evidences *that a state is not implemented*, never *how a screen behaves*.
- Contrast, target size, focus order, hierarchy and rhythm are **not claimed at all** — they need
  `browser_evaluate` or a screenshot, and neither was run.
- WCAG 2.2 level claimed: **none**. No axe-core sweep was injected, so nothing is said about A or AA.
- Rater count 1, single pass: the method says a single rater is "too unreliable to be trusted" for
  severity, so every severity below is a floor, not a mean.
- Nielsen heuristic findings are therefore marked `judgement` where they would otherwise be
  `failure`; the two `failure`-grade items (F1, F7) are reproducible from source (a 403 renders as an
  empty list — deterministic given `:44-47` and `:111`).

## 7. Feasibility — intended vs implemented, both sides cited

| Intended (documented) | Implemented | Gap |
|---|---|---|
| `admin.rs:788` "Admin can assign operator/viewer/api_user. **Only super_admin can assign admin/super_admin.**" | `ADMIN_ASSIGNABLE_ROLES = ["admin","operator","viewer","api_user"]` `admin.rs:876`; `super_admin` rejected for every actor `admin.rs:864-870` | yes — `super_admin` can never be granted through this route, comment says otherwise (F3) |
| `main.rs:229` "Admin routes (behind platform admin middleware)" | `require_admin_access` mounted once over the whole group `main.rs:440-443`, gate is platform-only `middleware.rs:68-79` | no gap at the route layer; the gap is that the SPA shell admits enterprise roles (F1) |
| `admin.rs:4393` "list all users (paginated, with tenant name)" | SQL is paginated `db.rs:482-492`; the only client calls it with `limit: 200`, `offset` never sent | yes — pagination exists at one layer only (F6) |
| `admin.rs:892` "create an inactive user (pending approval)" | `is_active = false` hard-coded in SQL `db.rs:521-524` | no gap — agreement |
| `admin_dto.rs:17-23` "All five DTOs here use `deny_unknown_fields` … only the `deny_unknown_fields` gate and the range checks are new" | the user routes use one DTO (`UserRoleUpdateReq`) and **two raw `serde_json::Value` bodies** (`admin_create_user`, `admin_update_user`) | partial — the doc's scope ("five DTOs") is honest, but the Users feature is half-covered (F4, F10) |

## 8. Competitive axis

Not produced. A teardown needs a comparison basis, a named representative version and a read date per
competitor fact (the method's own rule), and no competitor artifact was fetched in this session. Any
statement here would be an `external` finding with no URL — that is a question, not a finding.
What would produce it: pick a basis (e.g. "admin user-management actions before an audit row exists"),
compare against one representative build of a comparable platform's admin console, and record the date.

## 9. Triage

| Feature / capability | Verdict | Deciding metric | Threshold | Timeframe | Action | Owner |
|---|---|---|---|---|---|---|
| User list + search | **fix** | rendered count vs `total` (`admin.rs:4447`) | any tenant where `total > 200` makes the header wrong | 30 days | render `total`, add a pager (`offset` already accepted) | unnamed (no owner is recorded for this area in the repo; the metric names who should take it) |
| Create user | **fix** | client-side validation exists? | zero required-field validations today | 30 days | add required/length guards; keep the server rule as the authority | unnamed |
| Edit profile | **fix** | number of distinct email-validation rules in the feature | > 1 (F4) | 30 days | reuse the typed-DTO pattern already in `admin_dto.rs` | unnamed |
| Role change | **fix** | one role list or three | > 1 (F3) | 30 days | API serves the assignable set; client renders it | unnamed |
| Activate / deactivate | **fix** | self/last-admin lockout reachable? | reachable today (F2) | 14 days | target-side guard + confirmation | unnamed |
| Module permissions on the Users page | **the route stays, the surface is not built here** | any client caller for `GET /users/{id}/permissions` | 0 callers today | — | do not build a second permissions editor; if the Users page needs it, move the TenantDetail panel rather than duplicate it | unnamed |
| Delete user | **cut (as-is)** | — | — | — | deliberate: no delete route and no UI; deactivation is the audited lifecycle. Recorded as a cut so it is not re-proposed as missing | — |
| Bulk actions / CSV export | **bet** | admin minutes per account change | only worth it above ~50 accounts changed per week | 90 days | instrument first (F13); build only if the audit table shows the volume | unnamed |

Kill criteria: if the fix set is not taken, the pre-decided action is to leave the area as-is and
record it as accepted risk; the metric that would reverse that is any audit row whose actor is an
`admin` acting on a `super_admin` row (F2's failure signal).

## 10. Findings, most severe first

Severity = frequency × impact × persistence, on the 0-4 scale. `failure` = reproducible from the cited
source; `judgement` = a heuristic read in context, single pass.

| # | Sev | Kind | Class | Finding | Citation |
|---|---|---|---|---|---|
| F1 | 3 | failure | `code` | **Nav and route authorization disagree, and the page cannot express it.** An enterprise delegated admin can sign in to the panel (`is_canonical_admin_panel_role` admits the seven enterprise roles, `auth.rs:429`; the panel-wide role set is `is_admin_panel_role`, `middleware.rs:44-58`) and sees the static `Users` nav item (`AdminLayout.tsx:31`; `NAV_SECTIONS` at `:19-45` is not filtered by role although `isSuperAdmin` is computed at `:75`), but every `/api/v1/admin/users*` route sits under `require_admin_access`, which is platform-only (`main.rs:440-443`, `middleware.rs:68-79`, `:209-214`). The 403 lands in a page that destructures only `{data, isLoading}` (`Users.tsx:44-47`) and renders `data?.users ?? []` with `emptyText="No users found"` (`:83`, `:111`), so a refused request is displayed as "0 users across all tenants / No users found". | `main.rs:440-443`; `middleware.rs:44-58,68-79,209-214`; `auth.rs:429`; `AdminLayout.tsx:19-45,75`; `Users.tsx:44-47,83,111` |
| F2 | 3 | failure | `code` | **The role rule is checked against the actor and the requested role, never against the target.** `validate_platform_role_grant(actor_role, requested_role)` (`admin.rs:864-878`) is the only gate; the handler never compares the path `id` with `claims.user_id` (`admin.rs:789-802`), and `UPDATE_ROLE`/`DEACTIVATE` carry no target predicate (`db.rs:512-519`). So a platform `admin` can demote a `super_admin` to `viewer` (requesting `viewer` passes the gate) and can deactivate it, and any actor can deactivate itself. The one rule test exercises only the actor side (`admin.rs:8882-8888`). | `admin.rs:789-802,835-845,864-878,8882-8888`; `db.rs:512-519` |
| F3 | 2 | failure | `code` | **The UI offers a role the API refuses, and the handler's own comment states the opposite rule.** `ALL_ROLES` includes `super_admin` (`Users.tsx:11`) and is offered whenever the actor is a `super_admin` (`:30`, `:85`, `:196-215`); the server rejects `super_admin` for every actor (`ADMIN_ASSIGNABLE_ROLES` has 4 entries, `admin.rs:876-878`, 400 at `:864-870`) — while the doc-comment above the handler says "Only super_admin can assign admin/super_admin" (`admin.rs:788`). Three readings of one rule: server constant, client array, doc-comment. The client reading is strictly wider than the server's. | `Users.tsx:11,30,85,196-215`; `admin.rs:788,864-878` |
| F4 | 2 | failure | `code` | **Two sibling write paths in one feature: one validated, one raw.** `PUT /users/{id}` takes `Json<serde_json::Value>` and extracts `full_name`/`email` with no validation (`admin.rs:4505-4515`), while its sibling `PUT /users/{id}/role` uses the typed, `deny_unknown_fields`, length-validated `UserRoleUpdateReq` (`admin.rs:799-801`, `admin_dto.rs:133-138`). `UPDATE_PROFILE` guards `NULL` with `COALESCE` but not `''` (`db.rs:508-510`), and the edit form has no required/format guard (`Users.tsx:223`), so clearing the email field writes an empty string; login then matches `WHERE email = $1` (`db.rs:533-536`), which can never equal `''`. | `admin.rs:4505-4515`; `admin_dto.rs:133-138`; `db.rs:508-510,533-536`; `Users.tsx:221-236` |
| F5 | 2 | failure | `code` | **The same DB condition gets two different HTTP outcomes.** A duplicate email on create is mapped to 409 `CONFLICT` (`admin.rs:975-981`); the identical violation on update falls into the generic branch and returns 500 `Internal server error` (`admin.rs:4530-4536`) because `UPDATE_PROFILE` has no conflict branch and the handler reads no error class. A caller cannot distinguish "this email is taken" from "the server broke". | `admin.rs:975-981,4530-4536`; `db.rs:508-510` |
| F6 | 2 | failure | `code` | **The counts on screen are page-scoped and the payload's `total` is discarded.** The client pins `limit: 200` and never sends `offset` (`Users.tsx:46`); the header and all four StatCards derive from the loaded array (`:98-106`), while the server returns the filtered `total` from `COUNT_FILTERED` (`admin.rs:4443-4448`, `db.rs:494-501`). Above 200 users, or under any search, "N users across all tenants", Total, Active, Inactive and Admins are all wrong and nothing on screen says the list is truncated. Agreement row: `LIST_FILTERED` and `COUNT_FILTERED` share the same predicate verbatim (`db.rs:482-501`), so the count cannot drift from the list — the disagreement is only between the payload and the view. | `Users.tsx:46,83,98-106`; `admin.rs:4443-4448`; `db.rs:482-501` |
| F7 | 2 | failure | `code` | **The error and permission-denied states do not exist for the list.** `useQuery` is read as `{data, isLoading}` with no `isError` (`Users.tsx:44-47`); `DataTable` is given `isLoading` and `isEmpty` only (`:109-111`). A failed fetch and a 403 both render the empty state (see F1). Loading and empty do exist, so this is a partial state matrix, not a missing one. | `Users.tsx:44-47,109-111` |
| F8 | 2 | judgement | `code` | **The create modal validates nothing on the client; every rule is server-side and surfaces as a toast.** Required `email`/`password`/`tenant_id` and the 8-character floor are enforced only in the handler (`admin.rs:907-926`); the three `FormInput`s and the tenant selector carry no required/length/format guard (`Users.tsx:248-256`, `:256`), the submit button is disabled only while pending (`:263`), and failures arrive as `toast.error` with no field association (`:52`). Judgement: the walkthrough's Q4 ("will the user see progress") is answered "no" for the failing path. | `Users.tsx:244-266,52`; `admin.rs:907-926` |
| F9 | 2 | judgement | `code` | **An audited destructive action on an individual account has no confirmation, while the same codebase confirms a lesser one.** Deactivate fires straight from the panel (`Users.tsx:207-216`); revoking an API key in the sibling page is wrapped in `confirm(...)` (`TenantDetail.tsx:319`). Two policies for destructive actions in one frontend. | `Users.tsx:207-216`; `TenantDetail.tsx:319` |
| F10 | 2 | failure | `code` | **The permissions write path stores unvalidated JSON, so the module vocabulary exists only in the client.** `admin_update_user_permissions` puts `body.get("modules")` into the JSON column unchanged, with no membership or type check (`admin.rs:8438-8445`); the only vocabulary is `AVAILABLE_MODULES` in the UI (`TenantDetail.tsx:39-42`) and the `UserPermissions` type (`api/admin.ts:898-900`). The GET sibling (`admin.rs:8477-8500`) has no caller in the SPA — `getUserPermissions` does not exist in `api/admin.ts` — so the read side of this capability is dead while the write side is unguarded. Same pattern as F4, one layer down. | `admin.rs:8424-8445,8477-8500`; `TenantDetail.tsx:39-42`; `api/admin.ts:898-900,922-925` |
| F11 | 2 | failure | `code` | **The suite pins a second reading of the role rule, not the rule.** `is_assignable_role` (`admin.rs:8780-8783`) and `requires_super_admin` (`:8785-8788`) exist only inside `mod tests` and are called by no production code; seven tests assert against them (`:8843-8879`, `:8905-8917`). The production rule is `validate_platform_role_grant` (`admin.rs:864-878`), pinned by a single test (`:8882-8888`). A change to `ADMIN_ASSIGNABLE_ROLES` fails none of the seven, because they read the same constant through a test-local wrapper. | `admin.rs:864-878,8780-8788,8843-8879,8882-8888,8905-8917` |
| F12 | 1 | failure | `code` | **Fields are fetched and typed but never surfaced, and one query's extra columns are silently dropped.** `/tenants/{id}/users` selects eight columns (`db.rs:469-472`) and the handler declares a five-tuple (`admin.rs:757-762`); sqlx's tuple `FromRow` reads by index with no column-count assertion (sqlx-core 0.8.6 `src/from_row.rs:326-341`), so `tenant_id`, `created_at` and `last_login_at` vanish with no error and no compile-time signal. Separately, `last_login_at` is returned by both `GET /users` and `GET /users/{id}` (`admin.rs:4441,4486`) and typed in the client (`api/admin.ts:37`), yet appears nowhere in `Users.tsx` — the column set is Name/Email/Role/Tenant/Status (`:110`). | `db.rs:469-472`; `admin.rs:757-762,4440-4441,4485-4486`; `api/admin.ts:37`; `Users.tsx:110` |
| F13 | 2 | failure | `code` | **The feature has no metric.** `AdminMetrics` carries no user-management counter (`metrics.rs:45-78`), so the only trace of a user mutation outside the DB is the audit row written by the handler (`audit_admin_action`, `admin.rs:54`; all six mutating handlers call it: `:801`, `:846`, `:952`, `:990`, `:4517`, `:8447`). Coverage of the audit call is 6/6, which is an agreement row; the ratio audited/mutations is a `behaviour` metric and was **not** measured — no DB access, no running system. | `metrics.rs:45-78`; `admin.rs:54,801,846,952,990,4517,8447` |
| F14 | 1 | judgement | `code` | **The placeholder understates the predicate.** "Search by name or email..." (`Users.tsx:107`) while `LIST_FILTERED` also matches `role`, the tenant name and `user_id` (`db.rs:482-492`) — a search that silently spans three more fields than the UI promises, which is a surprise for an operator who types `admin` expecting a name match. | `Users.tsx:107`; `db.rs:482-492` |

Evidence class summary: `code` 14, `ui-observed` 0, `behaviour` 0, `user-verbatim` 0, `external` 0.

Agreement rows (recorded because an agreement is evidence too): the create payload's five fields match
the form and the handler (`Users.tsx:36`, `api/admin.ts:384-387`, `admin.rs:895-905`); the role body
`{role}` matches `UserRoleUpdateReq` exactly, unknown fields 422 (`api/admin.ts:394-396`,
`admin_dto.rs:133-138`); `LIST_FILTERED`/`COUNT_FILTERED` predicate parity (`db.rs:482-501`); CSRF
double-submit is wired on both sides (`client.ts:29-34` sends `X-CSRF-Token` on POST/PUT/PATCH/DELETE,
`middleware.rs:136-144,246-260` requires it for cookie auth); all six mutating handlers audit
(`admin.rs:801,846,952,990,4517,8447`); `ok()`'s `{success,data}` envelope and the client's `unwrap()`
agree (`admin.rs:29-32`, `api/admin.ts:321-326`).

## 11. Recommendations and their references

| Recommendation | Reference (who already does it best) | What we adopt |
|---|---|---|
| R1 — put the target-side guard in the route layer (F2) | OWASP ASVS v4.0.3 §4.1.3 ("verify the principle of least privilege") — named as a standard, artifact read this session: no. **Stated as a standard, not as a cited artifact.** | an explicit actor-vs-target check before `UPDATE_ROLE`/`DEACTIVATE`, plus a test asserting the pair's two readings agree |
| R2 — one source for the assignable-role set (F3, F11) | the repo's own pattern: `admin_dto.rs:17-23` makes the typed DTO the single reading | the API serves the set; the client renders it; the test-only duplicate (`admin.rs:8780-8788`) is deleted or pointed at the production rule |
| R3 — validate the two raw bodies the way the DTO path already does (F4, F5, F10) | same in-repo pattern | extend `admin_dto.rs` to the create/update/permissions bodies; map the unique violation to 409 in both write paths |
| R4 — render `total`, add a pager (F6) | the sibling endpoint `GET /agents/mcp`, whose doc-comment promises "`total` is the full count" (`admin.rs:8505-8506`) and whose handler computes it from `COUNT_ALL_MCP_AGENTS` (`admin.rs:8529`) | pass the already-returned `total` to the header and StatCards; send `offset` |
| R5 — state matrix completion (F7, F1) | the same page's own loading/empty handling (`Users.tsx:111`) | add error and permission-denied branches so a 403 is not an empty tenant |

## 12. What this analysis did not look at

Not looked at, and what would change the recommendation:

1. **The running app** — no view tree, no rendered screen, no breakpoints, no dark mode, no blur or
   grayscale test, no axe-core sweep, no `PerformanceObserver`. Consequence: no `ui-observed` finding
   and no contrast/target-size/focus-order claim exists here. Running the app would add the whole
   usability axis and could raise or kill F8/F9 (severity only).
2. **The database and its schema** — `db/migrations/` was not read, so the unique constraint on
   `users.email` and the default of `users.role` are assumed from the SQL statements alone; F5's 409/500
   asymmetry is argued from the handler's error mapping, not from the constraint's actual behaviour.
   Reading the migrations would confirm or kill F5.
3. **The audit table's contents** — F13's ratio was not computed; no `behaviour` finding exists. Query
   access would turn F13 from a coverage claim into a metric.
4. **TenantDetail's permissions panel in depth** — only the lines that share the users route family
   were read (`:39-42`, `:319`, `:346-350`, `:405-428`); its own coherence is out of scope.
5. **The other fifteen admin pages** — not read, so no cross-page generalization is claimed from the
   two confirm dialogs in F9.
6. **Tests that exercise these handlers** — the backend `tests/` tree was not read; F11 is a claim
   about the in-file test module only.
7. **Whether `admin_get_user_permissions` has a non-SPA caller** — only the frontend was searched for
   callers; a CLI or external integration could consume it.
8. **The git history of this feature** — not read, so no claim is made about when a drift was
   introduced.

## 13. Scorecard

| Dimension | Score | Anchor |
|---|---|---|
| Evidence relevance | 4 | every finding's citation is the line that carries the claim; one minor gap: F9 compares two pages without reading the other page in full |
| Class discipline | 4 | every finding carries exactly one class; `ui-observed` is claimed nowhere because it could not be produced (stated, not hidden) |
| Depth | 3 | every interactive control and data view reached the state-matrix level (§5e), but no property was measured — no contrast ratio, no type scale, no target size |
| Image evidence | **1** | no rendered screen was read; blur and grayscale tests not run; breakpoints and dark mode not captured |
| Axis coverage | 3 | feasibility and triage produced at depth; value produced as a readiness finding only; usability explicitly excluded; competition absent |
| Metric integrity | 2 | the one metric (audited/attempted) has a definition and a window but no denominator I could observe |
| Solution plurality | 4 | three solutions per opportunity against a pre-stated criterion (§3), decided before the recommendation |
| Feasibility grounding | 5 | every implementation claim is a `path:line`, and the doc-vs-code gaps (F3, F7, F12) cite both sides |
| Decision quality | 4 | every capability ends keep/fix/cut/bet with a metric, threshold and timeframe; **owners are unnamed** because the repo records none for this area |
| Scope calibration | 5 | §12 names eight things not looked at and what would flip each conclusion |

Mean = (4+4+3+1+3+2+4+5+4+5)/10 = **3.5 → "revise" band**, and independently: Image evidence = 1,
which the skill's own rule reads as **reject**. Both bands are reported because both apply — the
analysis is usable for the feasibility and coherence work and is not a complete product analysis, and
this artifact says so rather than averaging the gap away.
