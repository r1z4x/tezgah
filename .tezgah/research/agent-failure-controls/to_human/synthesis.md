# Synthesis: the five structural gaps and the smallest change that closes each

Design section, owned by the router. Every status claim cites E1/E2/E3 or a
file:line read this session; every literature mechanism cites a note in
`literature/`.

## Why the modes split the way they do

The measured split (E1: 7/7 write-time, 0/12 trajectory-time) is not an
oversight in the rule set; it is a property of the one surface that can refuse.
`tezgah_gate.decision` (`hooks/tezgah_gate.py:154-190`) reads a **single call's
arguments** and nothing else. Every covered mode is a violation *inside* one
call. Every uncovered mode is a property of one of five things the gate cannot
see:

| gap | what does not exist | modes that die on it |
|---|---|---|
| G1 no action identity | the ledger line is `{kind, ts, detail}` (`tezgah_integrity.py:113-124`); no id, no sequence, no argument digest, no structured exit status (`[exit=0]` is text inside `detail`) | the ten priority controls 1, 6, 7, 10; idempotency; replay |
| G2 nothing reads a sequence | `decision()` has no state except the once-per-session nudge; the ledger is written and never read on the PreToolUse path | same tool + same args repeated, wrong operation order, partial failure, concurrent writers, poisoned retry |
| G3 nothing inspects a result | `note_tool()` records the host's `failed` flag only (`tezgah_integrity.py:317-336`); no size, no content, no status field | exit-0-but-empty, queued/partial read as success, hidden failure, silent quality drop |
| G4 consent has no mechanical half | the rule is prose in `tezgah_policy.CORE`; E1 `p6`, `p7`, `p8`, `p12` pass the armed gate | unconsented force-push, branch delete, destructive command, dependency install, deploy |
| G5 input is not labelled untrusted | nothing distinguishes the user's prompt from a tool result, a file or an MCP response; `note_tool` writes the raw command with no redaction | prompt injection, unverified external content, secrets in the ledger |

Everything else in the report is a control that fits on top of one of these five.

## The changes, in dependency order

### 1. Give the ledger an action identity (G1) — S

One function writes every line (`note()`, `tezgah_integrity.py:113-124`, called
from `note_tool` and `_deny`). Add four keys: `seq` (monotone per session),
`digest` (sha1 of the normalised tool name plus its normalised arguments),
`exit` (int or null), `out_bytes` (int or null). Readers must tolerate lines
without them, which is the same forward-compatibility the file already needs.

This is the substrate for controls 1, 6, 7 and 10: a cycle detector needs
`digest`, a retry cap needs `digest` plus `exit`, a per-trace metric needs `seq`
and `out_bytes`, and any audit needs all four. Cost: one JSON key set and one
hash per tool call.

### 2. Redact and label before storing more (G5) — S

Before `detail` is written, redact credentials
(`(sk|pk|ghp|xox[baprs])-[A-Za-z0-9]{16,}` and
`[A-Za-z0-9_]*(KEY|TOKEN|SECRET|PASSWORD)[A-Za-z0-9_]*=\S+`) and record `trust`
(`user` | `tool` | `doc`) from the host payload. Landing this before step 4
matters: step 4 stores more of a tool result, and the corpus that motivates the
mode is raw secrets in traces (`literature/2608.07899.md`, telemetry sufficiency).
Cost: one regex pass over a ≤200-character string.

### 3. A sequence reader and the cycle rule (G2) — M

`last_verify()` and `kinds()` already replay the session ledger
(`tezgah_integrity.py:344-366`); a `prior_calls(session_id, digest)` reader is
the same loop. Then one gate branch: refuse a call whose `(tool, digest)` has
already appeared twice in the session, with a read-only allow-list so `git
status` stays legal. That is priority control 6 verbatim, and it lands the
contract's existing "three attempts on one failure is the ceiling" as a rule
instead of as prose.

The same reader answers partial failure: if the ledger already holds a
side-effecting `run` for the current step and the reply claims the workflow
finished while the newest `exit` is non-zero, the Stop gate has something to
check.

### 4. Record the result, and make the completion gate read it (G3) — M

`note_tool()` gains `exit` and `out_bytes`, and the Stop gate stops accepting a
completion claim whose only support is a verify event with `out_bytes == 0` or a
newest `exit != 0`. This is the local form of two published mechanisms:
stage-wise attribution of a tool failure at the moment the return enters context
(`literature/2608.22676.md`, `literature/2608.23635.md`), and the finding that
agents adopt corrupted or plausible-but-wrong tool returns at high rates
(`literature/2609.05587.md`: mean over a third, 68% for web search).

The stronger version of the same fix is a certificate: the reply's completion
claim must bind each required slot to evidence ids, in scope, with a replayable
transform — Evidence-Carrying Termination, which measured 0/288 unsafe
completions against 252/288 for a critic core (`literature/2608.23623.md`).
That is a larger change (a task contract per task) and is listed as the
direction, not as the next step.

### 5. A consent gate with a mechanical half (G4) — M

A verb table in the gate (`git push --force`, `push --delete`, `branch -D`,
`rm -rf` outside a temp path, publish/deploy/release, `terraform apply`, a
migration, a package install, `gh api -X DELETE`), plus a session flag the
prompt hook sets only when the user's own turn authorised that action. Refuse
when the verb matches and no authorising turn is recorded; hosts that cannot
block fall back to the prose rule, and the ledger marks the call either way.

