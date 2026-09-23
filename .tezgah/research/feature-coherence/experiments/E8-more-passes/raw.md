# E8 re-score — six first-feature artifacts against the frozen first corpus

Independent re-score by the `E8Rescore` session. It did not produce any of the six artifacts and
did not read the sessions that did.

Read for this score, and nothing else:

- `experiments/E1-defect-corpus/results.jsonl` (15 rows, D01-D15)
- `experiments/E1b-runtime-probe/results.jsonl` (R04, R05 as scored rows; R01-R03, R06 read as
  the settles-row notes they are)
- `experiments/E2-baseline-detection/scoring.md`, `scoring-addendum.md`
- the six artifacts `E8-{A1,A2,A3,B1,B2,B3}.md`
- read-only reads of the audited repository (`/Users/rizax/Projects/Ustam`) to settle D01's
  caller claim, D04's sibling-convention contrast and D12's default, and the two W3C
  Understanding pages quoted in §4

Not read: any `analysis.md`, any `raw/` file, `E2-rater*`, `E3-rater*`, the E6 control rubric.
The score therefore rests only on the corpus, the artifacts and the code they cite.

---

## 1. Scoring set, rule and tier definitions

**Scoring set.** D01-D15 (classes C1-C10) plus R04 (C7) and R05 (C6) — 17 rows — per
`scoring-addendum.md`: R04 and R05 are "**new row in the set**: a rater reporting it is a
detection, not a false positive", while R01-R03 and R06 "settle corpus rows that were already in
the set".

**Matching rule** (`scoring.md`, applied as written): a row is *detected* when the artifact states
the same defect — same layer pair (or same missing capability), same actor-visible effect — with
its own citation; a defect stated with no citation, or one whose citation does not show it, is an
unverifiable claim and not a detection; a defect reported on a pass row (D09, D15) is a false
positive; a finding matching no corpus row and surviving a re-check is a false positive that is
still counted and reported.

**Tiers** (batch contract):

- **tier A** — the defect is stated in a numbered finding, a named section, or an explicit verdict.
- **tier B** — tier A plus matrix/contract cells that state the defect.

A tier-B-only row is one whose only statement of the defect is a cell of a matrix or contract
table. Tier A count = rows at tier A; tier B count = tier A ∪ tier B.

**Judgement calls applied uniformly** (they are the whole of this score's discretion, and §6
gives their sensitivity):

1. Multi-element rows (D05, D06, D12) count as detected when the artifact states at least one of
   the row's named defects as a defect. The element stated is named in the per-row basis.
2. D11 is counted only where the artifact states the *split of one entity's edit across
   surfaces*, names the un-surfaced `GLOBAL_PROFILE_SELF_SERVICE_REQUIRED` guidance, or **proposes
   the missing detail aggregate**. Merely stating the dead `GET /users/:id` is D02's row, not
   D11's — otherwise one finding would carry two classes. §6 gives the looser alternative count.
3. D14 is element-level: the row's defect is that the required artifact has no place for a
   capability change, so the artifact that *supplies* that element (a named proposals section) has
   reached it, as has the artifact that names the element's absence. The proposal counts are
   reported separately, as the contract asks.
