# Admin Users area — feature coherence audit (single feature)

Feature: the admin Users area of `/Users/rizax/Projects/aibim-app` — the `users` entity
plus every action an operator can take on it, the routes that serve them, the
authorization they consult, the queries they run, and the React page and API client
that call them.

Boundary (the unit): entity `users`; actions list / search / view detail / create /
activate / deactivate / change role / edit profile / set module permissions; routes
`/api/v1/admin/users*`, `/api/v1/admin/tenants/{id}/users`; screens
`admin/frontend/src/pages/Users.tsx`, the user section of `pages/TenantDetail.tsx`,
the picker `components/ui/UserSearchSelect.tsx`; files
`admin/backend/src/handlers/admin.rs`, `admin/backend/src/db.rs`,
`admin/backend/src/main.rs`, `admin/backend/src/middleware.rs`.

Revision audited: `aibim-app` @ `a6e47df1444bf2a63136c4337229ba3205148300` (2026-08-28).

## 0. Measurement readiness — what is observable today

**The running app was not read.** The batch contract forbids starting Docker or a build, and
the app is audited from source in both arms. So every interface statement below is a
`code`-class reading of source, **not** `ui-observed`; no state was read from the DOM, the
accessibility tree, a screenshot or a page measurement. There is therefore **no** axe-core
sweep, **no** contrast or target-size measurement, **no** breakpoint capture, no dark-mode or
200%-text capture, and no blur/grayscale test in this artifact — each is named in its section
as `[NOT CHECKED: no running app]` rather than left out silently.

**Telemetry: none exists for this feature.** No analytics or event layer in either backend;
the only structured record is `audit_log`, written by `audit_admin_action`
(`admin/backend/src/handlers/admin.rs:54-62`) for six actions. So behaviour cannot be
reported as a ratio here: no numerator/denominator pair was read. What *is* observable is one
product metric, defined in §2 and never surfaced.

**Rater count: 1.** One source-reading pass plus one cross-read of the sibling user surface
(`TenantDetail.tsx`) as a convention check. The product-analysis skill requires 3-5
independent evaluations for a usability claim; a single agent reading source is one rater, so
every judgement below carries severity but claims no inter-rater agreement.

## 1. Capability matrix (action × layer)

`yes` = the layer implements it, with citation. `no` = absence, with the search that shows it.

| Action | Surface | Route | Authorization | Service / validation | Persistence |
|---|---|---|---|---|---|
| List users | yes — `Users.tsx:95-128` | yes — `main.rs:264`, `admin_list_all_users` `admin.rs:4394` | yes — `require_admin_access` `main.rs:440-443`, gate `middleware.rs:36-38` | no — no validation beyond `limit`/`offset` clamp `admin.rs:4399-4414` | yes — `db::users::LIST_FILTERED` `db.rs:482-493` |
| Search / filter | yes — `Users.tsx:107` | yes — `?search=` `admin.rs:4409-4412` | yes — as above | yes — `ILIKE` on 5 columns `db.rs:482-493` | yes — `COUNT_FILTERED` `db.rs:494-502` |
| View detail | yes — row click, `Users.tsx:120` | **no** — `GET /users/{id}` (`admin.rs:4469`) is never called; `fetchUser` `api/admin.ts:379` has no caller | yes — as above | yes — `GET_BY_ID` `db.rs:503-506` | yes — same query |
| Create user | yes — modal `Users.tsx:243-266` | yes — `main.rs:264`, `admin_create_user` `admin.rs:892` | yes — plus role grant rule `admin.rs:877-889` | partial — email/password/tenant non-empty, `password.len() < 8` `admin.rs:906-919`; no email format, no 255-char email bound, role defaults to `viewer` `admin.rs:896-900` | yes — `CREATE_INACTIVE` `db.rs:521-524` |
| Activate | yes — `Users.tsx:207-215` | yes — `main.rs:268`, `admin_activate_user` `admin.rs:989` | yes — as above | no — no state precondition (already-active user returns success) | yes — `ACTIVATE` `db.rs:518-520` |
| Deactivate | yes — `Users.tsx:207-215` | yes — `main.rs:260`, `admin_user_deactivate` `admin.rs:835` | yes — as above, **no self/last-super-admin guard** | no validation | yes — `DEACTIVATE` `db.rs:515-517` |
| Change role | yes — `Users.tsx:179-190` | yes — `main.rs:256`, `admin_user_role` `admin.rs:789` | yes — `validate_platform_role_grant` `admin.rs:877-889` | yes — typed DTO + `validate()` `admin.rs:796`, `admin_dto.rs:129-137` | yes — `UPDATE_ROLE` `db.rs:512-514` |
| Edit profile | yes — `Users.tsx:222-223` | yes — `main.rs:284`, `admin_update_user` `admin.rs:4505` | yes — as above | **no** — raw `Json<Value>`, no DTO, no validation `admin.rs:4505-4519` | yes — `UPDATE_PROFILE` `db.rs:508-510` |
| Set module permissions | **no** in this screen; yes in the sibling — `TenantDetail.tsx:408-424` | yes — `main.rs:338-340`, `admin_update_user_permissions` `admin.rs:8424` | yes — role re-check in the handler `admin.rs:8430-8436` | **no** — any JSON array accepted `admin.rs:8438-8441` | yes — `user_permissions::UPDATE` `db.rs:957-958` |

