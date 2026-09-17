# E3 - Injected-context budget and block bounds

- Line: `agent-failure-controls`
- Date written: 2026-09-17, committed before any result exists.

## Question

Two of the taxonomy's context modes are "context bloat" and "constraint loss".
Both are claims about what the harness injects. How many bytes does tezgah
inject per event, and does any injected block grow with repository or session
size?

## Instrument

`probe.py`, two parts, no model involved:

- **Part 1 (real repo)**: `tezgah_context.always_on_core()` and
  `context_for(event, cwd)` for `session_start`, `subagent_start` and
  `user_prompt` with five prompts - one plain, and one matching each conditional
  key (`spec`, `consult`, `research`, `cbm`) via `classify_prompt`. Each row
  records bytes, lines and the conditional keys armed. Token estimates use the
  README's own 4-bytes-per-token convention, so a comparison with the published
  band is like for like.
- **Part 2 (fixture)**: `lessons(root)` and `open_plans(root)` are called against
  a throwaway directory holding a 200-line `.tezgah/lessons.md` and eight
  `plans/open/*.md` files, and against an empty directory. The difference is the
  block's growth with unbounded input.

This measures the text tezgah itself injects. It does not measure the host's
conversation history, tool results or MCP schemas - the README already reports
the MCP band as the largest one.

## Prediction

1. `session_start` injects between 4 and 8 KB (the README's published band is
   ~1.3k tokens of contract text plus ~1.3k of skill metadata).
2. A prompt matching one conditional key adds at most 1.5 KB over the plain
   prompt, and a plain prompt arms no conditional key.
3. `lessons()` grows by less than 500 bytes when the file goes from empty to 200
   lines, and `open_plans()` by less than 500 bytes when the repo goes from no
   open plans to eight - both are capped (5 lines, 3 plans).
4. Therefore the blocks tezgah controls are bounded; the unbounded context in a
   session is the host's history and tool output, which is the part tezgah only
   touches on the hosts that wire a compaction event.

## Falsifier

- Prediction 1 fails outside the stated range if the injection is larger than
  the published band.
- Prediction 3 fails if either block grows by more than 500 bytes, which would
  mean a block that scales with repository or ledger size - the bloat mode with a
  tezgah-owned cause. `open_plans`' "(+N more)" line is expected and is inside
  the 500-byte allowance; a growth beyond it is a failed prediction.

## Decision rule

Sizes are reported as measured bytes, not rounded to tokens. A block is called
bounded when its growth is under the stated allowance; the fixture file is
deleted by the probe at the end of the run.

## Reproduce

```sh
python3 .tezgah/research/agent-failure-controls/experiments/E3-context-budget/probe.py \
  | tee .tezgah/research/agent-failure-controls/experiments/E3-context-budget/results.jsonl
```

## Known limits

- `context_for` returns text for the event; a host may inject it differently or
  not at all (opencode has no prompt-time hook).
- The conditional-key prompts are synthetic single-phrase prompts, so the
  classification result is a property of `PROMPT_HINTS`, not of real usage.
