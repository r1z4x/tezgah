# AGENTS.md

Repository notes for coding agents. The always-on tezgah contract (Turkish BLUF
replies, ponytail, code-graph-first) is injected by the harness; this file only
records how to check this repo.

## Docs

`docs/README.md` is the router for how this thing works: architecture, hosts,
contract, gate, evidence, status line, skills, testing, operations, glossary.
Reach a page with `bin/tezgah-docs <words>` (it reads `docs/index.json`) instead
of grepping the tree; a page that is not in the index is not reachable, and
`tests/test_docs.py` keeps the two in step.

## Checks, by tier

The full suite is ~570 s serially and the sharded run is ~105 s; neither belongs
in the edit loop. Three tiers, and the measured wall time of each (2026-10-01):

```sh
# while editing: the modules the change touches (~10-95 s, parallel)
python3 tests/impacted.py --run hooks/tezgah_integrity.py bin/tezgah-task

# before a commit: that set plus the cheap whole-tree checks (~40 s + lint)
python3 -m compileall -q hooks hosts bin statusline.py   # byte-compile every script
ruff check .                                              # lint; config in pyproject.toml
python3 bin/tezgah-docs --citations                       # only when hooks/ or bin/ changed
python3 bin/tezgah-docs --clarity                         # only when docs/ or CHANGELOG.md changed
python3 skills/plan-add/render_table.py --acceptance --strict

# once per final tree, before a merge (~105 s + the e2e scripts)
python3 tests/impacted.py --all                           # the whole suite, sharded
python3 tests/e2e_packaged_install.py                     # install from the built artifact, not the checkout
TEZGAH_E2E_STRICT=1 python3 tests/e2e_plan_flow.py        # the plan and decision rules, in a real project
```

`tests/impacted.py --ref <branch>` maps whatever changed since that ref;
`--list` prints the set without running. A helper under `tests/` (such as
`tests/bash_vectors.py`) runs the test modules that `import` it. A change to
`tests/support.py`, `hooks/tezgah_paths.py` or any path the map does not know
runs the full suite - that is the fail-safe, not a bug. Never run `--all` in the
edit loop, and never twice on one revision.

- `ruff` is installed as a uv tool (`uv tool install ruff`); without it, run the
  same check via `uvx ruff check .`. There is no other linter or type checker.
- CI runs the same checks on the Python matrix in `.github/workflows/ci.yml`,
  whose oldest version is the floor and newest the ceiling. Its ubuntu legs also
  measure the heredoc reader against bash 5.x. An `apps-e2e` job runs the
  app-MCP handshake below on node 20. The citations audit is the check the suite
  is silent about: a green run says nothing about a citation that moved with a
  file. The plan report (`render_table.py --acceptance --strict`) is local only:
  it reads the gitignored `.tezgah/`, which a CI checkout does not have.
- The artifact smoke is the one check that leaves the checkout: it builds
  `dist/tezgah-<version>.tar.gz` (`packaging/build.sh`), unpacks it in a temp
  dir and installs from the unpacked tree, so a broken manifest or a path that
  only resolves in a git checkout fails there and nowhere else. CI runs it as
  its own job on 3.10 and 3.12, and again on `windows-latest`, which is the only
  place the Windows claim is proven. Locally it prints `SKIP: ...` and exits 0
  when `sh`, `tar` or `python3` is missing, so read its output rather than its
  exit code; CI sets `TEZGAH_E2E_STRICT=1`, which turns that skip into a failure
  instead, because a runner that has all three has no reason to skip.

### Plan and decision rules, end to end

`TEZGAH_E2E_STRICT=1 python3 tests/e2e_plan_flow.py` builds a real `git`
repository under tempfile (HOME and `TEZGAH_ROOTS` redirected into it) and runs
the five rules the plan and decision records added, through the CLIs a person
runs: a plan whose Acceptance names no command cannot enter `implementation`
(and `render_table --acceptance --strict` exits 1 on the same item), one
command-bearing item moves the phase and writes `checkpoint:`, a dirty tree
records `pending <sha>` and the commit clears it, an unanswered `spike:` blocks
the move, and an ADR with no `status:` is refused while one with a status is
printed. No model call, no network. It is in the CI `test` job; it prints
`SKIP: ...` and exits 0 when `git` is missing, and 1 under
`TEZGAH_E2E_STRICT=1`, the same contract as the artifact smoke.

