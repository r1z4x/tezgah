# E8 analysis — the same probes, after the change

Raw: `raw/run-post-fix.txt` (the final revision), `raw/run-before-second-fix.txt`
(the same run before the second defect was closed), `raw/exploratory-attribution.txt`
(the follow-ups that located it), `raw/meta.txt` (protocol mtime before the run).

## Result

**6 of 8 refused, and 8 of 8 predictions matched**, against E1's **0 of 8** on the
same probe bodies.

| probe | rule | pre-change (E1) | final | attribution |
|---|---|---|---|---|
| P1 | locked evaluation | not refused | **refused** | `state.json evaluation locks no metric, baseline, locked_at` |
| P2 | `protocol.md` content | not refused | not refused | **as predicted**: the spec added no content rule for the protocol |
| P3 | results rows carry a source | not refused | **refused** | `results.jsonl:1 does not parse` |
| P4 | a proof cites the evidence | not refused | **refused** | `claim C1 is an evidence claim and cites nothing the line produced` |
| P5 | evidence with actual results | not refused | not refused (warn) | measured through `check`: warns, and `--strict` FAILs |
| P6 | a path the line never produced | not refused | **refused** | `claim C1 is an evidence claim and cites nothing the line produced` |
| P7 | session provenance tags | not refused | **refused** | `sessions[1] records no date`; with a date present, the tag itself fires |
| P8 | citations verified | not refused | **refused** | `literature/ holds 1 note(s) and no INDEX.jsonl` |

Six of six refusals name the rule the probe was built for - P7 fired on the
missing date rather than the bad tag because its fixture carries both defects, and
the exploratory pass shows the tag rule firing on its own
(`sessions[1] tag 'user-typed-it' is not one of user, ai-suggested, ai-executed,
user-revised`). Attribution therefore holds for 6 of 6.

## The defect this experiment found, and its closing

The first post-change run was **5 of 8**: P6 failed, and it was a hole rather than
a probe artifact. An `evidence` claim whose proof named only a repository file the
line never produced was accepted by the write path **and** by the checker:

```
claim q with {"kind":"evidence", ..., "proof":"src/unrelated.py"}  -> exit 0, "claim C1 recorded"
check q                                                            -> exit 0, no line names C1
check --strict                                                     -> exit 1, but nothing about the claim
```

E1's P6 measured the same hole on the pre-change checker; the change had closed
the no-token case (P4) and left the repo-file case, because resolution still fell
back to the repository root. Reported with the reproduction and the rule shape
that closes it without breaking mixed proofs, fixed on both sides, and this
experiment was re-run: P6 now refuses, and the raw of both runs is kept
(`raw/run-before-second-fix.txt` beside `raw/run-post-fix.txt`) so the before and
after are both readable rather than only the good one.

The one remaining non-refusal besides P2 is a probe artifact, not a rule failure:

- **P5** - the probe reads `claim`'s exit code, and the write path is deliberately
  the lenient side of the pair (`check` is the judge). Measured through `check`,
  the rule fires: warn, and `--strict` FAILs with `claim C1 cites experiment E1,
  whose results.jsonl holds no row`.

That is recorded as an EXPLORATORY follow-up because the protocol's cells did not
anticipate it; it is not a second confirmatory run.

## What the pair of experiments establishes

Over the same eight rule bodies, the checker's refusal of a violating line went
from **0 of 8** to **6 of 8**, with byte-identical probe bodies apart from the two
changes the protocol names: the claim fixtures now carry the `kind` the write path
requires, and P1's fixture sets `phase: inner` so the evaluation rule is tested
rather than its bootstrap exemption. The two that remain are named: `protocol.md`
content has no rule (out of the spec's scope), and P5 is the warn class by design.
The three probes that read `claim`'s exit (P4, P5, P6) are the ones this audit
should have pointed at `check` from the start - the write path is the lenient
side, which is what the first defect's fix made explicit.


Rows here are scope: fixture (the same probe bodies as E1, each one building a temp git repository).
