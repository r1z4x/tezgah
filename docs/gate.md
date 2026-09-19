# The gate: every refusal, and what lifts it

This page answers one question: why a tool call was refused before it ran. It is written for the maintainer adding a rule or reading a "the gate missed this"
report, and for the session that has just met a refusal in its transcript. [architecture.md](architecture.md) places the gate among the layers;
[evidence.md](evidence.md) describes the [ledger](glossary.md#ledger) a refusal writes to; [hosts.md](hosts.md) covers the per-host envelopes.

## Where it sits in the call path

One function decides every refusal: `decision(tool, inp, cwd, session_id)` returns a reason string or `None`, and nothing else
(`hooks/tezgah_gate.py:1442-1656`). It answers only inside a tezgah [root](glossary.md#root): outside one `root_for` returns nothing and every call passes
(`hooks/tezgah_gate.py:1446-1448`). The `pretooluse-off` kill switch drops the whole gate (`hooks/tezgah_gate.py:1444-1445`).

Each host's pre-tool hook calls it and wraps the string in that host's own deny envelope — opencode's is its `tool.execute.before`, which throws
`new Error(deny)`; a `None` prints no envelope at all.

| Host | Adapter | Refusal envelope |
|---|---|---|
| claude, dsh | `hooks/projects-pretooluse.py:24-30` (`hosts/dsh/hooks.json:13`) | `hookSpecificOutput.permissionDecision: "deny"` |
| codex, cursor, omp | `hosts/codex/hook.py:118-125`, `hosts/cursor/hook.py:279-281`, `hosts/omp/hook.py:117-120` | that host's own envelope — [hosts.md](hosts.md) |
| opencode | `hosts/opencode/plugins/tezgah.js:2013` | `new Error(deny)` thrown at `hosts/opencode/plugins/tezgah.js:2130` |

Every refusal is also recorded before it is returned: `_deny` appends a ledger row `deny` whose `detail` is `"<rule>: <reason, first 80 chars>"`, plus any
`extra` (`hooks/tezgah_gate.py:1425-1439`). That row, not the reason wording, is where "why was this denied" is answered, and `<rule>` is the name used below.

A call the gate lets through is also where it keeps the pre-write bytes: `capture` runs for a write tool, and for a shell command that writes a file through a
redirect or `tee` - the same shape the task phase rule reads, `write_paths` returns the target for both routes, and a shell write gets its pre-state the same
way (`hooks/tezgah_gate.py:1645-1655`, `write_paths` `hooks/tezgah_gate.py:981`, `shell_target` `hooks/tezgah_gate.py:1198`). Without it the after-state alone
cannot tell a redirect that wrote the file from one that wrote what was already there, and the freshness half of the Stop rule would read every redirect as a
change; the two halves of that rule are `hooks/tezgah_integrity.py`'s and are described in [evidence.md](evidence.md).

## The rules, in the order `decision` checks them

Bare `:NNN` references on this page are `hooks/tezgah_gate.py` unless another file is named. Each rule ends with its reach: *once*, a mark lifts the next
identical call; *standing*, only changing the call does.

### Explorer — the grep-only subagent

Trigger: tool `agent`/`task`/`subagent` whose `subagent_type` is `explore` or `explorer`, case-insensitively (`hooks/tezgah_gate.py:1449-1456`, `explored` `hooks/tezgah_gate.py:433-435`). Told: use
the general-purpose agent and name `search_graph`, `trace_path`, `search_code` in its prompt (`EXPLORE_DENY` `hooks/tezgah_gate.py:402-406`). Standing: no mark, every such
request is refused.

### Shortcut — a check made unable to fail, or a test disabled

Trigger, shell: `--no-verify`, or `SKIP=`/`HUSKY_SKIP_HOOKS=`/`HUSKY=0`, next to a git/hook word; or a verification command chained with `|| true`/`; true`
(`hooks/tezgah_integrity.py:749-766`, `NO_VERIFY` `:62`, `SKIP_ENV` `:61`, `NEUTER` `:56-57`, `GITISH` `:63`). Trigger, edit/write: a skip marker newly
introduced into a test file — the path must match `tests?/`, `test_*`, `*_test`, `*.test.*` (`TEST_PATH` `:75-78`), the marker must survive `mask()` so one
inside a string or comment does not count, and `_added` compares against the file's own text on disk for a `Write` (`:780-814`, `SKIP_TEST` `:65-70`). Told:
the texts at `:743-753` and `:810-813` — run the checks, or say the test is failing; ask the user first if the skip is intended. Standing, with one switch:
`verify-off` removes this check (`hooks/tezgah_gate.py:1466-1478`). The shell is a write route like any other, and the one E7c measured an
armed session taking once the write tools were refused: a heredoc that writes a skip into a test file meets the same predicate, run over the body the
command would land (`shell_write_body` `hooks/tezgah_gate.py:1259`, read at `hooks/tezgah_gate.py:1472` — the body is the raw text, because `mask()` blanks
heredoc bodies by design).

### Attribution — an AI/model credit on its way into an artifact

Trigger, shell: a write command (`WRITE_CMD` `hooks/tezgah_gate.py:169-174` — `git commit|merge|tag|notes`, `gh api`,
`gh pr|issue|release create|edit|comment|review|merge|close`) carrying a credit form (`ATTRIB` `hooks/tezgah_gate.py:140-142` — `co-authored-by:`, `generated with`, `made with`,
`built by`, `assisted by`, `authored by`, `noreply@anthropic`, a robot emoji). Trigger, edit/write: one of the content fields `EDIT_TEXT` (`hooks/tezgah_gate.py:157-158`)
containing a line that *starts* with a credit (`ATTRIB_LINE` `hooks/tezgah_gate.py:153-155`). Told: remove it and re-run; naming a tool in order to use it is fine, crediting it
as author is not (`ATTRIB_DENY` `hooks/tezgah_gate.py:408-412`). Standing. The line anchor is why prose that merely names the banned forms passes (`hooks/tezgah_gate.py:143-152`).
The same twin as the shortcut rule's: a credit a heredoc writes into a file is refused from the body (`hooks/tezgah_gate.py:1481`), and no command has to be
a `git`/`gh` write for it to be this rule's.

### Race — another session wrote this file minutes ago

Trigger: a write tool whose path, or `apply_patch` header, another session recorded a write of inside `RACE_WINDOW_MIN = 10` minutes (`hooks/tezgah_gate.py:954`, `race_reason`
`hooks/tezgah_gate.py:1009-1026`, reader `writers_elsewhere` `hooks/tezgah_integrity.py:527`). Told: re-read the file and re-apply the change to what is on disk now (`RACE_DENY`
`hooks/tezgah_gate.py:959-964`). Standing (`RACE_REFUSE = True` `hooks/tezgah_gate.py:958`) — a notice would not close a silent overwrite — and it lifts only by time.

### Untrusted sink — an effect in a turn that read what tezgah cannot vouch for

Trigger: this user turn has a read row carrying a `source` (web, mcp, network), and the call is an effect — a *tool* write whose realpath leaves the rule's
root (`outside_paths` `hooks/tezgah_gate.py:866-882`) or a shell command of any effect class (`hooks/tezgah_gate.py:1559-1561`; a shell redirect out of the root is not this rule's, see below). Told: put
it in front of the user; content is not the user, so an approval given before the read does not cover it (`UNTRUSTED_DENY` `hooks/tezgah_gate.py:852-859`). Lifts only on an
unspent user `grant` newer than the read (`sink_check` `hooks/tezgah_gate.py:885-916`). The refusal leaves the same `consent` ask row the rule below uses, labelled
`outside-workspace` when the realpath is what makes the call a sink (`SINK_WRITE` `hooks/tezgah_gate.py:863`, `hooks/tezgah_gate.py:1528`), so `bin/tezgah-consent` answers it identically. A write
*inside* the root is not this rule's sink.

### Consent — an irreversible or outward-facing command

Trigger: `effect_class` returns one of six classes for the command's masked text (`hooks/tezgah_gate.py:727-770`, first match wins, in the order below).

| Class | Matched by |
|---|---|
| `destructive` | a `git push` carrying `-f`/`--force*` whose segment is not scratch (`hooks/tezgah_gate.py:753-756`, `GIT_PUSH` `hooks/tezgah_gate.py:180-181`, `FORCE_FLAG` `hooks/tezgah_gate.py:182-183`, `SCRATCH` `hooks/tezgah_gate.py:184-185`); `git branch -D`/`--delete`, `git push --delete`/`-d` (`BRANCH_DELETE` `hooks/tezgah_gate.py:188-192`); a recursive force `rm` outside the run directory (`rm_outside` `hooks/tezgah_gate.py:664-706`, `RM` `hooks/tezgah_gate.py:219`, `RM_RECURSIVE` `hooks/tezgah_gate.py:220`, `RM_FORCE` `hooks/tezgah_gate.py:221`); a shared resource taken at a service — the remote repository `gh repo delete`/`archive` closes for everyone, the bucket `aws s3 rb` removes and `aws s3 rm --recursive` empties, and `gh run delete`/`gh cache delete` drop a CI run's record and the caches other runs read (`remote_destroy` `hooks/tezgah_gate.py:709-725`, `REMOTE_DESTROY` `hooks/tezgah_gate.py:209-212`, `AWS_S3_RM` `hooks/tezgah_gate.py:213`, `AWS_RECURSIVE` `hooks/tezgah_gate.py:214`) |
| `schema` | a migration runner (`MIGRATION` `hooks/tezgah_gate.py:236-244`), including the runner's own `clean` verb — `flyway clean` drops every object in the configured schemas, which is this class reached without an `up`/`down` word |
| `deploy` | a deploy runner (`DEPLOY` `hooks/tezgah_gate.py:246-255`) |
| `publish` | a registry/release/image push (`PUBLISH` `hooks/tezgah_gate.py:257-262`) |
| `outward` | a `git push` to `heroku`/`production`/`prod` (`OUTWARD` `hooks/tezgah_gate.py:264-266`) |
| `send` | mail, a payment API, `nc`/`ncat`/`scp`/`ssh`, an `rsync` whose destination is remote, a `curl`/`gh api` with a write method or a body, or a `gh pr`/`gh issue` write — the same effect as a `gh api` write, reached through a subcommand instead of through the raw API (`SEND` `hooks/tezgah_gate.py:295-311`, `GH_SUBCOMMANDS` `hooks/tezgah_gate.py:168`) |

The class is the first that matches. `send` is the one whose member is read by direction: a copy to another host carries data out only when the
*destination* is remote - rsync's last argument, options on either side of the arguments - so `rsync host:/src ./dst` is the read the untrusted
label covers and `rsync ./dst host:/dst` is this class (`hooks/tezgah_gate.py:275-291`). Its other members are matched by shape, not by direction:
`scp` and `ssh` alike, because `ssh host cmd` reaches a machine this ledger holds no pre-state for and runs a command there, which is the same egress
`scp` is - an interactive login is the same call with the command left out, and the class costs one ask either way rather than a policy about who may
log in, the reading `nc --version` already carries (`hooks/tezgah_gate.py:295`).

Told: the class and what it means, the action's digest, and `bin/tezgah-consent <digest>` (`CONSENT_DENY` `hooks/tezgah_gate.py:370-379`, `consent_reason` `hooks/tezgah_gate.py:803-817`) — never the
pattern that matched. Standing until the user's own `grant`; a re-issue adds nothing (`ASK_STANDS_NOTE` `hooks/tezgah_gate.py:384-386`). A command may declare
`tezgah:effect=<class>` (`DECLARED_EFFECT` `hooks/tezgah_gate.py:368`) for an effect no pattern sees; a declaration can only raise the class along `EFFECT_RANK` (`hooks/tezgah_gate.py:361`), and a
lowering one is named in the refusal (`consent_effect` `hooks/tezgah_gate.py:781-800`, `DOWNGRADE_NOTE` `hooks/tezgah_gate.py:391-393`). A `rm -rf` whose every target is under a temp root is scratch
and asks nobody (`SCRATCH_ROOTS` `hooks/tezgah_gate.py:229-230`, `scratch_ok=True` at `hooks/tezgah_gate.py:1561`; the sink half still counts it, `hooks/tezgah_gate.py:1559-1560`).

### Migration — the `schema` class of the rule above

Trigger: `alembic`/`flyway`/`goose`/`dbmate`/`sqitch` plus an upgrade/down/rollback word (`clean` among them — `flyway clean` drops every object in the
configured schemas), `knex|prisma|sequelize|typeorm ...migrat...`, `manage.py migrate`,
`rails db:migrate|rollback|reset|schema:load` (`MIGRATION` `hooks/tezgah_gate.py:236-244`, matched at `hooks/tezgah_gate.py:760`). Told: the `schema` clause and the consent path.
Standing until the user's grant.

### Secret — a credential on its way into a file

Trigger: one simple command (split on `&&`, `||`, `;`, newline — `SEGMENT` `hooks/tezgah_gate.py:337`) carrying both a token (`SECRET_TOKEN` `hooks/tezgah_gate.py:320-323` — an
`Authorization: Bearer` header, or a `name=value` assignment for `api_key`/`token`/`secret`/`password`/...) and a sink (`SECRET_SINK` `hooks/tezgah_gate.py:328-330` — `>`/`>>`,
`| tee`, a curl `--trace`, or `git add`); `secret_command` `hooks/tezgah_gate.py:919-935`. Told: record the name, length or a fingerprint instead, and pass the value through the
tool's environment (`SECRET_DENY` `hooks/tezgah_gate.py:395-400`). Standing, no escape hatch. The shell's own write route is the third twin: a credential inside a heredoc body
is refused from the body (`hooks/tezgah_gate.py:1590`), because `mask()` blanks that body and the text-level scan above cannot see it.

### Ordering — a commit while the newest check failed

The one rule here that asserts a relation between two actions rather than reading one call plus a ledger tail, and the shape FAVA found in 90% of real
agent-instruction projects ("do not commit before running the tests").

Trigger: the command is a `git commit` (or `--amend`; `COMMIT_CMD` `hooks/tezgah_gate.py:1303`, matched at `hooks/tezgah_gate.py:1598`) and the newest check in
this session **failed**. The state is the Stop rule's own fold over the ledger tail (`ORDER_TAIL = 200` `hooks/tezgah_gate.py:1302`, the fold
`tezgah_integrity._last_verify`), and the rule is structurally incapable of firing in either direction that would punish honest work: no check at all folds
to `None` and a passing newest check folds to `ok`, so a commit in a session that ran no check — a docs-only commit — and a commit after a green run both
pass. Only `fail` refuses: the tree the commit would freeze is the one a check just rejected.

Told: the failed check by name and nothing else (`ORDER_DENY` `hooks/tezgah_gate.py:1305-1310`, `commit_order_reason` `hooks/tezgah_gate.py:1313-1325`) —
making the newest check pass is the whole repair, so the refusal names no command that lifts it, for the reason the task refusals carry. Standing while the
tail still shows that failure, under `verify-off` (`hooks/tezgah_gate.py:1597`). Its deny row is its own rule name (`order`), so the counters separate it.

### Loop — the identical attempt that already failed twice

Trigger: the same call (same `call_id`) failed `LOOP_ATTEMPTS = 2` times already in the current user turn (`hooks/tezgah_gate.py:503`, `loop_reason` `hooks/tezgah_gate.py:525-553`). Told: attempt N
of an identical call, the failure class read from the ledger, "change the approach or stop" (`hooks/tezgah_gate.py:545-553`). Standing while the ledger tail still shows those
failures. Under `verify-off` (`hooks/tezgah_gate.py:1608`).

### Retry — the session-wide ceiling

Trigger: the same call has been attempted more than `RETRY_CEILING = 3` times in the session, whatever those attempts returned (`hooks/tezgah_gate.py:522`, `retry_reason`
`hooks/tezgah_gate.py:556-579`). Told: an unchanged repeat is not a retry (`hooks/tezgah_gate.py:574-579`). Standing. Under `verify-off` (`hooks/tezgah_gate.py:1608`). Both guards read only the ledger tail.

### Nudge — the first identifier-shaped search of a session

Trigger: a `Grep` whose pattern, or a `grep`/`rg` argument (`BASH_SEARCH` `hooks/tezgah_gate.py:136`), matches `IDENT` (`^[A-Za-z_][A-Za-z0-9_]{2,}$`, `hooks/tezgah_gate.py:133`), in a repo whose
codebase-memory db exists (`searched_identifier` `hooks/tezgah_gate.py:438-450`, `index_slug` `hooks/tezgah_gate.py:453-462`). Told: the index slug and the graph tools (`nudge_reason` `hooks/tezgah_gate.py:482-487`).
Once-only: the mark in `cache_dir()/nudged/<session>` is written *before* the refusal, so re-issuing the search passes (`first_nudge` `hooks/tezgah_gate.py:465-479`).

### Drift — a long turn loses the rules it started with

Trigger: 25 work rows (`DRIFT_STEPS` `hooks/tezgah_gate.py:1339`) in the current user turn and an effectful call — a write tool, or a git/gh artifact command (`effectful`
`hooks/tezgah_gate.py:1414-1422`). Told: the standing constraints re-stated, or the delta since the turn began; "re-issue this call unchanged" (`DRIFT_DENY` `hooks/tezgah_gate.py:1344-1348`,
`drift_reason` `hooks/tezgah_gate.py:1387-1411`). Once per turn: the `drift` mark is written before the refusal. Governed by `reminder-off`, not `verify-off` (`hooks/tezgah_gate.py:1626`).

## Seeing what the table does not place

The class table above can only grow from real traffic if something reads the calls it does not place, and `bin/tezgah-status --unclassified` does that:
every shell call that ran (`run`/`verify*`, `SHELL_KINDS` `hooks/tezgah_gate.py:1673`), was never refused (no `deny` row carries its id) and whose command
`effect_class` derives nothing from (`unclassified_effects` `hooks/tezgah_gate.py:1680-1717`). It is a reader: no new row shape, nothing written back, and it
asks today's class table rather than the class a row was judged under, so the answer moves when the table moves.

The CLI folds every ledger on the machine by default and ranks by program — the token the table is grown from — or, with a program argument, that program's
own commands (`bin/tezgah-status:91-117`, capped at `UNCLASSIFIED_CAP = 40` `hooks/tezgah_gate.py:1677`; `--json` prints the whole fold). The four commands
the table gained were checked this way: on this machine's ledger none of them had ever been allowed to run, so the addition costs zero refusals of traffic the
table used to pass.

## The consent path

The gate cannot ask a question mid-call, so the refusal *is* the ask: it records `consent` (the class as `detail`, the action's digest as `id`, the workspace)
and returns the reason that names the digest (`hooks/tezgah_gate.py:1572-1581`). It never writes a `grant` - `consent_mark` reads by kind, id and the workspace
the ask was made in, and treats only the CLI's row as an answer (`hooks/tezgah_gate.py:635-661`) - so a re-issued command meets the refusal again, marked
"the ask is on record already".

The user answers with `bin/tezgah-consent <digest>` or `--last` (the newest ask no grant answers — `open_ask` `bin/tezgah-consent:42-51`, dispatch `:90-96`).
The row written is `{"kind": "grant", "detail": "cli", "id": <digest>}` at `bin/tezgah-consent:109`, into the same session ledger the gate reads:
`cache_dir()/evidence/<slug>.jsonl` (`hooks/tezgah_integrity.py:243-244`). The session is named by `TEZGAH_SESSION` where the host sets it, else every ledger
is searched newest-first (`bin/tezgah-consent:62-66`).

The window: both the ask and the grant are read from the last `CONSENT_TAIL = 200` rows (`hooks/tezgah_gate.py:585`). The ask row also records the scope the
action is judged in - the directory the call runs in, which is what the effect is resolved against, so the identical command in another directory is another
action and is asked about on its own. The grant is a one-shot lease, not a standing permit: `unspent_grant` counts it spent as soon as an outcome row with
the same id follows it, the outcome being the kind a PostToolUse hook writes after a call ran (`STEP_KINDS`: `run`, `edit`, `verify`, `verify_ok`,
`verify_fail`) rather than an `exit` key - cursor's `afterShellExecution` carries no outcome signal and records `run`/`verify` with no key at all - so the
next identical command is asked about again (`hooks/tezgah_gate.py:588-632`). The digest itself stays cwd-blind: it is the loop guard's key too, and one
identity per session is what makes `loop` and `retry` count attempts instead of places (`hooks/tezgah_integrity.py:203`).

## What the gate deliberately does not catch

Read this before filing a security-ish issue; each is a decision, not an oversight.

- A hand-written migration — `psql -c "ALTER TABLE ..."`. "reading SQL intent is not a regex" (`hooks/tezgah_gate.py:234-235`).
- A raw SQL `UPDATE` through `psql -c`: the statement sits in a quoted string that `mask()` blanks (`hooks/tezgah_gate.py:292-294`, `hooks/tezgah_integrity.py:743-746`).
- A shell write outside the root (`echo x > ../y`): "the class table is the shell's sink list" (`hooks/tezgah_gate.py:849-851`).
- An effect whose target was not named in the user's prompt — the taxonomy's own version. A PreToolUse payload carries the call, never the prompt text, and
  the prompt path stores only `sha1(prompt)[:12]` (`hooks/tezgah_gate.py:830-832`).
- A write inside the root after a fetch: left to the taint notice that `hooks/tezgah_untrusted.py` rides the first effect with, because it is recoverable from
  the snapshot (`hooks/tezgah_gate.py:845-847`).
- `grep -A 3 foo`: a flag with its own value shifts the token, so the search passes unnudged (`hooks/tezgah_gate.py:134-135`).
- A path behind a `cd` in the same line resolves against `cwd`, not the `cd`: "it fails open, never closed" (`hooks/tezgah_gate.py:677-678`).
- A foreign `apply_patch` write: the PostToolUse writer records no path for that row (`hooks/tezgah_gate.py:1015-1016`); and a second session that spells the path differently
  escapes the rule, because the ledger keeps no `cwd` (`hooks/tezgah_gate.py:967-969`).
- `nc --version`: connection tools are matched by shape, so it is refused once like any other connection tool - "the direction is the safe one and the refusal
  is one-shot" (`hooks/tezgah_gate.py:275-290`). `rsync` is the one that reads its destination, and what that leaves is a remote destination the pattern
  cannot see as the last argument (behind an alias, a wrapper script or a shell variable) and a `rsync://` argument, which `mask()` blanks like any other
  comment tail (`hooks/tezgah_gate.py:285-291`).
- Which rule the user meant when a turn drifts: "a guess about intent wearing a check's clothes" (`hooks/tezgah_gate.py:1393-1394`).
- A skip already in the file, or one inside a string (a test *about* the rule), is not a disable (`hooks/tezgah_integrity.py:793-800`).
- The local, narrow deletes a class table could name but does not — `git reset --hard`, `git tag -d`, `docker compose down -v`, `chmod -R 000`, a plain
  `git push origin main`, `aws s3 rm` without `--recursive`. The line the `destructive`/`schema` additions above pass and these fail: **the effect leaves
  this machine, or takes a resource other people share.** A local operation recoverable from the working tree or the reflog is not worth a round-trip with the
  user, and asking for one trains the agent to re-issue without reading. `git reset --hard` on pushed work is the closest call of the set and is deliberately
  left to the user's judgement, not silently decided here.
- The content of a shell write that is not a heredoc: `echo "Co-Authored-By: x" > f` puts the credit inside a quoted string that no line-start anchor can see,
  and reading the whole command instead would deny a search for the form (`grep "Co-Authored-By" x > out`). The three twins read a heredoc body, which is the
  route E7c measured (`shell_write_body` `hooks/tezgah_gate.py:1259-1280`).
- An `aws s3 rm` whose `--recursive` sits in another simple command: the flag has to be in the same segment as the command (`remote_destroy`
  `hooks/tezgah_gate.py:709-725`), and the flag itself is read from the raw text because `mask()` blanks the `//` tail of an `s3://` argument.
- A shell write whose target is not a redirect: `cp`, `mv`, `sed -i`, `patch` and `git apply` name it as a positional argument, and which argument of those is
  the target is a per-program question, so the gate keeps no pre-state for it and the freshness half reads no change there (`write_paths`
  `hooks/tezgah_gate.py:981`). A shell write chained with a check in one call (`sed -i ... && pytest`) records as the check row, and the row that carries a
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
`tool.execute.before` (hosts/opencode/plugins/tezgah.js:1610, exported `hosts/opencode/plugins/tezgah.js:1961`) in the gate's own order (`hosts/opencode/plugins/tezgah.js:2027-2096`); its shortcut constants restate the same regexes (`NEUTER` `hosts/opencode/plugins/tezgah.js:300`,
`SKIP_ENV` hosts/opencode/plugins/tezgah.js:295, `NO_VERIFY` `hosts/opencode/plugins/tezgah.js:302`, `GITISH` `hosts/opencode/plugins/tezgah.js:303`, `SKIP_TEST` `hosts/opencode/plugins/tezgah.js:304`). What keeps the two halves honest is a test, not a shared module:
`tests/test_opencode_plugin.py` drives the plugin's hooks through a node harness with a throwaway HOME, and imports the Python `tezgah_integrity.call_id` so a
separator or canonical-form drift in the action id fails there instead of silently in a session (`tests/test_opencode_plugin.py:1-7`, `:21-24`, `tests/test_opencode_plugin.py:1026-1065`).

The two halves agree on the consent rule. A repeat of an irreversible or
outward-facing command the user has not approved is refused again, carrying the ask-stands note rather than a second question
(`hosts/opencode/plugins/tezgah.js:1032-1043`, `hooks/tezgah_gate.py:1572-1581`); a grant is a lease on one effect in one workspace, spent by
the outcome row that follows it, so the next identical command is asked about again instead of passing on the first approval
(`unspent_grant` `hooks/tezgah_gate.py:588-632`, `consentMark` `hosts/opencode/plugins/tezgah.js:963-972` - each half records the same scope,
`os.path.realpath(cwd)` against `realpathSync(dir)`, so a row one writes is one the other honours); and the refusal
names the action's digest and the CLI that answers it (`consent_reason` `hooks/tezgah_gate.py:803-817`, `ASK_STANDS_NOTE`
`hooks/tezgah_gate.py:384-386`). Each half's repeat path is pinned in its own suite (`tests/test_opencode_plugin.py:454-470`, `tests/test_opencode_plugin.py:471-484`;
`tests/test_gate.py:630-658`).

