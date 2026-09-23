# Product analysis - admin Users area (aibim-app)

Rubric applied: `.tezgah/research/feature-coherence/experiments/E6-pre-wiring-control/product-analysis-pre-wiring.md`
(rubric file identity, plus `skills/research/SKILL.md` for the claim/evidence rules).
Subject: `/Users/rizax/Projects/aibim-app` at `a6e47df` ("fix: bind AIBIM nginx behind shared proxy").
Feature in scope: the admin Users area - backend routes, handlers, the authorization they consult,
the queries they run, and the React page + API client that call them.

**Conditions of this run.** Read-only on `aibim-app`; no Docker, no build, no dev server, no database.
Everything below is either source read in this session or an external artifact read in this session.
No screen was rendered and no request was issued, so the `ui-observed` and `behaviour` classes are
empty by construction, not by omission. Write scope for this arm was the single artifact path, so the
research workspace (`tezgah-research init`, `claims.jsonl`, `protocol.md`, `review.json`) was **not**
scaffolded; the reason is the batch contract, and the drift is named here rather than hidden.

**Feature unit and its layers.** Backend routes `admin/backend/src/main.rs:236-341`, gated by
`admin/backend/src/main.rs:440-443` -> `middleware::require_admin_access`
(`admin/backend/src/middleware.rs:66-84`). SQL constants `admin/backend/src/db.rs:467-523`.
UI page `admin/frontend/src/pages/Users.tsx`, client `admin/frontend/src/api/admin.ts:364-405`, `:922-925`.

---

## 1. Measurement readiness (the gate)

| Question | Answer | Evidence |
|---|---|---|
| Is the feature's behaviour observable today? | Partly: server-side audit rows exist for all six of the feature's write paths, and an HTTP counter exists. No product analytics anywhere in the admin SPA. | `admin/backend/src/handlers/admin.rs:45-51` (declared purpose), `:54-80` (`audit_admin_action`), `:240-268` (`INSERT INTO audit_log` with `previous_hash`/`entry_hash` hash chain); `admin/backend/src/main.rs:579-583` (request counter); no analytics dependency or call site in `admin/frontend` (search of `admin/frontend/src` and `admin/frontend/package.json` for posthog / gtag / analytics / segment / mixpanel / matomo / plausible returned nothing) |
| Can the *product* question ("is this area working for its users") be answered from what exists? | No. `audit_log` can be turned into ratios, but nothing in the repo computes them, and this arm had no database to run them against. | class `behaviour` is therefore empty - see the empty-class statement below |
| Is there user feedback to read? | None in scope. | no interview, ticket, review or message corpus for this area was available to this arm |

**Findings, readiness:**

- **R1 - the Users feature has no product telemetry; the only feature-level record is a compliance
  audit trail.** class `code`. `admin/backend/src/handlers/admin.rs:54-80` writes `audit_log` rows (hash chain at `:240-268`) for
  `user_create`, `user_activate`, `user_deactivate`, `user_role_change`, `user_update`,
  `user_permissions_update`; `admin/backend/src/main.rs:579-583` counts HTTP requests only. Nothing
  records whether an admin succeeded in the task they came to do.
- **R3 - an audit-insert failure does not fail the operation, by explicit design.** The write path
  `warn!`s and returns `Ok(())` so the admin action still reports success; the intended observable is
  the missing row. That is documented intent, not a gap - but it means the signal R1 leans on can be
  absent at exactly the moment it matters most, and nothing alerts on it. class `code`.
  `admin/backend/src/handlers/admin.rs:45-49`.
- **R2 - "we cannot see this yet" is not a footnote here: the load-bearing behaviours (a demotion, a
  deactivation, a lockout) are only visible in a DB this arm could not open.** class `code` (the
  absence of any consumer), citation as R1. The class `behaviour`, `user-verbatim` and `ui-observed`
  rows therefore do not exist in this artifact, and every axis below says so in its own terms.

**Classes present:** `code` (all findings), `external` (2 competitor facts). **Classes absent:**
`user-verbatim`, `behaviour`, `ui-observed` - each with the reason above, not silently.

## 2. Objective - Goal -> Signal -> Metric

| Layer | Statement | Evidence |
|---|---|---|
| Goal | Privileged change control on the platform admin surface is correct and provable: the area's own code names it. | class `code`: `admin/backend/src/handlers/admin.rs:4433` ("the total count is SOC-visible; a silent 0 hides real DB outages"), `:50-51` (audit is hash-chained), `:240-268`, `.engineering/roles/admin-backend.md:3-5` ("Verify RBAC/platform boundary ... negative access paths") |
| Signal | A privileged change (role assignment, activation state) is performed by an actor entitled to perform it, and is recorded in a form that lets a reviewer reconstruct it. | class `code`: `admin/backend/src/handlers/admin.rs:875-888` (entitlement check), `admin/backend/src/db.rs:512,515,518` (the change itself) |
| Metric (proposed, not computed) | (a) share of `audit_log` rows with `operation IN ('user_role_change','user_deactivate','user_activate')` whose `actor_role` is `super_admin`, over all such rows in a 30-day window, using `audit_log.actor_role`; (b) median minutes from `users.created_at` to the `user_activate` audit row for users created in the same window. | class `code` for the columns the metric would read: `admin/backend/src/handlers/admin.rs:245-252` (`actor_role` column), `admin/backend/src/db.rs:521-523` (`CREATE_INACTIVE`), `admin/backend/src/handlers/admin.rs:1000-1014` (`user_activate` row) |

