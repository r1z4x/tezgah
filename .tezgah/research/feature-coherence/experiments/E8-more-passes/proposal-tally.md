# The capability-change proposal tally, recounted

## Why this file exists

The line's claim about the proposal slot read "13 of 13 against 2 of 5". An
independent review could not reconstruct it: the record enumerated 14 artifacts in
the following arm and 5 in the control arm, and no artifact held a 13/18 tally.
This is the recount, with the count standard stated and every borderline disclosed,
so the claim rests on a file a reader can re-derive it from.

## Count standard

A capability-change proposal is counted when the artifact proposes a fix that needs
a layer the product does not have - a contract, permission, schema, event, or search
layer. A UI or copy fix, and a fix that wires an existing layer (rewire, delete,
relabel, render an existing field, filter on the client), does not count.

## The two arms

| Arm | Artifacts | With at least one proposal | Proposals counted |
|---|---|---|---|
| followed `feature-audit` | 14 | **14** | 22 in the 11 read line by line, plus at least one each in E3's raters A-C |
| followed the pre-wiring rubric | 5 | **2** under the heading reading, **3** under the content reading | 7 |

The following arm: `E3-treatment-detection/raw` (raters A-E), `E4-mechanism-ablation/raw`
(arm B, both raters), `E5-transfer/raw` (both treatment raters), `E6-pre-wiring-control/raw`
(both treatment raters), `E8-more-passes/raw` (arm A, three raters). The control arm:
`E6-pre-wiring-control/raw` (both control raters) and `E8-more-passes/raw` (arm B, three
raters).

## Per-artifact counts (the 16 the recount read line by line)

| Artifact | Arm | Proposals | Deciding heading |
|---|---|---|---|
| E3-raterD | following | 1 | `## Capability-change proposal` |
| E3-raterE | following | 2 | `## 10. Capability-change proposals` |
| E4-armB-rater1 | following | 2 | `## 9. Capability-change proposals` |
| E4-armB-rater2 | following | 2 | `## Capability-change proposals` |
| E5-treat1 | following | 2 | `## Proposals (capability-change; required because the fix names a layer that does not exist)` |
| E5-treat2 | following | 2 | `## 8. Capability-change proposals` |
| E6-tre1 | following | 3 | `## 6. Capability-change proposals` |
| E6-tre2 | following | 1 | `## 10. Capability-change proposal (required by F5)` |
| E8-A1 | following | 2 | `## Proposals` |
| E8-A2 | following | 3 | `## 7. Capability-change proposals` |
| E8-A3 | following | 2 | `## 7. Capability-change proposals` |
| E6-ctl1 | pre-wiring | 0 | none: every recommendation wires an existing layer |
| E6-ctl2 | pre-wiring | 1 (borderline) | no proposal heading; a numbered recommendation proposes a server-side permission invariant F1/F2 prove absent |
| E8-B1 | pre-wiring | 2 | `## 10. Recommendations`, with its own declaration that two fixes "name layers that do not exist yet ... which is why they are written above as recommendations rather than as capability-change proposals" |
| E8-B2 | pre-wiring | 2 | `## Capability-change proposals` |
| E8-B3 | pre-wiring | 2 | `### Capability-change proposal: yes, two` |

E3's raters A-C were outside the recount's contract; each carries proposal sections
(four, one and one), so the following arm is 14 of 14 under any reading. Their text
was read for this count after the recount, from the same archive directory.

## Borderline calls, disclosed

1. `E6-ctl2` is the one content-level count in the control arm. Under a
   heading-only reading the control arm has 2 of 5 artifacts with a proposal and 6
   proposals.
2. `E8-A2`'s second proposal is contract-disposition flavoured (call the dead route
   or remove the operation); under a strict absent-layer reading that artifact has 2
   and the following arm 21.
3. `E6-tre1`'s second proposal is consolidation-flavoured (one source for the role
   set, with an optional endpoint delta); the same family is counted in E3-raterE,
   E8-B2 and E8-B3, where each adds an `assignable` notion to the server.

## What the count does and does not support

It supports: the artifact **requires** the proposal, and every artifact that followed
it produced one, 14 of 14.

It does not support: that a rubric without the slot produces none. `E8-B1` proposes
the same absent layers under a recommendations heading and says so. The difference is
the slot and the rejectable artifact the slot demands - a heading that requires the
proposal, a diff a checker can refuse - not the ability to notice the missing layer.
