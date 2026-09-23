# Findings — what `zzet/gortex` and `NVlabs/SoL-Pi` carry for tezgah

Question: *do zzet/gortex and NVlabs/SoL-Pi carry features worth adopting into tezgah,
and what would each cost to adopt?*

This is a **survey line**: nothing was installed, no index was built, no model call was
made, no experiment ran, and every claim below cites a note under `literature/`. The two
repositories were read at first hand (their own files through the GitHub API and raw
endpoints) and the paper through orx; no command was run against either repository.

## What we know

- **The question's premise was wrong, and that is the first finding.** Gortex is not a
  newer version of tezgah's code-graph engine: tezgah's `codegraph` is
  `colbymchenry/codegraph` (MIT, Rust kernel, 71,724 stars), the engine
  `plans/done/010-codegraph-backend-migration.md` records as the measured replacement of
  `codebase-memory-mcp`, while `zzet/gortex` (Apache-2.0, Go, 1,626 stars, v0.64.4) is a
  rival product with its own verbs, env var and store (C01). The honest comparison is
  therefore two engines with one job, and that choice was already made by measurement.
- **Gortex puts provenance into the answer, not beside it.** Every edge carries an origin
  tier (`lsp_resolved`, `ast_resolved`, `text_matched`), and a caller answer carries a
  structured caveat plus `name_only_candidates` — the call sites that name the symbol and
  bind to nothing — so a thin caller list reads as "1 verified, 20 unverified" rather than
  as proof of safety (C02). This is exactly the hole tezgah patched out of band with
  `bin/tezgah-doctor --coverage`, whose rule exists because codegraph "counts what it
  parsed, never what it skipped".
- **Gortex separates the two lifetimes of one write.** A call overrun is *abandoned*
  rather than killed, so a mutation reports `disk_status` (committed / not_applied /
  failed / in_flight) separately from `graph_status`, leaves a receipt queryable for 30
  minutes through `mutation_status`, and `physical_evidence` re-reads the file for sha256
  digests (C03). tezgah's ledger (`hooks/tezgah_integrity.py`) reasons only about calls
  whose PostToolUse arrived; a write whose hook never lands is indistinguishable there
  from a write that never happened.
- **Gortex's savings ledger is deliberately conservative, and its headline is not.**
  A file's whole-file baseline is credited at most once per session per file, at most 8
  distinct cited files are credited by any one call, and a call that credits no new file
  books nothing — while the README's "up to 50x" is one order of magnitude above what
  `BENCHMARK.md` measures on its own repository (31,530 to 972 and 23,027 to 577 tokens on
  two queries) on "a single operator's machine" (C04). This is a ready-made protocol for
  the counterfactual, and a warning about the headline.
- **Its installer is a hazard before its graph is a benefit.** `gortex install` and
  `gortex init` write `.mcp.json`, `.claude/settings.*`, a marker-guarded
  `CLAUDE.md`/`AGENTS.md` community block, repo-local hooks and per-agent MCP configs
  across a 20-host adapter matrix — the same six host surfaces `bin/tezgah-setup` alone
  owns, and the same files tezgah's own rule forbids a repository `CLAUDE.md`/`AGENTS.md`
  from using to demote the graph (C05).
- **SoL-Pi ships mechanisms, not the loop it is named for.** 24 source files under
  `src/sol-pi/` hold four Pi-extension mechanisms (Action Fusion, ObservationPack,
  Evidence-Preserving Reducer, Online Context Compact) and no proposal generator, no
  acceptance gate, no environment builder and no evaluator; the loop behind them — 152
  proposals in six families, about 535 environments, more than 3,000 runs — is prose in
  the paper and the blog (C06). The four mechanisms are Pi-extension code against a
  public Pi API, and tezgah has no Pi host adapter.
