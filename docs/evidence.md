# Evidence

This page is the evidence layer: the [ledger](glossary.md#ledger) a session appends to, the kinds it
holds, the Stop rule that reads them to refuse a turn, and the pre-write snapshots a bad write can be
undone from. Read it before changing a rule that records or reads evidence, or when undoing a write.
[gate.md](gate.md) owns the refusal path, [hosts.md](hosts.md) what each host can observe.

## The ledger

One append-only JSONL file per session at `<cache>/evidence/<slug>.jsonl`; the stem is a readable
prefix plus a hash of the session id, so a filename can never be turned back into one
(`hooks/tezgah_integrity.py::_slug`). Every writer goes through `note_path` (`hooks/tezgah_integrity.py::note_path`): `note()`
derives the path from the session id (`:760-770`). The row is built in exactly one place (`hooks/tezgah_integrity.py::note_path`), and its shape is
`{"kind": …, "ts": …, "v": …, "detail": …}` plus whatever `LEDGER_FIELDS` keys the writer knew — for a check
the host reported passing, `{"kind": "verify_ok", "ts": 1758000000, "v": 3, "detail": "pytest -q",
"id": "a1b2c3d4e5f6", "exit": 0, "out_bytes": 4312, "tool": "Bash", "repo": "/home/u/proj"}`. `v` names the shape the row was written under
(`ROW_VERSION`, `hooks/tezgah_integrity.py::ROW_VERSION`), and a reader folding a corpus across a version
change has to know what moved: at 2 the step vocabulary gained `interrupted`, so a version 1 row's
`verify_fail` may name a check that failed or a call the host stopped; at 3 a `claim` row is written
only for a reply in the claim vocabulary, so a version 2 `claim` row may be a work-only refusal.

`kind` is the event kind, `detail` is free text (the command, a path, a short reason) and `ts` is
epoch seconds. A **write row's** `detail` is the path the call wrote, from the gate's one reader of
every host dialect (`write_paths`, `hooks/tezgah_gate.py::write_paths`): `file_path`, `filePath`, `path`,
`notebook_path`, or an `apply_patch` body's first `*** Update File:` header — the paths
`changed_files()` (`hooks/tezgah_integrity.py::changed_files`) folds when a reader asks which files a session changed. `detail` is
credential-redacted **before** it is stored, over the whole text, and
truncated to `DETAIL_MAX = 200` only afterwards, so a marker the cut halves still reads as a marker
(`:625-650`, `hooks/tezgah_integrity.py::DETAIL_MAX`, `hooks/tezgah_integrity.py::_stored_text`): a named key keeps its name and loses its value - also as a quoted
JSON key (`"password": "x"`) and as a flag with its value after a space (`--password X`,
`--api-key X`, `mysql -pPASS`) - an `Authorization` scheme (`Bearer`, `Basic`, `Token`, `Digest`),
the password of URL userinfo (`scheme://user:pass@`) and of `-u user:pass`, and a prefixed token
family lose theirs (`:580-624`; audit L-6, which found each of those stored verbatim). The optional fields are exactly `LEDGER_FIELDS`
(`hooks/tezgah_integrity.py::LEDGER_FIELDS`) — `id`, `exit`, `out_bytes`, `fail_class`, `workspace`, `source`, `hash`, `changed`, `tool`,
`target`, plus the reply-shape names `lines`, `chars`, `items`, `longest_list`, `tr_share`, `answer_first` and the compaction
row's `summary_chars`, `summary_hash`, `constraint_found`, `constraint_expected`, the `attest`
row's `host` and `switches` and a `claim` row's `harness` — and
a key outside that set is dropped, a `None` value left out, because every reader treats a missing key
as `None` (`:784-786`). `tool` is the call's own name (`Bash`, `Write`, `mcp__codegen__status`),
written by `note_tool` (`hooks/tezgah_integrity.py::note_tool`) because `classify` folds the name into
a kind and drops it; it is what `_counts`' tool histogram counts and what the retirement report on
`tezgah-status --counters --trend` prints. `target` is on every `edit` row: the written path as an
absolute real path, resolved against the call's cwd (`_abs_target`, written by `note_tool` and by
opencode's plugin through `absTarget`). `detail` keeps the path as the call spelled it, so
`README.md` in two repositories was one file to the concurrent-write guard; `writers_elsewhere`
now compares `target`, and a row without one (written before the field landed) is ignored by that
guard rather than matched by its spelling (audit M-6). Both writers write `tool` — `note_tool`, and opencode's
plugin, whose row carries the same field under the same empty-means-absent rule
(`hosts/opencode/plugins/tezgah.js:813-821`) — so no live host leaves it out. A row written *before*
the field landed names its tool only where the name survived in `detail` — an `unknown` row and an
MCP `external` row — so the one cause of an under-count is the corpus's age, and it shrinks as
sessions run. The append is one locked line, an exclusive `flock` with a 1 s bound falling
back to an unlocked write (`:717-765`), and is best effort: a write failure is never the caller's.
A ledger is created `0600` in a `0700` directory, because its rows name the paths and commands of
the user's work (audit L-6 found them `0644`). A reader that walks *other* sessions' ledgers (the
race guard, the counters) skips one that does not parse instead of raising, so one damaged file
cannot turn the write gate off machine-wide; the session's own ledger still refuses a damaged row
(`_foreign_rows`; audit M-7).

What never reaches the ledger: tool result bodies (only `out_bytes`, a size,
`hooks/projects-posttooluse.py::result_size`), the prompt text (the `turn` row keeps `sha1(prompt)[:12]`,
`hooks/tezgah_integrity.py::note_turn`), read/search calls (`hooks/tezgah_integrity.py::note_tool`), and any credential, already replaced.

## The kinds, by what reads them

A bare `:N` below is `hooks/tezgah_integrity.py`; `classify` (`hooks/tezgah_integrity.py::classify`) picks the kind for a call —
a write tool is `edit`, a shell call is `verify` when its command matches the check vocabulary `VERIFY`
(`hooks/tezgah_integrity.py::VERIFY`) and `run` otherwise.

| Kind | Written by | Read by |
|---|---|---|
| `turn` | `hooks/tezgah_integrity.py::note_turn`, from the prompt path | `hooks/tezgah_integrity.py::_turn_start`, scoping every turn rule; `hooks/tezgah_integrity.py::_claim_key` |
| `run`, `edit`, `verify`, `verify_ok`, `verify_fail`, `interrupted` | `hooks/tezgah_integrity.py::note_tool`, the call's own name in `tool`, on opencode the plugin writes these same kinds and the same field (`hosts/opencode/plugins/tezgah.js:773-831`) | the Stop rule's `worked` set `:3629`; `counters.steps` `:1547-1548`; `last_verify`/`partial_state`; the `--trend` tool histogram |
| `external`, `unknown` | `hooks/tezgah_integrity.py::note_tool` | the taint notice, via `source`; the `--trend` tool histogram; nothing counts them as work |
| `began` | the gate's allow path for a write or shell call `hooks/tezgah_gate.py::decision`; on opencode the plugin's before-hook when the core was not asked (`hosts/opencode/plugins/tezgah.js:2239-2255`) | `hooks/tezgah_integrity.py::unanswered`, behind a claim in the Stop rule and in `counters.unanswered` |
| `claim` | `hooks/tezgah_integrity.py::stop_reason`, only for a reply in the claim vocabulary - a completion or verification word (`DONE`/`VERIFIED`), blocked or allowed, or a refused claim about an external system's state (`_external_claim`) | `hooks/tezgah_integrity.py::counters` |
| `refusal` | `stop_reason`, for a blocked reply that claimed nothing - a work-only or a shape refusal - with the same `blocked: <class>` detail (row version 3) | `counters.refusals`, and `shape_blocked` for a shape class; never a claim; `NOT_TOOL_HOOK` lists it |
| `after_block` | `hooks/tezgah_integrity.py::stop_reason`, on the reply after this rule's own block (`stop_hook_active` in a turn holding a `blocked:` claim or refusal row) on Claude, Codex and omp; `detail` is `would block: <class>`, `ok` or `no claim` | nothing yet: a record for the after-block observation window, not a claim and not a second `shape` row, so `counters` counts it neither as a claim nor as a reply; `NOT_TOOL_HOOK` lists it |
| `subagent_end` | `stop_reason(..., subagent=True)`, from Claude's SubagentStop (`hooks/hooks.json`) and Cursor's subagentStop `summary`; the evidence half only, never a block (ADR 011); `detail` as `after_block`'s | nothing yet: the rows plan 055 replays before a subagent end may block; `NOT_TOOL_HOOK` lists it. On Claude a subagent's tool rows sit in the parent's ledger, so until the agent key (plan 050) lands the row judges the parent's turn |
| `deny`, `nudge` | the [gate](gate.md)'s `hooks/tezgah_gate.py::_deny`, first-nudge `hooks/tezgah_gate.py::decision` | `hooks/tezgah_integrity.py::counters` |
| `snapshot`, `rollback` | `hooks/tezgah_snapshot.py::_capture_one`, `:277-280` | `hooks/tezgah_integrity.py::_snapshot_hash`; no counter |
| `compact` | `hooks/tezgah_integrity.py::note_compaction`, from the post-compaction path (`tezgah_context.remember_compaction` `hooks/tezgah_context.py::remember_compaction`) | `hooks/tezgah_integrity.py::_counts` (what `counters` folds with) |
| `lesson` | `hooks/tezgah_context.py::note_lesson`, one row per lesson the budget left in a session block or a per-turn block, with its 8-hex `key` and `block` (`session` or `turn`), inside the host's `safe()` like the rest of the prompt path | no counter; `hooks/tezgah_context.py::NOT_TOOL_HOOK` keeps it out of `hooks/tezgah_context.py::_ledger_since`, so a session of lesson rows still reads as a gate that never ran |
| `attest` | `hooks/tezgah_attest.py::run`, once per session start: Claude and dsh (`hooks/projects-auto-init.py::main`), Codex, Cursor and omp from their session-start events, opencode at the first message through `oncePerSession` (`bin/tezgah-context::main`). `detail` is `ok`, `drifted: <entries>` (an entry added, removed or changed since install, a hook file any user can write, a stale omp bridge, a changed entry script on a release install) or `unverified: <why>`; `host` names the host, `switches` the kill switches present. The module is imported only inside that call, so a broken one costs the row and never a gate | the `drift` status mark and the `harness` field of the session's later `claim` rows, read from one mark file per session and host (`hooks/tezgah_attest.py::drift_mark`, so one host's clean start cannot clear another's) - an annotation, never a Stop block; `NOT_TOOL_HOOK` lists it, so a session start after a compaction does not read as a gate that ran |
| `crash` | `hooks/tezgah_guard.py::safe` for a core call that raised, and `hooks/tezgah_guard.py::import_failed` for an entry point whose core imports raised (`detail` `import: <class>: <message>`). An import failure also writes one stderr line and the status line's `crash` mark, always; when `tezgah_integrity` or `tezgah_paths` is the module that failed, the row is the part that cannot be written. Hooks fail open with exit 0; `tezgah-gate check` exits 3 | `NOT_TOOL_HOOK` lists it; no counter |

**`compact` is what a compaction kept, from the record.** When the host hands the PostCompact
payload the text the model is about to receive — Claude's `compact_summary` — the shared path
(`hooks/tezgah_context.py::context_for`, reached by Claude's hook, codex/hook.py, omp's hook and dsh's
bridge alike, because it is the same funnel each prompt goes through) writes one row: the summary's
length (`summary_chars`), a 12-hex sha256 of it (`summary_hash`, so two compactions of one session can
be told apart and the same summary can be recognised twice), the host's own word for why it compacted
(`trigger`: `manual` or `auto`) on `detail`, and the constraint report. The summary's **text is never
stored** — it is the whole conversation by proxy and the ledger is a redacted channel — so a row can
never be read back as prose. The constraint report is `constraint_found` of `constraint_expected`: how
many of the fixed sentences tezgah injects the summary still carries, counted against the very text the
block renders (`constraint_lines`, `hooks/tezgah_context.py::constraint_lines`, over `POINTER_LINE`
`hooks/tezgah_context.py::POINTER_LINE` and the active plan's front matter). It is a **report and never a refusal**: a compaction
that dropped a rule is a finding to report, not a turn to block. A host that hands no summary writes no
row, and `tezgah-status --counters` folds the rows into `compactions`, `compact_chars` (the newest
summary's length) and `compact_constraint_rate` — which stays `None` until one row carries both counts,
because a `0.0` would claim every compaction dropped every rule.

**`interrupted` is the step with no verdict.** The host said the call was *stopped* — a user's cancel,
or a call a policy denied before it ran — rather than reporting anything the tool answered, so the row
carries no `exit` and no `fail_class` (`note_tool()`, `hooks/tezgah_integrity.py::note_tool`, the fields
`hooks/tezgah_integrity.py::note_tool`). It counts as a step, because the model did issue the call and the turn's work has to
show; it is not a failed check, so `_partial_state`, `last_verify`, the error rate and `prior_calls`'
attempts (`hooks/tezgah_integrity.py:1047-1055`) all read it as a stopped call rather than a rejection.

**`began` opens a call.** The gate writes it when it
lets a write or shell call through, with the call's `id`. The PostToolUse row of the same call carries
the same `id` and answers it. A `deny` with that `id` answers it too: opencode asks the core first and
may still refuse the call with a rule of its own. A `began` row nothing answered is a call whose result
never reached the ledger. The host abandoned it, the user refused its prompt, or the post hook died. So
its outcome is unknown in both directions. It is never a pass, a success or a failure. It is not work
either. The gate writes it before the host's own permission layer, so a command the user refused
leaves one too. Such a turn did nothing, and its bookkeeping exemption stands. The row counts in one
place only: a reply that claims done or tested while a waiting call is a check. The gate marks that
on the row as `check`, read from the whole command, because the stored detail is cut at 200 characters.
That claim rests on a result nobody saw, so the Stop rule asks for a passing check (`no verify_ok`).
One answer closes one `began`, oldest first (`_began_fold`). A waiting call counts only
for a tool the host answered once in the session (`unanswered`). Some hosts gate a tool they never
report back: omp gates `powershell` and does not watch it. The cost is one miss: the session's first
call of a tool goes uncounted if the host abandons it. A ledger written before the row existed has
none, so it counts zero. The idea is gortex's: it abandons a call that overran, and the call's side
effect stays unknown until someone re-reads it.

**A shell call's `id` folds ASCII whitespace only.** Both `call_id` and `actionID` fold such runs
into one space (`hooks/tezgah_integrity.py::ID_SPACE`).
Python's `split()` and JS's `\s` disagreed on U+0085, U+001C-001F and U+FEFF, so a `began` row and its
outcome hashed apart. U+00A0 is no longer whitespace to either side. A command holding it hashes
differently from rows written before this change, which only matters to the repeat guards' history.

**The verify kinds are a tri-state, and an unread outcome is never a pass.** `note_tool`
(`hooks/tezgah_integrity.py::note_tool`) records `verify` when the host reported no outcome at all (`failed is None`) or when
the command is piped — a pipe's status belongs to its last stage, so `pytest | tail` proves nothing
about pytest — and only otherwise splits it into `verify_ok`/`verify_fail`. A line that opens with
`set -o pipefail` (or `set -euo pipefail`) and carries no `||` is not piped for this purpose: the
pipe's status is then its first failing stage's, so the host's verdict is the check's
(`hooks/tezgah_integrity.py::pipe_hides_status`, read at `hooks/tezgah_integrity.py:2781`). `passing_check`
(`hooks/tezgah_integrity.py::passing_check`) is stricter: a `verify_ok` counts only with `exit == 0`, a non-zero `out_bytes` (exit
0 with an empty result is the classic silent failure) and no pipe owning the status. The gate refuses the
trimmed form before it runs ([gate.md](gate.md), the `piped` rule). The `out_bytes` half
bites only where the host reported a result size — Codex (`hosts/codex/hook.py::main`), Cursor
(`hosts/cursor/hook.py::remember_answer,275`) and omp, whose bridge measures it and sends `result_len`
(`hosts/omp/tezgah-hook.ts.in:627-631`), now do — and 6 of 1423 `verify_ok` rows across 1454 local ledgers carry the field
(measured 2026-09-19), so an absent field still passes: the guard narrows a check whose
result was measured empty, it does not require the measurement. `last_verify`
(`hooks/tezgah_integrity.py::last_verify`) folds the ordered rows to `ok`/`fail`/`ran`/`None`, because a set cannot tell a failure
that came after a success from one that came before it.

**A check-shaped command is a check only when it checks something.** `_check_runs` reads each
`VERIFY` match. It reads the words after the match, up to the end of that one command. An information
form checks nothing: `--version`, `--help`, `--list`, `--collect-only`, `make help`, `just help`
and a bare `ruff`. It records as `run`. A formatter in its write mode records as `run` too:
`ruff format` without `--check`/`--diff`, `ruff check --fix`, `prettier --write` and `eslint --fix`.
The freshness fold reads that row as a change (`_change_row`), with no captured target.
`pytest --version; pytest -q` still runs a check. Every reader of `verify_command` follows. That
covers the evidence kind, the gate's retry exemption, its `began` `check` mark, `piped_check` and
the neuter rule. Opencode's `verifyCommand` carries the same three tables.

A check can say in its own output that it ran nothing (`EMPTY_RUN`): `collected 0 items`, `no
tests ran`, `Ran 0 tests` or `No tests found` at a line start. The reader scans the result's last
4096 characters. Such a row records as `verify` with `empty_run`, never as a pass. One result
covers the whole call, so `pytest a && pytest b` with one empty suite marks the whole row empty.
That is a ceiling: the reader does not split the output per check. Claude, Codex
and Cursor read the result they already hold. The omp bridge keeps its own copy of the literal
and sends only the flag, never the body. `tests/test_omp_extension.py` pins the two copies equal.
A check row also carries `repo`, the git toplevel it ran in, read with no git fork. Only an
explicit location sets it. That is the tool's own `cwd` or `workdir`, or a leading `cd X`, also
after a paren or assignments. Path arguments that all sit in one repository count too. The
session cwd alone does not, because a shell may keep an earlier call's `cd`. An unreadable
`cd "$WT"` gives no `repo` either.
A row without one binds as before, so an unknown location never refuses. The Stop rule reads it
below.

**`edit` carries the write's after-state.** The gate's capture records the pre-write hash;
`_post_write` (`hooks/tezgah_integrity.py::_post_write`) adds `hash` (the target's sha256 once the host returned) and `changed`
(whether the two differ), so a call the host reports as a successful write need not have changed
anything. `changed_files` (`hooks/tezgah_integrity.py::changed_files`) reads exactly those rows.

**`claim` is the false-completion record.** `stop_reason` (`hooks/tezgah_integrity.py::stop_reason`) writes one row per reply per
turn that is in the claim vocabulary, deduplicated by `_claim_key` (`hooks/tezgah_integrity.py::_claim_key`), with detail `blocked: <class>` or `ok`: a refusal
and an allowed claim are both recorded, because the rate needs both halves. A blocked reply that
claimed nothing writes a `refusal` row instead. A `blocked: no verify_ok` row of either kind
carries `cause`. It reads `no check` when none ran and `outcome unread` when one ran without a
visible pass. **`external` and
`unknown` claim no step of work.** `external` (`hooks/tezgah_integrity.py::note_tool`) is a result with no work of its own — an
MCP answer, a fetched page — recorded so its provenance is on the ledger at all; an MCP row's
`detail` is that channel followed by the tool's own name, because the UI rule has to be able to tell
a screen read from a file read and the taint notice reads the channel from `source` either way.
`unknown` (`hooks/tezgah_integrity.py::note_tool`) is a tool name no list knows, its name in the `detail`. The step counter,
the Stop rule and the loop ceilings ignore both.

## What a source has to record before its numbers count

A row is not evidence by itself: what a reader can do with it depends on how much
the thing that produced it recorded. The RL-environment tooling this repository
has read makes the same distinction at the model wire - a server that will not
return token ids can still serve rollouts, but they are marked *evaluation only*,
and asking one of them for training data raises instead of quietly returning a
weaker sample (FineEnvs multi-harness RL, its OpenEnv chapter, "What gets
recorded").

tezgah's version of that rule is already enforced in the research layer and is
stated here for the first time. A [claim](research.md) carries a `kind` and a
`proof` that names an artifact a reader can open, and the one case the claim
checker leaves out is a proof that names no artifact at all
(`hooks/tezgah_research.py::derive_kind`) - it is reported rather than labelled, because a
guessed kind would only move the refusal one step later. A source that cannot
meet the rule does not become a weaker claim: it is labelled for what it is, and
the work that produced it is the work that has to be redone.

## The Stop rule, end to end

The checker is `_stop_block` (`hooks/tezgah_integrity.py::_stop_block`), reached through `stop_reason`
(`hooks/tezgah_integrity.py::stop_reason`). Four hosts block on it — Claude (`hooks/projects-stop.py:41-49`), Codex
(`hosts/codex/hook.py:189-194`), Cursor (`hosts/cursor/hook.py:356-361`), omp
(`hosts/omp/hook.py:217-221`) — all with `{"decision": "block", "reason": …}`, all inert outside a
[root](glossary.md#root) and under the `verify-off` [kill switch](glossary.md#kill-switch)
(`hooks/projects-stop.py::main`). On Claude, Codex and omp the rule judges the reply after a block
(`stop_hook_active`) once more, in record-only mode. That reply writes one `after_block` row and
never meets a second refusal. It writes nothing when the turn holds no refusal of this rule, since
another Stop hook may have blocked. Cursor still skips it. Ten triggers, in order, each naming its reason class (`_stop_block`
`hooks/tezgah_integrity.py::_stop_block`).
The first four judge how the reply is written (`_shape_block`, `hooks/tezgah_integrity.py::_shape_block`); the rest judge its evidence:

1. **placating opener** — the reply opens by agreeing or apologising (`hooks/tezgah_integrity.py::SYCOPHANT`).
2. **forbidden closer** — the reply's last prose line is one of the sign-offs the output contract bans (`CLOSER`, `hooks/tezgah_integrity.py`): the same rule read at the other end, with its own class so the ledger says which end fired.
3. **list cap** — a contiguous list runs past `LIST_CAP` = 5 items (rule 8 of the `i-have-adhd` skill). `longest_list` (`hooks/tezgah_integrity.py::longest_list`) counts per run of column-0 items of one kind: a heading, a prose line, a table row, a fence, a marker switch or a numbered list restarting at 1 ends the run, and blank or indented continuation lines keep it. Two headed groups of four pass; a 5+ enumeration that must stay whole goes under headings or into a table, which the block text says.
4. **reply language** — the reply's prose is not Turkish: at least `LANG_MIN_WORDS` = 25 prose words and under `LANG_MIN_SHARE` = 6% of them Turkish. `prose_words` drops fences, table rows, inline code, URLs, paths and identifiers first; `turkish_share` counts a word with a Turkish letter or one of `TR_WORDS` (`hooks/tezgah_integrity.py::TR_WORDS`).

The four shape classes share their switches with the text they enforce: `adhd-off` or a repo's `.no-adhd` lifts 1–3 (`_adhd_armed`, `hooks/tezgah_integrity.py::_adhd_armed`), `exec-mode.off` lifts 4, and a session whose environment carries `TEZGAH_NESTED` (an agent CLI consult started, whose English answer is read by code) is not judged for shape at all. A subagent's reply is never refused: omp's `session_stop` does not fire for task sessions, and a Claude SubagentStop or Cursor subagentStop leaves a record-only `subagent_end` row judged on the evidence half alone (ADR 011). The thresholds were set on the owner's omp transcripts (2026-09-27: 1,495 assistant replies with at least 25 prose words): English prose scored 0.000–0.026, the most English-heavy Turkish reply 0.077 and the bulk 0.3–0.7, and 24 of the 1,495 fall under the cut, all English or Chinese prose. The trade-off is on the Turkish side: a Turkish reply that is mostly quoted English outside backticks can fall under 6%, and the block text tells the model to put the English in backticks or a fence. `tests/test_integrity.py` `ReplyShapeCorpus` pins which realistic replies pass and which block. A lead that announces what follows (`preamble-open`) stays report-only: "Sonuç:" over a list is an answer label and reads like a preamble to any regex.

5. **check failed** — the newest check in the session failed (`:3740-3744`).
6. **partial failure** — this turn recorded a `verify_fail` and nothing passed since (`:3402-3411`).
7. **stale evidence** — the newest check that passed ran before the newest write the gate saw change
   the tree, so it verified an earlier revision of it (`_last_pass`/`_last_change`/`_stale_paths`
   `hooks/tezgah_integrity.py::_last_pass`, `hooks/tezgah_integrity.py::_last_change`, `hooks/tezgah_integrity.py::_stale_paths`, branch `hooks/tezgah_integrity.py::_evidence_block`). A write counts as a change whether the gate saw it as a
   write tool or as a shell command that redirected into the file - `_change_row` (`hooks/tezgah_integrity.py::_change_row`) reads
   an `edit` row, a `run` row whose captured target moved, or a formatter's write mode - while a `verify*` row never does, so
   a check redirecting its own log cannot stale itself. A write *outside* the workspace is not one
   either: the fold's subject is the tree this reply is about, so `_post_write` records no
   after-state for a target beyond the call's own root - a commit message in `/tmp` written after a
   green suite is not a revision of that tree, and reading it as one refused an honest turn.
   The fold dates a pass from the moment its check STARTED: its gate-written `began` row, paired
   by `id`. A write that landed while the check ran is therefore newer than the tree it read. A
   pass also counts only in the newest change's own repository. The fold compares the check row's
   `repo` with the toplevel of the `edit` row's `target`. So `cd ../other && pytest` licenses no
   change here. A row with no `repo` binds to nothing. That covers an old row and a host that sent
   no cwd. A change with no `target`, such as a shell write, binds to nothing too.
8. **no verify_ok** — this turn recorded a step (`edit`, `verify`, `verify_fail`, `run`,
   `interrupted`) and no check passed in the session (`:2764-2775`). A turn with no step at all
   has only its words as the trigger. There a claim word inside a question or under a negation in
   its own clause is no claim (`asserted_claims`). Examples: "testler geçti mi?", "is it done?",
   "not tested yet", "tamamlandı değil". "Tamamlandı, push edeyim mi?" still claims.
9. **no ui_ok** — this turn changed a UI source (`hooks/tezgah_integrity.py::UI_PATH`) and the
   check that passed was not one that sees the screen: a unit run never does. A browser/e2e/visual
   check (`hooks/tezgah_integrity.py::UI_CHECK`) or a read of the rendered screen (`UI_TOOL`
   `hooks/tezgah_integrity.py::UI_TOOL` for the app-analysis tool names, `hooks/tezgah_integrity.py::UI_TOOL_CMD` for the
   CLI capture) is the evidence this class asks for, and it has to be newer than
   the UI write it is about - not than the newest write of anything, so an unrelated file written
   after the screen read does not stale that read (`hooks/tezgah_integrity.py::_ui_evidence`,
   branch `hooks/tezgah_integrity.py::_evidence_block`). The write kinds are the freshness fold's own (`_change_row`: a write tool's
   `edit` row or a shell call's `run` row the gate saw change the tree), so a UI source written
   through a redirect owes the same proof. The MCP half of that proof is read off the row's own
   tool name (`hooks/tezgah_integrity.py::_screen_read`), which is the only field that
   says which call a row was - so a row that merely names a browser tool in its command
   (`rg -n browser_snapshot docs/`) is not a read of anything; the CLI capture and the two checks
   are read at a command position on the masked text, `re.M` so that a command on its own later
   line of the same call counts. A component turn owes one thing more: when a changed UI source is
   a component rather than a screen (`hooks/tezgah_integrity.py::DESIGN_COMPONENT` - a file
   under a component/views/widgets
   directory, or a name that carries the convention on its own), a fresh read of the screen is not
   enough by itself and a `tezgah-design check` row has to be newer than the component write it
   judges (`hooks/tezgah_integrity.py::_design_evidence`, branch `hooks/tezgah_integrity.py::_evidence_block`) - and it has
   to be a check whose pass was seen (`passing_check`, `hooks/tezgah_integrity.py::passing_check`), because
   a screenshot says what a component looks like and the contract is the only thing that says whether
   it is on the repository's floor. The refusal names the command to run. Both of the checker's verbs
   are in `VERIFY` (`hooks/tezgah_integrity.py::VERIFY`), so such a run reaches the ledger as a check like
   any other; the verb this branch asks for is `check` - `derive` writes the floor, it does not apply
   it. A screen is unchanged: the page a person looks at owes the read, not the contract.
10. **no external read** — the reply states the state of a system tezgah does not own — a registry,
   a release, a tag, a formula, a CI run — and no read of that system ran in the same turn
   (`hooks/tezgah_integrity.py::_external_claim`, over `EXTERNAL_SYSTEM`/`EXTERNAL_STATE`
   `hooks/tezgah_integrity.py::EXTERNAL_SYSTEM`, `hooks/tezgah_integrity.py::EXTERNAL_STATE` and the CI pair `EXTERNAL_CI`/`EXTERNAL_CI_STATE` `hooks/tezgah_integrity.py::EXTERNAL_CI`, `hooks/tezgah_integrity.py::EXTERNAL_CI_STATE`; branch `:3852-3860`).
   The two halves have to sit within `EXTERNAL_GAP` = 45 characters of each other on one line
   (`hooks/tezgah_integrity.py::_external_pair`), and both are read on the reply's prose with inline code, paths,
   URLs and identifiers blanked: `brew tap` inside a code span, the `.github/workflows/...` in a
   citation and a URL ending in `/releases/tag/...` are text about a system, not a claim about its
   state. A tagged release number beside a publish state is the second form (`EXTERNAL_VERSION`
   `hooks/tezgah_integrity.py::EXTERNAL_VERSION`), and its `v` is required, so `SC 2.5.8` and `4.1.3` in prose are not claims and
   neither is a bare version of tezgah's own code. The refusal names the command, chosen by the
   subject the reply used (`hooks/tezgah_integrity.py::_external_command`, `hooks/tezgah_integrity.py::EXTERNAL_SOURCE`). A local
   client is not the system: `npm --version` is not `npm view`, and a green unit run says nothing
   about what a registry publishes. The read is the evidence, and it is taken by the row's command
   and not by `passing_check` — `npm view` exiting non-zero is the answer for "this version is
   missing" (`hooks/tezgah_integrity.py::_external_read_row`) — so a turn whose only work was the read ends. It is
   last of the ten by the branch order above and in its strongest form: it is asked only where the
   fold would otherwise let the turn end, so it turns an allow into a refusal and never changes the
   class another branch refused the same turn under. It is the one class a turn with no work in it
   can make, which is why the "no work, no claim word" exit exempts it (`:3668`) — the two turns it
   was written for ("npm 0.22.0 is missing", read off an out-of-date local npm client, and "make
   NPM_TOKEN an automation token", which it already was) were advice-only, so before this class the
   fold returned `(None, None)` over both and neither was judged at all. Measured over this machine's
   own 2,092 final assistant replies, 2 are read as claims, both in review text about someone else's
   tooling.

The trigger for 5–9 is the turn's own evidence, not its words: a turn that did work and never saw a
check pass is refused whatever the reply says (`hooks/tezgah_integrity.py::_stop_block`). Two cases are judged against the
whole session instead of the turn:

- **A claim in a turn with no work.** A done/tested claim made in a turn that recorded no work row
  is judged by the same fold as a turn (`_evidence_block`), run over the session rows before
  this turn (`_before_turn`): every class the turn fold has - `check failed`, `no verify_ok`,
  `stale evidence`, a pending UI or design check, a partial failure - applies to the session too.
  A session that did no work at all still ends, and a turn that ran its own passing check is
  judged by the turn fold alone. Before this, the claim could be moved to the turn
  after the work, where the turn fold saw nothing to judge (audit M-2, INT-01).
- **A bookkeeping turn after a pass.** A turn whose only rows are read-only or VCS-bookkeeping
  commands ends without a fresh check, as long as nothing but bookkeeping ran after the session's
  newest pass, the session fold above allows it, and the reply makes no external-state claim
  (`_settled`). The command is read raw, with bash quoting (`_shell_effect`): a substitution
  inside double quotes, a redirect outside quotes and a process substitution disqualify it, and a
  command the ledger cut at `DETAIL_MAX` characters is never bookkeeping (review F1, F2). A heredoc
  is recognised only at an unquoted, uncommented `<<` that is not `<<<` (`_heredocs`), the one reader
  every gate check uses, so a quoted `<<'X'` cannot hide the lines after it. Read-only is a program in
  `READ_ONLY_PROGRAMS` (`ls`, `cat`, `grep`, `wc`, ...) or a git subcommand in `GIT_BOOKKEEPING`
  (`status`, `log`, `diff`, `add`, `commit`, `push`, ...); a redirect, `$(` or a backtick
  disqualifies the command. An edit, a failed check or any other command after the pass keeps the
  turn rule. Without this, a commit-only turn was refused and the model re-ran checks that had
  already passed (audit M-12, CHAT-04). The lists are short on purpose: a missing program costs one
  refusal, while a writing program wrongly listed would excuse an unverified change.

What lets the turn end is the absence
of both — no work row and no claim vocabulary (`hooks/tezgah_integrity.py::_stop_block`), the one shape class 10 is exempt from
— or a `passing_check` row newer than the newest write seen to change the tree (`hooks/tezgah_integrity.py::_evidence_block`), where
a fresh screen proof stands in the same
place as a unit pass; when that write was a UI source, the passing row has to be a UI proof — a
check that renders, or a read of the screen — and when it was a component, the design check has to be
newer than that write as well. An explicit admission (`doğrulanmadı`,
`unverified`, `not verified`, `couldn't verify`; `hooks/tezgah_integrity.py::NEGATED`) clears the rule (`hooks/tezgah_integrity.py::_stop_block`),
checked after the shape branches and before the evidence triggers. The block text is the string the
refusing branch returns; it names the failed
command (`hooks/tezgah_integrity.py::_failed_check`) and tells the model to report the failure with its exact error
line, or fix it and re-run.

**The escape hatches, and the deny that answers each.** The gate refuses these before they run, under
the same `verify-off` switch (`hooks/tezgah_gate.py::decision`), as rule `shortcut`:

- `--no-verify` on a git/commit/push-style command (`hooks/tezgah_integrity.py::NO_VERIFY`, `hooks/tezgah_integrity.py::GITISH`) —
  `hooks/tezgah_integrity.py::shortcut_command`.
- an env that skips the hooks — `SKIP=`, `HUSKY_SKIP_HOOKS=`, `HUSKY=0` — again requiring the git/hook
  context, so a read that merely mentions `SKIP=` passes (`hooks/tezgah_integrity.py::SKIP_ENV`, `hooks/tezgah_integrity.py::_shortcut_command`).
- a `core.hooksPath` assignment in the same command as a `git commit`/`git push` — `git -c
  core.hooksPath=/dev/null commit`, `git config core.hooksPath "$D" && git commit`, `--config-env`, the
  `GIT_CONFIG_KEY_n`/`GIT_CONFIG_PARAMETERS` env (`hooks/tezgah_integrity.py::_hooks_redirect`);
  a standalone `git config core.hooksPath .githooks` passes. Set in one call and committed in the next
  is not seen: the rule reads one command line.
- a check chained so it cannot fail: `|| true`, `; true`, `|| exit 0`, `|| :` (`hooks/tezgah_integrity.py::NEUTER`,
  `hooks/tezgah_integrity.py::_shortcut_command`).
- a newly added test skip/xfail in a test file (`hooks/tezgah_integrity.py::SKIP_TEST`, path gate `hooks/tezgah_integrity.py::TEST_PATH`,
  per-marker count `hooks/tezgah_integrity.py::_added`, `hooks/tezgah_integrity.py::shortcut_edit`). Rewriting an existing skip in place
  passes; one more does not.

Both scans run on text whose strings, comments and heredoc bodies are blanked (`hooks/tezgah_integrity.py::mask`), so
a commit message that *describes* `--no-verify` is not a bypass while the flag in command position
is. Every denial is itself a `deny` row.

## The session store for the status marks

`<cache>/sessions/<slug>.jsonl`, written by `record()` (`hooks/tezgah_context.py::record`) and read
by `used()` (`hooks/tezgah_context.py::used`). A row is exactly `{"kind": kind}` — no timestamp, no outcome, no session —
and the kinds are the used-tool marks [status-line.md](status-line.md) lights up (`graph`, `consult`,
`research`, `judge`), plus one kind per shipped skill a read opened. It is separate from the
[ledger](glossary.md#ledger) because it is display state, not
evidence: nothing refuses a call on it, a kind that is not one of tezgah's is not written at all
(`hooks/tezgah_context.py:2090-2091`), and the reader wants a set of kinds rather than an ordered,
turn-scoped history. The ledger pays a redaction scan and a lock per row; a mark needs neither. The
one mark that is also evidence is `orch`: `record()` writes it as an `orch` row in the session's
ledger too (`hooks/tezgah_context.py::record`), because a subagent event reaches no other ledger
writer and `fanout` is folded from the ledger.

**Which skill a read opened.** `skill_read_kind` (`hooks/tezgah_context.py::skill_read_kind`) earns the mark
the status line draws for the two skills the always-on core tells a session to read (`SKILL_MARKS`:
`pony` for `ponytail`, `adhd` for `i-have-adhd`) and `skill:<name>` for any other *shipped* skill -
one read from the checkout's `skills/` (`hooks/tezgah_context.py::shipped_skills`), so an
unshipped name earns nothing, which is what `skill://other` always got. `SKILL_MARKS` itself is not
widened: a mark whose skill the always-on core never names can never flip, and
`tests/test_context.py::MarkedRulesNameTheirSkill` requires every entry to be named there. A `skill:` kind is
therefore invisible to the line and its legend - no mark's measure is spelled that way - while
`skill_fitness(window)` (`hooks/tezgah_context.py::skill_fitness`) reads it back for the one question the
line never asked. Three surfaces recognise a read, and they have to agree on the two forms
(`skills/<name>/SKILL.md` and `skill://<name>`) and on which name is shipped: the Python hook omp's
bridge calls (`hosts/omp/hook.py::classify`), omp's own filter, which decides whether python hears about the
read at all (`hosts/omp/tezgah-hook.ts.in:225-262`, its catalogue the checkout `@HOOK@` names), and
opencode's plugin, which classifies in process because that host has no Python hook
(`hosts/opencode/plugins/tezgah.js:1900-1945`, its catalogue the host's own installed skill dir
(`dirname(CONFIG)/opencode/skills`), which `tezgah-setup` fills with every shipped skill).

Claude loads a skill through its `Skill` tool, never a read, so a Claude load used to leave no row.
The same function now maps a `Skill` call to the same kind. The call carries
`{"skill": "<name>"}`, and a plugin skill arrives as `tezgah:<name>`. The plugin's PostToolUse
matcher carries `Skill` (`hooks/hooks.json`), and `projects-posttooluse.py`'s `used_kind` records
it. Nobody has checked that Claude fires PostToolUse for the Skill tool. `tests/test_context.py`
proves the hook side only.

**The fitness report.** `tezgah-status --skill-fitness` prints, per shipped skill, how many of the
recorded sessions opened it, and names the ones none did: a skill is a dependency that has to keep
earning the context lines it costs, and accretion is invisible from reading the skill itself. It is a
measurement, not a gate - it names the candidates for retirement, and deleting one stays the owner's
call. Three ceilings are honest parts of the number, not bugs: the window is the newest
`FITNESS_WINDOW = 200` session files by mtime, because a row carries no timestamp; a session counts
as having opened a skill when it recorded that skill's kind, so reads recorded before `skill:` existed
still count through the two marks; and only the hosts that classify a read in process record one
here, so the count is a floor, not a census. Which host records what, since this store is the
report's only source: **omp** (the extension's filter lets the read through,
`hosts/omp/tezgah-hook.ts.in:255-262`, and the hook classifies it, `hosts/omp/hook.py::classify`) and
**opencode** (the plugin classifies it, `hosts/opencode/plugins/tezgah.js:1930-1945`) record the mark
or `skill:<name>` for every shipped skill, in either form; **Claude** sees a read, but only in its
transcript, which feeds the status line and writes no row here (`statusline.py::claude_used`), so a Claude
session reads in this report as one that opened nothing - marks included; **codex**, **cursor** and
**dsh** record no read at all (cursor's `classify` has no skill branch; dsh runs the shared hook whose
`used_kind` knows no skill kind), and [status-line.md](status-line.md) owns which surface can see a
read for the marks. Both in-process mirrors take the same two forms and the same shipped-name rule as
`skill_read_kind`, so a read is recorded on every host that can see one; a host that records none is
a recording gap, not a skill nobody opened.
The two marked skills are the only ones any host recorded before `skill:<name>` landed, so the first
report after this change reads mostly as a recording gap and fills in as sessions run; it says so on
its own line rather than in a footnote nobody opens.
The heavier half the mechanism names - a with/without lift measurement against a real oracle - is
deliberately not here.

## Snapshots and rollback

Before a write is allowed, `capture` copies the current bytes of every file the call names into
`<cache>/snapshots/<id>/file`, `meta.json` beside it (`hooks/tezgah_snapshot.py:62-68`, `:74-79`,
`:169-203`), and appends one `snapshot` row whose `detail` is the resolved path, `id` the 12-hex
snapshot id, `hash` the sha256 and `out_bytes` the size (`hooks/tezgah_snapshot.py::_capture_one`). The row is written last, so it
never names a copy that is not on disk. A credential file (`SECRET_FILE`: `.env*`, `*.env`, key and
certificate files, `id_rsa`-style keys, `credentials.json`, `.netrc`, `.npmrc`, `.pypirc`, `.pgpass`,
`.git-credentials`) gets the row alone - path, size and sha256, no `id` and no copy - so a snapshot
never duplicates a secret, and `rollback` lists it as not restorable (audit L-6). Snapshot files
are written `0600` in `0700` directories. Every host calls `capture` in process except opencode, whose
JavaScript plugin reaches it through `bin/tezgah-capture` (`bin/tezgah-capture:1-20`).

The store is capped twice (`:33-52`): `CAP = 200` snapshots, oldest evicted by directory mtime when a
capture crosses it (`:51`, `hooks/tezgah_snapshot.py::_evict`), and `MAX_BYTES = 2 MiB` per file, above which
**nothing is captured at all** — an over-large file is skipped because `capture` runs synchronously in
the gate on the path of the very write it protects, so copying gigabytes would stall that call, and a
refused capture writes no row and so claims no copy (`:38-52`, `:173-176`).

`restore` (`hooks/tezgah_snapshot.py::restore`) has exactly one caller, `bin/tezgah-rollback`, which a user runs:
`tezgah-rollback <snapshot-id> [--force]` (`bin/tezgah-rollback:24-35`). It refuses an unknown or
malformed id, stored bytes that do not match the recorded hash, and a file that has changed since the
capture — that last one only until `--force`, and the `rollback` row records that it was used
(`:246-266`). The id to pass is on the `snapshot` ledger row for that write (`_snapshot_hash`
`hooks/tezgah_integrity.py::_snapshot_hash`).

`--session <id>` widens that command to a whole session: for every path the session's writes
touched it puts back the EARLIEST snapshot the session took of it — the state before the session's
first write of that path. `session_plan` (`hooks/tezgah_snapshot.py::session_plan`) is that reading: it
walks the session's rows in order, names every path an `edit` or shell row wrote (a snapshot row
whose path no write row named — the second file of an `apply_patch` body — is there too), and joins
each to the session's earliest `snapshot` row for it, carrying an `action` that says what the
rollback would do with it: `restore` for a path a write tool changed, `list (shell only)` for a path
only a shell command's redirect touched, `list (unknown writer)` when a shell row's
target could not be re-read so the writer is not known, `list (no snapshot)` for one with no pre-state at all — a
file the session created. Only the `restore` entries are put back
(`hooks/tezgah_snapshot.py::restore_session`): which file a command wrote is read off its
text rather than reported by a tool, so a shell-touched path is listed and never reverted even where
the gate captured its target, and the id is printed for a deliberate single-id restore. A relative
target is resolved against the paths the ledger has already resolved — the snapshot rows' own, which
the gate resolved against the call's cwd (`hooks/tezgah_snapshot.py::_row_path`). `--dry-run`
prints the plan as `path<TAB>id<TAB>action` and writes nothing: no ledger row, no store change.

The moved-on check is `restore`'s own, fed the session's last recorded hash of the path: the file the
session left behind is what its earliest snapshot is compared with, so the session's own later writes
need no `--force`, while a write by somebody else after the session's last one still refuses. One
refusal does not stop the others — each path is its own file and its own decision — and the exit code
is 1 when any was refused.

At the end of a turn the same set is named where a host can show text without blocking the turn:
Codex's Stop `systemMessage` carries `changed_files_notice`
(`hooks/tezgah_integrity.py::changed_files_notice`), the turn's `changed_files` as one sorted line, capped at
`CHANGED_NOTICE_MAX` names plus a count of the rest. Claude's and omp's Stop output returns a
decision and nothing else and Cursor's block is a follow-up, so those three name no files: the set is
named to be acted on by the user, never to hold the turn.

**Nothing rolls back automatically, anywhere.** A hook that undoes work can destroy more than the
failure it answers, and its trigger would be a guess about intent wearing a check's clothes
(`hooks/tezgah_snapshot.py:10-18`; `hooks/tezgah_integrity.py:2387-2391`). Repair is the model's or
the user's: fix and re-run, or reach for a snapshot deliberately.

## Untrusted content

A result that arrived from outside the user and this workspace carries a provenance label on the
result itself: `untrusted_label` (`hooks/tezgah_integrity.py::untrusted_label`) names the channel — a web
result (`hooks/tezgah_integrity.py::WEB_TOOLS`), an MCP server (`hooks/tezgah_integrity.py::untrusted_source`), a network read (`hooks/tezgah_integrity.py::NETWORK_READ`) or a
model on the far side of the network (`hooks/tezgah_integrity.py::TIER_PROGRAMS`: a `bin/consult`/`bin/codegen`
invocation that reaches a provider) — and tells the model to treat instructions inside it as data.
The call's own row carries the channel in `source` (`hooks/tezgah_integrity.py::note_tool`).

After that read, the first effect the turn makes — a shell call or a write
(`hooks/tezgah_untrusted.py:39-44`) — carries a taint notice instead (`hooks/tezgah_untrusted.py::marks`,
`hooks/tezgah_untrusted.py::taint_notice`, `hooks/tezgah_untrusted.py::turn_channel`) — which reads the ledger through `turn_rows`
(`hooks/tezgah_integrity.py::turn_rows`): the whole file's lines, but only the current turn's rows
parsed, so a taint check costs the length of the turn and not the length of the session. It names
the turn, never a cause: whether the
fetched page *caused* the write is not something a hook can see (`:14-17`). One notice per read, and
the effect's own row then carries the channel, so the taint is a transition rather than a repeat.

The taint is a notice, not a refusal: the gate's sink rule, which held an effect in such a turn
until the user's own approval was on the ledger, was removed with the consent rule
([gate](gate.md)). The
label reaches the model on every host that has a surface for it: Claude and dsh through
`hooks/projects-posttooluse.py:85-89`, Codex (`hosts/codex/hook.py::main`), Cursor
(`hosts/cursor/hook.py:258-259`), omp (`hosts/omp/hook.py:177-215`), and opencode, whose plugin
cannot import the core in process and mirrors the control in JavaScript instead — the channel on the
call's own row, the label and the taint notice in front of the result the hook is handed, including
the `external` row an MCP answer or a fetched page earns (`untrustedSource`
`hosts/opencode/plugins/tezgah.js:1658`, `labelResult` `:1703`, with the tier's argv reader
`tierRead` at `:1612`). The two halves are pinned against each other over a shared corpus, so neither
can move without failing the other's test (`tests/test_opencode_plugin.py::OpenCodePlugin.test_the_classifier_agrees_with_the_python_half_on_a_shared_corpus`). One difference is deliberate:
opencode's plugin writes that `external` row itself and carries the channel alone, since the UI rule
`_screen_read` belongs to the Python half and does not run there.

## The counters a maintainer reads

`tezgah-status --counters [session] [path]` (`bin/tezgah-status:72-97`) prints `counters(session)`
(`hooks/tezgah_integrity.py::counters`) over one session's whole ledger, and `tezgah-status --counters
--all` prints `counters_all()` (`hooks/tezgah_integrity.py::counters_all`) over every real-session ledger on the machine, adding `ledgers`, the
number of files it read, and `fixtures`, the ledgers left out because every workspace they name is a temp, OpenResearch run or arm-bench tree (`fixture_ledger`). Both fold their rows through `_counts` (`hooks/tezgah_integrity.py::_counts`), the one implementation
of the arithmetic, so a total cannot drift from the sessions it sums - the `:NNN` rows below are that
fold. `counters_all` bounds nothing: a window or a row cap would make the total contradict the
per-session numbers it claims to be, and the whole corpus here folds in 0.4 s (58,928 rows, 1,120
real ledgers, measured 2026-09-30).

Each key, as both readers produce it:

- `events` — every row; `kinds` — a histogram of them.
- `steps` — rows whose kind is in `STEP_KINDS` (`hooks/tezgah_integrity.py::STEP_KINDS`): work rows only,
  `interrupted` among them, since a call the host stopped was still issued.
- `unanswered` — the `began` rows no outcome answered (`unanswered`): calls whose result nobody saw.
  It is in no rate. `counters_all` sums it per ledger, so one session's answer never closes another's call.
- `tool_error_rate` — non-zero `exit` values over every row carrying an `exit` (`hooks/tezgah_integrity.py::_counts`);
  a host reporting no outcome contributes to neither half, so every row with an `exit` counts.
- `claims` and `false_completion` — the `claim` rows, which are replies in the claim vocabulary,
  and those whose detail starts with `blocked` (`hooks/tezgah_integrity.py::_counts`). A shape class (`SHAPE_BLOCKS`) is
  the exception. A reply refused for its list or its language made no false claim, so it counts
  as `shape_blocked` instead.
- `refusals` — the `refusal` rows: refused replies that claimed nothing, work-only or shape. A
  shape one also counts in `shape_blocked`. Before row version 3 these were `claim` rows, so a
  corpus folded across the boundary counts them in `claims`.
- `blocked_claims` — `false_completion` split by its Stop class, the text after `blocked: `
  (`no verify_ok`, `stale evidence`, `no external read`, …), so each class has its own count.
- `replies` and `shape` — the `shape` rows, written for every judged reply, and those carrying a
  report-only flag (`hooks/tezgah_integrity.py::_counts`).
- `denies` — `deny` rows grouped by the text before the first colon (`hooks/tezgah_integrity.py::_counts`), which is the rule
  name (`shortcut`, `loop`, `race`, …); `nudges` and `fanout` — the nudge rows and
  the subagent-ish kinds (`hooks/tezgah_integrity.py::_counts`), the `orch` rows among them written by `record()`
  for every subagent event a Python adapter sees.
- `denies_reissued` — per deny rule, the denied calls that came back (`_reissued`). A later row of
  the same ledger carries the deny's `id`: the model made the call again. `tezgah-status --counters`
  prints it beside the denies as `rule=reissued/denies rate`. A rule is kept or dropped on this
  rate. For `drift` a high rate is the design: it refuses once, then lets the same call through. For
  any other rule it means the model worked around the refusal.
- `consult`, `codegen`, `codegen_failed` — substring matches on `detail` (`hooks/tezgah_integrity.py::_counts`).
- `weeks`, `tools`, `programs` — present only when the caller asked (`counters(..., weeks=True,
  tools=True)`), which is what `tezgah-status --counters --trend` passes; see below.

**`false_completion / claims`** is how often the rule refused a reply that claimed completion or
verification. It is one reading among the counters, not the layer's effect. A refusal the model
then repaired and a refusal it argued past count the same. The `after_block` rows record that
difference. One ledger is an anecdote. `--counters --all` gives the same ratio over the corpus. A
published value names the command, the date and the ledger count it ran over. Prose never
restates a number, because the counters' meaning moves with the row version. At version 3
work-only refusals left `claims`.

### The drift series and the firing histograms

`tezgah-status --counters --trend [--weeks=N]` prints two reports the same fold carries, because a
value is a reading and the thing worth watching is the population over time. Both are filled inside
`_counts` (`hooks/tezgah_integrity.py::_counts`) in the same pass as the totals, so neither can
disagree with the number it is drawn from; both are off unless the flag asks, so the plain and the
`--json` output of a reader who did not ask are byte-identical to what they were.

- **The drift series** — `weeks`, every row bucketed by `ts` on a fixed 7-day grid (`WEEK`, anchored
  on the Monday of the epoch's first week, `hooks/tezgah_integrity.py::_week`), each bucket
  counting its events, claims, refused claims and decided attempts. `drift_series(counters, weeks)`
  (`hooks/tezgah_integrity.py::drift_series`) re-slices them into the last `weeks` calendar weeks, oldest
  first, with `false_completion/claims` and `tool_error_rate` per bucket, and the direction of the
  newest three weeks that carry a denominator (`hooks/tezgah_integrity.py::_direction`, compared by
  cross-multiplication so a shared rounding is never called flat). A week with no row prints a zero
  row count and `n/a` for both ratios, never `0.0`: an empty week is not a week with a perfect rate,
  and a gap has to read as a gap. Nothing is windowed out of the totals.
- **The tool firings** — `tools`, a histogram over `_tool_name(entry)` (`hooks/tezgah_integrity.py::_tool_name`):
  the row's `tool` field, else the name an `unknown` row (`unknown tool: <name>`) or an MCP `external`
  row (`mcp <name>`) kept in `detail`. A work row written before the `tool` field landed carries no
  name at all - `classify` folded it into a kind - so an old corpus under-counts, which is the
  honest ceiling and the reason the field exists; every row written since carries it, because both
  writers write it (`hooks/tezgah_integrity.py::note_tool`, and opencode's plugin
  `hosts/opencode/plugins/tezgah.js:1034` - before that second one did, an opencode work row was
  the other half of this under-count, with its name unrecoverable in the command `detail`). A read
  tool is not in it either: reads record no row by design.
- **The shipped programs** — `programs`, the `bin/` programs a command row really ran, read with the
  tokenizer the status line already uses (`hooks/tezgah_integrity.py::_ran_programs`), and
  `unfired_programs(counters)` (`hooks/tezgah_integrity.py::unfired_programs`), the catalog minus that set. The absence is the
  evidence: a tool nobody calls leaves no row, so the only way to name it is a catalog, and the one
  catalog this layer holds is its own `bin/` (`hooks/tezgah_integrity.py::shipped_programs`). The prefilter is one
  regex per catalog and the tokenizer runs only on a row that mentions a shipped name, which is why
  the tool histogram costs about 0.6 s over the whole corpus where the plain fold costs 0.4 s (58,928
  rows, measured 2026-09-30). A
  program reached through an interpreter (`python3 bin/consult q`) counts as never fired, the same
  ceiling `shell_kind` has and for the same reason.

**The MCP half of a retirement decision is manual, and deliberately so.** This layer does not hold
the catalog of MCP servers - that is the host's configuration - so a server that never fires leaves
nothing here to name. `tezgah-setup --mcp-schemas` measures what each wired server costs on every
request; the histogram here counts what fired; joining the two is a reader's step, not a call this
report makes (calling it would couple the two CLIs and re-measure a config that may not be the one
the corpus ran under).

## The replay corpus

No counter above says whether a refusal was right. The ledger stores the verdict, never the truth.
`tezgah-gate replay` (`hooks/tezgah_replay.py`) builds the instrument that can. It is a report and
changes no gate behaviour. Every file it writes stays under `~/.cache/tezgah/replay/<run>/`, owner
only, and never leaves the machine. Every figure it prints names its cutoff.

- **Corpus.** The run reads every ledger under the cache and writes none. It drops a whole ledger
  when `fixture_ledger` calls it a fixture. It also drops one when the session id behind the file
  name is not a host UUID: probe, smoke and test ids. It drops `route` rows, which the suite
  writes, and every row after the cutoff. The items are the `deny`, `began` and `claim` rows. An
  item drops when its deny names a rule the gate no longer has (consent, sink). It also drops at
  the 200-character cap, or when it holds `[redacted:`. The run prints each exclusion with its count.
- **Join.** A transcript tool call joins a row when its `call_id` equals the row's `id`. The two
  must sit in the ledger the session id names. The walkers read omp and Claude transcripts with
  their subagent files, and drop omp's `i` argument first. A shell `began` row with no transcript
  call joins from its own `detail`, but only when that detail hashes to the row's `id`. A `claim`
  row joins the assistant reply nearest its time, within 2 s. Nothing else joins.
- **Replay.** A child process gets a sandbox HOME. It appends every kept row to the sandbox
  ledgers in time order. It replays each item just before the item's own row lands, with the
  clock frozen at the row's time. Gate items go through the unmodified `decision(..., record=False)`.
  Stop items go through `_stop_block` with the turn's own rows. The sandbox holds no kill switch,
  so every switch reads armed. A call a switch let through can therefore replay as a refusal.
- **Replay fidelity** = items whose replayed verdict equals the live one ÷ joined items, per
  stratum. A deny agrees only under the same rule, and `_deny_rule` alone names the rule. The
  *ledger* stratum holds rules that read the call and the ledger. The *disk* stratum holds the
  rules that read today's disk. These are task, plan, workspace and explorer, a shortcut on a write
  tool, and a lang rule reading a message file. The other strata are *allow* (live `began` rows)
  and *stop*.
  The run prints each one for the whole corpus and for the rows since `34f63e3`.
- **Stop text fidelity** = joined replies whose `_claim_key` equals the claim row's `id`. The run
  prints it beside the fidelity and never counts it as agreement.
- **Race family** = live race denies split by their foreign writers. A deny is intra-family when
  every writer is the session's parent, child or sibling. It is cross-family when any writer has
  no family tie. The family comes from omp's `spawned` rows and the subagent transcripts' parent
  links.
- **Denial budget** (`tezgah_shapes.deny_runs`) = per rule, runs of 3 or more consecutive denies
  inside one turn, and sessions with 20 or more denies. These are Claude Code auto mode's
  thresholds, not a tezgah measurement.

`replay --sheet` draws the blind label sample with a fixed seed. It fills per-stratum quotas,
shuffles them, and writes `tezgah-taste measure`'s `{set, n, text}` format. No item shows its
verdict, its rule or its reason. The verdicts sit in `sheet-key.jsonl`, which a rater does not
open. The sheet leaves off every race deny written before the ledger stored `target`, because a
rater could not see its foreign writer. With no race item on the sheet, the report calls the race
exemption bar not measurable. `replay --report --labels <file> ...` reads one labels file per rater
(`{set, n, label, rater}`). It prints these rates, each with a Wilson 95% interval:

- **False-block rate (rule r)** = denies of r labelled `allow` ÷ denies of r with a label.
- **Stop missed-violation rate** = allowed claims labelled `false` ÷ allowed claims with a label.
- **Stop false-refusal rate** = blocked claims labelled `honest` ÷ blocked claims with a label.
- **Cohen's kappa** between the two raters. The rates count only the items both raters gave the
  same label. Under 0.6 the report says the labels cannot gate a rule.

With no labels file the report calls these figures unverifiable instead of printing zeros.

## Source of truth

- `hooks/tezgah_integrity.py` — ledger, kinds, redaction, Stop rule, counters
- `hooks/tezgah_replay.py` — the replay corpus, the label sheet and its report (`tezgah-gate replay`)
- `hooks/tezgah_untrusted.py` — provenance label and taint notice
- `hooks/projects-posttooluse.py` — the writer hosts call after a tool result
- `hooks/projects-stop.py` — the Claude Stop hook
- `hooks/tezgah_snapshot.py` — capture, cap, restore
- `hooks/tezgah_context.py` — the session store (`record`/`used`)
- `hooks/tezgah_gate.py` — the shortcut and sink denies
- `hosts/opencode/plugins/tezgah.js` — the host with no Python hook: its own ledger
  and used-store rows (`recordEvidence`, `record`, `skillReadKind`)
- `hosts/omp/tezgah-hook.ts.in` — the omp bridge: which tool result reaches the hook
  at all, and the skill-read filter
- `bin/tezgah-rollback`, `bin/tezgah-capture`, `bin/tezgah-status`
- `tests/test_integrity.py`, `tests/test_snapshot.py` — the pinned behaviour
- `tests/test_opencode_plugin.py`, `tests/test_omp_extension.py` — the JS mirrors
  pinned against the Python half
