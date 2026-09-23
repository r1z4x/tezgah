# The mattpocock/skills pack against tezgah: what was measured

A research line's report. Every number below is a row in this directory's
`experiments/*/results*.jsonl`; every claim is in `claims.jsonl` with its
falsification criterion. What the evidence does **not** show is its own section,
and it is not a formality.

## The question

What does adopting `github.com/mattpocock/skills` (@ `c55ee46073`, 38 `SKILL.md`,
266844 stars, MIT) cost tezgah — in always-on context, in router-line
extractability, and in test/gate conflicts — and which of its mechanisms, if any,
earn an arm-bench effect block?

## What we know

**1. The pack is cheap in bytes and expensive in router reach.** Its 38
descriptions cost **6180 B** by the installer's own metadata formula against
**9000 B** for tezgah's 14 shipped skills — 0.69×, the opposite of what this line
predicted. The reason is measured: tezgah's descriptions average **624.1**
characters (max 961, `feature-audit`), the pack's **142.0** (max 421,
`code-review`). What the pack loses is at the router: tezgah's extractor returns a
line with no trigger sentence for **22 of the 38** bodies (all 22 user-invoked,
all 16 model-invoked ones keep theirs), against **14 of 14** for the shipped
control. Nine of the 22 return 100+ characters, so it is the sentence, not the
length.

**2. The same failure is already installed.** 19 of the 114 `SKILL.md` under
tezgah's own `skills/` return a non-trigger line — inside the vendored
`ai-research` bucket, which the router collapses to a count line.

**3. Two of the three candidate conflicts are packaging, not bodies.** The float
`tests/test_skills.py:92` rejects appears in **0 of 38** bodies and **1 of 66**
markdown files under `skills/`; a grafted body carrying it fails exactly one test
(`test_no_floating_npx_tag_and_the_fallback_names_the_wired_pins`) while the same
graft without it fails none.

**4. One conflict is a hole nobody enforces.** The pack's `triage` requires every
comment it posts to open with a generated-by-AI line
(`skills/engineering/triage/SKILL.md:15-17`); tezgah's contract bans AI
attribution on any host; and `hooks/tezgah_gate.py`'s `attribution()` returns
**false** for that line on both `gh issue comment` and `gh issue create`, while
denying the `Co-Authored-By` control in the same run. `gh issue comment` is a
write command the rule reads; the anchor set simply holds "generated **with**",
not "generated **by** AI". An adopted `triage` would publish attributed comments
with every gate green.

**5. The one mechanism measurably absent is the provoke-the-failure rule.** Asked
whether the always-on text asks the agent to make a check fail once on purpose so
the check is proved to discriminate, the judge seam returns **P(yes) 0.04** while
its two controls return **0.99** (prohibitions) and **0.98** (verification); the
marker probe agrees at **0 hits** over 49344 bytes. The text carries 17
prohibition markers, 51 verification markers and 9 positive-target ones, and 4 of
the 14 descriptions already carry an explicit non-trigger.

**6. The craft reference is affordable.** `writing-for-agents` plus
`SKILL-MECHANICS.md` is **13515 B**, 0.38× CONTRACT.

## The H4 round — the clause was run, and it moved nothing

The clause — *prove the check before you trust it* — is the one mechanism this
line's measurements found absent (judge P(yes) 0.04, zero marker hits). It took
three rounds to get a number for it, and the first two failed for two different
infrastructure reasons:

- **Round 1** (`72ff46bc`, $0.77): the treatment arm never armed — `orx exp run`
  executes in a copy of the node's tree and the deployed arm lived only in the
  session's worktree (C11). The two arms that did run left one readable comparison:
  of the runs whose hidden checks failed, the share whose final message claims
  completion is **2 of the armed control's 95 = 0.021** against the bare anchor's
  **19 of 75 = 0.253**, and excluding timeouts **2 of 46 = 0.043** against
  **19 of 69 = 0.275**, where the armed numerator rests on the 5 of its 46
  non-timeout failures that wrote any final message at all (41 wrote none).
  **C12c** supersedes the row as first folded: that row said 3, 0.032 and 0.065,
  and none of the three reproduces from the run's own rows under the predicate
  pinned at the time or the one in the tree today — re-folded on 2026-09-22 from
  the run's rows under
  `~/.local/share/openresearch/local-runs/72ff46bc-4245-4e65-9d17-4c7f9ba243f8/repo/benchmarks/arm-bench/results/orx/nogit/`,
  which is outside this line and named here so a reader can re-fold it. Read it as
  a direction and not a rate: the armed arm's failure population is 46 runs, 41 of
  which wrote nothing, so the two failure populations are not comparable (C11,
  C12c).