Per the rubric's rule, a metric with no goal above it is dropped: both metrics sit under the goal
above and both are ratios with a stated numerator, denominator and window. **Neither was computed -
this arm had no database. They are proposals, and they are labelled as such.**

## 3. Opportunities and candidate solutions

- **Opportunity - the one this feature is built around is an actor need, not a feature:** a platform
  admin must be able to change who can do what without the possibility of stranding the platform.
  Evidence class: **none available**. It is not `user-verbatim` (no user was read) and not `behaviour`
  (no ratios). Per the rubric, a finding without a class is a question: **this is a question, recorded
  in section 12, not a finding.**

**Three solutions compared against a pre-stated criterion.** Criterion stated first: *which mechanism
prevents the loss of the last privileged account while adding the least friction to the 99% of
operations that are not that case?* (cheapest falsifying test per option in section 4).

| Option | Mechanism | Cost | Failure mode |
|---|---|---|---|
| A. Query-level invariant | `DEACTIVATE` / `UPDATE_ROLE` carry a `WHERE` that refuses the change when the target is the last active `super_admin` | one SQL edit + one error branch per handler | the same guard must be repeated in every future write path |
| B. Handler-level guard | a shared `ensure_not_last_privileged_target(pool, actor, target)` called before the mutation | one new function, 4 call sites | a new handler that forgets the call is unguarded |
| C. Step-up authentication | re-authentication for the class "change a privileged role or activation state" | a token-freshness claim check in middleware plus a client prompt | largest change; irrelevant to the self-lockout case |

Recommendation: **A + B together** (A is the invariant, B is the caller-visible error) - see section 8,
reference Okta's protected-actions model for C as a later bet.

## 4. Risks by class, each with its cheapest falsifying test

| Class | Risk | Cheapest falsifying test |
|---|---|---|
| Value | the audit trail cannot answer the review question it exists for (no previous role) | read one `audit_log` row produced by `user_role_change` and try to state the prior role |
| Usability | a 403/500 on this page is rendered as "No users found" | load `/users` with the backend returning 500 |
| Viability | last-privileged-account loss without a recovery path | attempt to deactivate the only `super_admin` as an `admin` |
| Feasibility | page count vs. real count diverge above 200 users | create a 201st user and read the header subtitle |

## 5. Usability axis

**Scope statement (required by the method).** One section (admin Users), one user group (platform
`admin` / `super_admin`), one device class (desktop web), breakpoints **not exercised** (320 / 768 /
1280, dark mode, 200% text: none captured - no running app). Task in scope: *find a user, change their
role, deactivate them*; second task: *create a user and activate them after approval*.

**One rater, one pass.** The method wants three to five independent evaluations and says a single
rater is too unreliable to be trusted for severity. This arm is one rater, and its pass was made from
source, not from the running app. **Rater count: 1.** Every severity below is therefore provisional,
and the second pass (a different entry point, or the running app) is what would move it.

**Heuristics checked** (source-level reading; no heuristic can be *observed* without the app):

| Heuristic | Where it stands | Citation |
|---|---|---|
| H1 visibility of system status | partial: mutation buttons show pending text; the list has no error surface | `Users.tsx:207-215` (`Updating…`), `:42-47` (no `isError`) |
| H2 match with the real world | ok: role words, tenant names | `Users.tsx:13-15`, `:123-127` |
| H3 user control and freedom | partial: `Cancel` exists in edit mode; the detail panel closes by click-outside and by X, no Escape | `Users.tsx:236-241`, `DetailPanel.tsx:14-20` |
| H4 consistency and standards | **fails** against the sibling pages: 14 other admin pages render `QueryErrorState` on `isError`, this one does not | `Tenants.tsx:40`, `ApiKeys.tsx:39`, `Billing.tsx:29`, `Requests.tsx:431`, `AuditLogs.tsx:191`, `DetectionRules.tsx:453`, `Licenses.tsx:27`, `Enterprise.tsx:319`, `Dashboard.tsx:48`, `System.tsx:45`, `ThreatIntel.tsx:444`, `Agents.tsx:115`, `Benchmarks.tsx:187`, `TenantDetail.tsx:689` vs `Users.tsx:42-47` |
| H5 error prevention | **fails**: destructive/irreversible actions with no confirmation and no guard (see F13c, F2) | `Users.tsx:207-215`, `admin.rs:835-848` |
| H6 recognition rather than recall | ok for the list; the detail panel repeats the role as a badge | `Users.tsx:145-172` |
| H7 flexibility and efficiency | **fails**: no pagination, no sort, no filter beyond one text box; a user past the first 200 rows is reachable only by search | `Users.tsx:46`, `:107` |
| H8 aesthetic and minimalist design | out of scope for a source read (hierarchy is an image claim - section 5.4) | - |
| H9 help users recognise and recover from errors | **fails**: errors are toasts that vanish; no field-level error, no retry | `Users.tsx:49-79`, `:250-260` |
| H10 help and documentation | absent; no inline explanation of the role model (`super_admin` can be clicked and always fails - F9) | `Users.tsx:85`, `:179-196` |

