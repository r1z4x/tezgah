# feature-audit — Ustam admin `/users` (E4 arm B, rater 2)

Artifact under test: `/Users/rizax/Projects/tezgah/skills/feature-audit/SKILL.md`
(frozen). Arm: B. Extra instruction applied: **run the E4 protocol probe verbatim
before filling the capability matrix and record its output as the matrix's route
evidence** (`/Users/rizax/Projects/tezgah/.tezgah/research/feature-coherence/experiments/E4-mechanism-ablation/protocol.md`).

Repo under audit: `/Users/rizax/Projects/Ustam` at `98f985f6` (clean tree).
Running app read at `http://localhost:3000` (Next dev server, cwd `apps/admin`,
already running; not started or stopped by this rater). Today 2026-09-20.

## Feature boundary

- **Entity**: one organization membership — the `User` plus its `Membership` in
  the caller's organization.
- **Actions**: list, search, filter by membership state, read one, invite (create
  the user + membership), change role, change scope, deactivate, reactivate.
- **Screens**: `/users` only (there is no `/users/[id]`;
  `apps/admin/.next/types/routes.d.ts:52` lists `/users` and nothing under it).
- **Endpoints**: the five under `/api/v1/users` (`docs/openapi.json`).
- **Files**: `apps/admin/app/(dashboard)/users/{page,actions,user-labels}.ts`,
  `apps/api/src/users/{users.controller,users.service}.ts`,
  `packages/domain/src/users.ts`, `apps/admin/components/{AdminModal,
  AdminActionForm,ConfirmationDialog,MutationNotice}.tsx`, `apps/admin/lib/
  {api,admin-context,admin-panel-session,mutations,mutation-guard,admin-surfaces}.ts`,
  `apps/api/prisma/schema.prisma`, `docs/openapi.json`.

Passes run: **4** — (1) first-time operator, rendered page at 1440 and 320, light
and dark, screenshots read; (2) repeat operator workflow (filter → clear →
invite → confirm → refuse); (3) keyboard-only pass (tab order, focus trap,
Escape, focus return); (4) API client with no UI — the committed contract, the
generated client and the second (mobile) consumer, read statically; see
*Coverage* for what pass 4 could not do and why.

---

## Arm-B probe (step 1) — output recorded as the route-column evidence

Verbatim command (protocol.md, "The probe (arm B's raters run this verbatim)"),
run from `/Users/rizax/Projects/Ustam`:

```sh
cd /Users/rizax/Projects/Ustam && python3 - <<'PY'
import json, re, subprocess, pathlib
spec = json.loads(pathlib.Path("docs/openapi.json").read_text())
api = {f"{m.upper()} {p.replace('/api/v1','')}" for p, ops in spec["paths"].items()
       for m in ops if m.lower() in ("get","post","patch","put","delete")}
files = subprocess.run(["bash","-lc","grep -rloE 'adminApi\\(' apps/admin/app apps/admin/lib "
                        "--include=*.ts --include=*.tsx"],capture_output=True,text=True).stdout.split()
surface = set()
for f in files:
    t = pathlib.Path(f).read_text()
    for m in re.finditer(r"adminApi\(\s*[`']([^`']+)", t):
        p = m.group(1)
        if p.startswith("/users"):
            tail = t[m.end():m.end()+200]
            meth = "POST" if "'POST'" in tail or '"POST"' in tail else ("PATCH" if "'PATCH'" in tail or '"PATCH"' in tail else "GET")
            surface.add(f"{meth} /users{p[len('/users'):]}")
