# Pre-registration: arm benchmark

Status: **frozen before any scored run**. Every number produced by `bench.py`
is read against this document, not against a post-hoc story.

## 1. Questions, in the order they are worth answering

1. **Harness effect.** At a fixed host and model, does the tezgah contract
   change pass rate, cost per successful task (CPS), or diff discipline?
2. **Host effect.** At a fixed harness state and model, do the hosts differ?
3. **Cost curve.** How does CPS move with task difficulty, and which term
   dominates (turns, output tokens, fresh input, tool calls)?

A ranking of hosts with the harness varying is not an answer to any of them; the
two factors are crossed, never conflated.

## 2. Design

- **Factors.** `host` x `harness` x `model`. Enumerate cells explicitly in
  `arms.json`; an arm is exactly one `(host, harness)` pair with a recorded
  command and environment.
- **Model.** At least two families. `--model` is part of the row, never a
  default that can drift.
- **Repeats.** `k >= 5` per cell for a scored run. One repeat per cell is
  description. Within-cell variance in agentic runs is large (a median
  geometric spread of ~1.34x in token spend per specification, "Can your AI
  agent be cheaper?", arXiv 2608.25399), so a single-sample claim is not
  admissible.
- **Pairing.** Every task runs under every arm in the same block, with the
  task fixture byte-identical apart from the arm. Randomise task order and arm
  order per repeat.
- **Two stages, cheap first.** Stage I ranks arms on single bounded decisions
  and shorter task slices; only the survivors of Stage I run the full task set.
  This is the LoopArena result (`arXiv 2608.28281`): slice-form evaluation cut
  estimated cost 64.4% while preserving the ranking (Spearman rho 0.9747).
  `bench.py` implements the full-task stage; slices are the next increment.

## 3. Endpoints

| Class | Endpoint | Rule |
|---|---|---|
| Primary | CPS = total cost of the arm / number of passes | Lower is better; reported with the pass counts it divides |
| Co-primary | Pass rate with a Wilson 95% interval | Never quoted without `k` and `n` |
| Secondary | Turns, output tokens, fresh-input tokens, cache-read tokens, tool calls by type | Recorded per run; used to attribute the CPS difference |
| Secondary | Collateral-edit rate and constraint compliance | `collateral` in every row; a pass that edits outside `allow` is not a pass |
| Secondary | Timeouts and no-usage rows | Counted and reported, never silently dropped |

A qualitative dimension (for example Turkish adherence) may be reported only
with a published detector, an explicit threshold, and chance-corrected
agreement. Raw exact-match agreement overstates chance-corrected agreement by
33.8-41.3 points on average (arXiv 2606.19544), so an uncorrected rate is not a
result.

## 4. Accounting rules (each one fixes a real defect of round 2)

1. **A timeout is never a pass**, and its cost is never zero. A timed-out row
   gets `pass=false` and `usage` from whatever the run actually reported.
2. **A missing usage block is `null`, never `0.0`.** `bench.py` writes
   `usage_note` when it finds nothing, so an arm total can never be silently
   subsidised by an unparsed run.
3. **Reasoning tokens are recorded separately.** Hosts disagree on whether
   reasoning is inside `output`; a cross-arm "output tokens" comparison without
   that split is meaningless.
4. **Both totals are published**: timeouts excluded and timeouts included.
5. **Every row carries provenance**: exact model id, host version, arm command
   line, prompt hash, fixture hash, timestamp. A row without them is not
   admissible evidence.
6. **The grader is exogenous.** Checks live in `hidden/`, are never placed in
   the candidate tree, and the agent's run directory is discarded after grading.
   The gold tree is the confidential acceptance material: the executor never
   sees it.
7. **Pass/fail is execution-based.** No LLM judge decides a pass.

## 5. Exclusions and stopping

- Excluded, and stated in the report: a run whose host crashed before the model
  was called, and a run whose arm command was edited after the freeze.
- Stop a block when every cell has `k` completed rows. Do not top up a losing
  arm, and do not extend a block because the result is inconvenient.
- Any arm whose `flag_verified` is `false` in `arms.json` must be validated
  (does the bare arm really have no tezgah hook active?) before its rows are
  scored. An unvalidated toggle invalidates the comparison, not just the arm.

## 6. What this benchmark still cannot show

- It measures a harness at one model family and one provider; provider prefix
  caching behaviour is a confound and is recorded per run, not controlled.
- It does not measure long-horizon or multi-day behaviour: every fixture is a
  single bounded task.
- It cannot attribute a difference to a specific contract sentence. Component
  ablations are a separate, narrower experiment.
