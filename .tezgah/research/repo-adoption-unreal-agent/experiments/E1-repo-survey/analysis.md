# E1 — analysis of the reading pass

Protocol: `protocol.md`, committed at `c9a7243` before any survey returned. The protocol's
prediction is therefore provably older than every candidate it is scored against, which is
the only claim of ordering this experiment makes.

## What was done

Seven read-only surveys over the clone at `b7c9bf1`, each returning candidates as
`{what_it_does, evidence, invariant, tezgah_gap, tezgah_surface, verdict, cost}` with
`file:line` citations, plus a `refutations` list and a `coverage_gaps` list:

| Slice | Target | Candidates |
| --- | --- | --- |
| Coordinator + inbox | `harness/coordinator/`, `harness/inbox/` | 7 |
| Operations + primitives | `harness/operation/`, `harness/primitives/` | 8 |
| Context builder + tools | `harness/contextbuilder/`, `harness/tool/` | 7 |
| Session store | `harness/sessionstore/**` | 6 |
| LLM + runner + benchmark + CI | `harness/llm/`, `cmd/`, `benchmarks/`, `.github/` | 8 |
| tezgah extension surface | `hooks/`, `bin/`, `hosts/`, `skills/`, `workflows/`, `docs/` | 23 seams, 22 extension classes |
| Literature and positioning | `orx discover` + web, plus the four closest existing notes | 7 notes |

A separate literature step produced seven notes (`literature/INDEX.jsonl`), six of them
arXiv preprints whose records were confirmed through the arXiv API independently of the
notes that quote them.

## Verdicts, counted

Across the six repository slices: **3 `adopt`, 25 `adapt`, 8 `reject`** (candidates only;
refutations and coverage gaps are separate lists). The rejects are not a judgement on the
repository — they are the machinery that needs a state tezgah does not own: the operation
manager's actor runtime, the context builder's committed/staged split, the fork, the
session store, the container-shaped benchmark fixture, the mid-session settings path, and
the Docker/release image chain.

## Scoring the prediction

The protocol predicted two things.

**Half one — "the adoptable material is the repository's decomposition discipline rather
than its code; the tool-translator/operation split names a method tezgah can adopt at zero
dependency cost."** Holds. Every surviving candidate is a rule or a field, never a ported
component; the translator's I/O-free contract is precisely what a 5-second hook already has
to be; and no slice recommended importing the runtime.

**Half two — "the versioned forkable session store and the stable-id input dedup are the
two subsystems tezgah most lacks and would most likely have to build rather than borrow."**
Wrong in one direction and refuted in the other. Wrong: the version gate is a key, a
branch ahead of the field checks and a named refusal (~12 lines), and the identity rule is
two to three files — both are cheap *adaptations*, not subsystems to build. Refuted: the
fork path is declared unsound by the repository itself (`loop.go:552`, C10), so it was
never a borrowable source, and `2608.22928` is what makes that a named finding rather than
an omission from this survey.

**Falsifier from the protocol** — "every subsystem doing so [reducing to 'requires a host
tezgah does not have']" — did not fire: 28 of 36 candidates landed on a live tezgah surface.

**Score: PARTIAL.** Direction confirmed, one of the two named subsystems mispredicted.

## What was measured afterwards, and what it corrected

The reading pass produced cost *estimates*. They were later measured against the running
system's own recorded data — this machine's `~/.cache/tezgah/evidence/` ledgers and this
repository — and the rows are `results.jsonl` (M1-M5), with claims C21b-C24b superseding
the C21-C24 estimates. **Scope: `real`** — no fixture was generated for any row.

| Row | Measurement | Effect |
| --- | --- | --- |
| M1 | 9 `uses` lines over **3 distinct actions**, all `@v7`, 0 SHA-pinned, no `permissions:` block | CI item is smaller than stated |
| M2 | 15 lines, 268 claims, 32 `supersedes` refs, **0 dangling** | Lock-order defect is latent; surface is **3 writer sites, not 1** |
| M3 | 91 commits touching `plans/open`, **4** of them carrying 4 open plans | The cut **fires, and was already marked** — the "silent cut" this line first reported does not exist (C23c) |
| M4 | 2607 JSONL files: **0** unparseable, **0** missing a final newline | Committed-size item is latent |
| M5 | 2592 ledgers, 57469 rows, 16 kinds; 4852 run rows without an exit, but **203 of 1276 sessions all-or-nothing and only 5 mixed** | Step-identity evidence is **host-local, not systematic** |

Two of the five estimates were corrected upward in cost, two were shown latent, and one
lost its supporting evidence. Of the five, two survive as worth doing now (M3's marker and
M1's pins); one is cheap but forward-looking only (no `state.json` carries a version and no
schema migration has happened yet, so the version gate protects a future that has not
arrived).

The protocol is untouched by this — the rows were added after it was already in history,
which is the order the layer exists to make decidable.

## Why this is not a measurement of either system

No Go toolchain was invoked, nothing was compiled, no test was run, no binary was
produced, no container was started, no model call was made against either system, and no
file in the clone was modified. Nothing about `unreallabsai/unreal-agent` is measured
anywhere in this line: every claim about it is `literature` (over a note) or `code` (over
an artifact of this repository), and the twenty-four claims the line holds include no
`evidence` claim resting on a row about that repository.

What the line does measure is **its own repository and this machine**: five rows in
`results.jsonl`, all declared `scope: real`, and the four claims that rest on them
(C21b-C24b) carry that scope. The distinction is the point — a reading pass over 61,771
lines of Go produced estimates, and only the estimates about tezgah's own surfaces could
be turned into rows, by scanning tezgah's own stores.

The ceiling that follows: this line can say what the repository's code does when read, and
what the sources claim. It cannot say what either system does when run, and it does not.
