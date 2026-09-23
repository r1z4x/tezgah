# Findings

Question: `tezgah_judge` (the TypeSafe/Jev judgement seam) looks weak - what is it
today, where should it sit in this project's structure, and does the contract need
to name it?

Revision audited: HEAD `4bf25e8`, working tree at 2026-09-20 02:40. **Eight files
carry an uncommitted in-flight change** (`hooks/tezgah_policy.py`,
`hooks/tezgah_context.py`, `hooks/tezgah_paths.py`, `hooks/tezgah_skill_pick.py`,
`docs/contract.md`, `skills/tezgah-contract/SKILL.md`, `output-styles/tezgah.md`,
`tests/test_skill_pick.py`) that turns `skill-suggest-off` into an opt-in
`skill-suggest-on` arming marker. Line numbers below are the working tree's; a
citation that sits inside that change is marked **(in-flight)**. Everything else
was verified against a clean file, and `hooks/tezgah_judge.py`, `bin/tezgah-triage`
and `bin/tezgah-docs` are clean.

## What we know

### 1. The audit

**What the seam is.** `hooks/tezgah_judge.py`, 155 lines, stdlib only:

| part | line | what it does |
|---|---|---|
| module docstring | `hooks/tezgah_judge.py:1-30` | states the egress boundary, the two credential channels, and that `judge-off` is the off button |
| `URL`, `KEY_FILE`, `MODEL` | `:38-41` | one endpoint, one key path, **one hardcoded model** `jev-latest` |
| `_NoCrossHostRedirect` | `:44-59` | refuses a redirect that leaves the endpoint's host, so a `Location` cannot take the bearer |
| `OPENER` | `:62` | the module's one opener |
| `endpoint()` | `:65-67` | `TEZGAH_TYPESAFE_URL` repoints it (a test seam) |
| `key()` | `:70-83` | `TYPESAFE_API_KEY`, else `~/.config/typesafe/key`, else `None` |
| `available()` | `:86-88` | `bool(key()) and not tp.off("judge-off")` |
| `ask()` | `:91-122` | one batched POST, `timeout=30` default, at most 2 attempts, every failure `None` |
| `_transient()` | `:125-135` | 5xx / `OSError` retried; 4xx and malformed never |
| `_request()` | `:138-155` | the POST, the documented reply, `usage` and `latency_ms` carried back |

It is genuinely good plumbing: total (never raises, because a hook imports it),
stdlib only, one redirect guard, a retry class that was measured (0 of 184 live
calls returned `None` - `docs/operations.md:210-221`).

**Callers.** The code graph answered this (`trace_path` inbound on
`hooks.tezgah_judge.ask`, 41 callers including tests, cross-checked by grep for
the import); the three real ones are:

| caller | what it hand-builds | on failure |
|---|---|---|
| `bin/tezgah-triage` | `--select`: one noul per unit, **no `criteria`** (`:212-213`); 13 states with hand-written `criteria` (`:355-356`); reads replies with its own `prob()` (`:147-157`); prints the cost itself (`judge_line` `:165-170`) | exit 1 + one reason; the loop reads the tree |
| `bin/tezgah-docs` | a Choice over 10 pages, criteria from `title` + `answers` (`:191`), `none` offered; reads `answer.get("choice")` inline (`:197`) | returns `None`; the command prints what it always printed |
| `hooks/tezgah_skill_pick.py` | a Choice over 13 skill names + one Noul, criteria from each `SKILL.md` clause (`:145-152`), `GATE = 0.30` (`:39`), `ASK_TIMEOUT = 8.0` (`:44`), its own per-(session, prompt) cache `KEPT = 200` (`:69`, `:175-198`) | returns `""`; the turn loses the hint |

That is 3 copies of "build a question" and 3 copies of "read a Choice/noul back",
and the graph shows the wiring: `hooks.tezgah_context.context_for` reaches `ask`
in 3 hops, through `tezgah_skill_pick.suggest`.

**The weaknesses that are real, each with its line.**

