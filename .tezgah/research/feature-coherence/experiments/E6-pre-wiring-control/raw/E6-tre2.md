# Product analysis + feature coherence: the admin Users area (aibim-app)

Feature under analysis: the admin **Users** area of `/Users/rizax/Projects/aibim-app`
(Rust axum + sqlx admin backend; React 19 SPA). Unit of analysis is the feature, not
the screen: the entity is a *user account*, its actions are list / read / create /
update profile / change role / activate / deactivate / manage module permissions, and
its layers are the surface, the route, the authorization, the service, and the
persistence.

Skills applied as written: `skill://product-analysis` (five axes, one evidence class
per finding) and `skill://feature-audit` (the layer-coherence pass, matrices first).
Repository HEAD at analysis time: `a6e47df`. Analysis date: 2026-09-21.

## 0. Method, and what the brief forbade

| Constraint | Consequence for this artifact |
|---|---|
| Read-only on `aibim-app`; no Docker, no build | **No running app.** The whole `ui-observed` evidence class and the entire `analyze-app` half of the usability axis are unavailable. In the skill's own terms: *"a UI claim is read from the running app through `analyze-app` … never inferred from source"*, so **every surface finding below is class `code`, at component/state level in the source, not a reading of a running surface**. No screenshot was taken or read; the blur test, the grayscale test, the breakpoint sweep, dark mode, 200% text and the axe-core sweep were **not run** (each is named again in §5 rather than omitted). |
| `tezgah-research init` writes under `.tezgah/research/`, which the brief puts out of bounds (read *and* write) | The research line was **not** initialised and `tezgah-research check` was **not** run. This artifact is therefore a document, not a checked research workspace; the skill's artifact list is followed by hand. |
| ~12-minute box, one feature | The five axes are addressed; the competitive axis is answered as *not performed* with its reason, per the skill's "a section with no evidence says so in one line". |

Rater count: **1 agent, 3 passes from different entry points** — (1) the React surface,
(2) the HTTP/route contract with no UI, (3) the SQL and persistence layer. The skill is
explicit that one rater is *"too unreliable to be trusted"* for severity, so every
severity below is a **single-rater severity**, unconfirmed by a second rater.

## 1. Measurement readiness (the gate)

**We cannot see this feature's behaviour today.** Findings, in the skill's own terms:

- There is **no product analytics** in the admin SPA: `grep -rln "posthog\|plausible\|gtag\|mixpanel\|analytics" admin/frontend/src` → one false positive (the word appears as a module name in `TenantDetail.tsx`), no instrumentation library in `admin/frontend/package.json`.
- There **is** an event stream, and it is the only one: every mutating handler calls
  `audit_admin_action` (`admin/backend/src/handlers/admin.rs:54`), which inserts a
  hash-chained row into `audit_log` (`admin.rs:227` → `INSERT INTO audit_log` at
  `admin.rs:251` and `admin.rs:274`). Actions recorded include `user_create`,
  `user_update`, `user_role_change`, `user_deactivate`, `user_activate`,
  `user_permissions_update` (`admin.rs:817, 852, 952, 1006, 4528, 8455`).
- No frontend observability exists at all, and **no frontend test harness exists**: `git ls-files admin/frontend | grep -E "test|spec"` → **0 files**.

So: an audit-trail numerator exists server-side; a per-user denominator (how many
operators attempt what) does not. Any `behaviour`-class ratio this analysis wants must
be computed from `audit_log`, and **none was computed** — no database access under this
brief. That is the first finding, not a footnote.

## 2. The objective: Goals → Signals → Metrics

**Goal.** Operators change who has access to a tenant safely, and the resulting access
state is the one they intended — an admin access surface's goal is the integrity of the
access state, not engagement (HEART adapted: Happiness/Task-success are not the
relevant goals for a console).

**Signals.**
- S1 an access change completes end to end without a second, unrecorded channel.
- S2 the console shows the access state it acts on (no silent overwrite, no mislabelled count).

**Metrics** (a metric with no goal above it is dropped; raw counts are refused; each is a
ratio with its definition and window — **defined, not measured**, §1):

| # | Metric | Definition (numerator / denominator, window) | Source | Observed? |
|---|---|---|---|---|
| M1 | Access-change completion | distinct actors with a `user_*` `audit_log` row followed within 24 h by a contradicting `user_*` row on the same `resource_id` / all distinct actors with a `user_*` row, 7-day rolling | `audit_log` (admin.rs:251) | **no** |
| M2 | Role-grant rejection rate | 4xx on `PUT /api/v1/admin/users/{id}/role` / all requests, 7-day rolling | no metrics exist for users (`grep -n "user" admin/backend/src/metrics.rs` → **0 matches**) | **no** |
| M3 | Rendered-count fidelity | rows shown / `total` returned by the same request, per request | `admin.rs:4406-4414` (`count` from `COUNT_FILTERED`) | **no** (computable without a DB: §4 F3) |

Refused as metrics: "200 users" (a raw count, no goal above it, and itself a capped
page — §4 F3). `admin_stats`-style counters are held in reserve, not listed, because
they carry no window here.

## 3. Opportunities, solutions, risks

An **opportunity is a user need, never a feature** (Torres). Evidence class per line;
`user-verbatim` is **absent in this session** — there is no interview, ticket, review or
message in scope, so no opportunity below is user-validated, and none is presented as if
it were.

| # | Opportunity (a need) | Class | Citation |
|---|---|---|---|
| O1 | An operator must be able to tell "nothing here" from "we do not know" | `code` | `Users.tsx:44-47`, `DataTable.tsx:6-19`, `QueryErrorState.tsx` exists unused-by-this-page |
| O2 | An operator must see the access state a control will overwrite before overwriting it | `code` | `TenantDetail.tsx:393`, `admin.rs:771-781`, `db.rs:469-472` |
| O3 | An account created here must be usable by the person it was created for | `code` | `admin.rs:1004-1019`, no mailer/reset route (§4 F5) |
| O4 | Nobody, including the actor, should be able to lock the console out | `code` | `Users.tsx:207-217`, `db.rs:515-516` |

There is **no Opportunity Solution Tree with user scoring** (no interviews → no
opportunity score), so the tree stops at needs.

**Three candidate solutions against a pre-stated criterion.** Criterion, stated before
comparing: *the cheapest change that makes an access change verifiable end to end and
impossible for a later action to silently undo.*

