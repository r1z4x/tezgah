# The research layer, audited: what its checks actually enforce, and the seven
# changes that would close the gap

Deliverable of this research line. One page per idea; the full record is
`../findings.md`, the measurements are `../experiments/*/`, the sources are
`../literature/`, and every claim cited here is in `../claims.jsonl` (C01-C25).

## Headline

| measurement | number | evidence |
|---|---|---|
| documented rules the checker refused a violating line for | **0 of 8** (control 2 of 2) | E1 |
| real claims whose proof names an artifact the line produced | **24 of 75** (32%) | E1 analysis |
| experiments whose protocol-before-results order could be verified | **0 of 7** - the prescribed path is gitignored | E2 |
| claims naming an orx run id; tezgah code reading orx | **0**; **0** | E3 |
| non-academic-channel tokens in the rule and the skill | **0**; practice sources already in use: 5 of 14 notes | E4 |
| sources compared against each other anywhere | **0 artifacts**; 2 of 19 synthesis bullets name any source | E4 |
| documented behaviours no test pins | **25** | E6 |

## Findings, most severe first

**F1 - `critical` - the checker's reach is structural, so the contract's
discipline is unenforced.** `skills/research/SKILL.md`: "a claim's `proof`
resolving to an experiment directory that actually has results ... a falsification
criterion and evidence on every claim". Measured: eight lines each violating one
stated rule exited 0 (E1). The checker never opens `results.jsonl`, never reads
`state.json.evaluation`, `protocol.md`'s content, `analysis.md`, `sessions` or
`literature/`, and resolves a proof as `os.path.exists`
(`hooks/tezgah_research.py:195-203`). Fix: I2, I3, I4.

**F2 - `critical` - the one rule the checker does implement is unreachable where
the contract puts it.** `SKILL.md`: "**Commit it before the run.** That commit is
the temporal proof that the prediction came first". `.gitignore:18` ignored
`/.tezgah/`, 0 files under it were tracked, and all 7 experiments with results in
all 5 lines report the order as unverifiable while `check` exits 0 (E2). The
guarantee has never fired. Fix: I1. **Closed**, in two commits rather than one:
`74370f8` put this line's nine protocols into history and `e632642` added their
results, after which all nine "the order cannot be checked" warnings disappeared -
the rule decided the order on the commit graph for the first time in this
repository (C37). The re-include is written level by level because git never
descends into an excluded directory, and the results of the pre-existing lines are
deliberately left untracked: infra-candidates' E1 protocol states in its own text
that it was written after its run, and committing those results would have git
assert an order the file itself denies (C38).

**F3 - `major` - evidence binding is a path that exists; 68% of existing claims
are not bound to anything the line produced.** 36 of 75 claims name only
repository files, 15 name no path-like token at all (E1 analysis, C04). A prose
proof and a fabricated one are accepted identically. Fix: I3.

**F4 - `major` - execution and evidence are two stores with no join.** 0 of 75
claims name a run; no tezgah code runs orx and reads it (E3). A number transcribed
from a run log into `results.jsonl` carries no receipt. The registered project for
this repository is also broken: its run command names `benchmarks/arm-bench/orx-run.sh`,
which the tree no longer holds (E3 cell B). Fix: I4, I7.

**F5 - `major` - the non-academic channel is neither named nor graded, and
synthesis has no artifact.** 0 tokens in the rule and the skill, while
`product-analysis` already holds Google Research, Microsoft, DORA, NN/g and
Playwright docs; no line holds anything that compares two sources; 17 of 19
synthesis bullets cite nothing (E4). The standard for the missing half is written
down: source-quality assessment and a distinct search process (Garousi,
`literature/1707.02553`), inclusion criteria plus exclusion reasoning plus quoted
evidence per decision (SciLitBench, 17.0% / 28.8% / 0.551->0.633), and named grey
sources with archived queries (GLiSE). Fix: I5, I6.

**F6 - `minor` - the surface that reports the layer is measuring a proxy.** The
`research` mark lights when a shell command ran `orx`; `bin/tezgah-research`
cannot light it (E5). Two docs contradict the code: `bin/tezgah-setup:788` and
`docs/skills.md:33` say opencode has no prompt-time injection point, which holds
for a per-prompt skill list and not for rules
(`hosts/opencode/plugins/tezgah.js:2169`). And the layer has no reachable docs
page: `bin/tezgah-docs research` -> "nothing matches". Fix: I7.

**F7 - `minor` - 25 documented behaviours are unpinned** (E6), clustered as the
skill's method prose, the CLI's refusal edges, the degradation paths (no fcntl, no
git, `is_ancestor` None) and the status surface. Fix: I8.

