# E6-tre1 — product-analysis x feature-audit on the admin Users area of aibim-app

Repo: `/Users/rizax/Projects/aibim-app` @ `a6e47df`, read-only.
Methods applied: `skills/product-analysis/SKILL.md` + `skills/feature-audit/SKILL.md`,
read in full this session. Depth sections read too (`:300-345`, `:300-324`).
Artifact path fixed by the batch contract; the `tezgah-research init` ceremony is
out of bounds for this arm (the contract allows a write to this one file and no
other), so the research-line sidecar was not created. Rater count: **1 pass** —
the skill's three-independent-evaluator floor was not met, because the app cannot
be run (read-only, no Docker, no builds), so every judgement below carries
`confidence: single pass` and no severity is a panel mean.

## 0. Boundary — the unit is the feature, not the screen

One entity (`user`), the actions an operator takes on it, and the layers that carry
them.

| Part | Files |
|---|---|
| Surface | `admin/frontend/src/pages/Users.tsx` (273 lines) |
| Surface primitives it composes | `admin/frontend/src/components/ui/{DataTable,DetailPanel,Modal,AdminPrimitives,FormElements,TenantSearchSelect,StatusBadge,Pager}.tsx` |
| API client | `admin/frontend/src/api/admin.ts:374-404` (users block), `types/admin.ts:85-97` |
| Route table | `admin/backend/src/main.rs:230-443` (`admin_routes`, layer at :440-443) |
| Handlers | `admin/backend/src/handlers/admin.rs:757-1030`, `:4394-4559` |
| Authorization | `admin/backend/src/middleware.rs:41-102` (role gate), handler-level gate `admin.rs:875-886` |
| Queries | `admin/backend/src/db.rs:468-524` (`pub mod users`) |

Explicitly out of scope, named so the boundary is closed: the registration-request
queue (`handlers/admin.rs:1078-1320`, `admin/frontend/src/pages/Requests.tsx`),
`updateUserPermissions` (`api/admin.ts:922`, called from `TenantDetail.tsx`), the
tenant CRUD surface, and the second admin handler module in the product backend
(`app/backend/src/proxy/api_handlers/admin.rs`) — the last one is reported below
only as a coherence fact about the same feature name, not audited.

## 1. The gate: what is observable today

Not observable, and this is the first finding of the analysis rather than a
footnote:

| Question | Answer |
|---|---|
| Can the running UI be read? | **No.** Read-only on the repo, no Docker, no build → no `analyze-app` view tree, no screenshot, no `browser_evaluate`, no axe-core sweep, no breakpoint resize. Every UI statement below is therefore **`code` class**, read from source, and the skill's `ui-observed` class is empty for this arm. `[NOT CHECKED: no running app; read-only constraint]` |
| Is the surface's rendered look knowable? | No. Contrast below is **computed from declared hex values**, not measured in the page; the blur/grayscale tests and the breakpoint captures were not run. `[NOT CHECKED: no capture]` |
| Is account-change behaviour observable in data? | **Partly.** Every user mutation writes an audit row (`admin.rs:54-90` helper, called at `:814-825`, `:847-859`, `:949-961`, `:1004-1016`), so role-change/deactivate ratios are computable from that table in principle. Reads (list, search, detail) are not instrumented: `metrics.rs:94-140` exposes only `admin_login_*` and `admin_api_key_*` counters, and the admin SPA ships no analytics client (grep for `posthog\|analytics\|sentry` over `admin/frontend/src` matched one page unrelated to users). |
| Product-usage telemetry for this area? | Absent. `[NOT CHECKED: no access to any analytics/DB]` |

So: the value axis is a design argument, not a measurement; the usability axis is
source-deep and run-blind; the feasibility axis is fully checkable and is where the
weight of this artifact sits.

## 2. Axis: Value (HEART, Goals → Signals → Metrics)

