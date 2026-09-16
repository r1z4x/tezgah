# Harness benchmark: tezgah vs oh-my-pi (omp)

Compares the tezgah harness against [oh-my-pi](https://github.com/can1357/oh-my-pi)
(`omp`) on automated coding tasks. Two rounds are preserved; raw per-run logs,
JSON results, fixtures, tasks and the runners live beside this file.

## Arms

| Arm | What it is |
|---|---|
| `tezgah+opencode` | opencode 1.18.31 with the tezgah contract, skills, subagents and gate, plus the codebase-memory-mcp graph. Browser/device MCPs disabled for speed and parity. |
| `omp+graph` | bare omp control: same model, same graph MCP, no tezgah layer. |
| `omp+tezgah-port` | omp with the tezgah CORE as `AGENTS.md`, the 8 tezgah skills, the 5 tezgah subagents rewritten to omp's agent schema, the gate as an omp hook, and the graph MCP. |

Model held constant on every arm: `openrouter/deepseek/deepseek-v4-flash`.

## Round 2 (20 tasks x 3 arms, 60 runs)

Tasks cover rounding/off-by-one bugs, mutable-default and shared-state bugs,
spec-implemented features, cross-file renames and signature changes, trust-boundary
validation, an O(n^2)->O(n) rewrite, Unicode normalization, timezone-aware input,
an exact error contract, a Turkish BLUF explanation, no-collateral scoping, and
two read-only "who calls X / what breaks" impact tasks.

| Arm | Pass | Cost | Median | Max | Tools | Graph calls | Input tok | Output tok |
|---|---|---|---|---|---|---|---|---|
| tezgah+opencode | 19/20 | $0.0743 | 48s | 159s | 160 | 3 | 409,750 | 21,223 |
| omp+graph | 20/20 | $0.0656 | 47s | 240s | 165 | 0 | 187,390 | 29,074 |
| omp+tezgah-port | 19/20 | $0.1490 | 51s | 240s | 228 | 0 | 813,528 | 44,544 |

Failures:

- `t6` / `tezgah+opencode`: read "%20 KDV'li toplam" as the tax amount (0.60) instead of the total with tax (3.60). Genuine.
- `t19` / `omp+tezgah-port`: answered the transitive impact set (added `tests/test_report.py`). The recorded ground truth listed direct call sites only, so this is a ground-truth limitation, not clearly a failure.

Graph use: only `tezgah+opencode` reached for the graph (`search_graph` /
`search_code` on t19 and t20). All 40 omp runs used grep/shell only, including
the ported gate arm - the gate blocks the `grep` tool but keeps tezgah's own
shell-`rg` escape hatch, which the agent took.

### Token accounting caveat (read before comparing "output tokens")

`omp` reports reasoning inside `output`; opencode reports it in a separate
`reasoning` field (`oc.total = input + output + cache_read + reasoning`;
`omp.totalTokens = input + cacheRead + output`, with `reasoningTokens` a subset
of `output`). Raw `output` is therefore not comparable across arms. Corrected,
reasoning-inclusive generated tokens:

| Arm | Text | Reasoning | Generated |
|---|---|---|---|
| tezgah+opencode | 21,223 | 8,806 | 30,029 |
| omp+graph | 20,919 | 8,155 | 29,074 |
| omp+tezgah-port | 30,364 | 14,180 | 44,544 |

The port generates ~48% more than the other two (more text and more reasoning),
driven by more turns and tool calls (228 vs 165 overall; e.g. t15 28 steps vs 6,
t20 15 vs 3, t10 22 vs 10).

### The port's dominant cost is an input prompt-cache miss, not its output

Per-step `usage` shows the port failing to reuse the provider prompt cache.
`t17` (4 steps both arms):

```
omp+graph        cacheRead 26624 26624 27136 27392   input  221  621  382  445  (sum 1,669)
omp+tezgah-port  cacheRead  7168 29440  7168 30208   input 22399  327 23170  482  (sum 46,378)
```

`t18` shows the same shape: the port's first two steps reuse only 7,168 cached
tokens and are billed ~22.4k fresh input each, while `omp+graph` reuses
26.6k-27.9k. That repeats across tasks (several tasks have identical step counts
but 5-28x the non-cached input).

A component-removal probe (`probe-deepseek.log`, 7 variants x 2 runs, run via
the DeepSeek provider because the OpenRouter key hit its spend limit after the
scored run) isolates this:

- On DeepSeek direct the warm-cache penalty is only ~1.9k tokens once per
  session (port step-0 fresh input ~2,200 vs graph ~300), not the ~22k seen
  through OpenRouter. The large OpenRouter penalty is therefore dominated by
  that provider's prefix-cache behaviour, not by a tezgah component.
- The ~1.9k tracks the presence of `AGENTS.md` and **not** any single ported
  component: removing the hook, the MCP config, the skills or the agents one at
  a time leaves step-0 fresh input at ~2,150-2,250. Warm cached prompt size is
  ~26.1k-27.3k in every variant, so the ported metadata itself is small.
- The port's total input is inflated mainly by **more turns** (13 vs 6 on this
  task), which is agent behaviour, not a fixed prompt tax.

