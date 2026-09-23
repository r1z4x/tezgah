# Product analysis - Ustam admin "users" surface

Blind pass 1 of 3. Scope: `/Users/rizax/Projects/Ustam/apps/admin`, route `(dashboard)/users`,
its server actions, the shared components and API endpoints it depends on. Everything below was
observed in this session (2026-09-20) unless it is marked `[INFERENCE]`, `[DERIVATION]` or
"question".

**Rater count: 1 rater, two passes plus one repeat pass.** Pass 1 learned the surface (list, filters,
invite modal, row modal). Pass 2 hunted violations over the same surface. A repeat pass re-ran the
three highest-severity findings in a fresh browser session (F1 twice, F3, F5). The skill asks for
three to five *independent* evaluations and states a single rater is too unreliable to be trusted for
severity; one agent is one rater, so every severity below is a single-rater severity and the mean of
three was not produced.

**Running-app path.** The Playwright MCP (`browser_*`) server is not wired in this session, so
`analyze-app`'s fallback applies. Instead of the pinned `npx -y @playwright/mcp@0.0.81` CLI I used
the harness's own real-Chromium device (`browser.open` + `page.evaluate`/`page.screenshot` from
`tab.run`), which gives the same evidence class - live DOM reads, in-page measurements, real
screenshots - but **not** `browser_verify_*`, so no UX claim below rests on a re-runnable Playwright
assertion; each one is either a measurement or a judgement, and each says which.

**Environment.** Two instances, both started this session:
- shared dev pair: admin `127.0.0.1:3000` + API `:3001` on the seeded dev database `servistek`
  (56 users; the platform organisation `…-0003` has exactly one member, so this pair renders a
  one-row list);
- my pair: admin `127.0.0.1:3500` + API `:3501` on a **clone** of that database (`e2r1_users`,
  `pg_dump`/`psql`, 62 users) with six fixture users added to the platform organisation. Every
  number below that is about list behaviour was measured on that fixture; the fixture rows are:
  `Kemal Usta` (active, scope `assigned`, TECHNICIAN), `Pasif Teknisyen` (inactive membership),
  `Çok Rollü Kullanıcı` (two roles, scope `own`), `Çok Uzun Görünen Adlı …` (long name),
  `İlknur Işık` (`status = SUSPENDED`, membership active), `Rolsüz Kullanıcı` (`status = INVITED`,
  membership with zero roles), plus the platform owner (`SUPER_ADMIN`). The clone is scratch; the
  Ustam tree and the shared dev database were not written to.

---

## 1. Measurement readiness (the gate)

**We cannot see this feature's behaviour in the running product.** The admin app has a telemetry
layer (`lib/observability-runtime.ts`, `lib/api.ts` records `api.request` per call) but it is inert:
`createAdminObservability` falls back to `new NoopObservabilitySink()` when no sink is passed
(`apps/admin/lib/observability.ts:33`), the admin runtime passes none
(`apps/admin/lib/observability-runtime.ts:11-16`), and the default consent is
`{analytics: false, diagnostics: false}` (`apps/admin/lib/observability.ts:36-39`). No admin product
event or trace is recorded anywhere, no analytics SDK is present, and no metric for this surface is
readable by anyone. Evidence class: `code`.

Consequence for the rest of this document: there is **no `behaviour` class evidence about real
usage** - no numerator, denominator or window from production. The only ratios in this document come
from my own fixture and are labelled as such. Every value claim below is therefore a hypothesis with
a named test, not a measurement of the product in use.

## 2. The objective

`[DERIVATION]` - no goal statement for this surface exists in the code I read, so this is the chain I
would hold it to, not a claim about the product's own targets.

- **Goal:** an operator can change any team member's access in one screen without a support
  round-trip and without ever granting more access than intended.
- **Signal:** the operator completes the change without leaving the screen and without a second
  attempt; no unintended access change is later reverted.
- **Metrics (ratios, with definition and window):**
  - access-change completion = sessions with a successful `PATCH /users/:id` carrying a `roleKey` or
    `active` change ÷ sessions that opened the per-row dialog, over 30 days;
  - access-change retry rate = sessions with ≥2 submissions for the same target user within 10
    minutes ÷ sessions with ≥1 submission, over 30 days;
  - revert rate = memberships whose role set is changed back within 7 days ÷ memberships changed,
    over 30 days;
  - invitation completion = invites whose email becomes an active membership within 14 days ÷
    invitations sent, over 14-day cohorts.
- Dropped by the rule "a metric with no goal above it is dropped": users-list page views, row count,
  invites sent (raw counts, and none of them sits under the stated goal).

**Not observable today:** every metric above. The first work item is not a UI change; it is making
the completion and revert signal exist (`api.request` is already classified per route in
`lib/api.ts:41,132-140`, so this is a sink and a consent decision, not new instrumentation).

## 3. Opportunities and candidate solutions

`[DERIVATION]` - no interview, ticket or review was available to me in this session (see section 11),
so each opportunity is stated as a **need** with the evidence I do have (my own walkthrough of the
running screen), not as a user quote.