| Candidate | Covers | Cost / new layer | Against the criterion |
|---|---|---|---|
| S1 Surface what exists | O1, O2, and the capped-count defect | no backend change; 1 page + 2 client functions (`Pager.tsx:10` exists; `GET …/users/{id}` and `GET …/users/{id}/permissions` exist, `main.rs:284, 339`) | **wins** — closes 4 of the 5 layer disagreements with no new layer |
| S2 Prove the contract | O2, O4 | a contract test asserting every offered role/field is accepted by the handlers; no new layer | wins as the *prevent* half; proves nothing about O3 |
| S3 Add the missing layer | O3 | a mailer/invite-token layer that does not exist | loses on cost alone; correct for O3, and by the feature-audit rule it may **not** be shipped as a screen recommendation → §6 proposal |

**Risks by class, each with the cheapest falsifying test.**

| Risk | Class | Cheapest test that would falsify it |
|---|---|---|
| The access state an operator acted on was stale (F6 overwrites stored permissions) | value | create a user, set modules to `["proxy"]`, reopen Manage, tick nothing, Save; read `user_permissions` — falsified if the stored set survives |
| The list misreports the tenant's user base above 200 rows (F3) | usability | insert 201 users, read the header count vs `total` from the same response — falsified if they agree |
| A load failure is indistinguishable from an empty tenant (F2) | usability | `browser_network_state_set` on `/api/v1/admin/users` to force a 500 and read the page — falsified if the page shows anything but "No users found" |
| `super_admin` cannot be granted although the UI offers it (F4) | feasibility | call `PUT …/role {role:"super_admin"}` as a super_admin — falsified if it returns 200 (the vendored unit test at `admin.rs:8883-8899` says it returns 400) |
| The created user never receives a credential (F5) | viability | grep the create path for any outbound delivery artifact — already run, falsified if a mailer/invite path is found |
| A last super_admin can deactivate themselves (F7) | viability | log in as the only super_admin, deactivate self, retry login — falsified if it is refused |

## 4. Findings, most severe first

Every finding names **one** evidence class. Classes available under this brief:
`code` (a `path:line` in the repository), `external` (a URL read in this session —
one: the W3C APG Combobox pattern, read 2026-09-21),
`behaviour` (a ratio with a definition — none produced, §1),
`ui-observed` (a running screen — **unavailable**, §0), `user-verbatim` (none).

---

**F1 · The only path into the detail panel is a mouse click on a table row.**
Class `code`. — `Users.tsx:113-119`: `<tr className="table-row-hover cursor-pointer" onClick={() => openUserPanel(u)}>` with no `tabIndex`, no `role`, no `onKeyDown`. The detail panel is where *Edit Profile*, *Change Role* and *Deactivate* live (`Users.tsx:196-217`), so those three actions are unreachable by keyboard — SC 2.1.1, a failure, not a judgement.
Severity **4** (frequency: every keyboard user; impact: three capabilities blocked; persistence: permanent). Single-rater.
**Prevent** — no mechanical prevention exists: there is no frontend test harness (0 test files). The cheapest one that would have failed: an RTL assertion that the row is focusable and activates on `Enter`. Until it exists this stays a review item, and it is a checklist entry for `DataTable` (a row with a click handler must be a button or a grid row).

**F2 · A failed load renders as "No users found".**
Class `code`. — `Users.tsx:44-47` destructures only `{ data, isLoading }`; `DataTable.tsx:3-8` has only `isLoading`/`isEmpty`; `Users.tsx:111` passes `isEmpty={users.length === 0}` and `emptyText="No users found"`. The handler returns 500 on a DB error (`admin.rs:4460-4464`), so a database outage produces an *empty tenant* on screen. The sibling convention exists and is unused here: `QueryErrorState.tsx:6-16`, used at `ThreatIntel.tsx:13`.
Severity **4** (frequency: any DB blip; impact: the operator concludes the tenant has no users; persistence: until refresh). Failure. Single-rater.
**Prevent** — make `QueryErrorState` mandatory in the page template for every `useQuery`, and assert it with a route-mocked 500. No harness exists, so today: review item.

**F3 · Every headline number is computed over a capped page, and the server's `total` is discarded.**
Class `code`. — `Users.tsx:46` requests `limit: 200` and never sends `offset`; `Users.tsx:95` renders `${allUsers.length} users across all tenants`; `Users.tsx:101-104` computes Total/Active/Inactive/Admins by filtering the fetched page. The API returns a real total from `COUNT_FILTERED` (`admin.rs:4434-4443`, response `admin.rs:4458`), the client type declares it (`api/admin.ts:374`), and **nothing reads it**. Above 200 users every number on the page is wrong and the truncation is invisible. `Pager.tsx:10` exists and other pages use it (`ThreatIntel.tsx:247, 324, 407`).
Severity **4** (frequency: any tenant base over 200; impact: wrong operational numbers, no signal; persistence: constant). Failure. Single-rater.
**Prevent** — assert rows-rendered equals the response's `total` for the same query, or render `total`; also an assertion that the page's `Pager` is present when `total > pageSize`. No harness exists → review item, with `Pager` adoption as the fix.

**F4 · The UI offers `super_admin` and the server refuses it: a dead control.**
Class `code`. — `Users.tsx:14` `const ALL_ROLES = ['super_admin', 'admin', …]`, rendered at `Users.tsx:85, 179-192` for a super_admin (and again at `TenantDetail.tsx:353, 382`). The server's assignable set excludes it, `admin.rs:873`, and `validate_platform_role_grant` rejects it, `admin.rs:879-883`; the rule is *pinned by unit tests*, `admin.rs:8883-8886, 8894-8899`. The intent is documented — *"super_admin can only be created via the CLI tool"* (`admin.rs:872`) — and the surface contradicts it. The click returns 400 "Invalid platform role" surfaced only as a transient toast (`Users.tsx:71`).
Severity **3** (frequency: any super_admin, once; impact: a control that cannot work, plus a 4xx in the audit trail; persistence: every session). Failure. Single-rater.
**Prevent** — one source for the role enum (the server constant, or a shared generated type) plus a contract test asserting every role option the UI can render is accepted by `validate_platform_role_grant`. Today the test exists only for the server half, which is exactly why the drift survived.

