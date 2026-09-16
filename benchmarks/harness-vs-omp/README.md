# Harness benchmark: tezgah vs oh-my-pi (omp)

Compares the tezgah harness against [oh-my-pi](https://github.com/can1357/oh-my-pi)
(`omp`) on automated coding tasks. Two rounds were run; only the scored results
are published here (`round*/results.jsonl`, plus the round-2 `quality.jsonl`).
The working data - fixtures, task prompts, hidden tests, the runners, the port
configuration and the per-run logs - is not part of this repository.

## Arms

| Arm | What it is |
|---|---|
| `tezgah+opencode` | opencode 1.18.31 with the tezgah contract, skills, subagents and gate, plus the codebase-memory-mcp graph. Browser/device MCPs disabled for speed and parity. |
| `omp+graph` | bare omp control: same model, same graph MCP, no tezgah layer. |
| `omp+tezgah-port` | omp with the tezgah CORE as `AGENTS.md`, the 9 tezgah skills, the 5 tezgah subagents rewritten to omp's agent schema, the gate as an omp hook, and the graph MCP. |

Model held constant on every arm: `openrouter/deepseek/deepseek-v4-flash`.

## Round 2 (20 tasks x 3 arms, 60 runs)

Tasks cover rounding/off-by-one bugs, mutable-default and shared-state bugs,
spec-implemented features, cross-file renames and signature changes, trust-boundary
validation, an O(n^2)->O(n) rewrite, Unicode normalization, timezone-aware input,
an exact error contract, a Turkish BLUF explanation, no-collateral scoping, and
two read-only "who calls X / what breaks" impact tasks.

| Arm | Pass (not timed out) | Pass (as recorded) | Cost | Median | Max | Tools | Graph calls | Input tok | Output tok |
|---|---|---|---|---|---|---|---|---|---|
| tezgah+opencode | 19/20 | 19/20 | $0.0743 | 48s | 159s | 160 | 3 | 409,750 | 21,223 |
| omp+graph | 19/20 | 20/20 | $0.0656 | 47s | 240s | 165 | 0 | 187,390 | 29,074 |
| omp+tezgah-port | 18/20 | 19/20 | $0.1490 | 51s | 240s | 228 | 0 | 813,528 | 44,544 |

The two Pass columns differ wherever a run was scored `pass` despite
timing out: the runner called the checker unconditionally after killing the
process, so `omp+graph`'s published 20/20 counted a run that never finished, and
`omp+tezgah-port`'s 19/20 likewise. **The first column is the one to quote.**
Neither timeout was a genuine solve: `t5` was a real task that `tezgah+opencode`
completed in 159s for $0.0078, and neither omp arm produced a scored result for
it.

Failures:

- `t6` / `tezgah+opencode`: read "%20 KDV'li toplam" as the tax amount (0.60) instead of the total with tax (3.60). Genuine.
- `t19` / `omp+tezgah-port`: answered the transitive impact set (added `tests/test_report.py`). The recorded ground truth listed direct call sites only, so this is a ground-truth limitation, not clearly a failure. Note that the checker scored it by **exact set equality**, which cannot distinguish an over-broad answer from a wrong one; the new benchmark in `../arm-bench/` scores this family by precision and recall instead.

Cost accounting defect: `t5` timed out on both omp arms (`rc=-1`,
`wall_s=240.1`) and its `tokens` block is zero-filled (`cost: 0.0`), so the omp
cost totals above omit a task `tezgah+opencode` paid $0.0078 for. Read every
omp-vs-tezgah cost comparison here as one-sided in tezgah's favour until that
run is re-costed. Because a timed-out run is also a zero-cost run, publishing
timeout-excluded and timeout-included totals side by side would show the same
number for both omp arms - the run has to be re-costed, not just re-bucketed.

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

The published `results.jsonl` carries only `input`/`output`/`cache_read`/`total`,
with no `reasoning` field, so this text/reasoning split comes from the
unpublished per-step logs; it cannot be recomputed from this repository.

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

A component-removal probe (7 variants x 2 runs, run via the DeepSeek provider
because the OpenRouter key hit its spend limit after the scored run) isolated
this:

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

Every run was diffed against the pristine fixture; `quality.jsonl` holds the
per-run rows. Cells are medians unless the header says total: the
comment/docstring distributions are skewed, so their median is 0 for every arm
and only the totals separate them. The Turkish rate counts replies the detector
scored `tr_hits >= 2`; at the looser `>= 1` it is 85% / 60% / 80%, so the row is
a stated threshold, not a rounded rate.

| Arm | Median added lines | Files touched/task (median) | Comment lines (total) | Docstring lines (total) | Turkish replies (tr_hits>=2) | Claims a verification |
|---|---|---|---|---|---|---|
| tezgah+opencode | 2.0 | 1 | 1 | 1 | 75% | 60% |
| omp+graph | 2.5 | 1 | 8 | 10 | 30% | 55% |
| omp+tezgah-port | 2.5 | 1 | 1 | 6 | 65% | 65% |

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

`tezgah-setup` (no flags, or `--install`) prints what tezgah injects before the
first turn, so the cost side of each structure is visible. This is that report
verbatim at the commit that last ran it:

```
context budget (always-on text; ~tokens = chars/4):
     core contract (always-on, per session) ~ 1.3k tok    5377 chars
     per-turn reminder                  ~ 0.2k tok     961 chars
     skill metadata (9)                 ~ 1.3k tok    5207 chars
     subagent metadata (5)              ~ 0.2k tok     891 chars
     conditional rules (armed by task class) ~ 0.6k tok    2231 chars
     full contract (on demand)          ~ 6.0k tok  (only when the skill is read)
     MCP tool schemas                   run --mcp-schemas to measure
```

The core band is the one to watch: it grew from the 3,214 characters quoted in
the first revision of this file to **5,377**, and the cost side of that +67% is
borne by every session. The always-on bands total ~2.9k tokens before the first
turn; the conditional rules add ~0.6k only on the turn that arms them, and the
largest single band after the core is the skill metadata. MCP tool schemas are
the host's size to report and are the one band this instrument cannot see.

opencode's own always-on is higher: its generated skill router is a second
instructions file (see the main README's Cost section).

## Hook latency (re-measured)

The main README's Cost row quotes deltas over the interpreter start. Measured
again on the same machine, independently of the slice that published the row:
two rounds of 11 runs per entry point, wall time of the whole process (the
interpreter start included, because that is what a session pays), real checkout
and real HOME, warm caches. The payloads are the shapes the tests drive: Claude
`{"tool_name": "Bash", "tool_input": {"command": "ls"}}`, codex
`{"event": "PreToolUse", ...}`, cursor `{"hook_event_name": "preToolUse",
"tool_name": "Shell", "command": "ls"}`.

| Entry point | Median | Min | Max | Over the base |
|---|---|---|---|---|
| interpreter start (`python3 -c pass`) | 17.9-18.8 ms | 17.6 | 19.5 | - |
| turn (`projects-auto-init.py`, UserPromptSubmit) | 46.7-48.2 ms | 45.9 | 51.2 | +28 to +30 |
| session start (`projects-auto-init.py`, SessionStart) | 65.6-65.7 ms | 63.7 | 74.9 | +47 to +48 |
| session start, codex hook | 71.3-72.1 ms | 70.3 | 87.7 | +53 to +54 |
| session start, omp hook | 71.3-71.6 ms | 69.6 | 80.9 | +53 to +54 |
| session start, cursor hook | 72.2-72.3 ms | 69.8 | 79.6 | +54 |
| gated call, Claude entry (`projects-pretooluse.py`, Bash) | 34.5-34.8 ms | 33.9 | 36.1 | +16 to +17 |
| gated call, cursor hook (preToolUse, Shell) | 41.1-41.2 ms | 40.0 | 42.4 | +23 |
| gated call, codex hook (PreToolUse, Bash) | 71.2-71.9 ms | 69.4 | 79.7 | +53 |

Against the published row: the ~19 ms base holds (17.9-18.8 here, 20.0 in two
earlier rounds), and the turn adds +28 to +31 across four rounds against the
row's +31. Session start's 50-81 ms brackets the warm hosts at its lower end
(+47 to +54 measured here); its top end is the colder omp run the publishing
slice timed at 100.1 ms in total. The gated call's 24-25 ms is a pair of
readings, not a band: cursor measures +23 here, close to it, while the Claude
entry is +16 to +17 and the codex entry +53 with the payload above - the gate's
work follows the payload it is handed, which is why the row quotes one pair and
this table names the payloads behind the spread.

## Limitations

- One sample per (task, arm); a single model. Per-task variance is large enough
  that a 1/20 difference is not decisive.
- `t19` ground truth is under-specified (direct call sites vs transitive impact).
- Two runs (`t5`, both omp arms) hit the 240s cap, though their fix had already
  been written to disk and passed every check.
- The benchmark measures the harness, but the model does most of the work; the
  contract's effect shows up in cost, context and verbosity, not in pass rate here.
