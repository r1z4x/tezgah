# H4 - a keep-or-translate decision per term, against a glossary rail

**Change.** Arm A edits freely, as the shipped skill does. Arm B must first extract the
candidate terms in the draft and decide keep or translate for each, with the decision
read against a rail: ISO/IEC/IEEE 24765 for the developer register, the TDK dictionary
entries for Turkish, and the draft's own termbase where one exists. Both arms see the
same items, generator and prompt skeleton.

**Predicts.** Arm B's severity-weighted terminology error points per 1,000 words are at
most half of arm A's, and arm B commits no do-not-translate error on a segment the rail
marks as keep, while arm A commits some. Scoring uses the arithmetic the industry already
publishes - the MQM-Core error classes as scored by the Japan Translation Federation
guidelines: severity points 100/10/1, category weights, error points per 1,000 units, with
the JTF pass band for the target language as the reference line - so the number is one a
professional reviewer recognises.

**Why.** Models cannot reliably distinguish correct ISO/IEC/IEEE 24765 definitions from
systematically falsified ones, so a translated term is a rewrite of something the model
cannot check (literature/llm-unreliable-se-terminology.md). The other direction is a
documented over-labelling error: an integrated borrowing is the host language, not a
switch (literature/loanword-or-switch.md). Terminology evaluation in machine translation
already supplies the instrument - glossary accuracy, consistency, cross-term variation
(literature/term-evaluation-variation.md).

**Falsifies.** No reduction in error points; or a reduction bought by a comprehension
cost, with judges rating the kept-term drafts less clear; or errors moved rather than
removed, with untranslated errors rising as do-not-translate errors fall; or the term list
itself being wrong, which the protocol guards against by scoring only terms the rail
covers.

**Design, to be pinned here before the run.** Items: the same drafts as H1 plus a
developer and a legal item per language, seeded with terms from the rail. Term extraction: a fixed pattern set (identifiers, acronyms, quoted terms,
termbase hits), not a model's judgement, so both arms are scored on the same term list. The
rail is a termbase in the standard exchange format (ISO 30042 TBX) and the scoring is done
by a checker that reads it - Okapi CheckMate for the open-source path, Xbench for the
commercial one - never by a judge; the checker's non-translatable flag is what marks the
keep segments, so the do-not-translate class is decided by the file and not by opinion.
Judges are used only for the comprehension cost.

**Two directions, and the policy conflict written down.** MQM-Core names both errors -
translating a marked segment, and leaving a segment that was meant to be translated - and a
run can trade one for the other, which the falsifier above watches for. The policy itself is
not uniform across authorities and the rail has to say which one applies: the Turkish
Language Association instructs that an existing Turkish word be preferred over the loanword,
while the do-not-translate rules keep trademarks, identifiers, unit symbols, version strings,
standard numbers, medical and legal terminology and product names verbatim. So the decision
is by category and per this draft's rail, and both a wholesale keep and a wholesale
translate are wrong.
Languages: Turkish first, German second, which is also where H5's rail test runs.

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

**The rail.** `harness/rail.json`: thirteen keep entries (identifiers, a file
path, a URI, a product name, version strings, unit symbols, a metric name, an
acronym, a locally formatted number) and seven translate entries (the calque
family from the Turkish editorial authorities), plus one register override -
`deadline` stays in the corporate register, on the plaza-dili evidence. Scoring
is by script, not by a judge: a keep form present in the source and absent from
the edit scores its severity, a calque that survives scores its severity, and the
total is expressed as points per 1,000 words. A judge scores each pair only for
clarity and information preserved, which is the cost half of the falsifier.