- **Round 2** (`e868c63e`, $0.00): the packaging was fixed and verified, the
  treatment armed, and then every call was refused with `errorStatus` 402 — an
  unfunded OpenRouter account (C13).
- **Round 3** (`3eb8b9f8`, **$1.0997**, 300 rows, all usable): the route changed to
  `deepseek/deepseek-flash`, disclosed in the protocol as an instrument change.

| arm | runs | pass | pass% (Wilson) | timeouts | cost | cost/pass | Stop-rule refusals |
|---|---|---|---|---|---|---|---|
| `omp+tezgah` (armed control) | 100 | 89 | 89.0 (81.4-93.7) | 10 | $0.4498 | $0.00505 | 74 |
| `omp-bare` (anchor) | 100 | 93 | 93.0 (86.3-96.6) | 0 | $0.2788 | $0.00300 | 0 |
| `orx-mp-prove` (treatment) | 100 | 94 | 94.0 (87.5-97.2) | 5 | $0.3711 | $0.00395 | 74 |

**The clause changed nothing this instrument can see.** Its false-completion share
tied with the armed control's (both 1.000 — the protocol's P2 falsified by its own
wording), on denominators of **one** labelled failed run each: six of the
treatment's six failed runs and ten of the control's eleven wrote no final message,
so that column measures the capture, not the behaviour. Its pass rate is not below
the control's (94.0% against 89.0%, P3 confirmed, intervals overlapping), and both
armed arms fired the Stop rule exactly 74 times — the place a clause about proving
a check would show up first.

Round 3's absolute numbers live in their own space (the anchor passed 93 of 100 here
against 25 of 100 in round 1, median 17-51 s against 267.7 s); what it answers is the
within-run contrast, which is what the question needed.

## What the evidence does not show

- **The one mechanism this line found absent was measured and moved nothing** (C15): at two tasks and one model route the corpus cannot price it, and the false-completion column cannot separate the arms at a label rate of 1 in 11.
- **Nothing here shows adoption would help tezgah.** The pack's own value claim
  (that its skills make agents better) has no measurement behind it in its
  repository — no eval, no counter-metric, one release workflow that only versions
  and tags. This line did not measure it either.
- **The byte figures are the installer's cost model, not a live window.** They
  count description bytes as if all were always-on; only opencode gets a generated
  router, every other host lists `name` + `description` itself. No token count was
  taken.
- **The judge's 0.04 is a model's reading of one state**, not a proof of absence. A
  rule phrased differently would also score near zero while being present; the
  marker probe shares that limit. Two instruments agreeing is the strongest form
  this evidence takes, and it is still a reading.
- **The attribution-anchor hole is an open user decision, and this line did not
  close it.** C04 shows `attribution()` returns false for the pack's mandated
  "generated by AI" line while denying the `Co-Authored-By` control, because the
  anchor set (`hooks/tezgah_gate.py:151`) holds "generated **with**" and not
  "generated **by**". What to do about it is the user's to call and it is open:
  (a) widen the anchor set, which refuses the pack's mandated line repo-wide and is
  a behaviour change to a shipped gate; (b) leave it, and treat an adopted `triage`
  as text a human must edit; or (c) refuse the pack's `triage` skill outright. The
  line took none of the three: widening a gate is a policy change, not a research
  step, and no measurement here decides it. Recorded in `log.md` as well.
- **The conflict battery ran `tests/test_skills.py` only**, on a clone at HEAD, so
  a second test failing on a grafted candidate elsewhere in the suite is not
  excluded; `attribution()` was read alone, not its sibling rules.
