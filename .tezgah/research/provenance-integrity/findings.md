# Findings

## What we know

- **The field cannot be recovered, so it has to be declared.** Classifying all 520
  result rows of this repository's eight research lines by the path-shaped text
  they carry left 438 `unknown`, and the single claim the classifier flagged as
  fixture-presented-as-real was flagged because its directory is named
  `E6-rule-reach-probe`. A rule that reads a row and guesses what its numbers were
  measured on would be a guess in a check's clothes (E1).
- **The class is present in this repository's own artifacts.** `harness-hardening`
  E1's rows came from `/tmp/hh-budget.py`, which builds a temp HOME and a generated
  repository; the line's report states 9150 B as what a session is injected. No
  field on the row, the claim or the report said `fixture` until this line made the
  declaration, and the checker now prints it in `status` (C01, C02).
- **The presentation half is decidable; the declaration half is not.** A claim
  declaring `real` over rows that all record `fixture` is two recorded strings that
  disagree, and the checker refuses it. A session writing `scope: real` over a row
  it generated is invisible to the harness, and no rule here pretends otherwise
  (spec.md).
- **A number-in-the-proof rule is worth shipping as a warning, not a gate.** The
  rule as it finally ships leaves 80 of 82 numeric claims contained (98 percent)
  after six refinements made against real artifacts, and the two it warns about are
  rows two lines superseded with figures no artifact held (E2's `pass: final-rule`,
  E3, C13). It stays a warning because its match is a substring - a pass is not
  proof - and because a refusal would punish the supersede that did the right thing.
- **The undeclared-scope debt is closed, and by a reader.** 510 of 813 rows declared
  no scope before this session's six-slice pass; 0 of 822 declare none after it, with
  371 fixture rows naming what was generated and 0 that do not (E3's census, C14).
  The declarations came from reading each experiment's protocol, probe and `command`
  field, with a basis line left in every `analysis.md` - better than an undeclared
  row, worse than the producer's own statement.
- **A prompt is not a control.** The 100-agent swarm study lists forbidden
  constructs in its system prompt and records that the rule was "not actively
  enforced beyond the automated autograder checks" (C05).

## Patterns

- [C01] A misrepresentation needs two artifacts to be decidable - what was recorded
  at the time and what is claimed afterwards.
- [C02] The layer's own precedents are the shape to copy: `source` warns for the
  pre-migration class and `--strict` refuses it, and `scope` is now its twin.
- [C05] Every prose rule that matters here got a field beside it, and the two that
  could not are named as limits rather than written as advice.

## Lessons

- A rule written from a probe is a rule that was never measured: this line's
  containment probe said 83 percent, then 75, then 81, and the shipped rule said
  80 - each gap a copy of the rule drifting from the rule, the last time in this
  session's own probe (E2 analysis, the third-pass correction). The fix is to call
  the checker's helpers, not to reproduce them.
- Six refinements to one rule came from real artifacts and not from review: a
  directory walk, a comma read as a decimal, a date read as three numbers, a
  thousands separator read as a difference, a bare filename never opened, a number
  past the window. Each was found by a different claim, which is the argument for
  running a rule over a real corpus before trusting its shape.
- A probe's numbers are about the code path, and E1 of `harness-hardening` reported
  them as a property of the session until this line's field said otherwise. The
  cheap fix is a two-word declaration; the expensive part is noticing.
- Measure the rule you ship, not a rule you wrote down: E2's first pass measured a
  probe that walked whole directories and counted `p95` as a number, and neither was
  the rule that reached the checker (E2 analysis, "Revision").
- A controller that reports its own line's debt is worth more than one that is
  clean: `status` read `harness-hardening: ok, 2 fixture-scoped claim(s): C01, C02`
  when the debt was open, and reads 8 for that line now - the fact a reader would
  otherwise have to reconstruct.
- A citation re-anchor pass needs the tool, not the eye: the script this session
  used to fix shifted `file:line` references reported success while five bare
  references still pointed at the wrong line, and only `bin/tezgah-docs --citations`
  caught them. Re-anchor, then verify with the tool that flagged them.

## Open questions

- Does the declaration stay honest in practice? The field is a declaration, and the
  only pressure behind it is that `status` and the report rule force it into view.
  Whether that is enough is not measurable from this session.
- Can control C (a planted expectation) be built without changing what is measured?
  The mechanism needs the layer to generate a fixture whose expected value it knows
  - the repository's fixtures are hand-written today, which is the falsifier spec.md
  states.
- Would a stand-in registry (a file naming the modules that are substitutes) be
  cheap enough to keep, or would it rot into a list nobody updates? Unmeasured.