4. Pass-row verdicts (D04, D06's announcement element, D13, D15) are recorded as contradictions in
   §4 rather than as detections.

---

## 2. Per-artifact score

### A1 — `E8-A1.md` (feature-audit; 23 findings F-01…F-23, 5 matrices, 11 pass rows)

| Row | Class | Tier | Basis in the artifact |
|---|---|---|---|
| D01 | C1 | A | F-18 "Two routes for one action, one of them dead" (`POST /users/{id}/deactivate` no caller, different audit action); Matrix 1 cell "two — `PATCH` and `POST /users/{id}/deactivate` (F-18)" |
| D02 | C1 | A | F-03 "No detail view; the API's detail capability is unreachable"; Matrix 1 "View a member's detail — **no** … route **yes**" |
| D03 | C2 | A | F-21 "`locale` travels through the contract and reaches no view"; Matrix 2 `locale` row |
| D05 | C3 | A | F-06 "Filtering lives in the render, not the route … in-memory filter under a pagination envelope"; F-07 "The pagination envelope is a constant and the client drops it" |
| D06 | C4 | A | F-06 (no query contract; "the endpoint has no parameters and no `take`"); Matrix 1 "Search by name/email — route **no**" |
| D12 | C8 | A | F-12 "Closing a modal discards typed values with no announcement" (the no-draft element) |
| D14 | C10 | A | named section "## Proposals" (P1, P2), each with an absence proof and a falsifier |
| R04 | C7 | A | F-17 "At operator widths the list is a 1583 px table in a 242 px scroll region; 6 of 7 columns … outside it" (measured on a stand-in fixture; see §4 C-6) |

Tier A count **8**; tier B count **8** (no row is stated only in a cell).
Classes: C1, C2, C3, C4, C7, C8, C10 → **7 / 10**.
Proposals: **2** (P1 platform-scoped user administration, P2 invitation delivery).
Contradictions: D04, D06 (two elements), plus a self-contradiction inside A1 (§4 C-9).

### A2 — `E8-A2.md` (feature-audit; 12 findings, 5 matrices, 3 proposals)

| Row | Class | Tier | Basis in the artifact |
|---|---|---|---|
| D01 | C1 | A | finding 5 "Two routes for deactivate: the live one loses the audit action name and the dead one owns it"; Matrix 1 cell |
| D02 | C1 | A | finding 7 "`GET /users/{id}` is dead: the server has a detail capability no surface can reach" |
| D03 | C2 | A | finding 12 "Contract fields no surface reads: `locale`, and the pagination envelope" |
| D05 | C3 | A | finding 12 ("hardcoded … and never read by either client"); partial: the in-memory filter is a cell recorded as `yes` in Matrix 1, not as a defect |
| D06 | C4 | A | finding 12 + Matrix 1 route cell; partial: the announcement is **passed** and the route is marked `yes` |
| D11 | C7 | A | finding 7 + P3 "User detail capability, or removal of the dead endpoint" — the artifact *proposes* the detail aggregate D11 says is never proposed |
| D14 | C10 | A | named section "7. Capability-change proposals" (P1, P2, P3) |
| R04 | C7 | A | finding 4 "At 390 px five columns and every row action sit outside an undiscovered scroll, and the e-mail column is clipped mid-value" (read from the repo's own committed 390 px screenshot) |

Tier A count **7**; tier B count **7**.
Classes: C1, C2, C3, C7, C10 → **5 / 10**.
Proposals: **3** (invitation delivery, deactivate-route disposition, user-detail-or-removal).
Contradictions: D04; the D06 announcement verdict (§4 C-2).

### A3 — `E8-A3.md` (feature-audit; 12 findings F1…F12, 5 matrices, 2 proposals)

| Row | Class | Tier | Basis in the artifact |
|---|---|---|---|
| D01 | C1 | A | F5 "Two routes for one action, and the audit trail depends on which caller used it"; Matrix 1 "Deactivate a membership via the dedicated route — no … yes" |
| D02 | C1 | A | F4 "A capability the server has and no panel user can reach: the user detail" |
| D03 | C2 | A | F8 "`locale` is carried by the contract and rendered nowhere" |
| D05 | C3 | A | F6 "The filter runs in memory under a pagination envelope nobody computes" (states the count's unverifiable claim, i.e. the scale effect) |
| D06 | C4 | A | F6 (no query reaches the API) and F7 "Turkish casefold: an uppercase-ASCII name cannot be found by typing it in lowercase" (the ASCII-transliteration search miss) |
| D14 | C10 | A | named section "7. Capability-change proposals" (P1, P2) |
| D12 | C8 | B | Matrix 3, Resume/persistence cell: "**no persistence**: values live in uncontrolled DOM; a reload loses them" — the only statement of the row's no-draft element |

Tier A count **6**; tier B count **7** (adds D12).
Classes: tier A C1, C2, C3, C4, C10 → **5 / 10**; tier B adds C8 → 6 / 10.
Proposals: **2** (invitation delivery, server-side list query).
Contradictions: D04; the D06 announcement verdict; no statement about R04 at all
("**[NOT CHECKED: no running app, 320 px not rendered]**" on the reflow row).

### B1 — `E8-B1.md` (pre-wiring control rubric; 12 findings F1…F12 + U1-U10)

| Row | Class | Tier | Basis in the artifact |
|---|---|---|---|
| D05 | C3 | A | F5 "The list is the only org-scoped list in the panel with no server-side search or pagination: the page fetches every user and filters with `String.includes`, while the API returns `nextCursor: null`" |
| D06 | C4 | A | same F5 (no server-side search) |
| D14 | C10 | A | named section: "Fixes 1 and 3 name layers that do not exist yet. The pre-wiring rubric has no heading for that — its recommendations section is the only home for them, which is why they are written above as recommendations rather than as capability-change proposals" — the row's defect named outright |
| R04 | C7 | A | F7 + U6 "region client 1084 px vs table 1140 px … 686 vs 1140 at 768; 297 vs 1140 at 375; 242 vs 1140 at 320" (measured live; the region widths match R04 exactly) |
| D01 | C1 | B | §11 coverage note: "Not looked at: the `/users/:id` and `/users/:id/deactivate` endpoints as consumers (the panel never calls them — `users.controller.ts:49-86`)" — the fact is stated with a citation, but as a limitation, never as a defect |
| D02 | C1 | B | same §11 note |

Tier A count **4**; tier B count **6**.
Classes: tier A C3, C4, C7, C10 → **4 / 10**; tier B adds C1 → 5 / 10.
Proposals: **0** — and B1 is the only artifact that names the missing proposal element instead.
Contradictions: the D06 announcement verdict; a defect reported at D15's pass row (U1/F6).

### B2 — `E8-B2.md` (pre-wiring control rubric + feature-audit matrices; 11 findings F1…F11, 2 proposals)

| Row | Class | Tier | Basis in the artifact |
|---|---|---|---|
| D01 | C1 | A | F11 "asymmetric layers … `POST /users/:id/deactivate` has none either (`actions.ts:89-93` uses `PATCH {active:false}`)"; Matrix 1 cell |
| D02 | C1 | A | F11 "`GET /users/:id` has no panel caller" |
| D05 | C3 | A | F5 "no pagination and a client-side count: `users.service.ts:64` hardcodes `page: { nextCursor: null, hasNextPage: false }` … while the page fetches the whole list and filters in memory" |
| D06 | C4 | A | F5 + F8 "a filtered result is announced to nobody. The loaded page carries zero `[role=status]`/`[aria-live]` nodes (measured)" — the only artifact that agrees with the corpus on this element |
| D14 | C10 | A | named section "Capability-change proposals" (P1, P2) |
| R04 | C7 | A | F3 "the data view clips its own per-row control. Measured `tableWrap` `scrollWidth/clientWidth`: 1140/1084 at 1440, 1140/686 at 768, 1140/312 at 390" |
| D03 | C2 | B | Matrix 2 `locale` row: "not rendered anywhere in this area" |
| D12 | C8 | B | Matrix 3, listed under Gaps: "there is no persistence of the flow across a reload" |

Tier A count **6**; tier B count **8**.
Classes: tier A C1, C3, C4, C7, C10 → **5 / 10**; tier B adds C2 and C8 → 7 / 10.
Proposals: **2** (invitation delivery; one source for the role domain).
Contradictions: a defect reported at D15's site (the state matrix + walkthrough record the
platform-owner row as unusable); an unsupported citation on D01 (§4 C-5).

### B3 — `E8-B3.md` (pre-wiring control rubric; findings F1…F14, G1, G2, U1…U10, 2 proposals)

| Row | Class | Tier | Basis in the artifact |
|---|---|---|---|
| D05 | C3 | A | F12 "No paging on the roster. `page.tsx` renders `users.map(...)` over the entire `Response.data` array; the API advertises `page: { nextCursor: null, hasNextPage: false }` … and the page reads neither" |
| D12 | C8 | A | §7: "Ustam's panel does the inverse — on the platform organization the invite form's only option *is* the owner role, and it is pre-selected" + F1's cited default expression (the uncalled-out-default element; weakest row in this table — §6) |
| D14 | C10 | A | §10 R1/R2 "**Capability-change proposal**" and §12 "Capability-change proposal: yes, two" |
| R04 | C7 | A | U3 "at 1440 CSS px — the app's own baseline width — the last column is clipped and there is no visible affordance … 686/1140 at 768 … 242/1140 at 320" (measured live) |

Tier A count **4**; tier B count **4**.
Classes: C3, C7, C8, C10 → **4 / 10**.
Proposals: **2** (an *assignable role* rule; an invitation-outcome product event plus an
enablement path for the recorder).
Contradictions: a defect reported at D15's site (U2, severity 3).

### Row × artifact matrix

`A` = tier A, `b` = tier B only, `–` = not detected, `!` = the artifact asserts something the
corpus contradicts at that row.

| Row | Class | A1 | A2 | A3 | B1 | B2 | B3 |
|---|---|---|---|---|---|---|---|
| D01 dead deactivate route | C1 | A | A | A | b | A | – |
| D02 detail endpoint unreachable | C1 | A | A | A | b | A | – |
| D03 `locale` unrendered | C2 | A | A | A | – | b | – |
| D04 no autocomplete token | C2 | ! | ! | ! | – | – | – |
| D05 in-memory list, constant envelope | C3 | A | A | A | A | A | A |
| D06 search control | C4 | A ! | – ! | A ! | A ! | A | – |
| D07 picker is not a combobox | C4 | – | – | – | – | – | – |
| D08 picker cascade loses data silently | C5 | – | – | – | – | – | – |
| D09 apply gate enforced (pass) | C6 | – | – | – | – | – | – |
| D10 apply step 1 free-text / step 2 structured | C6 | – | – | – | – | – | – |
| D11 edit split across surfaces, detail never proposed | C7 | – | A | – | – | – | – |
| D12 invite dialog safeguards | C8 | A | – | b | – | b | A |
| D13 confirmation omits removed roles | C9 | – | – | – | – | – | – |
| D14 no proposal element | C10 | A | A | A | A | A | A |
| D15 row edit hides what the server refuses (pass) | C1 | – | – | – | ! | ! | ! |
| R04 table never fits its region | C7 | A | A | – | A | A | A |
| R05 wizard URL state vs rendered step | C6 | – | – | – | – | – | – |

---

## 3. Arm unions and counts

| Measure | Arm A (A1, A2, A3) | Arm B (B1, B2, B3) |
|---|---|---|
| Tier A union (row ids) | D01, D02, D03, D05, D06, D11, D12, D14, R04 — **9 rows** | D01, D02, D05, D06, D12, D14, R04 — **7 rows** |
| Tier B union | same 9 rows (no cell-only row) | **8 rows**: adds D03 (B2) |
| Classes reached, tier A | C1, C2, C3, C4, C7, C8, C10 → **7 / 10** | C1, C3, C4, C7, C8, C10 → **6 / 10** |
| Classes reached, tier B | **7 / 10** | **7 / 10** (adds C2 via B2) |
| Per-artifact tier A count | 8, 7, 6 → median **7** | 4, 6, 4 → median **4** |
| Per-artifact tier B count | 8, 7, 7 → median **7** | 6, 8, 4 → median **6** |
| Artifacts with ≥1 capability-change proposal | **3 / 3** (2, 3, 2) | **2 / 3** (B1 0, B2 2, B3 2) |

Row-level differences between the arms:

- **Reached by A at tier A and by B only at tier B, or not at all**: D03 (B2's matrix 2 cell only),
  D11 (A2's P3 only; no B artifact states the split or proposes the aggregate), D12 (A1's finding
  vs B2/B3's cells and §7 sentence).
- **Reached by both**: D01, D02 (A tier A; B1's §11 note is tier B), D05, D06, D14, R04.
- **Reached by neither**: D07, D08 (the `CoreRecordPicker` on the customers surface — outside every
  artifact's boundary), D09, D10, R05 (the apply wizard — the same), D13 (in scope, missed by all
  six), D15 (a pass row no artifact reports as a defect in the A arm; all three B artifacts report
  one).
- **Classes no artifact reaches**: C5, C6 (their rows live on the two surfaces outside the audited
  feature) and **C9 (D13), the one in-scope class all six miss** — the role-replacement
  confirmation's omission of the roles about to be removed.
- **C10 is the one class every artifact reaches**, and the B arm reaches it in two different ways:
  B1 by naming the missing element, B2/B3 by supplying one.

Beyond the contract's asks: the families that recur in all six artifacts and match no corpus row —
the `UserStatus` label map against the enum with `INVITED` written by nobody, the disabled
observability client, the deliverability of an invitation, and the role picker offering a value the
service refuses — would each count as a false positive under `scoring.md`'s third row (the corpus
is not exhaustive; the row is reported). They are noted here because they are the bulk of each
artifact's finding list and would dominate any noise comparison.

---

## 4. Contradictions, each with the passage that decides it

### C-1 · D04 (C2) vs A1, A2, A3 — the autocomplete token

Corpus D04: "The invite form's name and email inputs carry no autocomplete token … the same app's
registration wizard sets `autoComplete="email"` on its email field, so the convention exists and
this form deviates from it. WCAG 2.2 SC 1.3.5 (AA) names this as identifying input purpose."
R02 confirms the DOM fact.

- A1, Matrix 5: "SC 1.3.5 autocomplete tokens, scoped | **pass** — the search box collects no self
  data and claims no token; the invite email field collects *another person's* address, so no token
  is correct"
- A2, same table: "SC 1.3.5 `autocomplete` tokens | **no finding for user data** — the form's fields
  describe *another person* (invitee name/e-mail), not the user's own data, so no H98 token applies"
- A3, same table: "`autocomplete` token scope (SC 1.3.5, H98) | **pass** — the only fields are a
  search box and record fields, which are exactly the fields that must NOT carry a self-data token"

Deciding passage (SC 1.3.5 Understanding, W3C, read 2026-09-21): "This success criterion is
specifically scoped to inputs collecting *information about the user*. … An input field for
information that is not *about the user* does not need to programmatically expose its purpose,
even if that purpose is included in the Input Purposes list." Its Intent section makes the
corpus's own case explicit: "`type="email"` indicates that the field is for an email address but
does not clarify if the purpose is for entering the user's email address or some other person's
email."

All three A artifacts are on the standard's side; D04's WCAG grounding does not hold, and the
sibling-wizard contrast it rests on compares the invitee's address with the *applicant's own*
address. This is a corpus row the artifacts contradict correctly — the row, not the verdicts, is
the weaker side. Verified: the invite form carries no `autocomplete` attribute
(`apps/admin/app/(dashboard)/users/page.tsx:96-103`), the apply wizard does
(`apps/admin/app/apply/page.tsx:125`).

### C-2 · D06's announcement element / R03 vs A1, A2, A3, B1 — and B2 on the other side

Corpus D06: "the result count is written into a plain paragraph with no live region, so a screen
reader is told nothing when the filter changes." R03 adds the runtime measurement: "the count
element `role=null`, `aria-live=null`; live regions on the page: 0".

- A1, Matrix 4: "`q` (search) change + submit … What is announced | new document (full
  navigation) — nothing to announce"
- A2, Matrix 4: "page navigation reloads and the count text carries both numbers `:164` — pass"
- A3, Matrix 4: "the count line is text in the re-rendered document; no live region — but the whole
  page re-renders on a `GET`, so a notification is not required"
- B1, U10: "the screen carries no `role=status` / `role=alert` / `aria-live` element in any state I
  read. Because the filter is a full-page GET navigation, no announcement is required for it —
  recorded as a judgement, not a violation."
- B2, F8 (the only artifact that agrees with the corpus): "a filtered result is announced to
  nobody. The loaded page carries **zero** `[role=status]`/`[aria-live]` nodes (measured), and the
  result line is plain `.muted`"

Deciding passage (SC 4.1.3 Understanding, W3C, read 2026-09-21): "This success criterion
specifically addresses scenarios where new content is added to the page without changing the
user's context. … messages that involve changes of context do not need to be considered and are
not within the scope of this success criterion." A status message is defined as "change in content
that is **not** a change of context".

Neither side disputes the DOM fact; they split on whether a full-navigation filter owes an
announcement. On the standard's wording the four disagreeing artifacts have the better argument for
the native GET path, which leaves the corpus row resting on a client-side transition (B2 observed
one and still marked it a judgement). Recorded as a live corpus/artifact collision, not as a
scoring error on either side.

### C-3 · D06's casefold element vs A1

Corpus D06: "substring match over displayName+email only (Turkish lowercasing, no diacritic
folding, so `sukru` does not find `Şükrü`)".

A1, pass rows: "Turkish casefold search: both the query and the compared string are folded with
`toLocaleLowerCase('tr-TR')`, and a unit test covers `ipek` → "İpek". This is the defect the
sibling stack had; here it is closed."

A1 asserts the opposite of the row at that element. A3 reaches the same family from the other
direction and states it as open — F7: "an uppercase-ASCII name cannot be found by typing it in
lowercase … `"ilkay"` returns `[]` for a row whose `displayName` is `"ILKAY Demir"` … the durable
form is a normalized search column on the user query". A3's finding is aligned with D06 rather
than in conflict with it; A1's verdict is the conflict.

### C-4 · D15 (pass row) vs B1, B2, B3

Corpus D15: "The row edit hides its control for a platform owner and the server independently
refuses that target, so the UI affordance and the enforcement agree rather than drifting. Recorded
so the capability matrix reports agreement where it exists, not only where it fails."

- B1, U1/F6 (severity 4): "Of the screen's two actions, one (`invite`) is refused by the same
  request that offers it and the other (`update`) has no eligible row … The screen is reachable and
  its subject matter is absent."
- B3, U2 (severity 3): "The column that promises the action is present for 100% of the rows and
  actionable for 0% of them."
- B2, §4 state matrix / walkthrough: "Per-row control `Erişimi düzenle` / `Yeniden etkinleştir` |
  **✗ not present in the fixture** … there is no per-row control for the only row present".

None of the three disputes the agreement the corpus records; each adds a defect where the corpus
records a pass, which `scoring.md` scores as "rater reports a defect on a pass row (D09, D15) →
false positive". The A arm does the opposite — A1's pass rows ("the surface states the reason
instead of hiding the row"), A2's ("`SUPER_ADMIN` targets are blocked from both sides") and A3's
("the surface hides exactly what the service refuses") all record D15 as agreement.

### C-5 · D01 vs B2's justification — an unsupported citation

B2, F11: "`POST /users/:id/deactivate` has none either (`actions.ts:89-93` uses
`PATCH {active:false}`). … Kept deliberately for the mobile path
(`mobile-management.contract.test.ts:7`) — a pass row in reality, listed so the matrix is not
one-sided." The same reading recurs in B2's triage: "`GET /users/:id`, `POST /users/:id/deactivate`
| **keep** (mobile-safe paths)".

Checked in the repository: that test asserts the panel-only decoration of
`MembershipStatusController.manageOverview` and `DevicesController.manageRevoke` and says nothing
about the users routes; and the mobile client calls only `/users` (GET), `/users/invite` (POST) and
`/users/${id}` (PATCH) (`apps/mobile/src/features/users/organization-users-api.ts:38-56`). A
repository-wide search for `deactivate` over `apps/mobile/src`, `apps/admin/{app,lib,components}`,
`packages/api-client/src` and `packages/domain/src` returns only the generated OpenAPI operation
`users-deactivate` — no caller. So the route is dead exactly as D01 says, and B2's "kept for the
mobile path" is a citation that does not support its statement, which under `scoring.md` is the
shape of an unverifiable claim. Its detection of D01 stands on the other citation it gives (the
panel uses PATCH), but its verdict — a deliberate keep — does not.

### C-6 · R04 vs A1's figures — the fixture is visible in the number

R04: "the table is 1140 px wide at all three widths while the scroll container is 242 px at 320,
686 px at 768 and 924 px at 1280". A1's F-17 reports "a 1583 px table in a 242 px scroll region …
at 320 px region 242 / table 1583, at 390 px 312/1583, at 768 px 686/1583". The region widths are
identical to R04's; the table width is not. A1 labels the row a fixture measurement in its header
("every finding below is a **reading** except F-17, which is a measurement of a stand-in fixture")
and discards its own 1440 px reading "as a fixture artefact". The detection stands on the effect
(no breakpoint reflows the table, the action column is outside the region), on a number that is a
property of the fixture and not of the running app — so it is evidence about the behaviour, not the
figure R04 records. B2's and B1's numbers match R04's 1140/242/686 exactly; B3's do too.

### C-7 · D11's "is never proposed" vs A2's P3 — recorded as the detection, not a conflict

Corpus D11 ends: "A detail page per user, which the existing `GET /users/:id` would support, is
never proposed." A2's §7 heading is "### P3 · User detail capability, or removal of the dead
endpoint (finding 7)", with the capability "An operator can open one user and see the fields the
contract carries (including `locale`) …". A2 supplies the element the row says is absent; no other
artifact does, and B2's triage makes the opposite decision ("keep … leave; document that the panel
deliberately uses PATCH").

### C-8 · R05 — stated by nobody, and the nearest sentence is feature-scoped

R05: "GET /apply?step=2 -> final URL /apply?step=3, HTTP 200; body renders 'Başvuruyu başlat'". No
artifact mentions it. The nearest statement is A1, Matrix 3: "No URL names a step (no wizard), so
the 'URL naming a step the page does not render' class does not apply here." Read in place that is
a claim about the audited feature (`/users` has no wizard), not about `/apply`; it does not
contradict R05, and no artifact did the work the row would need.

### C-9 · A1 contradicts itself around the same control D15 is about

A1, F-23: "The option list is the organization's full role list (`roles.map` on both selects,
unfiltered), and on the live demo organization that list contains `SUPER_ADMIN`". A1, pass rows:
"the service refuses assignment, **the picker never offers it** (options come from the
organization's roles)". The two statements cannot both hold. It matters here only because it is the
row where A1 records D15 as agreement — the pass row's parenthetical is the part its own F-23
refutes.

