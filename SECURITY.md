# Security

## Reporting a vulnerability

Report vulnerabilities privately through GitHub's security advisories
(**Security** tab → **Report a vulnerability**), or directly at
https://github.com/r1z4x/tezgah/security/advisories/new. Please do not open a
public issue for a suspected vulnerability.

## In scope

tezgah runs shell hooks, writes host configuration, and injects text into every
session. Anything that makes a hook execute attacker-controlled code, leaks a
key into a config file, widens a sandbox, or lets repository content escalate
into instruction text is in scope.

## What to include

- the host (Claude Code, Codex, Cursor, opencode, dsh, omp) and its version
- the tezgah version: `bin/tezgah-setup --version`
- a minimal reproduction

We aim to acknowledge a report within a few days and to ship a fix in the next
release, with credit if you want it.
