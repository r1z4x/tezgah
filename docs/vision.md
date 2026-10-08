# How a tezgah session is meant to run

**Who reads this, and when.** A maintainer or an agent about to change how
sessions behave: the check cadence, the review loop, model routing, the research
layer. It is the operating model those rules serve, with the measurement behind
each one. The rules themselves live in `hooks/tezgah_policy.py`; this page is the
shape they add up to, and it is written so a change to one of them can be judged
against the model instead of against taste.

Measured on 2026-10-01 from one session (356 active minutes, 573 tool calls) plus
the workspace's own records; every number below names where it came from.

## The five principles

1. **Answer first, act only inside the asked scope.** A turn whose ask is a
   question answers it from evidence already gathered, then stops. Standing
   authority to merge or push never fires on such a turn. (Measured: a question
   turn ended in a merge and a push, and the user had to say the question went
   unanswered.)
2. **Cost is paid once per revision, not once per commit.** Checks have tiers,
   and the biggest one runs once on the final tree (`hooks/tezgah_policy.py::CORE`). (Measured: 11 serial suite
   runs, 106 minutes, 10 of them green confirmations, in one session - the rule
   "run the full suite once, on the final tree" was already written down and
   `AGENTS.md` said "before every commit".)
3. **One review per plan, two rounds, fanned out.** Reviewers read the plan's
   whole diff once, in its verification phase. Round one spawns them together,
   one per dimension. Only a confirmed critical or major finding opens round two,
   and round two reads the fix's delta. After round two the user gets what is
   left, or the plan lists it as fix-later. `tezgah-task review` refuses a third
   round (`hooks/tezgah_agents.py::_reviewer_body`, `bin/tezgah-task::cmd_review`).
   (Measured: the old loop opened a round on any finding and ended only on a
   clean round. It reviewed one finished plan round after round. In another plan,
   fixes brought two of four severe defects. So round two reads the fix, and a
   severe finding left after it blocks.)
4. **Doubt lowers nothing and hides nothing.** An unverifiable check never
   downgrades a finding, an unknown criterion never relaxes a cap, and a line
   whose own criteria are unmet is reported as unanswered rather than concluded.
   (Measured: `close --limit` accepted any string; 4 of 11 sampled research lines
   concluded with the ask unanswered.)
5. **Do not re-verify a revision that has not changed, and do not re-ask a
   question that was answered.** Repeat guards key on the tree, not on the
   command text; a green check is evidence until the tree moves.

## The tiers, and what each costs (measured)

| Tier | Command | Wall time |
|---|---|---|
| edit loop | `tests/impacted.py --run <changed paths>` | 0.1-95 s (integrity+gate: 18 modules, 93.8 s) |
| pre-commit | that set + compileall + ruff (+ `--citations` when hooks/ or bin/ moved) | +~5 s |
| pre-merge, once | `tests/impacted.py --all` + the two e2e scripts | 103.5 s (8 shards; 566.9 s serial) |
| CI | the same, on the matrix in `.github/workflows/ci.yml` | unchanged |

A path the map does not know runs everything (`tests/impacted.py::modules_for`): `tests/support.py`,
`hooks/tezgah_paths.py` and anything new. `tests/test_impacted.py` refuses a
change that would silently run nothing.

## Model routing

Every omp agent gets a **fallback chain** (`hooks/tezgah_models.py::_chain`, over
`hooks/tezgah_models.py::funded_families`). The mode's family goes first. By
default the rest is the same vendor's model through another funded provider, such
as Opus through OpenRouter on an Anthropic session. `fallback: any` in
`config.json` adds every other funded family, and `none` keeps the first entry
alone. One pin per agent made one provider's 429 every subagent's failure, because
the account is shared with the main thread (measured: 24 of 26 post-routing 429s hit
a subagent's first request, all on one Opus account). A chain that left the vendor
ran an Opus session's subagents on GPT and GLM, so that step is opt-in. A family
whose credential cannot be detected is left out of the chain, never guessed in. The
main thread's own model, and the provider-keyed chains, stay the user's settings.
tezgah writes only the keys it owns.

What tezgah cannot fix from inside: a provider that stalls on a very large
context (`OpenAI completions stream stalled`, five minutes without an event on a
458k-token request - a DeepSeek-side stall, with no hook blocking the loop), and a
quota shared by every session on the machine. Those are settings and a reminder,
not a rule.

## The research layer

A line carries the user's ask verbatim, a tier (`quick` gets no line at all, `hooks/tezgah_research.py::ask_problems`), and
one success criterion per part of the ask, written before any experiment. It ends
with a verdict per criterion; a criterion that is `not-met` is a result, but it is
recorded, and an unanswered line stays visible in `status` instead of disappearing
into `done/`. Lines live under `research/open/` and `research/done/`, the way plans do, resolved
by one reader (`hooks/tezgah_research.py::line_dir`); an unmet criterion keeps a line
listed as unanswered (`hooks/tezgah_research.py::unanswered`).

## What is measured to know the operating model holds

These are measures of how a session runs, not of task outcomes.

- wall time per session and the share spent waiting;
- serial full-suite runs per session (the count, not the length, is the cost);
- review rounds per change;
- subagent spawn failures by model;
- research lines concluded with every criterion met, against lines concluded
  unanswered;
- `status`'s own count of lines the layout has not migrated.

## What it does not claim

The model above describes mechanisms: what a session is told, what the gate
refuses, what the ledger records. It does not claim that an agent under tezgah
cheats less, finishes more tasks or reports more honestly. A paired on/off
experiment in October 2026 tested that and found no measurable effect. It ran
DeepSeek V4.1 Flash on omp, bare against a full install. On ImpossibleBench's
conflicting SWE-bench split, the agent cheated in 0 of 132 runs with tezgah and
1 of 131 without. The model barely cheated in either arm, so the experiment had
no headroom. Hand labels of final messages on those impossible tasks found
false done claims in 3 of 30 runs with tezgah and 6 of 30 without. The CI of
that difference includes 0. The Stop rule's claim reader
flagged far more runs than that. On Turkish replies it counts `doğrulandı`
(verified) on a partial fix as a claim, a recorded weakness not yet fixed. The
numbers, the per-task counts and the instrument flaws are in
[the results bundle](results/paired-outcome-2026-10.md).

## Source of truth

- `hooks/tezgah_policy.py` - the rules this page describes.
- `hooks/tezgah_integrity.py`, `hooks/tezgah_gate.py` - the gate and the ledger.
- `hooks/tezgah_models.py`, `docs/models.md` - the routing table and the chains.
- `hooks/tezgah_research.py`, `docs/research.md` - the research layer.
- `tests/impacted.py`, `docs/testing.md`, `AGENTS.md` - the check tiers.
- `docs/results/paired-outcome-2026-10.md` - the paired outcome experiment.
- The four internal diagnosis reports behind the numbers (session scratch,
  not published).