1. **The session is never told the off button exists.** `judge-off` is honoured at
   `hooks/tezgah_judge.py:88` and named in the docstring at `:20,28`, in
   `bin/tezgah-triage:92` and `bin/tezgah-docs:16` - but the always-on
   `**Kill switches:**` paragraph does not list it (`hooks/tezgah_policy.py:743-749`)
   and the contract's switch table has no row for it (`docs/contract.md:133-146`,
   **(in-flight)**). A session cannot name the switch it would have to tell the
   user about. `grep -rn judge-off` outside `__pycache__`, `docs/operations.md`,
   the two tools, the module and `tests/` returns nothing.
2. **Three callers, three answer readers, no shared vocabulary for a question.**
   The seam returns the raw API reply, so each caller re-implements
   `choice`/`noul` reading: `bin/tezgah-triage:147-157`, `bin/tezgah-docs:195-197`,
   `hooks/tezgah_skill_pick.py:157-161`. `criteria` is used where a caller thought
   of it and absent where it did not: the triage's `--select` noul carries none
   (`:212-213`) while its `--states` noul does (`:355-356`).
3. **No cost accounting anywhere in tezgah, and the highest-frequency caller's
   spend is invisible.** Only `bin/tezgah-triage` prints cost (`:165-170`);
   `bin/tezgah-docs` and `hooks/tezgah_skill_pick.py` drop `result["usage"]`.
   `tezgah-status --counters` has no judge key - it prints `consult`, `codegen`,
   `codegen_failed` (`bin/tezgah-status:82`), counted as substrings of `detail`
   (`hooks/tezgah_integrity.py:694-699`) - and a judgement made by
   `tezgah_skill_pick` is a hook call with no shell row at all, so nothing on the
   ledger ever records it.
4. **No status-line mark and no used-kind.** `_GROUP`
   (`hooks/tezgah_context.py:1186-1187`) holds `pony exec adhd | consult research
   cbm orch`; `TOOL_USE_MEASURES` (`:1220`) is `{consult, research, cbm, orch}`;
   `shell_kind` (`:1000-1006`) returns `consult`, `research` or `None`. A triage
   run earns no mark, and the status line cannot answer "has this session judged
   anything, and is the seam even armed".
5. **One global switch, no per-caller policy.** `judge-off` is all-or-nothing
   (`hooks/tezgah_judge.py:88`); only `tezgah_skill_pick` has its own channel
   (`SWITCH`/`ARM= skill-suggest-*`, **(in-flight)** `:35,:132-140`). Timeout is
   the seam's 30 s default for two callers and 8 s for the third (`ASK_TIMEOUT`
   `:44`); nothing anywhere sets a concurrency or retry budget for a caller in a
   loop.
6. **One hardcoded model, and the model is not in the record.** `MODEL = "jev-latest"`
   (`:41`), overridable only via `ask(model=...)` and no caller passes one; the
   reply carries `usage` but never the model that answered, so a printed cost
   cannot be tied to what produced it.
7. **Documentation drift, in the direction that hides the busiest caller.** The
   module docstring says "Two callers" (`hooks/tezgah_judge.py:3-5`) and
   `docs/operations.md:202-203` says "One judgement tool serves two callers" -
   there are three, and the one it does not name is the prompt-path caller that
   runs on unanswered prompts. There is no docs page for the seam at all:
   `docs/index.json` has 10 pages and none is about it.
8. **The install report's TypeSafe row answers a different question than the
   seam.** `have_typesafe_key()` (`hooks/tezgah_paths.py:213-228`) reads the env
   var and omp's login store and its docstring says the key file "is not a path
   omp opens"; `key()` (`hooks/tezgah_judge.py:70-83`) reads the env var and the
   key file. **Measured**: with the key file present and no omp store
   (`tp.HOME` pointed at an empty dir), `have_typesafe_key()` returns `False`
   while `tezgah_judge.available()` returns `True`. So the health row can report
   the credential missing on a machine where every judgement works.
9. **No caching in the seam, and no local fallback.** The seam has no cache; the
   one caller that caches does it privately (`hooks/tezgah_skill_pick.py:175-198`).
   The only offline lever is `TEZGAH_TYPESAFE_URL` (`:65-67`), which is a test
   seam, not a fallback: each caller owns its own deterministic path. **This is
   the one weakness I recommend leaving alone** - see the decision.