### 5.1 State matrix (mandatory: component x state)

Every row is readable from source, so its class is `code`; a state listed as missing is a claim about
the source at the cited line, **not** a `ui-observed` reading, and it needs the running app to be
confirmed as a user-visible defect.

| Component / data view | States present | States that do not exist | Citation |
|---|---|---|---|
| Users list (data view) | loading (spinner + text), empty ("No users found") | **error**, permission-denied, offline, skeleton, partial, oversized-result | `Users.tsx:109-128`; `DataTable.tsx:17-66` (only `isLoading` / `isEmpty` branches) |
| Search input | default | loading indicator while the query is in flight, no-results-for-term message distinct from "no users" | `Users.tsx:107`, `:42-47` |
| "Create User" toolbar button | default, hover (CSS) | disabled when the actor is not entitled (the backend is the only gate) | `Users.tsx:97-99`; `admin.rs:875-888` |
| Create-user form fields | default, type=password on the password field | **required marking**, field-level error, inline hint (8-character minimum), validation state | `Users.tsx:250-254` vs `FormElements.tsx:5-28` (the component supports `required` and `error`; the page passes neither) |
| Create-submit button | default, pending ("Creating…") | **disabled on incomplete input** - empty email/password/tenant still submits and the 400 arrives as a toast | `Users.tsx:263-267`; `admin.rs:908-911` |
| Role buttons (detail panel) | default, active (current role), disabled (current role, or while pending) | error state after a rejected change (a refused promotion leaves the panel unchanged with a toast only) | `Users.tsx:179-196`; `admin.rs:882-887` |
| Activate / Deactivate button | default, pending ("Updating…") | **confirmation step**, disabled-while-pending is present, no error-in-place | `Users.tsx:207-221` |
| Detail panel (data view) | populated from the list row | loading (nothing is fetched), error, partial (a user deleted by another admin keeps rendering a stale row) | `Users.tsx:130-243`; `fetchUser` is never called - `api/admin.ts:379-382` |
| Rows as the detail entry point | hover, selected (row tint) | keyboard state: a `<tr onClick>` is not focusable and has no key handler | `Users.tsx:114-126` |
| Modal (create) | open/closed, pending submit | Escape-to-close, focus trap, focus restore, dialog semantics | `Modal.tsx:14-26` |

### 5.2 Findings at their level, with severity

Severity = frequency x impact x persistence, 0-4. `failure` = reproducible break or a WCAG criterion;
`judgement` = a heuristic read in context (the source of that heuristic says a violation is not
automatically a problem). Single rater throughout.

| # | Level | Finding | Severity | Kind | Citation |
|---|---|---|---|---|---|
| U1 | component (data view) | no error state on the list: a 500 or a 403 renders as the empty state "No users found", so a backend outage and an empty platform are indistinguishable | 3 | `failure` in the shape of H4/H9; needs the app to confirm the rendered result | `Users.tsx:42-47`, `:109-128`; `DataTable.tsx:53-62`; contrast `QueryErrorState.tsx:6-16` and its 14 sibling call sites above |
| U2 | component | the modal has no dialog semantics: no `role="dialog"`, no `aria-modal`, no label wiring, no focus trap, no Escape, and focus is not moved on open or restored on close; the detail panel is the same shell | 3 | `failure` candidate (WCAG 2.1.1, 2.4.3, 4.1.2); a source read, not a page measurement | `Modal.tsx:14-26`; `DetailPanel.tsx:14-20`; no `role="dialog"`, `aria-modal`, `aria-label`, `htmlFor`, `onKeyDown` or Escape handler anywhere in `admin/frontend/src/components/ui` |
| U3 | component | the primary way into a user's detail is a mouse-only table row: no `tabIndex`, no keyboard handler, no link or button inside it | 3 | `failure` candidate (WCAG 2.1.1) | `Users.tsx:114-126` |
| U4 | property (measured arithmetically from source) | 4 of the 5 role badge colours fall below the 4.5:1 floor for text under 18.66px bold: `#4d84b8` 3.96:1, `#10B981` 2.54:1, `#F59E0B` 2.15:1, `#F43F5E` 3.67:1 on a white surface, at `text-[10px]`; only `#326da8` passes (5.40:1) and the fallback `#65748a` passes (4.75:1). Secondary text tokens are worse: `rgba(23,30,41,0.55)` computes to 3.81:1 and `rgba(23,30,41,0.40)` to 2.47:1 over white. | 3 | `failure` candidate (WCAG 1.4.3) - **computed, not measured in the page**; the surface assumption is stated | values `Users.tsx:13-15`, rendered at `text-[10px]` `Users.tsx:19-22`; token values `Users.tsx:122-126`, `:155-172` |
| U5 | state | no field-level error and no required marking, although the shared component supports both | 2 | `failure` in shape | `Users.tsx:250-254` vs `FormElements.tsx:5-28` |
| U6 | state | a destructive action has no confirmation and no guard: one click deactivates, including oneself | 4 | `failure` (security, see F2) | `Users.tsx:207-215`; `admin.rs:835-848` |
| U7 | component | the page offers a role the backend always rejects (`super_admin` in the role picker) so a legitimate-looking choice produces "Invalid platform role" | 2 | `failure` | `Users.tsx:11`, `:85`, `:179-196`, `:253`; `admin.rs:873-880` |
| U8 | screen | no pagination or sort control; the list is one 200-row page and the search box is the only way past it | 2 | `judgement` (H7) with the capacity claim in F5 | `Users.tsx:46`, `:107` |

