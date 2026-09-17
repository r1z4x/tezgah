---
id: 014
title: Record a claim under a lock, not by hand
status: open
branch: plan/014-claim-append-lock
pr:
created: 2026-09-17
updated: 2026-09-17
---
## Goal
`claims.jsonl` is the file every claim of a research line lives in, and it is the
one append-only path in this repository with no lock: `check` reads it and
nothing serialises writes to it. A session records a claim by editing the file
with its own write tool, which is an unlocked read-modify-write, and the only
guard is the gate's `race` rule - whose own comments name two ways a writer
escapes it (`hooks/tezgah_gate.py:805`, `:828`). Two sessions recording a claim
at the same moment can therefore lose one silently, or leave a line that does not
parse, which `check` then reports as `does not parse` rather than as a race.

Found while reading an external failure-mode corpus, and recorded as C17 in
`.tezgah/research/agent-failure-controls/claims.jsonl` (local state, not
repository content).

## Decisions
- **The lock goes where the write happens.** It cannot be added to the writer,
  because the writer is the session's own file tool; so the CLI grows the append
  path and the skill stops telling sessions to hand-edit the file.
- **A refusal beats a silent unlocked append.** The harness ledger's `_append`
  falls back to an unlocked write when the lock cannot be taken
  (`hooks/tezgah_integrity.py:313`). A ledger row is a trace; a claim is
  evidence, so this path refuses and names the reason instead.
- **`claim_problems` mirrors `check` exactly** - a statement, a falsification
  criterion, a proof, a provenance in `PROVENANCE`, a status in `STATUSES`, and
  every path-like token in `proof` resolving under the line or the repo. The CLI
  may not be stricter than the checker, or a session hits a wall `check` would
  never have raised.
- **No invented ids.** The command records the claim it is handed; numbering
  stays the session's business.
- **Stdin, not a flag.** A claim is a JSON object that is easy to get wrong and
  awkward to quote in argv; `claim <slug>` reads it from stdin like `consult -`.

## Acceptance
- [x] `tezgah-research claim <slug>` records one validated claim, exit 0.
      `tests/test_research.py` (`ClaimAppend`, 10 cases); the class is green on
      this tree and the CLI's own smoke agrees.
- [x] A claim that fails a rule is refused, exit 1, and the file is untouched.
      `tests/test_research.py` (falsification, provenance, a proof citing a path
      the line lacks, and a refused claim never creating the file).
- [x] Misuse exits 2: no slug, an unknown slug, stdin that is not one JSON object.
- [x] Concurrent appends all survive: 8 parallel processes, 8 parseable lines,
      every id present once.
- [x] A held lock refuses the write instead of writing unlocked, and names it.
- [x] `skills/research/SKILL.md` records claims through the command, with the
      reason a hand edit is not enough.
- [x] `python3 -m unittest discover -s tests` (711 tests, OK),
      `python3 -m compileall -q hooks hosts bin statusline.py` (ok), and
      `ruff check .` - which still reports the three pre-existing
      `benchmarks/arm-bench/analyze_e4[cd].py` / `analyze_e5.py` diagnostics and
      nothing in a file this plan changes.

## State
Implemented and verified on the branch. Two defects were found reviewing the
first drafts and fixed before the checks ran: a platform without `fcntl` reported
the refusal as another writer holding the file, and an append merged into a last
line that had no trailing newline - the one corruption this plan exists to
prevent. A third was fixed in the CLI: an `OSError` from the append (a line
directory that disappears, a read-only directory) printed a traceback instead of
a refusal.

## Next
The independent review of the diff, then merge. Open and deliberately not taken
here: `SITED` does not extract a bare filename, so a claim whose `proof` cites
one is never resolved (found by the enforcement audit, which also confirmed the
checker cannot see a note's evidence class or its content).
