# The gate: every refusal, and what lifts it

This page answers one question: why a tool call was refused before it ran. It is written for the maintainer adding a rule or reading a "the gate missed this"
report, and for the session that has just met a refusal in its transcript. [architecture.md](architecture.md) places the gate among the layers;
[evidence.md](evidence.md) describes the [ledger](glossary.md#ledger) a refusal writes to; [hosts.md](hosts.md) covers the per-host envelopes.

## Where it sits in the call path

One function decides every refusal: `decision(tool, inp, cwd, session_id)` returns a reason string or `None`, and nothing else
(`hooks/tezgah_gate.py:1207-1387`). It answers only inside a tezgah [root](glossary.md#root): outside one `root_for` returns nothing and every call passes
(`hooks/tezgah_gate.py:1211-1213`). The `pretooluse-off` kill switch drops the whole gate (`hooks/tezgah_gate.py:1209-1210`).

Each host's pre-tool hook calls it and wraps the string in that host's own deny envelope — opencode's is its `tool.execute.before`, which throws
`new Error(deny)`; a `None` prints no envelope at all.

| Host | Adapter | Refusal envelope |
|---|---|---|
| claude, dsh | `hooks/projects-pretooluse.py:24-30` (`hosts/dsh/hooks.json:13`) | `hookSpecificOutput.permissionDecision: "deny"` |
| codex, cursor, omp | `hosts/codex/hook.py:151-158`, `hosts/cursor/hook.py:336-337`, `hosts/omp/hook.py:118-121` | that host's own envelope — [hosts.md](hosts.md) |
| opencode | `hosts/opencode/plugins/tezgah.js:1611` | `new Error(deny)` thrown at `hosts/opencode/plugins/tezgah.js:1725` |

Every refusal is also recorded before it is returned: `_deny` appends a ledger row `deny` whose `detail` is `"<rule>: <reason, first 80 chars>"`, plus any
`extra` (`hooks/tezgah_gate.py:1191-1206`). That row, not the reason wording, is where "why was this denied" is answered, and `<rule>` is the name used below.

A call the gate lets through is also where it keeps the pre-write bytes: `capture` runs for a write tool, and for a shell command that writes a file through a
redirect or `tee` - the same shape the task phase rule reads, `write_paths` returns the target for both routes, and a shell write gets its pre-state the same
way (`hooks/tezgah_gate.py:1306-1325`, `write_paths` `hooks/tezgah_gate.py:585`, `shell_target` `hooks/tezgah_gate.py:839`). Without it the after-state alone
cannot tell a redirect that wrote the file from one that wrote what was already there, and the freshness half of the Stop rule would read every redirect as a
change; the two halves of that rule are `hooks/tezgah_integrity.py`'s and are described in [evidence.md](evidence.md).

## The rules, in the order `decision` checks them

Bare `:NNN` references on this page are `hooks/tezgah_gate.py` unless another file is named. Each rule ends with its reach: *once*, a mark lifts the next
identical call; *standing*, only changing the call does.

### Explorer — the grep-only subagent

Trigger: tool `agent`/`task`/`subagent` whose `subagent_type` is `explore` or `explorer`, case-insensitively (`hooks/tezgah_gate.py:1058-1059`, `explored` `hooks/tezgah_gate.py:363`). Told: use
the general-purpose agent and name the codegraph tools in its prompt (`EXPLORE_DENY` `hooks/tezgah_gate.py:212`). Standing: no mark, every such
request is refused.

### Shortcut — a check made unable to fail, or a test disabled

Trigger, shell: `--no-verify`, or `SKIP=`/`HUSKY_SKIP_HOOKS=`/`HUSKY=0`, next to a git/hook word; or a verification command chained with `|| true`/`; true`
(`hooks/tezgah_integrity.py:1225-1249`, `NO_VERIFY` `:139`, `SKIP_ENV` `:138`, `NEUTER` `:133-137`, `GITISH` `:140-141`). Trigger, edit/write: a skip marker newly
introduced into a test file — the path must match `tests?/`, `test_*`, `*_test`, `*.test.*` (`TEST_PATH` `:152-159`), the marker must survive `mask()` so one
inside a string or comment does not count, and `_added` compares against the file's own text on disk for a `Write` (`:1297-1316`, `SKIP_TEST` `:142-151`). Told:
the texts at `:1233-1243` and `:1349-1351` — run the checks, or say the test is failing; ask the user first if the skip is intended. Standing, with one switch:
`verify-off` removes this check (`hooks/tezgah_gate.py:1233-1250`). The shell is a write route like any other, and the one E7c measured an
armed session taking once the write tools were refused: a heredoc that writes a skip into a test file meets the same predicate, run over the body the
command would land (`shell_write_body` `hooks/tezgah_gate.py:900`, read at `hooks/tezgah_gate.py:1190` — the body is the raw text, because `mask()` blanks
heredoc bodies by design).

### Piped — a check whose status a trimmer owns

Trigger: a verification command (integrity's `VERIFY`) piped into a trimmer or filter — `tail`, `head`, `grep`/`egrep`/`fgrep`, `cut`, `wc`, `sed -n`, with
`|` or `|&`, a `tee` in between included — in one `&&`/`;`-separated segment of the line (`piped_check` `hooks/tezgah_integrity.py:1265-1296`, `TRIMMER`
`hooks/tezgah_integrity.py:1252-1254`). The line's exit status is the trimmer's, so the ledger can only record the check as ran, never as passed, and the Stop rule
then refuses every claim the run was meant to carry — observed in a real omp session where 13 checks ran piped and 3 of 6 completion claims were blocked.
Passes: a line that opens with `set -o pipefail` (`PIPEFAIL` `hooks/tezgah_integrity.py:1250-1251`), which integrity then records as decisive
(`verify_ok`/`verify_fail`, [evidence.md](evidence.md)); a redirect to a file; a pipe of anything that is not a check (`git log | head`). Told: redirect the
check to a file and read the file, or prefix `set -o pipefail;`, with the check named as it was typed. Standing, under `verify-off`
(`hooks/tezgah_gate.py:1233`). opencode asks the core for this rule on any shell line that pipes a check
(`hosts/opencode/plugins/tezgah.js:1677`) and records such a line as `verify` unless it opens with pipefail (`hosts/opencode/plugins/tezgah.js:628`).

### Attribution — an AI/model credit on its way into an artifact

Trigger, shell: a write command (`WRITE_CMD` `hooks/tezgah_gate.py:172-185` — `git commit|merge|tag|notes`, `gh api`,
`gh pr|issue|release create|edit|comment|review|merge|close`) carrying a credit form (`ATTRIB` `hooks/tezgah_gate.py:150` — `co-authored-by:`, `generated with`, `made with`,
`built by`, `assisted by`, `authored by`, `noreply@anthropic`, a robot emoji). Trigger, edit/write: one of the content fields `EDIT_TEXT` (`hooks/tezgah_gate.py:163`)
containing a line that *starts* with a credit (`ATTRIB_LINE` `hooks/tezgah_gate.py:161`). Told: remove it and re-run; naming a tool in order to use it is fine, crediting it
as author is not (`ATTRIB_DENY` `hooks/tezgah_gate.py:219`). Standing. The line anchor is why prose that merely names the banned forms passes (`hooks/tezgah_gate.py:132-149`).
The same twin as the shortcut rule's: a credit a heredoc writes into a file is refused from the body (`hooks/tezgah_gate.py:1199-1200`), and no command has to be
a `git`/`gh` write for it to be this rule's.

### Language — an identifier or message that is not English

Trigger, shell: a command that would create an identifier - `git checkout -b`/`git switch -c`, `git branch` with a new name, a commit subject (`git commit -m`/`--message`/`-F`), or a `gh pr|issue create --title` (the language section `hooks/tezgah_gate.py:237-348`, `created_texts` `hooks/tezgah_gate.py:326`; the text is read from the raw command, because `mask()` blanks quoted strings and a commit subject is one) - whose name or subject is **not English**: a letter outside ASCII anywhere (`non_english` `hooks/tezgah_lang.py:45` - a predicate rather than one language's letter list, so Russian, Greek, Arabic, Chinese and accented Latin hit it exactly as Turkish does) or an ASCII-folded Turkish word from the curated list (`ENGLISH` `hooks/tezgah_lang.py:76`, wi…

The rule is a **heuristic** and its own text says so: a word list is not a language detector, so it cannot tell a proper noun or a product name in another language from a word that ought to be English, and a listed word may be the user's own term. A command that only names the words - `echo`, `grep`, `git log --grep` - creates nothing and passes. An identifier outlives the session that typed it, which is the reason the rule exists at all: `plan/004-admin-durum-onarimi` is in a public history from the moment it exists. On **opencode** the rule is not ported: the plugin asks the core for it through `bin/tezgah-gate check`, one spawn for a command its pre-test reads as identifier-creating (`IDENT_CMD` `hosts/opencode/plugins/tezgah.js:329`, the call site `:1670…

### Race — another session wrote this file minutes ago

Trigger: a write tool whose path, or `apply_patch` header, another session recorded a write of inside `RACE_WINDOW_MIN = 10` minutes (`hooks/tezgah_gate.py:543`, `race_reason`
`hooks/tezgah_gate.py:613`, reader `writers_elsewhere` `hooks/tezgah_integrity.py:893-958`). Told: re-read the file and re-apply the change to what is on disk now (`RACE_DENY`
`hooks/tezgah_gate.py:563`). Standing (`RACE_REFUSE = True` `hooks/tezgah_gate.py:547`) — a notice would not close a silent overwrite — and it lifts only by time.

### Secret — a credential on its way into a file

Trigger: one simple command (split on `&&`, `||`, `;`, newline — `SEGMENT` `hooks/tezgah_gate.py:203-204`) carrying both a token (`SECRET_TOKEN` `hooks/tezgah_gate.py:186-193` — an
`Authorization: Bearer` header, or a `name=value` assignment for `api_key`/`token`/`secret`/`password`/...) and a sink (`SECRET_SINK` `hooks/tezgah_gate.py:194` — `>`/`>>`,
`| tee`, a curl `--trace`, or `git add`); `secret_command` `hooks/tezgah_gate.py:523`. Told: record the name, length or a fingerprint instead, and pass the value through the
tool's environment (`SECRET_DENY` `hooks/tezgah_gate.py:205`). Standing, no escape hatch. The shell's own write route is the third twin: a credential inside a heredoc body
is refused from the body (`hooks/tezgah_gate.py:1251-1252`), because `mask()` blanks that body and the text-level scan above cannot see it.

### Workspace — tezgah state outside `.tezgah/`

Trigger: a write tool, or a shell redirect/`tee` (`write_paths`), whose target relative to the repo root starts with `plans/`, `research/` or `analysis/` while the project tracks no file under that directory (`workspace_reason`, `hooks/tezgah_gate.py`). The refusal names `.tezgah/<kind>/` as the place to write. A directory the project already tracks is its own and passes. `mkdir` and positional shell targets (`cp`, `mv`) are not read - the same ceiling as `write_paths`. Off: `workspace-off`.

### Plan — a turn's third product file on `main`

Trigger: a write tool, or a shell redirect/`tee` (`write_paths` `hooks/tezgah_gate.py:585`), whose target is a product path, while the checkout is on `main` or `master` and this turn has
already written two other product files (`plan_reason` `hooks/tezgah_gate.py:1164-1190`, `_branch` `hooks/tezgah_gate.py:1118-1145`, `_product_path` `hooks/tezgah_gate.py:1146-1163`). The
count folds the turn's own write rows (`turn_rows` `hooks/tezgah_integrity.py:779-808`) together with the files the call in hand names, so it needs no state of its own, and it counts DISTINCT
paths - a turn that rewrites one file three times is still one file's work. The product paths are the ones at the repository root that a plan exists to scope - `hooks/`, `tests/`, `bin/`,
`skills/`, `docs/`, `statusline.py` and `MANIFEST` (`PLAN_DIRS`/`PLAN_FILES` `hooks/tezgah_gate.py:1104-1105`); a `.tezgah/` path is never one of them, and neither is a path outside the
repository. Told: the branch it read, how many files the turn has written, and the command that opens a plan - the `plan-add` skill, `/tezgah:plan-add <description>` (`PLAN_DENY`
`hooks/tezgah_gate.py:1108-1117`). Standing: only changing the tree's state changes it - the work moves to the `plan/NNN-slug` branch the skill creates (a one- or two-file fix is free either
way), or the repository carries a `.no-plan-gate` mark (the shape of `.no-graph` and `.no-lessons`). It passes wherever the question cannot be answered: no session or ledger, a directory that is
not a git repository, and a detached HEAD with no branch to name.

### Ordering — a commit while the newest check failed

The one rule here that asserts a relation between two actions rather than reading one call plus a ledger tail, and the shape FAVA found in 90% of real
agent-instruction projects ("do not commit before running the tests").

Trigger: the command is a `git commit` (or `--amend`; `COMMIT_CMD` `hooks/tezgah_gate.py:944`, matched at `hooks/tezgah_gate.py:1259`) and the newest check in
this session **failed**. The state is the Stop rule's own fold over the ledger tail (`ORDER_TAIL = 200` `hooks/tezgah_gate.py:891`, the fold
`tezgah_integrity._last_verify`), and the rule is structurally incapable of firing in either direction that would punish honest work: no check at all folds
to `None` and a passing newest check folds to `ok`, so a commit in a session that ran no check — a docs-only commit — and a commit after a green run both
pass. Only `fail` refuses: the tree the commit would freeze is the one a check just rejected.

Told: the failed check by name and nothing else (`ORDER_DENY` `hooks/tezgah_gate.py:946`, `commit_order_reason` `hooks/tezgah_gate.py:954`) —
making the newest check pass is the whole repair, so the refusal names no command that lifts it, for the reason the task refusals carry. Standing while the
tail still shows that failure, under `verify-off` (`hooks/tezgah_gate.py:1258`). Its deny row is its own rule name (`order`), so the counters separate it.

### Loop — the identical attempt that already failed twice

Trigger: the same call (same `call_id`) failed `LOOP_ATTEMPTS = 2` times already in the current user turn (`hooks/tezgah_gate.py:441`, `loop_reason` `hooks/tezgah_gate.py:466`). Told: attempt N
of an identical call, the failure class read from the ledger (`transient`, `user`, `permanent`, `unknown`; the cap is the same for every class, and a `user` failure - a 401/403, a missing credential, a login - says to ask the user), "change the approach or stop" (`hooks/tezgah_gate.py:471-479`). Standing while the ledger tail still shows those
failures. Under `verify-off` (`hooks/tezgah_gate.py:1269`).

### Retry — the session-wide ceiling

Trigger: the same call has been attempted more than `RETRY_CEILING = 3` times in the session, whatever those attempts returned (`hooks/tezgah_gate.py:463`, `retry_reason`
`hooks/tezgah_gate.py:497`). Told: an unchanged repeat is not a retry (`hooks/tezgah_gate.py:500-505`). Standing. Under `verify-off` (`hooks/tezgah_gate.py:1269`). Both guards read only the ledger tail.

### Nudge — the first identifier-shaped search of a session

Trigger: a `Grep` whose pattern, or a `grep`/`rg` argument (`BASH_SEARCH` `hooks/tezgah_gate.py:128`), matches `IDENT` (`^[A-Za-z_][A-Za-z0-9_]{2,}$`, `hooks/tezgah_gate.py:113`), in a repo whose
codegraph index exists (`<repo>/.codegraph/codegraph.db`; `searched_identifier`
`hooks/tezgah_gate.py:368`). Told: the runnable command built from the denied search (`codegraph explore <X>`, `codegraph callers <X>`, `codegraph impact <X>`), and that an omp subagent uses this CLI because omp's MCP device refuses concurrent writes
(`nudge_reason` `hooks/tezgah_gate.py:420`).
Once-only: the mark in `cache_dir()/nudged/<session>` is written *before* the refusal, so re-issuing the search passes (`first_nudge` `hooks/tezgah_gate.py:403`).

### Drift — a long turn loses the rules it started with

Trigger: 25 work rows (`DRIFT_STEPS` `hooks/tezgah_gate.py:984-988`) in the current user turn and an effectful call — a write tool, or a git/gh artifact command (`effectful`
`hooks/tezgah_gate.py:1064-1072`). Told: the standing constraints re-stated, or the delta since the turn began; "re-issue this call unchanged and carry on" (`DRIFT_DENY` `hooks/tezgah_gate.py:990`,
`drift_reason` `hooks/tezgah_gate.py:1034`). A refusal, last in `decision` after every other rule, and its only delivery: no host's PostToolUse side carries it, and opencode gets it from the core through `bin/tezgah-gate` on its write path. Once per turn: the `drift` mark is written *before* the refusal, so the identical call passes on the next attempt, and the count behind it is the turn's own — a bounded read (`DRIFT_TAIL` `hooks/tezgah_gate.py:989`) falls back to the turn's own start (`turn_rows` `hooks/tezgah_integrity.py:779-808`) when the turn outgrew the window. Governed by `reminder-off`, not `verify-off` (`hooks/tezgah_gate.py:1001`).

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
- A foreign `apply_patch` write: the PostToolUse writer records no path for that row (`hooks/tezgah_gate.py:604`); and a second session that spells the path differently
  escapes the rule, because the ledger keeps no `cwd` (`hooks/tezgah_gate.py:557-559`).
- Which rule the user meant when a turn drifts: "a guess about intent wearing a check's clothes" (`hooks/tezgah_gate.py:988`).
- A skip already in the file, or one inside a string (a test *about* the rule), is not a disable (`hooks/tezgah_integrity.py:1297-1316`).
- The content of a shell write that is not a heredoc: `echo "Co-Authored-By: x" > f` puts the credit inside a quoted string that no line-start anchor can see,
  and reading the whole command instead would deny a search for the form (`grep "Co-Authored-By" x > out`). The three twins read a heredoc body, which is the
  route E7c measured (`shell_write_body` `hooks/tezgah_gate.py:900`).
- A shell write whose target is not a redirect: `cp`, `mv`, `sed -i`, `patch` and `git apply` name it as a positional argument, and which argument of those is
  the target is a per-program question, so the gate keeps no pre-state for it and the freshness half reads no change there (`write_paths`
  `hooks/tezgah_gate.py:585`). A shell write chained with a check in one call (`sed -i ... && pytest`) records as the check row, and the row that carries a
  pass is never the row read as the change - otherwise a check redirecting its own log would stale itself (`tezgah_integrity._change_row`).
- A PRIOR shell write's target, in the plan rule's count: a write the shell landed is a `run` row whose detail is the command, so the count reads the turn's
  write-tool rows plus the redirect the call in hand names (`plan_reason` `hooks/tezgah_gate.py:1164-1190`). Three heredocs into product files in one turn
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
`tool.execute.before` (hosts/opencode/plugins/tezgah.js:1560, exported `hosts/opencode/plugins/tezgah.js:1559`) in the gate's own order (`hosts/opencode/plugins/tezgah.js:1622-1688`); its shortcut constants restate the same regexes (`NEUTER` `hosts/opencode/plugins/tezgah.js:261`,
`SKIP_ENV` hosts/opencode/plugins/tezgah.js:220, `NO_VERIFY` hosts/opencode/plugins/tezgah.js:263, `GITISH` hosts/opencode/plugins/tezgah.js:264, `SKIP_TEST` hosts/opencode/plugins/tezgah.js:265). What keeps the two halves honest is a test, not a shared module:
`tests/test_opencode_plugin.py` drives the plugin's hooks through a node harness with a throwaway HOME, and imports the Python `tezgah_integrity.call_id` so a
separator or canonical-form drift in the action id fails there instead of silently in a session (`tests/test_opencode_plugin.py:1-7`, `:21-24`, `tests/test_opencode_plugin.py:1046-1085`).

The shell rule kinds mirrored last are each pinned in both suites: the shell's write body (`SHELL_WRITE` `hosts/opencode/plugins/tezgah.js:437`,
`heredocBodies` `hosts/opencode/plugins/tezgah.js:443`, `shellWriteBody` `hosts/opencode/plugins/tezgah.js:487`, the shortcut and attribution twins at
`hosts/opencode/plugins/tezgah.js:1650` and `hosts/opencode/plugins/tezgah.js:988`, the credential twin at `hosts/opencode/plugins/tezgah.js:947`) and the
ordering obligation (`COMMIT_CMD` `hosts/opencode/plugins/tezgah.js:1038`, `ORDER_DENY`
`hosts/opencode/plugins/tezgah.js:880`, `lastVerify` `hosts/opencode/plugins/tezgah.js:890`, `orderReason` `hosts/opencode/plugins/tezgah.js:915`, dispatched at
`hosts/opencode/plugins/tezgah.js:1683`). `lastVerify` folds the tail exactly as `_last_verify` does, minus the `passing_check` narrowing - this rule reads only
`fail`, and a row that narrowing would refuse reads `ok`/`ran` on both sides, so the outcome is identical.