## The seven changes

Each names its acceptance test, which is the point: the fix for F1-F5 is a field
plus a check, not more prose.

| # | change | why / source | acceptance test |
|---|---|---|---|
| I1 | `init` refuses to scaffold a line whose path is gitignored, printing the `!` negation to add; `check` separates "the line's own path is ignored" (`FAIL`) from "results not committed yet" (`warn`) | F2; ClaimReceipt's manifest-before-outcomes | E2 cell B turns into the FAIL branch; a tracked line still passes cell A |
| I2 | `state.json.evaluation` gains an `environment` block (model id, prompt/ref, harness config) and the checker requires non-empty `metric`, `baseline`, `locked_at` and a `locked_at` no later than the first results row | preregistration for AI-agent experiments (2606.11217) | E1 P1 and P7 refuse; a line with the fields filled passes |
| I3 | claims gain `kind` (`evidence`/`code`/`literature`/`derivation`) with a per-kind proof rule: `evidence` must point inside the line at a file with non-empty `results.jsonl`; a proof with no path token is refused | F3; sufficiency (2609.01992), the hash-is-not-truth point (2609.08481) | E1 P4, P5, P6 refuse; the 5 existing lines' 75 claims classify without ambiguity |
| I4 | `results.jsonl` rows require `source`; `check` parses the file; `tezgah-research source <slug> --run <id>` captures `orx logs` into `raw/` and writes the row | F4; ClaimReceipt's replay boundary | E1 P3 refuses; a run-derived row resolves back to its log |
| I5 | `literature/INDEX.jsonl` per source: `class` (formal/grey), `inclusion`, `exclusion_reason`, `quoted_span`, `verified` (which of the four databases / which hosts); `check` requires an index once the line is past bootstrap, every `literature` claim to resolve to an indexed note, and a quality note on every grey source | F5; MLR guidelines (1707.02553), SciLitBench, GLiSE | E1 P8 refuses; `product-analysis`'s five practice sources pass with a class and a quality note |
| I6 | `to_human/review.md` with the six dimensions scored 1-5, the mean, and each finding carrying a `quote` that `check` requires to occur verbatim in the file it names; `findings.md` Patterns bullets must name a source id | F5; the skill's own review rule, rigor-reviewer | a review with a missing dimension or a non-verbatim quote refuses; E4's C3/C4 counts become questions the checker can ask |
| I7 | classify `tezgah-research` as the research kind in the ledger; fix the two opencode statements; add `docs/research.md` to `docs/index.json`; name the broken orx run command at session start | F6 | `bin/tezgah-docs research` resolves; the mark lights from the CLI; `bin/tezgah-research check` on a broken project reports it |
| I8 | pin the 25 behaviours, in the order E6 lists them, starting with the skill's method prose and the CLI's refusal edges | F7 | the new tests fail when the branch is deleted |

## And the question about web search and cross-source work

**Today: the human does both, and nothing in the layer knows.** A web search is
neither named nor recorded as a channel - the only live-web mention in the whole
contract belongs to `consult` (`hooks/tezgah_policy.py:367-369`), and the citation
rule names four scholarly databases only. The details of related work are
recorded per source when someone does look (`product-analysis`'s five practice
notes do exactly this, with the verification trail in note 02), but nothing
requires it, nothing grades the source, and **no line compares sources against
each other**: 0 comparison artifacts, 2 of 19 synthesis bullets naming any source
(E4). I5 and I6 are the two changes that turn that from a habit into a step with
a record.

## Review of this line's claims

| dimension | score | anchor |
|---|---|---|
| Evidence relevance | 5 | every claim cites a run, a probe line or a fetched source |
| Falsifiability | 5 | each claim carries the observation that would refute it |
| Scope calibration | 4 | three claims (C06, C10, C16) are repository-specific and say so; the grey-source rate is 14 notes, a small denominator |
| Argument coherence | 4 | E1's instrument was corrected mid-flight (disclosed) and one probe list was frozen before its confirmatory run rather than before its exploratory pass |
| Exploration integrity | 5 | two prediction misses (E4 C2, C4) recorded as misses, and the accidental cleanup line kept in the record |
| Methodological rigour | 4 | 0/8 rests on 8 probes and a 2-of-2 control; the control is what makes it credible, but 8 cases is a small frozen set |

Mean **4.5** -> accept, with the caveats above rather than instead of them.

