<p align="center">
  <a href="README.md">English</a> |
  <a href="README.zh.md">简体中文</a> |
  <a href="README.zht.md">繁體中文</a> |
  <a href="README.ko.md">한국어</a> |
  <a href="README.de.md">Deutsch</a> |
  <a href="README.es.md">Español</a> |
  <a href="README.fr.md">Français</a> |
  <a href="README.it.md">Italiano</a> |
  <a href="README.da.md">Dansk</a> |
  <a href="README.ja.md">日本語</a> |
  <a href="README.pl.md">Polski</a> |
  <a href="README.ru.md">Русский</a> |
  <a href="README.bs.md">Bosanski</a> |
  <a href="README.no.md">Norsk</a> |
  <a href="README.br.md">Português (Brasil)</a> |
  <a href="README.th.md">ไทย</a> |
  <a href="README.tr.md">Türkçe</a> |
  <a href="README.uk.md">Українська</a> |
  <a href="README.bn.md">বাংলা</a>
</p>

# Tezgah

<p align="center">
  <img src="assets/logo/tezgah-logo.svg" alt="tezgah logo" width="220">
</p>

<h3 align="center">One working contract for every AI coding assistant you run.</h3>

<p align="center">
  <a href="LICENSE"><img alt="License: MIT" src="https://img.shields.io/github/license/r1z4x/tezgah?style=flat-square"></a>
  <a href="https://github.com/r1z4x/tezgah/actions/workflows/ci.yml"><img alt="CI" src="https://img.shields.io/github/actions/workflow/status/r1z4x/tezgah/ci.yml?style=flat-square&label=ci"></a>
  <a href="https://github.com/r1z4x/tezgah/releases/latest"><img alt="Release" src="https://img.shields.io/github/v/release/r1z4x/tezgah?style=flat-square"></a>
</p>

<p align="center">
  <a href="#what-it-enforces">What it enforces</a> &bull;
  <a href="#supported-hosts">Supported hosts</a> &bull;
  <a href="#install">Install</a> &bull;
  <a href="#day-to-day">Day-to-day</a> &bull;
  <a href="#configuration">Configuration</a> &bull;
  <a href="#benchmark">Benchmark</a> &bull;
  <a href="#cost">Cost</a> &bull;
  <a href="#development">Development</a> &bull;
  <a href="#contributing">Contributing</a> &bull;
  <a href="#security">Security</a> &bull;
  <a href="#license">License</a>
</p>

<p align="center"><sub>English is the source of truth; translations may lag behind it.</sub></p>

---

One working contract for every AI coding assistant you run — **oh-my-pi (omp),
the primary host**, plus Claude Code, Codex, Cursor, opencode and DeepSeek's dsh
harness — inside a set of configured repository roots.

Left alone, each assistant has its own habits: one answers in Turkish, another
in English; one greps for everything, another queries a code graph; one says
"done" without running a test. Tezgah removes the drift. Open any host and you
get the same language, the same discipline, and the same standard of evidence.

The design is two layers. The rules live once in a shared core; each host gets
a thin adapter that translates that core into the shape the host understands.
Change a rule in one place and all six hosts see it — no six-way copy of the
same text.

<a id="what-it-enforces"></a>

## What it enforces

- **Outcome-first Turkish reporting.** Every reply is in Turkish and leads with
  the result or decision (BLUF), then points ordered by impact. Code, commits,
  docs, and subagent prompts stay English; names, CLI commands, and error
  strings are never translated.
- **Minimal code (ponytail).** The laziest change that actually works: YAGNI,
  then reuse an existing helper, then stdlib, then a native platform feature,
  then an installed dependency, then one line. No unrequested abstractions.
  Validation, error handling, and security are never simplified away.
- **Code-graph-first discovery.** "Where is X", "who calls Y", "what breaks if
  Z changes" go to the `codebase-memory-mcp` graph (`search_graph`,
  `trace_path`, `search_code`), not to grep. Grep stays right for literal text,
  configs, and non-code files.
