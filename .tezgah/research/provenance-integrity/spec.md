# spec.md - the controls, one class at a time

Question this line asked: *which classes of fabricated or misrepresented data can a
hook-based harness refuse mechanically, which can only be named as limits, and what
is the cheapest control per class that a session cannot talk its way past?*

Answer, in one line: **the presentation half is decidable and now enforced; the
declaration half is not, and the layer spends its rules on making the declaration
visible rather than on pretending to check it.**

## The classes, and what a hook can actually do

| # | The class | Decidable by a hook? | Control | Status |
|---|---|---|---|---|
| 1a | a claim presents fixture output as a property of the running system, while the rows say `fixture` | **yes** - two recorded strings, no judgement | `scope` on rows and claims; a claim declaring `real` over rows that all record `fixture` is **refused** (`_check_claim_scope`, `hooks/tezgah_research.py:747`) | shipped |
| 1b | a session writes `scope: real` over a row it generated | **no** - the harness cannot see the input | nothing mechanical; the row's `source`/`command` make it auditable after the fact, and the contract names the class ("Say what a number was measured on") | limit, stated |
| 1c | a line's numbers are fixture-scoped and no reader is told | **yes** - the field is on the row | `status` prints the fixture-scoped claims of every line; a concluded line's report must contain the word `fixture` when it carries one | shipped |
| 2 | a number a claim asserts is in no artifact it cites | **yes** - string containment | warn naming the number and the artifact (`_check_claim_numbers`, `hooks/tezgah_research.py:797`) | shipped (warn) |
| 3 | a stand-in inside a demo, presented as a working integration | **only where the harness generated the stand-in** | two decidable halves shipped (3a: a fixture row must name what was generated; 3b: a session whose only passing check ran in a scratch or stand-in path is reminded that its evidence is about the code path); the third half (a planted `expected` value) stays designed | 3a, 3b shipped; the planted half not implemented |
| 4 | a rule that exists only as prompt prose | **no** | every prose rule that matters gets a mechanical half; this line's own contract sentence was added beside the field it names | limit, stated |

## Acceptance and falsifier, per control

**Control A - scope (shipped).** Acceptance: `check` refuses a claim declaring
`real` over all-fixture rows; the write path (`claim_problems`) refuses the same
claim, so the two judges agree; a claim over fixture rows that declares nothing
warns and `--strict` refuses; `status` names the fixture-scoped claims; a concluded
report that never says `fixture` warns. Pinned by six tests in
`tests/test_research.py` (`ResultRows`, `ClaimScopes`, `ReportLimits`).
Falsifier: a line where a fixture row presented as a property of the running system
passes `check --strict` without being named; or the field being recovered rather
than declared (which E1 shows is impossible, and which is why it is not attempted).

**Control B - containment (shipped, warn).** Acceptance: a claim asserting a number
its cited artifacts do not contain is warned with the number and the artifact; a
metric name (`p95`, `E1`) is not treated as a number. Falsifier: a warned number
that *is* present in a cited artifact (the shipped tokenizer and reader are what
E2 measured: 53 of 71 fully contained), or a claim asserting a fabricated number
passing silently *and* its rows being trustworthy (the rule is consistency, not
honesty - see the limit below).

**Control C - the stand-in, in the three shapes it can take (3a and 3b shipped,
the third designed).** Acceptance for 3a: a row whose `scope` is `fixture` and
which does not name what was generated is warned, and `--strict` refuses it;
`source --run --scope fixture` takes `--fixture` so the tool cannot file the row
its own checker warns about. Acceptance for 3b: a session whose only passing check
ran a scratch or stand-in path gets one reminder naming the command, and a session
with any passing check against a real path gets none (fourteen tests across
`tests/test_research.py`, `tests/test_context.py` and `tests/test_integrity.py`, and
the reminder is dropped by `verify-off`, the switch that already owns the integrity
rule). **The planted-expectation third** - the CapCode/hack-verifiable mechanic
where the harness writes the value its fixture is supposed to produce - is still
not implemented, and its falsifier still holds: every fixture in this repository is
hand-written, so there is no value the harness wrote in advance for a claim to
contradict. What 3a changes is that the ground is now prepared: a fixture row must
already name what it generated, so a generated fixture can carry the `expected`
value beside it without a new field.