### Not a contradiction, recorded so it is not counted as one

D13 is missed by all six (§3). Five artifacts mark the rule "destructive confirmation names what is
lost" as pass, each citing the *deactivation* copy; B2's is the nearest rebuttal, because its
evidence quotes the replace semantics — "…rol seçilirse mevcut rollerin tamamının yerini alır…
(`page.tsx:236-244`)" — but D13's complaint is that the dialog's fields list only the values being
applied and never the roles being removed, which no pass row asserts.

---

## 5. Where these numbers differ from an expected reading

The brief's arm framing carries one expectation: B1-B3 "applied
`E6-pre-wiring-control/product-analysis-pre-wiring.md`, which has **no proposal element**, and were
told nothing about proposals". My count differs from the reading that follows from it.

- **Two of the three control artifacts wrote capability-change proposals**, not zero: B2's named
  section "Capability-change proposals" (P1 invitation delivery, P2 one source for the role domain)
  and B3's §10 R1/R2 with the summary line "Capability-change proposal: yes, two". B2 states why it
  has them — "The layer-coherence matrices of `skills/feature-audit` are filled because the ask is
  one feature, and that skill is what the rubric points at for them" — i.e. the proposal element
  entered through the matrices the control rubric points at, not through the rubric's own
  recommendations section. **Only B1 (0) matches the "no proposal element" premise**, and B1 matches
  it explicitly: "The pre-wiring rubric has no heading for that — its recommendations section is the
  only home for them, which is why they are written above as recommendations rather than as
  capability-change proposals."
