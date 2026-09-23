# E6 protocol — round 3: the clause, on a provider that answers

**Change under test:** one clause in the armed contract — *prove the check before
you trust it* — on the same arms, the same tasks and the same packaging as round 2.

**The one thing that differs, and why it is disclosed.** Rounds 1 and 2 could not
answer the question: round 1 never armed the treatment (C11), round 2 armed it and
the provider refused every call with `errorStatus` 402, leaving 300 zero-usage
failures at $0.00 (C13). This round changes the **model route only**:

| | rounds 1-2 (pinned) | round 3 |
|---|---|---|
| `MODEL` in `orx_block.py` | `openrouter/deepseek/deepseek-v4-flash` | `deepseek/deepseek-flash` |

That route was verified to answer before this protocol was written: `omp -p
--model deepseek/deepseek-flash "reply with the single word: ok"` → `ok`, exit 0,
usage reported. **Round 3's absolute numbers are therefore not comparable to
rounds 1-2**, and nothing in this round is reported as a comparison against them.

What stays comparable is what the clause's question needs: the three arms run in
**one run, on one model, over the same tasks**, so the treatment-versus-control
contrast is a within-round measurement. The instrument is otherwise untouched —
`orx-tasks.txt`, `REPEATS=50`, `PARALLEL=20`, `TIMEOUT=300`, `ANCHOR=omp-bare` and
the arm definitions are all as pinned.

## Predictions

- **P1 — the round runs.** All three arms write 100 rows and every row carries
  non-zero usage. *Falsified by* a zero-usage row, a `not armed` line, or an arm
  missing from the report table.
- **P2 — the clause moves false completion.** The treatment's false-completion
  share (`bench.py:885`, the `claims` predicate imported from
  `hooks/tezgah_integrity.py`, over the failed runs that produced a final message)
  is **below** the armed control's. *Falsified by* a share equal to or above it.
- **P3 — the clause does not cost passes.** The treatment's pass rate excluding
  timed-out runs is **not below** the armed control's. *Falsified by* a lower one,
  *made unanswerable* by a timeout rate that differs sharply between the two arms —
  in which case it is reported as unanswered, not as a pass or a failure.

## Disclosed ordering

The false-completion denominator (labelled failed runs) and the timeout-excluding
pass rate were chosen after round 1's numbers, as E5's protocol states; they are
carried over unchanged so the two rounds read the same way.

## Cost

Round 1 spent $0.77 for two arms; a full three-arm round is ≈ $1.7 at the measured
cost per run, on whichever account funds the provider this round uses.

## Known hazard, carried from round 1

The armed arm's median run was 267.7 s against the 300 s ceiling, so the ceiling may
again truncate the pass-family comparison. This round reports the timeout counts
rather than correcting for them.