## Code quality (round 2, naive metric `output` cannot see this)

`quality.py` diffs every run against the pristine fixture. Median stats:

| Arm | Median added lines | Files touched/task | Comments added | Docstring lines | Turkish replies | Claims a verification |
|---|---|---|---|---|---|---|
| tezgah+opencode | 2 | 1 | 1 | 1 | 75% | 60% |
| omp+graph | 2 | 1 | 8 | 10 | 30% | 55% |
| omp+tezgah-port | 2 | 1 | 1 | 6 | 65% | 65% |

Diff *size* is equal; diff *discipline* is not. On `t5` (root cause, shared
parser) all three found the same root cause and fixed it in a shared helper, but:

- `tezgah+opencode` added 12 lines (`unicodedata.category(ch) != "Cf"`, one
  docstring).
- `omp+tezgah-port` added 25 lines, including a defensive `isinstance` guard and
  a scope-creep edit to `validate.py`.
- `omp+graph` added 56 lines: a 45-line hex-escaped regex with a comment per
  Unicode block, plus a `validate.py` behaviour change nobody asked for.

So the contract's measurable benefit in this round is **discipline**, not task
success: fewer unrequested comments/docstrings (1 vs 8/10), fewer Turkish-rule
misses on English-prompted tasks (75%/65% vs 30%), and less over-reach. The port
transfers most of it (comments 1, Turkish 65%) but not all (docstring lines 6 vs
1, longest replies, and the `t5` over-reach persists).

## Round 1 (6 tasks x 3 arms, 18 runs)

Easier task set; every arm passed every task, so it separated cost/context only.

| Arm | Pass | Cost | Median | Max | Input tok | Output tok |
|---|---|---|---|---|---|---|
| tezgah+opencode | 6/6 | $0.0436 | 139s | 1041s | 258,881 | 7,295 |
| omp-bare | 6/6 | $0.0339 | 62s | 100s | 141,549 | 15,778 |
| omp+tezgah-port (AGENTS.md only) | 6/6 | $0.0423 | 72s | 127s | 223,081 | 19,727 |

## Always-on context budget (measured by the installer)

`tezgah-setup` (no flags, or `--install`) now prints what tezgah injects before
the first turn, so the cost side of each structure is visible:

```
context budget (always-on text; ~tokens = chars/4):
     core contract (per session)        ~ 1.2k tok    4836 chars
     per-turn reminder                  ~ 0.2k tok     621 chars
     skill metadata (8)                 ~ 1.1k tok    4255 chars
     subagent metadata (5)              ~ 0.2k tok     891 chars
     full contract (on demand)          ~ 5.0k tok  (only when the skill is read)
     MCP tool schemas                   host-side, not counted
```

~2.7k tokens are always-on; the largest single band after the core is the skill
metadata. MCP tool schemas are the host's size to report and are the one band
this instrument cannot see.

## Reproduce

Round 2:

```sh
cd round2
python3 run_bench2.py            # needs omp, opencode, codebase-memory-mcp, OPENROUTER_API_KEY
python3 analyze2.py
```

Round 1: `cd round1 && python3 run_bench.py && python3 analyze2.py` (round 2 ships the analyzer).

Per-run stdout/stderr are in `round*/logs.tar.gz`; the scored rows are
`round*/results.jsonl`.

## Limitations

- One sample per (task, arm); a single model. Per-task variance is large enough
  that a 1/20 difference is not decisive.
- `t19` ground truth is under-specified (direct call sites vs transitive impact).
- Two runs (`t5`, both omp arms) hit the 240s cap, though their fix had already
  been written to disk and passed every check.
- The benchmark measures the harness, but the model does most of the work; the
  contract's effect shows up in cost, context and verbosity, not in pass rate here.
