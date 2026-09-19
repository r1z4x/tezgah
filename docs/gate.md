# The gate: every refusal, and what lifts it

This page answers one question: why a tool call was refused before it ran. It is written for the maintainer adding a rule or reading a "the gate missed this"
report, and for the session that has just met a refusal in its transcript. [architecture.md](architecture.md) places the gate among the layers;
[evidence.md](evidence.md) describes the [ledger](glossary.md#ledger) a refusal writes to; [hosts.md](hosts.md) covers the per-host envelopes.

## Where it sits in the call path

One function decides every refusal: `decision(tool, inp, cwd, session_id)` returns a reason string or `None`, and nothing else
(`hooks/tezgah_gate.py:1198-1373`). It answers only inside a tezgah [root](glossary.md#root): outside one `root_for` returns nothing and every call passes
(`hooks/tezgah_gate.py:1202-1204`). The `pretooluse-off` kill switch drops the whole gate (`hooks/tezgah_gate.py:1200-1201`).

Each host's pre-tool hook calls it and wraps the string in that host's own deny envelope — opencode's is its `tool.execute.before`, which throws
`new Error(deny)`; a `None` prints no envelope at all.

| Host | Adapter | Refusal envelope |
|---|---|---|
| claude, dsh | `hooks/projects-pretooluse.py:24-30` (`hosts/dsh/hooks.json:13`) | `hookSpecificOutput.permissionDecision: "deny"` |
| codex, cursor, omp | `hosts/codex/hook.py:118-125`, `hosts/cursor/hook.py:279-281`, `hosts/omp/hook.py:117-120` | that host's own envelope — [hosts.md](hosts.md) |
| opencode | `hosts/opencode/plugins/tezgah.js:1407` | `new Error(deny)` thrown at `hosts/opencode/plugins/tezgah.js:1488` |

Every refusal is also recorded before it is returned: `_deny` appends a ledger row `deny` whose `detail` is `"<rule>: <reason, first 80 chars>"`, plus any
`extra` (`hooks/tezgah_gate.py:1181-1195`). That row, not the reason wording, is where "why was this denied" is answered, and `<rule>` is the name used below.

## The rules, in the order `decision` checks them

Bare `:NNN` references on this page are `hooks/tezgah_gate.py` unless another file is named. Each rule ends with its reach: *once*, a mark lifts the next
identical call; *standing*, only changing the call does.

### Explorer — the grep-only subagent

Trigger: tool `agent`/`task`/`subagent` whose `subagent_type` is `explore` or `explorer`, case-insensitively (`hooks/tezgah_gate.py:1205-1207`, `explored` `hooks/tezgah_gate.py:383-385`). Told: use
the general-purpose agent and name `search_graph`, `trace_path`, `search_code` in its prompt (`EXPLORE_DENY` `hooks/tezgah_gate.py:352-356`). Standing: no mark, every such
request is refused.

### Shortcut — a check made unable to fail, or a test disabled

Trigger, shell: `--no-verify`, or `SKIP=`/`HUSKY_SKIP_HOOKS=`/`HUSKY=0`, next to a git/hook word; or a verification command chained with `|| true`/`; true`
(`hooks/tezgah_integrity.py:736-753`, `NO_VERIFY` `:62`, `SKIP_ENV` `:61`, `NEUTER` `:56-57`, `GITISH` `:63`). Trigger, edit/write: a skip marker newly
introduced into a test file — the path must match `tests?/`, `test_*`, `*_test`, `*.test.*` (`TEST_PATH` `:75-78`), the marker must survive `mask()` so one
inside a string or comment does not count, and `_added` compares against the file's own text on disk for a `Write` (`:780-814`, `SKIP_TEST` `:65-70`). Told:
the texts at `:743-753` and `:810-813` — run the checks, or say the test is failing; ask the user first if the skip is intended. Standing, with one switch:
`verify-off` removes this check (`hooks/tezgah_gate.py:1216-1224`).

### Attribution — an AI/model credit on its way into an artifact

Trigger, shell: a write command (`WRITE_CMD` `hooks/tezgah_gate.py:148-153` — `git commit|merge|tag|notes`, `gh api`,
`gh pr|issue|release create|edit|comment|review|merge|close`) carrying a credit form (`ATTRIB` `hooks/tezgah_gate.py:119-121` — `co-authored-by:`, `generated with`, `made with`,
`built by`, `assisted by`, `authored by`, `noreply@anthropic`, a robot emoji). Trigger, edit/write: one of the content fields `EDIT_TEXT` (`hooks/tezgah_gate.py:136-137`)
containing a line that *starts* with a credit (`ATTRIB_LINE` `hooks/tezgah_gate.py:132-134`). Told: remove it and re-run; naming a tool in order to use it is fine, crediting it
as author is not (`ATTRIB_DENY` `hooks/tezgah_gate.py:358-362`). Standing. The line anchor is why prose that merely names the banned forms passes (`hooks/tezgah_gate.py:122-131`).

### Race — another session wrote this file minutes ago

Trigger: a write tool whose path, or `apply_patch` header, another session recorded a write of inside `RACE_WINDOW_MIN = 10` minutes (`hooks/tezgah_gate.py:886`, `race_reason`
`hooks/tezgah_gate.py:919-936`, reader `writers_elsewhere` `hooks/tezgah_integrity.py:514`). Told: re-read the file and re-apply the change to what is on disk now (`RACE_DENY`
`hooks/tezgah_gate.py:891-896`). Standing (`RACE_REFUSE = True` `hooks/tezgah_gate.py:890`) — a notice would not close a silent overwrite — and it lifts only by time.

### Untrusted sink — an effect in a turn that read what tezgah cannot vouch for

Trigger: this user turn has a read row carrying a `source` (web, mcp, network), and the call is an effect — a *tool* write whose realpath leaves the rule's
root (`outside_paths` `hooks/tezgah_gate.py:798-814`) or a shell command of any effect class (`hooks/tezgah_gate.py:1303-1305`; a shell redirect out of the root is not this rule's, see below). Told: put
it in front of the user; content is not the user, so an approval given before the read does not cover it (`UNTRUSTED_DENY` `hooks/tezgah_gate.py:784-791`). Lifts only on an
unspent user `grant` newer than the read (`sink_check` `hooks/tezgah_gate.py:817-848`). The refusal leaves the same `consent` ask row the rule below uses, labelled
`outside-workspace` when the realpath is what makes the call a sink (`SINK_WRITE` `hooks/tezgah_gate.py:795`, `hooks/tezgah_gate.py:1272`), so `bin/tezgah-consent` answers it identically. A write
*inside* the root is not this rule's sink.

### Consent — an irreversible or outward-facing command

Trigger: `effect_class` returns one of six classes for the command's masked text (`hooks/tezgah_gate.py:659-702`, first match wins, in the order below).

| Class | Matched by |
|---|---|
| `destructive` | a `git push` carrying `-f`/`--force*` whose segment is not scratch (`hooks/tezgah_gate.py:685-688`, `GIT_PUSH` `hooks/tezgah_gate.py:159-160`, `FORCE_FLAG` `hooks/tezgah_gate.py:161-162`, `SCRATCH` `hooks/tezgah_gate.py:163-164`); `git branch -D`/`--delete`, `git push --delete`/`-d` (`BRANCH_DELETE` `hooks/tezgah_gate.py:167-171`); a recursive force `rm` outside the run directory (`rm_outside` `hooks/tezgah_gate.py:614-656`, `RM` `hooks/tezgah_gate.py:176`, `RM_RECURSIVE` `hooks/tezgah_gate.py:177`, `RM_FORCE` `hooks/tezgah_gate.py:178`) |
| `schema` | a migration runner (`MIGRATION` `hooks/tezgah_gate.py:190-198`) |
| `deploy` | a deploy runner (`DEPLOY` `hooks/tezgah_gate.py:200-209`) |
| `publish` | a registry/release/image push (`PUBLISH` `hooks/tezgah_gate.py:211-216`) |
| `outward` | a `git push` to `heroku`/`production`/`prod` (`OUTWARD` `hooks/tezgah_gate.py:218-220`) |
| `send` | mail, a payment API, `nc`/`ncat`/`scp`, an `rsync` whose destination is remote, a `curl`/`gh api` with a write method or a body, or a `gh pr`/`gh issue` write — the same effect as a `gh api` write, reached through a subcommand instead of through the raw API (`SEND` `hooks/tezgah_gate.py:246-262`, `GH_SUBCOMMANDS` `hooks/tezgah_gate.py:147`) |

The class is the first that matches. `send` is the one whose member is read by direction: a copy to another host carries data out only when the
*destination* is remote - rsync's last argument, options on either side of the arguments - so `rsync host:/src ./dst` is the read the untrusted
label covers and `rsync ./dst host:/dst` is this class (`hooks/tezgah_gate.py:229-242`).

Told: the class and what it means, the action's digest, and `bin/tezgah-consent <digest>` (`CONSENT_DENY` `hooks/tezgah_gate.py:320-329`, `consent_reason` `hooks/tezgah_gate.py:735-749`) — never the
pattern that matched. Standing until the user's own `grant`; a re-issue adds nothing (`ASK_STANDS_NOTE` `hooks/tezgah_gate.py:334-336`). A command may declare
`tezgah:effect=<class>` (`DECLARED_EFFECT` `hooks/tezgah_gate.py:318`) for an effect no pattern sees; a declaration can only raise the class along `EFFECT_RANK` (`hooks/tezgah_gate.py:311`), and a
lowering one is named in the refusal (`consent_effect` `hooks/tezgah_gate.py:713-732`, `DOWNGRADE_NOTE` `hooks/tezgah_gate.py:341-343`). A `rm -rf` whose every target is under a temp root is scratch
and asks nobody (`SCRATCH_ROOTS` `hooks/tezgah_gate.py:186-187`, `scratch_ok=True` at `hooks/tezgah_gate.py:1305`; the sink half still counts it, `hooks/tezgah_gate.py:1303-1304`).

### Migration — the `schema` class of the rule above

Trigger: `alembic`/`flyway`/`goose`/`dbmate`/`sqitch` plus an upgrade/down/rollback word, `knex|prisma|sequelize|typeorm ...migrat...`, `manage.py migrate`,
`rails db:migrate|rollback|reset|schema:load` (`MIGRATION` `hooks/tezgah_gate.py:190-198`, matched at `hooks/tezgah_gate.py:692`). Told: the `schema` clause and the consent path.
Standing until the user's grant.

### Secret — a credential on its way into a file

Trigger: one simple command (split on `&&`, `||`, `;`, newline — `SEGMENT` `hooks/tezgah_gate.py:288`) carrying both a token (`SECRET_TOKEN` `hooks/tezgah_gate.py:271-274` — an
`Authorization: Bearer` header, or a `name=value` assignment for `api_key`/`token`/`secret`/`password`/...) and a sink (`SECRET_SINK` `hooks/tezgah_gate.py:279-281` — `>`/`>>`,
`| tee`, a curl `--trace`, or `git add`); `secret_command` `hooks/tezgah_gate.py:851-867`. Told: record the name, length or a fingerprint instead, and pass the value through the
tool's environment (`SECRET_DENY` `hooks/tezgah_gate.py:345-350`). Standing, no escape hatch.

### Loop — the identical attempt that already failed twice

Trigger: the same call (same `call_id`) failed `LOOP_ATTEMPTS = 2` times already in the current user turn (`hooks/tezgah_gate.py:453`, `loop_reason` `hooks/tezgah_gate.py:475-503`). Told: attempt N
of an identical call, the failure class read from the ledger, "change the approach or stop" (`hooks/tezgah_gate.py:495-503`). Standing while the ledger tail still shows those
failures. Under `verify-off` (`hooks/tezgah_gate.py:1339`).

### Retry — the session-wide ceiling

Trigger: the same call has been attempted more than `RETRY_CEILING = 3` times in the session, whatever those attempts returned (`hooks/tezgah_gate.py:472`, `retry_reason`
`hooks/tezgah_gate.py:506-529`). Told: an unchanged repeat is not a retry (`hooks/tezgah_gate.py:524-529`). Standing. Under `verify-off` (`hooks/tezgah_gate.py:1339`). Both guards read only the ledger tail.

### Nudge — the first identifier-shaped search of a session

Trigger: a `Grep` whose pattern, or a `grep`/`rg` argument (`BASH_SEARCH` `hooks/tezgah_gate.py:115`), matches `IDENT` (`^[A-Za-z_][A-Za-z0-9_]{2,}$`, `hooks/tezgah_gate.py:112`), in a repo whose
codebase-memory db exists (`searched_identifier` `hooks/tezgah_gate.py:388-400`, `index_slug` `hooks/tezgah_gate.py:403-412`). Told: the index slug and the graph tools (`nudge_reason` `hooks/tezgah_gate.py:432-437`).
Once-only: the mark in `cache_dir()/nudged/<session>` is written *before* the refusal, so re-issuing the search passes (`first_nudge` `hooks/tezgah_gate.py:415-429`).

### Drift — a long turn loses the rules it started with

Trigger: 25 work rows (`DRIFT_STEPS` `hooks/tezgah_gate.py:1095`) in the current user turn and an effectful call — a write tool, or a git/gh artifact command (`effectful`
`hooks/tezgah_gate.py:1170-1178`). Told: the standing constraints re-stated, or the delta since the turn began; "re-issue this call unchanged" (`DRIFT_DENY` `hooks/tezgah_gate.py:1100-1104`,
`drift_reason` `hooks/tezgah_gate.py:1143-1167`). Once per turn: the `drift` mark is written before the refusal. Governed by `reminder-off`, not `verify-off` (`hooks/tezgah_gate.py:1357`).

## The consent path

The gate cannot ask a question mid-call, so the refusal *is* the ask: it records `consent` (the class as `detail`, the action's digest as `id`, the workspace)
and returns the reason that names the digest (`hooks/tezgah_gate.py:1316-1325`). It never writes a `grant` - `consent_mark` reads by kind, id and the workspace
the ask was made in, and treats only the CLI's row as an answer (`hooks/tezgah_gate.py:585-611`) - so a re-issued command meets the refusal again, marked
"the ask is on record already".

The user answers with `bin/tezgah-consent <digest>` or `--last` (the newest ask no grant answers — `open_ask` `bin/tezgah-consent:42-51`, dispatch `:90-96`).
The row written is `{"kind": "grant", "detail": "cli", "id": <digest>}` at `bin/tezgah-consent:109`, into the same session ledger the gate reads:
`cache_dir()/evidence/<slug>.jsonl` (`hooks/tezgah_integrity.py:230-231`). The session is named by `TEZGAH_SESSION` where the host sets it, else every ledger
is searched newest-first (`bin/tezgah-consent:62-66`).

The window: both the ask and the grant are read from the last `CONSENT_TAIL = 200` rows (`hooks/tezgah_gate.py:535`). The ask row also records the scope the
action is judged in - the directory the call runs in, which is what the effect is resolved against, so the identical command in another directory is another
action and is asked about on its own. The grant is a one-shot lease, not a standing permit: `unspent_grant` counts it spent as soon as an outcome row with
the same id follows it, the outcome being the kind a PostToolUse hook writes after a call ran (`STEP_KINDS`: `run`, `edit`, `verify`, `verify_ok`,
`verify_fail`) rather than an `exit` key - cursor's `afterShellExecution` carries no outcome signal and records `run`/`verify` with no key at all - so the
next identical command is asked about again (`hooks/tezgah_gate.py:538-582`). The digest itself stays cwd-blind: it is the loop guard's key too, and one
identity per session is what makes `loop` and `retry` count attempts instead of places (`hooks/tezgah_integrity.py:190`).

## What the gate deliberately does not catch

Read this before filing a security-ish issue; each is a decision, not an oversight.

- A hand-written migration — `psql -c "ALTER TABLE ..."`. "reading SQL intent is not a regex" (`hooks/tezgah_gate.py:188-189`).
- A raw SQL `UPDATE` through `psql -c`: the statement sits in a quoted string that `mask()` blanks (`hooks/tezgah_gate.py:243-245`, `hooks/tezgah_integrity.py:730-733`).
- A shell write outside the root (`echo x > ../y`): "the class table is the shell's sink list" (`hooks/tezgah_gate.py:781-783`).
- An effect whose target was not named in the user's prompt — the taxonomy's own version. A PreToolUse payload carries the call, never the prompt text, and
  the prompt path stores only `sha1(prompt)[:12]` (`hooks/tezgah_gate.py:762-764`).
- A write inside the root after a fetch: left to the taint notice that `hooks/tezgah_untrusted.py` rides the first effect with, because it is recoverable from
  the snapshot (`hooks/tezgah_gate.py:777-779`).
- `grep -A 3 foo`: a flag with its own value shifts the token, so the search passes unnudged (`hooks/tezgah_gate.py:113-114`).
- A path behind a `cd` in the same line resolves against `cwd`, not the `cd`: "it fails open, never closed" (`hooks/tezgah_gate.py:627-628`).
- A foreign `apply_patch` write: the PostToolUse writer records no path for that row (`hooks/tezgah_gate.py:925-926`); and a second session that spells the path differently
  escapes the rule, because the ledger keeps no `cwd` (`hooks/tezgah_gate.py:899-901`).
- `nc --version`: connection tools are matched by shape, so it is refused once like any other connection tool - "the direction is the safe one and the refusal
  is one-shot" (`hooks/tezgah_gate.py:229-241`). `rsync` is the one that reads its destination, and what that leaves is a remote destination the pattern
  cannot see as the last argument (behind an alias, a wrapper script or a shell variable) and a `rsync://` argument, which `mask()` blanks like any other
  comment tail (`hooks/tezgah_gate.py:236-242`).
- Which rule the user meant when a turn drifts: "a guess about intent wearing a check's clothes" (`hooks/tezgah_gate.py:1149-1150`).
- A skip already in the file, or one inside a string (a test *about* the rule), is not a disable (`hooks/tezgah_integrity.py:780-787`).

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
no file in this checkout calls such a model.

## The mirror: the opencode plugin

opencode cannot run Python hooks, so `hosts/opencode/plugins/tezgah.js` is an independent JavaScript re-implementation of the same rules, dispatched from
`tool.execute.before` (hosts/opencode/plugins/tezgah.js:1407, exported `hosts/opencode/plugins/tezgah.js:1355`) in the gate's own order (`hosts/opencode/plugins/tezgah.js:1421-1466`); its shortcut constants restate the same regexes (`NEUTER` `hosts/opencode/plugins/tezgah.js:275`,
`SKIP_ENV` hosts/opencode/plugins/tezgah.js:276, `NO_VERIFY` `hosts/opencode/plugins/tezgah.js:277`, `GITISH` `hosts/opencode/plugins/tezgah.js:278`, `SKIP_TEST` `hosts/opencode/plugins/tezgah.js:279`). What keeps the two halves honest is a test, not a shared module:
`tests/test_opencode_plugin.py` drives the plugin's hooks through a node harness with a throwaway HOME, and imports the Python `tezgah_integrity.call_id` so a
separator or canonical-form drift in the action id fails there instead of silently in a session (`tests/test_opencode_plugin.py:1-7`, `:21-24`, `tests/test_opencode_plugin.py:876-914`).

The two halves agree on the consent rule. A repeat of an irreversible or
outward-facing command the user has not approved is refused again, carrying the ask-stands note rather than a second question
(`hosts/opencode/plugins/tezgah.js:863-874`, `hooks/tezgah_gate.py:1316-1325`); a grant is a lease on one effect in one workspace, spent by
the outcome row that follows it, so the next identical command is asked about again instead of passing on the first approval
(`unspent_grant` `hooks/tezgah_gate.py:538-582`, `consentMark` `hosts/opencode/plugins/tezgah.js:781-795` - each half records the same scope,
`os.path.realpath(cwd)` against `realpathSync(dir)`, so a row one writes is one the other honours); and the refusal
names the action's digest and the CLI that answers it (`consent_reason` `hooks/tezgah_gate.py:735-749`, `ASK_STANDS_NOTE`
`hooks/tezgah_gate.py:334-336`). Each half's repeat path is pinned in its own suite (`tests/test_opencode_plugin.py:395-410`, `tests/test_opencode_plugin.py:412-424`;
`tests/test_gate.py:555-583`).

## Adding a rule

1. Write the check inside `decision` (`hooks/tezgah_gate.py:1198-1373`). A rule is a function returning a `str` reason or `None`; keep an argument-shaped rule
   above the repeat guards (`hooks/tezgah_gate.py:1339-1345`) and the drift notice last (`hooks/tezgah_gate.py:1352-1360`), and put its constants beside its own section.
2. Return through `_deny(session_id, "<rule>", reason, tool, inp, base)` so the ledger counts the refusal (`hooks/tezgah_gate.py:1181-1195`); gate it on the kill switch it belongs
   to (`off(...)`), the way the shortcut and repeat rules use `verify-off` (`hooks/tezgah_gate.py:1216`, `hooks/tezgah_gate.py:1339`).
3. Extend `tests/test_gate.py`. It drives the real function through `tests/_probe_gate.py` (`tests/support.py:20`), which also carries the `capture_log` stub
   standing in for `tezgah_gate.capture` on the allow path (`tests/_probe_gate.py:20-30`). Only if the refusal envelope changes, touch
   `tests/test_claude_adapters.py:42-51` and the codex/cursor/omp hook tests.
4. Mirror the rule in `hosts/opencode/plugins/tezgah.js` and extend `tests/test_opencode_plugin.py` with its cases; that suite is where the two halves are
   compared and where a shared-vocabulary drift fails.

## Source of truth

- `hooks/tezgah_gate.py` — `decision` `hooks/tezgah_gate.py:1198-1373`; every rule constant and refusal text `hooks/tezgah_gate.py:111-362`; `attribution`/`attribution_edit` `hooks/tezgah_gate.py:365-380`; `explored`
  `hooks/tezgah_gate.py:383`; `searched_identifier` `hooks/tezgah_gate.py:388`, `index_slug` `hooks/tezgah_gate.py:403`, `first_nudge` `hooks/tezgah_gate.py:415`, `nudge_reason` `hooks/tezgah_gate.py:432`; `LOOP_ATTEMPTS` `hooks/tezgah_gate.py:453`, `loop_reason` `hooks/tezgah_gate.py:475`,
  `RETRY_CEILING` `hooks/tezgah_gate.py:472`, `retry_reason` `hooks/tezgah_gate.py:506`; `unspent_grant` `hooks/tezgah_gate.py:538`, `consent_mark` `hooks/tezgah_gate.py:585`, `rm_outside` `hooks/tezgah_gate.py:614`, `effect_class` `hooks/tezgah_gate.py:659`, `declared_effect`
  `hooks/tezgah_gate.py:705`, `consent_effect` `hooks/tezgah_gate.py:713`, `consent_reason` `hooks/tezgah_gate.py:735`, `outside_paths` `hooks/tezgah_gate.py:798`, `sink_check` `hooks/tezgah_gate.py:817`, `secret_command` `hooks/tezgah_gate.py:851`, `race_reason` `hooks/tezgah_gate.py:919`,
  `drift_reason` `hooks/tezgah_gate.py:1143`, `effectful` `hooks/tezgah_gate.py:1170`, `_deny` `hooks/tezgah_gate.py:1181`; the `capture` call `hooks/tezgah_gate.py:1368-1370`
- `hooks/projects-pretooluse.py` — the Claude and dsh envelope; `hooks/tezgah_paths.py` — `off`, `root_for`, `cache_dir`
- `hooks/tezgah_integrity.py` — `BASH_TOOLS`/`WRITE_TOOLS` `:110-114`; `NEUTER`/`SKIP_ENV`/`NO_VERIFY`/`GITISH` `:56-63`; `SKIP_TEST` `:65-70`; `TEST_PATH`
  `:75-78`; `call_id` `:190`; `_path` `:230`, `note` `:364`, `events` `:452`, `writers_elsewhere` `:514`, `mask` `:730`, `shortcut_command` `:736`,
  `shortcut_edit` `:780`
- `bin/tezgah-consent` — the user's half of the consent rule; `hosts/opencode/plugins/tezgah.js` — the JavaScript mirror
- `tests/test_gate.py`, `tests/_probe_gate.py`, `tests/test_opencode_plugin.py`, `tests/test_claude_adapters.py`
