# Product analysis — admin Users area (aibim-app), pre-wiring control arm

Rubric: `.tezgah/research/feature-coherence/experiments/E6-pre-wiring-control/product-analysis-pre-wiring.md` (read 2026-09-21, 323 lines, `:img` not used).
Feature in scope: the admin Users area — backend routes/handlers for users, the authorization they consult, the queries they run, and the React page + API client that call them.
Subject repository: `/Users/rizax/Projects/aibim-app` at `a6e47df` (2026-08-28 14:22:06 +0300), read-only, source only. No build, no Docker, no DB, no running app.
Evidence classes used: `code` (a `path:line` in aibim-app, or, once, a crate source file outside it), `external` (a named artifact read in this session), `user-verbatim` (none), `behaviour` (none), `ui-observed` (none).

## 1. Measurement readiness — the gate, first

**F1 (`code`, gate).** Nothing in this feature is observable from source alone, and no runtime evidence was produced: the batch constraints forbid builds/Docker, so the app was never run, and no analytics/telemetry readout for the users area was found in the repository. Consequences for this artifact, stated in the rubric's own terms: the usability axis is **not** produced at `ui-observed` depth (item 5 is source-read and labelled as such), the value axis has no `behaviour` row (no ratio with a denominator and a window), and the competition axis has no artifact to cite. The artifact therefore scores 1 on `Image evidence` and cannot pass its own scorecard (§Scorecard). Citation for "the app was not run": none — it is the absence of a run, and it is reported as such, not as a finding about the product.
**F2 (`code`).** A dormant-account signal is *latent* in the schema and unreachable in the product: `users.last_login_at` exists and is selected (`db.rs:505`, `db.rs:471`), is transported (`handlers/admin.rs:4454`, `:4493`), is typed in the client (`types/admin.ts:94`) — and is rendered nowhere: no column in the Users table (`pages/Users.tsx:109-110`), no row in the detail panel (`pages/Users.tsx:133-175`), and not in TenantDetail's user table either (`pages/TenantDetail.tsx:376-390`). "We cannot see this yet" is the first finding on the value axis, not a footnote.

## 2. Objective — Goal → Signal → Metric

Goal: platform admins keep the account set complete and least-privileged (the only stated intent found is the feature's own doc comment, `handlers/admin.rs:4393` "list all users (paginated, with tenant name)", and the panel's purpose line `docs/core/technical-reference.md:77`).
Signal: share of platform accounts that are live *and* genuinely in use, and the share of role grants that exceed a viewer/operator need.
Metric (defined, windowed): `users with is_active = true AND last_login_at >= now() - 30d` / `users with is_active = true`. Numerator and denominator are both derivable from `db.rs:503-506`; window: 30 days; source: none today (F1) — the query that would produce it exists, the readout does not. `is_active = true` alone is refused as a metric: it counts rows the admin created (and `CREATE_INACTIVE`, `db.rs:521-524`, sets it false), not accounts in use.

## 3. Opportunities, solutions, criterion

Opportunity (a need, not a feature): *an admin cannot tell which accounts are dormant, so an offboarded or abandoned account keeps its role indefinitely.* Evidence: `code` — F2's chain plus the fact that no filter, sort or column exposes it.
Criterion, pre-stated: smallest change that makes the need measurable *from the Users page with no new endpoint*.
Three candidates compared against it:
1. render `last_login_at` as a column + sort — reuses a field already returned (`handlers/admin.rs:4454`); 1 file. **Chosen.**
2. a `status=dormant` filter chip — needs a new query parameter and `db.rs:483-490` change; 3 files.
3. a separate "Dormant accounts" report page — new route, new handler; not justified at the current evidence level.
Rejected alternative recorded: (1) wins on the criterion, (2) is the fallback when a real dormancy threshold is agreed.

## 4. Risks

