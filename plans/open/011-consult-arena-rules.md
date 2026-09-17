---
id: 011
title: Bring agent-arena's critique discipline into consult
status: open
branch: plan/011-consult-arena-rules
pr:
created: 2026-09-17
updated: 2026-09-17
---
## Goal
`bin/consult` is one-shot: the same prompt to N models in parallel, each answer
printed, no cross-examination. A review of `zhjai/agent-arena` (MIT, a
protocol-only skill, no runtime) found eight transferable rules. Two consulted
models (gemini-2.5-pro, grok-4.3) both rejected its multi-round debate protocol
as ceremony for a stateless CLI and both named the same cheapest win: one
referee call after the independent round.

## Acceptance
- [x] `bin/consult` makes one referee call after the panel and prints the named
      digest fields (`recommendation`, `key disagreements`, `unchecked
      assumptions`, `what would change my mind`, `requested evidence`);
      `--no-referee` skips it.
- [x] `consult -` reads the packet from redirected stdin; a missing question
      argument stays a usage error rather than becoming a paid prompt.
- [x] The footer names a failure class per model and prints one retry line
      naming the single variable to change; it stays silent when nothing failed.
- [x] The CONSULT block carries checkable triage thresholds, the de-anchoring
      rule, and the field names; the verifier and reviewer bodies carry the
      raw-artifact rule.
- [x] The SPEC block asks for one genuinely different option beyond A/B/A+B,
      the cheapest reversible test, and the evidence that would flip the choice.
- [x] `python3 -m compileall -q hooks bin statusline.py`,
      `python3 -m unittest discover -s tests` and `ruff check .` pass.

## State
Landed on the branch in three commits (`plan: add 011`, `feat: consult judges
the panel with one referee call`, `docs: the consult and spec rules carry triage,
de-anchoring and option space`). Evidence, all observed: 438 tests pass,
`ruff check .` clean, `compileall` clean; `tests/test_consult_arena.py` drives the
new behaviour against a local fake endpoint (8 cases, 8 pass). One live run
against the real providers printed the panel, then `## referee
(google/gemini-2.5-pro)` with all five headings, and correctly reported "there
are no key disagreements" when the two models happened to agree - it did not
invent one.

The armed-by-task-class band grew 758 bytes (2,231 -> 2,989); the benchmark
README quotes the re-measured report, as do README.md and the 19 translations.

The branch was then rebased onto `main` once plan 010 merged (its review had
already flagged the stale base): the core band moved to 6,032 characters -
010's 5,987 plus 45 from the pointer-line wording - so the whole band material
was re-measured against the merged tree and the README cost rows follow it.

An independent review of the diff (tezgah-reviewer, read-only) reported three
minor defects and six suggestions; all are fixed in `fix: answer the independent
review's three findings`. The real ones: a scheme-less `CONSULT_URL` escaped the
worker as a traceback and exited 1 where the all-failed path owes 3; a stalled
body read classed as `error` rather than `timeout`, so the retry line named the
wrong lever; a missing question argument silently read stdin instead of printing
the usage error, turning a stray pipe into a paid prompt; and two more copies of
the consult rule still said "non-trivial or hard-to-reverse". A second round
confirmed every fix and found a fourth copy in `POINTERS`, which rides the
always-on core of every session - fixed with its `output-styles` mirror and the
two no-key notices. Four cases were added for the field list, the `empty` class,
the `CONSULT_JUDGE` default and the scheme-less endpoint, plus one that stalls a
server to pin the timeout class: 13 in the file, 449 in the suite.

`~/.config/tezgah/bin/consult` symlinks to the main checkout, so the live tool
picks this up only once this branch is on `main`.

## Not adopted, with reasons
- Multi-round stateful debate (independent -> critique -> revise -> blind judge):
  the client is stateless HTTP, the cost triples, and both consulted models
  called it ceremony for this use case. One referee call captures the
  cross-examination that was actually missing.
- The context/compaction checkpoint protocol: it exists because their arena runs
  inside the orchestrator's own context; ours returns one bounded blob. Only the
  stdin/redirect half was worth taking.
- The Claude-Code-CLI turn-budget and `error_max_turns` rules: we do not call
  that CLI, and the general principle (a dead call is not a result) is already
  the integrity and loop-discipline rule.
- The 13-mode taxonomy: our mode space is consult-inline vs reviewer-subagent.
- A separate `groundcheck` fact gate: already covered by consult's
  verify-against-code, the reviewer's confirmed/refuted/unverified, and the
  integrity gate.
- Their skill-packaging layout: `hosts/*` plus `tezgah_agents.py` render to more
  hosts than their plain markdown does.

## Next
Open the PR (`plan/011-consult-arena-rules` -> `main`) once the independent
review of the diff is clean.