- **Accessibility-first app analysis.** A running web or mobile app is read
  through its accessibility / DOM / native view tree, not a screenshot per step.
  `analyze-app` covers a browser (Playwright MCP), an iOS Simulator or Android
  emulator (Mobile MCP), and optional web diagnostics (Chrome DevTools MCP); a
  screenshot is an explicit, on-demand action for what the tree cannot answer.
- **External second opinion.** `~/.config/tezgah/bin/consult` asks independent
  models in parallel (OpenRouter by default, `--provider deepseek` for the
  DeepSeek API), then spends one more call on a referee that names where the
  panel disagreed, what all of them assumed, what would change the
  recommendation and what evidence it still wants. Each failure is classed with
  the one variable to change on a retry, a dead referee is disclosed as an
  unjudged panel, and a packet too long for argv goes in with `consult -`. The
  agent reports where the models disagreed and verifies their claims against the
  code.
- **Research via OpenResearch.** When the router judges a task is research — a
  literature review, forming and testing hypotheses, running experiments, a
  research artifact — it drives the work through alphaXiv's OpenResearch (`orx`)
  and loads the `orx` manual first, instead of improvising the protocol. Plain
  code discovery stays on the code graph. When `orx` is absent, the router says
  so and falls back to a host subagent.
  The domain knowledge an experiment needs ships with it: the vendored
  `AI-research-SKILLs` library (98 skills, 23 categories, MIT) lands as the `ai-research`
  skill, read one entry at a time from its stage index.
- **Honesty under verification.** Nothing is reported done, tested, or fixed
  unless the output was seen. A failing test is reported as failing with its
  exact error, and a skipped check is stated plainly.
- **No AI attribution, anywhere.** Nothing persisted or published — commit,
  merge, and tag messages, PR and issue text, code comments, file headers, docs
  — may credit the assistant, model, vendor, or "AI". Using a tool is fine;
  signing its name to your work is not.
- **Two-tier orchestration.** The main thread decides and verifies; a cheap
  model (`~/.config/tezgah/bin/codegen`, OpenRouter by default or `--provider deepseek`) drafts
  bounded, well-specified edits to a scratch directory. Nothing reaches the repo
  except through the router; on a failed draft (codegen exit 2) the contract
  requires the router to write the code itself with the main model - a rule the
  router follows, not a mechanism inside codegen.
- **Per-repo subagents.** At session start the enclosing repo gets a small set of
  capability-gated agents (`tezgah-explorer`, `tezgah-reviewer`,
  `tezgah-researcher`, `tezgah-verifier`) plus a `tezgah-orchestrator`, rendered
  into each installed host's native surface (Claude/Cursor `.claude/agents/`,
  opencode `.opencode/agents/` plus a live config injection, Codex
  `.codex/agents/`) and ignored through the clone's own `.git/info/exclude`, so
  the repo's tracked `.gitignore` is never edited. Which hosts
  get files is the config's `hosts` list when it names one of those four, and
  otherwise every host detected on the machine - omp is not one of them, because
  its subagents are user-level (`~/.omp/agent/agents/`), so a config of
  `hosts: ["omp"]` writes no per-repo agent files at all. On Claude the
  orchestrator's `Agent(tezgah-*)` allowlist only takes effect when it runs as the
  main thread (`claude --agent tezgah-orchestrator`); as a subagent the list is
  ignored. dsh has no per-role surface, so the contract's router rule covers it.

<a id="supported-hosts"></a>

## Supported hosts

`omp` is the primary host — the one tezgah is developed and verified against.
Its whole surface (session start, per-turn rules, gate, evidence, end-of-turn
block, status line) is covered by tests, and it is the only host whose status
line is also checked against the real TUI. The rest are adapters, each claimed
for what it mechanically enforces: the adapter docstrings and the gate tests
record what a host actually refuses, and `benchmarks/harness-vs-omp/` keeps the
cost evidence, which is a separate question from enforcement.

