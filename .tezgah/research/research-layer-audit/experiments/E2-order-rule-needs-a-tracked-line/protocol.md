# E2 protocol — does the protocol-order rule need the line to be git-tracked?

Written 2026-09-20 before the run. Predictions from reading
`_check_protocol_order` (`hooks/tezgah_research.py`) and the repository's own
`.gitignore`.

## Question

The contract calls the committed protocol "the temporal proof that the prediction
came first". For a line placed where the contract says to place it -
`<repo>/.tezgah/research/<slug>/` - is that proof obtainable at all?

## Locked evaluation

- **Metric**: how many of the four cells produce a *refusal* (exit 1) from the
  order rule, and how many produce the warning
  `results.jsonl is not committed yet` (exit 0).
- **Baseline**: the contract's claim is that `check` refuses a protocol that
  entered the history after the results. That is the rule's own baseline: at
  least one cell must refuse for the rule to be live.
- **Threshold**: live means the tracked cell refuses and the gitignored cell
  does not; anything else is a different finding and is reported as such.

## Cells and predictions

| cell | layout | predicted |
|---|---|---|
| A | temp repo, `.tezgah/research/q` tracked, protocol committed before results | clean, exit 0, no order warning |
| B | temp repo, protocol.md and results.jsonl present but uncommitted (the gitignored layout's effect) | warn `not committed yet`, exit 0 |
| C | this repository, all five existing lines | warn `not committed yet` for every experiment that has results, exit 0 |
| D | `git check-ignore -v` on this line's own `state.json` | names the `.gitignore` line that ignores `.tezgah/` |

Predicted: A clean; B and C warn without refusing; D names `/.tezgah/`.
The rule is therefore live only where the line is tracked, and the layout the
contract prescribes is the one where it is not.

## What would falsify

- Cell A refusing or warning: the tracked layout still cannot prove the order and
  H3 fails for a second reason.
- Any cell C experiment refusing: some line in this repository is tracked after
  all, and the "never verifiable here" claim is wrong.
- Cell D naming no ignore rule: `.tezgah/` is not ignored, and the whole cell is
  void.
