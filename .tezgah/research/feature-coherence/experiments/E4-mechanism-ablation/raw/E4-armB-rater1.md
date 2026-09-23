# feature-audit — Ustam admin, users area (`(dashboard)/users`)

Rater context: E4 arm B, rater 1. Artifact applied: `skills/feature-audit/SKILL.md` (frozen
text), plus the one extra instruction: run the E4 probe verbatim and record its output as the
capability matrix's evidence for the `route` column. Blind: no E2/E3 rater output, no
`feature-coherence` corpus file, and nothing under `.tezgah/research/` was read except
`experiments/E4-mechanism-ablation/protocol.md`, which the brief names.

## 1. The unit (boundary written down)

- **Entity**: the organisation member — a `User` plus its `Membership` in the caller's
  organisation (`apps/api/prisma/schema.prisma`, `UserStatus` at :39-44).
- **Actions**: list, search/filter, view one member's detail, invite, update access
  (role / scope / active), deactivate, reactivate, assign the platform role, and the invite's
  delivery to the recipient.
- **Screens**: one route, `/users` —
  `apps/admin/app/(dashboard)/users/page.tsx`: the member table, the filter toolbar, the invite
  modal, the per-row access modal, the per-row reactivate form, two locked surfaces, the empty
  state.
- **Endpoints**: `GET /users`, `GET /users/roles`, `GET /users/{id}`, `POST /users/invite`,
  `PATCH /users/{id}`, `POST /users/{id}/deactivate`
  (`apps/api/src/users/users.controller.ts:34-91`; `docs/openapi.json:5858-5969`).
- **Files**: `apps/admin/app/(dashboard)/users/{page.tsx,actions.ts,user-labels.ts}`;
  `apps/admin/components/{AdminModal,AdminActionForm,ConfirmationDialog,MutationNotice}.tsx`;
  `apps/admin/lib/{api,mutations,mutation-guard}.ts`;
  `apps/api/src/users/{users.controller.ts,users.service.ts}`; `packages/domain/src/users.ts`;
  `apps/mobile/src/features/users/organization-users-api.ts` (second client).
