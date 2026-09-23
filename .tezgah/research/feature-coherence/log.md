# Research log

Newest last. One line per decision, experiment, dead end or pivot, with the
evidence that drove it.

## 2026-09-20

- user: states the defect class on an admin users area (capability/CRUD, field existence, UI consistency, search dropdowns, post-selection state, wizard prerequisites, form-structure redesign, smart form patterns, user-benefit UX, and never proposing the infrastructure change); asks for research with subagents.
- ai-executed: E1 - read one real feature end to end and froze 15 defect rows in 10 classes (sha256 70871644e095372e6e9a5faa5fa761d8dee60c87e82eaca33d5dd857a938d1a6). 10/10 classes present; 9 of 13 defect rows invisible from the screen alone.
- ai-executed: E1b - drove the running app. Confirmed 3 rows at runtime, added 2 the reading missed. Its own prediction (that the capability rows are runtime-settleable) failed: the admin calls the API from the server, so the browser log for /users holds one entry. Recorded as the arm's finding.
- user-revised: not a form-only audit - every interface element and data view is in scope; and a feature-level ask must reach the rule (5 of 6 armed nothing at HEAD).
- ai-executed: E2 - three blind raters ran the shipped rubric. Union 4 of 10 classes, median 3; 14 findings each; no rater proposed a capability change. Prediction hit on both counts.
- ai-suggested: the fix is a feature-unit method plus a required proposal slot, not more prose about the same screens.
- ai-executed: shipped skills/feature-audit/SKILL.md, the product-rule coherence paragraph, the feature-surface hints (9/9 positives armed, 0 false arms on a 10-prompt negative set), skills/product-analysis wiring and docs/feature-audit.md.
- user-revised: the first skill text was too thin and the pm layer did not consume it; the skill was rewritten with the researched 40-rule table and the consumption wired.
- ai-executed: E4b - the static contract-vs-call-site probe reproduced D01/D02 in 3.09 s with no credential and no running app. Prediction hit.
- ai-suggested: E4 (the two-arm mechanism ablation) was not run; recorded rather than dropped.

## 2026-09-21

- ai-executed: E4b - the static contract-vs-call-site probe reproduced D01/D02 in 3.09 s with no credential and no running app (session-2, recorded here again after the tree moved).
- ai-executed: E5 - the artifact on a second, differently-architected feature (corpus frozen at sha256 9c72a2d4...). The claim that the effect transfers was made falsifiable by two raters per arm; the pair read level, so the transfer claim could not rest on it.
- ai-executed: E6 - the pre-wiring rubric extracted from commit 0f452df, 2 raters per arm on the same feature. Control 4/6 and treatment 4/6 in the pair's own reading; the independent re-score (E12) of the same eight artifacts reads it control 4, treatment 6.
- ai-executed: E7 - a corpus row the first freeze got wrong was found by a pass that had the source open; withdrawn and replaced, the corpus re-hashed.
- ai-executed: E12 - two independent re-scores. The first surfaced a frozen corpus overwritten by a later results write (restored, hash verified) and a scoring rule that counted findings but not matrix cells, which had under-counted both arms; the corrected rule is committed beside the score.
- ai-executed: E8 - three raters per arm on the first feature, independently scored: artifact 7 defect classes, pre-wiring rubric 6 (per-artifact rows 8/7/6 against 4/6/4). 13 of 13 artifact-following artifacts wrote at least one capability-change proposal against 2 of 5 pre-wiring; the difference is a discipline the artifact requires, not a kind of thinking it supplies.
- ai-executed: E9 - the second stack was brought up (COMPOSE_PROJECT_NAME=fce9, its own target unchanged, torn down after). The repository's make admin-dev never reaches its own users surface - the frontend crash-loops on an nginx upstream the dev composition does not start - which is the audited defect class found in the tooling. After a docker-only bridge: 13 ui-observed rows and the layout class (columns clipped and unreachable at 320, and at 768 with a long row).
- ai-executed: E10 - seven comparable products read at first hand (URL and date each); all seven deliver the invitation credential in-product, which turns the session's severity-4 finding into a market gap.
- ai-executed: E11 - the two evidence classes every arm declared unreachable were looked for wrongly: both products carry a wired, disabled analytics seam (noop sink, switch default off, consent false, and in the first product no caller ever passes enabled) and real user-voice sources (support tickets and messages, a customer-portal free-text request).
- ai-suggested: the seven claims these runs support are recorded with the CLI rather than prose; the line is concluded and the review is refreshed over the final claims.
- user-revised: the second target stays in the line (asked directly whether to keep it; the answer was keep), so the transfer experiments, the runtime run and the competition and source reads remain as they are.
- ai-executed: the six-pass distribution, the runtime run, the competition axis and the source reachability all landed in findings.md, the report and docs/feature-audit.md, with the proposal claim rewritten to what the 18 artifacts support.