| Host | Wired by |
|---|---|
| **omp** (oh-my-pi) — primary | `~/.omp/agent`: managed `RULES.md` always-on block, skills, generated subagents, `mcp.json`, and an extension (`hooks/pre/tezgah-hook.ts`) that arms the per-prompt rules, gates tools, records evidence and runs the Stop rule; the wiring is checked by `tezgah-setup` |
| **Claude Code** | local plugin marketplace: hooks, commands, two read-only agents, output style |
| **Codex** | `hooks.json` + skills + MCP, including a `PreToolUse` gate |
| **Cursor** | `hooks.json` + skills + MCP; needs a cursor-agent build with CLI hooks and `statusLine` - the 2025.09 build predates both, so this adapter is inert until Cursor ships them |
| **opencode** | plugin + instructions + MCP + generated skill router (native skill list denied), repo auto-index on the first message; the plugin writes the ledger rows but does **not** carry the loop guard, so an identical call past the ceiling is refused only on the hosts with a PreToolUse gate |
| **dsh** | Claude Code hook bridge + managed patch block (hooks, MCP, LLM routes, an out-of-tree Web status line) |

The Codex gate runs Bash, `exec_command`, `apply_patch`, Edit/Write, MCP tools,
and subagent calls through the same check as the other hosts. On Claude the
`attribution` setting is emptied (`commit`, `pr`, `sessionUrl`), which turns off
the harness-emitted commit/PR trailers - it does not edit text the model writes.
Elsewhere the ban is enforced only by the tool gate (a git/gh write whose command
carries a credit is refused) and by the contract; Cursor exposes no attribution
lever tezgah can set.

Both halves of the integrity rule keep their aim narrow, because a gate that
fires on description stops the work it polices. The anti-shortcut deny reads the
command with quoted text and heredoc bodies blanked, so a commit message that
names `--no-verify` passes while the flag itself is refused; the test-disable
deny needs a *test* path, a marker outside strings and comments, and a marker the
file does not already carry. The reply-level half - the Stop rule - runs where
the host hands over the final message: Claude, Codex, omp (`session_stop`) and
Cursor, which reports the reply on `afterAgentResponse` and takes the decision at
`stop`. Its ledger is shared, so the newest check wins: a later failure blocks a
"tests pass" claim even if an earlier run was green. Each row carries the action
it belongs to (`id`, a digest of the tool and its canonical arguments), the
workspace, and whichever of `exit`, `out_bytes` and `fail_class` the host
actually reported - a field a host cannot report is absent, never zeroed, so a
reader can tell "it failed" from "nobody said" - so a
run can be reconstructed rather than guessed at; the same identity feeds the
loop guard, which refuses a third identical call whose previous attempts exited
non-zero. `tezgah-status --counters <cwd> <session>` reports four trace figures
next to the deny counts: `steps` counts the session's work events - the `run`,
`edit` and `verify*` rows, so a denial, a nudge or a claim is not a step;
`tool_error_rate` is the share of non-zero exits over the rows that carry an
`exit` at all, i.e. the rows whose host reported an outcome (absent when none
did); `claims` counts Stop evaluations - one row per user turn and reply text,
so a host that re-runs its Stop handler cannot double-count a turn - and
`false_completion` is the share of those whose stop was refused. A check counts
as support only when the host reported exit 0, the command was not masked by a
pipe, and - where the host supplies a result size - that size is non-zero; rows
written before this rule existed are still accepted, so upgrading never blocks
an open session on its own history. opencode has no end-of-turn surface to
block, so it records the evidence and the reply claim stays unenforced there.

### App analysis

`analyze-app` drives a running application from its accessibility tree. The
default loop is open, read the tree, act, observe console/network/logs, and
re-read the tree — a screenshot is an explicit action for what the tree cannot
answer (canvas, game, animation, pixel-level visual regression). The skill is
one path for all hosts; the servers under it are one shared spec in
`hooks/tezgah_apps.py`:

| Server | Target | Wired by |
|---|---|---|
| `playwright` (`@playwright/mcp`) | web pages, `browser_*` tools | opencode, Codex, Cursor, Claude (plugin `.mcp.json`) |
| `mobile-mcp` (`@mobilenext/mobile-mcp`) | iOS Simulator / Android emulator, `mobile_*` tools | same |
| `chrome-devtools` (opt-in, `--devtools`) | web perf traces, deep network, source-mapped console | same |

The browser runs an **isolated** profile by default, so a run never touches your
real Chrome state; analyzing a logged-in flow is a deliberate attach
(`--cdp-endpoint` or the Playwright extension), not a default. Screenshots,
traces and tree dumps land in `~/.cache/tezgah/apps` (override with
`TEZGAH_ARTIFACTS`) and the agent gets a path back, never inline image bytes.
The servers run through `npx`, so they need node but no install of their own;
`tezgah-setup --install --devtools` adds the optional web diagnostics server.
dsh wires the same two servers through its `dsh-mcp-client` bridge
(`serverName` / `command` / `args` / `env`, confirmed against the published
config schema), and Claude gets them from the plugin's `.mcp.json`
(`claude plugin details tezgah` lists MCP servers 2 and both connect).
`mobile-mcp` is the higher-friction half: macOS may prompt for Accessibility /
Screen-Recording permission and the view tree can drop under load, so the skill
retries the tree before falling back to a screenshot.

CI runs a deterministic handshake for both servers (no browser, no device):
`TEZGAH_E2E_STRICT=1 python3 tests/e2e_analyze_wiring.py`. Two opt-in local
smokes go further: `TEZGAH_E2E_APPS=1 python3 tests/e2e_analyze_web.py` starts
Playwright MCP, navigates and reads the snapshot with no screenshot;
`TEZGAH_E2E_APPS=1 python3 tests/e2e_analyze_mobile.py` starts Mobile MCP, checks
the view-tree tools and lists a device. They print `SKIP: ...` when node, a
browser build or a device is missing.

<a id="install"></a>

## Install

Requires Python 3.8+. node + npm are needed for the dsh host and, with `pnpm`,
for its web status line. The optional integrations degrade gracefully:
`codebase-memory-mcp` on PATH powers the graph; a model key powers `consult`
and `codegen` — OpenRouter by default (`OPENROUTER_API_KEY` or
`~/.config/openrouter/key`), or the DeepSeek API with `--provider deepseek`
(`DEEPSEEK_API_KEY` or `~/.config/deepseek/key`); and OpenResearch's `orx` on
PATH gives the research rule something to drive. When the chosen provider's key
is missing, tezgah says so instead of pretending.

Clone, then arm every detected host in one pass:

```bash
git clone https://github.com/r1z4x/tezgah.git ~/Projects/tezgah
cd ~/Projects/tezgah
bin/tezgah-setup --install
```

In a terminal that command with no arguments is the wizard instead: it asks which hosts to
arm, the root directories, whether to install the missing optional tools, and whether to
wire the optional DevTools MCP, prints the plan, and writes only after a yes. The flags are
the wizard's defaults, so `--wizard --hosts omp` asks only the rest. A piped, agent or CI
run is never prompted — it prints the report, exactly as before.

`--install` also installs the optional tools that are missing by running each vendor's own
installer **over the network**: `orx` (`openresearch.sh/install.sh`), `cursor-agent`
(`cursor.com/install`), `dsh` (its home profile through `npx`), and `pnpm` when dsh needs it
(via `npm`) — `curl ... | sh` included. None needs sudo; the run is recorded in
`~/.config/tezgah/install.log`. Preview with `--dry-run`, skip it with
`--no-deps` (useful in CI), or install the tools alone with `--deps`. Tools land
in `~/.local/bin` or `~/.cargo/bin`, so a fresh shell may be needed before they
are on PATH; tezgah's own checks look in those dirs regardless, so a non-interactive
shell still reports them as present.