- Not in scope: teams, roles administration, the audit viewer, registration approval (cited only
  as the repository's own convention).

## 2. The probe (verbatim, its stdout and exit code)

Run exactly as written in
`.tezgah/research/feature-coherence/experiments/E4-mechanism-ablation/protocol.md`, from
`/Users/rizax/Projects/Ustam`:

```
$ cd /Users/rizax/Projects/Ustam && python3 - <<'PY'
#   the heredoc body is the protocol's probe block, copied verbatim (elided here
#   for length; the two printed lines below are the complete, unedited stdout)
PY
contract-only: ['GET /users/{id}', 'POST /users/{id}/deactivate']
surface-only: []
EXIT=0
```

Exit code 0, wall time 1.81 s. This output is the **`route` column evidence** of matrix 1: the
contract declares 6 `users` operations, the admin surface reaches 4 of them, and the two rows
above are declared-and-unreached in the admin app.

### 2.1 What the probe covers, and what it does not

- It scans `apps/admin/app` and `apps/admin/lib` for `adminApi(` only. The second client
  (`apps/mobile`) calls `apiClient.request(` and is invisible to it, so its "contract-only" set is
  *admin-only*. I adjudicated both rows with a call-site search across `apps/` and `packages/`
  (pattern `('/users|\`/users|"/users)`, gitignored files included). Hits: `page.tsx:58,59`
  (`/users`, `/users/roles`), `actions.ts:62` (`/users/invite`), `actions.ts:89` (`/users/${id}`,
  PATCH), `organization-users-api.ts:39` (`/users`), `:47` (`/users/invite`), `:56`
  (`/users/${id}`, PATCH). No other call site exists for `/users/{id}` in either client, and no
  call site at all for `/users/{id}/deactivate`. The two rows are therefore genuinely unreached,
  not an artifact of the probe's scan root.
- Method inference in the probe is textual: the verb is `POST` if the literal `'POST'`/`"POST"`
  appears within 200 characters after the path, else `PATCH`, else `GET`. It classified
  `actions.ts:89` as PATCH correctly (the `'PATCH'` literal is adjacent); a `GET` call whose
  neighbouring code mentions `POST` within 200 characters would be mislabelled. No such case
  exists in this area, and `surface-only` came back empty, so the heuristic produced no spurious
  row here — but the column it feeds is heuristic-derived and the raw set difference should be
  re-derived if the surface is edited.
- The `route` column below carries the probe's two rows plus the four rows it confirms as
  reached. It says nothing about authorization, validation or persistence; those columns come from
  reading the code, and every cell that was not read is marked `[NOT CHECKED]`.

## 3. Matrix 1 — capability

Rows are the entity's actions, columns the layers. `Route` cites the probe output then the code
path. Counts at the end of the section.

The probe's output, as the matrix's evidence for the `route` column (stdout verbatim, exit 0):

```
contract-only: ['GET /users/{id}', 'POST /users/{id}/deactivate']
surface-only: []
```

| # | Action | Surface (what a person can do) | Route | Authorization | Service / validation | Persistence |
|---|---|---|---|---|---|---|
| 1 | List the organisation's members | yes — table `page.tsx:167-285` | yes — `GET /users` in the probe's reached set (not in `contract-only`); `users.controller.ts:34-37` | yes — `user.manage`, `users.controller.ts:35`, `page.tsx:40-47` | yes — org-scoped query, `users.service.ts:26-67` | yes — `User`+`Membership`, `users.service.ts:33-46` |
| 2 | Search / filter the list | yes — toolbar `page.tsx:145-161` | **no** — `GET /users` declares no query parameter (`users.controller.ts:34-37`; zero `@Query` in the file, `Query` imported and unused at `:11`); the filter runs in the page, `page.tsx:60-67` | n/a (same as row 1) | yes, but in the page only | reachable only by fetching the whole membership set |
| 3 | View one member's detail | **no** — no detail view exists (the only `Link` on the route is "Filtreleri temizle", `page.tsx:159-161`) | **yes, unreached** — `GET /users/{id}` is in the probe's `contract-only` set; `users.controller.ts:49-57` | yes — `user.manage`, `:50` | yes — `users.service.ts:77-111` | yes — `User`+`Membership` with roles, `users.service.ts:88-107` |
| 4 | Invite a member | yes — `page.tsx:75-136` | yes — `POST /users/invite`, `actions.ts:62`; `users.controller.ts:59-68` | yes — `team.invite`→`user.manage` (`lib/mutations.ts:36`), guard `actions.ts:46`, API `:60` | yes — `InviteUserInput` (`packages/domain/src/users.ts:11-24`), zod pipe `users.controller.ts:64`, service rule `users.service.ts:114` | yes — `User`+`Membership`+`MembershipRole`+audit+outbox, `users.service.ts:117-176` |
| 5 | Deliver the invitation to the invited person | **no** — nothing on the route reports or carries a credential (`actions.ts:71` redirects with `result=user-invited` only) | **no** — no endpoint; the invite response is `{ data: { id, displayName } }`, `users.service.ts:174-176` | n/a | **no** — the generated password never leaves the service, `users.service.ts:116`, `:324` | the only artifacts are a `Notification` + a push attempt, `notification-event-mapper.ts:684-693`, `worker/push-notification.handler.ts:74,135,340` |
| 6 | Update access (role / scope / membership) | yes — per-row modal `page.tsx:224-279` | yes — `PATCH /users/{id}`, `actions.ts:89`; `users.controller.ts:70-80` | yes — `team.update`→`user.manage` (`lib/mutations.ts:38`), `actions.ts:75`, API `:71` | yes — `UserUpdateInput`, membership-only `users.service.ts:327-333`, platform-role `:187`, self-deactivate `:181-186`, inactive-membership `:200-207` | yes — membership + roles + audit + session/device revocation, `users.service.ts:209-243`, `:275-321` |
| 7 | Deactivate a member | yes, indirectly — the `Pasif — erişimi kaldır` option, `page.tsx:270-275` | **two routes for one action**: `PATCH /users/{id}` with `active:false` (used, `actions.ts:83-93`) and `POST /users/{id}/deactivate` (**unreached**, probe `contract-only`; `users.controller.ts:82-91`) | yes on both | yes — `users.service.ts:263` + `revokeMembershipAccess` `:275-321` | yes (PATCH path); the deactivate path's audit action `user.deactivate` (`users.service.ts:268`) is never written |
| 8 | Reactivate a member | yes — per-row form `page.tsx:208-221` | yes — `PATCH /users/{id}` body `{active:true}`, `actions.ts:81-82` | yes — `actions.ts:75`, API `:71` | yes — reactivation-only rule, `users.service.ts:200-207` | yes — `users.service.ts:263` + audit `:266-272` |
| 9 | Assign the platform role | **offered** when the server's role list contains it — role select from `GET /users/roles`, `page.tsx:104-118`, `:249-257` | yes — `roleKey` on both mutations | yes | **no** — the service refuses it: `users.service.ts:114` (invite), `:187` (update), `:336-349`; and the panel refuses it first, `actions.ts:61` and `:88` | n/a |

Rows: 9 checked, 0 uncheckable. Disagreements named by this matrix (details in findings):
rows 3 and 7 (`contract-only`, route yes / surface no), row 2 (surface yes / no server-side
capability), row 5 (the end of the action has no delivery path), row 7 (two routes for one
action), row 9 (an offer the system forbids).

Layers agree (pass rows, §10 has the full list): rows 1, 4, 6, 8 — panel gate, mutation registry
and controller all resolve to `user.manage`; row 8's reactivation-only precondition is enforced by
the service and mirrored by the surface.

### 3.1 The probe's two rows, read against the sibling surfaces

- `GET /users/{id}`: the same repository fetches a detail record exactly this way for customers —
  `customers/page.tsx:90-93` calls `/customers/${input.edit}` and renders the result. The users
  route has the endpoint and no such call: the strongest available standard, with both sides
  cited, is the customers list page.
- `POST /users/{id}/deactivate`: the panel's own action already does the same work through
  `PATCH /users/{id}` with `active:false` (`actions.ts:83-93`), so the endpoint is not merely
  unreached — it duplicates a live path under a second audit action name (`user.deactivate`,
  `users.service.ts:268`, vs `user.update` with `changed:['active']`, `:237`). The audit viewer
  carries labels for `user.invite`/`user.update` only (`audit/audit-model.ts:83-84`), so today's
  rows all render, but the two names describe one operation.

## 4. Matrix 2 — field contract

| Field | Column / type | Read by the API | Written by the API | Rendered (list / detail / form) | Validated | Label or enum source | Locale / format |
|---|---|---|---|---|---|---|---|
| `id` | uuid, `page.tsx:14` | yes, `users.service.ts:33` | no | list: key only `page.tsx:182`; form: hidden `:216`, `:246` | `z.uuid()`, `actions.ts:77` | — | — |
| `displayName` | string, `page.tsx:15` | yes, `users.service.ts:34`, `:82` | yes, on create `:125` | list column `page.tsx:183`; dialog title `:227`; invite/edit fields `:96-97`, none in the edit form (self-service by design, `actions.ts:78` comment, `users.service.ts:327-333`) | `min(1).max(120)`, `packages/domain/src/users.ts:13`; native `required maxLength={120}` `page.tsx:97` | — | displayed as given |
| `email` | string, `page.tsx:16` | yes, `users.service.ts:35` | yes, on create `:122-123` | list column `page.tsx:184`; invite field `:100-101` | `z.email()`, `packages/domain/src/users.ts:12` | — | no normalisation shown; the server stores `normalizedEmail` separately (`users.service.ts:121`) |
| `status` | `UserStatus`, `page.tsx:17` | yes, `users.service.ts:36` | **only at create, as the constant `ACTIVE`** — `users.service.ts:127`; no other writer in this feature (deactivate writes `membership.active`, `:209-215`, `:263`) | badge `page.tsx:185-189` | none | **two sources**: `userStatusLabels` `user-labels.ts:16-22` (ACTIVE, INVITED, SUSPENDED, DEACTIVATED, DELETED) vs the DB enum INVITED/ACTIVE/SUSPENDED/ARCHIVED `schema.prisma:39-44` — `DEACTIVATED`/`DELETED` can never arrive, `INVITED` is never written | raw key falls through as the badge text (`?? user.status`, `page.tsx:189`) |
| `locale` | string, `page.tsx:18` | yes, `users.service.ts:37`, `:85` | no — `UserUpdateInput.locale` is refused here (`users.service.ts:327-333`) | **not rendered**: the only hit for `locale` in `page.tsx` is the schema line (grep, 1 hit); the page states it is self-service (`page.tsx:164-166`) | `max(10)`, `packages/domain/src/users.ts:29` | — | — |
| `membership.scope` | string, `page.tsx:21` | yes, `users.service.ts:60` | yes — invite `:153`, update `:218-224` | list column `page.tsx:195-199`; invite select `:121-129`; edit select `:260-267` | `z.enum(['organization','team','assigned','own'])`, `packages/domain/src/users.ts:23`, `:41` | `scopeLabels`, `user-labels.ts:10-15` | **two defaults for one field**: the domain default is `organization` (`users.ts:23`), the invite form's default is `assigned` (`page.tsx:122`) — F17 |
| `membership.active` | boolean, `page.tsx:22` | yes, `users.service.ts:60` (hidden as `:61`) | yes — `:209-215`, `:263` | list cell `page.tsx:200`; select `:270-275` | boolean, `packages/domain/src/users.ts:42` | inline literals `'Aktif'`/`'Pasif'` (`page.tsx:200`) — the same words the `status` badge prints from another field | — |
| `membership.roles` | **two shapes** — list: `string[]` of keys, `users.service.ts:60`; detail: `{key,name}[]`, `users.service.ts:104-107` | yes, both | written by invite (one role, `:157-159`) and update (replace all, `:226-240`) | list joins labels `page.tsx:191-194`; edit select `:249-257` | role enum `packages/domain/src/users.ts:14-22`, `:30-39` | **two sources**: local `roleLabels` (`user-labels.ts:1-9`) wins over the server's `role.name` (`page.tsx:115`, `:254`) | — |
| invite response | `{id, displayName}` only, `users.service.ts:174-176` | — | — | nothing rendered | — | — | no field for a credential or a token — see finding F1 |
| filter `q`, `state` | not in the contract | n/a — endpoint has no query parameters | n/a | `page.tsx:145-156` | none | — | `toLocaleLowerCase('tr-TR')`, `page.tsx:60` (the one deliberate locale-aware choice in the feature) |

Rows: 11 checked, 0 uncheckable. Findings: the `status` label/enum drift and the missing writer
(§4 row 4), `locale` read and never rendered, `membership.roles` in two shapes, two label
sources for one enum (`roles`), two defaults for one field (`scope`), two fields printing
`Aktif`/`Pasif` in one row.

## 5. Matrix 3 — flow and step contract

The route has no URL steps; its multi-step behaviour is the client confirmation step inside
`AdminActionForm` (`:232-257` builds the summary, `ConfirmationDialog` renders it).

| Flow / step | Precondition | What it validates | What it writes | How a skip is prevented | Resume / persistence | Back-navigation retention | Where an error lands |
|---|---|---|---|---|---|---|---|
| Invite — step 1 form | `user.manage`: panel `page.tsx:40-47`, guard `actions.ts:46`, API `users.controller.ts:60` | domain `InviteUserInput` (`actions.ts:50-56`) + native `required`/`type=email`/`maxLength` (`page.tsx:97,101`) | nothing yet | the form is inside a modal that only opens on the trigger; no URL names it (`AdminModal` `page.tsx:75-79` passes no `id`) | **none** — a reload loses the form; `beforeunload` warns only while dirty (`AdminActionForm.tsx:143-148`) | cancel keeps the typed values (`AdminActionForm.tsx:309-312` does not reset the form); closing the modal discards them (F10) | inline, in the form (`actions.ts:19-44` → `AdminActionForm.tsx:272-298`) |
| Invite — step 2 confirmation | reached only from step 1 (`AdminActionForm.tsx:222-258`) | nothing; it summarises `displayName`/`email`/`roleKey`/`scope` (`page.tsx:83-87`) | nothing | client-side only — the server action re-validates and the API guards permission, so a skipped confirmation cannot bypass a rule | the pending `FormData` is held in a ref (`AdminActionForm.tsx:79`, `:231`) and lost on reload | cancel returns to the form with values intact | an error after confirm is rendered in the form behind the closed dialog |
| Access update — modal + confirmation | membership exists, not `SUPER_ADMIN`, membership active: the surface renders the edit modal only for active, non-platform rows (`page.tsx:204-206`), the service refuses otherwise (`users.service.ts:198`, `:200-207`) | domain `UserUpdateInput` (`actions.ts:79-85`) + the service rules | membership, roles, audit, session and device revocation (`users.service.ts:209-243`, `:275-321`) | the surface's branch and the service's rules agree; the panel's `SUPER_ADMIN` refusal duplicates the service (F7) | none | cancel keeps the values; the mutation drops the list's filter state (F6) | inline, in the dialog |
| Reactivate | membership inactive | none beyond permission (`actions.ts:79-82`) | `membership.active=true` + audit (`users.service.ts:246-272`) | the surface offers only this form for an inactive membership (`page.tsx:208-221`); the service refuses any other input for an inactive membership (`:200-207`) | none | n/a (single field) | inline |

Rows: 4 checked, 0 uncheckable. Findings: no persistence for any step, back-navigation that
discards (F10), the error summary's placement (F8), a confirmation used for ordinary creates
(F12).

## 6. Matrix 4 — interaction dependency

| Trigger | Dependents | Required action on change | Who owns the state | What is announced |
|---|---|---|---|---|
| `q` search field (`page.tsx:147-148`) | table rows, count paragraph `:163-166` | recompute or keep, per submit — the form is `method=get` (`:145`), so it is a document navigation | the URL (`searchParams`, `:36-39`) | nothing in-page: the results arrive in a new document render, so 4.1.3's "change without moving focus" does not describe it; the count text is the only result-side signal |
| `state` select (`:151-156`) | same | same | the URL | same |
| "Filtreleri temizle" link (`:159-161`) | both controls and the rows | reset | the URL (`href="/users"`) | nothing; the controls re-render empty |
| Row identity = the signed-in admin (`context.id`) | the `Pasif — erişimi kaldır` option (`:270-275`) | keep the option out | server context in the page; the service refuses self-deactivation (`users.service.ts:181-186`) | the option is simply absent; no announcement, and the server rule backs the surface |
| `membership.active = false` | the whole row's controls are replaced by the reactivate form (`:204-221`) | recompute (render the other branch) | the server (`users.service` list projection) | none in-page — the branch changes on a new render |
| `membership.roles` contains `SUPER_ADMIN` (`:205-206`) | the row's edit controls | keep them out | the page; the service refuses the target (`users.service.ts:198`, `:340-343`) | the row prints "Platform sahibi erişimi bu ekrandan değiştirilmez." |
| `roleKey` select = `''` ("Mevcut rolleri koru", `:249-256`) | the role write | keep vs replace-all are two distinct writes (`users.service.ts:226-240` deletes every role then creates one) | the form | yes — the dialog description (`:229`) and the confirmation body (`:238-241`) both state that selecting a role replaces all roles |
| a successful invite/update | the list's `q` and `state` | **keep** — they are the operator's context | nowhere: `actions.ts:71,98` redirect to bare `/users` | the notice says only "güncellendi"/"oluşturuldu" (F6) |
| the row modal's close control, Escape, or "Vazgeç" | typed values in that dialog | keep or warn | the client form, which has no close-time guard (F10) | nothing |

Rows: 9 checked, 0 uncheckable. Two of them are disagreements (F6, F10); the rest are pass rows,
including the two client-side guards that the service backs.

## 7. Matrix 5 — surface pattern, per rule

Sources are the artifact's: `APG x`, `SC n.n.n`, GOV.UK patterns. Contrast figures are computed
from the committed tokens in `apps/admin/app/globals.css` (`:root` variables) — a code-class
computation, not a rendered measurement; the rendered checks are marked `[NOT CHECKED]` with the
reason.

### Data views

| Rule | Verdict | Evidence |
|---|---|---|
| SC 1.3.1 real headers, labelled table | pass | `<th scope="col">` ×6/7 `page.tsx:172-178`, `<caption class="srOnly">` `:169` |
| `aria-sort` on the sorted column, reversing on activation | n/a — no column is sortable and no sort control exists; the server orders by `displayName asc` (`users.service.ts:47`) | `page.tsx:170-179` |
| Cells with widgets make the table a grid (one tab stop, arrow-key movement) | **violation** — one trigger per row in the tab order, plain table semantics | `AdminModal` trigger `page.tsx:224-226`, reactivate submit `:208-221`; 100 members = 100 stops |
| `aria-rowcount`/`aria-colcount` and position restore on return | n/a for virtualization (everything renders, `page.tsx:182-285`); position restore n/a (no detail view, F4) | — |
| SC 1.4.10 single-direction scroll at 320 px, table in its own scroll container | `[NOT CHECKED: the rendered page cannot be measured — no server may be started in this context]`; code path: `.tableWrap{overflow-x:auto}` `globals.css:561-563`, `th,td{white-space:nowrap}` `:575-577` | would be settled by a 320 px measurement of the table region |
| Pagination marks the current page, a one-page pager is hidden | n/a — no pager exists; the list is unbounded (no `take`/`limit` in `users.service.ts:26-67`) | F5 |
| Captions/headings describe the data, short nouns, first column human-readable, headers visible while scrolling | **violation** on the last clause — no `position: sticky` on `th` (the only `position: sticky` rules are the sidebar `globals.css:245` and the site intro `:1880`) | `page.tsx:172-178`, `globals.css:575-578` | F16 |
| Filters discoverable, active state visible in results | pass | control state persists in `defaultValue` (`page.tsx:148,152`) and the count text names it `:163-166`; "Filtreleri temizle" works `:159-161` |
| Detail view: `dl` key/value, every field shows a value or "not provided" | n/a — no detail view exists | F4 |
| A scroll region says it scrolls | pass | `role="region"` + `aria-label` + `tabIndex=0`, `page.tsx:167` |
| Long text has a strategy | pass, with the cost unmeasured — nothing is truncated (`white-space: nowrap`, `globals.css:575-577`) and the region scrolls; no value is hidden, but the operator loses columns | `[NOT CHECKED: the widths]` |

### Controls

| Rule | Verdict | Evidence |
|---|---|---|
| `APG combobox` (+ its keyboard rules) | n/a — no combobox on the route; role and scope are native `<select>` (`page.tsx:104,121,249,260,270`) | — |
| `APG listbox` | n/a — same | — |
| A row carrying its own controls is a grid/table, not a listbox | **violation** — see the grid row above | `page.tsx:208-279` |
| Visible persistent label; instructions where the format is not customary; a counter where a length limit exists | **violation** on the counter clause — `displayName` has `maxLength={120}` (`page.tsx:97`) with no counter and no stated ceiling; the ceiling is only revealed by the server message `1–120 karakter arasında bir ad girin.` (`actions.ts:11`) | email's format is customary, so the instructions clause is satisfied |
| SC 1.3.5 scoped: an `autocomplete` token on the user's own data, absent/`off` on search and record fields | pass — the invite fields collect the invitee's data, not the signed-in user's, so an H98 token would be wrong here; no `autocomplete` attribute is present anywhere in the area (grep), and the search field declares none, which the rule permits | `page.tsx:96-101`, `:147-148` |
| One required/optional convention across the product | `[NOT CHECKED: the product-wide convention was not surveyed]`; inside this feature nothing is marked visually — the two required fields carry the native `required` attribute only (`page.tsx:97,101`) and their requiredness is learned on submit | would be settled by the same survey across the other 15 list pages |
| `APG disclosure` | n/a — no show/hide control; the reveal surfaces are native dialogs | — |
| `APG tabs` | n/a — no tabs on the route | — |
| A conditional reveal reveals a question and announces it | n/a — no conditional reveal exists; the active/inactive branch is a server-rendered branch (see matrix 4) | `page.tsx:204-221` |
| Pickers: text entry alongside a calendar; a combobox where free text plus a known list is needed | n/a — no date field, and the role/scope pickers are closed lists served by the contract | — |
| SC 2.5.8 target size | pass at the CSS level — `.button{min-height:44px}` `globals.css:193-194`, `.buttonSmall{min-height:36px}` `:680-681`, both above the 24 px floor; `[NOT CHECKED: the rendered box for the inputs and selects, which declare no min-height]` | — |
| SC 2.4.7 focus visible / SC 1.4.11 | `[NOT CHECKED: the rendered indicator on the real background — a screen cannot be run here]`; the stylesheet does define focus rings (`:145-146`, `:2532-2536`) and no rule removes an outline wholesale (grep for `outline`: 4 hits, none on the controls used here) | — |
| SC 1.4.3 contrast, no colour-only state | pass — computed from the tokens: `--muted #60675f` on `--surface #ffffff` = **5.83:1** (table header text, 13 px, `globals.css:575-577`), on `--surface-muted #eef0ec` = 5.08:1; the warning badge uses the panel's own override `#875000 on #f4e7d6` = **5.43:1** (`globals.css:596-598` and the tint at `:588-591`) and the danger badge `#a82f2f` = 4.99:1, so the repo has already answered the "tinted background" case with a comment at `:596`; the status is text, never colour alone (`page.tsx:185-189`) | `[NOT CHECKED: the rendered pixels]` |

### Validation and errors

| Rule | Verdict | Evidence |
|---|---|---|
| Validation on submit, failing values kept, server-side validation present | pass — native `invalid` events are collected on submit (`AdminActionForm.tsx:41-45`, `:137-138`), the form is not reset (`:222-258`), the server validates the same input through the domain zod (`users.controller.ts:64,76`) and the action re-parses (`actions.ts:50,79`) | no `novalidate` anywhere in the app (grep) |
| SC 3.3.1/3.3.3 the item in error is identified and the correction described | pass for the mapped fields (`fieldHelp` `actions.ts:11-17`); **violation** when the zod issue has an empty path — `z.uuid()` on the hidden `id` produces `fieldErrors: {}` and only the generic `Alanları kontrol edin…` (`actions.ts:30-35`, `:77`) | F14 |
| Association: `aria-describedby` to the message, the same wording in the summary and beside the field, a summary entry that moves focus to its field | pass, with one shape to note — the message nodes live in one list (single source of wording) and `aria-describedby` points at them (`AdminActionForm.tsx:94-110`), each entry is a button that focuses its control (`:283-296`) | — |
| An error summary **at the top** of the form | **violation** — the feedback block is rendered after the `</fieldset>` (`AdminActionForm.tsx:272-298`), so focus moves to the bottom of the form (`:88-91`) | F8 |

### Flows

| Rule | Verdict | Evidence |
|---|---|---|
| One question per page, a unique heading per step, a back link and Continue | n/a — no URL-per-step flow on this route; the modal is one group under its own heading with a named submit (`page.tsx:76-78`, `:131-134`) | — |
| Check-your-answers: pre-populated, a per-section Change link with hidden text naming what it changes, a submit naming its action | pass in the shape this panel uses — the confirmation shows a `dl` built at submit (`AdminActionForm.tsx:232-257`, `:323-331`) and "Vazgeç" returns to the still-populated form (`:309-312`); the submit names its action (`Davet oluştur`, `page.tsx:132`) | — |
| SC 3.3.7 redundant entry | pass — the edit dialog pre-populates `scope` from the row (`page.tsx:260`) and the invitee's name/e-mail are asked once | — |
| SC 3.3.4 a data-changing submission is reversible, checked or confirmed | pass — deactivation is confirmed and the confirmation names the effect (`page.tsx:238-241`) | — |
| Destructive confirmation names what will be lost, keeps its actions inside the panel, reserved for the irreversible | partly — names the record and the effect (`page.tsx:238-241`), actions inside the dialog (`ConfirmationDialog.tsx:96-101`), focus on the least destructive (`:31`); **misuse**: the same confirmation pattern guards ordinary creates (invite, `page.tsx:83-87`; reactivate, `:210-215`) | F12 |
| `APG dialog`: `aria-modal` only when the background is inert, focus moves in and stays, returns to the invoker, an `alertdialog` focuses the least destructive action | pass — native `showModal()` supplies inertness and focus return (`AdminModal.tsx:21-22`, `:56`), Tab is wrapped (`:123-152`), Escape is scoped (`ConfirmationDialog.tsx:35-47`), focus lands on "Vazgeç" (`:31`) | `[NOT CHECKED: initial focus in the AdminModal — in DOM order the close button (`AdminModal.tsx:155-162`) precedes the body controls, so `showModal()`'s first-focusable rule lands focus on Close rather than the first question; and the dimming between two stacked layers is visual]` |

### Notifications

| Rule | Verdict | Evidence |
|---|---|---|
| SC 4.1.3 a change made without moving focus is programmatically determinable | n/a for the filter (a `method=get` submit is a document navigation, `page.tsx:145`) and for the post-mutation notice (the action redirects, so the notice is present in the new document, `actions.ts:71,98` → `MutationNotice` `role="status"` `MutationNotice.tsx:133`) | `[NOT CHECKED: whether a screen reader announces a role=status node present at first render — the announcement cannot be heard here]` |
| The whole status string is the announced unit, and the end of a wait is announced | pass at the code level — the pending label is a full sentence inside `role="status"` (`AdminActionForm.tsx:269-270`) and the success text is a full sentence (`MutationNotice.tsx:133`) | `[NOT CHECKED: the announcement]` |
| Changes that are not status messages stay out of live regions | pass with a note — the form's feedback block takes `role="alert"` for errors (`AdminActionForm.tsx:278`) *and* is focused (`:88-91`); APG and the GOV.UK error-summary pattern both combine an alert role with a programmatic focus, so this is the documented pattern rather than a violation, but it is a double-announcement shape | `[NOT CHECKED: the announcement]` |
| A notification banner is `role=region` with a label, before the h1, at most one, never stands in for validation errors | n/a — no banner on this route; the post-mutation notice is a `p.notice` between the header and the section (`page.tsx:73`), and errors are carried by the form, not by it | — |

Rows: matrix 5 checked 10 data-view rules, 13 control rules, 4 validation rules, 6 flow rules,
4 notification rules = 37 rows; 12 of those are `n/a` with a reason, 7 carry a
`[NOT CHECKED]` cell with the reason, 5 are violations, the rest are passes.

## 8. Findings, most severe first

Severity is the artifact's 0-4 scale (frequency × impact × persistence): 4 = the task cannot be
completed; 0 = cosmetic. Every finding names one evidence class.

**F1 — The invite creates an account with a password nobody receives; the action succeeds in the
database and fails the person.** severity 4.
Class: *the end of the action has no delivery path*. `code`.
Evidence: the service generates a password and stores only its hash (`users.service.ts:116`, `:324`),
creates the user with `status: 'ACTIVE'` (`:127`), and returns `{ data: { id, displayName } }`
(`:174-176`) — no credential, no token, no link field. The only output is the `UserInvited` outbox
event (`:172`), which the notification mapper turns into an in-app notification with copyKey
`notification.account.invited` (`notifications/notification-event-mapper.ts:226-230`, `:684-693`)
and the push handler turns into the push copy "ServisTek daveti" (`worker/push-notification.handler.ts:74`)
addressed to the invited user id (`:135`); push fan-out looks for that user's device tokens
(`:340`, `:485`), which a person who has never signed in does not have. Email exists in the
repository only for password reset (`auth/password-reset-email.provider.ts:6-20`, wired at
`auth/auth.module.ts:41`). The repository already hands over first-time credentials for the
neighbouring case: registration approval carries `decision.createdLogin` into a short-lived cookie
(`registration/actions.ts:51-63`) and renders it once (`registration/page.tsx:27-36`) through the
shared sentence builder `apps/admin/lib/login-handover.ts:11-16`, whose second branch already
handles "this e-mail was registered before, the password is unchanged" — exactly the two cases an
invite produces.
**Prevent**: an API-level assertion that a successful invite leaves a delivery artifact for the
recipient — today the check that would fail. Concretely: after `POST /users/invite`, assert that a
row exists that names the invitee and a credential or token (the fake mail provider's outbox, or an
invitation table), not merely an `OutboxEvent` of type `UserInvited`. The existing
`apps/admin/e2e/admin-core-recovery.e2e.ts:72` asserts only `result=user-invited`, which is why the
gap survives a green suite.

**F2 — A deactivated member still reads "Aktif", and the invitation has no state anyone can
see.** severity 3. Class: *state the operator cannot observe; two fields printing one word*. `code`.
Evidence: `status` is written once, as the constant `ACTIVE` (`users.service.ts:127`), and no code
path in this feature writes it again — deactivation writes `membership.active` only (`:209-215`,
`:263`). The row therefore prints "Durum: Aktif" (`page.tsx:185-189`, from `user.status`) beside
"Üyelik: Pasif" (`:200`, from `membership.active`): the same word for two different fields, and the
access-revoked row reads as active. The label map cannot help: `userStatusLabels` offers
`DEACTIVATED`/`DELETED` (`user-labels.ts:16-22`) which are not in the database enum
(`apps/api/prisma/schema.prisma:39-44`), while the enum's `INVITED` is never written by any code
path (grep: no non-generated writer), so the one state the operator needs — "invited, never signed
in" — is neither produced nor displayed. The repository's own suite pins the current behaviour rather
than the gap: `users.service.test.ts:100` asserts that the membership update never calls
`tx.user.update`, so leaving `status` at `ACTIVE` is a deliberate choice, not an accident — which is
why the finding is a product decision to revisit, not a bug report.
**Prevent**: a contract test that pins the pair — for each `UserStatus` in the schema there must be
a writer and a label, and for each label a reachable status; and a page test asserting that a row
whose membership is inactive cannot contain the string `Aktif` in the `status` cell. The existing
`page.test.tsx` feeds `status: 'ACTIVE'` in every fixture, so it cannot see this.

**F3 — The dedicated deactivate endpoint is unreachable, and the panel records a different audit
action for the same operation.** severity 3. Class: *two routes for one action / a capability the
server has and no user can reach*. `code`.
Evidence: probe output `contract-only: [..., 'POST /users/{id}/deactivate']` with `surface-only: []`;
the call-site search over `apps/` and `packages/` (pattern above) finds no caller in either client;
the controller exposes it at `users.controller.ts:82-91` and the panel's own action does the same
work through `PATCH` with `active:false` (`actions.ts:83-93`). The audit vocabulary differs:
`user.update` with `changed:['active']` (`users.service.ts:237`) is what today's rows say, while
`user.deactivate` (`:268`) is never written, and the viewer's label map knows only
`user.invite`/`user.update` (`audit/audit-model.ts:83-84`).
**Prevent**: a route-coverage test in the shape the repository already uses for visible actions
(`apps/admin/lib/visible-action-consumers.contract.test.ts`) extended to the direction it lacks:
every declared operation in `docs/openapi.json` under a surface's route root must have a caller, or
an allowlist entry with a reason. Today that assertion would fail on two rows.

**F4 — The member detail capability exists on the server and no surface reaches it.** severity 3.
Class: *a layer yes, surface no — a detail endpoint with no detail view; a contract field no view
renders*. `code`.
Evidence: probe `contract-only: ['GET /users/{id}', ...]`, no caller in either client;
`users.controller.ts:49-57` and `users.service.ts:77-111` serve it. The route renders no detail
view: the only `Link` on the page is "Filtreleri temizle" (`page.tsx:159-161`), the row's identity
is never a link, and the record can only be inspected by opening the edit dialog. Two contract
shapes result: the list returns `membership.roles` as a `string[]` of keys (`users.service.ts:60`),
the detail returns `{key,name}[]` (`:104-107`), and the panel compensates with a local label map
that overrides the server's own `role.name` (`page.tsx:115`, `:254`); `locale` is read by both
endpoints (`:37`, `:85`) and rendered nowhere (grep `locale` in `page.tsx`: 1 hit, the schema).
The repository's own convention is the opposite — the customers list fetches the detail record and
renders it (`customers/page.tsx:90-93`).
**Prevent**: a contract test asserting one shape per field across a route's operations (the same
`membership.roles` type in list and detail), plus a page test that every field the response schema
declares is either rendered or listed in an explicit "not rendered, because …" allowlist. The
`Response` zod schema (`page.tsx:14-27`) is the place the check can read.

