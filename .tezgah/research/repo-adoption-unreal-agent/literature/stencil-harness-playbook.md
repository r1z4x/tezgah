# stencil.so/blog/harness-playbook — the omp² playbook, read against tezgah

*The Harness Playbook*, Can Bölük, 2026-09-02, https://stencil.so/blog/harness-playbook — the
design rationale for **omp²**, the successor to omp. 2,918 lines, nine chapters and two
appendices, read in full on 2026-09-23 through the site's own markdown alternate
(`/index.md`). Nothing was installed, built or run.

**Grey source, and unusually good grey.** It is a maintainer's postmortem of a system people
used, and it carries measurements the author ran; it is not peer-reviewed and no number in it
was reproduced here. It is directly relevant because **omp is one of tezgah's six hosts** —
`hosts/omp/` is a first-class adapter — so this document is a host's own statement of where
that host is going.

## What the document argues

Four "architecture tests" (multiplexed workspace, remote driver, spectator, an automated
software factory against hostile input) force five consequences: one authoritative session;
a trusted control plane; bounded work; explicit compatibility; views are projections. Its
chapters argue each, and the shape of every argument is the same: **push the hard invariant
down into the layer that can enforce it**, so correctness does not depend on every
contributor remembering a convention.

## The measured claims it carries

- **78 official extension examples were reviewed: 60 stateless; of the 17 with state, only
  two were correct.** Appendix A names all nine failures with source links and the code that
  fails (`let turnCount = 0` in a closure; a save that scans abandoned branches;
  `session_shutdown` that fires on `/new` as well as exit). The conclusion drawn is that
  documentation would not repair that distribution of bugs — the engine needs one place where
  state can exist, and non-replayable state must be **unrepresentable**.
- **Tool-roster size costs wall-clock.** Median of 6 runs, fresh session each, task `sol`:
  limiting omp to five essential tools gives **36.6s**, ahead of Codex's **42.2s** and Pi's
  **37.0s**.
- **A render-pipeline rewrite**: `render(): string[]` → a streamed `RichText` pipeline,
  reported as **267 seconds → 90ms** for the same session.

## Where tezgah already agrees (this is most of it)

- **One authority, derived views.** tezgah's evidence ledger is append-only JSONL and its
  views are recomputed from it (`hooks/tezgah_integrity.py` counters and shapes). The post's
  first principle — state derivable from the events alone — is tezgah's shape.
- **Small local models for harness work, not a second agent.** `hooks/tezgah_judge.py` is
  called by `hooks/tezgah_skill_pick.py` for a one-line classification, and the picker's own
  docstring quotes the same economics.
- **The long tail behind a stable surface.** The post's `dyn` CLI (a stable discovery
  protocol with the long tail reachable through composition) is tezgah's `bin/tezgah-docs`
  router, `skill://`, and `bin/tezgah-research`: a small always-on surface plus a router.
- **Limits at the rendering layer, not per call site.** `hooks/tezgah_context.py`'s
  `budgeted` bounds a whole event under a byte budget with a documented drop order — the
  post's "one central implementation" — and `hooks/tezgah_apps.py` already reasons about
  roster width in its own comment ("a second copy of it would only widen the tool list").
- **Verification specified in advance.** "If how to verify is unknown and unspecified, the
  agent will side-channel a look-alike… it will create a test file that doesn't really check
  anything" is the failure `docs/testing.md` and the evidence rule's anti-neutered-check
  refusals exist against.
- **A declaration that carries its own flags.** The post's convar argument (scope,
  persistence and replication belong on the variable's definition, not in setter call sites)
  is `hooks/tezgah_components.py`: one row per component with its label, files, switch,
  editable flag and revert mode.

## Where it lands as work

**Superseded by the exhaustive sweep below, which is the section to read**: this list is the
first pass's selection, and the sweep found one more item and six more convergences.

- **Version the rows tezgah writes.** "Name, version, intent, input, output, diagnostics, and
  usage are protocol data. Once traces are used for evaluation or repair, guessing any of
  them becomes avoidable technical debt." tezgah's ledger row carries `kind`, `ts`, `detail`,
  `id`, `exit`, `out_bytes`, `hash` and a per-row `source` attribution — **no version** — and
  the repository has already recorded the gap itself: `hooks/tezgah_integrity.py:998-1000`
  names "a record version compared in the write path" as a missing capability. This matters
  the moment plan 004 reads those rows to propose a change.