**F5 · A user created in this area cannot receive its credential: the action has no delivery path.**
Class `code`. — the admin panel path inserts via `CREATE_INACTIVE` (`admin.rs:937-940`, `db.rs:521-524`, `is_active = false`) and answers *"User created (inactive). Activate after approval."* (`admin.rs:967`); the admin types the password into the form (`Users.tsx:250`). The registration-approval path inlines its own `INSERT … is_active, true` (`admin.rs:1152-1155`). A **third** create path is stricter still: `admin_enterprise_scim_user_upsert` (`admin.rs:5526`) generates `let random_password = uuid::Uuid::new_v4().to_string()` (`admin.rs:5680`), hashes it (`admin.rs:5681-5683`) and inserts an **active** user (`admin.rs:5689-5691`) — the plaintext is bound into no response, no log and no store, so even the admin who triggered it cannot know the credential the account was created with. It is UI-reachable (`api/admin.ts:724`). Searches that prove the absence of any delivery layer: `grep -rn "smtp\|mailer\|send_email\|send_mail\|Mail::" admin/backend/src --include=*.rs` → **0 matches**; `grep -rn "reset\|forgot" admin/backend/src/main.rs` → **0 routes**. If the hand-carried credential is lost the account is unrecoverable except by rewriting `password_hash` (`db.rs:540`).
Severity **4** for the product (frequency: every create; impact: the created account is unusable, and for the SCIM path not even the creator knows the password; persistence: until an out-of-band fix). Failure. Single-rater.
**Prevent** — a test asserting a delivery artifact exists before the create response is 201; by the feature-audit rule this needs a layer that does not exist, so it is written as the capability-change proposal in §6, not as a screen recommendation.

**F6 · The permission editor starts empty and overwrites what it cannot read.**
Class `code` (documented intent vs the code that enforces it — both sides cited). — `TenantDetail.tsx:393` seeds the checkboxes from `u.permissions?.modules ?? []`; `u` comes from `fetchTenantUsers` (`api/admin.ts:364-371`) → `admin_tenant_users` (`admin.rs:757-782`), which maps exactly five fields (`user_id, email, full_name, role, is_active`) out of `LIST_BY_TENANT` (`admin.rs:776-779`), a query that selects no permissions (`db.rs:469-472`). The **documented intent** says the field is populated ("populated by tenant detail view", `types/admin.ts:95-96`) and a GET that could populate it exists (`admin.rs:8477-8500`) with **no client caller**: `grep -rn "fetchUserPermissions\|/permissions" admin/frontend/src` → only `api/admin.ts:922` (the PUT). Saving therefore writes the set ticked in a session that began empty — silently deleting stored modules.
Severity **4** (frequency: any use of Manage; impact: silent privilege deletion, and a privilege *grant* is also possible without seeing the prior state; persistence: written to the DB). Failure. Single-rater.
**Prevent** — a contract test asserting the tenant-users payload carries `permissions.modules`; or read-before-write. There is no contract test for this payload today → review item plus that test.

**F7 · Deactivate is one unconfirmed click with no self- or last-admin guard.**
Class `code`. — `Users.tsx:207-217` mutates on `onClick` with no dialog; the server's `DEACTIVATE` is an unconditional update (`db.rs:515-516`) with no self check and no count of remaining active super_admins; the action *is* audited (`admin.rs:847-857`). The repository's own convention for a destructive admin action is a confirmation: `Requests.tsx:513`, `ThreatIntel.tsx:267, 342, 425`, `DetectionRules.tsx:80`. **A pass row with a window:** deactivation does block refresh — `GET_ACTIVE_BY_ID` (`db.rs:546-548`) is re-read in `handle_refresh` (`handlers/auth.rs:688`) and answers *"User not found or deactivated"* — while an already-issued access token stays valid for up to **900 s** (`auth.rs:463`).
Severity **3** (frequency: any deactivation; impact: a lockout with no way back in, or an accidental self-lockout; persistence: until another admin acts). Failure for the lockout case, judgement for the missing confirmation. Single-rater.
**Prevent** — a handler-side guard plus a test: *a super_admin cannot deactivate the last active super_admin*. That test does not exist; when it does, it fails on this commit.

**F8 · Profile updates validate nothing, and clearing a field persists an empty value.**
Class `code`. — `admin.rs:4511-4512` reads `full_name`/`email` verbatim; `UPDATE_PROFILE` uses `COALESCE($2, full_name), COALESCE($3, email)` (`db.rs:508-510`); the client always sends both keys (`Users.tsx:227-243`), so a cleared field binds `''` (not NULL) and *wins*: the email can become empty, and login matches on it (`db.rs:533`, `WHERE email = $1`) so the account is then unreachable. Duplicate email → the generic arm returns 500 "Internal server error" (`admin.rs:4537-4541`) while create maps the same class to 409 (`admin.rs:975-978`). The typed-body pattern that would fix this already exists in this file: `UserRoleUpdateReq` with `deny_unknown_fields` + `validate` (`admin_dto.rs:134-140`).
Severity **3** (frequency: any edit that clears a field, or any duplicate email; impact: unreachable account / misleading 500; persistence: written to the DB). Failure. Single-rater.
**Prevent** — bind the update to a typed request (existing pattern) and assert a unique-violation maps to 409; the assertion does not exist today.

**F9 · The tenant picker is a hand-rolled combobox with no roles and no keyboard entry point.**
Class `code` + `external`. — `TenantSearchSelect.tsx:86` opens the popup from an `onClick` on a plain `div` (no `tabIndex`), options are clickable `<button>`s (`:154-156`); `grep -n "aria-\|role=" TenantSearchSelect.tsx UserSearchSelect.tsx` → **0 matches**. Against the APG Combobox pattern (W3C, read 2026-09-21): `role="combobox"`, `aria-expanded`, `aria-controls`, `aria-activedescendant`, and the `listbox`/`option` roles are all required-or-expected and all absent. The field is server-required (`admin.rs:913-916`) and in *Create User* reachable only through this control (`Users.tsx:256`). The same component family is the user picker in `Enterprise.tsx:1425, 1493, 1669`.
Severity **4** for a keyboard/screen-reader operator, **2** for a mouse-only operator; reported as **4/2 split** rather than one number. Failure. Single-rater.
**Prevent** — role and accessible-name assertions on the picker in a component test. No harness exists → review item; the APG checklist entry belongs on the `TenantSearchSelect`/`UserSearchSelect` state matrix.

**F10 · Modal, detail panel and every labelled field lack their semantics.**
Class `code`. — `Modal.tsx:14-28`: an overlay `div` whose `onClick` closes (`Modal.tsx:18`), no `role="dialog"`, no `aria-modal`, no labelling, no Escape, no focus-in, no focus return. `DetailPanel.tsx:12-40`: the scrim closes the panel (`DetailPanel.tsx:14`), so a stray click outside destroys an in-progress edit — `Users.tsx:133` `setSelectedUser(null); setIsEditing(false)` — with no confirmation. `SearchInput` (`AdminPrimitives.tsx:57-75`) has a placeholder and no label or `aria-label`, so the search box has **no accessible name**. `FormInput`/`FormSelect` (`FormElements.tsx:5-26, 34-50`) render `<label>` with no `htmlFor` and an input with no `id` (`FormElements.tsx:17-18`) — the label is not associated. SC 4.1.2, 1.3.1, 3.3.2, 2.4.3.
Severity **3** (frequency: every page that uses these primitives; impact: assistive tech cannot name the dialog or the fields; the edit loss is a data-loss path; persistence: product-wide). Failure. Single-rater.
**Prevent** — a `Modal`/`DetailPanel` state-matrix checklist entry (role, name, Escape, focus in/out, scrim policy) plus an axe sweep in CI. No sweep exists → review item.

