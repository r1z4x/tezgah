# E1 - can the judgement seam serve a ~98-option routing choice?

Status: protocol written before the run. **Provenance note:** the first write of
this file did not land (the tool returned an unrelated notice instead of a
success message) and the run proceeded; this is the same text re-created
unchanged from the transcript after the fact, with nothing added from the
results. `.tezgah/research/` is untracked, so `tezgah-research check` reports the
protocol order as unverifiable either way (it warns rather than errors).

## What the change is

Candidate surface 6 of `.tezgah/research/typesafe-cost/findings.md`: the
`ai-research` skill is one of the 13 roster entries, and picking it is only half
the job - inside it sit 98 vendored entries across 23 categories, grouped into
six stages by `skills/ai-research/index/*.md`. Today the rule is "read one entry,
never the tree", which the model can only obey by reading the index first.

The seam (`hooks/tezgah_judge.py`) exposes exactly one primitive pair -
`available()` and one batched `ask(state, questions)` - and its three callers
hand-build the questions. Two of the candidate surfaces need one thing the seam
has no shape for: a Choice over a large option set (98 entries). The question this
run answers is whether that primitive holds at 98 options, or whether the surface
needs a two-stage (stage -> entry) shape instead.

## What it predicts

- P1: a flat Choice over all 98 entries reaches top-1 <= 0.65 against a
  hand-labelled query set. Falsified by flat top-1 >= 0.85.
- P2: the two-stage shape (Choice over the 6 stages, then a Choice over that
  stage's entries) reaches top-1 >= 0.80 and >= the flat arm. Falsified by
  two-stage top-1 < 0.65 or two-stage < flat.
- P3: the flat arm costs at least 3x the two-stage arm in input tokens per query.
  Falsified by flat < 3x two-stage.
- P4: no query comes back `none` in either arm - every query names something the
  option text carries. Falsified by any `none`.

## Method

- **Option text**: `name` + the entry's own `purpose` sentence, cut to 100
  characters, exactly the shape `hooks/tezgah_skill_pick.py` uses for the roster
  at `CLAUSE_CAP = 120`.
- **Query set**: 14 queries written by hand from
  `skills/ai-research/index/*.md`, each chosen so exactly one entry's purpose
  covers it and its nearest neighbour (a sibling the query must NOT pick) is a
  different entry. The label is the entry the query names.
- **Arm A (flat)**: one live call, state = the query, one `choice` question whose
  criteria are all 98 names with `none` offered.
- **Arm B (two-stage)**: one call over the 6 stages with their entry counts and
  the categories each holds, then, for the stage the call picked, one call over
  that stage's entries with `none` offered.
- **Metric**: top-1 accuracy against the label, plus input tokens, output tokens,
  latency and dollars per query, from the reply's own `usage`.
- **Price**: $0.042 per 1M input, $0 output, the figure `bin/tezgah-triage`
  prints.

## Why this is worth the money

The answer decides a spec item: if the flat arm holds, the seam needs no new
primitive and surface 6 is a ~30-line caller; if it does not, the surface needs a
two-stage helper AND every future many-option caller inherits that shape. That is
a design decision, not a preference.

## What would make this run worthless

A query set that is a verbatim copy of an option's purpose sentence would measure
string matching rather than routing. Each query below is a paraphrase that keeps
the discriminating technical term and drops the vendor name, so a query and its
label overlap on vocabulary but are not the same sentence. The inverse failure -
a set so unambiguous that both arms sit at the ceiling - is what actually
happened, and it is recorded in `analysis.md`.