Disagreements read out of the matrix:

- **A layer yes, surface no**: `GET /api/v1/admin/users/{id}` is routed and has a client
  function; no surface calls it (grep `fetchUser(` over
  `admin/frontend/src/**` → 1 hit, its own definition `api/admin.ts:379`). The detail panel
  renders the cached list row instead (`Users.tsx:120` → `openUserPanel`). Corollary:
  `db::users::LIST_ALL` (`db.rs:474-478`) has zero callers (grep `users::LIST_ALL` over
  `admin/backend/src` → 0 hits) — two queries for one list.
- **Surface yes, layers no**: module permissions are stored and rendered but enforced by no
  layer — see F10.
- **Two routes for one action**: `GET /api/v1/admin/users` (global, `admin.rs:4394`) and
  `GET /api/v1/admin/tenants/{id}/users` (`admin.rs:757`, no pagination, `total` =
  `users.len()` `admin.rs:781`). The tenant-scoped one is the only one that shows *tenant*
  users to a tenant screen; the global one is the operator's.
- **Route yes, authorization no**: none found — every `/api/v1/admin/users*` route is inside
  the router that carries `require_admin_access` (`main.rs:230-443`).
- **Pass rows (agreement)**: (a) authorization is coherent at platform scope — the middleware
  gate is `super_admin|admin` (`middleware.rs:36-38`), the handler-level role grant rule
  (`admin.rs:877-889`) is *also* reflected in the surface's role list for a non-super admin
  (`Users.tsx:10,85`); (b) all six mutating user actions write an audit row
  (`admin.rs:810,846,948,1002,8438` — `user_role_change`, `user_deactivate`, `user_create`,
  `user_activate`, `user_permissions_update`; profile update at `admin.rs:4528`).

## 2. Value axis

**Goal → Signal → Metric** (proposed; the metric is not exposed anywhere, which is itself F12):

- Goal: an operator can provision an account that its owner can actually use, without a
  second admin action and without leaking a credential.
- Signal: an admin-created inactive user reaches a first successful login.
- Metric: *create-to-first-login rate* = distinct `user_id` with a `user_activate` audit row
  **and** a non-null `users.last_login_at` within 7 days of that activation, divided by
  distinct `user_id` with a `user_create` audit row, window 30 days, source `audit_log` +
  `users.last_login_at` (`db.rs:503-506`). A ratio with its definition and window; it is
  computable from columns that exist and is read by no screen — the closest surface,
  `admin_dashboard`'s `total_users` (`admin.rs:8035`), is a raw count with no goal above it and
  is correctly dropped.

Opportunity (a user need, not a feature): *"I created the account; now I need to hand it over
and know it was used."* Three candidate solutions against a pre-stated criterion — cost to
the operator (steps), and whether the credential ever passes through a third party:

| Solution | Operator steps | Credential exposure | Verdict |
|---|---|---|---|
| Keep admin-typed password, add an "invite link" copy button | 2 | admin sees the secret | weak |
| Random server-generated password + delivery by mail | 1 | never seen by the admin | needs a delivery layer that does not exist (§F3) |
| Account created inactive, owner sets the credential by a one-time token | 1 | never seen by the admin | the reference behaviour (Keycloak "update password" required action, read 2026-09-20) |

The criterion chosen before comparing: no party other than the account owner should ever know
the credential, because a credential known to an admin is indistinguishable from an admin
holding the account. Solution 3 wins on it, and it names a layer that does not exist → it is
reported as a capability-change proposal in §8, not as a screen fix.

## 3. Feasibility — the coherence pass

### 3.1 Field contract

| Field | Column / type | Read by API | Written by API | Rendered | Validated | Label / enum source | Locale / format |
|---|---|---|---|---|---|---|---|
| `user_id` | `UUID` `001_core_tenants.sql:71` | `db.rs:483,504` | db default | truncated to 8 chars `Users.tsx:135`, `146` | n/a | — | — |
| `email` | `VARCHAR(255) NOT NULL UNIQUE` `:72` | `db.rs:482,503` | `UPDATE_PROFILE` `db.rs:508-510`; `CREATE_INACTIVE` `:521` | list `Users.tsx:122`, edit `:223` | only non-empty on create `admin.rs:906`; **none on update** | raw | not localised |
| `full_name` | `VARCHAR(255) DEFAULT ''` `:74` | same | same | list `:121`, panel title `:135`, edit `:222` | none; `COALESCE($2, full_name)` means NULL keeps the old value `db.rs:508-510` | raw | — |
| `role` | `VARCHAR(20) DEFAULT 'viewer'` `:75`; canonical CHECK `107_canonical_user_roles.sql:14-21` | same | `UPDATE_ROLE` `db.rs:512-514` | `RoleBadge` `Users.tsx:17-23` printing `role.replace('_',' ')` | enum list in the service `admin.rs:873`; **not** in a DTO for create/update | **two sources**: the constant `admin.rs:873`, the literals `Users.tsx:10-11` and `TenantDetail.tsx:353` | raw |
| `is_active` | `BOOLEAN DEFAULT TRUE` `:77` | same | `DEACTIVATE`/`ACTIVATE` `db.rs:515-520`; create forces `false` `:521-524` | `StatusBadge` `Users.tsx:125` (list), `:161` (detail) | no transition rule | — | — |
| `tenant_id` | `UUID NOT NULL REFERENCES tenants` `:76` | same | `CREATE_INACTIVE` `:521-524` | rendered only as a fallback id `Users.tsx:124,146` | non-empty on create `admin.rs:906` | — | — |
| `tenant_name` | JOIN `tenants.name` `db.rs:483` | list only (`db.rs:482`), **not** by `GET_BY_ID` (`:503-506`) | n/a | list `:124`, detail `:146` | n/a | — | — |
| `created_at` | `TIMESTAMPTZ` `:79` | both | db default | detail only `Users.tsx:169` | n/a | — | `en-US`, `dd MMM yyyy` |
| `last_login_at` | `TIMESTAMPTZ` `:78` | both `db.rs:483,504`, mapped `admin.rs:4454,4493` | `auth::UPDATE_LAST_LOGIN` `db.rs:543` | **nowhere** — F6 | n/a | — | — |
| `password` | request-only `admin.rs:893`; `password_hash` `:72` | never returned | `CREATE_INACTIVE` `:521` | `FormInput type="password"` `Users.tsx:250` | `len() < 8` `admin.rs:915` | raw | — |
| `permissions` | `JSONB DEFAULT '{}'` `016_user_permissions.sql:5` | `user_permissions::GET` `db.rs:960-961` | `user_permissions::UPDATE` `db.rs:957-958` | `TenantDetail.tsx:408` | none | UI offers 7 slugs `TenantDetail.tsx:39-47`; endpoint documents 4 `admin.rs:8423` | — |
| `is_deleted` | `BOOLEAN NOT NULL DEFAULT FALSE` `014_deletion_guard.sql:12` | **never** — F7 | never | never | n/a | — | — |