**F11 · Validation errors are transient toasts with no field association and no focus.**
Class `code`. — `Users.tsx:52, 60, 71, 80` route every failure to `toast.error`; `FormInput` accepts an `error` prop (`FormElements.tsx:4-7, 21-23`) that **is never passed** in the create form (`Users.tsx:248-256`). The server's messages — *"Password must be at least 8 characters"* (`admin.rs:916-919`), *"email, password, and tenant_id are required"* (`admin.rs:908-911`) — arrive only after a round trip and vanish on the toast timer, with nothing in the DOM and nothing moved into focus: SC 3.3.1, 3.3.3, 4.1.3.
Severity **3** (frequency: every rejected create/edit; impact: the operator must guess which field; persistence: per attempt). Failure. Single-rater.
**Prevent** — bind the handler's message to the field (`error` prop exists) and assert the text is in the DOM after a rejected submit.

**F12 · Search claims less than it does, and its active state is invisible.**
Class `code`. — the placeholder says *"Search by name or email…"* (`Users.tsx:107`) while `LIST_FILTERED`/`COUNT_FILTERED` also match `role`, `user_id` and the tenant name (`db.rs:484-501`); there is no result count, no active-filter indicator and no clear action, and the empty state reads "No users found" (`Users.tsx:111`) whether the tenant is empty or the search missed. Filter discoverability and a visible active state are named in the feature-audit data-view rules.
Severity **2** (frequency: daily; impact: an operator believes a role search is unsupported; persistence: none). Judgement (a violated rule in context — the query is more capable than the label claims, which is not automatically a problem).
**Prevent** — derive the placeholder from the query, or narrow the query; an assertion that a role search returns a row.

**F13 · Role change signals state by colour, offers self-demotion, and reports nothing while in flight.**
Class `code`. — `Users.tsx:179-192`: the current role is indicated by `RoleBadge` colour only (`roleColors`, `Users.tsx:16-18`) → SC 1.4.1 (state by colour alone); the whole button set disables during a mutation with no per-action progress (`disabled={active || roleMut.isPending}`) while the neighbouring deactivate button does show *"Updating…"* (`Users.tsx:215`); and a super_admin is offered their own role button, so self-demotion is one click. `admin.rs:789-832` has no self check.
Severity **2** (frequency: every role change; impact: ambiguity and an unrecoverable self-demotion for the last super_admin; persistence: per action). Judgement for the colour/progress half, failure for the self-demotion half. Single-rater.
**Prevent** — a text label for the current role and a self-demotion guard with a test.

**F14 · Cancelling the create form keeps the typed password in memory and re-shows it.**
Class `code`. — `Users.tsx:48` holds `form` in page state; the success path resets it (`Users.tsx:51`) but Cancel (`Users.tsx:261-262`) and the modal's own close (`Users.tsx:244, 246`) only flip `setShowCreate(false)`. Reopening shows the previous email/password/tenant verbatim.
Severity **2** (frequency: any abandoned create; impact: a credential left in the DOM of a shared admin workstation and a stale tenant/role on the next attempt; persistence: until the tab closes). Judgement. Single-rater.
**Prevent** — reset the form on close (one line), asserted by a test that reopens and finds empty fields.

**F15 · A malformed tenant id returns a 500, and the create form cannot catch it.**
Class `code`. — the picker allows typed text (`TenantSearchSelect.tsx:94-100`), the handler only checks emptiness (`admin.rs:908-911`) and binds `$5::uuid` (`db.rs:522-524`); the error branch classifies only duplicate-key text and otherwise returns 500 "Failed to create user" (`admin.rs:970-984`). Partial, dependent on the picker's free-text behaviour, which is a state I could not read from the running app.
Severity **2** (frequency: only a malformed submit; impact: a misleading error and a 5xx in the logs; persistence: per attempt). Judgement, [NOT CHECKED: whether the picker permits a value that is not a tenant id — needs the running app].
**Prevent** — validate the reference client-side and map a malformed-uuid error to 400; assert the 400.

### Pass rows (agreement between layers is part of the result)

| # | Agreement | Citation |
|---|---|---|
| P1 | Every route in this feature sits behind one platform-admin gate: `require_admin_access` → `is_platform_admin_role` | `main.rs:441-444`, `middleware.rs:68-81`, `middleware.rs:36-38` |
| P2 | Handlers with **no** `AdminClaims` extractor are still platform-admin-only, which is why that absence is not a finding | `admin.rs:757`, `admin.rs:4394`, `admin.rs:4469`, `admin.rs:8477` (all under the P1 layer) |
| P3 | Cookie-authenticated mutations require the CSRF double-submit token | `middleware.rs:139`, `middleware.rs:246-270` |
| P4 | Every mutation in the feature writes an `audit_log` row with the actor from the token, never from the body | `admin.rs:54`, `admin.rs:251`, `admin.rs:274`, and the reviewer-identity defence `admin.rs:1081-1084` |
| P5 | The role-grant rule agrees with the UI for the four roles the server accepts | `admin.rs:873-887` vs `Users.tsx:13, 85` |
| P6 | Deactivation blocks refresh but leaves ≤900 s of access-token validity | `handlers/auth.rs:688`, `handlers/auth.rs:463` |
| P7 | Duplicate email on create maps to 409 with a human message | `admin.rs:977-984` |
| P8 | The table uses real `<table>`/`<th>` | `DataTable.tsx:28-40` — SC 1.3.1 holds; the gap is the missing accessible name/caption, folded into F10 |

## 5. The usability section

**Scope.** Task: administer user accounts (list → find → act). Section: the `/users`
page and the per-tenant users table in `/tenants/{id}`. User group: platform admin
(`super_admin`/`admin`). Device: desktop web. Breakpoints in scope: 320, 768, 1280 CSS px.
**Heuristics checked** (Nielsen): visibility of system status, match to the real world,
user control and freedom, error prevention, recognition over recall, help users
recognise/diagnose/recover from errors, aesthetic and minimalist design, help and
documentation. **Not checked:** consistency could be checked only against the
repository's own convention, which is done in §4 (F3, F7, F10).

