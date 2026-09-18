# Contract: what a session is told, and how a rule is disarmed

The rule layer of tezgah: the text a session receives, the order it arrives in,
the file each piece is written from, and the switch that takes one out. Read it
when you add or edit a rule, when you need to know whether a session was really
told something, or when a session behaves as if a rule were missing. The
user-facing side of the same contract is [README.md](../README.md); the words
used here are defined once in [glossary.md](glossary.md); which host gets which
surface is [hosts.md](hosts.md).

Every string is a module constant in `hooks/tezgah_policy.py`, so that every
host says the same thing (`hooks/tezgah_policy.py:3-10`); path placeholders
(`{ROOT}`, `{CONSULT_BIN}`, `{ORX_BIN}`, …) are filled at injection time by
`render()` (`hooks/tezgah_context.py:89-100`).

## The four surfaces

| Surface | Text | Paid |
|---|---|---|
| always-on core | `CORE` (`hooks/tezgah_policy.py:485-637`) minus the four conditional paragraphs, plus the pointer line | once per session: `session_start` and `post_compact` |
| conditional paragraph | one of the four keyed by `CONDITIONAL_KEYS` (`hooks/tezgah_policy.py:643`) | only on the turn whose prompt matches its task class |
| per-turn reminder | `PROMPT_REMINDER` (`hooks/tezgah_policy.py:654-670`) | every user prompt |
| on-demand full contract | `CONTRACT` (`hooks/tezgah_policy.py:673-675`), shipped as `skills/tezgah-contract/SKILL.md` | only when the session loads that skill |

`context_for(event, …)` is the one dispatcher (`hooks/tezgah_context.py:712`):
`session_start`/`post_compact` build core plus live state, `user_prompt` builds
the reminder plus whatever was armed, `subagent_start` builds a short brief
(`hooks/tezgah_context.py:755`). Outside every configured root it returns `None`
(`hooks/tezgah_context.py:695-696`). A host whose static always-on file already
carries the core passes `with_core=False` so the session does not pay for the
contract twice (`hooks/tezgah_context.py:717-722`); a delegated agent gets
`subagent_core()`, which keeps every always-on label and its opening clause and
points at the skill (`hooks/tezgah_context.py:576-603`).

## Composition order of the always-on core

Paragraphs are concatenated in the order they appear in `CORE` and identified by
the bold label each starts with (`CORE_RULES`, `hooks/tezgah_context.py:70-86`).
That order, with the line each label sits on in `hooks/tezgah_policy.py`:
`**Turkish, BLUF.**` :488, `**Ponytail (minimal code).**` :497, `**Output shape:
ADHD-friendly.**` :508, `**Deliver the whole ask; never the shortcut.**` :518,
`**Integrity: evidence, or "doğrulanmadı".**` :532, `**Loop discipline.**` :543,
`**Spec before building.**` :549 *(conditional)*, `**Lessons ledger: stop
repeating mistakes.**` :563, `**Code discovery: graph first.**` :570
*(conditional)*, `**Consult before irreversible.**` :579 *(conditional)*,
`**Research: route it to OpenResearch.**` :593 *(conditional)*, `**No AI
attribution, ever, on any host.**` :602, `**Irreversible or outward-facing
actions need an explicit ask first.**` :612, `**Session scope: the user's repo,
not tezgah.**` :621, `**Kill switches:**` :630.

`always_on_core()` (`hooks/tezgah_context.py:565-573`) drops the four
conditional paragraphs and appends `POINTERS` (`hooks/tezgah_policy.py:648-650`):
one line each saying the rule exists and where its full text lives — spec-first,
a second opinion, OpenResearch routing, the code graph. That is what a host with
no prompt-time hook writes into a static file: opencode's
`~/.config/tezgah/opencode-contract.md` (`bin/tezgah-setup:528-563`) and omp's
managed `RULES.md` (`bin/tezgah-setup:1025-1027`). Claude applies
`output-styles/tezgah.md` as a plugin output style instead
(`output-styles/tezgah.md:11-12`); Codex and Cursor receive the same core from
their session-start hook (`hosts/codex/hook.py:36`, `hosts/cursor/hook.py:203`). `core_for()`
(`hooks/tezgah_context.py:556-562`) is that text with the kill-switch filtering
applied, and it also returns the names of the switches that fired.

