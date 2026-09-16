---
id: 007
title: Interactive install wizard for tezgah-setup
status: in-progress
branch: plan/007-setup-wizard
pr:
created: 2026-09-16
updated: 2026-09-16
---
## Goal
Someone who runs `bin/tezgah-setup` in a terminal should be asked what to
install instead of having to read the flag list, and nothing about the
automated callers (agents, CI, scripts) may change.

## Decisions
- **TTY-gated, with an escape hatch.** A bare run in a terminal is the wizard; a
  piped, agent or CI run keeps the report. `--wizard` forces it anywhere, which
  is also what makes the flow testable through a piped stdin. Two independent
  models consulted (`consult --online`, google/gemini-2.5-pro and
  x-ai/grok-4.3, 2026-09-16) both recommended exactly this gating plus a wizard
  that only collects answers.
- **stdlib only.** The repo declares no dependencies (`pyproject.toml` is lint
  config and there is no `[project]`), so the prompts are `input()`-based, not a
  vendored questionary/rich/prompt_toolkit.
- **One apply path.** The wizard calls `install_all()`, the function `--install`
  now uses too, so there is no second install implementation to drift.
- **Absolute roots only.** A relative root resolves against whatever cwd a later
  session has, which would silently arm the wrong tree.
- **`--report` exists** so a terminal user who wants the report (the whole of
  the old bare-run behavior) still has an explicit spelling for it.
- **Nothing is written before the final yes**, so a decline or Ctrl-C leaves the
  machine as it was.

## Acceptance
- [x] A piped bare run prints the report and never prompts.
      `Wizard::test_a_piped_bare_run_still_reports_and_asks_nothing`
- [x] The plan the wizard printed is what the shared install path applied.
      `Wizard::test_answers_drive_the_same_install_path_as_the_flags`
- [x] Flags act as the default answers.
      `Wizard::test_flags_stand_in_as_the_default_answers`
- [x] Invalid host and root answers are re-asked, not half-installed.
      `Wizard::test_a_bad_answer_is_asked_again_not_installed_half_way`
- [x] Declining the plan writes nothing.
      `Wizard::test_declining_the_plan_writes_nothing`
- [x] A closed stdin exits non-zero instead of hanging.
      `Wizard::test_a_closed_stdin_aborts_instead_of_hanging`
- [x] `python3 -m unittest discover -s tests` (320 tests) and `ruff check .`
      pass on the branch.

## State
Implemented on `plan/007-setup-wizard` (commit `00b60a7`): the wizard, the
`install_all()` extraction, the README paragraph and command rows. Manual smoke
run on this machine: five empty answers in a throwaway HOME printed the plan and
installed every detected host; exit 0.

## Next
Review, then merge, then `plan-sync` moves this file to `plans/done/`.
