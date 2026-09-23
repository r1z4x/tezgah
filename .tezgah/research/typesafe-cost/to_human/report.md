# TypeSafe in tezgah: what this line established

Question: TypeSafe is unused in tezgah; where does it apply, why is it unused, and
what would it save in cost, tokens and speed. This is the reader's copy of the
line recorded in `../findings.md`, `../claims.jsonl` and `../log.md`.

## What was established

**The read side is the cost lever, and it is measured.** Driving the exact server
tezgah wires (`npx -y @playwright/mcp@0.0.81 --isolated --caps=testing,storage,network`,
52 tools) against an admin fixture served over http:

| Surface | chars | ~tokens |
|---|---|---|
| 40-row work-order table, nav and filter form (~120 controls) | 14,805 | ~3,701 |
| WO detail screen, 20 buttons | 1,138 | ~284 |
| two-screen flow (list read, click, detail read) | 15,943 | ~3,985, 1.4 s wall time |
| a real docs page (`docs.typesafe.ai/primitives.md`) | 22,193 | ~5,548 |
| `about:blank` | 106 | ~26 |

Tokens are `chars / 4`, the convention the installer's own budget report uses.
The comparison that matters is not screen against screen but read against
decision: tezgah's own rules are regex and ledger arithmetic, free and exact,
while one screen read costs about 3.7k tokens of the expensive model's context
and is re-prefilled on every later turn of the session.

**tezgah's own injected text, for the other side of the ledger** (the installer's
context budget): 7,545 chars always-on core and 8,019 chars of skill roster per
session, an 891-char subagent brief block, a 961-char reminder per turn, 5,053
chars of conditional rules on matching turns, and an 8.6k-token full contract
read on demand.

**The levers this line ranked** (`findings.md` section 4), highest value first:
skill routing over the always-on roster; the `analyze-app` loop, where a triage
decides what the expensive model never has to read; the component x state matrix
as one batched call; per-finding verification; `bin/tezgah-docs` page choice over
10 pages; and ai-research entry selection over 98 entries. The shared shape is
that the cheap judgment sits *before* the read, so the unselected part never
reaches the expensive model. Four places are named as off limits, the gate and
the consent path first, because those refusals must stay reproducible and they
sit on the hot path of every tool call.

**Why it is not used**, each with its evidence: no hook has a network client at
all (`grep -rlE "^import (urllib|http|socket|requests)" hooks/` returns nothing);
the credential is resolvable from the key file but not from a non-login shell,
and `have_typesafe_key()` (`hooks/tezgah_paths.py:213`) only checks that omp can
resolve one; the `typesafe-ai` skill ships in the roster but nothing arms or
routes to it; and nothing measures where a session's tokens actually go.

**Two live measurements changed the conclusion mid-flight.** A first triage shape
(`tezgah-triage --select`, one question per snapshot line, 0.5 threshold) on a
356-line screen selected 26.4% of its lines but recalled only 58 of 83
load-bearing controls, 69.9%: prediction P1's 95% floor is refuted, and the same
jaggedness appears between identical sibling controls. A four-arm prompt
experiment over 28 labelled prompts then measured the compact roster as *worse*
(1/20 and 2/20 wrong loads against 0/20 for the full roster, no discordant pair
favouring compaction), so the ~1,516 tokens the compaction would save are not
taken.

## What this does not show

- **No TypeSafe cost saving was ever observed against a baseline.** The six
  surfaces are ranked by reasoning from vendor figures and measured read costs,
  not by a run: no triage, state-matrix pass, finding-verification call, page
  choice or skill-suggestion call was benchmarked against the manual path it
  would replace. The line does not establish that any of them pays on this repo.
- **The line holds no `experiments/` and no `literature/` directory.** Every
  claim's proof token points at `findings.md`, so the numbers above are
  paragraphs rather than artifacts a reader can re-open; the vendor's $0.042/1M
  economics, the 12.2x batching result and the 16.8% -> 7.3% skill-suggestion
  figure were read from live docs and are quoted, not stored.
- **It did not measure the agent's read costs as a series.** The line's own runs
  are one-off figures with no baseline to compare against and no variance; what
  changed since is that the ledger now carries one `judge` cost row per
  judgement (`hooks/tezgah_integrity.py` counts it by row kind, and both the
  shell caller and the prompt-path caller write one), so the next round has a
  series to read where this line had only single runs.
- **The read-cost numbers are single runs on single fixtures.** Each row of the
  table is one snapshot, with no repeats and no spread, and the tokens are
  derived as `chars / 4`; the `about:blank` baseline bounds the instrument, not
  the sampling. The ratios in `findings.md` section 2 rest on agent-model list
  prices the line marks as an inference it did not read, and they are given
  there as ranges (roughly 70x and 350x) rather than as measured multipliers.
- **P1-P4 are not a programme that was run.** P1 is refuted, P2's saving is
  measured and refused, and P3 and P4 were never run; `findings.md`'s Open
  questions now say exactly that, with the reason (a missing protocol and a
  missing labelled sample, not a missing credential), so the predictions carry
  no result for the batched state matrix or for per-finding verification.
- **The vendor's skill-suggestion result was not reproduced here.** On this
  13-skill roster the independent chooser was already at 0/20 wrong loads, so
  the arm had no headroom; the 16.8% -> 7.3% figure came from a 182-skill roster
  with a different agent and does not transfer as measured.
- **The two decisions are answered in the tree, not by this line.** Which
  credential path tezgah adopts (`TYPESAFE_API_KEY`, then tezgah's own key file,
  then the OpenRouter fallback) and that the seam stays on-demand with no gate
  and no always-on paragraph are now properties of `hooks/tezgah_judge.py`; the
  line recorded the options and the recommendation, and the build chose.

## What the tree has since built, refused, or left open (2026-09-22)

Read this alongside the ranking in `../findings.md` section 4: the order there
was written before P1 and the compaction arms ran, and the tree moved under it.

- **Built.** The seam itself (`hooks/tezgah_judge.py`: one batched call, one
  credential, `judge-off` plus a per-caller switch, an OpenRouter fallback), and
  five of the six ranked surfaces as its callers - the snapshot triage
  (`bin/tezgah-triage`, rank 2), the state matrix (`tezgah-triage --states`,
  rank 3), the docs page Choice (`bin/tezgah-docs`, rank 5, measured at 37 of 39
  queries right), and the prompt-time skill suggestion
  (`hooks/tezgah_skill_pick.py`, rank 1, opt-in behind `skill-suggest-on`).
- **Refused.** The roster compaction - the measured arm was worse (1/20 and 2/20
  wrong loads against 0/20), so the ~1,516 tokens are not taken, and the
  always-on roster is now *larger* than this line measured: 9,168 chars over 14
  skills against 8,019 chars over 13. The gate, the shortcut parser, the Stop
  rule and the consent path still carry no model call.
- **Open.** Rank 4, per-finding verification: unbuilt and unmeasured, and still
  the largest unmeasured prize. Rank 6, the 98-entry ai-research router: measured
  in `.tezgah/research/judge-positioning` (flat Choice 14 of 14, 4 of 4 refused)
  and not built. P3 and P4 were never run, and what they lack is a protocol and a
  labelled sample rather than a credential.
