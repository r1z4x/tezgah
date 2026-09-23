# E12 - the independent re-score: result

## What ran

One pass, independent of the session that built the corpus and the earlier scoring: it
read the four E5 artifacts and the four E6 artifacts against the corrected corpus
(A13 withdrawn, A15 in its place), re-ran the code checks the corpus rows rest on, and
recorded detections in two tiers - **tier A** a numbered finding, a named section or an
explicit verdict, **tier B** tier A plus matrix and contract cells that state the defect.

It reported two things the session had not noticed, and one number that changes a
conclusion.

## Finding 1: the instrument had been overwritten

`experiments/E5-transfer/results.jsonl` no longer held the 14 corpus rows - an earlier
commit in this session (the one that gave every experiment its result rows) replaced
them with the run rows X01/X02. The re-scorer recovered the corpus from git
(`452c533`, 9875 bytes, A01-A14) and scored against that. **The file on disk was the
wrong artifact.** Fixed at `f2e499f`: the instrument now lives in
`E5-transfer/corpus.jsonl` (sha256 `9c72a2d42f2c764d3b7614746f0abb1eabe60ed61e8c5d57c8393f366e505c5a`,
matching the freeze) and `results.jsonl` holds the run rows, each annotated with the
instrument's path and hash.

## Finding 2: the session's own scoring under-counted

Against the corrected corpus and tier A, the re-score gives:

| Artifact | Tier A classes | Tier A count |
|---|---|---|
| E5-base1 | C1, C2, C3, C8, C9 | 5 |
| E5-base2 | C1, C2, C3, C8, C10 | 5 |
| E5-treat1 | C1, C3, C8, C9, C10 | 5 |
| E5-treat2 | C1, C3, C8, C9, C10 | 5 |
| E6-ctl1 | C1, C3, C9 | 3 |
| E6-ctl2 | C1, C3, C8, C9 | 4 |
| E6-tre1 | C1, C3, C8, C9, C10 | 5 |
| E6-tre2 | C1, C2, C3, C8, C9, C10 | 6 |

| Arm | Tier A union | Session's earlier score |
|---|---|---|
| E5 baseline (post-wiring rubric) | C1, C2, C3, C8, C9, C10 = **6** | 5 |
| E5 treatment (artifact) | C1, C3, C8, C9, C10 = **5** | 4 |
| E6 control (pre-wiring rubric) | C1, C3, C8, C9 = **4** | 4 |
| E6 treatment (artifact) | C1, C2, C3, C8, C9, C10 = **6** | 4 |

Two differences matter:

- **C8 was reached by more arms than the session credited** (A15's client-guard and
  toast-only refusal is a form-pattern finding several artifacts state, in a matrix row
  the earlier scoring did not count).
- **E6's treatment arm reaches 6 of 6, not 4** - so on the second stack the pre-wiring
  rubric scores 4 and the artifact-with-wiring scores 6, a difference of two classes,
  which is the direction the first feature showed. The session's 4-against-4 reading
  came from scoring only numbered findings and from the lost corpus; with the corrected
  instrument and the tier rule, E6 confirms the transfer rather than falsifying it.

E5's ordering is unchanged in form: the post-wiring **axis skill alone** (6) is at
least as good as the axis skill plus the artifact (5) on that feature. Those two numbers
are the honest state of the marginal-value question: the wiring is what moves detection;
the artifact's reproducible contribution remains the proposal slot (C10: 0 in every
control artifact, present in five of the eight treatment artifacts).

## What this experiment is evidence about

- **An independent re-score is worth its cost.** Both problems it found - a destroyed
  instrument and a systematic under-count - were invisible from inside the session that
  produced them, and the second one changed a conclusion the line had already written
  into its report.
- **The two-tier rule should have been fixed before the first score.** Counting
  findings but not matrix cells systematically penalises the artifact whose whole
  method is matrices.

## Limits

- One re-scorer, one pass, no blind re-run: this is an independent reading, not a panel.
- Tier B is reported alongside tier A rather than merged into it, because a cell
  stating a defect and a finding naming one are not the same evidence weight - the
  table above uses tier A throughout, and the artifacts' tier B numbers are in
  `E12-rescore.md`.
