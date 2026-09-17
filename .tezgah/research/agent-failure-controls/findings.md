# Findings

## What we know

- The installed harness has four enforcement points and only two of them are
  mechanical: the PreToolUse gate (`hooks/tezgah_gate.py`, six deny branches over
  one call's arguments) and the Stop gate (`hooks/tezgah_integrity.stop_reason`,
  a keyword plus an evidence ledger). The prompt clause
  (`hooks/tezgah_policy.py`) has no runtime effect, and the workspace check
  (`bin/tezgah-research`) covers research lines only.
- Measured: the gate refuses 7/7 write-time controls and 0/12 trajectory-time
  cases (E1). The Stop rule refuses 8/10 explicit completion claims and 0/10
  implicit state descriptions (E2).
- The deny path and the ledger path are shared by every host that can block;
  opencode re-implements both in JavaScript and has no Stop hook
  (`hosts/opencode/plugins/tezgah.js`).
- The success-language gate exists and reads the ledger, not the tone: a failure
  after an earlier success still blocks (`tezgah_integrity.py:369-399`).
- Failure modes without any mechanical control today: repeated identical call,
  wrong-tool selection, fabricated tool name, empty/partial result read as
  success, hidden failure, wrong operation order, unconsented side effect
  (force-push, branch delete, destructive command, dependency install), partial
  failure with no rollback, concurrent write race, secret written to a log.
- The ten priority controls are mostly absent: the evidence ledger implements the
  success-language gate, and there are no operation ids, no cycle detector, no
  retry cap, no untrusted-content labelling and no per-trace false-completion
  metric.
- Literature found this session names the same classes as first-class problems,
  with mechanisms: evidence-carrying termination (2608.23623), unsupported final
  claims (2608.27768), compaction fabricating confirmed results (2607.13071),
  stage-wise tool failure diagnosis (2608.23635, 2608.22676), tool-output
  overtrust (2609.05587), harness lifecycle phases (2608.17597), long-horizon
  degradation as a per-step reliability law (2609.01660, 2606.29718),
  stateful/replay-resistant authorization for agent effects (2608.21159,
  2608.01710), retry amplification (2608.25403), policy-to-obligation
  verification harnesses (2608.23282, 2608.22868), and trajectory telemetry
  sufficiency (2608.07899).

## Patterns

- Every rule that exists today is a **single-call argument regex**. Every mode
  the taxonomy lists as unfixed is a **property of a sequence, a result, a
  resource or an authority** - none of which a single-call regex can see. That one
  line explains the whole coverage split, measured in E1.
- Every keyword rule has the same failure shape: it matches the vocabulary it was
  written with and misses a synonym of the same claim (`x3` "succeeded",
  `x10` "giderildi"), and its escape hatch is a single word anywhere in the reply
  (`NEGATED`).
- The harness fails open: `note()` swallows `OSError`, `last_verify()` swallows
  `OSError`, `first_nudge()` returns False on failure. A broken cache silently
  disables the Stop gate.

## Lessons

- A control's coverage is measurable without a model: call the rule with a
  labelled corpus and count. Both experiments cost seconds and turned two vague
  claims into numbers.
- A rule written from a regex must be probed with a corpus written from the
  failure mode, not from the regex, or the probe tests the regex against itself.
- Write the expectation per `(family, condition)`, not per case - E2's summary
  field got this wrong and the error is recorded rather than quietly fixed.

## Open questions

- Which enforcement point should carry the consent gate for irreversible
  actions, given that the gate sees one call and the contract already states the
  rule in prose?
- Can a cycle detector live in the PostToolUse ledger (which every blocking host
  already writes) instead of in the gate?
- Does an implicit state-description reply correlate with an unverified session,
  or do the two families differ in verification behaviour too?
- Which of the literature mechanisms can be implemented without a new host
  capability?
