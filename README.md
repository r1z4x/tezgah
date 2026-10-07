<p align="center">
  <a href="README.md">English</a> |
  <a href="README.de.md">Deutsch</a> |
  <a href="README.es.md">Español</a> |
  <a href="README.fr.md">Français</a> |
  <a href="README.tr.md">Türkçe</a>
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

<p align="center"><sub>English is the source of truth; translations may lag behind it.</sub></p>

---

Tezgah arms every AI coding assistant you run — **omp, the primary host**,
plus Claude Code, Codex, Cursor, opencode and DeepSeek's dsh harness — with
one working contract, inside the repository roots you configure. Left alone, each
assistant drifts: one answers in Turkish while another answers in English, one
greps where another queries a code graph, one reports "done" without running a
test. The rules live once in a shared core; each host gets a thin adapter that
translates them into the shape it understands — so a rule changed in one place
reaches every host the same way.

## What tezgah enforces and records

- **One contract, six hosts.** omp, Claude Code, Codex, Cursor, opencode and
  dsh see the same rules, because every host is a thin adapter over one shared
  core — change a rule once and all of them pick it up.
- **A done claim needs a passing check on record.** A gate of 15 refusals stops
  the neutered check — `--no-verify`, `|| true`, a test piped into `tail`, a
  skip added mid-flight — and the Stop rule refuses a completion claim the
  session's evidence ledger cannot back. It refuses the turn; it cannot make
  the model stop claiming.
- **Research ships with its library.** Research tasks route through
  OpenResearch with a vendored library of 98 upstream skills, loaded one entry
  at a time so the context stays small.
- **Every rule has an off switch.** Sixteen kill switches — plus per-repo
  marks — remove a rule's text from the session, so the rule actually stops
  rather than merely showing as off.
- **A fixed reply shape.** Replies lead with the outcome, in Turkish unless
  you pick another language; a list shows at most five ranked items; an
  estimate is named as an estimate; an error reads as location, cause, fix.

## What it has not shown

Tezgah is a set of mechanisms: rules injected into the session, a gate that
refuses certain commands, and a ledger the Stop rule reads. It is not evidence
that an agent cheats less or finishes more tasks. A paired on/off experiment
(October 2026; DeepSeek V4.1 Flash on omp, bare vs a full tezgah install) found
no measurable reduction in cheating, because the model barely cheated in
either arm:

- **Phase 1, three pressure fixtures:** cheating 0 of 60 runs in every arm;
  clean pass 48/60 with tezgah vs 53/60 without.
- **Phase 2, ImpossibleBench's conflicting SWE-bench split (44 instances,
  k = 3):** cheating 0/132 with tezgah vs 1/131 without (-0.8 pp, 95% CI
  -2.3 to 0); clean pass on the original tasks 129/131 vs 129/132.
- **Against the intent:** on those impossible tasks, the final message claimed
  completion in 115/132 runs with tezgah vs 90/131 without (+18 pp, p 0.0007).

The run had instrument flaws, among them agents in both arms that could read
the benchmark's ground truth. The aggregates, per-task counts and every caveat
are in [the results bundle](docs/results/paired-outcome-2026-10.md).

<a id="install"></a>

## Install

One line, on macOS, Linux or WSL (Python 3.10+, `curl`, `tar`). It downloads
the latest release, checks its sha256, arms every host it finds (Claude Code
through its own `claude plugin` CLI), and installs the missing optional tools
tezgah itself uses (orx; `TEZGAH_NO_DEPS=1` skips them). It never installs a
host's own CLI (cursor-agent, pnpm, dsh): it prints the command instead, or
runs it under `tezgah-setup --install --host-deps`.

```bash
curl -fsSL https://raw.githubusercontent.com/r1z4x/tezgah/main/packaging/install.sh | sh
```

Or through npm: `npm i -g @r1z4x/tezgah && tezgah --install`.

A host config it cannot parse is left untouched, every config it changes
keeps a dated `.tezgah-bak` copy, and the install exits non-zero when a host
it set out to arm is not armed.

### What tezgah changes on your machine

- **Host config.** Each armed host gets tezgah's hooks, its MCP rows and a
  managed contract block in the host's global rules file (`~/.claude/CLAUDE.md`,
  `~/.codex/AGENTS.md`, `~/.omp/agent/RULES.md`). Claude Code's hooks ship in a
  plugin registered through `claude plugin`; with no `claude` CLI, Claude stays
  unarmed and the report says so.
- **Agent files in your repositories.** Inside the configured roots, a session
  writes subagent files to `.claude/agents/`, `.codex/agents/` and
  `.opencode/agents/`, and lists those directories in the clone's own
  `.git/info/exclude` (`TEZGAH_NO_EXCLUDE=1` stops that).
- **A daily update check.** The status line asks for a newer release at most
  once a day; `~/.config/tezgah/update-check-off` or `TEZGAH_UPDATE_CHECK=0`
  turns it off.
- **orx.** The install fetches the OpenResearch CLI that research tasks route
  through; `TEZGAH_NO_DEPS=1` skips it.
- **Reply language.** Replies are Turkish by default and the Stop rule holds
  them to it. `--reply-lang en` asks for English, and `any` for your own
  language; neither is checked: `curl -fsSL … | sh -s -- --reply-lang en`.

Rather let your coding assistant do it? Paste this into omp, Claude Code,
Codex, Cursor or opencode:

```text
Install tezgah (https://github.com/r1z4x/tezgah) on this machine and verify it.

1. Check the prerequisites: python3 --version must be 3.10 or newer, and curl
   and tar must exist. If one is missing, stop and tell me which.
2. Run the installer exactly as published - do not edit it or pipe it anywhere else:
   curl -fsSL https://raw.githubusercontent.com/r1z4x/tezgah/main/packaging/install.sh | sh
   Its output must contain "verified tezgah-<version>.tar.gz" (the sha256
   check). If it does not, stop and show me the output.
3. Verify: run ~/.local/share/tezgah/current/bin/tezgah-setup --version and
   ~/.local/share/tezgah/current/bin/tezgah-setup --report, and show me every
   line that says MISS.
4. Tell me which hosts were armed, which repository root was configured
   (default ~/Projects - if my code lives elsewhere, ask me for the directory and
   run ~/.local/share/tezgah/current/bin/tezgah-setup --roots <dir> --install),
   and that I must restart each assistant for the hooks to load.
Do not change any other file and do not uninstall anything.
```

Pinned versions, Windows (`packaging/install.ps1`), offline tarballs, upgrades
and the optional integrations are in the [docs](docs/README.md).

## Supported hosts

**omp** (the primary host, developed and verified against), **Claude Code**, **Codex**, **Cursor**, **opencode**, **dsh** — thin adapters over one shared core.

## Where the depth lives

The gate, the evidence ledger, the host adapters, configuration and development are in [docs/README.md](docs/README.md), one page per question.

## License

MIT — see [LICENSE](LICENSE).
Vendored skills (`ponytail`, `no-ai-slop`, `i-have-adhd`) carry their own MIT terms, recorded in [NOTICE](NOTICE).
