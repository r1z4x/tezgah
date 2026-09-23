# E12 — independent re-score of the eight second-feature artifacts against the corrected corpus

Rater: one independent pass (agent `E12Rescore`). Date 2026-09-21.
Inputs read: `E5-transfer/scoring.md`, `E5-transfer/corpus-correction.md`, the frozen second corpus
(recovered, see §0), and the eight artifacts `E5-transfer/raw/E5-base{1,2}.md`,
`E5-transfer/raw/E5-treat{1,2}.md`, `E6-pre-wiring-control/raw/E6-ctl{1,2}.md`,
`E6-pre-wiring-control/raw/E6-tre{1,2}.md`. **`analysis.md` was not opened in either experiment**, so
nothing below is anchored to the session's own numbers; the only comparison is against the prediction
recorded in `E12-rescore-corrected/protocol.md` ("E5: baseline 5, treatment 4; E6: 4 and 4").
Evidence basis: `artifact` (the passage quoted from the arm), and `code` where I re-read the subject
repository to settle a contested claim (`aibim-app` @ `a6e47df`, read-only, no build).

## 0. Provenance note — the corpus is no longer on disk

The brief names `experiments/E5-transfer/results.jsonl` as the corpus input. As of commit
`bb2f7c6` ("research: give every experiment its result rows") that file holds two evidence rows
`X01`/`X02`, not the 14 corpus rows; the corpus survives in git at `452c533`
("research: freeze the second corpus on the Rust admin users area") and at `bb2f7c6^`.
`git show 452c533:.../E5-transfer/results.jsonl` reproduces the 9 875-byte, 14-row file exactly.
This re-score uses that frozen file plus `corpus-correction.md`. **If the line intends the corpus to
be readable, it currently is not** — reported, not fixed (out of my write scope).

## 1. The corrected corpus and the scoring rule I applied

14 rows, six defect classes (C1, C2, C3, C8, C9, C10), three pass rows in three classes
(C5's A07, C1's A08, C4's A09) and one class with no instance on this feature (C6's A11)
(`E5-transfer/scoring.md`):

| Row | Class | Kind | Subject |
|---|---|---|---|
| A01 | C1 capability | failure | two users handlers take no `AdminClaims` |
| A02 | C1 capability | failure | panel offers `super_admin`, server refuses it |
| A03 | C2 field contract | judgement | one role enum, three independent enumerations |
| A04 | C2 field contract | failure | committed technical reference vs the router |
| A05 | C3 list convention | failure | documented pagination vs fixed `limit: 200`, page shown as the population |
| A06 | C2 field contract | failure | typed role write path vs raw `Value` create/update with silent defaults |
| A07 | C5 | pass row | list state recomputed after a mutation |
| A08 | C1 | pass row | deactivate control agrees across layers |
| A09 | C4 | pass row | search is server-side on both layers |
| A10 | C9 destructive confirmation | judgement | deactivate and role change commit unconfirmed |
| A11 | C6 | no instance | the users area has no multi-step flow |
| A14 | C3 list convention | failure | `Pager` ships in the library, unreachable on this surface |
| A15 | C8 smart defaults | new | create form has no client guard; 400 lands as a toast, no field marked |
| ~~A13~~ | ~~C8~~ | **withdrawn** | the silent-default creation claim (false) |

Rule applied (`scoring.md` §Matching, unchanged): a row is **detected** when the artifact states the
same defect — same layer pair (or the same missing capability), same actor-visible effect — with a
citation that supports it. Recorded in two tiers so the reading is auditable:

- **Tier A (finding-level):** the defect is stated in a numbered finding, a formally named section
  (a capability-change proposal counts for A12), or an explicit verdict sentence outside a matrix.
- **Tier B (instrument-level):** Tier A plus a matrix / state-matrix / contract-row cell that states
  the defect — the matrices are this line's instrument, and `feature-audit` requires the cells to be
  filled, so a cell naming the disagreement is a statement of it.
- `partial` = the artifact touches the row's subject but states only part of it (name given below).
- A class counts as detected when ≥1 of its rows is detected. Pass rows (A07/A08/A09/A11) are scored
  separately as `recorded-agreement` and never as detections.

