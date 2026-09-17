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
