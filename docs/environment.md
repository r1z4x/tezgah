# Environment variables

Every environment variable tezgah reads, in one table per concern: what reads it,
what it defaults to, and what setting it changes. For someone pinning an install
in CI, repointing an endpoint in a test, or wondering why a hook ignores the
Python on PATH. A variable not on this page is not read by tezgah; one read by a
host and only passed through (such as `HOME` or `PATH`) is left out.

Nothing loads a `.env` file: a variable reaches tezgah only through the
environment of the process that started it - the shell, the host, or the host's
hook runner. A hook's environment is fixed when the host starts it, so a change
takes effect in the next session, not the running one.

The per-flag installer reference is in [operations](operations.md#installer-flags);
the kill switches are files, not variables, and live in
[contract](contract.md).

## Install, upgrade and packaging

| Variable | Read by | Default | Effect |
|---|---|---|---|
| `TEZGAH_PREFIX` | `packaging/install.sh:26`, `packaging/upgrade.sh`, `packaging/install.ps1`, `bin/tezgah-setup::default_prefix` | `$XDG_DATA_HOME/tezgah`, else `%LOCALAPPDATA%\tezgah` on Windows, else `~/.local/share/tezgah` | Where the artifact install unpacks its versions and the `current` link; `tezgah-setup` treats it as the install prefix. |
| `TEZGAH_VERSION` | `packaging/install.sh`, `packaging/upgrade.sh`, `packaging/install.ps1`, `packaging/build.sh:70` | the newest GitHub release; `build.sh` falls back to `VERSION`/the CHANGELOG | The version to install, or the version `build.sh` stamps when `--version` is not given. |
| `TEZGAH_REPO` | `packaging/install.sh:12`, `packaging/upgrade.sh`, `packaging/install.ps1` | `r1z4x/tezgah` | The GitHub repository releases are fetched from. |
| `TEZGAH_UPDATE_URL` | `hooks/tezgah_update.py` | `https://github.com/<TEZGAH_REPO>/releases/latest` | Where the daily release check reads the newest tag: from the redirect, or from a JSON body's `tag_name`. Tests point it at a `file://` fixture. |
| `TEZGAH_UPDATE_CHECK` | `hooks/tezgah_update.py` | unset | `0` turns off the update chip and the daily check. The test suite sets it, so no test reaches the network. |
| `TEZGAH_DIST` | `packaging/upgrade.sh:74`, `packaging/install.ps1` | unset: the release URL | A directory holding `tezgah-<V>.tar.gz` and its `.sha256` (what `build.sh --out` writes) used instead of the release download; CI exercises the real fetch-verify-unpack path with it. |
| `TEZGAH_GH` | `packaging/upgrade.sh` | `gh` on PATH | The `gh` that checks the tarball's build provenance (`gh attestation verify`). A path that does not exist reads as no `gh`: the upgrade prints `provenance not checked` and goes on. Tests point it at a stand-in. |
| `TEZGAH_NO_DEPS` | `bin/tezgah-setup::main` | unset | Any value but empty or `0` is `--no-deps`: the optional tools (codegraph, orx, host CLIs) are not installed. |
| `TEZGAH_NO_SYMLINK` | `bin/tezgah-setup::symlinks_refused` | unset | Any value but empty or `0` writes the copy layout a machine without symlinks gets, on a machine that has them. |
| `TEZGAH_PYTHON` | `hooks/tezgah_paths.py::python_cmd`, `bin/tezgah.js`, `bin/tezgah-dsh.cmd`, `hooks/hooks.json`, `hosts/*/hooks.json`, `hosts/omp/tezgah-hook.ts.in`, `hosts/opencode/plugins/tezgah.js`, `packaging/build.sh` | this process's interpreter, then `python3`/`python`/`py` on PATH | The interpreter every host hook and the npm shim start; pin it when the right Python is not first on PATH. |

## Where tezgah and the hosts keep state

| Variable | Read by | Default | Effect |
|---|---|---|---|
| `TEZGAH_ROOTS` | `hooks/tezgah_paths.py::roots`, `bin/tezgah-setup`, `hosts/opencode/plugins/tezgah.js` | `roots` in `~/.config/tezgah/config.json`, else `~/Projects` | The directories tezgah is armed over, `os.pathsep`-separated (`;` on Windows, the opencode plugin included); it outranks the config file. |
| `XDG_CONFIG_HOME` | `hooks/tezgah_paths.py::CONFIG_DIR`, `bin/tezgah-doctor`, `bin/tezgah-dsh.cmd`, `hosts/opencode/plugins/tezgah.js` | `~/.config` | Parent of tezgah's config dir (kill switches, `bin/` links, config) and of opencode's. |
| `XDG_DATA_HOME` | `bin/tezgah-setup::default_prefix`, `packaging/install.sh`, `packaging/upgrade.sh` | `~/.local/share` | Parent of the default install prefix. |
| `XDG_CACHE_HOME` | `hooks/tezgah_apps.py::ARTIFACTS` | `~/.cache` | Parent of the app-analysis artifact dir. |
| `TEZGAH_DEBUG` | `hooks/tezgah_guard.py` | unset | `1` makes every hook process append one line to `<cache>/debug.log` (host, script, each guarded call's outcome or exception class, elapsed ms; no prompt or tool text), created 0600 and swept by `tezgah-doctor --clean`. Off, it costs one environment read. |
| `TEZGAH_FALLBACK_CACHE` | `hooks/tezgah_paths.py::fallback_cache` | `<tempdir>/tezgah` | The cache a sandboxed hook writes when its normal cache dir is denied; a test knob. |
| `TEZGAH_ARTIFACTS` | `hooks/tezgah_apps.py::ARTIFACTS` | `$XDG_CACHE_HOME/tezgah/apps` | Where `analyze-app` screenshots, traces and tree dumps land. |
| `TEZGAH_NO_EXCLUDE` | `hooks/tezgah_agents.py::ensure_exclude` | unset | `1` stops tezgah adding its generated-agent dirs to the repository's `.git/info/exclude`. |
| `CODEX_HOME` | `hooks/tezgah_paths.py::HOST_DIRS` | `~/.codex` | The Codex home tezgah installs into and checks; the same variable Codex itself reads. |
| `DSH_HOME` | `hooks/tezgah_paths.py::HOST_DIRS`, `bin/tezgah-dsh`, `bin/tezgah-dsh.cmd` | `~/.dsh` | The dsh home tezgah installs into, and where `tezgah-dsh` looks for the CLI. |
| `TEZGAH_OPENCODE_DATA` | `bin/tezgah-setup::OPENCODE_DATA`, `bin/tezgah-doctor` | `~/.local/share/opencode` | opencode's data dir: its session database for `tezgah-doctor` and the installer. |

## Which binary runs

| Variable | Read by | Default | Effect |
|---|---|---|---|
| `TEZGAH_CODEGRAPH_BIN` | `hooks/tezgah_paths.py::codegraph_bin` | the config file, then `codegraph` on PATH | The codegraph executable the index and the graph marks use. |
| `TEZGAH_ORX_BIN` | `hooks/tezgah_paths.py::orx_bin` | `orx` on PATH | The OpenResearch CLI the research rule routes to. |
| `TEZGAH_OMP_BIN` | `hooks/tezgah_paths.py::omp_bin` | `omp` on PATH | The omp binary the installer, the model table and consult's session-model lookup run. |
| `TEZGAH_CLAUDE_BIN` | `claude_bin`, `hooks/tezgah_paths.py::claude_bin` | `claude` on PATH | The Claude Code CLI `--install` registers the plugin with (`claude plugin`); the test suite points it at a path that does not exist. |
| `TEZGAH_DSH_BIN` | `bin/tezgah-setup::reconcile_json_servers` | the profile-local entry, then `bin/tezgah-dsh`, then npx | How the installer invokes the dsh CLI. |
| `TEZGAH_INDEX_BIN` | `bin/tezgah-dsh:19`, `bin/tezgah-dsh.cmd` | `~/.config/tezgah/bin/tezgah-index` | The index worker `tezgah-dsh` warms before it starts dsh. |
| `TEZGAH_STATUS_BIN` | `hosts/dsh/statusline/lib/index.js:24`, `hosts/opencode/tui/tezgah-tui.tsx` | `~/.config/tezgah/bin/tezgah-status` | The status renderer the dsh status line and the opencode TUI call. |
| `TEZGAH_CONSULT_CLIS` | `hooks/tezgah_paths.py::consult_options` | unset: every agent CLI on PATH counts | Comma list of the agent CLIs that may count as consult members (empty: none); pins the answer in tests and CI. |

## Index worker

| Variable | Read by | Default | Effect |
|---|---|---|---|
| `TEZGAH_INDEX_TIMEOUT` | `hooks/tezgah_index.py::RUN_TIMEOUT` | `600` (seconds) | How long one index attempt may run before its process group is killed. Must be a number. |
| `TEZGAH_INDEX_RETRIES` | `hooks/tezgah_index.py::RETRIES` | `5` | Attempts the detached index worker makes. Must be an integer. |
| `TEZGAH_INDEX_RETRY_DELAY` | `hooks/tezgah_index.py::DELAY` | `3` (seconds) | The pause between attempts. Must be a number. |

## Model credentials and endpoints

| Variable | Read by | Default | Effect |
|---|---|---|---|
| `TYPESAFE_API_KEY` | `hooks/tezgah_judge.py::key`, `hooks/tezgah_paths.py` | `~/.config/typesafe/key` | The judgement seam's first credential; omp also reads it for its own judge. |
| `OPENROUTER_API_KEY` | `hooks/tezgah_judge.py::openrouter_key`, `bin/consult`, `bin/codegen`, `hooks/tezgah_models.py` | `~/.config/openrouter/key` | The seam's chat fallback, consult's and codegen's `openrouter` provider, and omp's `any` family. |
| `DEEPSEEK_API_KEY`, `INCEPTION_API_KEY` | `bin/consult`, `bin/codegen`, `hooks/tezgah_replay.py::label_model` | `~/.config/deepseek/key`, `~/.config/inception/key` | The `deepseek` and `inception` providers of consult and codegen; `DEEPSEEK_API_KEY` alone is also the replay sheet's `--provider deepseek` rater. |
| `ANTHROPIC_OAUTH_TOKEN`, `ANTHROPIC_API_KEY`, `ZAI_API_KEY` | `hooks/tezgah_models.py::OMP_AUTH` | omp's own auth store | Read as presence only: whether omp can run the `anthropic` or `zai` model family, so the model table can pick a row omp will run. |
| `TEZGAH_TYPESAFE_URL` | `hooks/tezgah_judge.py::endpoint` | `https://api.typesafe.ai/v1/systemone` | Repoints the seam's TypeSafe endpoint (tests). Plain `http` is refused unless the host is this machine; a cross-host redirect is refused. |
| `TEZGAH_OPENROUTER_URL` | `hooks/tezgah_judge.py::openrouter_url` | OpenRouter's chat-completions URL | Repoints the seam's chat fallback (tests). Plain `http` is refused unless the host is this machine. |
| `TEZGAH_DEEPSEEK_URL` | `hooks/tezgah_replay.py::_deepseek` | `https://api.deepseek.com/chat/completions` | Repoints the replay sheet's `--provider deepseek` rater (tests). Plain `http` is refused unless the host is this machine. |
| `TEZGAH_JUDGE_MODEL` | `hooks/tezgah_judge.py::fallback_model` | the cheap `any` row of the models table | The model the seam's chat fallback asks. |

## consult and codegen

| Variable | Read by | Default | Effect |
|---|---|---|---|
| `CONSULT_URL` | `bin/consult::endpoint` | the provider's URL | Repoints every HTTP member. Plain `http` is refused unless the host is this machine (failure class `plain-http`); the bearer token is dropped on a redirect to another host. |
| `CONSULT_MODELS` | `bin/consult::defaults` | the provider's default list | Comma list of `openrouter` models for the panel. |
| `CONSULT_JUDGE` | `bin/consult::main` | the recorded referee, else an available member outside the panel | The member that referees, after `--judge`. With none outside the panel a panel member referees and the run prints a note. |
| `CONSULT_SEED` | `bin/consult::referee_packet` | unset (a fresh shuffle) | Fixes the shuffled order of the anonymised answers the referee reads (tests). |
| `CONSULT_SESSION_MODEL` | `bin/consult::session_model` | omp's own record of the session model, read only on omp (`OMPCODE`) | The model this session runs on, so the panel skips it. |
| `OMPCODE`, `CLAUDECODE` | `bin/consult::own_cli` | set by the host | Names the calling host's own CLI, so consult does not ask the session to second-guess itself (omp sets both; `OMPCODE` wins). `OMPCODE` is also what lets consult read omp's session model. |
| `CODEGEN_URL` | `bin/codegen::ask` | the provider's URL | Repoints codegen's endpoint. Plain `http` is refused unless the host is this machine (`127.0.0.1`, `localhost`); a redirect to another host is refused. |
| `CODEGEN_MODEL` | `bin/codegen::MODEL` | the cheap `any` row of the models table | The model codegen drafts with. |

## Status line

| Variable | Read by | Default | Effect |
|---|---|---|---|
| `NO_COLOR` | `hooks/tezgah_context.py::color_default`, `hosts/omp/tezgah-hook.ts.in` | unset | Any value renders the status line without ANSI colour. |
| `TEZGAH_STATUS_COLOR` | `hooks/tezgah_context.py::color_default`, `hosts/omp/tezgah-hook.ts.in` | unset | `0` is the same opt-out as `NO_COLOR`, for tezgah alone. |
| `TEZGAH_STATUS_ANIMATE` | `hosts/omp/tezgah-hook.ts.in:65` | unset (animated) | `0` keeps omp's status colours and drops the motion. |
| `TEZGAH_STATUS_HOST` | `statusline.py::HOST` | `claude` | `cursor` renders for Cursor (the same as `--cursor`). |
| `TEZGAH_STATUS_LEGEND` | `statusline.py:127` | unset | `1` prints the mark legend under the line. |

## Set by tezgah or the host, not by a user

| Variable | Read by | Default | Effect |
|---|---|---|---|
| `TEZGAH_SESSION` | `bin/tezgah-status::main`, `bin/tezgah-docs`, `bin/tezgah-route`, `bin/tezgah-triage`, `hosts/omp/tezgah-hook.ts.in` | unset; the omp hook exports it to its shells | The session id `tezgah-docs`, `tezgah-route` and `tezgah-triage` write their ledger rows under, and the id `tezgah-status` lights its "used" marks from when none is passed. |
| `TEZGAH_CORE_IN_FILE` | `hooks/projects-auto-init.py::core_is_in_a_file`, `hooks/hooks.json` | unset | `1` (set by the Claude plugin's hook rows) drops the core rules from the injection when the host's static file really carries the tezgah block; a file without it falls back to the hook. |
| `TEZGAH_NESTED` | `hooks/tezgah_integrity.py::_shape_block`, `bin/consult` | unset | Set by consult on the agent CLIs it runs: that session's Stop rule does not fire. |
| `TEZGAH_CALL_OUTCOME` | `hooks/projects-posttooluse.py::main`, `hosts/dsh/hooks.json` | unset | `none` (dsh's Task rows) records the call's outcome as unknown instead of as a pass. |
| `CLAUDE_PROJECT_DIR` | `hooks/projects-auto-init.py::main` | the process cwd | The project dir when the hook payload carries no `cwd`. |
| `PLAYWRIGHT_BROWSERS_PATH`, `LOCALAPPDATA` | `hooks/tezgah_apps.py::_browser_caches`, `bin/tezgah-setup::default_prefix` (`LOCALAPPDATA` only) | Playwright's own cache dirs | Where `analyze-app` looks for an installed browser before it reports one missing; on Windows `LOCALAPPDATA` is also the parent of the default install prefix. |

## Test knob

| Variable | Read by | Default | Effect |
|---|---|---|---|
| `TEZGAH_E2E_STRICT` | `tests/e2e_*.py`, `.github/workflows/ci.yml` | unset (a missing prerequisite is a SKIP) | `1` turns an end-to-end script's SKIP into a FAIL; CI sets it. |

## Debugging

| Variable | Read by | Default | Effect |
|---|---|---|---|
| `TEZGAH_DEBUG` | `hooks/tezgah_guard.py` | unset (off) | Any value but empty or `0` makes every hook process append one line to `<cache>/debug.log` (created 0600): `<epoch> host=<codex\|cursor\|omp\|claude/dsh> script=<entry script> calls=<core fn>:<answer\|none\|ExceptionClass>,... ms=<elapsed>`. `answer` means the core returned something (a deny reason, a context block, a block decision). No prompt or tool text is written. Off, it costs one environment read. `tezgah-doctor --clean` removes the file once it has gone untouched for `--retention-days` (default 30). |

## Source of truth

`hooks/tezgah_paths.py`, `hooks/tezgah_judge.py`, `hooks/tezgah_models.py`,
`hooks/tezgah_index.py`, `hooks/tezgah_apps.py`, `hooks/tezgah_agents.py`,
`hooks/tezgah_context.py`, `hooks/tezgah_integrity.py`,
`hooks/projects-auto-init.py`, `hooks/projects-posttooluse.py`, `statusline.py`,
`bin/tezgah-setup`, `bin/consult`, `bin/codegen`, `bin/tezgah-status`,
`bin/tezgah-doctor`, `bin/tezgah-dsh`, `bin/tezgah.js`, `packaging/install.sh`,
`packaging/upgrade.sh`, `packaging/install.ps1`, `packaging/build.sh`,
`hosts/omp/tezgah-hook.ts.in`, `hosts/opencode/plugins/tezgah.js`,
`hosts/dsh/statusline/lib/index.js`. The list was taken by searching the shipped
code for `os.environ`, `getenv`, `process.env`, `$env:` and `${...}` reads; re-run
that search after adding a variable and add its row here.
