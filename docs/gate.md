# The gate: every refusal, and what lifts it

This page answers one question: why a tool call was refused before it ran. It is written for the maintainer adding a rule or reading a "the gate missed this"
report, and for the session that has just met a refusal in its transcript. [architecture.md](architecture.md) places the gate among the layers;
[evidence.md](evidence.md) describes the [ledger](glossary.md#ledger) a refusal writes to; [hosts.md](hosts.md) covers the per-host envelopes.

## Where it sits in the call path

One function decides every refusal: `decision(tool, inp, cwd, session_id)` returns a reason string or `None`, and nothing else
(`hooks/tezgah_gate.py:1378-1572`). It answers only inside a tezgah [root](glossary.md#root): outside one `root_for` returns nothing and every call passes
(`hooks/tezgah_gate.py:1213-1215`). The `pretooluse-off` kill switch drops the whole gate (`hooks/tezgah_gate.py:1211-1212`).

Each host's pre-tool hook calls it and wraps the string in that host's own deny envelope — opencode's is its `tool.execute.before`, which throws
`new Error(deny)`; a `None` prints no envelope at all.

| Host | Adapter | Refusal envelope |
|---|---|---|
| claude, dsh | `hooks/projects-pretooluse.py:24-30` (`hosts/dsh/hooks.json:13`) | `hookSpecificOutput.permissionDecision: "deny"` |
| codex, cursor, omp | `hosts/codex/hook.py:151-158`, `hosts/cursor/hook.py:336-337`, `hosts/omp/hook.py:118-121` | that host's own envelope — [hosts.md](hosts.md) |
| opencode | `hosts/opencode/plugins/tezgah.js:1621` | `new Error(deny)` thrown at `hosts/opencode/plugins/tezgah.js:1735` |

Every refusal is also recorded before it is returned: `_deny` appends a ledger row `deny` whose `detail` is `"<rule>: <reason, first 80 chars>"`, plus any
`extra` (`hooks/tezgah_gate.py:1362-1377`). That row, not the reason wording, is where "why was this denied" is answered, and `<rule>` is the name used below.

A call the gate lets through is also where it keeps the pre-write bytes: `capture` runs for a write tool, and for a shell command that writes a file through a
redirect or `tee` - the same shape the task phase rule reads, `write_paths` returns the target for both routes, and a shell write gets its pre-state the same
way (`hooks/tezgah_gate.py:1308-1327`, `write_paths` `hooks/tezgah_gate.py:592-619`, `shell_target` `hooks/tezgah_gate.py:944-983`). Without it the after-state alone
cannot tell a redirect that wrote the file from one that wrote what was already there, and the freshness half of the Stop rule would read every redirect as a
change; the two halves of that rule are `hooks/tezgah_integrity.py`'s and are described in [evidence.md](evidence.md).

## The rules, in the order `decision` checks them

Bare `:NNN` references on this page are `hooks/tezgah_gate.py` unless another file is named. Each rule ends with its reach: *once*, a mark lifts the next
identical call; *standing*, only changing the call does.

### Explorer — the grep-only subagent

Trigger: tool `agent`/`task`/`subagent` whose `subagent_type` is `explore` or `explorer`, case-insensitively (`hooks/tezgah_gate.py:1060-1061`, `explored` `hooks/tezgah_gate.py:368-372`). Told: use
the general-purpose agent and name the codegraph tools in its prompt (`EXPLORE_DENY` `hooks/tezgah_gate.py:217-223`). Standing: no mark, every such
request is refused.

### Shortcut — a check made unable to fail, or a test disabled

Trigger, shell: `--no-verify`, or `SKIP=`/`HUSKY_SKIP_HOOKS=`/`HUSKY=0`, next to a git/hook word; or a `core.hooksPath` assignment (`git -c core.hooksPath=...`, `git config core.hooksPath <dir>`) in the same command as a commit/push (`HOOKS_PATH` `hooks/tezgah_integrity.py:148-151`, `GIT_WRITE` `:152`, branch `:1549-1553`; husky's standalone setup and a `--get`/`--unset` pass); or a verification command chained with `|| true`/`; true`
(`hooks/tezgah_integrity.py:1534-1563`, `NO_VERIFY` `:139`, `SKIP_ENV` `:138`, `NEUTER` `:133-137`, `GITISH` `:140`). Trigger, edit/write: a skip marker newly
introduced into a test file — the path must match `tests?/`, `test_*`, `*_test`, `*.test.*` (`TEST_PATH` `:164-171`), the marker must survive `mask()` so one
inside a string or comment does not count, and `_added` compares against the file's own text on disk for a `Write` (`:1309-1328`, `SKIP_TEST` `:154-163`). Told:
the texts at `:1245-1255` and `:1361-1363` — run the checks, or say the test is failing; ask the user first if the skip is intended. Standing, with one switch:
`verify-off` removes this check (`hooks/tezgah_gate.py:1235-1252`). The shell is a write route like any other, and the one E7c measured an
armed session taking once the write tools were refused: a heredoc that writes a skip into a test file meets the same predicate, run over the body the
command would land (`shell_write_body` `hooks/tezgah_gate.py:1005-1047`, read at `hooks/tezgah_gate.py:1192` — the body is the raw text, because `mask()` blanks
heredoc bodies by design).

### Piped — a check whose status a trimmer owns

Trigger: a verification command (integrity's `VERIFY`) piped into a trimmer or filter — `tail`, `head`, `grep`/`egrep`/`fgrep`, `cut`, `wc`, `sed -n`, with
`|` or `|&`, a `tee` in between included — in one `&&`/`;`-separated segment of the line (`piped_check` `hooks/tezgah_integrity.py:1579-1610`, `TRIMMER`
`hooks/tezgah_integrity.py:1566-1568`). The line's exit status is the trimmer's, so the ledger can only record the check as ran, never as passed, and the Stop rule
then refuses every claim the run was meant to carry — observed in a real omp session where 13 checks ran piped and 3 of 6 completion claims were blocked.
Passes: a line that opens with `set -o pipefail` (`PIPEFAIL` `hooks/tezgah_integrity.py:1564-1565`), which integrity then records as decisive
(`verify_ok`/`verify_fail`, [evidence.md](evidence.md)); a redirect to a file; a pipe of anything that is not a check (`git log | head`). Told: redirect the
check to a file and read the file, or prefix `set -o pipefail;`, with the check named as it was typed. Standing, under `verify-off`
(`hooks/tezgah_gate.py:1235`). opencode asks the core for this rule on any shell line that pipes a check
(`hosts/opencode/plugins/tezgah.js:1687`) and records such a line as `verify` unless it opens with pipefail (`hosts/opencode/plugins/tezgah.js:638`).

### Attribution — an AI/model credit on its way into an artifact

Trigger, shell: a write command (`WRITE_CMD` `hooks/tezgah_gate.py:177-190` — `git commit|merge|tag|notes`, `gh api`,
`gh pr|issue|release create|edit|comment|review|merge|close`) carrying a credit form (`ATTRIB` `hooks/tezgah_gate.py:155-165` — `co-authored-by:`, `generated with`, `made with`,
`built by`, `assisted by`, `authored by`, `noreply@anthropic`, a robot emoji). Trigger, edit/write: one of the content fields `EDIT_TEXT` (`hooks/tezgah_gate.py:168-175`)
containing a line that *starts* with a credit (`ATTRIB_LINE` `hooks/tezgah_gate.py:166-167`). Told: remove it and re-run; naming a tool in order to use it is fine, crediting it
as author is not (`ATTRIB_DENY` `hooks/tezgah_gate.py:224-230`). Standing. The line anchor is why prose that merely names the banned forms passes (`hooks/tezgah_gate.py:132-149`).
The same twin as the shortcut rule's: a credit a heredoc writes into a file is refused from the body (`hooks/tezgah_gate.py:1201-1202`), and no command has to be
a `git`/`gh` write for it to be this rule's.

### Language — an identifier or message that is not English

Trigger, shell: a command that would create an identifier - `git checkout -b`/`git switch -c`, `git branch` with a new name, a commit subject (`git commit -m`/`--message`/`-F`), or a `gh pr|issue create --title` (the language section `hooks/tezgah_gate.py:237-348`, `created_texts` `hooks/tezgah_gate.py:331-353`; the text is read from the raw command, because `mask()` blanks quoted strings and a commit subject is one) - whose name or subject is **not English**: a letter outside ASCII anywhere (`non_english` `hooks/tezgah_lang.py:45` - a predicate rather than one language's letter list, so Russian, Greek, Arabic, Chinese and accented Latin hit it exactly as Turkish does) or an ASCII-folded Turkish word from the curated list (`ENGLISH` `hooks/tezgah_lang.py:76`, wi…

The rule is a **heuristic** and its own text says so: a word list is not a language detector, so it cannot tell a proper noun or a product name in another language from a word that ought to be English, and a listed word may be the user's own term. A command that only names the words - `echo`, `grep`, `git log --grep` - creates nothing and passes. An identifier outlives the session that typed it, which is the reason the rule exists at all: `plan/004-admin-durum-onarimi` is in a public history from the moment it exists. On **opencode** the rule is not ported: the plugin asks the core for it through `bin/tezgah-gate check`, one spawn for a command its pre-test reads as identifier-creating (`IDENT_CMD` `hosts/opencode/plugins/tezgah.js:334`, the call site `:1670…

### Race — another session wrote this file minutes ago

Trigger: a write tool whose path, or `apply_patch` header, another session recorded a write of inside `RACE_WINDOW_MIN = 10` minutes (`hooks/tezgah_gate.py:545`, `race_reason`
`hooks/tezgah_gate.py:620-657`, reader `writers_elsewhere` `hooks/tezgah_integrity.py:937-1002`). Told: re-read the file and re-apply the change to what is on disk now (`RACE_DENY`
`hooks/tezgah_gate.py:570-581`). Standing (`RACE_REFUSE = True` `hooks/tezgah_gate.py:549`) — a notice would not close a silent overwrite — and it lifts only by time.

### Task — the user's own phase and path allowlist

Trigger: a write tool, or a shell command that writes a file, while an active task is set — a plan file under `.tezgah/plans/open` whose frontmatter carries a valid
`phase` (`tezgah_task.active`). The phase refuses a write in a reading phase (`TASK_PHASE_DENY` `hooks/tezgah_gate.py:658-661`) and a shell command that writes one (`TASK_SHELL_DENY` `hooks/tezgah_gate.py:709-720`,
against `SHELL_WRITE` `hooks/tezgah_gate.py:700-708`); the allowlist refuses a target outside it (`TASK_SCOPE_DENY` `hooks/tezgah_gate.py:662-670`); and the record itself is refused twice over — a write whose target IS it
(`TASK_RECORD_DENY` `hooks/tezgah_gate.py:671-674`) and a shell command that would change it through the CLI (`TASK_UNLOCK_DENY` `hooks/tezgah_gate.py:675-681`, matched on the masked text by `TASK_CHANGE` `hooks/tezgah_gate.py:682-699`). Told:
none of them names the command that lifts it, on purpose — with the unlock printed, an armed arm removed or disabled the gate in 25 of 25 runs and obeyed it in none
(`hooks/tezgah_gate.py:665-669`) — so each names the phase or the allowlist as the user's to change. Standing: only the record changing lifts it. Off: `task-off`
(`hooks/tezgah_gate.py:1456`). It fails open wherever the question cannot be answered: no active task, no readable record; the record is written by `bin/tezgah-task` and
never by the agent, so this rule refuses on a decision the user made rather than one the gate inferred.

The fifth refusal under the same rule is the checkpoint. Trigger: a write, or a shell command that writes a file (`SHELL_WRITE` `hooks/tezgah_gate.py:700-708`), while the task is in
`phase: implementation`, its record reads `checkpoint: pending <sha>`, that sha is still the checkout's HEAD and the tree is dirty (`checkpoint_reason()`
`hooks/tezgah_gate.py:847-892`, `CHECKPOINT_DENY` `hooks/tezgah_gate.py:838-846`). Told: the task it read, that the record holds a `pending` checkpoint, and the one command
that makes the boundary real - unlike the refusals above it names that command, because running it *satisfies* the rule rather than taking it off. Standing: the recorded sha is the switch, not the tree - the commit
the refusal names moves HEAD off that sha, so the refusal clears itself, where keying on the word `pending` alone left the phase waiting on a record only
`bin/tezgah-task` rewrites. Off, with the rest of the rule: `task-off`. It fails open wherever the question cannot be answered: no record, no `checkpoint:` key, a
checkpoint that is a plain sha (the boundary is already real), a `pending` with no sha, a sha this checkout's HEAD does not name, and a repo whose HEAD cannot be read.

### Secret — a credential on its way into a file

Trigger: one simple command (split on `&&`, `||`, `;`, newline — `SEGMENT` `hooks/tezgah_gate.py:203-204`) carrying both a token (`SECRET_TOKEN` `hooks/tezgah_gate.py:186-193` — an
`Authorization: Bearer` header, or a `name=value` assignment for `api_key`/`token`/`secret`/`password`/...) and a sink (`SECRET_SINK` `hooks/tezgah_gate.py:199-207` — `>`/`>>`,
`| tee`, a curl `--trace`, or `git add`); `secret_command` `hooks/tezgah_gate.py:530-564`. Told: record the name, length or a fingerprint instead, and pass the value through the
tool's environment (`SECRET_DENY` `hooks/tezgah_gate.py:210-216`). Standing, no escape hatch. The shell's own write route is the third twin: a credential inside a heredoc body
is refused from the body (`hooks/tezgah_gate.py:1253-1254`), because `mask()` blanks that body and the text-level scan above cannot see it.

### Workspace — tezgah state outside `.tezgah/`

Trigger: a write tool, or a shell redirect/`tee` (`write_paths`), whose target relative to the repo root starts with `plans/`, `research/` or `analysis/` while the project tracks no file under that directory (`workspace_reason`, `hooks/tezgah_gate.py`). The refusal names `.tezgah/<kind>/` as the place to write. A directory the project already tracks is its own and passes. `mkdir` and positional shell targets (`cp`, `mv`) are not read - the same ceiling as `write_paths`. Off: `workspace-off`.

### Plan — a turn's third product file on `main`

Trigger: a write tool, or a shell redirect/`tee` (`write_paths` `hooks/tezgah_gate.py:592-619`), whose target is a product path, while the checkout is on `main` or `master` and this turn has
already written two other product files (`plan_reason` `hooks/tezgah_gate.py:1335-1361`, `_branch` `hooks/tezgah_gate.py:1241-1263`, `_product_path` `hooks/tezgah_gate.py:1317-1334`). The
count folds the turn's own write rows (`turn_rows` `hooks/tezgah_integrity.py:823-852`) together with the files the call in hand names, so it needs no state of its own, and it counts DISTINCT
paths - a turn that rewrites one file three times is still one file's work. The product paths are the ones at the repository root that a plan exists to scope - `hooks/`, `tests/`, `bin/`,
`skills/`, `docs/`, `statusline.py` and `MANIFEST` (`PLAN_DIRS`/`PLAN_FILES` `hooks/tezgah_gate.py:1209-1211`); a `.tezgah/` path is never one of them, and neither is a path outside the
repository. Told: the branch it read, how many files the turn has written, and the command that opens a plan - the `plan-add` skill, `/tezgah:plan-add <description>` (`PLAN_DENY`
`hooks/tezgah_gate.py:1213-1222`). Standing: only changing the tree's state changes it - the work moves to the `plan/NNN-slug` branch the skill creates (a one- or two-file fix is free either
way), or the repository carries a `.no-plan-gate` mark (the shape of `.no-graph` and `.no-lessons`). It passes wherever the question cannot be answered: no session or ledger, a directory that is
not a git repository, and a detached HEAD with no branch to name.

### Ordering — a commit while the newest check failed

The one rule here that asserts a relation between two actions rather than reading one call plus a ledger tail, and the shape FAVA found in 90% of real
agent-instruction projects ("do not commit before running the tests").

Trigger: the command is a `git commit` (or `--amend`; `COMMIT_CMD` `hooks/tezgah_gate.py:1049-1050`, matched at `hooks/tezgah_gate.py:1261`) and the newest check in
this session **failed**. The state is the Stop rule's own fold over the ledger tail (`ORDER_TAIL = 200` `hooks/tezgah_gate.py:893`, the fold
`tezgah_integrity._last_verify`), and the rule is structurally incapable of firing in either direction that would punish honest work: no check at all folds
to `None` and a passing newest check folds to `ok`, so a commit in a session that ran no check — a docs-only commit — and a commit after a green run both
pass. Only `fail` refuses: the tree the commit would freeze is the one a check just rejected.

Told: the failed check by name and nothing else (`ORDER_DENY` `hooks/tezgah_gate.py:1051-1058`, `commit_order_reason` `hooks/tezgah_gate.py:1059-1088`) —
making the newest check pass is the whole repair, so the refusal names no command that lifts it, for the reason the task refusals carry. Standing while the
tail still shows that failure, under `verify-off` (`hooks/tezgah_gate.py:1260`). Its deny row is its own rule name (`order`), so the counters separate it.

### Loop — the identical attempt that already failed twice

Trigger: the same call (same `call_id`) failed `LOOP_ATTEMPTS = 2` times already in the current user turn (`hooks/tezgah_gate.py:448-448`, `loop_reason` `hooks/tezgah_gate.py:473-503`). Told: attempt N
of an identical call, the failure class read from the ledger (`transient`, `user`, `permanent`, `unknown`; the cap is the same for every class, and a `user` failure - a 401/403, a missing credential, a login - says to ask the user), "change the approach or stop" (`hooks/tezgah_gate.py:473-481`). Standing while the ledger tail still shows those
failures. Under `verify-off` (`hooks/tezgah_gate.py:1271`).

### Retry — the session-wide ceiling

Trigger: the same call has been attempted more than `RETRY_CEILING = 3` times in the session, whatever those attempts returned (`hooks/tezgah_gate.py:470-472`, `retry_reason`
`hooks/tezgah_gate.py:504-529`). Told: an unchanged repeat is not a retry (`hooks/tezgah_gate.py:502-507`). Standing. Under `verify-off` (`hooks/tezgah_gate.py:1271`). Both guards read only the ledger tail.

### Nudge — the first identifier-shaped search of a session

Trigger: a `Grep` whose pattern, or a `grep`/`rg` argument (`BASH_SEARCH` `hooks/tezgah_gate.py:133-148`), matches `IDENT` (`^[A-Za-z_][A-Za-z0-9_]{2,}$`, `hooks/tezgah_gate.py:113`), in a repo whose
codegraph index exists (`<repo>/.codegraph/codegraph.db`; `searched_identifier`
`hooks/tezgah_gate.py:373-387`). Told: the runnable command built from the denied search (`codegraph explore <X>`, `codegraph callers <X>`, `codegraph impact <X>`), and that an omp subagent uses this CLI because omp's MCP device refuses concurrent writes
(`nudge_reason` `hooks/tezgah_gate.py:427-447`).
Once-only: the mark in `cache_dir()/nudged/<session>` is written *before* the refusal, so re-issuing the search passes (`first_nudge` `hooks/tezgah_gate.py:410-426`).

### Drift — a long turn loses the rules it started with

Trigger: 25 work rows (`DRIFT_STEPS` `hooks/tezgah_gate.py:1089-1093`) in the current user turn and an effectful call — a write tool, or a git/gh artifact command (`effectful`
`hooks/tezgah_gate.py:1066-1074`). Told: the standing constraints re-stated, or the delta since the turn began; "re-issue this call unchanged and carry on" (`DRIFT_DENY` `hooks/tezgah_gate.py:1095-1101`,
`drift_reason` `hooks/tezgah_gate.py:1139-1168`). A refusal, last in `decision` after every other rule, and its only delivery: no host's PostToolUse side carries it, and opencode gets it from the core through `bin/tezgah-gate` on its write path. Once per turn: the `drift` mark is written *before* the refusal, so the identical call passes on the next attempt, and the count behind it is the turn's own — a bounded read (`DRIFT_TAIL` `hooks/tezgah_gate.py:1094-1094`) falls back to the turn's own start (`turn_rows` `hooks/tezgah_integrity.py:823-852`) when the turn outgrew the window. Governed by `reminder-off`, not `verify-off` (`hooks/tezgah_gate.py:1003`).

## What the gate deliberately does not catch

Read this before filing a security-ish issue; each is a decision, not an oversight.

- Irreversible and outward-facing shell commands — force-pushes, migrations, deploys, `ssh`, `scp`, a `curl` write, a `gh pr` write — run without an ask.
  The consent rule and its `send`/`outward`/`deploy`/`publish`/`schema`/`destructive` class table were removed on purpose (2026-09-26): the ask it put in
  front of every server-side command cost a round-trip per effect, the user's chat approval could not lift it (only the deleted `bin/tezgah-consent` CLI
  could), and the sessions it actually gated were the user's own deploys. The untrusted-read half went with it: a turn that read web content may now run an
  outbound effect carrying only the taint notice, with no refusal in between. The notice itself stays (`hooks/tezgah_untrusted.py`).
- A write inside the root after a fetch: left to the taint notice that `hooks/tezgah_untrusted.py` rides the first effect with, because it is recoverable from
  the snapshot.
- `grep -A 3 foo`: a flag with its own value shifts the token, so the search passes unnudged (`hooks/tezgah_gate.py:114-115`).
- A foreign `apply_patch` write: the PostToolUse writer records no path for that row (`hooks/tezgah_gate.py:606`); and a second session that spells the path differently
  escapes the rule, because the ledger keeps no `cwd` (`hooks/tezgah_gate.py:559-561`).
- Which rule the user meant when a turn drifts: "a guess about intent wearing a check's clothes" (`hooks/tezgah_gate.py:990`).
- A skip already in the file, or one inside a string (a test *about* the rule), is not a disable (`hooks/tezgah_integrity.py:1309-1328`).
- The content of a shell write that is not a heredoc: `echo "Co-Authored-By: x" > f` puts the credit inside a quoted string that no line-start anchor can see,
  and reading the whole command instead would deny a search for the form (`grep "Co-Authored-By" x > out`). The three twins read a heredoc body, which is the
  route E7c measured (`shell_write_body` `hooks/tezgah_gate.py:1005-1047`).
- A shell write whose target is not a redirect: `cp`, `mv`, `sed -i`, `patch` and `git apply` name it as a positional argument, and which argument of those is
  the target is a per-program question, so the gate keeps no pre-state for it and the freshness half reads no change there (`write_paths`
  `hooks/tezgah_gate.py:592-619`). A shell write chained with a check in one call (`sed -i ... && pytest`) records as the check row, and the row that carries a
  pass is never the row read as the change - otherwise a check redirecting its own log would stale itself (`tezgah_integrity._change_row`).
- A PRIOR shell write's target, in the plan rule's count: a write the shell landed is a `run` row whose detail is the command, so the count reads the turn's
  write-tool rows plus the redirect the call in hand names (`plan_reason` `hooks/tezgah_gate.py:1335-1361`). Three heredocs into product files in one turn
  therefore pass where the same three through the write tools are refused, and reading a stored command line for its target would be a second reader of the
  table `write_paths` already holds.

**The seat a semantic rule would take on the Stop path, and why it stays empty.** The Stop rule's
claim detector is a vocabulary (`DONE`/`VERIFIED`, `hooks/tezgah_integrity.py`),
so it is the second place a classifier could sit - "does this reply claim the work
is done?". Measured 2026-09-19 over this machine's own 161 final replies from
`~/.omp/agent/sessions/-Projects-tezgah` and a hand-drawn set of 15 completions
stated as a *completed state*: the list caught 2 of the 15, and the misses are all
one shape - the Turkish passive and the English state predicate (`güncellendi`,
`kuruldu`, `düzeltildi`, `yayına girdi`, `landed`, `merged`, `is green`, `all checks
pass`). That is a lexical hole, not a semantic one, and naming 11 of the 13 closes
it: the list carries them now, 39 of the 161 replies are read as claims instead of
34, and 0 of the 5 control replies (a question, a plan, an explicit
`doğrulanmadı`) is claimed. The verdict never moved, which is the point - a turn
that recorded work is refused on its evidence whatever its wording (the `worked`
trigger, which is how this detector's real semantic weakness - the same unfounded
state stated as a description - was answered, at 0 of 10 refused before it). A
model here would be a synchronous remote call on the Stop event of four hosts, to
widen a list a regex already covers.

## The mirror: the opencode plugin

opencode cannot run Python hooks, so `hosts/opencode/plugins/tezgah.js` is an independent JavaScript re-implementation of the same rules, dispatched from
`tool.execute.before` (hosts/opencode/plugins/tezgah.js:1663, exported `hosts/opencode/plugins/tezgah.js:1621`) in the gate's own order (`hosts/opencode/plugins/tezgah.js:1673-1791`); its shortcut constants restate the same regexes (`NEUTER` `hosts/opencode/plugins/tezgah.js:261`,
`SKIP_ENV` hosts/opencode/plugins/tezgah.js:262, `NO_VERIFY` hosts/opencode/plugins/tezgah.js:263, `GITISH` hosts/opencode/plugins/tezgah.js:264, `SKIP_TEST` hosts/opencode/plugins/tezgah.js:265). What keeps the two halves honest is a test, not a shared module:
`tests/test_opencode_plugin.py` drives the plugin's hooks through a node harness with a throwaway HOME, and imports the Python `tezgah_integrity.call_id` so a
separator or canonical-form drift in the action id fails there instead of silently in a session (`tests/test_opencode_plugin.py:1-7`, `:21-24`, `tests/test_opencode_plugin.py:1054-1093`).