## What each always-on rule is for

- **Turkish, BLUF.** Every user-facing reply is Turkish even when the prompt is English, outcome first; code, commits, docs and subagent prompts stay English.
- **Ponytail (minimal code).** Take the laziest rung that holds (YAGNI → reuse → stdlib → platform → installed dependency → one line), never simplify away validation, error handling or security. A non-default level rides the reminder (`hooks/tezgah_context.py:103-110`).
- **Output shape: ADHD-friendly.** The action or answer is the first line, multi-step work is a numbered list whose position is restated, an estimate is in concrete units. Two upstream rules were rewritten rather than imported verbatim because they collided with rules already in force: the state restatement points at the todo list instead of duplicating it, and a time estimate can no longer be read as a measurement (`CHANGELOG.md:37-40`, `plans/done/001-act-on-it-rule-and-level-switch.md:33-35`).
- **Deliver the whole ask; never the shortcut.** The request is a floor: no cheaper stand-in, no silent scope cut, no token gesture reported as done.
- **Integrity: evidence, or "doğrulanmadı".** A done/tested claim holds only if the check ran in this session and its output was seen; the mechanical half is enforced by [gate.md](gate.md).
- **Loop discipline.** Never repeat an identical failing command; three attempts is the ceiling, then report what is still unknown.
- **Lessons ledger: stop repeating mistakes.** `.tezgah/lessons.md` lines are standing constraints; the recent ones are injected at session start.
- **No AI attribution, ever, on any host.** Nothing persisted or published may name a model, vendor or "AI" as author, co-author, generator or helper.
- **Irreversible or outward-facing actions need an explicit ask first.** The one invariant: it stays armed whatever the classifier decides (`tests/test_context.py:1177-1187`), because the classifier is advisory.
- **Session scope: the user's repo, not tezgah.** The session never maintains tezgah itself; a missing capability is one line plus the documented fallback.
- **Kill switches.** The switch list itself, so a session can tell the user how to disarm a rule it is asked to ignore; pinned against the shipped skill by `tests/test_skills.py:99-109`.

## Arming the conditional paragraphs, and the per-turn reminder

`PROMPT_HINTS` (`hooks/tezgah_context.py:42-58`) is one compiled pattern per key
— `spec`, `consult`, `research`, `cbm` — and `classify_prompt()` returns the keys
a prompt matches (`hooks/tezgah_context.py:466-469`). On that turn only, the
matching paragraphs are appended after the reminder
(`hooks/tezgah_context.py:721-729`); a session that never asks such a question
pays the one-line pointer instead. The patterns carry Turkish stems because the
user writes Turkish, and a plain prompt arms nothing. The same prompt arms the
same rules on every host (`tests/test_context.py:1145-1166`) and each advisory
rule keeps a pointer line in the always-on text (`tests/test_context.py:1168-1175`).

`PROMPT_REMINDER` is the compact restatement of the invariants, about a third of
the long form and still inside the `<harness-reminder>` envelope the hosts and
tests look for (`hooks/tezgah_policy.py:652-653`), with its `{PONY_LEVEL}` slot naming a non-default ponytail level
(`hooks/tezgah_context.py:103-110`). The session-start text ends with the pointer
telling the model to load `tezgah-contract` for the deep detail
(`hooks/tezgah_context.py:839`), whose two appendixes apply only on a machine
missing the code graph or every consult key (`hooks/tezgah_policy.py:424-442`).

## How a rule is disarmed

A kill switch removes the rule's text, not just a status mark
(`hooks/tezgah_context.py:559-560`). `off()` checks `~/.config/tezgah` and the
legacy `~/.claude` (`hooks/tezgah_paths.py:43-45`, `:218-220`); the drop itself
happens in `core_split()`.