**F5 — The list has no server-side search or paging: an unbounded fetch with a hardcoded empty
pagination envelope, filtered in memory.** severity 3. Class: *an in-memory list filter under a
pagination envelope nobody computes*. `code`.
Evidence: the page fetches every member and filters the array (`page.tsx:58-67`, with the Turkish
casefold at `:60`); the endpoint accepts no query parameter (`users.controller.ts:34-37`; the file
imports `Query` at `:11` and never uses it — zero `@Query`), and the service returns
`page: { nextCursor: null, hasNextPage: false }` as a constant (`users.service.ts:64`) with no
`take`/`skip` (`:26-67`). The sibling list pages do the opposite: `/customers` passes `limit=30`
and `q`, and follows `response.page.nextCursor` (`customers/page.tsx:88-96`), `/work-orders` renders
a next-cursor link when `hasNextPage` (`work-orders/page.tsx:404-409`), `/dispatch` and `/audit`
page the same way. A capability-change proposal is required for the fix (P1) because the endpoint
cannot express the input today.
**Prevent**: a contract test that every list operation which returns a `page` envelope must also
declare the cursor/limit query parameters it is meant to consume — the constant `nextCursor: null`
would fail it. Second, a page test with a fixture of 200 members asserting the request carries the
filter rather than that the DOM shows fewer rows.

