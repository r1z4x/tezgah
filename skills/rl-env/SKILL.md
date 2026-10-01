---
name: rl-env
description: >
  Use when the task is to build, port or reason about an RL training environment
  - the vendored FineEnvs set for authoring one across OpenEnv (HTTP + MCP,
  Hugging Face), OpenReward / ORS (a reward with each tool call), Verifiers
  (Prime Intellect, in-process tools and rubrics) and NeMo Gym (HTTP plus a
  post-episode /verify grader), with the orchestrator that interviews the user
  and ports one description across all four, including prompts like "make an env
  where the agent does X" or "wrap my game in OpenEnv". Read one entry, never
  the tree.
---

# rl-env: authoring an RL environment

Five upstream skills, vendored byte-for-byte from FineEnvs at the revision
`SOURCE` names (Apache-2.0; `NOTICE` records what changed, which is nothing but
the vendoring itself). They are instructions, not machinery: nothing here trains
a model or runs a rollout.

## What this repository does not have

An environment is a server, a task set and a reward; a trainer is a separate
thing that tezgah never owns (`docs/layers.md`). So this skill hands the user a
runnable environment, not a trained model: the job that consumes one needs a GPU,
a sandbox provider and an inference server. On this machine that job belongs to
`orx`, whose `hf` backend is the configured one - `orx compute status` says
whether it still is. Name that cost to the user before scaffolding anything, and
never claim a training result this skill cannot produce.

## Read one entry, never the tree

| Entry | What it produces |
|---|---|
| `rl-env-from-description/SKILL.md` | The orchestrator: a clarifying interview (`references/interview.md`), then the same description ported to all four frameworks - start here unless the user has already named a framework |
| `generate-openenv-env/SKILL.md` | OpenEnv (Hugging Face): HTTP + MCP, tools discovered through `list_tools()`, an optional Gradio UI, a Docker container or HF Space at the end |
| `generate-ors-env/SKILL.md` | OpenReward (ORS): HTTP + REST + SSE, a reward inline with each tool call instead of after the episode, task-spec sessions, train/val/test splits |
| `generate-verifiers-env/SKILL.md` | Verifiers (Prime Intellect): in-process tools with no HTTP server, composable rubrics, the shortest path from a prototype to a TRL `GRPOTrainer` |
| `generate-nemo-gym-env/SKILL.md` | NeMo Gym (NVIDIA): tools as `app.post()` endpoints with cookie sessions, a post-episode `/verify` grader, Ray-based orchestration |

Each of the four ports ships its own `references/architecture.md`; the
orchestrator ships one reference per framework beside its interview notes. The
framework whose shape matches the user's existing trainer is the one to pick, and
the four are not interchangeable - the orchestrator's own table says which is
right for what.

## Provenance

`SOURCE` carries the upstream revision, the per-file sha256 of every vendored
body, and the fact that nothing but the vendoring changed. Re-vendoring means
re-running the checkout and the table, never editing a vendored file in place:
an edited body is no longer the method `SOURCE` records.
