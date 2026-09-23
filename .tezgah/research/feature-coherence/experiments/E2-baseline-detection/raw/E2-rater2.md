# Product analysis - Ustam admin panel, "users" area (route `(dashboard)/users`)

Rater: E2-rater2. Session date: 2026-09-20. Repo under analysis: `/Users/rizax/Projects/Ustam`
(read-only; nothing in it was modified). Rubric: `skills/product-analysis/SKILL.md`, with
`skills/analyze-app/SKILL.md` and `skills/research/SKILL.md`.

**Rater count: 3 passes, one rater.** P1 default/mouse path at 1280 (platform-owner persona),
P2 keyboard-only persona (real `Tab`/`Enter`/`Escape` events, focus order and focus rings), P3
narrow-viewport + fault persona (320/390/768, 200% text, long-text probe, bad session token).
The skill asks for 3-5 *independent evaluators*; a single agent is one rater, so this is
three passes by one rater, not a panel, and severities are one rater's.

## 0. Which tool path was taken (analyze-app fallback clause)

The `browser_*` Playwright-MCP tools are **not** mounted in this session. `analyze-app` names
the fallback as the pinned CLI (`npx -y @playwright/mcp@0.0.81 --isolated --caps=testing,storage,network`).
I did not run that: an equivalent in-process Playwright is exposed by the harness
(`browser.open()` → tab with `ariaSnapshot`/`screenshot`/`evaluate`/`goto`, plus raw
`page` and `page.keyboard`/`page.cookies`/`page.setRequestInterception` through `tab.run`).
That is the path every `ui-observed` finding below came from, and it is re-runnable.
Consequence to be honest about: `browser_verify_text_visible` and friends do not exist here,
so "this control is not present" claims are assertions I ran in the page, not MCP verifications.

**Environment fix that matters for re-runs.** Loading the app at `http://127.0.0.1:3000` left the
document un-hydrated in the browser: the initial navigation logged 8× `403 (Forbidden)` on
`/_next/static/chunks/*.js`, and the trigger's `click` never reached React
(`document.querySelector('dialog.adminModal').open === false` after a real click, twice).
The same chunk URLs return `200` to `curl` and to a plain in-page `fetch`; re-loading the same
app at `http://localhost:3000` produced no 403 and a hydrated page (main-world probe:
`TURBOPACK=object`, 2 `__react` fiber keys on the trigger, dialog opens on click).
This is a dev-server/origin artifact of the shared dev server on :3000, **not** a product
finding, and every interactive result below is from the `localhost:3000` load. (Also visible in
captures: a dark circular "N" badge over the sidebar's Çıkış button - the Next.js dev-tools
overlay, not product UI.)

Credentials used: `platform@servistek.test` / the seed password (`apps/api/prisma/seed.ts:1489`).
The panel admits only `SUPER_ADMIN` (`apps/admin/app/api/session/sign-in/route.ts:17,33`); the
seed's only platform-owner membership is in the `PLATFORM` org (`apps/api/prisma/seed.ts:165-171`,
`210-216`). No mutation was performed on the demo database (see §5, "not looked at").

## 1. Measurement readiness - the gate first

`behaviour`-class evidence: **none obtainable.** No analytics, dashboard, cohort or log access
was available in this session, and I found none in the paths I read; the only numbers the
feature itself renders are the count line and the page's own copy. There is therefore no ratio,
window or denominator for this feature from inside the product. Crash reporting exists
(`apps/admin/lib/observability-runtime.ts` via `app/(dashboard)/error.tsx:14-16`) but is not a
product metric. Everything below is `ui-observed`, `code` or `external`; the value axis is a
hypothesis, and it says so.

The feature **is** observable by driving it (P1-P3 below), so this is "no telemetry", not
"cannot see the product".

## 2. Objective - Goal → Signal → Metric

- Goal: a platform operator can give a tenant's staff the right access, and take it away again,
  without engineering involvement.
- Signal: an operator completes an invite or an access change on this screen, and sees it in the list.
- Metric (proposed, and absent today): *share of sessions on `/users` that reach a confirmed
  success notice* = sessions with `?result=user-invited|user-updated` (page.tsx renders the
  notice from those params, `page.tsx:86`) ÷ sessions that open `/users`, over 7 days.
  A ratio needs a denominator; today the screen's own copy is the only ratio present
  ("1 kullanıcıdan 1 kayıt gösteriliyor", `page.tsx:163-166`), and it has no goal above it.
