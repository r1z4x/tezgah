# W2 brief — the surface that reports the research layer (I7)

You are the sole writer for this file set. Do not touch any other file:
`hooks/tezgah_context.py`, `bin/tezgah-setup`, `docs/skills.md`,
`docs/research.md` (new), `docs/index.json`, `tests/test_context.py`,
`tests/test_docs.py`, `tests/test_statusline.py`, and `statusline.py` if a change
there is genuinely required.

Read first:
`/Users/rizax/Projects/tezgah/.tezgah/research/research-layer-audit/to_human/implementation-spec.md`
row I7, and the audit's measurements in
`.../experiments/E5-research-routing-map/results.jsonl` (every row carries the
`path:line` that establishes it).

## What to build

1. **The mark sees the layer's own CLI.** Today the `research` measure lights only
   when a *shell command* ran `orx` (`hooks/tezgah_context.py:1000-1013`,
   `:1029-1062`, `:1272`; tests in `tests/test_context.py`, `tests/test_cursor_hook.py`,
   `tests/test_omp_hook.py`, `tests/test_statusline.py`). A shell command running
   `tezgah-research check|init|status|claim|migrate|source` must record the same
   `research` kind. Keep the existing classification shape; add the spelling that
   covers both `tezgah-research` and the absolute path
   (`bin/tezgah-research`, `<config>/bin/tezgah-research`). Do not let a bare
   mention in prose count - the existing tests for "a mention does not" must stay
   green.
2. **Two statements that contradict the code.**
   - `bin/tezgah-setup:788` and `docs/skills.md:33` say opencode has no
     prompt-time injection point. Measured: `hosts/opencode/plugins/tezgah.js:2169-2190`
     injects rule text for `user_prompt`. Fix both statements so they say what is
     true (no *per-prompt skill list* injection; conditional rules do reach the
     prompt) without restructuring the surrounding text.
3. **A reachable docs page.** `bin/tezgah-docs research` currently prints
   "nothing matches 'research'" - the layer has no page. Write `docs/research.md`
   in the house style of the other pages (title, audience, "answers" orientation,
   `path:line` citations into the code, nothing aspirational), covering: the
   workspace layout, the CLI and its exit codes, what `check` enforces (be exact
   and current - the parent is concurrently adding `--strict`, `kind`, `results.jsonl`
   `source`, `literature/INDEX.jsonl`, `review.json`, `migrate` and `source`; write
   the page against the spec's contract table, not against the old code, and say
   in your report that the page depends on W1 landing), the session note, the
   routing and the kill switch. Register it in `docs/index.json` so
   `tests/test_docs.py` stays green.
4. **`docs/index.json` + `tests/test_docs.py`** must stay in step - run
   `python3 -m unittest tests.test_docs` and report it.

## Hard constraints

- Do not run the full test suite, ruff, or compileall (the parent runs them once
  at the end). Run only the suites you own:
  `python3 -m unittest tests.test_context tests.test_docs tests.test_statusline tests.test_triage`.
- Do not commit. Do not touch `hooks/tezgah_research.py`, `bin/tezgah-research`,
  `tests/test_research.py`, `skills/research/SKILL.md`, `hooks/tezgah_policy.py`,
  `CHANGELOG.md`, or `docs/*` other than the two named above.
- `bin/tezgah-docs --citations` must report no *new* citation outside its symbol
  because of your edit: after writing `docs/research.md`, run it and report the
  count before and after. If your new page's citations are the only delta, that is
  expected; if a *pre-existing* page's citation moved, say so and do not fix it -
  the parent owns that pass.
- Python/markdown style: match the file you edit; no f-strings in
  `hooks/tezgah_context.py` where it uses `%`; no emoji; no attribution line, no
  model/vendor name anywhere.

## Acceptance (report these, with the command and its observed output)

1. `python3 -m unittest tests.test_context tests.test_docs tests.test_statusline tests.test_triage`
   -> count and `OK`.
2. The new mark test named, plus the pre-change reproduction: the old classifier
   does not light `research` for `tezgah-research check` (state how you showed
   it).
3. `bin/tezgah-docs research` -> the page it now resolves to.
4. `bin/tezgah-docs --citations` -> counts before and after your edit.
5. The two corrected statements, quoted before and after with `path:line`.

Report as text; the parent persists. Cite `path:line` for every claim.
