# zzet/gortex v0.64.4 — a Go code-intelligence engine, and the three ideas in it

https://github.com/zzet/gortex — Apache-2.0, Go (CGO, tree-sitter bindings), release
`v0.64.4` published 2026-09-16, created 2026-04-06, last push 2026-09-21. Read at first
hand through the GitHub API and the raw endpoints of `README.md`, `BENCHMARK.md`,
`docs/{architecture,mcp,cli,agents,features,savings,languages,multi-repo,installation}.md`,
the release asset list and `.github/workflows/ci.yml`. **Nothing was installed, no index
was built and no number below was reproduced**; the survey that read these files had no
ability to execute anything.

## What it is

A single Go binary that indexes a repository into a persistent SQLite knowledge graph and
serves it to agents over three transports - a cobra CLI, MCP (stdio plus an HTTP
transport) and a versioned HTTP `/v1` API with a standalone web UI - behind a long-lived
daemon on a unix socket. Nodes are `<repo_prefix>/<path>::<Symbol>`, so multi-repo is the
default shape rather than a bolted-on mode.

- **Scale and maturity, from the GitHub API on 2026-09-22**: 1,626 stars, 156 forks, 79
  open issues, ~45 MB repo. CI runs a 3-OS matrix on Go 1.27 with `go test -race
  -timeout=45m ./...`, a Codecov upload, a static-link build verified inside `debian:11`
  and `alpine:3`, and golangci-lint. Its own CI comment says the suite runs about 30
  minutes on the ubuntu runners.
- **Language coverage in three extraction tiers**: bespoke tree-sitter for roughly 30
  languages, regex for roughly 60, and forest-backed signature-only extraction for
  roughly 165, plus per-cell extraction for Jupyter and Databricks notebooks. The counts
  do not agree with each other in the repository's own docs: `README.md` and
  `docs/features.md` say 257, `docs/languages.md` says 256 and its "At a glance" table
  sums to 256.
- **MCP surface**: the same handlers are published as a 21-tool static facade for named
  clients, an approximately 35-tool `core` preset by default, or the full catalogue, which
  the docs count as "~180" in one place and "100+" in another while the README says 175
  (configurable). Presets run in `defer` (reachable through a search tool that promotes a
  schema into `tools/list`) or `hide` (removed and hard-blocked), and a stdio proxy can
  filter one client's surface while the daemon keeps serving the rest.
- **PR review as a graph-grounded verdict**: `review` emits line-anchored findings with a
  BLOCK/REVIEW/APPROVE verdict from an AST-grounded rulepack, `review_pack` folds that
  with per-file risk, contract impact and impacted test targets into one envelope with a
  derived `verification_command`, and `pr_risk`/`triage_prs`/`suggest_reviewers` sit beside
  them.
- **Packaging and supply chain**: signed binaries for linux/darwin/windows on amd64 and
  arm64 (the darwin/arm64 tarball is 51,226,304 bytes), a curl installer, a Homebrew tap,
  `.deb`/`.rpm`/`.apk`, a Scoop bucket, cosign signatures with SLSA-3 provenance and
  VirusTotal scans.
- **It is not tezgah's engine.** tezgah's code-graph rule is written against
  `colbymchenry/codegraph` (MIT, Rust kernel, 71,724 stars, 4,605 forks, 528 open issues),
  the engine `plans/done/010-codegraph-backend-migration.md` records as the measured
  replacement for `codebase-memory-mcp`. Gortex's verbs (`gortex query <sub>`,
  `gortex init`, `gortex daemon`), its env var (`GORTEX_TOOLS`) and its store (XDG, behind
  a daemon) belong to a different product that answers the same job description.

## Three ideas worth reading, and one hazard

**1. Edge provenance with an in-band honesty caveat.** Every edge carries an origin tier -
`lsp_resolved`, `lsp_dispatch`, `ast_resolved`, `ast_inferred`, `text_matched` - which
`get_callers`, `find_usages` and `find_implementations` can filter with `min_tier`. A
caller answer attaches a structured `caveat` (`likely_unused`, `possible_extraction_gap`,
`coverage_incomplete`) and reports `name_only_candidates`, the call sites that name the
symbol and bind to nothing, so a thin caller list reads as "1 verified, 20 unverified"
rather than as proof of safety. `analyze kind=resolution_outcomes` explains why an edge was
left unresolved. The docs call this the honest floor under a thin caller list.

**2. Two lifetimes for one write: disk versus graph, and a receipt for the abandoned call.**
Every tool call is bounded (60 s by default) and an overrun is *abandoned* rather than
killed: the client gets a terminal error while the handler keeps running. Mutations
therefore report `disk_status` (committed / not_applied / failed / in_flight) separately
from `graph_status` (fresh / pending / stale / failed), leave a receipt queryable for 30
minutes through `mutation_status`, and `physical_evidence: true` re-reads the file after an
atomic write and returns sha256 digests. The docs state the consequence for a caller: treat
any side effect of an abandoned call as unknown and re-read before assuming it did or did
not land.

**3. A savings ledger written to under-report.** Per-call, per-session and cross-session
token accounting priced with tiktoken `cl100k_base`, with two deliberate caps: a file's
whole-file baseline is credited at most once per session per file, and at most 8 distinct
cited files are credited by any single call. A call that credits no new file books nothing
rather than a zero-baseline row. The README's headline is "up to 50x fewer tokens per
response", which `BENCHMARK.md` does not state: its token-efficiency table measures 31,530
tokens to 972 and 23,027 to 577 on two queries against its own repository, which is about
32x and 40x on that one machine - and `BENCHMARK.md` says in its own words that the numbers
come from a single operator's machine.

**The hazard: its installer writes the files tezgah owns.** `gortex install` writes
user-level machinery and `gortex init` writes per-repo machinery - `.mcp.json`,
`.claude/settings.*`, a marker-guarded `CLAUDE.md`/`AGENTS.md` community block, repo-local
hooks and per-agent MCP configs across a 20-host adapter matrix. tezgah's installer
(`bin/tezgah-setup:185-194, 313-330, 544-570`) is the only writer of those same six host
surfaces, and tezgah's graph rule forbids a repository `CLAUDE.md`/`AGENTS.md` from
demoting the graph. Two writers, one file, no arbitration.

## Why it is in this line

The line asks whether either repository carries anything worth adopting. Gortex is the
source of the three portable ideas above and the reason the question has to be answered
"borrow the idea, not the code": its engine is a replacement shape, not an addition, and
the pieces worth having are habits of its answers rather than its architecture.

## Quality and limits

**Grey**: a tool's own documentation, README and benchmark page, written by its author and
independent of nothing. The Apache-2.0 text, the API metadata and the CI workflow are read
at first hand and are checkable; every performance, token, star and language-count figure is
the author's own and none was reproduced - no binary was installed, no daemon was started,
no index was built, and this survey ran no command against gortex at all. The docs disagree
with each other on the language count (257 against 256), the MCP tool count (175 against
"~180" against "100+") and the Go version floor (README's 1.26 against CI's 1.27), so any
figure quoted from this source is a figure the source does not state consistently. The
per-repo store path is never named; the docs say only that it follows XDG and is shared
across repos behind one daemon.