| Goal | Signal | Candidate metric (definition / window) | Observable today? |
|---|---|---|---|
| A platform admin can govern an account safely without a second system | an account change is completed and can be undone | `role-change success ratio = 2xx PUT /admin/users/:id/role / all such PUTs`, 7d rolling, from the audit table | **Partly** — numerator/denominator only via audit rows; not wired to a dashboard |
| An operator can find one account fast | the found account is the one acted on | `search→acted ratios` is not computable: no read telemetry | **No** — this metric is dropped until telemetry exists (the skill's rule: no goal above it, no metric) |
| No false picture of the platform | operator action taken on a truthful state | `misread incidents = account actions taken while the list was in error state / account actions`, 30d | **No** — the error state does not exist (F2), so the denominator is unmeasurable |

No raw count is reported as a metric. A metric with no goal above it was dropped
(search→acted until instrumentation), as the method requires.

## 3. Axis: Usability — scope and what was actually seen

- Scope, narrowed as the method demands: **one section** (Users), **one user group**
  (platform admin / super_admin), **one device class** (desktop web, the app's only
  form factor), **breakpoints not exercised** → the 320 px reflow check (SC 1.4.10)
  was not run and is not claimed either way. `[NOT CHECKED: no running app]`
- Heuristics checked by reading the surface and its primitives: visibility of
  system status, match system/real world, user control and freedom, error
  prevention, recognition over recall, help users recover from errors,
  accessibility. Not checkable without a run: aesthetic/minimalist design, help and
  documentation, and every felt-severity ordering.
- Every heuristic finding below is marked `failure` (a specific WCAG criterion, an
  APG pattern, or a flow that cannot be completed) or `judgement` (a heuristic read
  in context). Per the source, a violated heuristic is not automatically a problem;
  the context and the alternative are named for each judgement.
- WCAG level claimed by the product: **none declared** — no accessibility statement
  or level is stated anywhere in the Users area or the design system
  (`admin/frontend/src/components/ui/`, `index.css`). That absence is itself the
  claim boundary: the criteria below are applied as WCAG 2.2 AA because that is the
  common floor, not because the product claims it.
- axe-core sweep: **not run** (no page). Per its own figure it finds ~57 % of WCAG
  issues, and it has no rule for SC 1.4.10, 2.4.7, 3.3.1, 3.3.3 or 4.1.3, so the
  eight hand-checks are the ones this arm was limited to, from source.
- **Standards cited, and how they were reached.** No `external`-class finding is
  made here, and the reason is stated rather than hidden: the W3C pages were **not
  fetched from the web in this session**. The success criteria and APG patterns
  named below (`1.3.1, 1.4.3, 1.4.10, 1.4.11, 2.1.1, 2.4.7, 2.5.8, 3.3.1, 3.3.3,
  3.3.4, 3.3.7, 4.1.2, 4.1.3`; the combobox, listbox, dialog and table patterns) and
  their artifact URLs carry the read date they were recorded with in the vendored
  method itself — `skills/feature-audit/SKILL.md`, Sources section, read this
  session, which records `https://www.w3.org/WAI/WCAG22/Understanding/` and
  `https://www.w3.org/WAI/ARIA/apg/patterns/` as **read at source 2026-09-20**. A
  finding resting on those criteria *alone* would be an `external` finding with a
  second-hand read date; each one here rests on a `path:line` in this repository
  and uses the criterion as the yardstick, so it is a `code` finding whose standard
  is named. The contrast ratios in F15 are computed in this session, not quoted.
- SUS / UMUX-Lite: **to be run**, not produced here (they are instruments for real
  users).

### 3a. State matrix — one row per interactive component, one per data view

Legend: `y` exists in source, `—` does not exist (each `—` is a finding, folded
into the numbered findings below), `?` not checkable without a run.

| # | Component (citation) | default | hover | focus | active/pressed | disabled | loading | error | notes |
|---|---|---|---|---|---|---|---|---|---|
| I1 | "Create User" toolbar button (`Users.tsx:97-99`) | y | y (`hover:brightness-110`) | ? | y | — | — | — | not disabled while a create is in flight; no loading state on the invoker |
| I2 | Search input (`Users.tsx:107` → `AdminPrimitives.tsx:57-70`) | y | — | y-ish, suppressed (`outline-none`, `:65`) | n/a | — | — (250 ms debounce, `Users.tsx:31-34`) | — | no label, placeholder only; no clear affordance; result count not announced |
| I3 | Table row (`Users.tsx:112-127`) | y | y (`table-row-hover`) | **—** (`<tr onClick>`, no `tabIndex`/`onKeyDown`) | y (selected tint `:118-120`) | n/a | n/a | n/a | not keyboard reachable → F6 |
| I4 | Detail panel container (`DetailPanel.tsx:12-38`) | y | n/a | **—** (no focus move) | n/a | n/a | n/a | n/a | no `role="dialog"`, no `aria-modal`, no Escape → F6 |
| I5 | Role chip buttons, 5 for a super_admin (`Users.tsx:179-190`) | y | y | ? | y (active chip) | y (`:185`) | y (all disabled while `roleMut.isPending`) | — | no confirmation; the `super_admin` chip is refused by the server → F3 |
| I6 | "Edit Profile" (`Users.tsx:202-206`) | y | y | ? | y | — | — | — | stays enabled while the panel is mutating |
| I7 | "Deactivate"/"Activate" (`Users.tsx:207-217`) | y | y | ? | y | y (`:206`) | y (label `Updating…`) | — | no confirmation, no target naming → F5 |
| I8 | "Save Changes" (`Users.tsx:226-231`) | y | y | ? | y | y (`:221`) | y (`Saving…`) | — | field errors impossible: no `error` prop passed → F9 |
| I9 | "Cancel" (`Users.tsx:232-236`) | y | y (`hover:bg-…`) | ? | y | — | n/a | n/a | discards edits silently (no dirty guard) |
| I10 | Modal overlay + close (`Modal.tsx:14-30`) | y | y | **—** | n/a | n/a | n/a | n/a | overlay click closes; no Escape, no focus trap, no `aria-modal` → F6 |
| I11 | Password field (`Users.tsx:250`) | y | — | ? | n/a | n/a | n/a | **—** | no reveal toggle, no confirm field, no `autocomplete="new-password"` |
| I12 | Role select (create) (`Users.tsx:252-253`) | y | — | ? | n/a | — | n/a | — | options from `availableRoles`, which includes a refused value → F3 |
| I13 | Tenant picker (`Users.tsx:256` → `TenantSearchSelect.tsx`) | y | y | **—** (no keyboard handling anywhere in the file) | y | — | y (`isFetching`) | **—** | no `role="combobox"`, no `aria-expanded`, no option roles → F6 |
| D1 | Users table, list data view (`Users.tsx:109-128` → `DataTable.tsx:22-64`) | y | — | — | — | — | y (`:44-52`) | **—** | empty y (`:53-64`); **skeleton —**; **offline —**; **partial —** (no total/pagination, F4); **long-text —** (no truncation strategy on email/tenant, F4); **permission-denied —** collapses into empty (F2) |
| D2 | Detail panel key/value list (`Users.tsx:137-176`) | y | — | — | — | — | — | — | `created_at` row is conditional (`:164`), so the field **disappears** instead of showing "not provided" → F14 |

Counts: 13 interactive-component rows, 2 data-view rows; 15 rows total; **36 cells
hold no state at all** (counted over the table: every `—` cell, checked or
bold-highlighted; each is a finding or a folded sub-state), and 8 further data
states named inside D1's notes (skeleton, offline, partial, long-text,
permission-denied, error) are absent for the list view.

### 3b. Surface-pattern sweep (feature-audit matrix 5), rule by rule