- By the skill's own rule, a metric with no goal above it is dropped: I am recording the chain
  above as the missing one, not as a measured result. **No behaviour-class claim is made.**

## 3. Opportunities (needs, not features), with evidence class

| Opportunity (a need) | Class | Citation |
|---|---|---|
| A platform operator needs to grant or revoke **a tenant's** user access; today the panel's only user is the platform owner, so the need has no surface | `code` | `apps/api/prisma/seed.ts:87-90` (comment: "Panelin tek kullanıcısı platform sahibidir"), `:210-216` (single platform membership); `apps/admin/app/api/session/sign-in/route.ts:17` |
| The operator needs to know *why* an option is unavailable before committing, not after | `ui-observed` | P1: the invite role select offers one option (`SUPER_ADMIN=Platform sahibi`) and the refusal arrives only after the confirmation dialog is confirmed (§5, F1) |
| The operator needs to see a row's full access decision without horizontal scrolling | `ui-observed` | measured at 1280/768/320 (§5, F3) |

Three candidate solutions, compared against a criterion stated **before** comparing:
*criterion - a platform operator can grant or revoke a tenant user's access in ≤3 steps, from the
UI, without a code change, and the result is visible in the list.*

1. Make the list organization-switchable for `SUPER_ADMIN` (the API is already org-scoped by
   `auth.organizationId`, `apps/api/src/users/users.service.ts:22-24`); the screen changes, the
   API does not. Meets the criterion; highest effort.
2. Data-only fix: seed a `SUPER_ADMIN` membership in org A (`seed.ts:165-171` already creates
   `admin@servistek.test` as `ORG_ADMIN`). Makes the existing screen demonstrably work today,
   but gives an operator no tenant choice. Meets "≤3 steps" only for org A.
3. Let tenant admins into the panel for this route (widen `adminRoles`, `sign-in/route.ts:17`,
   and the surface disposition). Meets the criterion for tenants, but contradicts the shipped
   decision that the panel is platform-only (`seed.ts:88-90`) and needs an auth-model review.
   Cheapest to build, highest product risk.

**Recommendation (a bet, §9):** 1, with 2 as the immediate unblock; 3 explicitly declined on the
seed's own stated product decision.

## 4. Risks by class, each with its cheapest falsifier

| Class | Risk | Cheapest test that would falsify it |
|---|---|---|
| Value | The screen's job is done elsewhere (mobile app / provisioning script), so the panel screen is dead weight | Count sessions that reach a success notice (§1) - needs telemetry that does not exist yet |
| Usability | The invite can never succeed for this account | *Already falsified as a failure*: one attempt, one refusal, P1 (§5 F1) |
| Viability | `SUPER_ADMIN` is not assignable from this screen by design, so the only role the platform org has can never be granted | Read `users.service.ts:337-347` + the platform org's single role row; done, this is the finding |
| Feasibility | The list clipping is cosmetic only | Measure `.tableWrap` client vs scroll width at 1280 - done: 924 vs 1140 (§5 F3) |

## 5. Usability section

**Scope.** Task: *find a user, then grant or change their access* (invite; row-level update).
Section: `/users` and its shared components (`AdminActionForm`, `AdminModal`,
`ConfirmationDialog`, `MutationNotice`). Device: desktop-first web; breakpoints 320 / 768 / 1280
(full sweep) plus 390 in the app's own e2e. Light mode, dark mode (`prefers-color-scheme: dark`),
200% text. WCAG claimed: **AA** (nothing in the source names a level; that absence is itself a gap).

### State matrix (component × state)

Interactive components - `+` exists and was driven; `-` does not exist; `?` not driven.

