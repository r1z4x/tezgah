# E3 analysis - Injected-context budget and block bounds

Run: 2026-09-17, `probe.py` against this checkout (branch
`research/agent-failure-controls`), raw output in `results.jsonl`, plus one
post-hoc measurement in `results-exploratory.jsonl`.

## Result against the protocol

| prediction | result | verdict |
|---|---|---|
| `session_start` in 4-8 KB | 6,716 bytes (98 lines) | confirmed |
| conditional prompt adds <= 1.5 KB, plain arms none | spec +766, research +595, cbm +558, consult +414, plain 0 | confirmed |
| `lessons()` grows < 500 bytes from empty to 200 lines | 754 bytes | **falsified** |
| `open_plans()` grows < 500 bytes from none to eight | 362 bytes | confirmed |

Measured blocks, all events: `always_on_core` 5,387 B; `session_start`
6,716 B; `subagent_start` 1,992 B; `user_prompt` plain 961 B, and with one
conditional rule armed 1,375-1,727 B. At the README's own 4-bytes-per-token
convention the session-start injection is ~1,679 tokens, against the published
band of ~1.3k tokens of contract text plus ~1.3k of skill metadata - the part
measured here is the contract text and the live-state blocks, and the skill
metadata is injected by the host, not by `context_for`.

## The falsified prediction, and what the exploratory run shows

The allowance was wrong, not the cap: a lesson line is truncated to 200
characters (`tezgah_context.lessons`, `ln[:200]`) and five lines are injected, so
the block's ceiling is ~1 KB, and 754 bytes is the block arriving at that ceiling.
The falsifier as written fired, so the prediction is recorded as failed.

The boundedness question itself was then measured directly (post-hoc, labelled
EXPLORATORY because it ran after the results existed):

| block | input A | input B | bytes A | bytes B |
|---|---|---|---|---|
| `lessons()` | 200 lessons | 400 lessons | 1,174 | 1,174 |
| `open_plans()` | 8 plans | 16 plans | 248 | 249 |

Byte-identical for the ledger doubling, and +1 byte for the plans block, which is
the `(+N more)` counter gaining a digit. So the tezgah-owned blocks are bounded
by construction: the injected text cannot grow with the ledger or the plan list.

## Reading

The taxonomy's "context bloat" mode has no tezgah-owned cause in the injected
text: every block is either static (the contract) or capped (lessons 5x200,
plans 3 + a counter, `classify.log` a 64 KB ring). The unbounded context in a
session is the host's conversation history, tool output and MCP schemas - and
tezgah touches that only where a compaction event is wired, which per
`agent://ContextInjection` is Claude, Codex and opencode, and not Cursor, dsh or
omp.

The `subagent_start` block is 1,992 B, roughly 30% of the session-start block:
a subagent is briefed with a smaller core, which is the design intent but also
means a subagent's knowledge of the standing constraints is the reduced text,
not the full one.

## Limits

- `context_for` returns text for an event; a host may inject it differently, and
  opencode has no prompt-time hook at all, so those bytes are a Claude/Codex-shaped
  figure.
- The conditional-key prompts are one synthetic phrase each, so the arming result
  is a property of `PROMPT_HINTS`, not of real usage.
- Bytes are not tokens; the 4:1 conversion is the repository's own convention and
  is used only to compare against the published band.