- **The three borrowable ideas are procedure, not code.** A pre-rollout opportunity
  screen between a hypothesis and its protocol (the paper's Oracle Analysis), a token and
  cost counter-metric beside the capability metric, and a two-gate accept rule — capability
  within a predeclared tolerance *and* an improvement on a declared efficiency metric —
  with nondominated retention so the optimizing agent cannot move its own acceptance rule
  (C07).
- **`validateReceipt` is this repository's own review-quote rule in another language.** A
  delegated receipt is accepted only when its schema, its `source_sha256`, its status
  against the observed exit and every byte-exact quote check against the archived log, with
  a named refusal (`missing-failure-evidence`) so a failing log cannot arrive as a clean
  summary; both projects fail open when the mechanism cannot run (C08).
- **Against tezgah's research layer, SoL-Pi lacks what tezgah already enforces.** Its
  paper states the intent to fix capability metrics, tolerances and efficiency metrics
  before the search and to keep them out of the optimizing agent's control, but it ships no
  artifact, no check and no proof of ordering; tezgah's pre-registration is a fact decided
  on the commit graph (`_check_protocol_order`), its reviewer leaves a six-dimension
  `to_human/review.json` whose findings must quote their target, and its provenance ledger
  records `kind`, `provenance`, `falsification` and `scope` per claim (C09).
- **Nothing was reproduced, on either side.** Every performance, token and scale figure in
  both sources is its authors' claim on their own hardware and pricing (C10); SoL-Pi's
  numbers (44.7 to 49.0 percent less token traffic at 93.7 percent of Pi's score) and
  gortex's (a single operator's machine, by the benchmark page's own words) were read, not
  measured, and this line had no ability to measure them.

## Patterns

- **A repository name is not an engine identity** [C01] [literature/gortex-zzet-code-intelligence.md] —
  two projects with one job description ("graph-first code discovery for agents") can share
  no code, no protocol and no engine, so an adoption question asked about a repository has
  to name the surface that would change before it can be answered.
- **An honest answer carries its own floor** [C02] [C03] [literature/gortex-zzet-code-intelligence.md] —
  the two gortex mechanisms worth having are both about the *shape of an answer*: a caller
  list that says how much of itself it verified, and a mutation that says whether its bytes
  landed and whether the check that ran still knows. Neither needs gortex's engine, and
  both are absences in tezgah's surfaces rather than features of gortex's.
- **A savings number is only as good as the counterfactual it pre-commits to** [C04] [C07] [literature/2609.20519-sol-pi-auto-research-loops.md] —
  the one source that measures token traffic prices it against a baseline with declared
  caps, and the one source that publishes a headline saving admits its numbers come from a
  single machine; a claim about saved context is therefore a claim about a baseline, and
  the baseline has to be named before the measurement.
- **A repository can publish a research result without shipping the loop that produced it** [C06] [C09] [literature/sol-pi-nvlabs-harness-extensions.md] —
  SoL-Pi's four mechanisms are readable and its 152-proposal funnel is not, so a reader who
  wants the *method* is reading prose, and a reader who wants the *artifact* gets four
  Pi-only files; the discipline tezgah would borrow here is the one SoL-Pi does not ship.
- **Two installers writing one file is a category of defect, not an accident** [C05] [literature/gortex-zzet-code-intelligence.md] —
  gortex's installer targets the same six host surfaces tezgah's does, which puts the
  hazard before the benefit: the graph would have to be better than codegraph *and* the
  collision risk paid down before the engine swap could even be evaluated.
- **Verification discipline converges across projects** [C08] [literature/sol-pi-nvlabs-harness-extensions.md] —
  an independent implementation of "a claim is evidence only when every retained fragment
  checks against the archived original" was written in TypeScript for a different harness
  and lands on the same rule as `to_human/review.json`'s verbatim-quote requirement, which
  is evidence that the rule is load-bearing rather than stylistic.

## Lessons

- **The frame, not the code, was the deliverable.** The line was opened to ask what to
  adopt from two repositories; the largest finding is that one of them is not tezgah's
  engine at all (C01). A survey that had gone straight to "which features" would have
  produced a comparison of two engines' feature lists with the identity question unasked.
- **Read the repository, not its paper.** The repository named "Scaling Auto-Research
  Loops" contains no loop (C06); a line that had stopped at the abstract would have
  reported an installable method that does not exist, and every adoption estimate would
  have been priced against code that is not there.
- **A tool's own benchmark page is the honest half of its documentation.** Gortex's
  README states 50x and its `BENCHMARK.md` states two measured pairs on one machine and
  says so in its own text (C04); the two files disagree, and the disagreement is the
  finding.
- **The cheapest ideas were the ones about answer shape.** The two gortex mechanisms this
  line ranks highest need no engine, no dependency and no daemon — a paragraph of rule text
  and a status field — while the mechanism that would need a second install surface (the
  engine) is the one whose own installer is a hazard (C02, C03, C05).

## Open questions

- **Does tezgah's ledger want the third state?** C03 names the gap (a write whose hook
  never lands reads as absent) but this line ran nothing, so whether a pending-row
  implementation pays for itself against its blast radius is open, and it collides with
  open plan 004, which is editing the same file.
- **What is the operand for a pre-rollout screen in tezgah's own corpus?** SoL-Pi's screen
  is an oracle pass over existing trajectories (C07); tezgah's nearest instrument folds
  1,661 ledgers into 8 recurring failure shapes, and whether a screen built on that fold
  can name an operand a protocol's falsifier later reuses is untested.
- **Can a token and cost counter-metric be populated on all six hosts?** The survey's
  estimate (2-4 days) is dominated by per-host transcript parsing, and whether each of the
  six host session logs exposes the cache-read/cache-write split was not verified per host,
  so the field may be unmeasurable on some of them — in which case a total without the
  split answers nothing.
- **Does gortex bind extensionless, shebang-only files?** Its docs never state an
  extensionless intake rule and nothing was installed, so the one measurement tezgah
  already performed on codegraph (`benchmarks/codegraph-bench/probe.py`) has no counterpart
  for gortex — and it is the first thing a head-to-head would have to answer.
- **Would a Pi host adapter ever exist here?** SoL-Pi's four mechanisms need one
  (`docs/compatibility.md`: public Pi exports only), so every "port the mechanism" estimate
  is really an estimate for a host tezgah does not have.