**Reachability.** Neither `tezgah-triage` nor `tezgah-docs` appears in
`hooks/tezgah_policy.py`, `hooks/tezgah_context.py` or `agents/*.md` (grep, zero
hits). The seam is reachable only through `skills/analyze-app/SKILL.md:83,92,115`
(one of 13 roster skills, itself reached only if the model picks it),
`docs/operations.md:200-260` (read only if the session opens that page), the two
tools' `--help`, and - invisibly - the automatic prompt-path caller.
`skills/product-analysis/SKILL.md` never names `tezgah-triage`; it reaches the
`--states` mode only through `analyze-app` (`skills/product-analysis/SKILL.md:42`),
even though `--states` exists for exactly its component x state requirement.

### 2. The pattern it should match

tezgah names a capability in a small, repeated set of places. Reading the two
named precedents:

| | `consult` | `codegen` | the judge today |
|---|---|---|---|
| injected text | a conditional paragraph + a `POINTERS` line (`docs/contract.md:26-40, "Adding a rule"`) | none in `CORE`/`POINTERS`; the on-demand `CONTRACT` section only | none |
| kill switch | `consult-off`, in the switch paragraph and the contract table (`docs/contract.md:138`) | **none** | `judge-off` exists, in neither list |
| status mark | `consult`, group 1 (`hooks/tezgah_context.py:1186-1187`) | **none** | none |
| counters key | `consult` (`bin/tezgah-status:82`) | `codegen`, `codegen_failed` | none |
| bin tool | `bin/consult` | `bin/codegen` | `bin/tezgah-triage`, `bin/tezgah-docs` |
| user-facing doc | README bullet | README bullet | `docs/operations.md` section only, no README bullet, no docs page |
| how a session learns | core paragraph + pointer | README + the contract skill it may load | one skill (`analyze-app`) + one operations section |

So there is no single template - there are two tiers in use. **Tier A** (a
capability the injected text names: `consult`, `research`, `cbm`, `orch`) buys a
paragraph, a pointer line, a switch row and a mark. **Tier B** (a tool the
session reaches by name from a skill or the docs: `codegen`, `tezgah-triage`,
`tezgah-docs`, `tezgah-rollback`) buys a bin tool, a README/docs mention and a
counters key at most - `codegen` has a counter and no mark, and that is
deliberate.

The judge today is **below Tier B**: its two tools are Tier B but the seam itself
is named nowhere the model sees, and the property that makes it a tier rather
than a detail is that it is *shared* - three callers, one credential, one egress
boundary, one price, one switch, and one redirect guard protecting all of them.

**Is it an implementation detail of two tools, or a tier the contract should
name?** It is currently the former and structured like the latter. The costs:

- **Naming it** costs: one clause in the existing switch paragraph (~40 bytes per
  session, no new paragraph), one mark in group 1 (~6 characters of status line),
  one counters key, a per-caller switch per caller, a docs page + index entry, and
  the tests the contract's "Adding a rule" section already demands for a mark and
  a switch. It does **not** cost an always-on rule paragraph if the capability
  stays on-demand - and it should: `CONDITIONAL_KEYS` exists precisely so a
  session that never asks does not carry the text.
- **Leaving it unnamed** costs what the audit measured: the off button is
  unnameable, the spend is invisible, the status line cannot show armed/used, the
  fourth caller re-invents the question shape and the answer reader (the third one
  already did, with a cache and a threshold of its own), and every reader of the
  docs learns "two callers" about a three-caller seam.

### 3. The decision, with its tradeoffs

**Where it belongs.** `hooks/tezgah_judge.py` stays exactly where it is - a hook
module that is total, stdlib-only and dependency-free - because that is what makes
it safe on a hook import path, and its callers stay bin tools and one hook. What
changes is the *tier*: the capability it implements is a named on-demand
capability (Tier B, the `codegen` shape, not the `consult` shape), with the three
things Tier B is missing today - a switch the session can name, a mark, and a
counted cost - and with the seam's own parts split by who needs them:

- **policy** (must be visible to a session): that the state leaves the machine,
  that `judge-off` and each caller's own switch disarm it, and that a judgement is
  an aid and never the claim. The egress statement already lives in
  `skills/analyze-app/SKILL.md:115` and the module docstring; the switches belong
  in the paragraph and the contract table that already list every other one.
- **plumbing** (belongs in the module, invisible): credential resolution, the
  redirect guard, the retry class, the timeout, total-by-design.
- **on demand** (skill text and a docs page, never always-on): the per-mode
  behaviour, the thresholds, the measured recall, the price arithmetic.

**Tradeoff, stated.** Naming it in the injected text buys discovery at the cost
of bytes every session and one more thing a status line must not lie about (the
`observable` rule in `docs/status-line.md`: a mark asserting a state the surface
cannot see is a bug in the layer, so `judge` must render `info` where the
used-kinds store cannot be written). Not naming it buys nothing at all: the
capability is already paid for, and an unnamed switch is a switch nobody can use.

**What I would not trade away.** The module's three properties, because each one
has a reason with a test behind it: **total** (`ask` returns `None`, never raises -
a hook that raises takes a session down); **stdlib only** (it is the first and
only network path in `hooks/`; `grep -rlE "^import (urllib|http|socket|requests)" hooks/`
returned nothing before it and the suite is hermetic); **dependency-free** (no SDK,
no async, no client library, retry ceiling of one). A caller-level cache, an SDK,
or a local model would each trade one of those for a saving the measurements below
do not justify.

### 4. Where it should serve next, ranked, with the measurement status

Evidence column: "measured" = a number exists in this repo (with where), "refused"
= a measurement or an invariant says no, "open" = no measurement exists.

| # | surface | the judgement | evidence it is worth it | status |
|---|---|---|---|---|
| N1 | **the citation audit's unjudgeable half** (`bin/tezgah-docs --citations`) | per citation, does the cited range still show what the sentence names? | `bin/tezgah-docs --citations` (run 2026-09-20): "264 judged (1 outside the symbol they name), **734 not judgeable**"; `docs/README.md:47-57` names those as "the next audit's work list"; the tool's own comment (`bin/tezgah-docs:64-72`) says that half is a judgement about prose "a test that guessed at it would fail on rewording rather than on drift" | **open** |
| N2 | **the ai-research inner router** (98 entries) | which one of 98 vendored entries answers this request | measured this round: flat Choice 14/14, refuses 4/4 out-of-library, $0.000155 and ~830 ms per query - `experiments/E1-ai-research-router`, `E1b-none-refusal` | **measured (ceiling-limited)** |
| N3 | **product-analysis component x state matrix** | per-component state coverage | `tezgah-triage --states` is measured on a driven fixture (disabled 0.49-0.51 for a form whose only `[disabled]` sat on a child button; focus 0.95 beside active 0.82 - `bin/tezgah-triage:325-350`); the state set is one constant (`STATES`, `:64-68`); but `skills/product-analysis/SKILL.md` never names the tool | **partially measured**, routing gap open |
| N4 | **per-finding verification** (does the cited evidence support this claim?) | Noul/Choice per finding | `typesafe-cost` P4 predicts >=90% agreement with the agent's own verdicts, on a Ustam replay; nothing has been run | **open** |
| N5 | **file-action classification for the gate's effect table** | which `effect_class` an unclassified program belongs to, printed for a maintainer | `docs/gate.md:162-166`: the fold "is a READER ... ranks by program - the token the table is grown from", capped at 40 (`hooks/tezgah_gate.py:1677`) | **open** |
| N6 | **extend the docs page Choice to the new judge page** | which page answers this query | `bin/tezgah-docs:167-185`: measured over 39 live queries, 37 right, 0 wrong, 2 missed | **measured** |
| S1-6 | the six candidates of `.tezgah/research/typesafe-cost/findings.md` | see below | see below | see below |

**The six candidates of `typesafe-cost/findings.md`, after this round:**