**The state matrix.** Rules: every interactive component and every data view gets a row;
the states are default, hover, focus, active, disabled, loading, error for interactive
ones and empty, loading, skeleton, error, offline, partial, long-text/overflow,
permission-denied for data views. **Every "does it exist" cell is read from source**; a
state marked `[NOT CHECKED]` needed the running app. 12 rows.

| # | Component / data view | States present in source | States that do **not** exist (finding) | Not checked |
|---|---|---|---|---|
| S1 | Users data table (5 columns) | default, loading (`DataTable.tsx:43-51`), empty (`:53-62`) | **error (F2)**, **partial/truncated (F3)**, long-text strategy (no truncation rule), offline | aria/caption (F10); reflow at 320 px |
| S2 | Search input (`SearchInput`) | default, focus-implicit (no explicit focus-visible rule) | **accessible name (F10)**, clear action, results count (F12) | contrast of the placeholder colour |
| S3 | Table row (opens the panel) | default, hover (`table-row-hover`) | **focus, keyboard activation (F1)**, selected-by-keyboard | — |
| S4 | Role change buttons (5) | default, disabled, active-by-colour | **text state (F13)**, per-action loading (F13), confirmation of what changes | target size, focus ring |
| S5 | Activate/Deactivate button | default, pending ("Updating…") | **confirmation (F7)** | — |
| S6 | Create User modal | open, pending ("Creating…") | **role/name/Escape/focus (F10)**, inline error (F11), reset on cancel (F14) | — |
| S7 | Tenant picker (`TenantSearchSelect`) | closed, open, selection, clear | **every APG combobox state (F9)**; loading/empty/error of the popup are unreviewed in the same pattern | keyboard walk |
| S8 | Detail panel | view mode, edit mode | **role/name/Escape/focus (F10)**, unsaved-changes guard (F10) | — |
| S9 | Tenant-users table (TenantDetail) | default, empty ("No users") | error, truncation (no pager at all here), long-text | — |
| S10 | Module permission editor | collapsed, expanded, checked/unchecked | **loaded-from-server (F6)** — the initial checked state is always empty; saving/error state absent | — |
| S11 | Role `<select>` in TenantDetail | default | loading, disabled during mutation, error rollback | — |
| S12 | User picker (`UserSearchSelect`) | closed, open, selected, cleared | same APG gaps as S7; no "no results" copy; no create path for a missing user | — |

**Findings at their level.** F1 (component/state), F2 (screen/state), F3 (screen),
F4 (component), F5 (feature/flow), F6 (component/state), F7 (component + handler),
F8 (field/contract), F9 (component), F10 (component × 5 primitives), F11 (field/state),
F12 (property: label vs query), F13 (property: colour-only state), F14 (state),
F15 (field/state). Severities are in §4, each a single-rater severity.

**Screenshots read: none** — and therefore the blur test, the grayscale test, the
breakpoint sweep (320/768/1280), dark mode and 200% text were **not run**. Stated rather
than omitted: the visual axis (hierarchy, rhythm, colour, density, platform feel) is
**uncovered** by this artifact, and no property below is reported as measured.

**axe-core sweep: not run.** WCAG 2.2 level claimed: **none** — the codebase makes no
conformance claim (`grep -rn "WCAG\|2.2 AA" admin/frontend/src` finds none), so the
level is **missing**, which is itself the answer to "which level is claimed". Of the
eight checks the skill names as hand-checks, this artifact can decide only three from
source (3.3.1/3.3.3 via F11, 4.1.3 via F11/F12, aria-modal preconditions via F10); the
other five — focus indicator visibility, target size, 320 px reflow with the table
exception, autocomplete token fitness, and whether a revealed question is announced —
are `[NOT CHECKED: needs the running app]`, as is every contrast ratio (a computation
over computed styles, and no page was rendered).

**Cognitive walkthrough** — task: *"deactivate the account of someone who has left"*,
from a new admin's position. Four questions per step (Wharton et al.; NN/g):

| Step | 1 right effect? | 2 notice the action? | 3 associate with the effect? | 4 see progress? |
|---|---|---|---|---|
| Find the user | yes | yes (search is visible) | partial — the placeholder understates what search does (F12) | no result count (F12) |
| Open the account | yes | **no** for a keyboard user (F1) | yes | panel opens |
| Choose the action | yes | yes (two large buttons) | **partial**: "Deactivate" names the action but not the effect — the panel never says the user loses panel access or that the change is reversible (F7) | "Updating…" (good) |
| Confirm | **no such step** | — | — | a toast replaces the record's own state (F11) |

The walkthrough's "no" at step 2 is the defect heuristics miss: the control exists, is
labelled correctly, and still cannot be found by keyboard.

## 6. Feasibility: the coherence matrices

Rows checked: **capability 17**, **field contract 15**, **flow/step 7**,
**interaction dependency 7**. Cells that could not be checked are marked
`[NOT CHECKED: reason]` and stay in the table.

### Matrix 1 — capability