| Component | default | hover | focus | active | disabled | loading | error |
|---|---|---|---|---|---|---|---|
| "Takım üyesi davet et" trigger (`page.tsx:85-90`) | + | + (CSS, not separately captured) | + 3px `rgb(20,95,192)` ring | + | - (no `disabled` passed; not needed for this job) | - | n/a |
| Invite form fields Ad/E-posta/Rol/Kapsam (`page.tsx:91-127`) | + | n/a | + ring on each | + | - | + ("İşlem kaydediliyor…" via `AdminActionForm:121-125`) | + native + server (§ below) |
| Invite role select | + (1 option) | n/a | + | + | - | - | + refusal after confirm |
| ConfirmationDialog (`ConfirmationDialog.tsx`) | + | + | + (autofocus on Vazgeç) | + | - | - | n/a |
| Modal close ✕ (`AdminModal.tsx:151-158`) | + | + | + | + | - | - | n/a |
| Filter search / state select / Filtrele / Filtreleri temizle (`page.tsx:141-162`) | + | + | + ring | + | - | - (plain GET form) | - |
| Table scroll region (`page.tsx:167`) | + `tabindex=0` | n/a | + ring | + | - | - | n/a |
| Per-row "Erişimi düzenle" / "Yeniden etkinleştir" (`page.tsx:207-232`) | **unreachable** in shipped data | - | - | - | - | - | - |

Data views - the table, and the empty/loading/error states.

| View | empty | loading | skeleton | error | offline | partial | long-text | permission-denied |
|---|---|---|---|---|---|---|---|---|
| User list | + `page.tsx:288-290`, driven at `?q=zzzz` and `?state=inactive` | + `app/(dashboard)/loading.tsx`, observed at `/users` | + (same file; captured) | boundary exists `app/(dashboard)/error.tsx`, e2e-covered (below), **not driven by me** | not applicable (server-rendered; the page's data fetch is server-side) | - (no partial state; API returns `page.nextCursor: null`, `users.service.ts:64`) | + probe, F15 | code path exists `page.tsx:46-56`, **unreachable** (panel is SUPER_ADMIN-only) |

Three states that do not exist and are findings: **no partial/pagination state** (the API hard-codes
`nextCursor: null, hasNextPage: false`, `users.service.ts:64`, while the screen filters whatever
came back, `page.tsx:60-65`); **no route-level error state** (only the shared dashboard boundary);
**no permission-denied state reachable** through any account that can open the panel.

### Findings (screen / component / state / property), severity 0-4 = frequency × impact × persistence

Each is `failure` (reproducible) or `judgement` (heuristic read in context). Citations name the
tool call + state for `ui-observed`, or `path:line` for `code`.

**F1 - Invite has no assignable role: the feature's only mutation can never succeed. Severity 4,
`failure`, `ui-observed`.** P1: opened `/users` (localhost:3000) → clicked the trigger → the role
select's only option is `SUPER_ADMIN` = "Platform sahibi" (read: `Array.from(select.options)` →
`["SUPER_ADMIN=Platform sahibi"]`), scope defaults to "Atanan kayıtlar" (`assigned`). Filled
Ad="Rater Probe", E-posta=`platform@servistek.test` → submit → confirmation "Davet oluşturulsun mu?"
→ confirm → the form returned **"Platform sahibi bu ekrandan atanamaz."** and no navigation.
Code side (both sides cited, so this is also a feasibility finding): the select is built from
`GET /users/roles` (`page.tsx:108-120`; `UsersService.listRoles` `users.service.ts:69-76` returns
*every* role of the caller's org, including `SUPER_ADMIN`), while the action refuses exactly that
key (`actions.ts:71-72`) and the service refuses it again (`users.service.ts:336-338`).
In the platform org the seed creates only that one role (`seed-role-permissions.ts:67-70`), so the
form has one option and it is the forbidden one. The refusal is only discoverable after a
confirmation step, and the select gives no disabled/hint state.

**F2 - The list has one row and that row cannot be edited: the update half of the feature has no
subject. Severity 4, `ui-observed` + `code`.** P1: table renders exactly 1 row
(`platform@servistek.test`), whose action cell is the paragraph "Platform sahibi erişimi bu
ekrandan değiştirilmez." (`page.tsx:205-206`); no "Erişimi düzenle" / "Yeniden etkinleştir"
control is rendered anywhere (`document.querySelectorAll("tbody button").length === 0`). The seed
states the reason (`seed.ts:87-90`) and creates exactly one membership in the platform org
(`seed.ts:210-216`). The screen is written for a tenant-shaped list (permission-driven gate
`page.tsx:44-50`, membership/reactivation branches `page.tsx:207-221`) that this account can never see.

**F3 - The table's last column is cut off at every width. Severity 3, `failure` (measured),
`ui-observed`.** At 1280×900: `.tableWrap` client 924 vs scroll 1140, `table` width 1140, cell
widths `[134,197,72,132,163,64,379]`, last cell right edge 1443 > viewport 1280. At 768: client
686 vs scroll 1140. At 320: client 242 vs scroll 1140. Pixel read of `/tmp/r2-users-light-1280.png`
(vision, same capture) agrees and shows the row's last cell ending mid-word at "…erişin"; the
screen gives no scroll affordance (no fade, no "scroll for more", and the scrollbar is not
visible in the capture), so the operator cannot tell that content exists.

**F4 - The state filter keeps showing a stale value after "Filtreleri temizle". Severity 2,
`failure`, `ui-observed`.** P1 repro: select "Pasif" → "Filtrele" (URL `?q=&state=inactive`, 0 rows,
empty state shown) → click "Filtreleri temizle" (URL back to `/users`, 1 row) → the select still
reads "inactive" while the list shows all users. A fresh load of `/users` reads `""` (Tümü), so the
stale value comes from the client-side navigation not resetting the uncontrolled select
(`defaultValue`, `page.tsx:150`); the control then lies about the active filter.

**F5 - Two columns print the same word for different facts. Severity 2, `judgement`, `ui-observed`.**
The row shows "Aktif" in **Durum** (a user-status badge, `page.tsx:199-203`) and "Aktif" in
**Üyelik** (membership active, `page.tsx:192`). The header words carry the distinction; the values
do not. Read once; the same read appears in the 1280, 768 and dark captures.

**F6 - At 768px the navigation eats the first screen. Severity 2, `judgement`, `ui-observed`.**
`/tmp/r2-users-768.png`: the sidebar renders as a full-width two-column block ~490px tall, the
page's breadcrumb starts at y≈555, and no "Menüyü aç" button is shown at that width (measured:
`display:none` at 1280, `flex` 105×44 at 320). Content begins below the fold on a common tablet width.

