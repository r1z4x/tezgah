# Evidence

This page is the evidence layer: the [ledger](glossary.md#ledger) a session appends to, the kinds it
holds, the Stop rule that reads them to refuse a turn, and the pre-write snapshots a bad write can be
undone from. Read it before changing a rule that records or reads evidence, or when undoing a write.
[gate.md](gate.md) owns the refusal path, [hosts.md](hosts.md) what each host can observe.

## The ledger

One append-only JSONL file per session at `<cache>/evidence/<slug>.jsonl`; the stem is a readable
prefix plus a hash of the session id, so a filename can never be turned back into one
(`hooks/tezgah_integrity.py:424-440`). Every writer goes through `note_path` (`hooks/tezgah_integrity.py:757-781`): `note()`
derives the path from the session id (`:692-702`). The row is built in exactly one place (`:685-688`), and its shape is
`{"kind": …, "ts": …, "v": …, "detail": …}` plus whatever `LEDGER_FIELDS` keys the writer knew — for a check
the host reported passing, `{"kind": "verify_ok", "ts": 1758000000, "v": 2, "detail": "pytest -q",
"id": "a1b2c3d4e5f6", "exit": 0, "out_bytes": 4312, "tool": "Bash"}`. `v` names the shape the row was written under
(`ROW_VERSION`, `hooks/tezgah_integrity.py:445-447`), and a reader folding a corpus across a version
change has to know what moved: at 2 the step vocabulary gained `interrupted`, so a version 1 row's
`verify_fail` may name a check that failed or a call the host stopped.

`kind` is the event kind, `detail` is free text (the command, a path, a short reason) and `ts` is
epoch seconds. A **write row's** `detail` is the path the call wrote, from the gate's one reader of
every host dialect (`write_paths`, `hooks/tezgah_gate.py:636-663`): `file_path`, `filePath`, `path`,
`notebook_path`, or an `apply_patch` body's first `*** Update File:` header — the paths
`changed_files()` (`hooks/tezgah_integrity.py:2466-2479`) folds when a reader asks which files a session changed. `detail` is
credential-redacted **before** it is stored, over the whole text, and
truncated to `DETAIL_MAX = 200` only afterwards, so a marker the cut halves still reads as a marker
(`:524-549`, `:564`, `:666-670`): a named key keeps its name and loses its value - also as a quoted
JSON key (`"password": "x"`) and as a flag with its value after a space (`--password X`,
`--api-key X`, `mysql -pPASS`) - an `Authorization` scheme (`Bearer`, `Basic`, `Token`, `Digest`),
the password of URL userinfo (`scheme://user:pass@`) and of `-u user:pass`, and a prefixed token
family lose theirs (`:506-534`; audit L-6, which found each of those stored verbatim). The optional fields are exactly `LEDGER_FIELDS`
(`hooks/tezgah_integrity.py:422-444`) — `id`, `exit`, `out_bytes`, `fail_class`, `workspace`, `source`, `hash`, `changed`, `tool`,
`target`, plus the reply-shape names `lines`, `chars`, `items`, `longest_list`, `tr_share`, `answer_first` and the compaction
row's `summary_chars`, `summary_hash`, `constraint_found`, `constraint_expected` — and
a key outside that set is dropped, a `None` value left out, because every reader treats a missing key
as `None` (`:675-677`). `tool` is the call's own name (`Bash`, `Write`, `mcp__codegen__status`),
written by `note_tool` (`hooks/tezgah_integrity.py:2480-2598`) because `classify` folds the name into
a kind and drops it; it is what `_counts`' tool histogram counts and what the retirement report on
`tezgah-status --counters --trend` prints. `target` is on every `edit` row: the written path as an
absolute real path, resolved against the call's cwd (`_abs_target`, written by `note_tool` and by
opencode's plugin through `absTarget`). `detail` keeps the path as the call spelled it, so
`README.md` in two repositories was one file to the concurrent-write guard; `writers_elsewhere`
now compares `target`, and a row without one (written before the field landed) is ignored by that
guard rather than matched by its spelling (audit M-6). Both writers write `tool` — `note_tool`, and opencode's
plugin, whose row carries the same field under the same empty-means-absent rule
(`hosts/opencode/plugins/tezgah.js:774-782`) — so no live host leaves it out. A row written *before*
the field landed names its tool only where the name survived in `detail` — an `unknown` row and an
MCP `external` row — so the one cause of an under-count is the corpus's age, and it shrinks as
sessions run. The append is one locked line, an exclusive `flock` with a 1 s bound falling
back to an unlocked write (`:706-715`), and is best effort: a write failure is never the caller's.
A ledger is created `0600` in a `0700` directory, because its rows name the paths and commands of
the user's work (audit L-6 found them `0644`). A reader that walks *other* sessions' ledgers (the
race guard, the counters) skips one that does not parse instead of raising, so one damaged file
cannot turn the write gate off machine-wide; the session's own ledger still refuses a damaged row
(`_foreign_rows`; audit M-7).

What never reaches the ledger: tool result bodies (only `out_bytes`, a size,
`hooks/projects-posttooluse.py:44-61`), the prompt text (the `turn` row keeps `sha1(prompt)[:12]`,
`hooks/tezgah_integrity.py:999`), read/search calls (`hooks/tezgah_integrity.py:1816-1817`), and any credential, already replaced.

## The kinds, by what reads them

A bare `:N` below is `hooks/tezgah_integrity.py`; `classify` (`:1392-1444`) picks the kind for a call —
a write tool is `edit`, a shell call is `verify` when its command matches the check vocabulary `VERIFY`
(`:45-81`) and `run` otherwise.

| Kind | Written by | Read by |
|---|---|---|
| `turn` | `note_turn` `hooks/tezgah_integrity.py:1124-1147`, from the prompt path | `_turn_start` `hooks/tezgah_integrity.py:986-998`, scoping every turn rule; `_claim_key` `hooks/tezgah_integrity.py:2942-2958` |
| `run`, `edit`, `verify`, `verify_ok`, `verify_fail`, `interrupted` | `note_tool` `hooks/tezgah_integrity.py:2480-2598`, the call's own name in `tool`, on opencode the plugin writes these same kinds and the same field (`hosts/opencode/plugins/tezgah.js:734-792`) | the Stop rule's `worked` set `:2345`; `counters.steps` `:1195-1196`; `last_verify`/`partial_state`; the `--trend` tool histogram |
| `external`, `unknown` | `note_tool` `hooks/tezgah_integrity.py:2480-2598` | the taint notice, via `source`; the `--trend` tool histogram; nothing counts them as work |
| `claim` | `stop_reason` `hooks/tezgah_integrity.py:3161-3209` | `counters` `hooks/tezgah_integrity.py:1405-1436` |
| `deny`, `nudge` | the [gate](gate.md)'s `_deny` `hooks/tezgah_gate.py:1394-1409`, first-nudge `hooks/tezgah_gate.py:1382` | `counters` `hooks/tezgah_integrity.py:1405-1436` |
| `snapshot`, `rollback` | `hooks/tezgah_snapshot.py:184-186`, `:263-266` | `_snapshot_hash` `hooks/tezgah_integrity.py:2405-2418`; no counter |
| `compact` | `note_compaction` `hooks/tezgah_integrity.py:1148-1180`, from the post-compaction path (`tezgah_context.remember_compaction` `hooks/tezgah_context.py:1214-1232`) | `_counts` `hooks/tezgah_integrity.py:1463-1605` (what `counters` folds with) |

**`compact` is what a compaction kept, from the record.** When the host hands the PostCompact
payload the text the model is about to receive — Claude's `compact_summary` — the shared path
(`hooks/tezgah_context.py:1251-1252`, reached by Claude's hook, codex/hook.py, omp's hook and dsh's
bridge alike, because it is the same funnel each prompt goes through) writes one row: the summary's
length (`summary_chars`), a 12-hex sha256 of it (`summary_hash`, so two compactions of one session can
be told apart and the same summary can be recognised twice), the host's own word for why it compacted
(`trigger`: `manual` or `auto`) on `detail`, and the constraint report. The summary's **text is never
stored** — it is the whole conversation by proxy and the ledger is a redacted channel — so a row can
never be read back as prose. The constraint report is `constraint_found` of `constraint_expected`: how
many of the fixed sentences tezgah injects the summary still carries, counted against the very text the
block renders (`constraint_lines`, `hooks/tezgah_context.py:1434-1452`, over `POINTER_LINE`
`hooks/tezgah_context.py:1426-1430` and the active plan's front matter). It is a **report and never a refusal**: a compaction
that dropped a rule is a finding to report, not a turn to block. A host that hands no summary writes no
row, and `tezgah-status --counters` folds the rows into `compactions`, `compact_chars` (the newest
summary's length) and `compact_constraint_rate` — which stays `None` until one row carries both counts,
because a `0.0` would claim every compaction dropped every rule.

**`interrupted` is the step with no verdict.** The host said the call was *stopped* — a user's cancel,
or a call a policy denied before it ran — rather than reporting anything the tool answered, so the row
carries no `exit` and no `fail_class` (`note_tool()`, `hooks/tezgah_integrity.py:2480-2598`, the fields
`:1849-1858`). It counts as a step, because the model did issue the call and the turn's work has to
show; it is not a failed check, so `_partial_state`, `last_verify`, the error rate and `prior_calls`'
attempts (`hooks/tezgah_integrity.py:878-886`) all read it as a stopped call rather than a rejection.

**The verify kinds are a tri-state, and an unread outcome is never a pass.** `note_tool`
(`hooks/tezgah_integrity.py:2480-2598`) records `verify` when the host reported no outcome at all (`failed is None`) or when
the command is piped — a pipe's status belongs to its last stage, so `pytest | tail` proves nothing
about pytest — and only otherwise splits it into `verify_ok`/`verify_fail`. A line that opens with
`set -o pipefail` (or `set -euo pipefail`) and carries no `||` is not piped for this purpose: the
pipe's status is then its first failing stage's, so the host's verdict is the check's
(`pipe_hides_status` `hooks/tezgah_integrity.py:2066-2075`, read at `hooks/tezgah_integrity.py:1805`). `passing_check`
(`hooks/tezgah_integrity.py:2605-2619`) is stricter: a `verify_ok` counts only with `exit == 0`, a non-zero `out_bytes` (exit
0 with an empty result is the classic silent failure) and no pipe owning the status. The gate refuses the
trimmed form before it runs ([gate.md](gate.md), the `piped` rule). The `out_bytes` half
bites only where the host reported a result size — Codex (`hosts/codex/hook.py:158`), Cursor
(`hosts/cursor/hook.py:239,268`) and omp, whose bridge measures it and sends `result_len`
(`hosts/omp/tezgah-hook.ts.in:606-610`), now do — and 6 of 1423 `verify_ok` rows across 1454 local ledgers carry the field
(measured 2026-09-19), so an absent field still passes: the guard narrows a check whose
result was measured empty, it does not require the measurement. `last_verify`
(`hooks/tezgah_integrity.py:2834-2843`) folds the ordered rows to `ok`/`fail`/`ran`/`None`, because a set cannot tell a failure
that came after a success from one that came before it.

**`edit` carries the write's after-state.** The gate's capture records the pre-write hash;
`_post_write` (`hooks/tezgah_integrity.py:2419-2465`) adds `hash` (the target's sha256 once the host returned) and `changed`
(whether the two differ), so a call the host reports as a successful write need not have changed
anything. `changed_files` (`hooks/tezgah_integrity.py:2466-2479`) reads exactly those rows.

**`claim` is the false-completion record.** `stop_reason` (`hooks/tezgah_integrity.py:3161-3209`) writes one row per reply per
turn, deduplicated by `_claim_key` (`hooks/tezgah_integrity.py:2942-2958`), with detail `blocked: <class>` or `ok`: a refusal
and an allowed claim are both recorded, because the rate needs both halves. **`external` and
`unknown` claim no step of work.** `external` (`:1835-1837`) is a result with no work of its own — an
MCP answer, a fetched page — recorded so its provenance is on the ledger at all; an MCP row's
`detail` is that channel followed by the tool's own name, because the UI rule has to be able to tell
a screen read from a file read and the taint notice reads the channel from `source` either way.
`unknown` (`:1845-1848`) is a tool name no list knows, its name in the `detail`. The step counter,
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
(`hooks/tezgah_research.py:1498`) - it is reported rather than labelled, because a
guessed kind would only move the refusal one step later. A source that cannot
meet the rule does not become a weaker claim: it is labelled for what it is, and
the work that produced it is the work that has to be redone.

## The Stop rule, end to end

The checker is `_stop_block` (`hooks/tezgah_integrity.py:3396-3500`), reached through `stop_reason`
(`hooks/tezgah_integrity.py:3161-3209`). Four hosts block on it — Claude (`hooks/projects-stop.py:33-35`), Codex
(`hosts/codex/hook.py:184-189`), Cursor (`hosts/cursor/hook.py:348-353`), omp
(`hosts/omp/hook.py:167-171`) — all with `{"decision": "block", "reason": …}`, all inert outside a
[root](glossary.md#root) and under the `verify-off` [kill switch](glossary.md#kill-switch)
(`hooks/projects-stop.py:28`). Ten triggers, in order, each naming its reason class (`_stop_block`
`hooks/tezgah_integrity.py:3396-3500`).
The first four judge how the reply is written (`_shape_block`, `hooks/tezgah_integrity.py:3104-3160`); the rest judge its evidence:

1. **placating opener** — the reply opens by agreeing or apologising (`SYCOPHANT` `hooks/tezgah_integrity.py:265-278`).
2. **forbidden closer** — the reply's last prose line is one of the sign-offs the output contract bans (`CLOSER`, `hooks/tezgah_integrity.py`): the same rule read at the other end, with its own class so the ledger says which end fired.
3. **list cap** — a contiguous list runs past `LIST_CAP` = 5 items (rule 8 of the `i-have-adhd` skill). `longest_list` (`hooks/tezgah_integrity.py:2975-3001`) counts per run of column-0 items of one kind: a heading, a prose line, a table row, a fence, a marker switch or a numbered list restarting at 1 ends the run, and blank or indented continuation lines keep it. Two headed groups of four pass; a 5+ enumeration that must stay whole goes under headings or into a table, which the block text says.
4. **reply language** — the reply's prose is not Turkish: at least `LANG_MIN_WORDS` = 25 prose words and under `LANG_MIN_SHARE` = 6% of them Turkish. `prose_words` drops fences, table rows, inline code, URLs, paths and identifiers first; `turkish_share` counts a word with a Turkish letter or one of `TR_WORDS` (`hooks/tezgah_integrity.py:316-321`).

The four shape classes share their switches with the text they enforce: `adhd-off` or a repo's `.no-adhd` lifts 1–3 (`_adhd_armed`, `hooks/tezgah_integrity.py:3090-3103`), `exec-mode.off` lifts 4, and a session whose environment carries `TEZGAH_NESTED` (an agent CLI consult started, whose English answer is read by code) is not judged for shape at all. A subagent's reply never reaches the rule: omp's `session_stop` does not fire for task sessions, and Claude and Cursor end a subagent through SubagentStop, which runs no Stop rule. The thresholds were set on the owner's omp transcripts (2026-09-27: 1,495 assistant replies with at least 25 prose words): English prose scored 0.000–0.026, the most English-heavy Turkish reply 0.077 and the bulk 0.3–0.7, and 24 of the 1,495 fall under the cut, all English or Chinese prose. The trade-off is on the Turkish side: a Turkish reply that is mostly quoted English outside backticks can fall under 6%, and the block text tells the model to put the English in backticks or a fence. `tests/test_integrity.py` `ReplyShapeCorpus` pins which realistic replies pass and which block. A lead that announces what follows (`preamble-open`) stays report-only: "Sonuç:" over a list is an answer label and reads like a preamble to any regex.

5. **check failed** — the newest check in the session failed (`:2566-2572`).
6. **partial failure** — this turn recorded a `verify_fail` and nothing passed since (`:2574-2583`).
7. **stale evidence** — the newest check that passed ran before the newest write the gate saw change
   the tree, so it verified an earlier revision of it (`_last_pass`/`_last_change`/`_stale_paths`
   `hooks/tezgah_integrity.py:2654-2686`, branch `:2653-2664`). A write counts as a change whether the gate saw it as a
   write tool or as a shell command that redirected into the file - `_change_row` (`hooks/tezgah_integrity.py:2640-2653`) reads
   an `edit` row, or a `run` row whose captured target moved - while a `verify*` row never does, so
   a check redirecting its own log cannot stale itself. A write *outside* the workspace is not one
   either: the fold's subject is the tree this reply is about, so `_post_write` records no
   after-state for a target beyond the call's own root - a commit message in `/tmp` written after a
   green suite is not a revision of that tree, and reading it as one refused an honest turn.
8. **no verify_ok** — this turn recorded a step (`edit`, `verify`, `verify_fail`, `run`,
   `interrupted`) and no check passed in the session (`:2665-2676`).
9. **no ui_ok** — this turn changed a UI source (`UI_PATH` `hooks/tezgah_integrity.py:82-87`) and the
   check that passed was not one that sees the screen: a unit run never does. A browser/e2e/visual
   check (`UI_CHECK` `hooks/tezgah_integrity.py:102-118`) or a read of the rendered screen (`UI_TOOL`
   `hooks/tezgah_integrity.py:121-124` for the app-analysis tool names, `UI_TOOL_CMD` `:125-134` for the
   CLI capture) is the evidence this class asks for, and it has to be newer than
   the UI write it is about - not than the newest write of anything, so an unrelated file written
   after the screen read does not stale that read (`_ui_evidence` `hooks/tezgah_integrity.py:2768-2798`,
   branch `:2600-2612`). The write kinds are the freshness fold's own (`_change_row`: a write tool's
   `edit` row or a shell call's `run` row the gate saw change the tree), so a UI source written
   through a redirect owes the same proof. The MCP half of that proof is read off the row's own
   tool name (`_screen_read` `hooks/tezgah_integrity.py:2730-2767`), which is the only field that
   says which call a row was - so a row that merely names a browser tool in its command
   (`rg -n browser_snapshot docs/`) is not a read of anything; the CLI capture and the two checks
   are read at a command position on the masked text, `re.M` so that a command on its own later
   line of the same call counts. A component turn owes one thing more: when a changed UI source is
   a component rather than a screen (`DESIGN_COMPONENT` `hooks/tezgah_integrity.py:144-148` - a file
   under a component/views/widgets
   directory, or a name that carries the convention on its own), a fresh read of the screen is not
   enough by itself and a `tezgah-design check` row has to be newer than the component write it
   judges (`_design_evidence` `hooks/tezgah_integrity.py:2799-2819`, branch `:2620-2638`) - and it has
   to be a check whose pass was seen (`passing_check`, `hooks/tezgah_integrity.py:2605-2619`), because
   a screenshot says what a component looks like and the contract is the only thing that says whether
   it is on the repository's floor. The refusal names the command to run. Both of the checker's verbs
   are in `VERIFY` (`hooks/tezgah_integrity.py:57`), so such a run reaches the ledger as a check like
   any other; the verb this branch asks for is `check` - `derive` writes the floor, it does not apply
   it. A screen is unchanged: the page a person looks at owes the read, not the contract.
10. **no external read** — the reply states the state of a system tezgah does not own — a registry,
   a release, a tag, a formula, a CI run — and no read of that system ran in the same turn
   (`_external_claim` `hooks/tezgah_integrity.py:3771-3797`, over `EXTERNAL_SYSTEM`/`EXTERNAL_STATE`
   `:3685-3696` and the CI pair `EXTERNAL_CI`/`EXTERNAL_CI_STATE` `:3697-3704`; branch `:2677-2685`).
   The two halves have to sit within `EXTERNAL_GAP` = 45 characters of each other on one line
   (`_external_pair` `:3758-3770`), and both are read on the reply's prose with inline code, paths,
   URLs and identifiers blanked: `brew tap` inside a code span, the `.github/workflows/...` in a
   citation and a URL ending in `/releases/tag/...` are text about a system, not a claim about its
   state. A tagged release number beside a publish state is the second form (`EXTERNAL_VERSION`
   `:3711-3726`), and its `v` is required, so `SC 2.5.8` and `4.1.3` in prose are not claims and
   neither is a bare version of tezgah's own code. The refusal names the command, chosen by the
   subject the reply used (`_external_command` `:3798-3807`, `EXTERNAL_SOURCE` `:3743-3757`). A local
   client is not the system: `npm --version` is not `npm view`, and a green unit run says nothing
   about what a registry publishes. The read is the evidence, and it is taken by the row's command
   and not by `passing_check` — `npm view` exiting non-zero is the answer for "this version is
   missing" (`_external_read_row` `:3808-3830`) — so a turn whose only work was the read ends. It is
   last of the ten by the branch order above and in its strongest form: it is asked only where the
   fold would otherwise let the turn end, so it turns an allow into a refusal and never changes the
   class another branch refused the same turn under. It is the one class a turn with no work in it
   can make, which is why the "no work, no claim word" exit exempts it (`:2562`) — the two turns it
   was written for ("npm 0.22.0 is missing", read off an out-of-date local npm client, and "make
   NPM_TOKEN an automation token", which it already was) were advice-only, so before this class the
   fold returned `(None, None)` over both and neither was judged at all. Measured over this machine's
   own 2,092 final assistant replies, 2 are read as claims, both in review text about someone else's
   tooling.

The trigger for 5–9 is the turn's own evidence, not its words: a turn that did work and never saw a
check pass is refused whatever the reply says (`:2556-2563`). Two cases are judged against the
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
of both — no work row and no claim vocabulary (`:2562-2563`), the one shape class 10 is exempt from
— or a `passing_check` row newer than the newest write seen to change the tree (`:2650-2652`), where
a fresh screen proof stands in the same
place as a unit pass; when that write was a UI source, the passing row has to be a UI proof — a
check that renders, or a read of the screen — and when it was a component, the design check has to be
newer than that write as well. An explicit admission (`doğrulanmadı`,
`unverified`, `not verified`, `couldn't verify`; `NEGATED` `:242-264`) clears the rule (`:2518-2519`),
checked after the shape branches and before the evidence triggers. The block text is the string the
refusing branch returns; it names the failed
command (`_failed_check` `hooks/tezgah_integrity.py:3210-3224`) and tells the model to report the failure with its exact error
line, or fix it and re-run.

**The escape hatches, and the deny that answers each.** The gate refuses these before they run, under
the same `verify-off` switch (`hooks/tezgah_gate.py:1105-1233`), as rule `shortcut`:

- `--no-verify` on a git/commit/push-style command (`NO_VERIFY` `:158`, `GITISH` `:159`) —
  `shortcut_command` `hooks/tezgah_integrity.py:1897-1907`.
- an env that skips the hooks — `SKIP=`, `HUSKY_SKIP_HOOKS=`, `HUSKY=0` — again requiring the git/hook
  context, so a read that merely mentions `SKIP=` passes (`SKIP_ENV` `:157`, `:1713-1716`).
- a `core.hooksPath` assignment in the same command as a `git commit`/`git push` — `git -c
  core.hooksPath=/dev/null commit`, `git config core.hooksPath "$D" && git commit`, `--config-env`, the
  `GIT_CONFIG_KEY_n`/`GIT_CONFIG_PARAMETERS` env (`_hooks_redirect` `hooks/tezgah_integrity.py:1840-1896`);
  a standalone `git config core.hooksPath .githooks` passes. Set in one call and committed in the next
  is not seen: the rule reads one command line.
- a check chained so it cannot fail: `|| true`, `; true`, `|| exit 0`, `|| :` (`NEUTER` `:151-156`,
  `:1722-1725`).
- a newly added test skip/xfail in a test file (`SKIP_TEST` `:195-204`, path gate `TEST_PATH` `:205-212`,
  per-marker count `_added` `hooks/tezgah_integrity.py:2108-2129`, `shortcut_edit` `hooks/tezgah_integrity.py:2130-2166`). Rewriting an existing skip in place
  passes; one more does not.

Both scans run on text whose strings, comments and heredoc bodies are blanked (`mask` `hooks/tezgah_integrity.py:1747-1752`), so
a commit message that *describes* `--no-verify` is not a bypass while the flag in command position
is. Every denial is itself a `deny` row.

## The session store for the status marks

`<cache>/sessions/<slug>.jsonl`, written by `record()` (`hooks/tezgah_context.py:1564-1587`) and read
by `used()` (`hooks/tezgah_context.py:1842-1862`). A row is exactly `{"kind": kind}` — no timestamp, no outcome, no session —
and the kinds are the used-tool marks [status-line.md](status-line.md) lights up (`graph`, `consult`,
`research`, `judge`), plus one kind per shipped skill a read opened. It is separate from the
[ledger](glossary.md#ledger) because it is display state, not
evidence: nothing refuses a call on it, a kind that is not one of tezgah's is not written at all
(`hooks/tezgah_context.py:1575-1576`), and the reader wants a set of kinds rather than an ordered,
turn-scoped history. The ledger pays a redaction scan and a lock per row; a mark needs neither. The
one mark that is also evidence is `orch`: `record()` writes it as an `orch` row in the session's
ledger too (`hooks/tezgah_context.py:1577-1578`), because a subagent event reaches no other ledger
writer and `fanout` is folded from the ledger.

**Which skill a read opened.** `skill_read_kind` (`hooks/tezgah_context.py:449-483`) earns the mark
the status line draws for the two skills the always-on core tells a session to read (`SKILL_MARKS`:
`pony` for `ponytail`, `adhd` for `i-have-adhd`) and `skill:<name>` for any other *shipped* skill -
one read from the checkout's `skills/` (`shipped_skills` `hooks/tezgah_context.py:416-434`), so an
unshipped name earns nothing, which is what `skill://other` always got. `SKILL_MARKS` itself is not
widened: a mark whose skill the always-on core never names can never flip, and
`tests/test_context.py:1659-1672` requires every entry to be named there. A `skill:` kind is
therefore invisible to the line and its legend - no mark's measure is spelled that way - while
`skill_fitness(window)` (`hooks/tezgah_context.py:1475-1531`) reads it back for the one question the
line never asked. Three surfaces recognise a read, and they have to agree on the two forms
(`skills/<name>/SKILL.md` and `skill://<name>`) and on which name is shipped: the Python hook omp's
bridge calls (`hosts/omp/hook.py:71`), omp's own filter, which decides whether python hears about the
read at all (`hosts/omp/tezgah-hook.ts.in:225-262`, its catalogue the checkout `@HOOK@` names), and
opencode's plugin, which classifies in process because that host has no Python hook
(`hosts/opencode/plugins/tezgah.js:1593-1638`, its catalogue the host's own installed skill dir
(`dirname(CONFIG)/opencode/skills`), which `tezgah-setup` fills with every shipped skill).

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
`hosts/omp/tezgah-hook.ts.in:255-262`, and the hook classifies it, `hosts/omp/hook.py:71`) and
**opencode** (the plugin classifies it, `hosts/opencode/plugins/tezgah.js:1623-1638`) record the mark
or `skill:<name>` for every shipped skill, in either form; **Claude** sees a read, but only in its
transcript, which feeds the status line and writes no row here (`statusline.py:58-107`), so a Claude
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
`<cache>/snapshots/<id>/file`, `meta.json` beside it (`hooks/tezgah_snapshot.py:55-61`, `:67-72`,
`:155-189`), and appends one `snapshot` row whose `detail` is the resolved path, `id` the 12-hex
snapshot id, `hash` the sha256 and `out_bytes` the size (`:184-186`). The row is written last, so it
never names a copy that is not on disk. A credential file (`SECRET_FILE`: `.env*`, `*.env`, key and
certificate files, `id_rsa`-style keys, `credentials.json`, `.netrc`, `.npmrc`, `.pypirc`, `.pgpass`,
`.git-credentials`) gets the row alone - path, size and sha256, no `id` and no copy - so a snapshot
never duplicates a secret, and `rollback` lists it as not restorable (audit L-6). Snapshot files
are written `0600` in `0700` directories. Every host calls `capture` in process except opencode, whose
JavaScript plugin reaches it through `bin/tezgah-capture` (`bin/tezgah-capture:1-20`).

The store is capped twice (`:33-52`): `CAP = 200` snapshots, oldest evicted by directory mtime when a
capture crosses it (`:51`, `_evict` `:83-99`), and `MAX_BYTES = 2 MiB` per file, above which
**nothing is captured at all** — an over-large file is skipped because `capture` runs synchronously in
the gate on the path of the very write it protects, so copying gigabytes would stall that call, and a
refused capture writes no row and so claims no copy (`:38-52`, `:159-162`).

`restore` (`:247-304`) has exactly one caller, `bin/tezgah-rollback`, which a user runs:
`tezgah-rollback <snapshot-id> [--force]` (`bin/tezgah-rollback:24-35`). It refuses an unknown or
malformed id, stored bytes that do not match the recorded hash, and a file that has changed since the
capture — that last one only until `--force`, and the `rollback` row records that it was used
(`:246-266`). The id to pass is on the `snapshot` ledger row for that write (`_snapshot_hash`
`hooks/tezgah_integrity.py:2405-2418`).

`--session <id>` widens that command to a whole session: for every path the session's writes
touched it puts back the EARLIEST snapshot the session took of it — the state before the session's
first write of that path. `session_plan` (`hooks/tezgah_snapshot.py:345-419`) is that reading: it
walks the session's rows in order, names every path an `edit` or shell row wrote (a snapshot row
whose path no write row named — the second file of an `apply_patch` body — is there too), and joins
each to the session's earliest `snapshot` row for it, carrying an `action` that says what the
rollback would do with it: `restore` for a path a write tool changed, `list (shell only)` for a path
only a shell command's redirect touched, `list (unknown writer)` when a shell row's
target could not be re-read so the writer is not known, `list (no snapshot)` for one with no pre-state at all — a
file the session created. Only the `restore` entries are put back
(`restore_session` `hooks/tezgah_snapshot.py:421-436`): which file a command wrote is read off its
text rather than reported by a tool, so a shell-touched path is listed and never reverted even where
the gate captured its target, and the id is printed for a deliberate single-id restore. A relative
target is resolved against the paths the ledger has already resolved — the snapshot rows' own, which
the gate resolved against the call's cwd (`_row_path` `hooks/tezgah_snapshot.py:310-344`). `--dry-run`
prints the plan as `path<TAB>id<TAB>action` and writes nothing: no ledger row, no store change.

The moved-on check is `restore`'s own, fed the session's last recorded hash of the path: the file the
session left behind is what its earliest snapshot is compared with, so the session's own later writes
need no `--force`, while a write by somebody else after the session's last one still refuses. One
refusal does not stop the others — each path is its own file and its own decision — and the exit code
is 1 when any was refused.

At the end of a turn the same set is named where a host can show text without blocking the turn:
Codex's Stop `systemMessage` carries `changed_files_notice`
(`hooks/tezgah_integrity.py:3851-3886`), the turn's `changed_files` as one sorted line, capped at
`CHANGED_NOTICE_MAX` names plus a count of the rest. Claude's and omp's Stop output returns a
decision and nothing else and Cursor's block is a follow-up, so those three name no files: the set is
named to be acted on by the user, never to hold the turn.

**Nothing rolls back automatically, anywhere.** A hook that undoes work can destroy more than the
failure it answers, and its trigger would be a guess about intent wearing a check's clothes
(`hooks/tezgah_snapshot.py:10-18`; `hooks/tezgah_integrity.py:2306-2319`). Repair is the model's or
the user's: fix and re-run, or reach for a snapshot deliberately.

## Untrusted content

A result that arrived from outside the user and this workspace carries a provenance label on the
result itself: `untrusted_label` (`hooks/tezgah_integrity.py:2310-2324`) names the channel — a web
result (`WEB_TOOLS` `hooks/tezgah_integrity.py:2220-2221`), an MCP server (`:1447`), a network read (`NETWORK_READ` `hooks/tezgah_integrity.py:2227-2235`) or a
model on the far side of the network (`TIER_PROGRAMS` `hooks/tezgah_integrity.py:2236-2250`: a `bin/consult`/`bin/codegen`
invocation that reaches a provider) — and tells the model to treat instructions inside it as data.
The call's own row carries the channel in `source` (`hooks/tezgah_integrity.py:2433`).

After that read, the first effect the turn makes — a shell call or a write
(`hooks/tezgah_untrusted.py:39-44`) — carries a taint notice instead (`marks` `:79-91`,
`taint_notice` `:69-78`, `turn_channel` `:47-66`) — which reads the ledger through `turn_rows`
(`hooks/tezgah_integrity.py:929-958`): the whole file's lines, but only the current turn's rows
parsed, so a taint check costs the length of the turn and not the length of the session. It names
the turn, never a cause: whether the
fetched page *caused* the write is not something a hook can see (`:14-17`). One notice per read, and
the effect's own row then carries the channel, so the taint is a transition rather than a repeat.

The taint is a notice, not a refusal: the gate's sink rule, which held an effect in such a turn
until the user's own approval was on the ledger, was removed with the consent rule
([gate](gate.md)). The
label reaches the model on every host that has a surface for it: Claude and dsh through
`hooks/projects-posttooluse.py:85-89`, Codex (`hosts/codex/hook.py:171-173`), Cursor
(`hosts/cursor/hook.py:251-252`), omp (`hosts/omp/hook.py:146-165`), and opencode, whose plugin
cannot import the core in process and mirrors the control in JavaScript instead — the channel on the
call's own row, the label and the taint notice in front of the result the hook is handed, including
the `external` row an MCP answer or a fetched page earns (`untrustedSource`
`hosts/opencode/plugins/tezgah.js:1372`, `labelResult` `:1445`, with the tier's argv reader
`tierRead` at `:1355`). The two halves are pinned against each other over a shared corpus, so neither
can move without failing the other's test (`tests/test_opencode_plugin.py:1343`). One difference is deliberate:
opencode's plugin writes that `external` row itself and carries the channel alone, since the UI rule
`_screen_read` belongs to the Python half and does not run there.

## The counters a maintainer reads

`tezgah-status --counters [session] [path]` (`bin/tezgah-status:72-97`) prints `counters(session)`
(`hooks/tezgah_integrity.py:923-938`) over one session's whole ledger, and `tezgah-status --counters
--all` prints `counters_all()` (`hooks/tezgah_integrity.py:1437-1462`) over every real-session ledger on the machine, adding `ledgers`, the
number of files it read, and `fixtures`, the ledgers left out because every workspace they name is a temp, OpenResearch run or arm-bench tree (`fixture_ledger`). Both fold their rows through `_counts` (`hooks/tezgah_integrity.py:1463-1605`), the one implementation
of the arithmetic, so a total cannot drift from the sessions it sums - the `:NNN` rows below are that
fold. `counters_all` bounds nothing: a window or a row cap would make the total contradict the
per-session numbers it claims to be, and the whole corpus here folds in 0.4 s (58,928 rows, 1,120
real ledgers, measured 2026-09-30).

Each key, as both readers produce it:

- `events` — every row; `kinds` — a histogram of them.
- `steps` — rows whose kind is in `STEP_KINDS` (`hooks/tezgah_integrity.py:1194-1199`): work rows only,
  `interrupted` among them, since a call the host stopped was still issued.
- `tool_error_rate` — non-zero `exit` values over every row carrying an `exit` (`:1113-1116`, `:1092`);
  a host reporting no outcome contributes to neither half, so every row with an `exit` counts.
- `claims` and `false_completion` — the `claim` rows, and those whose detail starts with `blocked`
  (`:1122-1133`), except a shape class (`SHAPE_BLOCKS`): a reply refused for its list or its language
  made no false claim, so it counts as `shape_blocked` instead.
- `replies` and `shape` — the `shape` rows, written for every judged reply, and those carrying a
  report-only flag (`:1139-1146`).
- `denies` — `deny` rows grouped by the text before the first colon (`:1117-1119`), which is the rule
  name (`shortcut`, `loop`, `race`, …); `nudges` and `fanout` — the nudge rows and
  the subagent-ish kinds (`:1120-1121`, `:1155-1156`), the `orch` rows among them written by `record()`
  for every subagent event a Python adapter sees.
- `consult`, `codegen`, `codegen_failed` — substring matches on `detail` (`:1147-1152`).

The one ratio that matters is **`false_completion / claims`**: how often a reply claiming completion
or verification had to be refused — the only number here that measures the layer's effect rather than
its traffic, and the one its own docstring names as the point of the counters (`:1082-1083`). One
- `weeks`, `tools`, `programs` — present only when the caller asked (`counters(..., weeks=True,
  tools=True)`), which is what `tezgah-status --counters --trend` passes; see below.
ledger is an anecdote; `--counters --all` is the same ratio over the corpus, 0.224 across 1454
ledgers when this was written, which is the reading no single session could give.

### The drift series and the firing histograms

`tezgah-status --counters --trend [--weeks=N]` prints two reports the same fold carries, because a
value is a reading and the thing worth watching is the population over time. Both are filled inside
`_counts` (`hooks/tezgah_integrity.py:1463-1605`) in the same pass as the totals, so neither can
disagree with the number it is drawn from; both are off unless the flag asks, so the plain and the
`--json` output of a reader who did not ask are byte-identical to what they were.

- **The drift series** — `weeks`, every row bucketed by `ts` on a fixed 7-day grid (`WEEK`, anchored
  on the Monday of the epoch's first week, `_week` `hooks/tezgah_integrity.py:1225-1230`), each bucket
  counting its events, claims, refused claims and decided attempts. `drift_series(counters, weeks)`
  (`hooks/tezgah_integrity.py:1166-1206`) re-slices them into the last `weeks` calendar weeks, oldest
  first, with `false_completion/claims` and `tool_error_rate` per bucket, and the direction of the
  newest three weeks that carry a denominator (`_direction` `:1329-1346`, compared by
  cross-multiplication so a shared rounding is never called flat). A week with no row prints a zero
  row count and `n/a` for both ratios, never `0.0`: an empty week is not a week with a perfect rate,
  and a gap has to read as a gap. Nothing is windowed out of the totals.
- **The tool firings** — `tools`, a histogram over `_tool_name(entry)` (`hooks/tezgah_integrity.py:1119-1137`):
  the row's `tool` field, else the name an `unknown` row (`unknown tool: <name>`) or an MCP `external`
  row (`mcp <name>`) kept in `detail`. A work row written before the `tool` field landed carries no
  name at all - `classify` folded it into a kind - so an old corpus under-counts, which is the
  honest ceiling and the reason the field exists; every row written since carries it, because both
  writers write it (`note_tool` `hooks/tezgah_integrity.py:2480-2598`, and opencode's plugin
  `hosts/opencode/plugins/tezgah.js:774-782` - before that second one did, an opencode work row was
  the other half of this under-count, with its name unrecoverable in the command `detail`). A read
  tool is not in it either: reads record no row by design.
- **The shipped programs** — `programs`, the `bin/` programs a command row really ran, read with the
  tokenizer the status line already uses (`_ran_programs` `hooks/tezgah_integrity.py:1276-1299`), and
  `unfired_programs(counters)` (`:1207-1223`), the catalog minus that set. The absence is the
  evidence: a tool nobody calls leaves no row, so the only way to name it is a catalog, and the one
  catalog this layer holds is its own `bin/` (`shipped_programs` `:1234-1253`). The prefilter is one
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

## Source of truth

- `hooks/tezgah_integrity.py` — ledger, kinds, redaction, Stop rule, counters
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
