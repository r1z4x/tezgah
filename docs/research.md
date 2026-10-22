# Research: the line in the repository, the CLI that checks it, the mark it lights

The research layer is the repository's own record of an open-ended
investigation: one directory per line under `<repo>/.tezgah/research/<slug>/`,
the CLI that scaffolds and refuses it, and the conditional rule that routes a
research task to OpenResearch instead of ad-hoc scripting. Read this page before
you start a line, before you change what `check` refuses, and when a session
reported a result you have to re-verify. The workspace and the checks live in
`hooks/tezgah_research.py`; the session-facing rule is `RESEARCH`
(`hooks/tezgah_policy.py::RESEARCH`) and the tool is `bin/tezgah-research`.

The layer exists because a claim is only auditable if the repository holds the
prediction it was tested against. `protocol.md` is committed **before** the run
and `results.jsonl` after it, and `check` asks git whether that order holds - a
protocol written once the numbers are in is not a prediction
(`_check_protocol_order`, `hooks/tezgah_research.py::_check_protocol_order`). Three things the same
file answers that nothing read until now are read too: what the protocol
predicts and what would falsify it (`_check_protocol`,
`hooks/tezgah_research.py::_check_protocol`), what a concluded line's report does *not*
show (`_check_report`, `hooks/tezgah_research.py::_check_report`), and which claim a later
claim replaced (`_check_supersedes`, `hooks/tezgah_research.py::_check_supersedes`).
`predictions.jsonl` is the other half of the same idea and the one a refinement
loop needs: one row per proposed harness-text change, bound to the `commit` the
change landed in rather than to the session that proposed it, so the round after
it can falsify the prediction instead of remembering it.

## Where a line lives: open/, done/

A line is a directory under `.tezgah/research/`, and the layout is plans': a line
in flight sits in `open/<slug>/`, and a line that concluded or was closed as a
limit moves to `done/<slug>/` (`hooks/tezgah_research.py::move_line`). One
resolver answers where a line is (`hooks/tezgah_research.py::line_dir`), and
every reader uses it: `slugs`, `status`, the session note, the checker. A
workspace from before the split still holds flat `research/<slug>/` directories -
the resolver falls back to them, `status` says the workspace needs
`tezgah-research migrate-layout`, and that command moves each flat line to `open/`
or `done/` by its own state, idempotently.

## The ask contract

A line that states an ask (rules 3 onward) carries the user's words and a way to
judge the answer:

- `init <slug> --ask "<the user's words>"` - required; `--tier quick` refuses a
  line outright, because a question small enough to answer in the reply gets no
  line at all. `study` is the default, `program` the full machinery.
- `state.json` `ask` (verbatim), `tier`, and `success`: one row per part of the
  ask, `{id, criterion}`, written before any experiment.
- `tezgah-research verdict <slug> <id> met|not-met|unanswerable --evidence <ref>`
  records the judgement with the pointer it rests on.
- `tezgah-research conclude <slug>` refuses until every criterion carries a
  verdict, then moves the line to `done/`.
- `close --limit "<what is left>" --ack "<what the user said>"` is the way out
  when a criterion is `not-met`: `check` refuses a conclusion over an unjudged or
  unmet criterion without an acknowledgement, and `check <slug>` and `check
  --all-lines` keep refusing such a concluded line as unanswered
  (`hooks/tezgah_research.py::unanswered`).

The reason: 4 of 11 sampled lines in this workspace concluded with the ask
unanswered and 0 of 416 claims cited any part of it (measured 2026-10-01), because
nothing recorded the ask and `close --limit` accepted any string.

## Rule versions

`state.json` `rules` is the line's format version. `init` writes `RULES`, the
newest set (`hooks/tezgah_research.py::RULES`). Each set keeps its own gate. Rules 2
are the standards rules. Rules 3 add the ask contract. Rules 4 add the protocol
sections below. Rules 5 add the scope lock. Rules 6 add the selection warnings
("Held-out set, repeats and noise band" below). Rules 7 add the `exploratory`
method ("Rules 7: exploratory lines" below). A bump never weakens an older set.
Rules 8 (`EVIDENCE_RULES`) add captured evidence and a computed certainty per
claim ("Rules 8: captured evidence and computed certainty" below). `init` writes 8
now: `RULES` is `EVIDENCE_RULES` (`hooks/tezgah_research.py::EVIDENCE_RULES`).

A `rules` above `EVIDENCE_RULES` means a later tezgah wrote the line. `check` then reports
one error that names both numbers and reads nothing else. The writers refuse the
line too: `claim`, `predict`, `compare`, `source --run`, `verdict`, `conclude`,
`close` and `migrate` (`newer_rules`). Upgrade tezgah to work on such a line.

## Protocol sections (rules 4)

On an older line, a protocol passes on a prediction word and a falsifier word.
That let `prediction:` with nothing after it pass. Reading sections out of prose
then kept misreading new shapes, so a rules-4 line declares its answers as
`key: value` labels (`protocol_labels`). A label starts at column 0, and its key
matches in any case. Its value is the rest of the line plus the indented or `- `
lines under it. A blank line or the next column-0 line ends it. `check` reads no
heading and no prose. It refuses the protocol when:

- `prediction:`, `falsifier:`, `metric:` or `unit:` is missing or empty.
- the prediction and falsifier say the same thing, ignoring case, spacing,
  punctuation and emphasis.