| Class | Risk | Cheapest falsifying test |
|---|---|---|
| value | the panel's user list is not the system of record, so a dormancy readout changes nothing | count distinct actors in `admin_audit_logs` with action `user_*` over 30d (needs DB) |
| usability | the list's **error state does not exist** (F6) | serve a 500 on `GET /api/v1/admin/users` and read the page |
| viability | module-permission writes can silently reduce a grant set (F4) | open Manage on a user with modules, save without changing, read `users.permissions` |
| feasibility | the panel offers `super_admin` in two places and the backend refuses it (F5) | click the "super admin" role button, read the 400 |

## 5. Usability — source-read only, no rater panel, no `ui-observed` finding

Scope: one section (the admin Users page and its tenant-detail twin), one task (create → approve → role/status → module permissions), one device class (desktop web), breakpoints/axe/dark mode **not** run (no running app). Rater count: 1 (me), passes: 1 — so every item below is at best a `judgement` at low confidence, and none is a WCAG proof.

State matrix (evidence class `code`; `✗` = the state does not exist in the source, `✓` = present):

| Unit | default | hover | focus | active | disabled | loading | error | empty |
|---|---|---|---|---|---|---|---|---|
| users list query (`Users.tsx:44-47`) | ✓ | n/a | n/a | n/a | n/a | ✓ `isLoading` (`:111`) | **✗** | ✓ `emptyText="No users found"` (`:111`) |
| user table row (`Users.tsx:114-120`, `<tr onClick>` at `:120`) | ✓ | ✓ `table-row-hover` | **✗** no `tabIndex`/`role`/key handler | — | — | — | — | — |
| role buttons (`Users.tsx:179-195`) | ✓ | ✓ | **✗** (styled `<button>`, no focus ring in source) | — | ✓ `:185` | ✓ `roleMut.isPending` | toast only (`:71`) | n/a |
| deactivate/activate (`Users.tsx:207-216`) | ✓ | ✓ | ✗ as above | — | ✓ `:208` | ✓ `:215` | toast only (`:80`) | n/a |
| Edit-profile save/cancel (`Users.tsx:228-237`) | ✓ | ✓ | ✗ | — | ✓ | ✓ `:230` | toast only (`:62`) | n/a |
| create modal (`Users.tsx:236-268`) | ✓ | ✓ | ✗ | — | only `isPending` (`:263`); no required-field gate | ✓ `:266` | toast only (`:52`) | n/a |
| detail panel (`Users.tsx:131-176`) | ✓ | — | ✗ close button is styled, no `aria-label` | — | — | — | — | `—` placeholders only |
| tenant-users table (`TenantDetail.tsx:373-390`) | ✓ | ✓ | ✗ | — | — | ✓ (`:371`) | **✗** no error branch | ✓ (`:372`) |
| module-permission panel (`TenantDetail.tsx:393-427`) | ✓ | ✓ | partial | — | — | — | **✗** | ✗ (silently renders all-unchecked, see F4) |

Findings (level · severity 0-4 = frequency × impact × persistence):

