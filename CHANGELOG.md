# Changelog

All notable changes to this project are documented here. The format is based on
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project
adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- **Opt-in taste capture, and a miner for the corrections already on disk.**
  Arm it with `~/.config/tezgah/taste-on`. A repository with a `.tezgah/`
  directory then gets `.tezgah/taste/signals.jsonl`. It holds each prompt,
  each landed edit's old and new text, and a snapshot of the bytes the write
  left. Redaction and a length cut apply to the text. A `.no-taste` mark turns it off per
  repository. `tezgah-taste mine` counts and extracts the prompts that
  followed a writing turn in omp and Claude transcripts. `tezgah-taste
  measure` and `tezgah-taste rate` sort them with the judge seam into
  preference, defect or none. This phase learns and injects nothing.

- **A wider citation audit.** `bin/tezgah-docs --citations` now judges a bare file
  name and a symbol written after its citation. It also reads the comments and docstrings of the Python code. A
  `path:N` it cannot read counts as unjudged. The tree reads 512 judged and 1018
  unjudged, up from 429 judged. A file with more unjudged citations than
  `docs/citations-baseline.json` fails the check, and `--citations --update` rewrites
  that file. The same pass reads all ten Stop classes by AST. It also checks the
  gate's rule order and switches, the judge's callers and the kill-switch names.
  `tests/neuter_matrix.py` generates one mutant per gate rule.

### Fixed

- **Codex write rows know where they ran.** The Codex hook was the one host
  that gave the ledger no cwd. Its write rows carried no workspace, and a
  relative path resolved against the hook process instead of the repository.

- **Docs that disagreed with the code.** `docs/gate.md` listed Secret before Workspace,
  and `decision` checks them the other way. The Language section did not name `lang-off`.
  `docs/judge.md` counted four callers, and `bin/tezgah-taste` is the fifth. The READMEs
  said fourteen kill switches. CORE names sixteen. Forty-one bare-file citations, six in
  code comments, and the repeat-guard anchor in "Adding a rule" pointed at the wrong
  lines. An uninstall now also sweeps `docs-judge-off`, `triage-off`, `update-check-off`
  and `workspace-off` from `~/.claude`.

## [0.1.2] - 2026-10-04

### Added

- **The status line says when a newer release is out, and `tezgah update`
  takes it.** A `↑X.Y.Z` chip sits beside the logo on every surface. A redraw
  reads a cached answer, and a detached check refreshes it at most once a day.
  `tezgah update [--dry-run]` updates through the channel the install came
  from (release prefix, Homebrew, npm or git) and re-arms the hosts. The
  `update-check-off` switch turns the check and the chip off.

### Fixed

- **The Homebrew formula runs.** It copied `tezgah-setup` out of the tree, so
  the copy could not find `hooks/` and died on import. It now links into the
  installed tree, and also installs the command as `tezgah`.

## [0.1.1] - 2026-10-04

### Added

- First public release.

[Unreleased]: https://github.com/r1z4x/tezgah/compare/v0.1.2...HEAD
[0.1.2]: https://github.com/r1z4x/tezgah/releases/tag/v0.1.2
[0.1.1]: https://github.com/r1z4x/tezgah/releases/tag/v0.1.1