### 3.2 Flow / step contract

The create flow is one modal (`Users.tsx:243-266`), not a wizard.

| Step | Precondition | Validates | Writes | Skip prevention | Resume | Back-nav retention | Error lands |
|---|---|---|---|---|---|---|---|
| Open modal | platform admin session | — | — | n/a | in-memory React state, lost on reload `Users.tsx:36`) | Cancel discards all six fields | n/a |
| Fill 6 fields | a tenant must exist | **client: none** | — | n/a | none | n/a | — |
| Submit | — | server: email/password/tenant non-empty, password ≥ 8 `admin.rs:906-919`; role grant rule `:877-889` | user inactive `:937` | n/a | n/a | n/a | **toast only** `Users.tsx:50-52`; the message names three fields at once `admin.rs:907-910` and is not attached to any field |

Preconditions nothing enforces, read from the matrix: (a) the tenant picker
(`Users.tsx:256`) does not filter by tenant `status`, and the service does not check it, so a
user can be created inside a suspended tenant — no cascade where the contract requires one;
(b) no step is URL-addressable, so no step can be reached out of order — that half passes.

### 3.3 Interaction dependency

| Trigger | Dependents | Required action | Owner | Announced |
|---|---|---|---|---|
| search box `Users.tsx:107` | list, 4 stat cards `:101-104`, page subtitle `:95` | recompute from the server | React Query key `['users', debouncedSearch]` `:44-46` | **no** — the result count is not a live region (SC 4.1.3); `DataTable` has no `aria-live` `DataTable.tsx:27-66` |
| role mutation `Users.tsx:184` | detail panel role, list row | recompute | patched by hand `:66-70` and refetched `:69` | toast "Role updated" |
| status mutation `Users.tsx:207` | detail panel, list row, Active/Inactive cards | recompute | patched by hand `:75-79`, refetched `:78` | toast "Status updated" |
| any external change by another admin | open detail panel | recompute | **nobody** — the panel holds a snapshot `Users.tsx:32,88-93`; a refetch does not refresh it, so the panel can show a role or status the list no longer has | no |
| a mutation while a search filter is active | which row the open panel refers to | revalidate | nobody — the filter does not clear, so the panel can describe a row no longer in the results | no |

### 3.4 Surface pattern — data view and controls (read from source)

