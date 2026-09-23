# E2 analysis — could a number-in-the-proof rule be enforced?

## Revision, before this number was shipped (second pass, same day)

The first pass measured a rule the layer does not ship. Two differences, both now
recorded in `results.jsonl` under `pass: refined-tokenizer`:

- **The tokenizer.** The first pass counted any digit run, so the claim `the cache
  cuts p95` was warned about for not containing "95" in its proof. The shipped
  `NUMBER` requires the digits to stand alone (a digit glued to a letter is an
  identifier, not a measurement).
- **The text set.** The first pass read directory-shaped proofs by walking the
  directories a proof names (bounded, and it hung on its first run); the shipped
  rule reads only the files a proof names.

Measured over the *same* cited-file text, the two tokenizers are within a point of
each other (loose 58 of 78, 74 percent; shipped 53 of 71, 75 percent), so the
8-point gap against the first pass is the text set and not the tokenizer: 83
percent described a rule whose evidence included files the claim never cited.

**The shipped rule's number is 53 of 71 (75 percent)**, and that is the number the
rest of this analysis and the `spec.md` use.

## Against the predictions

| # | prediction | result | verdict |
|---|---|---|---|
| 1 | fewer than half of the numeric claims have every asserted number in their cited artifacts | **53 of 71 are fully contained (75%)** | **missed, in the control's favour** |
| 2 | the claims that pass quote a ledger fold or a test output verbatim | the 18 uncontained ones are mostly statements that compute a derived figure, or carry an aggregate of rows the claim does not cite | **holds** |
| 3 | therefore only a weaker shape is viable | at 75% a **hard** rule would refuse a quarter of claims that are mostly not wrong; a **warn** refuses nothing and still names the uncited number | **holds, with the number now known** |

## What the audit establishes
- **The rule is cheap to compute and lands inside tolerance**: read the claim's
  cited files, require each number token to appear verbatim. 18 claims fail.
- **At least one failure is a true positive of the class**: `harness-hardening`
  C01 asserts "every live-state block combined is 1069 B", and the file it cites
  (`experiments/E1-injection-budget/results.jsonl`) does not contain `1069` - the
  aggregate was computed in the analysis and travelled into the claim as if it were
  a reading. The rule names the number and the artifact, so the fix (cite the
  analysis, or record the sum) is one line.
- **It is a warn, not a gate.** The repository's checker already has this shape
  (`check` errors where it can decide, warns where it cannot, `--strict` turns the
  warns into refusals); the containment rule belongs in the warn class with the
  number it produced, so a session sees "3 of the numbers in this claim are not in
  its proof" rather than a silent pass.
- **Its blind spot is stated**: prose numbers ("twenty") and derived arithmetic
  are not tokens in any artifact, so containment can never be a hard rule without
  also forbidding arithmetic in a claim. A quarter of this repository's claims
  would have to be rewritten for it to become one, which is what makes it a warn.

## What it does not show
- Whether containment catches fabrication. A fabricated number that a session also
  writes into its own results file would pass - the rule checks that a claim is
  *consistent with its evidence*, never that the evidence is honest. That gap is
  the reason the scope field (E1) is the primary control and this is the secondary
  one.

## Reproducing this

`probe.py` beside these results reproduces the second pass (it calls the checker's
own tokenizer and artifact reader); the first pass is reproduced by
`../E1-scope-audit/probe.py`, whose rows carry the `e2_*` fields computed with the
loose tokenizer and the directory-walking reader. The rows' `command` field names
the throwaway path each run used, which is what ran and is left as recorded.

## Third pass, after six refinements made against real artifacts

The rule that finally ships leaves **80 of 82 numeric claims contained (98
percent)**, per line: harness-hardening 16/17, infra-candidates 20/20,
judge-positioning 1/1, product-analysis 2/2, provenance-integrity 4/4,
research-layer-audit 28/28, typesafe-cost 6/7, ustam-artifact-contract 3/3. The two
warned rows are `harness-hardening` C17 and `typesafe-cost` C5, both claims a line
superseded because their figure had no artifact behind it, and their warning is
kept on purpose. The pass is recorded as `pass: final-rule` in `results.jsonl` and
as E3's census.

Each of the six refinements was found by a real artifact and not by a thought
experiment: a probe that walked whole directories (pass 1), a claim whose "cache
cuts p95" was warned about for not containing "95", a date read as three numbers,
a thousands separator read as a difference, a bare `findings.md` the reader never
opened (a silent pass, the worse direction), and a number at byte 77120 that a
64 KB window could not see.

**The correction a third pass forced on this line's own probe**: its first rows for
this pass were written with a reading that omitted `_comparable` on the statement
side and reported 81 of 82; the shipped rule applies it to both sides and reports
80, because a claim's "2,019" is one number and not "2" and "019". The bad rows
were dropped and the probe aligned with the rule's own expression before anything
was committed - the same failure the first pass made (measuring a rule that was not
the one shipped), which is why the probe now calls the checker's helpers instead of
reproducing them.

**It stays a warning, and 98 percent does not change that.** Three reasons, in
order of weight: the corpus was cleaned by the same pass that measured it, so a
cleaner corpus is not a calibrated rule; the match is a substring, so a pass is not
proof (a claim's "10" is contained by an artifact's "10000"); and two of the 82 are
rows whose line did the right thing by superseding them, so a refusal would punish
the correction.
