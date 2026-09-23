# E3 - detection with the candidate artifact: result

## What ran

**Five** independent rater contexts applied the frozen artifact
(`skills/feature-audit/SKILL.md` as committed) to the same feature the baseline arm
audited. Two of the five were launched as replacements and finished after the first
scoring pass; all five are scored here on the same rules.

| Rater | Matrices filled | Passes | Findings | Capability-change proposals |
|---|---|---|---|---|
| E3-raterA | five matrices filled; 96.8 kB artifact | 3 | 16 | 2 |
| E3-raterC | five matrices filled; 62.5 kB artifact | 3 | 14 | 1 |
| E3-raterB | M1 12 rows / 60 cells; M2 11 rows / 88 cells; M3 6 rows; M4 6 rows; M5 33 rules (20 pass, 7 findings, 6 n/a) | 3 (first-time user, keyboard + measurement + axe with `target-size` enabled, API client with a minted ADMIN token: 403 / 400 refusals probed with no write) | 15, each with class, citation, Prevent line | 2 (P-01, P-02) |
| E3-raterD | M1 12 actions x 5 layers; M2 9 fields x 8 columns; M3 1 flow x 7 columns; M4 7 triggers x 5 columns; M5 38 rules | 3 (first-time operator, daily operator with widths measured, API client) | 18 | 1 (all 9 headings, plus a per-finding statement that its fix names no absent layer) |
| E3-raterE | M1 10 rows; M2 16 rows; M3 6 rows; M4 6 rows; M5 26 rules + a 4-surface x 8-state table | 3 (browser walk, keyboard + measurement + axe, API client) | 12 + 2 sub-findings | 2 (each with a rejectable artifact: OpenAPI + contract test + flag + ADR) |

Two earlier passes were voided when the artifact was rewritten mid-flight (they had
read the thin first version) and one rater reported the shared browser session being
signed out by a stray click mid-run; both are environment facts. Every rater ran
three passes from different entry points, and every rater declared its own coverage
gaps rather than filling them.

## Scoring

Scored against the same frozen corpus as E2, by reading each artifact's findings and
matrix cells, with the judgement model as a cross-check over the same rows. The model
again over-counted a pass row as detected and under-counted one bundled row; the
hand score is the reported one.

| Class | E2 baseline (3 raters) | E3 treatment (3 raters) |
|---|---|---|
| C1 capability | yes (1 of 3) | yes (3 of 3) - the two declared-and-unreached endpoints, plus the offered-but-refused role |
| C2 field contract | no | **yes (2 of 3)** - `locale` carried and rendered nowhere; the missing autocomplete token |
| C3 list convention | yes (2 of 3) | yes (3 of 3) - the in-memory filter, the constant page envelope, and a citation to the repository's own api-contract doc |
| C4 search | yes (half, 1 of 3) | yes (2 of 3) - the casefold probe (`SAHIBI` vs `sahibi`) and the unannounced result count |
| C5 interaction dependency | no | no (the picker that would show it is unreachable in this organisation) |
| C6 flow prerequisites | out of scope | out of scope |
| C7 data-view layout | yes (3 of 3) | yes (3 of 3) |
| C8 smart defaults | no | no |
| C9 destructive confirmation | no | **yes (1 of 3)** |
| C10 capability-change slot | **no - 0 proposals** | **yes - 5 proposals** across the three artifacts |

**Union: baseline 4 of 9 in-scope classes, treatment 7 of 9. Per-rater classes:**
baseline 2 / 3 / 3 (median 3); treatment A 5, B 6, C 5, D 4, E 4 (median 5). Every
class the treatment adds is one the baseline's own raters could have reached and did
not, and the two classes C9 and C10 appear in the treatment alone.

## Where the treatment differs beyond the count

- **The proposal slot was used, five times.** E2's three artifacts ended in UI and
  copy recommendations for defects whose fix needs a layer that does not exist; E3's
  three wrote five proposals, each naming the seam, a contract delta, a rollout with
  a flag and a kill switch, a verification that fails before and passes after, and an
  ADR - and two of them stated, per remaining finding, that its fix names no absent
  layer. That sentence is the check the artifact asks a reviewer to run, and it
  appeared unprompted.
- **Coverage became countable.** All three state how many matrix rows were checked
  and which could not be (no credential, no second user, axe unavailable in one
  case), so the classes they did not reach read as scope rather than oversight.
- **Agreement rows were recorded** (the same permission key on all five endpoints and
  the surface gate; SUPER_ADMIN refused at three layers), which the baseline never
  did.
- **The cost is visible too.** One rater could not run axe and hand-measured contrast
  and target sizes; another could not authenticate to the API and left one row
  code-only. Both said so.
- **The raters found defects the corpus does not hold**, including an invitation with
  no delivery path (a discarded password, no mail provider, a push to a device that
  cannot exist), a Turkish casefold applied to e-mail addresses under a unique index,
  and an unreachable permission-denied branch. The corpus is a floor, not the truth.

## Limits

- One feature, one stack, one model family; five passes is five passes, not five
  people.
- The class count depends on hand adjudication of bundled rows; the model
  cross-check is reported with its disagreements.
- C6 was out of scope for both arms (its rows live on a different route), so the
  denominator is nine classes.
