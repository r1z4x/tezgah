---
id: 002
title: an agent-reachable documentation layer under docs/
status: done
branch: main
pr:
created: 2026-09-18
updated: 2026-09-18
---
## Goal
The repository explains itself to a *user* (README) and to a *future session*
(AGENTS.md, plans/), but not to an agent that has to reason about the internals:
what the layers are, what runs when, which host can see what, where a rule lives,
what stops a claim. Build a `docs/` layer whose entry point is a router, so a
session (tezgah's own or any other agent) can reach the right page in one hop
instead of reading 55 Python files.

## Acceptance
- [x] `docs/README.md` answers the four questions the request names - why the
      project exists, what its architecture is, what it uses, what is inside it -
      and routes each to exactly one page, with a "start here" path per role
      (agent mid-task, maintainer, reviewer, new host).
- [x] Ten pages exist, each opening with what it is / who reads it / when:
      architecture, hosts, contract, gate, evidence, status-line, skills,
      testing, operations, glossary. Every non-obvious claim carries `path:line`.
- [x] `docs/index.json` lists every page with `{path, title, answers, audience,
      sources}`; a test asserts every entry resolves and every `docs/*.md` has an
      entry (no page can be added silently).
- [x] `bin/tezgah-docs [QUERY]` prints the matching page path(s) from that index,
      so an agent reaches a page without reading the index prose.
- [x] `AGENTS.md` carries one line pointing at `docs/README.md`.
- [x] No page duplicates the README's user-facing content or the CHANGELOG; the
      glossary is the only place a term is defined and other pages link to it.
- [x] Verification: an independent agent, given only `docs/README.md` and the
      index (no code reading), answers ten fixed questions with file:line for
      each - which hosts can observe a skill read, what stops an unverified
      "done", how a rule is disarmed, where a deny comes from, what the status
      states are, how a skill reaches a host, how the ledger records a check,
      what the install writes per host, how to run the checks, and what "root"
      means. Its answers are compared against the code.
- [x] `ruff check .` clean and `python3 -m unittest discover -s tests` green.

## State
Landed: `docs/` (ten topic pages, 1,974 lines total, plus the router and
`docs/index.json`), `bin/tezgah-docs`, and `tests/test_docs.py` (7 tests: index
vs directory, every entry's contract, the router links every page, every page
carries `## Source of truth` and a `path:line`, every cross-page anchor resolves
against the target's heading slugs, the CLI answers a query and refuses an empty
match).

Written by ten subagents, one page each, against a fixed doc contract. Their work
surfaced three real defects, all fixed in the same session:
1. Claude's transcript half resolved a Bash call with a substring test, so the
   `research` mark could never light and a mere mention lit `consult`; it now uses
   the shared `shell_kind` tokenizer (tests/test_statusline.py, two new cases).
2. dsh's status line had no used marks at all - the shared PostToolUse hook never
   recorded a used kind and dsh has no transcript; the hook now records the kind
   it can see and SubagentStart records `orch`.
3. The opencode gate's JavaScript half still carried the pre-lease consent model:
   a repeat of an unapproved irreversible command passed, and a `grant` was never
   spent. It now matches the Python gate (repeat refused with the ask-stands
   clause, grant spent by the outcome row, refusal names the digest and the CLI).

Verification: an independent agent answered ten fixed questions from `docs/`
alone (no code), with citations; a second agent checked 58 of those citations
against the tree (52 confirmed, 1 my own brief's file-prefix error, 2 genuine
drifts); a third re-resolved every citation in the ten pages after the code
changes (~970 tokens, 91 corrected, 2 sentences that had become false, and the
gate.md paragraph that documented the divergence as live). Checks: `ruff check .`
clean, 744 tests green, `--install` and `--sync` exit 0, plugin copy
byte-identical for `docs/`, `bin/tezgah-docs` and the patched plugin.

Two follow-ups the pages record rather than bless: the installer writes codex's
files in `install_codex` but no single page prints every host's written-file list
as one table (`docs/hosts.md` is where it belongs), and the scout used for the
acceptance run had no shell, so `bin/tezgah-docs` was exercised by
`tests/test_docs.py` rather than by that run.

## Next
- none open. The next session that changes a cited file owes the pages a citation
  refresh: `path:line` rots when the code moves, and only `tests/test_docs.py`'s
  weaker checks (a citation exists, the anchors resolve) run automatically.
