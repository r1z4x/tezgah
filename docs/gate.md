# The gate: every refusal, and what lifts it

This page answers one question: why a tool call was refused before it ran. It is written for the maintainer adding a rule or reading a "the gate missed this"
report, and for the session that has just met a refusal in its transcript. [architecture.md](architecture.md) places the gate among the layers;
[evidence.md](evidence.md) describes the [ledger](glossary.md#ledger) a refusal writes to; [hosts.md](hosts.md) covers the per-host envelopes.

## Where it sits in the call path

One function decides every refusal: `decision(tool, inp, cwd, session_id)` returns a reason string or `None`, and nothing else
(`hooks/tezgah_gate.py:1608-1848`). It answers only inside a tezgah [root](glossary.md#root): outside one `root_for` returns nothing and every call passes
(`hooks/tezgah_gate.py:1567-1569`). The `pretooluse-off` kill switch drops the whole gate (`hooks/tezgah_gate.py:1565-1566`).

Each host's pre-tool hook calls it and wraps the string in that host's own deny envelope — opencode's is its `tool.execute.before`, which throws
`new Error(deny)`; a `None` prints no envelope at all.

| Host | Adapter | Refusal envelope |
|---|---|---|
| claude, dsh | `hooks/projects-pretooluse.py:24-30` (`hosts/dsh/hooks.json:13`) | `hookSpecificOutput.permissionDecision: "deny"` |
| codex, cursor, omp | `hosts/codex/hook.py:136-143`, `hosts/cursor/hook.py:341-342`, `hosts/omp/hook.py:117-120` | that host's own envelope — [hosts.md](hosts.md) |
| opencode | `hosts/opencode/plugins/tezgah.js:2102` | `new Error(deny)` thrown at `hosts/opencode/plugins/tezgah.js:2225` |

Every refusal is also recorded before it is returned: `_deny` appends a ledger row `deny` whose `detail` is `"<rule>: <reason, first 80 chars>"`, plus any
`extra` (`hooks/tezgah_gate.py:1564-1580`). That row, not the reason wording, is where "why was this denied" is answered, and `<rule>` is the name used below.

A call the gate lets through is also where it keeps the pre-write bytes: `capture` runs for a write tool, and for a shell command that writes a file through a
redirect or `tee` - the same shape the task phase rule reads, `write_paths` returns the target for both routes, and a shell write gets its pre-state the same
way (`hooks/tezgah_gate.py:1776-1786`, `write_paths` `hooks/tezgah_gate.py:1133-1160`, `shell_target` `hooks/tezgah_gate.py:1350-1389`). Without it the after-state alone
cannot tell a redirect that wrote the file from one that wrote what was already there, and the freshness half of the Stop rule would read every redirect as a
change; the two halves of that rule are `hooks/tezgah_integrity.py`'s and are described in [evidence.md](evidence.md).

## The rules, in the order `decision` checks them

Bare `:NNN` references on this page are `hooks/tezgah_gate.py` unless another file is named. Each rule ends with its reach: *once*, a mark lifts the next
identical call; *standing*, only changing the call does.

### Explorer — the grep-only subagent

Trigger: tool `agent`/`task`/`subagent` whose `subagent_type` is `explore` or `explorer`, case-insensitively (`hooks/tezgah_gate.py:1570-1577`, `explored` `hooks/tezgah_gate.py:577-581`). Told: use
the general-purpose agent and name `search_graph`, `trace_path`, `search_code` in its prompt (`EXPLORE_DENY` `hooks/tezgah_gate.py:426-432`). Standing: no mark, every such
request is refused.

### Shortcut — a check made unable to fail, or a test disabled

Trigger, shell: `--no-verify`, or `SKIP=`/`HUSKY_SKIP_HOOKS=`/`HUSKY=0`, next to a git/hook word; or a verification command chained with `|| true`/`; true`
(`hooks/tezgah_integrity.py:1001-1019`, `NO_VERIFY` `:62`, `SKIP_ENV` `:61`, `NEUTER` `:56-57`, `GITISH` `:63`). Trigger, edit/write: a skip marker newly
introduced into a test file — the path must match `tests?/`, `test_*`, `*_test`, `*.test.*` (`TEST_PATH` `:75-78`), the marker must survive `mask()` so one
inside a string or comment does not count, and `_added` compares against the file's own text on disk for a `Write` (`:1023-1042`, `SKIP_TEST` `:65-70`). Told:
the texts at `:1008-1019` and `:1075-1078` — run the checks, or say the test is failing; ask the user first if the skip is intended. Standing, with one switch:
`verify-off` removes this check (`hooks/tezgah_gate.py:1587-1599`). The shell is a write route like any other, and the one E7c measured an
armed session taking once the write tools were refused: a heredoc that writes a skip into a test file meets the same predicate, run over the body the
command would land (`shell_write_body` `hooks/tezgah_gate.py:1411-1453`, read at `hooks/tezgah_gate.py:1593` — the body is the raw text, because `mask()` blanks
heredoc bodies by design).

### Attribution — an AI/model credit on its way into an artifact

Trigger, shell: a write command (`WRITE_CMD` `hooks/tezgah_gate.py:193-203` — `git commit|merge|tag|notes`, `gh api`,
`gh pr|issue|release create|edit|comment|review|merge|close`) carrying a credit form (`ATTRIB` `hooks/tezgah_gate.py:168-178` — `co-authored-by:`, `generated with`, `made with`,
`built by`, `assisted by`, `authored by`, `noreply@anthropic`, a robot emoji). Trigger, edit/write: one of the content fields `EDIT_TEXT` (`hooks/tezgah_gate.py:181-191`)
containing a line that *starts* with a credit (`ATTRIB_LINE` `hooks/tezgah_gate.py:179-180`). Told: remove it and re-run; naming a tool in order to use it is fine, crediting it
as author is not (`ATTRIB_DENY` `hooks/tezgah_gate.py:433-439`). Standing. The line anchor is why prose that merely names the banned forms passes (`hooks/tezgah_gate.py:150-159`).
The same twin as the shortcut rule's: a credit a heredoc writes into a file is refused from the body (`hooks/tezgah_gate.py:1602`), and no command has to be
a `git`/`gh` write for it to be this rule's.

### Language — an identifier or message that is not English

Trigger, shell: a command that would create an identifier - `git checkout -b`/`git switch -c`, `git branch` with a new name, a commit subject (`git commit -m`/`--message`/`-F`), or a `gh pr|issue create --title` (the language section `hooks/tezgah_gate.py:440-516`, `created_texts` `hooks/tezgah_gate.py:547`; the text is read from the raw command, because `mask()` blanks quoted strings and a commit subject is one) - whose name or subject is **not English**: a letter outside ASCII anywhere (`non_english` `hooks/tezgah_lang.py:45` - a predicate rather than one language's letter list, so Russian, Greek, Arabic, Chinese and accented Latin hit it exactly as Turkish does) or an ASCII-folded Turkish word from the curated list (`ENGLISH` `hooks/tezgah_lang.py:76`, with `SHORT` `hooks/tezgah_lang.py:153` keeping a four-letter stem whole-token so `sil` cannot refuse `silent`, and `WHOLE` `hooks/tezgah_lang.py:163` holding the three stems that are also prefixes of English words). Told: write the same thing in English and re-issue; the refusal names the offending tokens and, for the ones the list knows, the English to use instead (`refusal` `hooks/tezgah_lang.py:220`, `DENY` `hooks/tezgah_lang.py:165`). With one switch: `lang-off` removes this check (`hooks/tezgah_gate.py:1612-1615`).

The rule is a **heuristic** and its own text says so: a word list is not a language detector, so it cannot tell a proper noun or a product name in another language from a word that ought to be English, and a listed word may be the user's own term. A command that only names the words - `echo`, `grep`, `git log --grep` - creates nothing and passes. An identifier outlives the session that typed it, which is the reason the rule exists at all: `plan/004-admin-durum-onarimi` is in a public history from the moment it exists. On **opencode** the rule is not ported: the plugin asks the core for it through `bin/tezgah-gate check`, one spawn for a command its pre-test reads as identifier-creating (`IDENT_CMD` `hosts/opencode/plugins/tezgah.js:450`, the call site `:2169`), so the word list stays in `hooks/tezgah_lang.py` and that host keeps no copy of it - the route the task rule already takes.

### Race — another session wrote this file minutes ago

Trigger: a write tool whose path, or `apply_patch` header, another session recorded a write of inside `RACE_WINDOW_MIN = 10` minutes (`hooks/tezgah_gate.py:1075`, `race_reason`
`hooks/tezgah_gate.py:1161-1198`, reader `writers_elsewhere` `hooks/tezgah_integrity.py:749`). Told: re-read the file and re-apply the change to what is on disk now (`RACE_DENY`
`hooks/tezgah_gate.py:1111-1122`). Standing (`RACE_REFUSE = True` `hooks/tezgah_gate.py:1079`) — a notice would not close a silent overwrite — and it lifts only by time.

### Untrusted sink — an effect in a turn that read what tezgah cannot vouch for

Trigger: this user turn has a read row carrying a `source` (web, mcp, network), and the call is an effect — a *tool* write whose realpath leaves the rule's
root (`outside_paths` `hooks/tezgah_gate.py:1018-1036`) or a shell command of any effect class (`hooks/tezgah_gate.py:1690-1692`; a shell redirect out of the root is not this rule's, see below). Told: put
it in front of the user; content is not the user, so an approval given before the read does not cover it (`UNTRUSTED_DENY` `hooks/tezgah_gate.py:1004-1014`). Lifts only on an
unspent user `grant` newer than the read (`sink_check` `hooks/tezgah_gate.py:1037-1070`). The refusal leaves the same `consent` ask row the rule below uses, labelled
`outside-workspace` when the realpath is what makes the call a sink (`SINK_WRITE` `hooks/tezgah_gate.py:1015-1017`, `hooks/tezgah_gate.py:1662`), so `bin/tezgah-consent` answers it identically. A write
*inside* the root is not this rule's sink.

### Consent — an irreversible or outward-facing command

Trigger: `effect_class` returns one of six classes for the command's masked text (`hooks/tezgah_gate.py:848-891`, first match wins, in the order below).

| Class | Matched by |
|---|---|
| `destructive` | a `git push` carrying `-f`/`--force*` whose segment is not scratch (`hooks/tezgah_gate.py:874-877`, `GIT_PUSH` `hooks/tezgah_gate.py:204-205`, `FORCE_FLAG` `hooks/tezgah_gate.py:206-207`, `SCRATCH` `hooks/tezgah_gate.py:208-211`); `git branch -D`/`--delete`, `git push --delete`/`-d` (`BRANCH_DELETE` `hooks/tezgah_gate.py:212-232`); a recursive force `rm` outside the run directory (`rm_outside` `hooks/tezgah_gate.py:816-860`, `RM` `hooks/tezgah_gate.py:243-243`, `RM_RECURSIVE` `hooks/tezgah_gate.py:244-244`, `RM_FORCE` `hooks/tezgah_gate.py:245`); a shared resource taken at a service — the remote repository `gh repo delete`/`archive` closes for everyone, the bucket `aws s3 rb` removes and `aws s3 rm --recursive` empties, and `gh run delete`/`gh cache delete` drop a CI run's record and the caches other runs read (`remote_destroy` `hooks/tezgah_gate.py:861-878`, `REMOTE_DESTROY` `hooks/tezgah_gate.py:233-236`, `AWS_S3_RM` `hooks/tezgah_gate.py:237-237`, `AWS_RECURSIVE` `hooks/tezgah_gate.py:238`) |
| `schema` | a migration runner (`MIGRATION` `hooks/tezgah_gate.py:260-269`), including the runner's own `clean` verb — `flyway clean` drops every object in the configured schemas, which is this class reached without an `up`/`down` word |
| `deploy` | a deploy runner (`DEPLOY` `hooks/tezgah_gate.py:270-280`) |
| `publish` | a registry/release/image push (`PUBLISH` `hooks/tezgah_gate.py:281-287`) |
| `outward` | a `git push` to `heroku`/`production`/`prod` (`OUTWARD` `hooks/tezgah_gate.py:288-318`) |
| `send` | mail, a payment API, `nc`/`ncat`/`scp`/`ssh`, an `rsync` whose destination is remote, a `curl`/`gh api` with a write method or a body, or a `gh pr`/`gh issue` write — the same effect as a `gh api` write, reached through a subcommand instead of through the raw API (`SEND` `hooks/tezgah_gate.py:319-343`, `GH_SUBCOMMANDS` `hooks/tezgah_gate.py:192-192`) |

The class is the first that matches. `send` is the one whose member is read by direction: a copy to another host carries data out only when the
*destination* is remote - rsync's last argument, options on either side of the arguments - so `rsync host:/src ./dst` is the read the untrusted
label covers and `rsync ./dst host:/dst` is this class (`hooks/tezgah_gate.py:282-298`). Its other members are matched by shape, not by direction:
`scp` and `ssh` alike, because `ssh host cmd` reaches a machine this ledger holds no pre-state for and runs a command there, which is the same egress
`scp` is - an interactive login is the same call with the command left out, and the class costs one ask either way rather than a policy about who may
log in, the reading `nc --version` already carries (`hooks/tezgah_gate.py:302`).

Told: the class and what it means, the action's digest, and `bin/tezgah-consent <digest>` (`CONSENT_DENY` `hooks/tezgah_gate.py:394-407`, `consent_reason` `hooks/tezgah_gate.py:955-1003`) — never the
pattern that matched. Standing until the user's own `grant`; a re-issue adds nothing (`ASK_STANDS_NOTE` `hooks/tezgah_gate.py:408-414`). A command may declare
`tezgah:effect=<class>` (`DECLARED_EFFECT` `hooks/tezgah_gate.py:392`) for an effect no pattern sees; a declaration can only raise the class along `EFFECT_RANK` (`hooks/tezgah_gate.py:385`), and a
lowering one is named in the refusal (`consent_effect` `hooks/tezgah_gate.py:933-954`, `DOWNGRADE_NOTE` `hooks/tezgah_gate.py:415-418`). A `rm -rf` whose every target is under a temp root is scratch
and asks nobody (`SCRATCH_ROOTS` `hooks/tezgah_gate.py:253-259`, `scratch_ok=True` at `hooks/tezgah_gate.py:1692`; the sink half still counts it, `hooks/tezgah_gate.py:1690-1691`).

### Migration — the `schema` class of the rule above

Trigger: `alembic`/`flyway`/`goose`/`dbmate`/`sqitch` plus an upgrade/down/rollback word (`clean` among them — `flyway clean` drops every object in the
configured schemas), `knex|prisma|sequelize|typeorm ...migrat...`, `manage.py migrate`,
`rails db:migrate|rollback|reset|schema:load` (`MIGRATION` `hooks/tezgah_gate.py:260-269`, matched at `hooks/tezgah_gate.py:881`). Told: the `schema` clause and the consent path.
Standing until the user's grant.

### Secret — a credential on its way into a file

Trigger: one simple command (split on `&&`, `||`, `;`, newline — `SEGMENT` `hooks/tezgah_gate.py:344`) carrying both a token (`SECRET_TOKEN` `hooks/tezgah_gate.py:327-330` — an
`Authorization: Bearer` header, or a `name=value` assignment for `api_key`/`token`/`secret`/`password`/...) and a sink (`SECRET_SINK` `hooks/tezgah_gate.py:352-360` — `>`/`>>`,
`| tee`, a curl `--trace`, or `git add`); `secret_command` `hooks/tezgah_gate.py:1071-1105`. Told: record the name, length or a fingerprint instead, and pass the value through the
tool's environment (`SECRET_DENY` `hooks/tezgah_gate.py:419-425`). Standing, no escape hatch. The shell's own write route is the third twin: a credential inside a heredoc body
is refused from the body (`hooks/tezgah_gate.py:1721`), because `mask()` blanks that body and the text-level scan above cannot see it.

### Ordering — a commit while the newest check failed

The one rule here that asserts a relation between two actions rather than reading one call plus a ledger tail, and the shape FAVA found in 90% of real
agent-instruction projects ("do not commit before running the tests").

Trigger: the command is a `git commit` (or `--amend`; `COMMIT_CMD` `hooks/tezgah_gate.py:1455-1456`, matched at `hooks/tezgah_gate.py:1443`) and the newest check in
this session **failed**. The state is the Stop rule's own fold over the ledger tail (`ORDER_TAIL = 200` `hooks/tezgah_gate.py:1423`, the fold
`tezgah_integrity._last_verify`), and the rule is structurally incapable of firing in either direction that would punish honest work: no check at all folds
to `None` and a passing newest check folds to `ok`, so a commit in a session that ran no check — a docs-only commit — and a commit after a green run both
pass. Only `fail` refuses: the tree the commit would freeze is the one a check just rejected.

Told: the failed check by name and nothing else (`ORDER_DENY` `hooks/tezgah_gate.py:1457-1464`, `commit_order_reason` `hooks/tezgah_gate.py:1465-1495`) —
making the newest check pass is the whole repair, so the refusal names no command that lifts it, for the reason the task refusals carry. Standing while the
tail still shows that failure, under `verify-off` (`hooks/tezgah_gate.py:1728`). Its deny row is its own rule name (`order`), so the counters separate it.

### Loop — the identical attempt that already failed twice

Trigger: the same call (same `call_id`) failed `LOOP_ATTEMPTS = 2` times already in the current user turn (`hooks/tezgah_gate.py:655-655`, `loop_reason` `hooks/tezgah_gate.py:677-707`). Told: attempt N
of an identical call, the failure class read from the ledger, "change the approach or stop" (`hooks/tezgah_gate.py:666-674`). Standing while the ledger tail still shows those
failures. Under `verify-off` (`hooks/tezgah_gate.py:1757`).

### Retry — the session-wide ceiling

Trigger: the same call has been attempted more than `RETRY_CEILING = 3` times in the session, whatever those attempts returned (`hooks/tezgah_gate.py:674-676`, `retry_reason`
`hooks/tezgah_gate.py:708-736`). Told: an unchanged repeat is not a retry (`hooks/tezgah_gate.py:695-700`). Standing. Under `verify-off` (`hooks/tezgah_gate.py:1757`). Both guards read only the ledger tail.

### Nudge — the first identifier-shaped search of a session

Trigger: a `Grep` whose pattern, or a `grep`/`rg` argument (`BASH_SEARCH` `hooks/tezgah_gate.py:147`), matches `IDENT` (`^[A-Za-z_][A-Za-z0-9_]{2,}$`, `hooks/tezgah_gate.py:140`), in a repo whose
codegraph index exists (`<repo>/.codegraph/codegraph.db`; `searched_identifier`
`hooks/tezgah_gate.py:582-596`). Told: the index path and the graph tools
(`nudge_reason` `hooks/tezgah_gate.py:634-654`).
Once-only: the mark in `cache_dir()/nudged/<session>` is written *before* the refusal, so re-issuing the search passes (`first_nudge` `hooks/tezgah_gate.py:617-633`).

### Drift — a long turn loses the rules it started with

Trigger: 25 work rows (`DRIFT_STEPS` `hooks/tezgah_gate.py:1496-1500`) in the current user turn and an effectful call — a write tool, or a git/gh artifact command (`effectful`
`hooks/tezgah_gate.py:1553-1563`). Told: the standing constraints re-stated, or the delta since the turn began; "nothing was refused, so carry on" (`DRIFT_NOTICE` `hooks/tezgah_gate.py:1502-1507`,
`drift_reason` `hooks/tezgah_gate.py:1545-1579`). Not a refusal: the notice rides the tool-result channel, delivered by the PostToolUse side of claude/dsh, codex, cursor and omp, so `decision` never denies for it (opencode's plugin carries no drift path). Once per turn: the `drift` mark is written where the notice is produced, and the count behind it is the turn's own — a bounded read (`DRIFT_TAIL` `hooks/tezgah_gate.py:1501-1501`) falls back to the turn's own start (`turn_rows` `hooks/tezgah_integrity.py:635`) when the turn outgrew the window. Governed by `reminder-off`, not `verify-off` (`hooks/tezgah_gate.py:1537`).

## Seeing what the table does not place

The class table above can only grow from real traffic if something reads the calls it does not place, and `bin/tezgah-status --unclassified` does that:
every shell call that ran (`run`/`verify*`, `SHELL_KINDS` `hooks/tezgah_gate.py:1849-1852`), was never refused (no `deny` row carries its id) and whose command
`effect_class` derives nothing from (`unclassified_effects` `hooks/tezgah_gate.py:1856-1896`). It is a reader: no new row shape, nothing written back, and it
asks today's class table rather than the class a row was judged under, so the answer moves when the table moves.

The CLI folds every ledger on the machine by default and ranks by program — the token the table is grown from — or, with a program argument, that program's
own commands (`bin/tezgah-status:91-117`, capped at `UNCLASSIFIED_CAP = 40` `hooks/tezgah_gate.py:1808`; `--json` prints the whole fold). The four commands
the table gained were checked this way: on this machine's ledger none of them had ever been allowed to run, so the addition costs zero refusals of traffic the
table used to pass.

## The consent path

The gate cannot ask a question mid-call, so the refusal *is* the ask: it records `consent` (the class as `detail`, the action's digest as `id`, the workspace)
and returns the reason that names the digest (`hooks/tezgah_gate.py:1703-1712`). It never writes a `grant` - `consent_mark` reads by kind, id and the workspace
the ask was made in, and treats only the CLI's row as an answer (`hooks/tezgah_gate.py:756-782`) - so a re-issued command meets the refusal again, marked
"the ask is on record already".

The user answers with `bin/tezgah-consent <digest>` or `--last` (the newest ask no grant answers — `open_ask` `bin/tezgah-consent:42-51`, dispatch `:90-96`).
The row written is `{"kind": "grant", "detail": "cli", "id": <digest>}` at `bin/tezgah-consent:109`, into the same session ledger the gate reads:
`cache_dir()/evidence/<slug>.jsonl` (`hooks/tezgah_integrity.py:333-334`). The session is named by `TEZGAH_SESSION` where the host sets it, else every ledger
is searched newest-first (`bin/tezgah-consent:62-66`).

The window: both the ask and the grant are read from the last `CONSENT_TAIL = 200` rows (`hooks/tezgah_gate.py:706`). The ask row also records the scope the
action is judged in - the directory the call runs in, which is what the effect is resolved against, so the identical command in another directory is another
action and is asked about on its own. The grant is a one-shot lease, not a standing permit: `unspent_grant` counts it spent as soon as an outcome row with
the same id follows it, the outcome being the kind a PostToolUse hook writes after a call ran (`STEP_KINDS`: `run`, `edit`, `verify`, `verify_ok`,
`verify_fail`, `interrupted`) rather than an `exit` key - cursor's `afterShellExecution` carries no outcome signal and records `run`/`verify` with no key at all, and `interrupted` is the kind written for a call the host reported as *stopped* rather than answered, which carries no key either - so the
next identical command is asked about again (`hooks/tezgah_gate.py:740-786`). The digest itself stays cwd-blind: it is the loop guard's key too, and one
identity per session is what makes `loop` and `retry` count attempts instead of places (`hooks/tezgah_integrity.py:293`).

## What the gate deliberately does not catch

Read this before filing a security-ish issue; each is a decision, not an oversight.

- A hand-written migration — `psql -c "ALTER TABLE ..."`. "reading SQL intent is not a regex" (`hooks/tezgah_gate.py:241-242`).
- A raw SQL `UPDATE` through `psql -c`: the statement sits in a quoted string that `mask()` blanks (`hooks/tezgah_gate.py:299-301`, `hooks/tezgah_integrity.py:995-1000`).
- A shell write outside the root (`echo x > ../y`): "the class table is the shell's sink list" (`hooks/tezgah_gate.py:970-972`).
- An effect whose target was not named in the user's prompt — the taxonomy's own version. A PreToolUse payload carries the call, never the prompt text, and
  the prompt path stores only `sha1(prompt)[:12]` (`hooks/tezgah_gate.py:951-953`).
- A write inside the root after a fetch: left to the taint notice that `hooks/tezgah_untrusted.py` rides the first effect with, because it is recoverable from
  the snapshot (`hooks/tezgah_gate.py:966-968`).
- `grep -A 3 foo`: a flag with its own value shifts the token, so the search passes unnudged (`hooks/tezgah_gate.py:141-142`).
- A path behind a `cd` in the same line resolves against `cwd`, not the `cd`: "it fails open, never closed" (`hooks/tezgah_gate.py:798-799`).
- A foreign `apply_patch` write: the PostToolUse writer records no path for that row (`hooks/tezgah_gate.py:1136-1137`); and a second session that spells the path differently
  escapes the rule, because the ledger keeps no `cwd` (`hooks/tezgah_gate.py:1088-1090`).
- `nc --version`: connection tools are matched by shape, so it is refused once like any other connection tool - "the direction is the safe one and the refusal
  is one-shot" (`hooks/tezgah_gate.py:282-297`). `rsync` is the one that reads its destination, and what that leaves is a remote destination the pattern
  cannot see as the last argument (behind an alias, a wrapper script or a shell variable) and a `rsync://` argument, which `mask()` blanks like any other
  comment tail (`hooks/tezgah_gate.py:292-298`).
- Which rule the user meant when a turn drifts: "a guess about intent wearing a check's clothes" (`hooks/tezgah_gate.py:1524-1525`).
- A skip already in the file, or one inside a string (a test *about* the rule), is not a disable (`hooks/tezgah_integrity.py:1029-1036`).
- The local, narrow deletes a class table could name but does not — `git reset --hard`, `git tag -d`, `docker compose down -v`, `chmod -R 000`, a plain
  `git push origin main`, `aws s3 rm` without `--recursive`. The line the `destructive`/`schema` additions above pass and these fail: **the effect leaves
  this machine, or takes a resource other people share.** A local operation recoverable from the working tree or the reflog is not worth a round-trip with the
  user, and asking for one trains the agent to re-issue without reading. `git reset --hard` on pushed work is the closest call of the set and is deliberately
  left to the user's judgement, not silently decided here.
- The content of a shell write that is not a heredoc: `echo "Co-Authored-By: x" > f` puts the credit inside a quoted string that no line-start anchor can see,
  and reading the whole command instead would deny a search for the form (`grep "Co-Authored-By" x > out`). The three twins read a heredoc body, which is the
  route E7c measured (`shell_write_body` `hooks/tezgah_gate.py:1411-1453`).
- An `aws s3 rm` whose `--recursive` sits in another simple command: the flag has to be in the same segment as the command (`remote_destroy`
  `hooks/tezgah_gate.py:861-878`), and the flag itself is read from the raw text because `mask()` blanks the `//` tail of an `s3://` argument.
- A shell write whose target is not a redirect: `cp`, `mv`, `sed -i`, `patch` and `git apply` name it as a positional argument, and which argument of those is
  the target is a per-program question, so the gate keeps no pre-state for it and the freshness half reads no change there (`write_paths`
  `hooks/tezgah_gate.py:1133-1160`). A shell write chained with a check in one call (`sed -i ... && pytest`) records as the check row, and the row that carries a
  pass is never the row read as the change - otherwise a check redirecting its own log would stale itself (`tezgah_integrity._change_row`).

**The seat a semantic rule would take, and why it is empty.** Every entry above
is one shape: a call the structural table leaves unclassified, which is exactly
the set a classifier would be asked about. One would fire only when the call is an
effect **and** `effect_class` returned `None` **and** the call is therefore about
to be allowed; it would run inside `decision` on the pre-tool path; it could only
*raise* severity into the existing `consent` ask, never lower a class and never
touch the deny floor; and it would have to fail open on a missing key, a network
error or a timeout, because a gate that stays offline must not become a gate that
blocks when it cannot ask. Nothing of the sort is built, and the measurement is
why: on this machine's own ledger the structural pass missed nothing in 147
allowed effectful calls, an adversarially drawn 20 found two - both `gh` writes,
now covered by the `send` class above - and the classifier-shaped primitive the
eval harness already carries answered `yes` on 12 of those 20 rows, a precision of
0.167 at 768 ms per call. That line is local (`.tezgah/research/`, gitignored);
no file in this checkout calls such a model. The same corpus is what the reader in
[Seeing what the table does not place](#seeing-what-the-table-does-not-place)
re-reads: a table change that would have caught the miss is checkable against the
traffic that produced it, instead of against a hand-built adversarial set.

**The same seat on the Stop path, and why it stays empty too.** The Stop rule's
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
widen a list a regex already covers, on the primitive this page measured at 0.167
precision and 768 ms.

## The mirror: the opencode plugin

opencode cannot run Python hooks, so `hosts/opencode/plugins/tezgah.js` is an independent JavaScript re-implementation of the same rules, dispatched from
`tool.execute.before` (hosts/opencode/plugins/tezgah.js:2051, exported `hosts/opencode/plugins/tezgah.js:2050`) in the gate's own order (`hosts/opencode/plugins/tezgah.js:2113-2188`); its shortcut constants restate the same regexes (`NEUTER` `hosts/opencode/plugins/tezgah.js:382`,
`SKIP_ENV` hosts/opencode/plugins/tezgah.js:341, `NO_VERIFY` `hosts/opencode/plugins/tezgah.js:384`, `GITISH` `hosts/opencode/plugins/tezgah.js:385`, `SKIP_TEST` `hosts/opencode/plugins/tezgah.js:386`). What keeps the two halves honest is a test, not a shared module:
`tests/test_opencode_plugin.py` drives the plugin's hooks through a node harness with a throwaway HOME, and imports the Python `tezgah_integrity.call_id` so a
separator or canonical-form drift in the action id fails there instead of silently in a session (`tests/test_opencode_plugin.py:1-7`, `:21-24`, `tests/test_opencode_plugin.py:1026-1065`).

The two halves agree on the consent rule. A repeat of an irreversible or
outward-facing command the user has not approved is refused again, carrying the ask-stands note rather than a second question
(`hosts/opencode/plugins/tezgah.js:1169-1180`, `hooks/tezgah_gate.py:1703-1712`); a grant is a lease on one effect in one workspace, spent by
the outcome row that follows it, so the next identical command is asked about again instead of passing on the first approval
(`unspent_grant` `hooks/tezgah_gate.py:740-786`, `consentMark` `hosts/opencode/plugins/tezgah.js:1067-1076` - each half records the same scope,
`os.path.realpath(cwd)` against `realpathSync(dir)`, so a row one writes is one the other honours); and the refusal
names the action's digest and the CLI that answers it (`consent_reason` `hooks/tezgah_gate.py:955-1003`, `ASK_STANDS_NOTE`
`hooks/tezgah_gate.py:408-414`). Each half's repeat path is pinned in its own suite (`tests/test_opencode_plugin.py:454-470`, `tests/test_opencode_plugin.py:471-484`;
`tests/test_gate.py:630-658`).

The three rule kinds added last are mirrored too, each pinned in both suites: the shell's write body (`SHELL_WRITE` `hosts/opencode/plugins/tezgah.js:558`,
`heredocBodies` `hosts/opencode/plugins/tezgah.js:564`, `shellWriteBody` `hosts/opencode/plugins/tezgah.js:608`, the shortcut and attribution twins at
`hosts/opencode/plugins/tezgah.js:2149` and `hosts/opencode/plugins/tezgah.js:1239`, the credential twin at `hosts/opencode/plugins/tezgah.js:1198`), the two
shared-resource destroys (`REMOTE_DESTROY` `hosts/opencode/plugins/tezgah.js:237`, `remoteDestroy` `hosts/opencode/plugins/tezgah.js:1333`, `flyway clean` added
to `MIGRATION` `hosts/opencode/plugins/tezgah.js:256`), and the ordering obligation (`COMMIT_CMD` `hosts/opencode/plugins/tezgah.js:999`, `ORDER_DENY`
`hosts/opencode/plugins/tezgah.js:1001`, `lastVerify` `hosts/opencode/plugins/tezgah.js:1011`, `orderReason` `hosts/opencode/plugins/tezgah.js:1036`, dispatched at
`hosts/opencode/plugins/tezgah.js:2183`). `lastVerify` folds the tail exactly as `_last_verify` does, minus the `passing_check` narrowing - this rule reads only
`fail`, and a row that narrowing would refuse reads `ok`/`ran` on both sides, so the outcome is identical. The miner has no mirror: it is a reader on the
status CLI, not a rule a tool call meets.

## Adding a rule

1. Write the check inside `decision` (`hooks/tezgah_gate.py:1608-1848`). A rule is a function returning a `str` reason or `None`; keep an argument-shaped rule
   above the repeat guards (`hooks/tezgah_gate.py:1750-1763`) — the drift notice is no longer one of them, it rides the tool-result channel (see Drift) — and put its constants beside its own section.
2. Return through `_deny(session_id, "<rule>", reason, tool, inp, base)` so the ledger counts the refusal (`hooks/tezgah_gate.py:1564-1580`); gate it on the kill switch it belongs
   to (`off(...)`), the way the shortcut and repeat rules use `verify-off` (`hooks/tezgah_gate.py:1605`, `hooks/tezgah_gate.py:1757`).
3. Extend `tests/test_gate.py`. It drives the real function through `tests/_probe_gate.py` (`tests/support.py:20`), which also carries the `capture_log` stub
   standing in for `tezgah_gate.capture` on the allow path (`tests/_probe_gate.py:20-30`). Only if the refusal envelope changes, touch
   `tests/test_claude_adapters.py:42-51` and the codex/cursor/omp hook tests.
4. Mirror the rule in `hosts/opencode/plugins/tezgah.js` and extend `tests/test_opencode_plugin.py` with its cases; that suite is where the two halves are
   compared and where a shared-vocabulary drift fails.

## Source of truth

- `hooks/tezgah_gate.py` — `decision` `hooks/tezgah_gate.py:1608-1848`; every rule constant and refusal text `hooks/tezgah_gate.py:139-419`; `attribution`/`attribution_edit` `hooks/tezgah_gate.py:440-485`; `explored`
  `hooks/tezgah_gate.py:577`; `searched_identifier` `hooks/tezgah_gate.py:589`, `index_slug` `hooks/tezgah_gate.py:604`, `first_nudge` `hooks/tezgah_gate.py:617-633`, `nudge_reason` `hooks/tezgah_gate.py:634-654`; `LOOP_ATTEMPTS` `hooks/tezgah_gate.py:655-655`, `loop_reason` `hooks/tezgah_gate.py:677-707`,
  `RETRY_CEILING` `hooks/tezgah_gate.py:674-676`, `retry_reason` `hooks/tezgah_gate.py:708-736`; `unspent_grant` `hooks/tezgah_gate.py:740-786`, `consent_mark` `hooks/tezgah_gate.py:787-815`, `rm_outside` `hooks/tezgah_gate.py:816-860`, `effect_class` `hooks/tezgah_gate.py:879-924`, `declared_effect`
  `hooks/tezgah_gate.py:925-932`, `consent_effect` `hooks/tezgah_gate.py:933-954`, `consent_reason` `hooks/tezgah_gate.py:955-1003`, `outside_paths` `hooks/tezgah_gate.py:1018-1036`, `sink_check` `hooks/tezgah_gate.py:1037-1070`, `secret_command` `hooks/tezgah_gate.py:1071-1105`, `race_reason` `hooks/tezgah_gate.py:1161-1198`,
  `drift_reason` `hooks/tezgah_gate.py:1545-1579`, `effectful` `hooks/tezgah_gate.py:1553`, `_deny` `hooks/tezgah_gate.py:1591-1607`; `write_paths` `hooks/tezgah_gate.py:1133-1160`, `shell_target` `hooks/tezgah_gate.py:1350-1389`, `SHELL_AS_WRITE` `hooks/tezgah_gate.py:1130-1132`; the `capture` call `hooks/tezgah_gate.py:1776-1786` (a write tool's target, and a shell write's)
- `hooks/projects-pretooluse.py` — the Claude and dsh envelope; `hooks/tezgah_paths.py` — `off`, `root_for`, `cache_dir`
- `hooks/tezgah_integrity.py` — `BASH_TOOLS`/`WRITE_TOOLS` `hooks/tezgah_integrity.py:172-176`; `NEUTER`/`SKIP_ENV`/`NO_VERIFY`/`GITISH` `:56-63`; `SKIP_TEST` `:65-70`; `TEST_PATH`
  `:75-78`; `call_id` `hooks/tezgah_integrity.py:293`; `_path` `:333`, `note` `hooks/tezgah_integrity.py:512`, `events` `hooks/tezgah_integrity.py:617`, `writers_elsewhere` `hooks/tezgah_integrity.py:749`, `mask` `hooks/tezgah_integrity.py:995`, `shortcut_command` `hooks/tezgah_integrity.py:1001`,
  `shortcut_edit` `hooks/tezgah_integrity.py:1045`
- `bin/tezgah-consent` — the user's half of the consent rule; `hosts/opencode/plugins/tezgah.js` — the JavaScript mirror
- `tests/test_gate.py`, `tests/_probe_gate.py`, `tests/test_opencode_plugin.py`, `tests/test_claude_adapters.py`
