# Research log

Newest last. One line per decision, experiment, dead end or pivot, with the
evidence that drove it.

- 2026-09-20 bootstrap: the question fixed - what the seam is today, where it
  belongs, whether the contract should name it. Scope from the user's own words
  ("tezgah_judge zayıf, nasıl konumlanacağını araştır").
- 2026-09-20 read `hooks/tezgah_judge.py` (155 lines, clean at HEAD) and all three
  callers in full. First surprise: the module docstring at `:3-5` and
  `docs/operations.md:202-203` both say "two callers"; `hooks/tezgah_skill_pick.py`
  is the third and the only one on the prompt path of every turn.
- 2026-09-20 asked the graph instead of guessing: `trace_path` inbound on
  `hooks.tezgah_judge.ask` returned 41 caller edges (three program callers plus
  tests), cross-checked with grep for the import. The graph's line numbers matched
  the working tree, so it answered this question and the answer is not a guess.
- 2026-09-20 noted the working tree is dirty: eight files carry an uncommitted
  change turning `skill-suggest-off` into an opt-in `skill-suggest-on`. The tree
  was being written while this audit read it (mtimes moved between two `git status`
  calls), so every citation is labelled with the revision it came from.
- 2026-09-20 measured the two credential readers against each other instead of
  reading them: with the key file present and no omp store, `have_typesafe_key()`
  is False and `available()` is True. The install report can therefore call the
  credential missing on a machine where every judgement works.
- 2026-09-20 protocol written for E1 before any call: the 98-option flat Choice vs
  the two-stage shape, on 14 hand-labelled queries. Predictions P1-P4 fixed first.
- 2026-09-20 E1 run (42 live calls, $0.003516): both arms 14/14. P1 refuted, P3
  refuted (1.61x, not 3x), P2 confirmed only in its floor. Dead end recorded
  plainly: a hand-written unambiguous set measures a ceiling, so it cannot test
  P1 - the set, not the prediction, was the mistake.
- 2026-09-20 E1b written and run to make the measurement discriminate: four
  out-of-library queries, protocol first. 4/4 refusals in both arms, 0 forced
  picks. That is the half of the routing question that can actually fail.
- 2026-09-20 checked reachability by grep rather than by impression: neither
  `tezgah-triage` nor `tezgah-docs` appears in the injected text
  (`hooks/tezgah_policy.py`, `hooks/tezgah_context.py`, `agents/*.md`), and
  `skills/product-analysis/SKILL.md` never names the tool whose `--states` mode
  exists for its component x state requirement.
- 2026-09-20 concluded: the seam stays a hook module on Tier B (the `codegen`
  shape), with the three things Tier B is missing - a switch the session can name,
  a status mark, and a counted cost - and no always-on paragraph. Seven-item spec
  written, with the citation audit ranked first on evidence and last in order
  because it needs its own measured round first.
 | 25 | 2026-09-20 | correction | C4 declares scope fixture: this line's own report records that its measurement ran on a synthetic HOME, so the claim's figures are about the code path and not about the running system. Declared by the provenance-integrity session, which was closing the undeclared-scope gap; the claim itself is unchanged. |
| 26 | 2026-09-22 | correction | Closure pass. The seam's docs still said "two callers" in five shipped places (module docstring, three passages of `docs/operations.md`, a comment in `hooks/tezgah_context.py`, one in the opencode plugin); each now names all three callers - `bin/tezgah-triage`, `bin/tezgah-docs`, `hooks/tezgah_skill_pick.py`. The seam grew by J1-J6 of `to_human/spec.md` since the audit (switches, accessors, mark, counter, docs page, OpenRouter fallback), and `judge-off` is now in the kill-switch paragraph and the contract table. New claims: `C1-R-callers-fixed` (supported), `C3-R-spend-counted` (refuted - the spend is counted now), `C4-R-readers-named` (revised - `have_judge_key()` asks the seam's own question and the install report prints both rows). |
| 27 | 2026-09-22 | integrity defect | E1's `protocol.md` records that its first write did not land and was re-created from the transcript after the run, so the ordering property every E1 verdict rests on is unprovable from the artifacts. Kept, recorded in the report's limits and here, and not repaired by any later edit: the run, its rows and its verdicts stand, and only their ordering claim is unverifiable. E2 shows the lesson took - its protocol and `sample.json` were committed before the run (`da7148e`). |
| 28 | 2026-09-22 | evidence | C5 is settled, by the parent session, as `C5-R` (refuted): eleven pre-registered citations, one call each, agreement 5 of 9 = 0.56 against a 0.9 floor and precision 0.29 on the seven flagged rows (`experiments/E2-citation-adjudication`). The line's own report carried 734 citations in that remainder; the tool reports 878 of 1202 on today's tree, so the work list grew with the docs and the claim's number is stale in the honest direction. |