The three rule kinds added last are mirrored too, each pinned in both suites: the shell's write body (`SHELL_WRITE` `hosts/opencode/plugins/tezgah.js:454`,
`heredocBodies` `hosts/opencode/plugins/tezgah.js:460`, `shellWriteBody` `hosts/opencode/plugins/tezgah.js:504`, the shortcut and attribution twins at
`hosts/opencode/plugins/tezgah.js:2060` and `hosts/opencode/plugins/tezgah.js:2027`, the credential twin at `hosts/opencode/plugins/tezgah.js:1088`), the two
shared-resource destroys (`REMOTE_DESTROY` `hosts/opencode/plugins/tezgah.js:155`, `remoteDestroy` `hosts/opencode/plugins/tezgah.js:1223`, `flyway clean` added
to `MIGRATION` `hosts/opencode/plugins/tezgah.js:174`), and the ordering obligation (`COMMIT_CMD` `hosts/opencode/plugins/tezgah.js:895`, `ORDER_DENY`
`hosts/opencode/plugins/tezgah.js:897`, `lastVerify` `hosts/opencode/plugins/tezgah.js:907`, `orderReason` `hosts/opencode/plugins/tezgah.js:932`, dispatched at
`hosts/opencode/plugins/tezgah.js:2089`). `lastVerify` folds the tail exactly as `_last_verify` does, minus the `passing_check` narrowing - this rule reads only
`fail`, and a row that narrowing would refuse reads `ok`/`ran` on both sides, so the outcome is identical. The miner has no mirror: it is a reader on the
status CLI, not a rule a tool call meets.

