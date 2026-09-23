# E2 - the citations the deterministic half cannot judge

**The change.** `bin/tezgah-docs --citations` judges a citation mechanically only
when the cited range must lie inside a symbol the sentence names; everything else
it counts and refuses to judge (878 of 1202 on this tree, 745 of them naming a
file). The claim under test - C5-citation-surface - is that this remainder is
decidable by one batched model call per citation, at a precision worth acting on.

**Predicts.** On a pre-registered sample of eleven citations, a single model call
per citation agrees with the hand label on at least 9 of the 10 clear items (one
item is excluded, see below), and flags at most one citation the hand label reads
as showing what the sentence names. In other words: agreement >= 0.9 and false
alarms <= 1.

**Why.** The mechanical half stops where the judgement becomes a claim about prose
(`bin/tezgah-docs:64-72` says so). The line's own report records 734 citations in
that remainder, and C5 (untested) is the only claim in this line left standing on
a question nobody has asked a model. One call per citation is cheap enough to run
before deciding whether to build the surface.

**Falsifies.** Agreement below 0.9 on the clear items, or more than one false
alarm, or a run whose replies cannot be parsed into the two verdicts at all -
which is itself the answer that the surface is not decidable this way.

**Design, pinned before the run.** Sample: every Nth citation from the
deterministically ordered list of unjudgeable citations that name a file
(`bin/tezgah-docs`'s own scan, re-run in this session), taking 12 and dropping the
one whose citation writes a bare filename with no directory - it cannot be read
without resolving the name through the symbol table, so it is not a fair item.
Eleven items stand: seven hand-labelled `shows`, two `does-not-show`, two
`unclear`. The labels were written into `sample.json` and committed with this
protocol, before any model saw the items; the `unclear` pair is excluded from the
agreement figure because the citing sentence is a fragment that does not say what
the citation promises.

One call per item, prompt: the citing sentence, the cited range's text with line
numbers, and the question "does this range still show what the sentence names -
answer shows or does-not-show". Model: the session host's `slow` tier (no
provider credential with credit is available to this repository; the same
transport the natural-voice-fit line used). Verdicts are parsed from the reply's
first occurrence of either phrase; a reply that names neither is recorded as
`unparsed` and counted against agreement.

**What this cannot show.** Eleven citations out of 745 is a sample; the labels are
one reader's judgement, made by the same session that wrote the prompt, so a
model that shares that reader's priors can agree without being right. The floor
below is what would license building the surface, not evidence that no citation
in the remainder is drifted.
