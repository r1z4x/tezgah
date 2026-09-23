# Research log

Newest last. One line per decision, experiment, dead end or pivot, with the
evidence that drove it.

- 2026-09-20 — **init.** `bin/tezgah-research init layer-map --question "Which layer does tezgah
  sit in, and how is that boundary drawn against a host, a framework, an SDK, an IDE plugin, an
  eval harness, an orchestrator and MCP?"`. The tool wrote `state.json`, `findings.md`, `log.md`,
  `claims.jsonl` and the three directories; the line was **not** created with `--tracked`, because
  the ignore file is outside this slice's file scope and this is a local, unpublished line. The
  gap plan 005 names: this repository's `harness` is the wrapper around a host, UHP's is the
  "complete agent runtime".
- 2026-09-20 — **screened the six sources the plan names.** Five fetched through the arXiv API
  (`arxiv.org/abs/<id>`), returning title, author list, category and abstract; four of the five
  were cross-checked in OpenAlex by DOI (the fifth's 404 is the next entry). The sixth, the
  Unified Harness Protocol, was read at first
  hand from `raw.githubusercontent.com/HarnessRouter/harnessrouter` (`protocol/README.md` and the
  repository `README.md`). Nothing was inferred from a search snippet.
- 2026-09-20 — **one record did not corroborate.** `https://api.openalex.org/works/doi:10.48550/arxiv.2609.11677`
  answered HTTP 404 — the paper (2026-09-10) is newer than the index. The second record for
  Ecdysis is the alphaXiv mirror, whose first pages were read and which states "Preprint. Under
  review"; the INDEX row names both records and the note records the difference.
- 2026-09-20 — **wrote one note per source, then the index.** Six notes under `literature/`,
  then `literature/INDEX.jsonl` with one row per note: `note`, `id`, `class`, `source`,
  `inclusion`, `verified` (two records each) and `quality`. Five rows are `formal`; the UHP row is
  `grey` with its quality judgement, because it is a vendor's own specification and its own
  benchmark rather than a peer-reviewed record. No row was written before its note existed, so
  no note is unnamed and no row names a missing file.
- 2026-09-20 — **decision: the UHP source is one note with two halves.** The specification text is
  openly licensed and read at first hand; the vendor's benchmark figures (99.8% lower cost, 3.2x
  faster across eight harness x model configurations on one task) are the vendor's own claim about
  its own product and are recorded as such inside the same note, with the vendor as source. The
  alternative — a separate row for the benchmark — would have put a commercial number on equal
  footing with the protocol it is sold with.
- 2026-09-20 — **dead end: no protocol was written.** The layer's rule is that `protocol.md` is
  the prediction committed *before* a run, and `experiments/` would need a protocol-plus-results
  pair to hold anything. Screening six sources is not a run and produces no row, so writing a
  protocol here would invent a prediction nothing tested. `experiments/` stays empty on purpose;
  `check` reads the absence as the ordinary state of a bootstrap line, not as an omission.
- 2026-09-20 — **six literature claims recorded** (`C01`–`C06`), each with a statement, a
  falsification criterion, a proof naming a note under `literature/`, `kind: literature`,
  `provenance`, `status` and a `scope`. No claim declares `evidence`: every number in a note is the
  cited source's, and none was measured in this session. `C01` is the boundary collision itself;
  `C06` records that the vendor benchmark is uncorroborated rather than repeating its figures as
  established.
- 2026-09-20 — **what was left for the plan's other half.** The page, the glossary and
  `skills/harness/SKILL.md` are owned by other slices; this line supplies the source base and the
  boundary vocabulary, and its open questions (where MCP falls; whether any source assigns
  `harness` to a wrapper around a host, as this repository does) are handed to the page rather
  than answered here.
- 2026-09-20 — **this session ran no OpenResearch project.** The `orx` CLI is installed and its
  manual was read, but the task is a literature screen, not an experiment: there is no node to
  create, no run command to fix and no compute to launch. The manual's own rule — never edit a
  node once a run has answered it — has nothing to bind to when no run happens.
- 2026-09-22 — **closed: `concluded` / `conclude`, and the evaluation locked to the screening
  discipline.** The empty evaluation object bootstrap left is now the criterion the other
  literature lines use — one note per source with one `literature/INDEX.jsonl` row each (6 notes,
  6 rows), at zero refusals from `bin/tezgah-research check layer-map --strict` — with the
  environment naming no model and the text saying it is a deliverable count and not a behavioural
  metric. That is the honest evaluation for a line that ran nothing, and it replaces the warn
  `check --strict` was raising ("evaluation locks no metric, baseline, locked_at") with a recorded
  one; the line is now clean under both `check` and `check --strict`. Also written: the missing
  `to_human/report.md` and `to_human/review.json`, whose five findings each quote the file they
  target verbatim. Nothing new was measured, and no note, INDEX row or claim was edited.
- 2026-09-22 — **the boundary question: answered, with two parts explicitly unanswered.** What the
  line was opened for is settled and sourced — the collision (C01: UHP's harness is this
  repository's host, and this repository's harness is the wrapper around it) and the ruler the
  page answers against (C02: the definition paper's inclusion/exclusion list over agent framework,
  agent SDK, IDE plugin, eval harness and orchestrator) — and the answer itself lives on the page
  `docs/layers.md`, which plan 005 landed at 165 lines and 35 citations. Explicitly unanswered by
  this line's sources, and named as such in the report: where MCP falls (none of the six sources
  decides it) and whether any source assigns `harness` to a wrapper around a host, as this
  repository's glossary does (none of the five searched). The other recorded limits are the
  reading depth (four of six notes are an abstract read), the absence of a claim for Harness-R1,
  and the mirror-only second record for Ecdysis.