| # | candidate | status |
|---|---|---|
| 1 | skill routing (roster of 13) | **measured and partly refused.** An independent chooser was at 0/20 wrong with no hint, so the arm had no headroom; the roster compaction was refused (5/5 and 6/6 discordant pairs favour the full roster); the skip-the-roster idea is refuted at this roster size. The in-flight working-tree change (the picker becomes opt-in via `skill-suggest-on`) is the honest response to that measurement. |
| 2 | the analyze-app snapshot triage | **measured and shipped.** 100% of 83 control lines at a 94% read on the 356-line table, 100% at 74% on the 31-line screen, against 73.5% at 26% for the per-line shape. |
| 3 | product-analysis state matrix | **partially measured** (= N3): accuracy on a driven fixture; never run as a full-screen coverage pass, and not named by the skill that needs it. |
| 4 | per-finding verification | **open** - the largest unmeasured prize, and the one the spec defers until a labelled replay exists. |
| 5 | `bin/tezgah-docs` page Choice | **measured and shipped** (39 queries, 0 wrong). |
| 6 | ai-research entry (98 entries) | **measured this round** (= N2): the flat primitive holds and refuses; the near-miss case is still untested. |

**Refused, and why** (unchanged from `typesafe-cost` §5, plus this round's
confirmation): the gate's refusals, the shortcut parser, the Stop rule and the
consent path - refusal reproducibility is an invariant with tests behind it
(`tests/test_gate.py`, `tests/test_integrity.py`), and `docs/gate.md:256-260`
already records the same conclusion for a model call on the Stop path; the
PreToolUse hot path (a network round trip per tool call); and anywhere the current
mechanism is already free and exact (regex classification, hashing, ledger
arithmetic). This round adds one more: **a caller-level or seam-level cache is not
worth building now** - the measured price of a judgement is $0.000155 (98 options) to $0.000294 (the shipped
unit selection on the 356-line screen, 7,008 input tokens; the per-line shape it
replaced cost $0.000569), so the whole premise of a cache is
a saving measured in ten-thousandths of a dollar.

### 5. What the measurements in this round cost

| run | calls | input tokens | measured cost |
|---|---|---|---|
| E1 (flat + two-stage, 14 queries) | 42 | 83,712 | $0.003516 |
| E1b (none-refusal, flat arm) | 4 | 14,719 | $0.000618 |
| E1b stage arm | 4 | not recorded | <= $0.0002 [estimate] |
| **total** | **50** | - | **$0.0041 measured, under 1 cent** |

## Patterns

- **The seam is a subsystem wearing a helper's clothes.** ([C1], [C3]) One credential, one
  egress boundary, one price, one switch and one redirect guard serve three
  callers, two of which the docs do not know about. The cost of that mismatch is
  not in the code (155 lines, well written) but in what nobody can see: the off
  button, the spend, and the fact that a fourth caller is already being written.
- **tezgah's own tiers are decided by bytes, not by importance** ([C1]). `consult` is
  Tier A because a session must know to ask for a second opinion; `codegen` is
  Tier B because the router is the one that reaches for it. The judge is reached
  by an agent mid-loop, exactly like `codegen` - so the `codegen` shape is the
  precedent that fits, and `codegen`'s own gaps (no mark, no switch) are the ones
  not to copy.
- **Every capability tezgah names is named in the same handful of places** ([C1], [C3]) - the
  switch paragraph, the contract table, a group-1 mark, a counters key, a docs
  page, a bin tool, tests - and a capability missing two of them is invisible
  while still costing money on every prompt.
- **The measured answer to "can the primitive take 98 options" is yes, and the answer to "is two stages better" is no** ([C2]). Cost scales with the option text, not with the option count; the two-stage shape saved 1.61x tokens for a second round trip, which at $0.042/1M is worth $0.00006.
- **A ceiling is not a result** ([C2]). Both arms at 14/14 with 4/4 refusals says the
  primitive works and says nothing about where it breaks; the discriminating
  instrument is a query whose correct entry is separated from a plausible
  neighbour by something the clause does not carry.

## Lessons

- A judgement surface that never says "not mine" is worse than no surface
  (`bin/tezgah-docs` offers `none` for exactly this reason). Measured here: 4/4
  out-of-library queries were refused in both arms, so at 98 options the primitive
  did not force a nearest-neighbour pick.
- A mark must not claim a state the surface cannot see (`docs/status-line.md`), so
  a future `judge` mark must render `info` where the used-kinds store cannot be
  written - the same carve-out `TOOL_MEASURES`/`observable` exists for.