The shell rule kinds mirrored last are each pinned in both suites: the shell's write body (`SHELL_WRITE` `hosts/opencode/plugins/tezgah.js:447`,
`heredocBodies` `hosts/opencode/plugins/tezgah.js:453`, `shellWriteBody` `hosts/opencode/plugins/tezgah.js:497`, the shortcut and attribution twins at
`hosts/opencode/plugins/tezgah.js:1712` and `hosts/opencode/plugins/tezgah.js:1687`, the credential twin at `hosts/opencode/plugins/tezgah.js:971-974`) and the
ordering obligation (`COMMIT_CMD` `hosts/opencode/plugins/tezgah.js:902`, `ORDER_DENY`
`hosts/opencode/plugins/tezgah.js:904`, `lastVerify` `hosts/opencode/plugins/tezgah.js:914`, `orderReason` `hosts/opencode/plugins/tezgah.js:939`, dispatched at
`hosts/opencode/plugins/tezgah.js:1750`). `lastVerify` folds the tail exactly as `_last_verify` does, minus the `passing_check` narrowing - this rule reads only
`fail`, and a row that narrowing would refuse reads `ok`/`ran` on both sides, so the outcome is identical.

## Rule provenance

A rule is a refusal with a cause: something happened, the check was written, and a case was added so it cannot happen again unnoticed. That record used to live
only as a sentence inside each rule's own paragraph above. It is a table here instead, so it is one place and a machine reads it: `bin/tezgah-docs --citations`
opens `docs/gate.md`, reads this table, and refuses a rule name the source can still produce with no row, and a row whose `pin` names a test that does not exist.
The names are read off the source, not restated: the gate's rules are the `_deny(session_id, "<rule>", ...)` calls in `hooks/tezgah_gate.py`, and the Stop
rule's triggers are the classes `_stop_block` returns, the four `_shape_block` hands back included.