## Repair pass, same session

- ai-executed: an independent review of the concluded line (six dimensions, verbatim quotes) found record-level defects rather than scientific ones: two claims naming proof artifacts that do not hold their decisive content, six claims written without an id, a proposal tally (13 of 13) that the record cannot reconstruct, result rows citing evidence files that do not exist, a duplicated block in findings.md, and a Limits bullet contradicting the report's own measurement table.
- ai-executed: the proposal tally was recounted independently, artifact by artifact, with the count standard and every borderline written down (`experiments/E8-more-passes/proposal-tally.md`): 14 of 14 artifacts following the artifact wrote at least one capability-change proposal, against 2 of 5 following the pre-wiring rubric under a heading-only reading and 3 of 5 by content. `E8-B1` is the case that keeps the claim honest - it proposed the same absent layers under a recommendations heading.
- ai-executed: the six missing ids were added and C09's statement corrected in place (13/13 was a mis-recording, not a finding overtaken by evidence, so no supersede link is left behind); C08 and C13 were repointed at the artifacts holding their numbers; the three result rows naming absent files were repointed at `raw.md`; the six first-feature artifacts' raw copies came in from the scratch dir.
- ai-executed: `report.md` was rewritten where it contradicted the record - the Answer now carries the final ordering, the Limits no longer claim E4 never ran, the one-stack limit became two, and the two check warnings replace the older single-FAIL sentence.
- note: `claims.jsonl` is written through the CLI; the id fields and this one statement were repaired by hand because the CLI appends and derives only `kind`, and a record that cannot be cited by number is the worse defect. The repair is recorded here rather than left implicit.
- ai-executed: the reviewer's three remaining findings were closed: E1's pass-row count corrected from three to two (the scoring rule lists D09 and D15), the nine screen-invisible rows enumerated in full (D11 and D12 were omitted from the sentence while the arithmetic already counted them), and C06 scoped to what a committed artifact proves - the arming matcher's 8 positives and 7 negatives in `tests/test_context.py`, with the session's larger 9/10 sample named as recorded in `log.md` and carrying no run artifact.

## Closure pass, 2026-09-22

- ai-executed: no run and no model call - the two `check --strict` items this line still carried were settled as limits instead of by editing frozen evidence. E4b's protocol stays byte-identical (its own P03 pins the committed text at sha256 e40561f548decbd4), and the warn it draws was read before it was believed: the checker's falsifier rule is a denial test over words anywhere in the file, and the `no` of `no browser.` reaches the `falsify` of `## What would falsify it` because the rule allows up to four tokens between them (`browser.`, `##`, `What`, `would`), so the protocol does state a criterion and the checker is what misreads it. Editing it after its results is what the order rule refuses, so the warn stands, recorded here and in the report's Limits.
- ai-executed: each of the three `literature/INDEX.jsonl` rows now states in its `quality` field why it carries one record per source - a standard, vendor documentation and repositories are primary documents with no second bibliographic record, and a mirror is not one - so the warn reads as the honest state of the record rather than as an omission a later reader would have to explain.
- ai-executed: the report's Limits section now carries both, with the checker-misreads-the-protocol reading and the single-record reason named rather than the older "each note cites its sources in one line rather than two", which described the shape and not the reason.
