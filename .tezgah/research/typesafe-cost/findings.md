# TypeSafe (Jev) in tezgah: where it is, where it could be, what it would save

Question: the user observes TypeSafe is unused in tezgah, asks for a
comprehensive audit of the skills and the app-analysis surface, and names the
goal - cut cost, cut tokens, gain speed. Everything below is either a measured
number from this session or a quoted figure from the vendor's own documentation;
nothing is estimated without saying so.

## 1. What was measured

### 1a. The read side - what an app analysis costs today

Measured with the exact server tezgah wires
(`npx -y @playwright/mcp@0.0.81 --isolated --caps=testing,storage,network`,
52 tools), driving a fixture admin screen served over http, plus one real
public page. Tokens are `chars / 4`, the same convention the installer's own
budget report uses. Every row is one snapshot of one fixture (n=1) with no
repeat and no spread, so the numbers bound the instrument - what one screen of
this class costs - rather than sample it.

| Surface | `browser_snapshot` | tokens | notes |
|---|---|---|---|
| 40-row work-order table, 5 columns, nav + filter form (~120 controls) | 14,805 chars | ~3,701 | the ordinary case: one screen of a real admin app |
| WO detail screen, 20 buttons | 1,138 chars | ~284 | a small screen costs little |
| two-screen flow (list read, click, detail read) | 15,943 chars | ~3,985 | 1.4 s wall time - speed is not the bottleneck, context is |
| `https://docs.typesafe.ai/primitives.md` (a real docs page) | 22,193 chars | ~5,548 | a content page, for the upper bracket |
| `about:blank` | 106 chars | ~26 | baseline |

One snapshot lands in the expensive model's context and is re-prefilled on
every later turn of that session; an eight-step flow is roughly 20-30k tokens of
tree before any finding is written.

### 1b. The injected side - what tezgah costs per session

From `bin/tezgah-setup --install` its own context budget (measured, 2026-09-20):

| Block | chars | ~tokens | cadence |
|---|---|---|---|
| always-on core | 7,545 | 1.9k | per session |
| skill metadata (13 skills) | 8,019 | 2.0k | per session |
| subagent briefs (5) | 891 | 0.2k | per session |
| per-turn reminder | 961 | 0.24k | every user turn |
| conditional rules | 5,053 | 1.3k | turns whose prompt matches a task class |
| full contract | - | 8.6k | only when `tezgah-contract` is read |

Supporting inventory: `docs/index.json` is 6,246 bytes over 10 pages (1,894
chars of titles + answers); `agents/*.md` totals 8,044 bytes; the ai-research
library carries 98 entries behind one hand-written entry point; `skills/` holds
13 skills whose roster descriptions total 8,139 chars.

### 1c. The vendor's own economics (primary source, quoted)

- Price: `PRICE = (0.042, 0.00)  # $ per 1M tokens (input, output); TypeSafe
  jev-1.12 as of 2026-09` - `docs.typesafe.ai/cookbooks/parallel_questions.md`.
- Batching: "batching every question into one TypeSafe call is **12.2x cheaper
  and 10.0x faster** with no change in answers" (13 questions over a 54k-char
  document, 5 repeats each way, std dev identical).
- Skill suggestion: over 488 requests against `claude-haiku-4-5`, wrong skill
  loads **16.8% -> 7.3%** and needless loads **9.8% -> 4.0%** - out of a
  182-skill roster, with the winner's name going into *one line* of the system
  prompt.
- Re-ranking: top-1 accuracy **5% -> 18%**, top-10 **38% -> 62%** over
  30-passage shortlists.
- Line-by-line search: "score **218 line ids** against a plain-language query
  with a Choice question" in one request.
- Cascade: "most of the quality of a big reasoning model at a fraction of the
  cost" (`sde_cascade`).

## 2. The arithmetic

One measured admin screen (3,701 tokens) pushed through the expensive model
versus through TypeSafe:

| Path | Price per 1M input | Cost for that screen |
|---|---|---|
| TypeSafe jev-1.12 (quoted) | $0.042 | $0.00016 |
| a Sonnet-class agent model [INFERENCE list price] | ~$3 | $0.0111 (roughly 70x) |
| a reasoning-class model [INFERENCE list price] | ~$15 | $0.0555 (roughly 350x) |

Prices for the agent models are the well-known list prices [INFERENCE, not read
this session]; the TypeSafe price is quoted from its cookbook. The saving is
not "the agent never reads the tree" - it is that the *unselected* part never
reaches the expensive model, and that a judgment which today costs a whole
agent turn costs a fraction of a cent instead.

## 3. Why it is not used - five causes, each evidenced

1. **No model-calling layer exists.** `grep -rlE "^import
   (urllib|http|socket|requests)" hooks/` returns nothing: every hook is pure
   stdlib, offline, deterministic. A TypeSafe call would be the first network
   dependency on that path, and the suite is hermetic (TempHome, no network) by
   design.
2. **The credential is unreachable.** `have_typesafe_key()`
   (`hooks/tezgah_paths.py:213`) only *checks* that omp can resolve one. This
   session: store row present, `TYPESAFE_API_KEY` empty. The key lives in
   omp's private store (`~/.omp/agent/agent.db`, `auth_credentials.data`), and
   the helper's own docstring says `~/.config/typesafe/key` "is tezgah's own
   key-file convention, not a path omp opens". So no hook could call TypeSafe
   today even if it wanted to.
3. **The skill ships unarmed.** `typesafe-ai` is one of the 13 skills, but no
   `PROMPT_HINTS` pattern arms it and nothing routes to it: it fires only if the
   model picks it off the roster. The skill's own framing ("Build AI-powered
   software with TypeSafe") points at apps being *built*, not at tezgah
   *using* it - so nothing in the harness points it inward.
4. **Nothing measures where a session's tokens go.** tezgah measures its own
   injected text (the installer prints it) but not the agent's reads. The
   earlier work on this axis was about analysis *quality*; cost was never a
   stated metric, so no gap was visible.
5. **Determinism is a deliberate property.** The gate, the shortcut parser, the
   Stop rule and the consent path are invariants the tests pin
   (`hooks/tezgah_gate.py`, `hooks/tezgah_integrity.py`); a model call in any of
   them would make "the gate refuses X" non-reproducible, and it would add a
   network round-trip to the hottest path in the system (every tool call).

## 4. Where it pays, ranked

| # | Surface in tezgah | The judgment | Why it pays |
|---|---|---|---|
| 1 | skill routing (`hooks/tezgah_context.py` roster, 2.0k tok/session) | Choice over 13 skills + Noul "does this turn need one" | TypeSafe's own measured case (16.8% -> 7.3%); deletes most of the roster from the always-on text |
| 2 | the `analyze-app` loop (3,701 tok per screen, measured) | score the flattened tree line-by-line, read back only the selected refs | line-by-line search does 218 ids in one request; the unselected 80-90% never reaches the expensive model |
| 3 | the product-analysis state matrix (component x state, added 2026-09-20) | one batched call: per-component state coverage, severity, failure vs judgement | makes full-screen coverage affordable instead of three eyeballed components; batching is 12.2x cheaper than one call per question |
| 4 | product-analysis finding verification | Noul/Choice per finding: "does the cited evidence support this claim?", confidence routing the doubtful ones to the agent | the citation-check cookbook's exact shape; replaces an agent turn per finding |
| 5 | `bin/tezgah-docs <words>` over 10 pages (1,894 chars) | Choice: which page answers this | substring matching sends the agent to a wrong page of 1-3k tokens; the choice costs ~nothing |
| 6 | ai-research entry (98 entries) | hierarchical classification | "read one entry, never the tree" is currently a rule the model must obey by reading |

