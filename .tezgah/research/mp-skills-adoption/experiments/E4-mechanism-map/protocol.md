# E4 protocol — which mechanism is actually absent from the always-on text?

**Change under test:** none to the harness. Three instruments read `main` at the
line's own commit: the mechanical marker probe (`measure.py`), one batched judge
call over the same text (`measure.py --judge`), and the per-description
non-trigger probe over the 14 shipped skills.

The point of the round is to define the treatment clause for the H4 arm-bench
block, or to find that every candidate mechanism is already carried and no arm
is worth spending on.

**Ordering disclosed.** The mechanical counts were read once during
reconnaissance — first on the working tree, which was on another branch, then
confirmed on `main` — so they are **not** blind. They are reported as descriptive
rows and carry no prediction. One question in this round is genuinely blind: the
judge's, which had not been asked when this file was written.

## Prediction (the blind one)

Asked whether the always-on text instructs the agent to **deliberately provoke a
failing check, to prove the check discriminates before trusting it** — the rule
the pack's `setup-ts-deep-modules` step 6 states as "a config that doesn't fail
on a violation is worthless" — the judge returns **P(yes) < 0.5**, i.e. the rule
is absent from both CORE and CONTRACT.

**Two controls guard the instrument.** The same call asks whether the text
carries prohibitions and whether it carries verification language; both are
expected at **P(yes) ≥ 0.5**. A judge that answers "absent" to verification is
broken, and the treatment number would then say nothing.

## What would falsify it

- **P(yes) ≥ 0.5** on the provoke question: the rule is already there, the
  candidate clause is a no-op, and the H4 arm must be built from a different
  mechanism or dropped.
- **P(yes) < 0.5 on either control**: the instrument is broken and the main
  answer is unreadable.

## Instruments, and what each cannot see

- The **marker probe** is a declared regex set (`fail once`, `goes red`,
  `red-capable`, `see it fail`, `must fail`, `failure first`, `break it on
  purpose`). Zero hits is *weak* evidence of absence — it says the rule is not
  phrased that way, not that it is not there — which is exactly why the judge
  question exists beside it.
- The **judge** is the repository's own typed seam (`hooks/tezgah_judge.ask`,
  the `noul` question type, one batched request). It reads one state — CORE
  concatenated with CONTRACT, 49344 bytes — and returns a probability per
  question. Its answer is a model's reading, not a proof; the probability and the
  model that produced it are recorded with it.
- The **description probe** counts shipped skills whose `description` carries an
  explicit non-trigger ("don't invoke", "not for", "rather than"). It answers a
  count, not whether the phrasing helps.
