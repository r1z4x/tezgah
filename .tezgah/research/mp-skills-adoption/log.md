# Research log

Newest last. One line per decision, experiment, dead end or pivot, with the
evidence that drove it.

- 2026-09-21 — Line opened. Question fixed after the read-only review of
  `github.com/mattpocock/skills` at `c55ee46`: what the pack costs in always-on
  context, in router-line extractability and in conflicts, and which of its
  mechanisms earn an arm-bench effect block.
- 2026-09-21 — Evaluation locked in `state.json` and the three protocols
  committed in `a9426dc` **before any probe ran**; the commit is the prediction.
- 2026-09-21 — Reconnaissance, disclosed in E2's protocol: CORE 13483 B and
  CONTRACT 35860 B were read before the protocol was written. Used as the
  comparison scale only, never as a predicted outcome.
- 2026-09-21 — **Amendment 1** to `instrument.py`: the first `router-yield` run
  walked `skills/` and read 114 `SKILL.md`, not the protocol's 14 shipped names.
  The instrument now reports `tezgah-shipped` (the 14 in `SKILLS`) and
  `tezgah-tree` separately, and the control claim is measured on the 14 alone.
  The surprise it exposed is kept as C07.
- 2026-09-21 — **Amendment 2** to `instrument.py`: `tezgah_gate` imports its
  siblings by module name, so `hooks/` had to be importable before the load. No
  measurement changed; the first attempt produced no rows and exited 1.
- 2026-09-21 — E1 `router-yield` run: 22 of 38 upstream fall back, 14 of 14
  shipped trigger. Prediction confirmed.
- 2026-09-21 — E2 `context-cost` run: upstream 6180 B against tezgah's 9000 B.
  **Prediction 1 refuted**, prediction 2 confirmed (13515 < 35860). Recorded as
  refuted rather than reworded.
- 2026-09-21 — E3 `conflicts` run, both variants: float 0/38 bodies, 1/66 files;
  the mandated attribution line allowed; the tagged graft fails one test, the
  plain graft none.
- 2026-09-21 — Dead end, recorded: the live half (H4) was not run. The orx
  project `tezgah-harness-research` registers `bash benchmarks/arm-bench/orx-run.sh`,
  and that path does not exist at HEAD — the tree moved to `benchmarks/lab`
  (`5af240b`). An arm-bench block needs the branch checked out and the run command
  re-registered, which is the user's call and spends model credit.
- 2026-09-21 — **Defect in the line, reported rather than hidden:** `check` still
  refuses C06, because C06 declares `derivation` and cites
  `hooks/tezgah_policy.py:832`, a repository artifact the line does not hold. The
  corrected claim C06b (kind `code`, which is what the artifact makes it) was
  recorded through the CLI, and the correction does **not** clear the original:
  `_check_proof` runs over every row in `claims.jsonl` and does not skip a claim
  another one supersedes. The in-contract paths are exhausted — `migrate` fills
  only missing fields ("0 derived"), and hand-editing `claims.jsonl` is refused by
  `skills/research/SKILL.md`. Clearing it is one field in one row
  (`"kind": "derivation"` → `"code"` in C06), and that is the user's call.
- 2026-09-21 — Evidence organised by scope: each experiment's `results.jsonl` now
  holds the rows sharing the scope of the claim that cites it, with the other
  partition beside it (`results-upstream.jsonl`, `results-fixture.jsonl`) and a
  `derived_from` field saying what it was partitioned from.

- 2026-09-21 — `user`: approved the one-field correction to C06 (`kind`: `derivation`
  → `code`) after `check` refused it and every in-contract path had been exhausted;
  it is the only hand edit to `claims.jsonl` in this line, it is recorded here and
  in `state.json` as such, and `check` went from exit 1 to `1 line(s) ok` with it.
- 2026-09-21 — `user`: H4 stays open. The arm-bench effect block is not run this
  round; the recipe is in the entry above, and running it means checking out
  `benchmarks/lab` and re-registering the run command with `orx project edit`.