### 5.3 What the method demands and this arm could not produce

| Required | Status | Reason |
|---|---|---|
| `analyze-app` view-tree reads (`browser_snapshot`, `mobile_list_elements_on_screen`) | **not produced** | no running instance; the arm is read-only with no Docker, so no app could be launched |
| Rendered-screen reading, blur test, grayscale test | **not produced** | no screenshot exists; a test that needs pixels cannot be run from source. This is exactly the rubric's line "a UI claim is inferred from source is not evidence", so U1-U3, U5, U7 are named as source-shape findings, not observations |
| Breakpoint / dark-mode / 200%-text captures | **not produced** | same reason; the viewport of every layout claim is therefore unstated, and no layout claim is made |
| axe-core sweep (pinned version) | **not produced** | needs a page. The unpublished covered-check list is also unswept; the rubric's own figure (~57% of WCAG issues found automatically) means the hand-checked residue (focus appearance, target size, dragging, accessible authentication) is hand-checked here **only** to the extent source can show it, which is nowhere near the standard |
| `browser_evaluate` computed-style measurements (contrast, type scale, spacing, target size, focus order) | **not produced**; U4 is arithmetic on source constants with the surface assumed | no page |
| Core Web Vitals (LCP / INP / CLS) | **not produced** | needs a page |
| WCAG 2.2 level claimed | **not claimed**: no conformance level is asserted for this area, in the repo or here. The two criteria raised above (1.4.3, 2.1.1, 2.4.3, 4.1.2) are AA-level candidates at the *candidate* stage |  |
| SUS / UMUX-Lite | **to be run**, not run: an instrument for real users | the rubric forbids recording it as a number produced here |

### 5.4 Cognitive walkthrough (task: change a user's role)

Four questions per step, from a new user's position. Performed from source, so each answer is a
`judgement` with rater count 1 **and** the caveat that a walkthrough is meant to be walked.

| Step | Q1 right effect? | Q2 notice the action? | Q3 associate it with the effect? | Q4 see progress? |
|---|---|---|---|---|
| 1. Find the user | yes | yes (nav item `Users`) | yes | yes (list renders) |
| 2. Open the user | yes | **partly**: the row is clickable but carries no affordance (no chevron, no button) | **weak**: nothing says the row opens a panel | yes (panel slides in) |
| 3. Pick the new role | yes | yes | **weak**: the current role is shown as an active button and is disabled, so the control reads as a set of filter chips, and `super_admin` is offered although it always fails (U7) | yes (toast), but the panel's own row updates only on success |
| 4. Confirm the change happened | yes | n/a | n/a | **weak**: no confirmation, no before/after; the audit row (which does exist, F3) is not shown |

A "no" or a "weak" is a finding with the step it belongs to; steps 2 and 4 are the cheapest defects
this method catches that heuristics miss, and step 2 is consistent with U3.

## 6. Feasibility axis (intended vs implemented)

Format of the layer-coherence matrices the feature audit demands. **A disagreement between layers is a
finding; an agreement is a row too.** All rows `code` class.

### 6.1 Capability matrix (action x layer)

| Action | Backend route + handler | Query | Client fn | UI surface | Verdict |
|---|---|---|---|---|---|
| List users | `main.rs:263-266` -> `admin.rs:4394-4465` | `db.rs:482-500` | `api/admin.ts:374-377` | `Users.tsx:109-128` | **agree** |
| Get one user | `main.rs:283-286` -> `admin.rs:4469-4496` | `db.rs:503-506` | `api/admin.ts:379-382` | **none** | **disagree**: route + client exist, no UI calls it, and the client fn has no call site at all |
| Create user | `main.rs:263-266` -> `admin.rs:892-986` | `db.rs:521-523` | `api/admin.ts:384-387` | `Users.tsx:244-271` | **agree** |
| Update profile | `main.rs:283-286` -> `admin.rs:4505-4541` | `db.rs:508-510` | `api/admin.ts:389-392` | `Users.tsx:228-236` | **agree** |
| Change role | `main.rs:255-258` -> `admin.rs:789-833` | `db.rs:512-513` | `api/admin.ts:394-396` | `Users.tsx:179-196` | **disagree on the role set** (U7) and **disagree on the guard** (F1) |
| Deactivate / activate | `main.rs:259-262`, `:267-270` -> `admin.rs:835-862`, `:989-1022` | `db.rs:515-520` | `api/admin.ts:398-404` | `Users.tsx:207-223` | **agree on wiring, disagree on protection** (F2) |
| Read module permissions | `main.rs:337-341` -> `admin.rs:8477-8505` | `db.rs` `user_permissions::GET` | **none** | **none** | **disagree**: backend capability with no client fn and no surface |
| Write module permissions | `main.rs:337-341` -> `admin.rs:8424-8475` | `db.rs` `user_permissions::UPDATE` | `api/admin.ts:922-925` | only `TenantDetail.tsx:346-350` (tenant-scoped tab) | **disagree**: the platform Users page never surfaces it (F10) |
| Tenant-filtered user list | `main.rs:251-254` -> `admin.rs:757-785` | `db.rs:469-471` | `api/admin.ts:364-372` | `TenantDetail.tsx` UsersTab | **agree** (different surface) |