| Rule | Reading |
|---|---|
| SC 1.3.1 real headers | pass — `<th>` in `<thead>` `DataTable.tsx:29-41`, `<td>` cells `Users.tsx:121-125` |
| Table accessible name / caption | **no** — no `<caption>`, no `aria-label` `DataTable.tsx:28` |
| `aria-sort` on the sorted column | **not applicable and not present** — no column sorting exists at all; the only order is `ORDER BY u.created_at DESC` `db.rs:492`, unstated on screen |
| One tab stop per interactive row | **fail** — the only way to open the detail panel is `<tr onClick>` with no `tabIndex`, no role and no key handler `Users.tsx:114-126` (the `<tr>` opens at `:114`, `onClick` at `:120`); the panel is keyboard-unreachable (SC 2.1.1) |
| Pagination marks the current page; one-page pager hidden | **no pagination at all** — `limit: 200` `Users.tsx:46`; the `Pager` primitive exists (`Pager.tsx:10-28`, `total <= pageSize` returns null) and is not used here |
| Filters discoverable, active state visible | **fail** — one placeholder-only search (`Users.tsx:107`), no status filter although three of the four stat cards are status-based (`:102-104`), and no way to tell a filtered list from a full one except the text still in the box |
| Content: first column a human-readable identifier; headings short nouns | pass — Name/Email/Role/Tenant/Status `Users.tsx:110` |
| Detail view as key/value pairs | partial — the rows are `div`s with a `label`-looking `<span>`, not `<dl>` `Users.tsx:145-172` |
| Long-text strategy | **none** — `full_name`, `email` and `tenant_name` render with no truncation, `wrap` or title `Users.tsx:121-124`; a long value stretches the row (SC 1.4.10 unmeasured) |
| Scroll region says it scrolls | `[NOT CHECKED: no running app — the container's overflow is in `index.css`, unmeasured]` |
| Visible persistent label (never a placeholder as label) | **fail** — the search field has `placeholder` and nothing else: no `<label>`, no `aria-label` `AdminPrimitives.tsx:57-74`. Form fields do have labels `FormElements.tsx:17,44` |
| SC 1.3.5 autocomplete tokens | **fail** — the edit-profile email field is the record's own data but carries no `autocomplete` token, and it is not the user's own data (it is the target user's) so `H98` does not apply either; `Users.tsx:223` |
| One required/optional convention | **mixed** — `FormInput` supports `required` and renders `*` `FormElements.tsx:17`, but this form passes it for nothing `Users.tsx:248-256`, while the server requires three fields `admin.rs:906` |
| SC 2.5.8 target size | `[NOT CHECKED: no running app — role pills are `px-3 py-1.5`, ≈27 px tall by ≈30 px wide by class arithmetic, not measured]` |
| SC 2.4.7 focus visible | `[NOT CHECKED: no running app]` |
| SC 1.4.3 contrast; no colour-only state | `[NOT CHECKED: no running app]` — note the role pill carries text as well as colour `Users.tsx:20-22`, so it is not colour-only by construction |
| Validation on submit, not blur; failing values kept; server-side present | pass on submit/kept/server; **client-side absent** — the modal posts whatever is in the fields `Users.tsx:263` |
| SC 3.3.1/3.3.3 error identifies the item and describes the fix | **fail** — one toast, one message naming three fields, no field marked `Users.tsx:50-52`, `admin.rs:907-910` |
| Association `aria-describedby` to the message | **fail** — `FormInput`'s `error` prop renders a `<p>` with no `id`/`aria-describedby` `FormElements.tsx:26`; the create form does not use it at all |
| Error summary at the top of the form | **no** — no summary surface |
| SC 3.3.4 / destructive confirmation names what is lost | **fail** — `Deactivate` fires on click with no dialog naming the user `Users.tsx:207-215`; `TenantDetail.tsx:379` changes a role on `onChange` with no confirmation either |
| `APG dialog` on the create modal | partial — the overlay closes on backdrop click and the content stops propagation `Modal.tsx:18-27`; there is no `role="dialog"`, no `aria-modal`, no labelled heading wiring, no focus move or trap, no Escape handler `Modal.tsx:14-28` |
| SC 4.1.3 status messages | partial — successes go to a toast (sonner) `Users.tsx:51,57,67,76`; the filtered result count is silent (§3.3) |
| SC 1.4.10 reflow at 320 px | `[NOT CHECKED: no running app]`; three of five columns hold unbreakable tokens (`email`, `tenant_name`) `Users.tsx:121-124` |

## 4. Findings

Most severe first. One evidence class each; `code` means a `path:line` in this repository.

### F1 — the whole user surface is under FORCE RLS with no bypass branch, and no user handler uses the bypass helper · severity 4 · `code` · failure-class

- `admin/backend/src/db.rs:41-49` and `:57-65` exist to set `app.admin_bypass` for
  cross-tenant reads; `:7-16` explains that querying such a table through the bare pool is
  "silently dropped by RLS".
- The `users` table is forced: `db/migrations/049_force_rls.sql:21`; its only policy is
  `tenant_isolation` keyed on `app.current_tenant_id` with no bypass branch:
  `db/migrations/048_rls_complete_coverage.sql:31-35`.
- Migration 068 fixed exactly this for three tables and states the symptom in its own words —
  "zero rows returned → all three admin agent endpoints return empty results always" —
  and `users` is not among them: `db/migrations/068_admin_bypass_rls.sql:1-52`.
- Every user handler binds `&state.db_pool` with no helper: `admin.rs:4426,4434,4485,4514,804,840,937,994,8439`
  (absence proof: grep `admin_bypass_tx|admin_pool_conn` over `admin.rs` → hits only at
  `:2603` onward, the agent/enterprise handlers).
- Read consequence, stated as the inference it is: list → zero rows → `Users.tsx:111` renders
  "No users found"; `GET_BY_ID` → `Ok(None)` → 404 "User not found" `admin.rs:4495`;
  `UPDATE_ROLE` → `rows_affected 0` → 404 `admin.rs:808-826`; the create `INSERT` fails the
  policy's `WITH CHECK` → 500 "Failed to create user" `admin.rs:981-983`.
- Falsifier that would refute it: the DB role the admin backend connects as has `BYPASSRLS`
  or is a superuser (both bypass RLS regardless of FORCE). Migration 068's root-cause note is
  evidence that this deployment's role does **not** bypass; I could not read the role itself
  (`[NOT CHECKED: no DB access]`).
- Prevent: an integration test that asserts one row returned per user table used cross-tenant,
  or the policy branch itself — this class already has a regression shape (068).

### F2 — the caller decides the new user's password and no layer ever delivers it · severity 4 · `code`

- The password travels admin → API → hash: `Users.tsx:252`, `admin.rs:893`, `admin.rs:937`.
- There is no delivery path anywhere in the module: grep `smtp|lettre|send_mail|mailer` over
  `admin/backend/src` → 0 hits; the response body is the only place the account is described
  (`admin.rs:956-968`), and it carries no credential and no link.
- No forced change on first use: grep `must_change_password|force_password|password_reset` over
  `admin/backend/src` → 0 hits; `password_hash` is written once `db.rs:521-524` and only the
  user's own login can change it `db.rs:540-541`.
- External standard: an administrator-typed password is neither subscriber-chosen nor
  randomly assigned by the verifier, and NIST SP 800-63B (Rev 4) §3.1.1 requires one of those
  two (`https://pages.nist.gov/800-63-4/sp800-63b.html`, read 2026-09-20). Reference
  behaviour: Keycloak's "update password" required action, i.e. the user sets the credential
  (Keycloak 26.7.4 Server Administration Guide,
  `https://www.keycloak.org/docs/latest/server_admin/index.html`, read 2026-09-20).
- The end of the action, in the capability matrix's terms: this create "succeeded in the
  database and failed the user" — nothing the created person receives.
- Prevent: a contract test that a created user's response never contains a credential, plus
  the required-action column the proposal in §8 adds.

### F3 — a dead control: `super_admin` is offered twice and refused by the service · severity 3 · `code`

- Offered: `ALL_ROLES` includes it `Users.tsx:11`, used for the role pills `:85,179-188` and
  the create-role select `:252-253`; duplicated as a second literal in the sibling surface
  `TenantDetail.tsx:353,379-382`.
- Refused: `ADMIN_ASSIGNABLE_ROLES` excludes `super_admin` `admin.rs:873`, the check at
  `:879-884`, and a unit test pins that exclusion `admin.rs:8894-8899`.
- The documented intent says the opposite — "Only super_admin can assign admin/super_admin"
  `admin.rs:788-789` — so the comment and the constant are two readings of one rule and they
  disagree; the code is what runs. Where both sides are cited, this is the doc-vs-code gap the
  feasibility axis asks for.
- Consequence: for a super admin, clicking the `super admin` pill yields HTTP 400
  "Validation error: Invalid platform role" rendered as a toast `Users.tsx:79`. For any actor,
  the create modal offers a role the same request rejects.
- Prevent: derive the option list from one source — the existing test at `admin.rs:8884-8899`
  already fails if the pair drifts, so make the UI read a role list the backend serves.

### F4 — deactivation is not a revocation, and nothing guards it · severity 3 · `code`

- `DEACTIVATE` writes `is_active = false` only `db.rs:515-517`; no refresh-token or session
  deletion in the admin backend (grep `DELETE FROM refresh_tokens|revoke_all` over
  `admin/backend/src` → 0 hits), while the access cookie lives 900 s
  `handlers/auth.rs:48,149`. So a deactivated user keeps a working session for up to 15
  minutes, and any refresh path that does not re-read `is_active` extends it.
  `[NOT CHECKED: the refresh handler's `is_active` re-check at `auth.rs:615` was not read
  line by line]`
- No guard: an `admin` can deactivate a `super_admin`, and any admin can deactivate
  themselves (`admin.rs:835-862` — no actor-vs-target comparison), while the *neighbouring*
  action in the same feature does carry one for role grants `admin.rs:877-889`. One action
  guarded, the other not, in one screen.
- The surface offers it to everyone: the button renders for any selected row
  `Users.tsx:207-215`.
- Prevent: one shared `assert_actor_may_target(actor, target)` used by both handlers, and a
  session-revocation call inside `admin_user_deactivate`.

### F5 — the counts on screen are page counts, and 200 users is a hard ceiling · severity 3 · `code`

- The API returns the true filtered total `admin.rs:4458` from `COUNT_FILTERED`
  `db.rs:494-502`; the page never reads it — `const allUsers = data?.users ?? []`
  `Users.tsx:44-46,85`.
- "Total", "Active", "Inactive" and "Admins" are computed over the loaded page
  `Users.tsx:101-104`, as is the subtitle "N users across all tenants" `:95`; the API's clamp
  is 500 `admin.rs:4399-4404` and the page asks for 200 `Users.tsx:46`.
- Effect: at 201+ users the dashboard-style stats are wrong, the roster silently omits rows,
  and no pager appears although `Pager` exists and this repo's *sibling* list pages use it.
  A raw count with no denominator is exactly what the value axis refuses; here it is worse,
  because a correct denominator is on the wire and dropped.
- Prevent: assert in an e2e that the rendered total equals `total` for a fixture of
  `limit + 1` users.

### F6 — a stored field no view renders · severity 3 · `code`

- `last_login_at` is selected by both user queries `db.rs:482-493,503-506`, typed in the
  client `types/admin.ts:94`, declared in `UserSummary` `api/admin.ts:37` — and rendered by
  no screen: grep `last_login` over `admin/frontend/src` → 2 hits, both declarations; the
  detail panel's rows are Email / Tenant / Role / Status / Created `Users.tsx:145-172`.
- The need it answers is the operator's first question after F2: "has this person ever signed
  in?" Today the screen can only say Active/Inactive, which the admin set.
- Prevent: a field-contract check that every column a list query returns is either rendered
  or explicitly listed as internal.

### F7 — the soft-delete column is invisible to every user query · severity 3 · `code`

- `users.is_deleted` exists and is indexed: `db/migrations/014_deletion_guard.sql:12,188`;
  a BEFORE DELETE trigger redirects deletes to soft deletes `:94-97`.
- The users module filters it nowhere: `db.rs:469-525` (absence proof: grep `is_deleted` in
  that range → 0 hits, while `#[allow(dead_code)]` sits on the module `db.rs:467`).
- The sibling modules in the same file do filter it — `tenants` `db.rs:87-93`, `:102`,
  service accounts `db.rs:343-361` — so the convention exists and this module
  deviates, with both sides cited.
- Consequence: a soft-deleted user stays in the global roster, can be re-roled and
  re-activated, and the `idx_users_active` index `014:188` exists for a predicate no query
  uses.
- Prevent: one test asserting that a soft-deleted user is absent from `admin_list_all_users`.

### F8 — no error state: a failed load renders as "No users found" · severity 3 · `code`

- The query destructures `{ data, isLoading }` only `Users.tsx:44`, and the table is
  `isEmpty={users.length === 0}` with `emptyText="No users found"` `Users.tsx:111`.
- So a 403, a 500, a network failure and a genuinely empty roster render identically — and F1
  makes the failure case the likely one.
- Every other admin page imports `QueryErrorState` (`Tenants`, `Enterprise`, `Dashboard`,
  `Requests`, `ApiKeys`, `Agents`, `System`, `Benchmarks`, `ThreatIntel`, `Licenses`,
  `DetectionRules`, `TenantDetail`, `Billing`, `AuditLogs` — 14 files, users of the shared
  primitive exported at `components/ui/index.ts:15`); `Users.tsx` is the exception.
- Prevent: a shared list-page harness that fails when a page renders the empty state in the
  error state.

### F9 — the detail panel is a snapshot nothing refreshes · severity 3 · `code`

- `selectedUser` is a copy of the list row `Users.tsx:32,88-93`; mutations patch it by hand
  `:66-70,75-79` and only the list is invalidated `:69,78`.
- Any change by another admin (or by the same admin in the sibling `TenantDetail` surface,
  which listens to none of this) leaves the panel showing a role or status the roster no
  longer has — the interaction-dependency table's "control still showing a state the view no
  longer has", and the reason `GET /users/{id}` exists at all.
- Prevent: the panel reads the detail route it already has (`api/admin.ts:379`) with a query
  key keyed by `user_id`, so it refetches like the list does.

### F10 — module permissions are stored, displayed and enforced by nothing · severity 3 · `code`

- Producer: `admin_update_user_permissions` `admin.rs:8424-8462` and the writer
  `db.rs:957-958`; reader: `admin_get_user_permissions` `admin.rs:8477-8500`.
- Absence proof: grep `"modules"` over `*.rs`, `*.ts`, `*.tsx`, `*.py` (excluding
  `node_modules`, `target`) → 2 hits, both in the writer's own file `admin.rs:8423,8439`;
  grep `user_permissions` over `admin/backend/src` → the module at `db.rs:956` and its two
  handler call sites. No middleware, guard or query in either backend reads the column.
- So the permissions editor in `TenantDetail.tsx:380-424` is decorative: it writes a JSON
  array that no layer consults, and it offers 7 module slugs `TenantDetail.tsx:39-47` while
  the endpoint documents 4 `admin.rs:8423` and validates none `:8438-8441`.
- This is a value finding as much as a feasibility one: an operator told that unchecking
  "Proxy Gateway" removes access has been told something untrue.
- Prevent: either a guard that reads `users.permissions` (with a test that a user without the
  module gets 403) or the removal of the editor. Until one of those, the screen claims a
  capability the system does not have.

### F11 — the profile write has no checker, and the duplicate-email rule is enforced in two currencies · severity 3 · `code`

- Create maps a duplicate email to 409 with a named message `admin.rs:974-980`; update maps
  the same collision to the generic 500 branch `admin.rs:4521-4527`, because `UPDATE_PROFILE`
  sets email unvalidated `db.rs:508-510`. A unique-violation on the inline `UNIQUE` on email
  (`001_core_tenants.sql:72`) therefore reads as "Internal server error" and the field state
  is lost.
- The same handler is the only user writer without a typed DTO: `admin_user_role` validates
  through `UserRoleUpdateReq` `admin.rs:796`, `admin_dto.rs:129-137`, whose own comment
  records that a missing field defaulting silently is "a footgun" — and `admin_create_user`
  still does exactly that for `role` (`admin.rs:896-900`, default `viewer`) and `full_name`
  (`:895`, default `""`), with no email format check and no 255-character bound to match the
  column.
- Prevent: one `UserUpdateReq` DTO with `#[validate]`, and a duplicate-email test covering
  both write paths (this is the repository's own lesson — a write path and its checker drift
  in both directions).

### F12 — the metric that would justify the feature has no surface · severity 2 · `code`

- The evidence exists (`audit_log` via `audit_admin_action` `admin.rs:54-62`; confirmed
  writers for create, activate, deactivate, role change, update, permissions
  `admin.rs:810,846,948,1002,4528,8438`), and the product metric of §2 is computable from it.
- No screen reports it: the Users page's only numbers are the page counts of F5. The
  dashboard's `total_users` is a raw count `admin.rs:8035`.
- So the first honest statement about this feature is "we cannot see it yet": create-to-first-login
  rate has never been measured, and neither this artifact nor anyone else can report a value.
- Prevent: a metric view backed by the audit rows that already exist — no new instrumentation.

### F13 — the create form's errors are not field-level, and the aria plumbing to make them so already exists unused · severity 2 · `code`

- The modal has no client validation and posts whatever is typed `Users.tsx:248-256`; the
  server's refusal is one message naming three fields `admin.rs:907-910`; it reaches the
  operator as a toast `Users.tsx:50-51`.
- `FormInput` already renders an `error` `<p>` `FormElements.tsx:26` — but with no `id` and
  no `aria-describedby`, and the create form passes no `error` at all `Users.tsx:248-256`
  (SC 3.3.1/3.3.3, hand-checked: axe-core has no rule for 3.3.1/3.3.3).
- Prevent: a form harness that requires each named server field error to land on its control.

### F14 — the roster's only interaction is a mouse click · severity 2 · `code`

- `<tr onClick>` with no `tabIndex`, `role` or key handler `Users.tsx:117-120`; the detail
  panel — the only place role, edit and status actions exist — is unreachable by keyboard
  (SC 2.1.1, a re-runnable failure). The role pills inside the panel are real `<button>`s
  `:183-190`, so the reachability gap is exactly one level up.
- `DataTable` has no `aria-sort` and no caption `DataTable.tsx:28-41`; there is no sorting to
  announce, and the one real order (`created_at DESC` `db.rs:492`) is unstated.
- Prevent: a `<button>` inside the first cell (or a row-level `role="button"` with key
  handling) plus a caption; the table primitive is shared, so one change fixes every page.

### F15 — the search field is one placeholder and its promise is narrower than its query · severity 2 · `code`

- `SearchInput` renders an `<input>` with a `placeholder` and no accessible name
  `AdminPrimitives.tsx:57-74`; the call site says "Search by name or email..."
  `Users.tsx:107`.
- The query also matches `role`, `tenant_name` and `user_id` `db.rs:482-493` — under-promising
  costs discovery: the operator who wants "all viewers" will not type into a box labelled
  name-or-email, and there is no status filter at all although three stat cards are
  status-based `Users.tsx:102-104`.
- Prevent: give the control a label and a hint listing what it matches, or narrow the query to
  match the label.

## 5. Recommendations, with the reference for each

| # | Recommendation | Reference (read 2026-09-20) | What we adopt |
|---|---|---|---|
| 1 | Add the `app.admin_bypass` branch to the `users` policy and route the users handlers through the bypass helper | this repository's own migration 068 `db/migrations/068_admin_bypass_rls.sql:1-52` | the same fix, for the table it skipped |
| 2 | Never accept a caller-supplied password for a new account; issue a one-time token and a required "set password" step | NIST SP 800-63B Rev 4 §3.1.1 (`https://pages.nist.gov/800-63-4/sp800-63b.html`); Keycloak 26.7.4 Server Administration Guide "required actions" (`https://www.keycloak.org/docs/latest/server_admin/index.html`) | required-action on first login |
| 3 | Deactivation revokes sessions | Keycloak 26.7.4 Server Administration Guide — "Session management … Admins and users themselves can view and manage user sessions" | session list + revoke on deactivate |
| 4 | One role source served by the backend; delete the three literals | Keycloak's role model (same guide, "roles"/"user role mapping") | a role endpoint the UI reads |
| 5 | Render the true total and page the roster | this repository's `Pager` usage on its sibling list pages `components/ui/Pager.tsx:10-28` | reuse, not new UI |
| 6 | Enforce module permissions in a guard, or delete the editor | — none cited; no artifact read for this one | a guard reading `users.permissions` |

## 6. Triage

| Feature element | Verdict | Deciding metric | Threshold | Timeframe | Action | Flag / owner |
|---|---|---|---|---|---|---|
| Global users list + search | **fix** | rows returned vs `total` (`admin.rs:4458`); distinct users created per week | any `total > 200` **or** zero rows with a non-empty `users` table | 14 days after the F1 fix lands | F1, then F5/F8 | none today — owner: admin backend |
| Create user | **fix** | create-to-first-login rate (§2) | < 50% within 7 days of activation | 30 days | F2, F13 | none |
| Activate / deactivate | **fix** | deactivated users with a live session after 15 min (from `refresh_tokens` vs `users.is_active`) | any > 0 | 14 days | F4 | none |
| Role change | **fix** | role-change requests rejected with "Invalid platform role" in the access log | any > 0 | 7 days | F3 | none |
| Module permissions | **cut or fix** | requests denied by a module check | 0 (no check exists) | 30 days | F10 — cut the editor, or ship the guard | owner needed before the cut can happen |
| Profile edit | **fix** | 500s on `PUT /users/{id}` | any > 0 | 30 days | F11 | none |
| Detail panel | **bet** | fraction of sessions that open a panel and take an action from it | < 10% | 30 days | if low, fold the actions into the row (F9/F14) | none |

No flag or owner exists for any of these today, which is itself the triage finding: a cut
nobody owns will not happen.

## 7. Accessibility level

Claimed level: **none claimed**. The code uses semantic `<table>`/`<th>`/`<label>`/`<button>`
in places, which is consistent with an AA intent, but no conformance claim is made anywhere in
the repository and no axe-core sweep ran in this arm. The hand-checks SC 2.1.1 (F14), 3.3.1/3.3.3
(F13), 3.3.4 (deactivate), 4.1.3 (result count) and 2.5.8/1.4.3/1.4.10 (unmeasured) are the
ones the automated tools would not have covered even with a running app.

## 8. Capability-change proposal (required by F2 and F4)

A screen-level fix cannot reach either finding, because both need a layer that does not exist.

| Heading | Content |
|---|---|
| Capability | A new account receives a one-time secret through a channel the requester does not control, and a deactivated account's sessions stop being valid |
| Absence proof | no mailer module in `admin/backend/src` (grep `smtp|lettre|send_mail|mailer` → 0); no `must_change_password`-shaped column on `users` (`db.rs:469-525`, `db/migrations/016` is the last `ALTER TABLE users` before 107); no refresh-token deletion in the deactivate path (`admin.rs:835-856`) |
| Contract delta | `db/migrations/1xx_user_provisioning.sql`: `ALTER TABLE users ADD COLUMN credential_state TEXT NOT NULL DEFAULT 'active'` + `user_credential_tokens(token_hash, user_id, expires_at, used_at)`; `PUT /api/v1/admin/users/{id}/deactivate` gains a `revoke_sessions: bool` default true |
| Migration | expand (add columns, backfill `credential_state='active'`), migrate (create path writes `'pending'`), contract (drop the password field from the request body) with a dated contract step |
| Rollout | flag `admin_users_credential_flow`, boolean, lifetime 2 releases, initial exposure 0%, kill-switch owner: admin backend, abort threshold: create-to-first-login rate below the 30-day baseline (unmeasured today) within its window |
| Verification | a test that fails before and passes after: created user's stored hash is not the caller's input, and a deactivated user's refresh token is rejected |
| Reversibility | the new path writes to two new columns and one new table; restore step: keep the password field and the old insert behind the flag until the contract step, rollback = flip the flag |
| Decision | ADR: context (F2/F4), decision (required-action instead of admin-typed credential), status proposed, consequences (needs a delivery channel or a copy-once link), supersedes nothing |
| Appetite | two weeks, out of bounds: SSO/MFA work, the app backend, any other admin page |

Rejectable artifacts: the migration diff, the flag with a type and lifetime, the ADR with a
status, the pre/post test pair. Prose alone was not accepted here.

## 9. What this analysis did not look at, and what would flip it

- **The running app**: no DOM/a11y tree, no screenshot, no axe-core, no page measurement, no
  console/network log, no `PerformanceObserver` (LCP/INP/CLS), no 320/768/1280 breakpoint, no
  dark mode, no 200%-text pass. Every §3.4 row marked `[NOT CHECKED]` would move, and F14
  would become a re-runnable failure with a screenshot behind it. **This is the largest gap in
  the artifact and the base arm could not close it.**
- **Behaviour**: no telemetry and no database, so F1's zero-rows consequence and F4's session
  window are source-read inferences with named falsifiers, not measurements. One query against
  a seeded instance settles F1 outright.
- **The sibling surfaces**: `TenantDetail.tsx`'s user table, `UserSearchSelect`, and the
  `Requests` approval flow were read only where they share a component or contradict a
  convention; the other fifteen admin pages are out of scope.
- **Competition**: no comparison was run. Two external sources are cited (§5) as *references
  for a recommendation*, read 2026-09-20, and there is no competitor artifact, version or
  review-theme count in this artifact — a competitor fact needs its URL and the date it was
  read, and none was collected here.
- **Independence**: one rater, so no severity is the mean of three; the skill's own position
  is that a single rater is too unreliable to be trusted for severity.
- What would change the conclusions: `BYPASSRLS` on the app's DB role (kills F1); a mailer
  reached from another module (weakens F2); a guard reading `users.permissions` in the app
  backend (kills F10); an existing incident report naming create-to-first-login (would move
  the triage to *fix now*).

## 10. Scorecard

| Dimension | Score | Anchor reading |
|---|---|---|
| Evidence relevance | 4 | every finding's citation was read; F1/F4 carry named falsifiers because the consequence is inferred rather than observed |
| Class discipline | 3 | every finding has exactly one class, and `ui-observed` is honestly absent rather than faked — but no finding reaches the class the method prefers |
| Depth | 3 | component × state reached by reading source; nothing measured, no state read from a running surface |
| Image evidence | 1 | no screenshot exists or was read; blur and grayscale tests not run |
| Axis coverage | 4 | value, usability-from-source, feasibility, triage present; competition absent with its reason stated |
| Metric integrity | 5 | the one metric is a ratio with numerator, denominator, window and source, and its absence from the product is F12 |
| Solution plurality | 4 | three solutions against a criterion pre-stated in §2; none is benchmarked |
| Feasibility grounding | 5 | every implementation claim is a `path:line`; the two absences name the search that proves them |
| Decision quality | 4 | keep/fix/cut/bet with metric, threshold, timeframe and action; owners are named as missing, which is honest but incomplete |
| Scope calibration | 5 | §9 names the running app, behaviour, siblings and competition, and what would flip each conclusion |

Mean 3.8 → **weak accept** by the skill's thresholds, with one dimension at 1. The 1 is
`Image evidence`, and it is a property of the arm (no running app), not of the feature: an
arm that can open the app would raise it without changing any finding's substance.