## Adding a rule

1. Write the check inside `decision` (`hooks/tezgah_gate.py:1442-1656`). A rule is a function returning a `str` reason or `None`; keep an argument-shaped rule
   above the repeat guards (`hooks/tezgah_gate.py:1608-1614`) and the drift notice last (`hooks/tezgah_gate.py:1621-1629`), and put its constants beside its own section.
2. Return through `_deny(session_id, "<rule>", reason, tool, inp, base)` so the ledger counts the refusal (`hooks/tezgah_gate.py:1425-1439`); gate it on the kill switch it belongs
   to (`off(...)`), the way the shortcut and repeat rules use `verify-off` (`hooks/tezgah_gate.py:1466`, `hooks/tezgah_gate.py:1608`).
3. Extend `tests/test_gate.py`. It drives the real function through `tests/_probe_gate.py` (`tests/support.py:20`), which also carries the `capture_log` stub
   standing in for `tezgah_gate.capture` on the allow path (`tests/_probe_gate.py:20-30`). Only if the refusal envelope changes, touch
   `tests/test_claude_adapters.py:42-51` and the codex/cursor/omp hook tests.
4. Mirror the rule in `hosts/opencode/plugins/tezgah.js` and extend `tests/test_opencode_plugin.py` with its cases; that suite is where the two halves are
   compared and where a shared-vocabulary drift fails.