**F6 — A successful mutation throws away the operator's filter state.** severity 2.
Class: *a value the user chose silently discarded (no cascade, nothing announces it)*. `code`.
Evidence: the toolbar keeps `q`/`state` in the URL (`page.tsx:145-161`), and both actions end in a
bare redirect — `redirect('/users?result=user-invited')` (`actions.ts:71`) and
`redirect('/users?result=user-updated')` (`:98`). An operator working through a filtered list
("Pasif" members, say) lands on the unfiltered list after each edit, and the notice mentions only
the mutation (`MutationNotice.tsx:45-46`). The repository already has the convention for the
opposite: `/customers` posts a hidden `returnTo` built with `coreHref('/customers', input)`
(`customers/page.tsx:140`, `:198`; `work-orders/core-navigation.ts:2`) which its action reads back
(`customers/actions.ts:25`), and `/inventory` preserves `q` in its redirect (`inventory/actions.ts:81`).
**Prevent**: an e2e assertion that after an edit made from `/users?state=inactive` the URL still
carries `state=inactive`; or a unit assertion on the two actions that the redirect preserves the
search params it received.

**F7 — The role picker is fed by the server and offers a value three hand-copied guards refuse.**
severity 2. Class: *an offer the system forbids; one rule read in three places*. `code`.
Evidence: the select is populated from `GET /users/roles` (`page.tsx:59`, `:104-118`, `:249-257`),
whose source is every role row of the organisation (`users.service.ts:69-75`) — nothing excludes
`SUPER_ADMIN` (`prisma/seed-role-permissions.ts:66-70` seeds such a row for the platform
organisation, and a tenant organisation with one would offer it). The panel refuses it in the
action with a literal (`actions.ts:61`, duplicated at `:88`) and the service refuses it again
(`users.service.ts:114`, `:187`, `:336-349`), while the contract's own enum lists it as acceptable
input (`packages/domain/src/users.ts:14-22`, `:30-39`). Three readings of one rule, each written by
hand: the deviating one is the picker's source, not the rule.
**Prevent**: one source — a contract test asserting the role list the panel receives contains no key
the mutation enum refuses (or the enum is derived from the assignable set), plus a page test
asserting the rendered option values are a subset of the acceptable assignment set. The panel's
duplicate guard then has no reason to exist.