**F7 - Dialog focus starts on the ✕, not on the first field. Severity 1, `judgement`,
`ui-observed`.** P2: focus the trigger, `Enter` → dialog opens with `document.activeElement` =
the close button (`aria-label="Pencereyi kapat"`), which is also the first Tab stop. Tab order
inside the dialog is otherwise correct and wraps (`✕ → Ad → E-posta → Rol → Kapsam → Davet oluştur → ✕`),
and a real `Escape` closes it and **returns focus to the trigger** (verified).

**F8 - The error summary is styled like an input, and stale errors survive into the confirmation.
Severity 2, `judgement`, `ui-observed`.** The refusal screenshot shows the server error inside the
same bordered box that carries the 3px focus ring (the feedback div is `tabIndex=-1` and is focused
on error, `AdminActionForm:84-88`), so an alert reads as an editable field. In the confirmation
screenshot the previous submit's field errors are still listed behind the confirmation dialog
(they are only cleared when the action runs, `AdminActionForm:169`), and the confirmation overlays
the modal with no dimming between the two layers - two bright surfaces, one border.

**F9 - The column is titled as an action but mostly holds prose. Severity 1, `judgement`,
`ui-observed`.** Header "Yetki güncelle" (`page.tsx:178`) over a 379px cell whose only reachable
content is a sentence (`page.tsx:205-206`). The column promises a control in this data state and
delivers an explanation.

**F10 - Feasibility: the copy contract says this screen is outside the menu; the app says it is in
the menu. Severity 2, `code` (both sides cited).** `apps/admin/lib/admin-visible-copy.contract.test.ts:94-98`
allow-lists `app/(dashboard)/users/page.tsx` with the rationale *"Tenant user screen; outside the menu"*,
while the surface registry holds `{ href: '/users', label: 'Yöneticiler', disposition: 'platform', group: 'Platform', permission: 'user.manage' }` (`lib/admin-surfaces.ts:101-106`) and the
running sidebar renders "Yöneticiler" under **PLATFORM** and links to `/users` (P1 tree). The
allow-list entry survives on a false premise.

