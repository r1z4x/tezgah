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

## Why tezgah

- **One contract, six hosts.** omp, Claude Code, Codex, Cursor, opencode and
  dsh see the same rules, because every host is a thin adapter over one shared
  core — change a rule once and all of them pick it up.
- **"Done" means the check ran.** A gate of 15 refusals stops the neutered
  check — `--no-verify`, `|| true`, a test piped into `tail`, a skip added
  mid-flight — and blocks the completion claim the run cannot support.
- **Research ships with its library.** Research tasks route through
  OpenResearch with a vendored library of 98 upstream skills, loaded one entry
  at a time so the context stays small.
- **Every rule has an off switch.** Sixteen kill switches — plus per-repo
  marks — remove a rule's text from the session, so the rule actually stops
  rather than merely showing as off.
- **Answers you can act on.** Replies are Turkish and lead with the outcome; a
  list shows at most five ranked items; an estimate is named as an estimate;
  an error reads as location, cause, fix.

<a id="install"></a>

## Install

One line, on macOS, Linux or WSL (Python 3.10+, `curl`, `tar`). It downloads
the latest release, checks its sha256, arms every host it finds, and installs
the missing optional tools tezgah itself uses (orx; `TEZGAH_NO_DEPS=1` skips
them). It never installs a host's own CLI (cursor-agent, pnpm, dsh): it prints
the command instead, or runs it under `tezgah-setup --install --host-deps`.

```bash
curl -fsSL https://raw.githubusercontent.com/r1z4x/tezgah/main/packaging/install.sh | sh
```

Or through npm: `npm i -g @r1z4x/tezgah && tezgah --install`.

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