## Source of truth

- `hooks/tezgah_gate.py` — `decision` `hooks/tezgah_gate.py:1442-1656`; every rule constant and refusal text `hooks/tezgah_gate.py:132-412`; `attribution`/`attribution_edit` `hooks/tezgah_gate.py:415-430`; `explored`
  `hooks/tezgah_gate.py:433`; `searched_identifier` `hooks/tezgah_gate.py:438`, `index_slug` `hooks/tezgah_gate.py:453`, `first_nudge` `hooks/tezgah_gate.py:465`, `nudge_reason` `hooks/tezgah_gate.py:482`; `LOOP_ATTEMPTS` `hooks/tezgah_gate.py:503`, `loop_reason` `hooks/tezgah_gate.py:525`,
  `RETRY_CEILING` `hooks/tezgah_gate.py:522`, `retry_reason` `hooks/tezgah_gate.py:556`; `unspent_grant` `hooks/tezgah_gate.py:588`, `consent_mark` `hooks/tezgah_gate.py:635`, `rm_outside` `hooks/tezgah_gate.py:664`, `effect_class` `hooks/tezgah_gate.py:727`, `declared_effect`
  `hooks/tezgah_gate.py:773`, `consent_effect` `hooks/tezgah_gate.py:781`, `consent_reason` `hooks/tezgah_gate.py:803`, `outside_paths` `hooks/tezgah_gate.py:866`, `sink_check` `hooks/tezgah_gate.py:885`, `secret_command` `hooks/tezgah_gate.py:919`, `race_reason` `hooks/tezgah_gate.py:1009`,
  `drift_reason` `hooks/tezgah_gate.py:1387`, `effectful` `hooks/tezgah_gate.py:1414`, `_deny` `hooks/tezgah_gate.py:1425`; `write_paths` `hooks/tezgah_gate.py:981`, `shell_target` `hooks/tezgah_gate.py:1198`, `SHELL_AS_WRITE` `hooks/tezgah_gate.py:978`; the `capture` call `hooks/tezgah_gate.py:1645-1655` (a write tool's target, and a shell write's)
- `hooks/projects-pretooluse.py` — the Claude and dsh envelope; `hooks/tezgah_paths.py` — `off`, `root_for`, `cache_dir`
- `hooks/tezgah_integrity.py` — `BASH_TOOLS`/`WRITE_TOOLS` `:123-127`; `NEUTER`/`SKIP_ENV`/`NO_VERIFY`/`GITISH` `:56-63`; `SKIP_TEST` `:65-70`; `TEST_PATH`
  `:75-78`; `call_id` `:203`; `_path` `:243`, `note` `:377`, `events` `:465`, `writers_elsewhere` `:527`, `mask` `:752`, `shortcut_command` `:758`,
  `shortcut_edit` `:802`
- `bin/tezgah-consent` — the user's half of the consent rule; `hosts/opencode/plugins/tezgah.js` — the JavaScript mirror
- `tests/test_gate.py`, `tests/_probe_gate.py`, `tests/test_opencode_plugin.py`, `tests/test_claude_adapters.py`
