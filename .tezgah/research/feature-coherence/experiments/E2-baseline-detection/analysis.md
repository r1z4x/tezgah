# E2 - baseline detection with the shipped rubric: result

## What ran

Three independent rater contexts, each blind to the corpus and to the class list,
each given `product-analysis` + `analyze-app` + `research` and the same feature (the
Ustam admin users area), each writing its own artifact:

| Rater | Findings | Classes it used | Passes it declared |
|---|---|---|---|
| E2-rater1 | 13 findings + 1 question | 8 `ui-observed`, 5 `code`, 1 `behaviour` | 1 rater, 2 passes + a repeat on the top three |
| E2-rater2 | 13 findings | 7 `ui-observed`, 4 `code` | 3 passes, 1 rater |
| E2-rater3 | 14 findings | 7 `ui-observed`, 5 `code`, 2 `behaviour` | 3 passes by entry point |

Each also reported its own scorecard (3.6, 3.8 and 2.5 on the skill's anchors) and
each named what it could not produce. All three ran the app: two through the
harness's own Chromium, one through a cloned database on its own ports. Rater3
reported a hydration failure (5 JS chunks returning 403 in the dev server) and
recorded every interactive state as not driven because of it.

## Scoring

Scored against the frozen corpus plus the two runtime rows, by reading each
artifact's findings against each row (the ids below are the corpus's), with a
judgement model run over the same rows as a cross-check. The instrument disagreed
with the reading twice, and both disagreements are instructive rather than
concealed: it read the bundled C4 row as undetected although one rater reported one
half of it, and it scored the pass row D15 as detected by both raters.

| Class | Detected by | Row |
|---|---|---|
| C1 capability | rater2 | the reactivation comment vs `PATCH` vs the unused `POST /users/:id/deactivate` |
| C3 list convention | rater1, rater2, rater3 | the in-memory filter and the pagination envelope the service never computes |
| C4 search | rater3 (one half) | Turkish casefolding: `q=SAHIBI` returns 0 rows where `sahibi` returns 1 |
| C7 data-view layout | all three | the table measured at 1140 px inside 924 / 686 / 242 px containers |
| C2, C5, C6, C8, C9, C10 | none | field contract, interaction dependency, flow prerequisites, smart defaults, destructive confirmation, and the capability-change slot |

**Union: 4 of 10 classes. Per-rater: 2, 3 and 3 (median 3).** Against the metadata:

| Predicted | Observed | Verdict |
|---|---|---|
| union ≤ 4 classes | 4 | hit |
| median ≤ 3 | 3 | hit |
| the misses are C1, C2, C5, C6, C10 | C2, C5, C6, C8, C9, C10 (C1 was reached by one rater) | hit on the shape, one row off |

## What the baseline actually shows

- **The rubric can reach a cross-layer defect.** Rater2 found the unused endpoint by
  comparing a comment, the action and the controller; rater1 found the whole-org
  fetch as a feasibility drift. So the failure is not that the method forbids this
  work - it is that nothing requires it, and coverage is uneven across raters.
- **Three raters, three different subsets.** Only C7 was reached by all three; the
  union is 4 while the median is 3, which is what a method without a required matrix
  looks like: the analysis is as good as the rater's hunches, and the hunches differ.
- **The misses are the classes that need a second artifact in view.** The field
  contract needs the schema beside the form; the flow contract needs the wizard's
  states enumerated; the dependency matrix needs the app exercised after a
  selection; the capability-change slot needs the artifact to have one. None of the
  three artifacts proposed an infrastructure change for a defect whose fix needs
  one - the strongest single result of this arm, because it is not about detection
  at all.
- **The raters added classes the corpus did not hold** (an offer the system forbids;
  an invited account with no delivery path; a colour-only status distinction; a
  contrast failure axe left incomplete at 3.16:1). The corpus is a floor on what is
  findable, not the truth about the feature, and the union is therefore a lower
  bound on the baseline rather than a ceiling.

## Limits

- One feature, one stack, one model family for all three raters; the rater count is
  three passes, never three people.
- The raters were working in a session where the app was live and a previous pass
  had already located it; a cold session would likely score lower, not higher.
- Scoring by reading is a judgement; the model cross-check is reported with its two
  disagreements rather than presented as the ground truth.
