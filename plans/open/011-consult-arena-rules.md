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
- [ ] `bin/consult` makes one referee call after the panel and prints the named
      digest fields (`recommendation`, `key disagreements`, `uncertainties`,
      `what would change my mind`, `requested evidence`); `--no-referee` skips it.
- [ ] `consult -` reads the packet from stdin, and so does a redirect with no
      question argument.
- [ ] The footer names a failure class per model and prints one retry line
      naming the single variable to change; it stays silent when nothing failed.
- [ ] The CONSULT block carries checkable triage thresholds, the de-anchoring
      rule, and the field names; the verifier and reviewer bodies carry the
      raw-artifact rule.
- [ ] The SPEC block asks for one genuinely different option beyond A/B/A+B,
      the cheapest reversible test, and the evidence that would flip the choice.
- [ ] `python3 -m compileall -q hooks bin statusline.py`,
      `python3 -m unittest discover -s tests` and `ruff check .` pass.

## State
Analysis done (source read for both repos, cross-model second opinion recorded).
Branch based on `main`, not on plan 010: 010 carries 154 lines of unrelated
`hooks/tezgah_agents.py` plumbing and a rewritten `tests/test_providers.py`, and
another session is editing `CHANGELOG.md` in the shared checkout, so this work
runs in a separate worktree. New tests go in their own file to keep 010's
`tests/test_providers.py` untouched.

Not adopted, with reasons: multi-round stateful debate (stateless HTTP client,
3x cost, both consulted models called it ceremony), the context/compaction
checkpoint protocol (it exists because their arena runs inside the orchestrator's
own context; ours returns one bounded blob), the Claude-Code-CLI turn-budget
rules (we do not call that CLI), the 13-mode taxonomy, a separate `groundcheck`
fact gate (already covered by consult's verify-against-code, the reviewer's
confirmed/refuted/unverified, and the integrity gate).

## Next
Implement the referee stage in `bin/consult`.
