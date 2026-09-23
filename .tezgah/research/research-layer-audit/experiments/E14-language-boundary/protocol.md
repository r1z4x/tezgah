# E14 protocol — is the rule's boundary the contract's, or only Turkish?

**Ordering disclosed.** The user asked the question that produced this experiment
("what happens when it is not Turkish?"), the measurement ran, and this file was
written afterwards. E10 stays frozen: it answered 57/57 Turkish and 0/24 English,
and this is a *child* of it, the way E8 branched from E1 - the rule's boundary was
never what E10 measured.

## Question

The contract says "identifiers and messages stay English". The rule as delivered
refused *Turkish* - a non-ASCII letter list of one language plus a Turkish word
list. Does it refuse an identifier that is not Turkish and not English?

## Metric

Four groups, each read through `tezgah_lang.offending`:

1. non-Latin scripts (Cyrillic, Arabic, Chinese, Greek, Vietnamese);
2. accented Latin (French, Turkish with its own letters);
3. ASCII-folded words from another language (Polish, German);
4. English, including the tokens the first reading wrongly refused (`ID`, `CI`,
   `I1`, a version number).

## Baseline

The first reading - measured before this experiment - refused **none** of groups 1
and 2, and wrongly refused `ID`/`CI`/`I1` from group 4. That is the baseline this
experiment has to beat, and the reason it exists.

## Threshold

Groups 1 and 2 fully refused, group 4 fully clean. Group 3 is the stated ceiling:
if a folded word from a language the list does not know passes, that is recorded
as the ceiling rather than treated as a failure - closing it needs a language
detector, which the module deliberately is not.

## What would falsify

- Any of group 1 or 2 passing: the boundary is still one language.
- Any of group 4 refused: the rule blocks ordinary English identifiers, which is
  worse than missing a foreign one (`I1` blocked the commit that recorded this
  rule's own acceptance run).
- Group 3 claimed as covered: the ceiling is then being hidden rather than stated.