- `incident` — what produced the rule; `designed` where none is recorded. The ratio of incident-derived to designed rules is the maturity signal the research
  entry names, which is why the distinction is written down rather than smoothed over.
- `evidence` — where that incident is written down: the page section, the module comment, or the experiment's own preregistration.
- `pin` — the case that guards it, as `tests/<file>.py::<test_name>`. The checker refuses a pin that names no test, so the case and the row move together.
- `since` — the first commit in this repository's history that carries the rule (`git log -S`; where the history was rewritten, it is the earliest one left).

| rule | incident | evidence | pin | since |
|---|---|---|---|---|
| `explorer` | designed | the grep-only subagent was replaced by the graph tools; no incident recorded | `tests/test_gate.py::test_explore_subagent_denies` | 2026-09-23 |
| `shortcut` | E7c: with the write tools refused, 3 of 25 armed runs wrote a test skip through a heredoc | `benchmarks/lab PREREGISTRATION-E7.md`, on the `benchmarks/lab` branch | `tests/test_gate.py::test_a_shell_write_that_disables_a_test_is_denied` | 2026-09-23 |
| `piped` | a real omp session: 13 checks ran piped and 3 of 6 completion claims were blocked | the Piped section above | `tests/test_gate.py::test_a_piped_check_is_refused_and_pipefail_passes` | 2026-09-27 |
| `attribution` | E7c: the same 3 of 25 runs, a credit written through a heredoc | `benchmarks/lab PREREGISTRATION-E7.md` | `tests/test_gate.py::test_attribution_denies_a_credit_written_by_the_shell` | 2026-09-23 |
| `lang` | a plan branch was created as `plan/004-admin-durum-onarimi`, and its slug is in the public history for good | `hooks/tezgah_gate.py:257-266` | `tests/test_gate.py::test_a_turkish_branch_name_is_refused` | 2026-09-23 |
| `race` | two sessions on one file - a parent and its subagent, or two worktrees - landing on a stale read | `hooks/tezgah_gate.py:549-555` | `tests/test_gate.py::test_a_write_to_a_file_another_session_wrote_is_refused` | 2026-09-23 |
| `task` | E7: with the unlocking command printed, an armed arm removed or disabled the gate in 25 of 25 runs; E7b: the heredoc redirect in 3 of 25 | the Task section above (the checkpoint refusal) | `tests/test_gate.py::test_a_reading_phase_refuses_a_write_inside_the_allowlist` | 2026-09-23 |
| `secret` | E7c: the same 3 of 25 runs, a key written through a heredoc | `benchmarks/lab PREREGISTRATION-E7.md` | `tests/test_gate.py::test_a_credential_written_by_a_heredoc_is_denied` | 2026-09-23 |
| `workspace` | sessions wrote root `plans/`, `research/` and `analysis/` (observed in `~/Projects`: Ustam, codexit, sharelinks-intelligence) | `hooks/tezgah_gate.py:886-887` | `tests/test_gate.py::test_untracked_root_kinds_are_refused_for_tools_and_redirects` | 2026-09-27 |
| `plan` | a turn wrote four product files - a hook, its tests, its docs and the changelog - straight onto `main` | `hooks/tezgah_gate.py:1185-1186` | `tests/test_gate.py::test_the_third_product_write_on_main_is_refused` | 2026-09-29 |
| `order` | FAVA: the shape found in 90% of real agent-instruction projects ("do not commit before running the tests") | the Ordering section above | `tests/test_gate.py::test_a_commit_is_refused_while_the_newest_check_failed` | 2026-09-23 |
| `loop` | designed | the turn's own repeated failure; no incident recorded | `tests/test_gate.py::test_an_identical_failed_call_is_denied_after_the_ceiling` | 2026-09-23 |
| `retry` | designed | the session ceiling over the same guard; no incident recorded | `tests/test_gate.py::test_a_fourth_identical_call_is_refused_whatever_the_outcome` | 2026-09-23 |
| `drift` | plan 004's flip rule on the 2026-09-20 move to a result-channel notice: at 27 sessions the blocked-claim rate in turns under 25 work rows read 112/140 = 0.8000, against 59/142 = 0.4155 before | `hooks/tezgah_gate.py:1041-1053`; the 0.24.0 entry in `CHANGELOG.md` | `tests/test_gate.py::test_a_long_turn_restates_the_constraints_before_a_write` | 2026-09-30 |
| `check failed` | designed | the newest check failing is its own class; no incident recorded | `tests/test_integrity.py::test_failed_check_blocks` | 2026-09-23 |
| `partial failure` | designed | a failure the turn never resolved; no incident recorded | `tests/test_integrity.py::test_an_unresolved_failure_blocks_even_after_an_earlier_pass` | 2026-09-23 |
| `stale evidence` | measured 2026-09-19: reading a rewrite as a change refused honest turns | `hooks/tezgah_integrity.py:1799-1801` | `tests/test_integrity.py::test_a_write_after_the_check_makes_the_check_stale` | 2026-09-23 |
| `no verify_ok` | E2: 0 of 10 description-shaped claims refused before the `worked` trigger | `hooks/tezgah_integrity.py:2576-2585` | `tests/test_integrity.py::test_work_with_no_passing_check_is_refused_without_a_claim_word` | 2026-09-23 |
| `no ui_ok` | reading the fold the old way refused honest turns and named a screen check the turn had in fact run | `hooks/tezgah_integrity.py:2629-2630` | `tests/test_integrity.py::test_a_green_unit_run_does_not_license_a_ui_change` | 2026-09-29 |
| `no external read` | two turns: "npm 0.22.0 is missing" off a stale client, and "make NPM_TOKEN an automation token" when it already was | `hooks/tezgah_integrity.py:2721-2723` | `tests/test_integrity.py::test_an_external_claim_with_no_read_is_refused` | 2026-09-29 |
| `placating opener` | designed | output rule 10 read at the Stop event; no incident recorded | `tests/test_integrity.py::test_sycophantic_opener_blocks` | 2026-09-23 |
| `forbidden closer` | designed | output rule 10 read at the Stop event; no incident recorded | `tests/test_integrity.py::test_a_closer_from_the_skills_own_list_blocks` | 2026-09-23 |
| `list cap` | designed | output rule 8 read at the Stop event; no incident recorded | `tests/test_integrity.py::test_a_list_over_the_cap_blocks_with_its_size` | 2026-09-27 |
| `reply language` | measured 2026-09-19: the 161 final replies the claim vocabulary was read off | `hooks/tezgah_integrity.py:177-178` | `tests/test_integrity.py::test_english_prose_blocks_and_names_the_language` | 2026-09-27 |

