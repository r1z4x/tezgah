# Implementation spec: the eight improvements, each with its acceptance test

Source: `report.md` (findings F1-F7), `experiments/E1..E6`, `claims.jsonl` C01-C25.
Standard for "done": every item below has an acceptance test that **fails before**
the change and **passes after**, and the repository's own three checks stay green
(`compileall`, `ruff check .`, `unittest discover -s tests` unpiped).

Two cross-cutting decisions the whole spec depends on:

- **`check --strict`** exists after this work: it turns the *unverifiable* class of
  warnings (a guarantee the checker cannot decide: the line's path is ignored, a
  grey source has no quality note, a claim's evidence file has no rows, a
  synthesis bullet names no source) into `FAIL`. Default stays `warn`, because a
  session mid-flight must not be blocked by a guarantee that is merely unprovable
  yet. This is what answers F2's "warnings beside a green exit code".
- **Backwards compatibility is a hard constraint.** The five existing lines and
  this audit line must still pass `check` (exit 0) after the change, with the new
  guarantees surfacing as warnings. Where a new rule would refuse an existing
  artifact, it is a warning plus a `migrate` path, never a silent break.

## Contract: new fields and files

| where | field | rule |
|---|---|---|
| `state.json.evaluation` | `metric`, `baseline`, `locked_at` | non-empty strings; `phase != "bootstrap"` -> required (`FAIL` when missing) |
| `state.json.evaluation` | `environment` (object) | optional; when present must be an object; keys free (model, prompt, harness) |
| `state.json.sessions[]` | `tag`, `date`, `what` | dict with `tag` in PROVENANCE and non-empty `date`; a non-dict entry or a bad tag is `FAIL` |
| `claims.jsonl[]` | `kind` | one of `evidence`, `code`, `literature`, `derivation`; required by the write path |
| `claims.jsonl[].proof` | per kind | `evidence`: every token resolves inside the line, and the experiment it names has a non-empty `results.jsonl` (empty -> warn/strict-FAIL); `code`: every token resolves in the repo; `literature`: every token resolves under `literature/`; `derivation`: at least one token, each resolving inside the line; **a proof with no path-shaped token is `FAIL` for every kind** |
| `claims.jsonl[].proof` | `orx:<runId>` token | resolves to `raw/<runId>.log` under the experiment, or the repository; unresolved -> `FAIL` |
| `experiments/<h>/results.jsonl` | every row | one JSON object per non-blank line; `source` non-empty; parse error or missing `source` -> `FAIL` |
| `literature/INDEX.jsonl` | `note`, `id`, `class`, `source`, `inclusion`, `verified`[, `quality`, `excluded_reason`] | required when `literature/` holds any `.md`; `note` must resolve to a file and vice versa (`FAIL`); `class` in `formal|grey` (`FAIL`); `grey` without `quality` -> warn/strict-FAIL; `verified` with fewer than 2 entries -> warn/strict-FAIL |
| `to_human/review.json` | `dimensions`, `findings` | required when `phase == "concluded"`; the six dimension keys each an int 1-5 (`FAIL` otherwise); `findings[]` each with `severity` in `critical|major|minor|suggestion`, `target` (a path), and `quote` that must occur **verbatim** in the target file (`FAIL` otherwise) |
| `findings.md` `## Patterns` bullets | a source token | each bullet must name `[Cnn]`, a `literature/...` path or an `orx:<id>` -> warn/strict-FAIL (17 of 19 bullets in the existing lines have none) |

## CLI surface after this work

```sh
tezgah-research init <slug> [--question "..."] [--tracked]
tezgah-research check [<slug>] [--json] [--strict] [--orx]
tezgah-research status
tezgah-research claim <slug>                 # stdin: one claim, now with kind
tezgah-research migrate <slug> [--dry-run]   # derive kind/source/INDEX for existing artifacts
tezgah-research source <slug> <hypothesis> --run <orxRunId> [--command "<cmd>"]
```

- `init` prints a TRACKING block naming the exact `!<rel>/` negation when the new
  line's path is gitignored; `--tracked` appends that one line to `.gitignore`
  (never rewriting other lines, never staging).
