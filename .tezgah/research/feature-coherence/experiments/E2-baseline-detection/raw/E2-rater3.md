# Product analysis — Ustam admin, the users area (`(dashboard)/users`)

Rater: **E2-rater3**, one agent, blind to the two sibling raters and to every prior audit of this
app. Date of every observation in this artifact: **2026-09-20**.

**Rater count: 1.** The method asks for three to five independent evaluators and says a single
rater is "too unreliable to be trusted" for severity; an agent is one rater. I ran **three passes
over one screen with one rater**, from three entry points, and I report that number instead of
implying a panel:

| Pass | Entry point | What it produced |
|---|---|---|
| A | direct URL `/users`, 1440×1000 | rendered text, SSR HTML dump, geometry/type/contrast measurements, console + network observation |
| B | direct URL `/users`, authed, 1440/768/320 + dark + filtered states | accessibility tree (CDP `Accessibility.getFullAXTree`), axe-core 4.12.1 sweep, screenshots, filter state matrix |
| C | dashboard `/` → sidebar item "Yöneticiler" | heading/section structure, cognitive walkthrough of the invite task |

Passes A and B are the method's "one to learn the product, one to find violations"; pass C is the
second entry point. Two image reads were run on the same screen (grayscale, blur) and are reported
as agreeing or not.

**Tool path taken.** The `browser_*` / `mobile_*` MCP servers are not wired in this session. Per
`analyze-app`'s fallback instruction I drove the running app through the session's own Playwright
engine (`browser.open` / `tab.run` over Chromium, CDP for the accessibility tree, emulated media
and network conditions). axe-core was injected from a **pinned local build**,
`/Users/rizax/orq/node_modules/axe-core/axe.min.js`, `axe-core 4.12.1`, never a CDN tag.
Screenshots were captured to
`/Users/rizax/Projects/tezgah/.tezgah/scratch/feature-coherence/shots/` and **read** through a
vision model with a question per image; no image bytes entered this report. The triage helper
(`tezgah-triage`) was not used: on one screen with one data row, reading the tree directly is the
cheaper move, which is what the tool's own guidance says.

**The running app.** `apps/admin` on `http://127.0.0.1:3000` (Next 16.3.0 dev, turbopack) against
the API on `http://127.0.0.1:3001/api/v1`, PostgreSQL 16 on this machine. Not started for this
analysis; it was already running. Session established through the app's own
`POST /api/session/sign-in` route. The seed credential `admin@servistek.test` returns **401** against
this database; `platform@servistek.test` returns **200** and is the account every observation below
was made as. Data state: the platform organisation holds **exactly one user**
("Platform Sahibi", `platform@servistek.test`), so almost every row state this screen implements is
unreachable with the data on disk — that shapes the whole state matrix below and is stated as a
limit, not hidden.

---

## 1. Measurement readiness — what is observable today

**Finding (gate): we cannot see this feature's outcome yet.**

- The panel's own product telemetry is **off by default and has no sink**: `defaultAdminObservabilityConsent()`
  returns `{ analytics: false, diagnostics: false }` (`apps/admin/lib/observability.ts:36-38`), the
  client is constructed with `enabled: options.enabled === true` (at `:22`) and
  `sink ?? new NoopObservabilitySink()` (at `:33`), inside `createAdminObservability`
  (`apps/admin/lib/observability.ts:19-34`), and the runtime builds it with only `environment` and
  `consent` (`apps/admin/lib/observability-runtime.ts:7-10`). Every capture therefore returns
  `consent_denied` / `disabled`, not `captured`.
- Even switched on, the invite would not be counted: `classifyCreateEntity` recognises only
  `/customers` (at `:49`) and `/work-orders` (`apps/admin/lib/api.ts:46-53`), so `POST /users/invite`
  emits no `create.started` / `create.completed`. Only the generic `api.request` would fire, with
  `routeId = api.users.post` (`apps/admin/lib/api.ts:41-44,133-138`).
- No third-party analytics is present in the admin app (no posthog / mixpanel / amplitude /
  plausible / segment in `apps/admin`, excluding build output).
- No service worker and no web app manifest exist in `apps/admin` (`app/`, `public/`, `next.config.ts`
  contain none), so there is no offline or installable surface to instrument either.

Evidence class: `code`. Citation: the six `path:line` values above.

What that means: every statement in the value axis below is a **prior**, not a measurement. The one
count on the screen ("1 kullanıcıdan 1 kayıt gösteriliyor", `page.tsx:164`) is a count, not a ratio,
and it is computed after the filter, not stored.

Harness note, recorded honestly: the research line this analysis was asked to run under,
`.tezgah/research/feature-coherence`, currently **fails** `tezgah-research check` —
`FAIL feature-coherence: state.json phase 'run' is not one of bootstrap, inner, outer, concluded`
— and holds no claims. That line belongs to the main session; I did not write to it (a sibling
would collide), so **this artifact is not registered as a claim of that line** and carries no
published scorecard beyond the one at the end of this file.

## 2. The objective — Goal → Signal → Metric