- `headroom:` is missing. It says how much the change could move at best, before
  any arm runs. A survey with no arms writes `n/a` and a reason. Once results
  exist, `check` also refuses a headroom that projects none. `check` first drops
  `*`, `_`, `` ` `` and `~`. Such a value then holds no nonzero number. It is `none`,
  `no`, `zero`, `nil`, `0`, `negligible` or `nothing to gain`. Or it starts
  `none `, `none,`, `no headroom`, `0 `, `zero `, `no gain` or `no room`. A
  leading `0.0%`, `0 %`, `0 tokens` or `0 ms` reads as `0`. A digit inside a
  name such as `p95` is not a number. `0.5%`, `0 – 15%`, `no more than 12%` and
  `0% today, up to 40% could` are headroom.
- `unit:` counts tokens and `tokenizer:` or `bound:` (the under-reporting bound)
  is empty. `check` lower-cases the unit and reads punctuation and `_` as spaces.
  The head is the words before the first `per`. The unit counts tokens when a
  head word is `token`, `tokens`, `tok`, `toks` or `ktokens`. A time word as the
  last head word (`ms`, `s`, `sec`, `seconds`, `latency`, `time`) cancels it. So
  `prompt tokens per turn`, `input_tokens` and `tok/turn` count tokens.
  `token latency ms` and `tokenset` do not. The metric's wording never decides
  it.

An `evidence` claim gets the token rule only through the protocols it cites.
`check` refuses the claim when a cited protocol's `unit:` is tokens and it
leaves `tokenizer:` or `bound:` empty. The claim's own prose is never read for
it. The rules come from the gortex/SoL-Pi adoption's ideas 3 and 4 and from the
layer audit's P2 probe (`_check_protocol_sections`, `_token_claim_problem`).
Older lines keep the word rule.

## Scope lock (rules 5)

The owner reported on 2026-10-07 that research turned every question into
metrics. It also grew past the ask, stayed shallow, and drifted off topic. The
rule text pushed each of these. The injected rule sent every research task to
orx's experiment tree. The skill locked a metric at bootstrap. `check` refused a
line past `bootstrap` without one. An analysis owed three compared variants. The
ideation moves had no fence. Rules 5 lock a line to its question:

- `init --in "<covered>" --out "<left alone>"` (repeatable) write `state.json`
  `scope`. The in-scope items are `S1`, `S2`, ... in order. `--method
  qualitative|measured|exploratory` writes `method` (`exploratory` from rules 7,
  see "Rules 7: exploratory lines"). `scope_problems`
  (`hooks/tezgah_research.py::scope_problems`) names an empty `scope.in`, an
  empty `scope.out` and a missing method. `check` refuses them past `bootstrap`
  and warns at it.
- A claim's `trace` names the in-scope item it answers (`S<n>` or the item's
  text). `claim_problems` and `_check_claims` both call `trace_problem`
  (`hooks/tezgah_research.py::trace_problem`). The writer and the checker refuse
  the same off-topic claim.
- A `qualitative` line owes no metric. `_check_evaluation`
  (`hooks/tezgah_research.py::_check_evaluation`) skips it. `_check_scope`
  refuses one that records `results.jsonl`. A measured question says `measured`
  and locks its evaluation first.
- An `analysis` deliverable owes no variants (`deliverable_problems` takes the
  line's rules). A design, plan or code still does. Older lines keep three.

The session reads the same lock in the research rule
(`hooks/tezgah_policy.py::RESEARCH` and the paragraph `**Research: route it to
OpenResearch.**`). Restate the question verbatim. Name what is in and out of
scope. Drop a finding that answers nothing asked. Pick the method from the
question. Answer a plain factual question in the reply from primary sources, with
no line. Cite each finding's source with a confidence. The host-subagent fallback
gets the question, its scope and its method in its brief. The research skill's
"Scope and method" section is the long form.

## Variants of the deliverable

`state.json` `deliverable` names what the line delivers. Its `kind` is `design`,
`plan`, `code`, `analysis` or `finding`
(`hooks/tezgah_research.py::DELIVERABLE_KINDS`). A design or plan takes 3 compared
variants by default and code takes 2 (`hooks/tezgah_research.py::deliverable_problems`).
On a rules-5 line an analysis and a finding take none. `min_variants` changes the
count. A count below the default needs `single_variant_reason`, which says why
the line weighed no alternative. `check` compares any decision across at least 2
produced variants (`hooks/tezgah_research.py::_check_decisions`).

One comparison lives in `decisions/<id>/`, and one loader reads its files
(`hooks/tezgah_research.py::load_decision`):

| File | What it holds |
|---|---|
| `criteria.json` | `criteria`: a list of `{id, kind, direction}`, with `kind` `measured` or `judged` and `direction` `max`, `min` or `pass`. `baseline_variant`: the id of the status-quo variant in `variants.jsonl` |
| `variants.jsonl` | one `{id, status}` row per variant. A `produced` variant names its `artifact`: a file in the line or the repository, `git:<rev>` or `orx:<id>`. A `dropped` one gives `drop_reason` |
| `comparison.jsonl` | one cell per variant and criterion, written by `compare` |
| `decision.md` | the choice and why the others lost |

Write and commit `criteria.json` and `variants.jsonl` before the first cell. Then
record each cell with `tezgah-research compare <slug> <decision>`, one JSON object
on stdin (`hooks/tezgah_research.py::append_comparison`). A cell names a produced
`variant` and a defined `criterion`. It carries either a `value` with its `source`,
or `not_checked` with the reason. A cell source has to resolve in the line or the
repository. An optional `rater` names who judged it
(`hooks/tezgah_research.py::comparison_problems`). The writer and `check` apply
this same rule.

`check` reads the whole decision
(`hooks/tezgah_research.py::_check_decision`):

- `check` refuses two produced variants that are the same file.
- A matrix cell neither measured nor marked `not_checked` warns. It refuses once
  `decision.md` exists or the line concludes.
- A judged cell with fewer than two distinct raters warns.
- The criteria have to enter the history before the first cell, and
  `comparison.jsonl` only grows.
- `decision.md` names a produced variant on a `chosen: <id>` line.
- Each other produced variant shares a line of `decision.md` with a criterion id
  that ruled it out. Else: `rejects <id> on no criterion`.
- `decision.md` has a `flip:` line, the result that would reverse the choice.
- When every criterion is `max` or `min` and scored, no produced variant may
  dominate the chosen one. A dominating variant is at least as good on every
  criterion and better on one (`hooks/tezgah_research.py::dominated_by`).

## One line, one directory

| Path | Holds |
|---|---|
| `state.json` | the question, the phase (`bootstrap`/`inner`/`outer`/`concluded`), the direction, `method` and `scope` (rules 5, see "Scope lock"), the locked evaluation and its optional second gate (`capability_tolerance`, `counter_metric`) with its `noise_band`, the optional `held_out` set (rules 6), the `arena` of an exploratory line (`problem`, `budget`, and `evaluator`, `evaluator_sha256`, `metric` for a measurable one - rules 7, see "The arena lock"), the session events (`PHASES`, `hooks/tezgah_research.py::PHASES`), `rules` (the rule set `init` opened it under, `RULES`), `deliverable` (`kind`, `path`, `ask`, `min_variants`), `supersedes` for a new version of an older line, and `closed` once `close` records a deliberate limit. The phase is the author's declaration; `derived_phase` (`hooks/tezgah_research.py::derived_phase`) reads the *other* authority beside it from the line's own artifacts, and the checker names the two disagreeing |
| `log.md` | the decision log, newest last: one line per decision, experiment, dead end or pivot, with the evidence that drove it |
| `findings.md` | the four sections every line answers, named by `FINDINGS_SECTIONS` (`hooks/tezgah_research.py::FINDINGS_SECTIONS`) |
| `claims.jsonl` | one JSON object per row: `statement`, `falsification`, `proof`, `provenance`, `status`, `kind`, `trace` (the in-scope item, rules 5), `scope` (what the claim's numbers were measured on, which may not be wider than the rows it rests on), and `supersedes` when the row replaces an earlier claim |
| `predictions.jsonl` | one JSON object per row: `commit` (a 40-character sha the row is bound to), `claim` (an id the line holds, or empty when the prediction stands alone), `metric`, `value_before`, `value_after`, `falsifier`, `components` (the keys of the components the change touches, read from `hooks/tezgah_components.py`), and `granted_by` when a human granted what the frozen paths below forbid |
| `ideas.jsonl` | an exploratory line's ideas, one JSON object per row, appended by `idea` (rules 7, see "Three files") |
| `stages.jsonl` | an exploratory line's stage moves, one row per move, appended by `stage`; an idea's stage is its newest row |
| `tournament.jsonl` | an exploratory line's judged pairwise matches, appended by `match` |
| `experiments/<hypothesis>/protocol.md` | what the change is, what it predicts, what result would falsify it, why - committed before the run |
| `experiments/<hypothesis>/results.jsonl` | the rows the run produced, one JSON object per non-blank line, each carrying a non-empty `source` and, once declared, a `scope` of `real`, `fixture` or `derived`, and - when that scope is `fixture` - a `fixture` description of what was generated |
| `experiments/<hypothesis>/analysis.md` | what the rows mean, and which claim they move |
| `experiments/<hypothesis>/raw/<runId>.log` | the OpenResearch receipt `source` writes for one run |
| `literature/**` | one file per source, at any depth and of any extension |
| `literature/INDEX.jsonl` | the index that says which sources exist and which were used; `class` is `formal`, `grey` or `agent-report` |
| `decisions/<id>/` | one comparison of the deliverable's variants: `criteria.json`, `variants.jsonl`, `comparison.jsonl`, `decision.md` (see "Variants of the deliverable") |
| `to_human/report.md` | the reader's copy: what was established, what the evidence does not show, and the four validity threats |
| `to_human/review.json` | the six-dimension review by a `reviewer` other than the `producer`, owed once a report exists |

`init` writes the first four plus the three directories and never overwrites a
file that exists (`init`, `hooks/tezgah_research.py::init`); `predictions.jsonl` is not
one of them, because a file that exists without a row is a line that looks like
it predicted something - it appears with the first `predict` the line records,
and `check` reads an absent one as no rows rather than as a missing file. The
three campaign files work the same way. Each appears with its first `idea`,
`stage` or `match`. A slug
is lowercase letters, digits and dashes (`valid_slug`,
`hooks/tezgah_research.py::valid_slug`), because it is the directory name `check`, `status` and
`claim` look for.

## One open line at a time

A line is **open** until its work is either applied or deliberately not, and the
line is closed. Concretely, `open_lines` (`hooks/tezgah_research.py`) calls a line
open unless all of these hold: `phase` is `concluded`; no claim is still
`hypothesis` or `testing` *among the rows nothing supersedes*; every experiment
that has a `protocol.md` also has results and an analysis; `to_human/report.md`
and `to_human/review.json` exist; every review finding carries a `status`; and a
deliverable that takes compared variants has a decision holding them and its
`decision.md`. A line `close` concluded is not open. Those are exactly the reasons
`init` prints, one line per open line.

The supersede half of that is a rule about an append-only file rather than an
exception: a row another row supersedes keeps the status it was left in for ever -
nothing rewrites `claims.jsonl` - so reading its own status would leave the older
`hypothesis` live and the line open with no session able to close it. A row whose
`id` appears as another row's `supersedes` is therefore read through the row that
replaced it, only the newest row of a chain decides, and a replacement that is
itself `hypothesis` or `testing` keeps the line open under its own id.

The rule exists because it was broken the other way round: on 2026-09-22 this
repository held thirteen lines, eleven of them carrying unfinished work, while
later lines were opened on top of them - an unrun pre-registered experiment, a
missing report, a claim left at `hypothesis`. A line that is never closed is also
never decided, and a second line started over it hides the first.

So `tezgah-research init` refuses while anything is open, and the armed research
rule names the open lines with their reason counts on every research turn
(`open_note`, `hooks/tezgah_policy.py`). The way past is `--allow-open
"<reason>"`, which writes the reason into the new line's `log.md` - an explicit
decision on the record instead of a silent second line - and which is itself
refused while any open line has `check` errors (`broken_open_lines`): a hatch past
broken lines is how they stayed broken. What is left of a line that will not be
finished is recorded with `tezgah-research close <slug> --limit "<reason>"`
(`close_line`), which concludes it and writes the reasons it was still open into
`state.json` `closed` and `log.md` and seals it ("the order seal", below). Such
a limit is a normal outcome, not a failure to avoid. So are a hypothesis ended
`inconclusive` and a claim narrowed to what its evidence reaches. The skill and
the policy carry no "try harder" prompting: it measured null or negative (plan
127, 4.4). On a rules-8 line `check` caps a claim's certainty and warns on
overclaiming wording instead.
Its errors show in `check <slug>` and `check --all-lines`; the no-slug `check`
reads it by its seal hashes and counts it on one line (ADR 015). The
prompt-time note reads a line's `state.json`, its experiment directory and its
review, never `claims.jsonl`, so a line open *only* because of a live claim is
named by `init` and not by the note; that split is the note's cost budget and is
stated in the rule's own comment.

## The CLI

`bin/tezgah-research` is the only writer and the only reader of the workspace;
the no-slug check a session runs from the shell reads the same lines the session
note does (`check`, `hooks/tezgah_research.py::check`): each open line through
`check_line` (`hooks/tezgah_research.py::check_line`), each line under `done/`
through its seal.

| Command | What it does | Exit |
|---|---|---|
| `tezgah-research init <slug> [--question "..."] [--class R1..R12] [--allow-open "<reason>"] [--supersedes <slug>]` | scaffolds the line and makes sure `.tezgah/` is ignored by the project and has its own git repository (`tezgah_paths.ensure_workspace`). It refuses while another line is still open (see below), names each open line and its reasons one per line, and `--allow-open "<reason>"` is the way past unless an open line has `check` errors: the reason lands in the new line's `log.md` as its first entry, and an empty reason is misuse. A `--question` another line already asks is refused unless `--supersedes <that line>` says the new line is its next version (`serial_twins`). `--class` writes `state.question_class` and prints `obligations: <step>, ...` (`obligations`), the tier's `budget <slug>: sources a/b searches c/d runs e/f` (`budget`) and `overlap: <line>/<claim> <status> <similarity>` for each done claim close to the question (`overlaps`); `--class R0` exits 1 (`R0 gets no line`) before any other argument is read. Its next-step message names the commit loop: `tezgah-research commit` for the protocol, then again for the results in a later commit (`cmd_init`, `bin/tezgah-research`) | 0, 1 refused, 2 misuse |
| `tezgah-research commit <slug> "<message>"` | stages and commits only that line's path in `.tezgah`'s private repository - the commit the order rule reads (`cmd_commit`, `bin/tezgah-research`). With nothing left to commit it prints `nothing to commit: <paths> is already committed in <workspace>` and exits 0 | 0 (also with nothing to commit), 1 not a work tree or git failed, 2 misuse |
| `tezgah-research check [<slug>] [--json] [--strict] [--orx] [--online] [--all-lines] [-- <slug>]` | the discipline checks below. With no slug it checks the open lines in full and a line under `done/` by its order seal alone (`done_seal`, `hooks/tezgah_research.py::done_seal`), naming it only when the seal fails or its `state.json` or seal cannot be read, then prints `research: <n> done line(s): <s> checked by their seal, <u> unsealed (not checked); ...`; `--all-lines` checks every line in full, and `check <slug>` always checks that line in full (ADR 015). `--json` prints the report (no-slug default: the open lines and any done line whose seal read fails), `--strict` turns the unverifiable class into a refusal, `--orx` adds the registry check that asks `orx project view` for this repository (`check_orx`, `hooks/tezgah_research.py::check_orx`) and, on a rules-8 line, the run census; `--online` re-fetches a rules-8 line's citation receipts; a slug after `--` is never read as a flag, which is how the MCP tool `tezgah_research_check` passes its validated `slug`. A rules-8 line (`_check_rules8`) also prints report lines that are never counted - `certainty`, `stats`, `effect`, `instrument`, `ppi`, `stopping`, `online`, `budget` - and `--json` adds its per-claim `certainty` | 0 clean, 1 a line failed a rule or names no line |
| `tezgah-research status` | one line per line: an open line `ok` or a problem count, a line under `done/` read by its seal like the no-slug `check` - `done, seal ok`, `done, <n> seal problem(s)` or `done, unsealed (not checked)` (`summary`, `hooks/tezgah_research.py::summary`, plan 058 part 4) | 0 |
| `tezgah-research --all` | every checkout of this repository (the main checkout and each linked `git worktree`, `tezgah_paths.worktrees`), one header per checkout, then `  <slug>: <phase>` per line with the reasons it is still open; a checkout with none says `no research line`. Read-only: each checkout keeps its own `.tezgah`, locks and private repository, and nothing here writes to any of them (`across`, `hooks/tezgah_research.py::across`) | 0, 2 misuse |
| `tezgah-research claim <slug>` | reads one claim from stdin and either appends it under an exclusive lock or refuses it, printing one reason per problem | 0, 1 refused, 2 misuse |
| `tezgah-research predict <slug>` | reads one prediction row from stdin and either appends it under the same lock or refuses it with one reason per problem; a row whose `commit` git cannot place is appended with the warning printed, which is the fail-open `check` uses, and a row written now has to name at least one component the manifest defines (`append_prediction`, `hooks/tezgah_research.py::append_prediction`) | 0, 1 refused, 2 misuse |
| `tezgah-research components [--json]` | the per-component report: one bucket per component the manifest defines, in the manifest's own order, then any key a row names that the manifest does not, each holding the prediction rows that name it and each row's state, and last the rows that name no component; it prints the number of components and rows it read (`component_report`, `hooks/tezgah_research.py::component_report`) | 0, 2 misuse |
| `tezgah-research migrate <slug> [--dry-run]` | derives the fields a line written before these rules cannot carry, prints what it derived and what it could not, and is idempotent (`migrate`, `hooks/tezgah_research.py::migrate`) | 0, 2 misuse |
| `tezgah-research source <slug> <hypothesis> --run <orxRunId> [--command "..."] [--scope real\|fixture\|derived] [--fixture "<what was generated>"]` | keeps the receipt: runs `orx logs <runId>`, writes `raw/<runId>.log`, appends the results row `{"source": "orx:<runId>", ...}` and the scope and fixture description the filer states (`source_run`, `hooks/tezgah_research.py::source_run`). A `--scope fixture` filed without `--fixture` still writes the row and prints the field it still owes, so the tool is never the thing that makes its own checker warn silently; a given `--fixture` that is empty is misuse | 0, 1 nothing filed, 2 without orx |
| `tezgah-research compare <slug> <decision>` | reads one variants x criteria cell from stdin and appends it to `decisions/<decision>/comparison.jsonl` under the lock, or refuses it by the rule `check` applies (`append_comparison` and `comparison_problems`, `hooks/tezgah_research.py`); it notes when `criteria.json` is not committed yet | 0, 1 refused, 2 misuse |
| `tezgah-research close <slug> --limit "<reason>"` | concludes the line as a deliberate limit, writing the reasons it was still open into `state.json` `closed` and `log.md`, and seals it (`close_line`) | 0, 1 unreadable state, 2 misuse |
| `tezgah-research verdict <slug> <id> met\|not-met\|unanswerable --evidence "<ref>"` | records one success criterion's verdict and the evidence it rests on in the line's `state.json`, or refuses it with one `FAIL verdict:` line per problem (`verdict_problems`, `hooks/tezgah_research.py::verdict_problems`) | 0, 1 refused or unreadable state, 2 misuse |
| `tezgah-research conclude <slug>` | concludes a line once every success criterion carries a verdict, seals it and moves it to `done/` (`conclude_line`, `hooks/tezgah_research.py::conclude_line`) | 0, 1 refused, 2 misuse |
| `tezgah-research migrate-layout` | moves flat `research/<slug>` directories into `open/` or `done/` by each line's state, and is idempotent (`migrate_layout`, `hooks/tezgah_research.py::migrate_layout`) | 0, 2 misuse |
| `tezgah-research seal <slug> [--history-lost] --ack "<owner decision>"` | seals a line under `done/` that was concluded before seals existed: plainly, as `conclude` would, when every experiment's order still checks; with `--history-lost`, with that verdict for every experiment whose order the lost history left undecidable. Refuses a line with a real order violation, a plain seal on any order finding, and a `history-lost` seal with nothing lost (`retro_seal`, `hooks/tezgah_research.py::retro_seal`) | 0, 1 refused, 2 misuse |
| `tezgah-research import <checkout> [<slug>] [--allow-open "<reason>"]` | brings a line - or every line this checkout lacks - from another checkout's `.tezgah` repository with its history; an open line arrives beside open ones only with `--allow-open` (`import_line`, `hooks/tezgah_research.py::import_line`) | 0, 1 refused, 2 misuse |
| `tezgah-research next --topic <t> [--flow f] [--json]` | prints every step of a product flow with its status from the topic's files under `.tezgah/analysis/<topic>/`, then the first missing or due step's skill and command; `--flow` picks `metric-dashboard` (the default) or `feature`, and `--json` prints the same steps as data (`next_steps`, `hooks/tezgah_product.py::next_steps`) | 0, 2 unknown flow or no `--topic` |
| `tezgah-research init <slug> --ask "<the user's words>" --method exploratory --in "<covered>" --out "<left alone>" --arena "<problem>" --budget "<budget>" [--evaluator <path> --metric "<metric>"]` | opens a rules-7 exploratory line and writes the arena into `state.json` (`arena_record`, `hooks/tezgah_research.py::arena_record`). `--ask`, `--in` and `--out` are required as on any rules-5 line. Without `--arena` or `--budget` it is misuse; `--evaluator` and `--metric` go together; the evaluator has to be a file in the repository; the four flags on any other method are misuse. Its next step says to commit the arena before the first idea | 0, 1 refused over open lines, 2 misuse |
| `tezgah-research idea <slug>` | reads one idea row from stdin and appends it to `ideas.jsonl` under the lock, or refuses it with one reason per problem (`append_idea`, `hooks/tezgah_research.py::append_idea`) | 0 written, 1 refused, 2 misuse |
| `tezgah-research stage <slug> <idea> <stage> [--evidence "<ref or JSON>"] [--reason "<why>"]` | appends one stage move to `stages.jsonl` under the lock, or refuses it. `--reason` is the kill's reason, and a `known` prior art needs it for the kill appended with it (`append_stage`, `hooks/tezgah_research.py::append_stage`) | 0 written, 1 refused, 2 misuse |
| `tezgah-research match <slug>` | reads one judged match from stdin and appends it to `tournament.jsonl` under the lock, or refuses it (`append_match`, `hooks/tezgah_research.py::append_match`) | 0 written, 1 refused, 2 misuse |
| `tezgah-research board <slug> [--json]` | the campaign as its files show it: arena, rows, torn tails, each idea's stage, score and next action, the ideas tested and the next step; writes nothing (`board_text`, `hooks/tezgah_research.py::board_text`) | 0, 2 misuse |
| `tezgah-research dedup <slug> [--threshold <(0, 1]>] [--json]` | clusters the `proposed` ideas by statement and prints the `stage ... duplicate` command for each member; names the backend and the threshold's source; writes nothing (`dedup_text`, `hooks/tezgah_research.py::dedup_text`). A `--threshold` outside `(0, 1]` is misuse | 0, 2 misuse |
| `tezgah-research yield [--json] [--all-lines]` | per operator and per generator family, how many ideas reached each stage, the kill reasons, the board-score-to-pilot correlation and the next campaign's operator weights; writes nothing (`yield_text`, `hooks/tezgah_research.py::yield_text`) | 0, 2 misuse |

Exit code 2 is always misuse, so a caller can tell it from a line that fails the
checks (`misuse`, `bin/tezgah-research::misuse`). `check` asks nothing at all - no
network, no model - so its answer is reproducible on a machine with no
credential; only `--orx` asks the one question that leaves the machine.

## The next step of a product flow

`tezgah-research next --topic <t>` tells the session which step of a product flow
comes next. Its step table is `FLOWS` (`hooks/tezgah_product.py::FLOWS`).
Each step names its `id`, the `skill` that runs it, what it `leaves` behind and
the `command` that writes it. The `product-flow` skill lists the same nine steps
in prose and names `next` as their status source.

Two flows exist. `metric-dashboard` is the default and has nine steps. `feature`
drops the metrics and instrumentation steps, unless the topic's `flow.md` already
holds `## metrics`. `--flow <f>` picks one.

`next_steps` (`hooks/tezgah_product.py::next_steps`) computes each status from the
topic's folder, `.tezgah/analysis/<topic>/`, and reads nothing else. Nothing
stores a status. A step is `done`, `missing` or `due`:

| Step | Done when |
|---|---|
| `forward-spec` | `.tezgah/analysis/<topic>/spec.md` exists |
| `re-measure` | `flow.md` holds `## re-measure`. Before that it reads `due` once the `observe after: YYYY-MM-DD` date under `## decision` has passed |
| every other step | `flow.md` holds its `## <step>` heading |

The `design` and `build` commands start with `tezgah-design check`. The design
check and the Stop UI rule judge those two steps. The flow only asks for their
note. A topic that is not kebab-case (at most 64 characters) reads no file. A
topic with no folder yet lists every step as `missing`.

The text output prints one line per step, then one `next:` line:

```
<n>. <id> [<status>] <skill> - <detail>
next: <skill> - <command>
```

The `next:` line names the first `missing` or `due` step's skill and command.
With no such step it reads `next: nothing left`. `--json` prints the same steps
as a list of objects with `id`, `skill`, `status`, `detail` and `command`.

`next` exits 0 when it prints the steps. It exits 2 for an unknown flow or a
missing `--topic`.

## The pair the order rule compares

The order rule is decided on the commit graph, so it needs both files committable
and it needs them as two commits. Whether they are is a question about the two
files, not about the line's directory: an ignore rule can cover the directory
while the pair is tracked, and a directory that is tracked says nothing about the
results inside it. `_check_tracking`
(`hooks/tezgah_research.py::_check_tracking`) therefore probes each experiment's
`protocol.md` and `results.jsonl` with `_ignored`
(`hooks/tezgah_research.py::_ignored`) - the plain question *can `git add` stage
this?*, which git's `check-ignore` answers as no for a path the index already
holds - and reports the pair that is ignored.

The loop that keeps the order decidable, stated once here because the failure is
silent: **commit the protocol** (that commit is the prediction), **run, then
commit the results in a later commit**. Both commits land in `.tezgah`'s private
repository - the project ignores `.tezgah/` and never stages it:

```sh
tezgah-research commit <slug> "protocol <h>"   # = git -C .tezgah add ... && git -C .tezgah commit
# run it
tezgah-research commit <slug> "results <h>"
```

`_ignored` asks the repository that commits the file - the private one when it
exists, else the project's - and the history helpers (`_histories`,
`_oldest_adds`, `_top_for`, `is_ancestor`) read both histories. An **order** - the
first add of a protocol, results, criteria or comparison, the first lock - is read
along each history's HEAD and never `--all`: a side branch, an abandoned draft, a
stash or a backdated orphan is not the record, and reading every ref took the
date-oldest add among them. A **rewrite** - a committed row changed or removed
(`file_versions`), a protocol edited after the run - is read across every ref of
the private repository: a row amended away while a tag keeps the old commit is
a rewrite HEAD alone no longer shows, and a side ref can only add such evidence,
so it refuses and never passes. A line the project committed before the move
still proves its order there. A prediction's `commit` names a product commit and
is placed only in the project's history.

### What the order rule accepts

`_check_protocol_order` (`hooks/tezgah_research.py::_check_protocol_order`) accepts one proof.

**(A) the add-before-add rule.** The commit that added `protocol.md` must be a
*strict* ancestor, in HEAD's lineage, of the commit that added `results.jsonl` -
one commit adding both proves nothing, because the plan and the numbers would
share an instant. The commit graph decides this, not the dates: a rebase rewrites
dates but not ancestry. Every history that holds the results' add has to agree
(`_answers`): a history that committed the results with no protocol before them
refuses, whatever the other one shows. One exception orders across the two: the
private repository's import that added both at once, after the project
committed the protocol and never the results, is the plan first - the move is
the premise, and a project protocol committed after an import that already held
the results is its ceiling. The second half asks whether the protocol changed
after the run and compares **blobs** (`_changed_after`, `_changed_at_tips`): the
blob of `protocol.md` at the results' add must equal the blob at the tip of every
history that carries it. A commit that only deleted the path or took it out of
the index (`git rm --cached`, what the 2026-09-24 commit did to `.tezgah/`) leaves
that blob alone and is not a change; the working-tree file is then compared
instead, so a protocol untracked and rewritten on disk is one. A commit another
ref keeps that descends from the run and holds another blob is an edit after the
run HEAD dropped. The other history's tip is a change when that history held the
run's blob on any ref and moved off it - a pre-run draft restored after the run
included. When it never held the run's blob, nothing dates its version against
the run: that is a warning, and
`--strict` refuses it. A history git cannot read is the same class: a warning,
refused under `--strict`.

**What history a row counts in.** Each comparison stays inside one repository's
history: the project's commits in the project's, the private `.tezgah`
repository's in its own (`is_ancestor`, `hooks/tezgah_research.py::is_ancestor`). A project
commit and a private-repository commit are two unrelated histories whose shas
alone order nothing - the guess that any project commit precedes any private one
was removed, and a pair the graph cannot order is reported as undecided, never
passed; the one cross-history order kept is the import exception in (A). A
prediction's `commit` is placed in the project's history only: a commit HEAD
does not reach, a benchmark pin or one a re-root left behind, stays refused.
Neither rule has a waiver.

**No history bridge.** A re-root - the whole tree landing in one "initial
commit" - leaves every experiment's two files in one add, which (A) refuses. A
declared bridge (`.tezgah/history-bridge.json`, an anchor tag pinning the old
history) used to stand in for the lost order; it proved no experiment on this
repository's workspace, and ADR 015 deleted it. The file is no longer read. A
history that is really gone is recorded instead by the seal's `history-lost`
verdict (below).

### What the order proves, and the order seal

Protocol-before-results proves **commit order, not run order**. Git records that
the protocol entered the history before the results did. It records nothing
about when the run itself happened. A session can run first, commit the
protocol, and hold the results back until after: the rule passes that. It makes
the shortcut deliberate, not impossible. `source --run` checks only that
`protocol.md` exists on disk, not that a commit holds it (`source_run`,
`hooks/tezgah_research.py::source_run`).

A history can also go missing. The 2026-10-04 re-root left most concluded
lines' commits unresolvable. So `conclude` and `close` **seal** the line
(`order_seal`, `hooks/tezgah_research.py::order_seal`). The seal is
`state.json` `order_seal`. Per experiment it holds the sha256 of `protocol.md`
and of `results.jsonl`, with the add commits beside them as information only.
It stores no order verdict. While both blobs still hash as sealed, `check`
re-derives the order from git. So a line closed before its results reached a
commit keeps no "not committed yet" answer: committing them afterwards settles
it.

`check_line` verifies the hashes on every run, with or without git (`_check_seal`,
`hooks/tezgah_research.py::_check_seal`). An edited, removed or added experiment
fails the line. The session note (`failing`, `hooks/tezgah_research.py::failing`)
and the no-slug `check` (`check` with `all_lines=False`,
`hooks/tezgah_research.py::check`) read a line under `done/` by these hashes
alone, not by `check_line`. So they see an edit after the conclusion, and the
line's other findings stay with `check <slug>` and `check --all-lines` (ADR 015).
A line under `done/` without a seal adds nothing to either. The no-slug `check`
counts it as unsealed. A `state.json` that does not parse, or a seal that is
not an object with an `experiments` object, fails the line (`done_seal`). On a
copy of this repository's workspace (34 lines, 33 under `done/`) the note took
0.014 s instead of 0.67 s. The ceiling: the seal sits in the line's own `state.json`.
Whoever edits `results.jsonl` can recompute the seal there too. It catches an
edit, not a forger.

A line concluded before seals existed carries none. The owner's verdict for
those lines (ADR 009) is `history-lost`. `tezgah-research seal <slug>
--history-lost --ack "<the owner's decision>"` writes it (`retro_seal`,
`hooks/tezgah_research.py::retro_seal`). It covers only an order the lost
history left undecidable (`LOST_HISTORY`,
`hooks/tezgah_research.py::LOST_HISTORY`). That is git that cannot answer, a
pair split across two histories, or versions git cannot place. Such an
experiment gets
`history-lost`, and `finding` keeps what the check said. `check` then warns
about it and names the ack (`_sealed_order`,
`hooks/tezgah_research.py::_sealed_order`), and `--strict` refuses it. An
experiment whose order still checks stays re-derived. The command refuses a
line with a real violation and prints the finding, which stays an error. A real
violation is one commit that added both files, a protocol added or changed after
the run, or a file with no commit yet. It also refuses a line with nothing lost.
The command takes only a line under `done/`, only once, only with an ack.

Without `--history-lost` (ADR 018) the command writes the plain seal `conclude`
writes, for a line whose every experiment's order still checks. The ack goes to
`log.md`. Any order finding refuses it: a lost history points to
`--history-lost`, and a real violation leaves the line unsealed.

### Moving a line between checkouts

A repository keeps one `.tezgah`, in its main checkout, and every worktree writes
there. `import` moves a line out of a worktree `.tezgah` written before plan 097,
or out of another clone.
A **copy** of a line, committed in another checkout, lands protocol and results
in one commit. The copy destroys the proof: `check` refuses it as "one commit
added both". `tezgah-research import <checkout> [<slug>]` moves the line with
its history instead (`import_line`). It fetches the other checkout's repository
from its disk path. It merges that history as a second parent with
`--allow-unrelated-histories -s ours`. It then takes only the imported lines'
paths from it. The source's commits order the pair here, and none of its other
lines arrive. A workspace with no commit yet first gets an empty root commit.
The same merge follows, so the source's history is never its first parent.
`import` refuses a plain copy: a line the source never committed, or a source
with no `.tezgah` repository. It also refuses a slug this checkout already
holds, and a landing path that exists as something other than a line directory.
A line arriving from the source's `open/` is a new open line here, so `init`'s
rule applies. While another line here is still open, `import` refuses it unless
`--allow-open "<reason>"` says why. The reason lands in the line's `log.md` in
the import commit. A private remote for `.tezgah` stays the owner's call, and
`import` needs none.

## Two gates, when one locked metric is not enough

A line locks one metric, and one is still enough. Beside `metric`, `baseline` and
`locked_at` a line **may** write two more fields, and this is available rather
than required - every one of the fourteen lines in this tree locks the first three
and carries neither of these, and `check` neither demands them nor warns that they
are missing:

- `capability_tolerance` - the band the capability metric has to stay inside
  before a result counts at all, written as the sentence a reader checks it
  against: *"capability metric within 0.02 of the baseline"*;
- `counter_metric` - the non-empty name of the metric the change is supposed to
  move.

A candidate then has to pass both gates - inside the tolerance **and** an
improvement on the counter-metric - and the survivors are compared against each
other on the Pareto frontier instead of by the sign of a single number
(`_check_evaluation`, `hooks/tezgah_research.py::_check_evaluation`, and the two paragraphs the skill
carries where a session reads the loop).

The rule exists for two failures this layer has already paid for. **A candidate
can buy its gain by moving the metric**: one number improved says nothing about
the number that was not measured, and this tree has exactly that record - an
experiment whose secondary number swung from 2.20 to 0.00 between two runs of the
same configuration, with nothing in the locked evaluation shaped to catch it. A
declared capability band is what refuses that trade by construction. **And an
optimizer can be the thing judged**: the fields are read by `check`, which lives
in `hooks/tezgah_research.py`, a module the frozen set forbids a prediction's
commit to touch without a human `granted_by` (`FROZEN_PATHS`), so the gate that
decides which candidate survives is not machinery the candidate can rewrite.

What the pair cannot catch alone: **a tolerance its own author sets wide
enough**. A line that writes "capability metric within 5.0 of the baseline" has
adopted the form of the two-gate rule and none of its force. From rules 6 the band
is read against a measurement. `evaluation.noise_band` is
`{"experiment": "<the experiment dir that reran the unchanged baseline>",
"spread": <the spread that rerun measured>}`. `check` warns in three cases. The
line declares `capability_tolerance` and no `noise_band`. `noise_band.experiment`
names no experiment of the line. The tolerance sentence holds a number wider than
`spread`, so the tolerance passes what noise alone would. A digit inside a name
such as `p95` is not that number (`_check_selection`,
`hooks/tezgah_research.py::_check_selection`). Whether the rerun was a fair one
stays the review's call.

## Held-out set, repeats and noise band (rules 6)

The measured line `rsi-borrow-screen` found three gaps. Of 27 decisions, 25 select
a variant and report it on the same cells. Of 23 armed experiments, 13 run once per
arm. Three lines declare a tolerance, and none of them measured it. Rules 6 add one
warning for each (`_check_selection`, `hooks/tezgah_research.py::_check_selection`).
Each stays a warning under `--strict` too, never a refusal (ADR 019):

- **Held-out set.** A measured line may name its held-out set in
  `evaluation.held_out` (a non-empty string). It may log each look at that set in
  `held_out_log.jsonl` at the line root, one row
  `{"set", "candidate", "date", "result"}` per look. `check` warns when a
  `decisions/<id>/` holds comparison cells and the line names no `held_out`: the
  variant was selected and reported on the same cells. It also warns when one
  candidate looked at one set more than once: the held-out set became development
  data for it.
- **Repeats.** An experiment is armed when its `results.jsonl` rows carry `arm` or
  `variant` with two or more values. `check` warns when no row has `repeat`,
  `repeats` or `k` above 1 and its `protocol.md` states no `k:`/`repeats:` above 1.
  An armless experiment is not read.
- **Noise band.** `evaluation.noise_band`, read in "Two gates" above.

A line opened under rules 5 or earlier is not read for any of the three.

## Rules 7: exploratory lines

A `qualitative` or `measured` line answers a question. Some asks want new ideas,
methods or approaches instead of an answer. Rules 7 add the method `exploratory`
for those asks (`hooks/tezgah_research.py::EXPLORE_RULES`,
`hooks/tezgah_research.py::METHODS`). The line runs one campaign. Many ideas
enter it, a funnel kills most of them, and a run under a frozen evaluator judges
the few that remain. One campaign is one line, so "One open line at a time" still
holds. `scope_problems` (`hooks/tezgah_research.py::scope_problems`) accepts
`exploratory` only on a rules-7 line. On an older line it names `qualitative` and
`measured` as the two methods the line can take.

### The arena lock

`init <slug> --ask "<the user's words>" --method exploratory --in "<covered>"
--out "<left alone>" --arena "<problem>" --budget "<budget>"` opens
the line. The arena is the problem in the user's words. The budget says how many
ideas, pilots and full runs, and how much wall time, the campaign may spend. A
measurable arena adds `--evaluator <path> --metric "<metric>"`. The two flags go
together, and the evaluator has to be a file in the repository. A missing arena
or budget is misuse (exit 2).

`arena_record` (`hooks/tezgah_research.py::arena_record`) builds `state.json`
`arena`. It holds the problem and the budget. A measurable arena also holds the
evaluator path, the sha256 of the evaluator's bytes and the metric. `init` also
writes `deliverable: {"kind": "finding"}`. The campaign delivers its staged ideas
as findings, never as compared variants (`hooks/tezgah_research.py::init`).

The lock has three halves:

- `arena_problems` (`hooks/tezgah_research.py::arena_problems`) names an absent
  arena, an empty problem or budget, and an evaluator with no sha256 or no metric.
  `check` reads it through `scope_problems`. It refuses these past `bootstrap` and
  warns at it.
- `_check_arena_order` (`hooks/tezgah_research.py::_check_arena_order`) finds the
  lock commit. That commit is the first one along HEAD whose `state.json` arena
  names a problem and a budget. `ideas.jsonl` and every experiment's
  `results.jsonl` have to enter the history after it. An arena that differs from
  the locked one is a refusal too. A new arena means a new line.
- `evaluator_problem` (`hooks/tezgah_research.py::evaluator_problem`) hashes the
  evaluator again. While the hash differs from the locked one, the writer and
  `check` refuse every stage row. The candidate a campaign judges must not move
  its judge.
- `append_stage` (`hooks/tezgah_research.py::append_stage`) also compares the
  working `state.json` arena with the arena at the lock commit
  (`hooks/tezgah_research.py::_arena_lock`). While they differ, it refuses every
  stage row. So a rewritten `evaluator_sha256` does not reopen the campaign.

`init` prints the next step: commit the arena with `tezgah-research commit` before
the first idea. The arena replaces the one locked metric of a measured line.
`_check_evaluation` (`hooks/tezgah_research.py::_check_evaluation`) and
`_check_evaluation_order` (`hooks/tezgah_research.py::_check_evaluation_order`)
skip an exploratory line for that reason.

### Three files

The campaign lives in three append-only files at the line root. One function
judges each row type, and the writer and `check` both call it. No file stores a
status. An idea's stage is its newest `stages.jsonl` row
(`hooks/tezgah_research.py::campaign_stages`).

| File | One row | Writer | Judge |
|---|---|---|---|
| `ideas.jsonl` (`IDEAS_FILE`) | `id` (`I<n>`, unused so far), `statement` (two sentences at most), `mechanism`, `trace` (an in-scope item), `operator` (one of `OPERATORS`), `generator` (`{family, model}`), `kill` (the result that would kill it), `date`, and `parents` for a `mutation` (one or more) or a `crossover` (two or more) | `idea <slug>` | `idea_problems` |
| `stages.jsonl` (`STAGES_FILE`) | `idea`, `stage`, `evidence`, `reason` for a kill, `date` | `stage <slug> <idea> <stage>` | `stage_problems` |
| `tournament.jsonl` (`TOURNAMENT_FILE`) | `a`, `b`, `judge` (`{family, model}`), `order` (`ab` or `ba`), `winner` (`a`, `b` or `tie`), `rationale` | `match <slug>` | `match_problems` |

The field list is `IDEA_FIELDS` (`hooks/tezgah_research.py::IDEA_FIELDS`). The
moves are `OPERATORS` (`hooks/tezgah_research.py::OPERATORS`). `user` marks an
idea the person asked for. `PARENT_OPERATORS`
(`hooks/tezgah_research.py::PARENT_OPERATORS`) sets how many parents a derived
idea names. An idea outside the arena's scope gets one line under Open questions
in `findings.md`, never a row.

Every append goes through `_append_campaign`
(`hooks/tezgah_research.py::_append_campaign`). It takes the file lock and reads
the rows from the locked descriptor. It judges the new row against them, cuts any
torn tail (`truncate_to_committed`) and writes. A refused append leaves no file
behind. `check` refuses a committed row that a later version changed or dropped.

### The stage funnel

`STAGES` (`hooks/tezgah_research.py::STAGES`) gives the order: `proposed`,
`duplicate`, `prior-art`, `screened`, `piloted`, `promoted`, `confirmed`, and
`killed`. `stage_problems` (`hooks/tezgah_research.py::stage_problems`) holds
the moves to it:

- The idea row is the `proposed` stage. A stage row that says `proposed` is a
  refusal.
- A stage moves forward in that order only, or to `killed`. A kill needs
  `--reason`.
- A stage also needs its prerequisite somewhere in the idea's history
  (`hooks/tezgah_research.py::PREREQUISITES`). `screened` needs a `prior-art`
  row. `piloted` needs `screened`, `promoted` needs `piloted`, and `confirmed`
  needs `promoted`.
- `killed` is final. A revived idea is a new idea that names the old one as its
  parent.
- After `duplicate`, the only allowed row is `killed`. The same holds after a
  `known` prior art.

Each stage asks for its own evidence. `--evidence` takes a reference or a JSON
object.

| Stage | Evidence | What the judge asks |
|---|---|---|
| `duplicate` | `{"of": "<id>", "similarity": <0..1>}` | `of` names another idea of the line |
| `prior-art` | `{"verdict": "novel\|incremental\|known", "nearest": [...], "delta": "<one sentence>"}` | `nearest` names at least `NEAREST_MIN` (3) notes. `literature/INDEX.jsonl` indexes each one, and not all of them are `agent-report`. `delta` is one sentence (`_prior_art_problems`) |
| `screened` | none | `tournament.jsonl` holds at least one match that names the idea |
| `piloted`, `promoted` | `<h>` or `experiments/<h>` | `protocol.md` names the idea id and repeats its `kill` text. `results.jsonl` holds a row. When the check asks git, `protocol.md` is in a commit. If `results.jsonl` is committed too, `protocol.md` entered the history before it (`_run_problems`) |
| `confirmed` | `{"experiment": "<h>", "set": "<set>"}` | the arena has an evaluator. The experiment differs from every `promoted` row's experiment. The run passes the same `_run_problems` checks. The first `held_out_log.jsonl` row for that set names this idea. Each look of this idea at the set carries a `YYYY-MM-DD` date, and none is dated before the idea's promotion: an earlier look was part of the selection. A look logged after the confirmation changes nothing (`_confirm_problems`) |
| `killed` | `--reason "<why>"` | a reason |

A `known` prior art kills the idea in the same write. `append_stage`
(`hooks/tezgah_research.py::append_stage`) needs `--reason` for it. It appends
the prior-art row and its `killed` row under one lock, so no file state holds a
known idea alive. `check` refuses a `known` prior art with no kill after it.

### The tournament is a prior

A match is one judge's verdict on a pair. `bradley_terry`
(`hooks/tezgah_research.py::bradley_terry`) fits a strength per idea from the
matches. `board` ranks the ideas by it. The score moves no stage. `screened`
asks only that a match exists. An LLM ranking is a prior, and a run under the
frozen evaluator is the judge.

`_tournament_warnings` (`hooks/tezgah_research.py::_tournament_warnings`) warns
about thin judging. A pair judged only by the family that generated one of its
ideas warns, unless both generators' families judged it. A pair judged in one
presentation order warns. An idea with fewer than two judges warns.

### Reports: board, dedup, yield

The three reports write nothing and exit 0. None of them is a gate.

- `board <slug>` (`hooks/tezgah_research.py::board`) shows the arena and whether
  the evaluator still hashes as locked. It shows each file's row count, each
  idea's rank, stage, score, record, operator, generator family and next action,
  and the campaign's next step. An idea whose prior art is `known` gets the
  `stage ... killed --reason` command as its next action. That resumes a campaign
  whose kill row was torn off.
- `dedup <slug>` (`hooks/tezgah_research.py::dedup`) clusters the `proposed`
  ideas by statement, at one similarity threshold. The lowest id of a cluster
  represents it. For every other member it prints the `stage ... duplicate`
  command to run. `similarity_matrix` (`hooks/tezgah_research.py::similarity_matrix`)
  uses the static embedding when the feature is on and pinned. Otherwise it reads
  BM25 scores (`hooks/tezgah_rank.py::scores`) as a similarity. Every output names
  the backend and where its threshold came from.
- `yield` (`hooks/tezgah_research.py::yield_report`) counts, per operator and per
  generator family, how many ideas reached each stage. It lists the kill reasons.
  It gives Spearman's rho between the board score and the pilot outcome
  (`hooks/tezgah_research.py::spearman`). It proposes the next campaign's operator
  weights (`hooks/tezgah_research.py::operator_weights`). `EXPLORE_SHARE` (0.2)
  of each draw stays uniform, so a move with no payoff yet still gets tried. It
  reads the open exploratory lines, or every one with `--all-lines`.

### Resume from the files

Nothing outside the three files holds campaign state. A fresh session runs
`board` and goes on from its `next:` line. A writer that dies mid-append can
leave a fragment past the last newline. `_campaign_rows`
(`hooks/tezgah_research.py::_campaign_rows`) reads up to the committed boundary
and reports the fragment's size. `board` prints it on a `resume:` line. The next
append drops the fragment, so the fix is to run the append that crashed again.

### How many ideas were tested

Fifty ideas tested at the 5% level yield about 2.5 winners by chance. A reader
cannot discount what nobody counted. `_check_tested`
(`hooks/tezgah_research.py::_check_tested`) warns when `to_human/report.md` has
no line that names `piloted` with the number of ideas that reached it. The same
holds for `promoted`. A number followed by a full stop counts, as in "reached
piloted: 2.". `board` prints both numbers on its `tested:` line.

### The dedup threshold (two label sets)

Si et al. called two seed ideas duplicates at cosine 0.8 on MiniLM. That number
does not carry to another similarity. Two label sets measured it here.

- The fixture: 40 idea-statement pairs, 20 of them duplicates. The author of the
  code labelled them. The acceptance runner records the sweeps as fixture-scoped
  experiments: `dedup-calibration` (BM25) and `dedup-calibration-embed`
  (embed-mrl). Copies stay under `.tezgah/scratch/calibration/`.
- MRPC: 400 pairs of the Microsoft Research Paraphrase Corpus test set, 200
  paraphrases and 200 not, sampled with seed 87. Human annotators labelled them.
  The pairs are news sentences, and the negatives share many words. At BM25 0.30
  the sample kept every paraphrase and 95% of the negatives. The script and its
  output are `.tezgah/scratch/calib2/run.py` and `out.txt`.

| Backend | F1 at 0.8 (fixture / MRPC) | Default | F1 at the default (fixture / MRPC) |
|---|---|---|---|
| embed-mrl | 0.62 / 0.64 | 0.65 | 0.90 / 0.705 |
| BM25 | 0.09 / 0.41 | 0.40 | 0.70 / 0.69 |

The default is the threshold, in steps of 0.05, whose worse F1 over the two sets
is highest. Neither the author's labels nor the news domain picks it alone. On
MRPC the best F1 beats the always-duplicate baseline (0.667) by about 0.04. The
defaults are a coarse filter for a session to review, not a judge.

`DEDUP_THRESHOLDS` (`hooks/tezgah_research.py::DEDUP_THRESHOLDS`) holds the two
values. Any other backend keeps `DEDUP_THRESHOLD`
(`hooks/tezgah_research.py::DEDUP_THRESHOLD`), Si et al.'s 0.8, and the output
calls it uncalibrated. `--threshold` overrides all of them. Its range is
`(0, 1]`.

### The evidence behind the method

- Si et al., arXiv 2409.04109: about 5% of 4,000 generated seed ideas were not
  duplicates (cosine 0.8). The best LLM judge (a Claude-3.5 pairwise ranker)
  agreed with the human ranking 53.3% of the time. Split-half reviewer panels
  agreed 56.1%.
- The ideation-execution gap, arXiv 2506.20803: after execution, AI ideas lost
  1.98 points overall and human ideas lost 0.63.
- Gupta and Pruthi, arXiv 2502.16487: 24% of 50 AI research documents
  paraphrased or substantially borrowed earlier work. Plagiarism detectors missed
  them.
- HindSight, arXiv 2603.15164: novelty as an LLM judges it correlates negatively
  with realized impact (rho = -0.29).
- Darwin Godel Machine, arXiv 2505.22954: an archive of stepping stones beats
  hill-climbing. The loop also removed its own detection markers and faked test
  logs.
- ShinkaEvolve, arXiv 2509.19349: parent sampling by fitness and novelty,
  novelty rejection by embedding, and UCB1 over models.
- POPPER, arXiv 2502.09858: falsification experiments on measurable implications,
  with Type-I error control.

The consequences:

- An LLM ranking is a prior, never a verdict.
- A run under the frozen evaluator is the judge.
- Each idea gets its own prior-art check. No idea reaches `screened` without a
  `prior-art` row (`hooks/tezgah_research.py::PREREQUISITES`).
- `dedup` and the operator weights keep the ideas diverse.
- The report always states how many ideas the campaign tested.

Rules 1-6, `FROZEN_PATHS` and ADR 009 stay as they were. Predictions and
components take nothing new. `research-off` covers this method too.

## Rules 8: captured evidence and computed certainty

A rules-7 line takes the session's word for three things. A cited paper exists, a
quote stands in it, and a number came from a run. Rules 8 make the tool fetch
and store those bytes. `check` then re-derives each claim's
support from them and computes a certainty level per claim. No claim states its
own level. The capture commands are `hooks/tezgah_research_capture.py::COMMANDS`.
The instrument, release and calibration commands are
`hooks/tezgah_research_evidence.py::COMMANDS`. The statistics in
`hooks/tezgah_research_stats.py` use the standard library only.
`_check_rules8` (`hooks/tezgah_research.py::_check_rules8`) runs the capture
checks, the core checks and the certainty engine, in that order.

A line whose `state.json` `rules` is below 8 keeps every rule it had, and nothing
in this section reads it (`hooks/tezgah_research.py::_evidence`). It still gets
the claim-number rule under `--strict` and the INDEX `verified` warning. A rules-8
line gets `untraced-number` and the receipts instead. A missing obligation there
lowers a level and never refuses, not even under `--strict`.

### What `check` prints for a rules-8 line

`check` keeps its `FAIL <slug>:` and `warn <slug>:` lines. A rules-8 line adds
report lines after them, and they never count as problems: `certainty`, `stats`,
`effect`, `instrument`, `ppi`, `stopping`, `online` and `budget`. Under
`check --json` the line's row carries them as `report`. It also carries
`certainty`, one `{level, start, steps}` object per claim id
(`hooks/tezgah_research.py::check_line`). Every new command exits 0 when done. It
exits 1 on a refusal, prints `FAIL <slug>: <reason>` and writes nothing. It exits
2 on misuse.

`TEZGAH_CAPTURE_MAP=<json file>` answers every HTTP call of the capture commands
and of `check --online` from a map of URL to body file. Tests and offline runs use
it (`hooks/tezgah_research_capture.py::fetch_url`). `TEZGAH_ORX_BIN` overrides
the `orx` lookup.

### The question class: `init --class`

A complete command for a measured R6 line:

```
tezgah-research init cache-latency --ask "does the cache cut p95?" \
  --question "Does the read cache cut p95 latency of the read path?" \
  --method measured --class R6 --in "p95 of the read path" --out "write path"
```

Leave out `--question` and `check` refuses the line with
`state.json records no question`. `--class` writes `state.json` `question_class`.
`--class R0` exits 1 with `R0 gets no line` before any other argument counts
(`bin/tezgah-research::cmd_init`). An R0 question is factual or reference, and the
reply answers it. A new line owes more before `check` passes clean. It owes the
success criteria of "The ask contract" and the protocol labels of "Protocol
sections (rules 4)". It owes the scope of "Scope lock (rules 5)" and, on a
measured line, the committed evaluation lock under "What `check` refuses". It
writes four formats by hand, and `check` reads each one:

- An INDEX row's `note` is a path relative to `literature/`: `smith2020.md` names
  `literature/smith2020.md`. A path with `..`, or one `literature/` does not hold,
  fails with `which literature/ does not hold` (`hooks/tezgah_research.py::_read_index`).
- A claim's `provenance` and the `tag` of each `state.json` session entry take
  one of four values (`hooks/tezgah_research.py::PROVENANCE`). `user`: the user
  stated or confirmed it. `ai-suggested`: the session inferred it and nobody
  confirmed it. `ai-executed`: the session ran or wrote it. `user-revised`: the
  session suggested it and the user corrected it.
- `to_human/review.json` scores six `dimensions`: `evidence_relevance`,
  `falsifiability`, `scope_calibration`, `argument_coherence`,
  `exploration_integrity` and `methodological_rigour`
  (`hooks/tezgah_research.py::REVIEW_DIMENSIONS`). Each score is an integer from 1
  to 5. A missing score or one outside that range fails
  (`hooks/tezgah_research.py::_check_review`).
- `state.json` `deliverable` is an object. Its `kind` is one of
  `DELIVERABLE_KINDS`, and "Variants of the deliverable" covers its variant count.
  `path` names the deliverable's file, read relative to the line first and then
  to the repository (`hooks/tezgah_research.py::_deliverable_file`). `ask`, when
  present, is a list of the ask's items, each a non-empty string. Anything else
  fails with `state.json deliverable ask is not a list of the ask's items`
  (`hooks/tezgah_research.py::deliverable_problems`).

With a class, `init` prints three more things:

- `obligations: <step>, <step>, ...` lists every certainty step the class can
  trigger (`hooks/tezgah_research.py::obligations`).
- `budget <slug>: sources a/b searches c/d runs e/f` counts INDEX rows, SEARCHES
  rows and `source: orx:` results rows against the tier's caps
  (`hooks/tezgah_research.py::BUDGETS`). The caps are starting values: quick
  10/10/10, study 30/40/40, program 100/150/200. `check` prints the same line and
  warns `over budget` past any cap (`hooks/tezgah_research.py::budget`).
- `overlap: <line>/<claim> <status> <similarity>` names each claim of a done line
  whose similarity to the question reaches 0.5
  (`hooks/tezgah_research.py::overlaps`).

The class fixes the methods a line may take (`hooks/tezgah_research.py::CLASS_METHODS`)
and adds its own steps (`hooks/tezgah_research.py::CLASS_STEPS`):

| Class | Methods | Class steps (each -1 on every claim) |
|---|---|---|
| R1 | qualitative | none |
| R2 | qualitative | `no-grey-quality`: a grey INDEX row without `quality` |
| R3 | qualitative, measured | `no-population`: state lacks `population` or `n` |
| R4 | measured | `no-confounders`: a protocol without `confounders:` |
| R5 | measured | `fewer-than-two-rivals`, and `no-positive-control`: a measured protocol without `control:` |
| R6 | measured | `fewer-than-two-rivals`: fewer than two `rival: <text> excludes: <text>` protocol lines |
| R7 | qualitative | `no-dual-screening`: a screened record with fewer than two screeners, and `no-recall-stopping`: `stopping.rule` is not `hypergeometric` |
| R8 | qualitative | `no-dual-screening`: under 20% of records dual-screened, or a dropped record screened once |
| R9 | qualitative | `no-amstar`: an INDEX row without `amstar` |
| R10 | qualitative | `no-codebook`: no `codebook.md` in the line |
| R11 | exploratory | none |
| R12 | qualitative, measured | `fewer-than-two-approaches`: fewer than two `state.approaches` entries with `biases` |

Every class can also take `no-question-class` (no class at all), `class-unreviewed`
(the review's `question_class` is absent or differs) and `method-not-allowed`
(`hooks/tezgah_research.py::_routing_steps`). A search line is a line of class R1,
R2 or R7 to R10, a `qualitative` line, or a line with no class.

### Capture: `cite`, `fetch`, `search`, `source`

The tool fetches what a line cites, never the session. Each capture command
writes its files, appends its ledger rows and commits exactly those files as
`capture: <command> <slug>` (`hooks/tezgah_research_capture.py::commit_capture`).
The commit lands in the workspace's own repository, or in the project's when the
project tracks the workspace.

**`tezgah-research cite <slug>`** queries `arxiv`, `crossref`, `openalex` and
`semanticscholar` (`hooks/tezgah_research_capture.py::PROVIDERS`) for every formal
INDEX row whose `id` is an arXiv id or a DOI. A `pubmed:<pmid>` row goes to
`pubmed`. An `openalex:W<n>`, `s2:<paperId>` or `pubmed:<pmid>` id resolves through its
own registry alone, so it takes the step `one-provider`
(`hooks/tezgah_research_capture.py::receipt_urls`). Each answer of status 200
becomes a row of `literature/.receipts/RECEIPTS.jsonl`, and its raw bytes go to
`literature/.receipts/<sha256>.raw`. Any other status, such as a 404 or a 429,
prints `receipt <id> <provider>: status <n>, not recorded` and writes nothing. A
later `check --online` would read such an answer as drift, which is why it is not
recorded. A row filed by an older `cite` at another status is never compared. With no 200 at all,
`cite` prints `no registry answered 200, so nothing was written`
(`hooks/tezgah_research_capture.py::cmd_cite`). `cite` skips any other id and prints
`is not an arXiv, DOI, OpenAlex, Semantic Scholar or PubMed id`. With nothing to
cite it prints `no formal row with an arXiv, DOI, OpenAlex, Semantic Scholar or
PubMed id to cite`.
It exits 0 even when nothing resolves, because judging the receipts is `check`'s
job (`hooks/tezgah_research_capture.py::cmd_cite`). The INDEX may write an id as a bare DOI
such as `10.1145/abc.1`. It may also write a bare arXiv id in new or old style
(`1805.08612`, `hep-th/9901001`) or an `arxiv.org` abs, pdf or html URL. Each
reads as `doi:` or `arXiv:<id>`. A JSON number is never an id
(`hooks/tezgah_research_capture.py::norm_id`). `check`
reads the receipts offline and judges only those for an id the INDEX holds now
(`hooks/tezgah_research_capture.py::_check_receipts`):

- `check` refuses a receipt row that a re-parse of its raw bytes contradicts:
  `not derived from its capture`.
- A resolved receipt counts for the INDEX id only when its raw bytes name that id
  (`hooks/tezgah_research_capture.py::receipt_ids`). A receipt whose raw bytes name
  another id for the same work does not count for it, and `check` does not refuse
  it. It warns once:
  `the <provider> receipt for <id> names <ids>, not that id, so it does not count for it`.
  The INDEX row then resolves through the other providers, or fails with
  `resolves in no registry`.
  A receipt's `url` has to be the provider's receipt URL for that id. Else the refusal
  reads `<url> is not the <provider> receipt URL for that id (<expected>)`. A
  refused receipt resolves nothing.
- It refuses a formal row that no receipt resolves: `resolves in no registry`. A
  formal row with an empty `id` gets the same refusal. A row with
  `unindexed_reason` takes the step `unindexed-source` instead.
- A row that one provider alone resolves, with an agreeing header, takes the step
  `one-provider` (`hooks/tezgah_research_capture.py::citation_verdict`). An
  alphaXiv or `orx paper` record counts as `arxiv`.
- An INDEX `title`, `year` or `first_author` that agrees with no resolved
  receipt takes `header-mismatch`. Titles agree at a word overlap of 0.5 or more
  (`hooks/tezgah_research_capture.py::title_agrees`). Years agree within one, for
  a preprint against its venue year.
- `check --online` fetches up to ten receipts recorded from a 200 again from the
  provider's receipt URL. It never compares a row of another status
  (`hooks/tezgah_research_capture.py::_check_receipts`). A changed id, title, author or year prints
  `online <slug>: <id> <provider> <field> drifted`, for instance
  `online <slug>: <id> <provider> id drifted`, and takes `online-drift`.

**`tezgah-research fetch <slug> <note> [--file <path> --ack "<the user's words>" | --orx]`**
stores the passages of a source around every quote the line makes of it. The URL
always comes from a receipt. The first step that yields text decides the capture
(`hooks/tezgah_research_capture.py::cmd_fetch`):

| Step | Source | Access |
|---|---|---|
| 1 | `--file <path>` (needs `--ack "<the user's words>"`, else exit 2), or `--orx` | `user`, or `full` |
| 2 | an arXiv id: `https://arxiv.org/html/<id>` answering 200 | `full` |
| 3 | a DOI: the OpenAlex receipt's `open_access.oa_url` answering 200 with no PDF body and holding a work's body (below) | `full` |
| 4 | `orx paper --full <id>`, when orx is installed and prints text | `full`; `abstract` when the text is short and holds none of the line's quotes |
| 5 | the abstract of a resolved receipt | `abstract` |
| 6 | nothing yielded text: the record names the reason, exit 0 | `none` |

An `oa_url` page holds a work's body when its text has `BODY_SENTENCES` (100)
distinct sentences of `BODY_WORDS` (10) or more words
(`hooks/tezgah_research_capture.py::body_sentences`). A repository landing page
holds the metadata and the abstract, and falls short. When step 4 yields no text
either, `fetch` keeps that page as access `abstract`, with the `oa_url` as its
url. Its reason reads `the open-access page holds <n> distinct sentences of 10+
words, under the 100 of a work's body: a landing page`. A quote that page lacks
costs the step `abstract-only`, never a refusal.

Step 4 takes the same body test. Text under 100 such sentences that holds one of
the line's quotes still backs it, so it stays `full`. Text that holds none is
`abstract` - orx's metadata and abstract for a paper it cannot read whole - and
its reason reads `orx held <n> distinct sentences of 10+ words, under the 100 of
a work's body, and none of the line's <n> quotes: metadata and abstract, not full
text`. A quote the stub lacks costs `abstract-only`, never a refusal.

The quotes come from three places. One is a citing claim's `quote` field. Another
is each double-quoted span of three or more words in its `statement`. The last is
each `> "..."` blockquote of the note. A quote splits on `...`, `…` and `[...]`.
Each fragment of three or more words has to appear in order. `fetch` keeps the
whole extracted text in `literature/.sources/<sha256>.txt`, and its record names
it as `text_file` with `text_sha256`. `check` looks for each quote in that text,
in the stored passages and in the abstracts of the receipts for the note's id
(`hooks/tezgah_research_capture.py::_found`). Normalisation drops citation
markers, also one split by tags or spaces such as `[ 12 ]`. A hyphen between two
letters reads as a space. Inner quotation marks are optional: curly or straight,
single or double, in the quote and in the text. Where an extraction dropped a
space (`human-inthe-loop` for `human-in-the-loop`), a quote still matches with its
spaces optional, its letters in order (`hooks/tezgah_research_capture.py::_locate`). A TeX command beside rendered
math (`∼ \sim`) drops, `∼` reads as `~`, and a space beside a math symbol drops
(`hooks/tezgah_research_capture.py::normalise`). `check`
refuses a record whose text file is gone with `has no capture`, and one whose
text file hashes otherwise with `hash mismatch`
(`hooks/tezgah_research_capture.py::_source_text`). The record lands in
`literature/.sources/<sha256>.json` with the 300 characters either side of each
match, and `literature/.sources/SOURCES.jsonl` gets its row. A SOURCES row sets
access only through its own `literature/.sources/*.json` record for that note,
never through its own `access` field
(`hooks/tezgah_research_capture.py::_source_records`). A claim's proof may end a
note path with `.`, `,`, `;`, `:` or `)`, and the note still counts as cited
(`hooks/tezgah_research_capture.py::cited_tokens`). The note's latest record
decides what `check` does
(`hooks/tezgah_research_capture.py::_check_sources`):

- `full` or `user`: `check` looks for each quote of the note's own blockquotes in
  its capture. It looks for a claim's quote in the captures of every note the
  claim cites. It refuses that quote only when every cited note holds full text
  and none of them holds the quote. A cited note without full text already
  narrows the claim by its step. The refusal names the notes it searched:
  `claim <id>: "<quote>": quote not in the captured source text (searched literature/<a>, literature/<b>; ...)`
  (`hooks/tezgah_research_capture.py::_quote_missing`). The message names the two
  exits. Rephrase a non-quote without quotation marks, or `fetch --file` the
  version quoted. `check` skips the quotes of a claim that another row
  supersedes (`hooks/tezgah_research.py::_superseded`).
- `abstract`: claims citing the note take `abstract-only`.
- `none`, or no capture: they take `source-not-captured`, a ceiling.
- A concluded line with formal rows owes the share of its sources without full
  text in its report. The share counts a source with no capture, an `abstract`
  capture or a `none` capture alike. Any of `closed-access: <k> of <n>`,
  `not full text: <k> of <n>` or `abstract-only: <k> of <n>` states it. A missing
  share warns `report states no closed-access share: <k> of <n> sources have no full text`
  and names the three forms (`hooks/tezgah_research_capture.py::_check_sources`).
  The line also owes `user-supplied: <k> of <n> sources` when a latest record is `user`.
  Both rules are soft.

**`tezgah-research search <slug> --tag primary|snowball|counter|known [--item "<scope.in item>"] -- <connector> <args...>`**
stores a connector's raw output in `searches/raw/<sha256>.raw` and one row of
`searches/SEARCHES.jsonl`. Its `hits` and `ids` come from the raw bytes
(`hooks/tezgah_research_capture.py::cmd_search`). The allowlist is the four
registries, PubMed, Scopus, ACM DL, `orx discover` and `orx paper`. Any other
connector exits 1 with `connector not on the allowlist`. PubMed is E-utilities
`esearch` and yields `pubmed:<pmid>` ids. Scopus is the Elsevier search API. It
needs an API key in `TEZGAH_SCOPUS_KEY`, and without it `search` exits 2 naming the
variable. Its entries yield their DOIs. `dl.acm.org` answers a browser check with
403, so ACM DL reads through Crossref's ACM member (320) and yields its DOIs. `--tag counter` without an `--item` equal to a
`scope.in` entry exits 2. A search that does not answer 200 exits 1 and writes
nothing. An answer that does not parse as that connector's response exits 1 with
`does not parse as a <connector> response; nothing was written`. An answer
byte-identical to an earlier search's capture writes no row, and `search` says so
and exits 0. The session screens by hand, one row per decision in
`searches/screening.jsonl`: `{"search", "id", "decision": "kept"|"dropped", "reason", "screener"}`.
`check` refuses a SEARCHES or SOURCES row with no `file`:
`<SEARCHES|SOURCES> row <n> names no file, so it has no capture`
(`hooks/tezgah_research_capture.py::_check_ledger_files`). It also refuses a
SEARCHES row whose file lies outside `searches/raw/`, or whose capture another
row already names. Both messages end `so it has no capture`
(`hooks/tezgah_research_capture.py::_check_searches`). `check` refuses a capture
that does not parse under its row's connector with `not derived from its capture:
<file> does not parse as a <connector> response`
(`hooks/tezgah_research_capture.py::schema_ok`). It refuses a row whose `hits` or
`ids` a re-parse contradicts the same way. Only a row that passes these counts toward a
connector, a counter search or saturation. A screening row for an id that no
captured search returned takes the step `screened-outside-search`.

On a search line, claims that cite literature take these steps
(`hooks/tezgah_research_capture.py::_check_searches`). `one-connector` means fewer
than two connectors. `no-counter-search` means a `scope.in` item with no `counter`
search. `known-item-missed` means a `state.known_items` id that no capture holds.
The other two are `no-stopping-rule` and `stopping-not-met`. `state.stopping` names the stopping
rule. It has to enter the history before the first search row, or the line takes
`no-stopping-rule`:

- `{"rule": "hypergeometric", "recall": t, "confidence": c}` runs buscarpy's
  recall test (Callaghan and Müller-Hansen, 2020) over the screening order
  (`hooks/tezgah_research_stats.py::hypergeometric_p`). It holds when p < 1 - c,
  and `check` prints `stopping <slug>: hypergeometric p=<p> met|not met`.
- `{"rule": "saturation", "run": R}` holds when the last R search rows add no new
  record.
- `{"rule": "pragmatic", "risk": "<text>"}` always holds and names the risk taken.

**`tezgah-research source <slug> <h> --run <id> [--instrument <name>] [--arm <a>] [--item <i>] [--value <field>=<number>]... [--ack "<the user's words>"]`**
writes its results row itself (`hooks/tezgah_research.py::source_run`). On a
rules-8 line it first asks git for a commit that holds the evaluation lock. It
refuses before writing anything when it finds none:
`the evaluation lock is not committed: no committed state.json holding the metric and the baseline precedes this capture`.
The message names the way out, `tezgah-research commit <slug> "<message>"`. A
line with no `evaluation` is exempt, as in `check`
(`hooks/tezgah_research.py::_orders_lock`). An exploratory line's lock is its
arena. `source` refuses there when no committed `state.json` holding the arena
precedes the capture: `the arena is not committed`. On a rules-8 line it also
refuses before writing when the experiment's `protocol.md` is not committed
(`experiments/<h>/protocol.md is not committed`), or carries an invalid record
(`experiments/<h>/protocol.md carries an invalid record`). It refuses a protocol
whose `metric:` list holds no locked metric, by the rule `check` applies below:
`experiments/<h>/protocol.md registers a metric other than the locked one`
(`hooks/tezgah_research.py::metric_problem`). The capture commits its results at
once, and the protocol cannot change after that. Each of these messages names
`tezgah-research commit` as the way out and ends `nothing was written`.

`orx logs` may print a summary in place of the log: the path to the full log
file and its size. `source` then reads that file and checks its size against the
count orx printed (`hooks/tezgah_research.py::_full_log`). It stores the whole
log, printed or read from that file. A log above 16 MiB meets
`RUN_LOG_BOUND` and exits 1
(`hooks/tezgah_research.py::RUN_LOG_BOUND`), unless `--ack "<the user's words>"`
says to keep it. The log then lands whole and the row records the `ack`. Four
messages refuse a log it cannot hold:

- `printed the log's path without its size`
- `bytes, above the <bound>-byte bound a receipt is committed under`, which names
  `--ack`
- `cannot read the log orx logs <run> names`
- `the run is still writing it or it changed since`

`--ack` files a log above the bound and the row records the words. The row names
`run`, the arm, the item and each value as a number.
`--instrument <name>` writes `instrument`, `--arm` writes `arm` and `--item`
writes `item`, each without the others. A row with `instrument` and `item` is one
`gold` and `label` read. When the line names an orx project
the row also holds the engine's `status`. `source` matches `--value` against the
whole log, by one number reader (`hooks/tezgah_research_capture.py::log_numbers`). It
reads thousands separators, so `12,345` is 12345, and exponents such as
`1.2e-3`, which `--value k=1.2e-3` also accepts. It reads a number with a unit
glued on as that number: `22.3ms`, `1.2s`, `512MB`, `3.2x` and `45%`
(`hooks/tezgah_research_capture.py::LOG_NUMBER`). A number glued to letters in
front, such as `r1` or `h2`, stays no number. A value matches a logged number
by numeric equality, so `1.5` matches `1.50`. A value with no equal number in the
stored log exits 1 with
`value not in the run log (orx logs <run> holds no number equal to <v>)`. A
reserved key (`source`, `log`, `run`, `instrument`, `arm`, `item`, `scope`,
`fixture`, `status`, `command`, `ack`) as `--value` exits 2. A second filing of one run
writes `raw/<run>.<n>.log` and a second row. A refile is a correction. The latest
row filed for the same `run`, arm, item and instrument stands for it
(`hooks/tezgah_research.py::_live`). So a run filed once per arm or item keeps
every row, and every count and statistic counts each such row once. A row with
no `run` counts on its own.
`check --orx` reads `orx runs` for the census. It takes a JSON answer, or the
table orx 0.2.20 prints instead, which is all it has (no `--json`). The table's
`ID` and `STATUS` columns are the run and its status
(`hooks/tezgah_research_capture.py::_runs_table`). An answer that is neither warns
`printed neither JSON nor a run table`. It warns `orx run <id> has no results
row` for an engine run that no row names. A row with status `aborted` or `failed` stays a row and counts in no
group.

**Write once.** The capture files live under `literature/.receipts/`,
`literature/.sources/`, `searches/raw/`, `experiments/*/raw/` and
`instruments/gold/`. A command whose target exists with other bytes exits 1 with
`capture exists` (`hooks/tezgah_research_capture.py::write_captures`). The
ledgers only grow. `check` refuses what changed anyway
(`hooks/tezgah_research_capture.py::_check_write_once`,
`hooks/tezgah_research_capture.py::_check_ledger_files`):

- a capture file that differs from the blob its first commit added
  (`changed after its first commit`)
- a ledger row that a later version dropped, changed or moved:
  `a row changed, moved or went missing after its first commit; a ledger is append-only`.
  The rows of each earlier version have to stay in the latest one in their order.
  Two branches that appended and merged pass. `check` refuses a reordered ledger,
  because its readers take the latest SOURCES record, the first label and the
  first gold draw.
- a ledger row whose file does not hash to its `sha256`: `hash mismatch`.

Each RECEIPTS and SEARCHES row records `parser`, the version of the parser that
derived it (`hooks/tezgah_research_capture.py::PARSER`). A row without the field
reads as version 0. `check` re-derives every row under the current parser, so no
row is held to its hash on its own say-so. A later tezgah wrote any row that names
a newer version than the tool's, and `check` refuses it
(`hooks/tezgah_research_capture.py::_newer`):
`names parser version <v>, newer than this check's 1`.