| Group | Rules evaluated | Violated | Rules that could not be evaluated |
|---|---|---|---|
| Data views | 11 | 6 (row keyboard/`<tr onClick>`, no `aria-sort` + no sort at all, pagination absent, count not the server total, no long-text strategy, detail omission); 1 pass (real `<th>`; first column is a human name) | 2 (SC 1.4.10 reflow at 320 px, scroll-region affordance — no run); 2 n/a (not a grid, not virtualized) |
| Controls | 11 | 6 (combobox markup, combobox keyboard, listbox/option roles, placeholder-as-label, suppressed focus indicator `outline-none`, no required/optional convention); 2 pass (target size ≥ 32 px on the icon buttons, pickers enter text rather than forcing a list) | 2 (real target sizes in the rendered page, in-page contrast); 1 n/a (SC 1.3.5 tokens: an admin is not entering their *own* data here) |
| Validation and errors | 4 | 3 (submit-time/serverside mapping, 3.3.1/3.3.3 identification, summary association) | 1 (rendered wording) |
| Flows | 6 | 2 (confirm-before-commit 3.3.4, destructive naming) | 4 (single-step modal: one-question-per-page, check-answers, task list, 3.3.7 — mostly n/a, see M3) |
| Notifications | 4 | 3 (4.1.3 result count, whole-status-string, error-in-dialog) | 1 (announcement audio — cannot be heard by a tool) |

Two rows of the control table are **passes and stay in the table**, as the method
requires: pickers are not calendar-only, and the date the panel shows goes through
`toLocaleDateString` (`Users.tsx:173`) rather than a hand-rolled format.

## 4. Axis: Feasibility — the coherence pass (matrices 1-4)

### M1 — capability (action x layer)

| Action | Surface | Route | Authorization | Service / validation | Persistence |
|---|---|---|---|---|---|
| List users | yes `Users.tsx:109-128` | yes `main.rs:263-266` | yes platform-admin gate `main.rs:440-443` + `middleware.rs:68-79`; **no scope on the actor's reach** `admin.rs:4394-4398` | yes `admin.rs:4394-4467` | yes `db.rs:482-493` |
| Search users | yes `Users.tsx:107` | yes same row (`Query` params `admin.rs:4396`) | yes | yes `admin.rs:4413-4418` | yes `db.rs:482-493` (ILIKE x5) |
| View detail | yes, but only the list row's snapshot `Users.tsx:79-83,131-176` | yes `main.rs:283-286` → `admin.rs:4469` | yes | yes `admin.rs:4469-4503` | yes `db.rs:503-506` |
| Create user | yes `Users.tsx:243-268` | yes `main.rs:263-266` (POST) | yes `admin.rs:892-897`, role gate `:939-941` | yes `admin.rs:892-987` (min 8 chars `:930`) | yes `db.rs:521-523`, inserted `is_active=false` |
| Edit profile (name, email) | yes `Users.tsx:219-241` | yes `main.rs:283-286` (PUT) | yes `admin.rs:4505-4509` | yes `admin.rs:4505-4559`; **no format validation on email, no duplicate handling** | yes `db.rs:508-510` |
| Change role | yes `Users.tsx:179-190` | yes `main.rs:255-258` | yes, actor-role gate `admin.rs:875-886` | yes same | yes `db.rs:512-513` |
| Deactivate | yes `Users.tsx:200-215` | yes `main.rs:259-262` | yes `admin.rs:835-839` | yes `admin.rs:835-869` | yes `db.rs:515-516` |
| Activate | yes (same control) | yes `main.rs:267-270` | yes `admin.rs:988-992` | yes `admin.rs:988-1030` | yes `db.rs:518-519` |
| Delete user | **no** — no control in `Users.tsx` | **no** — no users DELETE in `main.rs:230-443` | n/a | n/a | **no** — `db.rs:468-524` has no DELETE constant (search: whole `pub mod users` block, 468-524) |
| Reset another user's password | **no** | **no** | n/a | n/a | **no** (same search) — the only password writes are `CREATE_INACTIVE` `:521` and the approve-request insert `admin.rs:1151-1154` |

Disagreements read out of the matrix:
- **Surface yes, layer no** → the `super_admin` role chip and select option (F3).
- **Layer yes, surface no** → the detail endpoint `GET /admin/users/{id}` and its
  client `fetchUser` have no caller (F8); `DELETE`/password-reset are absent on
  every layer, which is a recorded gap, not a defect.
- **Route yes, authorization no** → none found: every user route sits behind the
  platform-admin gate (`main.rs:440-443`), the strongest pass row in this audit.
- **The end of the action** → create sends no credential: the admin types the
  password (`Users.tsx:250`), the account lands inactive (`db.rs:521-523`), and no
  mail/push is sent from this path (no mail dependency in the create handler,
  `admin.rs:892-987`). The recipient receives nothing until a human tells them.
- **Agreement row**: audit writes on all four mutation paths (`admin.rs:949-961`,
  `:814-825`, `:847-859`, `:1004-1016`).
- **Sibling convention**: the repo scopes delegated reads by membership in six other
  modules (`db.rs:144,214,260,372,644,764` — enterprise accounts, business units,
  service accounts, ...), while `users` has none; the users routes are platform-admin
  only, so this is a *documented-intent* gap, not a live defect (F7/F1 area).

### M2 — field contract

