---
id: 008
title: Strengthen research with a workspace, a check and a skill
status: done
branch: plan/008-research-workspace
pr: 17
created: 2026-09-17
updated: 2026-09-17
---
## Goal
Research is the one task class whose deliverable is evidence, and the contract
only pointed at the OpenResearch CLI. Add the part that survives the session: the
state on disk, the proof that the plan came before the run, and the review a claim
passes before it is reported - adapted from Orchestra Research's MIT-licensed
`AI-research-SKILLs` library (its `autoresearch`, `ara-rigor-reviewer` and
`ara-research-manager` skills), in tezgah's own words, with orx staying the
execution engine.

## Decisions
- **Tezgah-owned, not vendored.** The four slices that matter here (the two-loop
  rhythm and workspace, the six-dimension claim review, the session provenance
  record, the ideation step) are rewritten as `skills/research/SKILL.md`. The
  library's 90+ ML-engineering domain skills are deliberately not copied: tezgah
  is a general coding harness, and copying them would bloat the router.
- **One mechanical rule, the one an agent can cheat on.** `protocol.md` must be
  committed before `results.jsonl`. The check decides it on the commit graph, not
  on timestamps: two commits inside the same second and a rebase stay clean, while
  a protocol *edited* after the results is refused.
- **The rest are completeness rules**: a claim with no falsification criterion or
  evidence, an unknown provenance or status, results with no analysis, an
  experiment with no protocol, a findings file that answers none of its four
  questions.
- **Cheap on the session path.** The session note runs the structural checks only
  (`git=False`), so it spawns no subprocess, and it is gated by `research-off`.

## Acceptance
- [x] The protocol-order rule is decided by ancestry and refuses an edited
      protocol. `tests/test_research.py` (same-second, edited-after-run, rebase,
      rename, one-commit-both, uncommitted).
- [x] A disciplined line is clean, and the session note appears only for a broken
      one. `tests/test_research.py` (SessionNote) and `tests/test_context.py`.
- [x] The check never raises on unreadable state. `tests/test_research.py`.
- [x] The CLI separates a broken line (1) from misuse (2), and a typo slug fails.
      `tests/test_research.py` (Cli).
- [x] The ninth skill's pinned numbers are updated everywhere they appear: the
      installer pin, the benchmark README block, all 19 READMEs.
- [x] `python3 -m unittest discover -s tests` and `ruff check .` pass.

## State
Implemented; the independent review found two medium defects (an edited protocol
was invisible; the second-resolution date comparison false-positived on
same-second commits and rebases) and four low ones (unguarded reads on the session
path, a bare command name that is not on PATH, unhonoured CLI exit codes, a stale
skill count in the benchmark README), all fixed before the merge. The tests were
written and then updated by a separate author, with each rule proved by breaking
the implementation.

## Next
Nothing outstanding; merged PR #17. `tezgah-setup --install` links the skill and
the CLI into every host.

merged PR #17 on 2026-09-16T21:26:06Z.
