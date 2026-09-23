# repo-adoption-gortex-solpi — what `zzet/gortex` and `NVlabs/SoL-Pi` carry, and what they do not

Line: `.tezgah/research/repo-adoption-gortex-solpi/`. Question: *do zzet/gortex and
NVlabs/SoL-Pi carry features worth adopting into tezgah, and what would each cost to
adopt?*

**This is a survey, not an adoption.** Nothing was installed, no index was built, no model
call was made, and no command was run against either repository. Every statement below
rests on the two repositories' own files (read at first hand through the GitHub API and raw
endpoints) and on one paper fetched through orx; the ten claims and their falsification
criteria are in `claims.jsonl`, and each cites a note under `literature/`.

## What was asked, and what the evidence did to it

The question assumed both repositories were adoption candidates. They are not the same
kind of thing:

- **`zzet/gortex` is not tezgah's engine.** tezgah's `codegraph` is
  `colbymchenry/codegraph` (MIT, Rust kernel, 71,724 stars), the engine
  `plans/done/010-codegraph-backend-migration.md` records as the measured replacement of
  `codebase-memory-mcp`, and the engine every tezgah surface is written against — the rule
  text in `hooks/tezgah_policy.py`, the briefs `hooks/tezgah_agents.py` generates, the argv
  and env `bin/tezgah-setup` writes into six host MCP rows, the `init`/`sync` worker in
  `hooks/tezgah_index.py`. Gortex (Apache-2.0, Go, 1,626 stars, v0.64.4, pushed
  2026-09-21) is a rival product with its own verbs, its own env var and its own XDG store
  behind a daemon. So the honest comparison is two engines with one job description, and
  tezgah already chose between them by measurement.
- **`NVlabs/SoL-Pi` does not ship the loop it is named for.** 24 source files under
  `src/sol-pi/` hold four Pi-extension mechanisms and nothing else; the loop (152
  proposals, about 535 environments, more than 3,000 runs) is prose in the paper. And the
  four mechanisms import only public Pi exports, against a host for which tezgah has no
  adapter.

What remains worth taking is therefore six *ideas*, none of which needs either repository
installed.

## Verdict: the six borrowable ideas

