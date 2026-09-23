# E8 - more passes per arm: result

## What ran

Six rater contexts on the first feature, three per arm, blind to the corpus and to each
other. Arm A applied `feature-audit`; arm B applied the pre-wiring rubric extracted from
history (`E6-pre-wiring-control/product-analysis-pre-wiring.md`), which has no proposal
element and whose brief said nothing about proposals. Two of the three arm-B raters and
two of the three arm-A raters had the running app available and used it.

Scored by an independent pass in the two-tier rule the second feature's re-score used
(tier A: a numbered finding, a named section, an explicit verdict; tier B: tier A plus
matrix and contract cells).

## Results

| Arm | Per-artifact tier-A rows | Tier-A union | Classes (tier A) | Artifacts with ≥1 proposal | Proposals |
|---|---|---|---|---|---|
| A - artifact (3) | 8, 7, 6 | 9 rows | **7** (C1, C2, C3, C4, C7, C8, C10) | **3 of 3** | 7 |
| B - pre-wiring rubric (3) | 4, 6, 4 | 7 rows | **6** (C1, C3, C4, C7, C8, C10) | **2 of 3** | 4 |

Against the E8 prediction (arm A median at or above five and its union at seven; arm B's
union below arm A's): the union clauses are hit - A 7 classes, B 6 - and the median is
not comparable because the re-score counts rows, not classes, per artifact.

## What the extra passes changed

- **The distribution is wider than the pair suggested.** Per-artifact tier-A classes run
  7, 6, 5 in arm A and 4, 5, 4 in arm B: a single pair of raters can sit anywhere in that
  range, which is why the earlier before/after readings on one or two raters per arm
  could not be attributed to the artifact.
- **The proposal slot is a discipline difference, not a categorical one.** All three
  artifact-arm artifacts wrote at least one proposal (7 across the arm); two of the three
  pre-wiring artifacts did too (4 across the arm), and the re-score records that the
  pre-wiring rubric's recommendations section is where the same content lands when it has
  no proposal heading. The honest claim is therefore: the artifact *requires* the
  proposal, and the arm that follows it produced one every time; the rubric that omits it
  produced one two times in three.
- **Both arms contradict pass rows.** All three arm-B artifacts and one arm-A artifact
  reported a defect at the corpus's pass row D15 (where the UI and the server agree),
  which is the same error the judgement model made in the session's own scoring: a pass
  row is hard to leave alone, and a corpus that carries only defects cannot show whether
  an analysis distinguishes agreement from drift.
- **The re-score contradicts two artifact claims**: an arm-B artifact justified one dead
  endpoint as "kept for the mobile path" citing a contract test that covers other
  controllers, and three artifacts marked the search-announcement element a pass where the
  corpus records it as a defect.
- **The class the artifact did not buy on this feature is C9**, which no arm-A or arm-B
  artifact reached here (it was reached once in E3's five passes).

## Limits

- Three raters per arm is a distribution, not a sample: the medians are reported with the
  ranges, and no significance is claimed.
- The re-score's own sensitivity notes (D11's split criterion, D12's three elements, D14
  read at element level versus naming the element) are recorded in its artifact and move
  the B union by at most one row.
- Two of six raters had no running app, so their `ui-observed` rows are absent by
  construction and their counts are lower than the arm's other members.