The append-only ledgers are read across every ref, as the results file is. The
stopping-rule order and the capture files read the current branch's lineage only
(`hooks/tezgah_research.py::file_versions`). A backdated side branch therefore
cannot satisfy the stopping-rule order. These
rules cannot see a capture that was false at its first write. `check --online` is
the check for that case.

### How a claim's certainty is computed

The levels, low to high, are `very-low`, `low`, `moderate` and `high`. A claim
below `moderate` is exploratory. Its start level is the highest over the parts
its `proof` cites (`hooks/tezgah_research_evidence.py::start_level`):

| Part the proof cites | Start |
|---|---|
| results of an experiment whose protocol says `design: experiment` (the default with a `change:` line) | `high` |
| results of an experiment with `design: observational` (the default without `change:`) | `low` |
| a literature note whose INDEX `class` is `formal` | `moderate` |
| a `grey` note | `low` |
| an `agent-report` note | `very-low` |
| a claim of `kind: code` | `high` |
| a claim of `kind: derivation` | `moderate` |

Each step `check` finds for a claim either lowers the level by one or caps it at
`low` (`hooks/tezgah_research_evidence.py::STEPS`). The decrements apply first,
then the ceilings, and the floor is `very-low`. A step counts once per claim even
when two parts trigger it (`hooks/tezgah_research_evidence.py::compute`). `check`
prints one line per claim, in `claims.jsonl` order:

    certainty <slug>: <id> <level> start=<level> steps=<step>,<step>|none

