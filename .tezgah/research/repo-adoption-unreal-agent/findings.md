# Findings

Line: `repo-adoption-unreal-agent`. Question: does `unreallabsai/unreal-agent` carry machinery
worth adopting into tezgah, and what would each piece cost to adopt?

Evidence base: one clone at commit `b7c9bf1` (169 Go files, 61,771 lines under `harness/
internal/ cmd/ benchmarks/`), read in seven read-only passes; seven literature notes
(`literature/INDEX.jsonl`), six of them arXiv preprints verified against two records each;
twenty claims in `claims.jsonl`. **Nothing was built, installed, imported or executed, and
no number in this line is a measurement of either system.** Every figure below is quoted
from a source or is a count of files that were opened.

## What we know

The repository is a single-process, event-loop-coordinated async tool-execution runtime
(C01, `literature/unreal-agent-unreallabs-harness.md`). One goroutine multiplexes inbox,
operation updates, tool heartbeat, grace deadline and model responses on a bare `select`
(`harness/coordinator/loop.go:125`); tool translators run synchronously on that loop and
may not perform I/O (`README.md:20`); asynchronous work becomes a versioned serializable
`operation.Operation` (`harness/operation/operation.go:29-46`) handed to an actor
manager whose local implementation is swappable (`harness/operation/local_manager.go`);
durability is one append-only, versioned session log with `Resume` and `Fork`
(`harness/sessionstore/sessionstore.go:85-117`).

That class is the slot tezgah's **hosts** occupy, not the slot tezgah occupies. tezgah is
25 hook modules wired by `hooks/hooks.json` to eight host events at 5-10 s timeouts, with
no scheduler, no session store, no tool execution engine and no long-lived process. So
"adopt the async engine" and "grow the process tezgah deliberately does not have" are the
same sentence in two directions. `2608.28553` is the published measurement of why: the
fault-tolerance guarantee such a process exists to buy is bought specifically by moving
records out of the failing process into a router and an append-owned transcript, and the
single-process reference in that study lost every session under one fault.

What does transfer is a decomposition discipline, and each piece of it landed on a tezgah
surface with a zero-dependency cost. Nine candidates survived to the report; the three
load-bearing ones are **commit-before-dispatch** (C02 — a tool call's status and the
operations it authorizes are one persisted record, and the executor is handed work only
from that committed value), the **version gate at record zero** (C03 — a writer stamps a
format version, and a reader refuses an unimplemented one by name before decoding
anything), and **producer-supplied identity with the seen-set rebuilt from history**
(C04). All three land as rules in tezgah, not as code from the repository.

Four things the repository does well are already partly present in tezgah, and the honest
reading is the reverse of the obvious one. The **omission record** its README promises is
declared and dead: `ChangeKind`, `Change`, `Report` and `Result.Report` exist, nothing
populates them, the only `Build()` caller discards the value, and the one test asserts the
change list stays **empty** (C09). tezgah, by contrast, *does* record its drops — `budgeted`,
`_drop_note` and `log_drop` name what went, in what order, at what size, and where the text
still lives (`hooks/tezgah_context.py:702-752`, C16). The dependency is therefore
backwards from the one a reader would guess: `2606.19409` names the evidence a compaction
loses, the repository claims to keep it and does not, and tezgah keeps it in an untyped
form. The adoptable move is to type tezgah's existing record, not to import theirs.

Three gaps are declared in the repository's own comments rather than in issues (C10): the
fork path "leave[s] inherited calls without results and retain[s] pending-input accounting"
(`harness/coordinator/loop.go:552`), the store does not preserve status snapshots in forked
history (`harness/sessionstore/localfile/state.go:401`), and a truncated remote result is
never captured to a file before truncation (`harness/operation/remote_job_output.go:4`).
The fork half is exactly the invariant `2608.22928` makes checkable, which turns an apology
in a comment into a named open finding — and which is why the fork path is not a source
this line borrows from.

**The estimates in the report were then measured, and the measurement corrected three of
them** (C21-C24). Measured on the running system's own stores — 2592 evidence ledgers
holding 57469 rows, and this repository's 15 research lines and 91 commits that touch
`plans/open`:

- The CI item is smaller than stated: 9 `uses` lines over exactly **3 distinct actions**,
  all on the mutable major tag `v7`, and no `permissions` block anywhere (C21).
- The validate-outside-the-lock order has **never produced a dangling relation** — 268
  claims across 15 lines carry 32 `supersedes` references and every target resolves — and
  its surface is **three writer sites, not one**, so it costs three times the estimate and
  has zero observed harm (C22).
- The output stores are **clean**: no unparseable line and no file missing its final
  newline across 2607 JSONL files, so the committed-size item is latent (C24).
- The plan cut **fires but is not silent**: the open-plan count is 4 in 4 of 91 commits,
  and `open_plans` already appends `(+N more)` when it drops any. This line first claimed
  the opposite from a reading that covered the function's loop and not its return; the
  claim is retracted and the item is withdrawn (C23c).
- The step-identity case is **weaker than this line first argued**: the 4852 `run` rows
  with no exit code are host-local, not systematic (203 of 1276 sessions write every run
  row without an exit; only 5 are mixed). What survives is a vocabulary fact — 16 ledger
  kinds exist, none meaning that a step began, none meaning that it was interrupted rather
  than failed (C24).

**A second source was added on request: the omp² playbook** (C25-C32, C33-C37). It is the
design rationale for the successor to omp — and omp is one of tezgah's six hosts, so it
doubles as a host's statement of where that host is going. Re-swept exhaustively (every
named mechanism, checked against the code): 25 mechanisms enumerated, **13 already agree**,
and **3 were implemented**. The first reading of this document reported "mostly convergence,
two items" — that was a selection, not a sweep, and it under-reported the convergence (the
failure-shapes fold, the digest-not-store stamp, the `EFFECTS` taxonomy, the off-screen test
harnesses, the explicit `unknown` and per-program shell classification were all missed) while
also missing one item.