| Opportunity (a need, not a feature) | Evidence class | Evidence |
|---|---|---|
| "I must be able to tell what access a change will leave behind, before it is applied" | `ui-observed` | the row dialog's confirmation summary is the only preview, and it showed a value the control no longer held (F1) |
| "I must be able to tell which of the two statuses I am looking at" | `ui-observed` | `Durum` and `Üyelik` disagree on the same row (`İlknur Işık`: Askıya alındı / Aktif); only `Üyelik` is filterable (F3) |
| "I must not be offered an action that will be refused" | `ui-observed` | the role list offers `Platform sahibi`; the action refuses it with an in-form alert (F2) |
| "I must be able to find a person in a list that will grow" | `code` | search runs in memory over the whole org membership set, and the endpoint has no page size (`users.service.ts:26-64`, `page.tsx:59-66`) |

Three candidate solutions per the skill's rule, compared against one pre-stated criterion: **the
cheapest change that removes the need without adding a screen**. The criterion was stated before I
looked at the three; they are ranked against it, not scored against each other.

| Solution | Against the criterion |
|---|---|
| S1 - make the row dialog's preview read the control's live value and echo the *resulting* role set ("Teknisyen → Salt okunur") | smallest diff, no new screen, removes the need for opportunities 1 and 3 |
| S2 - split "Durum" into one status column with the effective access spelled out, and add the missing states to the filter | medium diff, touches the API's list projection, removes opportunity 2 |
| S3 - server-side query + cursor pagination on `/users` and a server-side search field | largest diff, adds an endpoint contract, removes opportunity 4 only |

S1 is chosen for the findings section (section 10); S2 and S3 are kept as bets (section 8).

## 4. Risks, each with its cheapest falsifying test

| Risk class | Risk | Cheapest test that would falsify it |
|---|---|---|
| Value | access changes are rare enough that the screen's cost does not matter | count `api.users.patch` events over 30 days against the invitations sent; if the change rate is <1 per org per month the screen is over-built |
| Usability | operators get the wrong access applied because the preview is wrong (F1) | 5 operators, the real screen, one scripted task ("give Kemal read-only access"); count how many notice the summary says "Mevcut rolleri koru" - a wrong access change is the failure, not the extra click |
| Usability | the two status columns are read as one | same session, ask which of the two "Aktif" columns is the one being changed |
| Viability | a support ticket per wrong access change, and access changes are audited by the customer | sample 20 audit-log rows for `user.update` in the audit surface and count the reversals |
| Feasibility | the list cannot stay a whole-org fetch as tenants grow | take the largest tenant's membership count; if it exceeds ~200, the single-page fetch is the wrong shape (`users.service.ts:26-64` has no `take`) |

## 5. Usability

**Scope (narrowed as the skill requires).** One task family - *changing an existing member's access*
and *inviting a member* - on one section (`Yöneticiler`), one user group (the platform owner, the
only role the panel admits), web only, at 1440/768/320 px, light and emulated dark, largest text at
the browser default. Turkish (`tr-TR`) is the rendering locale. WCAG: no conformance level is
declared anywhere in the code I read; the level claim lives in `docs/design/*` documents that this
blind pass was instructed not to open, so I measured against **WCAG 2.2 AA** and report no declared
level.

**Heuristics checked** (Nielsen, with the severity scale 0-4): visibility of system status (F1, F5),
match between system and the real world (F3), user control and freedom (F1), consistency and
standards (F2, F4), error prevention (F2, F6), recognition rather than recall (F1), help users
recognise and recover from errors (F5), aesthetic and minimalist design (F8 note). Not checked:
flexibility/efficiency (no power-user path exists to judge), help and documentation (no help surface
reached this session), error-code diagnosis (no error codes are shown).

### State matrix

Rows are the interactive components and the data views of this one screen. "checked" names the states
I drove or read; "not reachable" names the states that do not exist or that this environment cannot
produce, with the reason.