**F6 (state level, `code`, severity 3, judgement-confidence high from source, reproducible failure candidate).** The Users list has no error state. `Users.tsx:44` destructures `{ data, isLoading }` and never `isError`; a failed `GET /api/v1/admin/users` therefore leaves `data` undefined, so `allUsers` is `[]` (`:83`) and the page renders `emptyText="No users found"` with four zeroed StatCards (`:101-104`). Contrast basis is the same app: 13 sibling pages bind `isError` and return `QueryErrorState` — `Tenants.tsx:40`, `ApiKeys.tsx:39`, `Billing.tsx:29`, `Licenses.tsx:27`, `Requests.tsx:431`, `AuditLogs.tsx:191`, `Agents.tsx:115`, `Benchmarks.tsx:187`, `Enterprise.tsx:319`, `System.tsx:45`, `Dashboard.tsx:48`, `DetectionRules.tsx:453`, `TenantDetail.tsx:689`; `QueryErrorState` is exported for exactly this (`components/ui/QueryErrorState.tsx:6`). The backend states the same principle for its own layer: "a stats handler returning zeros on an outage is the same silhouette as a quiet day and will hide real incidents" (`handlers/admin.rs:502-504`). Users is the one page that breaks it.
**F7 (state level, `code`, severity 2, judgement).** Deactivating an account has no confirmation step: `onClick={() => toggleMut.mutate(...)}` fires immediately (`Users.tsx:207`). Contrast: destructive actions elsewhere in the same app confirm first (`ThreatIntel.tsx:96`, `:267`, `:342`, `:425`). One click on a row's panel button disables a user's login; there is no undo affordance in the UI.
**F8 (property level, `code`, severity 2, judgement; WCAG 2.2 SC 2.1.1 candidate, hand-check required).** Table rows are click targets implemented as `<tr onClick>` with no `tabIndex`, no `role`, no key handler (`Users.tsx:114-120`), so "open the user panel" is mouse-only by construction. Class is `code`: a WCAG *failure* claim is not made because keyboard reachability, focus appearance (SC 2.4.11/2.4.13) and focus order were not measured in a page — `browser_evaluate`/axe-core were not run (F1). axe-core's own coverage limit (~57%) and the checks it cannot see are why this is hand-checked, not assumed.
**F9 (copy/contract, `code`, severity 1, judgement).** Search is documented to the user as scope-limited ("Search by name or email...", `Users.tsx:107`) while the query also matches role, user id and tenant name (`db.rs:483-490`). Under-promising is cheap to fix and currently hides a usable capability.
**Not produced, named:** contrast ratios, tap-target sizes, type scale, z-order, focus order, LCP/INP/CLS, the blur and grayscale tests, dark mode and 320/768/1280 captures, axe-core sweep with a pinned version, SUS/UMUX-Lite, and the rendered screen read as an image. Each requires a running app (`analyze-app`); none was possible here. The cognitive walkthrough was likewise **not** run as a separate instrument: with no running app each of its four questions could only be answered from source, which is the same defect the rubric names for heuristics. Recorded as missing, not as done.

## 6. Feasibility — intended vs implemented, both sides cited