**F11 - Feasibility: the panel gate and the screen's own permission model are two different models.
Severity 2, `code`.** The app's sign-in route hard-codes `const adminRoles = new Set(['SUPER_ADMIN'])`
(`app/api/session/sign-in/route.ts:17`, used at `:33`) - the API has the same rule in one place
(`apps/api/src/auth/auth.service.ts:39`), the admin app restates it locally. The screen itself is
permission-driven (`canUseAdminMutation('team.invite'|'team.update', …)` → `user.manage`,
`lib/mutations.ts:29,33`) and renders tenant-shaped copy plus a locked-surface branch
(`page.tsx:46-56`) that **no account can reach**. Two readings of "who may manage users" that cannot
both be exercised.

**F12 - Feasibility: reactivation is done by the path the comment says it is not. Severity 2,
`code`.** `actions.ts:79-81` comments "Reactivation is a separate API operation" and then builds
`{ active: true }` for the ordinary `PATCH /users/{id}`; the API does ship a separate operation -
`POST /users/{id}/deactivate` (204, `users.controller.ts:82-88`) - which the admin never calls, and
which only deactivates. `UsersService.update` carries its own guard for the reactivation case
(`users.service.ts:143-149`), so the behaviour is right, but the comment and the endpoint layout say
otherwise.

**F13 - Long display names and e-mail addresses stretch the table instead of wrapping. Severity 3,
`ui-observed`, probe.** *Declared probe:* text was injected into the rendered cells (not app data) to
reach the long-text state. With a 51-char name and a 74-char address, `table.scrollWidth` goes from
1140 → 2029 in a 924px window; `white-space` computes to `nowrap` and `overflow-wrap: normal`
(name cell 419 wide, e-mail cell 595). The layout has no truncation strategy, so real long addresses
push the last column further out of view than F3 already does.

### Reading the image (what the tree cannot answer)

Captures read (each `page.screenshot`, path returned, and looked at):
`/tmp/r2-users-light-1280.png`, `/tmp/r2-users-320.png`, `/tmp/r2-users-768.png`,
`/tmp/r2-users-dark-1280.png`, `/tmp/r2-users-gray-1280.png`, `/tmp/r2-users-blur-1280.png`,
`/tmp/r2-modal-invite-1280.png`, `/tmp/r2-confirm-1280.png`, `/tmp/r2-invite-refusal-1280.png`,
`/tmp/r2-longtext-1280.png`, `/tmp/r2-error-state.png`, plus the loading frame.

- **Blur test** (5px on `main`, 1280): the full-width green "Takım üyesi davet et" bar is the
  first thing that reads; the H1 "Yöneticiler" and the card heading "Kullanıcılar" follow. The
  primary action is findable without reading - pass. Run once.
- **Grayscale test** (1280): hierarchy survives - the CTA stays the heaviest block, the sidebar
  stays a distinct column, the active nav chip stays distinguishable by value. The two "Aktif"
  chips lose the colour that distinguishes them from neutral chips, but the word itself carries
  the meaning, so nothing semantic is lost - pass, with that nuance. Run once.
- **Dark mode** (`prefers-color-scheme: dark`, light theme shown as `data-theme=SYSTEM`):
  the shell and card invert correctly; the CTA stays legible; the active nav chip inverts to a
  pale mint pill with dark text. Hierarchy is flatter than light mode but nothing becomes unreadable.
- **200% text** (root font-size 32px, a probe on the rendered page): the table's scroll width grows
  924→1943 and the toolbar wraps; nothing is lost, but the horizontal scrolling of F3 roughly doubles.
- **Tree vs pixels, one case worth naming:** `axe-core` returns 19 `color-contrast` nodes as
  `incomplete`, all in the shell (brand, nav group labels, nav links). A computed-style chain walk
  cannot resolve them because the sidebar paints its dark surface as a gradient/image, not a
  background colour (every ancestor reports `rgba(0,0,0,0)`), which is exactly why axe also could
  not. The pixel read of the 1280 capture resolves them: white `rgb(255,255,255)` and
  `rgb(174,196,183)` text on a near-black green surface - readable, no failure claimed. My first
  computed ratio for those nodes (1.07-2.03) was an artifact of my own script defaulting to a white
  backdrop and is **withdrawn**.

