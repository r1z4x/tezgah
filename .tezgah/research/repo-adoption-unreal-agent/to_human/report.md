# unreallabsai/unreal-agent — can anything in it be integrated into tezgah?

**Verdict: yes, nine things, none of them code.** Everything worth taking is a rule, a
field or a paragraph. The repository is a single-process async execution runtime — an
architecture class tezgah's *hosts* occupy, not tezgah — so its engine is not portable and
the answer to "should we integrate it" is a ranked list of shapes, not a dependency.

Evidence: a clone at `b7c9bf1` (169 Go files, 61,771 lines) read in seven read-only passes;
seven literature notes, six of them arXiv preprints confirmed through the arXiv API; twenty
claims. **Nothing was built, installed or executed, and no number here is a measurement of
either system.**

## Why the engine itself is a reject, not a "later"

tezgah is hook-based and daemon-less: `hooks/hooks.json` wires eight host events with 5-10 s
timeouts, and there is no scheduler, session store, tool execution engine or long-lived
process anywhere in the tree. The repository owns all four. The fault-tolerance guarantee
that justifies owning them is bought specifically by moving records out of the failing
process into a router and an append-only transcript owned by no process (`2608.28553`), and
tezgah's hook invocations are serial per host, so it never faces the concurrent-delivery
cell that would justify the purchase (`2608.03836`). "Adopt the engine" and "grow the
process tezgah deliberately does not have" are the same sentence.

## The nine, ranked by payoff per line changed

Costs are **estimates**, formed from the shape of the change, not measured.

| # | Method | What it fixes in tezgah | Lands on | Verdict | Cost (est.) |
|---|---|---|---|---|---|
| 1 | **Commit before dispatch** — one persisted record carries a tool call's status *and* the work it authorizes; the executor is handed work only from that committed value | `hooks/tezgah_integrity.py:990` records the missing capability itself: "a step identity (workflow id, step id, per-step expected outcome) plus a durable pre-state and an inverse operation". tezgah writes intent and outcome from two different hook processes and has no reader for "started and not finished" | `hooks/tezgah_integrity.py` row shape + reader, `hooks/projects-pretooluse.py`, `tests/test_integrity.py` | adapt | 3 files |
| 2 | **A format version on durable state, refused by name** | No version key anywhere: `_check_state` (`hooks/tezgah_research.py:408-424`) validates fields, so a state written by a later tezgah reads as corrupt rather than as unimplemented — and the repo names this gap too ("a record version compared in the write path") | `state.json` template, `_check_state`, `bin/tezgah-research`, `docs/research.md` | adapt | 2 files + 1 test |
| 3 | **Validate inside the append lock** | `claim_problems` runs before `_locked` (`hooks/tezgah_research.py:1276` vs `:1280`), so a relation proved at validation time may not hold in the committed file — and the same order recurs in the prediction and derivation writers | `hooks/tezgah_research.py` | adapt | 1 file + 1 test |
| 4 | **A committed-size boundary on the JSONL stores** | No truncate-to-committed-size before append, and the two readers disagree: `tezgah_integrity._parse` silently skips a torn line (`:492-502`) while the research checker makes the identical damage a permanent refusal (`:969-972`) | `hooks/tezgah_research.py`, `hooks/tezgah_integrity.py` | adapt | 2 files + 1 test |
| 5 | **A third ledger outcome: interrupted, not failed** | `failed` is a boolean (`hooks/projects-posttooluse.py:111-114`), so a check an operator stopped is indistinguishable from one that failed — while those rows feed the partial-state view and the Stop rule | ledger value + host adapters + readers + tests | adapt | 3-4 files |
| 6 | **Truncation that names what it lost** | `_deny` cuts a refusal reason at 80 chars with no marker (`hooks/tezgah_gate.py:1601`), and each injected lesson is cut at `LESSON_CHARS` with no marker (`hooks/tezgah_context.py:374-379`) — while the plan block beside them *does* carry "(+N more)" (`:321`) and the lesson *count* does too (`:392`), so tezgah already has the convention and applies it to whole blocks only. The repository keeps a head *and* a tail, states the exact bytes dropped, and names the file holding the whole | `hooks/tezgah_gate.py`, `hooks/tezgah_context.py` | adapt | 1 helper + 2 sites |
| 7 | **Kill the process group, and verify a permission error before believing it** | tezgah bounds children with `subprocess.run(timeout=)` on the direct child only, so a grandchild outlives the bound; one index-worker call has no timeout at all (`hooks/tezgah_index.py:62-64`) | a shared spawn helper + 3-4 call sites | adapt | 1 helper + 3-4 sites |
| 8 | **A delegate may report progress but not widen its own scope** | Nothing checks that a returned subagent slice kept the scope, budget and question it was given; a delegate that answered a narrower or wider question is read as an answer | `skills/harness/SKILL.md` + brief template | adopt | 1 paragraph |
| 9 | **Evidence and identity adequacy** (`2608.26225`) | A reliability decision needs evidence capable of moving, attributable and deterministic; an identity that fails to discriminate yields a confident wrong answer. A direct test for the gate, the Stop rule and the counters | one paragraph in an existing skill | adopt | 0 new files |