Contracts (each row: producer, transport, consumer, verdict):
1. **`total` — produced, transported, never consumed (`code`).** Producer: `COUNT_FILTERED` (`db.rs:494-500`) → `"total": count` (`handlers/admin.rs:4458`). Transport: `fetchUsers(): Promise<{users; total: number}>` (`api/admin.ts:374-377`). Consumer: none — the page shows `allUsers.length` as "Total" (`Users.tsx:101`) and in the header (`:95`). The page requests a fixed `limit: 200` (`:46`) against a server clamp of `1..=500` (`handlers/admin.rs:4400-4402`) and renders no pager, while `Pager` exists and is used with `total` elsewhere (`ThreatIntel.tsx:247`, `:324`, `:407`). A tenant with more than 200 users is silently truncated and its Total is wrong.
2. **`last_login_at` — produced, transported, never consumed (`code`).** See F2; the field contract's consumer side is empty in both user views.
3. **`permissions` on a tenant-users row — consumed but never produced (`code`).** Consumer: `setEditModules(u.permissions?.modules ?? [])` (`TenantDetail.tsx:393`) off the row from `fetchTenantUsers`. Producer: `admin_tenant_users` decodes a 5-tuple and emits only `user_id/email/full_name/role/is_active` (`handlers/admin.rs:762-780`) although the bound query returns 8 columns (`db.rs:469-472`). sqlx's tuple `FromRow` does not check the column count — it calls `try_get(0..4)` and ignores the rest (read this session: `~/.cargo/registry/src/index.crates.io-1949cf8c6b5b557f/sqlx-core-0.8.6/src/from_row.rs:339-345`, class `external`) — so this is a silent field drop, not a runtime error. **Risk chain (code, derived, severity 4):** every Manage panel opens with all modules unchecked; saving writes `editModules` wholesale (`TenantDetail.tsx:427` → `api/admin.ts:922-925` → `handlers/admin.rs:8424` → `db.rs:957-958`, a full `SET permissions = $2::jsonb`), so a save from an untouched panel reduces a user's grant set. The read endpoint that would fix it exists and has **no client function at all**: `GET /api/v1/admin/users/{id}/permissions` (`main.rs:338-341`, `handlers/admin.rs:8477`) has no counterpart in `api/admin.ts` (the file defines only `updateUserPermissions`, `:922`).
4. **`message: "User created (inactive). Activate after approval."` — produced, dropped in the UI (`code`).** Producer: `handlers/admin.rs:967`. Consumer: `createUser` returns the body (`api/admin.ts:384-387`) and the mutation ignores it, toasting only `'User created'` (`Users.tsx:51`). The account is created `is_active = false` (`db.rs:521-524`) and the approval step is not surfaced by the flow that created it.
5. **Role options — the UI offers a role the backend always refuses (`code`).** UI: `ALL_ROLES` includes `super_admin` (`Users.tsx:11`), used for the Change Role buttons (`:179`) and the create-modal `FormSelect` (`:253`), and for the tenant-detail `<select>` (`TenantDetail.tsx:382`). Backend: `ADMIN_ASSIGNABLE_ROLES = ["admin","operator","viewer","api_user"]` (`handlers/admin.rs:873`); anything else is `400 "Invalid platform role"` (`:879-880`), and the intent is stated in-code: "super_admin can only be created via the CLI tool" (`:872`). So the option is dead in three places, and the failure reaches the user only as a toast (`Users.tsx:52` from the create modal, `:71` from the role buttons).
6. **Authorization — agrees across layers (`code`).** Every user route is registered on the platform-admin router (`main.rs:251-286`, `:336-341`) whose layer is `require_admin_access` (`main.rs:440-442`), which enforces `super_admin|admin` (`middleware.rs:68-79`), audience `aibim-admin`, `typ == "access"` and the `iss` gate (`middleware.rs:147-205`), and CSRF for cookie-authenticated mutating methods (`middleware.rs:139-145`, `:246-270`). Handlers add narrower checks: `validate_platform_role_grant` (`handlers/admin.rs:875-890`), `super_admin|admin` for permissions (`:8431-8435`). No handler in this area is reachable without the middleware, and no handler trusts a client-supplied actor id (audit rows are built from `AdminClaims`, `:227-288`). This row is an agreement, recorded as required.
7. **Doc vs code gap (`code`, both sides cited).** Documented intent: the admin API table lists exactly two user endpoints — `PUT /api/v1/admin/users/{id}/role` and `POST /api/v1/admin/users/{id}/deactivate`, both labelled `Admin` (`docs/core/technical-reference.md:1004-1005`). Implemented: seven user-related route registrations — ten path × method pairs — at `main.rs:251-286` (tenant users, role, deactivate, users list/create, activate, users/{id} read/update) and `main.rs:336-341` (permissions read/write), plus the SCIM user upsert at `main.rs:498-501`; and the role change is super_admin-only for an `admin`-level grant (`handlers/admin.rs:881-887`). A reader of the reference cannot learn that the panel creates users, activates them, edits profiles or writes module permissions — nor that `Admin` is too coarse for the role rule.
8. **Test coverage of this contract (`code`).** `handlers/admin.rs` has 40 `#[test]`/`#[tokio::test]` items, all pure-function (role-gate and hash/format helpers, e.g. `:8890-8899`); none calls a users handler. The frontend has no test file and `frontend/package.json` defines no `test` script. Every disagreement in rows 1-5 is therefore invisible to the suite: `total` could stop being returned and no test would fail.

## 7. Competition

Not produced: no competitor artifact was read in this session, so no comparison basis is stated and no competitor fact is cited — a basis stated without an artifact would be the failure mode the rubric names. Flip condition: name the basis first (feature density of the user-administration surface, or task time for "deactivate a user who left"), then read one pinned version of the two nearest products on a stated date.

## 8. Triage

