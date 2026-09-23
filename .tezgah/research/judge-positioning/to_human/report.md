# Positioning the judgement seam

Question: `tezgah_judge` (the TypeSafe/Jev judgement seam) looks weak - what is it
today, where should it sit in this project's structure, and should the contract
name it? Revision audited: HEAD `4bf25e8`, working tree at 2026-09-20, with eight
files carrying an uncommitted `skill-suggest-*` change.

## What the line established

**C1 - the seam has three callers, not two.** `hooks/tezgah_judge.ask` is reached
by `bin/tezgah-triage` (`:50`), `bin/tezgah-docs` and `hooks/tezgah_skill_pick.py`
(`:32`); the module docstring (`hooks/tezgah_judge.py:3-5`) and
`docs/operations.md:202-203` say two. The third is the only one on the prompt path
of every turn, and it is the one the docs do not name. Each caller hand-builds its
question and hand-reads the reply - three copies of each - and `criteria` is
present where a caller thought of it and absent where it did not.

**C3 - the spend is invisible.** `tezgah-status --counters` has no judge key; the
counter fold counts `consult` and `codegen` as `detail` substrings
(`hooks/tezgah_integrity.py:694-699`); only `bin/tezgah-triage` prints a cost at
all (`:165-170`), and a judgement made by the prompt-path caller is a hook call
with no shell row, so nothing on a session ledger records it.

**C4 - two credential readers answer two different questions.** Measured, not
read: with the key file present and no omp login store, `have_typesafe_key()`
returns `False` while `tezgah_judge.available()` returns `True`. The install
report's TypeSafe row can therefore read missing on a machine where every
judgement works.

**Reachability.** Neither `tezgah-triage` nor `tezgah-docs` appears in
`hooks/tezgah_policy.py`, `hooks/tezgah_context.py` or `agents/*.md` (grep, zero
hits). `judge-off` is honoured at `hooks/tezgah_judge.py:88` but appears in
neither the always-on kill-switch paragraph nor the contract's switch table, so a
session cannot name the switch it would have to tell the user about.

## What the measurement established

**C2 - the primitive holds at 98 options, and two stages is not better.** Both
arms answered 14 of 14 hand-labelled in-library queries, and both refused 4 of 4
out-of-library queries. The two-stage shape saved 1.61x input tokens (3,687 vs
2,293 per query) for one extra round trip - at $0.042/1M worth about $0.00006, so
it does not pay for a second call or a second code path. A flat Choice over
`name` + the entry's purpose clause costs about $0.000155 and 828 ms per query.

E1's P1 (flat top-1 <= 0.65) was **refuted**; P3 (>= 3x token ratio) was
**refuted**; P2 held only in its floor; P4 held. E1b's P5, P6 and P7 held.

The round cost 50 live calls and **$0.0041** - E1 42 calls / $0.003516, E1b 4
calls / $0.000618, and one E1b stage arm that was not recorded.

## The decision

The seam stays where it is - `hooks/tezgah_judge.py`, a total, stdlib-only hook
module - and its callers stay two bin tools and one hook. What changes is the
tier: the capability is a named on-demand capability of the `codegen` shape
(Tier B), with the three things Tier B is missing today - a switch the session can
name, a group-1 mark, and a counted cost on the ledger - and **no always-on
paragraph**; `CONDITIONAL_KEYS` exists so an on-demand capability is not paid for
every session. A seven-item spec (`to_human/spec.md`) states each item as a
command and the test that fails without it; the citation-audit caller is ranked
first on evidence and last in order, because it needs its own measured round
first.

## What the tree has since built (2026-09-22)

Six of the seven spec items are in the tree at HEAD `ddf72b4`, so the decision
above is no longer a proposal:

- **J1** `judge-off` is in the always-on kill-switch paragraph, the contract's
  switch table and its two mirrors, next to `triage-off` and `docs-judge-off`.
- **J2** `choice()` and `noul()` exist on the seam and all three callers read
  through them.
- **J3** a `judge` mark renders in group 1, with the `observable` carve-out
  `docs/status-line.md` requires.
- **J4** the ledger counts judgements: a `judge` key in the counter fold,
  counted on the row kind rather than a `detail` substring, printed by
  `bin/tezgah-status`, with one row per successful judgement from both the shell
  caller and the prompt-path caller.
