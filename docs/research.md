# Research: the line in the repository, the CLI that checks it, the mark it lights

The research layer is the repository's own record of an open-ended
investigation: one directory per line under `<repo>/.tezgah/research/<slug>/`,
the CLI that scaffolds and refuses it, and the conditional rule that routes a
research task to OpenResearch instead of ad-hoc scripting. Read this page before
you start a line, before you change what `check` refuses, and when a session
reported a result you have to re-verify. The workspace and the checks live in
`hooks/tezgah_research.py`; the session-facing rule is `RESEARCH`
(`hooks/tezgah_policy.py:386-452`) and the tool is `bin/tezgah-research`.

The layer exists because a claim is only auditable if the repository holds the
prediction it was tested against. `protocol.md` is committed **before** the run
and `results.jsonl` after it, and `check` asks git whether that order holds - a
protocol written once the numbers are in is not a prediction
(`_check_protocol_order`, `tezgah_research.py:1592`). Three things the same
file answers that nothing read until now are read too: what the protocol
predicts and what would falsify it (`_check_protocol`,
`tezgah_research.py:1423`), what a concluded line's report does *not*
show (`_check_report`, `tezgah_research.py:1812`), and which claim a later
claim replaced (`_check_supersedes`, `tezgah_research.py:1059`).
`predictions.jsonl` is the other half of the same idea and the one a refinement
loop needs: one row per proposed harness-text change, bound to the `commit` the
change landed in rather than to the session that proposed it, so the round after
it can falsify the prediction instead of remembering it.

## One line, one directory

