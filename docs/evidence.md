# Evidence

This page is the evidence layer: the [ledger](glossary.md#ledger) a session appends to, the kinds it
holds, the Stop rule that reads them to refuse a turn, and the pre-write snapshots a bad write can be
undone from. Read it before changing a rule that records or reads evidence, or when undoing a write.
[gate.md](gate.md) owns the refusal path, [hosts.md](hosts.md) what each host can observe.

## The ledger

One append-only JSONL file per session at `<cache>/evidence/<slug>.jsonl`; the stem is a readable
prefix plus a hash of the session id, so a filename can never be turned back into one
(`hooks/tezgah_integrity.py:381-397`). Every writer goes through `note_path` (`hooks/tezgah_integrity.py:627-648`): `note()`
derives the path from the session id (`:637-647`). The row is built in exactly one place (`:630-631`), and its shape is
`{"kind": …, "ts": …, "v": …, "detail": …}` plus whatever `LEDGER_FIELDS` keys the writer knew — for a check
the host reported passing, `{"kind": "verify_ok", "ts": 1758000000, "v": 2, "detail": "pytest -q",
"id": "a1b2c3d4e5f6", "exit": 0, "out_bytes": 4312}`. `v` names the shape the row was written under
(`ROW_VERSION`, `hooks/tezgah_integrity.py:369-371`), and a reader folding a corpus across a version
change has to know what moved: at 2 the step vocabulary gained `interrupted`, so a version 1 row's
`verify_fail` may name a check that failed or a call the host stopped.

`kind` is the event kind, `detail` is free text (the command, a path, a short reason) and `ts` is
epoch seconds. A **write row's** `detail` is the path the call wrote, from the gate's one reader of
every host dialect (`write_paths`, `hooks/tezgah_gate.py:587-614`): `file_path`, `filePath`, `path`,
`notebook_path`, or an `apply_patch` body's first `*** Update File:` header — the paths
`changed_files()` (`hooks/tezgah_integrity.py:1598-1611`) folds when a reader asks which files a session changed. `detail` is
credential-redacted **before** it is stored, over the whole text, and
truncated to `DETAIL_MAX = 200` only afterwards, so a marker the cut halves still reads as a marker
(`:481-506`, `:521`, `:623-627`): a named key keeps its name and loses its value, a `Bearer` token or
a prefixed token family loses it (`:463-491`). The optional fields are exactly `LEDGER_FIELDS`
(`hooks/tezgah_integrity.py:348-368`) — `id`, `exit`, `out_bytes`, `fail_class`, `workspace`, `source`, `hash`, `changed` — and
a key outside that set is dropped, a `None` value left out, because every reader treats a missing key
as `None` (`:632-634`). The append is one locked line, an exclusive `flock` with a 1 s bound falling
back to an unlocked write (`:596-605`), and is best effort: a write failure is never the caller's.

What never reaches the ledger: tool result bodies (only `out_bytes`, a size,
`hooks/projects-posttooluse.py:48-65`), the prompt text (the `turn` row keeps `sha1(prompt)[:12]`,
`hooks/tezgah_integrity.py:956`), read/search calls (`hooks/tezgah_integrity.py:1574-1575`), and any credential, already replaced.

## The kinds, by what reads them

A bare `:N` below is `hooks/tezgah_integrity.py`; `classify` (`:1266-1274`) picks the kind for a call —
a write tool is `edit`, a shell call is `verify` when its command matches the check vocabulary `VERIFY`
(`:40-65`) and `run` otherwise.

| Kind | Written by | Read by |
|---|---|---|
| `turn` | `note_turn` `hooks/tezgah_integrity.py:952-978`, from the prompt path | `_turn_start` `hooks/tezgah_integrity.py:829-841`, scoping every turn rule; `_claim_key` `hooks/tezgah_integrity.py:2029-2045` |
| `run`, `edit`, `verify`, `verify_ok`, `verify_fail`, `interrupted` | `note_tool` `hooks/tezgah_integrity.py:1612-1720` | the Stop rule's `worked` set `:2271`; `counters.steps` `:1038-1039`; `last_verify`/`partial_state` |
| `external`, `unknown` | `note_tool` `hooks/tezgah_integrity.py:1612-1720` | the taint notice, via `source`; nothing counts them as work |
| `claim` | `stop_reason` `hooks/tezgah_integrity.py:2248-2296` | `counters` `hooks/tezgah_integrity.py:995-1020` |
| `deny`, `nudge` | the [gate](gate.md)'s `_deny` `hooks/tezgah_gate.py:1198-1213`, first-nudge `hooks/tezgah_gate.py:1352` | `counters` `hooks/tezgah_integrity.py:995-1020` |
| `snapshot`, `rollback` | `hooks/tezgah_snapshot.py:184-186`, `:263-266` | `_snapshot_hash` `hooks/tezgah_integrity.py:1537-1550`; no counter |

**`interrupted` is the step with no verdict.** The host said the call was *stopped* — a user's cancel,
or a call a policy denied before it ran — rather than reporting anything the tool answered, so the row
carries no `exit` and no `fail_class` (`note_tool()`, `hooks/tezgah_integrity.py:1612-1720`, the fields
`:1607-1616`). It counts as a step, because the model did issue the call and the turn's work has to
show; it is not a failed check, so `_partial_state`, `last_verify`, the error rate and `prior_calls`'
attempts (`hooks/tezgah_integrity.py:835-843`) all read it as a stopped call rather than a rejection.

**The verify kinds are a tri-state, and an unread outcome is never a pass.** `note_tool`
(`hooks/tezgah_integrity.py:1612-1720`) records `verify` when the host reported no outcome at all (`failed is None`) or when
the command is piped — a pipe's status belongs to its last stage, so `pytest | tail` proves nothing
about pytest — and only otherwise splits it into `verify_ok`/`verify_fail`. A line that opens with
`set -o pipefail` (or `set -euo pipefail`) and carries no `||` is not piped for this purpose: the
pipe's status is then its first failing stage's, so the host's verdict is the check's
(`pipe_hides_status` `hooks/tezgah_integrity.py:1198-1207`, read at `hooks/tezgah_integrity.py:1563`). `passing_check`
(`hooks/tezgah_integrity.py:1727-1741`) is stricter: a `verify_ok` counts only with `exit == 0`, a non-zero `out_bytes` (exit
0 with an empty result is the classic silent failure) and no pipe owning the status. The gate refuses the
trimmed form before it runs ([gate.md](gate.md), the `piped` rule). The `out_bytes` half
bites only where the host reported a result size — Codex (`hosts/codex/hook.py:158`), Cursor
(`hosts/cursor/hook.py:239,268`) and omp, whose bridge measures it and sends `result_len`
(`hosts/omp/tezgah-hook.ts.in:286-290`), now do — and 6 of 1423 `verify_ok` rows across 1454 local ledgers carry the field
(measured 2026-09-19), so an absent field still passes: the guard narrows a check whose
result was measured empty, it does not require the measurement. `last_verify`
(`hooks/tezgah_integrity.py:1950-1962`) folds the ordered rows to `ok`/`fail`/`ran`/`None`, because a set cannot tell a failure
that came after a success from one that came before it.

**`edit` carries the write's after-state.** The gate's capture records the pre-write hash;
`_post_write` (`hooks/tezgah_integrity.py:1551-1597`) adds `hash` (the target's sha256 once the host returned) and `changed`
(whether the two differ), so a call the host reports as a successful write need not have changed
anything. `changed_files` (`hooks/tezgah_integrity.py:1598-1611`) reads exactly those rows.

**`claim` is the false-completion record.** `stop_reason` (`hooks/tezgah_integrity.py:2248-2296`) writes one row per reply per
turn, deduplicated by `_claim_key` (`hooks/tezgah_integrity.py:2029-2045`), with detail `blocked: <class>` or `ok`: a refusal
and an allowed claim are both recorded, because the rate needs both halves. **`external` and
`unknown` claim no step of work.** `external` (`:1593-1595`) is a result with no work of its own — an
MCP answer, a fetched page — recorded so its provenance is on the ledger at all; an MCP row's
`detail` is that channel followed by the tool's own name, because the UI rule has to be able to tell
a screen read from a file read and the taint notice reads the channel from `source` either way.
`unknown` (`:1603-1606`) is a tool name no list knows, its name in the `detail`. The step counter,
the Stop rule and the loop ceilings ignore both.

## The Stop rule, end to end

The checker is `_stop_block` (`hooks/tezgah_integrity.py:2310-2531`), reached through `stop_reason`
(`hooks/tezgah_integrity.py:2248-2296`). Four hosts block on it — Claude (`hooks/projects-stop.py:33-35`), Codex
(`hosts/codex/hook.py:191-196`), Cursor (`hosts/cursor/hook.py:353-358`), omp
(`hosts/omp/hook.py:172-176`) — all with `{"decision": "block", "reason": …}`, all inert outside a
[root](glossary.md#root) and under the `verify-off` [kill switch](glossary.md#kill-switch)
(`hooks/projects-stop.py:28`). Ten triggers, in order, each naming its reason class (`_stop_block`
`hooks/tezgah_integrity.py:2310-2531`).
The first four judge how the reply is written (`_shape_block`, `hooks/tezgah_integrity.py:2191-2247`); the rest judge its evidence:

1. **placating opener** — the reply opens by agreeing or apologising (`SYCOPHANT` `hooks/tezgah_integrity.py:212-225`).
2. **forbidden closer** — the reply's last prose line is one of the sign-offs the output contract bans (`CLOSER`, `hooks/tezgah_integrity.py`): the same rule read at the other end, with its own class so the ledger says which end fired.
3. **list cap** — a contiguous list runs past `LIST_CAP` = 5 items (rule 8 of the `i-have-adhd` skill). `longest_list` (`hooks/tezgah_integrity.py:2062-2088`) counts per run of column-0 items of one kind: a heading, a prose line, a table row, a fence, a marker switch or a numbered list restarting at 1 ends the run, and blank or indented continuation lines keep it. Two headed groups of four pass; a 5+ enumeration that must stay whole goes under headings or into a table, which the block text says.
4. **reply language** — the reply's prose is not Turkish: at least `LANG_MIN_WORDS` = 25 prose words and under `LANG_MIN_SHARE` = 6% of them Turkish. `prose_words` drops fences, table rows, inline code, URLs, paths and identifiers first; `turkish_share` counts a word with a Turkish letter or one of `TR_WORDS` (`hooks/tezgah_integrity.py:263-268`).

The four shape classes share their switches with the text they enforce: `adhd-off` or a repo's `.no-adhd` lifts 1–3 (`_adhd_armed`, `hooks/tezgah_integrity.py:2177-2190`), `exec-mode.off` lifts 4, and a session whose environment carries `TEZGAH_NESTED` (an agent CLI consult started, whose English answer is read by code) is not judged for shape at all. A subagent's reply never reaches the rule: omp's `session_stop` does not fire for task sessions, and Claude and Cursor end a subagent through SubagentStop, which runs no Stop rule. The thresholds were set on the owner's omp transcripts (2026-09-27: 1,495 assistant replies with at least 25 prose words): English prose scored 0.000–0.026, the most English-heavy Turkish reply 0.077 and the bulk 0.3–0.7, and 24 of the 1,495 fall under the cut, all English or Chinese prose. The trade-off is on the Turkish side: a Turkish reply that is mostly quoted English outside backticks can fall under 6%, and the block text tells the model to put the English in backticks or a fence. `tests/test_integrity.py` `ReplyShapeCorpus` pins which realistic replies pass and which block. A lead that announces what follows (`preamble-open`) stays report-only: "Sonuç:" over a list is an answer label and reads like a preamble to any regex.

5. **check failed** — the newest check in the session failed (`:2289-2295`).
6. **partial failure** — this turn recorded a `verify_fail` and nothing passed since (`:2297-2306`).
7. **stale evidence** — the newest check that passed ran before the newest write the gate saw change
   the tree, so it verified an earlier revision of it (`_last_pass`/`_last_change`/`_stale_paths`
   `hooks/tezgah_integrity.py:1776-1802`, branch `:2376-2387`). A write counts as a change whether the gate saw it as a
   write tool or as a shell command that redirected into the file - `_change_row` (`hooks/tezgah_integrity.py:1762-1775`) reads
   an `edit` row, or a `run` row whose captured target moved - while a `verify*` row never does, so
   a check redirecting its own log cannot stale itself. A write *outside* the workspace is not one
   either: the fold's subject is the tree this reply is about, so `_post_write` records no
   after-state for a target beyond the call's own root - a commit message in `/tmp` written after a
   green suite is not a revision of that tree, and reading it as one refused an honest turn.
8. **no verify_ok** — this turn recorded a step (`edit`, `verify`, `verify_fail`, `run`,
   `interrupted`) and no check passed in the session (`:2388-2399`).
9. **no ui_ok** — this turn changed a UI source (`UI_PATH` `hooks/tezgah_integrity.py:66-71`) and the
   check that passed was not one that sees the screen: a unit run never does. A browser/e2e/visual
   check (`UI_CHECK` `hooks/tezgah_integrity.py:86-102`) or a read of the rendered screen (`UI_TOOL`
   `hooks/tezgah_integrity.py:105-108` for the app-analysis tool names, `UI_TOOL_CMD` `:109-118` for the
   CLI capture) is the evidence this class asks for, and it has to be newer than
   the UI write it is about - not than the newest write of anything, so an unrelated file written
   after the screen read does not stale that read (`_ui_evidence` `hooks/tezgah_integrity.py:1884-1912`,
   branch `:2323-2335`). The write kinds are the freshness fold's own (`_change_row`: a write tool's
   `edit` row or a shell call's `run` row the gate saw change the tree), so a UI source written
   through a redirect owes the same proof. The MCP half of that proof is read off the row's own
   tool name (`_screen_read` `hooks/tezgah_integrity.py:1846-1883`), which is the only field that
   says which call a row was - so a row that merely names a browser tool in its command
   (`rg -n browser_snapshot docs/`) is not a read of anything; the CLI capture and the two checks
   are read at a command position on the masked text, `re.M` so that a command on its own later
   line of the same call counts. A component turn owes one thing more: when a changed UI source is
   a component rather than a screen (`DESIGN_COMPONENT` `hooks/tezgah_integrity.py:128-132` - a file
   under a component/views/widgets
   directory, or a name that carries the convention on its own), a fresh read of the screen is not
   enough by itself and a `tezgah-design check` row has to be newer than the component write it
   judges (`_design_evidence` `hooks/tezgah_integrity.py:1915-1935`, branch `:2343-2361`) - and it has
   to be a check whose pass was seen (`passing_check`, `hooks/tezgah_integrity.py:1727-1741`), because
   a screenshot says what a component looks like and the contract is the only thing that says whether
   it is on the repository's floor. The refusal names the command to run. Both of the checker's verbs
   are in `VERIFY` (`hooks/tezgah_integrity.py:56`), so such a run reaches the ledger as a check like
   any other; the verb this branch asks for is `check` - `derive` writes the floor, it does not apply
   it. A screen is unchanged: the page a person looks at owes the read, not the contract.
10. **no external read** — the reply states the state of a system tezgah does not own — a registry,
   a release, a tag, a formula, a CI run — and no read of that system ran in the same turn
   (`_external_claim` `hooks/tezgah_integrity.py:2618-2644`, over `EXTERNAL_SYSTEM`/`EXTERNAL_STATE`
   `:2532-2543` and the CI pair `EXTERNAL_CI`/`EXTERNAL_CI_STATE` `:2544-2551`; branch `:2400-2408`).
   The two halves have to sit within `EXTERNAL_GAP` = 45 characters of each other on one line
   (`_external_pair` `:2605-2617`), and both are read on the reply's prose with inline code, paths,
   URLs and identifiers blanked: `brew tap` inside a code span, the `.github/workflows/...` in a
   citation and a URL ending in `/releases/tag/...` are text about a system, not a claim about its
   state. A tagged release number beside a publish state is the second form (`EXTERNAL_VERSION`
   `:2558-2573`), and its `v` is required, so `SC 2.5.8` and `4.1.3` in prose are not claims and
   neither is a bare version of tezgah's own code. The refusal names the command, chosen by the
   subject the reply used (`_external_command` `:2645-2654`, `EXTERNAL_SOURCE` `:2590-2604`). A local
   client is not the system: `npm --version` is not `npm view`, and a green unit run says nothing
   about what a registry publishes. The read is the evidence, and it is taken by the row's command
   and not by `passing_check` — `npm view` exiting non-zero is the answer for "this version is
   missing" (`_external_read_row` `:2655-2677`) — so a turn whose only work was the read ends. It is
   last of the ten by the branch order above and in its strongest form: it is asked only where the
   fold would otherwise let the turn end, so it turns an allow into a refusal and never changes the
   class another branch refused the same turn under. It is the one class a turn with no work in it
   can make, which is why the "no work, no claim word" exit exempts it (`:2285`) — the two turns it
   was written for ("npm 0.22.0 is missing", read off an out-of-date local npm client, and "make
   NPM_TOKEN an automation token", which it already was) were advice-only, so before this class the
   fold returned `(None, None)` over both and neither was judged at all. Measured over this machine's
   own 2,092 final assistant replies, 2 are read as claims, both in review text about someone else's
   tooling.

The trigger for 5–9 is the turn's own evidence, not its words: a turn that did work and never saw a
check pass is refused whatever the reply says (`:2279-2286`). What lets the turn end is the absence
of both — no work row and no claim vocabulary (`:2285-2286`), the one shape class 10 is exempt from
— or a `passing_check` row newer than the newest write seen to change the tree (`:2373-2375`), where
a fresh screen proof stands in the same
place as a unit pass; when that write was a UI source, the passing row has to be a UI proof — a
check that renders, or a read of the screen — and when it was a component, the design check has to be
newer than that write as well. An explicit admission (`doğrulanmadı`,
`unverified`, `not verified`, `couldn't verify`; `NEGATED` `:189-211`) clears the rule (`:2253-2254`),
checked after the shape branches and before the evidence triggers. The block text is the string the
refusing branch returns; it names the failed
command (`_failed_check` `hooks/tezgah_integrity.py:2297-2309`) and tells the model to report the failure with its exact error
line, or fix it and re-run.

**The escape hatches, and the deny that answers each.** The gate refuses these before they run, under
the same `verify-off` switch (`hooks/tezgah_gate.py:1075-1203`), as rule `shortcut`:

- `--no-verify` on a git/commit/push-style command (`NO_VERIFY` `:139`, `GITISH` `:140-141`) —
  `shortcut_command` `hooks/tezgah_integrity.py:1168-1192`.
- an env that skips the hooks — `SKIP=`, `HUSKY_SKIP_HOOKS=`, `HUSKY=0` — again requiring the git/hook
  context, so a read that merely mentions `SKIP=` passes (`SKIP_ENV` `:138`, `:1146-1149`).
- a check chained so it cannot fail: `|| true`, `; true`, `|| exit 0`, `|| :` (`NEUTER` `:133-137`,
  `:1150-1153`).
- a newly added test skip/xfail in a test file (`SKIP_TEST` `:142-151`, path gate `TEST_PATH` `:152-159`,
  per-marker count `_added` `hooks/tezgah_integrity.py:1240-1261`, `shortcut_edit` `hooks/tezgah_integrity.py:1262-1298`). Rewriting an existing skip in place
  passes; one more does not.

Both scans run on text whose strings, comments and heredoc bodies are blanked (`mask` `hooks/tezgah_integrity.py:1162-1167`), so
a commit message that *describes* `--no-verify` is not a bypass while the flag in command position
is. Every denial is itself a `deny` row.

## The session store for the status marks

`<cache>/sessions/<slug>.jsonl`, written by `record()` (`hooks/tezgah_context.py:1330-1353`) and read
by `used()` (`hooks/tezgah_context.py:1358-1374`). A row is exactly `{"kind": kind}` — no timestamp, no outcome, no session —
and the kinds are the used-tool marks [status-line.md](status-line.md) lights up (`graph`, `consult`,
`research`). It is separate from the [ledger](glossary.md#ledger) because it is display state, not
evidence: nothing refuses a call on it, a kind that is not one of tezgah's is not written at all
(`hooks/tezgah_context.py:1330-1351`), and the reader wants a set of kinds rather than an ordered,
turn-scoped history. The ledger pays a redaction scan and a lock per row; a mark needs neither. The
one mark that is also evidence is `orch`: `record()` writes it as an `orch` row in the session's
ledger too (`hooks/tezgah_context.py:1343-1344`), because a subagent event reaches no other ledger
writer and `fanout` is folded from the ledger.

## Snapshots and rollback

Before a write is allowed, `capture` copies the current bytes of every file the call names into
`<cache>/snapshots/<id>/file`, `meta.json` beside it (`hooks/tezgah_snapshot.py:55-61`, `:67-72`,
`:155-189`), and appends one `snapshot` row whose `detail` is the resolved path, `id` the 12-hex
snapshot id, `hash` the sha256 and `out_bytes` the size (`:184-186`). The row is written last, so it
never names a copy that is not on disk. Every host calls `capture` in process except opencode, whose
JavaScript plugin reaches it through `bin/tezgah-capture` (`bin/tezgah-capture:1-20`).

The store is capped twice (`:33-52`): `CAP = 200` snapshots, oldest evicted by directory mtime when a
capture crosses it (`:51`, `_evict` `:83-99`), and `MAX_BYTES = 2 MiB` per file, above which
**nothing is captured at all** — an over-large file is skipped because `capture` runs synchronously in
the gate on the path of the very write it protects, so copying gigabytes would stall that call, and a
refused capture writes no row and so claims no copy (`:38-52`, `:159-162`).

`restore` (`:218-275`) has exactly one caller, `bin/tezgah-rollback`, which a user runs:
`tezgah-rollback <snapshot-id> [--force]` (`bin/tezgah-rollback:24-35`). It refuses an unknown or
malformed id, stored bytes that do not match the recorded hash, and a file that has changed since the
capture — that last one only until `--force`, and the `rollback` row records that it was used
(`:246-266`). The id to pass is on the `snapshot` ledger row for that write (`_snapshot_hash`
`hooks/tezgah_integrity.py:1537-1550`).

`--session <id>` widens that command to a whole session: for every path the session's writes
touched it puts back the EARLIEST snapshot the session took of it — the state before the session's
first write of that path. `session_plan` (`hooks/tezgah_snapshot.py:316-380`) is that reading: it
walks the session's rows in order, names every path an `edit` or shell row wrote (a snapshot row
whose path no write row named — the second file of an `apply_patch` body — is there too), and joins
each to the session's earliest `snapshot` row for it, carrying an `action` that says what the
rollback would do with it: `restore` for a path a write tool changed, `list (shell only)` for a path
only a shell command's redirect touched, `list (no snapshot)` for one with no pre-state at all — a
file the session created. Only the `restore` entries are put back
(`restore_session` `hooks/tezgah_snapshot.py:381-396`): which file a command wrote is read off its
text rather than reported by a tool, so a shell-touched path is listed and never reverted even where
the gate captured its target, and the id is printed for a deliberate single-id restore. A relative
target is resolved against the paths the ledger has already resolved — the snapshot rows' own, which
the gate resolved against the call's cwd (`_row_path` `hooks/tezgah_snapshot.py:281-315`). `--dry-run`
prints the plan as `path<TAB>id<TAB>action` and writes nothing: no ledger row, no store change.

The moved-on check is `restore`'s own, fed the session's last recorded hash of the path: the file the
session left behind is what its earliest snapshot is compared with, so the session's own later writes
need no `--force`, while a write by somebody else after the session's last one still refuses. One
refusal does not stop the others — each path is its own file and its own decision — and the exit code
is 1 when any was refused.

At the end of a turn the same set is named where a host can show text without blocking the turn:
Codex's Stop `systemMessage` carries `changed_files_notice`
(`hooks/tezgah_integrity.py:2698-2733`), the turn's `changed_files` as one sorted line, capped at
`CHANGED_NOTICE_MAX` names plus a count of the rest. Claude's and omp's Stop output returns a
decision and nothing else and Cursor's block is a follow-up, so those three name no files: the set is
named to be acted on by the user, never to hold the turn.

**Nothing rolls back automatically, anywhere.** A hook that undoes work can destroy more than the
failure it answers, and its trigger would be a guess about intent wearing a check's clothes
(`hooks/tezgah_snapshot.py:10-18`; `hooks/tezgah_integrity.py:1762-1775`). Repair is the model's or
the user's: fix and re-run, or reach for a snapshot deliberately.

## Untrusted content

A result that arrived from outside the user and this workspace carries a provenance label on the
result itself: `untrusted_label` (`hooks/tezgah_integrity.py:1442-1456`) names the channel — a web
result (`WEB_TOOLS` `hooks/tezgah_integrity.py:1352-1353`), an MCP server (`:1354`), a network read (`NETWORK_READ` `hooks/tezgah_integrity.py:1359-1367`) or a
model on the far side of the network (`TIER_PROGRAMS` `hooks/tezgah_integrity.py:1368-1382`: a `bin/consult`/`bin/codegen`
invocation that reaches a provider) — and tells the model to treat instructions inside it as data.
The call's own row carries the channel in `source` (`:1615`).

After that read, the first effect the turn makes — a shell call or a write
(`hooks/tezgah_untrusted.py:39-44`) — carries a taint notice instead (`marks` `:79-91`,
`taint_notice` `:69-78`, `turn_channel` `:47-66`) — which reads the ledger through `turn_rows`
(`hooks/tezgah_integrity.py:772-801`): the whole file's lines, but only the current turn's rows
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
without failing the other's test (`tests/test_opencode_plugin.py:1285`). One difference is deliberate:
opencode's plugin writes that `external` row itself and carries the channel alone, since the UI rule
`_screen_read` belongs to the Python half and does not run there.

## The counters a maintainer reads

`tezgah-status --counters [session] [path]` (`bin/tezgah-status:72-97`) prints `counters(session)`
(`hooks/tezgah_integrity.py:880-895`) over one session's whole ledger, and `tezgah-status --counters
--all` prints `counters_all()` (`hooks/tezgah_integrity.py:1021-1040`) over every real-session ledger on the machine, adding `ledgers`, the
number of files it read, and `fixtures`, the ledgers left out because every workspace they name is a temp, OpenResearch run or arm-bench tree (`fixture_ledger`). Both fold their rows through `_counts` (`hooks/tezgah_integrity.py:1041-1116`), the one implementation
of the arithmetic, so a total cannot drift from the sessions it sums - the `:NNN` rows below are that
fold. `counters_all` bounds nothing: a window or a row cap would make the total contradict the
per-session numbers it claims to be, and the whole corpus here folds in 0.17 s.

Each key, as both readers produce it:

- `events` — every row; `kinds` — a histogram of them.
- `steps` — rows whose kind is in `STEP_KINDS` (`hooks/tezgah_integrity.py:992-994`): work rows only,
  `interrupted` among them, since a call the host stopped was still issued.
- `tool_error_rate` — non-zero `exit` values over every row carrying an `exit` (`:1040-1043`, `:1019`);
  a host reporting no outcome contributes to neither half, so every row with an `exit` counts.
- `claims` and `false_completion` — the `claim` rows, and those whose detail starts with `blocked`
  (`:1049-1057`), except a shape class (`SHAPE_BLOCKS`): a reply refused for its list or its language
  made no false claim, so it counts as `shape_blocked` instead.
- `replies` and `shape` — the `shape` rows, written for every judged reply, and those carrying a
  report-only flag (`:1063-1070`).
- `denies` — `deny` rows grouped by the text before the first colon (`:1044-1046`), which is the rule
  name (`shortcut`, `loop`, `race`, …); `nudges` and `fanout` — the nudge rows and
  the subagent-ish kinds (`:1047-1048`, `:1079-1080`), the `orch` rows among them written by `record()`
  for every subagent event a Python adapter sees.
- `consult`, `codegen`, `codegen_failed` — substring matches on `detail` (`:1071-1076`).

The one ratio that matters is **`false_completion / claims`**: how often a reply claiming completion
or verification had to be refused — the only number here that measures the layer's effect rather than
its traffic, and the one its own docstring names as the point of the counters (`:1009-1010`). One
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
