---
id: 003
title: Harden the installer against the 2026-09-15 field report
status: open
branch: plan/003-install-hardening
pr:
created: 2026-09-15
updated: 2026-09-15
---
## Goal
Act on the field report from a clean install on another machine
(`~/Downloads/tezgah-kurulum-ve-hata-raporu.txt`): the dsh status-line install
fails, the dsh key check is wrong, pnpm is an undocumented prerequisite, tool
detection flaps with PATH, and two doc/dev gaps. Fix the tezgah-owned findings;
record the ones that are out of scope.

## Findings and verdict
- **BULGU-1 (P1, bug) — fixed.** `dsh_run` hardcoded
  `$DSH_HOME/profiles/node_modules/@deepseek-ai/dsh/lib/bin.js`, which does not
  exist when dsh was bootstrapped through npx, so the status line never linked.
  New `dsh_cli_args()` tries, in order: `TEZGAH_DSH_BIN`, the profile-local node
  entry, tezgah's own `bin/tezgah-dsh` launcher (which itself falls back to npx),
  a PATH `dsh`, then `npx -y @deepseek-ai/dsh`. The failure message now names the
  real cause (CLI missing vs pnpm missing).
- **BULGU-2 (P1, logic) — fixed.** The route check required both OpenRouter and
  DeepSeek keys and ignored `~/.config/*/key`. Now `host_checks_dsh` prints one
  row per route, and `dsh_key_resolvable` also honours
  `~/.config/openrouter/key` and `~/.config/deepseek/key`, matching
  `have_consult_key`.
- **BULGU-3 (P2, prerequisite) — fixed.** `pnpm` is added to the auto-installed
  deps (`npm install -g pnpm`), ordered before `dsh` because `dsh plugin` cannot
  initialize a profile without it. README now lists node + npm + pnpm.
- **BULGU-4 (P2, fragility) — fixed.** New `tezgah_paths.which_user()` falls back
  to `~/.local/bin` and `~/.cargo/bin`, so `orx`/`cbm`/`cursor-agent` read as
  present even in a non-interactive shell that never sourced the rc. Used by
  `orx_bin`, `cbm_bin`, `detected()` and the host checks.
- **BULGU-5 (P3, docs) — fixed.** README states the installers run over the
  network and documents `--no-deps` for CI.
- **BULGU-7 (P3, dev) — fixed.** Added `requirements-dev.txt` (pinned ruff) and
  CI now installs from it, so a clean machine and CI agree.
- **BULGU-6 (P3, migration) — not tezgah's code.** The statusLine loss happened
  when the *old/local* build's `--install` refused to write settings.json; the
  current build does write it. No change; the report's own note says it was
  merged by hand.
- **BULGU-8 — out of scope.** Claude CLI's project-scope uninstall UX is not
  tezgah.

## Acceptance
- [x] `dsh_cli_args`/`dsh_run` fall back past the missing profile-local CLI.
      Covered indirectly: the DshStatusline tests still pass with a profile-local
      CLI, and the error path is reachable.
- [x] dsh route keys are two rows and read the provider key files.
      `tests/test_setup.py` DshChecks.
- [x] pnpm is in the deps list and ordered before dsh; dry-run and install tests
      assert `install -g pnpm`.
- [x] `which_user` finds `~/.cargo/bin` / `~/.local/bin` off PATH.
      `tests/test_paths.py` UserBinFallback.
- [x] `python3 -m unittest discover -s tests` (128) and `ruff check .` pass;
      `requirements-dev.txt` pins the lint version.

## State
Implemented on branch `plan/003-install-hardening` (commit `2d0f20d`); not merged.
Manual check on this machine: `tezgah-setup --hosts dsh` reports both route rows
ok and `--deps --dry-run` reports all tools present.

## Next
Open the PR, then re-run the reported scenario on a clean machine (npx-only dsh,
no pnpm) and confirm the status line links without manual edits.
