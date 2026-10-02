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
`render()` (`hooks/tezgah_context.py:324-337`).

## The five surfaces

| Surface | Text | Paid |
|---|---|---|
| always-on core | `CORE` (`hooks/tezgah_policy.py:626-845`) minus the five conditional paragraphs, plus the pointer line | once per session: `session_start` and `post_compact` |
| conditional paragraph | one of the five keyed by `CONDITIONAL_KEYS` (`hooks/tezgah_policy.py:846-850`) | only on the turn whose prompt matches its task class |
| per-turn reminder | `PROMPT_REMINDER` (`hooks/tezgah_policy.py:857-877`) | every user prompt |
| skill suggestion | one `<skill_relevance>` line naming at most one installed skill, written by `suggest` (`hooks/tezgah_skill_pick.py:210-225`); off unless `skill-suggest-on` is armed | only on a turn the judgement answers with a skill |
| on-demand full contract | `CONTRACT` (`hooks/tezgah_policy.py:878-902`), shipped as `skills/tezgah-contract/SKILL.md` | only when the session loads that skill |

The skill suggestion is the one surface a judgement writes rather than a constant.
The roster reaches a session as an index of host-truncated one-liners, so which
entry to look at first is the turn's own weak spot; one batched judgement request
answers it - TypeSafe, or the OpenRouter fallback when no TypeSafe key resolves
(`credential()`, `hooks/tezgah_judge.py:150`) - a Choice across the installed
skill names plus `none`, and one Noul
asking whether the turn wants a skill at all - and the winner is appended after
the armed paragraphs as a hint to look at first, never as an instruction to load
(`hooks/tezgah_skill_pick.py:35-62` is the whole configuration, wired into
`context_for` at `hooks/tezgah_context.py:1298-1299`). Measured cost of the line
itself: 305-317 characters, about 78 tokens of prompt. Measured cost of the
judgement: one call per unanswered prompt, 909-915 input tokens, 0.77-0.81 s,
$0.000038 at $0.042/1M on three live judgements. It is OFF UNLESS ARMED -
`skill-suggest-on` in `~/.config/tezgah`, the same place the kill switches live -
because a labelled set of 28 prompts through an independent chooser was measured
at 0 of 20 wrong with no hint at all, so the line's benefit on this 13-skill
roster is unproven while its cost is measured; arming it is a decision the user
makes, and an unarmed install asks nothing. It changes nothing else - no
credential, a `none` answer, a slash command, a failed or stalled call, or the
absence of the arming file appends no bytes at all, and the same prompt in one
session is never paid for twice (`tests/test_skill_pick.py`). The host's own
roster text is left untouched: that is what a session matches on and what its
prefix cache covers, which is the whole reason the upstream recipe keeps it.

`context_for(event, …)` is the one dispatcher (`hooks/tezgah_context.py:1233`):
`session_start`/`post_compact` build core plus live state, `user_prompt` builds
the reminder, whatever was armed and any skill hint, `subagent_start` builds a short brief
(`hooks/tezgah_context.py:1340-1341`). Outside every configured root it returns `None`
(`hooks/tezgah_context.py:1244-1245`). A host whose static always-on file already
carries the core passes `with_core=False` so the session does not pay for the
contract twice (`hooks/tezgah_context.py:1238-1242`); a delegated agent gets
`subagent_core()`, which keeps every always-on label and its opening clause, and
carries the two always-on blocks that are not labelled rules - the on-demand
pointer line and the kill-switch list - in its header, because its header claims
every rule is in force and a delegate that cannot name a switch cannot tell its
caller how to disarm one (`hooks/tezgah_context.py:1006-1046`).

