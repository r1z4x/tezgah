# natural-voice-fit - findings

## What we know

- The shipped skill (`skills/no-ai-slop/SKILL.md` + `eval.md`) is English-only: 30+
  named patterns, a banned-word list, pass/fail checks that grade the *method* (was
  the point preserved, were banned words cut) and never the *result's fit* for a
  reader. Nothing in it names a language, a register or a reader.
- The user's three axes are the gap: Turkish output arrives translated-sounding,
  one voice serves sales, executives and developers alike, and nothing captures the
  writer's own vocabulary before editing.
- **Turkish.** The translationese paper the user pointed at measures English, German,
  Spanish, Greek and Pashto - **not Turkish** - so its mechanism transfers and its
  findings do not (2608.17399-translationese-mllm). The Turkish evidence is editorial
  and institutional instead: Alpay's Turkish usage guide gives the rule, the reason and
  the replacement (alpay-turkce-sorunlari-kilavuzu), Microsoft's Turkish style guide
  rejects the polite `-(y)InIz` as authoritative and names word-for-word Turkish stiff
  (ms-tr-style-guide), the Anadolu Agency's newsroom guide names the filler verbs
  (aa-turkceyi-dogru-kullan), and the TDK dictionary settles calques per entry -
  `fokuslanmak` redirects to `odaklanmak`, `adreslemek` and `implemente` have no entry
  (tdk-guncel-turkce-sozluk). What is *not* verified is the popular claim that
  `-mektedir`, `söz konusu` or `bu bağlamda` mark machine text: no primary Turkish
  source calls them that, only editorial defects are documented, so the skill must
  describe them as editorial defects and not as AI tells.
- **Inverted sentences are not the defect.** Alpay says so explicitly, and the one
  quantitative study finds inversion to be a register marker - more common in writers
  on social subjects, with the public divided (sengul-devrik-cumle). A Turkish marker
  set that penalises devrik cümle would be inventing the rule, and its real failure is
  a broken subject-predicate link, which is a coherence defect, not a word-order one.
- **Turkish morphology blocks the transfer of English detector features**, so the marker
  set cannot be a translation of the English one (ozdemir-turkish-ai-detection), and a
  human pass over model output does not settle it: post-edited text is *more*
  simplified and normalised than a human translation from scratch (toral-post-editese).
- **The language axis, not Turkish.** Translationese is a property of the language pair
  and the difficulty of the translation task, and it is measurable per segment by a
  classifier - the effect is proportional to the distance between the language the plan
  was formed in and the language the text is written in (translationese-as-task-difficulty).
  A language is also not one target: locale-specific evaluation shows models translate one
  locale's material better than another's, so the contract has to name a locale and
  compare against material written *in* that locale rather than against a translation of
  English source text (cultivar-locale-evaluation). Turkish was the first instance, and a
  design that only works for Turkish has not been built: it needs a rail per language - a
  normative authority, a per-register reference corpus, and in-language marker evidence -
  and the honest output of the research for a language with a missing leg is "this
  language is not covered yet", not a translated rule set.