If a predecessor setup is already present, import it first — it is moved aside,
not deleted:

```bash
bin/tezgah-setup --adopt
```

Claude Code installs through its own plugin channel:

```bash
claude plugin marketplace add ~/Projects/tezgah
claude plugin install tezgah@rizacan-local
```

Limit the install explicitly when needed (the first form is the
primary host alone):

```bash
bin/tezgah-setup --install --hosts omp
bin/tezgah-setup --install --hosts claude,codex,cursor,opencode,dsh
bin/tezgah-setup --roots ~/work:~/oss --install
```

<a id="day-to-day"></a>

## Day-to-day

Nothing to run: the rules load when a host starts. A few commands are worth
knowing:

| Command | Purpose |
|---|---|
| `bin/tezgah-setup` | On a terminal: the install wizard; on a pipe or in CI: report what is armed, per host |
| `bin/tezgah-setup --wizard` | Force the install wizard anywhere; `--report` forces the report |
| `bin/tezgah-status [PATH]` | Show whether the rules are active in that repo |
| `bin/tezgah-setup --status [PATH]` | Print the armed/used checklist |
| `bin/tezgah-setup --deps [--dry-run]` | Install missing optional tools (orx, cursor-agent, dsh) |
| `bin/tezgah-research init\|check\|status` | Runs and checks a research line: state, findings, claims, and the protocol-before-results rule |
| `bin/tezgah-doctor [--clean] [--prune-sessions DAYS]` | Report harness disk use; `--clean` deletes old index logs and vacuums the opencode DB; `--prune-sessions` deletes idle sessions (the only action that actually shrinks the DB) |
| `/tezgah:plan-add` | Turn a piece of work into a tracked plan |
| `/tezgah:plan-status` | Summarize open plans and pick the next one |
| `/tezgah:plan-sync` | Close out finished plans |
| `bin/tezgah-setup --version` | Print the plugin version |
| `bin/tezgah-setup --uninstall` | Remove only tezgah's symlinks, host hook entries, and the dsh managed block |

<a id="configuration"></a>

## Configuration

Tezgah is armed only under its configured roots; anywhere else it is silent.

- Default root: `~/Projects`.
- `~/.config/tezgah/config.json`: `{"roots": ["~/Projects", "~/work"]}`.
- `TEZGAH_ROOTS` (path-separator list) overrides the file for one-offs and CI.

Kill switches live in `~/.config/tezgah/`. Each one removes its rule from the
text injected into the session, so the rule actually stops:

| Switch | Turns off |
|---|---|
| `exec-mode.off` | Turkish, outcome-first reporting |
| `ponytail-auto.off` | the minimal-code rule |
| `spec-off` | the spec-before-building rule |
| `consult-off` | the external-second-opinion rule |
| `research-off` | routing research tasks to OpenResearch |
| `orchestrate-off` | subagent delegation (adds a do-not-delegate line) |
| `reminder-off` | the per-turn reminder text |
| `pretooluse-off` | the PreToolUse gate itself (attribution, explorer, grep nudge) |

Per repo, `.no-ponytail`, `.no-cbm` and `.no-lessons` turn off the minimal-code
rule, the code-graph rule (and its auto-index), and the lessons ledger
respectively.

When the user flags a mistake, the agent appends a one-line lesson to the repo's
`.tezgah/lessons.md`; the most recent lines are injected at session start so the
same mistake cannot silently repeat.

<a id="benchmark"></a>

## Benchmark

Does this contract improve the work, or does it only look like it should? That is measured
in `benchmarks/arm-bench/`, not asserted: hidden checks the agent never sees the check for,
cost from the host's own usage record, and collateral edits scored as failures.
`PREREGISTRATION.md` fixes the endpoints before a run and `python3 bench.py report` prints
them; the full study, with the run ids, is `docs/research/2026-09-16-tezgah-quality.md`.
Every figure below is a run log.