A claim may declare `"certainty": "<level>"`. `check` refuses a declared level
above the computed one: `claim <id> declares certainty <declared> above the computed
<level> (<steps>)`. On a concluded line, `to_human/report.md` owes one line per
claim that names its id and its computed level word. A claim below `moderate`
also owes `exploratory` on that line. A missing line warns
`report states no certainty for claim <id>`, and `--strict` refuses it.

A narrowed claim, an `inconclusive` hypothesis and `close --limit` are normal
outcomes of a rules-8 line. Lowering what a claim says is how a line meets a
low level, not pushing harder for a bigger one.

The steps, by name as `check` prints them:

| Step | Effect | Trigger |
|---|---|---|
| `header-mismatch` | -1 | the INDEX header agrees with no resolved receipt |
| `unindexed-source` | -1 | no receipt resolves the row, and it carries `unindexed_reason` |
| `online-drift` | -1 | `check --online` saw a stable field change |
| `abstract-only` | -1 | the note's latest capture has access `abstract` |
| `source-not-captured` | ceiling | the note has no capture, or its latest has access `none` |
| `one-connector` | -1 | search line: fewer than two connectors |
| `no-counter-search` | -1 | search line: a `scope.in` item with no `counter` search |
| `no-stopping-rule` | -1 | search line: `state.stopping` missing, invalid or committed after the first search |
| `stopping-not-met` | -1 | the recomputed stopping rule does not hold |
| `known-item-missed` | -1 | a `state.known_items` id is in no captured search |
| `screened-outside-search` | -1 | a screening row names an id that no captured search returned |
| `one-provider` | -1 | one provider alone resolves the formal id, and its header agrees |
| `falsifier-not-evaluable` | -1 | a measured protocol's falsifier has neither a comparator with a number nor a named test with its alpha |
| `fewer-than-two-rivals` | -1 | R5 or R6: fewer than two `rival:` lines |
| `no-replication` | -1 | a group of a cited experiment holds fewer than two rows |
| `no-power-plan` | -1 | a measured protocol lacks one of `alpha:`, `power:`, `mde:`, `n:` |
| `below-planned-n` | -1 | a `compare:` group holds fewer rows than `n:` |
| `no-interval` | ceiling | a `compare:` group has fewer than two rows |
| `interval-includes-zero` | ceiling | improvement claim: the interval's lower bound is 0 or less |
| `below-achieved-mde` | ceiling | improvement claim: the effect is below the achieved MDE |
| `no-multiplicity-correction` | -1 | more than two groups and no `correction:` |
| `fails-multiplicity` | ceiling | the declared correction does not reject the experiment |
| `no-sesoi` | ceiling | a no-difference claim whose protocol has no `sesoi:` |
| `tost-not-passed` | ceiling | a no-difference claim whose TOST fails |
| `untraced-number` | -1 | a number of an evidence claim that no cited row and log, and no `derived_from`, holds |
| `instrument-unvalidated` | ceiling | a cited row names an `unvalidated` instrument |
| `instrument-rejected` | ceiling | a cited row names a `rejected` instrument |
| `judged-row-incomplete` | -1 | a cited row with `judge` lacks `generator` or `order` |
| `uncalibrated-verifier` | ceiling | `verified_by` names an instrument that is not a validated verdict instrument |
| `no-question-class` and the class steps | -1 | see "The question class" above |