| Field | Column / type (`db.rs`) | Read by API | Written by API | Rendered (list / detail / form) | Validated | Label / enum source | Locale / format |
|---|---|---|---|---|---|---|---|
| `user_id` | `uuid`, `:483` | yes | generated | list key only; detail shows `slice(0,8)+'…'` `Users.tsx:132` | n/a | n/a | truncated, not human-readable (only as a subtitle, so pass) |
| `email` | `text` | yes | create `:521`, update `:508` | list `:121`, detail `:141`, create/edit form | min-length only via `is_empty` (`admin.rs:922-928`); **no format check on update** | raw | server passes through, client prints raw |
| `full_name` | `text`, `COALESCE(full_name,'')` | yes | yes | list `:120` (`'—'` fallback), detail, form | none | raw | none |
| `role` | `text` | yes | create + update | list badge `:122`, detail `:154`, chips `:179-190`, select `:252` | **two sources disagree**: surface `Users.tsx:11` vs server `admin.rs:875` | colour map `Users.tsx:18-20` | `replace('_',' ')` only (lowercase, `:23`) |
| `is_active` | `bool` | yes | create sets false, activate/deactivate | list badge `:126`, detail badge `:161` | n/a | `StatusBadge` | text label, not colour-only — pass |
| `tenant_id` | `uuid` | yes | create/update | list fallback `:123`, detail fallback `:142`, picker value | non-empty check only (`admin.rs:922-928`); **existence not checked** → FK error → scrubbed 500 (`admin.rs:979-983`) | n/a | `slice(0,8)` fallback |
| `tenant_name` | joined `t.name` `:484` | yes | n/a | list `:123`, detail `:142` | n/a | n/a | none |
| `created_at` | timestamp::text | yes | DB | detail only, conditional `:164-174` | n/a | n/a | `toLocaleDateString('en-US')` `:169` — **hard-coded locale, not the admin's** |
| `last_login_at` | timestamp::text | yes `:484` | DB | **nowhere** — no reference in `Users.tsx` | n/a | n/a | n/a |
| `password` | not stored; `password_hash` | request only | hash on create | create form `:250` | min 8 chars (`admin.rs:930-935`) | n/a | n/a |
| `permissions` | optional in type | **not read by this feature** | via another route `api/admin.ts:922` | nowhere in this feature | — | — | — |

### M3 — flow and step contract

| Step / flow | Precondition | What it validates | What it writes | Skip prevention | Resume / persistence | Back-nav retention | Where an error lands |
|---|---|---|---|---|---|---|---|
| Create user (single-step modal, `Users.tsx:243-268`) | actor holds panel role; a tenant must be chosen | client: none; server: non-empty email/password/tenant, password ≥8, role in `ALL` (`admin.rs:922-941`) | `users` row, inactive (`db.rs:521`) | only on the server — the modal's submit is enabled with every field empty (`Users.tsx:263-266`) | none: closing the modal drops the form; a reload drops it | n/a (single step) | a toast at the top-right, naming no field (`Users.tsx:52`) → F9 |
| Deactivate → Activate lifecycle (`Users.tsx:200-215`) | an open detail panel | none | `is_active` (`db.rs:515-519`) | none: one click acts (`Users.tsx:207`) | server-side, persists | n/a | health only via the toast (`Users.tsx:76`), which names neither the user nor the new state |
| Edit profile (in-panel mode, `Users.tsx:219-241`) | an open panel | none client-side; server applies `COALESCE` (`db.rs:508-510`) | `full_name`, `email`, `updated_at` | none | none: Cancel/Save discard; panel close keeps `editForm` in state until reopen | leave-and-return loses the edit with no warning | toast (`Users.tsx:59`) |

No multi-step wizard exists in this feature, so six of the flow rules are `n/a`
rather than unchecked — stated, not silently dropped.

### M4 — interaction dependency

| Trigger | Dependents | Required action on change | Who owns the state | What is announced |
|---|---|---|---|---|
| Tenant picker change (`Users.tsx:256`) | role select (`:252`) — the role set is **not** tenant-dependent | keep | `form` state, `Users.tsx:19` | nothing (correct: nothing changes) |
| `useMe` role resolves/changes (`Users.tsx:27-28,85`) | role chips + create select | recompute | react-query cache, `staleTime` 5 min (`useMe.ts:22-30`) | nothing — for up to 5 minutes after a server-side role change the picker can offer a set the server now refuses; single-pass judgement |
| Search input (`Users.tsx:107`) | table rows + 4 stat cards (`:100-105`) | recompute (debounced 250 ms, `:31-34`) | local state | **nothing** — the result count changes silently (SC 4.1.3; no live region anywhere in the feature) |
| Deactivate/activate (`Users.tsx:207`) | row badge, panel button label, stat cards | recompute | react-query invalidation (`:77`) | a toast reading "Status updated" — names neither user nor state |
| Role change (`Users.tsx:184`) | role badge(s), chips, stat cards | recompute | react-query invalidation (`:70`) | toast "Role updated" — no target name |
| Panel close (`DetailPanel.tsx:14`) | `selectedUser`, `isEditing`, `editForm` | reset | `Users.tsx:79-83,131` | n/a |

The class this matrix exists to catch — **a control still showing a state the view
no longer has** — does not occur here: the tenant picker resets its own search on
close/select (`TenantSearchSelect.tsx:59-63,73-79`) and the panel re-seeds
`editForm` on open. Recorded as a pass row, not silently dropped.

## 5. Findings, most severe first

Each: class, citation, severity 0-4 (frequency x impact x persistence), type,
rater count, Prevent.

### F1 — user mutations have no guard on the *target*
`code` · `admin.rs:789-833` (role), `:835-869` (deactivate), `db.rs:512-517`, doc `:787-788` · **severity 3** · **failure** · 1 pass.
The handler validates the *requested* role against the *actor's* role (`admin.rs:875-886`) and nothing else: `UPDATE users SET role = $2 WHERE user_id = $1` and `UPDATE users SET is_active = false WHERE user_id = $1` are keyed on the target id alone. An `admin` (not only a `super_admin`) can therefore demote a `super_admin`, deactivate the account that grants panel access, or deactivate themselves — one click each, no confirmation (F5), no reversal path stated anywhere in this feature.
**Prevent:** a service-level test that fails on the pre-change commit — "an actor may not modify a target whose role outranks the actor's, and self-deactivation is refused" — plus one line of product intent stating whether a platform `admin` is meant to be tenant-unscoped (today nothing says so).