### 6.2 Field-contract matrix

| Field | `GET /users` | `GET /users/:id` | `PUT /users/:id` body | `POST /users` body | Client type | Verdict |
|---|---|---|---|---|---|---|
| `user_id` | yes (`admin.rs:4452`) | yes | - | returned only | `AdminUser.user_id` | agree |
| `email` | yes | yes | optional | required, validated non-empty only | `string` | **weak**: format never validated at either layer |
| `full_name` | yes (COALESCE) | yes | optional | optional, defaults "" | `string` | agree |
| `role` | yes | yes | **not accepted here** | optional, **defaults to `"viewer"`** | `string` | **disagree**: `admin_dto.rs:129-132` records that the silent `"viewer"` default was a footgun and was fixed - on the role endpoint - while `admin.rs:900-903` still does `.unwrap_or("viewer")` for create. Doc and code both cited: a gap |
| `is_active` | yes | yes | - | always false | `boolean` | agree |
| `tenant_id` | yes | yes | - | required | `string` | agree |
| `tenant_name` | yes (LEFT JOIN) | **absent** | - | - | typed as present | **disagree**: the same entity has two shapes, and the client's `fetchUser` types the narrower one as if it had the wider field (`api/admin.ts:379-382` vs `admin.rs:4492-4493`) |
| `created_at` | yes (as text) | yes (as text) | - | - | `string?` | agree, with a note: `db.rs:482` and `:503` return `::text`, so the format is the DB's, and the panel parses it with `new Date(...)` (`Users.tsx:174-181`) |
| `last_login_at` | yes | yes | - | - | present | **disagree**: returned by both endpoints, never rendered anywhere in `Users.tsx` |
| `permissions.modules` | no | no | - | - | only in the tenant tab | **disagree**: the platform detail panel shows no permission state although the tenant tab does (`TenantDetail.tsx:346-421`) |
| `total` | yes (`admin.rs:4450`) | - | - | - | typed, ignored | **disagree**: see F5 |
| Body validation style | - | - | `serde_json::Value` (`admin.rs:4508-4510`) | `serde_json::Value` (`admin.rs:895`) | - | **disagree with the role endpoint**, which takes a typed DTO with deny-unknown-fields (`admin_dto.rs:129-140`, `admin.rs:793`) |

### 6.3 Flow / step matrix (provision a user)

`POST /users` -> inactive (`db.rs:521-523`) -> the row appears as "Inactive" (`Users.tsx:125`) -> an
`admin` opens the row -> "Activate" (`Users.tsx:207-215`) -> `POST /users/:id/activate`
(`admin.rs:989`). **All steps exist; no step is missing.** The friction inside the flow is U6 (no
confirmation) and U1 (an error at any step is a toast, not a state).

### 6.4 Interaction-dependency matrix

| Interaction | Depends on | Verdict |
|---|---|---|
| Create submit | the backend's required-field check; nothing client-side | **disagree** with the shared component's own capability (`FormElements.tsx:5-28`) |
| Role buttons | "the actor may assign this role" - the UI encodes it as `availableRoles` (`Users.tsx:85`), the backend as `ADMIN_ASSIGNABLE_ROLES` + a super_admin branch (`admin.rs:873-888`) | **disagree**: the UI is *stricter* than the backend for the admin tier, and *looser* for `super_admin` (offers a role the backend refuses) |
| Deactivate / activate | actor entitlement + target's entitlement | **disagree**: the second term does not exist anywhere (F1, F2) |
| Search | a 250 ms debounce then a server round trip (`Users.tsx:36-40`) | agree |

## 7. Competitive axis

**Comparison basis, stated before comparing:** *how a platform's admin surface protects the last
privileged account, and whether privileged changes require re-authentication.* Chosen because that is
the axis F1/F2 sit on and the axis the area's own goal (section 2) is about.

| Competitor fact | Artifact | Date read |
|---|---|---|
| Okta requires re-authentication for a configurable interval when an admin performs "protected actions", and the list includes *"Assign and revoke the super admin role"*, *"Assign and revoke a standard or custom admin role"*, *"Reset a super admin's MFA"*; it can also email an administrator whenever a protected action is taken. | `https://help.okta.com/en-us/content/topics/security/admin-console-protected-actions.htm` | 2026-09-21 |
| Grafana carries an explicit refusal to remove the last organisation admin - the error string "Cannot remove last organization admin" appears when the invariant would be broken. | `https://github.com/grafana/grafana/issues/2940` (opened 2015-10-13) | 2026-09-21 |

