# Models: which model runs which delegated task, and how the table stays current

The model table and the tier router. Read this page before you spawn a worker, when
a host runs an agent on a model you did not expect, when you change a model in the
table, or when `tezgah-route --check` says the table is stale. It is a capability,
not a rule: the ORCHESTRATE paragraph tells the router to use it, and nothing here
refuses a call.

## The shape

The main thread keeps one model for the whole session. The prompt cache is per
model, so a switch re-reads the whole cached prefix at write price; measured on this
repository's own omp logs (2026-08-31..2026-09-30), a main-thread Opus 5.5 turn read
a mean of about 435k cached tokens, so one Opus -> Sonnet -> Opus switch pair costs
about $3.26 against about $0.02 saved per explore turn. Routing therefore happens
where it is free: at the subagent a task is handed to.

Every generated agent has a slot (`AGENT_SLOT`, `hooks/tezgah_models.py:107-110`)
and every slot a model per family (`SLOTS`, `hooks/tezgah_models.py:85-106`). The
three tier workers - `tezgah-cheap`, `tezgah-standard`, `tezgah-frontier` - are
generated in every tezgah root because routing needs no capability (`ROLES`,
`hooks/tezgah_agents.py:239-261`; their brief, `_worker_body`,
`hooks/tezgah_agents.py:217-238`). A cheaper worker that meets work above its tier
answers `ESCALATE: <why>`, and the router restarts the task on `tezgah-frontier`
with the original brief rather than handing the failed trajectory up: continuing a
cheap trajectory on a frontier model was the most expensive option measured
(arXiv 2608.24358, Table 1: 1.61 cost units against 0.72 for frontier-only).

## The table (snapshot 2026-09-30)

| slot | agents | anthropic | zai (omp's own provider) | openai | any (OpenRouter id) |
|---|---|---|---|---|
| cheap | tezgah-cheap | Opus 5.5 @low | `zai/glm-5.3-flash` | GPT-6.1 Sol @low | GLM-5.3 Flash |
| explore | omp's bundled `scout` | Opus 5.5 @medium | `zai/glm-5.3-flash` | GPT-6.1 Sol @low | DeepSeek V4.1 Flash |
| standard | tezgah-standard | Opus 5.5 @medium | `zai/glm-5.3` | GPT-6.1 Sol @high | GPT-6.1 Sol @high |
| frontier | tezgah-frontier, tezgah-reviewer | Opus 5.5 @high | `zai/glm-5.3` | GPT-6 Astra @high | Opus 5.5 @high |

Why these, briefly. Inside the Anthropic family the lever is effort, not model:
Opus 5.5 and Sonnet 5.5 read cache at the same $0.20 per 1M tokens, and on
Artificial Analysis's per-effort runs (v4.3, read 2026-09-30) Sonnet 5.5 is not
cheaper per task at an equal Terminal-Bench 4.0 score (@high 43.9 at $1.08, @xhigh
57.1 at $2.74, against Opus 5.5 @high 56.6 at $1.82). Opus 5 lists at $5/$25 with an
index of 50.8 against Opus 5.5's $4/$20 and 57.6, so it is never a cheaper tier.
Across families the cheap tier is where the saving is: DeepSeek V4.1 Flash reads
cache at $0.0029 per 1M tokens and scores 84.0 on AA's long-context reasoning
against Opus 5.5's 84.7. Estimated on this repository's window, routing delegated
work across families costs about 25-27% less than all-Opus subagents, and tier
routing inside the Anthropic family at most 2.3% less; moving Opus subagents from
@high to the table's efforts about 11% less (estimates on measured token mixes, not
invoices).

## Which host reads which column