- **Goal.** A platform operator can give a named person exactly the access they need, and can take
  it away again, without a support round-trip. (Rodden/Hutchinson/Fu, HEART, CHI 2010 — the
  Goals → Signals → Metrics chain the skill's value axis is built on.)
- **Signal.** The invite is *accepted and used*: the invited person signs in at least once within
  the invite's lifetime. This signal exists in the schema — `membership.active` and the user's
  `status` (`apps/api/src/users/users.service.ts:27-66`) — but nothing records "invited → activated".
- **Metric (what the evidence supports).** Invite completion ratio =
  `memberships created by POST /users/invite whose user has a sign-in after creation` /
  `memberships created by POST /users/invite`, over a 30-day window, per organisation.
  **This metric is not derivable today**: the numerator needs an auth event joined to a membership,
  and the invite emits no product event at all (§1). Reporting a number here would be inventing it.

A metric with no goal above it is dropped, so the three tempting ones are dropped with their reason:
"number of users in the list" (a raw count, no goal), "invites per day" (no denominator, no window),
"time on the users page" (not a signal for any goal this feature has).

## 3. Opportunities, and three candidate solutions

An opportunity is a need, not a feature. Three needs this screen's evidence supports, each with the
class of the evidence that produced it:

- **O1 — the operator cannot tell what an invite actually granted.** After `POST /users/invite` the
  screen shows "Davet edildi" only via the account `status` badge, and the account is created
  `status: 'ACTIVE'` (`users.service.ts:127`), so a brand-new invite is indistinguishable from a
  live account. Evidence class: `code`.
- **O2 — the operator cannot see who is a panel administrator.** The list mixes the account
  (`status`, `locale`) with the membership (`scope`, `active`, `roles`) into seven columns whose
  two "status" surfaces share a name (§9 F-08). Evidence class: `ui-observed`.
- **O3 — a person invited on this screen cannot get in.** No credential is delivered and the only
  notification is a push to a device that cannot yet exist (§9 F-02). Evidence class: `code`.

Pre-stated comparison criterion, fixed **before** listing the candidates: *(a)* does it make the
invite's effect visible on this screen, *(b)* does it make an invited person able to sign in without
a support ticket, *(c)* can it be built on the tables and endpoints that already exist (no
migration), *(d)* what does it cost the operator per invite.

| Candidate | (a) effect visible | (b) invitee can enter | (c) no new schema | (d) operator cost |
|---|---|---|---|---|
| **S1** Make the invite form offer only roles that can actually sign in to this panel, and send a one-time set-password link by email | yes — the dialog names the access being granted | yes | needs a token/email path (`passwordResetChallenge` exists; an invite token does not) | one form |
| **S2** Keep the random password and show it once to the operator, in the confirmation dialog, with a copy control (the Google Workspace pattern, §7) | partly — the operator sees a password, not the effect | yes — the operator hands it over out of band | none, `randomInvitePassword()` is already generated at `users.service.ts:116,323-325` | one copy/paste |
| **S3** Split the screen: a "Panel yöneticileri" list (SUPER_ADMIN only) and an "Organizasyon kullanıcıları" list, each with its own invite | yes — the access being granted is the screen's subject | no — unchanged | none | one more navigation |

Against the pre-stated criterion, **S2 scores highest on (c)+(d)** and **S3 on (a)**, and S1 is the
only one that satisfies (b) end-to-end. The recommendation is **S1 with S2 as the interim**; the
recommendation's reference is Clerk (§7), which sends the invitation link by email and lets the
invitee set their own credentials.

## 4. Risks by class, each with its cheapest falsifying test

| Class | Risk | Cheapest test that would falsify it |
|---|---|---|
| Value | the operator never needs more than one panel administrator, so the whole screen is a museum piece | check the audit log for `user.invite` events over 30 days (`AuditService.record` at `users.service.ts:160-167`) — one query |
| Usability | a 7-column table with a 1140.3 px floor is unusable on the devices operators use | the 320 px pass in §5 already shows 5 of 7 columns off-screen; falsify by finding an operator who uses a phone |
| Viability | no invite-completion metric means no way to know if invites land (§1) | turn the observability client on with a real sink and re-read the events for one invite — one config change |
| Feasibility | permission-denied, reactivate and edit states exist in code but no account can reach them | sign in with a non-`SUPER_ADMIN` account: the panel refuses it (`app/api/session/sign-in/route.ts:17,33-36`), which *is* the falsifier |

## 5. Usability

**Scope (narrowed as the method requires).** One route, `/users`; one user group, the platform
operator (`SUPER_ADMIN`); one device class, desktop Chromium at 1440×1000, plus 768 and 320 for
reflow; breakpoints in scope 320 / 768 / 1440; dark mode (`prefers-color-scheme: dark`); text at
200 % of the root font size. Task in scope: *invite a team member and set their access.*

### 5.1 Heuristics checked (Nielsen, 0-4 severity scale) and the walkthrough

| Heuristic | Verdict on this screen | Finding |
|---|---|---|
| Visibility of system status | the count line states `N of M`; success/error come back as a query-param notice (`page.tsx:75`, `MutationNotice`) | F-08, F-12 |
| Match between system and the real world | role/scope labels are Turkish and specific ("Atanan kayıtlar") | — |
| User control and freedom | every mutation is behind a confirmation dialog; Escape closes via native `<dialog>` | F-13 (Escape not reachable while the client layer is inert) |
| Consistency and standards | three names for one entity; two "Aktif" surfaces; a column header that promises a control | F-08, F-11, F-12 |
| Error prevention | native `required` + `maxLength` on the invite form; server validation returns field-level messages (`actions.ts:21-43`) | — |
| Recognition rather than recall | scope options are spelled out ("Atanan kayıtlar"), not keys | — |
| Flexibility and efficiency | only `q` + membership-state filters; no role filter, no sort, no pagination | F-04, F-14 |
| Aesthetic and minimalist design | the primary CTA is a 1126×44 full-bleed band; a static note occupies an action column | F-10, F-12 |
| Help users recognise and recover from errors | `fieldHelp` maps five fields to Turkish help text; unknown codes fall back to a safe sentence | — |
| Help and documentation | none on the screen; the dialog's `description` is the only help | F-11 |

**Cognitive walkthrough** — task "invite a new team member", from a first-time operator's position,
four questions per step (Wharton et al.); each step run once in pass C:

1. **Notice the entry point.** Operator lands on "Yöneticiler" from the sidebar. The H1 says
   "Yöneticiler", the card says "Kullanıcılar", the route is `/users`, the button says "Takım üyesi
   davet et". Q1 yes (they will try here); **Q3 no** — the three names do not tell them whether this
   screen manages *panel* administrators or *organisation* users, and the answer matters because the
   roles differ (F-11).
2. **Open the invite dialog.** The trigger reads "Takım üyesi davet et" and is the only saturated
   control. Q2 yes, Q3 yes, Q4 yes. In this environment the dialog does not open at all (F-13).
3. **Choose a role.** The dialog says "Rol ve kayıt kapsamı davet anında atanır." and offers a route
   list. **Q4 no** — the only option is "Platform sahibi", and submitting it returns
   "Platform sahibi bu ekrandan atanamaz." (F-01). A first-time operator cannot tell that they are
   being offered the one role the screen refuses.
4. **Confirm.** A confirmation dialog names the person and what changes ("Pasife alma bu işletmedeki
   oturumları ve cihaz erişimini kaldırır"). Q1-Q4 yes.
5. **Verify the result.** The list gains a row. **Q4 no** — a new account is created `status: 'ACTIVE'`,
   so nothing on the screen distinguishes "invited" from "working here" (F-01 preamble, O1).

### 5.2 The state matrix (mandatory)

Read from the running app; the citation for every row is the pass named in the *how read* column.
A state that could not be driven is marked **not driven** with the reason; a state that does not
exist is a finding (**F-**).

**Interactive components**

| Component | default | hover | focus | active | disabled | loading | error | Missing |
|---|---|---|---|---|---|---|---|---|
| "Takım üyesi davet et" button | pass C: present, 1126×44 (measured) | not driven | pass B: `outline: solid 3px rgb(20,95,192) offset 3px` (measured) | not driven | not driven | n/a (opens a dialog) | n/a | hover/active/disabled not driven — needs the client layer, inert here (F-13) |
| Modal close "✕" (`aria-label="Pencereyi kapat"`) | present in SSR HTML, 0×0 while closed | — | — | — | — | — | — | every state not driven (dialog never opens, F-13) |
| Filter text input `q` (searchbox "Ad veya e-posta ara") | pass B: 201×44, focus ring 3px | not driven | measured | not driven | not driven | n/a | n/a | hover/active not driven |
| Filter select `state` (combobox "Üyelik durumu") | pass B: 100×44 | not driven | measured | not driven | not driven | n/a | n/a | hover/active not driven |
| "Filtrele" button | pass B: 92.5×**67** | not driven | measured | not driven | not driven | n/a | n/a | **F-07**: 67 px box against a 44 px input |
| "Filtreleri temizle" link | pass B: 165.1×**67** | not driven | measured | not driven | not driven | n/a | n/a | **F-07** |
| Table scroll region (`role="region"`, tabIndex 0) | pass B: 1084×120, min width 1140.3 | n/a | measured | n/a | n/a | n/a | n/a | no visual affordance that columns continue (**F-03**) |
| Invite form controls (Ad, E-posta, Rol, Kapsam, "Davet oluştur") | present in SSR HTML, 0×0 while the dialog is closed | — | — | — | — | — | — | not driven (F-13) |
| Per-row "Erişimi düzenle" / "Yeniden etkinleştir" | **not rendered for any row** — the only row is `SUPER_ADMIN` | — | — | — | — | — | — | the states exist (`page.tsx:207-224`, `228-256`) but the dataset cannot reach them |

**Data views**

| View | States | Verdict |
|---|---|---|
| Users table | loading | **exists**, `(dashboard)/loading.tsx:1-7` (`aria-busy`, `role="status"` "Sayfa yükleniyor…", skeleton line + block) inherited by `/users`; **not driven** — the network-throttle attempt lost the session first |
| | empty (filter) | **driven**: `?q=zzz` and `?state=inactive` → 0 rows and "Eşleşen kullanıcı yok. Filtreleri temizleyin veya yeni takım üyesi davet edin." (pass B); header row and count line stay |
| | empty (no users at all) | not driven — the org has one user; the same branch renders |
| | error (API 5xx / schema mismatch) | not driven. `Response.parse(...)` at `page.tsx:58` throws on a shape change and the route group's `(dashboard)/error.tsx` catches it; no `/users`-specific error copy exists |
| | offline | **driven**: `net::ERR_INTERNET_DISCONNECTED` — the browser's own error page, no app-level offline state, no service worker (§1) |
| | partial | n/a — the API returns the whole set in one response (`users.service.ts:29-71`) |
| | long-text / overflow | **driven on the input** (120-char `q`: no document overflow, `scrollWidth 1061` inside the field) and **observed in the table**: the e-mail is clipped at 320 (image read) |
| | permission-denied | **exists in code** (`page.tsx:50-56`, `role="alert"` locked surface) but **unreachable in the running app**: the panel admits only `SUPER_ADMIN` (`app/api/session/sign-in/route.ts:17,33-36`) |
| Count line | default / filtered | driven; states `N of M` correctly (pass B) |
| Role `<select>` options | one option | **F-01** |

### 5.3 Findings at their level

| # | Level | Finding | Severity 0-4 | Kind | Read from |
|---|---|---|---|---|---|
| F-03 | Screen + property | the table's minimum width is **1140.3 px** inside a region that is **1084 px** at 1440, **686 px** at 768 and **242 px** at 320 (measured); at 320 only "Ad" and "E-posta" are on screen and the e-mail is cut mid-string; worse, the columns beyond the fold are the ones that say *what access* someone has | 3 (every narrow viewport × cannot read the record × constant) | failure (measured + reproducible) | pass B; image reads at 768 and 320 |
| F-07 | Property | "Filtrele" and "Filtreleri temizle" are **67 px** tall against **44 px** inputs; their text centres sit at y=382.5 while the inputs' sit at y=394 — an **11.5 px** vertical offset (measured) | 2 | failure (measured) | pass B |
| F-08 | Component | the row shows "Aktif" twice with two treatments: a `.badge` chip in "Durum" (`page.tsx:187-189`) and plain text in "Üyelik" (`page.tsx:200`); the filter calls one of them "Üyelik durumu" with "Aktif/Pasif" while the column is called "Durum" — two different fields share a name | 2 | failure (observable in the tree and the image) | pass B (AX tree lists cell "Aktif" twice), grayscale image read |
| F-10 | Property + screen | the primary action is a **1126×44** full-bleed band; the blur test reads it as a banner competing with (arguably beating) the H1, the grayscale test agrees, and it also ties "Filtrele" with "Filtreleri temizle" as two equal-weight buttons. Two image reads, same conclusion | 2 | judgement (confidence: 2 passes agreed) | pass B; grayscale + blur captures, both read |
| F-12 | Component | the only row's last cell is a static sentence (`page.tsx:206`) under a column header that says "Yetki güncelle" — the header promises a control that is not there | 1 | failure (the text is not a control; asserted against the tree) | pass B (AX tree: columnheader "Yetki güncelle", cell is text) |
| F-13 | Screen | every mutation form is client-only: the SSR document carries `action="javascript:throw new Error('React form unexpectedly submitted.')"`, and in this dev server 5 JS chunks return **403**, React never hydrates, and clicking "Takım üyesi davet et" leaves `<dialog open>` false (2 clicks + 1 programmatic click). Whether that 403 is a shipped defect or a stale dev server I cannot decide from here — a saved e2e auth state written at 22:03 argues the app was interactive an hour earlier | 2 (as an environment fact; 0 as a product defect, unresolved) | behaviour (reproduced 3×) | pass A/B |
| F-14 | Screen | filtering is `q` + membership state only — no role, scope or e-mail filter; the roles column is displayed but not filterable | 1 | judgement | pass B (toolbar contents), state matrix |

### 5.4 The rendered screen

**Screenshots actually read** (all under `.tezgah/scratch/feature-coherence/shots/`):

| File | Read? | What it answered |
|---|---|---|
| `users-1440.png` | yes | full-page hierarchy at 1440; found the clipped last column and the full-bleed CTA |
| `users-768.png` | yes | reflow at 768; the sidebar becomes a top nav; reported "no overflow" because the shot shows only the columns that fit — which is itself why the finding needs the measurement |
| `users-auth-320-light.png` | yes | reflow at 320: only "Ad" and "E-posta" visible, e-mail clipped at `platform@ser`, mobile header with "Menüyü aç" |
| `users-auth-1440-dark.png` | yes | dark mode complete and coherent; no leaked light surface; the last column's note is the dimmest text |
| `users-empty-filter.png` | yes | the empty state: one gray line inside the table, header row kept, count line reads "1 kullanıcıdan 0 kayıt gösteriliyor" |
| `users-grayscale.png` | yes | grayscale test: hierarchy survives; the CTA wins on area, not on meaning |
| `users-blur.png` | yes | blur test: the CTA dominates and reads as a banner |
| `users-320.png`, `users-empty-320.png` | **no** | the first 320 capture's read was rate-limited (429) and the empty-320 capture was superseded by the authed 320 read; their measurements are in the tables above |

**Blur test:** the full-bleed invite band reads first, ahead of the H1 — a hierarchy failure in the
sense the method means, and a *judgement*: the band is one element doing the job of both page title
and primary action. **Grayscale test:** hierarchy survives; the two filter buttons tie, the "Aktif"
chip and the plain "Aktif" duplicate. Both tests were run once and read once each; both reads agree
with each other on the CTA and on the filter pair. Luminance proxy, measured rather than eyeballed:
CTA `L = 0.109` on a card at `L = 1.0` — the CTA stays a dark shape without colour.

**What the tree could not answer, and what was captured because of it:** hierarchy, rhythm, the
banner-like weight of the CTA, the clipping of the last column and the "two Aktif" duplication. The
tree did answer: roles, names, the column set, the region, focusability and the focus ring.

**axe-core.** `axe-core 4.12.1`, injected from the pinned local build, run on `main.content` at 1440:
**0 violations, 1 incomplete** — `td:nth-child(7) > p`, "Element's background color could not be
determined because it's partially obscured by another element". That node was hand-checked with a
computed-style contrast walk: **31 of 31 text nodes pass** their WCAG AA threshold (4.5:1, or 3:1 for
large text); the nearest pass is the CTA's white-on-green at **4.68:1** in dark mode. Dark mode was
measured the same way: 0 failures. axe's own figure is ~57 % of WCAG issues found automatically, so
**hand-checked here**: focus appearance (measured, 3 px solid `rgb(20,95,192)` with 3 px offset on
all controls, passes SC 2.4.7), target size (measured: every *visible* control is at least 44 px
tall and 92.5 px wide, passes SC 2.5.8's 24×24 floor; the 0×0 controls in the table above are inside
the closed dialog and are not visible), dragging (none), accessible authentication (not applicable).

**WCAG 2.2 level claimed: AA for the users screen, on the evidence above.** Two things prevent a
stronger claim and are stated rather than assumed: the reflow criterion (SC 1.4.10) passes only with
horizontal scrolling inside a labelled region, and the SC 1.4.4 text-resize behaviour is
inconsistent — setting the root font size to 200 % moved `h1` 32→64 px and `td` 16→32 px but left
`th`/`.muted` at 13 px and `.badge` at 12 px, because those are px-locked (`globals.css:564-584`,
`.badge` 12 px); the user's own font-size preference therefore changes part of the screen and not the
rest. There is no WCAG conformance statement anywhere in `apps/admin`.

**Properties measured** (not eyeballed): type scale `h1 32 / h2 19 / td 16 / button 16 / field label 14
/ th 13 / .muted 13 / .badge 12`, all `line-height: normal` (no explicit leading anywhere in the
table region); control geometry as in §5.3; focus ring as above; contrast 31/31 and dark 0 failures.

## 6. Feasibility — intended against implemented, both sides cited

| Intended behaviour (doc / copy / test) | The code that implements it | Verdict |
|---|---|---|
| "Panel kullanıcılarını, rollerini ve erişebildikleri kayıtları yönetin." (`page.tsx:72`) | sign-in admits `SUPER_ADMIN` only (`app/api/session/sign-in/route.ts:17`); the roles offered come from the caller's organisation (`users.service.ts:69-76`) | **gap**: on this panel the phrase "panel kullanıcıları" and the roles on offer cannot both be true |
| "Takım üyesi davet et" → "Davet oluşturulsun mu?" (`page.tsx:76-93`) | `inviteUserAction` refuses `SUPER_ADMIN` (`actions.ts:61`); the form's default is `TECHNICIAN` if present else `roles[0].key` (`page.tsx:106-112`) | **gap** — see F-01 |
| a role and scope are assigned at invite time (dialog description, `page.tsx:79`) | `membership` + `membershipRole` created in one transaction (`users.service.ts:149-158`) | holds |
| the invite reaches the person | account created with `hashPassword(this.randomInvitePassword())` (`users.service.ts:116`, `323-325`); outbox event `UserInvited` (`users.service.ts:168-175`) whose only consumer is a push handler (`apps/api/src/worker/push-notification.handler.ts:74,135`); the email provider is off unless `PASSWORD_RESET_EMAIL_PROVIDER=resend` (`password-reset-email.provider.ts:10`), default `disabled` (`apps/api/.env.example:10`) | **gap** — see F-02 |
| the list can grow | `list()` returns every user of the organisation with `page: { nextCursor: null, hasNextPage: false }` (`users.service.ts:29-71`); the page fetches it whole and filters in memory (`page.tsx:58-66`) | **gap** — see F-04 |
| a missing membership is a state the UI handles (`page.tsx:198,204`) | `where: { memberships: { some: { organizationId } } }` (`users.service.ts:29`) returns only users that *have* one | **gap**: the branch is unreachable |
| search matches a name in Turkish | `toLocaleLowerCase('tr-TR')` on both sides (`page.tsx:59`) | **gap** — see F-05 |
| the mutation is refused without permission | `requireAdminMutation('team.invite')` (`actions.ts:53`) and `canUseAdminMutation` gating the two column sets (`page.tsx:46-47`); tested at `apps/admin/lib/high-impact-pages.permission.test.tsx` | holds; the denied surface is unreachable in the running app, not broken |
| API contract | `GET /users`, `GET /users/roles`, `POST /users/invite`, `PATCH /users/:id` all present in `docs/openapi.json` and guarded by `@RequirePermissions('user.manage')` (`users.controller.ts:34-79`) | holds |

## 7. Competition — basis, set, and cited facts

**Comparison basis, stated before comparing:** *what the invited person receives and can act on, and
how the inviter sees the invite's state*. Representative builds only, each read on **2026-09-20**:

| Product | Fact | Artifact, date read |
|---|---|---|
| Clerk (dashboard + Backend API) | creating an invitation **sends an email with a unique invitation link**; the invitee is redirected to a sign-up page and their email is auto-verified; invitations expire after a month; an invitation can be **revoked**; bulk invitation exists (`createInvitationBulk`); `POST /v1/invitations` is rate limited to 100/hour | `https://clerk.com/docs/guides/users/inviting`, read 2026-09-20 |
| Google Workspace Admin console | the admin sets a password and can **preview and send the account details**, or **copy the password** to hand over out of band; "Pending invites" is a filter with a **Cancel invite** action per row; bulk invite by CSV; the welcome email's reset link **expires in 48 hours** | `https://knowledge.workspace.google.com/admin/users/add-an-account-for-a-new-user` (page states "Last updated 2026-09-18 UTC"), read 2026-09-20 |
| Vercel (team members) | invite by e-mail with the role selected at invite time; **Pending Invitations** is a sidebar section; the invitee has **7 days (30 for SAML teams)** to accept, then the invite shows as expired; role is editable after acceptance; "Remove from Team" is a row action | `https://vercel.com/docs/rbac/managing-team-members` (`last_updated: 2026-05-08`), read 2026-09-20 |

**Our position on that basis.** All three deliver something to the invitee (a link, or a password the
operator can hand over) and all three expose a *pending* state with an expiry. Ustam delivers neither
a link nor a visible password and shows no pending state distinct from an active account (§6, F-01,
F-02). The one thing our screen does that these do not is state the record scope ("Atanan kayıtlar",
"Takım kayıtları") at invite time, which is the axis to keep.

**What we adopt and what we deliberately do not.** Adopt: an invite that carries its own credential
delivery, and a per-row pending state with an expiry (Vercel's 7/30-day pattern). Do not adopt:
licence and billing coupling (Google) and per-project role assignment (Vercel) — the record-scope
model already covers what those encode here.

**Review mining: not done.** No app-store, G2 or forum review set for this product was read in this
session, so there are no themes, no sentiment and no volume to report. This is a missing element of
the competitive axis (see §11), not a covered one.

## 8. Triage

| Feature / surface | Verdict | Deciding metric | Threshold | Timeframe | Action | Flag | Owner |
|---|---|---|---|---|---|---|---|
| Invite (dialog + `POST /users/invite`) | **fix** | invite completion ratio (§2) | < 0.5 invites leading to a sign-in ⇒ the delivery path is the defect | 30 days after the ratio is made observable | deliver a credential (S1), interim: show the password once (S2) | `users.invite.delivery` | unassigned — **this is the gap that blocks the fix** |
| Users table (7 columns, 1140 px floor) | **fix** | share of list views at width < 768 px | any measurable narrow-screen traffic ⇒ mobile layout | next release | stack cells per record below 768 px; keep the region's `role`/`aria-label` | `users.table.reflow` | unassigned |
| In-memory filter + unpaginated list | **fix** | `GET /users` p95 duration and row count | > 500 users per organisation or > 300 ms ⇒ server-side filter + cursor | before the first 500-user organisation | wire the `page` object the API already returns | `users.list.scale` | unassigned |
| Role/scope assignment (`PATCH /users/:id`) | **keep** | — | — | — | keep; it is the one part that works without a new credential | — | — |
| Per-row edit for `SUPER_ADMIN` rows | **cut** | — | — | — | remove the "Yetki güncelle" column for rows it can never act on, or make the header honest | — | — |
| "Yeniden etkinleştir" | **bet** | reactivations per 30 days | 0 in 90 days ⇒ cut | 90 days | keep the code, stop rendering the column | `users.reactivate.use` | unassigned |
| This whole screen, if the panel stays single-operator | **cut (conditional)** | number of distinct `SUPER_ADMIN` accounts | 1 account after 6 months ⇒ the screen is dead weight | 6 months | fold it into the organisations screen | `users.screen.need` | unassigned |

No flag has an owner, because no owner information exists in this repository for these surfaces — a
cut nobody owns will not happen, which is why the column is left visibly empty rather than invented.

## 9. Findings, most severe first, each with its class and citation

**F-01 — the screen's only write action cannot succeed.** `code`.
The invite form's role `<select>` is populated from `GET /users/roles`, which returns the caller's
organisation roles (`apps/api/src/users/users.service.ts:69-76`); for the platform organisation that
is exactly one role — the rendered document offers the single option `('SUPER_ADMIN', 'Platform
sahibi')`, captured from the running app's SSR HTML in pass A. The form's default is
`roles.some(r => r.key === 'TECHNICIAN') ? 'TECHNICIAN' : roles[0]?.key` → `SUPER_ADMIN`
(`apps/admin/app/(dashboard)/users/page.tsx:106-112`), and the action refuses precisely that value:
`if (body.roleKey === 'SUPER_ADMIN') return { error: 'Platform sahibi bu ekrandan atanamaz.' }`
(`apps/admin/app/(dashboard)/users/actions.ts:61`). So the default submission is a refusal and no
other option exists. Severity 4. Evidence: `code` (the four citations) + `ui-observed` (the rendered
option list).

**F-02 — an invited person receives nothing they can sign in with.** `code`.
The invite creates the account with a random password the invitee never sees
(`users.service.ts:116`, `randomInvitePassword()` at `:323-325`), emits only `UserInvited` into the
outbox (`:168-174`), and the sole consumer of that event is a push notification to the invited
user's device (`apps/api/src/worker/push-notification.handler.ts:74,135`) — a device that cannot be
registered for an account that has never signed in. The only remaining path, password reset, needs
`PASSWORD_RESET_EMAIL_PROVIDER=resend` (`apps/api/src/auth/password-reset-email.provider.ts:10`),
whose shipped default is `disabled` (`apps/api/.env.example:10`). Scope: the shipped default
configuration; an operator who sets the provider restores the reset path but still sends no invite.
Severity 4.

**F-03 — the table cannot be read on a narrow screen.** `ui-observed` (measured).
`table { width: 100% }` with `th, td { white-space: nowrap }` (`apps/admin/app/globals.css:564-573`)
inside `.tableWrap { overflow-x: auto }` (`:561-562`) gives the table a measured 1140.3 px floor
against a region of 1084 px (1440), 686 px (768) and 242 px (320). At 320 the image read shows only
"Ad" and "E-posta", with the e-mail clipped at `platform@ser`, and the columns that carry the
access information ("Roller", "Kapsam", "Üyelik") are off-screen; the region is focusable
(`page.tsx:167`) so a keyboard user can scroll it, but nothing on screen says there is more.
Severity 3.

**F-04 — the list is unbounded and filtered in memory.** `code`.
`list()` selects every user with a membership in the caller's organisation and returns
`page: { nextCursor: null, hasNextPage: false }` (`users.service.ts:29-71`, the `page` object at
`:66`), and the page then fetches all of it and filters in memory (`page.tsx:58-66`). The API
contract already carries the pagination shape; nothing fills it. Severity 3.

**F-05 — Turkish search silently misses.** `behaviour`.
Reproduced against the running app on 2026-09-20, same account, same screen:
`q=sahibi` → 1 row; `q=SAHİBİ` → 1 row; **`q=SAHIBI` → 0 rows** and the empty state
("Eşleşen kullanıcı yok…"); `q=platform` and `q=PLATFORM` → 1 row. Definition: rows returned / rows
matching the case-insensitive prefix, window = the single render, denominator = 1 user in the
organisation. Cause, in code: both the term and the haystack are lowercased with
`toLocaleLowerCase('tr-TR')` (`page.tsx:59`), where `'I' → 'ı'`, so "SAHIBI" becomes `sahıbı` and
never matches `sahibi`. `'İ' → 'i'` is why the dotted form works. Severity 3.

**F-06 — the feature has no observable outcome.** `code`.
See §1: consent false by default, `enabled === true` never satisfied, `NoopObservabilitySink`
(`apps/admin/lib/observability.ts:19-38`), and `/users/invite` unclassified for create events
(`apps/admin/lib/api.ts:46-53`). The metric in §2 therefore cannot be computed. Severity 3.

**F-07 — the filter row is not on one line.** `ui-observed` (measured).
`.toolbar` is a flex row with default `align-items: stretch` (`globals.css:543-546`), so
"Filtrele" and "Filtreleri temizle" stretch to the 67 px height of the labelled `.field` columns
while the controls beside them are 44 px (`globals.css:167-186`, `.button` min-height 44 at
`:193-195`); measured text centres 382.5 px vs 394 px, an 11.5 px offset. Two image reads disagreed
here (one saw the offset, one did not); the measurement settles it. Severity 2.

**F-08 — one row, two "Aktif"s, two meanings.** `ui-observed`.
The accessibility tree of the running page lists cell "Aktif" twice in the same row; in the DOM one
is the status chip (`page.tsx:187-189`) and the other is the membership flag (`page.tsx:200`). The
filter above them is labelled "Üyelik durumu" with "Aktif/Pasif" (`page.tsx:150-155`) while the
column it is adjacent to is called "Durum" (`page.tsx:174`). Severity 2.

**F-09 — "Üyelik yok" is dead code.** `code`.
`page.tsx:198` and `:204` render "Üyelik yok" when `user.membership` is null, but the API's `where`
clause only returns users that have a membership in the caller's organisation and takes
`memberships[0]` (`users.service.ts:29,57-65`), so the branch cannot render. Severity 1.

**F-10 — the primary action outweighs the page title, and the two filter buttons tie.**
`ui-observed` (grayscale and blur captures, both read; both agree).
Measured 1126×44, `L 0.109` on a `L 1.0` card; at blur it reads as a banner that competes with the
H1, and in grayscale "Filtrele" and "Filtreleri temizle" have identical weight. Judgement, not a
failure: a full-width primary button is a legitimate pattern, and the alternative (a right-aligned
button in a page-actions row) is what the rest of this panel uses (`globals.css:539-542`,
`.pageActions`). Severity 2.

**F-11 — four names for one entity.** `ui-observed`.
Sidebar item and H1 "Yöneticiler" (text of the page under test), card heading "Kullanıcılar"
(`page.tsx:144`), route `/users` (the sidebar href, read in pass C), the invite copy "Takım üyesi
davet et" / "takım üyesi davet edin" (`page.tsx:70`, `:289`). A screen that offers role `TECHNICIAN`
as its default is not a list of managers, and a reader cannot tell which of the four is meant.
Severity 2.

**F-12 — a column header promises a control that is not there.** `ui-observed`.
The tree gives `columnheader "Yetki güncelle"` (`page.tsx:178`) over a cell whose content for the
only row is the sentence "Platform sahibi erişimi bu ekrandan değiştirilmez."
(`page.tsx:206`). Severity 1.

**F-13 — every mutation on this screen is client-JS-only, and in this environment the client layer
is inert.** `behaviour`.
The SSR document renders `action="javascript:throw new Error('React form unexpectedly submitted.')"`
on the invite form (captured in pass A), and the running dev server returns **403** for 5 JS chunks
on every fresh load (measured twice, cache disabled), so React never hydrates: `document.querySelectorAll("dialog")`
stays `open: false` after two real clicks and one programmatic click, and the close button measures
0×0. Reproduction: load `/users`, click "Takım üyesi davet et", read `dialog.open`. I cannot settle
whether the 403 is a defect or a stale dev server from inside this session — a Playwright auth-state
file written at 22:03 today proves the app *was* interactive an hour earlier — so this is reported
as an environment fact with an unresolved cause, severity 2, and every interactive state in §5.2 is
marked not driven because of it.

**F-14 — filters cannot reach the column the operator needs.** `ui-observed`.
The toolbar offers `q` and "Üyelik durumu" only (`page.tsx:145-164`); "Roller" and "Kapsam" are
displayed but not filterable, and there is no sort control. Severity 1.

## 10. For each recommendation, who already does it best

| Recommendation | Reference, cited | What we adopt |
|---|---|---|
| Deliver a credential with the invite (F-01, F-02) | Clerk — invitation email with a unique link, auto-verified e-mail, expiring, revocable (`https://clerk.com/docs/guides/users/inviting`, read 2026-09-20) | the link-with-expiry shape |
| Show the credential once when the link path does not exist yet (interim) | Google Workspace — "Preview And Send" or "Copy Password" (`https://knowledge.workspace.google.com/admin/users/add-an-account-for-a-new-user`, updated 2026-09-18, read 2026-09-20) | the copy-once pattern, on top of the password the service already generates |
| Distinguish invited from active (O1, F-01) | Vercel — a "Pending Invitations" section with a 7-day (30-day SAML) expiry shown per row (`https://vercel.com/docs/rbac/managing-team-members`, `last_updated 2026-05-08`, read 2026-09-20) | a pending state with an expiry, on `status: 'ACTIVE'`'s current silent behaviour |
| Filter and page the list server-side (F-04) | already in this repository — `docs/openapi.json` and `users.service.ts:64` carry the `page` object | fill the contract that exists rather than inventing one |

## 11. What this analysis did not look at

- **Interviews, tickets and reviews.** No user-verbatim evidence exists in this session; there is not
  one `user-verbatim` finding in this artifact, and no support-ticket or review corpus was read.
- **The competitive review mining** (themes, sentiment, volume) — named in §7 as missing.
- **SUS / UMUX-Lite.** Not run and not reported; the skill's own rule is that an agent records these
  as *to be run*, never as a number it produced.
- **The loading state** and the **error state** of `/users` — present in `(dashboard)/loading.tsx`
  and `(dashboard)/error.tsx`, not driven; two attempts lost the session first.
- **The permission-denied surface** — exists at `page.tsx:50-56`; unreachable because the panel
  admits only `SUPER_ADMIN`.
- **The invite, edit, reactivate and deactivate flows end to end** — the client layer is inert in this
  environment (F-13) and the dataset holds one user, so no `ALREADY_MEMBER`, `ROLE_NOT_FOUND`,
  field-error or confirmation-dialog state was driven. `apps/admin/app/(dashboard)/users/actions.test.ts`
  and `page.test.tsx` were read for intent only, never run (the assignment forbids project-wide
  suites, and a unit test is not the running app).
- **Core Web Vitals** — no `PerformanceObserver` run; LCP/INP/CLS are unmeasured, and the
  chrome-devtools sidecar is opt-in and off.
- **Mobile / native** — the `mobile_*` server is not wired and no simulator was booted; every mobile
  claim here is a web-reflow claim at 320 px, not a native one.
- **Performance under load** — no timing of `GET /users` was taken; F-04's threshold is an assumed
  ceiling, and it is marked as such in §8.
- **Prior audits of this app** — deliberately out of scope: `Ustam/.tezgah/`, `Ustam/docs/design/`,
  `Ustam/plans/`, and (for the same reason, the blind-pass rule) `Ustam/apps/admin/review/*.md`. The
  last directory was not named in the assignment but contains prior UX audits of the same app, so it
  was skipped and is disclosed here.
- **What would change the recommendation.** If a non-`SUPER_ADMIN` could sign in to this panel, F-01
  would move from "the form is a dead end" to "the form is mis-scoped"; if the observability client
  were switched on with a real sink, the value axis's ratios would become measurable and §2's metric
  could be computed; if the 403 chunk failures turn out to be a shipped defect, the F-13 severity
  moves from 2 to 4 and every interactive state in §5.2 becomes a product failure rather than a
  session limit.

---

## Scorecard (the skill's ten dimensions, 1-5, anchors from the `research` skill)

| Dimension | Score | Why |
|---|---|---|
| Evidence relevance | 4 | every finding's citation was read in this session; one minor gap: F-10's hierarchy claim is a judgement from image reads, and its two reads needed a measurement to settle a disagreement |
| Class discipline | 3 | every finding carries one class and `ui-observed` findings name the call and state; the gap is that the artifact has **no** `user-verbatim` and only one `behaviour` finding |
| Depth | 2 | the state matrix reaches component × state in the table, but 6 of the interactive rows are marked "not driven" and several data states were never reached |
| Image evidence | 2 | two breakpoints read plus dark and empty; the 320 capture's read was rate-limited, dark mode was read but not at a second breakpoint, and no 200 %-text capture was read |
| Axis coverage | 2 | all five axes are present, but competition rests on three vendor docs and value rests on one cited telemetry path with no measurement |
| Metric integrity | 1 | no metric was produced: the only ratio in the artifact is F-05's, and §2's metric is unfalsifiable today. **This dimension is not addressed at the level the skill asks for.** |
| Solution plurality | 1 | three solutions were compared against a pre-stated criterion, but none was costed and none was validated beyond desk reasoning. **Not addressed at the level the skill asks for.** |
| Feasibility grounding | 4 | §6 cites both sides of every claimed gap |
| Decision quality | 2 | every feature has a verdict and a criterion, but **no row has an owner** and no flag is wired |
| Scope calibration | 4 | §11 names what was not looked at and what would flip the recommendation |

**Mean 2.5** → below 3.0, and two dimensions sit at 1 → the skill's own rule reads this artifact as
**reject**. That is the honest grade for an analysis whose value axis has no measurement, whose
solution set was compared but not costed, and whose state matrix is half un-driven; the grade is the
summary, not a retraction of the findings above.

## The six-dimension review (research skill, `review.json` shape)

| Dimension | Score | Finding |
|---|---|---|
| Evidence relevance | 4 | F-05's citation is the run itself; F-10 is the weak one (a judgement twice read and once measured) |
| Falsifiability | 4 | F-05, F-03, F-07 and F-13 all carry a re-runnable command or measurement; F-01/F-02 are falsified by changing one environment variable or signing in as another account |
| Scope calibration | 3 | F-02 is explicitly scoped to the shipped default configuration; F-01 is scoped to the platform organisation actually observed — but F-04's scale threshold is an assumption presented in §8 as a threshold |
| Argument coherence | 4 | observation → gap → insight → solution → claim runs through §5 → §6 → §3 → §9 |
| Exploration integrity | 3 | the failed re-auth attempts, the missing axe run on `main.content` before it existed, the lost loading-state drive and the unknown cause of F-13 are all recorded rather than smoothed over |
| Methodological rigour | 2 | one rater, three passes, no second independent rater, no baseline from a same-harness run |

**Mean 3.17** → *revise*. No claim here should be read as shipping evidence for a change.

## Evidence files produced by this rater

All under `/Users/rizax/Projects/tezgah/.tezgah/scratch/feature-coherence/`:
`r3-users-1440.html` (SSR document), `r3-axtree.json` (227-node accessibility tree),
`r3-contrast.json` (31 text nodes, 12 controls), `r3-dark-contrast.json`, `r3-align.json`
(toolbar geometry, focus rings, narrow empty state), `r3-filter-states.txt` (the state matrix rows),
and `shots/` (8 PNGs, 7 of them read).