### Statistics on results rows

A measured protocol plans its test with `alpha:`, `power:`, `mde:` and `n:`. It may
add `compare: <T> vs <C> on <field>, lower|higher is better`, `sesoi:` and
`correction: bh|holm|bonferroni|e-bh`. Rows group by `arm`, else by `phase`, else
into one group `all` (`hooks/tezgah_research.py::experiment_record`).

One reader takes every protocol number (`hooks/tezgah_research.py::protocol_number`).
It reads `0.05`, `.05`, `5%` (as 0.05) and `1e-1`. `alpha:` and `power:` have to
fall in (0, 1), and `sesoi:` and `mde:` have to be above 0. `check` refuses any
other value, including one with no number:

- `experiment <h>: protocol.md <alpha|power>: <value> is not a number in (0, 1)`
- `experiment <h>: protocol.md <sesoi|mde>: <value> is not a number above 0`
- `protocol.md alpha: <value> leaves a quantile at 0 or 1`

A statistic that still fails to compute gives one refusal per experiment, never a
traceback: `experiment <h>: statistics could not be computed: <error>`
(`hooks/tezgah_research.py::_check_rules8`).

- A group whose rows all carry an `outcome` of 0 or 1 prints
  `stats <slug>: <h> <group> n=<n> k=<k> wilson=[<lo>, <hi>] cp=[<lo>, <hi>]`, the
  Wilson and Clopper-Pearson intervals at 1 - alpha. A JSON `true` or `false`
  outcome counts as 1 or 0.
