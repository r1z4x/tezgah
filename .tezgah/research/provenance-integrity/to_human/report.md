# What a hook can refuse, and what it can only name

**Answer first.** A hook can refuse a claim whose numbers were measured on a
generated input when the claim presents them as the running system's - that is two
recorded strings disagreeing, and `tezgah-research check` now refuses it. It cannot
verify the declaration itself: a session that writes `scope: real` over a row it
generated is invisible to the harness, and no rule here pretends otherwise. The
layer's answer to that half is visibility rather than enforcement: the field is
declared by the producer, `status` prints the fixture-scoped claims of every line,
and a concluded line's report has to say `fixture` when it carries one.

## What was built, and what it rests on

| Control | What it does | Evidence it rests on |
|---|---|---|
| `scope` on results rows (`real`/`fixture`/`derived`) | a missing one is reported once per file with the count; an off-vocabulary one is refused | E1: 438 of 520 rows of this repository's own lines fell to `unknown` under a path-text classifier, so the field is declared, never inferred |
| claim scope | a claim declaring `real` over rows that all record `fixture` is **refused**, and the write path refuses it too; a claim resting on fixture rows that declares nothing warns, and `--strict` refuses | E1, and the layer's own `source` precedent (warn for the pre-migration class, refuse under `--strict`) |
| containment | a number a claim asserts that its cited artifacts do not contain is warned with the number and the artifact | E2 and E3: the rule as it finally ships leaves 80 of 82 numeric claims contained (98 percent), and the two it warns about are rows a line superseded with figures no artifact held - it stays a warning because its match is a substring, so a pass is not proof |
| `status` and the report rule | every line's fixture-scoped claims are printed where a reader sees them without opening the protocol; a concluded report carrying one must say `fixture` | the class is invisible exactly when the reader opens the report alone |
| a fixture row names its stand-in | a row whose scope is `fixture` must say what was generated; missing warns, `--strict` refuses; `source --run --fixture` lets the filer state it | a label without the stand-in named is a row a reader still cannot weigh |
| the scratch-path reminder | a session whose only passing check ran a scratch or stand-in path is told, in one line, that its evidence is about the code path | the ordinary-work half of the same class, where no research line exists to carry a scope field |
| `source --run --scope` | the producer declares the scope at the point of filing, instead of it being reconstructed later | the operator is the only one who knows |

Six of these are pinned in `tests/test_research.py` (classes `ResultRows`,
`ClaimScopes`, `ReportLimits`); the checker's 195 research tests and the repository
suite pass with them.

## What the evidence does not show

- **It does not show the declaration is honest.** `scope` records what the producer
  says it did. What makes a lie expensive is that the row also carries `source`
  (and usually `command`), the ledger carries the tool calls, and the claim is
  forced to be labelled - a reader who cares can check the row against its command.
  That is a smaller claim than detection, and it is the claim this work makes.
- **A stand-in inside a demo, presented as a working integration, is not covered.**
  The gate sees tool calls and file writes, not imports. The decidable version
  needs a value the harness wrote before the run (the capped-evaluation mechanic in
  `literature/2606.07379-*.md` and the planted-vulnerability argument in
  `literature/2605.20744-*.md`), and this repository's fixtures are hand-written
  today - which is the falsifier `spec.md` states for that control. It is designed
  there and deliberately not sketched into the tree.
- **Prose numbers are unmeasured by the containment rule**: "about 85%" and "a
  quarter" are not tokens in any artifact, and the rule cannot see them without
  forbidding arithmetic inside a claim.
- **Whether the declared debt stays declared, and by whom, is unmeasured.** The
  pre-pass census counted 510 of 813 rows undeclared; the closure pass declared
  them and the census now reads 0 of 822, with 371 fixture rows naming what was
  generated. Most of those declarations were made by a session that did not run the
  rows - a reader's classification of another line's protocol, probe and `command`,
  with a basis line left in each `analysis.md`. Better than an undeclared row, worse
  than the producer's own statement, and the difference is not recoverable from the
  artifact.
- **The containment rule's match is a substring**, so a pass is weak evidence and a
  warning is the strong signal: a claim's `10` is contained by an artifact holding
  `10000`, and `1,5` by `1.5`. That is why it stays a warning at 80 of 82 rather
  than becoming a gate - and the share itself is taken over a denominator that
  grows whenever any line records a claim.
- **Four warning classes stay by design and are not gaps**, read from
  `tezgah-research check` over the whole tree rather than quoted from the session
  that wrote this report (the counts move whenever another line records a claim):
  protocols that state no prediction (written as briefs, and editing one after its
  results is what the order rule refuses), `supersedes` relations (the field this
  line asked for is why they are printed at all), containment warnings on rows a
  line superseded with figures that had no artifact behind them, and sources that
  exist in a single index.
- **Three questions this line leaves unmeasured** (`findings.md`, "Open
  questions"), named here so a reader meets them without opening the findings file.
  *Does the declaration stay honest in practice?* The field is a declaration, and the
  only pressure behind it is that `status` and the report rule force it into view;
  nothing here measures whether a session fills it truthfully, and the honest answer
  is that this is the control's whole ceiling. *Can control C - a planted
  expectation - be built without changing what is measured?* It needs the layer to
  generate a fixture whose expected value it knows, and this repository's fixtures
  are hand-written today, which is the falsifier `spec.md` states; the design is
  recorded there and deliberately not sketched into the tree. *Would a stand-in
  registry - a file naming the modules that are substitutes - be cheap enough to
  keep, or would it rot into a list nobody updates?* Unmeasured. None of the three
  was run, and each would need a session that builds or watches the mechanism, which
  is outside what this line did.
- **The evaluation field was written at conclusion, not at bootstrap.** What it
  records is the criterion the two protocols had already fixed before either run
  (their predictions and falsifiers, committed as 83fc406), and the commit is named
  in the field; the reader should read it as a pointer to a pre-registered
  criterion rather than as a timestamp taken at the time.

## The three numbers this line is willing to be judged on

- **438 of 520** rows could not be classified by their text - the reason the field
  exists (E1, `scope: real` over the real repository's artifacts).
- **510 of 813** rows declared no scope before the closure pass and **0 of 822**
  declare none after it, 371 fixture rows naming what was generated and 0 that do
  not (E3's census, `scope: real`). The denominator moved because every results row
  in the tree is counted, this line's included.
- **80 of 82** numeric claims are contained in the artifacts they cite under the
  rule as it finally ships (E3 and E2's `pass: final-rule`), the two exceptions
  being rows two lines superseded with figures no artifact held. The same rule read
  53 of 71 at its first pass; the difference is six refinements made against real
  artifacts and the receipt corrections those refinements forced - and that is also
  why 98 percent does not make it a gate.

Fixture-scoped claims in this line: none. Every row of its three experiments
declares `scope: real`, because all three read this repository's own artifacts; the
numbers above that describe *other* lines - `harness-hardening`'s fixture rows and
its C01/C02 - are the fixture-scoped ones, and every one of them now says so.