## Adding a rule

1. Write the check inside `decision` (`hooks/tezgah_gate.py:1207-1387`). A rule is a function returning a `str` reason or `None`; keep an argument-shaped rule
   above the repeat guards (`hooks/tezgah_gate.py:1269-1275`) — the drift refusal stays last, below every other rule — and put its constants beside its own section.
   Moving this file shifts every line-number citation on this page, so re-run `bin/tezgah-docs --citations` in the same pass as the suite and re-anchor what it flags.
2. Return through `_deny(session_id, "<rule>", reason, tool, inp, base)` so the ledger counts the refusal (`hooks/tezgah_gate.py:1191-1206`); gate it on the kill switch it belongs
   to (`off(...)`), the way the shortcut and repeat rules use `verify-off` (`hooks/tezgah_gate.py:1233`, `hooks/tezgah_gate.py:1336`).
3. Extend `tests/test_gate.py`. It drives the real function through `tests/_probe_gate.py` (`tests/support.py:20`), which also carries the `capture_log` stub
   standing in for `tezgah_gate.capture` on the allow path (`tests/_probe_gate.py:20-30`). Only if the refusal envelope changes, touch
   `tests/test_claude_adapters.py:42-51` and the codex/cursor/omp hook tests.
4. Mirror the rule in `hosts/opencode/plugins/tezgah.js` and extend `tests/test_opencode_plugin.py` with its cases; that suite is where the two halves are
   compared and where a shared-vocabulary drift fails.