**Falsifier for the whole control**: a line where a report presents a stand-in's
output as the running system's and passes `check --strict`; or a fixture row
describing an input it did not build. The first is now refused by class 1a's rule
when the rows declare their scope, and the second is not decidable - which is the
line between the two halves.

## What stays unenforceable, and what the layer does instead

- **A false declaration** (1b). The field records what the producer says it did.
  What the layer can do is make the lie expensive: the row carries `source` and
  usually `command`, the ledger carries the tool calls, and `status` and the report
  rule force the claim to be labelled - so a reader who cares can check the row
  against its command. That is a smaller claim than "the layer detects it", which
  is why the docs and the sector here say *declared*, never *verified*. The closure
  pass moved 510 of 813 rows from undeclared to declared - which is 510 statements
  the layer now carries and none of them it can check.
- **A declaration made by a reader, not the producer.** Most of those 510 rows were
  declared by a session that did not run them, reading each experiment's protocol,
  probe and `command` field, with a basis line left in its `analysis.md`. That is
  better than an undeclared row and worse than the producer's own statement, and
  the difference is not recoverable from the artifact.
- **A stand-in inside a demo** (3), outside the layer's own generators. The gate
  sees tool calls and file writes, not imports; a stand-in registry would have to
  be maintained by the repository, and inventing one here would be the scaffolding
  this layer refuses elsewhere. The fallback is the contract sentence, 3a's
  description field and the review dimension that asks it.
- **Prose numbers and arithmetic** (`about 85%`, `a quarter`). Not decidable
  without forbidding arithmetic in a claim; the containment warn's blind spot.
- **The containment match is a substring.** A claim's `10` is contained by an
  artifact holding `10000`, and a claim's `1,5` by an artifact holding `1.5`. So a
  *pass* is weak evidence and a *warning* is the strong signal - the opposite of a
  gate's reading, and the reason the rule stays in the warn class even at 80 of 82.
- **A moving denominator.** The containment share is taken over every numeric claim
  in the tree, so it changes whenever any line records a claim. 813 and 822 rows,
  and 71 and 82 claims, are the same tree at different moments; the share is
  comparable only with the moment it names.
- **A peer noticing.** The swarm study's whistleblowers were agents whose context
  made the exploit visible; a session here is one agent with one user, so nothing
  can rest on a peer (C06's note).

## The warnings that remain, and why each is not a gap

After the closure pass the checker reports 0 errors and these warnings: seven
protocols that state no prediction or no falsifier (committed before the rule
existed, and editing one after its results is what the order rule refuses), five
supersede relations (the layer's deliberate signal that an older row is not
current), two containment warnings on superseded rows (`harness-hardening` C17,
`typesafe-cost` C5 - the figures had no artifact behind them and the record of that
stays visible), one source that exists in a single index, and the git-tracking
warns that the commit clears.

## The evidence behind each choice

- E1 (`experiments/E1-scope-audit/`): the field cannot be inferred - 438 of 520
  rows of this repository's own lines fell to `unknown` under a path-text rule, and
  the one flag the rule produced came from a directory name. Hence a declared field
  rather than a check.
- E2 (`experiments/E2-number-containment/`): the containment rule as shipped is
  inside tolerance for 53 of 71 claims, so a refusal would refuse a quarter of the
  claims that are not wrong. Hence a warn.
- C04-C06 (`literature/`): a cap makes an over-claim decidable only because the
  harness wrote the expected value first; a planted vulnerability is what makes
  hacking verifiable without a judge; a prompt-only integrity rule does not bind,
  which is the argument for a field beside the sentence.
- C11 (`literature/2609.15319-receipt-based-agent-audit.md`): statement-level
  provenance is what a receipt-based audit of frontier agentic QA recommends after
  finding fabricated structural claims mixed with accurate numeric tables, so the
  field on the row and on the claim is the published shape and not this line's
  invention.
