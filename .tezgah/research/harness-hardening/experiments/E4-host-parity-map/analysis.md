# E4 analysis — the host-parity map

## What was read
`results.jsonl` (16 rows), produced by a read-only scout from
`hooks/tezgah_gate.py`, `hooks/tezgah_lang.py`,
`hosts/opencode/plugins/tezgah.js`, `bin/tezgah-gate` and
`tests/test_opencode_plugin.py`. The map is the scout's; every row carries the
line it came from, and the odd-numbered claims below were spot-checked by
reading the named lines.

Rows here are scope: real (protocol.md: "Read the Python gate and the plugin" - this repository's own shipped code).

## Against the predictions

| # | prediction | result | verdict |
|---|---|---|---|
| 1 | opencode is where a rule is absent or divergent | **1 absent (`lang`), 5 divergent** (`explorer`, `task`, `loop`, `nudge`, `drift`) of 14 | **holds** |
| 2 | the plugin test does not cover every label | it compares **5 of 14** (sink text, task char-for-char via the real CLI, consent/loop/retry by rows) | **holds** |
| 3 | no other host reimplements a rule | codex, cursor and omp import `decision()` in process | **holds** |

## What the numbers say
- One decision point, three enforcement surfaces: the Python core, the plugin's
  own JS port of the shell rules, and the plugin's **delegation** for write tools
  and task-CLI commands (`bin/tezgah-gate check`, stdout used verbatim).
- **The language rule does not exist on opencode at all.** It is one of the two
  rules about artifacts that outlive the session (the other is attribution, which
  is implemented), so on that host a non-English branch name or commit subject
  is created unchecked. This is the largest parity gap the map found.
- **Delegation fails open by design**: a missing CLI, a non-zero exit or a
  broken pipe returns `""` and the call is allowed. The behaviour is pinned by a
  test, so it is a decision, not an accident — but it means the write half of the
  gate on opencode is a best-effort check whose failure mode is silence.
- Nine of fourteen labels have no comparison test in the plugin's own suite. The
  divergence that shipped once (the pre-lease consent model letting a repeat
  through) is exactly the class this gap admits.

## What this does not show
- Whether any divergent rule *behaves* differently in practice; the map is
  static. The instrument for behaviour is the arm-bench lab's two-host block,
  which found no pass-rate difference between hosts at its sizes.
- Whether the delegation path is fast enough in the field: it spawns a second
  Python process per write on opencode, which E3 measured at 61 ms for the core
  half alone.