## Source of truth

- `hooks/tezgah_gate.py` — `decision` `hooks/tezgah_gate.py:1207-1387`; every rule constant and refusal text `hooks/tezgah_gate.py:113-213`; `attribution`/`attribution_edit` `hooks/tezgah_gate.py:237-271`; `explored`
  `hooks/tezgah_gate.py:363`; `searched_identifier` `hooks/tezgah_gate.py:368`, `index_slug` `hooks/tezgah_gate.py:383`, `first_nudge` `hooks/tezgah_gate.py:403`, `nudge_reason` `hooks/tezgah_gate.py:420`; `LOOP_ATTEMPTS` `hooks/tezgah_gate.py:441`, `loop_reason` `hooks/tezgah_gate.py:466`,
  `RETRY_CEILING` `hooks/tezgah_gate.py:463`, `retry_reason` `hooks/tezgah_gate.py:497`; `secret_command` `hooks/tezgah_gate.py:523`, `race_reason` `hooks/tezgah_gate.py:613`,
  `drift_reason` `hooks/tezgah_gate.py:1034`, `effectful` `hooks/tezgah_gate.py:1064-1072`, `_deny` `hooks/tezgah_gate.py:1191`; the plan rule's own section `hooks/tezgah_gate.py:1072-1185` — `plan_reason` `hooks/tezgah_gate.py:1164`, `_branch` `hooks/tezgah_gate.py:1118`, `_product_path` `hooks/tezgah_gate.py:1146`, `PLAN_DENY` `hooks/tezgah_gate.py:1108`; `write_paths` `hooks/tezgah_gate.py:585`, `shell_target` `hooks/tezgah_gate.py:839`, `SHELL_AS_WRITE` `hooks/tezgah_gate.py:582`; the `capture` call `hooks/tezgah_gate.py:1306-1325` (a write tool's target, and a shell write's)
- `hooks/projects-pretooluse.py` — the Claude and dsh envelope; `hooks/tezgah_paths.py` — `off`, `root_for`, `cache_dir`
- `hooks/tezgah_integrity.py` — `BASH_TOOLS`/`WRITE_TOOLS` `hooks/tezgah_integrity.py:287-296`; `NEUTER`/`SKIP_ENV`/`NO_VERIFY`/`GITISH` `:133-141`; `SKIP_TEST` `:142-151`; `TEST_PATH`
  `:152-159`; `call_id` `hooks/tezgah_integrity.py:438-462`; `_path` `:478`, `note` `hooks/tezgah_integrity.py:656-668`, `events` `hooks/tezgah_integrity.py:761-774`, `writers_elsewhere` `hooks/tezgah_integrity.py:893-958`, `mask` `hooks/tezgah_integrity.py:1219-1224`, `shortcut_command` `hooks/tezgah_integrity.py:1225-1249`,
  `shortcut_edit` `hooks/tezgah_integrity.py:1319-1355`
- `hosts/opencode/plugins/tezgah.js` — the JavaScript mirror
- `tests/test_gate.py`, `tests/_probe_gate.py`, `tests/test_opencode_plugin.py`, `tests/test_claude_adapters.py`
