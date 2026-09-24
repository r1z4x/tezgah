# Testing: the checks, the probes, the e2e scripts

This page is for a maintainer adding or changing a test, or who has just changed
a hook, a CLI or a status line and wants to know what will notice. It records the
checks that gate a commit, the shape of the suite, the helpers to reach for, and
the rules a new test must satisfy.

## The three checks

```sh
python3 -m compileall -q hooks hosts bin statusline.py   # byte-compile every script
python3 -m unittest discover -s tests                     # stdlib test suite
ruff check .                                              # lint; config in pyproject.toml
```

[`AGENTS.md`](../AGENTS.md) gives them in that order (`AGENTS.md:18-20`), and
[`CONTRIBUTING.md`](../CONTRIBUTING.md) repeats the same three before a pull
request (`CONTRIBUTING.md:13-19`).

| Check | What it catches that the other two do not |
|---|---|
| `compileall` | A syntax error in any `.py` under `hooks/` and `hosts/`, plus `statusline.py`, without running a line of it and with no environment set up. The `bin/` CLIs are Python sources with no `.py` suffix, so only running one compiles it (`test_setup.py:83`). |
| `unittest` | Behaviour: what a hook answers, what the [gate](glossary.md#gate) denies, what reaches the [ledger](glossary.md#ledger), what a status line renders. |
| `ruff` | Lint only, with the rule set pinned in `pyproject.toml:12-14` (`E4`, `E7`, `E9`, `F`; `E501` ignored). The pin exists because newer ruff releases ship a broader default and would otherwise change `ruff check .` in CI (`pyproject.toml:10-11`). One pre-existing script is exempted per-file in `pyproject.toml:19-20`. |

`ruff` is not vendored: install it as a uv tool, run `uvx ruff check .` without
installing it, or use the version CI installs from `requirements-dev.txt:3`
(`ruff==0.16.7`). There is no other linter and no type checker
(`AGENTS.md:27`).

## Continuous integration

`.github/workflows/ci.yml` runs four jobs:

- `test` (`ci.yml:12-37`) on Python 3.10 and 3.12 - 3.10 is the floor the project
  supports, and the byte-compile step is what exercises it rather than asserts
  it: the same three commands, with `-v` on the suite and ruff installed from
  `requirements-dev.txt` (`ci.yml:30-31`).
- `apps-e2e` (`ci.yml:39-56`) on Python 3.12 and node 20: one step,
  `TEZGAH_E2E_STRICT=1 python3 tests/e2e_analyze_wiring.py`. It completes the
  app-MCP handshake only - no browser, no device - so it stays deterministic;
  strict mode makes a server that cannot start a failure rather than a skip, so
  a broken wire cannot hide behind a skip (`e2e_analyze_wiring.py:4-12`).
- `artifact-install` (`ci.yml:58-95`) on Python 3.10 and 3.12: builds the
  tarball, installs from it under a temp prefix, and runs the artifact smoke on
  the installed tree instead of the checkout.
- `artifact-install-windows` (`ci.yml:97-143`) on `windows-latest`: the same
  build, install and smoke through `packaging/install.ps1` - the twin a Windows
  user runs - so it is the only place the Windows claim is proven.

The dsh and omp status-line scripts are not in CI.

## How the suite is shaped

Every test that exercises a hook runs it in a subprocess with an environment the
test built: a throwaway `HOME`, `TEZGAH_ROOTS` under tempfile, `PYTHONPATH` at
`hooks/`, so the real `~/.claude`, `~/.config/tezgah` and `~/.cache` are never
read or written (`tests/support.py:3-5`). Four kinds of test live under `tests/`,
on top of that support layer.

**Unit tests over a module.** `tests/test_paths.py:15-16` imports
`hooks/tezgah_paths.py` directly and drives it in-process; where a temp HOME must
matter it patches the module's own constants with
`unittest.mock.patch.multiple` (`test_paths.py:134-137`). Reach for this only for
pure logic or for concurrency, which a subprocess cannot express.

**Subprocess tests with a temp HOME.** The default. `TempHome` gives the test a
fresh `home` and a `roots` dir, `env()`, `make_repo()`, `config()` and `touch()`
(`support.py:87-113`); the hook or CLI is then run with `run`/`run_json`
(`support.py:73-84`). `tests/test_codex_hook.py:9-16` is the smallest example.

**Probes.** `tests/_probe_*.py` are tiny scripts that call one function of a
shared module and print its result as JSON, so the call happens in a process
whose `HOME` and `TEZGAH_ROOTS` are already the test's. They exist because those
modules derive paths from `HOME` at import time - `hooks/tezgah_paths.py:18-31`
builds `CONFIG`, `CACHE` and `DEFAULT_ROOT` at module level - so importing them
into the test process would answer about the developer's real machine.

| Probe | Command | Entry points |
|---|---|---|
| `tests/_probe_paths.py` | argv op, no payload (`:11`) | `roots`, `root_for`, `off`, `default_root`, `config`, `off_dirs`, `cache_dir`, `which_user`, `orx_bin`, `have_consult_key`, `have_typesafe_key`, `codegraph_bin` |
| `tests/_probe_context.py` | JSON on stdin, `{"fn": ...}` (`:4-5`) | `context_for`, `health_lines`, `health_segments`, `record` |
| `tests/_probe_integrity.py` | JSON on stdin (`:4-6`) | `note`, `note_tool`, `note_turn`, `kinds`, `events`, `prior_calls`, `counters`, `shortcut_command`, `shortcut_edit`, `stop_reason`, `verify_command` |
| `tests/_probe_agents.py` | JSON on stdin (`:3-4`) | `sync_root`, `opencode_json`, `cleanup`, `detect` |
| `tests/_probe_gate.py` | JSON on stdin (`:4-8`) | the shared gate `decision(tool, input, cwd, session_id)`; `capture_log` plants a stub `tezgah_snapshot` in `sys.modules`, so the snapshot call site is pinned whether or not that module has landed |

A probe is invoked through `support.run`/`run_json` with its path constant
(`support.PROBE_PATHS`, `support.PROBE_CONTEXT`, ... in `support.py:19-23`), e.g.
`run_json([support.PROBE_CONTEXT], {"fn": "health_lines", "cwd": repo},
env=self.env())` (`test_context.py:82-84`). Nothing in `tests/_probe_*.py` is
collected: the name does not match discovery's `test*.py` pattern and no probe
defines a `TestCase`.

**End-to-end scripts.** `tests/e2e_*.py` are not collected either
(`e2e_omp_statusline.py:13-18`) and are run by hand. They exit 0 on `PASS` or
`SKIP` and 1 only on a real failure (`e2e_dsh_statusline.py:137-140`).

| Script | Needs | Prints `SKIP` when |
|---|---|---|
| `e2e_analyze_wiring.py` | node (`npx`) (`:39-40`) | npx is absent; a server that cannot start is a skip, or a failure under `TEZGAH_E2E_STRICT=1` (`:10-12`) |
| `e2e_analyze_web.py` | `TEZGAH_E2E_APPS=1`, npx, a Playwright browser build (`:9-13`) | the opt-in env var, npx, the server start or the browser build is missing |
| `e2e_analyze_mobile.py` | `TEZGAH_E2E_APPS=1`, npx, a booted simulator or emulator (`:9-14`) | the same, or no running device |
| `e2e_dsh_statusline.py` | the `dsh` binary, Playwright, a Chromium build, a persisted session (`:90-138`) | any of them is missing (`:93`, `:97`, `:108`, `:118`) |
| `e2e_omp_statusline.py` | the `omp` binary and the extension `tezgah-setup` installs, plus a pty (`:101-108`) | either is missing (`:103-107`) |
| `e2e_docker_cycle.py` | a running Docker daemon; the image is `python:3.12-slim` unless `TEZGAH_E2E_DOCKER_IMAGE` says otherwise (`:27-28`) | docker or its daemon is missing (`:53-60`) |

`SKIP` is the designed answer, not a hideout: these scripts test that a wire or a
render works, and a missing prerequisite says nothing about the repository. Two
are opt-in behind `TEZGAH_E2E_APPS=1` because they do real work, so they never run
by surprise (`e2e_analyze_web.py:33-35`), and the omp script starts the TUI with
no prompt, so the run costs no model call (`e2e_omp_statusline.py:2-4`).

## The rules a new test must satisfy

**It must fail on a plausible bug.** Where the repo turns a behaviour into a
string, the pin *is* the contract: the exact status segment
(`test_statusline.py:8-17`, compared at `:37-43`), a `tezgah-setup --status` row
label (`test_setup.py:1114-1120`), the opencode router line a skill's trigger
reaches (`test_setup.py:589-609`), the kill-switch labels whose deletion must
fail the test rather than silently disarm a rule (`test_context.py:439-441`). An
intentional change updates the pin in the same commit; deleting the test because
it is now red is the failure mode these pins exist to catch.

**Assert observable behaviour, not wiring, defaults or source text.** A test that
reads a file to check a copy of an implementation, or that asserts an internal
call was forwarded, dies at the first refactor. Where text is asserted it is
output the user or a host sees. The suite's own comments say the rule twice:
pin the behaviour, not one phrasing of it (`test_skills.py:79-81`), and pin a
rule on a synthetic input, not only on the shipped pair
(`test_setup.py:539-542`).

**Stay deterministic and isolated.** A temp HOME is the mechanism
(`support.py:3-5`); `base_env` also points `TEZGAH_CODEGRAPH_BIN` and `TEZGAH_ORX_BIN`
at paths that do not exist, so the machine's own graph binary and orx cannot leak
into an assertion (`support.py:49-53`). The installer suite sets
`TEZGAH_NO_DEPS=1` so `--install` fetches nothing (`test_setup.py:57-59`). No test
reaches the network: where a provider is needed it is a loopback stub
(`test_providers.py:106-108`, `test_consult_arena.py:72`).

**Run inside the default discovery.** A new test is `tests/test_<thing>.py`, a
`unittest.TestCase`, and passes under
`python3 -m unittest discover -s tests` from the repository root. A check that
cannot run everywhere is not a test: it goes to `e2e_*.py` (needs a binary,
a browser or a device) or to a `_probe_*.py` helper the tests call.

## What the suite deliberately does not do

- **No coverage target and no coverage tool.** `requirements-dev.txt` pins ruff
  and nothing else (`requirements-dev.txt:1-3`); no coverage tool is named there
  or in `pyproject.toml`. A line count is not a check.
- **No fixtures framework.** Stdlib `unittest` only (`CONTRIBUTING.md:26`);
  `tests/support.py` is the whole fixture layer, with no `conftest.py`.
- **No network.** Loopback stubs only, as above.
- **Two e2e scripts stay opt-in and local**: `e2e_analyze_web.py` and
  `e2e_analyze_mobile.py`, behind `TEZGAH_E2E_APPS=1`, with the wiring handshake
  as their CI substitute (`AGENTS.md:45-48`).

## Adding a test

**For a hook.** Subclass `TempHome`, make a repo, run the adapter with a payload
and `self.env()`, assert on its JSON output:

1. `from support import TempHome, run_json` and `import support` (`test_codex_hook.py:1-6`).
2. `repo = self.make_repo()`; seed any state with `self.touch(...)` / `self.config({...})`.
3. `out, proc = run_json([support.CODEX_HOOK], {"hook_event_name": "Stop", "cwd": repo, "session_id": "s"}, env=self.env())`.
4. `self.assertEqual(proc.returncode, 0, proc.stderr)` first, then assert the field you changed.
   Which host lives where: `support.py:24-33` (`CODEX_HOOK`, `CURSOR_HOOK`, `OMP_HOOK`, `STATUSLINE`).
5. Reading back what the hook wrote? Use the ledger probe, not the file path
   (`test_codex_hook.py:82-86` uses `support.PROBE_INTEGRITY` with `{"fn": "kinds"}`).

**For a CLI.** Run it with a temp environment and assert on its stdout or on the
tree it left. A `bin/` CLI is run as a subprocess with `sys.executable` and an
explicit environment (`test_setup.py:78-85`); `SetupBase` in
`test_setup.py:41-95` is the worked example for `bin/tezgah-setup` (fake host
dirs, `TEZGAH_NO_DEPS=1`, stdin always a pipe so the wizard cannot block on a
real terminal). For a plain CLI,
`run([support.STATUSLINE], {"cwd": repo}, env=self.envv)` is enough
(`test_statusline.py:37-39`).

**For a status-line change.**

1. Change the [mark](glossary.md#mark) in `hooks/tezgah_context.py` (the shared
   builder) or in the host surface named on [status-line](status-line.md).
2. Update the pinned segment in `tests/test_statusline.py:8-17` - both the
   in-roots and off-roots constants - and re-run
   `python3 -m unittest discover -s tests -p 'test_statusline.py'`.
3. If the colour or the state changed, extend the `NO_COLOR` / `TEZGAH_STATUS_COLOR`
   cases (`test_statusline.py:118-134`) rather than adding a new file.
4. The shared builder is covered through the context probe
   (`test_context.py:82-84`, `:86-96`); a mark that flips on an event belongs there.
5. Only the drawing is left to the real surface, and that is
   `e2e_omp_statusline.py` / `e2e_dsh_statusline.py`, run by hand.

## Source of truth

- `AGENTS.md`
- `CONTRIBUTING.md`
- `.github/workflows/ci.yml`
- `pyproject.toml`, `requirements-dev.txt`
- `tests/support.py`
- `tests/_probe_paths.py`, `tests/_probe_gate.py`, `tests/_probe_context.py`,
  `tests/_probe_integrity.py`, `tests/_probe_agents.py`
- `tests/e2e_analyze_wiring.py`, `tests/e2e_analyze_web.py`,
  `tests/e2e_analyze_mobile.py`, `tests/e2e_dsh_statusline.py`,
  `tests/e2e_omp_statusline.py`
- `tests/test_statusline.py`, `tests/test_codex_hook.py`, `tests/test_setup.py`,
  `tests/test_context.py`, `tests/test_paths.py`