| Switch file | Rule it removes | Where the drop is implemented |
|---|---|---|
| `exec-mode.off` | `**Turkish, BLUF.**` | `hooks/tezgah_context.py:513-515` |
| `ponytail-auto.off` | `**Ponytail (minimal code).**` | `hooks/tezgah_context.py:516-519` |
| `adhd-off` | `**Output shape: ADHD-friendly.**` | `hooks/tezgah_context.py:520-522` |
| `spec-off` | `**Spec before building.**` | `hooks/tezgah_context.py:523-525` |
| `verify-off` | `**Integrity: evidence…**` | `hooks/tezgah_context.py:526-528` |
| `consult-off` | `**Consult before irreversible.**` | `hooks/tezgah_context.py:532-534` |
| `research-off` | `**Research: route it to OpenResearch.**` | `hooks/tezgah_context.py:535-537` |
| `orchestrate-off` | the orchestration section of the on-demand skill (there is no core paragraph) | `hooks/tezgah_context.py:538-539` disables it, `:805-809` injects "Orchestration is off", and the skill-ignore note is `hooks/tezgah_context.py:730-732` |
| `reminder-off` | the per-turn reminder | `hooks/tezgah_context.py:780-782` returns `None` |
| `pretooluse-off` | the gate's denials, not a rule | [gate.md](gate.md) |
| `.no-ponytail` | `**Ponytail (minimal code).**` | `hooks/tezgah_context.py:516-519` |
| `.no-adhd` | `**Output shape: ADHD-friendly.**` | `hooks/tezgah_context.py:520-522` |
| `.no-cbm` | `**Code discovery: graph first.**` | `hooks/tezgah_context.py:540-542` |
| `.no-lessons` | `**Lessons ledger: stop repeating mistakes.**` | `hooks/tezgah_context.py:529-531`, and the lessons block is not injected (`hooks/tezgah_context.py:826-829`) |