### Automated sweep and its gaps

`axe-core` **4.10.2**, fetched from the registry as a pinned tarball
(`npm pack axe-core@4.10.2`, unpacked at `/tmp/axepin/package/axe.min.js`, 2026-09-20) and injected
in-page; run twice (once on the `127.0.0.1` load, once on the `localhost` load).
Result on `/users` at 1280: **0 violations**, 47 passes, 43 inapplicable, 19 `incomplete`
(`color-contrast`, shell only). axe's own figure is that it finds ~57% of WCAG issues; the named
blind spots I hand-checked: focus appearance (measured, 3px ring, present and visible on both
light and dark surfaces), target size (measured, smallest interactive control 64×44 CSS px,
above the 24×24 floor of SC 2.5.8), and text spacing (200% probe above). Not hand-checked:
dragging, accessible authentication, and any criterion needing a real assistive technology.

### WCAG 2.2 level

**Claimed: AA** (by me, because the product states none anywhere I read). What I could measure is
clean: contrast of every text run in `main` above threshold (minimum 5.47 for 16px `muted`),
target sizes above 24×24, visible focus rings, `aria-busy`/`role="status"` on the shared loading
state, `lang` attribute (not verified), table caption present (`srOnly`, `page.tsx:169`), scroll
region labelled (`page.tsx:167`). The unverified remainder is exactly axe's `incomplete` set plus
the AT-dependent criteria.

### Cognitive walkthrough (task: "give this new colleague access")

| Step | Four questions (Whitton et al.) | Verdict |
|---|---|---|
| 1. Open `/users` from the panel | right effect? yes, "Yöneticiler" is in the PLATFORM group; notice? yes; associate? yes; progress? the list renders | pass |
| 2. Filter to the person | right effect? yes; notice the toolbar; associate "Ad veya e-posta ara"; progress (count line changes) | pass |
| 3. Pick the row's access action | **fail: for the only row in the shipped state the cell answers with prose, not a control** (F2) | finding |
| 4. Choose a role and submit | right effect? yes; notice the select; associate? **the only option is refused (F1)**; progress: the confirmation appears, then a refusal | finding |
| 5. Confirm and see the change | progress? **never: the refusal is the terminal state for this account** | finding |

## 6. Feasibility - intended vs implemented, cited

| Intended behaviour | Code that implements it | Verdict |
|---|---|---|
| Only roles the org can assign are offered | `page.tsx:108-120` (renders `GET /users/roles`) + `users.service.ts:69-76` (returns all org roles) | **drift**: `SUPER_ADMIN` is offered and refused (`actions.ts:71-72`, `users.service.ts:336-347`) - F1 |
| Access changes are permission-gated | `page.tsx:44-50`, `lib/mutations.ts:29,33`, `actions.ts:58,75` (`requireAdminMutation`) | implemented; unreachable for any account that can sign in - F11 |
| Global profile fields stay self-service | `users.service.ts:325-331` rejects `displayName`/`locale`; the screen says so in its count line (`page.tsx:164-165`) | implemented, consistent |
| Reactivation is a separate operation | comment `actions.ts:78-79` vs `actions.ts:80-81` (PATCH) vs `users.controller.ts:82-88` (dedicated endpoint, unused) | **drift** - F12 |
| List is complete and stable | `users.service.ts:64` hard-codes `nextCursor: null, hasNextPage: false`; `page.tsx:60-65` filters client-side; `users.service.ts:28` orders by `displayName` | implemented for small orgs; no pagination state exists |
| A data failure shows a recoverable error | `app/(dashboard)/error.tsx` (shared boundary) + `AdminSurfaceErrorView`; `/users` is in the fault-proxy probe list (`e2e/admin-state-recovery.e2e.ts:8,55-77`) | implemented and e2e-covered; **I did not reproduce it** |
| Narrow widths do not break the page | `e2e/admin-state-recovery.e2e.ts:98-107` asserts `documentElement.scrollWidth - innerWidth <= 1` | **the assertion cannot see F3**: the overflow lives *inside* `.tableWrap`, so the document never overflows and the suite passes while the last column is cut |
| Super-admin membership cannot be granted from the panel | `users.service.ts:340-347` | implemented; the UI's only offered role is the one it forbids - the two truths make the screen dead |