`code` checks I ran in `aibim-app` to settle contested items (all read-only):
`admin_list_all_users` and `admin_get_user` take **no** `AdminClaims` extractor
(`handlers/admin.rs:4394-4397`, `:4469-4472`) → A01's mechanism holds;
`admin_create_user` binds `unwrap_or("")`/`unwrap_or("viewer")` and then returns 400 on empty
email/password/tenant (`:892-913`) → A13's mechanism is false, exactly as the correction says;
`Users.tsx:244-271` is not a `<form>`, passes no `required`, disables the submit on `isPending` only,
and reports failures as `toast.error` (`:52`), while `Tenants.tsx:164,184` marks `required` and gates
its own submit → A15 holds; `components/ui/Pager.tsx` exists and is imported only by
`ThreatIntel.tsx:13,247,324,407`, never `Users.tsx` → A14 holds; `roleColors` carries five keys and
`ROLES` three inside `ALL_ROLES` (`Users.tsx:11-16`) → A02/A03 hold; `grep -n confirm Users.tsx` →
empty → A10 holds.

## 2. Per-artifact × per-row matrix

Legend: `✓` detected (Tier A), `▣` detected at Tier B only (matrix cell), `~` partial, `—` not
detected. Artifact short names: **b1** E5-base1, **b2** E5-base2, **t1** E5-treat1, **t2** E5-treat2,
**c1** E6-ctl1, **c2** E6-ctl2, **r1** E6-tre1, **r2** E6-tre2.

| Row | Class | b1 | b2 | t1 | t2 | c1 | c2 | r1 | r2 | Where it is stated |
|---|---|---|---|---|---|---|---|---|---|---|
| A01 | C1 | — | — | — | — | — | — | — | — | see §5.1 — all eight miss it or call it a pass row |
| A02 | C1 | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | b1 F3 · b2 F3 · t1 F3 · t2 F4 · c1 §9.5 · c2 F9/U7 · r1 F3 · r2 F4 |
| A03 | C2 | ~ | ▣ | ▣ | ~ | ~ | ~ | ▣ | ▣ | b1 F3 names a doc-comment as the third reading, not a value list · b2 §3.1 "two sources: the constant …, the literals `Users.tsx:10-11` and `TenantDetail.tsx:353`" · t1 matrix 2 role row "**two sources** … `TenantDetail.tsx:357`" · r1 P2 "hand-maintains two arrays while `admin.rs:875` holds a third" · r2 matrix 2 row 4 "**four sources**" |
| A04 | C2 | — | — | — | — | ▣ | — | — | — | c1 §6 row 7: "the admin API table lists exactly two user endpoints … Implemented: seven user-related route registrations" |
| A05 | C3 | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | b1 F6 · b2 F5 · t1 F7 · t2 F5/F16 · c1 §6.1/§9.4 · c2 F4 · r1 F4 · r2 F3 |
| A14 | C3 | ~ | ✓ | ✓ | ✓ | ▣ | ~ | ✓ | ✓ | b2 F5 "no pager appears although `Pager` exists and this repo's sibling list pages use it" · t1 F7 · t2 F5 · c1 §6.1 "`Pager` exists and is used with `total` elsewhere" · r1 F4 · r2 F3. b1 F6 only recommends "add a pager"; c2 F4 reports no pagination and never names the primitive |
| A06 | C2 | ✓ | ✓ | ~ | ~ | — | ▣ | ~ | ✓ | b1 F4 "sibling write paths … one validated, one raw" · b2 F11 "the only user writer without a typed DTO" · c2 §6.2 "Body validation style … **disagree with the role endpoint**" · r2 F8 + matrix 2 row 2 "create: presence; update: **none**" · t1 matrix 1 update cell "email is not validated (F-contract row)" · t2 matrix 1 row 4 "partial — no email format check, no empty check" · r1 M1/M2 cells only |
| A07 | C5 | ~ | ~ | ~ | ✓ | — | — | ~ | ✓ | t2 pass row A7 "Mutations invalidate the list query, so the table converges" · r2 matrix 4 row 3 · b1 §5d · b2 §3.3 · t1 M4 · r1 M4 name the patch+invalidate mechanism but attach a caveat |
| A08 | C1 | — | ~ | — | ~ | ~ | — | ✓ | ✓ | r1 pass row P-b · r2 pass rows P1/P2 · c1 §6 row 6 "Authorization — agrees across layers" · t2 pass row A1 · b2 §1 pass row (a) |
| A09 | C4 | ✓ | — | ✓ | ✓ | — | ✓ | ✓ | ✓ | b1 §5c ("walkthrough pass 1 clean") · c2 §6.4 "Search … **agree**" · t1 matrix 1 row 2 · t2 §3.1 · r1 M1 row 2 · r2 matrix 1 row 2 |
| A10 | C9 | ✓ | ▣ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | b1 F9 · b2 §3.4 "SC 3.3.4 … **fail** — `Deactivate` fires on click with no dialog naming the user `Users.tsx:207-215`" · t1 F8 · t2 F7 · c1 F7 · c2 U6/F12 · r1 F5 · r2 F7 |
| A11 | C6 | — | ✓ | — | — | — | — | ✓ | — | b2 §3.2 "one modal … not a wizard" · r1 M3 "No multi-step wizard exists in this feature". t1 M3, t2 §4, c2 §6.3 and r2 matrix 3 instead model create→activate as a three-to-seven step flow; C6 is not a defect class, so no score moves |
| A14→A15 | C8 | ✓ | ✓ | ✓ | ✓ | ▣ | ✓ | ✓ | ✓ | b1 F8 · b2 F13 · t1 F12/F11 · t2 F9 · c2 U5 + §5.1 · r1 F9 · r2 F11. c1 states it only in the §5 state matrix ("only `isPending` (`:263`); no required-field gate" / "toast only (`:52`)") and §9.11 keeps such cells judgement-level |
| A12 | C10 | ~ | ✓ | ✓ | ✓ | — | — | ✓ | ✓ | b2 §8 "Capability-change proposal (required by F2 and F4)" · t1 P1/P2 · t2 P-1/P-2 · r1 P1-P3 · r2 §10. b1's capability matrix calls one row a "capability-change proposal, not a screen fix" but proposes nothing; c1/c2 write no proposal (c2 §3 compares guards inside existing layers) |

