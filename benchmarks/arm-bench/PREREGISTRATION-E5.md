# Pre-registration: E5 - the controls on tasks whose default answer is wrong

Status: **frozen before the scored run.** Written because the four earlier blocks
converged on one conclusion: on `e01`, the pass rate is not a function of the
harness at any size this instrument reaches, and the reason is that the model's
default is right most of the time - a refusal has little to change. This block
swaps the endpoint to the failure itself and spends its runs on tasks where the
default is wrong.

## 1. Task selection, from pilots run before this file

Three candidate tasks were written for this block and each was piloted at `k=3`
on the harness-free arm (the default answer, no harness):

| task | pilot | route taken | verdict |
|---|---|---|---|
| `e04-untested-second-caller` | 0 of 3 failed | `both` x3 | too easy: the model found the untested caller every time |
| `e05-three-call-sites` | **1 of 3 failed** | `both`, `one-site`, `both` | **selected** - one run fixed only the reported site |
| `e06-obvious-fix-wrong-contract` | 0 of 3 failed | `contract-aware` x3 | too easy: the README rule was read every time |

`e01-silent-one-liner` joins it. Its default-wrong rate is the best measured one
on this task set: 6/25 in E4c and 12/50 in E4d on the harness-free arm, about
0.24.

The two rejected candidates stay in the tree as negative controls; nothing was
tuned after its pilot was seen, and the agents that wrote them reported the
0-of-3 result rather than adjusting the fixture.

## 2. Design

Two tasks x four arms x `k=50` = **400 runs**, model
`openrouter/deepseek/deepseek-v4-flash`, pool of 20 jobs of 5 repeats.
`bench.py` records `route`, `stop_fires` and `session_rows` per row; the task
declares its routes in `meta.json` (`e01`: call-site/helper, `e05`:
one-site/more-sites/shared-helper).

| arm | gate | Stop rule |
|---|---|---|
| `omp+tezgah` | on | on |
| `orx-verify-off` | on | off |
| `orx-gate-off` | off | off |
| `omp-bare` | no harness | no harness |

**Power.** At 100 runs per arm (two tasks x 50) the smallest detectable
difference is about 16 points for a rate near 0.20; at one task's 50 it is 22.
Effects below that are invisible here by design.

**Pinned host state.** The installed omp hook loads `hosts/omp/hook.py` from
`/Users/rizax/Projects/tezgah` by absolute path. The HEAD is read before the
block and re-read after; the block is void if it moved. The pinned tree must
carry the Stop decision row (`fix/stop-decision-row`, merged to main and into
that tree at `ef950f5`), or the fires endpoint is void rather than zero.

## 3. Predictions, before the run

Mechanism: on a task whose default answer is an incomplete fix, the Stop rule
refuses the "done" turn while no check passes; the turn continues, and a second
look is where the remaining sites usually get found. So the arm with the Stop
rule should take the wrong route less often than the arms without it.

1. **`omp+tezgah` takes the wrong route in at most 12% of its runs**, while the
   three arms without the Stop rule take it in at least 22% pooled. (`e01`:
   `helper`; `e05`: `one-site`.)
2. **Stop fires at least 5 times across `omp+tezgah`'s 100 rows**, and zero
   across the other 300.
3. **Among `omp+tezgah`'s rows, the ones where the Stop rule fired pass more
   often than the ones where it did not** - the rule's own effect, read inside
   one arm rather than between arms.
4. **Pass rate:** `omp+tezgah` >= `orx-verify-off` >= `orx-gate-off`.
5. **Arming:** at least 90% of the harness arms' rows carry `session_rows > 0`,
   every `omp-bare` row is `-1`, and `route` is present on all 400 rows.

**Falsifier.** If the wrong-route rate of `omp+tezgah` and the pooled Stop-off
arms land within 5 points of each other with overlapping Wilson intervals, the
Stop rule has no measurable effect even on a task whose default is wrong, and
predictions 1 and 3 are wrong. That would be the strongest negative result this
line can produce, and it is worth reporting as one.

## 4. What this still cannot show

- Two tasks, one model, four omp arms. `e05`'s pilot rests on 3 runs; this block
  is the first real measurement of its default-wrong rate.
- The wrong-route endpoint is a property of (harness, task, model) and depends on
  each task having a named set of plausible routes; it does not generalise as a
  number.
- Prediction 3 is not a counterfactual: rows that fired may differ from rows that
  did not for reasons other than the fire.