One block on those two events is not a standing rule but the live turn state.
`session_start` and `post_compact` also build `resume_state`: a plan's
`## State` and `## Next`, the branch's last three commits, the newest
`verify_ok`/`verify_fail` the session ledger holds, and the files the last turn
changed. The plan named is the one the checked-out `plan/...` branch owns, and
when the checkout owns none the lowest-id open plan is offered as what it is -
`open plan NNN (not this branch)` - because another plan's Next read as the
active one would invent a task. It is what a session that compacts, or resumes the next morning, would
otherwise lose - the contract, the plans and the lessons arrive, but not what the
turn was doing. It is written as a state of the world and never as an order. Each
part is silent when its fact is unknown and the block is left out whole when
every part is empty. On Claude it reaches the model through SessionStart, which
fires again as `SessionStart:compact` after a compaction and delivers its
`additionalContext`. It does NOT go out on PostCompact: a real compaction on
Claude Code 2.1.283 (plan 021) showed the host rejecting a PostCompact envelope
("Hook JSON output validation failed - hookSpecificOutput.hookEventName:
expected one of ...") and printing the raw JSON into the transcript as a failed
hook, so `hooks/projects-auto-init.py` builds the block on that event - which is
where the compaction is recorded - and prints nothing.

The same event is where a compaction is recorded rather than only answered. When
the host hands the PostCompact payload a summary - Claude's `compact_summary`,
the text the model is about to receive - the shared funnel writes one ledger row
holding the summary's length, a 12-hex digest of it, the host's `trigger`
(`manual` or `auto`) and how many of the fixed constraint lines tezgah injects
(the pointer line, and the active plan's line when the repo keeps an open plan)
the summary still carries, out of how many were injected. The text itself is
never stored: the summary is the whole conversation by proxy and the ledger is a
redacted channel, so a row must not be readable as prose. The count is a report
and never a refusal - a compaction that dropped a rule is a finding to report,
not a turn to block - and `tezgah-status --counters` folds the rows into
`compactions`, `compact_chars` and `compact_constraint_rate`
([evidence.md](evidence.md#the-kinds-by-what-reads-them)).

One per-turn line is not a rule but a check on the turn's own evidence. When the
ledger says every check that passed in this session ran in a scratch or stand-in
path - `/tmp/`, `/var/folders/`, `$TMPDIR`, or a path segment naming a
`fixture`/`fake`/`stub`/`sample`/`demo` (`SCRATCH_PATH`,
`hooks/tezgah_integrity.py:2771-2777`; `scratch_evidence`,
`hooks/tezgah_integrity.py:2792-2816`) - the turn is told the command and the
rule: evidence from a scratch path is evidence about the code path, so a claim
about the running system needs a check that ran against it (`SCRATCH_REMINDER`,
`hooks/tezgah_context.py:1292-1298`, appended at `hooks/tezgah_context.py:1327`).
It is a reminder and not a block because whether a scratch script exercises the
real system is not decidable from the command; one passing check against a real
path makes the reader answer `None`, so a session that also ran the real thing is
never told this; and a ledger with no such row costs no bytes. `verify-off` drops
it with the integrity rule it restates.

## Composition order of the always-on core

Paragraphs are concatenated in the order they appear in `CORE` and identified by
the bold label each starts with (`CORE_RULES`, `hooks/tezgah_context.py:304-323`).
That order, with the line each label sits on in `hooks/tezgah_policy.py`:
`**Turkish, BLUF.**` :616, `**Ponytail (minimal code).**` :625, `**Output shape:
ADHD-friendly.**` :636, `**Deliver the whole ask; never the shortcut.**` :650,
`**Integrity: evidence, or "doğrulanmadı".**` :664, `**Loop discipline.**` :679,
`**Spec before building.**` :685 *(conditional)*, `**Lessons ledger: stop
repeating mistakes.**` :699, `**Code discovery: graph first.**` :706
*(conditional)*, `**Consult before irreversible.**` :715 *(conditional)*,
`**Research: route it to OpenResearch.**` :729 *(conditional)*, `**Product
analysis: five axes, one evidence class per finding.**` :745 *(conditional)*,
`**No AI attribution, ever, on any host.**` :778, `**Identifiers and messages
stay English.**` :788, `**Session scope: the user's repo, not tezgah.**` :794,
`**Kill switches:**` :803.

`always_on_core()` (`hooks/tezgah_context.py:1113-1123`) drops the five
conditional paragraphs and appends `POINTERS` (`hooks/tezgah_policy.py:851-856`):
one line each saying the rule exists and where its full text lives — spec-first,
a second opinion, OpenResearch routing, product analysis, the code graph, and the
per-repo design contract `bin/tezgah-design` checks a UI change against (the one
pointer with no conditional paragraph behind it, because the Stop rule's `no
ui_ok` class is what asks for the check). That is
what a host with no prompt-time hook writes into a static file: opencode's
`~/.config/tezgah/opencode-contract.md` (`bin/tezgah-setup:788-792`) and omp's
managed `RULES.md` (`bin/tezgah-setup:1299-1301`). Claude gets it from the
managed block in `~/.claude/CLAUDE.md` (its global memory file, and the reason
its session-start hook drops the core: `TEZGAH_CORE_IN_FILE`) and from
`output-styles/tezgah.md` where a build loads plugin output styles
(`output-styles/tezgah.md:11-12`); Codex gets it from the managed block in its
global instructions file; Cursor receives the same core from its session-start
hook (`hosts/codex/hook.py:36`, `hosts/cursor/hook.py:241`). `core_for()`
(`hooks/tezgah_context.py:1104-1112`) is that text with the kill-switch filtering
applied, and it also returns the names of the switches that fired.

## What each always-on rule is for

- **Turkish, BLUF.** Every user-facing reply is Turkish even when the prompt is English, outcome first; code, commits, docs and subagent prompts stay English.
- **Ponytail (minimal code).** Take the laziest rung that holds (YAGNI → reuse → stdlib → platform → installed dependency → one line), never simplify away validation, error handling or security. A non-default level rides the reminder (`hooks/tezgah_context.py:338-354`).
- **Output shape: ADHD-friendly.** The action or answer is the first line, multi-step work is a numbered list whose position is restated, an estimate is in concrete units. Two upstream rules were rewritten rather than imported verbatim because they collided with rules already in force: the state restatement points at the todo list instead of duplicating it, and a time estimate can no longer be read as a measurement (`CHANGELOG.md:1442-1445`, `.tezgah/plans/done/001-act-on-it-rule-and-level-switch.md:33-35`).
- **Deliver the whole ask; never the shortcut.** The request is a floor: no cheaper stand-in, no silent scope cut, no token gesture reported as done.
- **Integrity: evidence, or "doğrulanmadı".** A done/tested claim holds only if the check ran in this session and its output was seen; the mechanical half is enforced by [gate.md](gate.md).
- **Loop discipline.** Never repeat an identical failing command; three attempts is the ceiling, then report what is still unknown.
- **Lessons ledger: stop repeating mistakes.** `.tezgah/lessons.md` lines are standing constraints; the recent ones are injected at session start.
- **No AI attribution, ever, on any host.** Nothing persisted or published may name a model, vendor or "AI" as author, co-author, generator or helper; one already in pushed history is reported.
- **Identifiers and messages stay English.** A branch, a plan slug, a commit subject, a PR or issue title is in the repository - often a public one - from the moment it exists, so the gate refuses one that is not English - any non-ASCII letter, or a Turkish word from a curated list - and names the English to write instead (`hooks/tezgah_policy.py:788-792`, [gate.md](gate.md#language-an-identifier-or-message-that-is-not-english)). The word list behind it is a heuristic, not a language detector, and the rule says so where it refuses.
- **Session scope: the user's repo, not tezgah.** The session never maintains tezgah itself; a missing capability is one line plus the documented fallback.
- **Kill switches.** The switch list itself, so a session can tell the user how to disarm a rule it is asked to ignore; pinned against the shipped skill by `tests/test_skills.py:99-109`.

## Arming the conditional paragraphs, and the per-turn reminder

`PROMPT_HINTS` (`hooks/tezgah_context.py:82-294`) is one compiled pattern per key
— `spec`, `consult`, `research`, `product`, `graph` — and `classify_prompt()` returns the keys
a prompt matches (`hooks/tezgah_context.py:890-895`). On that turn only, the
matching paragraphs are appended after the reminder
(`hooks/tezgah_context.py:1277-1290`); a session that never asks such a question
pays the one-line pointer instead. The patterns carry Turkish stems because the
user writes Turkish, and a plain prompt arms nothing. The same prompt arms the
same rules on every host (`tests/test_context.py:1838-1860`) and each advisory
rule keeps a pointer line in the always-on text (`tests/test_context.py:1861-1870`).

`PROMPT_REMINDER` is the compact restatement of the invariants, about a third of
the long form and still inside the `<harness-reminder>` envelope the hosts and
tests look for (`hooks/tezgah_policy.py:853-873`), with its `{PONY_LEVEL}` slot naming a non-default ponytail level
(`hooks/tezgah_context.py:338-354`). The session-start text ends with the pointer
telling the model to load `tezgah-contract` for the deep detail
(`hooks/tezgah_context.py:1431-1432`), whose two appendixes apply only on a machine
missing the code graph or every consult option (`hooks/tezgah_policy.py:538-558`).

## How a rule is disarmed

A kill switch removes the rule's text, not just a status mark
(`hooks/tezgah_context.py:929-985`). `off()` checks `~/.config/tezgah` and the
legacy `~/.claude` (`hooks/tezgah_paths.py:46`, `:463-465`); the drop itself
happens in `core_split()`.

| Switch file | Rule it removes | Where the drop is implemented |
|---|---|---|
| `exec-mode.off` | `**Turkish, BLUF.**` | `hooks/tezgah_context.py:937-939` |
| `ponytail-auto.off` | `**Ponytail (minimal code).**` | `hooks/tezgah_context.py:940-943` |
| `adhd-off` | `**Output shape: ADHD-friendly.**` | `hooks/tezgah_context.py:944-946` |
| `spec-off` | `**Spec before building.**` | `hooks/tezgah_context.py:947-949` |
| `verify-off` | `**Integrity: evidence…**`, and the per-turn evidence-scope line with it | `hooks/tezgah_context.py:950-952`, `:1322` |
| `consult-off` | `**Consult before irreversible.**` | `hooks/tezgah_context.py:956-958` |
| `research-off` | `**Research: route it to OpenResearch.**` | `hooks/tezgah_context.py:959-964` |
| `orchestrate-off` | the orchestration section of the on-demand skill (there is no core paragraph) | `hooks/tezgah_context.py:965-966` disables it, `hooks/tezgah_context.py:1419-1421` injects "Orchestration is off", and the skill-ignore note is `hooks/tezgah_context.py:1257` |
| `reminder-off` | the per-turn reminder | `hooks/tezgah_context.py:1273-1274` returns `None` |
| `judge-off` | the judgement seam: the snapshot triage, the docs page fallback and the skill hint | `hooks/tezgah_judge.py:165` — `available()` is asked before any call, so an armed switch makes no request at all |
| `triage-off` | the snapshot triage alone (`bin/tezgah-triage`), leaving the docs fallback and the skill hint armed | `bin/tezgah-triage:120` — `off_reason()` answers this switch before the seam's, so the analyze-app loop reads the tree instead of paying for a judgement |
| `docs-judge-off` | the docs page fallback alone (`bin/tezgah-docs`), leaving the triage and the skill hint armed | `bin/tezgah-docs:177` — `off()` answers this switch first, so a query the index cannot place exits 1 with what it always printed |
| `lang-off` | `**Identifiers and messages stay English.**` | `hooks/tezgah_context.py:967-969` drops the paragraph; the gate's own check reads the same switch (`hooks/tezgah_gate.py:1298`) |
| `pretooluse-off` | the gate's denials, not a rule | [gate.md](gate.md) |
| `.no-ponytail` | `**Ponytail (minimal code).**` | `hooks/tezgah_context.py:940-943` |
| `.no-adhd` | `**Output shape: ADHD-friendly.**` | `hooks/tezgah_context.py:944-946` |
| `.no-graph` | `**Code discovery: graph first.**` | `hooks/tezgah_context.py:970-972` |
| `.no-lessons` | `**Lessons ledger: stop repeating mistakes.**` | `hooks/tezgah_context.py:953-955`, and the lessons block is not injected (`hooks/tezgah_context.py:1404-1407`) |

The last four are per-repo [marks](glossary.md#per-repo-mark), read by
`repo_marks()`, walking up to the enclosing [root](glossary.md#root)
(`hooks/tezgah_context.py:1605-1621`). Every switch that fired is named back to the
session at start (`hooks/tezgah_context.py:1256-1258`) and per turn (`hooks/tezgah_context.py:1331-1333`), with the instruction to
ignore the matching section in `tezgah-contract` — that skill is loaded
separately and would otherwise re-arm the rule. `tezgah-adhd off` writes the same
channel as the file (`bin/tezgah-adhd:19`); the ponytail *level* is not a switch.

`**Deliver the whole ask**`, the sycophancy ban and the attribution ban are
invariants: no switch touches them, and `tests/test_context.py:709-718` asserts
they survive every other switch being off.

## Adding a rule

1. Write the full text as a constant in `hooks/tezgah_policy.py`.
2. If not every session should pay it, add the key to `CONDITIONAL_KEYS`
   (`hooks/tezgah_policy.py:846-850`), a pattern to `PROMPT_HINTS`
   (`hooks/tezgah_context.py:82-294`) and a line to `POINTERS`
   (`hooks/tezgah_policy.py:851-856`); the two halves are asserted together
   (`tests/test_context.py:1861-1870`).
3. Put the paragraph in `CORE` with its bold label and add the `(key, label)`
   pair to `CORE_RULES` (`hooks/tezgah_context.py:304-323`). The label is the
   contract: `core_split()` matches paragraphs by it and `subagent_core()` builds
   the brief from it, so a label edit fails loudly instead of silently dropping
   a rule.
4. If the rule names a kill switch, add the drop to `core_split()` and list the
   switch in the `**Kill switches:**` paragraph (`hooks/tezgah_policy.py:803-812`).
5. Mirror the full text into `skills/tezgah-contract/SKILL.md`, and regenerate
   `output-styles/tezgah.md` from a fresh Python process when the paragraph is
   always-on — a warm interpreter serves a stale `CORE`.
6. Last step, the tests that pin it: add the label to `KillSwitchEnforcement`
   (`tests/test_context.py:674-900`) and, for a conditional rule, to the
   `ArmingConformance` label map (`tests/test_context.py:1801-1835`); then run the mirror pair —
   `OutputStyleMirrorsCore.test_body_is_the_always_on_core`
   (`tests/test_context.py:1989-1999`) and
   `ContractParity.test_every_rule_and_heading_in_the_contract_reaches_the_skill`
   (`tests/test_setup.py:799-809`).

## The two copies that must stay in step

| Copy A | Copy B | Test that fails when only one changed |
|---|---|---|
| `CORE`, via `always_on_core()` | `output-styles/tezgah.md` (Claude's hookless duplicate) | `tests/test_context.py:1989` |
| `policy.CONTRACT` (`hooks/tezgah_policy.py:851`) | `skills/tezgah-contract/SKILL.md` | `tests/test_setup.py:799` |

Drift between the source and what a host reads is caught on the rendered side:
`~/.config/tezgah/contract.sha256` holds one `<sha>  <path>` line per rendered
artifact (the managed blocks of `CLAUDE.md`, `AGENTS.md`, `RULES.md`, and
opencode's contract and skill routers), and `--report` compares each artifact's
bytes with a fresh render. That notices that the text a session gets changed;
`ContractParity` is what notices that only one of the pair above changed, which
is the drift that actually happens (`tests/test_setup.py:1297-1311`).
`tezgah-setup --refresh` re-renders every armed host's artifact, not only
opencode's, and drops the paragraph of any global kill switch that is on
(`refresh_contract`, `bin/tezgah-setup:1191-1208`).

## When the injected text grows too large

Each event has a byte budget: `session_start` and `post_compact` 12000,
`user_prompt` 6000, `subagent_start` 5000, anything else 12000
(`hooks/tezgah_context.py:1079-1081`). Each sits at about 1.5× the largest text
that event was measured to build in this repository, so it never fires on a
healthy repo and fires before a pathological one reaches the model; it is a byte
count, not a token estimate (`hooks/tezgah_context.py:1077-1078`).

Over budget, `budgeted()` gives up whole blocks in `DROP_ORDER`, lowest value
first — the text another surface already carries (project knowledge, the
sibling-checkout line, lessons, the plan table) first, then the tooling-availability lines and the live graph
glance, then the resume state (it outlives those because it is the only one that
says what this session was doing, and it still yields to a rule), then the
evidence-scope warning, the task phase, the delta, and the skill pointer last
(`hooks/tezgah_context.py:1082-1096`, `hooks/tezgah_context.py:1097-1100`). Any key absent from that tuple is
never dropped: the core, the reminder and the armed paragraphs are the rules, and
a budget able to spend them would turn bloat into rule loss. The note naming what
went is appended after the count, so the sentence explaining the trim cannot force
another one, and it says so when what remains is still over the limit
(`hooks/tezgah_context.py:1103-1117`); the drop is logged to `~/.cache/tezgah/context-drops.log`, truncated
to its last 200 lines (`hooks/tezgah_context.py:1118-1135`).

## Source of truth

- `hooks/tezgah_policy.py` — `CORE`, `CONDITIONAL_KEYS`, `POINTERS`, `PROMPT_REMINDER`, `CONTRACT`, and the long-form blocks they are built from
- `hooks/tezgah_context.py` — `CORE_RULES`, `PROMPT_HINTS`, `classify_prompt`, `core_split`, `core_for`, `always_on_core`, `subagent_core`, `context_for`, `repo_marks`, `CONTEXT_BUDGET`, `DROP_ORDER`, `budgeted`, `log_drop`
- `hooks/tezgah_paths.py` — `OFF_DIRS`, `off()`, the ponytail level path; `bin/tezgah-setup` — `install_common`, `opencode_contract`, `refresh_contract`, the omp `RULES.md` writer, `--refresh`; `bin/tezgah-adhd` — the CLI that writes the `adhd-off` switch
- `skills/tezgah-contract/SKILL.md` — the on-demand full contract; `output-styles/tezgah.md` — Claude's always-on duplicate of the core
- `tests/test_context.py`, `tests/test_setup.py`, `tests/test_skills.py` — the label, kill-switch, budget and mirror tests; `CHANGELOG.md` and `.tezgah/plans/done/001-act-on-it-rule-and-level-switch.md` — why two upstream rules were rewritten
