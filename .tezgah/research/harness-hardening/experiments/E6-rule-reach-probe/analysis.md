# E6 analysis — `explorer` and `order` against their own shape

## What was read
`results.jsonl` (8 rows): seven cases run against the real gate
(`hooks/tezgah_gate.decision`) in a throwaway HOME and root, plus a totals row.
Every row carries `source` and `command`; the run wrote 7 cases, 4 refusals, 0
unexpected.

Rows here are scope: fixture (protocol.md: "A throwaway HOME and a `Projects` root inside it").

## Against the predictions

| # | prediction | result | verdict |
|---|---|---|---|
| 1 | `explorer` refuses `subagent_type=explore`/`explorer` and leaves a `deny` row labelled `explorer` | both spellings refuse with `EXPLORE_DENY`; the ledger's newest deny row is labelled `explorer` in each | **holds** |
| 2 | `order` refuses `git commit` while the newest check failed, leaves a `deny` row labelled `order`, and passes when the newest check passed or none ran | refused, `ORDER_DENY` names `pytest -q`, the row is labelled `order`; both negatives return None | **holds** |
| 3 | the `shortcut` control refuses `git commit --no-verify -m x` under the same environment | refused; the row is labelled `shortcut` | **holds** |

No prediction missed. No falsifier fired: no shape returned None while the
control refused, the control did refuse, and every refusal left a `deny` row
under its own label.

## The two refusals, verbatim
- `explorer` (`subagent_type=explore` and `=explorer`): "A grep-only explorer
  subagent is not allowed in this tree: it greps by design and ignores the code
  graph. Use the general-purpose agent and name the exact codebase-memory-mcp
  tools (search_graph, trace_path, search_code) in its prompt, with the
  tool-loading step so they are armed."
- `order` (`git commit -m x`, newest check a failing `pytest -q`): "Commit order
  denied: the newest check in this session failed, and a commit is a claim that
  the tree passed. What would be frozen is the state that check just rejected -
  the newest failing one was pytest -q - so fix what it reported and run it
  again, commit once the newest check is green, or say plainly that it is failing
  and why the commit is wanted anyway."
- control (`git commit --no-verify -m x`): "Verification bypass denied:
  `--no-verify` skips the commit/push hooks that run the checks. Run the checks,
  fix what they report, and commit without it. A skipped hook is not a passing
  check."

So the two zero-count rules are **reachable**: each refuses the shape it exists
for, and the refusal is on the ledger under the label E2 folds. Their zero counts
in 1613 ledgers are a fact about the traffic, not a dead code path.

## What the probe had to seed
`order` reads a relation between two actions, not one call, so the state it asks
about had to be built before the commit (`hooks/tezgah_gate.py:1434`):

- `commit_order_reason` refuses only when `_last_verify(events(session))` folds to
  `"fail"` and the command matches `COMMIT_CMD` (`:1442`).
- `_last_verify` (`hooks/tezgah_integrity.py:1257`) folds the newest `verify*`
  row: `verify_fail` -> `"fail"`, `verify_ok` -> `"ok"` only when `passing_check`
  agrees (exit 0, a non-empty result, an unmasked command), and `verify` ->
  `"ran"`. `None` (no check) does not refuse.
- The rows were written through `hooks/tezgah_integrity.note_tool`, the writer a
  host's PostToolUse hook uses, not by hand: a `verify_fail` row for the refusal
  case, a `verify_ok` row (`out_bytes=12`) for the passed-check negative, and
  nothing for the no-check negative.

Because the probe runs in a throwaway HOME, its `deny` rows are not in this
machine's real ledgers: E2's fold would still read `explorer` and `order` at
zero. The probe measures the rules' reach, not a new corpus count.

## What this does not show
- **Unreachability.** The probe enumerates shapes; a shape it did not think of
  could still fail to reach a label. A None here would have meant "no shape
  listed here triggers", never "no shape could". Every shape listed did trigger,
  so the question does not even arise for these seven.
- **Whether real sessions ever issue the shape.** The in-situ half of the zero
  count is untouched: the probe says the rule would fire, not that the gate has
  been offered the call. That is still E2's question, and it needs live traffic,
  not a probe.
- A hidden coupling: the control commit was refused by `shortcut`
  (`hooks/tezgah_gate.py:1596`), which sits above `order` (`:1728`) in the
  cascade, so the control shows the gate refuses a commit in this environment
  without exercising the `order` path. The `order` positives are what exercise
  it.