### F2 — the users table has no error state; an outage renders as "No users found"
`code` · `DataTable.tsx:22-24,44-64` (props are `isLoading`/`isEmpty` only), `Users.tsx:111`, backend intent `admin.rs:4436-4443` · **severity 3** · **failure** · 1 pass.
A failed `useQuery` leaves `data` undefined, so `users.length === 0` and the table prints "No users found" while the four stat cards print 0 — a DB outage is indistinguishable from an empty platform. The component library already ships `QueryErrorState.tsx` and the backend deliberately fails loudly here (its own comment: "the total count is SOC-visible; a silent 0 hides real DB outages"), so the client collapses exactly the signal the server was protecting. The same collapse applies to a 403 (permission-denied state absent, D1).
**Prevent:** a `DataTable` error branch plus a component test asserting `isError` renders an alert — not the empty state; the assertion has to be on the error case, since an empty-state test passes today.

### F3 — the surface offers a role every layer refuses
`code` · `Users.tsx:11,85,184,253` vs `admin.rs:875,880-886` · **severity 3** · **failure** · 1 pass.
`ALL_ROLES` includes `super_admin`, `availableRoles` hands it to a super_admin in both the chip row and the create select, and `ADMIN_ASSIGNABLE_ROLES` excludes `super_admin` for every actor, so the click returns 400 "Invalid platform role". A dead control that looks privileged — the exact "an offer the system forbids" class.
**Prevent:** one source for the assignable set (proposal P2); the guard is a test asserting the UI's option list is a subset of `ADMIN_ASSIGNABLE_ROLES`.

### F4 — the list silently truncates at 200, discards the authoritative total, and has no pager
`code` · `Users.tsx:46,95,101` vs `admin.rs:4437-4450` (`COUNT_FILTERED` returns the real total), `Pager.tsx:10-11`, `ThreatIntel.tsx:247` · **severity 3** · **failure** · 1 pass.
The API computes a filtered total and the client throws it away, hard-codes `limit: 200`, and prints `allUsers.length` as both the page subtitle and the "Total" stat card. Past 200 users the header number is wrong and there is no way to reach row 201 — while the design system ships `Pager` and the sibling surface ThreatIntel uses it. The result count after a search changes with no live-region announcement (SC 4.1.3, no `aria-live` in the feature).
**Prevent:** a component-checklist rule "a list view renders Pager when `total > pageSize`, and a count shown to the user is the server total"; the e2e assertion is that the rendered total equals `COUNT_FILTERED`, which fails today.

### F5 — deactivate and role change commit on one click, name no target, and cannot be undone
`code` · `Users.tsx:184,207`, `db.rs:512-517` · **severity 3** · **failure (SC 3.3.4)** · 1 pass.
Both act directly from a click handler with no confirmation and no undo; the one guard is `disabled` on the currently-active role chip (`:185`). The consequence — an operator locks a colleague out by misreading the row they clicked — is a judgement, but the missing check/reversal for a data-changing, access-removing action is a criterion failure. The repo already has the pattern to follow: `ServiceAccountSearchSelect`-era confirm dialogs elsewhere in the panel.
**Prevent:** an e2e assertion that a destructive control opens a confirmation naming the user's email and that the mutation is not sent until confirmed (the assertion must be on the request log, since a UI-only check passes while the request still fires).

### F6 — no accessible semantics on the table, the picker, the search field, the modal or the panel
`code` · `DataTable.tsx:28-40` (`<th>` with no `scope`, no caption/accessible name), `AdminPrimitives.tsx:57-70` (placeholder-only input, `outline-none` at `:65`), `TenantSearchSelect.tsx` (a grep for `role=\|aria-\|onKeyDown\|tabIndex` over `components/ui/*.tsx` returned **zero** matches for this file and for the primitives it sits with), `Modal.tsx:14-30` (no `role="dialog"`, no `aria-modal`, no Escape, no focus move), `DetailPanel.tsx:12-38` (same), `Users.tsx:112-127` (`<tr onClick>` with no `tabIndex`/`onKeyDown`) · **severity 3** · **failure** (APG combobox/listbox/dialog; SC 2.1.1, 1.3.1, 3.3.2, 4.1.2) · 1 pass.
The Users table is unreachable by keyboard: opening a row's detail panel requires a mouse, and the panel cannot be escaped except by clicking. The picker is a styled input over a `div` popup with no combobox contract, and neither the modal nor the panel announces itself as a dialog. Two of the eight hand-checks the skill names (focus indicator visibility, and whether a revealed thing is announced) remain open because they need a page.
**Prevent:** component tests asserting `role`/`aria-*` on each primitive (they fail today) plus the pinned axe-core injection in CI as a net, not as the proof.

### F7 — documented intent vs implemented capability (both sides cited)
`code` · doc `admin.rs:787-788` ("Only super_admin can assign admin/super_admin") vs code `:875-886` · **severity 2** · **failure** · 1 pass.
`ADMIN_ASSIGNABLE_ROLES` excludes `super_admin`, and the gate is `requested == "admin" && actor != "super_admin"` → a super_admin cannot assign `super_admin` either, and `admin`-role actors can assign `operator`/`viewer`/`api_user`. The comment claims a capability no code path implements; the sibling note in the same file ("super_admin can only be created via the CLI tool", `:873`) contradicts it two lines later.
**Prevent:** the comment is generated from, or explicitly references, `ADMIN_ASSIGNABLE_ROLES`; a doc-vs-constant test fails on the pre-change commit.

### F8 — the detail endpoint and its client function have no caller
`code` · `main.rs:283-286`, `admin.rs:4469-4503`, `api/admin.ts:379-381`, panel renders the row snapshot `Users.tsx:79-83,131-176` · **severity 2** · **failure** (absence proof: grep `fetchUser` over `admin/frontend/src` matched only its definition at `admin.ts:379`; grep of the route string matched only `admin.ts:380`) · 1 pass.
A whole read path exists and nothing calls it: the panel shows whatever the list snapshot held, so a change made by another admin is invisible until the list is invalidated. Whether the staleness bites is a judgement; the dead path is a fact.
**Prevent:** either wire the panel to `GET /admin/users/{id}` or delete both; the mechanical net is a call-site check (ts-prune/knip-style) that fails on an exported client function with no importer.

