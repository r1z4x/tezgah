# E5 analysis — round 2 is void: the provider refused every call (402)

Raw: `raw/e868c63e-….log` (the run's own log, filed as the receipt) and the rows
under `…/local-runs/e868c63e-…/repo/benchmarks/arm-bench/results/orx/nogit/*.jsonl`.

## Outcome — no prediction is answerable

| arm | n | pass | timeouts | median wall | cost | zero-usage rows | empty final messages |
|---|---|---|---|---|---|---|---|
| `omp+tezgah` | 100 | 0 | 0 | 8.5 s | **$0.0000** | 100 | 100 |
| `omp-bare` | 100 | 0 | 0 | 4.7 s | **$0.0000** | 100 | 100 |
| `orx-mp-prove` | 100 | 0 | 0 | 7.8 s | **$0.0000** | 100 | 100 |

**P1 is half met and half void.** The packaging fix worked — `orx-mp-prove` wrote
its 100 rows, so the round is no longer refused at the pre-flight (that was round
1's failure). But the rows carry no work: every arm, including the treatment,
produced zero tokens at zero cost in under nine seconds.

## The cause, reproduced

One arm-shaped call, by hand, with the arm's own environment:

```
PI_CODING_AGENT_DIR=<arm> TEZGAH_ROOTS=… OPENROUTER_API_KEY=<the file> \
  omp -p --mode json --cwd <dir> --model openrouter/deepseek/deepseek-v4-flash "…"
```

→ `{"type":"message_start","message":{"role":"assistant","content":[],
"api":"openrouter","provider":"openrouter","model":"deepseek/deepseek-v4-flash",
"usage":{"input":0,"output":0,…,"cost":{…"total":0}},"stopReason":"error",
"errorStatus":402}` after 7.1 s.

`402` is "payment required": **the OpenRouter account cannot fund the call the arms
make.** The control is the same binary on the other provider — `omp -p` against
`deepseek/deepseek-flash` answered `ok`, exit 0, in the same conditions — so the
harness, the bridge, the key file and the model slug are all healthy, and the
blocker is credit on one account.

## What this does and does not change

- **The clause is still unmeasured.** Round 2 adds no evidence about it, positive or
  negative; P2 and P3 are unanswered, and this file does not report them as either.
- **Round 2 cost nothing.** A refused call is not billed: $0.0000 across all 300
  rows against round 1's $0.77.
- **Round 1 stands.** Its two arms that ran did spend and did produce rows (C12c,
  the keeper row: C12 as first folded is superseded, its false-completion numbers
  having not reproduced); nothing here revises round 1's direction.
- **The packaging lesson is confirmed, not just predicted.** The treatment arm
  armed and ran this time; the pre-flight check passed *inside a copy of the node
  branch* before the launch, which is the check round 1 skipped.

## What a third round needs

Either credit on the OpenRouter account, so the pinned instrument runs unchanged
and its numbers stay comparable to round 1 — or a disclosed instrument change to a
provider that answers, in which case round 3 is comparable within itself (three
arms, one model, one run) and **not** to round 1. The second is a different
measurement wearing the same name; it should be pre-registered as such before it
runs.
