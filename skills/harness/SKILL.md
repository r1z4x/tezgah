---
name: harness
description: >
  Pick and run the right multi-agent harness for a task in this tree, backed by the
  codebase-memory graph. Routes to the cbm-map, cbm-review, or cbm-impact dynamic
  workflows, or to a single general-purpose subagent briefed with the cbm tools when a full harness is overkill.
  Use when the user asks for depth, coverage, an audit, a full review, "every call
  site", "what breaks if", "how does this work end to end", says ultracode, or when
  a task is too wide for one context window.
---

Repo tree is indexed by codebase-memory-mcp. Graph beats grep for structure. On Claude, load the graph tools with
ToolSearch("select:mcp__codebase-memory-mcp__detect_changes,mcp__codebase-memory-mcp__search_graph,mcp__codebase-memory-mcp__trace_path,mcp__codebase-memory-mcp__search_code,mcp__codebase-memory-mcp__get_code_snippet,mcp__codebase-memory-mcp__get_architecture,mcp__codebase-memory-mcp__query_graph,mcp__codebase-memory-mcp__check_index_coverage") before searching by hand. On Codex, Cursor, opencode, dsh and omp the same tools are exposed directly as MCP tools; use them as-is.

## Route

The table below is the Claude path. `Workflow(...)` is a Claude Code runtime; on
Codex, Cursor, opencode, dsh and omp run the SAME phases with the host's subagents - one
graph-backed reader per module in parallel, a synthesizer, then a critic that
names what was dropped - and report the same caps.

| Request shape | Harness | Cost |
|---|---|---|
| "how does X work", "map this", unfamiliar subsystem before an edit | `Workflow({name:'cbm-map', args:{focus:'...'}})` (other hosts: parallel readers + synthesize + gap-check) | ~11 agents |
| "review this", diff/branch/PR, "find bugs in my changes" | `Workflow({name:'cbm-review', args:{target:'...'}})` (other hosts: per-dimension reviewers, then refuters) | ~13 agents |
| rename, API migration, "every call site", "safe to delete?" | `Workflow({name:'cbm-impact', args:{target:'<symbol>'}})` (other hosts: trace callers, plan per module, sweep blind spots) | ~8 agents |
| one lookup, one file, scope already clear | no workflow - one general-purpose subagent briefed with the cbm tools, or do it inline | 0-1 agents |

Each workflow already fans out and adversarially verifies its own output. Do not re-verify its findings by
hand, and do not run two harnesses on the same question.

## Rules

Report the harness and agent count before launching, so the cost is visible up front.

Every workflow returns caps explicitly - `modules_dropped`, `unverified`, `modules_skipped`,
`graph_blind_spots`. Relay them. A capped run reads as complete coverage unless you say what was dropped.

`cbm-review` splits findings into `confirmed` (no refuter refuted it), `refuted` (do not report as bugs),
and `unverified` (hit the cap - label them as such). Never promote a refuted or unverified finding.

`cbm-impact`'s `graph_blind_spots` are call sites the graph could not see - string dispatch, config,
templates, generated code. They are usually where a migration actually breaks. Lead with them.

Chain across turns instead of building one giant workflow: map, then let the user decide, then impact, then
review. Read each result before choosing the next phase.

Skip the harness for small, local, already-understood edits. Multi-agent orchestration costs real tokens and
buys nothing when one context window already holds the whole problem.

## Repair

Workflow name not found on Claude -> the script's `meta` block failed to parse, or the file is not under a loaded
workflows directory. `~/.claude/workflows/` is user-global (installed by `bin/tezgah-setup --install`).
On Codex, Cursor, opencode, dsh and omp there is no `Workflow` runtime: run the phases by hand as above (dsh exposes a single subagent at a time, so run its readers sequentially).
Survey/trace returns nothing -> repo not indexed yet; run `index_repository(repo_path=<repo root>)`, or
`codebase-memory-mcp cli index_repository --repo-path <root>` in a shell, then retry.
Editing a harness: scripts live in the plugin's `workflows/` directory, symlinked from `~/.claude/workflows/*.js`; re-run with
`Workflow({scriptPath:'...'})` while iterating, `Workflow({name:'...'})` once it is right.