**F8 — The error summary renders below the fields and takes focus to the bottom of the form.**
severity 2. Class: *an error mapped to the whole flow instead of the field*. `code`.
Evidence: `AdminActionForm` renders its `fieldset` first (`:261-268`) and the feedback block after
it (`:272-298`), then focuses that block on every result (`:88-91`); the entries inside it are the
only place an error message exists, and each is a button that focuses its control (`:283-296`). So
after a failed invite the operator is moved past the form to its last element — the rule the
artifact cites is "an error summary **at the top** of the form naming what went wrong and linking
each item to its field".
**Prevent**: an e2e assertion that, after a validation failure, the focused element precedes the
form's first field in document order, and that each summary entry moves focus to its field. The
existing `actions.test.ts` asserts the returned `fieldErrors` object, not what the operator sees.

**F9 — Every row carries its own control in the tab order, with plain table semantics.** severity 2.
Class: *cells that contain widgets make it a grid, not a table of tab stops*. `code`.
Evidence: the last column holds one `AdminModal` trigger per editable row (`page.tsx:224-226`) or a
reactivate submit (`:208-221`); the container is a plain `<table>` with column headers and no grid
semantics — no `role="grid"`, no `aria-rowindex`, no arrow-key movement (grep: none on the route).
For a 100-member organisation that is 100 tab stops between the filter toolbar and the end of the
page.
**Prevent**: an e2e assertion with a 40-row fixture that the table region exposes a bounded number
of tab stops (the number the chosen pattern fixes) rather than one per row — today the assertion
would count 40.