| Capability | Verdict | Deciding metric | Threshold | Timeframe | Action | Flag | Owner |
|---|---|---|---|---|---|---|---|
| list users | **fix** | share of failed list requests that render the empty state instead of an error state | any non-zero → 0 | next release | bind `isError` → `QueryErrorState` (`Users.tsx:44`) | none exists | unassigned — no owner is named anywhere in this repo for the admin panel; flag `admin_users_list_state` proposed |
| list pagination | **fix** | users returned / users matching (`total`) | ratio = 1, or a pager present | next release | consume `total` (`admin.rs:4458`, `admin.ts:374`) + `Pager` | none | unassigned |
| read one user (`GET /users/{id}`, `fetchUser`) | **cut** | callers of `fetchUser` outside its definition | 0 callers today | now | delete `api/admin.ts:379-382`, or make the panel refetch on open | none | unassigned |
| write module permissions | **fix** (first) | grants lost per Manage-save/unmodified-open | 0 | immediately | call `GET /users/{id}/permissions` (`admin.rs:8477`) on expand and seed `editModules` from it | none | unassigned |
| role options | **fix** | dead options offered / all options | 0/5 | next release | derive the role list from the assignable set (`admin.rs:873`) | none | unassigned |
| create-user flow | **fix** | created accounts never activated (`is_active=false`, no follow-up surfaced) | 0 without an explicit prompt | next release | surface `message` (`admin.rs:967`) and offer Activate | none | unassigned |
| dormant-account readout | **bet** | dormant share = active accounts with `last_login_at` older than 30d / all active accounts | > 10% → build the filter (candidate 2) | 1 quarter | column + sort from the field already returned | none | unassigned |
| lifecycle audit trail in the Users view | **cut for now** | — | — | — | audit rows exist (`admin.rs:227-288`) but the AuditLogs page already owns this view | — | — |
No metric, threshold, timeframe or action in this table was measured — the owners and flags do not exist in the repository today, which is itself the reason "fix" is the verdict rather than "keep".

## 9. Findings, most severe first

1. **F4a (`code`, severity 4).** A Manage-save on the tenant user list can reduce a user's module permissions without the admin seeing the change, because the panel is seeded from a field the endpoint never returns (`TenantDetail.tsx:393` vs `handlers/admin.rs:762-780`, `db.rs:469-472`; sqlx tuple rule: `sqlx-core-0.8.6/src/from_row.rs:339-345`, `external`), and the write is a wholesale `SET permissions` (`db.rs:957-958`).
2. **F4b (`code`, severity 4, capability row).** `GET /api/v1/admin/users/{id}/permissions` (`main.rs:338-341`, `handlers/admin.rs:8477`) has no client function in `api/admin.ts` — the read half of the RBAC contract is unreachable from the panel.
3. **F6 (`code`, severity 3).** The Users list has no error state; a backend outage reads as "No users found" with zeroed stats (`Users.tsx:44`, `:83`, `:101-104`, `:111`), against 13 sibling pages that do it correctly (`Tenants.tsx:40` … `TenantDetail.tsx:689`).
4. **F3 (`code`, severity 3).** `total` is produced and transported and never consumed, so the list is silently truncated at 200 and its Total is a page size (`handlers/admin.rs:4458`, `db.rs:494-500`, `api/admin.ts:374`, `Users.tsx:46`, `:101`).
5. **F5 (`code`, severity 3).** `super_admin` is offered as a role in three UI places and refused by the backend in all three (`Users.tsx:11`, `:179`, `:253`, `TenantDetail.tsx:382` vs `handlers/admin.rs:872-880`).
6. **F2/`last_login_at` (`code`, severity 2).** Produced and typed, rendered nowhere (`handlers/admin.rs:4454`, `types/admin.ts:94`, `Users.tsx:109-110`, `:133-175`).
7. **F7 (`code`, severity 2).** Deactivation is one unconfirmed click (`Users.tsx:207`), unlike the confirmations used elsewhere (`ThreatIntel.tsx:267`, `:342`, `:425`).
8. **F8 (`code`, severity 2, judgement).** Row-open is mouse-only: `<tr onClick>` without `tabIndex`/`role`/key handler (`Users.tsx:114-120`); WCAG 2.2 SC 2.1.1 candidate, not proven (no page measurement, no axe sweep).
9. **F9 (`code`, severity 1).** The search placeholder understates the query's scope (`Users.tsx:107` vs `db.rs:483-490`).
10. **F10 (`code`, severity 1).** `fetchUser`/`admin_get_user` is dead from the panel (`api/admin.ts:379-382`, `main.rs:284-286`); the detail panel renders the list row instead.
11. **F11 (`code`, severity 2).** No test in the repository would catch any of rows 1-5 (§6.8). Not a user-visible defect; it is why they persist.
Findings in states-marked entries of §5 that are not repeated here (`role buttons` disabled/loading present, `create modal` submit gating thin) are judgement-level and stay in the matrix.