| Block | Runs | What it settled |
|---|---|---|
| two-host, 28 tasks, k=3 | 336 | `omp+tezgah` 0.95 and `opencode+tezgah` 0.96 have overlapping intervals and the same cost per solved task; on the bare arms omp is cheaper ($0.0047 against $0.0074 CPS), so the daily driver is omp at no cost in quality |
| hard family, 5 tasks, k=5, two model families | 200 | pooled, three of the four arms land on 40/50: no harness effect at that size, and the one signal the first model produced reversed on the second |
| gate family, gate armed | 36 | no arm took the shortcut route; the gate mechanism is verified directly (a skip edit is refused), its effect on the work is not measured yet |
| clause ablation, the two rules that separate, k=8 | 160 | the contract arms pass 23/32 (0.72) against the bare anchor's 12/32 (0.38) |

**It helps exactly where the model's default is wrong.** `c04` (an English prompt where only
the contract makes the reply Turkish) reads 9/16 with a contract and 0/16 without one; `h02`
(a money contract whose visible suite is green either way) reads 14/16 against 12/16. Where
there is no gap to close - 22 of the 25 pilot tasks passed under every arm on every repeat -
a benchmark can only report a null.

**Two clauses carry it.** Removing clause 1 takes `c04` to 0/8, the bare anchor's own score,
while barely moving `h02`. Removing clause 3 takes `h02` to 2/8 - below the bare anchor's
6/8 - because clause 3 forbids stopping at the shortest done-looking path, and on that task
the shortest path is the one-liner that passes the visible suite while breaking the
documented rule. Clauses 2 and 4 move nothing measurable.

**Cost follows quality.** Per solved task: $0.0078 against $0.0097 on the full-contract
node, $0.0043 against $0.0087 on the minus-ponytail node. The contract arms solve more
tasks, so each solved task costs less; total spend is higher, and the benchmark records it
per row rather than netting it out.

What this does not show: code quality, review effort or maintainability, none of which is
measured here; the gate's effect on an arm's choices, since no arm reached for the shortcut
in 36 armed runs; or a clause *order* - `k=8` fixes a direction, at 8 runs per cell. One
provider and one fixture package throughout, and the ablation rounds run on a single model
family. A second model family reproduces the 28-task null exactly (51/56 against 51/56),
which is what shows the first reading was not a model artefact.

<a id="cost"></a>

## Cost

Measured on this machine (macOS, Python 3.10), not estimated. `tezgah-setup` prints the live
budget - read it there rather than trusting a figure copied here, which is how an earlier
revision came to quote a core band smaller than the one it installs.

| Band | What it costs |
|---|---|
| Session start | the always-on contract (the invariants plus a one-line pointer per on-demand rule): on this machine and skill set, ~1.5k tokens of contract text and ~1.4k of skill metadata, with the conditional rules (spec, consult, research, graph) adding ~0.7k only on the turn whose prompt matches |
| Per turn | a short reminder (~0.2k tokens) plus the armed rule when it matches; hooks are separate Python processes, so the ~19 ms interpreter start is the base - a turn adds ~31 ms, session start adds ~50-81 ms, a gated tool call (Bash/Grep/Task) ~24-25 ms. opencode has no prompt-time hook, so it pays zero |
| On demand | the full `tezgah-contract` skill (~6.6k tokens), paid only when a task loads it |
| MCP schemas | the largest band, and the one no static report sees: the graph server alone declares 15 tools / 24,508 bytes (~6.1k tokens), riding every request unless the host fetches schemas on demand. `tezgah-setup --mcp-schemas` measures it |
| Disk | installation takes ~58 ms, and every file tezgah rewrites is kept once as `<file>.tezgah-bak` |