## 7. Competition

**Not covered, and why.** The skill requires a comparison basis stated before comparing, and every
competitor fact to carry its artifact URL and the date read. I read no competitor artifact in this
session (no vendor/admin-UI page, no review corpus, no pricing page), so any "compared with X"
sentence would be a framework named without its artifact - the first failure mode the skill lists.
What is needed to close it: pick 2-3 representative admin user-management surfaces (e.g. the
user/role screens of a workspace admin product and of a field-service product), state the basis
(feature density, steps-to-grant, revoke semantics), and record each URL with its read date. I
record this axis as **missing**, not as covered.

## 8. Triage - keep / fix / cut / bet

| Feature (in this route) | Verdict | Deciding metric | Threshold | Timeframe | Action | Flag | Owner |
|---|---|---|---|---|---|---|---|
| Invite a team member | **fix** | share of invites reaching the success notice = `?result=user-invited` sessions ÷ invite submissions | today 0/1 attempts fail (F1); target 100% of submissions with an assignable role offered | before the next demo | filter the role list to what `team.invite` may assign, or disable the trigger with the reason visible | `team.invite` + `SUPER_ADMIN_PROVISIONING_REQUIRED` | Platform panel owner |
| Per-row access update | **bet** | share of list rows carrying an actionable control | today 0 of 1 rows (F2); bet pays off when the first tenant-scoped list shows ≥1 editable row | 1 sprint | build the org switch (candidate 1), keep the seed fix (candidate 2) as the interim | `user.manage` scope decision | Platform owner + panel owner |
| Search + state filter | **keep** | filter round-trip success | empty state and 0-row count verified at `?q=zzzz` and `?state=inactive` | - | keep; fix only the stale select (F4) | `page.tsx:141-162` | Admin UI owner |
| Permission-denied locked surface | **cut** | is it reachable at all | unreachable for every account that can open the panel | now | delete the branch or make the model reachable; do not keep a state no user can enter | `page.tsx:46-56` | Platform panel owner |
| "Yetki güncelle" as a column | **fix** | last-column visibility at 1280 with a 74-char address | today clipped at 1280 (F3) and 2029px wide under F13 | next patch | per-row action or wrapping, plus a scroll affordance | - | Admin UI owner |

"Everything is important" is avoided: two of five rows are fix, one is a bet, one is keep, one is cut.

## 9. Findings, most severe first (all classes and citations above)

F1 severity 4 `ui-observed` · F2 severity 4 `ui-observed`+`code` · F3 severity 3 measured `ui-observed`
· F13 severity 3 probe `ui-observed` · F4 severity 2 `ui-observed` · F5 severity 2 `judgement` ·
F6 severity 2 `judgement` · F8 severity 2 `judgement` · F10 severity 2 `code` · F11 severity 2 `code` ·
F12 severity 2 `code` · F7 severity 1 `judgement` · F9 severity 1 `judgement`.
**13 findings: 3 `failure` (F1, F3, F4), 9 `judgement` (F5-F9), 4 `code`-anchored feasibility items
(F10-F12, plus the code half of F2).** No `user-verbatim` and no `behaviour` finding exists in this
session - both are recorded as absent, not as zero-severity.
Also carried as questions rather than findings, because one evidence class is missing:
(a) the error surface content at `/users` (boundary exists, `code`; not reproduced);
(b) whether `lang="tr"` is set on the served document (not measured);
(c) whether any server-side rate limit protects `team.invite` in the panel context (not inspected).

## 10. Recommendations and their reference

| Recommendation | Who already does it best (cited) | What we adopt |
|---|---|---|
| Show only assignable roles, and explain the rule before the submit | WCAG 2.2 / Nielsen H5 error prevention - a control must not offer a value the system will reject; the product's own contract pattern (`admin-crud-coverage`) already asserts action coverage | filter `listRoles` by what the caller may assign; disable/hint the option |
| Keep one dialog per job (the `AdminModal` doc comment, `components/AdminModal.tsx:12-17`) and place initial focus on the first field | `ConfirmationDialog` already focuses Vazgeç knowingly - apply the same intent to the form | move initial focus to the first input |
| Make the scroll region discoverable, or remove the need to scroll | The app's own e2e asserts document-level overflow only (`admin-state-recovery.e2e.ts:98-107`); a container-level assertion is the fix | assert the last column's right edge ≤ container right edge at 1280 |