| # | Action | Surface | Route | Authorization | Service / validation | Persistence |
|---|---|---|---|---|---|---|
| 1 | List users | yes `Users.tsx:46` | yes `main.rs:263-266` | yes P1 | yes `admin.rs:4394` | yes `db.rs:482, 494` |
| 2 | Search users | yes `Users.tsx:107` | yes `admin.rs:4408-4411` | yes P1 | yes `db.rs:484-501` | yes |
| 3 | Page users | **no** — no `Pager` on this page, fixed `limit: 200`, no `offset` | yes `admin.rs:4398-4411` | yes | yes | yes — **disagreement, F3** |
| 4 | Read one user | **no** — no client caller: the panel reuses the list row | yes `main.rs:284-285` | yes | yes `admin.rs:4469` | yes `db.rs:503` — **disagreement** |
| 5 | Create user (admin panel) | yes `Users.tsx:243-256` | yes `main.rs:265` | yes `admin.rs:922` | partial: presence + ≥8 chars (`admin.rs:908-919`), no email format, no tenant-format check (F15) | yes `db.rs:521` — **no delivery path, F5** |
| 6 | Change role | yes `Users.tsx:179-192` | yes `main.rs:256-257` | yes `admin.rs:800, 875-887` | yes typed body `admin_dto.rs:134-140` | yes `db.rs:512` — **dead option, F4** |
| 7 | Update profile | yes `Users.tsx:227-243` | yes `main.rs:284-285` | yes | **no** `admin.rs:4511-4512` (F8) | yes `db.rs:508` |
| 8 | Deactivate | yes `Users.tsx:207-217` | yes `main.rs:260-261` | yes route; **no self/last-admin rule** (F7) | none | yes `db.rs:515` |
| 9 | Activate | yes `Users.tsx:207-217` | yes `main.rs:268-269` | yes | none | yes `db.rs:518` |
| 10 | Manage module permissions | **partial** — `TenantDetail.tsx:392-427` only, never the Users page | yes `main.rs:337-341` | yes `admin.rs:8430-8436` | none (module names unvalidated) | yes — **unreadable, F6** |
| 11 | Read permissions | **no** — no client caller (`grep … /permissions` → only the PUT) | yes `main.rs:339` | yes (route only; handler has no `claims`) | — | yes — **disagreement** |
| 12 | Delete a user | no | no | — | — | no (no soft-delete in the users module) |
| 13 | Deliver a credential / reset a password | **no** | **no** (`main.rs` has no route) | — | **no** (no mailer) | n/a — **capability absent end to end, F5** |
| 14 | List a tenant's users | yes `TenantDetail.tsx:336-337` | yes `main.rs:251-253` | yes route; handler `admin.rs:757` consults no claims | none | yes `db.rs:469` |
| 15 | Bulk role/status change | no | no | — | — | — |
| 16 | Pick a user while creating something else | yes `Enterprise.tsx:1425` | yes = row 1 | yes | none | yes |
| 17 | Create/activate a user by IdP provisioning (SCIM) | yes — via `api/admin.ts:724`, no per-user surface | yes `main.rs:499-501` | yes P1 + a delegated-manager rule (`admin.rs:5659-5664`) | none; role hardcoded `'viewer'` (`admin.rs:5690`) | yes `admin.rs:5689-5691` — **no delivery path (random password), F5** |

Reading the disagreements: two capabilities are server-only (rows 4, 11 — dead
endpoints by the search above), one is unsurfaced (row 3), one is unsurfaced on the page
that owns the feature (row 10), one control is refused by the layer behind it (row 6),
one action's output has no delivery path (row 5), and one capability is absent at every
layer (row 13). Rows 1, 2, 6 (for its four accepted values), 9, 14, 16 are pass rows.
Row 13 is why §6's proposal exists: **a fix here needs a layer that does not exist**, so
it may not be reported as a screen recommendation.

### Matrix 2 — field contract

| # | Field | Column / type | Read by the API | Written by the API | Rendered (list / detail / form) | Validated | Label / enum source | Locale / format |
|---|---|---|---|---|---|---|---|---|
| 1 | `user_id` | uuid, `users.user_id` | `db.rs:503` | generated | list key, panel subtitle (`Users.tsx:136`) | — | — | sliced to 8 chars |
| 2 | `email` | text, unique | `db.rs:503` | create `db.rs:521`, update `db.rs:508` | list + panel + edit form | create: presence; update: **none** (F8) | label `FormInput` (unassociated, F10) | none |
| 3 | `full_name` | text, nullable → `COALESCE('')` | `db.rs:503` | create + update | list + panel + edit | none | `FormInput` | none |
| 4 | `role` | text | `db.rs:503` | `db.rs:512`, create | badge + buttons + `<select>` | server enum, 4 values (F4) | **four sources**: `Users.tsx:13`, `Users.tsx:14`, `TenantDetail.tsx:353`, `admin.rs:873` | `_` → space |
| 5 | `is_active` | bool | `db.rs:503` | `db.rs:515, 518`, create (`false`) | status badge (list + panel) | — | literal copy | — |
| 6 | `tenant_id` | uuid | `db.rs:503`, `db.rs:469` | create | list fallback shows 8 chars (`Users.tsx:124`) | create presence only (F15) | picker (F9) | — |
| 7 | `tenant_name` | join `tenants.name` | `db.rs:484` (list) | never (derived) | list + panel | — | — | **absent from `LIST_BY_TENANT` `db.rs:469-472`** — the same word means the page's tenant there |
| 8 | `created_at` | timestamptz | `db.rs:503` | DB default | **panel only** `Users.tsx:164-171` | — | — | `toLocaleDateString('en-US')` hardcoded |
| 9 | `last_login_at` | timestamptz, nullable | `db.rs:482-491, 503` | `db.rs:543` on login | **nowhere** — the table has 5 columns (`Users.tsx:109-110`) | — | — | — **contract field no view renders** |
| 10 | `password` | text (input only) | — | hashed `admin.rs:928` | create form only | ≥8 chars server-side (F11) | `FormInput` | never echoed |
| 11 | `password_hash` | text | never | `db.rs:540` | never | Argon2id | — | — |
| 12 | `permissions.modules` | jsonb | `db.rs` user_permissions::GET | PUT | **type claims it, wire never carries it** | none | — | — (F6) |
| 13 | `total` | int from `COUNT` | `admin.rs:4426-4447` | — | **nowhere** (`api/admin.ts:374` declares it) | — | — | — (F3) |
| 14 | `permissions` (tenant row) | text[] on tenants | `db.rs:104-106` | — | `TenantDetail.tsx:652-659` | — | — | different entity, same word |
| 15 | `invite`/`reset` token | — | — | — | — | — | — | **absent (F5)** |

Gaps that are findings: rows 9 and 13 (carried and never rendered), 12 (rendered from a
field no layer supplies → F6), 4 (one enum, four sources → F4), 2 (requiredness enforced
in one layer only → F8), 7 (one word, two meanings), 8 (a fixed locale in a product whose
data is Turkish).

### Matrix 3 — flow and step contract

| # | Step | Precondition | What it validates | What it writes | How a skip is prevented | Resume / persistence | Back-navigation retention | Where an error lands |
|---|---|---|---|---|---|---|---|---|
| 1 | Open *Create User* | platform admin (route gate P1) | — | nothing | n/a | none needed | **cancel keeps the whole form, including the password (F14)** | — |
| 2 | Fill the form | none | client: **nothing** | nothing | n/a | n/a | n/a | nothing until submit |
| 3 | Submit | none | server: email/password/tenant presence, ≥8 chars, role grant | `users` row, `is_active = false` | n/a | n/a | n/a | a transient toast, no field, no focus (F11) |
| 4 | Hand the credential over | — | — | — | — | — | — | **no layer; F5 — the flow ends in silence** |
| 5 | Activate the user | the account exists and is inactive | `rows_affected > 0` (`admin.rs:996-1004`) | `is_active = true` | n/a (a different control, in the detail panel) | none | n/a | toast |
| 6 | Approve a registration request (the other create path) | `status == pending` (`admin.rs:1136-1138`) | presence + ≥8 chars + role grant | `users` row, **`is_active = true`**, inline SQL (`admin.rs:1152-1155`) | precondition enforced server-side | n/a | n/a | HTTP error, not a toast path |
| 7 | Create/activate a user by SCIM push (the third create path) | a valid enterprise id + `claims` (route P1) | delegated-manager rule (`admin.rs:5659-5664`); the existing row's active state decides insert vs update | `users` row, **`is_active = true`**, role `'viewer'` (`admin.rs:5689-5691`) | n/a (machine-driven) | n/a | n/a | an HTTP error to the IdP; the human never sees it |