| # | Idea (source) | Verdict | Cost, one line | The check that would prove it |
|---|---|---|---|---|
| 1 | Edge-provenance tiers with an in-band caveat that an empty or short caller list is not proof of safety (gortex) | **borrow-the-idea** | a paragraph in the graph rule plus the explorer/reviewer briefs — order 20-40 lines and the regenerated briefs, no mechanism | `tests/test_agents.py` passes with the floor sentence asserted for every host, **and** one real answer on a file `bin/tezgah-doctor --coverage` already reports uncovered (a shebang-only `bin/` script) states what the graph cannot see instead of implying completeness |
| 2 | The two-lifetime write model: `disk_status` against `graph_status`, plus a queryable receipt for an abandoned call (gortex) | **borrow-the-idea** | order 100-200 lines in `hooks/tezgah_integrity.py` plus cases in its test, and it edits the same file open plan 004 is working in | a test in which a mutating call's PostToolUse never arrives asserts the ledger and the Stop verdict report that call as unknown/abandoned rather than silently green, while the existing Stop cases stay green — the signal fires on the missing case and never on the ordinary one |
| 3 | A token-savings baseline that pre-commits to its own under-reporting caps (gortex) | **adopt** (as a protocol rule for this layer's own measurements; no code) | about an hour, and it closes the layer's largest hole: tezgah has zero token or cost accounting, only latency in milliseconds | the protocol names both caps and the tokenizer *before* it measures, and a reader who did not run it can re-derive the number from the protocol alone |
| 4 | A pre-rollout opportunity screen between a hypothesis and its protocol (SoL-Pi's Oracle Analysis) | **borrow-the-idea** | 1-2 days: one hook function and one check clause (order 100-150 lines with tests) over the failure-shape fold that already exists | the screen's projected operand and the subsequent protocol's falsifier are the *same* number — prove it on the two shapes the existing fold ranks highest by distinct sessions (`drift`, `task`) — and a shape whose screen projects about zero opportunity is flagged rather than run |
| 5 | A token and cost counter-metric beside the capability metric, split Input / Cache-R / Cache-W / Output (SoL-Pi) | **borrow-the-idea** | 2-4 days, dominated by per-host transcript parsing in one adapter shape per `hosts/` entry, not by the aggregation | one paired on/off comparison with `scope: real` rows shows the split populated on at least two hosts; on any host whose logs cannot supply it the field is reported unmeasurable rather than estimated |
| 6 | A two-gate accept rule: within a predeclared capability tolerance **and** an improvement on a declared efficiency metric (SoL-Pi) | **borrow-the-idea**, with its retention half **rejected** | 1-2 days for the check clause; the retention half (nondominated comparison across a population of lineages) is refused, because tezgah's binding constraint is that lines do not close, not that it lacks breadth | re-read open plan 004's already-landed prediction row under the rule and confirm it would have been refused as ill-formed (it declares no capability tolerance anywhere in its protocol), then confirm a corrected row is accepted — a rule that accepts the row which produced the undecided round has not been implemented |

**Rejected outright, with the reason on the record:**

- **Swapping in, or dual-running, either engine.** Engine identity is a measured choice
  already made (`plans/done/010-codegraph-backend-migration.md`), and gortex's installer
  writes `.mcp.json`, `.claude/*`, a `CLAUDE.md`/`AGENTS.md` community block and host hooks
  into the same six host surfaces `bin/tezgah-setup` alone owns — a hazard that lands
  before any benefit from the graph it would serve.
- **SoL-Pi's parallel-lineage population loop.** 152 proposals screened into ~150 lineages
  against ~535 purpose-built environments is a lab-scale funnel whose paper concedes the
  cost; tezgah's constraint runs the other way (lines that do not close), so borrowing
  that shape would multiply the layer's actual failure mode.
- **Porting the four shipped mechanisms.** They are Pi-extension code against a host
  tezgah does not have; if a Pi adapter ever exists, `evidence-preserving-reducer/receipt.ts`
  and `observation-pack` are the two files worth reading again — and the first of those
  restates a rule `to_human/review.json` already enforces here.

**Bottom line.** No: implementing either repository as a dependency is not sensible. Two
reasons, both measured rather than argued. First, engine identity is a decision this
repository already made by measurement — tezgah's graph engine is `colbymchenry/codegraph`,
recorded in plan 010, and every rule, brief, installer row and index worker is written
against that engine's verbs and flags; gortex is a different product with one job
description, and adopting it would be a re-run of plan 010 against a smaller project (1,626
stars against 71,724) whose installer collides with tezgah's own. Second, SoL-Pi ships
mechanisms written for a different harness: its four extensions import only public Pi
exports, tezgah has no Pi host adapter, and its research loop — the piece its name promises
— is not in the repository at all. What is left when both dependencies are refused is six
ideas, four of them about the shape of an answer tezgah already produces and two about
measurement the layer already lacks; the cheapest of them is a table of caps in a protocol,
and the most expensive is a counter-metric whose per-host cost is unverified.

## What this does not show

- **Nothing was installed, run or benchmarked.** No gortex binary was downloaded, no
  daemon was started, no index was built, no SoL-Pi extension was loaded, no Pi installation
  exists here, and no command was run against either repository. Every mechanism described
  above was read from source and documentation, never exercised, so this line says what the
  sources claim, not what the software does.
- **Every number is its author's.** Gortex's performance, token, language-count and star
  figures, and SoL-Pi's token-traffic, cost and scale figures, are the projects' own claims
  about themselves; gortex's benchmark page states in its own words that its numbers come
  from a single operator's machine, and the paper's prices are dated to its own August 2026
  list. None was reproduced, and none can be weighed without running the projects, which
  this line did not do.
- **The paper's loop was read as prose and could not be inspected.** Oracle Analysis, the
  acceptance gates, the environment builder and the lineage scheduler are not published in
  SoL-Pi's repository, so idea 4 and idea 6 are borrowed from a *description* of a method,
  with no code to check the description against and no independent replication of the
  results the method produced. EdgeBench, the held-out half of that protocol, was not
  obtained.
- **The two gortex mechanisms this line ranks highest are unverified in tezgah's own
  setting.** Borrowing the provenance floor and the two-lifetime write model would cost
  edits to the highest-blast-radius rules tezgah has (`hooks/tezgah_policy.py`,
  `hooks/tezgah_integrity.py`), and neither this line nor any measurement it holds can say
  whether such an edit pays for itself; open plan 004 is already editing the second file.
- **The five costs above are estimates, not measurements.** They are order-of-magnitude
  guesses from the shape of the change, marked as guesses where they were formed; the
  per-host half of idea 5 in particular was not verified against any host's session-log
  format, so its 2-4 days are the least reliable number in this report.
- **Whether gortex would even work here is unmeasured.** Its docs never state an
  extensionless-file intake rule, so the one question tezgah already answered for codegraph
  (whether a shebang-only `bin/*` script binds) has no answer for gortex, and its per-repo
  store path is named nowhere in its docs.
