# natural-voice-fit - decision log

- 2026-09-21 (ai-executed): line opened with `tezgah-research init --tracked`. Question:
  does a language- and audience-aware edit contract beat the shipped English-only
  marker set on native-ness and audience fit, judged blind? Baseline read:
  `skills/no-ai-slop/SKILL.md` (30+ named patterns, banned-word list) and its
  `eval.md` (pass/fail checks); both are English-only and neither names a register.
- 2026-09-21 (ai-executed): evaluation locked before any run - metric, baseline and
  threshold in `state.json`, hypotheses H1-H3 with their falsifiers. The user's own
  framing fixed the three axes: Turkish-native markers, audience register (sales,
  executive, developer), and voice captured from the writer's own prose.
- 2026-09-21 (ai-executed): three literature slices opened (Turkish markers,
  register/audience, voice measurement). No run starts until their notes are in
  `literature/` and the first protocol is committed.
- 2026-09-21 (ai-executed): the user clarified two things, and the line was widened before any run, so no node had been answered yet. (1) Turkish was an example, not the target: the contract has to take a position for any target language and locale, so H5 was added (a second-language rail test) and the question and metric were reworded to be language-general. (2) Some languages must keep some concepts untranslated: H4 was added (a keep-or-translate decision per term against a glossary rail), with the terminology error rate as a second secondary metric, and five notes were written for the two axes (translationese as task difficulty, the loanword-vs-switch annotation boundary, unreliable LLM understanding of ISO/IEC/IEEE 24765 terminology, term evaluation with variation, and locale-oriented evaluation). No prior result existed to invalidate.
- 2026-09-21 (ai-executed): the protocols were pinned and the runs switched transport. OpenRouter returned HTTP 402 (Payment Required) on the first call, so the runs execute over the agent host's own model access (the session's completion primitive: generator tier `slow`, judge tiers `default` and `smol`), and the environment field now records that instead of claiming a provider that could not serve the call. H2 and H3 protocols were written before their runs. Everything the tracks read is fixture material authored in this session (items, rail, briefs, voice samples), so the results measure the contract texts' effect on those drafts, not any real writer's workflow.
- 2026-09-21 (ai-executed): five tracks ran over the host transport (h1 twice for a harness fix, h2 twice, h3, h4, h5) and five claims landed. The harness fix that forced the H1 re-run: the model kept appending the shipped skill's own `What changed` section to the edited draft, so both runs of every track now truncate at that marker before judging. H1 was refuted by its own criterion (delta -0.58, CI -0.71 to -0.42), H2 supported (+1.96), H3 marginally supported (share 0.67), H4 supported (266.4 to 0.00 points per 1,000 words), H5 supported (+1.13). Six dimensions reviewed in to_human/review.json; methodological rigour scored 3 of 5 and the reasons are named there rather than left in this session.
- 2026-09-21 (ai-executed): the line concluded and the skill changed. Five orx experiment nodes were registered in the repo's
  orx project (one per hypothesis) with `python3 harness/run.py --track <h>` as the run command; no `orx exp run` was launched,
  because the OpenRouter key returned HTTP 402 and the runs executed over the host transport instead. The harness now refuses
  with a named reason when neither transport can serve a call, so the recorded command cannot fail obscurely.
  The skill change follows the rows, not the plan: the reader brief, the term rail and the writer samples went in (H2, H4, H3),
  the language rail section went in as a mechanism with the coverage boundary stated (H5, C07), and the Turkish marker list did
  not go in at all (H1 refuted, C03).