norm = lambda k: re.sub(r"\$\{[^}]+\}", "{id}", k)
c = {norm(k) for k in api if k.split(' ')[1].startswith("/users")}
s = {norm(k) for k in surface}
print("contract-only:", sorted(c - s))
print("surface-only:", sorted(s - c))
PY
```

**stdout** (unchanged):

```
contract-only: ['GET /users/{id}', 'POST /users/{id}/deactivate']
surface-only: []
```

**exit code**: `0`.

**What this evidence covers, and its limit.** The probe compares the committed
contract against the *admin* call sites only (`apps/admin/app`, `apps/admin/lib`).
It proves two endpoints have no admin-side caller; it does **not** prove they are
dead, because a second consumer exists outside those two roots. My own search
across `apps/admin/app`, `apps/admin/lib`, `apps/mobile/src` and
`packages/api-client/src` for `users/` returned only `POST /users/invite` and
`PATCH /users/{id}` as writes and `GET /users` as a read — no `GET /users/{id}`,
no `POST /users/{id}/deactivate` anywhere. The repo's own consumer map agrees:
`docs/design/admin-owner-v3-2026-09-19/evidence/mobile-consumers.md:530-536`
lists `users` as 3 endpoints (`GET /users`, `PATCH /users/{userId}`,
`POST /users/invite`). So both rows are contrived-and-unreached, established by
the probe *and* by a search that covers the non-admin consumer.

---

## Matrix 1 — capability (11 rows: 11 checked, 0 unchecked)

Route column: the arm-B probe output above, plus the controller read for the
per-endpoint guard. `no` counts prove absence by the search named in the finding.

| Action | Surface | Route | Authorization | Service / validation | Persistence |
|---|---|---|---|---|---|
| List the organization's users | `yes` — table `page.tsx:167-200` | `yes` — `GET /users`, `users.controller.ts:34`; probe: reached | `yes` — `@RequirePermissions('user.manage')` `:35`; surface `page.tsx:46` | `yes` — `users.service.ts:26-65`; client re-parses `page.tsx:13-32` | `yes` — `User`+`Membership`+`MembershipRole` `schema.prisma:1053,1108,1436` |
| Search by name/email | `yes` — `page.tsx:145-148,156-158` | **`no`** — the query is applied in memory over the full list, `page.tsx:60-66`; no query param on the route (`users.controller.ts:34-40` takes no arguments) | n/a (same read) | n/a | n/a |
| Filter by membership state | `yes` — `page.tsx:150-156` | **`no`** — same in-memory filter, `page.tsx:63-65` | n/a | n/a | n/a |
| Read one user's full record | **`no`** — no detail view and no row link; the only affordance is the edit dialog `page.tsx:224-279` | `yes` — `GET /users/{id}`, `users.controller.ts:49`; **probe: contract-only**, and no caller in `apps/mobile/src` either | `yes` — `user.manage` `:50` | `yes` — `users.service.ts:77-111`, returns roles as `{key,name}` objects | `yes` — same tables |
| Invite (create user + membership) | `yes` — modal `page.tsx:74-136`; exercised | `yes` — `POST /users/invite` `:59` | `yes` — `user.manage` `:60` + `requireAdminMutation('team.invite')` `actions.ts:53` → `user.manage` `mutations.ts:29` | `yes` — `InviteUserInput` `users.ts:11-24`, `ZodValidationPipe` `users.controller.ts:64` | `yes` — `users.service.ts:113-177`; audit `:160`, outbox `:168` |
| Change role | `yes` — single-choice select `page.tsx:249-256` | `yes` — `PATCH /users/{id}` `:70` | `yes` — `user.manage` `:71`; `team.update`→`user.manage` `mutations.ts:33` | `yes` — `UserUpdateInput.roleKey` `users.ts:30-37`; replace-all `users.service.ts:223-232` | `yes` — `membership_roles` `schema.prisma:1436` |
| Change record scope | `yes` — select `page.tsx:260-266` | `yes` — same `PATCH` | `yes` — same | `yes` — `scope` enum `users.ts:41` | `yes` — `Membership.scope` `schema.prisma:1113` |
| Deactivate membership | `yes` — `active=false` option `page.tsx:270-275`, + confirm `page.tsx:235-243` | `yes` — `PATCH /users/{id}` | `yes` — same | `yes` — `users.service.ts:179-241`; revocation `:275-318` | `yes` — `Membership.active`, `RefreshSession.revokedAt`, `DevicePushToken.active`, `DeviceActivation.state` |
| Reactivate membership | `yes` — dedicated form `page.tsx:208-222` | `yes` — `PATCH` `{active:true}` `actions.ts:79-82` | `yes` — same | `yes` — reactivation-only invariant `users.service.ts:199-207` | `yes` — `Membership.active` |
| Deactivate via the dedicated operation | **`no`** — no surface affordance | `yes` — `POST /users/{id}/deactivate` `:82`; **probe: contract-only, confirmed unreached by any client** | `yes` — `user.manage` `:84` | `yes` — `users.service.ts:246-273`, audits `user.deactivate` `:265` | `yes` — same revocation |
| Read the assignable role list | `yes` — feeds both selects `page.tsx:59,106-118,251-258` | `yes` — `GET /users/roles` `:42` | `yes` — the **only** users route carrying `@RequireAdminPanel()` `:43` **and** `user.manage` `:44`; the panel session itself is enforced in `admin-panel-session.ts:17` | `yes` — `users.service.ts:69-75`, org-scoped | `yes` — `roles` `schema.prisma:1411` |

Disagreements read off the table:

- **A layer yes, surface no** (2 rows): `GET /users/{id}` and
  `POST /users/{id}/deactivate` are declared, authorized and implemented, and no
  surface or client reaches either. Findings F5, F6.
- **Two routes for one action**: deactivation has a dedicated operation
  (`POST /users/{id}/deactivate`, audits `user.deactivate`) and a general one
  (`PATCH /users/{id}`, audits `user.update`). The surface uses only the general
  one, so a panel deactivation is recorded under `user.update` with
  `redactedDiff: {changed:['active']}` while the dedicated audit action is never
  emitted. Finding F6.
- **An offer the system forbids**: the invite form's role select is populated
  from `GET /users/roles` and does not exclude `SUPER_ADMIN`, which the same
  codebase refuses at `actions.ts:61` and `users.service.ts:336-338`. In the
  seeded platform organization the *only* option is `SUPER_ADMIN`. Finding F1.
- **The end of the action**: an invite writes a `User` (status `ACTIVE`, a random
  password hash) and a `Membership`, emits `UserInvited` to the outbox, and stops
  — no credential reaches the invited person. Finding F2.
- **The layers agree** (pass rows P1, P2, P3, P4, P5 below).

## Matrix 2 — field contract (13 rows: 13 checked, 0 unchecked)

| Field | Column / type | Read by the API | Written by the API | Rendered (list / detail / form) | Validated | Label or enum source | Locale / format |
|---|---|---|---|---|---|---|---|
| `id` | `User.id` uuid, `schema.prisma:1054` | yes `users.service.ts:33` | generated | not rendered; carried in hidden inputs `page.tsx:216,246` | `z.uuid()` `actions.ts:77`, `ParseUUIDPipe` | — | — |
| `displayName` | `display_name` String `:1059` | yes `:34` | create only `:122` | list `page.tsx:184`; form `page.tsx:95-98` | `InviteUserInput` 1–120 `users.ts:13`; update deliberately forbidden `users.service.ts:327-334` | literal `Ad` | none |
| `email` | `email` + `normalized_email` unique `:1055-1056` | yes `:35` | create only `:121` | list `page.tsx:185`; form `page.tsx:99-102` | `z.email()` `users.ts:12`; normalised `users.service.ts:115` | literal `E-posta` | none |
| `status` | `UserStatus` INVITED/ACTIVE/SUSPENDED/ARCHIVED `schema.prisma:39-44` | yes `:36` | create sets `ACTIVE` `:127`; **no update path** | list badge `page.tsx:186-190` | **unvalidated** — `z.string()` `page.tsx:19`, and no shared enum exists in `packages/domain/src/enums.ts` | `userStatusLabels` `user-labels.ts:16-22` — disagrees with the enum both ways | none |
| `locale` | `locale` String default `tr-TR` `:1062` | yes `:37` | create writes nothing; update path exists in the schema `users.ts:29` but is forbidden `users.service.ts:327-334` | **not rendered anywhere** (in `Response` `page.tsx:20`, unused) | `max(10)` `users.ts:29` | — | — |
| `membership.scope` | `Membership.scope` String default `organization` `schema.prisma:1113` | yes `users.service.ts:41` | invite `:153`, update `:217-221` | list `page.tsx:196-198`; form `page.tsx:122-129,263-274` | `z.enum` `users.ts:23,38` | `scopeLabels` `user-labels.ts:10-15`, options from a third local copy `page.tsx:37` | none |
| `membership.active` | Boolean default true `schema.prisma:1114` | yes `:42` | invite `:146`, update `:204-207`, `setActive` `:263` | list `page.tsx:200`; form `page.tsx:270-275` | literal `'true'/'false'` `actions.ts:84` | `Aktif`/`Pasif` literals | none |
| `membership.roles` | join table `membership_roles` `schema.prisma:1436-1444` | yes, `{key,name}[]` `users.service.ts:43,92-98` | invite creates **one** `:152`, update deletes all and creates **one** `:223-227` | list joins with `, ` `page.tsx:192`; form is single-choice `page.tsx:250` | `roleKey` enum `users.ts:30-37` | row: `roleLabels` `user-labels.ts:1-9`; select: DB `Role.name` `users.service.ts:71` — **two sources** | none |
| `membership` absence | nullable relation | yes `users.service.ts:59-62` | — | list `page.tsx:196-198,200` | — | — | — |
| `Role.key` / `Role.name` | `roles.key/name` `schema.prisma:1414-1415` | yes `:70-73` (org-scoped) | seed only | select options `page.tsx:116-118` | `org_key` unique `:1423` | DB `name` + client map | none |
| `passwordHash` | `password_hash` `:1060` | never returned | random on invite `users.service.ts:116,323-325` | never | — | — | — |
| `themePreference` | `theme_preference` default `SYSTEM` `:1063` | via `/me` `admin-context.ts:16` | self-service profile only | shell attribute `apps/admin/app/(dashboard)/layout.tsx:19` | `ThemePreference` `admin-context.ts:16` | — | — |
| `User.email` vs `normalizedEmail` | two columns, one identity | both | both | only `email` shown | normalised with `toLocaleLowerCase('tr-TR')` `users.service.ts:115` | — | list search lowers with `tr-TR` `page.tsx:60` |

Gaps: `locale` read and never rendered (F8); one row printing `Aktif` from two
different fields (F9); a null membership rendering contradictory cells (F10); the
role label read from two sources (F11); a status label map that disagrees with
the DB enum in both directions with no shared enum at all (F12); a scope enum
from three sources with a default mismatch (F13).

## Matrix 3 — flow and step contract (6 rows: 6 checked, 0 unchecked)

| Step | Precondition | What it validates | What it writes | How a skip is prevented | Resume / persistence | Back-navigation retention | Where an error lands |
|---|---|---|---|---|---|---|---|
| Invite 1 — form (`page.tsx:80-135`) | `canInvite` (`user.manage`) — server-enforced at render `page.tsx:46,74` **and** at submit `actions.ts:53` + API `users.controller.ts:60` | native constraints on submit only (`AdminActionForm.tsx:120-138`); nothing else | nothing | — | none; closing the dialog keeps the values in the DOM (observed) | the dialog is never reset, so reopening keeps values and the previous error (F19) | in-place, modal `role="alert"` `AdminActionForm.tsx:273-281` |
| Invite 2 — confirm (`AdminActionForm.tsx:305-330`, `ConfirmationDialog.tsx:51-104`) | step 1 values only | none | nothing | the confirmation is **client-only** (`onSubmit` `AdminActionForm.tsx:224-258`); a direct submit of the Server Action skips it | none | the summary is rebuilt from the DOM at submit time `AdminActionForm.tsx:231-257` | the confirm dialog has no error surface; errors land back in step 1 |
| Invite 3 — submit + redirect (`actions.ts:53-71`) | step 2 confirm | re-parses with `InviteUserInput` `actions.ts:55`; refuses `SUPER_ADMIN` `:61` | user + membership + audit + outbox | — | none | `?result=user-invited` survives reload and Back (F18) | `?result=`/`?error=` into `MutationNotice` `page.tsx:73` |
| Edit 1 — form (`page.tsx:224-279`) | `canUpdate`; the row is not the actor's own (the `Pasif` option is withheld `page.tsx:272-273`) | native constraints; `z.uuid()` on the id `actions.ts:77` | nothing | — | none | same as above | in-place, modal |
| Edit 2 — confirm (`page.tsx:235-243`) | step 1 values | none | nothing | client-only | none | — | — |
| Reactivate (single step, `page.tsx:208-222`) | `canUpdate`; `membership.active === false` — the branch that renders it `page.tsx:207-222` | nothing client-side; service enforces reactivation-only `users.service.ts:199-207` | `active:true` + audit | — | none | — | in-place |

Precondition enforcement, side by side: `canInvite`/`canUpdate` and the id format
are enforced in the server action *and* the API; the confirmation step exists only
in the client (that is inherent to a confirm dialog, and it is stated here because
the matrix asks which side enforces it); the reactivation-only state machine is
enforced in the service, which is why the surface can render two different forms
for the same endpoint without the API accepting the wrong one.

## Matrix 4 — interaction dependency (8 rows: 8 checked, 0 unchecked)

| Trigger | Dependents | Required action on change | Who owns the state | What is announced |
|---|---|---|---|---|
| `q` search (`page.tsx:146-148`) | the row set, the count paragraph `:164` | recompute (submit) | URL `searchParams` | new page load (GET form) — nothing in a live region |
| `state` filter (`page.tsx:150-155`) | the row set, the count | recompute | URL | new page load |
| `Filtreleri temizle` (`page.tsx:159-161`) | the row set, the count, **and the controls themselves** | reset controls + recompute | React render of the same route | **nothing** — and the reset does not happen: F7 |
| Invite `roleKey` select (`page.tsx:106-118`) | the request the server will accept | none offered | server-rendered `defaultValue` | — |
| Edit `roleKey` select (`page.tsx:249-256`) | the roles the row will hold | recompute server-side (`deleteMany` + `create`) | server | — |
| Edit `active` select (`page.tsx:270-275`) | the `roleKey`/`scope` fields: choosing `Pasif` makes them inapplicable | the service refuses a non-reactivation update on an inactive membership, but the form still offers it — **no cascade** | service | — |
| Actor identity (`context.id`) vs the row (`page.tsx:272-273`) | the `Pasif` option | keep | server render | — |
| Panel session expiry (`api.ts:119`) | every read and write | redirect to recovery | server | new page |

No cascade where the contract requires one (row 6): the edit dialog offers
`Pasif` alongside a role and a scope change; the service then returns
`INACTIVE_MEMBERSHIP_REACTIVATION_ONLY` (`users.service.ts:199-207`) for any
inactive membership that is not being reactivated — but that state is unreachable
through the UI, because the row renders the reactivation form first
(`page.tsx:207-222`). So this is a latent, not observable, divergence.

## Matrix 5 — surface pattern (45 rows: 43 checked, 2 marked `[NOT CHECKED]`)

Sources: `APG x` = WAI-ARIA Authoring Practices pattern, `SC n.n.n` = WCAG 2.2
success criterion, both read at source 2026-09-20 (links in the artifact's
Sources). axe-core 4.10.3 run on the closed and open states.

### Data views (15 rows)

| Rule | Result |
|---|---|
| SC 1.3.1 real headers + labelled table | **pass** — `th scope="col"` ×7 and `caption` `page.tsx:169,174-179` (read from the DOM) |
| `aria-sort` on the sorted column | **finding F20** — server-sorted by `displayName` `users.service.ts:47`, no `aria-sort`, no sort affordance |
| Cells with widgets make it a grid | **finding (F23, low)** — the last cell holds a form/dialog trigger per row `page.tsx:201-278` inside a plain `<table>`; 1 control per row in the current data |
| `aria-rowcount`/`aria-colcount`, position restored | **n/a** — no virtualization, no pager, no detail view to return from |
| SC 1.4.10 reflow at 320 CSS px | **pass** — measured `documentElement.scrollWidth = 320 = innerWidth`; table 1140 px inside a 242 px region with `overflow-x:auto` `page.tsx:167` |
| Pager marks the current page, one-page pager hidden | **n/a** — there is no pager at all (F4) |
| Captions/headings describe the data, first column human-readable | **pass** — `Ad` holds `displayName` `page.tsx:184` |
| Filters discoverable, active state visible in the results | **finding F7** — the control keeps a state the view no longer has |
| Detail view as key/value, no field silently omitted | **n/a** — no detail view (F5) |
| Scroll region says it scrolls | **finding F17 (low)** — at 1440 the table (1140 px) exceeds its region (1084 px) and the last column is cut mid-word with no visible affordance; the region is `role="region"`, labelled and `tabindex=0`, so it is reachable |
| Long text has a strategy | **finding F17** — the same clipping; no truncation-with-reveal, no wrap strategy |
| State coverage: default | **pass** — read at 1440 and 320, light and dark |
| State coverage: empty | **pass** — `state=inactive` renders `.empty` with `Eşleşen kullanıcı yok…` `page.tsx:287-290` (observed) |
| State coverage: loading, error | `[NOT CHECKED: the render awaits on the server (`page.tsx:58-59`) and the e2e fault proxy that drives these states is not running; starting it is outside this brief — the states exist and are asserted in `admin-state-recovery.e2e.ts:8`]` |
| State coverage: permission-denied | `[NOT CHECKED: the two locked surfaces `page.tsx:48-56,138-142` need a panel credential without `user.manage`; creating one writes to the shared database, which this brief forbids]` |
| State coverage: skeleton, offline, partial | **n/a** — this surface has no client-side fetch; every read is a server render |

### Controls (14 rows)

| Rule | Result |
|---|---|
| `APG combobox` roles/attributes | **n/a** — both pickers are native `<select>` |
| `APG combobox` keyboard | **n/a** |
| `APG listbox` | **n/a** — native selects |
| A row of controls is a grid, not a listbox | **pass** — the rows are `<tr>`, not options |
| Visible persistent label (never a placeholder) | **pass** — every control is wrapped in `<label className="field">` with a `<span>` `page.tsx:95-135,145-155`; no `placeholder` attribute anywhere on the page |
| SC 1.3.5 `autocomplete` scoped correctly | **pass** — no `autocomplete` on the invite fields (another person's data) or on the search field, which is the required behaviour for both |
| One required/optional convention | **finding F24 (low)** — `required` on `displayName`/`email` `page.tsx:97,101` with no visible marker and no explanation; the edit form's fields carry no `required` |
| `APG disclosure` | **n/a** — no show/hide disclosure on this surface |
| `APG tabs` | **n/a** |
| Conditional reveal reveals a question and announces it | **n/a** — the only conditional rendering is the permission-gated invite block `page.tsx:74`, which is a whole region, not a revealed question |
| Pickers: text entry + known list where needed | **pass** — role/scope are closed enumerations, native selects are correct; no date or country picker here |
| SC 2.5.8 target size | **pass** — measured: no interactive target under 24×24; the smallest is the modal close button at 36×36 |
| SC 2.4.7 / SC 1.4.11 focus visible | **pass** — measured `outline: 3px solid rgb(20,95,192)` on every control tabbed through |
| SC 1.4.3 contrast, no colour-only state | **pass** — hand-measured because axe returned `incomplete` on 19 nodes (gradient sidebar) and 1 (modal backdrop): light `td` 16.63:1, `th` 5.83:1, `p.muted` 5.47:1, badge 14.5:1, sidebar group label 8.73:1; dark 7.6–14.29:1; the status badge carries text, not colour alone |

### Validation and errors (4 rows)

| Rule | Result |
|---|---|
| On submit not on blur; failing values kept; server validation present; native validation suppressed | **partial** — on-submit collection `AdminActionForm.tsx:120-138`, values kept (observed: the typed name survives the refusal), server validation present (`ZodValidationPipe` + service invariants); **no `novalidate`**, a documented deviation (`AdminActionForm.tsx:42-44` relies on the browser's `invalid` event) — F21 |
| SC 3.3.1/3.3.3 item identified + correction described | **pass (with F1 as the exception)** — `fieldHelp` `actions.ts:11-17` and `nativeFieldMessage` `AdminActionForm.tsx:45-62`; `aria-describedby` wired, `aria-invalid=true` set (measured) |
| Association: `aria-describedby`, same wording in summary and beside the field, summary entry moves focus | **pass** — observed ids `_R_…-error-0/1`, the summary items are buttons that focus the field `AdminActionForm.tsx:284-296` |
| Error summary at the top of the form | **finding F15 (low)** — measured: the summary renders at y=577 while the form starts at y=351, i.e. below the fields |

### Flows (8 rows)

| Rule | Result |
|---|---|
| One question per page, unique heading, back link, Continue | **pass** — the modal is one job with its own `h2` `AdminModal.tsx:148`, `aria-labelledby`, and a `✕` labelled `Pencereyi kapat` |
| Check-your-answers: pre-populated, named Change links, a submit that names its action | **pass** — the confirm dialog shows a `dl` of the four values `AdminActionForm.tsx:323-330` and the button names the action (`Daveti oluştur` / `Erişimi güncelle`) |
| Task list | **n/a** |
| SC 3.3.7 redundant entry | **pass** — no value is asked twice; the id travels hidden `page.tsx:216,246` |
| SC 3.3.4 reversible / checked / confirmed | **pass** — deactivation is confirmed, names the effect (`page.tsx:235-243`) and is reversible through the reactivation form |
| Destructive confirmation names what is lost, keeps actions inside the panel, reserved for the irreversible | **partial** — it names the object and the effect (`page.tsx:237`), and its actions are inside the dialog; but the same confirm pattern is used for the non-destructive invite (`page.tsx:83-94`), so it is not reserved — **F25 (low)** |
| `APG dialog` / `alertdialog` | **pass** — native `<dialog>` + `showModal()` `AdminModal.tsx:56`, `aria-haspopup="dialog"` `:101`, focus trapped (measured: close → displayName → email → roleKey → scope → submit → close), Escape closes, focus **returns to the trigger** (measured after a real mouse click), and the confirm dialog focuses `Vazgeç` first `ConfirmationDialog.tsx:31` |
| Initial focus target | **finding F16 (low)** — focus lands on `✕`, the dismiss control, not the first field |

### Notifications (4 rows)

| Rule | Result |
|---|---|
| SC 4.1.3 changes without a focus move are programmatically determinable | **partial** — filter/search are full GET navigations (a new page, so not a live-region case); the pending state is `role="status"` `AdminActionForm.tsx:269-270`; the failure is `role="alert"` `:278`. The invite's success message is rendered on a fresh load from `?result=` and persists there (F18) |
| The whole status string is announced, and the end of a wait | **pass** — `MutationNotice` `role="status"` carries a whole sentence `MutationNotice.tsx:133-135`; the pending label is a whole sentence |
| Non-status changes stay out of live regions | **pass** — field errors inside the focused dialog are `role="alert"` inside the form, not a page-level live region |
| A notification banner is a labelled region, before the `h1`, at most one | **pass** — the notice is a single `p`/`div` above the list and below the `h1` `page.tsx:73`; no banner pattern is used here |

`[NOT CHECKED]` rows (2, both in Data views, with their reason in the cell): the
loading/error states and the permission-denied state. Both are stated rather than
omitted, so they are not read as checked. The conditional-reveal row and the
SC 1.3.5 row are `n/a`/pass on their merits, not unchecked: this surface has no
disclosure that reveals a question, and it collects another person's data rather
than the user's own, so a missing `autocomplete` token is the required behaviour.

---

## Findings (most severe first)

Each names one evidence class. `ui-observed` = read from the running app in this
session (tool call and the state read are named); `code` = a cited `path:line`.

**F1 — The invite form offers only a role the same codebase refuses.**
Class: `ui-observed` (opened the modal, read `select[name=roleKey]` → one option,
value `SUPER_ADMIN`, selected; the code citations below are the corroboration). Standard: skill Matrix 1, "an offer the
system forbids". The select is populated from `GET /users/roles`
(`page.tsx:59,106-118`), which returns every role of the organization
(`users.service.ts:69-75`); `inviteUserAction` returns
`'Platform sahibi bu ekrandan atanamaz.'` for `SUPER_ADMIN` (`actions.ts:61`) and
the service throws `SUPER_ADMIN_PROVISIONING_REQUIRED`
(`users.service.ts:336-338`); the mobile client excludes the same key
(`organization-users-api.ts:36`, `OrganizationUserRole = Exclude<Role,'SUPER_ADMIN'>`)
while the admin surface does not. Exercised: filled the form and confirmed —
`role="alert"` "Platform sahibi bu ekrandan atanamaz.", no field marked, the
offending value still selected. In a single-role organization the surface's only
write action is unusable. Severity 4.
**Prevent**: an e2e assertion that every option rendered by the invite role select
is accepted by `POST /users/invite` with the panel's own token (option set ⊆
server-acceptable set); plus the mobile client's filter, applied to the same list.

**F2 — An invited person receives no way to sign in.**
Class: `code`. `users.service.ts:114-127` creates the `User` with
`passwordHash = hashPassword(randomInvitePassword())` (`:116`, `:323-325`) and
`status: 'ACTIVE'`; the only output is `outbox.emit(… eventType: 'UserInvited')`
(`:168-174`). That event maps to an in-app notification for the invited user
(`notification-event-mapper.ts:684-690`, `accountResult` requires
`payload.userId === recipient.userId`) and a push addressed to
`event.aggregateId` — the invitee's own device (`push-notification.handler.ts:135`),
which a person who has never signed in does not have. No email provider is called;
the only one in the tree is wired to password reset
(`apps/api/src/auth/password-reset-email.provider.ts`). Severity 4 for a new
invitee (the record succeeds and the person cannot act on it).
**Prevent**: a contract test asserting every `UserInvited` emit has a delivery
path for a user with zero device tokens; and an assertion that an invite-created
`User` cannot reach `ACTIVE` without a consumed credential hand-off.

**F3 — The role write path can hold exactly one role while the read path,
the model and the other client all hold many.**
Class: `code`. Write: `users.service.ts:223-232` deletes every
`membership_roles` row and creates one; the contract is a single
`roleKey` (`users.ts:30-37`); the surface is a single-choice `<select
name="roleKey">` (`page.tsx:249-256`). Read: a joined list (`page.tsx:192`), a
`{key,name}[]` response (`users.service.ts:104-107`), a join table with
`@@id([membershipId, roleId])` (`schema.prisma:1436-1444`), and a mobile client
typed as an array (`organization-users-api.ts:19-32`). The delete-then-create also
makes the write lossy: any set the read path can show collapses to one on the next
save. Severity 3. Proposal P1.
**Prevent**: a contract test that round-trips what the read path can return —
persist two roles, read them back, assert both survive an update that does not
name roles.

**F4 — The list renders every membership and the envelope hardcodes a single
page.**
Class: `code`. `users.service.ts:26-47` takes no cursor or limit;
`:64` returns `page: { nextCursor: null, hasNextPage: false }` unconditionally;
`users.controller.ts:34-40` declares no query parameters; the surface parses only
`data` (`page.tsx:58`) and then filters it in memory (`:60-66`). Sibling
convention: `apps/api/src/common/cursor.service.ts` is used by 13 services
(customers, teams, agenda, finance, technical, community, directory,
field-learning, marketplace, …) — measured by a repo-wide search for
`CursorService`; `users.service.ts` is the deviation. Not observable in this
instance: the seeded platform organization has exactly one user, so the cost is
latent (the e2e probe at `admin-state-recovery.e2e.ts:8` treats `/users` as a
single-page read). Severity 3 at scale, 0 in the fixture. Proposal P2.
**Prevent**: a list-contract test asserting that every index route either declares
a cursor or asserts its bound, and an e2e fixture with more members than one page.

**F5 — `GET /users/{id}` is declared, authorized, implemented, and unreached.**
Class: `code` (+ the arm-B probe, which is the route-column evidence). The route
exists at `users.controller.ts:49`; no admin call site (probe: `contract-only`),
no mobile call site (my search over `apps/mobile/src`), and the repo's own
consumer map lists three consumers for `users` and not this one
(`mobile-consumers.md:530-536`). There is no detail view to consume it: the
surface's only per-row affordance is the edit dialog (`page.tsx:224-279`), and the
route table has no `/users/[id]`. One of the two must go. Severity 2.
**Prevent**: a contract test that fails on a declared endpoint with no reachable
consumer, keyed on the consumer map already in the repo
(`docs/design/admin-owner-v3-2026-09-19/evidence/mobile-consumers.md`).

**F6 — Deactivation has two routes; the surface uses the one whose audit action
is generic, and the dedicated audit action is never emitted.**
Class: `code`. `POST /users/{id}/deactivate` (`users.controller.ts:82-89`) audits
`user.deactivate` (`users.service.ts:265-272`); it is unreached (probe +
search). The panel deactivates through `PATCH /users/{id}`
(`actions.ts:79-91`), which audits `user.update` with
`redactedDiff: { changed: ['active'] }` (`users.service.ts:234-240`). Both call
`revokeMembershipAccess` (`:275-318`). Severity 2. No proposal: both fixes (wire
the surface to the dedicated route, or delete it) name layers that already exist.
**Prevent**: an assertion that the audit action names the effect — one
`user.deactivate` per deactivation, whichever route carries it.

**F7 — The membership-state filter keeps a state the view no longer has.**
Class: `ui-observed`. Applied `state=inactive` → URL
`/users?q=&state=inactive`, 0 rows, empty-state visible; clicked
`Filtreleri temizle` → URL `/users`, 1 row, empty-state gone, **and
`select[name=state]` still reads `inactive` ("Pasif")**, visible in the 320 px
screenshot. The control is `defaultValue={input.state ?? ''}` (`page.tsx:150-155`)
and the reset is a client-side `<Link href="/users">` (`page.tsx:159-161`), so the
uncontrolled select keeps its DOM value across the same-route navigation. This is
the skill's named case, reproduced. Severity 2.
**Prevent**: a component-state assertion that every filter control's value equals
its URL parameter after the clear link is activated (`page.test.tsx:57-58` asserts
the server-rendered value only, which is why it passes today).

**F8 — `locale` travels the whole contract and no view renders it.**
Class: `code`. Read by the API (`users.service.ts:37`), modelled
in the surface's schema (`page.tsx:20`), never rendered — confirmed by reading the
rendered table's cells. The caption says locale is changed "in the user's own
profile" (`page.tsx:164-165`) with no link to it. Severity 2.
**Prevent**: a field-contract test over the API response asserting every field the
response carries is either rendered or explicitly listed as hidden-with-reason.

**F9 — One row prints the same word from two different fields.**
Class: `ui-observed`. `Durum` renders `User.status` (`page.tsx:186-190`) and
`Üyelik` renders `membership.active` (`:200`); both print `Aktif` for the seeded
row. Two different states, one word, no legend. Severity 2.
**Prevent**: a rendering test that no two cells of one row resolve to the same
label from different fields without a distinguishing group header.

**F10 — A null membership renders contradictory cells.**
Class: `code`. With `membership === null`, `Kapsam` prints `Üyelik yok`
(`page.tsx:196-198`) and `Üyelik` prints `Pasif` (`:200`), because
`user.membership?.active` is `undefined` → falsy. Severity 2.
**Prevent**: a rendering test with a membership-less row asserting `Üyelik` is not
`Pasif` when `Kapsam` is `Üyelik yok`.

**F11 — One role, two labels.**
Class: `code`. The row labels a role from the hardcoded map
(`page.tsx:192`, `user-labels.ts:1-9`); the selects label the same role from the
DB `Role.name` (`page.tsx:116-118,253-256`, `users.service.ts:71`). The repo's own
fixture shows the drift: `page.test.tsx:25` uses `İşletme Yöneticisi` while the map
has `İşletme yöneticisi`. Severity 2.
**Prevent**: one label source — resolve `Role.key → label` once and feed both the
row and the select; assert it with a test that the same key renders identically in
both places.

**F12 — The status label map disagrees with the status enum in both directions,
and no shared enum exists.**
Class: `code`. `UserStatus` is `INVITED|ACTIVE|SUSPENDED|ARCHIVED`
(`schema.prisma:39-44`); `userStatusLabels` has `DEACTIVATED` and `DELETED`
(absent from the enum) and lacks `ARCHIVED` (`user-labels.ts:16-22`), which is the
value the list filters out (`users.service.ts:30`) and would therefore print raw.
`status` is typed `z.string()` on both clients (`page.tsx:19`,
`organization-users-api.ts:13`) and `packages/domain/src/enums.ts` has no
`UserStatus`. `INVITED` is written nowhere (repo-wide search), so its label is
dead. Severity 2.
**Prevent**: a shared `UserStatus` enum in `packages/domain` plus a test asserting
the label map's key set equals the enum's.

**F13 — The scope enumeration has three sources and the invite default differs
from the contract's.**
Class: `code`. `ResourceScope` in
`packages/domain/src/permissions.ts` (exact line: the `export type ResourceScope`
declaration), `scopeOptions` re-declared locally at `page.tsx:37`, and
`Membership.scope` as a free `String` with a DB default (`schema.prisma:1113`).
The invite form defaults to `assigned` (`page.tsx:122`) while `InviteUserInput`
defaults to `organization` (`users.ts:23`) and `Membership` defaults to
`organization` (`schema.prisma:1113`) — so the same request means different things
depending on who builds it. Severity 1.
**Prevent**: derive the option list from the domain enum; a contract test
asserting the form's default equals the schema default.

**F14 — The unsaved-data guard stays armed after the dialog is closed.**
Class: `ui-observed`. Typed into the invite form, closed the dialog, then
navigated: the browser raised a `beforeunload` prompt (the harness refused the
navigation with "a beforeunload("") dialog opened"), although the modal and its
pending work were gone. The guard is armed on any `onChange`
(`AdminActionForm.tsx:217-220,143-147`) and cleared only on success (`:194`);
`AdminModal`'s close path (`AdminModal.tsx:114-127`) does not reset the form.
Severity 2.
**Prevent**: an interaction test asserting no `beforeunload` listener is live once
the dialog is closed or cancelled.

**F15 — The error summary renders below the fields.**
Class: `ui-observed`. Measured after an empty submit: the summary is at y=577, the
form starts at y=351, and focus is moved to the summary — so the user is taken
past the fields they must fix before being offered the links back
(`AdminActionForm.tsx:273-300`). Severity 1.
**Prevent**: a DOM-order assertion that the error summary precedes the first form
control.

**F16 — The dialog's initial focus is the dismiss control.**
Class: `ui-observed`. Opening the invite modal puts focus on `✕`
(`AdminModal.tsx:155-160`), so the first thing a keyboard user must traverse is
the way out. Severity 1.
**Prevent**: a component-state assertion on `document.activeElement` after open,
or an `autofocus` on the first field.

**F17 — The last column is cut mid-word at 1440 with no visible affordance.**
Class: `ui-observed`. Measured at 1440×1000: `.tableWrap` client 1084 px, table
1140 px, `overflow-x: auto` (`page.tsx:167`); the rendered screen shows the last
column's sentence cut at the card edge ("…bu ekrandan değiştir"), in light and in
dark. The region is labelled and focusable, so the content is reachable; the
affordance is a platform-hidden overlay scrollbar. Severity 1.
**Prevent**: a document-level overflow assertion is the wrong check (it passes
here); assert instead that each table cell's `scrollWidth <= clientWidth` or that
the region shows a visible scroll affordance.

**F18 — A past result message survives reload and Back.**
Class: `code`. Success is delivered by redirecting to
`/users?result=user-invited` (`actions.ts:71`) and rendered by
`MutationNotice` from `searchParams.result` (`page.tsx:73`), so the confirmation
is still on screen after a reload or a Back into the URL. Severity 1.
**Prevent**: clear the parameter after first render (history replace) and assert
it in an e2e.

**F19 — Reopening the dialog after a failure shows the previous error.**
Class: `ui-observed`. After a refused invite, closing and reopening the modal
still shows `Platform sahibi bu ekrandan atanamaz.` and the previous values — the
`<dialog>` element is reused (`AdminModal.tsx:56`) and `AdminActionForm`'s
`result` state is never reset on close. Severity 1.
**Prevent**: an interaction test asserting the feedback region is empty on
reopen.

**F20 — The list is server-sorted with no `aria-sort` and no way to change it.**
Class: `code`. `orderBy: { displayName: 'asc' }`
(`users.service.ts:47`); the headers are plain `th scope="col"` with no
`aria-sort` (`page.tsx:174-179`, read from the DOM). Severity 1.
**Prevent**: if the column is presented as sorted, assert `aria-sort`; if it is
not, drop the server ordering or expose it.

**F21 — Native validation is not suppressed.**
Class: `code`. The rule asks for `novalidate` so the surface owns the messages;
`AdminActionForm.tsx:42-44` documents the opposite choice — it relies on the
browser's `invalid` event to build the summary. The chosen wording is generic
(`nativeFieldMessage:48-62` → "Bu alanı doldurun.") rather than the field-specific
`fieldHelp` (`actions.ts:11-17`). Severity 1.
**Prevent**: if the deviation is intentional, assert the summary's wording source;
otherwise add `noValidate` and route everything through `fieldHelp`.

**F22 — The confirmation is client-enforced only.**
Class: `code`. `AdminActionForm.tsx:224-258` prevents the submit and opens the
dialog; a direct POST to the Server Action reaches `inviteUserAction` with no
confirmation. This is inherent to a confirm dialog (the service cannot know), and
the *permission* precondition is enforced server-side at both layers
(`actions.ts:53`, `users.controller.ts:60`), so this is recorded as a fact, not a
defect. Severity 0.
**Prevent**: none available beyond the audit trail (`user.invite`
`users.service.ts:160-167`), which is the compensating control.

**F23 — Per-row controls inside a plain table.**
Class: `code`. Each row's last cell holds a form or dialog trigger
(`page.tsx:201-278`) in a `<table>` that is not a grid; with many rows every one
becomes a tab stop. Not reachable at scale in this instance. Severity 1.
**Prevent**: if the row control count grows, move the table to a grid pattern with
a single tab stop.

**F24 — Requiredness is invisible to a sighted user.**
Class: `code`. `required` on `displayName` and `email`
(`page.tsx:97,101`) with no asterisk, no "(zorunlu)", and no legend; the rendered
modal shows bare labels. Severity 1.
**Prevent**: one required/optional convention applied by the shared field
component and asserted in a rendering test.

**F25 — The confirm pattern is applied to a non-destructive action.**
Class: `ui-observed`. The invite — a create, reversible only by deactivation — uses
the same confirmation furniture as deactivation (`page.tsx:83-94` vs
`:243-247`). Severity 1.
**Prevent**: reserve the pattern by policy: assert the set of actions using
`confirmation` equals the set of destructive actions.

### Pass rows (agreement between layers)

- **P1** `user.manage` is the surface's gate, the mutation registry's mapping and
  the route's requirement (`page.tsx:46-47`, `mutations.ts:29,33`,
  `users.controller.ts:35,44,50,60,71,84`).
- **P2** Every write is validated server-side: `ZodValidationPipe` on the body
  (`users.controller.ts:64,76`), the domain schemas (`users.ts:11-44`) and service
  invariants (`users.service.ts:180-207,327-341`).
- **P3** Self-deactivation is refused at two layers (the option withheld,
  `page.tsx:272-273`; the service, `users.service.ts:181-186,247-251`).
- **P4** The platform owner is protected at three layers (`page.tsx:205-206`,
  `actions.ts:61,87`, `users.service.ts:336-341`).
- **P5** Every write is audited (`users.service.ts:160,234,265`) and the invite
  emits an outbox event (`:168`).
- **P6** Dialog semantics: `aria-haspopup="dialog"`, labelled + described native
  `<dialog>`, trapped focus, Escape, focus return to the trigger, least-destructive
  initial focus in the confirmation (all measured in pass 3).
- **P7** Contrast, target size and focus visibility pass in light and dark
  (measured; see Matrix 5).
- **P8** Table semantics pass: real `th scope="col"`, a `caption`, a labelled
  focusable scroll region.
- **P9** SC 1.4.10 passes at 320: no document-level overflow, table contained.
- **P10** axe-core 4.10.3: **0 violations** in the closed state (18 rules passing)
  and **0** with the modal open (25 passing); the two `incomplete` results were
  hand-checked and pass.

---

## Capability-change proposals

Two findings name a layer the product does not have. Each proposal carries an
artifact something other than its author can reject.

### P1 — a membership can hold a role set (from F3)

| Heading | Content | Falsified by |
|---|---|---|
| Capability | A membership's authorization is a set of roles, and one operation writes the whole set. | a cited code path that already writes more than one role per membership |
| Absence proof | `apps/api/src/users/users.service.ts:223-232` deletes all `membership_roles` and creates exactly one; `packages/domain/src/users.ts:30-37` accepts a single `roleKey`. Input that fails: `{"roleKeys":["DISPATCHER","ACCOUNTANT"]}` → the contract cannot express it. | a cited path that persists two roles from one request |
| Contract delta | `UserUpdateInput.roleKey → roleKeys: Role[]` and the same on `InviteUserInput`; regenerate `packages/api-client/src/generated/schema.ts` and `docs/openapi.json`. Compatibility checker: `packages/domain/src/api-contracts.test.ts` plus the client's type check. | the checker green with no diff |
| Migration | expand (accept both `roleKey` and `roleKeys` for one release) → migrate (the panel sends `roleKeys`) → contract (drop `roleKey` at release+1, dated in the ADR). No schema migration: `membership_roles` already carries the set. | a contract phase with no date |
| Rollout | flag `users-role-set`, boolean, lifetime 90 days, initial exposure 0%, owner: the `/users` surface owner; abort if `PATCH /users/{id}` 4xx > 2% over 7 days. | a flag with no lifetime, or an unmeasurable threshold |
| Verification | a test that PATCHes two roles and asserts both come back from `GET /users` and render in the row; it fails on the pre-change commit. | a check that also passes pre-change |
| Reversibility | writes `membership_roles` rows; restore = re-issue the single-role PATCH. | data written with no restore step |
| Decision | ADR "membership role sets" (context: F3; status: Proposed; consequences: the surface needs a multi-select, the audit diff must name the set). | an ADR without a status |
| Appetite | one week; out of bounds: role hierarchy, permission resolution, per-role scope. | no box |

### P2 — the membership list is readable one page at a time (from F4)

| Heading | Content | Falsified by |
|---|---|---|
| Capability | The caller reads the organization's memberships one bounded page at a time, with a stable cursor. | a cited path that pages `GET /users` |
| Absence proof | `apps/api/src/users/users.controller.ts:34-40` declares no query parameters; `users.service.ts:26-47` has no cursor/limit; `:64` returns `hasNextPage: false` unconditionally. Input that fails: `GET /users?cursor=…&limit=50`. | a cited path that honours those parameters |
| Contract delta | `GET /users?cursor&limit` + `page.hasMore`; regenerate `docs/openapi.json` and the generated client. Checker: `apps/api/src/domain/api-contracts.test.ts`-style contract test plus the regenerated schema. | the checker green with no diff |
| Migration | none (read-only). The admin surface reads `page.hasNextPage` and adds a pager, or keeps a full read behind the flag. | a contract phase with no date |
| Rollout | flag `users-list-pagination`, boolean, 60 days, initial exposure: the panel only; owner: the `/users` surface owner; abort if the pager's `hasNextPage` disagrees with the row count in any request. | an unmeasurable threshold |
| Verification | a test that seeds 51 members and asserts page 1 returns 50 with `hasNextPage: true`; fails pre-change. | a check that also passes pre-change |
| Reversibility | one-way for the response shape only after the contract phase; before it, dropping the query parameters restores today's behaviour. | a restore step that does not exist |
| Decision | ADR "users list pagination" (status: Proposed; supersedes: the implicit single-page envelope). | an ADR without a status |
| Appetite | three days; out of bounds: filtering and search move server-side in the same change (they stay in memory until a separate proposal). | no box |

No proposal is emitted for F2 (the invite delivery): its fix names layers that
already exist — `PasswordResetChallenge` and
`apps/api/src/auth/password-reset-email.provider.ts` — so it is a finding with a
fix, not a capability change. If the chosen fix is a new re-issue endpoint
(`POST /users/{id}/invitation`), that endpoint is a contract delta with the same
proposal shape as P2.

Reviewer's five absences, self-checked: every capability above has a `code`
finding behind it (F3, F4); both proposals carry a rejectable artifact (a domain
schema diff with a contract-test checker; a flag with a type, owner and lifetime);
no schema-touching step lacks migration phases (P1 needs none and says so; P2 has
none and says so); no flag lacks a lifetime or owner; P1's contract change carries
an ADR and a pre/post check pair.

---

## Coverage

| Matrix | Rows | Checked | Not checked |
|---|---|---|---|
| 1 — capability | 11 | 11 | 0 |
| 2 — field contract | 13 | 13 | 0 |
| 3 — flow and step | 6 | 6 | 0 |
| 4 — interaction dependency | 8 | 8 | 0 |
| 5 — surface pattern | 45 | 43 | 2 |

States exercised on the running page: default (1 row); filter applied (`q`,
`state`) and cleared; empty result (`state=inactive` → "Eşleşen kullanıcı yok");
invite modal closed/open; the two-step confirm; refusal of the only offered role;
empty submit (native invalid → summary, `aria-invalid`, `aria-describedby`); the
dev-overlay-free focus reads; 1440 and 320 CSS px; light and dark.

States **not** exercised, and why: the two permission-locked surfaces (no
non-privileged panel credential exists in this instance, and creating one writes
to the database — the assignment forbids that); a row whose membership is `null`;
an inactive membership row (so the reactivation form and the edit form's `Pasif`
option were read from the code, not the screen); more than one role on a
membership; more than one page of members; the error and loading boundaries; a
production build (this is a dev server, whose overlay interfered with one focus
read until it was removed); 200 % zoom and text-spacing overrides; any screen
reader (the tree, axe and the live-region wiring were read, but no AT was run).

What would change the conclusion:

- the two `[NOT CHECKED]` rows, if a non-privileged credential and the e2e fault
  proxy are provided;
- a data set with an inactive member, a memberless user and a multi-role member —
  F10, F3's write loss and the reactivation flow become `ui-observed` instead of
  `code`;
- more members than one page — F4 moves from latent to observable;
- a production build — the dev overlay is the only thing that ever put focus
  outside the dialog, so P6's focus-return result would be re-read there.

Limits of the arm-B probe on this feature: it compares only the admin call sites
against the contract, so it cannot see the mobile consumer; the two rows it
reported were confirmed unreached only by the additional search named in F5/F6.
Its output is recorded above verbatim and used as the capability matrix's route
evidence; the route column also carries the controller read, because the probe
cannot see the per-endpoint guard.
