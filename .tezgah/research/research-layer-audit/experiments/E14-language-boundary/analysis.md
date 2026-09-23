# E14 analysis — the boundary is English now, and one defect on the way

Raw: `raw/probe.txt`.

## Result

| group | before | now |
|---|---|---|
| Cyrillic, Arabic, Chinese, Greek, Vietnamese | **all passed** (nothing refused) | all refused, by token |
| French accented, Turkish letters | all passed | refused |
| English (`status-repair`, a subject, a version, `I1 in C40`, `ID`, `Fix CI`) | `ID`, `CI`, `I1` **refused** | all clean |
| ASCII-folded Polish/German | passed | still passes - **the stated ceiling** |

Two changes produced it, and both came from a measurement rather than a reading:

1. **The letter half became a predicate**: any alphanumeric outside ASCII, rather
   than a list of one language's letters. The contract says English, not
   not-Turkish, and the four non-Latin scripts above are the evidence that the
   list form was the wrong boundary.
2. **ASCII `I` left the letter set.** It had been there because `İ` folds to it
   for the word list - and that single character refused `ID`, `CI` and `I1`,
   including the commit subject recording this rule's own acceptance run. The
   test that pinned the behaviour (`offending("Fix CI") == ["CI"]`) was pinning a
   defect, and is replaced by the guard on the corrected behaviour.

## The ceiling, stated rather than hidden

An ASCII-folded word from a language the list does not know passes:
`naprawa-stanu`, `status-reparatur`. Three honest options, in cost order:

1. **Leave it** and keep the ceiling in the rule's own docstring and refusal text
   (what this change does).
2. **Extend the list per language when a real case appears** - one entry and one
   test per word, the same shape as the Turkish stems.
3. **Put a judgement on the denial path** - the `judge` seam could classify the
   token, at a per-command cost and with a nondeterministic answer on the path
   that refuses work. The module's docstring says why it is not that.

## Scope the rule does not cover, named

The gate sees the commands that create an identifier: a branch, a commit subject,
a PR or issue title. A file *name* written by an editor, a slug typed by hand into
a plan file, or a name created by another tool is not in that list - `plan-add`
states the rule where a session writes the slug, and the
`**Identifiers and messages stay English.**` paragraph is what the session is told
every turn.

Rows here are scope: fixture (protocol.md: "Four groups, each read through `tezgah_lang.offending`"; the identifiers are hand-written).
