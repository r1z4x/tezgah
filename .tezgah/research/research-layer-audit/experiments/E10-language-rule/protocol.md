# E10 protocol — does the Turkish-identifier rule catch what it claims, and refuse English?

**Ordering disclosed.** The measurement ran before this file was written, because
it is the verification of a rule another writer delivered. Both readings are kept:
the first probe (before the coverage gap was closed) and this one.

## Question

The rule refuses a git/gh identifier that reads as Turkish. Two properties decide
whether it is usable at all, and they pull in opposite directions:

1. coverage - does it catch Turkish words in the shapes an identifier actually
   takes (a folded slug, a bare noun, a suffixed form)?
2. precision - does it refuse English? A rule that refuses `silent` because `sil`
   is a Turkish stem is worse than no rule, because it blocks ordinary work.

## Locked evaluation

- **Metric**: `caught / 57` Turkish words, and `refused / 24` English words.
- **Baseline**: the first reading - 30 of 57 caught, 0 of 24 English refused - is
  the gap the writer was sent; the baseline for acceptance is 57/57 and 0/24.
- **Threshold**: 57/57 with 0 English refused. Below that, the missing words and
  the exact English word that would break are named rather than averaged.

## Cells and predictions

| cell | predicted |
|---|---|
| Turkish coverage over 57 common words | 57/57 after the gap was reported |
| English precision over 24 words including `verify`/`verification`/`Aramaic`/`silent`/`silky` | 0 refused |
| the reported case `plan/004-admin-durum-onarimi` | both tokens named |
| the refusal text | names the tokens and offers the English (`status`, `repair`) |

## What would falsify

- Any Turkish word missed: the list is thinner than the claim.
- Any English word refused: the rule blocks ordinary identifiers, and the word
  that caused it must be removed.
- A refusal that names no replacement: the session is left guessing, which the
  rule's own text promises it will not be.