- **Close the loop from recorded failure to a change, and filter the reports.**
  The post's AutoQA tool exists to collect "which tool fails and how it can be improved", and
  it states the step that makes the data usable: the reports are noisy, and "it is very easy
  to filter them out, and once you do, you get a tremendous amount of signal". Plan
  `004-failure-driven-refinement.md` is the same loop in this repository, already open, and
  its Goal names the same raw material (`deny` rows by rule, `claim` rows, `verify_fail`)
  across 1454 sessions with no code reading them. This post is independent evidence that the
  plan's direction is the right one, and it supplies the filtering step the plan does not yet
  describe.
- **A bound that cuts inside a block should still say so, and be overridable.** The post's
  rule is central enforcement plus an explicit opt-out (`notrunc`); tezgah centralises the
  *block* budget and cuts *within* blocks silently (`hooks/tezgah_gate.py:1601` truncates a
  refusal reason at 80 characters; each injected lesson is cut at `LESSON_CHARS`).
- **The roster tax is a reason for plan 012, not a new plan.** tezgah mounts two MCP servers
  into every session by default (`hooks/tezgah_apps.py` SERVERS: playwright, mobile-mcp) and
  a third opt-in; the post measures what that class of decision costs in wall-clock. Plan
  `012-mcp-feature-toggles.md` is the registry that makes the selection first-class.

## The exhaustive pass: every named mechanism against tezgah

The first reading of this document reported "mostly convergence, two items". Re-read
chapter by chapter for every mechanism it *names*, and checked against tezgah's code rather
than from memory, the harvest changes twice: the convergence list is **longer**, and the
work is **three** items rather than two. Both corrections are recorded because the first
reading was a selection, not a sweep. **Twenty-five mechanisms were enumerated: 13 converge
and 3 were implemented.**

| # | Mechanism the playbook names | tezgah | Verdict |
| --- | --- | --- | --- |
| 1 | State must be derivable from the journal alone | ledger is append-only; `counters`/`failure_shapes` recompute from it | converge |
| 2 | Non-replayable state must be unrepresentable | `tezgah_components.py` pins a label, a switch and a revert mode per rule; `check` refuses rather than the writer remembering | converge |
| 3 | Hash the template and store its variables, do not repeat it in every log | `tezgah_context.write_stamp`/`state_delta` store a count+digest per session, not the text | converge |
| 4 | Sandbox executes, host decides | the gate decides before the host acts; tezgah owns no execution | converge in shape |
| 5 | Bound output once, centrally, with an explicit opt-out | `budgeted` bounds a whole event; the cuts *inside* a block were silent | **implemented** |
| 6 | One stdio-shaped job primitive (`signal` + in + out) | the host's `hub`; not tezgah's to own | n/a |
| 7 | Cancellation needs a kill boundary, not cooperation | the index worker is spawned with `start_new_session=True`, but its own codegraph call was unbounded and killed only the child | **implemented** |
| 8 | Copy-on-write subagent isolation (`pi-iso`) | tezgah spawns no agents; its answer is a read-only role definition | reject |
| 9 | Convar: a typed variable whose flags are declared where it is born | `tezgah_components.py` rows carry label, files, switch, editable, revert | converge |
| 10 | Directors: one composable stack owning the yield | tezgah has no loop to own | reject |
| 11 | Explicit compatibility: one owner per fact, an `unknown` state, an error on ambiguous precedence | `bin/tezgah-setup`'s event tables and `hosts/*/hooks.json` are checked against each other; `TEZGAH_CALL_OUTCOME=none` is an explicit unknown | converge |
| 12 | Corrective inference: repair malformed JSON, detect repetition and leaked dialects | `bin/codegen` refuses a truncated or unparseable draft by design and names which; `bin/consult` classifies a malformed reply | partial |
| 13 | Validate *and* correct a model's tool arguments | no tool layer | reject |
| 14 | Forced-tool-call policy (soft prompt, native flag only when free, escalate) | no tool choice | reject |
| 15 | Compaction scheduled speculatively, not triggered | compaction is the host's act; tezgah only reacts to `post_compact` | reject |
| 16 | A small local model for harness work | `hooks/tezgah_judge.py`, called by `hooks/tezgah_skill_pick.py` | converge |
| 17 | Every tool schema has a tax; a small roster, long tail behind a stable surface | `bin/tezgah-docs`, `skill://`, `bin/tezgah-research` are the router; the MCP roster is plan 012's subject | converge |
| 18 | Version your tools; name, version, intent, input, output, diagnostics, usage are protocol data | the row carried `kind, ts, detail, id, exit, out_bytes, hash, workspace, source` and **no version** | **implemented** |
| 19 | Bash as a policy-aware command language | `tezgah_context.shell_programs` tokenizes a line into the programs it would run; `shell_kind` classifies by program, not by substring | converge |
| 20 | Approval at the capability boundary, not the shell-string boundary | the `EFFECTS` taxonomy, with a command able to self-declare `tezgah:effect=<class>` | converge |
| 21 | AutoQA: collect what agents found confusing, filter the misattributions, repair from the signal | `bin/tezgah-status --failure-shapes` folds recurring refusals across sessions with `fires_per_session` as the precision proxy; plan 004 is the half that proposes a change | converge (was under-reported) |
| 22 | Presentation policy belongs to the renderer (semantic colour, icons, truncation, pacing) | `statusline.py` resolves colour through `color_default()`/`render_line`, not literals in place | converge |
| 23 | Verification is part of the interface: a non-destructive, off-screen, multi-instance harness | `tests/_omp_extension_harness.mjs`, `_opencode_plugin_harness.mjs`, `_probe_*.py` | converge |
| 24 | Model the hard invariant formally and keep a reference to update | the research layer's committed protocol + its checks; no TUI to model here | converge in method |
| 25 | Language choice is architecture; Python for extensions | tezgah is Python | converge |

