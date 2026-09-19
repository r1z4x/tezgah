# Evidence

This page is the evidence layer: the [ledger](glossary.md#ledger) a session appends to, the kinds it
holds, the Stop rule that reads them to refuse a turn, and the pre-write snapshots a bad write can be
undone from. Read it before changing a rule that records or reads evidence, or when undoing a write.
[gate.md](gate.md) owns the refusal path, [hosts.md](hosts.md) what each host can observe.

## The ledger

One append-only JSONL file per session at `<cache>/evidence/<slug>.jsonl`; the stem is a readable
prefix plus a hash of the session id, so a filename can never be turned back into one
(`hooks/tezgah_integrity.py:215-231`). Every writer goes through `note_path` (`:342-361`): `note()`
derives the path from the session id (`:364-374`), and the consent CLI passes an explicit path,
holding no session id. The row is built in exactly one place (`:357-360`), and its shape is
`{"kind": …, "ts": …, "detail": …}` plus whatever `LEDGER_FIELDS` keys the writer knew — for a check
the host reported passing, `{"kind": "verify_ok", "ts": 1758000000, "detail": "pytest -q",
"id": "a1b2c3d4e5f6", "exit": 0, "out_bytes": 4312}`.

`kind` is the event kind, `detail` is free text (the command, a path, a short reason) and `ts` is
epoch seconds. `detail` is credential-redacted **before** it is stored, over the whole text, and
truncated to `DETAIL_MAX = 200` only afterwards, so a marker the cut halves still reads as a marker
(`:266-291`, `:293`, `:350-358`): a named key keeps its name and loses its value, a `Bearer` token or
a prefixed token family loses it (`:246-263`). The optional fields are exactly `LEDGER_FIELDS`
(`:148-149`) — `id`, `exit`, `out_bytes`, `fail_class`, `workspace`, `source`, `hash`, `changed` — and
a key outside that set is dropped, a `None` value left out, because every reader treats a missing key
as `None` (`:359-360`). The append is one locked line, an exclusive `flock` with a 1 s bound falling
back to an unlocked write (`:296-338`), and is best effort: a write failure is never the caller's.

What never reaches the ledger: tool result bodies (only `out_bytes`, a size,
`hooks/projects-posttooluse.py:41-58`), the prompt text (the `turn` row keeps `sha1(prompt)[:12]`,
`:580-597`), read/search calls (`:1035-1036`), and any credential, already replaced.

## The kinds, by what reads them

A bare `:N` below is `hooks/tezgah_integrity.py`; `classify` (`:817-824`) picks the kind for a call —
a write tool is `edit`, a shell call is `verify` when its command matches the check vocabulary `VERIFY`
(`:39-53`) and `run` otherwise.

| Kind | Written by | Read by |
|---|---|---|
| `turn` | `note_turn` `:580-597`, from the prompt path | `_turn_start` `:461-466`, scoping every turn rule; `_claim_key` `:1191-1204` |
| `run`, `edit`, `verify`, `verify_ok`, `verify_fail` | `note_tool` `:1001-1069` | the Stop rule's `worked` set `:1293`; `counters.steps` `:666-667`; `last_verify`/`partial_state` |
| `external`, `unknown` | `note_tool` `:1041-1058` | the sink rule, via `source`; nothing counts them as work |
| `claim` | `stop_reason` `:1207-1232` | `counters` `:677-680` |
| `deny`, `nudge` | the [gate](gate.md)'s `_deny` `hooks/tezgah_gate.py:1181`, first-nudge `hooks/tezgah_gate.py:1348-1351` | `counters` `:672-676` |
| `snapshot`, `rollback` | `hooks/tezgah_snapshot.py:183-185`, `:262-265` | `_snapshot_hash` `:947-958`; no counter |

**The verify kinds are a tri-state, and an unread outcome is never a pass.** `note_tool`
(`:1030-1034`) records `verify` when the host reported no outcome at all (`failed is None`) or when
the command is piped — a pipe's status belongs to its last stage, so `pytest | tail` proves nothing
about pytest — and only otherwise splits it into `verify_ok`/`verify_fail`. `passing_check`
(`:1078-1089`) is stricter: a `verify_ok` counts only with `exit == 0`, a non-zero `out_bytes` (exit
0 with an empty result is the classic silent failure) and no `|` in the detail. The `out_bytes` half
bites only where the host reported a result size, and no `verify_ok` row has yet: 0 of 1224 across
the 1162 local ledgers carried the field (measured 2026-09-19), so an absent field still passes and
the guard has not rejected one. `last_verify`
(`:1149-1157`) folds the ordered rows to `ok`/`fail`/`ran`/`None`, because a set cannot tell a failure
that came after a success from one that came before it.

**`edit` carries the write's after-state.** The gate's capture records the pre-write hash;
`_post_write` (`:961-988`) adds `hash` (the target's sha256 once the host returned) and `changed`
(whether the two differ), so a call the host reports as a successful write need not have changed
anything. `changed_files` (`:990-994`) reads exactly those rows.

**`claim` is the false-completion record.** `stop_reason` (`:1207-1232`) writes one row per reply per
turn, deduplicated by `_claim_key` (`:1191-1204`), with detail `blocked: <class>` or `ok`: a refusal
and an allowed claim are both recorded, because the rate needs both halves. **`external` and
`unknown` claim no step of work.** `external` (`:1041-1047`) is a result with no work of its own — an
MCP answer, a fetched page — recorded so its provenance is on the ledger at all; `unknown`
(`:1048-1058`) is a tool name no list knows. The step counter, the Stop rule and the loop ceilings
ignore both.

## The Stop rule, end to end

The checker is `_stop_block` (`hooks/tezgah_integrity.py:1247-1344`), reached through `stop_reason`
(`:1207-1232`). Four hosts block on it — Claude (`hooks/projects-stop.py:33-35`), Codex
(`hosts/codex/hook.py:157-162`), Cursor (`hosts/cursor/hook.py:292-297`), omp
(`hosts/omp/hook.py:160-164`) — all with `{"decision": "block", "reason": …}`, all inert outside a
[root](glossary.md#root) and under the `verify-off` [kill switch](glossary.md#kill-switch)
(`hooks/projects-stop.py:28`). Five triggers, in order, each naming its reason class (`:1222`):

1. **placating opener** — the reply opens by agreeing or apologising (`:1272-1277`, `SYCOPHANT` `:103-108`).
2. **check failed** — the newest check in the session failed (`:1299-1304`).
3. **partial failure** — this turn recorded a `verify_fail` and nothing passed since (`:1307-1326`).
4. **stale evidence** — the newest check that passed ran before the newest write the gate saw change
   the tree, so it verified an earlier revision of it (`_last_pass`/`_last_change`/`_stale_paths`
   `:1116-1133`, branch `:1328-1335`).
5. **no verify_ok** — this turn recorded a step (`edit`, `verify`, `verify_fail`, `run`) and no check
   passed in the session (`:1338-1344`).

The trigger for 2–5 is the turn's own evidence, not its words: a turn that did work and never saw a
check pass is refused whatever the reply says (`:1293`). What lets the turn end is the absence
of both — no work row and no claim vocabulary (`:1294-1295`) — or a `passing_check` row newer than
the newest write seen to change the tree (`:1322-1323`). An explicit admission (`doğrulanmadı`,
`unverified`, `not verified`, `couldn't verify`; `NEGATED` `:99-101`) clears the rule (`:1279-1280`),
checked after the placating-opener branch and before the evidence triggers. The block text is the
string at `:1273-1277`, `:1300-1304`, `:1308-1326`, `:1329-1335`, `:1339-1344`; it names the failed
command (`_failed_check` `:1234-1244`) and tells the model to report the failure with its exact error
line, or fix it and re-run.

**The escape hatches, and the deny that answers each.** The gate refuses these before they run, under
the same `verify-off` switch (`hooks/tezgah_gate.py:1216-1224`), as rule `shortcut`:

- `--no-verify` on a git/commit/push-style command (`NO_VERIFY` `:62`, `GITISH` `:63`) —
  `shortcut_command` `:743-746`.
- an env that skips the hooks — `SKIP=`, `HUSKY_SKIP_HOOKS=`, `HUSKY=0` — again requiring the git/hook
  context, so a read that merely mentions `SKIP=` passes (`SKIP_ENV` `:61`, `:747-750`).
- a check chained so it cannot fail: `|| true`, `; true`, `|| exit 0`, `|| :` (`NEUTER` `:56-57`,
  `:751-754`).
- a newly added test skip/xfail in a test file (`SKIP_TEST` `:65-73`, path gate `TEST_PATH` `:75-78`,
  per-marker count `_added` `:758-777`, `shortcut_edit` `:780`). Rewriting an existing skip in place
  passes; one more does not.

Both scans run on text whose strings, comments and heredoc bodies are blanked (`mask` `:730-733`), so
a commit message that *describes* `--no-verify` is not a bypass while the flag in command position
is. Every denial is itself a `deny` row.

## The session store for the status marks

`<cache>/sessions/<slug>.jsonl`, written by `record()` (`hooks/tezgah_context.py:988-1004`) and read
by `used()` (`hooks/tezgah_context.py:1007-1021`). A row is exactly `{"kind": kind}` — no timestamp, no outcome, no session —
and the kinds are the used-tool marks [status-line.md](status-line.md) lights up (`cbm`, `consult`,
`research`). It is separate from the [ledger](glossary.md#ledger) because it is display state, not
evidence: nothing refuses a call on it, a kind that is not one of tezgah's is not written at all
(`:939-940`), and the reader wants a set of kinds rather than an ordered, turn-scoped history. The
ledger pays a redaction scan and a lock per row; a mark needs neither.

## Snapshots and rollback

Before a write is allowed, `capture` copies the current bytes of every file the call names into
`<cache>/snapshots/<id>/file`, `meta.json` beside it (`hooks/tezgah_snapshot.py:56-62`, `:68-73`,
`:155-188`), and appends one `snapshot` row whose `detail` is the resolved path, `id` the 12-hex
snapshot id, `hash` the sha256 and `out_bytes` the size (`:183-185`). The row is written last, so it
never names a copy that is not on disk. Every host calls `capture` in process except opencode, whose
JavaScript plugin reaches it through `bin/tezgah-capture` (`bin/tezgah-capture:1-20`).

The store is capped twice (`:34-53`): `CAP = 200` snapshots, oldest evicted by directory mtime when a
capture crosses it (`:52`, `_evict` `:83-98`), and `MAX_BYTES = 2 MiB` per file, above which
**nothing is captured at all** — an over-large file is skipped because `capture` runs synchronously in
the gate on the path of the very write it protects, so copying gigabytes would stall that call, and a
refused capture writes no row and so claims no copy (`:39-53`, `:159-162`).

`restore` (`:216-263`) has exactly one caller, `bin/tezgah-rollback`, which a user runs:
`tezgah-rollback <snapshot-id> [--force]` (`bin/tezgah-rollback:24-35`). It refuses an unknown or
malformed id, stored bytes that do not match the recorded hash, and a file that has changed since the
capture — that last one only until `--force`, and the `rollback` row records that it was used
(`:245-256`). The id to pass is on the `snapshot` ledger row for that write (`_snapshot_hash`
`:947-958`).

**Nothing rolls back automatically, anywhere.** A hook that undoes work can destroy more than the
failure it answers, and its trigger would be a guess about intent wearing a check's clothes
(`hooks/tezgah_snapshot.py:10-18`; `hooks/tezgah_integrity.py:1183-1189`). Repair is the model's or
the user's: fix and re-run, or reach for a snapshot deliberately.

## Untrusted content

A result that arrived from outside the user and this workspace carries a provenance label on the
result itself: `untrusted_label` (`hooks/tezgah_integrity.py:900-912`) names the channel — a web
result (`WEB_TOOLS` `:867`), an MCP server (`:869`), a network read (`NETWORK_READ` `:874`) — and
tells the model to treat instructions inside it as data. The call's own row carries the channel in
`source` (`:1063`).

After that read, the first effect the turn makes — a shell call or a write
(`hooks/tezgah_untrusted.py:36-41`) — carries a taint notice instead (`marks` `:81-93`,
`taint_notice` `:69-79`, `turn_channel` `:44-66`). It names the turn, never a cause: whether the
fetched page *caused* the write is not something a hook can see (`:14-17`). One notice per read, and
the effect's own row then carries the channel, so the taint is a transition rather than a repeat.

The taint is enforced at the sink: while an untrusted read is live, an effect is refused unless the
user's own approval was written *after* the read (`sink_check` `hooks/tezgah_gate.py:817-849`; deny
rule `sink` at `:1271-1280` for a write outside the root, `:1308-1309` for a shell effect class). The
label reaches the model on the four Python hosts: Claude and dsh through
`hooks/projects-posttooluse.py:80-83`, Codex (`hosts/codex/hook.py:135-136`), Cursor
(`hosts/cursor/hook.py:213-214`), omp (`hosts/omp/hook.py:139-158`). opencode's plugin makes no call
to the provenance test (`hosts/opencode/plugins/tezgah.js`), so that host supplies neither half.

## The counters a maintainer reads

`tezgah-status --counters [path] [session]` (`bin/tezgah-status:56-82`) prints `counters(session)`
(`hooks/tezgah_integrity.py:616-629`) over one session's whole ledger, and `tezgah-status --counters
--all` prints `counters_all()` (`:632-648`) over every ledger on the machine, adding `ledgers`, the
number of files it read. Both fold their rows through `_counts` (`:652-691`), the one implementation
of the arithmetic, so a total cannot drift from the sessions it sums - the `:NNN` rows below are that
fold. `counters_all` bounds nothing: a window or a row cap would make the total contradict the
per-session numbers it claims to be, and the whole corpus here folds in 0.17 s.

Each key, as both readers produce it:

- `events` — every row; `kinds` — a histogram of them.
- `steps` — rows whose kind is in `STEP_KINDS` (`:666-667`): work rows only.
- `tool_error_rate` — non-zero `exit` values over every row carrying an `exit` (`:668-671`, `:687-688`);
  a host reporting no outcome contributes to neither half, so every row with an `exit` counts.
- `claims` and `false_completion` — the `claim` rows, and those whose detail starts with `blocked`
  (`:677-680`).
- `denies` — `deny` rows grouped by the text before the first colon (`:672-674`), which is the rule
  name (`shortcut`, `loop`, `consent`, `sink`, `race`, …); `nudges` and `fanout` — the nudge rows and
  the subagent-ish kinds (`:689-690`).
- `consult`, `codegen`, `codegen_failed` — substring matches on `detail` (`:681-686`).

The one ratio that matters is **`false_completion / claims`**: how often a reply claiming completion
or verification had to be refused — the only number here that measures the layer's effect rather than
its traffic, and the one its own docstring names as the point of the counters (`:616-627`). One
ledger is an anecdote; `--counters --all` is the same ratio over the corpus, 0.271 across 1166
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
