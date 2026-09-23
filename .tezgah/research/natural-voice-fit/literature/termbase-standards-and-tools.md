# Termbases and their checkers: TBX, Okapi CheckMate, Xbench

**What it is and claims.** The container and the verification exist as standards and tools: ISO 30042 TBX is the standard exchange format for a termbase, Okapi CheckMate reads a glossary (TBX, CSV or TSV), looks each source term up in the target and warns when no corresponding translation is found, supports a pattern whose expected target can be the literal keyword meaning same as the source, and never processes entries flagged as non-translatable; Xbench provides the same family of QA plugins commercially.

**How it changes the skill.** The keep-or-translate check can be automated against a railroad file rather than judged: the skill supplies the termbase, the checker reports conformance, and the number the experiment reads is the checker's output.

**Quality.** Formal: a standard, a peer-reviewed paper or an institutional framework.