## 10. Recommendations and their references

- Fix the permission seed by calling the endpoint that exists (`handlers/admin.rs:8477`) — reference: the app's own pattern of fetching the detail record before editing it (`TenantDetail.tsx:336-338` fetches before rendering). Adopt: GET-before-write on expand.
- Bind the list's error state — reference: `Tenants.tsx:40` in this same panel. Adopt: the shared `QueryErrorState` component (`components/ui/QueryErrorState.tsx:6`).
- Consume `total` with `Pager` — reference: the same panel's threat-intel tables (`ThreatIntel.tsx:247`). Adopt: `Pager page/total/pageSize`.
- Render `last_login_at` — no external best-practice is cited; the reference is the field's own existence in this schema (`db.rs:505`) and the acknowledged absence of a competitor artifact (§7).
- Derive role options from the assignable set — reference: the backend constant itself (`handlers/admin.rs:873`, `:872`). Adopt: one source for the option list.

## 11. What this analysis did not look at, and what would flip it

Not looked at: the running app (no build/Docker — the whole usability axis is at source depth), the database and any real user row, `users.permissions` values in any environment, telemetry/analytics, competitor artifacts, the SCIM provisioning path (`handlers/admin.rs:5526`) and the enterprise delegated-admin surface that also writes roles, the app-side (`app/`) user surface, i18n/Turkish copy, mobile widths, and the Login/registration flow that produces the accounts this page manages.
What would flip it: a single run of the admin panel against a seeded DB would turn §5 into `ui-observed` findings and could raise or lower F6-F9; a 30-day `admin_audit_logs` extract would turn the value axis's metric into a `behaviour` row and could demote the dormancy bet; reading one pinned competitor on a stated basis would fill §7.

## Scorecard

| Dimension | Score | Why |
|---|---|---|
| Evidence relevance | 4 | every finding's citation was read in this session and supports the claim; `sqlx` tuple behaviour is labelled `external` with its path |
| Class discipline | 4 | one class per finding; no `ui-observed`, `behaviour` or `user-verbatim` finding is claimed because none could be produced (F1) |
| Depth | 3 | screens reach component × state in a matrix and the missing states are named, but nothing is measured (`isError`, `tabIndex`, `total` are read, not computed) |
| Image evidence | 1 | no rendered screen was read: no breakpoint, dark mode, blur or grayscale test, no axe sweep |
| Axis coverage | 3 | value, usability (source depth), feasibility, triage produced; competition explicitly excluded |
| Metric integrity | 3 | the metric is a ratio with a definition and a 30-day window, but its source does not exist yet (F1/F2) |
| Solution plurality | 4 | three candidates compared against a criterion stated before the comparison (§3) |
| Feasibility grounding | 5 | every claim is a `path:line`, and each doc-vs-code or layer-vs-layer disagreement cites both sides |
| Decision quality | 4 | every capability has keep/fix/cut/bet with metric, threshold, timeframe and action; owners do not exist in the repository and are reported as missing |
| Scope calibration | 5 | §1 and §11 name what was not looked at and what would flip the recommendations |
Mean: **(4+4+3+1+3+3+4+5+4+5)/10 = 3.6** → the rubric's band is `revise`, and because `Image evidence` is 1 the rubric's own rule is **reject**. That verdict is what a source-only, read-only arm must earn: the coherence matrices and the feasibility axis are complete enough to be checked, and the usability axis is below the depth the rubric demands because the app was never run.
