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

### Fixed

- **A host config the installer cannot parse is left alone.** Seven install
  steps read a host's JSON config and then rewrote it. They cover Codex and
  Cursor `hooks.json`, opencode's `opencode.json` and `tui.json`, Cursor's
  `mcp.json` and `cli-config.json`, and omp's `mcp.json`. A trailing comma, a
  `//` comment or a top level that is not an object made the installer write
  its default over the file. `--install` now names that file and the parse
  error, leaves its bytes alone and exits 1.
- **Every changing write keeps its own backup.** A write that changes a file
  copies it to `<file>.<timestamp>.tezgah-bak` first. Before, only the first
  write left a backup. The first copy is always kept, beside the newest four.
  A full uninstall removes the timestamped backups of tezgah's own state too.
- **`--install` fails when a planned host is not armed.** The run printed MISS
  under a host and still exited 0. Now it exits 1 and names the host and row
  under `not armed:`. Only the arming rows count: hooks wired, the contract
  current, and omp's extension row where an omp CLI exists. Codex
  `hooks trusted`, the provider keys and Claude's plugin copy stay out,
  because a correct fresh install leaves them MISS.
- **Codex write rows know where they ran.** The Codex hook was the one host
  that gave the ledger no cwd. Its write rows carried no workspace, and a
  relative path resolved against the hook process instead of the repository.

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