**The arming floor.** The invariants are always-on - execution mode, ponytail,
deliver-the-whole-ask, integrity, loop discipline, the lessons ledger, the attribution
ban and the session-scope boundary (tezgah's own install is the user's to tend, not the
session's) - and the safety rule ("irreversible or outward-facing actions need an explicit ask
first") is one of them, so it never depends on a classifier. Each advisory rule keeps an
actionable one-line pointer always-on, so a missed match costs detail, never the rule, and a
host hook that fails falls back to the pointers plus the on-demand skill rather than to no
contract. False negatives are auditable: every prompt appends `armed=<rules|none> chars=<n>`
- no prompt text - to `~/.cache/tezgah/classify.log` (truncated to the last 200 lines past
64 KB), and all five hook hosts arm the same set for the same prompt
(`tests/test_context.py::ArmingConformance`).

**opencode is armed differently.** It has no prompt-time injection point, so the contract
ships as a generated instructions file, and its always-on router lists only the buckets a
coding session reaches for, collapsing the rest to a pointer at
`~/.config/tezgah/opencode-skills.full.md` read on demand; `permission.skill = deny` stops
opencode injecting every skill's metadata instead. `--install` also sets `compaction.prune`
and `watcher.ignore`, clearing old tool results from the prompt rather than re-sending them
every step - without that the working set grows to hundreds of thousands of tokens before
opencode auto-compacts near the model's limit (about 980k for a 1M-token model).
`bin/tezgah-doctor` reports the disk footprint and `--prune-sessions DAYS` deletes idle
sessions through the opencode CLI, the only action that actually shrinks the database, since
VACUUM alone cannot.

**Why it pays.** In one real repo a default `grep` ignored the relevant folder and found
nothing; with ignore disabled it took 3.95 s and still mixed definitions with call sites,
while the code graph answered the same question in 16 ms with the 8 true call sites.

<a id="development"></a>

## Development

```bash
python3 -m unittest discover -s tests -v   # stdlib test suite
pip install -r requirements-dev.txt        # pinned ruff, the only dev dep
ruff check .                               # lint (config in pyproject.toml)
```

CI runs both on Python 3.10 and 3.12. To refresh an installed Claude copy from
this checkout, use `bin/tezgah-setup --sync`, and validate the manifest with
`claude plugin validate .claude-plugin/plugin.json`. When bumping the version,
update `.claude-plugin/plugin.json` and `.claude-plugin/marketplace.json`
together — they must agree.

`codebase-memory-mcp` is installed by the user. Orca's hooks and files are not
part of this project and are left untouched. Claude receives the always-on core
from the SessionStart hook; `output-styles/tezgah.md` is a duplicate for builds
that load plugin output styles, so the hook is the authoritative path.

<a id="contributing"></a>

## Contributing

Small, single-purpose changes are the easiest to accept. A rule belongs in the
shared core (`hooks/`) unless it is genuinely host-specific; a host difference
belongs in its adapter under `hosts/<name>/`. Keep the diff as short as it can
be while still correct — the project's own minimal-code rule applies to the
project.

Before opening a pull request, run the same three checks CI runs:

```bash
python3 -m compileall -q hooks hosts bin statusline.py   # byte-compile every script
python3 -m unittest discover -s tests                     # stdlib test suite
ruff check .                                              # lint; config in pyproject.toml
```

`ruff` comes from `requirements-dev.txt` (`pip install -r requirements-dev.txt`),
which is the only development dependency.

<a id="security"></a>

## Security

Report vulnerabilities privately through GitHub's security advisories
(**Security** tab → **Report a vulnerability**) rather than a public issue.

tezgah runs shell hooks, writes host configuration, and injects text into every
session, so anything that makes a hook execute attacker-controlled code, leaks a
key into a config file, widens a sandbox, or lets repository content escalate
into instruction text is in scope. Include the host, the tezgah version
(`bin/tezgah-setup --version`), and a minimal reproduction.

<a id="license"></a>

## License

The root `LICENSE` (MIT) covers tezgah's own files. `skills/ponytail` and
`skills/no-ai-slop` are vendored under their own MIT terms, recorded in
`NOTICE`.