This table is the reading taken before the implementation pass. `review.json`, the
artifact the checker reads, was refreshed after it and scores argument coherence at
5, which puts its mean at **4.67** with the same `accept`; `methodological_rigour`
stays 4 in both readings - for the reason the table gives, and, in `review.json`,
because two defects escaped the suite that shipped beside them. The two are left as
they were written - one is the session's first reading, the other the refreshed one -
and the table above is not edited to match, because a review is a judgement and no
rule here writes one after the fact.

## What this audit does not show

- It does not measure whether the workspace makes a session's research *better*.
  That needs two comparable lines, and the benchmark project registered for that
  question cannot run as registered (E3).
- It measures documents and files, not sessions: how often a session skips
  `protocol.md` in practice is unmeasured (E2 open question).
- The 8-probe set is the whole population of probes; a rule not probed is not
  evidence of coverage.
- 22 of this line's claims rest on a fixture input - a temp git repository the
  probe built, or a hand-written word and identifier list - so they are evidence
  about the rule's code path and not about the running system.
- **Six of the fourteen protocols are briefs rather than predictions, and they
  cannot be turned into predictions now.** E5, E6, E9, E11, E12 and E14 each say
  in their own text that the file was written after the run it covers - E5, E6 and
  E11 as the verbatim brief a read-only agent received before it ran, E12 as a
  judgement pass delegated to the pages' owners, and E9 and E14 as measurements the
  session ran and wrote up once they were done - and `check` reports each as "states no
  prediction". What that costs a reader: for those six experiments the line does not
  hold a pre-registered prediction, so their falsifiability rests on the claim's own
  criterion rather than on a result that was written down in advance and could have
  contradicted the reading; and the gap cannot be closed, because rewriting a
  protocol after its results is exactly what the order rule refuses. `check
  --strict` names all six, and the line leaves them standing rather than editing
  committed evidence.
- **Whether dsh delivers the prompt-time context stays open, with the test named**
  (C48). The manifest's `UserPromptSubmit` and the bridge's own event list are pinned
  in this repository; the `additionalContext` forwarding happens in the third-party
  bridge, so a driven dsh session with a research-class prompt, or a stub of the
  bridge's forwarder, is what decides it - neither exists, so the claim is recorded
  untested instead of asserted either way.
- **One of the twelve literature rows rests on a single record.** The source behind
  `2609.automating-literature-screening-llms` has no second database entry - its
  arXiv route 404s and a title search returns only the same record - so its citation
  is checked once rather than twice, and the warn stands (C39).

## Update: the plan was implemented in this session

The user asked for the seven items to be completed with subagents. All eight
(I1-I8) landed; the spec they were built against is
`implementation-spec.md`, written before any writer started, and the acceptance
is a runner written from that spec rather than from the code.

| measurement | result | evidence |
|---|---|---|
| acceptance cells passing on the final revision | **29 of 29**, both gate cells included | E7 |
| the same eight frozen probe bodies, refused before vs after | **0 of 8 -> 6 of 8**, 8 of 8 predictions matched | E1, E8 |
| `check` over the six lines | exit 0, 0 FAIL | E7 gate cell |
| `check --strict` over the six lines | exit 1, 190 FAILs in the unverifiable classes | E7 gate cell |
| docs citations outside the symbol they name | **0 of 329 judged** (from 36), 748 not judgeable named as the residue | E9 |
| full test suite | `Ran 1137 tests in 229.341s` - **OK** (`1021` at the baseline, before the writers started) | the parent's own run |

**Two real defects were found by the measurement, not by review, and both were
closed:**

1. `claim` refused a claim the checker only warns about (a row-less evidence
   file) - the two readings of one rule disagreeing in the strict direction.
2. `kind: evidence` accepted a proof naming only a repository file the line never
   produced - E1's P6, half-closed by the first pass. Re-running E8 after the fix
   is what turned 5 of 8 into 6 of 8.

Both were invisible to the 167-test suite that shipped beside them. A new rule is
not verified by tests written from the same reading of the spec that produced it,
and that is the sharpest lesson this implementation produced.

**What is still not done, named rather than implied:** the protocol's *content* is
still unchecked - the checker reads a protocol for the words `predict` and
`falsify`, which is why the six brief protocols above warn and why a protocol
carrying a real falsifier can still be reported as carrying none; the rule about a
concluded report's limits is a warning rather than a refusal, so a report that
states nothing about its limits is reported, not stopped; a superseded claim is now
visible to `check` - C49 carries `supersedes: C27` and the relation is printed,
closing review finding F10 - but it is printed as a warning, so `--strict` does not
stop on it; and the repository's own `.gitignore` still keeps the lines local, so
`init --tracked` exists while this repository's lines remain unable to prove
protocol-before-results - the user's policy call, not the layer's.
