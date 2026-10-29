# The gate: every refusal, and what lifts it

This page answers one question: why a tool call was refused before it ran. It is written for the maintainer adding a rule or reading a "the gate missed this"
report, and for the session that has just met a refusal in its transcript. [architecture.md](architecture.md) places the gate among the layers;
[evidence.md](evidence.md) describes the [ledger](glossary.md#ledger) a refusal writes to; [hosts.md](hosts.md) covers the per-host envelopes.

## Where it sits in the call path

One function decides every refusal: `decision(tool, inp, cwd, session_id)` returns a reason string or `None`, and nothing else
(`hooks/tezgah_gate.py::decision`). It answers only inside a tezgah [root](glossary.md#root): outside one `root_for` returns nothing and every call passes
(`hooks/tezgah_gate.py::decision`). A repository that commits `tezgah.owner` with `harness: excluded` is out of every root the same way. One that
says `tasks: off` keeps the root and turns off only the task rules. The record rule then holds no write to its own
plan files ([operations.md](operations.md#a-repository-that-is-not-this-harnesss)).
The `pretooluse-off` kill switch drops the whole gate (`hooks/tezgah_gate.py::decision`). `decision` binds the session first.
It reads every switch through the session latch ([contract.md](contract.md#how-a-rule-is-disarmed)).

Each host's pre-tool hook calls it and wraps the string in that host's own deny envelope — opencode's is its `tool.execute.before`, which throws
`new Error(deny)`; a `None` prints no envelope at all.

A host that is not Python reaches the same function through `bin/tezgah-gate`. Two of its verbs
answer one call (`decision(..., record=...)`). `decide` is the live gate: it records what `decision` records - the
deny, drift and nudge rows and the pre-write snapshot - and it is the verb opencode's plugin calls,
because the once-per-turn drift refusal depends on the recorded row. `check` is a true dry run: the
same answer with nothing written anywhere, and it is what a person and the MCP `tezgah_gate_check`
tool ask. Before 2026-10-02 `check` recorded too, so a dry run against a live session id wrote
refusal rows into that session's counters (audit L-14b, CHAT-07).

The third verb, `replay`, answers no call. It measures the gate. It replays the real ledgers
through the unmodified dry run in a sandbox HOME. Per stratum, it prints how often the replayed
verdict equals the recorded one. `replay --sheet` draws a blind label sample.
`replay --label-model` labels it with a model as rater 2, and `replay --report` reads the labels
into per-rule false-block rates. It changes no gate behaviour, and everything it
writes stays under `~/.cache/tezgah/replay`. The corpus, the exclusions and the metrics are in
[evidence.md](evidence.md#the-replay-corpus).

| Host | Adapter | Refusal envelope |
|---|---|---|
| claude, dsh | `hooks/projects-pretooluse.py::main` (`hosts/dsh/hooks.json:13-14`) | `hookSpecificOutput.permissionDecision: "deny"` |
| codex, cursor, omp | `hosts/codex/hook.py::main`, `hosts/cursor/hook.py::dispatch`, `hosts/omp/hook.py::handle` | that host's own envelope — [hosts.md](hosts.md) |
| opencode | `hosts/opencode/plugins/tezgah.js:2988` | `new Error(deny)` thrown at `hosts/opencode/plugins/tezgah.js:3152` |

Every refusal is also recorded before it is returned: `_deny` appends a ledger row `deny` whose `detail` is `"<rule>: <reason, first 80 chars>"`, plus any
`extra` (`hooks/tezgah_gate.py::_deny`). That row, not the reason wording, is where "why was this denied" is answered, and `<rule>` is the name used below.

A call the gate lets through is also where it keeps the pre-write bytes: `capture` runs for a write tool, and for a shell command that writes a file through a
redirect or `tee` - the same shape the task phase rule reads, `write_paths` returns the target for both routes, and a shell write gets its pre-state the same
way (`hooks/tezgah_gate.py::decision`, `hooks/tezgah_gate.py::write_paths`, `hooks/tezgah_gate.py::shell_target`). Without it the after-state alone
cannot tell a redirect that wrote the file from one that wrote what was already there, and the freshness half of the Stop rule would read every redirect as a
change; the two halves of that rule are `hooks/tezgah_integrity.py`'s and are described in [evidence.md](evidence.md).

## MCP — a server's effect tool

An MCP effect tool reaches `decision` on every host that can route it ([hosts.md](hosts.md)). No rule refuses it for what it is.
Its verb class only picks which existing content rules read its payload. An effect verb in the tool part of the name decides the class, case-sensitive
like the host matcher (`hooks/tezgah_integrity.py::mcp_class`, `hooks/tezgah_integrity.py::MCP_VERBS`). The tool part is what follows the last `__`.
A clause of it that a read verb leads (`get_commit`) is a read. An effect verb in another clause still decides (`get_or_create_issue`).
omp's `mcp__<server>_<tool>` has no server boundary, so there an effect verb anywhere decides.
A `write` call such as `write_file` meets the shortcut, attribution and secret rules.
A `publish` call such as `send_message` meets attribution and secret. An `act` call such as `click` meets none of them.
Every class counts as an effect for the drift re-statement (`hooks/tezgah_gate.py::effectful`) and the taint notice
(`hooks/tezgah_untrusted.py::effectful`). So an `act` call can now draw the drift re-statement, once per long turn.
The gate reads the payload through a bounded walk (`hooks/tezgah_integrity.py::mcp_text`).
An unbounded read of an unbounded payload runs past the 5 s hook budget, and a late hook refuses nothing (audit H-3).
On Claude, dsh and omp the host matcher names the effect verbs only, so a read-only MCP call spawns no hook.
A temp-HOME fixture measured the cost: 200 spawns per case, on a loaded machine.
The Claude hook took p95 135 ms on a 300-byte MCP write and 222 ms on a 1 MB one. A plain `Bash` call took 101 ms.

## The rules, in the order `decision` checks them

Code on this page is cited by symbol (`path::name`, see [the convention](README.md#how-these-pages-are-written)). Each rule ends with its reach: *once*, a mark lifts the next
identical call; *standing*, only changing the call does.
`bin/tezgah-docs --citations` checks the headings below against `decision`, read by AST (`rule_sites`). They keep the order
of each rule's first deny site. A rule's section names every `off(...)` switch that guards it.

### Control — tezgah's own control plane

Trigger: a write tool or a shell command that changes a file the other rules rest on (`control_reason` `hooks/tezgah_gate.py::control_reason`). `decision` checks
it first after the root check (`decision` `hooks/tezgah_gate.py::decision`). The protected set (`control_target` `hooks/tezgah_gate.py::control_target`):

| What | Paths | Refused for |
|---|---|---|
| kill switches and opt-in markers | every name in `SWITCHES` (`hooks/tezgah_paths.py::SWITCHES`) under `~/.config/tezgah` or `~/.claude` | any write |
| tezgah's configuration | all of `~/.config/tezgah` (`config.json`, `bin/`, `ponytail.level`, the `hook:<host>:...` rows of `contract.sha256`, ...) | any write |
| evidence and session state | the cache's `tezgah.db` (with its `-wal` and `-shm` files), `evidence/`, the `sessions/`, `switches/`, `gate-inactive/`, `harness-drift/` and `import-crash/` directories that database imports once, and `workspace-index.json`, in the global cache and the temp fallback (`hooks/tezgah_gate.py::CONTROL_CACHE`) | any write |
| hook wiring | the opencode plugin file, the omp hook, the Claude plugin copy, the install prefix, and the tree the hooks run from unless the session works inside it (`hooks/tezgah_gate.py::_registration`, `hooks/tezgah_gate.py::_install_trees`) | any write |
| shared registration files | `.claude/settings.json` and `settings.local.json`, `~/.claude/plugins/installed_plugins.json` and `known_marketplaces.json`, Codex's and Cursor's `hooks.json`, Codex's `config.toml`, Gemini's `settings.json`, Goose's `~/.config/goose/settings.json` | a shell write; a write tool only when it changes an entry that is tezgah's - `statusLine`, `attribution`, a key that turns hooks off (Claude's `disableAllHooks`, Gemini's `hooksConfig`; `hooks/tezgah_gate.py::OWNED_KEYS`), a key or item naming tezgah, such as `tezgah` in Goose's `disabledPlugins` (the user's own hook beside tezgah's in one matcher group stays theirs), or any `[hooks...]` line of `config.toml`, where the trust entries live (`hooks/tezgah_gate.py::_shared_change`) |
| repository marks and hooks | a `REPO_MARKS` name under a root, the session checkout's `.git/hooks` (a `.sample` file and a clone elsewhere pass), `git config core.hooksPath` set or unset there or `--global` | any write |
| | `.husky` | a delete, a chmod that takes a permission away, or a move |
| | a directory holding any protected path (`rm -rf ~/.cache`, `mv .git /tmp/x`), also through a link (`rm -rf link/`), including `.tezgah/plans/open/` itself, every ancestor of it (`rm -rf .tezgah`, `mv .tezgah/plans /tmp/x`) and a glob or brace directly under it (`rm -rf .tezgah/plans/open/*`) | a delete or move |
| evidence only | a delete or move of one named plan under `.tezgah/plans/open/`; a glob or the directory is refused (row above); `git add -f` or `--force` of a `.tezgah/` path (`_git_change` `hooks/tezgah_gate.py::_git_change`) | never: the call goes on to the other rules and, if they let it through, leaves a `disarm` row whose `detail` is `control: <what>` (`CONTROL_EVIDENCE` `hooks/tezgah_gate.py::CONTROL_EVIDENCE`); `git rm --cached` leaves none (plan-sync's move) |
| the CLIs | `tezgah-gate decide`, `tezgah-capture`, `tezgah-pony <level>`, `tezgah-adhd on` or `off`, `tezgah-context attest` or `user_prompt`, by basename with or without `.py` (`hooks/tezgah_gate.py::CONTROL_CLIS`) | always |
| the hook entries | `projects-auto-init`, `projects-pretooluse`, `projects-posttooluse`, `projects-stop`, `hook.py` under `hosts/codex`, `hosts/cursor` or `hosts/omp`, and the `tezgah-codex-hook`/`tezgah-cursor-hook` launchers (`hooks/tezgah_gate.py::HOOK_ENTRIES`, `hooks/tezgah_gate.py::_host_hook`): fed a forged payload, one writes genuine rows, the switch latch's `authorized` row among them | always |

The rule reads the shell word by word, one simple command at a time (`shell_control` `hooks/tezgah_gate.py::shell_control`). It reads each redirect target.
It reads the arguments of `touch`, `rm`, `rmdir`, `unlink`, `mv`, `chmod`, `mkdir`, `tee`, `truncate`, `sqlite3`, the copiers' destination and `sed -i`/`perl -i`.
It reads the value of `cp -t`, `curl -o`, `wget -O`, `tar -C` on extraction and `unzip -d` (`OPTION_TARGETS`). It expands `~`, `$HOME` and the XDG
variables first. It follows a `cd` within the line and reads past `if`/`then`/`do`/`!`/`{`. It opens `eval` and `bash -c`, and any flag cluster holding
`c` is `-c`. A path counts as written and with its last link resolved. A quoted word is a word, so a grep or a commit message that names a switch passes. `SHELL_WRITE` stays as it was: it feeds the
task phase rule and the opencode mirror. The task CLI is not a control-plane target: the session runs it itself (see the task rule below). Told: what the call would
change, and that the user changes it in their own terminal (`CONTROL_DENY` `hooks/tezgah_gate.py::CONTROL_DENY`). The text names no command. Standing. No switch
but `pretooluse-off` removes the rule, and that switch is a protected file. The rule cannot tell a change the user asked for from one the agent chose. It
refuses both inside the session, and it never sees the user's own terminal. Plan 050's replay of three weeks of real ledgers found the two evidence-only
targets refused without the user's say-so more than once a week. Its falsifier kept the tamper evidence and dropped the refusal for them. The rule still
refuses a call that also changes a refusing target.

### Explorer — the grep-only subagent

Trigger: tool `agent`/`task`/`subagent` whose `subagent_type` is `explore` or `explorer`, case-insensitively (`hooks/tezgah_gate.py::decision`, `hooks/tezgah_gate.py::explored`). Told: use
the general-purpose agent and name the codegraph tools in its prompt (`hooks/tezgah_gate.py::EXPLORE_DENY`). Standing: no mark, every such
request is refused.

### Shortcut — a check made unable to fail, or a test disabled

Trigger, shell: `--no-verify`, or `SKIP=`/`HUSKY_SKIP_HOOKS=`/`HUSKY=0`, next to a git/hook word; or a `core.hooksPath` assignment (`git -c core.hooksPath=...`, `git config core.hooksPath <dir>` with a quoted value too, `--config-env`, `GIT_CONFIG_KEY_n`/`GIT_CONFIG_PARAMETERS`) in the same command as a `git commit`/`git push` (`HOOKS_KEY`/`GIT_VALUE_OPTS`/`CONFIG_READS`/`ROUGH_WORDS` `hooks/tezgah_integrity.py::HOOKS_KEY`, `hooks/tezgah_integrity.py::GIT_VALUE_OPTS`, `hooks/tezgah_integrity.py::CONFIG_READS`, `hooks/tezgah_integrity.py::ROUGH_WORDS`, `hooks/tezgah_integrity.py::_shell_segments` reads the line word by word the way shlex does - an unquoted backtick ends a command (`hooks/tezgah_integrity.py::_unquoted_backticks`; one inside double quotes is read as data, the blind spot `mask` has) and a line shlex cannot read is read roughly rather than dropped - `hooks/tezgah_integrity.py::_hooks_redirect`; husky's standalone setup, a read or `--unset`, a hook install naming `pre-push`, and a commit message naming the key or the env var pass); or a verification command chained with `|| true`/`; true`
(`hooks/tezgah_integrity.py::_shortcut_command`, `hooks/tezgah_integrity.py::NO_VERIFY`, `hooks/tezgah_integrity.py::SKIP_ENV`, `hooks/tezgah_integrity.py::NEUTER`, `hooks/tezgah_integrity.py::GITISH`).
These shell predicates read the line through `mask()` (`hooks/tezgah_integrity.py::mask`), which blanks quotes and comments the way bash reads them. A URL's `//`, a word's `#`, a `/* */` glob pair and `'x\'` are words there, so they do not hide the command after them. The word reader takes a `$'...'` as one word and a `$( )` or backtick body as a command of its own (`hooks/tezgah_integrity.py::_for_shlex`). Every shell reader asks one rule for a comment and a line continuation (`hooks/tezgah_integrity.py::_opens_comment`, `hooks/tezgah_integrity.py::CONTINUATION`). A `#` opens a comment only at a word's start, so `x\ #`, `x\<newline>#` and `x\r#` hide nothing. A `)` that closes a substitution or an array is no word end either (`$(:)#`, `<(:)#`, `x=(a)#`, `hooks/tezgah_integrity.py::_kept`). A subshell's `(true)#` does open a comment. The readers drop a backslash-newline where bash drops it, so `-de\<newline>lete` reads as `-delete`. `mask()` moves it to its word's start, so its rules read `tr\<newline>ue` as `true` and `|\<newline>|` as `||`. A rule that slices the raw line reads it at the same offsets (`hooks/tezgah_integrity.py::joined`). The opencode mirror asks its port, `opensComment`. Trigger, edit/write: a skip marker newly
introduced into a test file — the path must match `tests?/`, `test_*`, `*_test`, `*.test.*` (`hooks/tezgah_integrity.py::TEST_PATH`), the marker must survive `mask_source()` so one
inside a string or comment does not count, and `_added` compares against the file's own text on disk for a `Write` (`hooks/tezgah_integrity.py::_added`, `hooks/tezgah_integrity.py::SKIP_TEST`). Every write dialect is read
through one reader (`hooks/tezgah_integrity.py::write_texts`, over `hooks/tezgah_taste.py::edit_text`): `new_string`/`newString`, `new_str`, `content`/`file_text`, `edits[]` and an `apply_patch` body, which is split per `*** Update File:`/`*** Add File:` header so the test-path gate and the count run per file (`hooks/tezgah_integrity.py::PATCH_FILE`). Told:
the texts at `hooks/tezgah_integrity.py::shortcut_edit` — run the checks, or say the test is failing; ask the user first if the skip is intended. Standing, with one switch:
`verify-off` removes this check (`hooks/tezgah_gate.py::decision`). The shell is a write route like any other, and the one E7c measured an
armed session taking once the write tools were refused: a heredoc that writes a skip into a test file meets the same predicate, run over the body the
command would land (`hooks/tezgah_gate.py::shell_write_body`, read at `hooks/tezgah_gate.py::decision` — the body is the raw text, because `mask()` blanks
heredoc bodies by design). An MCP `write` call meets the same predicate over its payload text ([MCP](#mcp-a-servers-effect-tool)).

### Piped — a check whose status a trimmer owns

Trigger: a verification command (integrity's `VERIFY`) piped into a trimmer or filter — `tail`, `head`, `grep`/`egrep`/`fgrep`, `cut`, `wc`, `sed -n`, with
`|` or `|&`, a `tee` in between included — in one `&&`/`;`-separated segment of the line (`hooks/tezgah_integrity.py::piped_check`, `TRIMMER`
`hooks/tezgah_integrity.py::TRIMMER`). The line's exit status is the trimmer's, so the ledger can only record the check as ran, never as passed, and the Stop rule
then refuses every claim the run was meant to carry — observed in a real omp session where 13 checks ran piped and 3 of 6 completion claims were blocked.
Passes: a line that opens with `set -o pipefail` (`hooks/tezgah_integrity.py::PIPEFAIL`), which integrity then records as decisive
(`verify_ok`/`verify_fail`, [evidence.md](evidence.md)); a redirect to a file; a pipe of anything that is not a check (`git log | head`). The
remedy is one sentence, `hooks/tezgah_integrity.py::PIPED_REMEDY`, which the always-on core and the contract skill quote too. Told: keep the check last with its output in a file, then read the file in a separate call, or open the line with `set -o pipefail;`. A `; tail` on the same line hands the status to `tail`. The refusal names the check as it was typed. Standing, under `verify-off`
(`hooks/tezgah_gate.py::decision`). opencode asks the core for this rule on any shell line that pipes a check
(`hosts/opencode/plugins/tezgah.js:3069-3073`) and records such a line as `verify` when a pipe or a later command owns its status (`statusHidden`, `hosts/opencode/plugins/tezgah.js:505`).

### Attribution — an AI/model credit on its way into an artifact

Trigger, shell: a write command (`hooks/tezgah_gate.py::WRITE_CMD` — `git commit|merge|tag|notes`, `gh api`,
`gh pr|issue|release create|edit|comment|review|merge|close`) carrying a credit form (`hooks/tezgah_gate.py::ATTRIB` — `co-authored-by:`, `generated with`, `made with`,
a credit verb, `noreply@anthropic`, a robot emoji). A credit verb is `built`, `written`, `drafted` or a like verb, then `by`, `with` or `using`, then a model or vendor name. Trigger, edit/write: one of the content fields `EDIT_TEXT` (`hooks/tezgah_gate.py::EDIT_TEXT`)
containing a line that *starts* with a credit (`hooks/tezgah_gate.py::ATTRIB_LINE`). Told: remove it and re-run; naming a tool in order to use it is fine, crediting it
as author is not (`hooks/tezgah_gate.py::ATTRIB_DENY`). Standing. The line anchor is why prose that merely names the banned forms passes (`hooks/tezgah_gate.py::_CREDIT`).
The same twin as the shortcut rule's: a credit a heredoc writes into a file is refused from the body (`hooks/tezgah_gate.py::decision`), and no command has to be
a `git`/`gh` write for it to be this rule's. An MCP `write` or `publish` call meets `ATTRIB_LINE` over its payload text ([MCP](#mcp-a-servers-effect-tool)).
A folded `.tezgah` (`hooks/tezgah_research.py::folded`) makes `tezgah-research commit` write the project's own history with a message the gate never reads in the command. The CLI runs it through this rule's reader, `hooks/tezgah_gate.py::ATTRIB`, and the language rule's (`hooks/tezgah_lang.py::refusal`, under `lang-off`) before committing. It prints the same refusal, with exit 2 and nothing committed (`bin/tezgah-research::message_refusal`).

### Language — an identifier or message that is not English

Trigger, shell: a command that would create an identifier - `git checkout -b`/`git switch -c`, `git branch` with a new name, a commit subject (`git commit -m`/`--message`/`-F`), or a `gh pr|issue create --title` (the language section `hooks/tezgah_gate.py::lang_reason`, `hooks/tezgah_gate.py::BRANCH_NEW`, `hooks/tezgah_gate.py::COMMIT_MSG`, `hooks/tezgah_gate.py::GH_NEW`, `hooks/tezgah_gate.py::created_texts`; the text is read from the raw command, because `mask()` blanks quoted strings and a commit subject is one) - whose name or subject is **not English**: a letter outside ASCII anywhere (`hooks/tezgah_lang.py::non_english` - a predicate rather than one language's letter list, so Russian, Greek, Arabic, Chinese and accented Latin hit it exactly as Turkish does) or an ASCII-folded Turkish word from the curated list (`hooks/tezgah_lang.py::ENGLISH`, wi…

The rule is a **heuristic** and its own text says so: a word list is not a language detector, so it cannot tell a proper noun or a product name in another language from a word that ought to be English, and a listed word may be the user's own term. A command that only names the words - `echo`, `grep`, `git log --grep` - creates nothing and passes. An identifier outlives the session that typed it, which is the reason the rule exists at all: `plan/004-admin-durum-onarimi` is in a public history from the moment it exists. On **opencode** the rule is not ported: the plugin asks the core for it through `bin/tezgah-gate check`, one spawn for a command its pre-test reads as identifier-creating (`IDENT_CMD` `hosts/opencode/plugins/tezgah.js:632`, the call site `hosts/opencode/plugins/tezgah.js:3069-3073`).

Off: `lang-off`, the rule's own switch (`hooks/tezgah_gate.py::decision`), and `pretooluse-off` drops it with the whole gate.

### Race — another session wrote this file minutes ago

Trigger: another session recorded a write of this call's file inside `RACE_WINDOW_MIN = 10` minutes (`hooks/tezgah_gate.py::RACE_WINDOW_MIN`). The call's files are
its path field, its `apply_patch` headers, or a shell redirect or `tee` target (`hooks/tezgah_gate.py::write_paths`, `hooks/tezgah_gate.py::race_reason`).
The reader counts an `edit` row and a shell `run` row that carries a `target` (`hooks/tezgah_integrity.py::writers_elsewhere`).
Scratch is skipped: a temp file or a device (`hooks/tezgah_integrity.py::scratch_target`). A file a git checkout holds is never scratch, even when the checkout lives under the temp dir (`hooks/tezgah_gate.py::_scratch`). A `run` row that writes only scratch carries no `target`. The rule also skips the harness's own channels (`hooks/tezgah_gate.py::URI_CHANNEL`), such as `agent://`, `xd://` and `conflict://`. It skips a shell target with an unknown variable too.
It skips this session's own subagent once its slice record has closed after the subagent's newest write of the file (`hooks/tezgah_gate.py::ended_child`). The writer ledger's `spawned` row names the child, and the record is read after `pending` closes an ended omp child. A child with no record, an open one, or a write newer than the close stays refused.
Told: re-read the file and re-apply the change to what is on disk now (`RACE_DENY`
`hooks/tezgah_gate.py::RACE_DENY`). The text names each writer by its relation to this session (`hooks/tezgah_gate.py::RACE_WHO`, `hooks/tezgah_integrity.py::_relation`).
The relations are your subagent, your parent, a sibling subagent, an omp fork, the fork's origin and an unrelated session. The omp hook writes a fork's `forked` row from its header's `parentSession` (`hosts/omp/hook.py::handle`).
Standing (`RACE_REFUSE = True` `hooks/tezgah_gate.py::RACE_REFUSE`) — a notice would not close a silent overwrite — and it lifts only by time.

A write into another repository than cwd's gets one notice per session and target repository, never a refusal (`hooks/tezgah_gate.py::cross_project_note`). It says that repository's plans, lessons and slice journal do not apply to this session. A worktree counts as its main checkout, and a repository's own `.tezgah` as that repository. Claude, dsh, Codex, Cursor and omp carry it on their post-tool channel. opencode does not.

### Lease — a sibling slice owns this file

Trigger: a write into a file an open sibling slice owns, or into the main checkout while the writer's own brief declares a worktree (`hooks/tezgah_gate.py::lease_reason`).
A brief's `Owns:` line holds the globs, split on commas and spaces, or lists them as `- glob` items under it. The slice record stores them as `owns` (`hooks/tezgah_task.py::owned_globs`, `hooks/tezgah_task.py::open_slice`). The owner is the open record whose globs match (`hooks/tezgah_task.py::owner_of`). A reader, an agent named for a read-only role such as a reviewer, holds no lease.
The main-checkout refusal reads the worktree a `Worktree:`, `Checkout` or `Cwd:` line declares, the slice's own task first (`hooks/tezgah_task.py::_declared_in`). A path the brief only names declares nothing, and a declared main checkout means the slice works there. The journal still keeps the named worktree for reconcile, resume and the board.
A shell target resolves against the call's own `cwd` and every `cd` or `pushd` before it (`hooks/tezgah_gate.py::_shell_dir`). A redirect to `/dev/*` or a descriptor writes no file.
A slice may write a path its own `Owns:` names. The `.tezgah` directory and scratch stay free, and a closed owner frees its files. A checkout under the temp dir is not scratch here either (`hooks/tezgah_gate.py::_scratch`).
On omp, the ledger's `spawned` row maps the writing session to its record (`hooks/tezgah_integrity.py::spawn_of`, `hooks/tezgah_task.py::slice_of`). A Claude background child maps through the `agent_id` its calls carry, which the spawn's result named (`hooks/projects-posttooluse.py`). Its SubagentStop closes the record (`hooks/tezgah_task.py::close_child`). Everything else fails open. A Claude foreground agent, dsh, Cursor and opencode open the record only once the child has ended, and Codex writes no `spawned` row.
Told: the owner, its globs, how to reach it - omp `write agent://<name>`, Claude `SendMessage`, else the parent - and the `tezgah-task slice done <id>` that frees it (`hooks/tezgah_gate.py::LEASE_DENY`, `hooks/tezgah_gate.py::MAIN_CHECKOUT_DENY`). Standing while the owner's record runs.
Off: `orchestrate-off`, whose fan-out rule it backs, and `slices-off`, which keeps no record to read (`hooks/tezgah_gate.py::decision`).
A spawn whose writing slices name one worktree gets a warning, never a refusal, since a reviewer panel shares a checkout freely (`hooks/tezgah_gate.py::spawn_advice`, `hooks/tezgah_task.py::worktree_clash`). The warning covers two slices in the call and one beside an open sibling. Omp, Claude and dsh carry it with the spawn's result.

### Task — the active plan's phase and path allowlist

Trigger: a write tool, or a shell command that writes a file, while an active task is set — a plan file under `.tezgah/plans/open` whose frontmatter carries a valid
`phase` (`tezgah_task.active`). The phase refuses a write in a reading phase (`hooks/tezgah_gate.py::TASK_PHASE_DENY`) and a shell command that writes one (`hooks/tezgah_gate.py::TASK_SHELL_DENY`,
against `hooks/tezgah_gate.py::SHELL_WRITE`); the allowlist refuses a target outside it (`hooks/tezgah_gate.py::TASK_SCOPE_DENY`) — a write tool's path, and a shell command's redirect or `tee` target (`hooks/tezgah_gate.py::write_paths`); and a write whose target IS the record, by a write tool or a shell redirect/`tee`, is refused
(`hooks/tezgah_gate.py::TASK_RECORD_DENY`) - the active task's record and any other open plan that carries a phase (`hooks/tezgah_task.py::phased_record`), matched without case and read against the main checkout, so a session in a worktree meets the same rule - because only `bin/tezgah-task` writes it and that CLI makes the checks a retyped frontmatter would skip. Told:
the move that lifts it, made by the session itself — `tezgah-task phase implementation` or `tezgah-task allow <glob> ... --why "<reason>"` — since the orchestrator owns the plan lifecycle and the CLI refuses
the move until the plan's Acceptance, spike and checkpoint are in order, and records the reason for a widened scope (`allowed_why:`). The record's body has its own writers, on any open plan, run from the main checkout or from any of its worktrees. `tezgah-task tick NNN <n> [--undo]` ticks Acceptance item n (`bin/tezgah-task::cmd_tick`). `tezgah-task note NNN state|next "<text>"` replaces the newest `## State` or the `## Next` body (`bin/tezgah-task::cmd_note`). `tezgah-task spike NNN "<answer>"` writes `spike_recorded:`, the answer `implementation` waits for (`bin/tezgah-task::cmd_spike`). `tezgah-task unmet <NNN> <n> "<reason, who accepted it>"` annotates Acceptance item n with `UNMET:`, the form `close NNN done` accepts in place of a ticked box (`bin/tezgah-task::cmd_unmet`). `tezgah-task sweep` makes one idempotent pass over what the last session left behind (`bin/tezgah-task::cmd_sweep`). It lists every pending slice as one line. It removes the landed worktrees and branches, and clears a `phase:` whose branch is gone. It prints the pending slices instead of closing them, because resuming one is the session's move. None of them commits. Standing: only the record changing lifts it.
Scratch meets no allowlist: a temp file or a device, such as `pytest > /tmp/check.log` (`hooks/tezgah_gate.py::task_reason`). Build output inside the repo stays held. So does a file in the repo or its worktrees when the checkout lives under the temp dir, as CI's does.
The task rule holds repository paths only. A target under no git checkout and no configured root, such as `~/.config/runpod/key`, is no plan's work (`hooks/tezgah_gate.py::_no_repo`). Neither the phase nor the allowlist refuses it, while every other rule, the secret rule among them, still reads that write. The gate reads a relative target in the call's own directory. Any doubt keeps the target held. A line that moves the directory stays held, however it spells the `cd`, `pushd` or `popd`. So does a line that reads `$PWD` back. A line that makes a link stays held: `ln`, `install`, `cp -s`, `cp -l`. So does a target whose parent directory does not exist yet. So does a file with a second hard link. Host agent and instruction files and the shell rc files stay held too, in any letter case (`hooks/tezgah_gate.py::HOME_HELD`). Under `~/.claude` those are `agents/**`, `hooks/**`, `commands/**`, `skills/**` and `CLAUDE.md`. Elsewhere they are `~/.omp/agent/**`, `~/.codex/AGENTS.md`, `~/.codex/prompts/**`, `~/.cursor/**` and `~/.config/opencode/**`. The rc files are `~/.zshrc`, `~/.zshenv`, `~/.zprofile`, `~/.zlogin`, `~/.bashrc`, `~/.bash_profile`, `~/.bash_login` and `~/.profile`. A target in another repository stays refused as outside this one.
Three targets are no project file, so neither the phase nor the allowlist refuses them (`hooks/tezgah_gate.py::unnamed_target`). A URI is one: a tool device (`xd://<tool>`), an agent message (`agent://X`) or a conflict resolution (`conflict://2`). A `file://` URI names a checkout file and stays held. A shell target with an unknown variable is another. `write_paths` first expands a variable from an assignment earlier on the line. So the allowlist holds `B=src; git diff > $B/x.patch` as `src/x.patch`. A variable the same line set to the checkout, such as `R=$(git rev-parse --show-toplevel)`, is read as the checkout (`hooks/tezgah_gate.py::known_tail`). The third is tezgah's own workspace under `.tezgah/`, such as research lines, lessons and briefs (`hooks/tezgah_gate.py::workspace_free`). The slice journal stays held. So does every shell write into `.tezgah/plans/open/`, because such a file could make itself the active task. A plan file stays held too when its text, once the write lands, carries a `phase:` line (`hooks/tezgah_gate.py::_text_after`). The gate judges the whole text, so two edits cannot each pass on their own. The record rule still refuses the active record there.
The gate matches a file in a linked worktree of the same repository relative to that worktree's top (`hooks/tezgah_task.py::relative`). Each writing slice gets its own worktree, so `hooks/a.py` there is in scope when `hooks/a.py` is. The phase, allowlist and checkpoint rules read a sibling. The record rule reads the main checkout, and the workspace rule keeps the cwd's own root. The worktree's admin directory must point back at it, and a worktree of another repository stays outside.
Two plans can run at once, one per worktree. A linked worktree holds plan NNN when its branch is `plan/NNN-...` (`hooks/tezgah_task.py::branch_task`). That covers the plan's declared `branch:` and every slice branch the plan fans out to. Of several, the declared branch's worktree is the one the checkpoint and review read (`hooks/tezgah_task.py::plan_holders`). It then answers to plan NNN's phase, allowlist and checkpoint while plan NNN carries a phase. A session whose cwd is that worktree reads plan NNN as the active task. A write from anywhere else into that worktree meets plan NNN too (`hooks/tezgah_task.py::worktree_task`). A shell line meets the plan of every redirect and `tee` target it names (`hooks/tezgah_gate.py::_owners`). It meets the cwd's task as well when it writes where no target was read. That is a positional writer such as `sed -i`, a `tee` with more than one file, or more write shapes than targets. The checkpoint's sha is read against that worktree's HEAD and tree, and the refusal names `git -C <worktree>`. Every other checkout reads the main checkout's plans. Its task is the first phased plan no worktree holds. When every phased plan is held, it has no scope of its own, and a write outside the plan worktrees meets no plan (`hooks/tezgah_task.py::active`). The record rule still refuses a direct write to each held record. `tezgah-task start` keeps another plan's phase in one case only (`bin/tezgah-task::cmd_start`). Both plans then run in their own worktrees, and their allowlists share no prefix. Otherwise it clears that phase. `allow`, and `phase --any-path`, refuse a scope that shares a prefix with such a held plan (`bin/tezgah-task::held_overlap`). Off: `task-off`
(`hooks/tezgah_gate.py::decision`). It fails open wherever the question cannot be answered: no active task, no readable record.

The fourth refusal under the same rule is the checkpoint. Trigger: a write, or a shell command that writes a file (`hooks/tezgah_gate.py::SHELL_WRITE`), while the task is in
`phase: implementation`, its record reads `checkpoint: pending <sha>`, that sha is still the checkout's HEAD and the tree is dirty (`checkpoint_reason()`
`hooks/tezgah_gate.py::checkpoint_reason`, `hooks/tezgah_gate.py::CHECKPOINT_DENY`). Told: the task it read, that the record holds a `pending` checkpoint, and the one command
that makes the boundary real - it names that command because running it *satisfies* the rule rather than taking it off. Standing: the recorded sha is the switch, not the tree - the commit
the refusal names moves HEAD off that sha, so the refusal clears itself, where keying on the word `pending` alone left the phase waiting on a record only
`bin/tezgah-task` rewrites. Off, with the rest of the rule: `task-off`. It fails open wherever the question cannot be answered: no record, no `checkpoint:` key, a
checkpoint that is a plain sha (the boundary is already real), a `pending` with no sha, a sha this checkout's HEAD does not name, and a repo whose HEAD cannot be read.

### Workspace — tezgah state outside `.tezgah/`

Trigger: a write tool, or a shell redirect/`tee` (`write_paths`), whose target relative to the repo root starts with `plans/`, `research/` or `analysis/` while the project tracks no file under that directory (`workspace_reason`, `hooks/tezgah_gate.py`). The refusal names `.tezgah/<kind>/` as the place to write. It also names the commit form for the workspace's shape (`hooks/tezgah_research.py::folded`). An own repository gets `git -C .tezgah` (`hooks/tezgah_gate.py::WORKSPACE_OWN`). A folded one the project tracks gets its own `git add`/`git commit` (`hooks/tezgah_gate.py::WORKSPACE_FOLDED`). A directory the project already tracks is its own and passes. `mkdir` and positional shell targets (`cp`, `mv`) are not read - the same ceiling as `write_paths`. Off: `workspace-off`.

A second trigger under the same switch: a write under a dot dir directly below `.tezgah/research/`, such as `.tezgah/research/.staging/x/state.json` (`hooks/tezgah_gate.py::research_hidden_reason`). It is read against the main checkout and against the session's own root. `slugs()` skips dot dirs, so a line there is invisible to `status` and `check`. The refusal says a refused line goes to the owner (`hooks/tezgah_gate.py::RESEARCH_HIDDEN_DENY`). `open/`, `done/` and a dot file directly in `research/` pass.

### Secret — a credential on its way into a file

Three triggers, one per shape a credential takes on its way into a file (`hooks/tezgah_gate.py::secret_command`, `hooks/tezgah_gate.py::secret_edit`, read at `hooks/tezgah_gate.py::decision`):

- **Shell text.** One simple command (split on `&&`, `||`, `;`, newline — `hooks/tezgah_gate.py::SEGMENT`) carrying both a token (`hooks/tezgah_gate.py::SECRET_TOKEN` — an
  `Authorization: Bearer` header, or a `name=value` assignment for `api_key`/`token`/`secret`/`password`/...) and a sink (`hooks/tezgah_gate.py::SECRET_SINK` — `>`/`>>`,
  `| tee`, a curl `--trace`, or `git add`). Told: record the name, length or a fingerprint instead, and pass the value through the tool's environment (`hooks/tezgah_gate.py::SECRET_DENY`).
  A token only in the leading `NAME=value` words of a program reaches that program's environment, not the file.
  So `API_KEY="$(cat key)" python3 tool.py > run.log` passes (`hooks/tezgah_gate.py::_env_prefix_only`).
  An allowlist is the ceiling of this case (`hooks/tezgah_gate.py::_secret_runner`). Only a script runner named by itself passes: `python`, `node`, `bun`, `deno run`, `bash`, `sh` or `zsh`.
  It needs a script file ending in `.py`, `.js`, `.mjs`, `.ts` or `.sh`.
  No option before the file may run inline text, stdin, a preload, interactive mode or a trace.
  Those are `-c`, `-e`, `-p`, `-`, `-r`, `-i`, `-x`, `-v` and `-o` (`hooks/tezgah_gate.py::SECRET_INLINE`).
  Every other program holds, because it may print its environment: `env`, `echo`, `xargs env`, `node -pe`, a bare `prog`, a program named by its path.
  It also holds when the sink is a `git add` or a curl trace (`hooks/tezgah_gate.py::SECRET_OUTPUT`).
  A line that reads `/proc/*/environ`, defines a function or runs `set -x` holds too.
  So does a line that sets an interpreter's startup or trace variable (`hooks/tezgah_gate.py::SECRET_STARTUP`: `BASH_ENV`, `NODE_OPTIONS`, `PYTHONSTARTUP`, `LD_PRELOAD`, ...).
  The rule cannot read the script itself: an allowlisted script that prints its own environment still writes the key.
  A name an earlier command on the line set to a token stays carried. A printer that reads it into a file still denies, as in `API_KEY=x; echo $API_KEY > f` (`hooks/tezgah_gate.py::_printer_owns_sink`).
  That check reads the pipeline stage that owns the sink, so `echo "$TOKEN" | docker login --password-stdin > log` passes. A `> /dev/null` is not a file there.
  The rule reads token shapes, not file names: `echo "$KEY" > f` and `cat key > f` carry no token and pass.
- **A credential file staged.** A `git add` that names a credential file (`hooks/tezgah_snapshot.py::SECRET_FILE`: `.env`, `.env.local`, a key, `id_rsa`, `credentials.json`).
  The command is read word by word (`hooks/tezgah_gate.py::_secret_add`). `.env.example`, `.env.sample`, `.env.template`, `.env.dist` and `.env.defaults` carry names without values and pass (`hooks/tezgah_gate.py::SECRET_TEMPLATES`).
  The rule does not read `git add -A` or `git add .` (`hooks/tezgah_gate.py::SECRET_ADD_DENY`).
- **The text a write lands.** The text holds a token with a known credential prefix. It is read on every route: a write tool in every dialect, an `apply_patch` file by file, a heredoc body.
  The prefixes are the redactor's families (`hooks/tezgah_integrity.py::SECRET_PREFIXED`: `ghp_`, `github_pat_`, `sk-live-`, `xox?-`, `AKIA`, `AIza`, `glpat-`, `npm_`).
  An `sk`/`pk`/`rk` token counts only with its qualifier (`sk-live-`, `pk_test_`, `sk-proj-`). The redactor's bare branch also matches identifiers such as `pk_users_organization_id`.
  A token the file already carried does not count: the baseline is the replaced text plus the file on disk (`hooks/tezgah_gate.py::secret_edit`). This trigger does not read `name=value`.
  A template or test-fixture file may carry a token (`hooks/tezgah_gate.py::SECRET_FIXTURE`: `*.example`, `tests/**/fixtures/**`, and the templates above).
  A documentation placeholder passes: a token that says `example`, one whose body is one repeated character, and a published docs key (`hooks/tezgah_gate.py::SECRET_PUBLISHED`).
  In a file's text, `password = os.environ[...]` is a program that reads its credential. A Write, an Edit, a patch and a heredoc that land it all pass.
- **An MCP payload.** The gate refuses an MCP `write` or `publish` payload that carries a vendor token such as `ghp_` or `sk_live_` (`hooks/tezgah_gate.py::MCP_TOKEN`).
  A bare `sk-`, `pk_` or `rk_` prefix does not count there, because identifiers and branch names carry it (`hooks/tezgah_gate.py::MCP_SECRET_DENY`).
  Neither does the `name=value` shape, which a program's own text matches.

Standing, no escape hatch, and outside `verify-off`.

### Plan — a turn's third product file on a branch no plan binds

Trigger: a write tool, or a shell redirect/`tee` (`hooks/tezgah_gate.py::write_paths`), whose target is a product path, while the checkout holding that target is on a branch that binds no open plan
and this turn has already written two other product files into the same checkout (`hooks/tezgah_gate.py::plan_reason`, `hooks/tezgah_gate.py::_branch`, `hooks/tezgah_gate.py::_checkout`,
`hooks/tezgah_gate.py::_product`). The branch comes from that checkout, not from the session's cwd. A branch binds a plan when it is `plan/NNN-slug` for an open plan NNN, or when an open plan
declares it in its `branch:` frontmatter (`hooks/tezgah_gate.py::_unplanned`, `hooks/tezgah_task.py::plan_of_branch`, `hooks/tezgah_task.py::declared_branches`). So `plan/999-nope` binds
nothing, and Orca's `r1z4x/<slug>` branches bind by declaration. The task rule holds a bound checkout, by its plan's phase and allowlist. `main` and `master` never bind a plan, whatever a plan
declares. The count folds the turn's own write rows (`hooks/tezgah_integrity.py::turn_rows`) together with the files the call in hand names, so it needs no state of its own, and it counts DISTINCT
paths - a turn that rewrites one file three times is still one file's work. A product path is any path in the checkout, whatever the project's layout (`apps/`, `packages/`, `.maestro/` count as
`hooks/` does). Tezgah's and git's own state does not count: `.tezgah/`, `.codegraph/` and `.git/` (`hooks/tezgah_gate.py::PLAN_SKIP`). Neither does a host's generated `agents/` set
(`hooks/tezgah_gate.py::PLAN_AGENT_HOSTS`). A path outside any git repository never counts. Nor does a path that names no file on this disk: a URI such as `agent://<id>` or `local://x.md`, or a `file://` URL naming another host. A local `file://` URL counts as the file it names, in the checkout that holds that file. The writer stores that file as the row's `target`, and any other URI's own spelling. The race guard compares that spelling, and this rule skips it (`hooks/tezgah_integrity.py::file_url_path`). Told: the branch it read, how many files the turn has written, and
the command that opens a plan - the `plan-add` skill, `/tezgah:plan-add <description>` (`hooks/tezgah_gate.py::PLAN_DENY`). Off the trunk it also names the bind route: `tezgah-task start NNN
--phase P --branch <branch>` writes the plan's `branch:` (`hooks/tezgah_gate.py::PLAN_BIND`, `bin/tezgah-task::cmd_start`). On `main` or `master` it names only the `plan/NNN-slug` route or
another branch an open plan declares (`hooks/tezgah_gate.py::PLAN_BIND_TRUNK`). `cmd_start` refuses `--branch main` or `--branch master` too. The record rule refuses a hand edit of a phased record. Standing: only changing the tree's state changes it - the
work moves to the `plan/NNN-slug` branch the skill creates or to a bound branch (a one- or two-file fix is free either way), or the repository carries a `.no-plan-gate` mark (the shape of
`.no-graph` and `.no-lessons`). It passes while a merge or rebase is in progress (`MERGE_HEAD`, `rebase-merge/` or `rebase-apply/` in the checkout's gitdir, `hooks/tezgah_gate.py::_merging`):
resolving conflicts is not new work. It passes wherever the question cannot be answered: no session or ledger, a directory that is not a git repository, and a detached HEAD with no branch to name.

### Ordering — a commit while the newest check failed

The one rule here that asserts a relation between two actions rather than reading one call plus a ledger tail, and the shape FAVA found in 90% of real
agent-instruction projects ("do not commit before running the tests").

Trigger: the command is a `git commit` (or `--amend`; `hooks/tezgah_gate.py::COMMIT_CMD`, matched at `hooks/tezgah_gate.py::commit_order_reason`) and the newest check in
this session **failed**. The state is the Stop rule's own fold over the ledger tail (`ORDER_TAIL = 200` `hooks/tezgah_gate.py::ORDER_TAIL`, the fold
`tezgah_integrity._last_verify`), and the rule is structurally incapable of firing in either direction that would punish honest work: no check at all folds
to `None` and a passing newest check folds to `ok`, so a commit in a session that ran no check — a docs-only commit — and a commit after a green run both
pass. Only `fail` refuses: the tree the commit would freeze is the one a check just rejected.

Told: the failed check by name and nothing else (`hooks/tezgah_gate.py::ORDER_DENY`, `hooks/tezgah_gate.py::commit_order_reason`) —
making the newest check pass is the whole repair, so the refusal names no command that lifts it, for the reason the task refusals carry. Standing while the
tail still shows that failure, under `verify-off` (`hooks/tezgah_gate.py::decision`). Its deny row is its own rule name (`order`), so the counters separate it.

### Loop — the identical attempt that already failed twice

Trigger: the same call (same `call_id`) failed `LOOP_ATTEMPTS = 2` times already in the current user turn (`hooks/tezgah_gate.py::LOOP_ATTEMPTS`, `hooks/tezgah_gate.py::loop_reason`). Told: attempt N
of an identical call, the failure class read from the ledger (`transient`, `user`, `permanent`, `unknown`; the cap is the same for every class, and a `user` failure - a 401/403, a missing credential, a login - says to take a route that needs no credential first and ask the user once only when none is left), "change the approach or stop" (`hooks/tezgah_gate.py::loop_reason`). Standing while the ledger tail still shows those
failures. Under `verify-off` (`hooks/tezgah_gate.py::decision`).

### Retry — the session-wide ceiling

Trigger: the same call has been attempted more than `RETRY_CEILING = 3` times in the session, whatever those attempts returned (`hooks/tezgah_gate.py::RETRY_CEILING`, `retry_reason`
`hooks/tezgah_gate.py::retry_reason`). Told: an unchanged repeat is not a retry (`hooks/tezgah_gate.py::loop_reason`). Standing. Under `verify-off` (`hooks/tezgah_gate.py::decision`). Both guards read only the ledger tail.

### Nudge — the first code-symbol search of a session, then a line beside every later one

Trigger: a search for a code symbol, in a repo whose codegraph index exists (`<repo>/.codegraph/codegraph.db`) and that has no `.no-graph` (`hooks/tezgah_gate.py::index_slug`).
A code symbol has an inner underscore or a lower-to-upper step, or sits in a `def x` or `x\(` pattern (`hooks/tezgah_gate.py::symbol_in`).
A plain word such as `TODO` is literal text and never matches.
The search is the pattern of a `grep`, `search` or `ast_grep` tool, a term of omp's `find`, or a `grep`/`rg` argument (`hooks/tezgah_gate.py::searched_symbol`, `hooks/tezgah_gate.py::BASH_SEARCH`).
omp's bridge sends `find`, `search` and `ast_grep` to the gate, because omp's own prompt sends code discovery to `find` first (`hosts/omp/tezgah-hook.ts.in`).
Told: the host's graph tool (`hooks/tezgah_gate.py::graph_tool`) and the runnable command built from the denied search (`codegraph explore <X>`, `codegraph callers <X>`, `codegraph impact <X>`).
An omp subagent uses this CLI, because omp's MCP device refuses concurrent writes (`hooks/tezgah_gate.py::nudge_reason`).
Once-only: the mark is a `nudged` row of the cache's `tezgah.db`, keyed `sha1(session)[:16]`. It is written *before* the refusal, so re-issuing the search passes (`hooks/tezgah_gate.py::first_nudge`). opencode's `oncePerSession` writes the same key (`hooks/tezgah_gate.py::nudge_key`).
After that, every later symbol search passes with one line naming the graph tool, while the index stamp equals HEAD (`hooks/tezgah_gate.py::graph_advice`).
Claude reads the line as PreToolUse `additionalContext` (`hooks/projects-pretooluse.py`), and omp reads it with the call's `tool_result` (`hosts/omp/tezgah-hook.ts.in`).
Codex and Cursor read it with their PostToolUse result (`hosts/codex/hook.py`, `hosts/cursor/hook.py`).

### Drift — a long turn loses the rules it started with

Trigger: 25 work rows (`hooks/tezgah_gate.py::DRIFT_STEPS`) in the current user turn and an effectful call — a write tool, or a git/gh artifact command (`effectful`
`hooks/tezgah_gate.py::effectful`). An MCP call of any verb class counts as an effectful call too. Told: the standing constraints re-stated, or the delta since the turn began; "re-issue this call unchanged and carry on" (`hooks/tezgah_gate.py::DRIFT_DENY`,
`hooks/tezgah_gate.py::drift_reason`). A refusal, last in `decision` after every other built-in rule. Only a repository's own rule runs after it ([Adding a rule](#a-repositorys-own-rule)). Its only delivery: no host's PostToolUse side carries it, and opencode gets it from the core through `bin/tezgah-gate` on its write path. Once per turn: the `drift` mark is written *before* the refusal, so the identical call passes on the next attempt. The count behind it is the turn's own — a bounded read (`hooks/tezgah_gate.py::DRIFT_TAIL`) falls back to the turn's own start (`hooks/tezgah_integrity.py::turn_rows`) when the turn outgrew the window. Governed by `reminder-off`, not `verify-off` (`hooks/tezgah_gate.py::drift_reason`).

### Repo-rule — a repository's own `.tezgah/gate.py` refuses the call

Trigger: the repository's rule file, in the git index, answers `{"deny": "<reason>"}` for this call (`hooks/tezgah_gate.py::repo_rule_reason`). Told: that reason, capped at 600 characters, inside a label naming it repository-supplied (`hooks/tezgah_gate.py::REPO_RULE_DENY`). Last in `decision`, after every built-in refusal. A timeout, a non-zero exit or malformed output allows. Off with `pretooluse-off`, or `TEZGAH_REPO_RULE=0` in the environment. The contract is [A repository's own rule](#a-repositorys-own-rule).

### Ask — an ask-tool question with no recommended option

Not a rule of `decision`: the hosts ask for this warning after `decision` lets the call through, as they ask for the graph line.
Trigger: an omp `ask` call or a Claude AskUserQuestion call inside a root (`hooks/tezgah_gate.py::ask_advice`).
The gate counts the questions and the ones that carry a recommended option (`hooks/tezgah_integrity.py::undefaulted`).
omp marks one with a question's `recommended` index. Claude marks one with an option label such as "(Recommended)" or "(önerilen)".
Told: how many questions carry no default, and that each question names one, unless the step waits on the user by nature (`hooks/tezgah_gate.py::ASK_NO_DEFAULT`).
A question about a step the user granted this session gets a second line: take the step, do not ask again (`hooks/tezgah_gate.py::ASK_GRANTED`).
A warning, never a deny: the line rides back with the call's result, as the graph line does. Every such call leaves an `ask` row with `questions` and `defaults`.
Claude routes the tool through its PreToolUse matcher (`hooks/hooks.json`), and omp through its `GATED` list (`hosts/omp/tezgah-hook.ts.in`).
Off under `verify-off` and `pretooluse-off`. The rest of the ask policy is the Stop rule's `needless ask` class ([evidence.md](evidence.md#the-stop-rule-end-to-end)).

## What the gate deliberately does not catch

Read this before filing a security-ish issue; each is a decision, not an oversight.

- Irreversible and outward-facing shell commands — force-pushes, migrations, deploys, `ssh`, `scp`, a `curl` write, a `gh pr` write — run without an ask.
  The consent rule and its `send`/`outward`/`deploy`/`publish`/`schema`/`destructive` class table were removed on purpose (2026-09-26): the ask it put in
  front of every server-side command cost a round-trip per effect, the user's chat approval could not lift it (only the deleted `bin/tezgah-consent` CLI
  could), and the sessions it actually gated were the user's own deploys. The untrusted-read half went with it: a turn that read web content may now run an
  outbound effect carrying only the taint notice, with no refusal in between. The notice itself stays (`hooks/tezgah_untrusted.py`).
  The ask policy replaced it (plan 086, S3). It is a class table in the contract, the Stop rule's `needless ask` class and the ask-tool warning above.
  A grant the user writes in chat ("bana sormadan pushla") lifts the ask for its class. Outward commands still run with no refusal.
- A write inside the root after a fetch: left to the taint notice that `hooks/tezgah_untrusted.py` rides the first effect with, because it is recoverable from
  the snapshot.
- `grep -A 3 foo`: a flag with its own value shifts the token, so the search passes unnudged (`hooks/tezgah_gate.py::BASH_SEARCH`).
- A foreign `apply_patch` write: the PostToolUse writer records no path for that row (`hooks/tezgah_gate.py::write_paths`); and the guard skips a row an older writer left with no
  `target`, because that row names no file (`hooks/tezgah_integrity.py::writers_elsewhere`).
- Which rule the user meant when a turn drifts: "a guess about intent wearing a check's clothes" (`hooks/tezgah_gate.py::drift_reason`).
- The MCP walk stops at 64 KiB of text, 8 levels or 4096 values (`hooks/tezgah_integrity.py::MCP_WALK_MAX`). Text past the cap goes unread.
  A tool name with no verb from `MCP_VERBS` counts as a read. Both cost that call the content rules, never a refusal.
- A skip already in the file, or one inside a string (a test *about* the rule), is not a disable (`hooks/tezgah_integrity.py::_added`).
- A `core.hooksPath` redirect behind an alias or a variable: `git -c core.hooksPath=/tmp/h -c alias.c=commit c` and `K=core.hooksPath; GIT_CONFIG_KEY_0=$K ...` set the directory and commit without the words `commit`/`push` or the literal key, so the word reader (`hooks/tezgah_integrity.py::_hooks_redirect`) does not see them. Same class as `bash -c '<line>'`, which the program-position reader also does not open: a shell feature that hides the command is out of scope rather than half-read. A command substitution inside double quotes (`"$(git config core.hooksPath /dev/null)"` beside a commit) is the same class, and the reader's docstring says so (`hooks/tezgah_integrity.py::_unquoted_backticks`).
- The content of a shell write that is not a heredoc: `echo "Co-Authored-By: x" > f` puts the credit inside a quoted string that no line-start anchor can see,
  and reading the whole command instead would deny a search for the form (`grep "Co-Authored-By" x > out`). The three twins read a heredoc body, which is the
  route E7c measured (`hooks/tezgah_gate.py::shell_write_body`).
- A shell write whose target is not a redirect: `cp`, `mv`, `sed -i`, `patch` and `git apply` name it as a positional argument, and which argument of those is
  the target is a per-program question, so the gate keeps no pre-state for it and the freshness half reads no change there (`write_paths`
  `hooks/tezgah_gate.py::write_paths`). A shell write chained with a check in one call (`sed -i ... && pytest`) records as the check row, and the row that carries a
  pass is never the row read as the change - otherwise a check redirecting its own log would stale itself (`tezgah_integrity._change_row`).
- A PRIOR shell write's target, in the plan rule's count: a write the shell landed is a `run` row whose detail is the command, so the count reads the turn's
  write-tool rows plus the redirect the call in hand names (`hooks/tezgah_gate.py::plan_reason`). Three heredocs into product files in one turn
  therefore pass where the same three through the write tools are refused, and reading a stored command line for its target would be a second reader of the
  table `write_paths` already holds.
- A control-plane write through an interpreter: `python3 -c "open(...)"`, `node -e`, or a script the agent wrote. `find -delete` and `xargs` are the same
  class, and so is a path built from variables other than `~`, `$HOME` and the XDG ones. The control rule reads the command line, not what a program does at
  run time. `SECURITY.md` names these as the residual routes. A forged `verify_ok` row appended this way no longer passes: with no gate-written `began`
  row before it, it is an orphan (`hooks/tezgah_integrity.py::_pair`, `docs/evidence.md`). A forged `began` row plus its pass still does.

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
`tool.execute.before` (hosts/opencode/plugins/tezgah.js:2988, exported `hosts/opencode/plugins/tezgah.js:2936`) in the gate's own order (`hosts/opencode/plugins/tezgah.js:2988-3153`); its shortcut constants restate the same regexes (`NEUTER` `hosts/opencode/plugins/tezgah.js:314`,
`SKIP_ENV` hosts/opencode/plugins/tezgah.js:315, `NO_VERIFY` hosts/opencode/plugins/tezgah.js:316, `GITISH` hosts/opencode/plugins/tezgah.js:317, `SKIP_TEST` hosts/opencode/plugins/tezgah.js:575). What keeps the two halves honest is a test, not a shared module:
`tests/test_opencode_plugin.py` drives the plugin's hooks through a node harness with a throwaway HOME, and imports the Python `tezgah_integrity.call_id` so a
separator or canonical-form drift in the action id fails there instead of silently in a session (`tests/test_opencode_plugin.py:1-7`, `tests/test_opencode_plugin.py:27-30`, `tests/test_opencode_plugin.py::OpenCodePlugin.test_the_id_is_the_hash_the_python_writer_computes`).

The shell rule kinds mirrored last are each pinned in both suites: the shell's write body (`SHELL_WRITE` `hosts/opencode/plugins/tezgah.js:1039`,
`heredocBodies` `hosts/opencode/plugins/tezgah.js:1045`, `shellWriteBody` `hosts/opencode/plugins/tezgah.js:1078`, the shortcut and attribution twins at
`hosts/opencode/plugins/tezgah.js:3043-3044` and `hosts/opencode/plugins/tezgah.js:2010`, the credential twin at `hosts/opencode/plugins/tezgah.js:1970-1974`) and the
ordering obligation (`COMMIT_CMD` `hosts/opencode/plugins/tezgah.js:1899`, `ORDER_DENY`
`hosts/opencode/plugins/tezgah.js:1901`, `lastVerify` `hosts/opencode/plugins/tezgah.js:1911`, `orderReason` `hosts/opencode/plugins/tezgah.js:1936`, dispatched at
`hosts/opencode/plugins/tezgah.js:3084-3087`). `lastVerify` folds the tail exactly as `_last_verify` does, minus the `passing_check` narrowing - this rule reads only
`fail`, and a row that narrowing would refuse reads `ok`/`ran` on both sides, so the outcome is identical.

The control rule has no JavaScript copy. The plugin's `CONTROL_CMD` pre-test picks the shell lines that could touch the control plane. The plugin puts each
such line to the core before any rule of its own, and returns the core's answer verbatim. A write tool already goes to the core. The plugin's own `off()`
answers only for a name in its `SWITCHES` list, and `tests/test_paths.py` holds that list equal to `tezgah_paths.SWITCHES`.

## Rule provenance

A rule is a refusal with a cause: something happened, the check was written, and a case was added so it cannot happen again unnoticed. That record used to live
only as a sentence inside each rule's own paragraph above. It is a table here instead, so it is one place and a machine reads it: `bin/tezgah-docs --citations`
opens `docs/gate.md`, reads this table, and refuses a rule name the source can still produce with no row, and a row whose `pin` names a test that does not exist.
The names are read off the source, not restated: the gate's rules are the `_deny(session_id, "<rule>", ...)` calls in `hooks/tezgah_gate.py`, and the Stop
rule's triggers are the classes `_stop_block` returns, the four `_shape_block` hands back and the six `_evidence_text` words for the temporal spec included.

- `incident` — what produced the rule; `designed` where none is recorded. The ratio of incident-derived to designed rules is the maturity signal the research
  entry names, which is why the distinction is written down rather than smoothed over.
- `evidence` — where that incident is written down: the page section, the module comment, or the experiment's own preregistration.
- `pin` — the case that guards it, as `tests/<file>.py::<test_name>`. The checker refuses a pin that names no test, so the case and the row move together.

| rule | incident | evidence | pin |
|---|---|---|---|
| `control` | the deep analysis (REPORT R05): all 12 tamper probes passed the gate - a `touch` of a switch, a Write to one, `rm .git/hooks/pre-commit`, an `echo` into the ledger, `git add -f .tezgah/x` | `SECURITY.md` (Threat model) | `tests/test_control_plane.py::test_every_tamper_probe_is_refused_without_naming_a_command` |
| `explorer` | designed | the grep-only subagent was replaced by the graph tools; no incident recorded | `tests/test_gate.py::test_explore_subagent_denies` |
| `shortcut` | E7c: with the write tools refused, 3 of 25 armed runs wrote a test skip through a heredoc | an internal benchmark (block E7, not published) | `tests/test_gate.py::test_a_shell_write_that_disables_a_test_is_denied` |
| `piped` | a real omp session: 13 checks ran piped and 3 of 6 completion claims were blocked | the Piped section above | `tests/test_gate.py::test_a_piped_check_is_refused_and_pipefail_passes` |
| `attribution` | E7c: the same 3 of 25 runs, a credit written through a heredoc | an internal benchmark (block E7, not published) | `tests/test_gate.py::test_attribution_denies_a_credit_written_by_the_shell` |
| `lang` | a plan branch was created as `plan/004-admin-durum-onarimi`, and its slug is in the public history for good | the comment above `hooks/tezgah_gate.py::BRANCH_NEW` | `tests/test_gate.py::test_a_turkish_branch_name_is_refused` |
| `race` | two sessions on one file - a parent and its subagent, or two worktrees - landing on a stale read | the comment above `hooks/tezgah_gate.py::RACE_WINDOW_MIN` | `tests/test_gate.py::test_a_write_to_a_file_another_session_wrote_is_refused` |
| `lease` | plan 086 wave 1: two slices wrote into the main checkout through relative paths; 24 sibling race refusals in real transcripts, all in a shared worktree, tree or record | the Lease section above | `tests/test_gate.py::test_a_sibling_slices_lease_refuses_its_file_and_frees_the_owner` |
| `task` | E7: with the unlocking command printed, an armed arm removed or disabled the gate in 25 of 25 runs; E7b: the heredoc redirect in 3 of 25 | the Task section above (the checkpoint refusal) | `tests/test_gate.py::test_a_reading_phase_refuses_a_write_inside_the_allowlist` |
| `secret` | E7c: the same 3 of 25 runs, a key written through a heredoc | an internal benchmark (block E7, not published) | `tests/test_gate.py::test_a_credential_written_by_a_heredoc_is_denied` |
| `workspace` | sessions wrote root `plans/`, `research/` and `analysis/` (observed across several unrelated projects on one machine) | the comment above `hooks/tezgah_gate.py::WORKSPACE_KINDS` | `tests/test_gate.py::test_untracked_root_kinds_are_refused_for_tools_and_redirects` |
| `plan` | a turn wrote four product files - a hook, its tests, its docs and the changelog - straight onto `main` | the comment above `hooks/tezgah_gate.py::PLAN_TRUNKS` | `tests/test_gate.py::test_the_third_product_write_on_main_is_refused` |
| `order` | FAVA: the shape found in 90% of real agent-instruction projects ("do not commit before running the tests") | the Ordering section above | `tests/test_gate.py::test_a_commit_is_refused_while_the_newest_check_failed` |
| `loop` | designed | the turn's own repeated failure; no incident recorded | `tests/test_gate.py::test_an_identical_failed_call_is_denied_after_the_ceiling` |
| `retry` | designed | the session ceiling over the same guard; no incident recorded | `tests/test_gate.py::test_a_fourth_identical_call_is_refused_whatever_the_outcome` |
| `drift` | an internal plan's flip rule on the 2026-09-20 move to a result-channel notice: at 27 sessions the blocked-claim rate in turns under 25 work rows read 112/140 = 0.8000, against 59/142 = 0.4155 before | an internal plan (not published) | `tests/test_gate.py::test_a_long_turn_restates_the_constraints_before_a_write` |
| `repo-rule` | designed | a repository's own refusal through the extension seam (plan 124), no incident recorded | `tests/test_gate.py::test_a_repo_rule_denies_its_call_and_allows_the_rest` |
| `evidence tampered` | a terminated garbage line made `_parse` raise, and the guard then failed the Stop rule open for the turn; corrupting a `verify_fail` row was an allow route. A `verify_ok` appended with `python3 -c` licensed a claim (security-03), so a pass with no `began` row is an orphan (`hooks/tezgah_integrity.py::_pair`) | `hooks/tezgah_integrity.py::_parse` | `tests/test_integrity.py::test_a_damaged_ledger_blocks_a_done_claim_as_evidence_tampered` |
| `check failed` | designed | the newest check failing is its own class; no incident recorded | `tests/test_integrity.py::test_failed_check_blocks` |
| `partial failure` | designed | a failure the turn never resolved; no incident recorded | `tests/test_integrity.py::test_an_unresolved_failure_blocks_even_after_an_earlier_pass` |
| `no ui_ok` | reading the fold the old way refused honest turns and named a screen check the turn had in fact run | `hooks/tezgah_stopspec.py::FORMULAS` | `tests/test_integrity.py::test_a_green_unit_run_does_not_license_a_ui_change` |
| `stale evidence` | measured 2026-09-19: reading a rewrite as a change refused honest turns | `hooks/tezgah_integrity.py::_post_write` | `tests/test_integrity.py::test_a_write_after_the_check_makes_the_check_stale` |
| `no verify_ok` | E2: 0 of 10 description-shaped claims refused before the `worked` trigger | `hooks/tezgah_integrity.py::_stop_block` | `tests/test_integrity.py::test_work_with_no_passing_check_is_refused_without_a_claim_word` |
| `no external read` | two turns: "npm 0.22.0 is missing" off a stale client, and "make NPM_TOKEN an automation token" when it already was | `hooks/tezgah_integrity.py::_external_read_row` | `tests/test_integrity.py::test_an_external_claim_with_no_read_is_refused` |
| `residual work` | the owner's report (2026-10-11): turns end on "Açık kalanlar / Doğrulanmadı / Sıradaki adım" instead of the work; measured 503 of 1876 final replies with such a label at a line start, 467 in turns that called a non-read tool | `hooks/tezgah_integrity.py::_residual_block` | `tests/test_integrity.py::test_a_residual_list_is_refused_once_and_the_reply_after_it_recorded` |
| `ready steps` | measured 2026-10-11 (research line `orchestrator-flow-audit`): 13.1% of 451 omp user turns were a bare "devam", and 192 of 281 spawns were followed by `wait` with no other call between, at 82 of them with four or more todo items open | `hooks/tezgah_integrity.py::ready_left` | `tests/test_integrity.py::test_a_ready_todo_step_left_is_refused_once` |
| `open todo` | the owner's report (2026-10-12, plan 097 item 2): `ready_left` counted only `pending` items, so a done claim over an `in_progress` todo item ended the turn | `hooks/tezgah_integrity.py::open_left` | `tests/test_integrity.py::test_a_done_claim_over_an_in_progress_todo_is_refused_once` |
| `needless ask` | research line `orchestrator-flow-audit` S3: 33 of 48 final replies that ended on a question in the owner's omp transcripts were process questions ("Başlayayım mı?"), and 9 of 47 next prompts were a bare "devam" or "evet" | `hooks/tezgah_integrity.py::needless_ask` | `tests/test_integrity.py::test_a_process_question_at_the_end_is_refused_once` |
| `stopped slice` | measured 2026-10-11 (research line `subagent-resume-orchestration`): 118 of 1413 omp subagent runs ended stopped, and in the newest 20 the parent absorbed the work inline 16 times instead of resuming it | `hooks/tezgah_integrity.py::_stopped_slice` | `tests/test_integrity.py::test_a_stopped_slice_of_this_session_refuses_the_turn_once` |
| `handed step` | measured 2026-10-29 on the owner's top-level omp and Claude transcripts: of 3307 user turns, 27 replies handed the reader a command in backticks, 21 of them steps the ask policy keeps (consent, publish, release, install, an OTP) and 6 steps the session could have taken, none refused by any class; the `needless ask` refusal pushes the same step out of a question and into prose. The shipped shapes refuse 14 of those turns, 12 of them a real handover (the review of plan 142 cut "you can run", which refused an answer about how a command is run) | `hooks/tezgah_integrity.py::handed_steps` | `tests/test_integrity.py::test_a_handed_step_is_refused_once` |
| `plan claim` | probe 2026-10-29: a read-only plan turn whose reply claimed "test ettim" ended the turn, because every evidence class needs a work row and plan mode produces none; the same mode's approval question was refused as `needless ask` | `hooks/tezgah_integrity.py::READ_ONLY_MODES` | `tests/test_integrity.py::test_a_done_claim_in_plan_mode_is_refused` |
| `placating opener` | designed | output rule 10 read at the Stop event; no incident recorded | `tests/test_integrity.py::test_sycophantic_opener_blocks` |
| `forbidden closer` | designed | output rule 10 read at the Stop event; no incident recorded | `tests/test_integrity.py::test_a_closer_from_the_skills_own_list_blocks` |
| `list cap` | designed | output rule 8 read at the Stop event; no incident recorded | `tests/test_integrity.py::test_a_list_over_the_cap_blocks_with_its_size` |
| `reply language` | measured 2026-09-19: the 161 final replies the claim vocabulary was read off | `hooks/tezgah_integrity.py::DONE` | `tests/test_integrity.py::test_english_prose_blocks_and_names_the_language` |

## Adding a rule

1. Write the check inside `decision` (`hooks/tezgah_gate.py::decision`). A rule is a function returning a `str` reason or `None`; keep an argument-shaped rule
   above the repeat guards (`hooks/tezgah_gate.py::decision`) — the drift refusal stays last among the built-in rules, followed only by the repo rule below — and put its constants beside its own section.
   A citation into this file names its symbol, so moving code inside it shifts nothing. Renaming or removing a cited symbol does, and `bin/tezgah-docs --citations`
   flags it - re-run it in the same pass as the suite and re-anchor what it flags.
2. Return through `_deny(session_id, "<rule>", reason, tool, inp, base)` so the ledger counts the refusal (`hooks/tezgah_gate.py::_deny`); gate it on the kill switch it belongs
   to (`off(...)`), the way the shortcut and repeat rules use `verify-off` (`hooks/tezgah_gate.py::decision`). The rule name is now a record too: add its row to
   [Rule provenance](#rule-provenance), or `bin/tezgah-docs --citations` refuses the rule for having none.
3. Extend `tests/test_gate.py`. It drives the real function through `tests/_probe_gate.py` (`tests/support.py::PROBE_GATE`), which also carries the `capture_log` stub
   standing in for `tezgah_gate.capture` on the allow path (`tests/_probe_gate.py:21-31`). Only if the refusal envelope changes, touch
   `tests/test_claude_adapters.py::PreToolUse` and the codex/cursor/omp hook tests.
4. Mirror the rule in `hosts/opencode/plugins/tezgah.js` and extend `tests/test_opencode_plugin.py` with its cases; that suite is where the two halves are
   compared and where a shared-vocabulary drift fails.
5. Add the rule's vectors to the shared corpus `tests/gate_vectors.json`. Its `owner` field says who keeps it. Write one call per route the rule reads, with the
   verdict the core gives it. `tests/test_gate_vectors.py` sends each vector through every host's own entry point, under the tool name that host uses.
   A host gets the call only when its own matcher routes that name (`hooks/hooks.json`, `hosts/dsh/hooks.json`, `hosts/codex/hooks.json`, `hosts/cursor/hooks.json`,
   omp's `GATED` list). A cell that disagrees with the core fails the suite. The corpus may name it a ceiling, with the plan that closes it. A ceiling that agrees fails too.

### A repository's own rule

A repository adds a refusal without editing the harness: it commits a Python file at `<repo>/.tezgah/gate.py`, run with the gate's own interpreter (`hooks/tezgah_gate.py::repo_rule_reason`).
The gate finds it with the status line's walk - nearest above the call's cwd, at most `MAX_WALK` levels, never above the configured root (`hooks/tezgah_gate.py::repo_rule_path`). A repo without one pays one `isfile` per level and no fork. Both it and the manifest are control plane (`hooks/tezgah_gate.py::_target_label`): the session stages them and the user's own terminal owns them.
The file runs only when it is in the git index of the repository that holds its directory - the project's, or the workspace's own `.tezgah` repository (`git ls-files --error-unmatch`, `hooks/tezgah_gate.py::_indexed`). An uncommitted drop is inert, and staging it is enough.
The file runs as a bounded child in the repo root, with one JSON object on stdin: `{"api": 1, "event": "pretool", "cwd", "repo_root", "session_id", "tool", "input"}` (the extension envelope, `hooks/tezgah_extension.py::call_envelope`, plus the call).
It answers `{"deny": "<reason>"}` on stdout to refuse, and nothing to allow. The reason reaches the agent cut to 600 characters (`hooks/tezgah_gate.py::REPO_RULE_CAP`). It opens with `Repository-supplied rule:`. A line then says the text is the repository's data, not tezgah's instruction (`hooks/tezgah_gate.py::REPO_RULE_DENY`). The labelled text leaves a `deny` row under `repo-rule`.
Fail-open: a non-zero exit, a timeout (1000 ms, `hooks/tezgah_extension.py::DEFAULT_TIMEOUT_MS`) and malformed output allow. The rule runs after every built-in refusal, so a built-in one wins and the repo rule only adds. `pretooluse-off` drops it with the whole gate. `TEZGAH_REPO_RULE=0` in the hook's environment skips it alone, before any fork (`hooks/tezgah_gate.py::REPO_RULE_VALVE`).
The dry check (`tezgah-gate check`) runs it too, since it is part of `decision`. What the file can do is in [SECURITY.md](../SECURITY.md#threat-model).
opencode runs the same file, with the same envelope, index check, valve, cap and label (`hosts/opencode/plugins/tezgah.js`, `repoRuleReason`). It does so when the core was not asked.
Its interpreter is the plugin's `pythonBin()`, not the gate's `sys.executable`. That is `TEZGAH_PYTHON`, else the first of `python3`, `python`, `py` on PATH.
The opencode classifier does not read the manifest's `checks`, so a declared check records there as a plain run. That is a lost credit, never a false one.

## Source of truth

- `hooks/tezgah_gate.py` — `hooks/tezgah_gate.py::decision`; every rule constant and refusal text `hooks/tezgah_gate.py::DENY_RULES`, `hooks/tezgah_gate.py::SECRET_DENY`, `hooks/tezgah_gate.py::SECRET_EDIT_DENY`, `hooks/tezgah_gate.py::SECRET_ADD_DENY`, `hooks/tezgah_gate.py::MCP_SECRET_DENY`, `hooks/tezgah_gate.py::EXPLORE_DENY`, `hooks/tezgah_gate.py::ATTRIB_DENY`, `hooks/tezgah_gate.py::RACE_DENY`, `hooks/tezgah_gate.py::RACE_WHO`, `hooks/tezgah_gate.py::LEASE_DENY`, `hooks/tezgah_gate.py::MAIN_CHECKOUT_DENY`, `hooks/tezgah_gate.py::TASK_PHASE_DENY`, `hooks/tezgah_gate.py::TASK_SCOPE_DENY`, `hooks/tezgah_gate.py::TASK_SCOPE_OUTSIDE`, `hooks/tezgah_gate.py::TASK_RECORD_DENY`, `hooks/tezgah_gate.py::TASK_SHELL_DENY`, `hooks/tezgah_gate.py::CHECKPOINT_DENY`, `hooks/tezgah_gate.py::WORKSPACE_DENY`, `hooks/tezgah_gate.py::ORDER_DENY`, `hooks/tezgah_gate.py::DRIFT_DENY`, `hooks/tezgah_gate.py::CONTROL_DENY`; `attribution`/`attribution_edit` `hooks/tezgah_gate.py::attribution`, `hooks/tezgah_gate.py::attribution_edit`; `explored`
  `hooks/tezgah_gate.py::explored`; `hooks/tezgah_gate.py::searched_symbol`, `hooks/tezgah_gate.py::index_slug`, `hooks/tezgah_gate.py::first_nudge`, `hooks/tezgah_gate.py::nudge_reason`, `hooks/tezgah_gate.py::graph_advice`; `hooks/tezgah_gate.py::LOOP_ATTEMPTS`, `hooks/tezgah_gate.py::loop_reason`,
  `hooks/tezgah_gate.py::RETRY_CEILING`, `hooks/tezgah_gate.py::retry_reason`; `hooks/tezgah_gate.py::secret_command`, `hooks/tezgah_gate.py::race_reason`,
  `hooks/tezgah_gate.py::drift_reason`, `hooks/tezgah_gate.py::effectful`, `hooks/tezgah_gate.py::_deny`; the plan rule's own section `hooks/tezgah_gate.py::PLAN_TRUNKS`, `hooks/tezgah_gate.py::PLAN_SKIP`, `hooks/tezgah_gate.py::PLAN_AGENT_HOSTS`, `hooks/tezgah_gate.py::PLAN_WRITES`, `hooks/tezgah_gate.py::PLAN_MERGING`, `hooks/tezgah_gate.py::PLAN_BIND`, `hooks/tezgah_gate.py::PLAN_BIND_TRUNK`, `hooks/tezgah_gate.py::_gitdir`, `hooks/tezgah_gate.py::_head`, `hooks/tezgah_gate.py::_merging`, `hooks/tezgah_gate.py::_unplanned` — `hooks/tezgah_gate.py::plan_reason`, `hooks/tezgah_gate.py::_branch`, `hooks/tezgah_gate.py::_checkout`, `hooks/tezgah_gate.py::_product`, `hooks/tezgah_gate.py::PLAN_DENY`; `hooks/tezgah_gate.py::write_paths`, `hooks/tezgah_gate.py::shell_target`, `hooks/tezgah_gate.py::SHELL_AS_WRITE`; the `capture` call `hooks/tezgah_gate.py::decision` (a write tool's target, and a shell write's)
- `hooks/projects-pretooluse.py` — the Claude and dsh envelope; `hooks/tezgah_paths.py` — `off`, `root_for`, `cache_dir`
- `hooks/tezgah_integrity.py` — `hooks/tezgah_integrity.py::WRITE_TOOLS`, `hooks/tezgah_integrity.py::BASH_TOOLS`; `NEUTER`/`SKIP_ENV`/`NO_VERIFY`/`GITISH` `hooks/tezgah_integrity.py::NEUTER`, `hooks/tezgah_integrity.py::SKIP_ENV`, `hooks/tezgah_integrity.py::NO_VERIFY`, `hooks/tezgah_integrity.py::GITISH`; `HOOKS_KEY`/`GIT_VALUE_OPTS`/`CONFIG_READS`/`ROUGH_WORDS` `hooks/tezgah_integrity.py::HOOKS_KEY`, `hooks/tezgah_integrity.py::GIT_VALUE_OPTS`, `hooks/tezgah_integrity.py::CONFIG_READS`, `hooks/tezgah_integrity.py::ROUGH_WORDS`; `hooks/tezgah_integrity.py::SKIP_TEST`; `TEST_PATH`
  `hooks/tezgah_integrity.py::TEST_PATH`; `hooks/tezgah_integrity.py::call_id`; `hooks/tezgah_integrity.py::_path`, `hooks/tezgah_integrity.py::note`, `hooks/tezgah_integrity.py::events`, `hooks/tezgah_integrity.py::writers_elsewhere`, `hooks/tezgah_integrity.py::mask`, `hooks/tezgah_integrity.py::shortcut_command`,
  `hooks/tezgah_integrity.py::shortcut_edit`
- `hosts/opencode/plugins/tezgah.js` — the JavaScript mirror
- `bin/tezgah-docs` — the rule-ledger check (`ledger_failures`) that reads this page's provenance table; `tests/test_docs.py` drives it
- `tests/test_gate.py`, `tests/_probe_gate.py`, `tests/test_opencode_plugin.py`, `tests/test_claude_adapters.py`