Row totals across the eight columns — defect rows (A01-A06, A10, A12, A14, A15) detected at
Tier A: b1 5, b2 6, t1 6, t2 6, c1 3, c2 4, r1 6, r2 7. Pass rows named at all
(A07/A08/A09/A11, never counted as detections): b1 A07 A09 · b2 A07 A08 A11 · t1 A07 A09 ·
t2 A07 A08 A09 · c1 A08 · c2 A09 · r1 A07 A08 A09 A11 · r2 A07 A08 A09.

## 3. Per-artifact score and the withdrawn-row check

| Artifact | Classes, Tier A | Classes, Tier B | A13 mechanism asserted? | Claim the corrected corpus contradicts |
|---|---|---|---|---|
| E5-base1 | C1 C2 C3 C8 C9 = **5** | 5 | **No** — F8 reads it correctly: "Required `email`/`password`/`tenant_id` and the 8-character floor are enforced only in the handler (`admin.rs:907-926`)" | none |
| E5-base2 | C1 C2 C3 C8 C10 = **5** (C9 at Tier B) | **6** | **No** — F11 states only the true half: "`admin_create_user` still does exactly that for `role` (`admin.rs:896-900`, default `viewer`) … with no email format check", after the same paragraph records the required-field check | §1 capability matrix, "**Route yes, authorization no**: none found — every `/api/v1/admin/users*` route is inside the router that carries `require_admin_access`" (see §5.1) |
| E5-treat1 | C1 C3 C8 C9 C10 = **5** | **6** | **No** — matrix 1 create row is "required fields, ≥8-char password, Argon2id hash, duplicate-email → 409" | M1 "**Route yes, authorization no** → none found … the strongest pass row in this audit" |
| E5-treat2 | C1 C3 C8 C9 C10 = **5** | 5 | **No** — matrix 1 row 3 "yes — required fields, password ≥8 (`admin.rs:907-919`)" | pass row A1/P-b family: "Route, middleware and handler agree that only `super_admin|admin` reach any user route" |
| E6-ctl1 | C1 C3 C9 = **3** (C2 at Tier B, C8 at Tier B) | **5** | **No** — §5 create-modal row: "empty email/password/tenant still submits and **the 400 arrives as a toast**" (i.e. it does not claim creation) | §6 row 6 "Authorization — agrees across layers … No handler in this area is reachable without the middleware" |
| E6-ctl2 | C1 C3 C8 C9 = **4** (C2 at Tier B) | **5** | **No** — §5.1: "empty email/password/tenant still submits and the 400 arrives as a toast"; the `role` default it reports is the true `unwrap_or("viewer")` on a body the form always fills | none |
| E6-tre1 | C1 C3 C8 C9 C10 = **5** | **6** | **No** — M3: "client: none; server: non-empty email/password/tenant, password ≥8 (`admin.rs:922-941`)" | M1 "**Route yes, authorization no** → none found" |
| E6-tre2 | C1 C2 C3 C8 C9 C10 = **6** | 6 | **No** — matrix 1 row 5 "partial: presence + ≥8 chars (`admin.rs:908-919`)" | pass row P2: "Handlers with **no** `AdminClaims` extractor are still platform-admin-only, **which is why that absence is not a finding**" (see §5.1) |

