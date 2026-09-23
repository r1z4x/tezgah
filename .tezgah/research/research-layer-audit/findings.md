# Findings

Question: which rules the research layer documents does the shipped
implementation actually enforce, and what does the current research-workflow
literature say should be enforced instead?

## What we know

**The checker's reach is structural, and the contract's prose is five times
wider than it.** Eight frozen probes, each violating one rule that
`skills/research/SKILL.md` states as enforced, were run against
`bin/tezgah-research check`: **0 of 8 were refused**, with a 2-of-2 control
confirming the harness reads the verdict (E1). The rules that *are* enforced are
file presence, JSON parse, enum membership, findings-section headings, and the
protocol/results commit order. Everything needing the *contents* of an artifact -
the locked evaluation, the protocol's predictions, the results rows, an analysis
label, a claim's evidence relation, the session record, a citation - is unread.

**The evidence binding is existence, and in practice it is mostly absent.** A
claim's `proof` is prose; the checker resolves path-shaped tokens with
`os.path.exists` and accepts everything else (E1 P4-P6). Measured over the five
lines that already exist: of **75 claims, 24 (32%)** name an artifact the line
produced, **36 (48%)** name only repository files, and **15 (20%)** name no
path-like token at all.

**The flagship rule has never fired.** `protocol.md` committed before
`results.jsonl` is decided on the commit graph, so it is live only inside a
git-tracked path. This repository's `.gitignore:18` ignores `/.tezgah/`, no file
under it is tracked, and **all 7 experiments with results across all 5 lines**
report "the protocol order cannot be checked" while `check` exits 0 (E2).

**Execution and evidence are two stores with no join.** 0 of 75 claims cite an
orx run or experiment id, and 0 places in `hooks/`, `bin/` or `hosts/` run orx
and read its output (E3). The registered orx project for this repository fixes a
run command naming `benchmarks/arm-bench/orx-run.sh`, which the tree no longer
holds (E3 cell B).

**The non-academic channel is unnamed but already in use.** 0 matching tokens in
the research rule and in the skill; yet 5 of 14 existing notes are grey/practice
sources (Google Research, Microsoft, DORA, NN/g, Playwright docs), all five in
`product-analysis`, and three of five lines hold no literature at all (E4).

**Synthesis has no home and no links.** No line holds an artifact that compares
two or more sources, and 2 of 19 `findings.md` Patterns bullets name any source
at all - as bare short names, in a form neither a checker nor a reader can follow
(E4).

**The routing is complete; the mark measures a proxy.** All six hosts arm the
rule at prompt time and all six render the `research` measure, but the measure
lights only when a *shell command* ran orx - `bin/tezgah-research` cannot light it
(E5).

**The layer's discipline lives in prose, and nothing reads the prose.** 25
documented behaviours are unpinned by any test, including the whole method half of
the skill and the CLI's refusal edges (E6).

## What the implementation proved, and what it cost

The seven improvement items were implemented in this session (I1-I6 in
`hooks/tezgah_research.py` and `bin/tezgah-research`, I7 across the routing, the
two corrected statements and a new `docs/research.md`, I8 as 86 new tests in
`tests/test_research.py` plus 13 across three other suites). Measured after:

- **The acceptance runner written from the spec before the code existed passes 29
  of 29 cells**, including both gate cells: `check` exits 0 over the six lines and
  `check --strict` exits 1 (E7).
- **The same eight frozen probe bodies went from 0 of 8 refused to 6 of 8**, with
  8 of 8 predictions matched and every refusal naming its probe's rule (E8). The
  two that remain are named: `protocol.md` content has no rule by design, and P5
  is a warn-class rule the probe reads through the lenient side.
- **Two defects were found by the measurement, not by review**, and both were
  reported with a reproduction and closed:
  1. the write path refused a claim the checker only warns about (a row-less
     evidence file), which contradicts the pair's own contract;
  2. `kind: evidence` accepted a proof naming only a repository file the line
     never produced - E1's P6, half-closed by the first pass. Re-running E8 after
     the fix is what turned 5 of 8 into 6 of 8, and both runs are kept as raw.

The cost is worth recording too: the acceptance pass is what found both defects,
and both were invisible to the 167-test suite that shipped with them. A new rule
is not verified by the tests written from the same reading of the spec that
produced it.

## Patterns

- **A rule with no artifact is a rule with no check** ([C01], [C15]). Every unenforced rule in
  E1 is one whose content has no *field*: the locked evaluation is three keys
  nothing reads, the review is prose with no file, a citation is prose with no id.
  The checker enforces exactly the rules whose carrier is a file or an enum, which
  is why 8 of 8 slots in the probe set came back empty and why the fix for each is
  a field rather than a sentence.
