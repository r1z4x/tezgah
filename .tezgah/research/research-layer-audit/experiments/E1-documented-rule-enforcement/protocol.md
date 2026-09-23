# E1 protocol — which documented rules does `tezgah-research check` actually enforce?

Frozen 2026-09-20T11:59:18+0300, before the confirmatory run below.

**Amendment, 2026-09-20, recorded before the confirmatory run.** The frozen file
sha256 `99d0403590c53242f0b8e78dc1ce1897ae7c0c68dd1928015c71c8f0014b718f` carried
a dead last line, `shutil.rmtree(os.path.dirname(tempfile.gettempdir()))`, left
over from the exploratory pass. On this machine `tempfile.gettempdir()` honours
`TMPDIR`, so the line deleted the per-user temp directory's contents - contained,
not harmless: it is exactly the accident this line's protocol exists to catch,
in the probe script rather than in the thing being probed. The line and the now
unused `import shutil` are removed; **no probe body changed**. Amended file
sha256 `755239adddb6e0b39790c740f5729dff51004b6ca051e8c101dbdae0e232f750`, and it
is this amended file the confirmatory run executes.

## Disclosure: one exploratory pass came first

A first pass of the same probe list ran before this file existed, to find out
which rules were worth probing at all. That pass is why the list has eight
members rather than the two originally guessed. The predictions below are
therefore **not** blind: they are derived from reading
`hooks/tezgah_research.py` (the checker) against `skills/research/SKILL.md` (the
contract) and are recorded here before the confirmatory run. The confirmatory run
uses the frozen `run.py` above, unmodified; if any probe's verdict differs from
the prediction, that is reported as a miss, not adjusted away.

## Question

`skills/research/SKILL.md` states what a research line must hold and what
`check` enforces. Which of those stated rules does the shipped `check` refuse a
line for violating?

## Locked evaluation

- **Metric**: refusal proportion over the frozen probe set -
  `probes the CLI refused / 8`. A probe is *refused* when the CLI exits non-zero
  and names the violated rule. Exit 0 with only warnings counts as **not
  refused**, because `check`'s exit code is what a hook or a person acts on.
- **Baseline**: the contract's own claim - every rule below is stated by
  `skills/research/SKILL.md` as one `check` enforces, so the documented baseline
  is `8 / 8`.
- **Threshold**: a probe counts as enforced only at 8/8. Anything less is a gap;
  the gap's size is the finding, not a pass/fail bit.

## Hypotheses

- **H1**: `check` enforces only structural presence and enum rules (file exists,
  JSON parses, phase/direction/status/provenance in range, findings sections
  present, protocol committed before results). Predicted
  **refusal proportion 0/8** - not because the rules are absent from the
  contract, but because the checker never opens the artifacts that carry them.
- **H2**: a claim's evidence binding is path existence only, so a prose proof and
  a proof naming any file in the repository both pass.
- **H3**: the protocol-order rule fires only for a line inside a git-tracked
  path. A line under a gitignored `.tezgah/` degrades to a warning, so the rule
  is unverifiable in exactly the layout the contract prescribes.

## Prediction table

| probe | documented rule (`skills/research/SKILL.md`) | predicted verdict |
|---|---|---|
| P1 | lock the metric and baseline before running anything (`evaluation` in state.json) | not refused |
| P2 | `protocol.md` states what changes, what it predicts, why, and what would falsify it | not refused |
| P3 | every result row carries its source; an analysis labels each outcome CONFIRMATORY or EXPLORATORY | not refused |
| P4 | a proof cites the evidence; fabricated evidence is refused | not refused |
| P5 | proof resolves to an experiment directory that actually has results | not refused |
| P6 | a proof naming a path the line never produced is the fabricated-evidence failure | not refused |
| P7 | session events are tagged `user`/`ai-suggested`/`ai-executed`/`user-revised` in `state.json.sessions` | not refused |
| P8 | never write a citation from memory; verify it against two of Semantic Scholar, CrossRef, arXiv, OpenAlex | not refused |

Predicted refusal proportion: **0/8**.

## What would falsify

- Any probe refused: the checker is wider than H1 says, and the gap list shrinks
  by that probe. The exact refusal text is recorded either way.
- The run not reproducing: the same frozen `run.py` on the same CLI giving a
  different verdict per probe across two runs falsifies the measurement, not the
  hypothesis.
- Control: a line that violates a rule the checker *is* known to enforce
  (protocol committed after results, claim without a falsification criterion)
  must exit non-zero. If the control does not refuse, the probe harness is not
  reading the CLI's verdict and the whole result is void.

## Out of scope

Whether the *rules themselves* are the right ones is a literature question and
belongs to the line's literature notes; this experiment only measures the
distance between the contract's text and the shipped checker.
