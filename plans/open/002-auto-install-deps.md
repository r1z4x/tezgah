---
id: 002
title: Install missing optional tools automatically during --install
status: open
branch: plan/002-auto-install-deps
pr:
created: 2026-09-15
updated: 2026-09-15
---
## Goal
A fresh `tezgah-setup --install` should not skip the optional tools tezgah uses.
It should install the missing ones with each vendor's own installer, so `orx`
(research routing), `cursor-agent` (the cursor host), and `dsh` (its home
profile) are present and the corresponding rules/hosts arm in the same run.
The user asked for this explicitly after installs on other machines reported
"orx not on PATH", "cursor-agent CLI yok", "~/.dsh yok" as skipped.

## Acceptance
- [x] `--install` installs missing optional tools by default; `--no-deps` skips
      it and says so; `--deps` installs them alone; `--dry-run` previews without
      running. Proof: `tests/test_setup.py` Deps class.
- [x] Each tool uses its verified vendor installer, no sudo:
      orx -> `curl -LsSf https://openresearch.sh/install.sh | sh`;
      cursor-agent -> `curl https://cursor.com/install -fsS | bash`;
      dsh -> `npx -y @deepseek-ai/dsh plugin --profile web --version`
      (initializes `$DSH_HOME`; the first `dsh web` boot finishes it).
- [x] Safety rails: helper preflight (`curl`/`sh`/`bash`/`npx`) aborts with a
      clear message instead of a half-run; idempotent (present tools are
      skipped); PATH is augmented with `~/.local/bin` and `~/.cargo/bin` so a
      just-installed tool is found in the same run; the command is logged to
      `~/.config/tezgah/install.log`; Windows prints manual steps.
- [x] Tests never hit the network: `tests/test_setup.py` SetupBase sets
      `TEZGAH_NO_DEPS=1`, which the code honours like `--no-deps`.
- [x] `python3 -m unittest discover -s tests` (106) and `ruff check .` pass.

## State
Implemented on branch `plan/002-auto-install-deps` (commit `0c1c092`); not merged.
- `bin/tezgah-setup`: a `DEPS` table (name, probe, needed helpers, vendor
  command, why), `install_deps()`, `_augment_path()`, `_dep_log()`; `--install`
  runs deps before arming and re-detects hosts when `--hosts` was not given, so
  a just-installed `cursor-agent`/`dsh` is armed in the same pass. New flags
  `--deps`, `--no-deps`, `--dry-run`.
- `bin/tezgah-dsh`: falls back to `npx -y @deepseek-ai/dsh "$@"` when the local
  profile tree is missing, so the launcher works on a machine that only ran the
  npx init.
- README install section and command table updated.

Consult (Gemini 2.5 Pro + Grok 4.3) both argued against auto-install in
`--install` and for an opt-in `--deps` only (curl|sh supply-chain risk,
non-interactive safety, PATH). The user explicitly overrode this ("otomatik
kurulum yapmamız lazım"), so the result is auto-by-default with the safety rails
above and an explicit `--no-deps`/`TEZGAH_NO_DEPS` escape; the consult's concerns
are recorded here rather than ignored.

## Next
Open the PR, then verify on a clean machine (no orx/cursor-agent/~/.dsh) that a
single `--install` installs all three and arms orx, cursor and dsh in one run.
