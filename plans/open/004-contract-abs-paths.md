---
id: 004
title: Inject stable absolute CLI paths into the contract text
status: open
branch: plan/004-contract-abs-paths
pr:
created: 2026-09-15
updated: 2026-09-15
---
## Goal
The injected contract called tezgah's CLIs by bare/relative name (`bin/consult`,
`orx`). In the non-interactive session shell the cwd is not the tezgah checkout,
so `bin/` does not resolve, and `~/.cargo/bin` is not on PATH, so `orx` does not
either: the agent saw "not found". Fix the root cause in the injected text with
stable absolute paths, not by mutating env/PATH - which also fits tezgah's
"never edit the user's rc files" rule.

## Acceptance
- [x] `{ORX_BIN}` is a render placeholder: `hooks/tezgah_context.render()` fills
      it with `orx_bin()` (which now also checks `~/.cargo/bin`) or the bare
      `orx` when the CLI is absent, preserving the "not installed" behaviour.
- [x] `hooks/tezgah_policy.py` CORE, REMINDER and RESEARCH use `{CONSULT_BIN}` /
      `{ORX_BIN}` instead of bare `bin/consult` / `orx`; the placeholder list in
      the module docstring documents `{ORX_BIN}`.
- [x] `skills/tezgah-contract/SKILL.md` is static (not rendered), so it names
      `~/.config/tezgah/bin/consult` / `codegen` and resolves orx as `orx` on
      PATH else `~/.cargo/bin/orx`.
- [x] README command references updated to the stable paths.
- [x] No bare command reference remains and `{ORX_BIN}` is always substituted.
- [x] `python3 -m unittest discover -s tests` (128) and `ruff check .` pass.

## State
Implemented on branch `plan/004-contract-abs-paths` (commit `a47b649`); not merged.
- Root cause confirmed by two independent models (gemini-2.5-pro, grok-4.3):
  the fix belongs in the injected text as absolute paths.
- Verified by rendering CORE/RESEARCH/REMINDER in-process and by generating
  `opencode-contract.md` in a throwaway HOME: zero bare `bin/consult` /
  `bin/codegen` / `through the orx CLI`, the absolute consult path is present,
  and orx renders as `/Users/rizax/.cargo/bin/orx`.
- Note on the report's check: `grep -c 'bin/consult'` also matches the tail of
  the absolute path `…/tezgah/bin/consult`, so it is not 0 even when correct;
  the precise check is a bare occurrence (`(?<!tezgah/)bin/consult`), which is 0.

## Next
Open the PR and merge, then re-run `tezgah-setup --install` on the reported
machine to regenerate `opencode-contract.md` with the absolute paths.
