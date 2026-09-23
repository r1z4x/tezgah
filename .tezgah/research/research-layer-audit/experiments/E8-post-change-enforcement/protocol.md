# E8 protocol — the same eight probes, against the changed checker

Frozen 2026-09-20 before its run. **A child of E1, not an edit of it:** E1's probe
file stays frozen at sha256 `755239adddb…750` because a run already answered it,
and this experiment branches with two documented differences.

## Question

After the implementation session changed `check`, `claim` and the workspace
schema, does the same documented-rule probe set still pass a violating line?

## Locked evaluation

- **Metric**: refusal proportion over the same eight probes, plus per-probe
  attribution - *why* each refusal fired, read from the message, because several
  rules now carry two classes (a `FAIL` and a warn that `--strict` escalates).
- **Baseline**: E1 measured **0 of 8** on the pre-change checker (control 2 of 2).
- **Threshold**: any refusal above 0 is a change; the finding is the *set* and the
  attribution, not the count. A refusal for a reason other than the probe's rule
  counts as a miss, not as enforcement.

## The two differences from E1's frozen file, and why

1. The claim fixtures now carry `"kind": "evidence"`. `claim` requires the field
   after this change, so without it every claim probe would be refused for the
   missing field and the refusal would carry no information about the rule under
   test. This is the one thing the frozen probe could not anticipate.
2. P1's fixture sets `phase: "inner"`. The evaluation rule is a `FAIL` only once a
   line is past bootstrap (a brand-new line is not yet expected to have locked its
   criterion), and E1's fixture left the default phase. This makes the probe test
   the rule the spec states rather than its bootstrap exemption.

Both are stated in the run report; nothing else in the probe bodies changed.

## Cells and predictions

| probe | rule | predicted | reason |
|---|---|---|---|
| P1 | locked evaluation | **refused** | empty metric at `phase=inner` is a FAIL |
| P2 | protocol.md content | not refused | still unchecked - the spec did not add a content rule for `protocol.md` |
| P3 | results rows carry a source | **refused** | the file is not JSON: a parse error is a FAIL |
| P4 | a proof cites the evidence | **refused** | a proof naming no artifact is a FAIL for every kind |
| P5 | evidence with actual results | not refused (warn) | the spec's class: an empty `results.jsonl` warns, `--strict` escalates |
| P6 | a path the line never produced | **refused** | an `evidence` proof must resolve inside the line |
| P7 | session provenance tags | **refused** | a tag outside `PROVENANCE` is a FAIL |
| P8 | citations verified | **refused** | a literature note with no INDEX row is a FAIL |

Predicted refusal proportion: **6 of 8**, with P2 and P5 named as the exceptions
and P7's fixture (a `sessions` entry with a bad tag) expected to fail rather than
warn because the entry carries no date at all - the report says which rule fired.

## What would falsify

- A refusal whose message names a rule other than the probe's: attribution fails,
  and the probe counts as a miss.
- Fewer than 6 refused: an item the spec claims is enforced is not.
- More than 6 refused including P2: a `protocol.md` content rule landed that the
  spec did not ask for.
- The control from E1 not reproducing: the harness is broken, not the checker.
