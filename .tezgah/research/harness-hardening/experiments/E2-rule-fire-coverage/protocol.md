# E2 — does every shipped refusal earn its keep?

## The change under measurement
None. This counts the shipped gate's refusals over the machine's whole ledger
corpus.

## What it predicts
1. At least one shipped deny rule has **fired zero times** over the corpus
   (predicted: the `lang` rule and the `attribution` rule, the two newest and the
   two whose trigger needs a specific artifact command).
2. At least two rules fired **only on the day they shipped** — their corpus life
   is their own construction session, not later traffic.
3. The corpus spans **more than one host** (a refusal is recorded by whichever
   host's adapter saw the call), so a zero count is not an artifact of one host
   never running.

## What would falsify it
- Every shipped deny rule fires at least once on at least two distinct days.
- No rule's fires are confined to a single day.
- Every refusal in the corpus comes from one host.

## Why this is worth a measurement
The layer's own docstring says it: "a rule that never fires is indistinguishable
from a rule that is wrong." A rule that costs text and a code path in every
session but has never refused a real call is the cheapest thing to find and the
hardest thing to keep looking at. The repo's counters count refusals in total,
never per rule; the raw ledger holds the label, so this is a fold, not a probe.

## Method
- Fold every `~/.cache/tezgah/evidence/*.jsonl` (1610 files at the last count).
- Group `deny` rows by the rule label `_deny` writes (the text before the first
  `:` in `detail`), and report per rule: `fires`, `distinct_days`, `first_day`,
  `last_day`, and the host from the session slug/workspace field when it carries
  one.
- Group `nudge` and `judge` rows the same way, as the non-refusal marks.
- Cross-check the label set against the labels the Python gate can emit, so a
  rule with zero rows is named as zero rather than absent from the fold.

## Reported rows
One object per rule: `rule`, `fires`, `distinct_days`, `first_day`, `last_day`,
`hosts`, `command`, `source`. Plus one row for the corpus totals.