### What was implemented

- **The ledger row carries the contract that wrote it** (`tezgah_integrity.ROW_VERSION`,
  stamped in `note_path` beside `kind` and `ts`, so it is not a caller field, and a caller
  passing one is dropped like any other typo). It is read, not decorative:
  `failure_shapes` counts rows per contract and `bin/tezgah-status --failure-shapes` prints
  `row contracts read: unversioned xN, v1 xM`, on the module's own stated principle that an
  answer must say what corpus produced it.
- **One cut boundary** (`tezgah_integrity.cut`), used by the three places that shorten a
  text a reader or the model then relies on: the injected lesson (a rule sentence that lost
  its verb in silence), the plan block's `Next` line, and the refusal reason stored in the
  ledger. The marker rides *on top of* the limit rather than inside it, `budgeted`'s rule.
  A fourth cut — `_stale_paths` shortening a path for a refusal message — is deliberately
  left alone: the full path is still in the row, so no information is lost there, and a
  marker would only lengthen a message.
- **A bounded index attempt that kills its process group**
  (`tezgah_index.run_bounded`, `TEZGAH_INDEX_TIMEOUT`, default 600 s). Without it a hung
  codegraph held this repository's flock forever, and the next session's auto-index then
  declined to start for the rest of the machine's uptime.

## What does not transfer

- **The session DOM, the Director stack, the component renderer, the TLA+ transcript
  protocol.** All four presuppose a process that owns an agent loop and a terminal. tezgah is
  hook-based, has no loop, no session store and no renderer; "adopt the DOM" and "become a
  harness" are the same sentence. The transferable half is the *method* — model the hard
  invariant, check it, keep a reference to update — which is what tezgah's research layer
  already does with a frozen protocol.
- **The sandbox/host split and the copy-on-write subagent isolation (`pi-iso`).** tezgah does
  not spawn agents; its answer to the same threat is a read-only subagent definition
  (`hooks/tezgah_agents.py` `ROLES`, fifth element), enforced per host dialect.
- **Scheduled speculative compaction.** Compaction is the host's act; tezgah only reacts to
  `post_compact`.

## Host-compatibility risk, stated plainly

The document describes **omp²**, a replacement whose extension surface is Python plus a
Director API, and it says of the current one that "this class of software did not exist
before". tezgah's omp support is a TypeScript bridge (`hosts/omp/tezgah-hook.ts.in`) mapping
omp's agent-loop events onto tezgah's vocabulary. Nothing in the document commits to keeping
those event names, and no migration guide is published. This is a **forward risk to
`hosts/omp/` that this line can name but cannot measure** — no omp² build was available to
test against.
