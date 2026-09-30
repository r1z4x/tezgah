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

Every generated agent has a slot (`AGENT_SLOT`, `hooks/tezgah_models.py:64-67`)
and every slot a model per family (`SLOTS`, `hooks/tezgah_models.py:50-63`). The
three tier workers - `tezgah-cheap`, `tezgah-standard`, `tezgah-frontier` - are
generated in every tezgah root because routing needs no capability (`ROLES`,
`hooks/tezgah_agents.py:260-294`; their brief, `_worker_body`,
`hooks/tezgah_agents.py:241-256`). A cheaper worker that meets work above its tier
answers `ESCALATE: <why>`, and the router restarts the task on `tezgah-frontier`
with the original brief rather than handing the failed trajectory up: continuing a
cheap trajectory on a frontier model was the most expensive option measured
(arXiv 2608.24358, Table 1: 1.61 cost units against 0.72 for frontier-only).

## The table (snapshot 2026-09-30)

| slot | agents | anthropic | openai | any (OpenRouter id) |
|---|---|---|---|---|
| cheap | tezgah-cheap, tezgah-verifier | Opus 5.5 @low | GPT-6.1 Sol @low | GLM-5.3 Flash |
| explore | tezgah-explorer | Opus 5.5 @medium | GPT-6.1 Sol @low | DeepSeek V4.1 Flash |
| standard | tezgah-standard | Opus 5.5 @medium | GPT-6.1 Sol @high | GPT-6.1 Sol @high |
| frontier | tezgah-frontier, tezgah-reviewer, tezgah-researcher | Opus 5.5 @high | GPT-6 Astra @high | Opus 5.5 @high |

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
| Claude Code, Cursor | anthropic | the agent file's `model:` and `effort:` (`_model_lines`, `hooks/tezgah_agents.py:319-326`); Cursor reads the same file, and whether it maps `claude-opus-5-5` is unverified |
| Codex | openai | `model` and `model_reasoning_effort` in `.codex/agents/*.toml` |
| opencode | any | a selector `--refresh` found in `opencode models` for the slot's model under any configured provider (`resolve_opencode`, `hooks/tezgah_models.py:221-241`); none found, no model line, so the agent inherits |
| omp | anthropic when the session default is an Anthropic model, any otherwise (`omp_mode`, `hooks/tezgah_models.py:117-122`) | `task.agentModelOverrides`, which omp resolves before the agent file; frontier agents get no entry and inherit the session default (`omp_overrides`, `hooks/tezgah_models.py:125-137`); the user's own entries are kept (`apply_omp`, `hooks/tezgah_models.py:161-180`) |
| dsh | - | none: no model setting was found to write |

The orchestrator agent keeps `model: inherit`: it is the main thread's own agent.

## The router

`tezgah-route "<brief>"` prints the worker to spawn and why (`main`,
`bin/tezgah-route:32-89`; `route`, `hooks/tezgah_models.py:291-309`). The order is
fixed:

1. A brief naming stored data, a migration, credentials, the gate or security goes
   to frontier by rule (`OVERRIDE`, `hooks/tezgah_models.py:262-265`) - the class
   the judge under-routed in its measurement.
2. Otherwise Jev answers one Choice over three tiers (`TIER_QUESTION`,
   `hooks/tezgah_models.py:269-288`). Measured on 40 English briefs labelled by
   the same session that wrote the rubric (2026-09-30, twice): under-route 0.025,
   accuracy 0.925 and 0.900, 392 ms median, about 656 input tokens per call; a
   keyword rule on the same set under-routed 0.100.
3. With no judgement (`judge-off`, no key, a failed call) `--phase` picks the tier
   from the static table (`PHASE_TIER`, `hooks/tezgah_models.py:267-268`), and
   with no phase the middle tier is used.

The brief leaves the machine for the judge, like every judgement ([judge](judge.md)).
A routed call writes one `judge` ledger row with the tier, so a later fold can join
the tier to the gate outcome of the work it routed.

## Keeping it current

`tezgah-route --refresh` re-reads OpenRouter's public model list, writes prices to
`~/.config/tezgah/models.json`, flags a model that left the list or whose price
moved against the snapshot (`SNAPSHOT`, `hooks/tezgah_models.py:70-74`;
`refresh`, `hooks/tezgah_models.py:186-218`), resolves opencode selectors, and
re-applies omp's overrides. Scores are not re-read - they need a key - so
`tezgah-route --check` reports the snapshot's age and exits 1 past 60 days or with
a flag (`check`, `hooks/tezgah_models.py:244-257`); that is the moment to re-read
the leaderboards and edit `SLOTS`. `tezgah-route --mode anthropic|any|auto` pins
omp's family instead of following the session default. `tezgah-setup --install`
writes omp's overrides and `--uninstall` removes only the `tezgah-*` entries; the
omp status report carries a row for them.

## Source of truth

- `hooks/tezgah_models.py` - the table, the overlay, omp's overrides, refresh, the router.
- `bin/tezgah-route` - the CLI.
- `hooks/tezgah_agents.py` - the tier workers and the per-host model lines.
- `hooks/tezgah_policy.py` - the ORCHESTRATE paragraph that tells the router to use it.
- `bin/tezgah-setup` - omp's overrides on install and uninstall, and the status row.
- `tests/test_models.py`, `tests/test_agents.py` - the behaviour pinned.