### F9 — validation is server-only and the error names no field
`code` · `Users.tsx:243-268` (no `required`, no `error` prop — `FormElements.tsx:5-33` supports `error` and it is never passed), `:52` (toast only), `admin.rs:922-941` · **severity 2** · **failure (SC 3.3.1/3.3.3)** · 1 pass.
The submit button is enabled with every field empty, the only feedback is a top-right toast, and the message ("email, password, and tenant_id are required") arrives after a round trip. A bogus `tenant_id` produces a scrubbed 500 rather than an error on the field (`admin.rs:979-983`). Values are kept and the toast is not a validation error inside a dialog (so the notification rule is honoured) — the field identification is the failure.
**Prevent:** `FormInput error` wired to a field-keyed map from the server's response and an `aria-describedby` on the invalid field; the test asserts the invalid input carries the association.

### F10 — the create toast hides that the account cannot log in yet
`code` · `Users.tsx:50` ("User created") vs `admin.rs:963-970` (returns `is_active:false` and the message "User created (inactive). Activate after approval.") · **severity 2** · **failure (SC 4.1.3 context)** · 1 pass.
The client discards the server's message, so an admin can believe an account is usable when it is not; the new row then reads "Inactive", the same word the surface uses for a deliberately deactivated account.
**Prevent:** the toast renders the server's `message` field; a unit test on the created-user copy fails today.

### F11 — the search label understates what the search reaches
`code` · `Users.tsx:107` ("Search by name or email...") vs `db.rs:482-493` (email, full_name, role, `user_id::text`, tenant name) · **severity 2** · **failure** for the label gap; the casefold question is **`[NOT CHECKED: no database, no collation observable from source]`** · 1 pass.
Five ILIKE predicates with no normalization: whether a Turkish "İ" name is found by typing "i" depends on the column collation, which source cannot answer — this is the exact class the method's worked example calls out, and it is left as a question here rather than asserted.
**Prevent:** the label lists the searchable fields (or the predicate shrinks to the label) and a query test with a Turkish-cased fixture; the fixture test is the assertion that fails before a collation fix.

### F12 — the same feature name lives twice, and one copy is unmounted and unauthenticated
`code` · `app/backend/src/proxy/api_handlers/admin.rs:11-253` (handlers incl. `admin_user_role`, `admin_user_deactivate`), re-exported at `proxy/api_handlers/mod.rs:24`, with **no router registration**: the only admin route mounted in that backend is `/api/v1/admin/detection-rules/reload` (`proxy/server.rs:886`), and none of these handler names appears in any `.route(` (grep of the six handler symbols over `app/backend/src` matched only the file itself, the re-export, and a string literal in a policy test) · **severity 2** · **failure** (absence proof) · 1 pass.
These handlers take no auth extractor and hard-code a default role (`admin.rs:200-247`, the `unwrap_or("viewer")` body parse). Dead today; registered tomorrow by anyone wiring the admin area into the product backend, they become an unauthenticated role-change surface. The layer matrices for the *admin backend* feature are unaffected — this is the neighbouring module with the same name.
**Prevent:** delete the module, or a router-coverage test that fails when a `pub async fn` handler in `api_handlers/` has no `.route(` registration.

### F13 — a contract field no surface renders
`code` · `db.rs:482-486` and `types/admin.ts:94` (`last_login_at`), `:96` (`permissions`) vs `Users.tsx` (no reference to either) · **severity 1** · **failure** · 1 pass.
`last_login_at` is selected, joined, typed and shipped to the browser on every list load and shown nowhere — an operator asking "is this account in use?" has the answer in the payload and no way to see it. `permissions` is typed into the same interface and populated only by another screen.
**Prevent:** a field-to-surface table checked in the component checklist, or the field dropped from the list response so the contract matches what the screen needs.

### F14 — the detail panel omits a field instead of saying "not provided"
`code` · `Users.tsx:164-174` (the `created_at` row is conditional on the value) · **severity 1** · **failure** (feature-audit data-view rule: "every field showing a value or an explicit 'not provided'") · 1 pass.
A null `created_at` (the column is nullable in the row mapping — `db.rs:483` casts to text without a `COALESCE`) makes the row vanish, so a missing value is indistinguishable from a field the panel never had.
**Prevent:** render the row with an explicit "not provided"; a component test on the null case, which fails today because the row is absent.

### F15 — badge text contrast is far below the AA floor (computed, not measured in the page)
`code` (values) / would be `ui-observed` (rendering) · `StatusBadge.tsx:14-25` and `Users.tsx:18-24` set `color: <hue>` on a `${hue}10`/`${hue}12` tint over the page background `#d8dee7` (`index.css:5`) · **severity 3 (if the declared values are what renders)** · **failure (measured from declared values)** · 1 pass.
Computed WCAG ratios against the page background: `#00D97E` **1.38:1**, `#F59E0B` **1.59:1**, `#10B981` **1.87:1**, `#F43F5E` **2.71:1**, `#4d84b8` **2.92:1**, `#65748a` **3.51:1** — at 10 px, so the 3:1 large-text allowance does not apply (SC 1.4.3 needs 4.5:1). Assumption stated: the pill background is a ~6 % tint of the same hue over `--color-bg-page`, so the ratio is dominated by the text hue. **A page measurement (`browser_evaluate` reading computed styles) or a screenshot was not run — this is a computation from source, not an observed ratio**, and the "Active" badge is the worst case.
**Prevent:** the palette tokens carry their contrast ratio and a test computes it at build time (a ratio assertion per status colour), rather than an eyeballed palette in a `Record<string,string>` literal.

