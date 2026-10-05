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

- **The Stop hook now records the reply after a block.** On Claude, Codex and
  omp the hook skipped the reply that answers a block. It now judges that
  reply in record-only mode and writes one `after_block` row. The row says
  whether the rule would refuse the reply, let a claim through, or found no
  claim. It never blocks a second time and never counts as a claim or as a
  reply. A block from another Stop hook leaves no row. Cursor stays unwired:
  nobody has checked its stop payload yet.

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
  write left a backup. The oldest timestamped copy is always kept, beside the
  newest four. A bare `<file>.tezgah-bak` from an older release stays as is.
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
- **`tezgah-capture` no longer counts as a read of the screen.** It is the
  pre-write file snapshot CLI. A turn could end on a done claim because this
  run stood in for a screen proof or for a passing check.
- **dsh has no Stop rule.** Its bridge drops every call's outcome, so no check
  there can show a pass. The rule could only refuse honest work there. The
  Stop entry leaves `hosts/dsh/hooks.json` until the bridge carries outcomes.

- **A release publishes only after CI passed on its commit.** `release.yml`
  now runs `ci.yml` as its `ci` job. `npm-publish` and `brew-formula` wait for
  it. v0.1.2 reached npm and brew while its own CI run failed.
- **A test run that runs nothing no longer passes.** A docs-only
  `tests/impacted.py --run` matched no test file and passed with 0 tests. It
  now runs the docs modules. A run where nothing maps, and a `--ref` with no
  change, exit 5. It prints a failed module's log, not only its path.
- **The suite stays out of the real ledger.** Importing `tests/support.py`
  gives the process a temp HOME and drops `TEZGAH_SESSION`. `tests/test_models.py`
  does the same for the `tezgah-route` runs it starts.
- **CI shows what it checks.** The plan report step read the gitignored
  `.tezgah/` and could never fail, so it left CI. It stays a local check. The
  docs now take the CI version list from `.github/workflows/ci.yml`.
  `test-sharded` runs `tests/impacted.py --all` on 3.10 and 3.14 as a
  four-week shadow of the four-version matrix. No matrix cancels its other
  legs on a failure.
- **`bin/tezgah-mcp.py` exists**, the `.py` twin every other Python entry
  point in `bin/` has.

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
