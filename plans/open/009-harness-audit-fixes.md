---
id: 009
title: Fix what the harness audit found
status: in-progress
branch: plan/009-harness-audit-fixes
pr:
created: 2026-09-17
updated: 2026-09-17
---
## Goal
Act on the five-slice audit (host parity, skills, contract, omp runtime, cost) so
the harness does not merely look armed: a hook that dies says so, the Turkish
prompt class actually arms its rules, every host runs the current checkout, the
marks stop over-reporting, and the published numbers match the machine.

## Findings and verdict
- **P0 - the omp bridge swallows every failure.** `hosts/omp/tezgah-hook.ts.in:44-51`
  catches all errors and returns `{}`, so a moved checkout or a crashed hook
  disables the whole omp surface with no signal. Reproduced: with a broken hook
  path, an attribution commit and an unverified done-claim both passed.
- **P0 - the Turkish hints are dead on inflected forms.** `\b(stem)\b` cannot
  match `düzgün çalışsın`, `araştırma yap`, `hipotezi test et` - and the contract
  names `düzgün çalışsın` as its canonical example. Measured with
  `classify_prompt`.
- **P1 - Claude runs a stale copy.** `~/.claude/plugins/cache/.../0.9.0` holds 8
  skills and old hooks; the other five hosts execute the checkout live.
- **P1 - opencode has no per-prompt arming** and ships a hand-kept reminder
  paraphrase that drops whole-ask, sycophancy, spec, consult and research.
- **P2 - Cursor's gate cannot see edit/write tools** (`Shell|Grep|Task` matcher),
  dsh's bridge drops PostCompact/PostToolUseFailure, codex's live `CODEX_HOME` is
  a relocated home the installer never checks, and the marks over-report
  (`consult✓` fires on the substring `consult` in any command).
- **P3 - the published latency figures are 1.7-2.8x optimistic**, with 4 git
  spawns per session start where 2 do, and 9 skill-standard violations including
  a router generator that drops every trigger word from two skills.

## Acceptance
- [x] A broken hook path produces a visible signal on omp, and a test drives it.
- [x] Every Turkish phrase the audit listed arms its rule, pinned in
      `tests/test_context.py`.
- [x] The installer detects a stale Claude plugin copy and refreshes it.
- [x] opencode arms the conditional rules per prompt through the shared builder.
- [x] Cursor routes edit/write tools through the gate and briefs subagents.
- [x] The codex install and checks honour a relocated `CODEX_HOME`.
- [x] A mark only turns `✓` when the tool actually ran.
- [x] README and the benchmark README carry re-measured latencies.
- [x] The 9 skill-standard violations are fixed.
- [x] `python3 -m unittest discover -s tests` and `ruff check .` pass.

## State
All five slices landed on the branch: 414 tests and `ruff check .` green.
Every finding carries a test that fails on the pre-fix code. The live surfaces
(Claude plugin copy, relocated codex home, omp extension snapshot) go current
when the machine runs `tezgah-setup --install`.

## Next
Open the PR, let CI confirm on 3.10/3.12, merge, then run `--install` on this
machine.
