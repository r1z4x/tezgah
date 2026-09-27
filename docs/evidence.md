# Evidence

This page is the evidence layer: the [ledger](glossary.md#ledger) a session appends to, the kinds it
holds, the Stop rule that reads them to refuse a turn, and the pre-write snapshots a bad write can be
undone from. Read it before changing a rule that records or reads evidence, or when undoing a write.
[gate.md](gate.md) owns the refusal path, [hosts.md](hosts.md) what each host can observe.

## The ledger

One append-only JSONL file per session at `<cache>/evidence/<slug>.jsonl`; the stem is a readable
prefix plus a hash of the session id, so a filename can never be turned back into one
(`hooks/tezgah_integrity.py:358-374`). Every writer goes through `note_path` (`hooks/tezgah_integrity.py:529`): `note()`
derives the path from the session id (`:552-562`). The row is built in exactly one place (`:545-546`), and its shape is
`{"kind": …, "ts": …, "v": …, "detail": …}` plus whatever `LEDGER_FIELDS` keys the writer knew — for a check
the host reported passing, `{"kind": "verify_ok", "ts": 1758000000, "v": 2, "detail": "pytest -q",
"id": "a1b2c3d4e5f6", "exit": 0, "out_bytes": 4312}`. `v` names the shape the row was written under
(`ROW_VERSION`, `hooks/tezgah_integrity.py:272`), and a reader folding a corpus across a version
change has to know what moved: at 2 the step vocabulary gained `interrupted`, so a version 1 row's
`verify_fail` may name a check that failed or a call the host stopped.

`kind` is the event kind, `detail` is free text (the command, a path, a short reason) and `ts` is
epoch seconds. A **write row's** `detail` is the path the call wrote, from the gate's one reader of
every host dialect (`write_paths`, `hooks/tezgah_gate.py:571-598`): `file_path`, `filePath`, `path`,
`notebook_path`, or an `apply_patch` body's first `*** Update File:` header — the paths
`changed_files()` (`hooks/tezgah_integrity.py:1370`) folds when a reader asks which files a session changed. `detail` is
credential-redacted **before** it is stored, over the whole text, and
truncated to `DETAIL_MAX = 200` only afterwards, so a marker the cut halves still reads as a marker
(`:396-421`, `:436`, `:538-542`): a named key keeps its name and loses its value, a `Bearer` token or
a prefixed token family loses it (`:376-406`). The optional fields are exactly `LEDGER_FIELDS`
(`hooks/tezgah_integrity.py:251-252`) — `id`, `exit`, `out_bytes`, `fail_class`, `workspace`, `source`, `hash`, `changed` — and
a key outside that set is dropped, a `None` value left out, because every reader treats a missing key
as `None` (`:547-548`). The append is one locked line, an exclusive `flock` with a 1 s bound falling
back to an unlocked write (`:511-522`), and is best effort: a write failure is never the caller's.

What never reaches the ledger: tool result bodies (only `out_bytes`, a size,
`hooks/projects-posttooluse.py:48-65`), the prompt text (the `turn` row keeps `sha1(prompt)[:12]`,
`hooks/tezgah_integrity.py:870-871`), read/search calls (`hooks/tezgah_integrity.py:1435-1436`), and any credential, already replaced.

## The kinds, by what reads them

A bare `:N` below is `hooks/tezgah_integrity.py`; `classify` (`:1131-1139`) picks the kind for a call —
a write tool is `edit`, a shell call is `verify` when its command matches the check vocabulary `VERIFY`
(`:39-54`) and `run` otherwise.

| Kind | Written by | Read by |
|---|---|---|
| `turn` | `note_turn` `hooks/tezgah_integrity.py:854-871`, from the prompt path | `_turn_start` `hooks/tezgah_integrity.py:731-736`, scoping every turn rule; `_claim_key` `hooks/tezgah_integrity.py:1658` |
| `run`, `edit`, `verify`, `verify_ok`, `verify_fail`, `interrupted` | `note_tool` `hooks/tezgah_integrity.py:1384` | the Stop rule's `worked` set `:1991`; `counters.steps` `:952-953`; `last_verify`/`partial_state` |
| `external`, `unknown` | `note_tool` `hooks/tezgah_integrity.py:1441-1458` | the taint notice, via `source`; nothing counts them as work |
| `claim` | `stop_reason` `hooks/tezgah_integrity.py:1877` | `counters` `hooks/tezgah_integrity.py:897-914` |
| `deny`, `nudge` | the [gate](gate.md)'s `_deny` `hooks/tezgah_gate.py:1029-1044`, first-nudge `hooks/tezgah_gate.py:1169-1170` | `counters` `hooks/tezgah_integrity.py:897-914` |
| `snapshot`, `rollback` | `hooks/tezgah_snapshot.py:184-186`, `:263-266` | `_snapshot_hash` `hooks/tezgah_integrity.py:1309`; no counter |

**`interrupted` is the step with no verdict.** The host said the call was *stopped* — a user's cancel,
or a call a policy denied before it ran — rather than reporting anything the tool answered, so the row
carries no `exit` and no `fail_class` (`note_tool()`, `hooks/tezgah_integrity.py:1428-1434`, the fields
`:1461-1466`). It counts as a step, because the model did issue the call and the turn's work has to
show; it is not a failed check, so `_partial_state`, `last_verify`, the error rate and `prior_calls`'
attempts (`hooks/tezgah_integrity.py:753`) all read it as a stopped call rather than a rejection.

**The verify kinds are a tri-state, and an unread outcome is never a pass.** `note_tool`
(`hooks/tezgah_integrity.py:1384`) records `verify` when the host reported no outcome at all (`failed is None`) or when
the command is piped — a pipe's status belongs to its last stage, so `pytest | tail` proves nothing
about pytest — and only otherwise splits it into `verify_ok`/`verify_fail`. `passing_check`
(`hooks/tezgah_integrity.py:1489`) is stricter: a `verify_ok` counts only with `exit == 0`, a non-zero `out_bytes` (exit
0 with an empty result is the classic silent failure) and no `|` in the detail. The `out_bytes` half
bites only where the host reported a result size — Codex (`hosts/codex/hook.py:173`), Cursor
(`hosts/cursor/hook.py:239,268`) and omp, whose bridge measures it and sends `result_len`
(`hosts/omp/tezgah-hook.ts.in:286-290`), now do — and 6 of 1423 `verify_ok` rows across 1454 local ledgers carry the field
(measured 2026-09-19), so an absent field still passes: the guard narrows a check whose
result was measured empty, it does not require the measurement. `last_verify`
(`hooks/tezgah_integrity.py:1579`) folds the ordered rows to `ok`/`fail`/`ran`/`None`, because a set cannot tell a failure
that came after a success from one that came before it.

**`edit` carries the write's after-state.** The gate's capture records the pre-write hash;
`_post_write` (`hooks/tezgah_integrity.py:1323`) adds `hash` (the target's sha256 once the host returned) and `changed`
(whether the two differ), so a call the host reports as a successful write need not have changed
anything. `changed_files` (`hooks/tezgah_integrity.py:1370`) reads exactly those rows.

**`claim` is the false-completion record.** `stop_reason` (`hooks/tezgah_integrity.py:1878`) writes one row per reply per
turn, deduplicated by `_claim_key` (`hooks/tezgah_integrity.py:1659`), with detail `blocked: <class>` or `ok`: a refusal
and an allowed claim are both recorded, because the rate needs both halves. **`external` and
`unknown` claim no step of work.** `external` (`:1448`) is a result with no work of its own — an
MCP answer, a fetched page — recorded so its provenance is on the ledger at all; `unknown`
(`:1459`) is a tool name no list knows. The step counter, the Stop rule and the loop ceilings
ignore both.

## The Stop rule, end to end

The checker is `_stop_block` (`hooks/tezgah_integrity.py:1938-2042`), reached through `stop_reason`
(`hooks/tezgah_integrity.py:1877`). Four hosts block on it — Claude (`hooks/projects-stop.py:33-35`), Codex
(`hosts/codex/hook.py:191-196`), Cursor (`hosts/cursor/hook.py:353-358`), omp
(`hosts/omp/hook.py:172-176`) — all with `{"decision": "block", "reason": …}`, all inert outside a
[root](glossary.md#root) and under the `verify-off` [kill switch](glossary.md#kill-switch)
(`hooks/projects-stop.py:28`). Eight triggers, in order, each naming its reason class (`hooks/tezgah_integrity.py:1890-1895`).
The first four judge how the reply is written (`_shape_block`, `hooks/tezgah_integrity.py:1820-1874`); the rest judge its evidence:

1. **placating opener** — the reply opens by agreeing or apologising (`SYCOPHANT` `hooks/tezgah_integrity.py:135-148`).
2. **forbidden closer** — the reply's last prose line is one of the sign-offs the output contract bans (`CLOSER`, `hooks/tezgah_integrity.py`): the same rule read at the other end, with its own class so the ledger says which end fired.
3. **list cap** — a contiguous list runs past `LIST_CAP` = 5 items (rule 8 of the `i-have-adhd` skill). `longest_list` (`hooks/tezgah_integrity.py:1691-1715`) counts per run of column-0 items of one kind: a heading, a prose line, a table row, a fence, a marker switch or a numbered list restarting at 1 ends the run, and blank or indented continuation lines keep it. Two headed groups of four pass; a 5+ enumeration that must stay whole goes under headings or into a table, which the block text says.
4. **reply language** — the reply's prose is not Turkish: at least `LANG_MIN_WORDS` = 25 prose words and under `LANG_MIN_SHARE` = 6% of them Turkish. `prose_words` drops fences, table rows, inline code, URLs, paths and identifiers first; `turkish_share` counts a word with a Turkish letter or one of `TR_WORDS` (`hooks/tezgah_integrity.py:1718-1739`).

The four shape classes share their switches with the text they enforce: `adhd-off` or a repo's `.no-adhd` lifts 1–3 (`_adhd_armed`, `hooks/tezgah_integrity.py:1806-1817`), `exec-mode.off` lifts 4, and a session whose environment carries `TEZGAH_NESTED` (an agent CLI consult started, whose English answer is read by code) is not judged for shape at all. A subagent's reply never reaches the rule: omp's `session_stop` does not fire for task sessions, and Claude and Cursor end a subagent through SubagentStop, which runs no Stop rule. The thresholds were set on the owner's omp transcripts (2026-09-27: 1,495 assistant replies with at least 25 prose words): English prose scored 0.000–0.026, the most English-heavy Turkish reply 0.077 and the bulk 0.3–0.7, and 24 of the 1,495 fall under the cut, all English or Chinese prose. The trade-off is on the Turkish side: a Turkish reply that is mostly quoted English outside backticks can fall under 6%, and the block text tells the model to put the English in backticks or a fence. `tests/test_integrity.py` `ReplyShapeCorpus` pins which realistic replies pass and which block. A lead that announces what follows (`preamble-open`) stays report-only: "Sonuç:" over a list is an answer label and reads like a preamble to any regex.

5. **check failed** — the newest check in the session failed (`:1997-2001`).
6. **partial failure** — this turn recorded a `verify_fail` and nothing passed since (`:2005-2014`).
7. **stale evidence** — the newest check that passed ran before the newest write the gate saw change
   the tree, so it verified an earlier revision of it (`_last_pass`/`_last_change`/`_stale_paths`
   `hooks/tezgah_integrity.py:1538`, branch `:2022-2035`). A write counts as a change whether the gate saw it as a
   write tool or as a shell command that redirected into the file - `_change_row` (`hooks/tezgah_integrity.py:1524`) reads
   an `edit` row, or a `run` row whose captured target moved - while a `verify*` row never does, so
   a check redirecting its own log cannot stale itself. A write *outside* the workspace is not one
   either: the fold's subject is the tree this reply is about, so `_post_write` records no
   after-state for a target beyond the call's own root - a commit message in `/tmp` written after a
   green suite is not a revision of that tree, and reading it as one refused an honest turn.
8. **no verify_ok** — this turn recorded a step (`edit`, `verify`, `verify_fail`, `run`,
   `interrupted`) and no check passed in the session (`:2035-2043`).

The trigger for 5–8 is the turn's own evidence, not its words: a turn that did work and never saw a
check pass is refused whatever the reply says (`:1980-1985`). What lets the turn end is the absence
of both — no work row and no claim vocabulary (`:1993-1994`) — or a `passing_check` row newer than
the newest write seen to change the tree (`:2021-2022`). An explicit admission (`doğrulanmadı`,
`unverified`, `not verified`, `couldn't verify`; `NEGATED` `:112-115`) clears the rule (`:1973-1974`),
checked after the shape branches and before the evidence triggers. The block text is the
string at `:1835-1874`, `:1998-2001`, `:2006-2014`, `:2027-2036`, `:2037-2043`; it names the failed
command (`_failed_check` `hooks/tezgah_integrity.py:1925`) and tells the model to report the failure with its exact error
line, or fix it and re-run.

**The escape hatches, and the deny that answers each.** The gate refuses these before they run, under
the same `verify-off` switch (`hooks/tezgah_gate.py:1074-1086`), as rule `shortcut`:

- `--no-verify` on a git/commit/push-style command (`NO_VERIFY` `:62`, `GITISH` `:63`) —
  `shortcut_command` `hooks/tezgah_integrity.py:1049`.
- an env that skips the hooks — `SKIP=`, `HUSKY_SKIP_HOOKS=`, `HUSKY=0` — again requiring the git/hook
  context, so a read that merely mentions `SKIP=` passes (`SKIP_ENV` `:61`, `:1061-1064`).
- a check chained so it cannot fail: `|| true`, `; true`, `|| exit 0`, `|| :` (`NEUTER` `:56-57`,
  `:1065-1068`).
- a newly added test skip/xfail in a test file (`SKIP_TEST` `:65-73`, path gate `TEST_PATH` `:75-78`,
  per-marker count `_added` `hooks/tezgah_integrity.py:1071`, `shortcut_edit` `hooks/tezgah_integrity.py:1093`). Rewriting an existing skip in place
  passes; one more does not.

Both scans run on text whose strings, comments and heredoc bodies are blanked (`mask` `hooks/tezgah_integrity.py:1043`), so
a commit message that *describes* `--no-verify` is not a bypass while the flag in command position
is. Every denial is itself a `deny` row.

## The session store for the status marks

`<cache>/sessions/<slug>.jsonl`, written by `record()` (`hooks/tezgah_context.py:1111`) and read
by `used()` (`hooks/tezgah_context.py:1130-1146`). A row is exactly `{"kind": kind}` — no timestamp, no outcome, no session —
and the kinds are the used-tool marks [status-line.md](status-line.md) lights up (`graph`, `consult`,
`research`). It is separate from the [ledger](glossary.md#ledger) because it is display state, not
evidence: nothing refuses a call on it, a kind that is not one of tezgah's is not written at all
(`:1126-1127`), and the reader wants a set of kinds rather than an ordered, turn-scoped history. The
ledger pays a redaction scan and a lock per row; a mark needs neither.

## Snapshots and rollback

Before a write is allowed, `capture` copies the current bytes of every file the call names into
`<cache>/snapshots/<id>/file`, `meta.json` beside it (`hooks/tezgah_snapshot.py:55-61`, `:67-72`,
`:155-189`), and appends one `snapshot` row whose `detail` is the resolved path, `id` the 12-hex
snapshot id, `hash` the sha256 and `out_bytes` the size (`:184-186`). The row is written last, so it
never names a copy that is not on disk. Every host calls `capture` in process except opencode, whose
JavaScript plugin reaches it through `bin/tezgah-capture` (`bin/tezgah-capture:1-20`).

The store is capped twice (`:33-52`): `CAP = 200` snapshots, oldest evicted by directory mtime when a
capture crosses it (`:51`, `_evict` `:82-98`), and `MAX_BYTES = 2 MiB` per file, above which
**nothing is captured at all** — an over-large file is skipped because `capture` runs synchronously in
the gate on the path of the very write it protects, so copying gigabytes would stall that call, and a
refused capture writes no row and so claims no copy (`:38-52`, `:159-162`).

`restore` (`:217-264`) has exactly one caller, `bin/tezgah-rollback`, which a user runs:
`tezgah-rollback <snapshot-id> [--force]` (`bin/tezgah-rollback:24-35`). It refuses an unknown or
malformed id, stored bytes that do not match the recorded hash, and a file that has changed since the
capture — that last one only until `--force`, and the `rollback` row records that it was used
(`:246-266`). The id to pass is on the `snapshot` ledger row for that write (`_snapshot_hash`
`hooks/tezgah_integrity.py:1309`).

**Nothing rolls back automatically, anywhere.** A hook that undoes work can destroy more than the
failure it answers, and its trigger would be a guess about intent wearing a check's clothes
(`hooks/tezgah_snapshot.py:10-18`; `hooks/tezgah_integrity.py:1643-1646`). Repair is the model's or
the user's: fix and re-run, or reach for a snapshot deliberately.

## Untrusted content

A result that arrived from outside the user and this workspace carries a provenance label on the
result itself: `untrusted_label` (`hooks/tezgah_integrity.py:1262-1276`) names the channel — a web
result (`WEB_TOOLS` `hooks/tezgah_integrity.py:1183`), an MCP server (`:1107`), a network read (`NETWORK_READ` `hooks/tezgah_integrity.py:1190`) or a
model on the far side of the network (`TIER_PROGRAMS` `hooks/tezgah_integrity.py:1199`: a `bin/consult`/`bin/codegen`
invocation that reaches a provider) — and tells the model to treat instructions inside it as data.
The call's own row carries the channel in `source` (`:1468`).

After that read, the first effect the turn makes — a shell call or a write
(`hooks/tezgah_untrusted.py:39-44`) — carries a taint notice instead (`marks` `:79-91`,
`taint_notice` `:69-78`, `turn_channel` `:47-66`) — which reads the ledger through `turn_rows`
(`hooks/tezgah_integrity.py:674`): the whole file's lines, but only the current turn's rows
parsed, so a taint check costs the length of the turn and not the length of the session. It names
the turn, never a cause: whether the
fetched page *caused* the write is not something a hook can see (`:14-17`). One notice per read, and
the effect's own row then carries the channel, so the taint is a transition rather than a repeat.

The taint is a notice, not a refusal: the gate's sink rule, which held an effect in such a turn
until the user's own approval was on the ledger, was removed with the consent rule
([gate](gate.md)). The
label reaches the model on every host that has a surface for it: Claude and dsh through
`hooks/projects-posttooluse.py:87-100`, Codex (`hosts/codex/hook.py:168-169`), Cursor
(`hosts/cursor/hook.py:251-252`), omp (`hosts/omp/hook.py:146-170`), and opencode, whose plugin
cannot import the core in process and mirrors the control in JavaScript instead — the channel on the
call's own row, the label and the taint notice in front of the result the hook is handed, including
the `external` row an MCP answer or a fetched page earns (`untrustedSource`
`hosts/opencode/plugins/tezgah.js:1228`, `labelResult` `:1735`, with the tier's argv reader at
`:1558`). The two halves are pinned against each other over a shared corpus, so neither can move
without failing the other's test (`tests/test_opencode_plugin.py:1285`).

## The counters a maintainer reads

`tezgah-status --counters [path] [session]` (`bin/tezgah-status:60-82`) prints `counters(session)`
(`hooks/tezgah_integrity.py:897-912`) over one session's whole ledger, and `tezgah-status --counters
--all` prints `counters_all()` (`hooks/tezgah_integrity.py:917`) over every ledger on the machine, adding `ledgers`, the
number of files it read. Both fold their rows through `_counts` (`hooks/tezgah_integrity.py:937`), the one implementation
of the arithmetic, so a total cannot drift from the sessions it sums - the `:NNN` rows below are that
fold. `counters_all` bounds nothing: a window or a row cap would make the total contradict the
per-session numbers it claims to be, and the whole corpus here folds in 0.17 s.

Each key, as both readers produce it:

- `events` — every row; `kinds` — a histogram of them.
- `steps` — rows whose kind is in `STEP_KINDS` (`hooks/tezgah_integrity.py:894-896`): work rows only,
  `interrupted` among them, since a call the host stopped was still issued.
- `tool_error_rate` — non-zero `exit` values over every row carrying an `exit` (`:955-958`, `:992-993`);
  a host reporting no outcome contributes to neither half, so every row with an `exit` counts.
- `claims` and `false_completion` — the `claim` rows, and those whose detail starts with `blocked`
  (`:964-972`), except a shape class (`SHAPE_BLOCKS`): a reply refused for its list or its language
  made no false claim, so it counts as `shape_blocked` instead.
- `replies` and `shape` — the `shape` rows, written for every judged reply, and those carrying a
  report-only flag (`:977-985`).
- `denies` — `deny` rows grouped by the text before the first colon (`:959-961`), which is the rule
  name (`shortcut`, `loop`, `race`, …); `nudges` and `fanout` — the nudge rows and
  the subagent-ish kinds (`:962-963`, `:994-995`).
- `consult`, `codegen`, `codegen_failed` — substring matches on `detail` (`:986-991`).

The one ratio that matters is **`false_completion / claims`**: how often a reply claiming completion
or verification had to be refused — the only number here that measures the layer's effect rather than
its traffic, and the one its own docstring names as the point of the counters (`:909-910`). One
ledger is an anecdote; `--counters --all` is the same ratio over the corpus, 0.224 across 1454
ledgers when this was written, which is the reading no single session could give.

## Source of truth

- `hooks/tezgah_integrity.py` — ledger, kinds, redaction, Stop rule, counters
- `hooks/tezgah_untrusted.py` — provenance label and taint notice
- `hooks/projects-posttooluse.py` — the writer hosts call after a tool result
- `hooks/projects-stop.py` — the Claude Stop hook
- `hooks/tezgah_snapshot.py` — capture, cap, restore
- `hooks/tezgah_context.py` — the session store (`record`/`used`)
- `hooks/tezgah_gate.py` — the shortcut and sink denies
- `bin/tezgah-rollback`, `bin/tezgah-capture`, `bin/tezgah-status`
- `tests/test_integrity.py`, `tests/test_snapshot.py` — the pinned behaviour