Also `adopt`, from the surveyed repository's CI: **pin every third-party action to a
commit SHA, scope each job's token, keep the fuzz corpus on failure.** tezgah's
`.github/workflows/ci.yml` has nine `uses:` lines all on mutable major tags and no
`permissions:` block at all. One file.

## What not to take, and why

- **The async execution engine, the operation manager, the session store, the fork** — each
  needs state tezgah does not own. The fork is worse than unusable: the repository declares
  it unsound (`loop.go:552`), which `2608.22928` turns into a named finding.
- **The context builder's staged/committed split** — protects a caller holding a stale
  request; tezgah has no model-input assembler and no caller that could hold one.
- **The omission record** — declared and dead: three declared kinds, no producer, and a
  test asserting emptiness while the README states the feature as shipped. tezgah already
  logs its drops (`budgeted`/`_drop_note`/`log_drop`); the move is to add a `kind` to what
  it already writes, not to import a record that does not exist.
- **The container-shaped benchmark fixture** (`benchmarks/harbor`) — needs a task runtime
  and a verifier tezgah would have to own.

## Measured (the estimates above, checked)

The estimates were then measured, and the measurement corrected three of them. Basis: this
machine's `~/.cache/tezgah/evidence/` store (2592 ledgers, 57,469 rows) plus this
repository (15 research lines, 268 claims, 91 commits touching `plans/open`). **Scope: the
running system's own recorded data** — no fixture was generated.

| Item | Measurement | Verdict |
|---|---|---|
| CI pins | 9 `uses` lines over **3 distinct actions**, all `@v7`, no `permissions:` block | **Smaller than estimated**; 9 lines, no behavioural risk |
| 3 — lock order | 268 claims across 15 lines carry 32 `supersedes` refs, **0 dangling** | **No harm observed**; and the surface is **3 writer sites, not 1** — three times the estimate |
| 4 — committed size | across 2607 JSONL files: **0** unparseable lines, **0** files missing a final newline | **Latent** — the damage class has never occurred |
| 5a — plan cut | over the 91 commits touching `plans/open`, the count is 4 in 4 commits and ≤3 in the rest | **Retracted.** The cut fires, but it was **already marked**: `open_plans` appends `(+N more)` at `hooks/tezgah_context.py:321`, introduced by `2cc51e4` and present before this session began. This line's first reading of it covered the loop and not the return, and asserted a defect from half a function (C23c) |
| 1 — step identity | 20.1% of `run` rows carry no exit code **but** 203 of 1276 sessions write every run row without one and only 5 are mixed | **Evidence weaker than claimed** — host-local, not systematic. What survives: 16 ledger kinds exist, none meaning "began" and none meaning "interrupted" |

So of the five, **one survives as worth doing now**: the CI pins (3 distinct actions, no
risk). Item 2 is cheap but its benefit is forward-looking only — 15 of 15 `state.json`
files carry no version and no schema migration has happened yet. Items 3 and 4 are
**latent**, and 3 costs three times what was first stated. The plan cut is **not a defect
at all** — it was already marked, and this report's author asserted otherwise from half a
function — while item 1's evidence is weaker than it claimed.

