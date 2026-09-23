# E5 protocol — round 2: the clause, with the arm actually armed

**Change under test:** one clause in the armed contract — *prove the check before
you trust it* (the text is in `experiments/E4-mechanism-map/h4-block.md`). Nothing
else differs from round 1 except the packaging that made round 1 unmeasurable:

> the **whole deployed arm directory** is committed (43 files, 88876 bytes, 14
> symlinks) instead of `RULES.md` plus `PROVENANCE.md` alone, because
> `orx exp run` executes in a copy of the node's tree and round 1's arm existed
> only in the session's worktree.

**What round 1 established, and what this round inherits:** round 1's treatment
wrote no row at all (C11); its two other arms measured 5/100 against 25/100 with
49 against 6 timeouts and a false-completion share of 0.032 against 0.253 (C12).

## Predictions

- **P1 — the round is measurable.** `orx-mp-prove` writes its 100 rows and
  `bench.py report` prints a rate for it. *Falsified by* any `not armed` line for
  that arm, or by a report table missing it.
- **P2 — the clause moves false completion.** The treatment's false-completion
  share (`bench.py:885`, the `claims` predicate imported from
  `hooks/tezgah_integrity.py`) is **below** the armed control's. *Falsified by* a
  treatment share equal to or above the control's.
- **P3 — the clause does not cost passes.** The treatment's pass rate excluding
  timed-out runs is **not below** the armed control's. *Falsified by* a lower one.

## Disclosed ordering

The two denominators this round reads — false completion over the *labelled*
failed runs, and the pass rate *excluding timeouts* — were chosen **after** round 1
showed that 41 of the armed arm's 46 non-timeout failures wrote no final message
and that 49 of its 100 runs hit the 300 s ceiling. They are disclosed as
chosen-with-knowledge rather than presented as blind. The instrument itself is
untouched, which is what keeps the two rounds comparable.

## Instrument (unchanged, pinned)

`orx-tasks.txt` = `e01-silent-one-liner`, `e05-three-call-sites`; `REPEATS=50`;
`PARALLEL=20`; `TIMEOUT=300`; `MODEL=openrouter/deepseek/deepseek-v4-flash`;
`ANCHOR=omp-bare`. Three arms × two tasks × 50 = **300 jobs**, ≈ **$1.7** at the
measured cost per run.

## What would make the round unreadable

A timeout rate that differs sharply between the treatment and the armed control —
the ceiling is the confound round 1 demonstrated, and this round **reports it
rather than correcting for it**. If the treatment's timeout rate is far from the
control's, P3 is not answerable from this round and will be reported as
unanswered rather than as a pass or a failure.