Finding classes in the order the skill ranks them: **no persistence** is not applicable
(no multi-page flow); **back-navigation keeps what it should discard** — step 1, F14;
**an error lands at the wrong place** — step 3, F11; and the flow that simply **has no
last step** — step 4, F5. Step 5's "activate" is a separate control with no queue: a
pending account is not distinguishable from an inactive one in the list, so the operator
who creates a user must remember to find it again — a walkthrough gap recorded here and
scored inside F5.

### Matrix 4 — interaction dependency

| # | Trigger | Dependents | Required action | Who owns the state | What is announced |
|---|---|---|---|---|---|
| 1 | Search text (debounced 250 ms) | result rows, `StatCard` values | recompute | `Users.tsx:43-47` | **nothing** — no live region, no count (F12) |
| 2 | Search text | the four `StatCard`s labelled Total/Active/Inactive/Admins | recompute — but they recompute over the *filtered page* while labelled as if global | `Users.tsx:101-104` | nothing (F3) |
| 3 | Role button click | panel badge, table row role | recompute | server + `invalidateQueries` (`Users.tsx:76`) | success toast only |
| 4 | `useMe()` resolution | `availableRoles` (5 vs 3 options) | recompute | `Users.tsx:29-30, 85` | **nothing** — the option set swaps in after the response (F14-adjacent, low severity) |
| 5 | Tenant picker change (create form) | role options, tenant label | keep (server accepts role independently) — a pass row | `Users.tsx:255-256` | n/a |
| 6 | Tenant picker free text | `tenant_id` sent as `$5::uuid` | revalidate | client does not | nothing: a malformed value returns 500 (F15) |
| 7 | Deactivate | the target's sessions | recompute outside the page | server (`auth.rs:688`) | nothing in the panel; the badge updates after refetch |

Row 2 is the finding the matrix earns: a *dependent* value that is recomputed on a
narrower set while its label keeps claiming the wider one — the "control still showing a
state the view no longer has" class, one level up. Row 7 is a pass with a stated window
(≤900 s of access-token validity, `auth.rs:463`).

### Coverage

| Matrix | Rows | Checked from source | Could not be checked | What would change the conclusion |
|---|---|---|---|---|
| Capability | 17 | 17 | 0 cells; but rows 3, 4, 11, 13 are *absences*, each with the search that proves it (`grep -rn "fetchUserPermissions\|/permissions" admin/frontend/src`; `grep -rn "smtp\|mailer\|send_email\|send_mail\|Mail::" admin/backend/src --include=*.rs`; `grep -rn "reset\|forgot" admin/backend/src/main.rs`) | a client caller for rows 4/11, a pager for row 3, a delivery layer for row 13 |
| Field contract | 15 | 15 | 0 | a wire capture showing `permissions` or `total` reaching the client |
| Flow / step | 7 | 7 | 0 | a running app showing a resume or a queued approval |
| Interaction dependency | 7 | 7 | row 6's premise (does the picker permit free text?) | the running app |
| State matrix | 12 components | 12 read from source | every measured property (contrast, target size, reflow, focus ring), all image tests, the axe sweep | one `analyze-app` session |

## 7. The competitive axis — not performed

No competitor product was selected as a comparison basis in this brief, so no
comparison basis was pre-stated, no representative version was chosen and no competitor
artifact was read with a date. **No `external` competitor fact is in this artifact.**
One external artifact *was* read in this session and is cited where it is used: the W3C
APG Combobox pattern, `https://www.w3.org/WAI/ARIA/apg/patterns/combobox/`, read
2026-09-21 (F9). What would change this: a stated basis (e.g. *task time to deactivate an
account*), two named admin consoles at named versions, and their documentation read with
dates. Review mining was not performed (no review corpus in scope) — again stated, not
omitted.

## 8. Triage

| Feature | Verdict | Deciding metric | Threshold | Timeframe | Action | Flag / owner |
|---|---|---|---|---|---|---|
| Permission editor (F6) | **fix** (first) | distinct permission sets that shrank without the operator ticking a removal | any single occurrence | 30 days | read-before-write; carry `permissions.modules` on the tenant-users payload | `admin.users.permissions.readback` / **owner unassigned — required before work starts** |
| Created account usability (F5) | **bet** | share of users created here that ever log in | < 0.5 | 30 days | §6 proposal below | `admin.user.invite_delivery` / owner required |
| List integrity (F2, F3) | **fix** | rows rendered ÷ `total` from the same response | ≠ 1 | 14 days | render `total`, add `Pager`, add `QueryErrorState` | `admin.users.list.fidelity` / owner required |
| Role editor (F4, F13) | **fix** | 4xx on `PUT …/role` | > 0 | 14 days | derive the option list from the server constant; text state for the current role | `admin.users.role.options` / owner required |
| Deactivate (F7) | **fix** | self-deactivations by an active super_admin | > 0 | 30 days | confirmation naming the effect + last-admin/self guard | `admin.users.deactivate.guard` / owner required |
| Profile update (F8) | **fix** | 5xx on `PUT …/users/{id}` | > 0 | 30 days | typed body + 409 mapping | `admin.users.update.contract` / owner required |
| Delete a user | **cut** | `audit_log` rows requesting deletion | 0 | 90 days | do nothing; deactivate is the intended verb | not required |
| Bulk role/status change | **cut** (for now) | operator requests for it | 0 | 90 days | do nothing | not required |
| Table sorting | **keep** (absent) | search-miss rate | no data | 90 days | re-decide with M1 data | not required |

"Everything is important" is not a verdict, so a cut is listed twice with the metric that
would revive it. No owner is named in the repository for any of these; the skill requires
an owner for a cut and a flag for a bet, so the rows name the flag and mark the owner as
**unassigned**, which is itself an unowned-decision finding rather than a hidden one.

## 9. Reference for each recommendation

The convention each recommendation adopts is the repository's own, which the
feature-audit skill names as the strongest available standard:

| Recommendation | Who already does it, cited | What we adopt |
|---|---|---|
| Page the user list with the server's total | `ThreatIntel.tsx:247, 324, 407` using `Pager.tsx:10` | the same `Pager` + `data.total` pattern |
| Show a load failure | `QueryErrorState.tsx:1-15`, used at `ThreatIntel.tsx:13` | render it on a query error |
| Confirm a destructive admin action | `Requests.tsx:513`, `ThreatIntel.tsx:267, 342, 425` | confirm naming the effect |
| Type the request body and validate it | `admin_dto.rs:134-140` (`deny_unknown_fields` + `validate`) | the same request type for profile update |
| Accessible combobox | the W3C APG combobox pattern (read 2026-09-21) | `role=combobox`, `aria-expanded`, `aria-controls`, a `listbox` popup |

## 10. Capability-change proposal (required by F5)

A finding whose fix names a layer that does not exist may not be reported as a screen
recommendation, so it is emitted here, with every heading's falsifier.

| Heading | Content | Falsified by |
|---|---|---|
| **Capability** | An account created by an admin receives its access credential without the admin transmitting it by hand, and can recover it if it is lost. | a cited code path that already delivers it |
| **Absence proof** | `admin.rs:1004-1019` creates `is_active = false` and answers "Activate after approval"; `db.rs:521-524` is the only write; `grep -rn "smtp\|mailer\|send_email\|send_mail\|Mail::" admin/backend/src --include=*.rs` → 0; `grep -rn "reset\|forgot" admin/backend/src/main.rs` → 0 routes; the failing input is any create: the API returns 201 and no delivery artifact exists. | a cited path that handles that input |
| **Contract delta** | A route `POST /api/v1/admin/users/{id}/credential-invite` (added to the `admin_routes` table, `main.rs:251-341`), and a migration adding `users.invite_token_hash text null, users.invite_expires_at timestamptz null`. Checkable: the route-table test and a migration-sequence check (`db/migrations` is numbered; the next free number is the artifact). | the compatibility checker going green with no diff |
| **Migration** | expand (add the nullable columns, backfill none) → migrate (write a token inside `CREATE_INACTIVE` and on the approve path `admin.rs:1147`) → contract (drop nothing; the columns stay, dated step **2026-10-20**). | a contract phase with no date |
| **Rollout** | flag `admin.user.invite_delivery`, boolean, expected lifetime 90 days, initial exposure 0 tenants, kill-switch owner: platform on-call, abort threshold: invite send failures > 2 % over 24 h. | an unmeasurable threshold or a flag with no lifetime |
| **Verification** | fails before / passes after: a test in `admin/backend/tests/` asserting that a 201 create is accompanied by exactly one invite artifact row; on this commit no such artifact type exists, so the test cannot pass. | the check also passing on the pre-change commit |
| **Reversibility** | writes one `invite_tokens` row; restore = delete by `token_hash`; the `users` row's existing columns are untouched. | data written with no restore step and no label |
| **Decision** | ADR `0007-user-invite-delivery` — context: the only credential path is out of band; decision: token + delivery layer; status: **proposed**; consequences: a new external dependency and a new failure mode. Supersedes nothing. | an ADR without a status |
| **Appetite** | 2 weeks; out of bounds: the provider choice, the password-reset UI, and anything touching the app backend. | no box, or an implicit extension |

Reviewer's five absences, checked: capability with a `code` finding behind it (yes, F5);
proposal with a rejectable artifact (yes — a route/migration diff and a flag with a type);
schema-touching step with migration phases (yes); flag with a lifetime and owner (yes);
contract change with an ADR and a pre/post check pair (yes).

## 11. What this analysis did **not** look at, and what would change it

- **No running app** → the entire `ui-observed` class, every measurement (contrast,
  target size, focus ring, reflow at 320 px), all image evidence (blur, grayscale,
  breakpoints, dark mode, 200 % text), the axe sweep, and any loading/INP/LCP/CLS
  reading. One `analyze-app` session would move the scorecard's *Image evidence* and
  *Depth* dimensions up; it would not change §4's `code` findings.
- **No database** → every `behaviour` metric in §2 is defined and unobserved; the audit
  table was read as code (its INSERT at `admin.rs:251`), never queried.
- **No users** → no `user-verbatim`, no SUS/UMUX-Lite (an instrument for real users; for
  an agent it is recorded as **to be run**, never as a number).
- **No competitor** → §7.
- **Not read:** `app/backend` and `app/frontend` (other than confirming no mailer exists
  where this feature's create path would need one), the native-enforcement and SDK trees,
  the `.agent/`, `.claude/`, `.codex/` harness directories. The registration-request
  *review* surface was read only where it creates a user.
- **What would flip the recommendations:** a client caller for `GET …/users/{id}` or
  `GET …/users/{id}/permissions` found outside `admin/frontend/src` (the searches above
  covered only that tree); a tenant base under 200 for every tenant (F3 becomes
  theoretical); a delivery layer outside `admin/backend` (F5's proposal collapses —
  `grep` covered only `admin/backend/src`).

## 12. Scorecard (anchors: the `research` skill's 1-5)

| Dimension | Score | Why |
|---|---|---|
| Evidence relevance | 4 | every citation re-read before writing; one finding (F15) carries a premise I could not check and says so |
| Class discipline | 4 | every finding has exactly one class; `ui-observed` is unavailable and declared rather than faked; no `behaviour` number is asserted |
| Depth | 3 | component and state level from source; no property measured — the ladder stops where the running app began |
| Image evidence | 2 | no rendered screen was read, for a stated constraint; the visual axis is uncovered, which is a real gap in a *usability* claim, not a silent one |
| Axis coverage | 4 | all five axes addressed; competition declared not performed with its reason |
| Metric integrity | 3 | metrics are ratios with definitions and windows; none observed, and no denominator exists for three of them |
| Solution plurality | 4 | three candidates compared against a criterion stated before the comparison |
| Feasibility grounding | 5 | every implementation claim is a `path:line`; absences carry the search that proves them |
| Decision quality | 4 | every feature ends keep/fix/cut/bet with a metric, threshold, timeframe and flag; owners are unassigned in the repository, which is stated |
| Scope calibration | 5 | §11 names what was not looked at and what would flip each conclusion |

Mean **3.8** (10 dimensions, arithmetic above) → **weak accept**, with the two lowest
dimensions (Image evidence 2, Depth 3) both moving up on a single `analyze-app` session
and neither affecting the `code` findings. No dimension is at 1, so the artifact is not
rejected on the scorecard; the honest reading is that this is a **layer-coherence audit
with the running-app half missing**, not a complete usability evaluation.