| Component / view | States checked | States that do not exist / were not reachable |
|---|---|---|
| `Takım üyesi davet et` trigger | default, hover (CSS only, not driven), focus (native), active (native), opened dialog | `disabled` - the trigger has no disabled path in the page; `loading` - the client form owns pending, not this trigger |
| Invite form (Ad, E-posta, Rol, Kapsam) | default, empty-submit error (native constraint path), valid + confirm dialog, cancel (values preserved), server error shown as `role=alert`, `aria-invalid` + per-field messages | `disabled` (only via the shared pending state); `loading` = the shared "İşlem kaydediliyor…" line (not driven for this form); no field-level help text |
| Invite confirm dialog | open, summary rows, focus starts on `Vazgeç`, cancel closes only the confirm | none missing - this component is the most complete on the screen |
| Per-row `Erişimi düzenle` trigger | default, opened dialog | `disabled`, `loading` |
| Per-row edit form (Yeni rol, Kapsam, Üyelik) | default, confirm dialog with summary, submit → success, `Yeniden etkinleştir` variant (inactive membership) | **the "new role" control cannot take effect (F1)**; no error state of its own on the happy path; no "no role" option (only "keep current" or a role) |
| `Üyelik durumu` select in the row form | default `Aktif`, `Pasif — erişimi kaldır` | the `Pasif` option is absent on the operator's own row (self-guard) and the whole form is replaced on a SUPER_ADMIN row (protected text) |
| Filter toolbar (search, state select, Filtrele, Filtreleri temizle) | default, `?q=`, `?state=`, both, no-match empty state, `?state=bogus` (silently ignored → all rows) | `loading` (full-page GET, generic skeleton), `disabled`, server-side error of its own | 
| Users table (data view) | 1 row (dev seed), 8 rows (fixture), 0 rows with empty state, long-text row, empty cell (F4), 320/768/1440 widths | `loading` = the generic `(dashboard)/loading.tsx` skeleton (a line + one card block, not a table skeleton); `error` = the root error surface and the shell is lost (F5); `skeleton` rows: none; `offline`: none (server-rendered, no service worker - the browser's own offline page is what appears, `net::ERR_INTERNET_DISCONNECTED` reproduced); `partial`: none (one response, no partial rendering); `permission-denied` for the list: the code path exists but was **not reachable** - the panel sign-in admits only `SUPER_ADMIN` (`app/api/session/sign-in/route.ts:17,33`) |
| Row action cell | `Erişimi düzenle`, `Yeniden etkinleştir`, protected-text variant | a bulk-select/bulk-action state: does not exist |

### Findings, most severe first (usability axis)

**U1 - the per-row "Yeni rol" control silently discards the chosen role, and the screen reports
success.** Level: component × state. Screen: `Yöneticiler`, row dialog `Erişimi düzenle · Kemal Usta`
/ `· Çok Rollü Kullanıcı`. Severity **4** (frequency: every role change; impact: the operator
believes access changed when it did not; persistence: until someone reads the row again). Kind:
**failure** (reproducible, and the row it produces is wrong).
Read from: the running app, two passes, same result both times. Steps: open the row dialog → choose
`Salt okunur kullanıcı` in `Yeni rol` (the DOM value reads `VIEWER` immediately after and again 1.2 s
later) → `Erişimi kaydet` → the confirmation summary reads **"Yeni rol: Mevcut rolleri koru"** →
`Erişimi güncelle` → `?result=user-updated` and the notice "Takım üyeliği güncellendi." → the row
still reads `Teknisyen` and the database still holds `TECHNICIAN`. Second pass, a different user and
role: DOM `ACCOUNTANT`, summary "Mevcut rolleri koru", row unchanged (`TECHNICIAN, VIEWER`).
Code behind it: `page.tsx:249` (`<select name="roleKey" defaultValue="">`), the summary reading the
control at submit time `AdminActionForm.tsx:226,232-249`, and `actions.ts:82-86` which only sends
`roleKey` when the field is non-empty. The internal mechanism (which re-render returns the select to
its default) is a **question** - I did not instrument React to prove it; the user-visible behaviour
is not.

**U2 - the role list offers `Platform sahibi`, and the action refuses it.** Level: component × state.
Severity **3** (frequency: any invite that picks it; impact: a refused submit with text that names a
rule the form itself broke; persistence: until the option is removed). Kind: **failure**.
Read from: the running app. The invite `Rol` select offers `ACCOUNTANT, ORG_ADMIN, SUPER_ADMIN,
TECHNICIAN, VIEWER` (`page.tsx:106`), the row dialog offers the same set plus "keep current"
(`page.tsx:249-256`); submitting `SUPER_ADMIN` renders `role=alert` "Platform sahibi bu ekrandan
atanamaz." and the dialog stays open (`actions.ts:61` and `:87-88`), while the role list itself comes
from `/users/roles`, which returns the organisation's roles including `SUPER_ADMIN`
(`users.service.ts:69-74`).

**U3 - two status columns disagree, and only one of them is filterable.** Level: screen × state.
Severity **3** (frequency: applies to every non-ACTIVE user; impact: the filter's answer is not the
answer to the question the label asks; persistence: until the model or the labels change). Kind:
**failure** (a reproduced state, and the label is wrong about its own data).
Read from: the running app. `Durum` renders the user's account status (`page.tsx:187-189`), `Üyelik`
renders the membership's `active` (`page.tsx:200`); the filter compares only `membership.active`
(`page.tsx:64-65`), so `?state=active` returned 6 of 8 rows **including** `İlknur Işık`, whose
`Durum` reads `Askıya alındı`. The state select offers only `Tümü / Aktif / Pasif` (`page.tsx:152-155`),
so `Davet edildi`, `Askıya alındı`, `Devre dışı` and `Silindi` are not selectable.

**U4 - an empty roles cell renders blank, not the fallback the code intends.** Level: component ×
state. Severity **2** (frequency: any membership with no role; impact: an empty cell reads as a
rendering bug rather than "no role"; persistence: permanent). Kind: **failure**.
Read from: the running app (`Rolsüz Kullanıcı`, `Roller` cell blank) and the screenshot. Cause in
code: `page.tsx:192-193` - `roles.map(...).join(', ') ?? '—'` never reaches `'—'`, because an empty
array joins to `''`.

**U5 - with the backend down the screen loses its shell and shows the root error page, and the paste
never names the surface.** Level: screen × state. Severity **3** (frequency: every backend outage;
impact: no navigation, no retry that keeps the task, and copy that does not say which page failed;
persistence: until the API returns). Kind: **failure**.
Read from: the running app, API stopped for the duration of one load: HTTP 500 and the rendered text
"Sayfa açılamadı / Beklenmeyen bir sorun oluştu. Yeniden deneyin; olmazsa genel bakışa dönün ya da
çıkış yapıp yeniden giriş yapın." with `Tekrar dene`, `Genel bakışa dön`, `Çıkış` - that string is
`app/error.tsx:31-33`, i.e. the **root** boundary, not the dashboard one. `[INFERENCE]` the cause is
that the group layout fetches the session first (`app/(dashboard)/layout.tsx:12`), so the dashboard's
own error view (`app/(dashboard)/error.tsx:20-24`, different copy) cannot catch it. The root surface
has no `role="alert"` (my `[role=alert]` query returned nothing) and uses the `loginPage` card, so it
is also a full-page layout jump.

**U6 - the "suspect" status badge measures 3.16:1, below AA for its size.** Level: property.
Severity **3** (frequency: every non-ACTIVE row; impact: the state that matters most is the hardest
to read; persistence: permanent). Kind: **failure (measured)**.
Read from the page, computed styles: `.badgeWarn` = `color: rgb(135, 80, 0)` on
`color(srgb 0.955451 0.907137 0.84)` at `font-size: 12px, font-weight: 750` → contrast **3.16:1**
(my in-page computation, `?q`-read from the same capture); WCAG 2.2 SC 1.4.3 requires 4.5:1 at this
size (12 px bold is not large text). Every other pair I measured passes: `h1` 15.61, `h2` 16.63,
`p.muted` 5.47, `th` 5.83, `td` 16.63, `.badge` 14.5. axe-core left exactly this pair undecided
(section below), which is why it is hand-measured here.

**U7 - no dark rendering, and the OS preference changes nothing.** Level: screen × property. Severity
**2** (frequency: any operator on a dark OS; impact: the product's own `themePreference` field
promises a preference the admin surface does not honour; persistence: permanent). Kind: **failure
(measured)**.
Read from the page with `prefers-color-scheme: dark` emulated and a reload: `body` background stayed
`rgb(247, 248, 246)`, text `rgb(25, 32, 26)`, no theme class on `html`, `localStorage.theme` empty.
The API exposes a theme preference (`lib/admin-context.ts` `themePreference`), so this is a gap, not
an absence of the concept.

**U8 - the table is the whole list, so the screen's own scale story is missing.** Level: screen ×
state. Severity **2** (frequency: any tenant beyond one screenful; impact: the operator scrolls a
column-scrolling table with no page size, no sort control and no "N of M" beyond the count line;
persistence: until pagination exists). Kind: **judgement** (a heuristic read - "visibility of system
status" and "aesthetic and minimalist design" - in context; a one-page list is defensible at small
scale). Confidence: **single pass, not certain**.
Read from: the running app and the measurements - the endpoint has no `take` and declares
`page: { nextCursor: null, hasNextPage: false }` (`users.service.ts:26-64`), the page ignores `page`
and filters in memory (`page.tsx:59-66`), and at 320 px the table region scrolls 1689 px inside a
242 px box (`.tableWrap`).

**U9 - the loading state is generic and does not match the screen.** Level: screen × state. Severity
**1** (frequency: every navigation and every filter submit; impact: a flash of a line + a card block
where a table is coming; persistence: brief). Kind: **judgement**. Read from: the capture and the
code - `app/(dashboard)/loading.tsx:2-7` renders `Sayfa yükleniyor…` with `skeletonLine` and a
`skeletonBlock` card; `users/` has no `loading.tsx` of its own.

**U10 - one unidentified resource 404s on first paint.** Kind: **question**, not a finding: a console
error ("Failed to load resource: the status 404") was recorded during the first load of the dev
instance, and I did not capture the URL. Which resource, and whether it is the favicon, is unknown.

### The walkthrough (a task, from a new operator's position)

Task: *give an existing team member read-only access.* Four questions (Wharton et al.), answered from
the observed flow, one rater: 1. **Right effect here?** yes - the row carries `Erişimi düzenle`
(page.tsx:224-230). 2. **Will the operator notice the action?** yes, but it competes: eight rows ×
one trigger each, `variant="secondary"`/`small`, in the last column; the same word appears 8 times.
3. **Will they associate it with the effect?** partly - the dialog title repeats the person's name, so
the association is anchored (page.tsx:227); the *confirm* step then breaks it, because the summary
shows a value the operator did not choose (U1) - the walkthrough's step 4 fails here: **no, the user
cannot see progress is being made**, they see a summary that contradicts their input and then a
success message for a change that did not happen. 4. **Progress visible?** the pending line
("İşlem kaydediliyor…") and the `role=alert`/`role=status` feedback exist and were read in the run,
so for the invite flow the answer is yes; for the role change it is a false yes (U1). The single
"no" is U1, and it is the defect heuristics alone would rate as "works".

### Screenshots read (paths are the captures, and each was read, not just saved)

`shots/users-1440-loaded-full.png`, `users-1440-blur.png`, `users-1440-grayscale.png`,
`users-768.png`, `users-320.png`, `users-1440-dark.png`, `users-1440.png` (initial, caught the
loading state), `users-backend-down.png`. All under
`.tezgah/scratch/feature-coherence/shots/`. They were read through a vision query on the file, not by
pasting bytes into the transcript.

- **Blur test** (viewport 1440, blurred capture): the *table mass* still pulls first and the primary
  action does not - the invite button reads as a small faint pill and the page title loses its weight
  entirely. Failure of the test as stated ("does the primary action still read first?"): the largest
  element wins, not the action. Kind: judgement, one pass.
- **Grayscale test**: the hierarchy survives (fill and weight carry it: the active nav pill, the
  breadcrumb, the filled primary button), but the two `badgeWarn` states (`Askıya alındı`,
  `Davet edildi`) become indistinguishable from each other without their text - consistent with U6's
  colour measurement; no hue distinction to lose. Kind: judgement, one pass.
- **Vertical rhythm (from the loaded capture + geometry)**: the table starts at y≈498 in a 1000 px
  viewport - the header, the full-width invite button, the count line and the toolbar consume the
  first half of the screen before the first row. The invite button is the only saturated green
  element and spans the content width, so it dominates an action that is rare compared with reading
  the list. Kind: judgement (hierarchy from the image), supported by the measured `table.getBoundingClientRect().top`.
- **320 px**: the page itself does not overflow (scrollWidth = clientWidth = 320) and the toolbar
  stacks and stays usable; the table keeps its 1689 px width and scrolls inside `tableWrap`, which is
  focusable and labelled (`page.tsx:167`), so the cut-off columns are reachable - clipping is
  contained, not lost. Kind: judgement + measurement.

### axe-core sweep and what it cannot see

axe-core **4.10.3**, pinned build (sha256 `880970c081707360…`, 553,446 bytes fetched this session),
injected into the page from that pinned file and run over the rendered `/users` screen with the tags
`wcag2a, wcag2aa, wcag21a, wcag21aa, wcag22aa, best-practice`: **0 violations, 1 incomplete
(`color-contrast`, 38 nodes)**. The one contrast pair I measured by hand (U6) is exactly what axe
left undecided, which is the documented ~57 % coverage limit in practice. Hand-checked because axe
does not cover them: **target size** - 13 interactive controls measured, none below 24×24 CSS px
(WCAG 2.2 SC 2.5.8 passes at this sample); **focus appearance** - not checked (no `verify`-class tool
in this session, and I did not tab through the full focus order); **dragging** - not applicable;
**accessible authentication** - out of scope (the login screen is not this surface). The focus order
I did read runs skip-link → brand → menu button → sidebar items → page controls, in DOM order.

### Core Web Vitals

Measured in the page with `PerformanceObserver` on the loaded document: **LCP 516 ms** (good,
≤ 2500), **CLS 0** (good, ≤ 0.1). **INP not measured** - it needs real interaction timing at the 75th
percentile and was not produced; treat the two numbers as a single desktop-load sample, not a
distribution.

## 6. Feasibility (intended vs implemented)

Each row cites both sides when it claims a gap.

| Intended behaviour | What implements it (cited) | Gap |
|---|---|---|
| the list shows the organisation's members | `users.service.ts:26-47` (filter on `memberships.some.organizationId`, `orderBy displayName asc`), `page.tsx:59` | none - and it is org-scoped, which is why the shared dev seed (platform org, 1 member) renders one row |
| the list can paginate | `users.service.ts:64` returns `page: { nextCursor: null, hasNextPage: false }` | **gap**: the envelope exists, no `take`/`skip`/cursor parameter exists, and `page.tsx:58` (the `Response` schema is `page.tsx:13`) parses only `data` and ignores `page` - so the declaration is decorative |
| search narrows the list | `page.tsx:60-63` filters `allUsers` in memory with `toLocaleLowerCase('tr-TR')` | works (verified: `?q=KEMAL` and `?q=İLKNUR` both match); **gap**: the search is client-side over the full fetch, so it cannot narrow a list the endpoint did not send |
| a member without a membership shows "Üyelik yok" | `page.tsx:198,204` | **gap (dead branch)**: the query requires a membership in the caller's org (`users.service.ts:29`), so `user.memberships[0]` is always present and the two `'Üyelik yok'` branches cannot render; `membership: … ?? null` (`users.service.ts:56`) is likewise unreachable |
| an operator cannot remove their own access | `page.tsx:272-274` (`user.id !== context.id` hides the `Pasif` option) | **partly dead**: the row of a SUPER_ADMIN is replaced by the protected text first (`page.tsx:205`), and the panel admits only `SUPER_ADMIN` (`app/api/session/sign-in/route.ts:17,33`), so the self-guard only bites if the operator's own SUPER_ADMIN role was revoked mid-session - reachable, but not the case it was written for |
| `Platform sahibi` is not assignable here | `actions.ts:61` (invite), `actions.ts:87-88` (update) | the server refuses it, but the form offers it (U2) - the two readings of the rule disagree |
| a failed API call is reported | `lib/api.ts:119-127` (401 → session recovery; other non-2xx → `AdminApiError`), `actions.ts:20-46` (field-scoped messages), `AdminActionForm.tsx:277-281` (`role=alert`) | works for the invite path I drove; a 401 instead redirects to the session recovery path and the operator loses the form |
| the same mutation is retried safely | `AdminActionForm` supports `idempotencyKeyField` (`AdminActionForm.tsx:36,169-184`) | **gap**: neither `inviteUserAction`'s form nor the row form passes it (`page.tsx:80-135`, `:232-278`), so a double submit relies only on the in-memory `locked` ref |
| telemetry records the screen's behaviour | `lib/api.ts:132-140` records `api.<root>.<method>` events (`classifyApiRoute`, `lib/api.ts:41`) | **gap**: no sink (`lib/observability.ts:33`), consent off (`:36-39`) - section 1 |

## 7. Competition

**Comparison basis, stated before comparing:** *how many steps and how much confirmation a competent
admin tool requires to change one member's role, and what the tool does to prevent the operator from
locking themselves or the last owner out.* Units: steps to complete the change, and the presence of a
last-owner/self guard. Compared set: Slack (Help Center) and Google Workspace (Help Center). I read
two sources this session; a third was not reached, so the set is two and the generalisation is narrow.

| Competitor fact | Artifact | Date read |
|---|---|---|
| Changing a member's role is an owner/admin action; the doc warns "Proceed with caution when promoting members to owner or admin roles. Depending on your role, you may be unable to demote them later." - i.e. a demotion can be refused by the role model itself | https://slack.com/help/articles/218124397-Change-a-members-role | 2026-09-20 |
| Guest/Owner conversions are deliberately two steps ("you'll need to make them a regular member first, then promote them") | same | 2026-09-20 |
| "Only super admins can … Create and assign administrator roles", and "At least one user in your account needs to be a super administrator"; a User Management admin "can't assign administrator privileges … Only a super administrator can perform those tasks" | https://knowledge.workspace.google.com/admin/users/prebuilt-administrator-roles (page states "Last updated 2026-09-18 UTC") | 2026-09-20 |

Against our screen: our equivalent of Slack's role-list-does-not-match-your-authority problem is
handled *after* the fact - the option is offered and then refused (U2) - whereas Slack states the
rule before the action and Google simply does not offer the privilege to a non-super-admin. Our
last-owner protection is structural (`SUPER_ADMIN` row read-only) and matches Google's "at least one
super administrator" constraint in effect; our self-lockout guard is the dead branch noted in
section 6. What we would adopt and who owns it: (a) filter the role list by the operator's own
authority so a refused option is never offered - the API already knows the organisation's roles, and
`listRoles` is the place to narrow it (`users.service.ts:69-74`); (b) put the consequence sentence in
the dialog body, not only in the confirm step, the way both competitors do. **Review mining was not
done** (no review corpus was read), so "where the market is unhappy" is absent from this section.

## 8. Triage

Every feature on this surface ends keep, fix, cut or bet. The deciding metric is the one from
section 2; thresholds are pre-decided here and are `[DERIVATION]` - no owner has agreed to them.

| Feature | Verdict | Deciding metric, threshold, timeframe, action | Flag / owner |
|---|---|---|---|
| Users list (read) | **keep** | list-load failure ratio (5xx ÷ loads) < 0.1 % over 30 days; above it, the surface's error path (U5) is the work | `admin.users.list` / platform team |
| Invite a member | **fix** | invitation completion ≥ 70 % within 14 days of invite; below it, the form's role list and copy (U2) are the work | `admin.users.invite` / platform team |
| Per-row access change | **fix** (highest) | access-change revert rate ≤ 5 % of changes within 7 days **and** retry rate ≤ 10 %; a wrong applied change (U1) is a release blocker regardless of the ratio | `admin.users.update` / platform team |
| `Yeniden etkinleştir` | **keep** | reactivation completions ÷ clicks on the button ≥ 90 % over 30 days (it worked in the pass) | `admin.users.reactivate` / platform team |
| Status filter (`Aktif/Pasif`) | **fix** | filter sessions that produce a change to the list ÷ filter submissions ≥ 60 %; below it, either the labels or the states are wrong (U3) | `admin.users.filter` / platform team |
| Whole-org single fetch (no pagination) | **bet** | take the largest tenant's membership count; if > 200 within a quarter, build cursor pagination (section 6 row 2) | `admin.users.pagination` / platform team, review at quarter end |
| Dark mode | **cut** for now | no dark usage signal exists to justify it (and no signal exists at all - section 1); revisit only when a theme preference is honoured app-wide | none - deliberately unowned |
| Bulk action (select many rows) | **cut** | no evidence anyone needs it: the surface has no multi-row operation and the audit model is per-membership | none - deliberately unowned |

## 9. Findings, consolidated (severity first, each with class and citation)

| # | Finding | Class | Citation |
|---|---|---|---|
| 1 | The per-row role change is a silent no-op that reports success (U1) | `ui-observed` | running app at `127.0.0.1:3500/users`, two passes: DOM `roleKey` = `VIEWER`/`ACCOUNTANT` before submit; confirmation summary "Yeni rol: Mevcut rolleri koru"; notices "Takım üyeliği güncellendi."; row + DB unchanged. Code: `apps/admin/app/(dashboard)/users/page.tsx:249`, `apps/admin/components/AdminActionForm.tsx:226,232-249`, `apps/admin/app/(dashboard)/users/actions.ts:82-86` |
| 2 | The feature has no observable behaviour (section 1) | `code` | `apps/admin/lib/observability.ts:33,36-39`; `apps/admin/lib/observability-runtime.ts:11-16` |
| 3 | With the backend down the shell is lost and the surface's own error copy never renders (U5) | `ui-observed` | API stopped, `/users` → HTTP 500, rendered text = `apps/admin/app/error.tsx:31-33`; `app/(dashboard)/layout.tsx:12`; `app/(dashboard)/error.tsx:20-24` |
| 4 | `Platform sahibi` is offered and refused (U2) | `ui-observed` | role option list in the invite dialog (`page.tsx:106`) and the row dialog (`page.tsx:249`); refusal on submit, `role=alert` "Platform sahibi bu ekrandan atanamaz." (`actions.ts:61,87-88`) |
| 5 | Two status columns disagree; only one is filterable (U3) | `ui-observed` | `?state=active` → 6/8 rows including `İlknur Işık` / `Askıya alındı`; `page.tsx:64-65,152-155,187-189,200` |
| 6 | `badgeWarn` contrast 3.16:1 at 12 px (U6) | `ui-observed` | computed styles read in the page: `rgb(135, 80, 0)` on `srgb 0.955/0.907/0.84`, 12 px / 750; axe 4.10.3 left it `incomplete` |
| 7 | An empty roles cell renders blank, not `—` (U4) | `ui-observed` | `Rolsüz Kullanıcı` row in the capture and the screenshot; `page.tsx:192-193` |
| 8 | The list endpoint cannot paginate and the page ignores its envelope (U8) | `code` | `apps/api/src/users/users.service.ts:26-47,64`; `page.tsx:58,59-66` |
| 9 | The two `Üyelik yok` branches and the membership `null` are unreachable (section 6) | `code` | `users.service.ts:29,56`; `page.tsx:198,204` |
| 10 | The self-lockout guard is masked by the SUPER_ADMIN branch and the panel gate (section 6) | `code` | `page.tsx:205,272-274`; `apps/admin/app/api/session/sign-in/route.ts:17,33` |
| 11 | The loading state is the generic dashboard skeleton, not a table shape (U9) | `ui-observed` | capture `shots/users-1440.png` + `app/(dashboard)/loading.tsx:2-7`; `app/(dashboard)/users/` holds no `loading.tsx` |
| 11b | No dark rendering despite a theme preference in the model (U7) | `ui-observed` | `prefers-color-scheme: dark` + reload: body `rgb(247, 248, 246)`, no theme class, `localStorage.theme` null; `lib/admin-context.ts` `themePreference` |
| 12 | Invite/row mutation forms carry no idempotency key (section 6) | `code` | `apps/admin/components/AdminActionForm.tsx:36,169-184` versus `page.tsx:80-135,232-278` |
| 13 | Fixture-scoped shape of the list (8 members): 1 with no roles (1/8), 1 with an inactive membership (1/8), 1 suspended but membership-active (1/8), 1 SUPER_ADMIN (1/8) | `behaviour` (scope: `fixture`) | `e2r1_users` clone, membership rows for organisation `10000000-0000-4000-8000-000000000003`, read 2026-09-20; **these ratios are about my fixture, not about the product** |
| 14 | One unidentified 404 on first paint (U10) | `question` | console error recorded during the first load; the URL was not captured |

No `user-verbatim` finding exists in this pass: no interview, ticket or review was in my hands
(section 11). No `external` finding is claimed about our own product; the two competitor facts in
section 7 are `external` but describe Slack and Google, not Ustam.

## 10. Recommendations and their references

1. **Make the row dialog's preview truthful and echo the resulting role set** (fixes finding 1).
   Reference: both competitors state the consequence before the action, not after - Google's admin
   roles page names the privilege boundary in the role description itself
   (https://knowledge.workspace.google.com/admin/users/prebuilt-administrator-roles, read
   2026-09-20); Slack warns at the top of the role article (https://slack.com/help/articles/218124397-Change-a-members-role,
   read 2026-09-20). Adopt: the summary reads the live control and prints `Teknisyen → Salt okunur`.
2. **Narrow the assignable role list to what the operator may assign** (fixes finding 4).
   Reference: Google's page states the same rule as a capability boundary ("Only super admins
   can … Create and assign administrator roles"), i.e. the option does not appear for others. Adopt:
   filter in `listRoles`.
3. **Name one status, or name both and filter both** (fixes finding 5). Reference: no competitor
   artifact was read for this wording; it is a local decision, and the deciding test is in section 4.
4. **Raise `badgeWarn` to AA for 12 px text** (fixes finding 6). Reference: WCAG 2.2 SC 1.4.3
   (https://www.w3.org/TR/WCAG22/) - this is the one recommendation that does not need a competitor;
   it needs the measured ratio 3.16 → ≥4.5.
5. **Turn on a sink and a consent decision before optimising anything else** (fixes finding 2).
   Without it none of the triage thresholds in section 8 can ever be evaluated.

## 11. What this analysis did not look at, and what would flip it

- **Everything behavioural in production.** No analytics, no tickets, no interviews; the telemetry is
  inert (finding 2). A single real cohort of access changes would replace sections 2-4 with numbers.
- **The permission-denied state of the list itself.** The code path exists
  (`page.tsx:48-57`), but the panel admits only `SUPER_ADMIN` (`sign-in/route.ts:17,33`), so I could
  not render it. An account with `user.manage` absent *and* panel access would flip this row.
- **Real-user instruments.** SUS/UMUX-Lite were not run: they need real users, and the skill says the
  agent records them as *to be run*, never as a number it produced. Same for INP.
- **Two of the three to five independent evaluations the UX axis asks for.** One rater, two passes,
  one repeat pass. Severities are single-rater and the top finding's mean-of-three was not produced.
- **The `docs/design/*` documents.** They hold the surface's own WCAG and accessibility claims, and
  this blind pass was instructed not to open them. That is the one place a "declared level" could
  have come from; section 5 therefore reports no declared level.
- **Review mining and a third competitor.** Two help-centre pages were read; no review corpus and no
  product screenshots of competitors, so the competitive section is a rules comparison, not a
  teardown with process/cost dimensions.
- **Focus appearance.** Named by axe as one of its own gaps (with target size, dragging, accessible
  authentication); target size was hand-checked, focus appearance was not.
- **Non-users surfaces.** Nothing outside `(dashboard)/users` and the shared components it uses.

**What would flip the recommendations:** if the access-change revert rate turned out to be ~0 (no
wrong changes reach production), finding 1 drops from "release blocker" to a usability defect and the
triage's `fix` for the row change softens; if the role list were narrowed by the API tomorrow,
finding 4 becomes unreproducible; if any sink is enabled, section 8 stops being pre-decided
thresholds and becomes measurable.

## Scorecard (self-assessment, 1-5, anchors from the `research` skill)

| Dimension | Score | Why |
|---|---|---|
| Evidence relevance | 4 | every citation is a file read or a call made this session; section 1 and 13 mark the two places where a number is about my fixture rather than the product |
| Class discipline | 4 | one class per finding and the `question` rows are labelled as questions; the UX claims are `ui-observed`, not inferred from source, but no claim rests on a re-runnable assertion tool |
| Depth | 3 | component × state is filled for the components I could reach; permission-denied and a server-side error state of the list were not reachable, and properties are measured for contrast/type/targets but not for spacing rhythm |
| Image evidence | 3 | screenshots at 1440/768/320 + dark + blur + grayscale were taken and read; the 1440 dark capture shows no dark rendering (so no dark comparison exists), and INP was not produced |
| Axis coverage | 4 | all five axes present; competition is a two-source rules comparison, not a teardown |
| Metric integrity | 3 | every metric is a ratio with a definition and a window and traces to the section-2 goal; none is measured, because nothing is observable |
| Solution plurality | 3 | three solutions compared against one pre-stated criterion, but criterion and ranking are my derivation, with no owner |
| Feasibility grounding | 5 | every feasibility row cites the code; both sides are cited for each declared gap |
| Decision quality | 3 | every feature ends keep/fix/cut/bet with a metric, threshold and timeframe; owners are team-shaped placeholders, no named person, and two items are deliberately unowned |
| Scope calibration | 4 | section 11 names what was skipped and what would flip the calls |

Mean 3.6 → a **revise** band, driven by the two dimensions this session could not fix (Depth, Image
evidence) and by the absent behavioural data. The scorecard is worth what the scorecard is worth: it
is my own reading of my own artifact, one rater.

---

### Reproducing this pass

- Clone the dev seed database into a scratch database, add the fixture rows listed at the top, then
  point an API instance and an admin instance at it (`API_URL=http://127.0.0.1:3501/api/v1`,
  `SERVISTEK_ADMIN_E2E=1` for a separate `distDir`). Sign in at `/api/session/sign-in` as
  `platform@servistek.test` (demo password from `apps/api/prisma/seed.ts:68`), then work `/users`.
- Finding 1's reproduction: row dialog → set `Yeni rol` → `Erişimi kaydet` → read the confirmation
  summary; the summary is the observable.
- Finding 3's reproduction: stop the API, reload `/users`, compare the rendered paragraph with
  `app/error.tsx:31-33`.
- The axe sweep: the pinned file `axe-4.10.3.min.js` sits beside this artifact (fetched this
  session, sha256 `880970c081707360…`); inject it into the loaded page and run it with the tag list in
  section 5.