- `compare:` gives the mean difference in the better direction. The two groups
  pair by `item` when they hold the same item set, else the test is Welch's
  (`hooks/tezgah_research_stats.py::mean_diff`). The achieved MDE is
  (z(1 - alpha/2) + z(power)) times the standard error
  (`hooks/tezgah_research_stats.py::achieved_mde`). `check` prints
  `effect <slug>: <h> <T> vs <C> on <field> effect=<e> ci=[<lo>, <hi>] mde=<m>`,
  or `ci=none mde=none` when a group has fewer than two rows.
- `check` corrects every experiment that declares a `correction:` together with
  the others of the same method (`hooks/tezgah_research.py::_multiplicity`). `e-bh`
  reads `e-value: <x>` from each `analysis.md`.
- A claim citing the experiment is an improvement claim, unless it carries
  `"effect": "no-difference"`. Then TOST has to place the 1 - 2 alpha interval
  inside (-sesoi, +sesoi) (`hooks/tezgah_research_stats.py::tost`).

### Hypotheses and falsifiers

On a measured line, a falsifier needs a comparator and a number, or a named test
with its alpha (`hooks/tezgah_research.py::falsifier_testable`). Claims citing an
experiment whose falsifier has neither take the step `falsifier-not-evaluable`.
The structured form
`falsifier: <field> <op> <number> [on <group>]` is the one `check` evaluates. Its
`<op>` is `<`, `<=`, `>`, `>=`, `=`, `≤`, `≥`, `at most`, `at least`, `above`,
`below`, `less than`, `more than`, `fewer than`, `greater than`, `exceed`,
`exceeds`, `under` or `over` (`hooks/tezgah_research.py::FALSIFIER_OPS`). It
fires when the mean of the field over the group's rows meets the comparison. A
falsifier with no `on <group>` over an experiment of several groups is not
evaluated, and its claims take `falsifier-not-evaluable`
(`hooks/tezgah_research.py::falsifier_unscoped`). A
`supported` claim citing an experiment whose falsifier fired fails with
`while its falsifier fired` (`hooks/tezgah_research.py::fired_problems`). A
prediction equal to its falsifier still fails with `say the same thing`.

Neither this refusal nor `does not recompute` (below) reaches a claim that another
row supersedes. The record is append-only, so that row is the correction, and
`claim` and `check` skip the superseded claim alike
(`hooks/tezgah_research.py::_superseded`).

`state.hypotheses[]` holds `{"id", "text", "status", "probability"}` entries. A
concluded line ends each one as `supported`, `refuted`, `weakened`, `revised`,
`untested` or `inconclusive`. `check` refuses an entry left open with
`has no terminal status`, and `conclude` refuses it first
(`hooks/tezgah_research.py::hypothesis_problems`).

### The execution trail

A number in an evidence claim's statement counts as traced when a cited row holds
that value and the row's `log` file contains the token. The claim's `derived_from`
can also name it (`hooks/tezgah_research.py::_untraced`). An untraced number costs
the step `untraced-number`, and `check` never refuses it.

`derived_from` maps each derived number, as written, to how it came about:
`{"<number>": {"op": "mean|sum|min|max|diff|ratio|count", "of": ["<h>/<run>:<field>", "<h>/#<row>:<field>"]}}`.
`diff` is the first minus the second, and `ratio` the first over the second.
`check` recomputes the value in decimal arithmetic and rounds it at the written
precision. Either half-up or half-even rounding may match, so mean(2, 3) accepts
both `2` and `3` (`hooks/tezgah_research.py::_rounds_to`). It refuses a mismatch:
`does not recompute` (`hooks/tezgah_research.py::derived_problems`).

The protocol's other lines bind the analysis
(`hooks/tezgah_research.py::_check_experiment8`):

- Each metric of the `metric:` list appears in `report.md`, or in a
  `not_reported: <metric>: <reason>` line. The list splits at the commas between
  names, never inside parentheses or between digit groups. So `10,000-piece` and
  `(median of 5 runs)` stay whole (`hooks/tezgah_research.py::METRIC_COMMA`). The
  locked metric is one name, and a comma in it never splits it
  (`hooks/tezgah_research.py::_registered`). A metric neither reported nor excused
  fails with `registered metric <m> is neither reported nor marked not_reported - <exit>`.
  Before the run the exit reads
  ``name it in to_human/report.md, or before the run mark it `not_reported: <metric>: <reason>` in protocol.md``.
  A filed run freezes `protocol.md`, so after it the exit reads
  `the run is filed, so protocol.md is frozen: name it in to_human/report.md`.
  A registered metric that matches the locked one counts as reported when the
  report names the locked metric. The match collapses whitespace in the report, so
  a name wrapped across lines still counts.
- A `metric:` list must hold the locked metric. Else:
  `metric other than the locked one`. A protocol metric matches the lock when
  either is the other, a word-boundary prefix of it either way, or a rewording.
  A rewording holds every word of the lock in the registered name, in any order,
  with the joining words (`of`, `the`, `per`, ...) ignored
  (`hooks/tezgah_research.py::_same_metric`). So `p95 latency`, `p95 latency of
  the read path` and `read-path p95 latency` all match one another.
- `evaluator: <path> [sha256:<hex>]` pins the scoring file to its bytes at the
  protocol's first commit. `check` looks the path up in the line, the repository
  and the checkout it runs in, in that order
  (`hooks/tezgah_research.py::evaluator_file`). A path none of them holds fails
  with `evaluator <path> is not a file in the line, the repository or the checkout`.
  `check` compares the evaluator with its last version before that commit
  (`hooks/tezgah_research.py::_check_evaluator`). Else: `evaluator file changed after lock`.
  A concluded line compares the evaluator as it stood at the conclusion. The
  order seal `conclude` writes holds the evaluator's sha256 per experiment
  (`hooks/tezgah_research.py::_seal_rows`). A seal older than that field reads
  the evaluator at the first committed `state.json` holding the seal
  (`hooks/tezgah_research.py::_sealed_evaluator`). A later project edit therefore
  does not refuse a concluded line under `--all-lines`.
- `select: min|max <field>` picks the group with the lowest or highest mean, and
  `analysis.md` names it as `selected: <group>`. `check` refuses a different pick
  with `select rule picks`. A missing `selected:` line warns
  `analysis states no selected group`.

### The instrument ledger

An instrument is whatever turns an item into a number: a measure or an LLM
judge. A results row names it in `instrument` (or `judge`). An instrument that
`instruments/INSTRUMENTS.jsonl` does not hold counts as `unvalidated`. The
commands (`hooks/tezgah_research_evidence.py::COMMANDS`):

- `tezgah-research instrument add <slug> <name> --kind measure|verdict --rung R1|R2|R3|R4 --construct "<text>"`
  declares it.
- `tezgah-research gold <slug> <instrument> --arm <a> --n N --seed S` draws the
  gold sample. It sorts the arm's items by `sha256("<S>:<a>:<item>")` and keeps
  the first N (`hooks/tezgah_research_evidence.py::seeded_draw`). The first draw
  per instrument and arm is the one every rule reads. A draw once the arm has
  labels exits 1 with `gold draw after labels`. A draw over results or verdict
  rows that are not committed exits 1 with
  `has results or verdict rows that are not committed`, names
  `tezgah-research commit` and writes nothing
  (`hooks/tezgah_research_evidence.py::cmd_gold`). `check` refuses a gold file that
  is not its seed's draw: `differs from the seeded draw`. It also refuses a GOLD
  row that disagrees with its file on instrument, arm, seed or n:
  `<file> differs from the seeded draw: its GOLD row names <i> arm <a> seed <s> n <n>, the file <i> arm <a> seed <s> n <n>`
  (`hooks/tezgah_research_evidence.py::gold_record`).
- `tezgah-research label <slug> <instrument> --arm <a> --human "<name>" --ack "<the user's words>"`
  reads `{"item", "truth"}` rows on stdin. An item outside the gold sample exits 1
  with `not in the gold sample`.
- `tezgah-research label <slug> <instrument> --arm <a> --provider openrouter --model <m>`
  asks the model once per gold item, at temperature 0. It needs
  `OPENROUTER_API_KEY`, else it exits 2.
- `tezgah-research switch <slug> <instrument> --to R1|R2|R3|R4|<method> --reason "<why>"`
  records a move to another rung or method.
  `switch <slug> <instrument> --narrow "<what the claims now say>" --reason "<why>"`
  records a narrowing of the claims instead.

A label's `output` is the results row's `outcome`, and an error is a truth that
differs from it. A row without both `truth` and `output` labels nothing
(`hooks/tezgah_research_evidence.py::_is_label`). `check` refuses a label whose
output is not the results row's outcome:
`label output differs from its results row: <i> arm <a> item <x> output <o>, results row <r|none>`
(`hooks/tezgah_research_evidence.py::label_problems`). A label that holds the
outcome of a row a later refile replaced is stale
(`hooks/tezgah_research_evidence.py::_stale`). `check` neither counts nor refuses
it, and its item reads unlabelled until a new label arrives. The first label per
item counts, and a later one warns. An arm
counts as labelled when every item of its first draw has a label. Its error bound is the
two-sided 95% Clopper-Pearson upper bound of errors over n
(`hooks/tezgah_research_evidence.py::instrument_report`). The status follows
(`hooks/tezgah_research_evidence.py::judge_status`):

