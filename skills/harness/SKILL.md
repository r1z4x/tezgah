---
name: harness
description: >
  Pick and run the right multi-agent harness for a task in this tree, backed by the
  codegraph index. Routes to the graph-map, graph-review, or graph-impact dynamic
  workflows, or to a single general-purpose subagent briefed with the codegraph tools when a full harness is overkill.
  Use when the user asks for depth, coverage, an audit, a full review, "every call
  site", "what breaks if", "how does this work end to end", says ultracode, or when
  a task is too wide for one context window.
---

This skill is the **multi-agent** sense of the word "harness": it picks and runs a
multi-agent harness over the code graph for a task too wide for one context window.
It is not tezgah's own layer around a host, and not the runtime a host itself is -
`docs/layers.md` (repo-relative) separates the three senses, and the injected
`<harness-reminder>` text is the other one.

Repo tree is indexed by codegraph, at the repo's own `.codegraph/codegraph.db`.
Graph beats grep for structure. On Claude load the one default MCP tool with
ToolSearch("select:mcp__codegraph__codegraph_explore") before searching by hand;
on Codex, Cursor, opencode, dsh and omp that server is registered too. Everything
else is the CLI and needs no loading: `codegraph callers`, `callees`, `impact`,
`affected`, `node`, `files`, `status`, `query`, `explore`. A missing index is
`codegraph init` (about 1 s for a repo this size) and a stale one is
`codegraph sync`.

## Route

The table below is the Claude path. `Workflow(...)` is a Claude Code runtime; on
Codex, Cursor, opencode, dsh and omp run the SAME phases with the host's subagents - one
graph-backed reader per module in parallel, a synthesizer, then a critic that
names what was dropped - and report the same caps.

| Request shape | Harness | Cost |
|---|---|---|
| "how does X work", "map this", unfamiliar subsystem before an edit | `Workflow({name:'graph-map', args:{focus:'...'}})` (other hosts: parallel readers + synthesize + gap-check) | ~11 agents |
| "review this", diff/branch/PR, "find bugs in my changes" | `Workflow({name:'graph-review', args:{target:'...'}})` (other hosts: per-dimension reviewers, then refuters) | ~13 agents |
| rename, API migration, "every call site", "safe to delete?" | `Workflow({name:'graph-impact', args:{target:'<symbol>'}})` (other hosts: trace callers, plan per module, sweep blind spots) | ~8 agents |
| one lookup, one file, scope already clear | no workflow - one general-purpose subagent briefed with the codegraph tools, or do it inline | 0-1 agents |

Each workflow already fans out and adversarially verifies its own output. Do not re-verify its findings by
hand, and do not run two harnesses on the same question.

## Rules

Report the harness and agent count before launching, so the cost is visible up front.

Every workflow returns caps explicitly - `modules_dropped`, `unverified`, `modules_skipped`,
`graph_blind_spots`. Relay them. A capped run reads as complete coverage unless you say what was dropped.

`graph-review` splits findings into `confirmed` (no refuter refuted it), `refuted` (do not report as bugs),
and `unverified` (hit the cap - label them as such). Never promote a refuted or unverified finding.

`graph-impact`'s `graph_blind_spots` are call sites the graph could not see - string dispatch, config,
templates, generated code. They are usually where a migration actually breaks. Lead with them.

Chain across turns instead of building one giant workflow: map, then let the user decide, then impact, then
review. Read each result before choosing the next phase.

Skip the harness for small, local, already-understood edits. Multi-agent orchestration costs real tokens and
buys nothing when one context window already holds the whole problem.

## Repair

Workflow name not found on Claude -> the script's `meta` block failed to parse, or the file is not under a loaded
workflows directory. `~/.claude/workflows/` is user-global (installed by `bin/tezgah-setup --install`).
On Codex, Cursor, opencode, dsh and omp there is no `Workflow` runtime: run the phases by hand as above (dsh exposes a single subagent at a time, so run its readers sequentially).
Survey/trace returns nothing -> repo not indexed yet; run `codegraph init` in the repo root (or
`codegraph sync` to bring an existing index up to HEAD), then retry. One live MCP writer per project: a
second writer waits for the lock, and `codegraph unlock` clears the stale one a dead writer left - a run
that hangs at the index is that lock, not a slow query.
Editing a harness: scripts live in the plugin's `workflows/` directory, symlinked from `~/.claude/workflows/*.js`; re-run with
`Workflow({scriptPath:'...'})` while iterating, `Workflow({name:'...'})` once it is right.
