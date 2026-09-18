# The gate: every refusal, and what lifts it

This page answers one question: why a tool call was refused before it ran. It is written for the maintainer adding a rule or reading a "the gate missed this"
report, and for the session that has just met a refusal in its transcript. [architecture.md](architecture.md) places the gate among the layers;
[evidence.md](evidence.md) describes the [ledger](glossary.md#ledger) a refusal writes to; [hosts.md](hosts.md) covers the per-host envelopes.

## Where it sits in the call path

One function decides every refusal: `decision(tool, inp, cwd, session_id)` returns a reason string or `None`, and nothing else
(`hooks/tezgah_gate.py:1150-1312`). It answers only inside a tezgah [root](glossary.md#root): outside one `root_for` returns nothing and every call passes
(`hooks/tezgah_gate.py:1154-1156`). The `pretooluse-off` kill switch drops the whole gate (`hooks/tezgah_gate.py:1152-1153`).

Each host's pre-tool hook calls it and wraps the string in that host's own deny envelope — opencode's is its `tool.execute.before`, which throws
`new Error(deny)`; a `None` prints no envelope at all.

| Host | Adapter | Refusal envelope |
|---|---|---|
| claude, dsh | `hooks/projects-pretooluse.py:24-30` (`hosts/dsh/hooks.json:13`) | `hookSpecificOutput.permissionDecision: "deny"` |
| codex, cursor, omp | `hosts/codex/hook.py:118-125`, `hosts/cursor/hook.py:279-281`, `hosts/omp/hook.py:117-120` | that host's own envelope — [hosts.md](hosts.md) |
| opencode | `hosts/opencode/plugins/tezgah.js:1372` | `new Error(deny)` thrown at `hosts/opencode/plugins/tezgah.js:1453` |

Every refusal is also recorded before it is returned: `_deny` appends a ledger row `deny` whose `detail` is `"<rule>: <reason, first 80 chars>"`, plus any
`extra` (`hooks/tezgah_gate.py:1133-1147`). That row, not the reason wording, is where "why was this denied" is answered, and `<rule>` is the name used below.

## The rules, in the order `decision` checks them

Bare `:NNN` references on this page are `hooks/tezgah_gate.py` unless another file is named. Each rule ends with its reach: *once*, a mark lifts the next
identical call; *standing*, only changing the call does.

### Explorer — the grep-only subagent

Trigger: tool `agent`/`task`/`subagent` whose `subagent_type` is `explore` or `explorer`, case-insensitively (`hooks/tezgah_gate.py:1158-1159`, `explored` `hooks/tezgah_gate.py:360-362`). Told: use
the general-purpose agent and name `search_graph`, `trace_path`, `search_code` in its prompt (`EXPLORE_DENY` `hooks/tezgah_gate.py:329-333`). Standing: no mark, every such
request is refused.

### Shortcut — a check made unable to fail, or a test disabled

Trigger, shell: `--no-verify`, or `SKIP=`/`HUSKY_SKIP_HOOKS=`/`HUSKY=0`, next to a git/hook word; or a verification command chained with `|| true`/`; true`
(`hooks/tezgah_integrity.py:709-726`, `NO_VERIFY` `:62`, `SKIP_ENV` `:61`, `NEUTER` `:56-57`, `GITISH` `:63`). Trigger, edit/write: a skip marker newly
introduced into a test file — the path must match `tests?/`, `test_*`, `*_test`, `*.test.*` (`TEST_PATH` `:75-78`), the marker must survive `mask()` so one
inside a string or comment does not count, and `_added` compares against the file's own text on disk for a `Write` (`:753-787`, `SKIP_TEST` `:65-70`). Told:
the texts at `:716-726` and `:783-786` — run the checks, or say the test is failing; ask the user first if the skip is intended. Standing, with one switch:
`verify-off` removes this check (`hooks/tezgah_gate.py:1168-1176`).

### Attribution — an AI/model credit on its way into an artifact

Trigger, shell: a write command (`WRITE_CMD` `hooks/tezgah_gate.py:141-147` — `git commit|merge|tag|notes`, `gh api`,
`gh pr|issue|release create|edit|comment|review|merge|close`) carrying a credit form (`ATTRIB` `hooks/tezgah_gate.py:119-121` — `co-authored-by:`, `generated with`, `made with`,
`built by`, `assisted by`, `authored by`, `noreply@anthropic`, a robot emoji). Trigger, edit/write: one of the content fields `EDIT_TEXT` (`hooks/tezgah_gate.py:136-137`)
containing a line that *starts* with a credit (`ATTRIB_LINE` `hooks/tezgah_gate.py:132-134`). Told: remove it and re-run; naming a tool in order to use it is fine, crediting it
as author is not (`ATTRIB_DENY` `hooks/tezgah_gate.py:335-339`). Standing. The line anchor is why prose that merely names the banned forms passes (`hooks/tezgah_gate.py:122-131`).

### Race — another session wrote this file minutes ago

Trigger: a write tool whose path, or `apply_patch` header, another session recorded a write of inside `RACE_WINDOW_MIN = 10` minutes (`hooks/tezgah_gate.py:838`, `race_reason`
`hooks/tezgah_gate.py:871-888`, reader `writers_elsewhere` `hooks/tezgah_integrity.py:514`). Told: re-read the file and re-apply the change to what is on disk now (`RACE_DENY`
`hooks/tezgah_gate.py:843-852`). Standing (`RACE_REFUSE = True` `hooks/tezgah_gate.py:842`) — a notice would not close a silent overwrite — and it lifts only by time.

### Untrusted sink — an effect in a turn that read what tezgah cannot vouch for

Trigger: this user turn has a read row carrying a `source` (web, mcp, network), and the call is an effect — a *tool* write whose realpath leaves the rule's
root (`outside_paths` `hooks/tezgah_gate.py:753-769`) or a shell command of any effect class (`hooks/tezgah_gate.py:1245-1247`; a shell redirect out of the root is not this rule's, see below). Told: put
it in front of the user; content is not the user, so an approval given before the read does not cover it (`UNTRUSTED_DENY` `hooks/tezgah_gate.py:739-748`). Lifts only on an
unspent user `grant` newer than the read (`sink_check` `hooks/tezgah_gate.py:772-800`). The refusal leaves the same `consent` ask row the rule below uses, labelled
`outside-workspace` when the realpath is what makes the call a sink (`SINK_WRITE` `hooks/tezgah_gate.py:750`, `hooks/tezgah_gate.py:1223`), so `bin/tezgah-consent` answers it identically. A write
*inside* the root is not this rule's sink.

### Consent — an irreversible or outward-facing command

Trigger: `effect_class` returns one of six classes for the command's masked text (`hooks/tezgah_gate.py:614-657`, first match wins, in the order below).

| Class | Matched by |
|---|---|
| `destructive` | a `git push` carrying `-f`/`--force*` whose segment is not scratch (`:613-616`, `GIT_PUSH` `hooks/tezgah_gate.py:180-181`, `FORCE_FLAG` `hooks/tezgah_gate.py:182-183`, `SCRATCH` `hooks/tezgah_gate.py:157-158`); `git branch -D`/`--delete`, `git push --delete`/`-d` (`BRANCH_DELETE` `hooks/tezgah_gate.py:161-165`); a recursive force `rm` outside the run directory (`rm_outside` `hooks/tezgah_gate.py:569-611`, `RM` `hooks/tezgah_gate.py:170`, `RM_RECURSIVE` `hooks/tezgah_gate.py:171`, `RM_FORCE` `hooks/tezgah_gate.py:172`) |
| `schema` | a migration runner (`MIGRATION` `hooks/tezgah_gate.py:184-192`) |
| `deploy` | a deploy runner (`DEPLOY` `hooks/tezgah_gate.py:194-203`) |
| `publish` | a registry/release/image push (`PUBLISH` `hooks/tezgah_gate.py:205-210`) |
| `outward` | a `git push` to `heroku`/`production`/`prod` (`OUTWARD` `hooks/tezgah_gate.py:212-214`) |
| `send` | mail, a payment API, `nc`/`ncat`/`scp`/`rsync`, or a `curl`/`gh api` with a write method or a body (`SEND` `hooks/tezgah_gate.py:226-240`) |

Told: the class and what it means, the action's digest, and `bin/tezgah-consent <digest>` (`CONSENT_DENY` `hooks/tezgah_gate.py:297-309`, `consent_reason` `hooks/tezgah_gate.py:690-704`) — never the
pattern that matched. Standing until the user's own `grant`; a re-issue adds nothing (`ASK_STANDS_NOTE` `hooks/tezgah_gate.py:311-313`). A command may declare
`tezgah:effect=<class>` (`DECLARED_EFFECT` `hooks/tezgah_gate.py:295`) for an effect no pattern sees; a declaration can only raise the class along `EFFECT_RANK` (`hooks/tezgah_gate.py:288`), and a
lowering one is named in the refusal (`consent_effect` `hooks/tezgah_gate.py:668-687`, `DOWNGRADE_NOTE` `hooks/tezgah_gate.py:318-320`). A `rm -rf` whose every target is under a temp root is scratch
and asks nobody (`SCRATCH_ROOTS` `hooks/tezgah_gate.py:180-181`, `scratch_ok=True` at `hooks/tezgah_gate.py:1247`; the sink half still counts it, `hooks/tezgah_gate.py:1245-1246`).

### Migration — the `schema` class of the rule above

Trigger: `alembic`/`flyway`/`goose`/`dbmate`/`sqitch` plus an upgrade/down/rollback word, `knex|prisma|sequelize|typeorm ...migrat...`, `manage.py migrate`,
`rails db:migrate|rollback|reset|schema:load` (`MIGRATION` `hooks/tezgah_gate.py:184-192`, matched at `hooks/tezgah_gate.py:647`). Told: the `schema` clause and the consent path.
Standing until the user's grant.

### Secret — a credential on its way into a file

Trigger: one simple command (split on `&&`, `||`, `;`, newline — `SEGMENT` `hooks/tezgah_gate.py:265`) carrying both a token (`SECRET_TOKEN` `hooks/tezgah_gate.py:248-251` — an
`Authorization: Bearer` header, or a `name=value` assignment for `api_key`/`token`/`secret`/`password`/...) and a sink (`SECRET_SINK` `hooks/tezgah_gate.py:256-258` — `>`/`>>`,
`| tee`, a curl `--trace`, or `git add`); `secret_command` `hooks/tezgah_gate.py:803-819`. Told: record the name, length or a fingerprint instead, and pass the value through the
tool's environment (`SECRET_DENY` `hooks/tezgah_gate.py:322-327`). Standing, no escape hatch.

### Loop — the identical attempt that already failed twice

Trigger: the same call (same `call_id`) failed `LOOP_ATTEMPTS = 2` times already in the current user turn (`hooks/tezgah_gate.py:430`, `loop_reason` `hooks/tezgah_gate.py:452-481`). Told: attempt N
of an identical call, the failure class read from the ledger, "change the approach or stop" (`hooks/tezgah_gate.py:472-481`). Standing while the ledger tail still shows those
failures. Under `verify-off` (`hooks/tezgah_gate.py:1278`).

### Retry — the session-wide ceiling

Trigger: the same call has been attempted more than `RETRY_CEILING = 3` times in the session, whatever those attempts returned (`hooks/tezgah_gate.py:449`, `retry_reason`
`hooks/tezgah_gate.py:483-505`). Told: an unchanged repeat is not a retry (`hooks/tezgah_gate.py:501-506`). Standing. Under `verify-off` (`hooks/tezgah_gate.py:1278`). Both guards read only the ledger tail.

### Nudge — the first identifier-shaped search of a session

Trigger: a `Grep` whose pattern, or a `grep`/`rg` argument (`BASH_SEARCH` `hooks/tezgah_gate.py:115`), matches `IDENT` (`^[A-Za-z_][A-Za-z0-9_]{2,}$`, `hooks/tezgah_gate.py:112`), in a repo whose
codebase-memory db exists (`searched_identifier` `hooks/tezgah_gate.py:392-377`, `index_slug` `hooks/tezgah_gate.py:380-389`). Told: the index slug and the graph tools (`nudge_reason` `hooks/tezgah_gate.py:409-414`).
Once-only: the mark in `cache_dir()/nudged/<session>` is written *before* the refusal, so re-issuing the search passes (`first_nudge` `hooks/tezgah_gate.py:392-407`).

### Drift — a long turn loses the rules it started with

Trigger: 25 work rows (`DRIFT_STEPS` `hooks/tezgah_gate.py:1047`) in the current user turn and an effectful call — a write tool, or a git/gh artifact command (`effectful`
`hooks/tezgah_gate.py:1122-1130`). Told: the standing constraints re-stated, or the delta since the turn began; "re-issue this call unchanged" (`DRIFT_DENY` `hooks/tezgah_gate.py:1052-1057`,
`drift_reason` `hooks/tezgah_gate.py:1095-1119`). Once per turn: the `drift` mark is written before the refusal. Governed by `reminder-off`, not `verify-off` (`hooks/tezgah_gate.py:1296`).

## The consent path

The gate cannot ask a question mid-call, so the refusal *is* the ask: it records `consent` (the class as `detail`, the action's digest as `id`, the workspace)
and returns the reason that names the digest (`hooks/tezgah_gate.py:1256-1264`). It never writes a `grant` — `consent_mark` reads by kind and id and treats
only the CLI's row as an answer (`hooks/tezgah_gate.py:544-566`) — so a re-issued command meets the refusal again, marked "the ask is on record already".

The user answers with `bin/tezgah-consent <digest>` or `--last` (the newest ask no grant answers — `open_ask` `bin/tezgah-consent:42-51`, dispatch `:90-96`).
The row written is `{"kind": "grant", "detail": "cli", "id": <digest>}` at `bin/tezgah-consent:109`, into the same session ledger the gate reads:
`cache_dir()/evidence/<slug>.jsonl` (`hooks/tezgah_integrity.py:230-231`). The session is named by `TEZGAH_SESSION` where the host sets it, else every ledger
is searched newest-first (`bin/tezgah-consent:62-66`).

The window: both the ask and the grant are read from the last `CONSENT_TAIL = 200` rows (`hooks/tezgah_gate.py:512`). The grant is a one-shot lease, not a
standing permit: `unspent_grant` counts it spent as soon as an outcome row (`exit`) with the same id follows it, so the next identical command is asked about
again (`hooks/tezgah_gate.py:515-541`).

## What the gate deliberately does not catch

Read this before filing a security-ish issue; each is a decision, not an oversight.

- A hand-written migration — `psql -c "ALTER TABLE ..."`. "reading SQL intent is not a regex" (`hooks/tezgah_gate.py:182-183`).
- A raw SQL `UPDATE` through `psql -c`: the statement sits in a quoted string that `mask()` blanks (`hooks/tezgah_gate.py:222-225`, `hooks/tezgah_integrity.py:703-706`).
- A shell write outside the root (`echo x > ../y`): "the class table is the shell's sink list" (`hooks/tezgah_gate.py:736-738`).
- An effect whose target was not named in the user's prompt — the taxonomy's own version. A PreToolUse payload carries the call, never the prompt text, and
  the prompt path stores only `sha1(prompt)[:12]` (`hooks/tezgah_gate.py:717-721`).
- A write inside the root after a fetch: left to the taint notice that `hooks/tezgah_untrusted.py` rides the first effect with, because it is recoverable from
  the snapshot (`hooks/tezgah_gate.py:732-738`).
- `grep -A 3 foo`: a flag with its own value shifts the token, so the search passes unnudged (`hooks/tezgah_gate.py:113-114`).
- A path behind a `cd` in the same line resolves against `cwd`, not the `cd`: "it fails open, never closed" (`hooks/tezgah_gate.py:582-583`).
- A foreign `apply_patch` write: the PostToolUse writer records no path for that row (`hooks/tezgah_gate.py:877-880`); and a second session that spells the path differently
  escapes the rule, because the ledger keeps no `cwd` (`hooks/tezgah_gate.py:1122-854`).
- `nc --version`: connection tools are matched by shape, so it is refused once like any other connection tool — "the direction is the safe one and the refusal
  is one-shot" (`hooks/tezgah_gate.py:220-222`).
- Which rule the user meant when a turn drifts: "a guess about intent wearing a check's clothes" (`hooks/tezgah_gate.py:1101-1104`).
- A skip already in the file, or one inside a string (a test *about* the rule), is not a disable (`hooks/tezgah_integrity.py:753-760`).

## The mirror: the opencode plugin

opencode cannot run Python hooks, so `hosts/opencode/plugins/tezgah.js` is an independent JavaScript re-implementation of the same rules, dispatched from
`tool.execute.before` (hosts/opencode/plugins/tezgah.js:1372, exported `hosts/opencode/plugins/tezgah.js:1320`) in the gate's own order (`hosts/opencode/plugins/tezgah.js:1386-1431`); its shortcut constants restate the same regexes (`NEUTER` `hosts/opencode/plugins/tezgah.js:274`,
`SKIP_ENV` hosts/opencode/plugins/tezgah.js:275, `NO_VERIFY` `hosts/opencode/plugins/tezgah.js:276`, `GITISH` `hosts/opencode/plugins/tezgah.js:277`, `SKIP_TEST` `hosts/opencode/plugins/tezgah.js:278`). What keeps the two halves honest is a test, not a shared module:
`tests/test_opencode_plugin.py` drives the plugin's hooks through a node harness with a throwaway HOME, and imports the Python `tezgah_integrity.call_id` so a
separator or canonical-form drift in the action id fails there instead of silently in a session (`tests/test_opencode_plugin.py:1-7`, `:21-24`, `tests/test_opencode_plugin.py:807-845`).

The two halves agree on the consent rule. A repeat of an irreversible or
outward-facing command the user has not approved is refused again, carrying the ask-stands note rather than a second question
(`hosts/opencode/plugins/tezgah.js:828-838`, `hooks/tezgah_gate.py:1256-1264`); a grant is a lease on one effect, spent by
the outcome row that follows it, so the next identical command is asked about again instead of passing on the first approval
(`unspent_grant` `hooks/tezgah_gate.py:515-541`, `consentMark` `hosts/opencode/plugins/tezgah.js:767-778`); and the refusal
names the action's digest and the CLI that answers it (`consent_reason` `hooks/tezgah_gate.py:690-680`, `ASK_STANDS_NOTE`
`hooks/tezgah_gate.py:311-313`). Each half's repeat path is pinned in its own suite (`tests/test_opencode_plugin.py:328-343`, `tests/test_opencode_plugin.py:378-393`;
`tests/test_gate.py:539-586`).

## Adding a rule

1. Write the check inside `decision` (`hooks/tezgah_gate.py:1150-1312`). A rule is a function returning a `str` reason or `None`; keep an argument-shaped rule
   above the repeat guards (`hooks/tezgah_gate.py:1271-1277`) and the drift notice last (`hooks/tezgah_gate.py:1291-1295`), and put its constants beside its own section.
2. Return through `_deny(session_id, "<rule>", reason, tool, inp, base)` so the ledger counts the refusal (`hooks/tezgah_gate.py:1133-1147`); gate it on the kill switch it belongs
   to (`off(...)`), the way the shortcut and repeat rules use `verify-off` (`hooks/tezgah_gate.py:1168`, `hooks/tezgah_gate.py:1278`).
3. Extend `tests/test_gate.py`. It drives the real function through `tests/_probe_gate.py` (`tests/support.py:20`), which also carries the `capture_log` stub
   standing in for `tezgah_gate.capture` on the allow path (`tests/_probe_gate.py:20-30`). Only if the refusal envelope changes, touch
   `tests/test_claude_adapters.py:42-51` and the codex/cursor/omp hook tests.
4. Mirror the rule in `hosts/opencode/plugins/tezgah.js` and extend `tests/test_opencode_plugin.py` with its cases; that suite is where the two halves are
   compared and where a shared-vocabulary drift fails.

## Source of truth

- `hooks/tezgah_gate.py` — `decision` `hooks/tezgah_gate.py:1150-1312`; every rule constant and refusal text `hooks/tezgah_gate.py:111-339`; `attribution`/`attribution_edit` `hooks/tezgah_gate.py:342-357`; `explored`
  `hooks/tezgah_gate.py:360`; `searched_identifier` `hooks/tezgah_gate.py:392`, `index_slug` `hooks/tezgah_gate.py:380`, `first_nudge` `hooks/tezgah_gate.py:392`, `nudge_reason` `hooks/tezgah_gate.py:409`; `LOOP_ATTEMPTS` `hooks/tezgah_gate.py:430`, `loop_reason` `hooks/tezgah_gate.py:452`,
  `RETRY_CEILING` `hooks/tezgah_gate.py:449`, `retry_reason` `hooks/tezgah_gate.py:483`; `unspent_grant` `hooks/tezgah_gate.py:515`, `consent_mark` `hooks/tezgah_gate.py:544`, `rm_outside` `hooks/tezgah_gate.py:569`, `effect_class` `hooks/tezgah_gate.py:614`, `declared_effect`
  `hooks/tezgah_gate.py:660`, `consent_effect` `hooks/tezgah_gate.py:668`, `consent_reason` `hooks/tezgah_gate.py:690`, `outside_paths` `hooks/tezgah_gate.py:753`, `sink_check` `hooks/tezgah_gate.py:772`, `secret_command` `hooks/tezgah_gate.py:803`, `race_reason` `hooks/tezgah_gate.py:871`,
  `drift_reason` `hooks/tezgah_gate.py:1095`, `effectful` `hooks/tezgah_gate.py:1122`, `_deny` `hooks/tezgah_gate.py:1133`; the `capture` call `:1110-1113`
- `hooks/projects-pretooluse.py` — the Claude and dsh envelope; `hooks/tezgah_paths.py` — `off`, `root_for`, `cache_dir`
- `hooks/tezgah_integrity.py` — `BASH_TOOLS`/`WRITE_TOOLS` `:110-114`; `NEUTER`/`SKIP_ENV`/`NO_VERIFY`/`GITISH` `:56-63`; `SKIP_TEST` `:65-70`; `TEST_PATH`
  `:75-78`; `call_id` `:190`; `_path` `:230`, `note` `:364`, `events` `:452`, `writers_elsewhere` `:514`, `mask` `:703`, `shortcut_command` `:709`,
  `shortcut_edit` `:753`
- `bin/tezgah-consent` — the user's half of the consent rule; `hosts/opencode/plugins/tezgah.js` — the JavaScript mirror
- `tests/test_gate.py`, `tests/_probe_gate.py`, `tests/test_opencode_plugin.py`, `tests/test_claude_adapters.py`
