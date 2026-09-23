# E1 — the injection budget and rule loss

## The change under measurement
None. This measures the shipped builder (`hooks/tezgah_context.py`) as it stands.

## What it predicts
1. `session_start` and `user_prompt` inject **at most 80% of their budget**
   (`DEFAULT_BUDGET = 12000` bytes; the per-event overrides in `CONTEXT_BUDGET`).
2. Over the whole history of `~/.cache/tezgah/context-drops.log`, **no drop names
   a block that carries a rule** — the always-on core and the per-turn reminder
   are not in `DROP_ORDER` and are never given up.
3. `subagent_start` is the event that actually binds: it drops at least one
   block, because its budget is the smallest (`{subagent_start: 4000}`) while the
   live-state half is the same.

## What would falsify it
- A `session_start` or `user_prompt` build over 80% of its budget.
- A drop row naming a `CORE_RULES` label, or any drop at `session_start`.
- `subagent_start` dropping nothing on this machine.

## Why this is worth a measurement
The rebuild ships generated per-host text and a live-state half that grows with
the repository (lessons, plans, graph status, the active task, the delta). The
design calls a dropped block "bloat as rule loss" and the audit already caught
one real instance of it (a new core rule pushed the subagent text over its
budget and it dropped `consult`). A metric for how close a normal session sits to
the ceiling is what says whether that risk is theoretical or routine.

## Method
- Build a synthetic repository under a temp HOME: a `plans/open/` plan with a
  phase and an allowlist, a `.tezgah/lessons.md`, enough files for the graph
  glance, and the kill-switch-free config dir.
- Call `context_for` for `session_start`, `user_prompt` and `subagent_start` with
  `with_core` both ways, and record **per-key byte sizes** from `budgeted`'s
  parts plus the final returned size against the event's limit.
- Read the drop log's whole content and classify each drop by whether the key is
  a `CORE_RULES` label, a droppable live-state key, or other.
- Repeat the `user_prompt` build with a 5x lessons file and a 5x plan set, to see
  which key crosses first.

## Reported rows
One `results.jsonl` object per (event, with_core, variant) with: `event`,
`limit`, `total_bytes`, `pct_of_limit`, `blocks` (key → bytes), `dropped`,
`command`, `source`.
