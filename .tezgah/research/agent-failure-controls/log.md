# Research log

Newest last. One line per decision, experiment, dead end or pivot, with the
evidence that drove it.

- 2026-09-17 decision: research line opened for the user's 44-mode taxonomy (plus the ten priority controls) plus
  the ten priority controls; question locked in `state.json`. Evidence: the
  request itself.
- 2026-09-17 decision: branch `research/agent-failure-controls` off `main`, not
  off the open `plan/010` branch, so the line does not inherit unmerged work.
  Evidence: `git log main..plan/010` lists six unmerged commits.
- 2026-09-17 dead end: none attempted yet on the compute axis; the existing orx
  project `tezgah-harness-research` carries a fixed run command
  (`bash benchmarks/arm-bench/orx-run.sh`) whose comparability the 2026-09-16
  study depends on, so it is not reused and not edited. `orx` is used for the
  literature loop and the workspace stays `tezgah-research`-checked.
- 2026-09-17 decision: instrument the two claims that can be measured against
  the installed rules without a model - gate coverage and Stop-rule coverage -
  and mark the rest of the taxonomy design work rather than implying it was
  measured. Evidence: `experiments/E1-*/protocol.md`,
  `experiments/E2-*/protocol.md`, both committed before any run (5ddae7d).
- 2026-09-17 experiment E1 (gate coverage over a 19-case labelled corpus):
  prediction confirmed exactly - 7/7 write-time controls refused, 12/12
  trajectory-time cases allowed, no mismatch. Evidence:
  `experiments/E1-write-path-coverage/results.jsonl`.
- 2026-09-17 experiment E2 (Stop rule over 20 completion claims and 7 openers):
  explicit claims 8/10 refused, implicit 0/10, verified ledger 0/20, openers 5/5
  with 0/2 controls refused. Instrument defect found and recorded: the summary's
  `mismatches` field compares verified-ledger rows against a per-case label.
  Evidence: `experiments/E2-completion-claim-coverage/results.jsonl`.
- 2026-09-17 experiment E3 (injected-context budget): `session_start` injects
  6,716 bytes, a conditional rule adds 414-766 bytes, and the falsifier for the
  lessons block fired (754 B growth against a 500 B allowance). A post-hoc
  exploratory measurement settled the question the failed allowance obscured:
  the lessons block is byte-identical at 200 and 400 ledger lines, so every
  tezgah-injected block is bounded. Evidence:
  `experiments/E3-context-budget/results.jsonl`,
  `results-exploratory.jsonl`.
- 2026-09-17 decision: seven writers, one per taxonomy group, draft the
  per-mode control sections against the five scout inventories and the 38
  fetched paper notes; the router integrates, reviews and verifies them rather
  than writing all 44 modes in one context. Evidence: this log and
  `to_human/sections/`.
- 2026-09-17 decision attempt, failed: the synthesis's five-gap cut was put to
  `consult` (Gemini + Grok via OpenRouter) before the sections landed; both
  providers answered HTTP 403 "Key limit exceeded", so the external second
  opinion was skipped and the report says so. Evidence: the consult output in
  this session; no claim in the report is corroborated by an external model.
- 2026-09-17 correction: three literature ids (`2605.05403`, `2608.29646`,
  `2608.25920`) were named in writer briefs but were not in `literature/` when
  the sections that cite them were written; all three were fetched afterwards and
  the two sections that flagged the gap carry a note recording it.
- 2026-09-17 review: two independent read-only passes checked 39 claim-level
  defects across the seven sections (8 major, 3 stale anchors caused by edits
  made while the pass was reading). All were applied; the dominant class was an
  absence claim stated as "returns only" over a grep that returns more. Evidence:
  `to_human/review.md`.
- 2026-09-17 decision: two cross-section conflicts were resolved by the router
  rather than patched locally - one ledger schema (P1) and one attempt counter
  (P4) now live in the synthesis, and F6/G6/G7/F4/G10 reference them. Evidence:
  `to_human/synthesis.md`, "Shared primitives".
- 2026-09-17 conclude: the report is assembled as
  `to_human/agent-failure-controls.md` (frame, synthesis, the seven sections, the
  review, reproduction). The line's deliverable is the evidence and the design;
  implementing any control is follow-on work, not claimed here.
- 2026-09-17 experiment E4 (mechanical-off block, 60 runs): no measurable
  difference between the arms. Two of the three tasks were passed 5/5 by every
  arm including the bare anchor; the only task that moved did so by one run.
  All six failures were the same mistake with the same completion claim, spread
  across the arms. Evidence: `to_human/blocks/E4-mechanical-off-effect/results.jsonl`,
  `analysis.md`.
- 2026-09-17 correction: the E4 block was filed under `to_human/blocks/`
  (bd68a36) after its run, so every evidence pointer that still said
  `experiments/E4-mechanical-off-effect/` was stale - `claims.jsonl` (C10,
  C11), `state.json` (H7) and the log line above now name the real
  location, and the block's own protocol keeps the pre-move command.
  `tezgah-research check` grew the rule that found it: a claim's proof must
  name a path this line has.
- 2026-09-17 lesson: a task must be piloted for ARM-level separation (k=1 per
  arm) before a block is spent on it. `bench.py selftest` proves a task separates
  fixture from gold, which is a different property, and E4 paid for the
  difference.
- 2026-09-17 decision: the external second opinion ran for real this time (the
  env OpenRouter key is over its limit; the file key has $18.66 left). Gemini and
  Grok agreed that the ledger's action identity is the load-bearing change and
  disagreed on the priority order; the referee picked Gemini. Recorded in
  `to_human/synthesis.md` next to the design cut.
