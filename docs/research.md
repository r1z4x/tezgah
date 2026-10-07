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
sections below. A bump never weakens an older set.

A `rules` above `RULES` means a later tezgah wrote the line. `check` then reports
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

## One line, one directory

| Path | Holds |
|---|---|
| `state.json` | the question, the phase (`bootstrap`/`inner`/`outer`/`concluded`), the direction, the locked evaluation and its optional second gate (`capability_tolerance`, `counter_metric`), the session events (`PHASES`, `hooks/tezgah_research.py::PHASES`), `rules` (the rule set `init` opened it under, `RULES`), `deliverable` (`kind`, `path`, `ask`, `min_variants`), `supersedes` for a new version of an older line, and `closed` once `close` records a deliberate limit. The phase is the author's declaration; `derived_phase` (`hooks/tezgah_research.py::derived_phase`) reads the *other* authority beside it from the line's own artifacts, and the checker names the two disagreeing |
| `log.md` | the decision log, newest last: one line per decision, experiment, dead end or pivot, with the evidence that drove it |
| `findings.md` | the four sections every line answers, named by `FINDINGS_SECTIONS` (`hooks/tezgah_research.py::FINDINGS_SECTIONS`) |
| `claims.jsonl` | one JSON object per row: `statement`, `falsification`, `proof`, `provenance`, `status`, `kind`, `scope` (what the claim's numbers were measured on, which may not be wider than the rows it rests on), and `supersedes` when the row replaces an earlier claim |
| `predictions.jsonl` | one JSON object per row: `commit` (a 40-character sha the row is bound to), `claim` (an id the line holds, or empty when the prediction stands alone), `metric`, `value_before`, `value_after`, `falsifier`, `components` (the keys of the components the change touches, read from `hooks/tezgah_components.py`), and `granted_by` when a human granted what the frozen paths below forbid |
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
and `check` reads an absent one as no rows rather than as a missing file. A slug
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
`state.json` `closed` and `log.md` and seals it ("the order seal", below).
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
| `tezgah-research init <slug> [--question "..."] [--allow-open "<reason>"] [--supersedes <slug>]` | scaffolds the line and makes sure `.tezgah/` is ignored by the project and has its own git repository (`tezgah_paths.ensure_workspace`). It refuses while another line is still open (see below), names each open line and its reasons one per line, and `--allow-open "<reason>"` is the way past unless an open line has `check` errors: the reason lands in the new line's `log.md` as its first entry, and an empty reason is misuse. A `--question` another line already asks is refused unless `--supersedes <that line>` says the new line is its next version (`serial_twins`). Its next-step message names the commit loop: `tezgah-research commit` for the protocol, then again for the results in a later commit (`cmd_init`, `bin/tezgah-research`) | 0, 1 refused, 2 misuse |
| `tezgah-research commit <slug> "<message>"` | stages and commits only that line's path in `.tezgah`'s private repository - the commit the order rule reads (`cmd_commit`, `bin/tezgah-research`) | 0, 1 not a work tree or git failed, 2 misuse |
| `tezgah-research check [<slug>] [--json] [--strict] [--orx] [--all-lines] [-- <slug>]` | the discipline checks below. With no slug it checks the open lines in full and a line under `done/` by its order seal alone (`done_seal`, `hooks/tezgah_research.py::done_seal`), naming it only when the seal fails or its `state.json` or seal cannot be read, then prints `research: <n> done line(s): <s> checked by their seal, <u> unsealed (not checked); ...`; `--all-lines` checks every line in full, and `check <slug>` always checks that line in full (ADR 015). `--json` prints the report (no-slug default: the open lines and any done line whose seal read fails), `--strict` turns the unverifiable class into a refusal, `--orx` adds the registry check that asks `orx project view` for this repository (`check_orx`, `hooks/tezgah_research.py::check_orx`); a slug after `--` is never read as a flag, which is how the MCP tool `tezgah_research_check` passes its validated `slug` | 0 clean, 1 a line failed a rule or names no line |
| `tezgah-research status` | one line per line: an open line `ok` or a problem count, a line under `done/` read by its seal like the no-slug `check` - `done, seal ok`, `done, <n> seal problem(s)` or `done, unsealed (not checked)` (`summary`, `hooks/tezgah_research.py::summary`, plan 058 part 4) | 0 |
| `tezgah-research --all` | every checkout of this repository (the main checkout and each linked `git worktree`, `tezgah_paths.worktrees`), one header per checkout, then `  <slug>: <phase>` per line with the reasons it is still open; a checkout with none says `no research line`. Read-only: each checkout keeps its own `.tezgah`, locks and private repository, and nothing here writes to any of them (`across`, `hooks/tezgah_research.py::across`) | 0, 2 misuse |
| `tezgah-research claim <slug>` | reads one claim from stdin and either appends it under an exclusive lock or refuses it, printing one reason per problem | 0, 1 refused, 2 misuse |
| `tezgah-research predict <slug>` | reads one prediction row from stdin and either appends it under the same lock or refuses it with one reason per problem; a row whose `commit` git cannot place is appended with the warning printed, which is the fail-open `check` uses, and a row written now has to name at least one component the manifest defines (`append_prediction`, `hooks/tezgah_research.py::append_prediction`) | 0, 1 refused, 2 misuse |
| `tezgah-research components [--json]` | the per-component report: one bucket per component the manifest defines, in the manifest's own order, then any key a row names that the manifest does not, each holding the prediction rows that name it and each row's state, and last the rows that name no component; it prints the number of components and rows it read (`component_report`, `hooks/tezgah_research.py::component_report`) | 0, 2 misuse |
| `tezgah-research migrate <slug> [--dry-run]` | derives the fields a line written before these rules cannot carry, prints what it derived and what it could not, and is idempotent (`migrate`, `hooks/tezgah_research.py::migrate`) | 0, 2 misuse |
| `tezgah-research source <slug> <hypothesis> --run <orxRunId> [--command "..."] [--scope real\|fixture\|derived] [--fixture "<what was generated>"]` | keeps the receipt: runs `orx logs <runId>`, writes `raw/<runId>.log`, appends the results row `{"source": "orx:<runId>", ...}` and the scope and fixture description the filer states (`source_run`, `hooks/tezgah_research.py::source_run`). A `--scope fixture` filed without `--fixture` still writes the row and prints the field it still owes, so the tool is never the thing that makes its own checker warn silently; a given `--fixture` that is empty is misuse | 0, 1 nothing filed, 2 without orx |
| `tezgah-research compare <slug> <decision>` | reads one variants x criteria cell from stdin and appends it to `decisions/<decision>/comparison.jsonl` under the lock, or refuses it by the rule `check` applies (`append_comparison` and `comparison_problems`, `hooks/tezgah_research.py`); it notes when `criteria.json` is not committed yet | 0, 1 refused, 2 misuse |
| `tezgah-research close <slug> --limit "<reason>"` | concludes the line as a deliberate limit, writing the reasons it was still open into `state.json` `closed` and `log.md`, and seals it (`close_line`) | 0, 1 unreadable state, 2 misuse |
| `tezgah-research seal <slug> [--history-lost] --ack "<owner decision>"` | seals a line under `done/` that was concluded before seals existed: plainly, as `conclude` would, when every experiment's order still checks; with `--history-lost`, with that verdict for every experiment whose order the lost history left undecidable. Refuses a line with a real order violation, a plain seal on any order finding, and a `history-lost` seal with nothing lost (`retro_seal`, `hooks/tezgah_research.py::retro_seal`) | 0, 1 refused, 2 misuse |
| `tezgah-research import <checkout> [<slug>] [--allow-open "<reason>"]` | brings a line - or every line this checkout lacks - from another checkout's `.tezgah` repository with its history; an open line arrives beside open ones only with `--allow-open` (`import_line`, `hooks/tezgah_research.py::import_line`) | 0, 1 refused, 2 misuse |

Exit code 2 is always misuse, so a caller can tell it from a line that fails the
checks (`misuse`, `bin/tezgah-research::misuse`). `check` asks nothing at all - no
network, no model - so its answer is reproducible on a machine with no
credential; only `--orx` asks the one question that leaves the machine.

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

Each checkout keeps its own `.tezgah` repository, and that repository has no
remote. One directory on one disk holds the only copy of a line's order proof.
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

What the pair cannot catch: **a tolerance its own author sets wide enough**. The
band is a sentence, not a measurement, and `check` can see that it is written and
readable - never that 0.02 is tight. A line that writes "capability metric within
5.0 of the baseline" has adopted the form of the two-gate rule and none of its
force, and the review is the only place that is decided.

## What `check` refuses, and what it only warns about

A **refusal** (exit 1) is a guarantee the checker can decide. A **warning** is a
guarantee it cannot: the artifact is not wrong, it is unverifiable. `--strict`
turns that whole class into a refusal, which is what a release gate wants and
what a session mid-flight must not have, so the default stays `warn`.

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

One warn is **not** promoted by `--strict`, and it is the only one: a `phase`
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
  `init` and `summary`.
- `hooks/tezgah_components.py` - the manifest: the one definition of an editable
  component, the keys a prediction row names and the rules a row's outcome is
  attributed to.
- `bin/tezgah-research` - the CLI, its subcommands and its exit codes.
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