Implemented, each verified by a test that fails without it: the **ledger row names the
contract that wrote it** (`ROW_VERSION`, read back by `failure_shapes` and printed by
`bin/tezgah-status`) (C33); **one cut boundary** that makes a shortened text say what it
dropped, at the three sites where a reader relies on the text (C34); and **a bounded index
attempt that kills its process group**, without which a hung codegraph held this repository's
flock for the rest of the machine's uptime (C35). What the sweep also produced is a
correction and a limit: the first harvest was under-counted (C36), and one real gap remains
unclosed — `state.json`'s `phase` and `direction` are author-maintained rather than derived,
which is the post's own "two authorities" defect (C37). Its own machinery — session DOM,
Director stack, renderer, TLA+ transcript protocol — presupposes a loop tezgah does not have
(C32).

## Patterns

- A guarantee a daemon-less hook layer cannot hold should be named and declined [C01], not
  approximated. `2608.28553` shows the reversibility guarantee is bought by a process
  boundary, and `2608.03836` shows even durable backends fail consume-once under concurrent
  delivery; tezgah's hooks are serial per host, so it does not face that cell. The usable
  output is the six-property vocabulary for saying which guarantees it does and does not
  hold.
- The borrowable unit is consistently a shape-of-record, never a runtime [C02] [C03] [C05]
  [C06] [C07] [C15]. Across all seven slices, every surviving candidate turned out to be a
  rule, a field or a paragraph — an intent committed before its effect, a version gate, a
  marker on a cut, a closed status vocabulary, a delegation whose scope the delegate may
  not widen — while every candidate that needed state tezgah does not own (the operation
  manager, the context builder's staged/committed split, the fork, the session store) was
  rejected.
- A declared-but-unwired interface survives review because the type exists [C09]. The
  repository ships an omission record with three declared kinds, no producer and a test
  asserting emptiness, while its README states the feature as shipped. This is the defect
  class tezgah's own `skills/feature-audit/SKILL.md` exists to find, and it is evidence for
  that rule from outside the repository.
- Two readers of one file shape, with opposite postures, is a defect neither can see [C14].
  tezgah's ledger reader silently skips a torn line and its research checker refuses the
  same damage permanently; the repository under survey instead fixes a committed-size
  boundary and truncates to it before appending.
- A reliability decision needs evidence that can move and identity that discriminates [C12] [C15].
  `2608.26225` derives both from measured production incidents, one of them a
  progress signal computed over an identifier that was constant by construction. Both are
  tests tezgah can apply to its own gate, Stop rule and counters at zero dependency cost.
- A bound that does not name what it dropped turns a trim into a silent loss [C07] [C16].
  The repository's truncation keeps a head and a tail, states the exact byte count dropped
  and names the file holding the whole. tezgah applies the convention to whole blocks —
  the plan and lesson *counts* both carry `(+N ...)` — and not inside a block: `_deny`
  cuts a reason at 80 characters and each lesson is cut at `LESSON_CHARS`, both silently.
  The rule is therefore about where tezgah stops applying a convention it already has,
  not about adopting one.

- A trace that has to be read for repair must say which build produced it [C29]. The playbook's
  rule ("once traces are used for evaluation or repair, guessing any of them becomes avoidable
  technical debt") lands on tezgah's own ledger, where 57,469 rows carry no version and an
  open plan is about to read them.
- A published design document is worth reading for its *convergences* first [C25] [C32]. Six of
  the playbook's stated methods were already tezgah's, and the honest harvest was one field and
  one cut site — so the cost of reading it was mostly the cost of confirming what tezgah
  already does, which is itself the useful result.

## Lessons

- **A prediction written before the reading is worth writing even when it scores partial.**
  The protocol predicted the borrowable material would be decomposition rather than code
  (held) and that the session store and input dedup would be subsystems tezgah must build
  rather than borrow (wrong: both are cheap adaptations). Recording it first is what makes
  the correction visible instead of invisible (C19).
- **Survey a repository by its own declared gaps before its features.** The three
  `FIXME`/`TODO` comments in the clone were the fastest route to the honest answer, and one
  of them (`loop.go:552`) was the single most decision-relevant line in 61,771.
- **A repository's README component table is a claim about intent, not about code.** The
  only way to settle it was to grep for the producer of the declared type; the answer
  changed this line's central recommendation from "adopt their record" to "type your own".
- **Verify a delegated survey's load-bearing claim before it enters a claim row.** The
  `Report`-is-dead finding and the `FIXME` were each re-read at the cited lines, and
  `[CITATION NEEDED]`-style risk was checked by confirming all six arXiv records through
  the arXiv API independently of the notes that quoted them.

## Open questions

- Which of tezgah's six hosts can report an **interrupted** tool call distinctly from a
  failed one. The absent third outcome (C15) is confirmed on tezgah's side; the host half
  was not established, because no host was run.
- Whether the `remote_job` proxy path can be reached without the operation manager's actor
  runtime, or only with it. The routing, version-matching and update validation were read;
  the execution side was not exercised.
- What a tezgah-side task fixture would measure if it were driven through a host CLI
  rather than a container. `2608.06790` puts the instrument question on the table and this
  line rejects the container-shaped answer without evaluating the host-CLI-shaped one.
- Whether typing tezgah's drop record (C16) is worth more than the one field it costs. The
  argument for it rests on `2606.19409`'s claim that compression loses evidence; that claim
  is architectural, not measured.