- **J5** each caller has its own switch, with `judge-off` the master.
- **J6** `docs/judge.md` exists and is indexed, so `tezgah-docs judge` routes
  from the keyword index and pays for no Choice.

J7 is refuted, not built: its pre-registered round is
`experiments/E2-citation-adjudication`, and `C5-R` records that one call per
citation agreed with the hand labels on 5 of 9 clear items against a 0.9 floor,
with precision 0.29 on the seven it flagged.

The pass that closed this line also corrected the drift the audit first measured:
five shipped places still said the seam had two callers - the module docstring,
three passages of `docs/operations.md`, a comment in `hooks/tezgah_context.py`
and one in the opencode plugin - and each now names all three
(`C1-R-callers-fixed`).

## What this does not show

- **It does not show where the flat 98-option Choice breaks.** The 14-query set is
  hand-written to be unambiguous, so 14/14 is a ceiling. The near-miss case - a
  query just outside a category whose entry clause is close - was never run, and
  P1 is open as written rather than answered.
- **It does not show that a router refuses anything subtle.** The refusal evidence
  is four queries whose option text shares no vocabulary with the query at all;
  that bounds the gross failure, not the near-miss. Four is a small count and no
  query was repeated.
- **It did not measure variance.** Each arm ran once over 14 queries, so no arm
  has a spread; the 1.61x token ratio and the ~830 ms latency are single-run
  figures, and the two-stage arm's accuracy is a tie at the ceiling, which shows
  neither shape is better.
- **It does not show what the seam actually costs in use.** The prompt-path
  caller's spend was unmeasured when this line concluded; the ledger counts it now
  (`C3-R-spend-counted`), but this line still holds no series of its size.
- **It does not show the citation surface is impossible, only that the first
  format of it fails.** C5 is settled as `C5-R` (refuted): agreement 0.56 against a
  0.9 floor, precision 0.29. The run's own analysis bounds it - the model answered
  `does-not-show` seven times out of eleven, so what is refuted is a single-call
  two-phrase format, and a two-order format with a worked example was not run. The
  work list has also grown since the claim was written: `bin/tezgah-docs
  --citations` reports 878 citations it cannot judge of 1202 on today's tree,
  against the 734 this line recorded.
- **It does not establish how common the install-report divergence is.** C4 is one
  measurement on a synthetic HOME; the two readers are now named, and the install
  report prints both rows (`C4-R-readers-named`), but how many real machines hold
  the key file without an omp store is still unknown.
- **It does not show the audited revision is still the current one.** The tree was
  being edited while it was read (eight files in flight), and the in-flight
  `skill-suggest-on` change was not committed; what happened afterwards is that
  HEAD moved and the change landed, so the citations in `findings.md` are labelled
  with the revision they came from rather than converted to today's lines.
- **It leaves two design questions open, and the tree has since answered both**:
  the per-caller switch is a kill switch (`triage-off`, `docs-judge-off`) for the
  two shell callers and an arming marker (`skill-suggest-on`) for the prompt-path
  one; and the egress boundary is stated in `docs/judge.md`, the module docstring
  and `skills/analyze-app/SKILL.md`, not in the always-on text - so the session
  that never picks `analyze-app` still does not read it.
- **It did not run the ranked next surfaces.** N4 and N5 have no measurement; N3
  is measured on a driven fixture but never as a full-screen coverage pass.

## Artifact state a reader should know

**An integrity defect this line carries, stated plainly.** E1's `protocol.md` says
in its own text that the first write did not land and that the file was re-created
from the transcript *after* the run. The ordering property every E1 verdict rests
on - a prediction provably older than its result - is therefore not demonstrable
from the artifacts, and no later edit can repair it: the honest move is to keep
the run, its rows and its verdicts and to record the defect, which is what
`log.md` (entry 27) and this section do. `.tezgah/research/` is gitignored, so
`tezgah-research check` can only warn on the class rather than decide it. The same
line's second experiment does not carry the defect: E2's protocol and its
labelled `sample.json` were committed at `da7148e`, before the run at `ddf72b4`.

The experiment `results.jsonl` files are tracked now, and every row declares
`source` and `scope: fixture`: both runs measured a query set written by hand, not
the running system's own traffic, so C2 - the only claim resting on those rows -
declares `fixture` too, and what it established is a property of that set. All
eight claims carry a `kind`, and the `## Patterns` bullets name the claim they
generalise from. The line's own `to_human/review.json` records the defects the
review found, each with the status this close-out gave it.