Read against us: aibim-app has **neither** the invariant (F1/F2 show the last active `super_admin` can
be demoted or deactivated, and an actor can deactivate themselves) **nor** step-up authentication for
privileged changes. What we would adopt: Grafana's invariant (option A of section 3) now; Okta's
protected-action model (option C) as the bet in section 9.

**Review mining: not performed.** Volume and sentiment per theme need competitor review corpora, which
this arm did not fetch. This section therefore contains two cited facts and no market-words layer -
stated so the gap does not read as coverage. Cost/effort numbers: none quoted, deliberately (the
method's first limitation is false precision, and this arm had no basis for a range).

## 8. Findings, most severe first (class + citation on every row)

| # | Severity | Finding | Class | Citation |
|---|---|---|---|---|
| F1 | 4 | **An `admin` can demote a `super_admin` to any assignable role.** `admin_user_role` validates only the *requested* role (must be in `["admin","operator","viewer","api_user"]`, and assigning `admin` needs `super_admin`); the *target's* current role is never read, and `UPDATE_ROLE` is an unconditional update by id. The documented intent in the same file says the opposite. | `code` (doc-vs-code gap, both sides cited) | intent `admin/backend/src/handlers/admin.rs:787-788`; enforcement `:875-888`; query `admin/backend/src/db.rs:512-513`; gate `admin/backend/src/middleware.rs:38-47` |
| F2 | 4 | **Deactivation has no entitlement check on the target and no self-guard.** `admin_user_deactivate` and `admin_activate_user` take no role argument beyond the middleware, `DEACTIVATE`/`ACTIVATE` are unconditional by id, and `login` requires `is_active = true` - so an `admin` can lock out a `super_admin`, or lock themselves out permanently, in one click from `Users.tsx:207-215`. | `code` | `admin/backend/src/handlers/admin.rs:835-862`, `:989-1022`; `admin/backend/src/db.rs:515-520`; login gate `admin/backend/src/db.rs:533-537`; UI path `admin/frontend/src/pages/Users.tsx:207-215` |
| F3 | 3 | **The role-change audit row cannot reconstruct the transition: it stores `new_role` only, never the previous role.** For an area whose own comment calls the trail SOC-visible, "who was demoted from what" is unanswerable. | `code` | `admin/backend/src/handlers/admin.rs:811-822` (details `{ "new_role": role }`), insert at `:240-268` |
| F4 | 3 | **The list page's numbers are page counts presented as platform totals.** The query is `limit: 200` with no offset and no pager; the header claims "N users across all tenants" and all four stat cards derive from the same 200-row page, while the backend does return the real `total`. Above 200 users the stats under-count silently and the remaining users are unreachable except by search. | `code` | `admin/frontend/src/pages/Users.tsx:46`, `:83`, `:95`, `:101-104`; server `total` `admin/backend/src/handlers/admin.rs:4433`, `:4434-4441`, `:4458`; `admin/backend/src/db.rs:482-500`; client type `admin/frontend/src/api/admin.ts:374-377` |
| F5 | 3 | **The page has no error state, so a backend failure is indistinguishable from an empty platform.** | `code` | `admin/frontend/src/pages/Users.tsx:42-47`, `:109-128`; `DataTable.tsx:17-66`; the 14 sibling pages that do render it (section 5, H4 row) |
| F6 | 3 | **A duplicate email on profile update returns 500 "Internal server error", not 409.** `UPDATE_PROFILE` hits the table's `UNIQUE` constraint; `admin_create_user` maps the same failure to 409 with a message, so one failure has two responses depending on the endpoint. | `code` | `admin/backend/src/db.rs:508-510`; `db/migrations/001_core_tenants.sql:72` (`email ... UNIQUE`); create-path mapping `admin/backend/src/handlers/admin.rs:974-984`; update path `:4527-4542` |
| F7 | 3 | **Four of the five role-badge colours fail the 4.5:1 text-contrast floor at their rendered 10px** (arithmetic in U4), and the secondary text tokens (0.40 / 0.50 / 0.55 alpha) land between 2.47:1 and 3.81:1 over white. Computed from source, needs one `browser_evaluate` to become a measurement. | `code` (property) | `admin/frontend/src/pages/Users.tsx:13-15`, :19-22`, `:122-126`, `:155-172` |
| F8 | 3 | **The admin Users page never surfaces module permissions**, although the write endpoint, the client function and a tenant-scoped UI for exactly that exist. | `code` | `admin/frontend/src/api/admin.ts:922-925`; `admin/backend/src/handlers/admin.rs:8424-8475`; only surface `admin/frontend/src/pages/TenantDetail.tsx:346-421`; absent from `Users.tsx:2` (the page's own import list) |
| F9 | 2 | **The role picker offers `super_admin`, which the backend always rejects** (`ADMIN_ASSIGNABLE_ROLES` excludes it), so a legitimate-looking choice yields "Invalid platform role"; in the other direction the UI is stricter than the backend for the admin tier, which is the guard the backend lacks (F1). | `code` | `admin/frontend/src/pages/Users.tsx:11`, `:85`, `:179-196`, `:253`; `admin/backend/src/handlers/admin.rs:873-880` |
| F10 | 2 | **No dialog semantics on the modal or the detail panel**, and the mouse-only table row (U2, U3) is the only entry point to a user. | `code` | `Modal.tsx:14-26`; `DetailPanel.tsx:14-20`; `Users.tsx:114-126` |
| F11 | 2 | **The feature's validation logic has no test on production code.** `mod tests` at `admin/backend/src/handlers/admin.rs:8765` defines test-local mirror helpers (`validate_password_length` `:8771`, `is_assignable_role` `:8781`, `requires_super_admin` `:8786`) and tests those (`:8818-8916`); the production `validate_platform_role_grant` (`:875`) has no test, and the mirror helpers have no production call site - so a change to the real guard cannot fail the suite. There is also no test for a target-role or self-target guard, because no such guard exists. | `code` | as cited; `admin/frontend` has no test directory and `admin/backend/tests` does not exist |
| F12 | 2 | **Unguarded destructive action in the UI** (U6) and **no confirmation**; combined with F2 this is the lockout path end to end. | `code` | `Users.tsx:207-215`; `admin.rs:835-848` |
| F13 | 1 | **Dead client code and unrendered fields:** `fetchUser` (`api/admin.ts:379-382`) has no call site; `last_login_at` is returned by both list and detail endpoints and rendered nowhere. | `code` | `api/admin.ts:379-382`; `Users.tsx:2` (imports), `:150-172` (panel fields) |
| F14 | 1 | **`RoleBadge` replaces only the first underscore** (`role.replace('_', ' ')`), which is correct for today's five roles and wrong for any future multi-underscore role. | `code` | `Users.tsx:22` |

## 9. Triage - every feature ends keep / fix / cut / bet

Owner column: the repo names owners by role in `.engineering/roles/`; `admin-backend.md:3-5` owns
`admin/backend` (RBAC/platform boundary, negative access paths), `frontend.md` owns the SPA. The
rubric wants a named owner: **role-level owners are as specific as this repository gets; no individual
is named anywhere**, and that is itself a gap in the criterion.

| Feature | Verdict | Deciding metric | Threshold | Timeframe | Action if it fails | Flag / owner |
|---|---|---|---|---|---|---|
| Role assignment | **fix** | share of `audit_log` `user_role_change` rows whose actor is `super_admin` | any row whose target was `super_admin` and whose actor was not -> immediate | 30 days of rows, or the first reproduction | add the target-entitlement guard (option A+B) and a last-super_admin invariant | F1 / admin-backend |
| Activate / deactivate | **fix** | count of `user_deactivate` rows where `resource_id` = `actor_id` | > 0 | 30 days | self-guard + last-privileged-account invariant + confirmation | F2 / admin-backend |
| Audit of role change | **fix** | share of `user_role_change` rows from which the prior role is recoverable | 0% today -> must be 100% | next release | record the prior role in `action_details` | F3 / admin-backend |
| Users list (paging + counts) | **fix** | ratio (rendered rows / `total` from the API) | < 1 at any tenant set above 200 users | next release | wire `total`, add offset paging, stop calling a page count a platform total | F4 / frontend |
| Users list (error state) | **fix** | n/a - convention, not a metric: does the page render `QueryErrorState` on `isError` like its 14 siblings | yes/no | next release | render it | F5 / frontend |
| Module permissions on the platform page | **keep / fix** (fix wiring, keep the capability): today it lives in the tenant tab only | share of tenants whose permission state is reviewed at all (needs the analytics of R1; unobservable now) | - | - | **this one is blocked on R1**: the decision cannot be made until the behaviour is observable, and that is the decision | F8 / frontend |
| `GET /users/:id` route + `fetchUser` client fn | **cut** (the client fn) - no call site; the route stays (no evidence about other consumers was gathered) | - | - | - | delete the dead fn | F13 / frontend |
| Step-up auth for privileged changes (option C) | **bet** | share of privileged changes preceded by a fresh authentication event | >= 90% within the step-up window | one quarter | if the share stays near 0 because the prompt is bypassed, drop the mechanism and keep the invariant | this bet is the one to kill first / admin-backend |

## 10. Recommendations, each with its reference

| Recommendation | Who does it best (cited) | What we adopt |
|---|---|---|
| Refuse to strip the last privileged account (options A+B, F1/F2) | Grafana: "Cannot remove last organization admin" (`https://github.com/grafana/grafana/issues/2940`, read 2026-09-21) | the invariant plus a caller-visible refusal, in the query and at the handler |
| Step-up authentication for privileged changes | Okta protected actions, which name "Assign and revoke the super admin role" (`https://help.okta.com/en-us/content/topics/security/admin-console-protected-actions.htm`, read 2026-09-21) | re-auth interval on the role/activation class, plus an email notification on a protected action |
| Render an error state, not an empty state | the repository's own convention: 14 sibling pages call `QueryErrorState` (citations in section 5, H4) | the same call, with a retry |
| Record prior state in the audit row (F3) | the trail is already hash-chained and SOC-visible by our own code (`admin.rs:50-51`, `:240-268`) | `action_details: { "from_role": ..., "new_role": ... }` |
| Confirm destructive actions in the UI (U6) | `TenantDetail.tsx:319` already gates revocation behind `confirm(...)` | the same pattern, and a self-target refusal that does not depend on the UI |
| Field-level validation and required marking (U5) | the shared component already implements it (`FormElements.tsx:5-28`) | pass `required` / `error` at the call site |

## 11. What this analysis did not look at, and what would change it

1. **The running app** - not launched. Every usability finding would move from "source shape" to
   `ui-observed` or be refuted by one run with the app up; U1, U2, U3, U5, U7 are the ones most likely
   to change, because they are claims about rendering.
2. **Any database** - not opened. F4's capacity claim, F6's 500-vs-409, F1/F2's guard absence and both
   metrics in section 2 are code-level claims; a row of data each would turn them into behaviour.
   F1 and F2 are *worst-case* claims derived from absent checks; a single attempt against a live
   instance would settle them.
3. **The app backend** (`app/backend`) - out of scope by the brief. It has its own `admin/users`
   surface (`app/backend/src/api_handlers/admin.rs:167-260`) reached through a different middleware
   gate; **if the platform admin surface shares its authorization model, findings F1/F2 may apply
   there too, and that is not established here.**
4. **Screenshots, breakpoints, dark mode, 200% text, image tests, axe-core, Core Web Vitals** - none
   produced (section 5.3). This is the artifact's largest gap.
5. **Competitor review corpora** - not fetched (section 7).
6. **Other consumers of these routes** - not searched outside `admin/frontend`, which is why F13 keeps
   the route and cuts only the client function.
7. **What would flip the triage:** if the row-level metrics in section 2 come back with zero
   non-super_admin actors touching `super_admin` targets and zero self-deactivations over 30 days of
   real traffic, F1/F2 drop from `fix` to `bet` - the guard is then a cheap invariant, not a fire.

## 12. Open questions (a finding's class would be `none`, so these are questions)

- Q1. Does any user review, ticket or message corpus exist for this area? Without `user-verbatim`, the
  opportunity in section 3 stays a question and the value axis stays a hypothesis.
- Q2. Has the app ever been run against a seeded tenant set above 200 users (F4)?
- Q3. Was the tenant-scoped permission editor (`TenantDetail.tsx:346-421`) intended to be the only one,
  or is the platform page's absence of it (F8) an omission? The repo states no intent either way.

## 13. Scorecard (anchors from the `research` skill: 5 nothing material missing, 4 one minor gap, 3 a gap a reviewer would raise, 2 a gap that undermines a claim, 1 not addressed)

| Dimension | Score | Why |
|---|---|---|
| Evidence relevance | 4 | every finding's citation is the source of the claim; U4/F7 are arithmetic on source constants rather than in-page measurements - one minor gap |
| Class discipline | 4 | one class per finding; the three unproducible classes are named with reasons rather than filled |
| Depth | 4 | component x state covered for every interactive component and data view; nothing measured in the page |
| Image evidence | **1** | no rendered screen was read; blur, grayscale, breakpoints, dark mode all absent. **Not addressed.** |
| Axis coverage | 4 | all five axes addressed; the competitive axis carries two facts and no review-mining layer |
| Metric integrity | 3 | the metric traces to a goal cited in code and is a ratio with a definition, window and denominator - but it was not computed |
| Solution plurality | 3 | three solutions compared for the one decision that needed them; most findings carry a single fix |
| Feasibility grounding | 5 | every implementation claim is a cited `path:line`; the two doc-vs-code gaps cite both sides |
| Decision quality | 4 | keep/fix/cut/bet for every feature with a metric, threshold, action and a role-level owner - no individual is named anywhere in the repo |
| Scope calibration | 5 | what was not looked at, and what would flip the verdict, are both stated |
| **Mean** | **3.7** | ARITHMETIC OF THE TEN SCORES ABOVE |

The rubric's bands put 3.7 in "revise" (>=3.0), but its rule "below that, **or any dimension at 1**,
reject" applies: Image evidence is 1, so this artifact is a **reject as written** - which is the
honest reading of a control run that was forbidden the running app. The ceiling it measures is
structural, not stylistic: a source-only arm cannot reach the Image evidence dimension at all, so no
amount of extra source reading moves the mean past ~4.5.

## 14. Provenance and limits of this artifact

- Identity of the rubric applied: `product-analysis-pre-wiring-control` (file read in full, including
  its tail from line 301), plus `skills/research/SKILL.md` for the claim/evidence rules.
- Every citation above was read in this session at commit `a6e47df`; no citation is from memory and no
  symbol was quoted from the code graph (the graph index was behind HEAD, so no graph answer is used).
- The research workspace was not scaffolded and no `claims.jsonl` was written: write scope was the
  single artifact path named by the batch contract.
- The arm's own claim, in the rubric's terms: **this is a feasibility-and-coherence audit with a
  source-shaped usability hypothesis layer, not a product analysis of the running product.**