The literature's version of this is an execution grant that binds intent to
boundary conformance (`literature/2609.11596.md`), a flow-centric policy
language (`literature/2608.22868.md`) and the compilation of natural-language
policy into checkable obligations (`literature/2608.23282.md`). All three agree
on the property tezgah lacks: the rule must be evaluable at the point of the
call, not stated in a prompt.

## Weaknesses to fix in the same pass

- **The gate fails open silently.** `note()` and `last_verify()` swallow
  `OSError` (`tezgah_integrity.py:121`, `:357`), so an unwritable cache disables
  the Stop gate with no signal. Distinguish "no ledger" from "no check ran".
- **`NEGATED` is unscoped** (`tezgah_integrity.py:383`): one word anywhere in
  the reply waives the rule. Scope it to the claim's sentence.
- **The claim patterns are a closed vocabulary**: 0/10 on state descriptions,
  and `succeeded` / `giderildi` missed (E2 `x3`, `x10`).
- **Host parity**: opencode re-implements the gate in JS and has no Stop hook;
  Cursor, dsh and omp wire no compaction event (`agent://ContextInjection`). The
  README's host table (`README.md:139-150`) lists what wires each host, not which
  rule stops firing there, so the gap is invisible to a reader of that table.
- **The ledger has no lock** while `tezgah_index` uses flock
  (`hooks/tezgah_index.py:32`); two writers on one session file can interleave.

## Shared primitives: one definition each

The group sections were written independently, so several of them propose the
same object under three names. These are the router's resolutions; a section that
needs one of them should reference this list rather than restating it.

**P1 - the ledger line.** One schema, extended once:

| key | meaning |
|---|---|
| `kind`, `ts`, `detail` | unchanged, as `note()` writes them today (`hooks/tezgah_integrity.py:113-124`) |
| `id` | the action id (P2) |
| `target` | the file path, repo slug, ref or URL the action names |
| `parent` | the id of the prior call in the same turn, for a reconstructable graph |
| `step` | monotone counter, derivable from the ledger length |
| `digest` | sha1 of the normalised tool plus its normalised arguments |
| `exit` | `0` / `1` / `null` (never a `[exit=0]` string inside `detail`) |
| `out_bytes` | bytes the call returned, `null` when the host exposes none |
| `fail_class` | `transient` / `permanent` / `unknown` |
| `trust` | `user` / `tool` / `doc` (P5) |
| `ms` | interval since the previous event, because no host reports a call's own duration |
| `workspace` | realpath of `root_for(cwd)` |

F4's `(turn, step, tool_call_id, reply_sha256)` and G10's
`id/step/outcome/fail/ms` are both satisfied by this table; neither should write a
second schema into `evidence/<slug>.jsonl`. Two writers exist: Python `note()`
and the opencode plugin's `recordEvidence` (`hosts/opencode/plugins/tezgah.js:215-235`),
so any field added here has to be added in both.

**P2 - the action id.** `sha256(tool + canonical(args) + repo_slug + session_id)`,
computed in `decision()` before the rules run; `canonical()` is the argv list the
existing tokenizer already produces (`hooks/tezgah_context.py:540-563`) for shell
tools and the raw payload field otherwise.

**P3 - the consent record.** One object, not three: A mode 3's consent set, B mode
7's one-shot lease, E mode 1's session mark and G control 3's `consent` row are
the same thing - a row naming the effect class and the resource, minted only from
the user's own turn (the prompt hook already reads it,
`hooks/tezgah_context.py:278-288`), consumed by the action it authorises, and
expired at the end of the turn unless the user's sentence named the resource
again. Bound to the turn, not the session: a session-scoped mark with no clear
path denies legitimate work for the rest of the session, which is the failure the
E verification pass found in the untrusted-read design.

**P4 - the attempt counter and its ceiling.** Keyed on `(tool, digest)`, counted
from the ledger rows, reset per user turn. Ceiling: **2 attempts when the
`fail_class` is `transient`, 1 when it is `unknown` or `permanent`** - the user's
own number for the transient case, and no third identical attempt in any class.
F mode 6's "deny the third", G control 6's "two prior rows" and G control 7's
"cap 2 / cap 1" collapse into this one rule.

**P5 - the trust label.** Every event carries `trust` (`user` / `tool` / `doc`)
and the reply's claims are scoped to the events behind them. This is the only
form of the untrusted-input control reachable today, because no hook receives the
assembled prompt: the label rides the ledger, it does not ride the text the model
reads.

## What this study does not establish

- **Nothing about work quality.** No experiment here measured whether a control
  changes what an agent does; E1 and E2 measure whether the rule fires. The
  2026-09-16 clause study's caution stands: a rule the model would honour anyway
  produces a null, so a control's value has to be measured on an AP-Acc-shaped
  task (`docs/research/2026-09-16-tezgah-quality.md`).
- **Coverage counts are per corpus.** The twelve uncovered E1 cases establish
  the absence of a rule for those inputs, not for every possible input.
- **The group sections are design, not measurement**, except where they cite
  E1/E2/E3 or a file:line.
- **The literature is a 41-source retrieval sample**, not a systematic review;
  the index names every source and the two OpenAlex reviews whose full text was
  not read.
