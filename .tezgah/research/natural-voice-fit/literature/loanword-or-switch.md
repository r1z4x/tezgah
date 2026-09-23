# Loanword or switch? The annotation boundary drives Kazakh-Russian code-switching detection (arXiv 2608.00581)

**What it is and claims.** Off-the-shelf language identification over-labels text as mixed because a Russian loanword inside Kazakh looks like code-switching under a shared script. Their guideline keeps integrated borrowings as the host language and reserves mixed for clause-level switches. The finding is that the bottleneck is the annotation boundary, not the model class.

**How it changes the skill.** This is the rule the untranslated-term axis needs in the other direction: an integrated borrowing is the host language, not a foreign word, so a skill that hunts loanwords will flag established usage - the same mistake as penalising inverted Turkish sentences. The check has to be per term, against a glossary, not per word-shape.

**Quality.** Formal: an arXiv record with an OpenAlex record; read as abstract in session.