- Consequence for D14/C10: at element level all six reach it (§2), so C10 does not separate the arms
  at all; what separates them is *how* — B1 names the missing element, the other five supply one.
- I was given no expected numeric table (row ids, counts, class totals) for the six artifacts, so
  there is nothing else to compare these numbers against. If a prior reading of this corpus by the
  second feature's re-score used a looser D11 criterion, my C7 numbers are the ones that move (§6).

---

## 6. Limits of this score, and the sensitivity of the judgement calls

- **D11 (C7)**: I counted it only where the artifact states the *split* or proposes the detail
  aggregate, so that D02's finding could not be double-counted into C7. Under the looser reading —
  any statement of the missing single-user aggregate — A1 (F-03), A3 (F4) and B2 (F11) would also
  count D11, taking A's tier A union to 9 rows unchanged (A2 already has it) and B's to 8. C7 was
  reached by both arms regardless, through R04.
- **D12 (C8)**: the row has three elements and no artifact states all of them. B3's is the weakest
  entry in the table (a comparison-section sentence plus F1's cited default); dropping it takes B3
  to 3 tier A rows and B's tier A union to 6 rows (D12 is still reached by A1, A3 and B2). A1's
  entry rests on F-12, which names the invitation dialog's missing persistence but not the
  inline-uniqueness or the default-scope elements.
- **D05/D06 (C3/C4)**: both arms reach both rows; the differing element is D06, where A1, A2, A3
  and B1 contradict the corpus's announcement element (C-2) and A2 does not state the search defect
  at all (its Matrix 1 marks the route `yes` and its Matrix 4 marks the announcement a pass).
- **D14 (C10)**: element-level by construction; under a strict reading that requires the artifact to
  *name* the missing element, only B1 detects it and no arm reaches C10 — the class is a property of
  the artifact template, not of the audited feature, so this score reports both readings.
- I did not re-derive any artifact's finding from the codebase except where a row turned on it
  (D01's callers, D04's sibling contrast, D12's default, the two W3C pages). Everything else is the
  artifact's own citation as written; a citation I did not open is recorded as the artifact's claim.