| Path | Holds |
|---|---|
| `state.json` | the question, the phase (`bootstrap`/`inner`/`outer`/`concluded`), the direction, the locked evaluation and its optional second gate (`capability_tolerance`, `counter_metric`), the session events (`PHASES`, `hooks/tezgah_research.py:103`). The phase is the author's declaration; `derived_phase` (`tezgah_research.py:1925`) reads the *other* authority beside it from the line's own artifacts, and the checker names the two disagreeing |
| `log.md` | the decision log, newest last: one line per decision, experiment, dead end or pivot, with the evidence that drove it |
| `findings.md` | the four sections every line answers, named by `FINDINGS_SECTIONS` (`hooks/tezgah_research.py:113`) |
| `claims.jsonl` | one JSON object per row: `statement`, `falsification`, `proof`, `provenance`, `status`, `kind`, `scope` (what the claim's numbers were measured on, which may not be wider than the rows it rests on), and `supersedes` when the row replaces an earlier claim |
| `predictions.jsonl` | one JSON object per row: `commit` (a 40-character sha the row is bound to), `claim` (an id the line holds, or empty when the prediction stands alone), `metric`, `value_before`, `value_after`, `falsifier`, `components` (the keys of the components the change touches, read from `hooks/tezgah_components.py`), and `granted_by` when a human granted what the frozen paths below forbid |
| `experiments/<hypothesis>/protocol.md` | what the change is, what it predicts, what result would falsify it, why - committed before the run |
| `experiments/<hypothesis>/results.jsonl` | the rows the run produced, one JSON object per non-blank line, each carrying a non-empty `source` and, once declared, a `scope` of `real`, `fixture` or `derived`, and - when that scope is `fixture` - a `fixture` description of what was generated |
| `experiments/<hypothesis>/analysis.md` | what the rows mean, and which claim they move |
| `experiments/<hypothesis>/raw/<runId>.log` | the OpenResearch receipt `source` writes for one run |
| `literature/*.md` | one note per source |
| `literature/INDEX.jsonl` | the index that says which notes exist and which were used |
| `to_human/report.md` | the reader's copy: what was established, and what the evidence does not show |
| `to_human/review.json` | the six-dimension review, once the line concludes |

`init` writes the first four plus the three directories and never overwrites a
file that exists (`init`, `tezgah_research.py:2609`); `predictions.jsonl` is not
one of them, because a file that exists without a row is a line that looks like
it predicted something - it appears with the first `predict` the line records,
and `check` reads an absent one as no rows rather than as a missing file. A slug
is lowercase letters, digits and dashes (`valid_slug`,
`tezgah_research.py:266`), because it is the directory name `check`, `status` and
`claim` look for.

## One open line at a time

A line is **open** until its work is either applied or deliberately not, and the
line is closed. Concretely, `open_lines` (`hooks/tezgah_research.py`) calls a line
open unless all of these hold: `phase` is `concluded`; no claim is still
`hypothesis` or `testing` *among the rows nothing supersedes*; every experiment
that has a `protocol.md` also has results and an analysis; `to_human/report.md`
and `to_human/review.json` exist; and every review finding carries a `status`.
Those are exactly the reasons `init` prints, one line per open line.

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
decision on the record instead of a silent second line. The prompt-time note
reads a line's `state.json`, its experiment directory and its review, never
`claims.jsonl`, so a line open *only* because of a live claim is named by `init`
and not by the note; that split is the note's cost budget and is stated in the
rule's own comment.

## The CLI

`bin/tezgah-research` is the only writer and the only reader of the workspace;
the check a session runs from the shell is the same function the session note
calls (`check_line`, `tezgah_research.py:1855`).

| Command | What it does | Exit |
|---|---|---|
| `tezgah-research init <slug> [--question "..."] [--tracked] [--allow-open "<reason>"]` | scaffolds the line, then prints a TRACKING block when git ignores its path; `--tracked` appends the lines that re-include it - one negation, or the chain when an ancestor directory is excluded - to the file carrying the ignore, never rewriting another line, never staging, and not at all when that file is outside the repository. It refuses while another line is still open (see below), names each open line and its reasons one per line, and `--allow-open "<reason>"` is the way past: the reason lands in the new line's `log.md` as its first entry, and an empty reason is misuse. Its next-step message names the commit loop: the protocol committed normally, the results added by explicit path (`report_tracking`, `bin/tezgah-research:127`; `cmd_init`, `bin/tezgah-research:89`) | 0, 1 refused, 2 misuse |
| `tezgah-research check [<slug>] [--json] [--strict] [--orx]` | the discipline checks below; `--json` prints the report, `--strict` turns the unverifiable class into a refusal, `--orx` adds the registry check that asks `orx project view` for this repository (`check_orx`, `tezgah_research.py:2115`) | 0 clean, 1 a line failed a rule or names no line |
| `tezgah-research status` | one line per line, `ok` or a problem count (`summary`, `tezgah_research.py:2091`) | 0 |
| `tezgah-research claim <slug>` | reads one claim from stdin and either appends it under an exclusive lock or refuses it, printing one reason per problem | 0, 1 refused, 2 misuse |
| `tezgah-research predict <slug>` | reads one prediction row from stdin and either appends it under the same lock or refuses it with one reason per problem; a row whose `commit` git cannot place is appended with the warning printed, which is the fail-open `check` uses, and a row written now has to name at least one component the manifest defines (`append_prediction`, `tezgah_research.py:2844`) | 0, 1 refused, 2 misuse |
| `tezgah-research components [--json]` | the per-component report: one bucket per component the manifest defines, in the manifest's own order, then any key a row names that the manifest does not, each holding the prediction rows that name it and each row's state, and last the rows that name no component; it prints the number of components and rows it read (`component_report`, `tezgah_research.py:3005`) | 0, 2 misuse |
| `tezgah-research migrate <slug> [--dry-run]` | derives the fields a line written before these rules cannot carry, prints what it derived and what it could not, and is idempotent (`migrate`, `tezgah_research.py:2183`) | 0, 2 misuse |
| `tezgah-research source <slug> <hypothesis> --run <orxRunId> [--command "..."] [--scope real\|fixture\|derived] [--fixture "<what was generated>"]` | keeps the receipt: runs `orx logs <runId>`, writes `raw/<runId>.log`, appends the results row `{"source": "orx:<runId>", ...}` and the scope and fixture description the filer states (`source_run`, `tezgah_research.py:2465`). A `--scope fixture` filed without `--fixture` still writes the row and prints the field it still owes, so the tool is never the thing that makes its own checker warn silently; a given `--fixture` that is empty is misuse | 0, 1 nothing filed, 2 without orx |

Exit code 2 is always misuse, so a caller can tell it from a line that fails the
checks (`misuse`, `bin/tezgah-research:83`). `check` asks nothing at all - no
network, no model - so its answer is reproducible on a machine with no
credential; only `--orx` asks the one question that leaves the machine.

## The pair the order rule compares

The order rule is decided on the commit graph, so it needs both files committable
and it needs them as two commits. Whether they are is a question about the two
files, not about the line's directory: an ignore rule can cover the directory
while the pair is tracked, and a directory that is tracked says nothing about the
results inside it. `_check_tracking`
(`tezgah_research.py:1453`) therefore probes each experiment's
`protocol.md` and `results.jsonl` with `_ignored`
(`tezgah_research.py:305`) - the plain question *can `git add` stage
this?*, which git's `check-ignore` answers as no for a path the index already
holds - and reports the pair that is ignored.

The loop that keeps the order decidable, stated once here because the failure is
silent: **commit the protocol normally** (that commit is the prediction), **then
add the results by explicit path**:

```sh
git add .tezgah/research/<slug>/experiments/<h>/protocol.md && git commit ...
# run it
git add -f .tezgah/research/<slug>/experiments/<h>/results.jsonl && git commit ...
```

A plain `git add <results.jsonl>` stages nothing while the path is ignored, and
that silent no-op looks exactly like a commit - which is why the warning carries
the `git add -f <path>` that fixes it rather than the pattern alone.

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
(`_check_evaluation`, `tezgah_research.py:459`, and the two paragraphs the skill
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

- a required file missing (`STATE_FILES`, `hooks/tezgah_research.py:114`), a
  `state.json` that does not parse, no question, or a `phase`/`direction` outside
  its enum (`_check_state`, `tezgah_research.py:435`);
- `evaluation.metric`, `evaluation.baseline` or `evaluation.locked_at` empty
  once `phase != "bootstrap"` - a criterion chosen after seeing the results is not
  a criterion (`_check_evaluation`, `tezgah_research.py:459`) - or an
  `environment` that is not the object it is optional as, or a
  `capability_tolerance`/`counter_metric` that is present and names nothing - an
  empty string, a blank one, or a value of the wrong type. The two-gate pair is
  refused in that state only: an absent key is a line that locks one metric, which
  is the ordinary shape and every line in this tree, so nothing here fires on the
  absence (`_check_evaluation`, `tezgah_research.py:459`);
- a `sessions[]` entry that is not an object, one whose `date` is empty, or one
  whose `tag` is outside `PROVENANCE` (`hooks/tezgah_research.py:105`): an
  untagged inference reads as the user's word. The older `{date, events: [...]}`
  shape carries the tag on each event, and each of those is checked the same way;
- a `findings.md` that does not answer all four sections
  (`_check_findings`, `tezgah_research.py:600`);
- a claim that states nothing, carries no falsification criterion
  (`_check_claims`, `tezgah_research.py:1003`) or cites no proof; a proof
  naming no artifact at all, whatever the kind; a `kind` outside `KINDS`; an
  `evidence` claim naming nothing the line produced, a `literature` claim citing
  no note under `literature/`, a `derivation` token the line does not hold
  (`_check_proof`, `tezgah_research.py:1138`); a token the line never
  produced (`_resolves`, `tezgah_research.py:705`); a `provenance` or
  `status` outside its enum;
- a claim whose `supersedes` is neither a claim id nor a list of them, or that
  names an id no claim in the line carries
  (`_check_supersedes`, `tezgah_research.py:1059`): a relation to nothing is
  the same as none, and the write path refuses it too
  (`_supersedes`, `tezgah_research.py:1086`);
- a prediction row that names no `commit` or a `commit` that is not a
  40-character sha, one whose `commit` is not an ancestor of HEAD, one whose
  `metric` or `value_before` carries no number to move, one with no `falsifier`,
  one whose `claim` names an id the line does not hold, or one whose `components`
  is not a non-empty list of keys the manifest defines - a key nothing defines
  cannot attribute the change to a component, which is what the field is for, and
  the write path refuses both of those the same way
  (`prediction_problems`, `tezgah_research.py:2722`); a row whose commit changed
  a **frozen** path is refused unless it carries a human `granted_by`, and the
  frozen set is one module-level tuple, `FROZEN_PATHS`
  (`hooks/tezgah_research.py:2676`), read only through `_frozen`
  (`tezgah_research.py:2686`) so the write path and the checker cannot drift
  apart: `hooks/tezgah_gate.py` and `hooks/tezgah_integrity.py` (the verifier and
  the ledger's write path), `hooks/tezgah_research.py` (this module - the
  machinery that decides the rule, which the loop it judges may not edit), any
  `tests/` path (the hidden checks), `benchmarks/`, and any line's
  `experiments/*/protocol.md` (the pre-registration);
- an `orx:<runId>` proof token with no `raw/<runId>.log` under the line or the
  repository;
- an experiment with no `protocol.md`, results with no `analysis.md`
  (`_check_experiments`, `tezgah_research.py:1380`), or a git history in
  which `protocol.md` entered after `results.jsonl`, entered in the same commit,
  or changed after the run;
- a `results.jsonl` line that does not parse or is not an object, a row whose
  `source` is present and blank, or a `fixture`-scoped row whose `fixture`
  description is present and empty or not a string - the row claims the field and
  names nothing (`_check_rows`, `tezgah_research.py:1494`);
- a row or a claim whose `scope` is present and outside `SCOPES` (`real`,
  `fixture`, `derived`) - a label nothing shares is a label no reader can weigh -
  or a claim that declares `real` over rows that all record `fixture`: the field is
  what the producer saw, and a claim may not claim a wider one than its evidence
  (`_check_claim_scope`, `tezgah_research.py:843`); the write path refuses the
  same two (`claim_problems`, `tezgah_research.py:1224`);
- `literature/` holding notes and no `INDEX.jsonl` at all, an INDEX line that
  does not parse or is not an object, an INDEX row naming no note or naming a
  file `literature/` does not hold, a `class` outside `formal`/`grey`, or a note
  the index does not name (`_check_literature`, `tezgah_research.py:1633`;
  `_read_index`, `tezgah_research.py:1670`);
- a `review.json` that does not parse, carries no `dimensions` or `findings`, a
  dimension missing or outside 1-5, a `severity` outside
  `critical`/`major`/`minor`/`suggestion`, a finding targeting no file or quoting
  nothing, or a finding whose `quote` does not occur verbatim in its `target`
  (`_check_review`, `tezgah_research.py:1735`).

Warned, and refused under `--strict` - each is the honest state of an artifact
this layer cannot decide on, not a defect:

- a file whose rows declare no `scope`: the field cannot be inferred afterwards -
  a probe run against a generated repository and a measurement of the running
  system read identically once the run is over - so this is reported once per file
  with the count, and `--strict` refuses it (`_check_rows`,
  `tezgah_research.py:1494`). The same class as a row written before `source` did:
  the fix is the producer's to write, and every rule here only names it;
- a row that declares `scope: fixture` and does not say what was generated: the
  scope names the class and the field beside it names the input, so a row written
  before this one warns with the count and `--strict` refuses it - a class a reader
  cannot size is not an input they can weigh (`_check_rows`,
  `tezgah_research.py:1494`);
- a claim resting on a fixture row that declares no scope of its own
  (`_check_claim_scope`, `tezgah_research.py:843`), because a reader of the claim
  alone takes a generated input for the running system; declaring `fixture` is the
  whole fix;
- a claim that declares `real` over rows that mix one fixture row with real ones
  (`_check_claim_scope`, `tezgah_research.py:843`), naming the experiment(s) the
  fixture rows are in: the all-fixture case is the refusal above, and under-declaring
  is the safe direction here because the declaration is a warning to the reader, so
  a mixed claim that says `real` hides the half that is not the running system;
- a number a claim asserts that the artifacts its proof names do not contain
  (`_check_claim_numbers`, `tezgah_research.py:893`): 80 of this repository's own 82
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
  called missing. What it can never decide is a token found inside a longer
  number - a claim's `10` is contained by an artifact holding `10000` - so the
  warning is a consistency check and not a proof that the number was measured;
- a concluded line's `report.md` carrying a fixture-scoped claim and never saying
  `fixture` anywhere in it (`_check_report`, `tezgah_research.py:1812`);
- a prediction whose `commit` git cannot place against HEAD, or whose commit git
  cannot read at all (`commit_paths`, `tezgah_research.py:2702`): the row may name
  a real change in a shallow clone or a repository git cannot read here, so the
  question is unverified rather than answered - the same class as a pair the
  order rule cannot order - and `--strict` is what refuses it. The write path
  records the row and prints the same warning, because a writer that refused what
  the checker only warns about would be the stricter of two judges that have to
  agree;
- a prediction row that carries no `components` at all
  (`prediction_problems`, `tezgah_research.py:2722`): every row in this
  repository predates the field, and which component an old change touched cannot
  be recovered from the row afterwards, so the class is the warn one and
  `--strict` refuses it. The asymmetry is the only one the field has and it is
  deliberate: `predict` refuses a row being written now that names no component
  (`new` on the same function), because the writer of a new row can name it and
  the reader of an old one cannot;
- a pair the order rule compares that git ignores and does not track, so the
  protocol order will never be decidable for it; the message names the
  `git add -f <path>` that fixes it (`_check_tracking`,
  `tezgah_research.py:1453`);
- a `protocol.md` that answers neither what it predicts nor what would falsify it
  - the marker is a prediction word and a falsifier word anywhere in the file,
  read as prose and not by shape, and a sentence that *disclaims* one ("this file
  is the brief, not a prediction") does not answer it; the warning names which of
  the two questions it could not find. Three of this repository's own protocols
  are briefs for a read-only agent and carry no prediction by design, which is why
  the class is the warn one (`_check_protocol`,
  `tezgah_research.py:1423`; `_protocol_answers`,
  `tezgah_research.py:1408`);
- a concluded line's `to_human/report.md` that names no limit anywhere, or is not
  written at all - there is no report in which to state what the evidence does not
  show (`_check_report`, `tezgah_research.py:1812`; the marker is the
  phrase a limit is stated with - "does not show", "did not look at",
  "limitation", "non-goal", "open question", "unmeasured" - and a heading and a
  sentence count alike, `REPORT_LIMITS`, `hooks/tezgah_research.py:159`);
- a `## Patterns` bullet in `findings.md` naming no source - `[Cnn]`, a
  `literature/...` path or an `orx:<id>` (`_check_patterns`,
  `tezgah_research.py:632`);
- a claim with no `kind` at all, the pre-migration state `migrate` closes;
- a claim that supersedes another: the relation is reported naming both ids, so a
  reader who opens the older claim alone is told the line has replaced it
  (`_check_supersedes`, `tezgah_research.py:1059`);
- an `evidence` claim whose experiment's `results.jsonl` is missing or holds no
  row;
- a `results.jsonl` row with no `source` key at all: the rows written before the
  rule look like this, and inventing a source for someone else's measurement is
  the fabrication the rule exists to catch;
- a `grey` source with no `quality` note, an INDEX row verified by fewer than two
  records, or an INDEX row recording no `id`, `source` or `inclusion`
  (`_index_fields`, `tezgah_research.py:1707`);
- `review.json` missing on a line whose `phase` is `concluded` - a review is a
  judgement, so no migration can write one for the lines that concluded before
  the rule existed.

One warn is **not** promoted by `--strict`, and it is the only one: a `phase`
declared in `state.json` behind the phase the line's own artifacts show
(`_check_derived_phase`, `tezgah_research.py:1952`). The field is the author's
declared intent and `_check_report` and `_check_review` read it, so a derivation
simpler than that judgement must never fail a line the field says is fine. What
it does say is the "two authorities" defect this module names in its own source:
a field maintained by hand beside artifacts that are not, where a line whose
protocols, results, claims, findings, report and review are all written can still
report `inner` and no reader is told. `derived_phase`
(`tezgah_research.py:1925`) walks the artifacts the line already holds, in
`PHASES` vocabulary, and takes the furthest rung that holds: the question alone is
`bootstrap`; something run is `inner` - an experiment with a protocol and at
least one committed `results.jsonl` row (`_measured`,
`tezgah_research.py:1904`), or a claim recorded; the results folded back into
`findings.md` are `outer`, read as content under one of its four sections
(`_findings_written`, `tezgah_research.py:1895`); and the two artifacts a
concluded line owes, `to_human/report.md` and `to_human/review.json`, are
`concluded`. What each rung *is* is not decided here - whether a protocol answers
its two questions, or a review carries six scored dimensions, stays
`_check_protocol`'s and `_check_review`'s business - so the derivation only says
how far the line got. A field *ahead* of its artifacts is the author's call and is
never reported: `open_lines` and `_open_reasons` read the field when a caller has
to decide whether a line is finished, and this rule does not second-guess it.

## The write path and the checker stay in step

`claim_problems` (`tezgah_research.py:1224`) applies exactly the rules
`check` applies to a row, so the writer can never refuse a claim the checker
would accept: a statement, a falsification criterion, a proof naming an artifact
with a `kind`, a `provenance` in `PROVENANCE`, a `status` in `STATUSES`, every
cited path resolving under the line or the repository, and a `supersedes` id the
line holds - the ids already in `claims.jsonl`, read by `_claim_ids`
(`tezgah_research.py:1108`). The append itself takes an exclusive `flock`
with a 1 s bound (`_locked`, `tezgah_research.py:1305`), because two
sessions recording a claim at once is normal and a torn line is not. **The lock is
taken before the judgement, and the ids it judges are read from the descriptor the
lock is held on** (`_claim_ids`'s `handle` argument, `tezgah_research.py:1108`):
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

`prediction_problems` (`tezgah_research.py:2722`) is the same arrangement for the
prediction rows and the single place the two readings of that rule meet: `check`
calls it for each row of `predictions.jsonl` (`_check_predictions`,
`tezgah_research.py:2823`) and `predict` calls it inside the append lock, so a
row's verdict is one function's and the writer cannot be stricter than the
checker. The two asymmetries are deliberate and named: `check_line`'s `git=False`,
which is what the session note pays for, skips the commit half, so the shape rules
are what the cheap path reads; and `new=True`, which only the write path passes,
is what refuses a row being written now that names no `components` - a row that is
already in the file is the warning class above. The append takes the same
exclusive `flock` with the 1 s bound and the same committed-size repair the claim
path uses, and `_locked` now takes the name of the file it refuses
(`tezgah_research.py:1305`).

The row writer is the third site of the same order (`_append_row`,
`tezgah_research.py:2553`): it takes the lock, then judges the row with
`row_problems` (`tezgah_research.py:2518`) - exactly the hard refusals `_check_rows`
applies to a row's own shape (an object, a non-empty `source`, a `scope` in
`SCOPES`, a non-empty `fixture` description), and deliberately not the warn class a
pre-rule row is in, because a writer stricter than the checker refuses what the
checker only reports.

**An append starts at the committed boundary.** `committed_size`
(`hooks/tezgah_integrity.py:407`) is the offset just past the last `\n` in a file,
and `truncate_to_committed` (`hooks/tezgah_integrity.py:433`) cuts a descriptor
back to it; all three writers truncate first and write after
(`append_claim`, `tezgah_research.py:1324`; `_append_row`; `append_prediction`,
`tezgah_research.py:2844`). A fragment a killed writer left behind - no newline
ever terminated it - is then neither read as a record nor appended beside as one.
Every JSONL reader here stops at the same boundary (`_committed_text`,
`tezgah_research.py:743`; `_rows`, `tezgah_research.py:768`), so a reader and a
writer agree about where the records end; a record that *did* terminate and does
not parse is still refused, because the boundary hides the tail and not the file.
Before this, the claim writer terminated the fragment instead and the research
reader read to the last byte, so one kill during one append refused a line for
good while the ledger reader skipped the identical damage.

`kind` is what the proof has to be, and it decides what the proof must name -
`KINDS`, `hooks/tezgah_research.py:120`: an `evidence` claim has to name an
artifact of the line itself (a repository file is not the run it rests on), and
the experiment it names has to carry rows; a `literature` claim has to cite a
note under `literature/`; a `code` claim resolves anywhere in the repository; a
`derivation` claim resolves inside the line. `migrate` derives the kind per claim
from the proof's own tokens, with the same literature test the rule applies
(`derive_kind`, `tezgah_research.py:1201`), and reports what it could not
derive rather than inventing a value.

## The per-component report

A prediction row names the components its change touches, and
`tezgah-research components` prints what that buys: per component, the rows that
name it and their state. The manifest it groups by is
`hooks/tezgah_components.py` - the one definition of what a component is, whose
`keys()` the rules read and whose `COMPONENTS` the report reads for the labels -
and it is imported inside the call that needs it (`_components`,
`tezgah_research.py:2932`), so the path a session pays for at import time never
loads it.

The state of a row is read, never guessed (`_prediction_state`,
`tezgah_research.py:2969`): `falsified` when the `claim` the row names is
`refuted` in the line's own `claims.jsonl`, because the line's own rows are the
only record of a verdict; `unmeasured` when `value_after` is empty, which is the
round that has not run; `held` when it is filled, which is the number that came
back. A row whose `claim` the line does not hold decides nothing - the filled
`value_after` is not a verdict - so it stays `unmeasured` and the report prints
why, beside the row. `PREDICTION_STATES` (`hooks/tezgah_research.py:2896`) is
that vocabulary, and the headers count it.

It is a **report, not a gate**: it exits 0 whatever the rows look like, because
the refusals belong to `check` and a second judge with a different verdict is the
disagreement this module exists to avoid. What it prints first - the number of
components and of rows it read (`components_text`,
`tezgah_research.py:3039`) - is what tells an empty manifest from a line that has
predicted nothing, and a key the manifest does not define is reported as a bucket
of its own rather than dropped, so a hand-written row is visible.

## `migrate`: what the artifacts already hold

Three derivations and nothing else (`migrate`,
`tezgah_research.py:2183`): each claim's `kind` from the files its proof
names, each results row's `source` from the fields the row carries, and the
`literature/INDEX.jsonl` rows from the notes.

A row written before the `source` rule says where it came from in a field of its
own, and `_migrate_rows` (`tezgah_research.py:2231`) reads exactly those:
`log` or `raw` is the receipt itself and is taken as written, `run` or `id` is
the run the row came out of and is prefixed with the field it came from, so a
reader can tell a run id from a row id (`ROW_SOURCE_FIELDS`,
`hooks/tezgah_research.py:170`; `_row_source`,
`tezgah_research.py:2211`). A row that carries none of the four is reported
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
(`PROMPT_HINTS`, `hooks/tezgah_context.py:50`) - and the armed paragraph is
`RESEARCH` (`hooks/tezgah_policy.py:386-452`), which names `{RESEARCH_BIN}` (the
installed `bin/tezgah-research`) and the `orx` manual step.

The note, when orx is absent or a line is broken: a session is told that `orx` is
not installed and to fall back to a host subagent rather than improvise the
protocol (`context_for`, `hooks/tezgah_context.py:800-976`), and at session start and
after a compaction a line with structural problems is named with its first error
and the advice to run `check` before reporting a result (the note
`research_broken` in `context_for`, `hooks/tezgah_context.py:800-976`).

The mark: `research` in the status line. It is armed when `research-off` is
absent and the research tooling is present (`health_segments`,
`hooks/tezgah_context.py:1297-1365`) and turns used when a shell command really ran
the layer - `orx` or `tezgah-research`
in a command position, classified by the shared tokenizer
(`shell_kind`, `hooks/tezgah_context.py:1057-1082`), so a command that merely mentions
either name marks nothing. That is the same reader every host's status segment
uses ([status line](status-line.md)).

## The switch

`research-off` is the kill switch: with it armed the `RESEARCH` paragraph is
dropped, the session note is not built, and the mark reads `off` rather than
armed. It removes the rule, not just the mark - the diff is in `core_split`,
`hooks/tezgah_context.py:552-608` ([kill switch](glossary.md#kill-switch)).

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
