# H5 - the same rail design in a second language

**Change.** The German instance of the H1 design: both arms edit the same four
German drafts under the same shipped contract, and arm B additionally receives
`harness/candidate_de.md` - a German section built the way the rail requires, from
the German orthographic authority, the DWDS corpus, the measured anglicism
evidence, and the German plain-language supplement to ISO 24495-1.

**Predicts.** Blind judges score arm B at least 0.5 higher on a 0-5 native-German
rubric over the four German items, so the delta is at least as large as the
Turkish one - the claim that the design is not Turkish-shaped.

**Why.** The rails are uneven: authority and corpus exist for German, French,
Spanish, Portuguese, Italian, Dutch, Polish, Russian, Japanese, Korean, Chinese,
Arabic, Hindi and Indonesian, while an in-language quantified marker study exists
only for Japanese and Korean (literature/language-rails-coverage.md). German's
legs are the spelling council, DWDS, and the Denglisch measurements, which is
what makes it the honest second instance: a language with rules and a corpus but
no in-language marker study of its own. ISO 24495-1 supplies the
language-independent backbone and its German supplement the local one
(literature/iso-24495-plain-language.md).

**Falsifies.** A delta that collapses toward 0 - or a rail leg that could not be
filled for German at all, which would be a finding about coverage rather than a
failure to hide.

**Pinned before the run (2026-09-21).** Items: `harness/items_de.json`, four
drafts (two executive, two developer). Harness: `harness/run.py --track h5`.
Transport: the agent host's own model access (generator tier `slow`, judge tiers
`default` and `smol`), the same as the other tracks. Scope: fixture, for the same
reason as H1.
