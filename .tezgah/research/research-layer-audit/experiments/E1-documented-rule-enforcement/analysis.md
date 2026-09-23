# E1 analysis — the checker's reach, measured

Run 2026-09-20, protocol frozen beforehand, `run.py` sha256 `755239adddb6…750`.
Raw: `raw/run-1.txt` (confirmatory), `raw/run-2-replay.txt` (byte-identical
replay), `raw/control.txt`, `raw/meta.txt` (protocol mtime and size before the
run - the ordering proof git would give is the thing E2 shows is unavailable).

## Result

**Refusal proportion 0 / 8.** Every probe line that violated a rule
`skills/research/SKILL.md` states as enforced exited 0 with at most warnings.
The control refused **2 / 2**, so the harness reads the CLI's verdict and the
0/8 is the checker's reach, not a broken probe.

**CONFIRMATORY.** All eight probes matched their predicted verdict, and the
replay was byte-identical.

## What the 0/8 means

Not that the rules are absent - each is written in the contract - but that the
checker never opens the artifact that carries the rule. The reachable set is
structural: file presence, JSON parse, enum membership, findings-section
headings, and the protocol/results commit order. The unreached set is everything
that needs the *contents* of `state.json.evaluation`, `protocol.md`,
`results.jsonl`, `analysis.md`, `claims.jsonl[proof]` beyond
"does this path exist", `state.json.sessions`, and `literature/`.

The gap is one code shape repeated: `_check_state` reads three keys of
`state.json` (`question`, `phase`, `direction`) and ignores `evaluation` and
`sessions`; `_check_claims` calls `_resolves` (`hooks/tezgah_research.py:195-203`)
which is `os.path.exists`; `_check_experiments` checks that `results.jsonl`
exists and never opens it; nothing reads `literature/` at all.

## The two most consequential members of the gap

**P4/P6 - a claim's proof is prose with a path-shaped token or nothing.**
Measured over the five lines that already exist: of **75 claims, 24 (32%)** name
an artifact the line produced (`experiments/`, `literature/`, `to_human/`),
**36 (48%)** name only repository files outside the line, and **15 (20%)** name
no path-like token at all. All three shapes are accepted identically. This is the
fabricated-evidence hole the checker was built to close; it closes only the
narrowest form of it (a path that does not exist).

**P1/P3 - the locked evaluation and the results rows are never read.** The
contract calls the locked metric and baseline the thing that makes a later
criterion inadmissible, and says every result row carries its source. A line
passes with an empty metric, an unparseable `results.jsonl`, and an analysis with
no CONFIRMATORY/EXPLORATORY label.

## The one that costs the most in practice

E2's cells, not this one: the ordering rule is live only where the line is
git-tracked, and the contract's own prescribed location is gitignored here. So
the flagship rule of this layer has never fired once for any of the five real
lines.

## Method note, and an own goal

The frozen probe file carried a leftover cleanup line that deleted the per-user
temp directory's contents - the accident the protocol exists to catch, in the
probe rather than the probed. Contained (TMPDIR-based, home intact, verified) and
amended out before the confirmatory run, with the amendment recorded in
`protocol.md` as a pre-run change and a new hash. It is kept in the record
because a research line that hides its own mid-flight correction is the failure
the provenance tags were added for.

Rows here are scope: fixture (run.py: "Each probe builds the smallest line that violates exactly one rule" in a temp git repository).