## Second source: the omp² playbook (added on request)

*The Harness Playbook* — Can Bölük, 2026-09-02, `stencil.so/blog/harness-playbook`, 2,918 lines
read in full. It is the design rationale for **omp²**, and omp is one of tezgah's six hosts, so
it is a host's own statement of where that host is going.

**Verdict, after an exhaustive re-sweep.** The first reading reported "mostly convergence,
two items"; re-read chapter by chapter for *every* mechanism it names and checked against
tezgah's code rather than from memory, that was a selection and not a sweep — and it was wrong
in both directions. The convergence list is **longer** (25 mechanisms were enumerated; **13
already agree**, six of them found only on the second pass: the failure-shapes fold, the
digest-not-text stamp, the effect taxonomy, the off-screen test harnesses, the explicit
`unknown`, and per-program shell classification). The work is **three** items, not two, and
all three are **implemented** — the full table is in
`literature/stencil-harness-playbook.md`.

| # | Implemented | What it fixes | Where | Verified by |
|---|---|---|---|---|
| A | **The ledger row names the contract that wrote it.** The post: "once traces are used for evaluation or repair, guessing any of them becomes avoidable technical debt". 57,469 rows carried no version, and the repo named the gap itself (`hooks/tezgah_integrity.py:998-1000`) | a repair reader (plan 004) cannot tell a shape that moved because the rule changed from one that moved because the row's meaning did | `tezgah_integrity.ROW_VERSION`, stamped in `note_path`; read by `failure_shapes`; printed by `bin/tezgah-status --failure-shapes` as `row contracts read: unversioned xN, v1 xM` | `tests/test_integrity.py::RowContract`, `tests/test_shapes.py` |
| B | **One cut boundary; a shortened text says what it dropped.** The post puts limits in the library layer with an explicit opt-out, because a per-site helper gives uneven coverage and breaks composition | three silent cuts on texts a reader relies on — the injected lesson, the plan block's `Next` line, the refusal reason in the ledger | `tezgah_integrity.cut`, used by `tezgah_context` and `tezgah_gate` | `tests/test_integrity.py::RowContract` |
| C | **A bounded index attempt that kills its process group.** The post: bound blocking time once, and cancellation needs a kill boundary rather than cooperation | a hung codegraph held this repo's flock forever, so auto-index declined to start for the rest of the machine's uptime; `subprocess.run(timeout=)` would kill only the child | `tezgah_index.run_bounded`, `TEZGAH_INDEX_TIMEOUT` (600 s default) | `tests/test_index.py` |

Two further items are **validation rather than new work**: the post's AutoQA loop is this
repository's open plan `004-failure-driven-refinement.md` — same raw material, `deny`/`claim`/
`verify_fail` rows, "and no code reads them to propose a change" — and it supplies the filtering
step that plan does not yet describe ("the reports are noisy… once you do, you get a tremendous
amount of signal"); its measured roster tax (**36.6s** at five tools vs **42.2s** and **37.0s**,
median of 6 runs on task `sol`) is the cost argument behind open plan
`012-mcp-feature-toggles.md`. And **one real gap remains unclosed**: the plan's own `phase` and
`direction` are author-maintained rather than derived from the artifacts (the post's "two
authorities" defect, measured here at 78 examples / 60 stateless / 2 of 17 stateful correct).

Its own machinery — session DOM, Director stack, component renderer, TLA+ transcript protocol —
presupposes a loop, a session store and a terminal. "Adopt the DOM" and "become a harness" are
the same sentence.

**Forward risk, named and not measurable:** tezgah's omp support is a TypeScript bridge over
omp's event names (`hosts/omp/tezgah-hook.ts.in`). The document describes a successor whose
extension surface is Python plus a Director API, commits to nothing about those names, and no
successor build was available to test against.

## What this survey cannot say

No host was run, so whether any of tezgah's six hosts can report an **interrupted** tool call
distinctly from a failed one is not established (item 5's host half). The `remote_job` proxy
path was read but not exercised. Nothing about either system's runtime behaviour is claimed,
and every figure quoted from the repository or from a paper is its author's own.
