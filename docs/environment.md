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
| `TEZGAH_PREFIX` | `packaging/install.sh:24`, `packaging/upgrade.sh`, `packaging/install.ps1`, `bin/tezgah-setup:61` | `$XDG_DATA_HOME/tezgah`, else `~/.local/share/tezgah` (`%LOCALAPPDATA%\tezgah` on Windows) | Where the artifact install unpacks its versions and the `current` link; `tezgah-setup` treats it as the install prefix. |
| `TEZGAH_VERSION` | `packaging/install.sh`, `packaging/upgrade.sh`, `packaging/install.ps1`, `packaging/build.sh:70` | the newest GitHub release; `build.sh` falls back to `VERSION`/the CHANGELOG | The version to install, or the version `build.sh` stamps when `--version` is not given. |
| `TEZGAH_REPO` | `packaging/install.sh:12`, `packaging/upgrade.sh`, `packaging/install.ps1` | `r1z4x/tezgah` | The GitHub repository releases are fetched from. |
| `TEZGAH_UPDATE_URL` | `hooks/tezgah_update.py` | `https://github.com/<TEZGAH_REPO>/releases/latest` | Where the daily release check reads the newest tag: from the redirect, or from a JSON body's `tag_name`. Tests point it at a `file://` fixture. |
| `TEZGAH_UPDATE_CHECK` | `hooks/tezgah_update.py` | unset | `0` turns off the update chip and the daily check. The test suite sets it, so no test reaches the network. |
| `TEZGAH_DIST` | `packaging/upgrade.sh:72`, `packaging/install.ps1` | unset: the release URL | A directory holding `tezgah-<V>.tar.gz` and its `.sha256` (what `build.sh --out` writes) used instead of the release download; CI exercises the real fetch-verify-unpack path with it. |
| `TEZGAH_NO_DEPS` | `bin/tezgah-setup:4636` | unset | Any value but empty or `0` is `--no-deps`: the optional tools (codegraph, orx, host CLIs) are not installed. |
| `TEZGAH_NO_SYMLINK` | `bin/tezgah-setup:396` | unset | Any value but empty or `0` writes the copy layout a machine without symlinks gets, on a machine that has them. |
| `TEZGAH_PYTHON` | `hooks/tezgah_paths.py:344`, `bin/tezgah.js`, `bin/tezgah-dsh.cmd`, `hooks/hooks.json`, `hosts/*/hooks.json`, `hosts/omp/tezgah-hook.ts.in`, `hosts/opencode/plugins/tezgah.js`, `packaging/build.sh` | this process's interpreter, then `python3`/`python`/`py` on PATH | The interpreter every host hook and the npm shim start; pin it when the right Python is not first on PATH. |

## Where tezgah and the hosts keep state