| Kind | Rejected when | Validated when |
|---|---|---|
| `measure` | the labelled arms' bounds sum to the smallest `mde:` of the experiments using it, or more | the sum stays below it and every arm with rows is labelled |
| `verdict` | an arm's bound is above 0.10 | every arm's bound is 0.10 or less and every arm with rows is labelled |

Anything else is `unvalidated`, and so is a measure with no `mde:` to compare
against. A measure whose `mde:` is above 1 stays `unvalidated` too, because its
threshold reads a difference of proportions
(`hooks/tezgah_research_evidence.py::proportion_threshold`). Its status line ends
`(mde above 1: the threshold reads a difference of proportions)`. With an MDE of
0.10 and two arms, 72 items per arm with no error
validate (bound 0.0499). 71 do not. At 20 items and no error the bound is 0.1684.
`check` prints `instrument <slug>: <name> arm <a> n=<n> errors=<k> upper=<u>` per
labelled arm and `instrument <slug>: <name> <status> sum=|max=<x> threshold=<t>`.
An R3 instrument also prints a PPI++ mean per labelled arm:
`ppi <slug>: <name> arm <a> lambda=<l> estimate=<e> ci=[<lo>, <hi>]`
(`hooks/tezgah_research_stats.py::ppi_mean`). It combines the gold truths with the
arm's unlabelled outputs. The line prints `ci=none` when fewer than two gold items
or fewer than two other items exist.

`conclude` refuses a line with a `rejected` instrument and no `switch` row for it:
`has no switch or narrowing row` (`hooks/tezgah_research_evidence.py::conclude_problems`).
A concluded line with human labels owes `user-supplied: <k> of <n> labels` in its
report.

**Verifiers.** A claim's `verified_by: <instrument>` has to name a `verdict`
instrument whose status is `validated`. Else the claim takes
`uncalibrated-verifier`, a ceiling.

### `release-check` and `calibration`

`tezgah-research release-check [--fixtures <dir>]` measures whether the checks
catch what they claim to catch. It needs no research line and runs from any
directory (`hooks/tezgah_research_evidence.py::cmd_release_check`). Its default
set, `tests/fixtures/rules8-known-truth/`, holds 38 defect and 18 sound cases of
citations, quotes and instruments. The functions `check` uses score each case,
with the set's `capture-map.json` as the capture map. It prints
`misses: <k>/<n> upper=<u>` and `false alarms: <k>/<n> upper=<u>`. It exits 1 when
the misses' Clopper-Pearson upper bound passes 0.10 or the false alarms' passes
0.20. The CI workflow runs it on every pull request and push to `main`, and
each release reuses that green run. On that fixture set it printed
`misses: 0/38 upper=0.0925` and `false alarms: 0/18 upper=0.1853`.

`tezgah-research calibration` scores every line's hypotheses that carry a
`probability` and end `supported` or `refuted`. It prints
`brier: <x> over <n> resolved hypotheses` and exits 0
(`hooks/tezgah_research_evidence.py::cmd_calibration`).

### Review, overlap and the smaller rules

- `to_human/review.json` adds `producer_family`, `reviewer_family` and
  `question_class`. One family on both sides warns `same-family review`. A
  reviewer equal to the producer, ignoring case and spaces, fails with
  `is the producer`. When the line holds an evidence claim, a finding has to
  target a file under `experiments/*/raw/` or a code file. Else it warns
  `review quotes no raw log or code` (`hooks/tezgah_research.py::_check_review8`).
- `check` warns `overlaps refuted claim <line>/<claim>` for a refuted claim that
  `init` reported as an overlap. A row of `related.jsonl`,
  `{"line", "claim", "relation": "builds-on"|"dismissed", "reason"}`, answers it.
- The overclaim lint warns in both modes: `claim <id> overclaims: "<word>"`. It
  fires on a universal word (every, all, always, never, any) over fixture
  evidence. It also fires on a causal word (cause, leads to, due to, because of)
  over an observational or single-group experiment
  (`hooks/tezgah_research.py::_overclaim`).
- A variant whose `variants.jsonl` row entered the history after the first
  `comparison.jsonl` cell is post-hoc. A `decision.md` that chooses it and never
  says `post-hoc` or `post_hoc` fails with `without saying post-hoc`
  (`hooks/tezgah_research.py::_post_hoc`).
- The supersedes warning drops when a `report.md` line names both claim ids
  (`hooks/tezgah_research.py::_check_supersedes`). Otherwise it stays soft, so
  `--strict` refuses it.
- A `Patterns` bullet in `findings.md` on a rules-8 line runs over its indented
  continuation lines, so a source on a wrapped line counts
  (`hooks/tezgah_research.py::_check_patterns`). An older line reads each
  bullet's first line only, as before.

### What rules 8 cannot see

- A gold seed chosen offline after the session saw the outputs goes undetected.
  The first-draw rule only stops a redraw once a draw exists.
- `check` reads a number that the session printed into a captured run log as
  measured. The log's bytes are real to every rule.

## What `check` refuses, and what it only warns about

A **refusal** (exit 1) is a guarantee the checker can decide. A **warning** is a
guarantee it cannot: the artifact is not wrong, it is unverifiable. `--strict`
turns the warnings the listed rules write through `_soft` into a refusal, which is
what a release gate wants and what a session mid-flight must not have, so the
default stays `warn`. A warning written outside `_soft` stays one. The section
below names three groups of them.

Refused:

- a required file missing (`STATE_FILES`, `hooks/tezgah_research.py::STATE_FILES`), a
  `state.json` that does not parse, no question, or a `phase`/`direction` outside
  its enum (`_check_state`, `hooks/tezgah_research.py::_check_state`);
- `evaluation.metric`, `evaluation.baseline` or `evaluation.locked_at` empty
  once `phase != "bootstrap"` - a criterion chosen after seeing the results is not
  a criterion (`_check_evaluation`, `hooks/tezgah_research.py::_check_evaluation`) - or an
  `environment` that is not the object it is optional as, or a
  `capability_tolerance`/`counter_metric` that is present and names nothing - an
  empty string, a blank one, or a value of the wrong type. The two-gate pair is
  refused in that state only: an absent key is a line that locks one metric, which
  is the ordinary shape and every line in this tree, so nothing here fires on the
  absence (`_check_evaluation`, `hooks/tezgah_research.py::_check_evaluation`);
- a `sessions[]` entry that is not an object, one whose `date` is empty, or one
  whose `tag` is outside `PROVENANCE` (`hooks/tezgah_research.py::PROVENANCE`): an
  untagged inference reads as the user's word. The older `{date, events: [...]}`
  shape carries the tag on each event, and each of those is checked the same way;
- a `findings.md` that does not answer all four sections
  (`_check_findings`, `hooks/tezgah_research.py::_check_findings`);
- a claim that states nothing, carries no falsification criterion
  (`_check_claims`, `hooks/tezgah_research.py::_check_claims`) or cites no proof; a proof
  naming no artifact at all, whatever the kind; a `kind` outside `KINDS`; an
  `evidence` claim naming nothing the line produced, a `literature` claim citing
  no note under `literature/`, a `derivation` token the line does not hold
  (`_check_proof`, `hooks/tezgah_research.py::_check_proof`); a token the line never
  produced (`_resolves`, `hooks/tezgah_research.py::_resolves`); a `provenance` or
  `status` outside its enum;
- a claim whose `supersedes` is neither a claim id nor a list of them, or that
  names an id no claim in the line carries
  (`_check_supersedes`, `hooks/tezgah_research.py::_check_supersedes`): a relation to nothing is
  the same as none, and the write path refuses it too
  (`_supersedes`, `hooks/tezgah_research.py::_supersedes`);
- a prediction row that names no `commit` or a `commit` that is not a
  40-character sha, one whose `commit` is not an ancestor of HEAD, one whose
  `metric` or `value_before` carries no number to move, one with no `falsifier`,
  one whose `claim` names an id the line does not hold, or one whose `components`
  is not a non-empty list of keys the manifest defines - a key nothing defines
  cannot attribute the change to a component, which is what the field is for, and
  the write path refuses both of those the same way
  (`prediction_problems`, `hooks/tezgah_research.py::prediction_problems`); a row whose commit changed
  a **frozen** path is refused unless it carries a human `granted_by`, and the
  frozen set is one module-level tuple, `FROZEN_PATHS`
  (`hooks/tezgah_research.py::FROZEN_PATHS`), read only through `_frozen`
  (`hooks/tezgah_research.py::_frozen`) so the write path and the checker cannot drift
  apart: `hooks/tezgah_gate.py` and `hooks/tezgah_integrity.py` (the verifier and
  the ledger's write path), `hooks/tezgah_research.py` (this module - the
  machinery that decides the rule, which the loop it judges may not edit), any
  `tests/` path (the hidden checks), `benchmarks/`, and any line's
  `experiments/*/protocol.md` (the pre-registration);
- an `orx:<runId>` proof token with no `raw/<runId>.log` under the line or the
  repository;
- an experiment with no `protocol.md`, results with no `analysis.md`
  (`_check_experiments`, `hooks/tezgah_research.py::_check_experiments`), or a git history in
  which `protocol.md` entered after `results.jsonl`, entered in the same commit,
  or changed after the run;
- a `results.jsonl` line that does not parse or is not an object, a row whose
  `source` is present and blank, or a `fixture`-scoped row whose `fixture`
  description is present and empty or not a string - the row claims the field and
  names nothing (`_check_rows`, `hooks/tezgah_research.py::_check_rows`);
- a row or a claim whose `scope` is present and outside `SCOPES` (`real`,
  `fixture`, `derived`) - a label nothing shares is a label no reader can weigh -
  or a claim that declares `real` over rows that all record `fixture`: the field is
  what the producer saw, and a claim may not claim a wider one than its evidence
  (`_check_claim_scope`, `hooks/tezgah_research.py::_check_claim_scope`); the write path refuses the
  same two (`claim_problems`, `hooks/tezgah_research.py::claim_problems`);
- `literature/` holding notes and no `INDEX.jsonl` at all, an INDEX line that
  does not parse or is not an object, an INDEX row naming no note or naming a
  file `literature/` does not hold, a `class` outside `formal`/`grey`, or a note
  the index does not name (`_check_literature`, `hooks/tezgah_research.py::_check_literature`;
  `_read_index`, `hooks/tezgah_research.py::_read_index`);
- a `review.json` that does not parse, carries no `dimensions` or `findings`, a
  dimension missing or outside 1-5, a `severity` outside
  `critical`/`major`/`minor`/`suggestion`, a finding targeting no file or quoting
  nothing, or a finding whose `quote` does not occur verbatim in its `target`
  (`_check_review`, `hooks/tezgah_research.py::_check_review`).

On an exploratory line (rules 7), `check` also refuses each of these
(`_check_exploratory`, `hooks/tezgah_research.py::_check_exploratory`, called
from `_check_standards`):

- an arena that `arena_problems` faults, past `bootstrap`. The faults are no
  arena object, no problem, no budget, and an evaluator with no sha256 or no
  metric (`hooks/tezgah_research.py::arena_problems`).
- an arena that differs from the one the lock commit holds. The same goes for an
  `ideas.jsonl` or `results.jsonl` that entered the history before that commit
  (`hooks/tezgah_research.py::_check_arena_order`).
- an idea row that `idea_problems` faults
  (`hooks/tezgah_research.py::idea_problems`). That means a missing field, a
  `generator` that is not `{family, model}`, or an id that is not `I<n>` or
  repeats an earlier one. It also means an operator outside `OPERATORS`, a parent
  no earlier idea carries, or too few parents for a `mutation` or `crossover`. The
  last cases are a statement of more than two sentences and a date that is not
  `YYYY-MM-DD`. A trace to no in-scope item and a missing arena fail it too.
- a stage row that `stage_problems` faults
  (`hooks/tezgah_research.py::stage_problems`). The funnel above lists the
  moves and the evidence each stage asks for. Every stage row fails while the
  evaluator's hash differs from the locked one
  (`hooks/tezgah_research.py::evaluator_problem`).
- a stage row that skips its `PREREQUISITES` stage, and any row but `killed`
  after `duplicate` or after a `known` prior art.
- a `known` prior art with no `killed` row after it.
- a match row that `match_problems` faults
  (`hooks/tezgah_research.py::match_problems`). That means a side that names no
  idea, an idea matched against itself, or a `judge` that is not
  `{family, model}`. It also means an `order` outside `MATCH_ORDERS`, a `winner`
  outside `MATCH_WINNERS`, or no `rationale`.
- a campaign file line that does not parse or is not an object
  (`hooks/tezgah_research.py::_campaign_rows`).
- a committed campaign row that a later version changed or dropped.

Warned, and refused under `--strict` - each is the honest state of an artifact
this layer cannot decide on, not a defect:

- a file whose rows declare no `scope`: the field cannot be inferred afterwards -
  a probe run against a generated repository and a measurement of the running
  system read identically once the run is over - so this is reported once per file
  with the count, and `--strict` refuses it (`_check_rows`,
  `hooks/tezgah_research.py::_check_rows`). The same class as a row written before `source` did:
  the fix is the producer's to write, and every rule here only names it;
- a row that declares `scope: fixture` and does not say what was generated: the
  scope names the class and the field beside it names the input, so a row written
  before this one warns with the count and `--strict` refuses it - a class a reader
  cannot size is not an input they can weigh (`_check_rows`,
  `hooks/tezgah_research.py::_check_rows`);
- a claim resting on a fixture row that declares no scope of its own
  (`_check_claim_scope`, `hooks/tezgah_research.py::_check_claim_scope`), because a reader of the claim
  alone takes a generated input for the running system; declaring `fixture` is the
  whole fix;
- a claim that declares `real` over rows that mix one fixture row with real ones
  (`_check_claim_scope`, `hooks/tezgah_research.py::_check_claim_scope`), naming the experiment(s) the
  fixture rows are in: the all-fixture case is the refusal above, and under-declaring
  is the safe direction here because the declaration is a warning to the reader, so
  a mixed claim that says `real` hides the half that is not the running system;
- a number a claim asserts that the artifacts its proof names do not contain
  (`_check_claim_numbers`, `hooks/tezgah_research.py::_check_claim_numbers`): 80 of this repository's own 82
  numeric claims are fully contained under this reader, so a refusal would refuse the
  one or two that are not wrong - a proportion computed in the sentence, a count
  restated in words - and what the warning buys is the number and the artifact,
  named. Five readings are read through rather than warned about: a date
  (`2026-09-19`), lifted off the statement before it is tokenised because a
  measurement is a standalone number; a thousands separator, so a claim stating
  `20480` is contained by an artifact holding `20,480`; a comma list, which is the
  figures it holds and not decimal numbers, so `4,2,2,1,1,2` is six tokens and not
  `4,2`, `2,1`, `1,2`; a bare filename, which the reader resolves with the same token
  set the proof rule does instead of passing the claim against nothing; and a number
  past the per-file reading window, which is streamed for in chunks rather than
  called missing. A `path:line` citation reads through like a date: its line
  number names a place in a file, not a measurement. What it can never decide
  is a token found inside a longer
  number - a claim's `10` is contained by an artifact holding `10000` - so the
  warning is a consistency check and not a proof that the number was measured;
- a concluded line's `report.md` carrying a fixture-scoped claim and never saying
  `fixture` anywhere in it (`_check_report`, `hooks/tezgah_research.py::_check_report`);
- a prediction whose `commit` git cannot place against HEAD, or whose commit git
  cannot read at all (`commit_paths`, `hooks/tezgah_research.py::commit_paths`): the row may name
  a real change in a shallow clone or a repository git cannot read here, so the
  question is unverified rather than answered - the same class as a pair the
  order rule cannot order - and `--strict` is what refuses it. The write path
  records the row and prints the same warning, because a writer that refused what
  the checker only warns about would be the stricter of two judges that have to
  agree;