**Re-ranked after the measurements (2026-09-22).** The order above was written
before P1 and the compaction arms ran, and the tree moved under it. Rank 1 (skill
routing) is now built and had no headroom on this roster, so it does not rank first
on benefit; rank 2's per-line shape is refuted and the shipped unit shape reads 94%
of the screen, so "read back only the selected refs" is bounded by the screen's own
structure (a 76% floor, not a tuning failure); rank 3 is built as
`tezgah-triage --states`; rank 5's page Choice is built and measured at 37 of 39
queries right (`bin/tezgah-docs`); rank 6 is measured in
`.tezgah/research/judge-positioning` (a flat Choice over 98 entries, 14 of 14) and
not built; rank 4, per-finding verification, is the one surface still unbuilt and
unmeasured, and it is the largest unmeasured prize. What the re-ranking changes is
the order of the *remaining* work, not the finding that a cheap judgement before a
read is where the money is.

## 5. Where it must not go

- The gate's refusals, the shortcut parser, the Stop rule and consent: refusal
  reproducibility is an invariant with tests behind it; a probabilistic answer
  there is a policy bug, not an optimisation.
- The PreToolUse hot path generally: a network round-trip per tool call would
  add latency to the fastest path in the system.
- Anywhere the current mechanism is already free and exact (regex classification
  of a command, hashing a file, counting a ledger).

## 6. Open decisions (the analysis cannot settle these)

1. **Credential path.** The key is in omp's private store and not in the env.
   Options: (a) export `TYPESAFE_API_KEY` in the profile - what the SDK, the
   docs and omp all read, and the only route that needs no new code; (b) tezgah
   reads omp's store - rejected, it is another tool's private credential blob;
   (c) a tezgah-owned key file + reader - a second key to rotate, but keeps
   tezgah independent of omp.
