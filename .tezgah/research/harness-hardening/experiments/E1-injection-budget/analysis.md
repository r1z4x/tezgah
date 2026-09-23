# E1 analysis — the injection budget and rule loss

## What was read
`results.jsonl` (10 rows) plus the machine's whole `context-drops.log` (2 rows).

Rows here are scope: fixture (protocol.md: "Build a synthetic repository under a
temp HOME"), except the drop-log row, which is scope: real.

## Against the predictions

| # | prediction | result | verdict |
|---|---|---|---|
| 1 | `session_start`/`user_prompt` ≤ 80% of budget | 9150/12000 = 76.2%; 1134/6000 = 18.9% | **holds, with 2850 B of margin at `session_start`** |
| 2 | no rule-bearing block is ever dropped | 0 of the 2 drop rows name a core label; both drops are droppable live-state keys | **holds on this machine's history** |
| 3 | `subagent_start` is the event that binds | 4028/4400 = 91.5% (one real drop in history, at the then-limit of 4000) | **holds** |

## What the numbers say
- The core is **8081 B of the 9150 B** a session pays at start (88% of the
  injected text, 67% of the budget). Everything the repository knows about
  itself — lessons, open plans, graph glance, pointer, subagent note — is
  **1069 B combined**.
- The per-turn reminder is **961 B of the 1134 B** a user prompt pays; the
  active-task line is 171 B.
- **The live half does not grow with the repository.** The `--big` variant
  multiplied the lessons file and the open-plan set 5x and moved *neither* block
  (lessons 517 → 518 B, plans 221 → 222 B): both are bounded by the builder, not
  by the input. That is the property that makes prediction 1 stable rather than
  lucky, and it is why the budget has only ever bound at `subagent_start`.
- The one historical drop is the documented failure mode and it was already
  fixed: `subagent_start` dropped `research`, `graph` and `pointer` at a 4000 B
  limit, and the limit is 4400 B now.

## What this does not show
- Whether 9150 B is *the right size*. This measures the budget's headroom, not
  the text's effect: the arm-bench lab's clause ablations are the instrument for
  that question, and they found the effect only on the reporting-language family.
- Any host but the ones in this session. A host that injects the core from a
  static file pays the 1013 B half only; a host that does not pays 9150 B.