External references used, all read in this session via the skill text they are quoted from:
Nielsen's severity scale and 10 heuristics, WCAG 2.2 (SC 1.4.3, 2.5.8), axe-core's ~57% figure
(`https://github.com/dequelabs/axe-core`), the cognitive-walkthrough four questions
(Wharton et al. 1994; NN/g), Carbon's component-state checklist. I did not open these URLs directly
this session; they are cited through `skills/product-analysis/SKILL.md`, which is the artifact I read.

## 11. What this analysis did NOT look at, and what would change the recommendation

- **No mutation of the demo data.** I deliberately never completed a successful invite (F1 means it
  is impossible for this account anyway) and never deactivated the platform owner, because sibling
  raters share this live demo database and its "1 user" state. So the success path (redirect to
  `?result=user-invited`, `actions.ts:70-71`) and the row-level edit dialog are **unobserved**; their
  behaviour is inferred from `actions.test.ts`/`page.test.tsx` (311 lines, not run here) and the code.
  What would change the recommendation: a second user existing in the platform org - I would then
  drive the edit and reactivate dialogs and re-grade F2.
- **The error and permission-denied surfaces** were not reproduced (no fault proxy available to me,
  and the panel admits only `SUPER_ADMIN`). I also could not reach them accidentally: a bogus access
  cookie was silently repaired (307 → refresh hop → 200 with the full list, no error shown), which is
  itself a positive `ui-observed` result for session recovery.
- **Not inspected**: mobile app equivalents of these screens, the audit log's rendering of
  `user.invite`/`user.update` (`users.service.ts:130-136`), rate limits, `openapi.json`
  (docs/api-contract.md are outside my allowed reads), the shared `Observability` layer, i18n (the
  product is Turkish-only, so no length-overflow locale to test), SUS/UMUX-Lite (needs real users -
  recorded as *to be run*, never as a number I produced), and the competitive axis (§7).
- **Fixture caveats**: everything measured here is a running dev server on `:3000` with the seed
  corpus (`ServisTek Demo İstanbul` + `ServisTek Platform`), against the platform org, with the
  browser's own viewport. F13's long values are injected probe text, not data. The 200% text figure
  is a root-font-size probe, not a browser zoom setting.
- What would flip the triage: a telemetry layer (then the "invite share" metric becomes measurable
  and the bet gets a real threshold), or a product decision that tenant admins may enter the panel
  (then candidate 3 replaces the org switch and F11's drift becomes the fix).

## Scorecard (research-skill anchors: 5 nothing material missing, 1 not addressed)

| Dimension | Score | Anchor |
|---|---|---|
| Evidence relevance | 4 | every finding cites a tool call/state or `path:line`; two citations rest on my own probes, and I withdrew one computed ratio that my script, not the product, produced |
| Class discipline | 4 | one class per finding; `ui-observed` came from the running app; three items are demoted to questions rather than given a class |
| Depth | 4 | component × state matrix filled, properties measured (contrast, target size, scroll widths, focus rings); two states could not be driven |
| Image evidence | 4 | 11 captures read; blur and grayscale run once each; dark, 320, 768, 200% |
| Axis coverage | 3 | value/usability/feasibility/triage covered; competition explicitly missing |
| Metric integrity | 2 | the product has no metric with a goal above it; the chain is recorded as missing, no ratio is claimed |
| Solution plurality | 4 | three candidates against a criterion stated before comparing |
| Feasibility grounding | 5 | every implementation claim is a cited `path:line`; three drifts cite both sides |
| Decision quality | 4 | keep/fix/cut/bet with metric, threshold, timeframe, action, flag; owners are roles, not named people |
| Scope calibration | 4 | what was not looked at is stated with what would flip the verdict |

Mean **3.8 → weak accept** on the skill's own bands. The two low dimensions (axis coverage 3,
metric integrity 2) are properties of the product's missing measurement layer and the session's
lack of competitor access, reported rather than smoothed over; by the scorecard's rule no dimension
is below 3 except metric integrity at 2, and the mean sits in "weak accept".