### Pass rows (agreement between layers, kept as the control)

| # | Agreement | Citation |
|---|---|---|
| P-a | Real `<table>`/`<th>` headers, so the table is a table to assistive tech (no `scope`/caption — F6, but the primitive is right) | `DataTable.tsx:28-33` |
| P-b | Every user route sits behind the platform-admin gate, and the handler re-checks the actor role | `main.rs:440-443`, `middleware.rs:68-79`, `admin.rs:800-802` |
| P-c | Every user mutation writes an audit row with actor, action, target | `admin.rs:814-825,847-859,949-961,1004-1016`, helper `:54-90` |
| P-d | `total` is computed with the same predicate as the rows, so the count matches the filter | `db.rs:494-501` vs `:482-493` |
| P-e | `limit` is clamped server-side (1..500), so the client's 200 is legal and cannot DoS the query | `admin.rs:4400-4406` |
| P-f | `text-white` in the JSX is remapped to `--color-text-primary` inside `.admin-main`, so the dark-on-light text passes — a source-only read that stopped at the class name would have reported a 1.2:1 catastrophe | `index.css:120-122` |
| P-g | The tenant picker resets its own search on close/select, so it cannot show a stale query | `TenantSearchSelect.tsx:59-63,73-79` |
| P-h | Activate/deactivate are symmetric single-statement updates | `db.rs:515-519` |

## 6. Capability-change proposals

A fix naming a layer that does not exist yet is a proposal, with a rejectable
artifact. Three:

### P1 — target-authority guard for user mutations
| Heading | Content |
|---|---|
| Capability (`code`) | an actor may modify only a user their authority covers, and may never remove their own panel access |
| Absence proof (`code`) | `admin.rs:789-833` and `:835-869` consult only the actor's role; `db.rs:512-517` key on the target id alone; the input that fails: `PUT /admin/users/{super_admin_id}/role {"role":"viewer"}` from an `admin` session |
| Contract delta | a permission rule plus its test: `role_rank(target) < role_rank(actor)` and `actor_id != target_id`, asserted as a contract test over the four user mutations; rejected by running that test on the current commit |
| Migration | none (no schema change); if the rule is enforced in SQL instead, expand→backfill is empty→contract in the same release |
| Rollout | flag `admin_user_mutation_guard` (boolean, expected lifetime one release), initial exposure internal super_admins, owner: platform admin area owner, abort threshold: any 403 on a legitimate self-scoped edit within 24 h |
| Verification | new test file for the handler guard: fails before, passes after |
| Reversibility | the guard writes nothing; restore = revert the commit |
| Decision | ADR "Target authority for platform admin mutations", status: proposed; supersedes the unwritten assumption that any platform admin may act on any account |
| Appetite | one day, out of bounds: redesigning the role model or adding a role hierarchy table |

### P2 — one source for the assignable role set
| Heading | Content |
|---|---|
| Capability (`code`) | the role options a surface offers are exactly the roles every layer accepts, for the actor in question |
| Absence proof | `Users.tsx:10-11` hand-maintains two arrays while `admin.rs:875` holds a third (`ADMIN_ASSIGNABLE_ROLES`); the failing input: clicking the `super_admin` chip → 400 (`admin.rs:880-886`) |
| Contract delta | a generated TS constant (or a JSON/endpoint) derived from `ADMIN_ASSIGNABLE_ROLES`, plus a test asserting `seteq(UI options for role R, serverAssignable(R))`; rejected by running the comparison test on the current commit |
| Migration | none |
| Rollout | no flag (a build-time constant); abort: revert; owner: admin SPA owner |
| Verification | the comparison test, plus the existing role-grant handler test family (`admin.rs` test module) |
| Reversibility | nothing persisted |
| Decision | ADR "Assignable-role single source", status: proposed |
| Appetite | half a day; out of bounds: changing the role model itself |

### P3 — credential reset for an existing account (capability absent on every layer)
| Heading | Content |
|---|---|
| Capability (`code`) | an admin can restore an account holder's access by issuing a new credential, with a stated delivery path |
| Absence proof | no route in `main.rs:230-443`; no DELETE/credential constant in `db.rs:468-524`; the only password write is `CREATE_INACTIVE` (`db.rs:521`); failing input: a user's forgotten password has no in-product remedy other than delete (also absent) and re-create |
| Contract delta | a proto/OpenAPI-level route `POST /admin/users/{id}/password-reset` + permission rule + the assertion that the old hash no longer verifies and the new one does (a contract test that fails on the current commit) |
| Migration | none for storage; the delivery channel is the delta (mail or one-time link), expand → enable → contract with a dated retirement of the manual path |
| Rollout | flag `admin_password_reset` (boolean, lifetime two releases), owner: identity owner, abort threshold: >1 % failed verifications after reset within 7 days |
| Verification | an integration test: reset → login with the new credential succeeds, with the old one fails |
| Reversibility | the new hash overwrites the old — **one-way for the affected credential**; the restore step is the previous hash only if captured before, so treat as approval-gated |
| Decision | ADR "Admin-issued credential reset", status: proposed |
| Appetite | two days; out of bounds: self-service reset, MFA |

## 7. Axis: Competition — not covered, in one line

Not covered in this arm's box, and the method is explicit about what would count:
no competitor artifact was read in this session, so no comparison basis can be
stated and no fact carries a URL and a read date. What would change it: an
artifact-backed teardown of the platform-admin user surfaces of two comparable
products (basis stated first: task time to deactivate one account, and audit
completeness per action), read on a dated session. Until then the
recommendations below rest on the repository's own conventions and the cited
standards, and that is stated rather than dressed up as a market position.

## 8. Axis: Triage

