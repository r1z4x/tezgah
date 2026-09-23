# E4 - does the probe carry the detection, or the prose? Result

## What ran

Two rater contexts applied the frozen `feature-audit` artifact to the same feature
as E3, with one instruction added: run the probe in this experiment's protocol before
filling the capability matrix, and record its output as that column's evidence.

Both ran it, verbatim, and both embedded the output:

    contract-only: ['GET /users/{id}', 'POST /users/{id}/deactivate']
    surface-only: []

| Rater | Probe | Matrices | Findings | Proposals |
|---|---|---|---|---|
| E4-armB-rater1 | exit 0, 1.81 s | 5 matrices (9 / 11 / 4 / 9 / 37 rows) | 17 | 2, each with a rejectable artifact (OpenAPI diff checked by `verify-api-contract.mjs`, a flag with a lifetime, an ADR) |
| E4-armB-rater2 | exit 0 | 5 matrices (11 / 13 / 6 / 8 / 45 rows, 2 cells `[NOT CHECKED]`) | 25, 10 pass rows | 2, each with a contract delta, dated migration phases, a flag with an owner and an abort threshold, and an ADR |

Arm A is the E3 arm: five raters, same artifact, same feature, no probe instruction.
Both arm B raters also read the running app, as arm A's raters did.

## Scoring

Same corpus and rule; judgement model as the cross-check (it again counted the pass
row D15 as detected, in every arm, and is ignored for it).

| Arm | Per-rater classes | Union | Capability-change proposals |
|---|---|---|---|
| A - artifact, no probe instruction (5 raters) | 5, 6, 5, 4, 4 (median 5) | C1, C2, C3, C4, C7, C9, C10 = **7** | 5 across the arm |
| B - artifact + mandatory probe (2 raters) | 6, 6 (median 6) | C1, C2, C3, C4, C7, C10 = **6** | 4 across the arm |

**The prediction was that the two arms detect the same classes, and a difference of
one class or more in B's favour would support H4.** They did not: B's union is one
class *below* A's (A's raterB reached C9, destructive-confirmation content; neither B
rater did), and the class B was expected to gain - the capability rows the probe
settles - was already reached by every rater in both arms.

## What this means

- **H4 is not supported: the probe is a convenience, not the mechanism.** The
  matrices already force the comparison the probe performs; a rater filling the
  capability matrix by reading arrives at the same two declared-and-unreached rows.
  The probe's value is that it makes the row cheap and re-runnable (1.81 s, no
  credential, exit code), not that it finds something the method misses.
- **The one-class difference is rater variance, not a probe effect.** Selecting
  evidence class C9 in one artifact and not another is what the E2 arm showed within
  a single arm (2 / 3 / 3 across three raters). With two raters per arm, a one-class
  difference is not attributable, and it is reported as unattributable rather than
  interpreted.
- **Both arm B raters found a defect no other rater has**, including the role write
  path collapsing a multi-role set to one on save (rater2's F3) - the third time in
  this line that new raters added a class of defect the corpus did not hold.
- **Disclosures from the arm** (recorded, not scored): rater2 flagged that the
  assignment told it to run the probe while the batch constraints forbade reading the
  research directory, read only that one protocol file, and said so; it also re-read
  a prior design note under `docs/design/` that the earlier arms were told to avoid.
  Its citations (146 `path:line`) were re-resolved against the files afterwards.

## Limits

- Two raters in arm B against five in arm A: the comparison is directional.
- Both arms could read the running app and did; a probe-less arm without app access
  would not have been comparable.
- The probe compares the contract against one app's call sites; rater2 noted this is
  one-directional and searched the mobile client and the shared API client package
  itself before accepting the two rows - which is the reviewer behaviour the artifact
  asks for, not something the probe supplies.
