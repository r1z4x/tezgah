# E6 - the pre-wiring control on the second stack: result

## What ran

Four rater contexts on the same feature as E5 (the admin Users area of `aibim-app`),
same bucket of blindness, code-scope, differing only in the rubric:

| Arm | Rater | Rubric | Findings | Matrices | Proposals |
|---|---|---|---|---|---|
| control | E6-ctl1 | `product-analysis-pre-wiring.md` (323 lines, from commit `0f452df`) + `research` | 13 | improvised from the feasibility axis | 0 |
| control | E6-ctl2 | same | 8 named + a full five-axis report | capability 11 rows | 0 |
| treatment | E6-tre1 | current `product-analysis` + `feature-audit` | 15 | 5 matrices + a 15-row state matrix | 3 |
| treatment | E6-tre2 | same | 15 | 5 matrices, 46 numbered rows | 1 (all 9 headings, rejectable artifact) |

Both control raters reported axes the pre-wiring text asks for and filled matrices
anyway - the feasibility axis ("intended vs implemented, both sides cited") invites a
capability comparison on its own, which is why the control arm is not the weak
baseline E5's missing contrast assumed.

## Scoring

Against the frozen second corpus with the correction in
`E5-transfer/corpus-correction.md` applied (A13 withdrawn as false; A15, the client
guard and the toast-only refusal, carries class C8). Six defect classes.

| Class | Control union | Treatment union |
|---|---|---|
| C1 capability | yes (A02) | yes (A02) |
| C2 field contract | yes (A06) | no |
| C3 list convention | yes (A05, A14) | yes (A05, A14) |
| C8 form pattern | no (ctl2 asserted the withdrawn mechanism - a false claim, not a detection) | no |
| C9 destructive confirmation | yes (A10, ctl2) | yes (A10, tre1) |
| C10 capability-change slot | **no - 0 proposals** | **yes - 4 across two artifacts** |

**Control 4 of 6, treatment 4 of 6.** E6's prediction - control at most two, treatment
at least four, a gap of at least two - is **falsified on the control half and on the
gap**, and confirmed only on the treatment half. The before/after difference measured
on the first feature (4 of 9 against 7 of 9) did **not** reproduce on the second
stack.

## What the two features together say

- **The one difference that reproduced is the output slot.** Control artifacts wrote
  **0** capability-change proposals on both features; treatment artifacts wrote **5**
  (feature 1) and **3** (feature 2). Detection varied with the rater; the proposal did
  not vary at all, because the artifact requires one and the pre-wiring rubric has no
  element for it.
- **Detection is rater-dependent, and the second stack shows it plainly.** The
  pre-wiring rubric with a diligent rater reached four of six classes here, so a
  class-count difference between arms on one feature is not attributable to the
  artifact without repeated passes.
- **The correction matters more than the contrast.** E7 showed the class C8 row was
  false, and a wrong row manufactures agreement: an arm that reported the story the
  corpus told it looked like a detection. The corpus is the instrument; a false row in
  it is a measurement error, not a scoring nuance.
- **Both arms found defects the corpus does not hold** (an admin able to demote a
  platform owner, self-deactivation with no guard, a permission editor that saves an
  empty set, a `?result=` state that survives a reload), which is the third and fourth
  time this line has had to say that its corpus is a floor.

## Limits

- Two raters per arm, one feature, one prompt shape; the arms differ in a text the
  raters were told to apply, and both arms were allowed to read the repository freely.
- The control text was extracted from history and is authentic, but no rater knew it
  was old; that is deliberate, and it means the arms measure the text, not a
  chronological before/after of the same session.
- C8's corrected row (A15) was reached by neither arm unprompted, and by both prompted
  raters in E7 - declared here rather than folded into a "miss".
