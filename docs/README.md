# tezgah docs

The engineering layer of this repository. The [README](../README.md) explains the
tool to someone deciding whether to install it; `AGENTS.md` says how to check a
change; these pages explain how the thing actually works, so a session does not
have to re-derive it by reading 55 Python files. Every page is written for one
reader with one question in mind, and every non-obvious claim in it carries a
`path:line` you can open.

## Start here

| You are | Read |
|---|---|
| an agent mid-task, before touching a rule or a host | [contract](contract.md), then [hosts](hosts.md) |
| an agent that has to decide whether something is safe to do | [gate](gate.md), [evidence](evidence.md) |
| a maintainer adding a rule, a host or a mark | [architecture](architecture.md), then the page of the thing you are adding |
| someone debugging what a session was actually told | [contract](contract.md), [status-line](status-line.md) |
| someone releasing or repairing an install | [operations](operations.md) |
| new to the repository | [architecture](architecture.md), then [glossary](glossary.md) |

## The questions this layer answers

| Question | Page |
|---|---|
| Why does this exist, and what are its layers? | [architecture](architecture.md) |
| What runs when, from session start to Stop? | [architecture](architecture.md) |
| Which layer is tezgah, and which sense of "harness" is which? | [layers](layers.md) |
| What is a session told, and how is a rule disarmed? | [contract](contract.md) |
| Why was my command denied, and what needs approval? | [gate](gate.md) |
| What is recorded, and what stops an unverified "done"? | [evidence](evidence.md) |
| What does each status mark mean? | [status-line](status-line.md) |
| What is the judgement seam, who may call it and how is it switched off? | [judge](judge.md) |
| Where does a research line live, and what does `tezgah-research check` refuse? | [research](research.md) |
| What does each host get, and what can it observe? | [hosts](hosts.md) |
| Which skills ship, and how does one reach a host? | [skills](skills.md) |
| How is one feature audited across its layers, and what does a capability change need to carry? | [feature-audit](feature-audit.md) |
| How do I check a change, and how do I test it? | [testing](testing.md) |
| How do I install, upgrade or repair this? | [operations](operations.md) |
| What does this word mean here? | [glossary](glossary.md) |

## How these pages are written

- English. The READMEs are the only translated surface.
- A page opens with what it is, who reads it and when; it ends with
  `## Source of truth`, the files it documents, so a reader can re-verify it
  after a change.
- A non-obvious claim carries `path:line`. A claim nobody can point at does not
  belong on a page: delete it rather than soften it.
- A citation is checked against HEAD by hand, not generated: the suite only
  checks that the cited file exists and that the line is inside it
  (`tests/test_docs.py`), because whether the line still *shows the thing the
  sentence names* is a judgement, not a regex. The layer was audited page by page
  on 2026-09-19 after the code moved under it. The judgement is mechanical in one
  case, and that case is where the drift lands: a citation that names a symbol
  (`note_tool` `hooks/tezgah_integrity.py:1335`) must point inside that symbol's body, so
  `bin/tezgah-docs --citations` re-runs that half of the audit in one command and
  counts the citations it cannot judge - 355 judged and 755 not judgeable on this
  tree, 2026-09-20. Those 755 are the next audit's work list rather than a claim
  of cleanliness. It is a report, not a gate - a
  symbol named beside a path is judged in that file, and a citation with no
  symbol beside it is left unjudged rather than guessed at.
- Two hundred lines is the ceiling. A page that needs more is two pages.
- The [glossary](glossary.md) is the only place a term is defined; every other
  page uses the term and links to it there.
- No page restates the README's user-facing sections (what it enforces, install,
  benchmark, cost) or the CHANGELOG. Link instead of duplicating.

## Reaching a page without reading this file

`docs/index.json` is the machine-readable index: one entry per page with its
title, the questions it answers, its audience and its sources.

```sh
tezgah-docs                 # every page, one line each
tezgah-docs deny shortcut   # the page(s) that answer a query
tezgah-docs --json status   # the same, for a program
tezgah-docs --citations     # the citations that no longer show what they name
```

`bin/tezgah-docs` reads that index and prints file paths, so an agent can pick a
page without guessing and a script can assert the layer is intact. A test keeps
the index and the directory in step: a page cannot be added without an entry, and
an entry cannot name a file that is not there.

## The private layer

`docs/research/` is gitignored: local research notes, kept out of the published
repository. Nothing under it is a source of truth for anything here.