The last four are per-repo [marks](glossary.md#per-repo-mark), read by
`repo_marks()`, walking up to the enclosing [root](glossary.md#root)
(`hooks/tezgah_context.py:1001-1014`). Every switch that fired is named back to the
session at start (`hooks/tezgah_context.py:839`) and per turn (`hooks/tezgah_context.py:780-782`), with the instruction to
ignore the matching section in `tezgah-contract` — that skill is loaded
separately and would otherwise re-arm the rule. `tezgah-adhd off` writes the same
channel as the file (`bin/tezgah-adhd:19`); the ponytail *level* is not a switch.

`**Deliver the whole ask**`, the sycophancy ban and the attribution ban are
invariants: no switch touches them, and `tests/test_context.py:407-417` asserts
they survive every other switch being off.

## Adding a rule

1. Write the full text as a constant in `hooks/tezgah_policy.py`.
2. If not every session should pay it, add the key to `CONDITIONAL_KEYS`
   (`hooks/tezgah_policy.py:643`), a pattern to `PROMPT_HINTS`
   (`hooks/tezgah_context.py:42-58`) and a line to `POINTERS`
   (`hooks/tezgah_policy.py:648-650`); the two halves are asserted together
   (`tests/test_context.py:1168-1175`).
3. Put the paragraph in `CORE` with its bold label and add the `(key, label)`
   pair to `CORE_RULES` (`hooks/tezgah_context.py:70-86`). The label is the
   contract: `core_split()` matches paragraphs by it and `subagent_core()` builds
   the brief from it, so a label edit fails loudly instead of silently dropping
   a rule.
4. If the rule names a kill switch, add the drop to `core_split()` and list the
   switch in the `**Kill switches:**` paragraph (`hooks/tezgah_policy.py:630`).
5. Mirror the full text into `skills/tezgah-contract/SKILL.md`, and regenerate
   `output-styles/tezgah.md` from a fresh Python process when the paragraph is
   always-on — a warm interpreter serves a stale `CORE`.
6. Last step, the tests that pin it: add the label to `KillSwitchEnforcement`
   (`tests/test_context.py:364-380`) and, for a conditional rule, to the
   `ArmingConformance` label map (`tests/test_context.py:1126-1129`); then run the mirror pair —
   `OutputStyleMirrorsCore.test_body_is_the_always_on_core`
   (`tests/test_context.py:1230-1238`) and
   `ContractParity.test_every_rule_and_heading_in_the_contract_reaches_the_skill`
   (`tests/test_setup.py:604-618`).

## The two copies that must stay in step

| Copy A | Copy B | Test that fails when only one changed |
|---|---|---|
| `CORE`, via `always_on_core()` | `output-styles/tezgah.md` (Claude's hookless duplicate) | `tests/test_context.py:1230` |
| `policy.CONTRACT` (`hooks/tezgah_policy.py:673`) | `skills/tezgah-contract/SKILL.md` | `tests/test_setup.py:604` |

The second pair is also hashed as one source for the generated opencode contract
(`bin/tezgah-setup:148-149`, `:152-184`), which notices that *one* of them
changed; `ContractParity` is what notices that only one of them did, which is the
drift that actually happens (`tests/test_setup.py:593-596`). `tezgah-setup
--refresh` re-renders the generated artifacts in a running session when that hash
is stale (`bin/tezgah-setup:566-581`, `bin/tezgah-setup:2279-2281`).

## When the injected text grows too large

Each event has a byte budget: `session_start` and `post_compact` 12000,
`user_prompt` 6000, `subagent_start` 4000, anything else 12000
(`hooks/tezgah_context.py:630-631`). Each sits at about 1.5× the largest text
that event was measured to build in this repository, so it never fires on a
healthy repo and fires before a pathological one reaches the model; it is a byte
count, not a token estimate (`hooks/tezgah_context.py:620-629`).

Over budget, `budgeted()` gives up whole blocks in `DROP_ORDER`, lowest value
first — the lessons and their neighbours before the tooling-availability lines,
the live graph and state lines, the delta, and the skill pointer last
(`hooks/tezgah_context.py:642-644`, `hooks/tezgah_context.py:680-709`). Any key absent from that tuple is
never dropped: the core, the reminder and the armed paragraphs are the rules, and
a budget able to spend them would turn bloat into rule loss. The note naming what
went is appended after the count, so the sentence explaining the trim cannot force
another one, and it says so when what remains is still over the limit
(`hooks/tezgah_context.py:647-659`); the drop is logged to `~/.cache/tezgah/context-drops.log`, truncated
to its last 200 lines (`hooks/tezgah_context.py:662-677`).

## Source of truth

- `hooks/tezgah_policy.py` — `CORE`, `CONDITIONAL_KEYS`, `POINTERS`, `PROMPT_REMINDER`, `CONTRACT`, and the long-form blocks they are built from
- `hooks/tezgah_context.py` — `CORE_RULES`, `PROMPT_HINTS`, `classify_prompt`, `core_split`, `core_for`, `always_on_core`, `subagent_core`, `context_for`, `repo_marks`, `CONTEXT_BUDGET`, `DROP_ORDER`, `budgeted`, `log_drop`
- `hooks/tezgah_paths.py` — `OFF_DIRS`, `off()`, the ponytail level path; `bin/tezgah-setup` — `install_common`, `opencode_contract`, `refresh_contract`, the omp `RULES.md` writer, `--refresh`; `bin/tezgah-adhd` — the CLI that writes the `adhd-off` switch
- `skills/tezgah-contract/SKILL.md` — the on-demand full contract; `output-styles/tezgah.md` — Claude's always-on duplicate of the core
- `tests/test_context.py`, `tests/test_setup.py`, `tests/test_skills.py` — the label, kill-switch, budget and mirror tests; `CHANGELOG.md` and `plans/done/001-act-on-it-rule-and-level-switch.md` — why two upstream rules were rewritten
