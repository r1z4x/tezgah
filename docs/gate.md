# The gate: every refusal, and what lifts it

This page answers one question: why a tool call was refused before it ran. It is written for the maintainer adding a rule or reading a "the gate missed this"
report, and for the session that has just met a refusal in its transcript. [architecture.md](architecture.md) places the gate among the layers;
[evidence.md](evidence.md) describes the [ledger](glossary.md#ledger) a refusal writes to; [hosts.md](hosts.md) covers the per-host envelopes.

## Where it sits in the call path

One function decides every refusal: `decision(tool, inp, cwd, session_id)` returns a reason string or `None`, and nothing else
(`hooks/tezgah_gate.py:1094-1266`). It answers only inside a tezgah [root](glossary.md#root): outside one `root_for` returns nothing and every call passes
(`hooks/tezgah_gate.py:1049-1051`). The `pretooluse-off` kill switch drops the whole gate (`hooks/tezgah_gate.py:1047`).

Each host's pre-tool hook calls it and wraps the string in that host's own deny envelope — opencode's is its `tool.execute.before`, which throws
`new Error(deny)`; a `None` prints no envelope at all.

| Host | Adapter | Refusal envelope |
|---|---|---|
| claude, dsh | `hooks/projects-pretooluse.py:24-30` (`hosts/dsh/hooks.json:13`) | `hookSpecificOutput.permissionDecision: "deny"` |
| codex, cursor, omp | `hosts/codex/hook.py:151-158`, `hosts/cursor/hook.py:341-342`, `hosts/omp/hook.py:118-121` | that host's own envelope — [hosts.md](hosts.md) |
| opencode | `hosts/opencode/plugins/tezgah.js:1611` | `new Error(deny)` thrown at `hosts/opencode/plugins/tezgah.js:1725` |

Every refusal is also recorded before it is returned: `_deny` appends a ledger row `deny` whose `detail` is `"<rule>: <reason, first 80 chars>"`, plus any
`extra` (`hooks/tezgah_gate.py:1078-1093`). That row, not the reason wording, is where "why was this denied" is answered, and `<rule>` is the name used below.

A call the gate lets through is also where it keeps the pre-write bytes: `capture` runs for a write tool, and for a shell command that writes a file through a
redirect or `tee` - the same shape the task phase rule reads, `write_paths` returns the target for both routes, and a shell write gets its pre-state the same
way (`hooks/tezgah_gate.py:1196-1206`, `write_paths` `hooks/tezgah_gate.py:583`, `shell_target` `hooks/tezgah_gate.py:837`). Without it the after-state alone
cannot tell a redirect that wrote the file from one that wrote what was already there, and the freshness half of the Stop rule would read every redirect as a
change; the two halves of that rule are `hooks/tezgah_integrity.py`'s and are described in [evidence.md](evidence.md).

## The rules, in the order `decision` checks them

Bare `:NNN` references on this page are `hooks/tezgah_gate.py` unless another file is named. Each rule ends with its reach: *once*, a mark lifts the next
identical call; *standing*, only changing the call does.

### Explorer — the grep-only subagent

Trigger: tool `agent`/`task`/`subagent` whose `subagent_type` is `explore` or `explorer`, case-insensitively (`hooks/tezgah_gate.py:1064-1065`, `explored` `hooks/tezgah_gate.py:364`). Told: use
the general-purpose agent and name the codegraph tools in its prompt (`EXPLORE_DENY` `hooks/tezgah_gate.py:213`). Standing: no mark, every such
request is refused.

### Shortcut — a check made unable to fail, or a test disabled

Trigger, shell: `--no-verify`, or `SKIP=`/`HUSKY_SKIP_HOOKS=`/`HUSKY=0`, next to a git/hook word; or a verification command chained with `|| true`/`; true`
(`hooks/tezgah_integrity.py:1049-1067`, `NO_VERIFY` `:103`, `SKIP_ENV` `:102`, `NEUTER` `:97-101`, `GITISH` `:104-105`). Trigger, edit/write: a skip marker newly
introduced into a test file — the path must match `tests?/`, `test_*`, `*_test`, `*.test.*` (`TEST_PATH` `:116-123`), the marker must survive `mask()` so one
inside a string or comment does not count, and `_added` compares against the file's own text on disk for a `Write` (`:1072-1091`, `SKIP_TEST` `:106-115`). Told:
the texts at `:1057-1068` and `:1124-1127` — run the checks, or say the test is failing; ask the user first if the skip is intended. Standing, with one switch:
`verify-off` removes this check (`hooks/tezgah_gate.py:1074-1086`). The shell is a write route like any other, and the one E7c measured an
armed session taking once the write tools were refused: a heredoc that writes a skip into a test file meets the same predicate, run over the body the
command would land (`shell_write_body` `hooks/tezgah_gate.py:898`, read at `hooks/tezgah_gate.py:1080` — the body is the raw text, because `mask()` blanks
heredoc bodies by design).

### Piped — a check whose status a trimmer owns

Trigger: a verification command (integrity's `VERIFY`) piped into a trimmer or filter — `tail`, `head`, `grep`/`egrep`/`fgrep`, `cut`, `wc`, `sed -n`, with
`|` or `|&`, a `tee` in between included — in one `&&`/`;`-separated segment of the line (`piped_check` `hooks/tezgah_integrity.py:1130-1161`, `TRIMMER`
`hooks/tezgah_integrity.py:1117-1119`). The line's exit status is the trimmer's, so the ledger can only record the check as ran, never as passed, and the Stop rule
then refuses every claim the run was meant to carry — observed in a real omp session where 13 checks ran piped and 3 of 6 completion claims were blocked.
Passes: a line that opens with `set -o pipefail` (`PIPEFAIL` `hooks/tezgah_integrity.py:1115-1116`), which integrity then records as decisive
(`verify_ok`/`verify_fail`, [evidence.md](evidence.md)); a redirect to a file; a pipe of anything that is not a check (`git log | head`). Told: redirect the
check to a file and read the file, or prefix `set -o pipefail;`, with the check named as it was typed. Standing, under `verify-off`
(`hooks/tezgah_gate.py:1086`). opencode asks the core for this rule on any shell line that pipes a check
(`hosts/opencode/plugins/tezgah.js:1677`) and records such a line as `verify` unless it opens with pipefail (`hosts/opencode/plugins/tezgah.js:628`).

### Attribution — an AI/model credit on its way into an artifact

Trigger, shell: a write command (`WRITE_CMD` `hooks/tezgah_gate.py:173-186` — `git commit|merge|tag|notes`, `gh api`,
`gh pr|issue|release create|edit|comment|review|merge|close`) carrying a credit form (`ATTRIB` `hooks/tezgah_gate.py:151` — `co-authored-by:`, `generated with`, `made with`,
`built by`, `assisted by`, `authored by`, `noreply@anthropic`, a robot emoji). Trigger, edit/write: one of the content fields `EDIT_TEXT` (`hooks/tezgah_gate.py:164`)
containing a line that *starts* with a credit (`ATTRIB_LINE` `hooks/tezgah_gate.py:162`). Told: remove it and re-run; naming a tool in order to use it is fine, crediting it
as author is not (`ATTRIB_DENY` `hooks/tezgah_gate.py:220`). Standing. The line anchor is why prose that merely names the banned forms passes (`hooks/tezgah_gate.py:133-150`).
The same twin as the shortcut rule's: a credit a heredoc writes into a file is refused from the body (`hooks/tezgah_gate.py:1089-1090`), and no command has to be
a `git`/`gh` write for it to be this rule's.

### Language — an identifier or message that is not English

Trigger, shell: a command that would create an identifier - `git checkout -b`/`git switch -c`, `git branch` with a new name, a commit subject (`git commit -m`/`--message`/`-F`), or a `gh pr|issue create --title` (the language section `hooks/tezgah_gate.py:238-349`, `created_texts` `hooks/tezgah_gate.py:327`; the text is read from the raw command, because `mask()` blanks quoted strings and a commit subject is one) - whose name or subject is **not English**: a letter outside ASCII anywhere (`non_english` `hooks/tezgah_lang.py:45` - a predicate rather than one language's letter list, so Russian, Greek, Arabic, Chinese and accented Latin hit it exactly as Turkish does) or an ASCII-folded Turkish word from the curated list (`ENGLISH` `hooks/tezgah_lang.py:76`, wi…

The rule is a **heuristic** and its own text says so: a word list is not a language detector, so it cannot tell a proper noun or a product name in another language from a word that ought to be English, and a listed word may be the user's own term. A command that only names the words - `echo`, `grep`, `git log --grep` - creates nothing and passes. An identifier outlives the session that typed it, which is the reason the rule exists at all: `plan/004-admin-durum-onarimi` is in a public history from the moment it exists. On **opencode** the rule is not ported: the plugin asks the core for it through `bin/tezgah-gate check`, one spawn for a command its pre-test reads as identifier-creating (`IDENT_CMD` `hosts/opencode/plugins/tezgah.js:329`, the call site `:1670…

### Race — another session wrote this file minutes ago

Trigger: a write tool whose path, or `apply_patch` header, another session recorded a write of inside `RACE_WINDOW_MIN = 10` minutes (`hooks/tezgah_gate.py:544`, `race_reason`
`hooks/tezgah_gate.py:611`, reader `writers_elsewhere` `hooks/tezgah_integrity.py:829-894`). Told: re-read the file and re-apply the change to what is on disk now (`RACE_DENY`
`hooks/tezgah_gate.py:561`). Standing (`RACE_REFUSE = True` `hooks/tezgah_gate.py:548`) — a notice would not close a silent overwrite — and it lifts only by time.

### Secret — a credential on its way into a file

Trigger: one simple command (split on `&&`, `||`, `;`, newline — `SEGMENT` `hooks/tezgah_gate.py:192`) carrying both a token (`SECRET_TOKEN` `hooks/tezgah_gate.py:175` — an
`Authorization: Bearer` header, or a `name=value` assignment for `api_key`/`token`/`secret`/`password`/...) and a sink (`SECRET_SINK` `hooks/tezgah_gate.py:195` — `>`/`>>`,
`| tee`, a curl `--trace`, or `git add`); `secret_command` `hooks/tezgah_gate.py:521`. Told: record the name, length or a fingerprint instead, and pass the value through the
tool's environment (`SECRET_DENY` `hooks/tezgah_gate.py:206`). Standing, no escape hatch. The shell's own write route is the third twin: a credential inside a heredoc body
is refused from the body (`hooks/tezgah_gate.py:1141-1142`), because `mask()` blanks that body and the text-level scan above cannot see it.

### Workspace — tezgah state outside `.tezgah/`

Trigger: a write tool, or a shell redirect/`tee` (`write_paths`), whose target relative to the repo root starts with `plans/`, `research/` or `analysis/` while the project tracks no file under that directory (`workspace_reason`, `hooks/tezgah_gate.py`). The refusal names `.tezgah/<kind>/` as the place to write. A directory the project already tracks is its own and passes. `mkdir` and positional shell targets (`cp`, `mv`) are not read - the same ceiling as `write_paths`. Off: `workspace-off`.

### Ordering — a commit while the newest check failed

The one rule here that asserts a relation between two actions rather than reading one call plus a ledger tail, and the shape FAVA found in 90% of real
agent-instruction projects ("do not commit before running the tests").

Trigger: the command is a `git commit` (or `--amend`; `COMMIT_CMD` `hooks/tezgah_gate.py:942`, matched at `hooks/tezgah_gate.py:1149`) and the newest check in
this session **failed**. The state is the Stop rule's own fold over the ledger tail (`ORDER_TAIL = 200` `hooks/tezgah_gate.py:892`, the fold
`tezgah_integrity._last_verify`), and the rule is structurally incapable of firing in either direction that would punish honest work: no check at all folds
to `None` and a passing newest check folds to `ok`, so a commit in a session that ran no check — a docs-only commit — and a commit after a green run both
pass. Only `fail` refuses: the tree the commit would freeze is the one a check just rejected.

Told: the failed check by name and nothing else (`ORDER_DENY` `hooks/tezgah_gate.py:944`, `commit_order_reason` `hooks/tezgah_gate.py:952`) —
making the newest check pass is the whole repair, so the refusal names no command that lifts it, for the reason the task refusals carry. Standing while the
tail still shows that failure, under `verify-off` (`hooks/tezgah_gate.py:1148`). Its deny row is its own rule name (`order`), so the counters separate it.

### Loop — the identical attempt that already failed twice

Trigger: the same call (same `call_id`) failed `LOOP_ATTEMPTS = 2` times already in the current user turn (`hooks/tezgah_gate.py:442`, `loop_reason` `hooks/tezgah_gate.py:464`). Told: attempt N
of an identical call, the failure class read from the ledger, "change the approach or stop" (`hooks/tezgah_gate.py:472-480`). Standing while the ledger tail still shows those
failures. Under `verify-off` (`hooks/tezgah_gate.py:1159`).

### Retry — the session-wide ceiling

Trigger: the same call has been attempted more than `RETRY_CEILING = 3` times in the session, whatever those attempts returned (`hooks/tezgah_gate.py:461`, `retry_reason`
`hooks/tezgah_gate.py:495`). Told: an unchanged repeat is not a retry (`hooks/tezgah_gate.py:501-506`). Standing. Under `verify-off` (`hooks/tezgah_gate.py:1159`). Both guards read only the ledger tail.

### Nudge — the first identifier-shaped search of a session

Trigger: a `Grep` whose pattern, or a `grep`/`rg` argument (`BASH_SEARCH` `hooks/tezgah_gate.py:129`), matches `IDENT` (`^[A-Za-z_][A-Za-z0-9_]{2,}$`, `hooks/tezgah_gate.py:114`), in a repo whose
codegraph index exists (`<repo>/.codegraph/codegraph.db`; `searched_identifier`
`hooks/tezgah_gate.py:369`). Told: the runnable command built from the denied search (`codegraph explore <X>`, `codegraph callers <X>`, `codegraph impact <X>`), and that an omp subagent uses this CLI because omp's MCP device refuses concurrent writes
(`nudge_reason` `hooks/tezgah_gate.py:421`).
Once-only: the mark in `cache_dir()/nudged/<session>` is written *before* the refusal, so re-issuing the search passes (`first_nudge` `hooks/tezgah_gate.py:404`).

### Drift — a long turn loses the rules it started with

Trigger: 25 work rows (`DRIFT_STEPS` `hooks/tezgah_gate.py:983-987`) in the current user turn and an effectful call — a write tool, or a git/gh artifact command (`effectful`
`hooks/tezgah_gate.py:1018`). Told: the standing constraints re-stated, or the delta since the turn began; "nothing was refused, so carry on" (`DRIFT_NOTICE` `hooks/tezgah_gate.py:989`,
`drift_reason` `hooks/tezgah_gate.py:1032`). Not a refusal: the notice rides the tool-result channel, delivered by the PostToolUse side of claude/dsh, codex, cursor and omp, so `decision` never denies for it (opencode's plugin carries no drift path). Once per turn: the `drift` mark is written where the notice is produced, and the count behind it is the turn's own — a bounded read (`DRIFT_TAIL` `hooks/tezgah_gate.py:988`) falls back to the turn's own start (`turn_rows` `hooks/tezgah_integrity.py:715-744`) when the turn outgrew the window. Governed by `reminder-off`, not `verify-off` (`hooks/tezgah_gate.py:1002`).

## What the gate deliberately does not catch

Read this before filing a security-ish issue; each is a decision, not an oversight.

- Irreversible and outward-facing shell commands — force-pushes, migrations, deploys, `ssh`, `scp`, a `curl` write, a `gh pr` write — run without an ask.
  The consent rule and its `send`/`outward`/`deploy`/`publish`/`schema`/`destructive` class table were removed on purpose (2026-09-26): the ask it put in
  front of every server-side command cost a round-trip per effect, the user's chat approval could not lift it (only the deleted `bin/tezgah-consent` CLI
  could), and the sessions it actually gated were the user's own deploys. The untrusted-read half went with it: a turn that read web content may now run an
  outbound effect carrying only the taint notice, with no refusal in between. The notice itself stays (`hooks/tezgah_untrusted.py`).
- A write inside the root after a fetch: left to the taint notice that `hooks/tezgah_untrusted.py` rides the first effect with, because it is recoverable from
  the snapshot.
- `grep -A 3 foo`: a flag with its own value shifts the token, so the search passes unnudged (`hooks/tezgah_gate.py:115-116`).
- A foreign `apply_patch` write: the PostToolUse writer records no path for that row (`hooks/tezgah_gate.py:605`); and a second session that spells the path differently
  escapes the rule, because the ledger keeps no `cwd` (`hooks/tezgah_gate.py:558-560`).
- Which rule the user meant when a turn drifts: "a guess about intent wearing a check's clothes" (`hooks/tezgah_gate.py:990`).
- A skip already in the file, or one inside a string (a test *about* the rule), is not a disable (`hooks/tezgah_integrity.py:1077-1084`).
- The content of a shell write that is not a heredoc: `echo "Co-Authored-By: x" > f` puts the credit inside a quoted string that no line-start anchor can see,
  and reading the whole command instead would deny a search for the form (`grep "Co-Authored-By" x > out`). The three twins read a heredoc body, which is the
  route E7c measured (`shell_write_body` `hooks/tezgah_gate.py:898`).
- A shell write whose target is not a redirect: `cp`, `mv`, `sed -i`, `patch` and `git apply` name it as a positional argument, and which argument of those is
  the target is a per-program question, so the gate keeps no pre-state for it and the freshness half reads no change there (`write_paths`
  `hooks/tezgah_gate.py:583`). A shell write chained with a check in one call (`sed -i ... && pytest`) records as the check row, and the row that carries a
  pass is never the row read as the change - otherwise a check redirecting its own log would stale itself (`tezgah_integrity._change_row`).

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
separator or canonical-form drift in the action id fails there instead of silently in a session (`tests/test_opencode_plugin.py:1-7`, `:21-24`, `tests/test_opencode_plugin.py:1026-1065`).

The shell rule kinds mirrored last are each pinned in both suites: the shell's write body (`SHELL_WRITE` `hosts/opencode/plugins/tezgah.js:437`,
`heredocBodies` `hosts/opencode/plugins/tezgah.js:443`, `shellWriteBody` `hosts/opencode/plugins/tezgah.js:487`, the shortcut and attribution twins at
`hosts/opencode/plugins/tezgah.js:1650` and `hosts/opencode/plugins/tezgah.js:988`, the credential twin at `hosts/opencode/plugins/tezgah.js:947`) and the
ordering obligation (`COMMIT_CMD` `hosts/opencode/plugins/tezgah.js:1038`, `ORDER_DENY`
`hosts/opencode/plugins/tezgah.js:880`, `lastVerify` `hosts/opencode/plugins/tezgah.js:890`, `orderReason` `hosts/opencode/plugins/tezgah.js:915`, dispatched at
`hosts/opencode/plugins/tezgah.js:1683`). `lastVerify` folds the tail exactly as `_last_verify` does, minus the `passing_check` narrowing - this rule reads only
`fail`, and a row that narrowing would refuse reads `ok`/`ran` on both sides, so the outcome is identical.

## Adding a rule

1. Write the check inside `decision` (`hooks/tezgah_gate.py:1094-1266`). A rule is a function returning a `str` reason or `None`; keep an argument-shaped rule
   above the repeat guards (`hooks/tezgah_gate.py:1159-1165`) — the drift notice is no longer one of them, it rides the tool-result channel (see Drift) — and put its constants beside its own section.
2. Return through `_deny(session_id, "<rule>", reason, tool, inp, base)` so the ledger counts the refusal (`hooks/tezgah_gate.py:1078-1093`); gate it on the kill switch it belongs
   to (`off(...)`), the way the shortcut and repeat rules use `verify-off` (`hooks/tezgah_gate.py:1074`, `hooks/tezgah_gate.py:1159`).
3. Extend `tests/test_gate.py`. It drives the real function through `tests/_probe_gate.py` (`tests/support.py:20`), which also carries the `capture_log` stub
   standing in for `tezgah_gate.capture` on the allow path (`tests/_probe_gate.py:20-30`). Only if the refusal envelope changes, touch
   `tests/test_claude_adapters.py:42-51` and the codex/cursor/omp hook tests.
4. Mirror the rule in `hosts/opencode/plugins/tezgah.js` and extend `tests/test_opencode_plugin.py` with its cases; that suite is where the two halves are
   compared and where a shared-vocabulary drift fails.

## Source of truth

- `hooks/tezgah_gate.py` — `decision` `hooks/tezgah_gate.py:1094-1266`; every rule constant and refusal text `hooks/tezgah_gate.py:114-214`; `attribution`/`attribution_edit` `hooks/tezgah_gate.py:227-272`; `explored`
  `hooks/tezgah_gate.py:364`; `searched_identifier` `hooks/tezgah_gate.py:369`, `index_slug` `hooks/tezgah_gate.py:384`, `first_nudge` `hooks/tezgah_gate.py:404`, `nudge_reason` `hooks/tezgah_gate.py:421`; `LOOP_ATTEMPTS` `hooks/tezgah_gate.py:442`, `loop_reason` `hooks/tezgah_gate.py:464`,
  `RETRY_CEILING` `hooks/tezgah_gate.py:461`, `retry_reason` `hooks/tezgah_gate.py:495`; `secret_command` `hooks/tezgah_gate.py:521`, `race_reason` `hooks/tezgah_gate.py:611`,
  `drift_reason` `hooks/tezgah_gate.py:1032`, `effectful` `hooks/tezgah_gate.py:1018`, `_deny` `hooks/tezgah_gate.py:1078`; `write_paths` `hooks/tezgah_gate.py:583`, `shell_target` `hooks/tezgah_gate.py:837`, `SHELL_AS_WRITE` `hooks/tezgah_gate.py:580`; the `capture` call `hooks/tezgah_gate.py:1196-1206` (a write tool's target, and a shell write's)
- `hooks/projects-pretooluse.py` — the Claude and dsh envelope; `hooks/tezgah_paths.py` — `off`, `root_for`, `cache_dir`
- `hooks/tezgah_integrity.py` — `BASH_TOOLS`/`WRITE_TOOLS` `hooks/tezgah_integrity.py:251-260`; `NEUTER`/`SKIP_ENV`/`NO_VERIFY`/`GITISH` `:97-105`; `SKIP_TEST` `:106-115`; `TEST_PATH`
  `:116-123`; `call_id` `hooks/tezgah_integrity.py:374-398`; `_path` `:373`, `note` `hooks/tezgah_integrity.py:592-604`, `events` `hooks/tezgah_integrity.py:697-710`, `writers_elsewhere` `hooks/tezgah_integrity.py:829-894`, `mask` `hooks/tezgah_integrity.py:1084-1089`, `shortcut_command` `hooks/tezgah_integrity.py:1090-1114`,
  `shortcut_edit` `hooks/tezgah_integrity.py:1184-1220`
- `hosts/opencode/plugins/tezgah.js` — the JavaScript mirror
- `tests/test_gate.py`, `tests/_probe_gate.py`, `tests/test_opencode_plugin.py`, `tests/test_claude_adapters.py`
