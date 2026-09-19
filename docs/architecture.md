# Architecture

This page answers one question: how tezgah is built, and what runs when a
session starts. It is written for the maintainer adding a rule, a [host](glossary.md#host)
or a [mark](glossary.md#mark), and for any session that has to reason about why
the thing behaved the way it did instead of re-deriving it from the Python. Read
it before [gate](gate.md), [evidence](evidence.md) or [hosts](hosts.md); those
pages assume the layers named here.

## One idea

tezgah is a working contract — rules about honesty, minimal code, and evidence —
written once as plain strings, injected into six coding-agent hosts, and backed
by two mechanisms that make the contract checkable rather than merely stated: a
[gate](glossary.md#gate) that refuses a tool call before it runs, and an evidence
[ledger](glossary.md#ledger) that records what actually ran so a "done" claim can
be contradicted. Everything else in the repository exists to keep those three
things — one text, one gate, one ledger — shared rather than copied.

## The layers, bottom-up

### `hooks/` — the shared Python core

The core is host-independent: it answers in tezgah's own vocabulary and knows
nothing about a host's event names or output envelope.

| Module | Owns | Point at |
|---|---|---|
| `tezgah_context.py` | the one builder of injected text; event normalisation to `session_start`/`user_prompt`/`subagent_start`/`post_compact`; the status segments and the used marks | `hooks/tezgah_context.py:2-6`, `context_for` `hooks/tezgah_context.py:735` |
| `tezgah_policy.py` | the contract itself, as strings: `CORE`, the conditional paragraphs, the pointer line, the per-turn reminder, and `CONTRACT` (the on-demand whole) | `hooks/tezgah_policy.py:2-11`, `CORE` `:485`, `CONDITIONAL_KEYS` `:643` |
| `tezgah_gate.py` | the tool gate: explorer refusal, the one-time grep nudge, attribution and test-disable denies, loop/retry ceilings, [consent](glossary.md#consent) | `hooks/tezgah_gate.py:2-27`, `decision` `:976` |
| `tezgah_integrity.py` | the evidence ledger, redaction, the anti-shortcut parser and the Stop rule | `hooks/tezgah_integrity.py:2-23`, `note_tool` `:974`, `stop_reason` `:1180` |
| `tezgah_paths.py` | where tezgah is armed: [roots](glossary.md#root), kill switches, the config dir, and the writable cache dir | `hooks/tezgah_paths.py:2-14`, `cache_dir` `:122`, `root_for` `:167` |
| `tezgah_snapshot.py` | pre-write bytes of every file a write is about to change, and the one explicit restore | `hooks/tezgah_snapshot.py:2-17`, `capture` `:190` |
| `tezgah_untrusted.py` | the untrusted-content label on a result from outside the user and workspace, and the taint notice on the next effect | `hooks/tezgah_untrusted.py:2-19`, `marks` `:81` |
| `tezgah_agents.py` | per-repo subagent definitions generated into each host that has an agent surface | `hooks/tezgah_agents.py:2-21`, `sync_root` `:509` |
| `tezgah_research.py` | the in-repo research workspace and the check that a protocol predates its results | `hooks/tezgah_research.py:2-27`, `check` `:406` |
| `tezgah_index.py` | the detached graph auto-index worker (flock-guarded, bounded retry) | `hooks/tezgah_index.py:2-11`, `main` `:27` |

`hooks/projects-*.py` are the Claude/dsh event entry points, not core: they hold
only the envelope (see the event sequence below).

### `hosts/<name>/` — the adapters

A host adapter translates one host's event names and output schema into the
core's vocabulary and translates the answer back. It contains no rule text and
no gate logic; the imports are the proof. Codex is the most readable example:
its hook maps `SessionStart`/`UserPromptSubmit`/`SubagentStart`/`PostCompact` to
the core's events (`hosts/codex/hook.py:35-40`), imports the builder, gate,
integrity and untrusted modules from `hooks/` (`hosts/codex/hook.py:21-33`), and
passes Codex's tool names through a translation table before calling the gate
(`hosts/codex/hook.py:45-53`, `gate_name` `:70`, `decision` at `:89`). omp is
the same split in another language: the TypeScript extension is "only the
bridge" and substitutes the absolute path of
the Python half (`hosts/omp/tezgah-hook.ts.in:3-6`), whose `handle()` dispatches
every event (`hosts/omp/hook.py:109`). Cursor (`hosts/cursor/hook.py:2-23`) and
opencode (`hosts/opencode/plugins/tezgah.js:1-42`) follow the same rule; opencode
is the one host whose plugin cannot call the core in process, so it shells out
through `bin/tezgah-context` and `bin/tezgah-capture` instead of copying it
(`hosts/opencode/plugins/tezgah.js:5-8,33-34`).

### `bin/` — the CLIs and the installer

`bin/tezgah-setup` is the installer and the only writer of host wiring: it arms
every detected host, regenerates the generated contract files and the subagent
sets, and reports what is armed (`bin/tezgah-setup:2-25`). The rest are the small
stable CLIs the contract cites by absolute path because a session shell has no
interactive PATH: `bin/tezgah-status` (the checklist in any host,
`bin/tezgah-status:2-14`), `bin/tezgah-consent`, `bin/tezgah-rollback`,
`bin/tezgah-capture`, `bin/tezgah-context`, `bin/tezgah-index`,
`bin/tezgah-agents`, and the optional `bin/consult` / `bin/codegen`.

### The surfaces

A surface draws the marks; it never decides them. `statusline.py` is the Claude
and Cursor status line, and resolves the checkout from its own symlink before
importing the core (`statusline.py:2-23`). `hosts/opencode/tui/tezgah-tui.tsx` is
the opencode TUI plugin, which is event-driven and shells out to
`bin/tezgah-status` rather than rendering its own segments
(`hosts/opencode/tui/tezgah-tui.tsx:1-17`). `hosts/dsh/statusline/lib/index.js`
serves the same line to the dsh Web UI behind dsh's own authenticated API, and
declares which measures that host can observe (`hosts/dsh/statusline/lib/index.js:1-18`).

## What runs when

One session, in order. Each step names the file that handles the event on Claude
(the reference adapter) and the core function it calls.

1. **SessionStart** — `hooks/projects-auto-init.py` (`hooks/hooks.json:2-4`) calls
   `context_for("session_start", …)` (`hooks/tezgah_context.py:735`), which builds
   the always-on CORE (`hooks/tezgah_context.py:568`) plus this repo's live state:
   the graph index status and the detached index spawn (`hooks/tezgah_context.py:179`),
   the open plans, the lessons ledger, and the active kill switches. Outside a
   configured root it returns `None` and the session is untouched
   (`hooks/tezgah_context.py:746-747`).
2. **UserPromptSubmit** — the same file, `context_for("user_prompt", …)`
   (`hooks/tezgah_context.py:756`): a turn marker for the loop guard, the per-turn
   reminder, the conditional paragraph(s) this prompt arms
   (`classify_prompt`, `hooks/tezgah_context.py:478`), one line naming what moved
   since the previous turn (`hooks/tezgah_context.py:426`), and the stale-index
   notice (`hooks/tezgah_context.py:1087`).
3. **PreToolUse** — `hooks/projects-pretooluse.py:24` calls `decision` and emits
   the deny envelope (`hooks/projects-pretooluse.py:25-30`). The gate is the same
   object on every host: `hosts/omp/hook.py:118`, `hosts/codex/hook.py:89`.
4. **PostToolUse** — `hooks/projects-posttooluse.py:61` writes the evidence row
   through `note_tool` (`hooks/projects-posttooluse.py:98`), records the used
   kind for the status line (`tezgah_context.record`, `hooks/projects-posttooluse.py:84`),
   and attaches the untrusted-content label when the result came from outside.
5. **Stop** — `hooks/projects-stop.py:33` calls `stop_reason`, which reads the
   ledger and can refuse the turn (`hooks/tezgah_integrity.py:1207`). omp and
   Codex reach the same function from their own Stop events
   (`hosts/omp/hook.py:163`).

`SubagentStart` and `PostCompact` reuse steps 1 and 2 with their own event key;
on `subagent_start` the payload is the short brief, not the whole CORE
(`hooks/tezgah_context.py:588`).

## The two-tier text model

| Tier | What it is | Assembled at | Paid |
|---|---|---|---|
| Always-on CORE | the rules every session carries: reply language, integrity, loop discipline, consent, attribution, scope | `hooks/tezgah_policy.py:486`, injected by `hooks/tezgah_context.py:568` | once per session |
| Conditional paragraphs | spec, consult, research, graph — armed by task class, for that turn only | `hooks/tezgah_policy.py:644`, armed at `hooks/tezgah_context.py:774-780` | the turns whose prompt matches |
| Pointer line | one line per conditional rule, so a host that never sees the paragraph still knows the rule exists | `hooks/tezgah_policy.py:649`, appended at `hooks/tezgah_context.py:574` | once per session |
| Per-turn reminder | the compact `<harness-reminder>` envelope | `hooks/tezgah_policy.py:655`, injected at `hooks/tezgah_context.py:772` | every user turn |
| On-demand full contract | the deep detail — orchestration, codegen, the exact kill switches — as a skill, not a hook payload | `skills/tezgah-contract/SKILL.md`, whose joined text is `CONTRACT` `hooks/tezgah_policy.py:674` | only when loaded |

A host that carries the CORE in a static file does not pay for it twice: omp's
managed `RULES.md` already holds it (`bin/tezgah-setup:1023-1025`), so its session hook
passes `with_core=False` and injects only the live state
(`hosts/omp/hook.py:123-128`, `hooks/tezgah_context.py:735-744`). opencode's
always-on file is written from the same policy by the installer
(`bin/tezgah-setup:556-560`). The
sum of every block is bounded per event, and when the bound is crossed the
lowest-value blocks are dropped in a fixed order rather than the rules
(`hooks/tezgah_context.py:665-667`, `budgeted` `:652`).

## State: where it lives, who writes it

| Store | Path | Writer | Authoritative for |
|---|---|---|---|
| Evidence ledger | `~/.cache/tezgah/evidence/<session>.jsonl` (`hooks/tezgah_integrity.py:230-231`) | `note_tool` from each host's PostToolUse (`hooks/tezgah_integrity.py:1001`) | what a session actually ran, and therefore the Stop verdict |
| Session store (used marks) | the chosen cache dir, `sessions/<session>.jsonl` (`hooks/tezgah_context.py:999-1001`) | `record` (`hooks/tezgah_context.py:988`) from every adapter | nothing evidential: a convenience channel for a surface that has no transcript |
| Snapshot store | `<cache dir>/snapshots` (`hooks/tezgah_snapshot.py:56-61`) | `capture` on the write path (`hooks/tezgah_snapshot.py:190`) | the pre-write bytes; the rollback source |
| Turn stamp | `<cache dir>/turns/<session>.json` (`hooks/tezgah_context.py:398-399`) | `write_stamp` (`hooks/tezgah_context.py:414`) | the comparison behind the one-line delta, nothing else |
| Installed config dir | `~/.config/tezgah` (`hooks/tezgah_paths.py:21-25`) | the installer and the user | which roots are armed, which kill switches are on |
| Plugin copy | `~/.claude/plugins/cache/<marketplace>/tezgah/<version>/` (`bin/tezgah-setup:1978-1986`) | `tezgah-setup --sync` (`bin/tezgah-setup:2003`) | what Claude Code actually executes — a copy, never this checkout |

The cache dir is resolved once per process and falls back to a temp dir on a
sandboxed host, so one session's state never splits across two files
(`hooks/tezgah_paths.py:112-140`). Per-repo state — `plans/open/`,
`.tezgah/lessons.md`, `.tezgah/research/` — lives in the repository, and the
checkout is the source from which the plugin copy is made.

## Invariants

- **One definition per concept.** The contract text lives only in
  `hooks/tezgah_policy.py`; adapters carry envelopes (`hooks/projects-auto-init.py:2-7`).
  Host-specific copies exist only where a host cannot load Python, and those are
  generated from the policy, not hand-kept (`bin/tezgah-setup:556-560`).
- **The root boundary.** Every hook is inert outside a configured root:
  `context_for` returns `None` (`hooks/tezgah_context.py:746`), the gate only acts
  inside one (`hooks/tezgah_gate.py:4`), and the status line is the single
  deliberate exception, because a globally loaded rules file must still show that
  it is armed (`hosts/omp/hook.py:32-34`).
- **No cross-host drift.** A host shares the core, never a copy of it. Adding a
  rule means editing the policy; adding behaviour means editing `hooks/` and
  letting every adapter inherit it.
- **The kill switch is the label.** Each always-on rule starts with a bold label
  and a switch drops exactly its paragraph, so a label edit fails a test instead
  of silently disabling a rule (`hooks/tezgah_context.py:67-86`).

## Source of truth

- `hooks/tezgah_context.py`, `hooks/tezgah_policy.py`, `hooks/tezgah_gate.py`,
  `hooks/tezgah_integrity.py`, `hooks/tezgah_paths.py`, `hooks/tezgah_snapshot.py`,
  `hooks/tezgah_untrusted.py`, `hooks/tezgah_agents.py`, `hooks/tezgah_research.py`,
  `hooks/tezgah_index.py`
- `hooks/hooks.json`, `hooks/projects-auto-init.py`, `hooks/projects-pretooluse.py`,
  `hooks/projects-posttooluse.py`, `hooks/projects-stop.py`
- `hosts/codex/hook.py`, `hosts/omp/hook.py`, `hosts/omp/tezgah-hook.ts.in`,
  `hosts/cursor/hook.py`, `hosts/opencode/plugins/tezgah.js`,
  `hosts/dsh/hooks.json`
- `bin/tezgah-setup`, `bin/tezgah-status`, `statusline.py`,
  `hosts/opencode/tui/tezgah-tui.tsx`, `hosts/dsh/statusline/lib/index.js`
- `skills/tezgah-contract/SKILL.md`, `README.md` (Supported hosts)