| Variable | Read by | Default | Effect |
|---|---|---|---|
| `TEZGAH_ROOTS` | `hooks/tezgah_paths.py:176`, `bin/tezgah-setup`, `hosts/opencode/plugins/tezgah.js` | `roots` in `~/.config/tezgah/config.json`, else `~/Projects` | The directories tezgah is armed over, `os.pathsep`-separated; it outranks the config file. |
| `XDG_CONFIG_HOME` | `hooks/tezgah_paths.py:21`, `bin/tezgah-doctor`, `bin/tezgah-dsh.cmd`, `hosts/opencode/plugins/tezgah.js` | `~/.config` | Parent of tezgah's config dir (kill switches, `bin/` links, config) and of opencode's. |
| `XDG_DATA_HOME` | `bin/tezgah-setup:64`, `packaging/install.sh`, `packaging/upgrade.sh` | `~/.local/share` | Parent of the default install prefix. |
| `XDG_CACHE_HOME` | `hooks/tezgah_apps.py:27` | `~/.cache` | Parent of the app-analysis artifact dir. |
| `TEZGAH_DEBUG` | `hooks/tezgah_guard.py` | unset | `1` makes every hook process append one line to `<cache>/debug.log` (host, script, each guarded call's outcome or exception class, elapsed ms; no prompt or tool text), created 0600 and swept by `tezgah-doctor --clean`. Off, it costs one environment read. |
| `TEZGAH_FALLBACK_CACHE` | `hooks/tezgah_paths.py:135` | `<tempdir>/tezgah` | The cache a sandboxed hook writes when its normal cache dir is denied; a test knob. |
| `TEZGAH_ARTIFACTS` | `hooks/tezgah_apps.py:26` | `$XDG_CACHE_HOME/tezgah/apps` | Where `analyze-app` screenshots, traces and tree dumps land. |
| `TEZGAH_NO_EXCLUDE` | `hooks/tezgah_agents.py:662` | unset | `1` stops tezgah adding its generated-agent dirs to the repository's `.git/info/exclude`. |
| `CODEX_HOME` | `hooks/tezgah_paths.py:58` | `~/.codex` | The Codex home tezgah installs into and checks; the same variable Codex itself reads. |
| `DSH_HOME` | `hooks/tezgah_paths.py:61`, `bin/tezgah-dsh`, `bin/tezgah-dsh.cmd` | `~/.dsh` | The dsh home tezgah installs into, and where `tezgah-dsh` looks for the CLI. |
| `TEZGAH_OPENCODE_DATA` | `bin/tezgah-setup:98`, `bin/tezgah-doctor` | `~/.local/share/opencode` | opencode's data dir: its session database for `tezgah-doctor` and the installer. |

## Which binary runs

| Variable | Read by | Default | Effect |
|---|---|---|---|
| `TEZGAH_CODEGRAPH_BIN` | `hooks/tezgah_paths.py:379` | the config file, then `codegraph` on PATH | The codegraph executable the index and the graph marks use. |
| `TEZGAH_ORX_BIN` | `hooks/tezgah_paths.py:492` | `orx` on PATH | The OpenResearch CLI the research rule routes to. |
| `TEZGAH_OMP_BIN` | `hooks/tezgah_paths.py:502` | `omp` on PATH | The omp binary the installer, the model table and consult's session-model lookup run. |
| `TEZGAH_DSH_BIN` | `bin/tezgah-setup:759` | the profile-local entry, then `bin/tezgah-dsh`, then npx | How the installer invokes the dsh CLI. |
| `TEZGAH_INDEX_BIN` | `bin/tezgah-dsh:19`, `bin/tezgah-dsh.cmd` | `~/.config/tezgah/bin/tezgah-index` | The index worker `tezgah-dsh` warms before it starts dsh. |
| `TEZGAH_STATUS_BIN` | `hosts/dsh/statusline/lib/index.js:24`, `hosts/opencode/tui/tezgah-tui.tsx` | `~/.config/tezgah/bin/tezgah-status` | The status renderer the dsh status line and the opencode TUI call. |
| `TEZGAH_CONSULT_CLIS` | `hooks/tezgah_paths.py:431` | unset: every agent CLI on PATH counts | Comma list of the agent CLIs that may count as consult members (empty: none); pins the answer in tests and CI. |

## Index worker

| Variable | Read by | Default | Effect |
|---|---|---|---|
| `TEZGAH_INDEX_TIMEOUT` | `hooks/tezgah_index.py:37` | `600` (seconds) | How long one index attempt may run before its process group is killed. Must be a number. |
| `TEZGAH_INDEX_RETRIES` | `hooks/tezgah_index.py:30` | `5` | Attempts the detached index worker makes. Must be an integer. |
| `TEZGAH_INDEX_RETRY_DELAY` | `hooks/tezgah_index.py:31` | `3` (seconds) | The pause between attempts. Must be a number. |

## Model credentials and endpoints

| Variable | Read by | Default | Effect |
|---|---|---|---|
| `TYPESAFE_API_KEY` | `hooks/tezgah_judge.py:109`, `hooks/tezgah_paths.py` | `~/.config/typesafe/key` | The judgement seam's first credential; omp also reads it for its own judge. |
| `OPENROUTER_API_KEY` | `hooks/tezgah_judge.py:130`, `bin/consult`, `bin/codegen`, `hooks/tezgah_models.py` | `~/.config/openrouter/key` | The seam's chat fallback, consult's and codegen's `openrouter` provider, and omp's `any` family. |
| `DEEPSEEK_API_KEY`, `INCEPTION_API_KEY` | `bin/consult`, `bin/codegen` | `~/.config/deepseek/key`, `~/.config/inception/key` | The `deepseek` and `inception` providers of consult and codegen. |
| `ANTHROPIC_OAUTH_TOKEN`, `ANTHROPIC_API_KEY`, `ZAI_API_KEY` | `hooks/tezgah_models.py:208` | omp's own auth store | Read as presence only: whether omp can run the `anthropic` or `zai` model family, so the model table can pick a row omp will run. |
| `TEZGAH_TYPESAFE_URL` | `hooks/tezgah_judge.py:100` | `https://api.typesafe.ai/v1/systemone` | Repoints the seam's TypeSafe endpoint (tests). A cross-host redirect is refused. |
| `TEZGAH_OPENROUTER_URL` | `hooks/tezgah_judge.py:121` | OpenRouter's chat-completions URL | Repoints the seam's chat fallback (tests). |
| `TEZGAH_JUDGE_MODEL` | `hooks/tezgah_judge.py:146` | the cheap `any` row of the models table | The model the seam's chat fallback asks. |

## consult and codegen

| Variable | Read by | Default | Effect |
|---|---|---|---|
| `CONSULT_URL` | `bin/consult:173` | the provider's URL | Repoints every HTTP member. The bearer token is dropped on a redirect to another host. |
| `CONSULT_MODELS` | `bin/consult:167` | the provider's default list | Comma list of `openrouter` models for the panel. |
| `CONSULT_JUDGE` | `bin/consult:707` | the recorded referee | The member that referees, after `--judge`. |
| `CONSULT_SESSION_MODEL` | `bin/consult:348` | omp's own record of the session model | The model this session runs on, so the panel skips it. |
| `OMPCODE`, `CLAUDECODE` | `bin/consult:333` | set by the host | Names the calling host's own CLI, so consult does not ask the session to second-guess itself (omp sets both; `OMPCODE` wins). |
| `CODEGEN_URL` | `bin/codegen:173` | the provider's URL | Repoints codegen's endpoint. |
| `CODEGEN_MODEL` | `bin/codegen:99` | the cheap `any` row of the models table | The model codegen drafts with. |

## Status line

| Variable | Read by | Default | Effect |
|---|---|---|---|
| `NO_COLOR` | `hooks/tezgah_context.py:2484`, `hosts/omp/tezgah-hook.ts.in` | unset | Any value renders the status line without ANSI colour. |
| `TEZGAH_STATUS_COLOR` | `hooks/tezgah_context.py:2485`, `hosts/omp/tezgah-hook.ts.in` | unset | `0` is the same opt-out as `NO_COLOR`, for tezgah alone. |
| `TEZGAH_STATUS_ANIMATE` | `hosts/omp/tezgah-hook.ts.in:65` | unset (animated) | `0` keeps omp's status colours and drops the motion. |
| `TEZGAH_STATUS_HOST` | `statusline.py:32` | `claude` | `cursor` renders for Cursor (the same as `--cursor`). |
| `TEZGAH_STATUS_LEGEND` | `statusline.py:120` | unset | `1` prints the mark legend under the line. |

## Set by tezgah or the host, not by a user

| Variable | Read by | Default | Effect |
|---|---|---|---|
| `TEZGAH_SESSION` | `bin/tezgah-status:229`, `bin/tezgah-docs`, `bin/tezgah-route`, `bin/tezgah-triage`, `hosts/omp/tezgah-hook.ts.in` | unset; the omp hook exports it to its shells | The session id `tezgah-docs`, `tezgah-route` and `tezgah-triage` write their ledger rows under, and the id `tezgah-status` lights its "used" marks from when none is passed. |
| `TEZGAH_CORE_IN_FILE` | `hooks/projects-auto-init.py:53`, `hooks/hooks.json` | unset | `1` (set by the Claude plugin's hook rows) drops the core rules from the injection when the host's static file really carries the tezgah block; a file without it falls back to the hook. |
| `TEZGAH_NESTED` | `hooks/tezgah_integrity.py:3298`, `bin/consult` | unset | Set by consult on the agent CLIs it runs: that session's Stop rule does not fire. |
| `TEZGAH_CALL_OUTCOME` | `hooks/projects-posttooluse.py:102`, `hosts/dsh/hooks.json` | unset | `none` (dsh's Task rows) records the call's outcome as unknown instead of as a pass. |
| `CLAUDE_PROJECT_DIR` | `hooks/projects-auto-init.py:68` | the process cwd | The project dir when the hook payload carries no `cwd`. |
| `PLAYWRIGHT_BROWSERS_PATH`, `LOCALAPPDATA` | `hooks/tezgah_apps.py:83` | Playwright's own cache dirs | Where `analyze-app` looks for an installed browser before it reports one missing. |

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