- `check` reports an ignored line path as a named warning ("the protocol order can
  never be verified") and `--strict` makes it `FAIL`.
- `check --orx` additionally asks `orx project view` for this repository and
  reports a registered project whose run command names a path the tree does not
  hold.
- `source` runs `orx logs <runId>`, writes `experiments/<h>/raw/<runId>.log`, and
  appends the results row `{"source": "orx:<runId>", "log": "raw/<runId>.log"}`;
  without orx it exits 2 and says so.
- `migrate` derives, per claim, `kind` from its proof tokens
  (`experiments/` -> evidence, `literature/` -> literature, else code, no token ->
  derivation), reports what it derived and what it could not, is idempotent, and
  writes under the same `flock` as `claim`. It also writes `literature/INDEX.jsonl`
  from the notes that exist (host-classified formal vs grey; `id` from the note's
  `id:` line; `verified` from its `verified:` line) reporting every field it could
  not derive rather than inventing one.

## The eight items and their acceptance tests

| # | item | acceptance test |
|---|---|---|
| I1 | tracking is named, not assumed | `init` on a gitignored path prints the negation; `check` on that line warns with the reason; `check --strict` exits 1; a tracked line passes both |
| I2 | locked evaluation and environment | empty `metric`/`baseline`/`locked_at` at `phase=inner` -> `FAIL`; the same at `bootstrap` -> warn; `sessions` with a bad tag or a non-dict -> `FAIL` |
| I3 | claim kind and per-kind proof | proof with no path token -> `FAIL` for every kind; `evidence` citing a row-less `results.jsonl` -> warn/strict-FAIL; `migrate` classifies the 75 existing claims and reports the ones it cannot |
| I4 | results rows carry a source; orx receipts | a `results.jsonl` row without `source`, or a file that does not parse per line -> `FAIL`; `source --run X` writes the log and the row, and `check` stays green; no orx -> exit 2 |
| I5 | literature index and source class | a note absent from `INDEX.jsonl` -> `FAIL`; an INDEX row naming no note -> `FAIL`; `class` outside the enum -> `FAIL`; grey without a quality note -> warn/strict-FAIL; `verified` with one entry -> warn/strict-FAIL |
| I6 | the review is an artifact | `phase=concluded` without `review.json` -> `FAIL`; a dimension missing or outside 1-5 -> `FAIL`; a finding whose `quote` is not verbatim in its target -> `FAIL`; an unsourced Patterns bullet -> warn/strict-FAIL |
| I7 | the surface sees the layer | a shell command running `tezgah-research` records the `research` kind in the ledger and flips the mark; `bin/tezgah-docs research` resolves to a real page; the two opencode statements match the code |
| I8 | the 25 unpinned behaviours | each new test fails when its branch is deleted; the list is E6's `results.jsonl` rows 1-25 |

## File ownership (no two writers on one file)

- **Wave 1 - W1** owns `hooks/tezgah_research.py`, `bin/tezgah-research`,
  `tests/test_research.py`, `skills/research/SKILL.md`, the RESEARCH paragraph of
  `hooks/tezgah_policy.py`: I1-I6 and the workspace half of I8, plus `migrate`.
- **Wave 1 - W2** owns `hooks/tezgah_context.py`, `bin/tezgah-setup`,
  `docs/skills.md`, `docs/research.md` (new), `docs/index.json`,
  `tests/test_context.py`, `tests/test_docs.py`, `tests/test_statusline.py`,
  `statusline.py` if needed: I7 only.
- **Wave 2 - W3** owns `tests/test_research.py` alone (after W1 stops): the
  remaining I8 pins (CLI refusal edges, degradation paths, the status surface).
- **Parent** owns `.gitignore` (not touched), `docs/*` citations
  (`bin/tezgah-docs --citations`), `CHANGELOG.md`, the commit, and this line's own
  `INDEX.jsonl`/`review.json` content.

## Out of scope, stated rather than silently dropped

- The five existing lines' artifacts are migrated only where `migrate` can derive
  a field; fields it cannot derive are reported, not invented.
- No new dependency, no network at check time, no change to `check`'s exit
  contract for the default (non-strict) path.

## Amendments recorded after the writers' reports

Each was forced by the back-compatibility constraint (a rule may not break the
six lines that already exist) and by "no rule may invent a provenance it cannot
derive". The audit's own E7 runner was corrected to match, so the standard and
the code say the same thing.

| spec said | landed as | why (measured) |
|---|---|---|
| a results row with no `source` -> `FAIL` | warn + strict-FAIL; a `source` that is present but empty or not a string stays `FAIL` | 71 pre-existing rows across the six lines carry no `source` (judge-positioning 18, research-layer-audit 53) and no rule can derive one - inventing it is the fabricated-provenance failure the rule exists to catch |
| `phase == "concluded"` with no `to_human/review.json` -> `FAIL` | warn + strict-FAIL; when the file is present it is fully checked at any phase, and every malformed case is `FAIL` | four pre-existing concluded lines have no review, and a review is a judgement no migration can author |
| an INDEX row missing `id`, `source` or `inclusion` -> unclassified | warn, aggregated per line | those fields are not in the spec's required list; `migrate` derives them only when the note carries them and reports the rest |
| a `literature` claim: every proof token resolves under `literature/` | at least one token is a note under `literature/`, and every literature-shaped token resolves there | the spec's own derivation turns "a note beside the code it is about" into `kind=literature`; "every token" then refuses what `migrate` just wrote, and the write path may not refuse what the checker accepts |
| `state.json.hypotheses` unvalidated | each entry a non-empty string, or an object with a non-empty `text` | E6 row 20 names the hypothesis list as a promise nothing validated; all six lines pass |
| `check --orx`'s dangling run command -> "reports" | warn + strict-FAIL | the finding is decidable; the spec's verb did not assign a class, and the parent keeps the softer class until the user says otherwise |

Also recorded: the write path was found refusing a row-less `evidence` file that
`check` only warns about (E7 cell I3, observed 2026-09-20). That is a defect
against this spec's cross-cutting rule, not a deviation - it was reported to the
writer of `claim_problems` with the reproduction.

**Narrowed after the tracking change (2026-09-20).** I1's probe asks each
experiment's `protocol.md`/`results.jsonl` pair rather than the line's directory.
A directory can be matched by an ignore rule while the files the order rule needs
are tracked - `.gitignore`re-includes those two names level by level - so the
directory form reported a line as unverifiable after it had become verifiable, and
said nothing useful about a line with no experiments yet. The warning also prints
the exact `git add -f <path>` now, because a plain `git add` on an ignored path
succeeds at adding nothing, which is the silent failure the message exists to
prevent.