2. **The offline invariant.** Whether hooks may become network-dependent at all,
   and if so on which paths only (recommendation: on-demand actions only -
   `tezgah-docs`, the app-analysis loop, a prompt-time skill suggestion - with a
   no-key fallback to today's deterministic behaviour, and never in the gate).

## 7. Untested predictions

Written before any TypeSafe call exists in this repo, each with the check that
would falsify it.

| # | Prediction | Falsified by |
|---|---|---|
| P1 | a TypeSafe tree triage keeps >=95% of the load-bearing controls while the agent reads <=30% of the tree lines | recall < 95%, or the agent still reading >30% on the measured fixture screens |
| P2 | a prompt-time skill suggestion removes >=1.5k tokens per session of roster text without increasing wrong skill loads | wrong loads rise, or the roster cannot be shrunk without breaking the opencode router path |
| P3 | the batched state-matrix pass costs < $0.01 per screen and covers every control the manual pass covered | cost per screen above $0.01, or any control the manual pass found is missed |
| P4 | per-finding verification via one batched TypeSafe call agrees with the agent's own verdicts on >=90% of findings | agreement below 90% on a replay of the Ustam artifact |

## What we know

- tezgah's hook layer has no model-calling code path. The only TypeSafe code in the
  tree is `have_typesafe_key()` (`hooks/tezgah_paths.py`), a health row that reports
  whether *omp* can resolve a credential; no hook, bin tool or host adapter calls
  TypeSafe.
- The credential exists and is resolvable, but not from a non-login shell: the key
  file is 108 bytes at mode 0600, `~/.zshenv` exports it, an interactive zsh sees it
  (length 107) and this session's non-login shell does not.
- Measured read cost of an app analysis with the pinned Playwright MCP: a 40-row
  admin screen `browser_snapshot` is 14,805 chars (~3,701 tokens); a two-screen flow
  15,943 chars (~3,985) in 1.4 s; a real docs page 22,193 chars (~5,548).
- Measured always-on text tezgah injects: core 7,545 chars (~1.9k tokens) and the
  13-skill roster 8,019 chars (~2.0k) per session, a 961-char reminder per turn,
  5,053 chars of conditional rules on matching turns, and an 8.6k-token on-demand
  full contract.
- TypeSafe's published economics: $0.042 per 1M input tokens and $0 output
  (jev-1.12, 2026-09); batching 13 questions into one call is 12.2x cheaper and
  10.0x faster with identical answers; the skill-suggestion cookbook over 488
  requests moved wrong skill loads 16.8% -> 7.3% and needless loads 9.8% -> 4.0%.

## Patterns

- The cost lives in what the agent reads, not in tezgah's own decisions: the rules are regex and ledger arithmetic, which are free and exact, while a single screen read costs about 3.7k tokens of the expensive model's context and is re-prefilled on every later turn ([C1], [C3]).
- The cheapest place to put a judgment is before the read, not after it: a batched cheap judgment over candidates can decide what the expensive model never has to see, which is the shape all six candidate surfaces share ([C4], [C5]).
- Determinism is load-bearing exactly where a refusal is: the gate, the shortcut parser, the Stop rule and consent are pinned by tests because their refusals must be reproducible and they sit on the hot path of every tool call ([C1]).

## Lessons

- A fixture measured through `file://` returned the same 106 chars as `about:blank`,
  so the first numbers were a silent zero rather than a reading; serving the same
  fixture over http gave the real ones. A blank-looking measurement is a fixture bug
  before it is a finding.
- A credential can be present and still unreachable: the store row and the env var
  answer different questions, and only the env var (or the file behind it) is usable
  by a process that this shell did not source.

## Open questions

- Which credential path tezgah should standardise on: the exported env var, or its
  own key file read directly (the file fallback is what makes hooks work at all,
  since they run in non-login shells).
- Whether any hook may become network-dependent, and on which paths only.
- Whether the remaining predictions hold: P1 is measured and refuted (the per-line
  shape recalled 69.9% of the controls, and the shipped unit shape recalls 100% of
  them but reads 94% of the screen), P2's saving is measured and refused, and P3 and
  P4 were never run. A key-resolved TypeSafe call now exists
  (`hooks/tezgah_judge.py`), so P3 and P4 stay unrun for want of a protocol and a
  labelled sample, not for want of a key.

- MEASURED (2026-09-20, live): `tezgah-triage --select` on a real 356-line / 13,045-char
  admin screen selected 94 lines (26.4%), skipped 262 lines / 9,149 chars, and cost
  13,559 input tokens, 6,304 output, 1,734 ms, $0.000569. Recall of the screen's
  load-bearing interactive controls (83 button/searchbox/combobox lines) was 58 of 83
  = 69.9%: prediction P1's 95% floor is REFUTED. Identical sibling controls scored on
  both sides of the 0.5 threshold (Sil 0.92 next to Sil 0.61, and 25 buttons under
  0.5), so the noise is in the per-line question shape, not only in the threshold -
  the same jaggedness the vendor documents for jev-1.13.

- MEASURED, AND THE COMPACTION WAS REFUSED (2026-09-20). A labelled set of 28 prompts
  (20 covered by exactly one skill, 8 covered by none) was run through four arms on an
  independent chooser (`consult --provider deepseek --models deepseek-flash
  --no-referee`, 0 of 88 cells changed between two runs, so a single-cell difference is
  noise) with TypeSafe as a biased secondary. Wrong-load: full roster 0/20, full+line
  0/20, compact 1/20, compact+line 2/20; needless-load 0/8 in every arm. No discordant
  pair anywhere favoured the compact roster (5/5 and 6/6 favour the full one; two-sided
  sign test p=0.0625 and p=0.031). The saving the compaction would buy is exactly the
  6,063 characters / ~1,516 tokens claimed, and it is not taken: the quality cost is
  measured and one-directional. Cost of the experiment: $0.0504 ($0.0422 consult
  estimated from characters, $0.0082 TypeSafe measured over 200 calls).
- The skill-suggestion line's benefit on THIS roster is unproven: the independent
  chooser was already at 0/20 wrong without it, so the arm has no headroom to improve,
  and the TypeSafe arm's difference (1/20 -> 2/20) sits inside jev's own 10%
  self-disagreement. The line costs 305-325 characters (~78 tokens) per fresh prompt
  plus $0.000038 and ~0.8 s; the vendor's 16.8% -> 7.3% was measured on a 182-skill
  roster with a different agent.

## Closure (2026-09-22): what the tree has since built, refused, or left open

The line concluded on 2026-09-20. The tree moved under it, so this section says
what each part of it looks like on the tree of 2026-09-22 (HEAD `ddf72b4`) and
supersedes the claims the movement invalidates.

**Built, and not by this line.** `hooks/tezgah_judge.py` is the judgement seam:
one batched `ask()`, one credential, one redirect guard, `judge-off` plus a
per-caller switch, and an OpenRouter fallback provider for a machine with no Jev
key. Its three callers are the surfaces this line ranked: `bin/tezgah-triage`
(rank 2's triage, and rank 3's state matrix as `--states`), `bin/tezgah-docs`
(rank 5's page Choice, measured at 37 of 39 queries right), and
`hooks/tezgah_skill_pick.py` (rank 1's prompt-time skill suggestion). Rank 6, the
200-entry ai-research router, is measured in `.tezgah/research/judge-positioning`
(a flat Choice over 98 entries answered 14 of 14 and refused 4 of 4) and is not
built. Rank 4, per-finding verification, is unbuilt and unmeasured. The seam's
price is pinned in the tree at `PRICE_PER_MILLION` (`bin/tezgah-triage`), which is
$0.042 per 1M input tokens - the same figure `findings.md` above quotes from the
vendor's cookbook.

**Refused, with the measurement behind the refusal.** The roster compaction is
refused: the four-arm experiment measured the compact arm at 1/20 and 2/20 wrong
loads against 0/20 for the full roster, so the ~1,516 tokens are not taken, and
the always-on roster is *larger* today than when the line measured it - 9,168
chars over 14 skills, against 8,019 chars over 13 skills on 2026-09-20, measured
this session through `bin/tezgah-setup`'s own `context_budget()`. The skill
suggestion ships opt-in (`skill-suggest-on`) rather than armed, which is the
honest shape for a surface whose benefit this roster could not show. The gate, the
shortcut parser, the Stop rule and the consent path are still untouched by any
model call.

**Open, and why.** Per-finding verification (rank 4) has no protocol and no
labelled sample. P3 (the batched state-matrix cost) and P4 (per-finding agreement)
were never run; the key they were waiting for now resolves, so what they lack is a
protocol, not a credential. The two decisions the line left to the user are
answered in code rather than by a choice: tezgah reads its own key file (env var
first) and falls back to OpenRouter, and the seam is on-demand - no gate, no
always-on paragraph.

**Claims superseded here.** `C1` (no code path calls TypeSafe) is refuted by
`hooks/tezgah_judge.py` (`C1-seam-exists`); `C4` (the vendor economics) is
re-recorded as a quoted secondary the line cannot re-open (`C4-secondary-economics`),
and the file that moved it is `hooks/tezgah_judge.py`, which ships the second
provider and reads its own credential; `C5`/`C5-R` (the skill suggestion as the
highest-value first surface) is weakened by the build plus the no-headroom
measurement, and the file that moved it is `hooks/tezgah_skill_pick.py`
(`C5-picker-built`); `C6` (95% recall at 30% read) is refuted in its read half by
the shipped unit shape in `bin/tezgah-triage` - 100% of the 83 control lines at a
94% read, floored at 76% by the screen's own structure (`C6-unit-shape`). `C6-R`
(the per-line shape at 69.9%) and `C7` (the compaction refusal) stand as written.