- **The rail, and how uneven it is.** A language rail has four legs: a normative
  authority, a per-register reference corpus, in-language marker evidence, and a
  naturalness criterion. Measured across fourteen languages, **no language has all four
  from one tradition** (language-rails-coverage). Authority and corpus exist nearly
  everywhere - the German spelling council and DWDS, the Academie francaise and Frantext,
  the RAE and CORPES XXI, the Accademia della Crusca and CORIS, the Korean institute and
  its Modu corpus, the Japanese cultural-affairs recommendation and BCCWJ. The marker leg
  is quantified and written *in* the language only for Japanese (katakana loanwords 224.7
  against 82.4 per 10,000 characters, `kanojo` 19.4 against 0.3) and Korean (a national
  institute's family list with a replacement for each); Chinese, Arabic and Russian have
  detection work instead; Italian and Spanish have single studies; the rest have none
  found (meldrum-japanese-translationese, korean-nikl-translationese,
  hu-2018-translated-chinese). So the honest output for a language is a coverage
  statement, not a translated rule set.
- **What is language-independent.** Three instruments do not need a per-language
  invention: ISO 24495-1, whose own architecture is one standard plus a language
  supplement (German's is DIN 8581-1) and whose abstract says it applies to most if not
  all written languages (iso-24495-1); Burrows' Delta, which needed only a different token
  definition to work on unsegmented Chinese (burrows-delta-crosslingual); and detection
  benchmarks such as MULTITuDE's eleven languages, usable as a sanity check rather than a
  source of markers (multitude-benchmark).
- **Terms that must not be translated - the axis has a standard name and instruments.** The
  published concept is do-not-translate (DNT): it is a flag on a segment (HTML's `translate`
  attribute and ITS 2.0 / XLIFF 2.0, where translating a protected attribute value breaks
  the page), an error class in MQM-Core (do not translate, and the opposite error,
  untranslated, both listed with severity), and a container in ISO 30042 TBX, checkable by
  tools that read a glossary and report conformance (Okapi CheckMate, Xbench)
  (do-not-translate-standard, mqm-core-dnt, termbase-standards-and-tools). The scoring
  arithmetic is already published - severity points 100/10/1, category weights, error points
  per 1,000 units, with pass bands per language pair - so the experiment adopts it rather
  than inventing a metric (jtf-quality-guidelines).
- **The keep list is per category, and the categories are citable.** Trademarks are never
  translated and may not even be transliterated (Apple's rules: keep Apple Arcade in English,
  do not render it in katakana); organisational names are written as their organisations
  write them; standard numbers are not re-grouped and programming-language syntax overrides
  the host language's conventions (ISO/IEC Directives Part 2); unit symbols are mathematical
  entities, not abbreviations, so they take no plural and no full stop (BIPM SI Brochure);
  quotations and document titles are reproduced rather than re-styled, and an untranslated
  abbreviation keeps its original capitalisation (EC English Style Guide). Some terminology
  is regulated rather than preferred: MedDRA is not to be altered, drug labelling requires
  English on the label, and anatomical terminology is a Latin-titled controlled vocabulary.
- **Identifiers are not prose, and treating them as language breaks things.** The engineering
  rule is that culture-independent strings - tags, user names, file paths, system object
  names - are compared ordinally, because culture-sensitive handling causes bugs and security
  issues; the canonical case is the Turkish dotless i, documented when a build under the
  Turkish locale failed on an enum constant whose uppercase form no longer matched
  (turkish-i-locale-bug). This is the sharpest evidence that the dev register's keep list is
  not pedantry.
- **The counter-case is published too, and the policy conflict is real.** The same EC guide
  that says to reproduce quotations says `per diem` and many others have English equivalents
  that should be preferred; Google's glossary lets a loan be overridden when a reader would
  not understand it; and the Turkish Language Association instructs that an existing Turkish
  word be preferred over the loanword, while the DNT rules keep specific categories verbatim
  (ec-english-style-guide, google-cloud-glossary, tdk-yabanci-sozlere-karsiliklar). A
  wholesale keep rule and a wholesale translate rule are both wrong, and the decision is by
  category and per the draft's own rail.
- **The term axis is two-way in the opposite sense as well.** The loanword-versus-switch
  boundary is an annotation decision rather than a model output, and an integrated borrowing
  belongs to the host language rather than being a foreign word (loanword-or-switch); the
  keep-or-translate decision runs both directions by language - translated Japanese reaches
  for katakana loanwords about 2.7 times as often as original Japanese
  (meldrum-japanese-translationese) while Turkish corporate prose keeps English on purpose
  (plaza-dili).
- **Audience.** Register is a measurable variable (biber-register-variation) and the
  adaptation only works when the target is decomposed into checkable features and
  validated - naming a persona half-fails (thillainathan-controlled-generation).
  It is also two-way: plain-language flattening measurably costs a knowledgeable
  reader, so a developer or an executive who knows the domain gains nothing from it
  (august-know-your-audience). Developer register has a citable feature list
  (google-developer-style) and the executive register has a measured reading budget
  (gong-exec-reading-budget).
- **Measurement.** Detectors cannot be the ruler (61.3% false positives on
  non-native English essays, and a paraphrase drops detection from 70.3% to 4.6%).
  Two instruments survive: expert-style human judgement, where five trained
  annotators beat every open detector and the released taxonomy groups the clues as
  vocabulary, sentence structure, grammar and punctuation, originality, quotes and
  clarity (russell-expert-clues); and register-aware stylometry against a human
  corpus of the same register, which is MMD over 67 Biber features with released
  code (nieth-register-aware-humanlikeness). LLM judges are usable only with the
  mitigations the bias literature demands - swap the pair, never let the generating
  model judge (zheng-llm-judge-biases).
- **The ceiling, stated honestly.** Post-editing moves style similarity toward the
  writer's own prose but still leaves the text closer to model output than to a
  human control, with less stylistic diversity than unassisted writing
  (2604.24444-post-editing-personal-style). So "sounds like you" is measurable and
  "no model traces" is a different, unsupported claim.

## Patterns

- The fix is not a longer banned-word list but a contract with three inputs the current skill never asks for - the language, the reader, and samples of the writer (literature/2608.17399-translationese-mllm.md, literature/2608.30873-personas-vs-native-language.md, literature/2604.24444-post-editing-personal-style.md).
- The defect is mechanical rather than a matter of taste, so its markers are enumerable and testable (literature/ozdemir-turkish-ai-detection.md, literature/toral-post-editese.md).
- The Turkish markers have to be named as editorial defects with a replacement, not as machine-text tells, because only the former is sourced (literature/alpay-turkce-sorunlari-kilavuzu.md, literature/aa-turkceyi-dogru-kullan.md, literature/tdk-guncel-turkce-sozluk.md).
- Turkish register is not taste either: it is a regulation and a publisher standard, so both the defect and the fix have a citable feature list (literature/resmi-yazisma-yonetmeligi.md, literature/ms-tr-style-guide.md).
- Register adaptation without a validated feature list degenerates into a persona label (literature/thillainathan-controlled-generation.md, literature/august-know-your-audience.md).
- A trained human reader, not a detector, is the instrument for this class of question (literature/russell-expert-clues.md).
- A language rail is authority plus corpus plus in-language evidence, and a missing leg is a finding about coverage, not a licence to guess (literature/cultivar-locale-evaluation.md, literature/translationese-as-task-difficulty.md).
- A term is kept or translated one term at a time against a glossary, because word-shape is the wrong signal and an integrated borrowing belongs to the host language (literature/loanword-or-switch.md, literature/llm-unreliable-se-terminology.md).
- The keep-or-translate decision is per language and can run both ways: translated Japanese reaches for katakana loanwords about 2.7 times as often as original Japanese, while Turkish corporate prose keeps English on purpose - so the rule is a policy per language and register, not a principle (literature/meldrum-japanese-translationese.md, literature/plaza-dili.md).
- The keep-or-translate class has a published name and a published measurement, so the skill writes neither: do-not-translate is a segment flag, an MQM-Core error class and a TBX termbase entry, scored as error points per 1,000 units (literature/do-not-translate-standard.md, literature/mqm-core-dnt.md, literature/jtf-quality-guidelines.md).
- A language's rail is declared with its legs and its dates, and a missing leg is reported as coverage rather than filled in from English (literature/language-rails-coverage.md, literature/iso-24495-plain-language.md).


## Lessons

- Three refusals shaped the bootstrap: a hypothesis entry must carry `text` (an object with only `id` and `status` states nothing); a `## Patterns` bullet must name its source on its own line, because the checker matches per line and a wrapped citation counts as none; and a citation is only verified when two records back it.
- The slice that read the primary sources corrected the line's own framing: the paper the user offered as the mechanism does not include Turkish, and the most obvious Turkish marker, the inverted sentence, is documented as not a defect. A citation verified for existence is not a citation verified for scope.
- A `primary` class is not one of the two the index allows (`formal`, `grey`); an institutional dictionary is a grey source with a quality note.

## Open questions

- Which languages have a complete rail today (authority, per-register corpus, in-language
  marker evidence) and which have a missing leg is being measured; until that lands, the
  language-generality claim is a design, not a result.
- The keep-or-translate call needs a termbase per domain, and none is bundled with the
  skill: the developer register has ISO/IEC/IEEE 24765 to point at, Turkish has the TDK
  entries, and the other registers have nothing yet.
- Whether *these* Turkish markers beat the generic English set is untested; the
  experiment is pre-registered but not run. The marker set itself is now sourced, but a
  sourced rule is not a demonstrated improvement.
- Does the marker set ever hurt? Cutting calques could cost precision in a technical
  text, which the design has to be able to show (paired items in the developer register,
  scored on both naturalness and information preserved).
- Turkish register has reference corpora (turkish-corpora) and a naturalness criterion
  (turkbench-naturalness) but no published per-register distance measurement, so the
  audience axis is measurable with work rather than out of the box.
- No verified Turkish sentence-length ceiling exists; a limit in the skill would be
  invented, so any number has to be measured on a corpus first.
- `anlam kopukluğu` is not an established Turkish term for this - the field's words are
  cohesion and coherence, and Alpay's is redundant semantic repetition - so the skill
  should adopt one of those.