- a prediction row that carries no `components` at all
  (`prediction_problems`, `hooks/tezgah_research.py::prediction_problems`): every row in this
  repository predates the field, and which component an old change touched cannot
  be recovered from the row afterwards, so the class is the warn one and
  `--strict` refuses it. The asymmetry is the only one the field has and it is
  deliberate: `predict` refuses a row being written now that names no component
  (`new` on the same function), because the writer of a new row can name it and
  the reader of an old one cannot;
- a pair the order rule compares that no repository can commit, so the
  protocol order will never be decidable for it; the message names the
  `git -C .tezgah add -f <path>` or `tezgah-research commit` that fixes it (`_check_tracking`,
  `hooks/tezgah_research.py::_check_tracking`);
- a `protocol.md` that answers neither what it predicts nor what would falsify it
  - the marker is a prediction word and a falsifier word anywhere in the file,
  read as prose and not by shape, and a sentence that *disclaims* one ("this file
  is the brief, not a prediction") does not answer it; the warning names which of
  the two questions it could not find. Three of this repository's own protocols
  are briefs for a read-only agent and carry no prediction by design, which is why
  the class is the warn one (`_check_protocol`,
  `hooks/tezgah_research.py::_check_protocol`; `_protocol_answers`,
  `hooks/tezgah_research.py::_protocol_answers`);
- a concluded line's `to_human/report.md` that names no limit anywhere, or is not
  written at all - there is no report in which to state what the evidence does not
  show (`_check_report`, `hooks/tezgah_research.py::_check_report`; the marker is the
  phrase a limit is stated with - "does not show", "did not look at",
  "limitation", "non-goal", "open question", "unmeasured" - and a heading and a
  sentence count alike, `REPORT_LIMITS`, `hooks/tezgah_research.py::REPORT_LIMITS`);
- a `## Patterns` bullet in `findings.md` naming no source - `[Cnn]`, a
  `literature/...` path or an `orx:<id>` (`_check_patterns`,
  `hooks/tezgah_research.py::_check_patterns`);
- a claim with no `kind` at all, the pre-migration state `migrate` closes;
- a claim that supersedes another: the relation is reported naming both ids, so a
  reader who opens the older claim alone is told the line has replaced it
  (`_check_supersedes`, `hooks/tezgah_research.py::_check_supersedes`);
- an `evidence` claim whose experiment's `results.jsonl` is missing or holds no
  row;
- a `results.jsonl` row with no `source` key at all: the rows written before the
  rule look like this, and inventing a source for someone else's measurement is
  the fabrication the rule exists to catch;
- a `grey` source with no `quality` note, an INDEX row verified by fewer than two
  records, or an INDEX row recording no `id`, `source` or `inclusion`
  (`_index_fields`, `hooks/tezgah_research.py::_index_fields`);
- `review.json` missing on a line whose `phase` is `concluded` - a review is a
  judgement, so no migration can write one for the lines that concluded before
  the rule existed.

On an exploratory line, two more warnings take this class. One is an arena
fault at `bootstrap`. The other is a campaign file git cannot order against the
arena lock (`_check_arena_order`).

Three groups of warnings are **not** promoted by `--strict`. The rules-6
three (held-out set, repeats, noise band) stay warnings by ADR 019. The rules-7
four stay warnings for the same reason: a tournament is a prior and a count is a
disclosure. They are a pair that only a generator family of one of its ideas
judged, unless both generators' families judged it. They are a pair judged in one
order, and an idea with fewer than two judges (`_tournament_warnings`). The fourth
is a `report.md` that does not state how many ideas reached `piloted` and
`promoted` (`_check_tested`). The last is a `phase`
declared in `state.json` behind the phase the line's own artifacts show
(`_check_derived_phase`, `hooks/tezgah_research.py::_check_derived_phase`). The field is the author's
declared intent and `_check_report` and `_check_review` read it, so a derivation
simpler than that judgement must never fail a line the field says is fine. What
it does say is the "two authorities" defect this module names in its own source:
a field maintained by hand beside artifacts that are not, where a line whose
protocols, results, claims, findings, report and review are all written can still
report `inner` and no reader is told. `derived_phase`
(`hooks/tezgah_research.py::derived_phase`) walks the artifacts the line already holds, in
`PHASES` vocabulary, and takes the furthest rung that holds: the question alone is
`bootstrap`; something run is `inner` - an experiment with a protocol and at
least one committed `results.jsonl` row (`_measured`,
`hooks/tezgah_research.py::_measured`), or a claim recorded; the results folded back into
`findings.md` are `outer`, read as content under one of its four sections
(`_findings_written`, `hooks/tezgah_research.py::_findings_written`); and the two artifacts a
concluded line owes, `to_human/report.md` and `to_human/review.json`, are
`concluded`. What each rung *is* is not decided here - whether a protocol answers
its two questions, or a review carries six scored dimensions, stays
`_check_protocol`'s and `_check_review`'s business - so the derivation only says
how far the line got. A field *ahead* of its artifacts is the author's call and is
never reported: `open_lines` and `_open_reasons` read the field when a caller has
to decide whether a line is finished, and this rule does not second-guess it.

The same rule reads `direction` against the artifacts. Written findings mean the
outer loop has chosen, so `undecided` warns from `outer` on. A delivered line
shows `conclude`, so any other direction warns there. The choice between
`deepen`, `broaden` and `pivot` is a judgement no artifact holds, so the rule
leaves it alone.

## The write path and the checker stay in step

`claim_problems` (`hooks/tezgah_research.py::claim_problems`) applies exactly the rules
`check` applies to a row, so the writer can never refuse a claim the checker
would accept: a statement, a falsification criterion, a proof naming an artifact
with a `kind`, a `provenance` in `PROVENANCE`, a `status` in `STATUSES`, every
cited path resolving under the line or the repository, and a `supersedes` id the
line holds - the ids already in `claims.jsonl`, read by `_claim_ids`
(`hooks/tezgah_research.py::_claim_ids`). The append itself takes an exclusive `flock`
with a 1 s bound (`_locked`, `hooks/tezgah_research.py::_locked`), because two
sessions recording a claim at once is normal and a torn line is not. **The lock is
taken before the judgement, and the ids it judges are read from the descriptor the
lock is held on** (`_claim_ids`'s `handle` argument, `hooks/tezgah_research.py::_claim_ids`):
judging a relation and then locking lets another session land the very id the check
had just found absent, so the writer refuses a claim the committed file accepts and
its proof describes an instant its append does not commit to. Three rules
deliberately stricter at write time, and the code says so: a new claim must
carry a `kind` (`check` only warns for a pre-rule row, which `migrate` closes),
and its proof must name an artifact (`check` applies that rule only to a row that
already carries a kind). Everything else is the checker's own - the evidence-row
rule included: an empty `results.jsonl` warns on both paths, and `--strict`
refuses it on both. A refusal never leaves an empty `claims.jsonl` behind: the line
decides when it has claims, and an empty file reads as "no claims recorded yet"
where an absent one reads as a missed requirement.

`prediction_problems` (`hooks/tezgah_research.py::prediction_problems`) is the same arrangement for the
prediction rows and the single place the two readings of that rule meet: `check`
calls it for each row of `predictions.jsonl` (`_check_predictions`,
`hooks/tezgah_research.py::_check_predictions`) and `predict` calls it inside the append lock, so a
row's verdict is one function's and the writer cannot be stricter than the
checker. The two asymmetries are deliberate and named: `check_line`'s `git=False`,
which is what the session note pays for, skips the commit half, so the shape rules
are what the cheap path reads; and `new=True`, which only the write path passes,
is what refuses a row being written now that names no `components` - a row that is
already in the file is the warning class above. The append takes the same
exclusive `flock` with the 1 s bound and the same committed-size repair the claim
path uses, and `_locked` now takes the name of the file it refuses
(`hooks/tezgah_research.py::_locked`).

The row writer is the third site of the same order (`_append_row`,
`hooks/tezgah_research.py::_append_row`): it takes the lock, then judges the row with
`row_problems` (`hooks/tezgah_research.py::row_problems`) - exactly the hard refusals `_check_rows`
applies to a row's own shape (an object, a non-empty `source`, a `scope` in
`SCOPES`, a non-empty `fixture` description), and deliberately not the warn class a
pre-rule row is in, because a writer stricter than the checker refuses what the
checker only reports.

**An append starts at the committed boundary.** `committed_size`
(`hooks/tezgah_integrity.py::committed_size`) is the offset just past the last `\n` in a file,
and `truncate_to_committed` (`hooks/tezgah_integrity.py::truncate_to_committed`) cuts a descriptor
back to it; all three writers truncate first and write after
(`append_claim`, `hooks/tezgah_research.py::append_claim`; `_append_row`; `append_prediction`,
`hooks/tezgah_research.py::append_prediction`). A fragment a killed writer left behind - no newline
ever terminated it - is then neither read as a record nor appended beside as one.
Every JSONL reader here stops at the same boundary (`_committed_text`,
`hooks/tezgah_research.py::_committed_text`; `_rows`, `hooks/tezgah_research.py::_rows`), so a reader and a
writer agree about where the records end; a record that *did* terminate and does
not parse is still refused, because the boundary hides the tail and not the file.
Before this, the claim writer terminated the fragment instead and the research
reader read to the last byte, so one kill during one append refused a line for
good while the ledger reader skipped the identical damage.

`kind` is what the proof has to be, and it decides what the proof must name -
`KINDS`, `hooks/tezgah_research.py::KINDS`: an `evidence` claim has to name an
artifact of the line itself (a repository file is not the run it rests on), and
the experiment it names has to carry rows; a `literature` claim has to cite a
note under `literature/`; a `code` claim resolves anywhere in the repository; a
`derivation` claim resolves inside the line. `migrate` derives the kind per claim
from the proof's own tokens, with the same literature test the rule applies
(`derive_kind`, `hooks/tezgah_research.py::derive_kind`), and reports what it could not
derive rather than inventing a value.

## The per-component report

A prediction row names the components its change touches, and
`tezgah-research components` prints what that buys: per component, the rows that
name it and their state. The manifest it groups by is
`hooks/tezgah_components.py` - the one definition of what a component is, whose
`keys()` the rules read and whose `COMPONENTS` the report reads for the labels -
and it is imported inside the call that needs it (`_components`,
`hooks/tezgah_research.py::_components`), so the path a session pays for at import time never
loads it.

The state of a row is read, never guessed (`_prediction_state`,
`hooks/tezgah_research.py::_prediction_state`): `falsified` when the `claim` the row names is
`refuted` in the line's own `claims.jsonl`, because the line's own rows are the
only record of a verdict; `unmeasured` when `value_after` is empty, which is the
round that has not run; `held` when it is filled, which is the number that came
back. A row whose `claim` the line does not hold decides nothing - the filled
`value_after` is not a verdict - so it stays `unmeasured` and the report prints
why, beside the row. `PREDICTION_STATES` (`hooks/tezgah_research.py::PREDICTION_STATES`) is
that vocabulary, and the headers count it.

It is a **report, not a gate**: it exits 0 whatever the rows look like, because
the refusals belong to `check` and a second judge with a different verdict is the
disagreement this module exists to avoid. What it prints first - the number of
components and of rows it read (`components_text`,
`hooks/tezgah_research.py::components_text`) - is what tells an empty manifest from a line that has
predicted nothing, and a key the manifest does not define is reported as a bucket
of its own rather than dropped, so a hand-written row is visible.

Predictions and this report are **frozen** (ADR 009). They keep working as
documented and take no new rule, field or command. Nobody measured their use,
so the layer stays at this size. A measured use is what would reopen it.

## `migrate`: what the artifacts already hold

Three derivations and nothing else (`migrate`,
`hooks/tezgah_research.py::migrate`): each claim's `kind` from the files its proof
names, each results row's `source` from the fields the row carries, and the
`literature/INDEX.jsonl` rows from the notes.

A row written before the `source` rule says where it came from in a field of its
own, and `_migrate_rows` (`hooks/tezgah_research.py::_migrate_rows`) reads exactly those:
`log` or `raw` is the receipt itself and is taken as written, `run` or `id` is
the run the row came out of and is prefixed with the field it came from, so a
reader can tell a run id from a row id (`ROW_SOURCE_FIELDS`,
`hooks/tezgah_research.py::ROW_SOURCE_FIELDS`; `_row_source`,
`hooks/tezgah_research.py::_row_source`). A row that carries none of the four is reported
and left alone: a source invented for someone else's measurement is the
fabrication the rule exists to catch. Both JSONL files are rewritten under the
same exclusive lock `claim` appends under, and the run is idempotent.

`scope` is the field it refuses to derive, and the refusal is the point: only the
session that ran the experiment knows whether the input was the running system or
something it generated, and a migration that read it off a path would be the same
inference E1 measured and found unusable (438 of 520 rows unknown). A row it cannot
supply stays unscoped, and `check` names it by count.

## The session sees the layer two ways

The rule, conditionally: the prompt classifier arms `research` on a research
question - the hints are the words a reader would use, not the tool's name
(`PROMPT_HINTS`, `hooks/tezgah_context.py::PROMPT_HINTS`) - and the armed paragraph is
`RESEARCH` (`hooks/tezgah_policy.py::RESEARCH`), which names `{RESEARCH_BIN}` (the
installed `bin/tezgah-research`) and the `orx` manual step.

The note, when orx is absent or a line is broken: a session is told that `orx` is
not installed and to fall back to a host subagent rather than improvise the
protocol (`context_for`, `hooks/tezgah_context.py::context_for`), and at session start and
after a compaction a line with structural problems is named with its first error
and the advice to run `check` before reporting a result (the note
`research_broken` in `context_for`, `hooks/tezgah_context.py::context_for`). A
line under `done/` reaches the note only through its seal hashes.

The mark: `research` in the status line. It is armed when `research-off` is
absent and the research tooling is present (`health_segments`,
`hooks/tezgah_context.py::health_segments`) and turns used when a shell command really ran
the layer - `orx` or `tezgah-research`
in a command position, classified by the shared tokenizer
(`shell_kind`, `hooks/tezgah_context.py::shell_kind`), so a command that merely mentions
either name marks nothing. That is the same reader every host's status segment
uses ([status line](status-line.md)).

## The switch

`research-off` is the kill switch: with it armed the `RESEARCH` paragraph is
dropped, the session note is not built, and the mark reads `off` rather than
armed. It removes the rule, not just the mark - the diff is in `core_split`,
`hooks/tezgah_context.py::core_split` ([kill switch](glossary.md#kill-switch)).

## Source of truth

- `hooks/tezgah_research.py` - the workspace, the enums, `check_line`, the claim
  rules shared with the writer, the prediction rules shared the same way and the
  frozen set they read (`FROZEN_PATHS`), the protocol order and its tracked pair,
  the protocol's two questions, the concluded report's limits, the `supersedes`
  relation, `component_report` with the state it reads, `migrate`, `source_run`,
  `init` and `summary`, and the rules-7 campaign: the arena lock, the three row
  judges and their writers, `board`, `dedup` and `yield_report`.
- `hooks/tezgah_components.py` - the manifest: the one definition of an editable
  component, the keys a prediction row names and the rules a row's outcome is
  attributed to.
- `bin/tezgah-research` - the CLI, its subcommands and its exit codes.
- `hooks/tezgah_product.py` - the product-flow steps and the `next` status reader.
- `hooks/tezgah_rank.py` - `scores`, the BM25 reading `dedup` falls back to when
  the static embedding is off.
- `hooks/tezgah_policy.py` - the `RESEARCH` paragraph a session is armed with.
- `hooks/tezgah_context.py` - the prompt hint, the missing-orx note, the broken
  line note and the `research` mark.
- `skills/research/SKILL.md` - the two-loop rhythm, the claim review and the
  provenance tags a session records.
- `tests/test_research.py` - the CLI's refusals, the checker's rules and their
  edges, the prediction cases that pin the checker and the write path to the same
  verdict, and the per-component report.
- `tests/test_components.py` - the manifest's own shapes, its label pin and the
  mapping table it carries.
