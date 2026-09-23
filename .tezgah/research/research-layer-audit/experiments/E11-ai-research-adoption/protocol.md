# E11 protocol — is the vendored ai-research library used, and what does it cost?

**Ordering disclosed.** A delegated read-only audit (its brief issued verbatim
before it ran) produced these numbers; the parent persisted them because a
read-only agent cannot write. No prediction is claimed for a measurement that was
commissioned as a question.

## Question

Two halves of the user's question: does the 98-entry vendored library get used at
full capacity, and does it create complexity?

## Instruments, and what each can see

1. **The harness ledger** (`~/.cache/tezgah/evidence/*.jsonl`): 30,750 rows,
   1,546 files. It records `run`, `edit`, `snapshot`, `verify*`, `claim`, `deny`
   and similar rows - **not a host file read**, so silence in it is weak evidence
   for "nobody read an entry" and must be said rather than glossed. What it can
   see decisively is a shell command that reads a path.
2. **The repository's own research lines** under `.tezgah/research/*/`: whether any
   line cites a library entry in `literature/`, `claims.jsonl`, `findings.md` or
   `log.md`.
3. **The router and the tests**: what is injected for the library and what is
   mechanically verified about it (the manifest, the importer) versus what is not
   (adoption).

## Metric

- ledger rows that read a vendored entry body, versus rows that read the same
  material from the upstream clone;
- research lines citing an entry;
- the always-on and per-prompt byte cost of the library;
- tests guarding the tree, split into integrity and adoption.

## What would falsify

- Ten or more rows reading entry bodies: the "essentially unused" reading fails.
- A line citing an entry as evidence: adoption exists where it counts.
- The router cost being the bucket's count line (as one comment claimed): the
  measured rendered file decides, and it decides for the code.