- **`C03` as filed is superseded by `C03c`.** The original row's proof named
  `results.jsonl` for counts the scope partition had moved into
  `results-fixture.jsonl`, and it listed `tests/test_skills.py:91-98` as a receipt
  for a line number rather than for content. `C03c` states the same finding over
  the artifact the counts live in, and the counts were re-read on 2026-09-22 over
  the pinned clone (`/tmp/mp-skills/skills` at `c55ee46`) with the instrument's own
  corpus definitions: 38 bodies with 0 hits, 66 markdown files with 1
  (`skills/in-progress/README.md`), the tezgah control's 114 bodies with 0. The
  checker's warning on `C03` remains, because the rule reads every row and a row
  cannot be repaired in place — the line's only write is an append.
- **The fixture-scoped claims are about a clone, not about the running system**:
  C01, C02, C03c, C05, C06b are `fixture`-scoped (C03 as filed is superseded);
  C04, C07, C08, C09, C10 are `real`, and the H4 block's rows are `derived`.
- **The line's anchors point outside it.** `bin/tezgah-setup`, `hooks/tezgah_gate.py`,
  `hooks/tezgah_policy.py` and `tests/` are repository paths this directory does
  not hold; an auditor reading only this directory cannot check them.

## Independent audit

An adversarial read of all 27 files (a separate session, read-only) found ten
defects and one unsupported claim. Nine are fixed in `5dd139d`: the invocation
split is now a recorded row rather than a claim about rows, both wrong corpus
labels are corrected, E1's row count is 131 lines and not 154, every results
header carries the tree sha it was measured at, `findings.md` cites C06b and not
the superseded C06, and the cost arithmetic reads 300 × $0.0058 = $1.74. `C03`'s
proof path is the tenth: superseded by `C03c` on 2026-09-22 and still reported by
`check`, since a row cannot be repaired in place and the layer's only write is an
append. A second adversarial read found the false-completion row's own arithmetic
(the recorded 3 against the 2 the rows carry) and that is settled by `C12c`.

## Where the artifacts are

| | |
|---|---|
| Line | `.tezgah/research/mp-skills-adoption/` on `main` |
| Review | `to_human/review.json` - **weak accept** (mean 4.33, `methodological_rigour` 3), four findings, all closed: two settled by superseding claims (`C03c`, `C12c`), none left open |
| Check | `python3 bin/tezgah-research check mp-skills-adoption` → `1 line(s) ok`, exit 0, with the warn class named below |
| Open | `check --strict` refuses the supersession warnings (`C03`/`C03b`/`C06b`/`C12`/`C12b` each superseded, and each old row still readable on its own) - honest state, not something an append can clear |

## Closing pass (2026-09-22)

The line is concluded. What this pass settled and how:

- **C03's stale proof path** — settled by appending `C03c` through the CLI, over
  `results-fixture.jsonl` and the analysis where the counts actually live, and
  re-read the counts over the pinned clone: 38 bodies / 0 hits, 66 markdown files /
  1 hit, 114 control bodies / 0. The original row's warning is the layer's rule
  reading every row, not an unfixed defect.
- **C12's false-completion row** — settled by `C12c`: the run's own rows give 2 of
  95 (0.021) and 2 of 46 (0.043) for the armed control against 19 of 75 (0.253) and
  19 of 69 (0.275) for the anchor, where the row as first folded said 3, 0.032 and
  0.065. The two arms' failure populations differ too much for this to be a rate;
  the direction is what it supports.
- **The attribution-anchor hole** — recorded above as an open user decision with
  three options and no line-level action taken.
- **`E5-round2-clause/protocol.md` quotes the row as first folded** (0.032 against
  0.253). It is a pre-registered protocol and is not edited; the number it took as
  its input is the superseded one, and round 2 failed for a provider reason that no
  number in it depends on.

What stays open, and why:

- The attribution decision (above) - the user's, not a measurement.
- The corpus limit: two tasks at one model route cannot price a one-sentence clause
  (C14, C15), and the false-completion column's label rate is 1 failed run in 11.
- Adoption's value claim itself: nothing measured it - not the pack (no eval, no
  counter-metric) and not this line (C15).
- Whether a trigger-sentence rewrite would make the 22 fallback descriptions
  routable, or whether the router wants a per-skill exemption for user-invoked
  skills. This one is answerable with a rewrite and a re-run of E1's instrument, and
  it is not part of concluding.
