# H3 - three samples of the writer's prose before the edit

**Change.** Both arms edit the same drafts under the same contract. Arm A gets no
information about the writer. Arm B is given three short samples of the writer's
own prose and told to match that writer's vocabulary, cadence and level of
polish.

**Predicts.** On a forced choice - which of the two edits sounds more like this
writer - arm B wins at least 60% of the blind pairwise judgements (three judges,
both orders, ties excluded from the share and reported separately).

**Why.** The pre-registered post-editing study finds style similarity moves toward
the writer's own prose when the writer shapes the text, while the output still
stays closer to model text than to the writer's control sample and loses stylistic
diversity (literature/2604.24444-post-editing-personal-style.md). That paper also
supplies the bound this hypothesis has to respect: passing a forced choice is not
the same as removing machine traces, and the report states that limit.

**Falsifies.** A preference share at or below 0.5.

**Design, to be pinned here before the run.** Items: the six Turkish drafts.
Samples: `harness/voice.json` - three short passages authored in this session as a
fixture, in a deliberately plain first-person voice. Harness: `harness/run.py
--track h3`.