- Two credential readers in one repo answer two different questions: this round
  measured `have_typesafe_key() == False` while `available() == True` on a machine
  holding only the key file.
- A hand-written unambiguous query set measures the ceiling; write the falsifier
  as a floor AND write the set so the floor is reachable.

## Open questions

- Does the flat 98-option Choice hold on the *near-miss* case - a query just
  outside a category whose entry clause is close? E1's set cannot test it; the
  falsifiable design is named in `experiments/E1-ai-research-router/analysis.md`.
- Which of N1/N3/N4/N5 the user wants next. The measurements rank N1 highest on
  evidence (a 734-item work list the repo itself names) and N4 highest on value
  (it replaces an agent turn per finding), and neither has been run.
- Whether a per-caller switch should be a kill switch (`triage-off`) or an arming
  marker (`triage-on`) - the in-flight change answers this for `skill_pick` only,
  and the two have different defaults for an unconfigured machine.
- Whether the egress boundary should be stated in the always-on text or only in
  the skill that reaches the tool. The current choice (skill text only) means a
  session that never picks `analyze-app` never reads that a screen's text leaves
  the machine.

## Closure (2026-09-22): what moved, what was built, what the line still owes

This line concluded on 2026-09-20 at HEAD `4bf25e8` with eight files in flight.
On 2026-09-22 (HEAD `ddf72b4`) five of its seven spec items are built, one is
refuted by its own pre-registered run, and one part of its record is an integrity
defect that no later reading can repair.

**Built.** J1 (the off button named where the session can see it): `judge-off`,
`triage-off` and `docs-judge-off` are in the kill-switch paragraph, the contract
table and its two mirrors. J2 (one answer reader): `choice()` and `noul()` on the
seam, and all three callers read through them. J3 (a `judge` mark in group 1,
with the `observable` carve-out). J4 (the spend counted): a `judge` key in the
counter fold, counted on the row kind rather than a `detail` substring, printed by
`bin/tezgah-status`, with one row per successful judgement from the shell caller
and the prompt-path caller. J5 (a switch per caller, `judge-off` the master). J6
(`docs/judge.md`, indexed, so `tezgah-docs judge` answers from the keyword index
and pays for no Choice).

**Refuted.** J7 (the citation audit's unjudgeable half) went through its own
pre-registered round as `experiments/E2-citation-adjudication`: eleven hand-labelled
citations, one call each, agreement 5 of 9 = 0.56 against a floor of 0.9, and
precision on the seven flagged rows 0.29. `C5-R` records it as refuted. The
analysis is honest about the bound: the model answered `does-not-show` seven times
out of eleven, so the run refutes the *format* it was given, not the possibility -
a two-order format with a worked example was not run.

**The integrity defect this line carries.** E1's `protocol.md` states that its own
first write did not land and that the text was re-created from the transcript
*after* the run. Nothing in the artifacts can therefore prove the predictions
predate the results, which is the property every E1 verdict rests on. The rows
carry `source` and `scope`, the file is tracked, and the run's own numbers stand -
but the ordering claim is unprovable and is recorded as such here, in `log.md` and
in `to_human/report.md` rather than left for a reader to discover. `.tezgah/research/`
is gitignored, so `tezgah-research check` can only warn on the class either way.

**Between E1 and E2 the lesson was applied.** E2's protocol and its labelled
`sample.json` were committed *before* the run (commit `da7148e`), so E2's ordering
is decidable where E1's is not.

**Correction (2026-09-22): the seam has three callers in every shipped place.**
The pass that closed this line found the drift the audit first measured still live
in five spots - the module docstring (`hooks/tezgah_judge.py:4`), three passages of
`docs/operations.md`, a comment in `hooks/tezgah_context.py` and one in the
opencode plugin - and corrected each to name all three: `bin/tezgah-triage`,
`bin/tezgah-docs` and `hooks/tezgah_skill_pick.py`. The third caller is the
prompt-path hint, the one no shell row sees. `C1-R-callers-fixed` records it;
`C3-R-spend-counted` and `C4-R-readers-named` record the two other weaknesses this
line measured that the tree has since answered.