## Adding a rule

1. Write the check inside `decision` (`hooks/tezgah_gate.py:1378-1572`). A rule is a function returning a `str` reason or `None`; keep an argument-shaped rule
   above the repeat guards (`hooks/tezgah_gate.py:1271-1277`) — the drift refusal stays last, below every other rule — and put its constants beside its own section.
   Moving this file shifts every line-number citation on this page, so re-run `bin/tezgah-docs --citations` in the same pass as the suite and re-anchor what it flags.
2. Return through `_deny(session_id, "<rule>", reason, tool, inp, base)` so the ledger counts the refusal (`hooks/tezgah_gate.py:1362-1377`); gate it on the kill switch it belongs
   to (`off(...)`), the way the shortcut and repeat rules use `verify-off` (`hooks/tezgah_gate.py:1235`, `hooks/tezgah_gate.py:1338`). The rule name is now a record too: add its row to
   [Rule provenance](#rule-provenance), or `bin/tezgah-docs --citations` refuses the rule for having none.
3. Extend `tests/test_gate.py`. It drives the real function through `tests/_probe_gate.py` (`tests/support.py:20`), which also carries the `capture_log` stub
   standing in for `tezgah_gate.capture` on the allow path (`tests/_probe_gate.py:20-30`). Only if the refusal envelope changes, touch
   `tests/test_claude_adapters.py:96-110` and the codex/cursor/omp hook tests.
4. Mirror the rule in `hosts/opencode/plugins/tezgah.js` and extend `tests/test_opencode_plugin.py` with its cases; that suite is where the two halves are
   compared and where a shared-vocabulary drift fails.

## Source of truth

- `hooks/tezgah_gate.py` — `decision` `hooks/tezgah_gate.py:1378-1572`; every rule constant and refusal text `hooks/tezgah_gate.py:113-213`; `attribution`/`attribution_edit` `hooks/tezgah_gate.py:237-271`; `explored`
  `hooks/tezgah_gate.py:368-372`; `searched_identifier` `hooks/tezgah_gate.py:373-387`, `index_slug` `hooks/tezgah_gate.py:388-409`, `first_nudge` `hooks/tezgah_gate.py:410-426`, `nudge_reason` `hooks/tezgah_gate.py:427-447`; `LOOP_ATTEMPTS` `hooks/tezgah_gate.py:448-448`, `loop_reason` `hooks/tezgah_gate.py:473-503`,
  `RETRY_CEILING` `hooks/tezgah_gate.py:470-472`, `retry_reason` `hooks/tezgah_gate.py:504-529`; `secret_command` `hooks/tezgah_gate.py:530-564`, `race_reason` `hooks/tezgah_gate.py:620-657`,
  `drift_reason` `hooks/tezgah_gate.py:1139-1168`, `effectful` `hooks/tezgah_gate.py:1066-1074`, `_deny` `hooks/tezgah_gate.py:1362-1377`; the plan rule's own section `hooks/tezgah_gate.py:1074-1187` — `plan_reason` `hooks/tezgah_gate.py:1335-1361`, `_branch` `hooks/tezgah_gate.py:1241-1263`, `_product_path` `hooks/tezgah_gate.py:1317-1334`, `PLAN_DENY` `hooks/tezgah_gate.py:1213-1222`; `write_paths` `hooks/tezgah_gate.py:592-619`, `shell_target` `hooks/tezgah_gate.py:944-983`, `SHELL_AS_WRITE` `hooks/tezgah_gate.py:589-591`; the `capture` call `hooks/tezgah_gate.py:1308-1327` (a write tool's target, and a shell write's)
- `hooks/projects-pretooluse.py` — the Claude and dsh envelope; `hooks/tezgah_paths.py` — `off`, `root_for`, `cache_dir`
- `hooks/tezgah_integrity.py` — `BASH_TOOLS`/`WRITE_TOOLS` `hooks/tezgah_integrity.py:299-308`; `NEUTER`/`SKIP_ENV`/`NO_VERIFY`/`GITISH` `:133-140`; `HOOKS_PATH`/`GIT_WRITE` `:148-152`; `SKIP_TEST` `:154-163`; `TEST_PATH`
  `:164-171`; `call_id` `hooks/tezgah_integrity.py:461-485`; `_path` `:490`, `note` `hooks/tezgah_integrity.py:700-712`, `events` `hooks/tezgah_integrity.py:805-818`, `writers_elsewhere` `hooks/tezgah_integrity.py:937-1002`, `mask` `hooks/tezgah_integrity.py:1528-1533`, `shortcut_command` `hooks/tezgah_integrity.py:1534-1563`,
  `shortcut_edit` `hooks/tezgah_integrity.py:1633-1669`
- `hosts/opencode/plugins/tezgah.js` — the JavaScript mirror
- `bin/tezgah-docs` — the rule-ledger check (`ledger_failures`) that reads this page's provenance table; `tests/test_docs.py` drives it
- `tests/test_gate.py`, `tests/_probe_gate.py`, `tests/test_opencode_plugin.py`, `tests/test_claude_adapters.py`