- 2026-09-21 — The working tree moved to `plan/010-codegraph-backend-migration`
  mid-session (another session's work), which is where `hosts/omp/hook.py` exits 1
  with `ImportError: cannot import name 'CBM' from 'tezgah_paths'`. Every
  artifact from here on was written in a clone of `main` and pushed back with
  `git fetch <clone> main:main`, so the user's branch was never touched.
- 2026-09-21 — E4 `mechanism-map` run, both instruments: the provoke-the-failure
  rule is absent (judge 0.04, marker 0 hits) and both controls pass (0.99, 0.98);
  17 prohibition markers against 9 positive-target ones; 4 of 14 descriptions
  already carry a non-trigger. The blind prediction held.
- 2026-09-21 — H4 pre-registered (`experiments/E4-mechanism-map/h4-block.md`) and
  **not run**: the arms resolve their hooks through `const HOOK =
  /Users/rizax/Projects/tezgah/hosts/omp/hook.py`, which exits 1 at the checked-out
  commit, so a block now would measure a broken harness on both sides of the pair.
- 2026-09-21 — H4 round set up and launched: the baseline ref reconstructed
  (`orx/baseline-full-contract-vs-bare-anchor` = current main plus the arm-bench
  instrument, `db2bf19`; the node branch `1b42dd1`). The orx node branches from the
  earlier rounds no longer exist, so this round could not branch off them.
- 2026-09-21 — An independent adversarial audit of the line (a separate read-only
  session, 27 files) returned ten defects; nine are fixed in `5dd139d`, C03's proof
  path is left as filed and reported.
- 2026-09-21 — H4 round ran (`72ff46bc`, 300 jobs, $0.77). **The treatment arm never
  ran**: 100 of 100 jobs refused with `not armed ... holds no hooks/pre/tezgah-hook.ts`,
  because `orx exp run` executes in a copy of the node's tree and the deployed arm
  directory existed only in the session's worktree. No treatment row, no spend on
  it. The clause's question stays unanswered; the round's one readable number is the
  armed arm's false-completion share against the bare anchor's (C12), with the
  timeout ceiling named as the reason the pass comparison cannot be read.
- 2026-09-21 — Round 2 pre-registered (E5) and run (`e868c63e`, 300 jobs). The
  packaging fix held — the treatment arm armed and wrote all 100 of its rows — and
  then every arm failed identically: zero usage, zero cost, under nine seconds. One
  arm-shaped call by hand reproduced it as `errorStatus` 402, an unfunded
  OpenRouter account. **$0.00 spent, the clause still unmeasured** (C13).
- 2026-09-21 — The user's branch moved back to `main` mid-round, so the E5 protocol
  and the round-2 artifacts were committed in the working tree; one file of another
  research line (`natural-voice-fit`) was left untouched.
- 2026-09-21 — Round 3 pre-registered (E6) with the provider change disclosed, run as
  `3eb8b9f8` (300 rows, all usable, $1.0997, model deepseek/deepseek-flash). The
  clause moved nothing the instrument can see: P1 confirmed, **P2 falsified** by its
  own wording (both shares 1.000, on one labelled failed run each), P3 confirmed
  (94.0% against 89.0%), refusals identical at 74 (C14, C15).
- 2026-09-21 — The three rounds now read as one arc: an arm that never armed, a
  provider that refused, and a measurement that came out null.

- 2026-09-22 — **Closing pass. `C03` settled through the CLI**: `C03c` supersedes it
  and cites `experiments/E3-conflict-battery/results-fixture.jsonl` and the
  analysis, which is where the counts live (the row as filed cited `results.jsonl`
  for numbers the scope partition had moved out, and named `tests/test_skills.py:91-98`
  as a receipt for a line number). Before recording it the counts were re-read over
  the pinned clone `/tmp/mp-skills/skills` at `c55ee46073` with the instrument's own
  corpus definitions: 38 `SKILL.md` with 0 float hits, 66 markdown files with 1
  (`skills/in-progress/README.md`), the control's 114 tezgah bodies with 0 — the same
  numbers the fixture row recorded. The original row's `check` warning remains: the
  rule reads every row and the layer's only write is an append.
- 2026-09-22 — **`C12` settled, and it was wrong in a second way**: re-folding the
  H4 run's own rows with the run's own `bench.false_completion` gives the armed
  control 2 claiming of 95 failed runs = 0.021 (2 of 46 = 0.043 excluding timeouts),
  against the anchor's 19 of 75 = 0.253 (19 of 69 = 0.275), where the recorded row
  says 3, 0.032 and 0.065. Both the pinned predicate (branch `1b42dd1`) and the tree's
  current one agree on 2; the two rows a human reads as completion claims and no
  predicate matches are `e01-silent-one-liner` r26 ("TÜM DOĞRULAMALAR GEÇTİ") and
  `e05-three-call-sites` r46 ("9/9 green … Tamam"). The anchor's row reproduces
  exactly, so the fold was not uniformly wrong. `C12c` is the keeper and supersedes
  both `C12` and the first correction row `C12b`, whose possessive apostrophes were
  lost to shell quoting and which the append-only rule means is superseded rather
  than edited. `experiments/E4-mechanism-map/analysis.md` keeps its fold as written
  and carries a dated correction section; `E5-round2-clause/protocol.md`, which took
  0.032 against 0.253 as its input, is pre-registered and is not touched.
- 2026-09-22 — **The attribution-anchor hole is left an open user decision, named
  here and in the report**: `attribution()` (`hooks/tezgah_gate.py:151`) holds
  "generated **with**" and not "generated **by**", so the pack's mandated line passes
  while the `Co-Authored-By` control is denied (C04). Widening the anchor set refuses
  the pack's line repo-wide and is a behaviour change to a shipped gate; leaving it
  makes an adopted `triage` a text a human must edit; refusing that skill outright is
  the third option. The line took none: no measurement here decides it and a gate
  change is a policy call, not a research step.
- 2026-09-22 — **The line's own review is written** (`to_human/review.json`):
  weak accept, mean 4.33 with `methodological_rigour` at 3, and four findings - the
  false-completion row that does not reproduce (major), `C03`'s proof path (major),
  round 2's protocol quoting the superseded share (minor) and the H4 label rate
  (minor). All four are closed, the two majors by superseding claims.
- 2026-09-22 — **Line concluded** (`phase: concluded`, `direction: conclude`). The
  question is answered as far as this instrument goes: the pack costs 6180 B against
  tezgah's 9000 B (C02) and loses 22 of its 38 router lines (C01), two of its three
  candidate conflicts are packaging (C03c, C05) and the third is an unenforced hole
  (C04), the one mechanism measurably absent is the provoke-the-failure rule (C08)
  and the run that tested it moved nothing (C15). What is left open is the attribution
  decision above, a corpus that can price a one-sentence clause, and adoption's own
  value claim, which neither the pack nor this line measured.