| Feature / capability | Verdict | Deciding metric | Threshold | Timeframe | Action | Flag | Owner |
|---|---|---|---|---|---|---|---|
| List users | **fix** | rendered total vs `COUNT_FILTERED` | any mismatch | next release | wire `Pager` + server total (F4) | none | admin SPA owner |
| Search users | **fix** | label-vs-predicate test | test red | next release | align label and predicate; add the Turkish fixture (F11) | none | admin SPA owner |
| View user detail | **cut or fix** | caller count for `GET /users/{id}` | 0 callers | next release | wire it or delete it (F8) | none | admin SPA owner |
| Create user | **fix** | field-error binding test | test red | next release | field-level errors + server message surfaced (F9, F10) | none | admin SPA owner |
| Edit profile | **keep** | — | — | — | record as accepted: no email validation is a known debt | none | platform admin owner |
| Change role | **fix** | target-authority test | test red | next release | P1 + P2, and the confirm step (F1, F3, F5) | `admin_user_mutation_guard` | platform admin owner |
| Deactivate / activate | **fix** | same target-authority test + confirm assertion | test red | next release | P1 + confirmation naming the user (F1, F5) | same flag | platform admin owner |
| Credential reset | **bet** | support tickets for "user cannot log in" per 30 d | > the triage period's baseline, or the manual path costs > 15 min/incident | one quarter | P3, gated by the ADR | `admin_password_reset` | identity owner |
| Delete user | **cut** (deliberate absence) | — | — | — | record as a decision: absence is intentional until a retention policy exists | none | platform admin owner |
| Accessible semantics of the area | **fix** | axe-core sweep + the component aria tests | any rule red / test red | next release | F6's primitive tests | none | design-system owner |
| Badge contrast palette | **fix** | computed ratio per status hue | < 4.5:1 | next release | F15's build-time ratio test | none | design-system owner |

"No flag, no owner" rows were not created where the action is a code change inside
an existing owner's area; the two flagged rows name a lifetime, an abort threshold
and an owner, per the method.

## 9. Coverage — rows checked, rows that could not be

| Matrix | Rows | Checked from source | Not checkable here | What would change the conclusion |
|---|---|---|---|---|
| M1 capability | 10 | 10 | 0 | a running app to confirm the controls exist and are enabled (`ui-observed`) |
| M2 field contract | 11 | 11 | 0 | a DB read to see real null/duplicate data |
| M3 flow / step | 3 | 3 | 0 (6 sub-rules `n/a`: no wizard in this feature) | a run to see the modal's real submit behaviour |
| M4 interaction dependency | 6 | 6 | 0 | a run to see announcement timing |
| M5 surface patterns | 36 rules | 36 rules | 11 rules (SC 1.4.10, 2.4.7, target sizes, the in-page contrast, announcement audio) | axe-core + `browser_evaluate` + screenshots at 320/768/1280, dark mode, 200 % text |
| State matrix | 15 rows | 15 rows | 21 cells | any capture of the surface |
| Findings | 15 | 15 (all `code`) | 0 | `user-verbatim`, `behaviour` and `ui-observed` are all **empty classes** in this artifact: no interview/ticket was read, no telemetry was accessible, no screen was rendered |

Behaviour class, precisely: role-change/deactivate activity *is* reconstructible
from the audit rows (`admin.rs:54-90` and the four call sites) as a ratio with a
denominator, but this arm had no database, so no such ratio is reported here — an
uncomputed metric, not a measured one.

## 10. Scorecard (research-skill anchors, 1-5)

| Dimension | Score | Why |
|---|---|---|
| Evidence relevance | 4 | every finding cites a named file:line read this session; the two source-only near-misses (`text-white`, the enterprise-role gate) were caught and re-classed as passes |
| Class discipline | 4 | every finding carries exactly one class; `ui-observed`, `behaviour` and `user-verbatim` are declared empty rather than faked |
| Depth | 4 | component x state reached for 13 controls and 2 data views; the two measured items (contrast) are computed from declared values with the assumption stated |
| Image evidence | 1 | nothing was rendered: no screenshot, no blur test, no grayscale test, no breakpoint, no dark mode. The read-only constraint is the reason, and the score is not excused by it |
| Axis coverage | 4 | all five axes addressed; competition is one honest line, not a fabrication |
| Metric integrity | 4 | Goals→Signals→Metrics chain given; two metrics dropped for having no signal; no raw count presented as a metric |
| Solution plurality | 2 | only one solution per finding; the method's three-candidate comparison was not run — the largest methodological gap in this artifact |
| Feasibility grounding | 5 | every capability cell is a `path:line`; the two absences (DELETE, password reset) name the search that covered the module |
| Decision quality | 4 | every feature ends keep/fix/cut/bet with a metric and an owner; the "keep" row's debt is named rather than hidden |
| Scope calibration | 5 | section 0 and section 9 name the boundary and the misses; the flip conditions are stated |

Mean = **3.7** (no dimension below 1, two above 4.5 on none) → **revise**, per the
method's bands, driven entirely by the two dimensions a read-only, run-less arm
cannot satisfy: image evidence and solution plurality. Those two are the change
list for the next arm, not a caveat on the findings.

## 11. What this analysis did not look at, and what would flip it

- **The running app** — no view tree, no screenshot, no page measurement, axe-core
  or Core Web Vitals; hence no `ui-observed` row and no verified severity ordering.
  A second pass with the app up would promote or demote F6/F15 and probably add the
  two classes the method's worked example found only by running it (a table wider
  than its container at 320 px, and a casefolded search miss).
- **The database** — no collation, no real nulls, no duplicate-email behaviour, no
  row counts; F11's casefold question and the "200-user cap" impact stay questions.
- **Users and telemetry** — no interview, ticket, review or dashboard was read, so
  the whole `behaviour` and `user-verbatim` side is missing and every priority above
  rests on defect severity rather than on observed harm.
- **Competition** — see section 7.
- **Accessibility level** — the product declares none; the AA floor applied here is
  this arm's assumption, not the product's claim.