- **A guarantee depends on a second system's configuration** ([C05], [C07],
  [C09]). The order rule needs git to track the line; the prescribed layout is
  gitignored. The same shape repeats on the execution/evidence join (needs run
  ids) and on the citation rule (needs a resolver). Each is stated as a
  discipline and delivered as a warning.
- **Warnings do not survive a green exit code** ([C06], [C31]). The layer reports seven
  unverifiable guarantees as `warn` beside `research: 5 line(s) ok`. Both a human
  and a hook read the exit status, so an unverifiable rule and a satisfied one are
  indistinguishable at the only interface that matters.
- **The producer is the assessor** ([C06], [C15]). `check` is run by the session that wrote the
  line, and the six-dimension review is prose the session writes about itself.
  The independent artifact - the commit graph, and behind it the git history -
  is the one the prescribed layout disables.
- **The instrument records what the layer would have done** ([C13]). The single mark that
  reports whether the layer was used fires on any shell command containing `orx`,
  not on the layer's own CLI: the surface measures the tool, not the discipline.

## Lessons

- Measure the checker, not the docstring. The eight probes took about three
  seconds and moved the audit from "the skill says X is enforced" to "the checker
  enforces none of it", which none of the reading had settled.
- A probe script is production code while it runs. The frozen probe carried a
  dead cleanup line that removed the per-user temp directory's contents; it was
  caught by running it before trusting it, disclosed in `protocol.md`, and amended
  pre-run. The control cell is what made the 0/8 credible; without it, a harness
  bug and a finding look identical.
- A prediction table that records misses is worth more than one that records hits.
  E4's C2 predicted 0 grey sources and found 5; that miss converted a
  capability-absence finding into a codification finding, which is the difference
  between "add a feature" and "write down what one line already does".
- Do not let the token set decide the finding. E4's C4 hit 0 because the lines cite
  sources as bare names in parentheses; the post-hoc pass is labelled
  EXPLORATORY in the results for exactly that reason.
- A write path and a checker are two readings of one rule, and they drift. Both
  defects this session found were the pair disagreeing about the same condition -
  once stricter than the checker, once laxer. Any rule added to one side needs a
  test that pins the *pair*, not the side.
- A probe that reads the lenient side measures the lenient side. E1's claim probes
  (P4-P6) read `claim`'s exit code; after the write path was made deliberately
  permissive, those probes stopped measuring the rule they name. The audit's own
  instrument inherited its blind spot from the code's split, and only re-reading
  the raw output caught it.
- A validated claim cannot be corrected in place. C27's number became stale when
  the second fix landed, and the tool that records claims has no update command, so
  the correction had to be a new claim (C34) that names the old one. That is the
  append-only design working as intended, and it is also a real gap: nothing in
  `check` reports that a claim has been superseded.

## Open questions

- Does a *tracked* line change session behaviour, or only the checker's verdict?
  E2 shows the rule fires; nobody has run two comparable lines, one tracked and
  one not, and compared what the sessions recorded.
- What is the cheapest way to join the stores? An orx run id as a first-class
  proof token is a small change to `_cited` plus a lookup; whether a session
  actually records it after writing a number into `results.jsonl` is unmeasured.
- Should the workspace ship a *screening* artifact (inclusion criteria, a
  per-source decision with a quoted span, a source class) or is a note-field
  convention enough to make the citation rule checkable?
- Which of the 25 unpinned behaviours are worth pinning first? E6 ranks by
  documented-refusal-without-test, but nothing measures which one a real session
  actually hits.
- Nothing here measures whether the layer's *output* is better than a session
  without the workspace - the same open question the harness's own benchmark
  exists to answer (E3 cell B: the project registered for that work cannot run).
- **Is the warning class the right default?** After this change `check` is green
  over the six lines while `check --strict` refuses 190 things in them. `init`
  now names a gitignored path and `--strict` is one flag away, but whether a
  session should run strict by default - and what that would cost a line mid-run -
  is a policy call nobody has measured.
- **Tracing and publishing.** `init --tracked` exists and this repository's
  `.gitignore:18` still ignores `/.tezgah/`, deliberately: the maintainer's own
  policy keeps the lines local (`CHANGELOG`: "local, gitignored"). That is exactly
  the layout E2 measured as making the flagship rule unverifiable, and it is the
  user's call, not the layer's.
- **A superseded claim is invisible.** C27's number went stale when the second fix
  landed; C34 records the correction, and nothing in `check` reports that a claim
  has been superseded by a later one. An append-only record needs a supersedes
  relation, or the newest claim about a number is a convention rather than a rule.
- **The two remaining `protocol.md` gaps stay open by design**: its *content* is
  unchecked (P2), and no rule requires a line's `to_human/report.md` to state what
  the evidence does not show.
