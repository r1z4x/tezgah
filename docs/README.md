# tezgah docs

Tezgah arms every AI coding assistant you run with one working contract, inside
the repository roots you configure. These pages are the engineering layer of
this repository. The [README](../README.md) explains the
tool to someone deciding whether to install it; `AGENTS.md` says how to check a
change; these pages explain how the thing actually works, so a session does not
have to re-derive it by reading 55 Python files. Every page is written for one
reader with one question in mind, and every non-obvious claim in it carries a
citation you can open: `path::symbol` into Python code, `path:line` elsewhere.

## Start here

| You are | Read |
|---|---|
| an agent mid-task, before touching a rule or a host | [contract](contract.md), then [hosts](hosts.md) |
| a user in the first session after installing | the [README install section](../README.md#install) (what changed on your machine), then `tezgah-setup --report --live` (every host's hooks run and its gate denies), then [contract](contract.md) for what the session is told |
| an agent that has to decide whether something is safe to do | [gate](gate.md), [evidence](evidence.md) |
| a maintainer adding a rule, a host or a mark | [architecture](architecture.md), then the page of the thing you are adding |
| someone debugging what a session was actually told | [contract](contract.md), [status-line](status-line.md) |
| someone releasing or repairing an install | [operations](operations.md), [environment](environment.md) |
| new to the repository | [architecture](architecture.md), then [glossary](glossary.md) |

## The questions this layer answers

| Question | Page |
|---|---|
| Why does this exist, and what are its layers? | [architecture](architecture.md) |
| What runs when, from session start to Stop? | [architecture](architecture.md) |
| Which layer is tezgah, and which sense of "harness" is which? | [layers](layers.md) |
| What is a session told, and how is a rule disarmed? | [contract](contract.md) |
| Why was my command denied? | [gate](gate.md) |
| What is recorded, and what stops an unverified "done"? | [evidence](evidence.md) |
| What does each status mark mean? | [status-line](status-line.md) |
| What is the judgement seam, who may call it and how is it switched off? | [judge](judge.md) |
| Which model runs which subagent, and how does `tezgah-route` pick one? | [models](models.md) |
| Where does a research line live, and what does `tezgah-research check` refuse? | [research](research.md) |
| What does each host get, and what can it observe? | [hosts](hosts.md) |
| Which skills ship, and how does one reach a host? | [skills](skills.md) |
| How is one feature audited across its layers, and what does a capability change need to carry? | [feature-audit](feature-audit.md) |
| How do I check a change, and how do I test it? | [testing](testing.md) |
| How do I install, upgrade or repair this? | [operations](operations.md) |
| Which environment variables does tezgah read, and what does each change? | [environment](environment.md) |
| What does this word mean here? | [glossary](glossary.md) |
| How is a session meant to run, and what does each tier cost? | [vision](vision.md) |

## How these pages are written

- English. The READMEs are the only translated surface.
- A page opens with what it is, who reads it and when; it ends with
  `## Source of truth`, the files it documents, so a reader can re-verify it
  after a change.
- A non-obvious claim carries a citation. A claim nobody can point at does not
  belong on a page: delete it rather than soften it.
- Code in a Python file is cited by symbol: `path::name` for a top-level def,
  class or assignment, `path::Class.method` or `path::outer.inner` for a nested
  one (`hooks/tezgah_gate.py::decision`). It carries no line number, so an edit
  that moves code above or inside the symbol moves no citation. The sentence says
  which part of the symbol it means. Everything else stays `path:line`: a
  JavaScript, TypeScript, JSON, YAML or Markdown target, module-level code outside
  every def and class, and a range across several symbols. Never name a symbol
  that does not contain what the sentence cites.
- `bin/tezgah-docs --citations` checks both forms. It reads every page under `docs/`
  and the comments and docstrings of the Python code. A string literal, such as a
  fixture or a captured output, is data and is not read. A symbol citation is
  resolved against the AST of the file it names. It fails when that file defines
  no such name. A name without a dot may also name the one method of that name
  in a class. That is how a test pin names its test. A def local to a function
  never stands in for it. A `path:line` with a symbol named
  before it, or right after it in parentheses, must point inside that symbol's
  body. A bare file name means the one code file of that name. The suite also
  checks that a cited file exists and that a cited line is inside it
  (`tests/test_docs.py`). Whether a line still *shows the thing the sentence names*
  is a judgement, not a regex. So a `path:line` with no symbol beside it is left
  unjudged rather than guessed at. So is a `path:N` the pattern cannot read
  (unquoted, or a comma list), but it is counted.
  On this tree, 2026-10-06: 996 judged (995 of them symbol citations), 577 not
  judgeable, 85 of those unreadable.
  The unjudged count is a ratchet. `docs/citations-baseline.json` holds each file's
  count, and a file above or below it fails. Only `--citations --update` rewrites
  it, so CI never writes it. The same pass checks the rule ledger and three inventories read
  by AST: the gate's rule headings and switches ([gate](gate.md)), the judge's
  callers ([judge](judge.md)), and the kill-switch names. CI runs it, and it exits
  non-zero on any of them.
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
tezgah-docs -- --no-verify  # `--` ends the options; a word after it is a query word
tezgah-docs --citations     # the citations that no longer show what they name
```

`bin/tezgah-docs` reads that index and prints file paths, so an agent can pick a
page without guessing and a script can assert the layer is intact. A test keeps
the index and the directory in step: a page cannot be added without an entry, and
an entry cannot name a file that is not there.

## The private layer

`docs/research/` is gitignored: local research notes, kept out of the published
repository. Nothing under it is a source of truth for anything here.