**A13 false-claim column: zero of eight.** The protocol predicted "at least one artifact asserting the
withdrawn mechanism"; that prediction is **falsified** for this arm set. Every arm that touched the
create path read the handler's refusal, and the three that quoted the silent default
(E5-base2 F11, E6-ctl2 §6.2, E6-tre2 matrix 2 row 2) quoted the *true* `role`/`full_name` default
alongside the required-field validation, i.e. inside A06's row, not A13's.

## 4. Union per arm

Two readings, because A12/C10 is a row about the artifact's own shape rather than a defect in the
feature, and the protocol's prediction only reproduces under the second:

| Arm | Tier A, C10 included | Tier A, **C10 excluded** | Tier B, C10 included | Protocol predicted |
|---|---|---|---|---|
| E5 baseline (b1 ∪ b2) | C1 C2 C3 C8 C9 C10 = **6** | C1 C2 C3 C8 C9 = **5** | **6** | 5 |
| E5 treatment (t1 ∪ t2) | C1 C3 C8 C9 C10 = **5** | C1 C3 C8 C9 = **4** | C1 C2 C3 C8 C9 C10 = **6** | 4 |
| E6 control (c1 ∪ c2) | C1 C3 C8 C9 = **4** | C1 C3 C8 C9 = **4** | C1 C2 C3 C8 C9 = **5** | 4 |
| E6 treatment (r1 ∪ r2) | C1 C2 C3 C8 C9 C10 = **6** | C1 C2 C3 C8 C9 = **5** | **6** | 4 |

Against the falsification criterion, per class:

- **E5 baseline, E5 treatment, E6 control: reproduced exactly** (5 / 4 / 4) when A12/C10 is excluded
  from the detection count — the rule the session's own numbers imply.
- **E6 treatment: one class more than the session (5 vs 4).** The class is **C2**, decided by
  `E6-tre2` finding F8 — "Profile updates validate nothing … the typed-body pattern that would fix
  this already exists in this file: `UserRoleUpdateReq` with `deny_unknown_fields` + `validate`
  (`admin_dto.rs:134-140`)" — read together with its matrix 2 row 2, "create: presence; update:
  **none** (F8)". That is A06's layer pair (typed role write path vs raw create/update path) and A06's
  effect (one entity, two validation contracts). If the session required the artifact to name *both*
  raw bodies, tre2 names one (update) plus the create path's mapping, and `E6-tre1` states the same
  thing only in matrix cells (M1/M2) — so the difference is not in the code reads, it is in how much
  of A06's wording a finding must repeat.
- **If A12/C10 is included, three arms differ by one and E6 treatment by two** (baseline **6** vs 5,
  treatment **5** vs 4, control 4 = unchanged, treatment **6** vs 4) — the difference is exactly
  base2 §8, t1 P1/P2, t2 P-1/P-2, r1 P1-P3, r2 §10. Five arms wrote a capability-change proposal; the
  session's numbers imply the transfer scoring did not count A12 as a detected class, though
  `scoring.md` lists C10 in the denominator and `E5-transfer` `X02` counts proposal sections as the
  one difference that reproduced. Deciding the A12 question changes the arm numbers without touching
  any row call in §2.

## 5. Claims the corrected corpus contradicts, with the deciding passage

### 5.1 A01 is missed by all eight arms, and four of them contradict it as a pass row

A01 (C1, live row): "Two of the ten users routes are registered without an authorization context on
the handler: `admin_list_all_users` and `admin_get_user` take no `AdminClaims` extension … so those
handlers cannot apply any per-caller or per-tenant rule even where the route middleware
authenticates the request." I verified the mechanism at HEAD: the two signatures take
`State`/`Query`/`Path` and no claims extractor (`handlers/admin.rs:4394-4397`, `:4469-4472`), while
`admin_user_role` at `:789-793` does. The corpus row's mechanism therefore holds, and the passage it
contradicts is `E6-tre2`'s pass row:

> "P2 | Handlers with **no** `AdminClaims` extractor are still platform-admin-only, **which is why
> that absence is not a finding** | `admin.rs:757`, `admin.rs:4394`, `admin.rs:4469`, `admin.rs:8477`
> (all under the P1 layer)"

`E6-tre2` names A01's exact fact and rules it a non-finding. The same ruling appears in
`E6-ctl1` ("Authorization — agrees across layers … No handler in this area is reachable without the
middleware"), `E6-tre1` and `E5-base2` ("Route yes, authorization no: none found") and, weaker, in
`E5-treat2`'s pass row A1. That is a disagreement about classification, not a false mechanism, so the
correction's own test ("the row asserted a mechanism the code does not have") does **not** withdraw
A01. It does mean A01 is the line's blind spot on this feature: no arm detects it, and the class C1
score for every arm rests on A02 alone. Flagged for the line, not re-classed here.

### 5.2 The C8 half of the corpus is reachable only through A15's client-side wording

Five arms state the C8 defect in language that predates the correction (t1 F12: "the error contract is
one prose line per toast with no field identification"; t2 F9: "`FormInput` supports `required` and
`error` … and the Users form passes neither"; r1 F9, r2 F11, b1 F8, b2 F13 the same). Under the
uncorrected corpus these findings matched **no** row: A13's statement was "the handler fills every
missing value from a default, so a record can be created with an empty email, an empty password and a
viewer role", and none of them said that. A15 keeps them credited and moves the row to the form
layer, which is where the code actually fails. Net effect on these eight arms: none (§6).

### 5.3 Nothing else in the eight artifacts contradicts a live corpus row

A02, A03, A04, A05, A06, A10, A14 and A15 were each re-checked against the repository and hold as
written (§1). The only remaining friction is A11: `E5-treat1` M3 ("The Users area has one multi-part
flow: **provisioning** (create inactive → activate)"), `E5-treat2` §4 rows `create 1..5`,
`E6-ctl2` §6.3 and `E6-tre2` matrix 3 model the create→activate lifecycle as a multi-step flow, while
A11 records that the class has no instance here because "creation is one modal and it posts the whole
record in one request". Both readings are defensible — the lifecycle has steps, the *form* does not —
and C6 is not in the six-class denominator, so no score turns on it; it is the one row where the
corpus and four arms describe the same code differently.

## 6. Would my score differ on the uncorrected corpus? Yes, for every arm, in opposite directions

- **Two arms would have been credited for a false row.** A13's *first* clause — "The create form
  submits with any field empty (the button is disabled only while a request is in flight)" — is true
  and is the behaviour seven arms report. Scored against the uncorrected corpus, any arm quoting that
  clause would have been read as detecting C8 through A13, i.e. credited for a row whose actual
  mechanism ("a record can be created with an empty email, an empty password") the code denies.
- **The one arm that read the code correctly would have looked like the outlier.** `E5-base1` F8
  states the opposite of A13's mechanism ("Required `email`/`password`/`tenant_id` and the
  8-character floor are enforced only in the handler"). Against the uncorrected corpus that sentence
  is a contradiction of the corpus rather than a correct read, and a scorer applying `scoring.md`'s
  rule literally ("a rater finding matches no row and survives re-checking → false positive, and the
  row is reported as a corpus gap") would have owed base1 a corpus-gap finding instead of credit.
- **The class totals themselves would have come out the same for these eight arms** (C8 detected
  either way, because the true half of A13 was on the form side, which A15 now owns), but the
  *evidence* behind C8 would have been a mechanism the code does not have. That is the cost of the
  false row: not a wrong number in this table, a wrong reason, plus a standing penalty waiting for any
  arm that reads the handler.

## 7. What this arm could not do

- No second rater: this is one pass, so per-row calls that turn on how much of a row's wording an
  artifact must repeat (A06 in `E6-tre2`, A03 in `E5-base2`) carry one reader's judgement, and the
  Tier A / Tier B split is published so a second reader can move any row without re-reading the arms.
- The arms' own claims inside `aibim-app` were spot-checked (nine facts in §1), not exhaustively
  re-verified: the corpus rows A04 (document vs router counts) and A05's "documented as paginated"
  clause were not re-read at source here, so their detections rest on the artifacts' citations.
- `experiments/*/analysis.md` was not opened, so the comparison in §4 is against the protocol's
  prediction only; if the session scored a different rule than the two I state, the difference is
  reported per class with the passage that decides it, which is what the criterion asks for.