### Anti-shortcut guards, mutated

`TEZGAH_E2E_STRICT=1 python3 tests/neuter_matrix.py` clones HEAD once per guard
in the gate's mechanical integrity half, reverts that one guard and runs the
gate's test modules; it fails if a mutant survives or the unmutated control is
red. It reads HEAD, so commit first. Run it after adding or changing a deny rule
(and add the rule's row to `MUTANTS`); CI runs it weekly
(`.github/workflows/neuter.yml`), not per push.

### Shell readers against real bash

`python3 tests/fuzz_shell.py --seed 1 --lines 10000` draws seeded shell lines
from the hand vectors' grammar and runs each in real `bash` with a stub per
program word. It prints, per 10^4 lines, each class where `shell_programs` or
`mask` disagrees with what bash ran. `--js` reads the same lines with the
opencode plugin's ports (`maskText`, `shellPrograms`, through node and
`tests/_fuzz_shell_reader.mjs`) and adds a `js-parity:` class wherever a port
answers differently from the core. `tests/test_fuzz_shell.py` runs 60 lines
in the normal suite and fails if `mask` or its port blanks a program bash ran,
or if a port disagrees with the core; `TEZGAH_FUZZ_LINES=10000` widens the
sample.

### Gate latency

`python3 tests/bench_gate_latency.py [--hooks DIR]` times
`tezgah_gate.decision(..., record=False)` over 200 common calls in a throwaway
HOME and prints p50/p95 in milliseconds; `--hooks` points it at another
revision's exported `hooks/` (`git archive <rev> hooks | tar -x -C /tmp/base`).

### Injected bytes per session

`python3 tests/replay_context.py [--base REV] [--head REV] [--json]` replays the
prompts of the top-level omp and Claude transcripts `bin/tezgah-taste mine`
reads (read-only) through `tezgah_context.context_for` on two revisions, each
exported to a path of the same length (`<scratch>/base/tree`,
`<scratch>/head/tree`: the plugin path is part of the injected text) and run in
a throwaway HOME against one empty project. It prints n sessions,
median/p90/total injected bytes per session per revision and the head/base
ratios. No model call; `tests/test_replay_context.py` runs it on a seeded
two-session fixture.

### App-analysis MCP, end to end

`TEZGAH_E2E_STRICT=1 python3 tests/e2e_analyze_wiring.py` starts the exact
`playwright` and `mobile-mcp` commands `tezgah-setup` writes, completes the MCP
handshake and asserts the tree tools exist - no browser, no device, so it is
deterministic in CI. `TEZGAH_E2E_APPS=1 python3 tests/e2e_analyze_web.py` and
`... e2e_analyze_mobile.py` go further (real navigation / a listed device) and
print `SKIP: ...` when node, a browser build or a device is missing; those two
are opt-in and local only. The shared spec is `hooks/tezgah_apps.py`.

### dsh Web status line, end to end

`python3 tests/e2e_dsh_statusline.py` boots the real `dsh --profile web` UI in
headless Chromium (Playwright), opens a persisted session, and asserts the
tezgah status string renders in the session header with a 200 from
`/api/tezgah.status`. It prints `SKIP: ...` when dsh, Playwright, a Chromium
build, or a persisted session is missing. Opt-in and local only; not part of CI.

### omp status line, end to end

`python3 tests/e2e_omp_statusline.py` starts the real `omp` TUI in a pty with no
prompt (so the run costs no model call), reads its output and asserts the tezgah
marks appear in the footer the extension writes them to. It prints `SKIP: ...`
when the omp binary or the installed extension is missing. Opt-in and local only;
not part of CI.

## Layout

- `hooks/` the shared Python contract and tool gate; `hosts/<name>/` per-host
  adapters and plugin bundles.
- `bin/tezgah-setup` owns install/uninstall and the `--status` report; its
  `host_checks_<host>` functions are the report's source of truth.
- The dsh Web status line plugin lives in `hosts/dsh/statusline/`; `tezgah-setup`
  links it into the dsh web profile and enables its patch row.