**F10 — Closing a row dialog discards typed values with no warning.** severity 1.
Class: *back-navigation that discards what it should keep*. `code`.
Evidence: `AdminModal`'s close control, Escape and cancel all just set `open=false`
(`AdminModal.tsx:155-162`, `:114-122`); the form inside has no close-time guard, and its
protection is `beforeunload` only, which fires on a page unload, not a dialog close
(`AdminActionForm.tsx:143-148`). The repository has a primitive for this case,
`components/useUnsavedChangesGuard.ts`, used by the technical editors
(`technical/TechnicalStructuredContentEditor.tsx:6` and two siblings).
**Prevent**: a component-state checklist entry ("a dialog that contains a form is closed through
the same guard as a page") plus one test: opening the invite dialog, typing a name, pressing
Escape, and asserting the guard fired or the value survived.

**F11 — The empty state is one flat sentence that names an action it cannot reach.** severity 1.
Class: *content rules + a deviation from the repository's own empty-state convention*. `code`.
Evidence: `page.tsx:288-290` renders a single text node — "Eşleşen kullanıcı yok. Filtreleri
temizleyin veya yeni takım üyesi davet edin." — with no `<strong>`/`<p>` structure, no link, and no
distinction between "filtered to nothing" and "no members". The siblings distinguish the two and
link the repair: `/quotes` (`quotes/page.tsx:404-418`), `/maintenance`
(`maintenance/page.tsx:330-345`), `/customers` (`:374-380` with `<a href="#customer-create">` at
`:394`). The hash link works elsewhere because the modal takes an `id` (`AdminModal.tsx:70-90`, `:99-107`);
the invite modal passes none (`page.tsx:75-79`), so this route has no deep link to its own create
action — and `.empty a.button` exists in the stylesheet (`globals.css:961-963`) unused here.
**Prevent**: a page test that the empty state contains a focusable control whose target opens the
create action (the `/customers` shape), run against both empty variants.

**F12 — Confirmation is the default for ordinary creates, which flattens the one confirmation that
matters.** severity 1. Class: *the destructive-confirmation pattern used for ordinary branch
points*. `code`.
Evidence: invite (`page.tsx:83-87`), reactivate (`:210-215`) and the irreversible access update
(`:235-244`) all use the same `confirmation` prop of the same component. The invitation and the
reactivation are ordinary creates; deactivation is the one whose sessions and devices are revoked
one-way (`users.service.ts:275-321`), and its confirmation does not say it cannot be undone
(`page.tsx:240-241` names the effect, not the reversibility).
**Prevent**: a checklist entry naming which mutations may carry a confirmation, asserted as a test
over the `confirmation` props of the route; and one sentence added to the deactivation body naming
that revoked sessions and devices are not restored by reactivating.

**F13 — A length limit is enforced in three layers and stated in none.** severity 1.
Class: *instructions and counters*. `code`.
Evidence: `maxLength={120}` on the input (`page.tsx:97`), `max(120)` in the contract
(`packages/domain/src/users.ts:13`), and the failure text `1–120 karakter arasında bir ad girin.`
served only after a failed submit (`actions.ts:11`). The rule the artifact cites asks for a counter
where a length limit exists.
**Prevent**: a component-state checklist entry ("a control with a length limit renders its
remaining count or its limit as help text"), asserted by a page test that the invite form's
`displayName` field has an `aria-describedby` target.

**F14 — A validation failure with no field path produces a message that names no field.**
severity 1. Class: *an error mapped to the whole flow instead of the field*. `code`.
Evidence: `failure()` maps a zod issue only when `fieldHelp` has an entry for the first path segment
(`actions.ts:30-35`, `:11-17`); `z.uuid().parse(text(data, 'id'))` (`:77`) raises an issue with an
empty path, so the result is `fieldErrors: {}` and the generic `Alanları kontrol edin. İşaretlenen
bilgileri düzeltip yeniden deneyin.` — with no field marked and, in the form, no summary entry
(`AdminActionForm.tsx:278` then shows the error text only). Reachable only by tampering with the
hidden `id`, which is why it is severity 1 rather than 3.
**Prevent**: a unit assertion that every zod failure produced by the two actions yields at least one
`fieldErrors` entry, or an explicit "record-level error" branch in the UI that names the record.

**F15 — A surface state with no producer: `?error=`.** severity 1.
Class: *a producer-less surface state*. `code`.
Evidence: the route parses and renders `input.error` (`page.tsx:37`, `:73`) through
`MutationNotice`'s error branch (`MutationNotice.tsx:113-130`), but no code path in this feature
ever produces it — both actions return errors inline and redirect with `?result=` only
(`actions.ts:71`, `:98`; grep for `error=` in the route: no producer). Other routes do produce it
(`announcements/actions.ts:38`), so the branch is live in the product and dead here.
**Prevent**: none mechanical — this stays a review item; the honest options are to delete the
parameter from the route's `searchParams` type or to make the guard failures (`requireAdminMutation`)
redirect with it instead of throwing.

**F16 — An unbounded list scrolls its column headers away.** severity 1.
Class: *data-view content rules*. `code`.
Evidence: the table renders every member (no `take`, `users.service.ts:26-67`) inside
`.tableWrap{overflow-x:auto}` (`globals.css:561-563`) with `th{color:var(--muted);font-size:13px}`
(`:575-578`) and no `position: sticky` on `th` (the only two sticky rules in the stylesheet are the
sidebar `:245` and the site intro `:1880`). The rule the artifact cites asks that headers stay
visible while scrolling.
**Prevent**: an e2e assertion that after scrolling the list body the column header row is still
within the viewport — the measurement the artifact warns about ("a document-overflow check passes
while the column is clipped") is not this check, so it must be written as a header-position check.

**F17 — Two defaults for one field across the panel and the contract.** severity 0.
Class: *two readings of one rule — a default that differs by layer*. `code`.
Evidence: the contract defaults `scope` to `organization` (`packages/domain/src/users.ts:23`) while
the invite form's select defaults to `assigned` (`page.tsx:122`); both clients send an explicit
value (`actions.ts:54`, `organization-users-api.ts:45-51`), so no user meets the difference today —
it is visible only to the next client, which would get a different default for the same field
depending on which document it read.
**Prevent**: a schema test asserting the panel's form default equals the domain default, or that
the form default is read from the schema; it is cheap and would fail on the next divergence.

## 9. Capability-change proposals

Two findings name a layer that does not exist yet, so they may not be delivered as screen-level
recommendations.

### P1 — Server-side filter and cursor paging for the member list (from F5)

| Heading | Content | Falsified by |
|---|---|---|
| Capability | Query the organisation's membership set by a match term and a membership state, and iterate it in cursor-bounded pages. | a cited code path that already narrows or bounds the set (`users.service.ts:26-67` does neither; `page.tsx:61-67` narrows only in the browser) |
| Absence proof | `GET /users` declares no query parameters (`users.controller.ts:34-37`; `@Query` count = 0) and the service returns a constant envelope (`users.service.ts:64`); the failing input is `/api/v1/users?limit=30&cursor=<key>&q=ipek&state=inactive`, whose parameters are ignored and which returns every member. | a route that accepts and honours those parameters |
| Contract delta | `docs/openapi.json:5858-5876` gains `q`, `state`, `limit`, `cursor` on the list operation, and the list parameters/response schema of the generated client `packages/api-client/src/generated/schema.ts` are regenerated. Rejectable artifact: `node scripts/verify-api-contract.mjs` (it compares the committed spec/client pair, `scripts/api-contract-verifier.contract.mjs:20`). | running the verifier green with an unchanged diff |
| Migration | No schema change: the query is a `where`/`orderBy`/`take` on the existing `User`/`Membership` projections. Phases: expand (parameters accepted, ignored) → migrate (the panel starts sending them) → contract (parameters required in the spec) — the contract phase carries the release date, and no backfill is needed because nothing is stored. | a contract phase with no date |
| Rollout | Flag `admin_users_server_paging` (boolean, OpenFeature-style, expected lifetime one release), initial exposure the panel only, kill-switch owner the platform owner, abort when the p95 of `api.users.get` in `recordAdminProductEvent` (`lib/api.ts:133-140`) rises above 1.5× the pre-change value over a 24-hour window. | an unmeasurable threshold, or a flag with no lifetime |
| Verification | Fails before / passes after: `apps/admin/app/(dashboard)/users/page.test.tsx` gains a 200-row fixture asserting the request carries the filter and the cursor (`api.mock.calls[0][0]` today is the bare `/users`, see `page.test.tsx:31`), plus the API-level spec check in `scripts/verify-api-contract.mjs`. | a check that also passes on the pre-change commit |
| Reversibility | Writes nothing. Restore = revert the flag; the panel falls back to the in-memory filter. Not a one-way door. | data written with no restore step |
| Decision | ADR "member list paging is server-side": context (F5), decision (cursor paging with the contract's existing envelope), status proposed, consequences (the panel loses the whole-set count, which becomes page-scoped and must say so). Supersedes nothing. | an ADR without a status |
| Appetite | One week; out of bounds: changing the response envelope shape, sorting, or the mobile client; when the box ends, ship the parameters with the panel still reading the whole set (flag off) and report it. | no box, or an implicit extension |

### P2 — A delivery path for an invitation (from F1)

| Heading | Content | Falsified by |
|---|---|---|
| Capability | The invited person receives, without a prior session, the means to sign in for the first time. | a cited path that already hands a first-time credential to an invited user (`users.service.ts:174-176` returns none; `registration/page.tsx:27-36` does it only for registration approval) |
| Absence proof | The invite response has no field for a credential or a token (`users.service.ts:174-176`) while the password is generated and hashed inside the service (`:116`, `:324`); the only outbox event's consumer notifies (`notification-event-mapper.ts:684-693`) and pushes (`push-notification.handler.ts:74`) to a user id that has no device token yet (`:340`). The failing input is a fresh e-mail address: the row appears, the person cannot sign in. | a cited path that delivers to a fresh invitee |
| Contract delta | Either an `InviteUserResponse` carrying `{ id, displayName, handover: CreatedLogin }` (the shape `apps/admin/lib/login-handover.ts:3-7` already defines and `registration` already transports), or a new `POST /users/{id}/invitation` issuing a single-use token with a TTL. Spec + generated client regenerated; rejectable by `scripts/verify-api-contract.mjs`. | the verifier green with no diff |
| Migration | No table change for the response option; the token option adds one table (`Invitation`), so: expand (table + nullable columns) → migrate (no backfill; existing pending invites have no token and are handled by the password-reset path) → contract (drop nothing; the token column becomes required only when invites stop being silent) — contract phase dated with the release that enables the email channel. | a contract phase with no date |
| Rollout | Flag `user_invite_delivery` (enum: `none` \| `notice` \| `email`, expected lifetime one release, owner the platform owner), initial exposure one organisation, abort when the share of invites with no delivery artifact in a 7-day window exceeds 0 and the invite-to-first-login conversion does not rise — the first half of that threshold is measurable today only after F1's Prevent check exists, which is why that check ships first. | an unmeasurable threshold, or a flag with no lifetime |
| Verification | Fails before / passes after: the F1 Prevent check (a post-invite assertion that a delivery artifact exists for the invitee) and, for the panel half, a test that a fresh invite renders the handover sentence built by `createdLoginSentence` (`login-handover.ts:11-16`). | a check that also passes on the pre-change commit |
| Reversibility | Writes a credential (one-way for the recipient once read) — so the handover must be shown once, never stored, exactly as `login-handover.ts:1-5` documents for registration, and the token option must record its own revocation step: deleting the token row restores "invited, undelivered". The e-mail branch sends to a third party and cannot be recalled: **one-way door, approval required**. | data written with no restore step and no label |
| Decision | ADR "an invitation must be deliverable": context (F1), decision (response-carried handover first, e-mail second), status proposed, consequences (the panel must render a once-only surface; the API must never log the credential). Supersedes nothing. | an ADR without a status |
| Appetite | Two weeks; out of bounds: changing the invite's permission model, merging it with registration, or adding an SMS channel; at the end of the box, ship the handover response and the panel surface with the e-mail channel still off and report the residual gap. | no box, or an implicit extension |

## 10. Pass rows (the layers agree)

- Read and both mutations resolve to the same permission in the panel, the mutation registry and
  the API: `user.manage` (`lib/mutations.ts:36,38`, `page.tsx:40-47`, `users.controller.ts:35,44,50,60,71,84`).
- Self-deactivation is prevented twice: the surface omits the option for the caller's own row
  (`page.tsx:270-275`) and the service refuses it with `SELF_DEACTIVATE`
  (`users.service.ts:181-186`, `:249-251`).
- Reactivation-only for an inactive membership: the surface renders only the reactivate form
  (`page.tsx:204-221`), the service enforces it (`users.service.ts:200-207`), and the mobile client
  is held to the same rule (`organization-users-api.ts:54-56`).
- The platform role is protected on both sides: no edit controls for a `SUPER_ADMIN` member with the
  reason printed (`page.tsx:205-206`), and the service refuses the target (`users.service.ts:198`,
  `:340-343`).
- Global profile fields stay self-service: the panel never sends `displayName`/`locale`
  (`actions.ts:78-85`, asserted at `actions.test.ts:40-53`) and the service refuses them
  (`users.service.ts:327-333`).
- The invitation's "replace all roles" semantics is announced before it happens, in the dialog
  description (`page.tsx:229`) and again in the confirmation (`:238-241`).
- Confirmation dialog behaviour: least-destructive focus (`ConfirmationDialog.tsx:31`), Escape
  scoped to the top layer (`:35-47`), actions inside the panel (`:96-101`).
- Validation is submit-time with values kept (`AdminActionForm.tsx:41-45`, `:137-138`, `:222-258`)
  and re-checked on the server (`users.controller.ts:64,76`).
- Contrast of the peripheral text is above AA, computed from the tokens: `--muted` 5.83:1 on
  `--surface`, the warning badge 5.43:1 with the panel's own override (`globals.css:596-598`), and
  the status is never colour-only (`page.tsx:185-189`).
- The Turkish casefold is deliberate and correct for the search (`page.tsx:60`, `toLocaleLowerCase('tr-TR')`).

## 11. Coverage, and what would change the conclusion

| Matrix | Rows checked | Rows not checkable | Note |
|---|---|---|---|
| 1 capability | 9 | 0 | 2 of the 9 are the probe's `contract-only` rows |
| 2 field contract | 11 | 0 | `locale` and the invite response are the rows with a gap |
| 3 flow / step | 4 | 0 | 4 flows, of which 2 have a confirmation step |
| 4 interaction dependency | 9 | 0 | 2 disagreements, 7 passes |
| 5 surface patterns | 37 | 7 cells | 12 rules are `n/a` with a reason; the 7 uncheckable cells are the rendered checks below |

Not checkable in this context, and why:

- **The running app.** No server may be started or stopped in this context, so no page was
  exercised: every claim above is a reading of committed source plus the probe's output. The
  consequences are that the artifact's 8 mechanical blind spots stay open: the error text's
  adequacy (partly readable in `actions.ts:11-17`, but not as rendered), the destructive
  confirmation's wording as read by a person, the announcement of status messages, the visibility
  of the focus indicator, the 320 px reflow measurement, the autocomplete-token judgement (settled
  here by reasoning, not by a browser), the dialog's initial focus (the DOM order says the close
  button wins, unobserved), and whether a conditionally revealed question is announced.
  What would change the conclusion: a 320 px and a 1440 px run of `/users` with the table region
  measured; a screen-reader pass over the invite form's failure path; a device-scale check of
  `page.tsx:270-275`'s option list.
- **The corpus and the other arms.** Deliberately unread (blindness).
- **A credential.** None was available or needed: nothing was executed against a database or a
  server, and no state was written anywhere. Every claim is reproducible from the listed
  `path:line` citations plus the probe.

## 12. Method: the passes that ran

Three passes, from three entry points, all by reading (the artifact's floor is three passes; one
rater is not a measurement):

1. **API client with no UI** — the committed contract (`docs/openapi.json:5858-5969`), the
   controller and service, the domain schemas, and the call-site set difference (the probe plus my
   wider search across both clients). Produced F3, F4, F5, F7, F17.
2. **The operator who does this daily** — the list, the filters, the table, the per-row modal, the
   counts, the redirects: what the row tells them and what survives their next action. Produced
   F2, F6, F8, F9, F16.
3. **The first-time user** — the invite form, the locked surfaces, the empty state, the error path,
   the confirmation step. Produced F1, F10, F11, F12, F13, F14, F15.

The probe's output joined all three: it is the `route` column of matrix 1 and the evidence behind
F3 and F4, and it is the same set difference pass 1 arrived at by hand — in this feature the probe
and the reading agreed row for row, and the probe confirmed two rows a reading might have written
off as "probably used by mobile": it was not.
