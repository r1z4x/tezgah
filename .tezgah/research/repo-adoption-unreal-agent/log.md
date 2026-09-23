# Research log

Newest last. One line per decision, experiment, dead end or pivot, with the
evidence that drove it.

- 2026-09-22 — line opened on the user's ask: a comprehensive survey of
  `unreallabsai/unreal-agent` as an adoption candidate, run through subagents and
  the research layer. `tezgah-research init` accepted it because all fourteen
  existing lines report `ok`; the one-line-open rule was satisfied, not waived.
- 2026-09-22 — repository cloned at `b7c9bf1` into `.tezgah/scratch/unreal-agent`
  (gitignored, inside the workspace so a read-only agent can reach it) after
  `api.github.com` rate-limited the metadata query. First pass: 169 Go files,
  61,771 lines under `harness/ internal/ cmd/ benchmarks/`, MIT, Go 1.27,
  `CONTRIBUTING.md` stating the repo is "selected components from a larger internal
  codebase" and does not review pull requests — which fixes the adoption shape as
  idea-copying rather than an upstream dependency.
- 2026-09-22 — evaluation locked and `experiments/E1-repo-survey/protocol.md`
  committed at `c9a7243` BEFORE any survey ran, so the prediction is provably older
  than the candidates it scores. Decision driven by the layer's own order rule.
- 2026-09-22 — seven read-only slices fanned out in one batch (six `scout`, one
  `task` for the shell-requiring literature step), each given the clone path, the
  verdict vocabulary, a citation requirement and a per-slice `outputSchema`. Slice
  boundaries were drawn so no two agents read the same package.
- 2026-09-22 — while the slices ran, the highest-signal files were read first-hand
  for later verification rather than left to the reports: `inbox/{inbox,local}.go`,
  `operation/operation.go`, `sessionstore.go`, `coordinator/{coordinator,loop}.go`,
  both prompts, `tool/{tool,registry,skill_use}.go`, `contextbuilder.go`,
  `localfile/{codec,store}.go`, `primitives/{process,primitive_dispatch}.go`.
- 2026-09-22 — first verification that changed the conclusion: a grep for `Report`
  across the whole clone returned only the type declaration, the `Result` field, and
  a test asserting the list is EMPTY. The README's omission record is declared and
  dead. This flipped the central recommendation from "adopt their record" to "type
  tezgah's own" — tezgah's `budgeted`/`_drop_note` already logs its drops.
- 2026-09-22 — second verification: `// FIXME: Forks leave inherited calls without
  results and retain pending-input accounting.` at `loop.go:552`, plus TODOs at
  `localfile/state.go:401` and `operation/remote_job_output.go:4`. Three self-declared
  gaps, all confirmed by re-reading the lines.
- 2026-09-22 — the literature slice read the launch post and the Hacker News thread;
  both were then checked independently here (HN item `49805748` via the Firebase
  API: score 56, 42 comments, correct URL; blog: HTTP 200), and all six arXiv ids
  were confirmed through `export.arxiv.org/api/query` independently of the notes
  that quote them. One correction: `2608.03836` is `cs.LG`, not `cs.ML`.
- 2026-09-22 — every tezgah-side claim a slice reported was re-read before it could
  enter a claim row: `_check_state` (no version key), the validate-outside-the-lock
  order in the claim path, the ledger's silent skip against the research checker's
  permanent refusal of identical damage, `_parse` vs `claims.jsonl does not parse`,
  the two timeout sites, the nine unpinned `uses:` lines, and the ledger's boolean
  `failed` with its `None` case. All confirmed.
- 2026-09-22 — dead end recorded rather than papered over: the prediction's second
  half was wrong. The version gate is a key plus a branch, not a subsystem to build,
  and the fork path is not a borrowable source at all because the repository declares
  it unsound. Score: PARTIAL.
- 2026-09-22 — closed out: seven literature notes and their `INDEX.jsonl` rows,
  twenty claims recorded through `tezgah-research claim` (never by editing the file),
  `findings.md`, this analysis, `to_human/report.md` and `to_human/review.json`.
  Nothing was built, installed, executed or measured; the line holds no `evidence`
  claim and declares no scope, because it recorded no row.
- 2026-09-22 — state left deliberately open, and this is the reason a later session
  will see: `experiments/E1-repo-survey/` has a committed `protocol.md` and no
  `results.jsonl`, so `tezgah-research status` reports the line open with
  "has a protocol and no results" even though `check --strict` passes and the phase
  is `concluded`. That is the layer working as intended, not an oversight: the
  protocol is the prediction this line is scored against and must stay in history,
  and writing a `results.jsonl` would mean inventing a row for a reading pass that
  measured nothing. A session that needs to open another line passes
  `--allow-open "repo-adoption-unreal-agent ran no experiment by design: the
  deliverable was a reading pass, recorded in experiments/E1-repo-survey/analysis.md"`.
- 2026-09-23 — the line's five cost estimates were then MEASURED on the running
  system's own stores (2592 evidence ledgers / 57469 rows, this repo's 15 lines and
  91 commits touching `plans/open`), and the measurement corrected three of them:
  the CI item is 3 distinct actions rather than an unknown set; the
  validate-outside-the-lock order has produced 0 dangling `supersedes` in 268 claims
  and costs three writer sites rather than one; 2607 JSONL files show 0 unparseable
  lines and 0 missing final newlines, so the committed-size item is latent. The
  silent plan cut is the ONLY item with an observed occurrence (4 of 91 commits
  carried 4 open plans), and the step-identity case lost most of its force: the
  outcome-less `run` rows are host-local (203 of 1276 sessions all-or-nothing, 5
  mixed), not systematic. Recorded as C21-C24 and written into the report's Measured
  section. Two of the five survive as worth doing now.
- 2026-09-23 — the line's own top finding was withdrawn. Before implementing it, the
  cut site was read in full and `open_plans` turns out to append `(+N more)` at
  `hooks/tezgah_context.py:321`, introduced by `2cc51e4` and already present when
  this session began. The earlier claim was formed by reading the function's loop
  and never its return - a defect asserted from half a function. Recorded as C23c
  (status refuted, superseding C23b), and the report, findings and analysis were
  corrected rather than left to stand. The five-item list therefore yields ONE
  actionable item, not two. The lesson is the one this repository already keeps:
  read the whole function before naming it a defect.
- 2026-09-23 — the surviving item was implemented: `.github/workflows/ci.yml` now
  pins all nine `uses` lines to commit SHAs (`actions/checkout@3d3c42e5`,
  `actions/setup-python@5fda3b95`, `actions/setup-node@82076278`, each with its tag
  in a trailing comment), declares `permissions: {}` at the top and
  `contents: read` per job, and sets `persist-credentials: false` on all four
  checkouts. A YAML parse over the committed file reports 9 uses lines, 0
  unpinned, 0 mutable tags and 4 persist-credentials lines.