| Host | Family | Where the model lands |
|---|---|---|
| Claude Code | anthropic | the agent file's alias and `effort:` (`_model_lines`): an alias follows the provider and keeps the main session's variant, where a full id breaks on Bedrock, Vertex and a gateway (code.claude.com/docs/en/sub-agents) |
| Codex | openai | `model` and `model_reasoning_effort` in `.codex/agents/*.toml` |
| opencode | any | a selector `--refresh` found in `opencode models` for the slot's model under any configured provider (`resolve_opencode`); none found, no model line, so the agent inherits. The slot's effort rides the JSON agent config as `reasoningEffort` (opencode.ai/docs/agents) |
| omp | anthropic when the session default is an Anthropic model, any otherwise (`omp_mode`); a non-Anthropic default is `any`, never a silent fall back to the Anthropic column | `task.agentModelOverrides`, which omp resolves before the agent or bundled model (omp's own docs: `omp://task-agent-discovery.md`, *Model and structured-output precedence*); every slot is written, the frontier row included, so no agent in the row runs on the session default; each override is a **cross-family fallback chain** (`omp_overrides`): the mode's family first, then every other family this machine holds a credential for (`funded_families` reads omp's auth store and the provider env keys; a family it cannot see is left out, never guessed in) - omp splits the chain into per-spawn patterns (omp's own docs: `omp://settings.md (its `retry.fallbackChains` section)`), so one provider's 429 falls through instead of killing the spawn, measured before this: 24 of 26 post-routing 429s hit a subagent's first request, all on one Opus account every slot shared; `apply_omp` also writes `modelRoles.plan` and `.slow` on that frontier row (same record, same ownership) so plan mode designs on it, and their fallbacks go to `retry.fallbackChains.<role>`, the only chain keys tezgah owns (`default` and provider-keyed chains stay the user's); `apply_omp` writes through the installer's own binary and agent dir, from HOME so a repository's `.omp/config.yml` never leaks machine-wide, and touches only the entries tezgah wrote (recorded in `~/.config/tezgah/models.json` as `omp_written`; a machine written before that record is adopted by its value, `_ours_by_shape`) |
| dsh | - | none: no model setting was found to write |

The orchestrator agent keeps `model: inherit`: it is the main thread's own agent.

| Cursor | - | reads `.claude/agents/` today; Cursor wants its own model ids with the effort **inside** the id (`claude-opus-5[effort=high]`, cursor.com/docs/subagents), and no id this table names was verified against Cursor's models page - so a `.cursor/agents/` rendering that pins a model is not generated yet |

omp's bundled agents are routed through the same record (omp's own docs: `omp://task-agent-discovery.md`, *Bundled agents*): `scout` on the explore slot, `sonic` on the cheap slot, `task` on the standard slot, and `reviewer`/`security-reviewer` left to inherit, because a review is frontier work. A user's own value for any of them wins (see the ownership rule above). Those two are the gap this leaves: the record carries no entry for them, so a session on a cheap model reviews on that model - routing them is one more `BUNDLED` entry, not decided here.

## What is not routed yet

- **Claude Code's built-in subagents** (Explore, general-purpose, Plan) run on the session model. `CLAUDE_CODE_SUBAGENT_MODEL` and a settings `env` block exist but carry no effort, and whether a project agent with a built-in's name replaces it is not stated where it can be cited - so nothing is generated on a guess. What would close it: a documented per-agent effort for built-ins, or a confirmed name-collision rule.
- **Codex's default subagent** (spawned with no agent file): only `.codex/agents/*.toml` carries a model today. What would close it: a documented `[agents]` default settable from a repo-scoped file tezgah already writes.
- **opencode's built-in agents**: the injected JSON could carry `model`/`reasoningEffort` for them, but the merge semantics for a built-in entry are not documented where they can be cited, and a wrong merge would replace a built-in prompt instead of adding a model.
- **dsh**: the model is a plugin config, not an agent field. The composed profile carries `agent-default-model` with `config: {provider: deepseek-official, model: deepseek-flash}` (`dsh --profile web --dump-config`, 2026-09-30) and tezgah's managed patch block already patches plugin config by id (its `llm-pi-ai` row), so a `- id: agent-default-model` row would set the profile's model. Not written, because that knob is one model for the whole session - no `subagent*` entry in the composed tree carries a model - and a single session-wide model is the main thread's setting, which this design deliberately leaves alone ([why the main thread keeps one model](#the-shape)). What would close it: a per-agent model in dsh's config surface.

## The router

`tezgah-route "<brief>"` prints the worker to spawn and why (`main`,
`bin/tezgah-route:45-123`; `route`, `hooks/tezgah_models.py:665-691`). The order is
fixed:

1. A brief naming stored data, a persistence or schema change, a migration,
   credentials, a token or key shape, the gate or security goes
   to frontier by rule (`OVERRIDE`, `hooks/tezgah_models.py:633-641`) - the class
   the judge under-routed in its measurement.
2. Otherwise the brief - redacted with the ledger's own reader
   (`redact`, `hooks/tezgah_integrity.py:625`) - goes to Jev as one Choice over three tiers (`TIER_QUESTION`,
   `hooks/tezgah_models.py:643-664`). Measured on 40 English briefs labelled by
   the same session that wrote the rubric (2026-09-30, twice): under-route 0.025,
   accuracy 0.925 and 0.900, 392 ms median, about 656 input tokens per call; a
   keyword rule on the same set under-routed 0.100.
3. With no judgement (`judge-off`, no key, a failed call) `--phase` picks the tier
   from the static table (`PHASE_TIER`, `hooks/tezgah_models.py:641-642`), and
   with no phase the middle tier is used.

The brief leaves the machine for the judge, like every judgement ([judge](judge.md)).
Every routed call writes one `route` row to the session's ledger. The row names the
tier and the agent. `via` says what set the tier: `rule`, `jev`, `phase` or
`default`. `static` is the static table's tier when the caller passed `--phase`.
`model` names the worker's model on this host. `override` reads `user` when omp holds
an entry the user owns, and `mode` when omp holds none and the session model runs.

A routed worker runs in its own session, so its checks land in its own ledger. On omp
and opencode the child's ledger opens with a `spawned` row that names its parent
session. `tezgah-route --report` matches a route to a child by agent type first. On
opencode the child's own title carries the type. On omp the parent's task call
records which type each named child runs. Order is the fallback, and only when one
child sits between each route and the next with no two spawns in one second. The
report then reads each child's first check: `pass`, `fail`, `ran` (no outcome seen)
or `none`. A route it cannot prove counts as `unjoined`. That covers a tie, an
unrouted spawn, a nested subagent, and every host with no parent signal: Claude
Code, Codex, Cursor and dsh. The parent's own next check never counts for the worker.
One line per `via` and tier gives the first-attempt pass rate. The `jev-below-static`
line counts Jev routes under the static tier and how many of them failed. That is the
measurement that decides whether Jev routing becomes the default or the static table
replaces it.

The second-opinion panel (`bin/consult`) skips a member that shares the session's
model family, not only its exact model. A family comes from a stem in the model name,
so `deepseek-chat` and `deepseek/deepseek-flash` are one family. Bedrock's
`us.anthropic.claude-sonnet-4` is Anthropic, and `o3` is OpenAI. EleutherAI's
`gpt-j` is not OpenAI. `cli:claude` and `cli:codex` carry their vendor's family.
`--use` naming the member asks it anyway.

## Keeping it current

`tezgah-route --refresh` re-reads OpenRouter's public model list, writes prices to
`~/.config/tezgah/models.json`, flags a model that left the list or whose price
moved against the snapshot (`SNAPSHOT`, `hooks/tezgah_models.py:113-117`;
`refresh`, `hooks/tezgah_models.py:549-583`), resolves opencode selectors, and
re-applies omp's overrides. Scores are not re-read - they need a key - so
`tezgah-route --check` reports the snapshot's age and exits 1 past 60 days or with
a flag (`check`, `hooks/tezgah_models.py:609-622`); that is the moment to re-read
the leaderboards and edit `SLOTS`. `tezgah-route --mode anthropic|zai|any|auto|off` pins
omp's family instead of following the session default; `off` removes every entry
and role the table wrote and writes nothing, which is the way back when the
provider those selectors need has no budget - a measured case, not a
hypothetical one. `tezgah-setup --install`
writes omp's overrides and `--uninstall` removes only the `tezgah-*` entries; the
omp status report carries a row for them.

## Source of truth

- `hooks/tezgah_models.py` - the table, the overlay, omp's overrides, refresh, the router.
- `frontier_model(family)` / `cheap_model(family)` in `hooks/tezgah_models.py` - the
  table's accessors: a caller that needs a strong or a cheap model names none of its
  own, but asks for that row's `(model, effort)`, or `None` when the family has no
  such row.
- `bin/tezgah-route` - the CLI.
- `hooks/tezgah_agents.py` - the tier workers and the per-host model lines.
- `hooks/tezgah_policy.py` - the ORCHESTRATE paragraph that tells the router to use it.
- `bin/tezgah-setup` - omp's overrides on install and uninstall, and the status row.
- `tests/test_models.py`, `tests/test_agents.py` - the behaviour pinned.
