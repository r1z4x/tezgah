# H1 - a Turkish marker section against the shipped contract

**What ran.** `harness/run.py --track h1`, transport `host` (generator tier `slow`, judge
tiers `default` and `smol`), six Turkish fixture drafts, both arms edited under the same
shipped `skills/no-ai-slop/SKILL.md` body, arm B additionally carrying
`harness/candidate_tr.md`. Six judge pairs per item, arms swapped, labels hidden.

**What the rows say.** Mean delta (arm B minus arm A) **-0.58**, bootstrap 95% CI
**[-0.71, -0.42]**, which excludes zero in the *negative* direction: the judges scored the
candidate section's edits *lower* on native Turkish than the shipped contract's edits. The
secondary number agrees with the direction of the finding - marker density per 100 words is
**0.00 in both arms**, so the shipped contract already removes every surface marker the list
counts, and the new section buys nothing measurable on this axis.

**Which claim it moves.** C03 is recorded as refuted: hypothesis H1, as written, did not
survive its own run. The candidate section did not improve native-ness and the marker
density it targets is not what separates the arms.

**What it does not show.** Six fixture drafts written in this session, one generator, two
cheap judge tiers, no human Turkish reader: the CI is narrow because the judges were
consistent, not because the sample is representative, and a judge's opinion of Turkish
naturalness is not a native speaker's. The negative delta may also be a side effect of the
section's own caution rules (do not touch inverted sentences, leave established loans), which
make the model edit less - that reading is consistent with the logs but is not measured here.
The result says the *section as written* earns nothing; it does not say the marker families
are absent from model Turkish, only that this contract text did not remove them better than
the shipped contract already does.
