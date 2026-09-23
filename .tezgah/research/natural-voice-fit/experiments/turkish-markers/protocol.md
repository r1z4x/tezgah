# H1 - a Turkish-native marker set against the shipped English-only set

**Change.** Arm A is the shipped skill: `skills/no-ai-slop/SKILL.md` and its
`eval.md`, unchanged. Arm B is the candidate: the same skill plus a Turkish marker
section, whose entries come from the translationese indicators and the Turkish
register sources already in `literature/`, and the same `eval.md` extended with the
Turkish checks. Both arms see the same prompt skeleton, the same items and the same
generator model; only the committed skill text differs.

**Predicts.** On Turkish items, blind judges score arm B's edits at least 0.5 higher
on a 0-5 native-language rubric; connective density moves toward the human reference
(measured against the Turkish connective inventory) while sentence-length variance
rises; readability does not fall.

**Why.** The mechanism is internal translation plus a register imitation that goes
wrong, and the Turkish evidence for it is editorial and institutional rather than
statistical: Alpay's usage guide gives the rule, the reason and the replacement for the
calque and redundancy families; Microsoft's Turkish style guide names word-for-word
Turkish stiff and rejects the authoritative `-(y)InIz`; the Anadolu Agency guide names
the filler verbs; and the TDK dictionary resolves calques per entry. The translationese
literature supplies the measurement protocol only - the five languages of the paper the
user offered are English, German, Spanish, Greek and Pashto, so its Turkish reach is
zero and no Turkish finding may be cited from it. Two honest limits are written into the
arm: the markers are named as editorial defects, because no primary Turkish source calls
them machine-text tells; and inverted sentences are excluded, because Alpay says
explicitly that they are not defective and the one quantitative study finds them to be a
register feature.

**Falsifies.** Any of: a delta of 0 or less, or a 95% CI that includes 0, on the
Turkish subset; a readability loss that comes with the gain; or an equal
marker-density drop in both arms, which would mean the shipped skill already removed
those markers and the new section buys nothing.

**Design, to be pinned here before the run.** Items: 12 Turkish drafts, four per
register (sales, executive, developer), each written to be slop-typical on purpose so
both arms have something to fix. Generator: one model id for both arms. Judges: three
models from three different families, never the generator; each pair judged twice
with the arms swapped; the rubric carries verbatim-quote anchors from the clue
taxonomy. Secondary instruments: the Turkish connective inventory, sentence-length
variance, a Turkish readability formula (and its known disagreement with the others,
so it is reported, not gated), and the register-aware Biber-feature distance against
a human corpus where one exists. Decision rule: locked in `state.json` - delta >=
+0.5 with a CI that excludes 0.

**Not yet run.** This protocol is committed before any arm is executed; the item set,
the model ids and the rubric anchors are filled in here, in a further commit, before
the run.

**The language axis.** This protocol is the first instance of H5, not the whole test. The
same design runs a second time with a second language's own rail (a normative authority,
a per-register corpus, in-language marker evidence), and the finding of interest is
whether the delta holds there or collapses - a collapse, or a missing rail leg, is a
result about coverage rather than a failure to be hidden. The pair matters as much as the
target: translationese scales with the distance between the language the draft was formed
in and the language it is written in (literature/translationese-as-task-difficulty.md).

**Pinned before the run (2026-09-21).** Items: `harness/items_tr.json` (six Turkish
drafts, two each in the sales, executive and developer registers) and
`harness/items_de.json` (four German drafts). Contracts: arm A is the body of
`skills/no-ai-slop/SKILL.md` as shipped; arm B is the same body plus
`harness/candidate_tr.md` (or `harness/candidate_de.md`). Harness:
`harness/run.py --track h1` (or `h5`). Transport: the agent host's own model
access, because the OpenRouter path returned HTTP 402 (no credit on the key);
the generator tier is `slow` and the judge tiers are `default` and `smol`. Judges
score each pair twice with the arms swapped and never see which contract produced
which draft. Every item is authored in this session, so the run's scope is
fixture: it measures the code path (what the two contract texts do to the same
drafts under the same model), not the behaviour of any real writer's workflow.
