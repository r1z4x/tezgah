# Changelog

All notable changes to this project are documented here. The format is based on
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project
adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Changed

- **The temporal spec decides the Stop rule's evidence classes.** Its shadow run agreed on all 420 live Stops it reached. `_stop_block` now asks `tezgah_stopspec`, and the refusal texts stay the same. The `stop_spec` shadow row and `TEZGAH_STOPSPEC_STRICT` are gone. `tests/stop_spec_eval.py` keeps only `--mutants`, and the neuter workflow also runs on a change to the spec.
- **A claim needs a check someone saw pass.** A done or tested claim over a `verify_ok` row with no passing output now owes `no verify_ok`. An earlier pass and a turn of git bookkeeping no longer excuse it.
- **A research, analysis, review or plan ask ends at the plan.** The contract now says so. Building that plan is a question in the approval batch, and a finding outside the ask becomes a plan, not code.
- **No plan, no third product file, on any branch.** The no-plan rule held only `main` and `master`. It now holds every branch that no open plan binds, so an Orca worktree on `r1z4x/<name>` meets it too. A worktree on the branch a plan names in `branch:` answers to that plan, as a `plan/NNN-*` one does.

### Fixed

- **A bare repository's worktrees share one workspace.** It lives in the bare git directory, `<bare>/.tezgah`, and each worktree's `.tezgah` links to it. No `git worktree remove`, detach or branch switch removes it, and a plan worktree there is held to its plan. Commands read project files in the worktree they run in. That covers the checkpoint, research files and claims, the arena evaluator, the merge checks and `tezgah-taste mine`. A bare repository with one worktree prints no worktrees line.
- **`close` prunes a worktree whose `.tezgah` is a link.** It read the link to the workspace as the worktree's own data and kept the worktree. The merge step's deferred checks are now looked up in the plan's own worktree when one holds the plan.
- **A plan worktree moves only its own plan's record.** In a `plan/NNN-*` worktree whose plan is not active, `allow`, `phase` and `stop` refuse. They used to change the main checkout's first phased plan.
- **`close` prunes a worktree of generated files.** Managed agent files and the `.codegraph` index regenerate, so they keep no landed worktree. Any other ignored file still keeps it. So do a FIFO, a directory link and a directory `close` cannot list.
- **A Ctrl-C as an installer starts still stops it.** `--deps` armed its group kill only after the installer had started. A Ctrl-C in that gap left the installer running on its own, and a test timed out on it under load.
- **`close` drops the branch of a worktree Orca removed.** Orca answers before the checkout is gone. Git then refused to delete the branch, and close printed `branch kept`. Close now waits up to 10 seconds for the directory to go, and names a checkout still there as kept.

## [1.8.3] - 2026-10-13

### Changed

- **A release reuses the green CI of its commit.** It waits for the push run of `ci.yml` on the same commit to finish. It skips its own CI run only when that run succeeded, which saves about 12 minutes. Any other outcome runs CI as before.
- **Fewer full-suite runs.** A change under `.tezgah/` runs no test module, and a workflow file runs the modules that read it. Both used to run all 100. Two large runs on one machine now take turns instead of slowing each other down.
- **A worktree shows the main checkout's `.tezgah`.** Session start in a linked worktree makes its `.tezgah` a link to the main checkout's workspace. A relative `.tezgah/...` write from a worktree session or subagent now lands there. It used to create a second `.tezgah` that `git worktree remove` deleted.

### Fixed

- **A release re-run no longer fails on a current Homebrew formula.** The tap job committed even when the formula already named the version. So a re-run stopped with "nothing to commit". It now commits and pushes only a change.

## [1.8.2] - 2026-10-13

### Fixed

- **The v1.8.1 release builds.** A packaging test still pinned the serial suite step that 1.8.1 removed from CI. So the release workflow stopped before it built the artifact. `tests/impacted.py` no longer crashes on a deleted test module. Each neuter fall-through module runs in its own HOME, as the control does.

## [1.8.1] - 2026-10-13

### Changed

- **The neuter matrix runs in CI, and in minutes.** Each mutant first runs the one test that killed it last time, kept in `tests/neuter_killers.json`. A full search runs only when that test passes. A cached run took 240 s, against about an hour before. CI runs it on a push that changes a guarded file, and weekly. A session checks a new rule's mutant with `--only <name>`.
- **The suite is faster.** It starts the largest modules first. Slow tests share their expensive installs per class, and one test now covers each duplicated path. A change under `benchmarks/arm-bench/` runs that lab's module, not all 100.
- **CI runs the suite once per Python.** The serial `unittest discover` step is gone. The sharded job runs the same modules, and both caught the same failures. A push to `main` now takes about 11 minutes, not 30.

### Fixed

- **A checkout under the temp dir is not scratch.** The gate treated any path under the temp dir as scratch. So the task scope, the race rule and the main-checkout rule skipped it, and a plan worktree there let a write outside its scope pass. A file inside a git checkout now meets those rules, and a plain temp file stays scratch.
- **The test suite runs on CI runners.** A fixture had no git identity for the record commit that `close` now makes. The opencode capture test read only the SQLite ledger, so it missed the rows node 20 writes to the legacy file.

## [1.8.0] - 2026-10-13

### Changed

- **Typed worker output and a recall hop.** Tier workers and `tezgah-tester` now end their report with an `Output to orchestrator` block. It comes after any other shape the session asks for. A worker lists changed files, the commit sha and the `ESCALATE:` reason. For each check it gives the command, the exit code and the last lines of its output file. The tester gives pass, fail and skip counts and the first failure verbatim. A report that misses a field, or an `ESCALATE:`, gets one narrower re-brief of the same role. Only a second miss goes to `tezgah-frontier`, with the original brief and a fresh start. This ships as text only. An h05 spike on omp+tezgah spawned no subagent, so the arm-bench pilot could not measure it. No default changed.
- **A route joins the workers it actually started.** `tezgah-route --report` used to drop a route when the session spawned unrouted workers of its type. It also dropped a route whose one task call started several workers. A route now owns the first task call of its type after it. One failed first check in that call fails the route. A task call more than 30 minutes after its route stays unjoined. Two routes before one shared task call stay unjoined, since the report cannot tell whose worker is whose. On this machine 6 of the 10 real omp routes now join, up from 1.
- **On Claude Code, `tezgah-task` now reads the session id.** Claude's shells now carry `TEZGAH_SESSION`, as omp's do. So the review guard counts only this session's slice records. A bare name in `slice board`, `slice done` or `slice resume` now matches only this session's or unowned records.
- **A key passed to a script as an environment prefix is no longer refused.** `API_KEY="$(cat key)" python3 tool.py > run.log` now passes, since the key reaches only the program's environment. Only a script runner given a script file qualifies. A trace or verbose option, a startup or trace variable, `/proc/*/environ` or a function defined on the line holds it. A later printer that reads a key assigned earlier on the line is now refused too. The opencode plugin answers the same.
- **One `.tezgah` per repository, in its main checkout.** A session or CLI in a linked worktree now reads and writes the main checkout's `.tezgah`. That covers the session context, research lines, decisions, lessons, taste and the design contract. Before, `git worktree remove` deleted research lines and lessons written there. A worktree's session also never saw the lessons or open plans. `tezgah-research import` moves a line left in an old worktree workspace.
- **Any `plan/NNN-*` branch answers to plan NNN.** A plan's slice worktrees on their own `plan/NNN-*` branches now meet that plan's phase and allowlist. When every phased plan is held by a worktree, the main checkout has no active task. It used to take the first held plan's scope.
- **`tezgah-task close NNN done` refuses an open Acceptance item.** It names each unticked item that carries no `UNMET: <reason>`. `--resolved` does not lift it, and `discarded` still closes freely. Close also records the `landed:` commit once main holds the work, and commits the moved record in the private `.tezgah` repository.

### Added

- **Claude Code, Codex and Cursor routes can join their workers.** On Claude and Codex, SubagentStart writes a `subagent_start` row. It names the child's id and type, and it goes into the parent's ledger. Claude's SessionStart exports `TEZGAH_SESSION` through `CLAUDE_ENV_FILE`. On Codex, `tezgah-route` writes under the shell's `CODEX_THREAD_ID`. On Cursor it writes under `CURSOR_CONVERSATION_ID`. Cursor's subagentStart opens the child's ledger with a row that names the parent conversation. The report counts that link only after the child writes a row of its own. `cursor-agent` fires no subagentStart, so its routes stay unjoined, and so do dsh routes.
- **Two plans at once, one worktree each.** A linked worktree on a plan's own `branch:` now answers to that plan's phase, allowlist and checkpoint. This holds for a session inside the worktree and for a write into it from anywhere else. `tezgah-task start` keeps another plan's phase only when both plans run in their own worktrees on disjoint scopes. Otherwise it clears the others as before. The main checkout reads the first phased plan no worktree holds. A worktree on any other branch reads the main checkout's task. `allow` and `phase --any-path` refuse a scope that a held plan could share. The CLI takes a pending checkpoint from the plan's own worktree, and its refusal names `git -C <worktree>`. `tick`, `note`, `spike`, `review` and `close` run from any worktree. `review` records the plan worktree's HEAD, and the verification steps print `git -C <worktree> diff`.
- **`tezgah-task spike NNN "<answer>"`.** It writes `spike_recorded:` on an open plan, active or not. `phase implementation` then passes, with no stop, hand edit and restart.
- **A forced-delegation arm and 20 harder tasks for arm-bench.** `omp+tezgah-delegate` hands every edit to the worker `tezgah-route` names, so a run exercises the role text. One paid arming run verified it. `block.py` takes task globs and `--dry-run`. Tasks x01-x20 cover hidden invariants, sites a grep misses, spec edge clauses and long sweeps. On deepseek-v4-flash they passed 99 of 100 runs, so they stay as a regression corpus.
- **The Stop rule holds a done claim over an in-progress todo item.** The new `open todo` class names the open items. Finish them, mark them done, or type each one with its blocker. A step a running slice works on passes. A Cursor `merge: true` list is partial, so the class skips it.

### Fixed

- **A route row never lands in another host's ledger.** A host started from another host's agent shell inherits that host's session id. `tezgah-route` now writes no row when its three session variables name different sessions. Such a route counts as unjoined.
- **A Codex subagent's repeat limits count only its own attempts**, as on Claude. The root's next try no longer fails for the subagent's attempts.
- **A shell line is read target by target.** Each redirect and `tee` target meets the phase, allowlist and checkpoint of the plan it lands under. Some lines also meet the task where the session runs. That holds for a line with more write shapes than read targets. It also holds for a positional writer such as `cp` or `sed -i`. So `tee <plan worktree>/a README.md` no longer escapes a reading phase. Two redirects into one plan worktree meet only that plan.
- **Two edits cannot give a plan a phase.** The gate judged an edit to an open plan by its new string alone. So `xphase: implementation` and then `xphase` -> `phase` both passed. It now judges the plan's text as it will read after the write.
- **The plan record is the record in any case and from any checkout.** The gate refuses a write to `.TEZGAH/PLANS/open/<plan>.md` as a record write. It refuses a write to any phased record from a session in a linked worktree too.
- **A slice keeps its own plan.** Its tag comes from its `plan/NNN` branch first. Next comes `plan NNN` in its brief or shared context, then its earlier tag. A re-open with no brief keeps the tag.
- **`tezgah-task close` run inside a landed worktree keeps that worktree.** The session's own directory is no longer removed from under it.
- **arm-bench's arming proof reads the evidence store.** `session_rows` and `stop_classes` read the old JSONL ledger, which the hooks no longer write. So every arm recorded 0 and `{}`, armed or not. Both now read the SQLite store, as `counters` does. A fixture copy also leaves out stale `__pycache__` and bytecode.
- **The task rule holds repository paths only.** Some writes land under no git checkout and no configured root, such as a user's `~/.config/runpod/key`. Those no longer meet the active plan's phase, allowlist or checkpoint. The secret rule and every other rule still read them. A target in another repository is still refused. Any doubt holds the write. That covers a line that moves the directory or reads `$PWD`, and a line that makes a link. It also covers a target whose parent does not exist yet and a file with a second hard link. Host agent and instruction files and shell rc files stay held too, in any letter case.
- **`tezgah-task` exits cleanly when its reader leaves early.** `tezgah-task stop | head -1` prints no traceback. It finishes its work and keeps its own exit code, buffered or under `PYTHONUNBUFFERED=1`.
- **Nothing inside `.tezgah` treats it as a project.** The workspace keeps its own `.git`, so git named `.tezgah` itself as the top level there. Session start then set up `.tezgah/.tezgah`, agents and a graph index inside it. The plans table renderer wrote `.tezgah/.tezgah/plans/README.md`. Every resolver now maps a path inside `.tezgah` to the repository around it.
- **Plan records survive concurrent writers.** `tick`, `note`, field writes and `close` hold a lock on the plans directory and replace the file atomically. A reader saw a torn record in 29 of 40 rounds before. `tick` now finds its item under the lock.
- **The slice journal closes a landed slice whose worktree `close` removed.** `reconcile` no longer names the main checkout's HEAD as a removed worktree's last commit.
- **`close` deletes a squash-merged plan branch.** It used `git branch -d`, which refuses a squash merge, and dropped the error. It now deletes with `-D` only after proving the branch landed, and names a branch it keeps.
- **Two worktrees can commit to the private `.tezgah` repository at once.** In a fixture, a busy `index.lock` failed 11 of 19 close commits. Close still exited 0. Commits there now wait out a short lock, and close exits 1 when its record commit fails.

## [1.7.0] - 2026-10-12

### Added

- **Exploratory research lines (rules 7).** An ask for new ideas, methods or approaches now gets a campaign: `tezgah-research init --method exploratory`. Its arena holds the problem and a budget, and the line's scope says what it covers. A measurable arena adds an evaluator, its sha256 and its metric. The session commits the arena before the first idea. `idea`, `stage` and `match` append `ideas.jsonl`, `stages.jsonl` and `tournament.jsonl` under the lock. One function judges each row type for the writer and for `check`. An idea moves forward only, and each stage needs the one before it: prior art, then screening, a pilot, a full run and a confirmation. A kill with a reason ends it at any stage, and a duplicate ends in a kill. Prior art needs three indexed nearest works and a verdict, and `known` kills the idea in the same append. `check` refuses ideas or results committed before the arena and an arena changed after it. It refuses every stage row while the evaluator hash differs. It also refuses a confirmation on the promoting run. The same goes for a set another idea looked at first, or one this idea looked at before its promotion. It warns about thin judging and about a report that hides how many ideas it tested. `board`, `dedup` and `yield` are reports. `board` gives a Bradley-Terry prior and each idea's next action, and it is the resume point after a crash. `dedup` names its backend, embed-mrl or BM25. Its thresholds come from 40 fixture pairs and 400 human-labelled MRPC pairs. `yield` counts per operator and model family. Lines opened under rules 1-6 read none of it. The research paragraph armed per turn grows by 149 characters, and the on-demand research rule by 593.
- **An ask policy.** One class table in the contract now says what is asked at all. Work and process steps, a local merge of the session's branch included, are taken, never asked. A push or a release runs on a grant the user wrote in chat ("bana sormadan pushla") and is otherwise asked once. A force push, a delete, production, a credential or a spend over the new `spend_cap` setting waits for an answer. Every other question goes in one "Onay için sorular" batch with a recommended default, and the work goes on with the defaults. A new Stop class, `needless ask`, refuses once per turn a reply that ends on a question the agent can decide. A KARAR item with no options or default is no blocker any more. An omp `ask` or Claude AskUserQuestion question with no recommended option gets a warning, never a deny, and leaves an `ask` row. Each prompt's grants and lifts leave `grant` rows. `tezgah-gate replay` prints four new counts: process questions, cheap answers, ask-tool questions without a default and outward turns without a grant.
- **Language packs.** The detection words now live in data files, one per language: `hooks/lang/en.json` and `hooks/lang/tr.json`. They cover claims, admissions, openers, closers, residual labels, blocker tokens, prompt hints, constraint shapes and ranking stopwords. Every reader compiles the union of the packs, so a third language is one file. On a corpus of 45,810 test, doc and transcript strings, the en and tr packs answer as the inlined regexes did.
- **`language` and `--language`.** The reply-language setting is `language` in `config.json`. An older `reply_lang` is still read and never rewritten, and `--reply-lang` still works. A first install takes the locale (`LANGUAGE`, `LC_ALL`, `LC_MESSAGES`, `LANG`), and a locale with no pack gives English. An install over a config with neither key writes `tr`.
- **A router context nudge.** The prompt hook reads the router's newest input-side token count from the transcript. This works on omp, Claude and Codex, and omp now hands its session file to the prompt hook for it. At 700 k or more it adds one line, once per session until a compaction. The line says to push heavy reads and check output through a slice, or to run `/compact`. The threshold sits just under the measured p90 of 724 k. `orchestrate-off` silences it. The contract skill now says heavy check output goes through a reader slice. The disarmed-gate check now reads omp's transcript too.
- **An ownership lease on every delegated slice.** `Owns:` lines in a brief
  name the globs only that slice writes. They sit on the line or as `- glob`
  items under it. The journal stores them as `owns`. The gate refuses a
  sibling's write into them while the owner runs. A brief may declare its
  worktree on a `Worktree:`, `Checkout` or `Cwd:` line. The gate then refuses
  that slice's write into the main checkout, the shape two wave-1 slices hit
  with relative paths. A shell target resolves against the call's own `cwd`
  and its `cd` or `pushd`. A path the brief only names declares nothing, so an
  integrator that lists worktrees to remove still works in the main checkout.
  The journal keeps that named worktree for reconcile, resume and the board.
  The refusal names the owner, its globs, how to reach it - omp `write
  agent://<name>`, Claude `SendMessage`, else the parent - and the
  `tezgah-task slice done <id>` that frees it. `.tezgah/` and scratch stay
  free. A closed owner frees its files. A reader agent holds no lease. omp
  maps a writing session to its
  record through its ledger's `spawned` row. A Claude background child maps
  through the `agentId` its launch result names, and its SubagentStop closes
  the record. Every other host fails open. `tezgah-task slice board` lists one
  parent's open slices with their lease, worktree, branch and last commit.
  `slice merge-plan` puts a branch touching MANIFEST or the citation baseline
  last. It orders the rest by their forecast `git merge-tree` conflicts and
  leaves CHANGELOG.md to its union driver. It names a branch it cannot
  forecast and exits 1. A spawn whose writing slices name one worktree gets a
  warning. The orchestration text now tells every writing brief to name
  `Owns:` globs and declare its worktree. It gives the shared append points to
  the integrator. Siblings message each other only on an interface or
  ownership change. `orchestrate-off` and `slices-off` disarm it.

- **`CHANGELOG.md` merges with the union driver.** A new `.gitattributes` keeps both branches' lines, so parallel slices no longer conflict on the `[Unreleased]` head.
- **The todo list is the orchestrator's step queue.** The orchestration text, the fan-out rule and the orchestrator agent say to dispatch every ready step at once, mark each dispatched step blocked on its slice and never `wait` while a step is ready. Once every open step waits on a running slice, `wait` and ending the turn are both fine. The per-turn checks still run in the turn, and only the heavy tier joins at merge. Every host's todo call now leaves a `todo` ledger row with its open, ready and blocked counts and the ready heads: omp `todo` and `wait` are watched, Claude and dsh `TodoWrite` joined the PostToolUse matcher, opencode records `todowrite`, and Cursor `todo_write` and Codex `update_plan` arrive with no matcher. No pre-tool rule reads a todo call, so only omp's `wait` reaches the gate. A `ready steps` Stop class refuses, once per turn, a turn that did work and ends while the session's newest todo list holds a ready step the reply neither did nor named beside KARAR, YETKİ, GERİ ALINAMAZ or ORTAM. A step an open slice of the session works on is not ready, and a subagent's own list never counts. An omp `wait` right after a spawn, with ready steps open, gets a warning with its result, never a block.
- **`tezgah-task tick` and `tezgah-task note`.** `tick NNN <n>` ticks Acceptance item n, and `--undo` unticks it. `note NNN state|next "<text>"` replaces the newest State body or the Next body. Both work on any open plan and commit nothing. The gate refuses a direct write to the active plan, so an agent used to report a box it could not tick as a blocker. The refusal now names both commands.
- **The subagent model chain follows provider health.** A family whose provider answered a limit leaves omp's chain until its reset. The reset is read from a `429 ... reset at` or a `retry-after-ms`. An OpenRouter key with no limit left is down too. `tezgah-route --health` probes the other families, records the downs and re-applies the chain. Session start and each prompt start it in the background when it is due. `tezgah-route --fallback vendor|any|none` sets which families a chain may fall back to. Under `any`, zai comes before OpenRouter for every agent. Before, any credential counted as funded, so subagents fell back onto a key past its limit.
- **A `residual work` Stop class.** A turn that did work can no longer end on a list of what is left, such as "Açık kalanlar", "Doğrulanmadı:", "Sıradaki adım", "TODO" or "Next steps". The Stop rule refuses it once with "Bu maddeleri şimdi yap veya engel türü ve kanıtla yaz." An item stays when it names KARAR or GERİ ALINAMAZ in capitals. It also stays when it names YETKİ or ORTAM in capitals and quotes a command that failed in the turn; the type or the quote alone does not keep it. A label that closes itself ("Düzeltilen eksik", "Doğrulanmayan kalmadı"), a risk, and "kalan" as an adjective ("Kalan riskler", "Kalan süre") open no list. A turn with no work, a subagent's end and a nested session stay unjudged. Such a refusal counts in `blocked_claims` but not as a false completion. Before the class, 503 of 1876 final replies carried such a label, 467 of them in turns with work.
- **Trap cases for doable work listed as open.** The EVALS of tezgah-contract, i-have-adhd and ponytail each gained one.
- **Held-out, repeat and noise-band warnings (rules 6).** A measured line may name `evaluation.held_out` and log each look at it in `held_out_log.jsonl`. It may also declare `evaluation.noise_band`. `check` warns when a decision picks and reports a variant on the same cells. It warns when one candidate looks at the held-out set twice. It warns when an armed experiment runs once per arm. It warns when `capability_tolerance` has no measured band, or a wider one. None of these refuses, `--strict` included.
- **`tezgah-gate replay --split search|holdout`.** A stable hash of the session id picks the side. Tune a gate threshold on one side and report it on the other. The report names its side.
- **A `lesson_changed` ledger row.** Rewriting or removing a `.tezgah/lessons.md` line now leaves one row per line. The row holds the old line's key and its redacted text. Taint does not matter, and it never refuses.
- **`tezgah-doctor --repair-evidence`.** It finds sessions whose legacy ledger file went into the store more than once and counts the extra rows. Each import offset row of a file is one import, so a file imported three times keeps one copy, not two. A row written to the database directly beside the copies stays. `--apply` backs the database up first and deletes the copies in one transaction. It counts the rows against the plan before the commit and rolls back, exiting 1, if one is missing or left. It leaves a session whole for manual review when the session holds a line fewer times than its imports put it in. It names a file that is gone and skips it.
- **A slice journal for delegated work.** Each spawned subagent slice gets one row in `.tezgah/slices/slices.db`, a SQLite file opened like the taste store. The first open imports an older one-file-per-record journal once and deletes it. A crash, an omp `/clear`, a quota or 429 stop, or a model or host switch no longer loses it. The hooks open a record on every spawn call of omp, Claude, dsh, Cursor, Codex and opencode, and close it with a failure class. Session start lists the pending slices. `tezgah-task slice reconcile --prune` lists them with a resume brief and removes landed worktrees and branches. `slice resume` prints the native resume path or a re-dispatch brief that starts from the last commit. `slice stats` counts failures per class and host and names the lever for a repeating one. `slices-off` turns the journal off.
- **A SWE-Bench Pro split for arm-bench.** `benchmarks/arm-bench/swe_pro.py` samples public Pro instances and grades them with the official test script. Its `validate` checks that the gold patch passes and the base fails. The committed 3-instance sample validates 3 of 3.
- **A cross-project write notice.** A write into another repository than the session's cwd gets one line, once per session and target repository. The line says that repository's plans, lessons and slice journal do not apply to this session. It never refuses. A worktree counts as its main checkout. opencode does not show it yet.

### Fixed

- **A subagent's limit stop moves the routing at once.** A slice that stops on a quota or rate limit now holds its provider family down in the health record and re-applies omp's chain. Before, the next session start's probe moved it. A quota is held until its reset or six hours, a rate limit until its retry-after or ten minutes. The mode's own family still leads every chain. The record is re-read under a lock before each write. A YETKİ or ORTAM blocker that quotes a model provider's quota or rate limit is refused while another family the fallback setting allows is up. The refusal names that family. A GitHub or npm rate limit stays a blocker. The task gate's scope refusal prints the ready `tezgah-task allow` line with the current globs and the new path, and none for a path outside the repository. `RELEASING.md` ends with a local `tezgah-setup --refresh` and version read.
- **An English install no longer asks for Turkish tokens.** The contract and the Stop refusals name the blocker heading, the admission word and the four blocker tokens in the configured language: `Blockers`, `unverified` and DECISION/ACCESS/IRREVERSIBLE/ENV under `en`. Under `tr` they stay "Engeller", `doğrulanmadı` and KARAR/YETKİ/GERİ ALINAMAZ/ORTAM. The Turkish first lines of the residual, ready-step and stopped-slice refusals now come only with `tr`. The reviewer and orchestrator agents and `tezgah-task`'s review lines take the token from the same pack. The contract, plan-sync and i-have-adhd skills name both spellings. opencode's todo reader takes its tokens from the packs. The Stop rule accepts both spellings.
- **Spanish, French and Dutch prose no longer passes as Turkish.** The reply-language markers dropped de, da, en, ne, ya, her and mi. Those replies now score 0. No Turkish reply in the 4,003 judged corpus texts changed sides.
- **Another session no longer takes over a stopped slice.** The journal keyed a slice record by the agent name alone. A second session that spawned an unrelated `Fixer` re-opened the first session's stopped `Fixer`, which then left that session's resume line and its Stop rule. A same-named spawn under another brief now gets its own record, `Fixer-<sha1[:6]>`. The same brief from another session still re-opens the record. `slice done|stop|resume` takes an exact id from any session, so a crashed session's slice stays reachable. A bare spawned name answers only for this session under `TEZGAH_SESSION`. The review guard counts this session's records by id, agent or name, and its refusal prints the exact id. A slice whose brief works in another repository names it as `repo`, and its line says `(in <name>)`.
- **The race rule knows a session's own subagent and its fork.** A subagent stopped on a quota error. The rule then refused its parent's takeover for ten minutes. A subagent whose slice record closed after its last write of the file is now no race. A live one still is. The refusal now names how each writer relates to this session, such as your subagent or an omp fork. It used to print a bare ledger id. The omp hook records a fork's parent at its start.
- **The transcript miners read only the current repository.** `tezgah-taste mine` and `tests/replay_context.py` read every project under `~/Projects` by default. Another project's prompts and paths then landed in this repository's research data. Both now read the current repository. `--all-projects` reads every project. `mine` writes a pseudonym (`project-<sha1[:8]>`) for each mined repository, in its `repo` and `cwd` and in every prompt, in any case.
- **The resume block names this repository's last check.** A session that last ran a check in another project showed that check as this repository's.
- **The residual-list rule asks every turn it should.** On omp the reply after a Stop refusal sat in a turn of its own. A rewrite with no tool call skipped `residual work`, and a failure quoted from the refused turn did not count. That reply is now judged on the rows of every turn in the re-ask chain. A subagent's end is still never refused, but its `subagent_end` row counts the items no type accounts for. The parent's Stop refuses a reply that types none of its own. Claude and Cursor write that row from their subagent-stop events. omp's bridge now writes it from a task session's `agent_end`, into the ledger of the session that spawned the child, once per child. Codex, opencode and dsh still write none. A turn of known reads, such as `git status`, `tail`, `find`, `jq`, `sed -n`, `gh pr view`, `curl -s`, a read-only `sqlite3` or `ssh host ls`, no longer owes a check. A reader with a writing option or script, such as `find -exec`, `sort -o` or `curl -o`, still does, and so does any other command, a commit or an unknown program included. The labels gained first-person negatives ("Yapamadım", "Test etmedim"), "Yarım kalanlar", "Henüz kontrol edilmeyen", "Unresolved", "Still open" and a residual word alone on a line over a list. "Engeller: yok", an empty "Engeller" heading and a blocker item that reports itself gone ("… yoktu. Artık var.") hold no item. A YETKİ or ORTAM item now needs an error of its type, such as a missing tool or a 403. It also needs a quoted command that failed, or, for an item about a subagent or a provider, a spawn call of the turn that failed at the provider. An assertion, a grep alone that matched nothing, a bare "yok" or a failed edit no longer passes as one. A spent quota now classifies as a `user` failure.
- **A session lists only its own slices.** Every prompt listed each pending slice of the repository, so another session's stopped slices rode this session's context. The prompt now lists only the slices this session spawned and those opened by hand. The resume block at session start adds one line that counts the other sessions' slices. `tezgah-task slice reconcile` still lists them all. The `.tezgah` repository also ignores the journal now.
- **A device-id change no longer imports a ledger twice.** The store found a legacy file's offset by name, device and inode. After the volume's device id changed, every file went in again from the start, and most ledgers read every row twice. The store now resumes from the longest import under any device id, so an old id coming back imports nothing again either. It keeps one offset row per earlier import for the repair to count.
- **The task rule no longer refuses targets that are no project file.** It refused `write xd://<tool>`, `agent://X` and `conflict://2` as paths outside the allowlist. It refused `git diff > $B/x.patch` under the literal name `$B/x.patch`. It refused files in tezgah's own `.tezgah/` workspace. Now a URI, a shell target with an unknown variable and the `.tezgah/` workspace pass. A `file://` URI and a variable set to the checkout stay held. So do the slice journal and a plan file that could make itself active. The gate first expands a variable set earlier on the line. The record rule still refuses the active plan record, and `tezgah-task start`, `review`, `tick` and `note` take only an open plan.
- **The task allowlist reads linked worktrees.** The gate used to place a file in a linked worktree outside the repo root. It then refused every in-scope write there. The gate now matches such a file against the worktree's own top. A worktree of another repository stays outside.
- **The task allowlist expands `~`.** It read a `~/...` path as relative to the working directory. It then refused an in-scope file spelled that way. With a `**` allowlist it also let a write to the home directory through as a repo path. It now expands `~` first.
- **The plan and slow role fallbacks reach omp.** `apply_omp` wrote them under `retry.fallbackChains.fallbackChains.plan`, a key omp never reads. They now go under `plan` and `slow`, and `apply_omp` deletes the misplaced keys.

### Changed

- **The Stop rule judges the reply after a block.** The rule used to only record that reply, so a new fault in it went unjudged. Now the rule refuses it once more for a new class, one it has not refused in that turn. An example is a blocker list with no evidence after a `no verify_ok` refusal. A turn takes at most two refusals and never two of one class. The core counts them from the turn's ledger rows for Claude, Codex, Cursor and omp. On omp the block comes back as a new `turn` row, and a refusal row's `reask` key ties that row to its turn. Before, omp left that reply unjudged and unrecorded. A host's own flag decides only when the session has no turn row.
- **"doğrulanmadı" no longer ends a turn by itself.** The admission used to clear every Stop refusal, so writing it cost less than verifying. It now clears only a class whose repair is a check: check failed, partial failure, stale evidence and no verify_ok. It needs a check that ran and failed after the turn's newest change. It clears no ui_ok only when that failed check is the screen or design check itself, it never clears no external read or evidence tampered, and the tamper check now runs first.
- **Residuals are work, not a report section.** The Integrity paragraph carries this rule. Its label reads "Integrity: evidence, or a named blocker." It asks for every open item to be done now. An item that cannot be done stays as one of the four blockers, with its evidence, under one "Engeller" heading of at most three lines. The per-turn reminder carries the short form. Ponytail notes only a requested part the session cut. A reply ends on the one step only the reader can take, or on nothing. The decision-quality line no longer asks to name a skipped check: it asks to run every check the change reaches. The session fixes a minor review finding, and fix-later needs a user decision (KARAR).
- **The session budgets move with the core.** The residual rule added 1473 B to the core and 151 B to the reminder. `session_start` and `post_compact` go from 13000 to 14500 B, and `user_prompt` from 6000 to 6500 B.
- **Heavy checks run once, at merge.** In a turn the session runs compileall, ruff and the impacted tests of what changed. The full suite, neuter, both docs audits, `render_table.py --acceptance --strict` and the e2e scripts run once at the merge step and in CI. A replay of 522 turns keeps about 0.6 of the in-turn checks with no lost failure. The Stop refusals for stale evidence and a missing check now name `python3 tests/impacted.py --run <paths>`. `tezgah-task` lists the deferred checks as the merge step's one run, and CI runs `tezgah-docs --clarity` beside every citations step.
- **The session resumes a stopped slice instead of absorbing it.** The orchestration text and the orchestrator agent say so. A slice commits `wip:` after each step. The session resumes or re-dispatches a stopped slice, and `tezgah-task slice reconcile --prune` runs before the turn that merged slices ends.
- **Judge figures name their provider.** Each judge figure in `docs/judge.md` and `docs/models.md` now names its provider and model. Where the record does not say, the page says so. A figure does not carry over to another default.

## [1.6.0] - 2026-10-10

### Added

- **A data, metric or dashboard ask reaches the product rule.** "Bu veriye uygun bir metric dashboard tasarla" armed no rule before. A dashboard, chart or metric-choice ask now arms `product`, judged per clause. A code marker in the same clause, such as a metrics endpoint, keeps it out.
- **product-analysis chooses metrics.** It names a North Star and its input metrics. Each metric gets one record: goal, signal, definition, window, baseline and more.
- **Dashboard rules in design-contract.** The new `data-views.md` picks the chart for the question. It also sets the context, the window and the widget states.
- **feature-audit forward mode.** A feature not built yet gets its five matrices in `spec.md`. The audit after the build compares against it.
- **analyze-app writes the design measurement.** Nothing produced `measurement.json` before. The skill now gives its shape and the snippet that reads it.
- **The local skill search reaches design-library's entries.** The search now reads the entries a skill's `INDEX.md` lists, one row each.
- **The product-flow skill and `tezgah-research next`.** A new product capability now runs in a fixed order, from research to re-measure. Each step leaves a file under `.tezgah/analysis/<topic>/`: a `## <step>` note in `flow.md`, or `spec.md` for the forward spec. `tezgah-research next --topic <t>` prints each step's status from those files, and a re-measure is due once the decision's `observe after:` date has passed. It then names the first missing or due step's skill and command. The skill lists the steps, and `FLOWS` in `hooks/tezgah_product.py` holds their done rules.

### Removed

- **The product ledger is cut before release (ADR 025).** Plan 075's measured run did not show the ledger beating the playbook alone. Gone: writing and reading `.tezgah/product/ledger.jsonl`, `tezgah-research record`, `due` and `commit --product`, the ledger part of `check`, `product:` citations and the session-start note on due decisions. An existing `ledger.jsonl` is left in place, and nothing reads it.

### Changed

- **The session runs the plan lifecycle itself.** The gate refused a session's
  own `tezgah-task start|phase|allow|stop`. It told the session to ask the user,
  so every plan ended with a command handed back. That refusal is gone. A phase
  or scope refusal now names the move (`tezgah-task phase implementation`,
  `tezgah-task allow`). The CLI still checks Acceptance, the spike, the
  checkpoint and the review on each move. The gate still refuses a write to the
  plan file itself. `tezgah-task allow` now needs `--why`, and `status` prints
  the reason next to the widened scope.
- **`close` cleans up.** `tezgah-task close` on the active task clears its
  phase instead of refusing. It then removes each linked worktree whose branch
  has landed and which holds nothing else, through Orca when Orca tracks it. A
  squash merge counts as landed. A branch whose commits cancel out does not. It
  prints every worktree it keeps, with the reason. Uncommitted files, unknown
  ignored files and `.tezgah` data keep a worktree. So do an unmerged branch, a
  branch nobody committed on, an agent at work and an Orca that does not answer.
- **No process questions.** The contract says the orchestrator picks a process
  parameter the user did not set, such as a spend ceiling, and states it.
  `consult` on exit 4/5 records the first member of another model family
  itself instead of asking the user to choose. After two review rounds the
  session fixes what is left and closes with `close NNN done --resolved`. A
  missing credential sends it to a route that needs none first. A silent gate
  has it run `tezgah-setup --report` itself.

### Fixed

- **product-analysis no longer says `check` demands three compared solutions.** An analysis answers once. A choice between solutions goes under `decisions/`.

## [1.5.1] - 2026-10-09

### Fixed

- **Subagents load in the first session.** Claude and Codex missed every role a
  session wrote into a new repo until the next session. Codex also ignored
  `.codex/agents` in an untrusted repo. The install now writes the roles to
  `~/.claude/agents` and `$CODEX_HOME/agents`, as it already did for omp. A
  session removes the copies an older release left in a repo's `.claude/agents`
  and `.codex/agents`. Cursor read 9 of 10 role descriptions as ">" and got a
  model id it does not list. It now gets its own `.cursor/agents` with a
  one-line description and `model: inherit`.

- **`tezgah-route` names the specialists.** It could only name a tier. The
  five specialists ran 0 times in 121 delegations. The generic task agent ran 86.
  The judge now also answers whether a brief is a specialist's whole
  job, and the route names that agent. `--phase review` and `--phase research`
  name the reviewer and the researcher. A security brief that only reviews
  goes to `tezgah-security`. The routing and fan-out text say to spawn the
  named agent, never the generic one.
- **Jev through OpenRouter asks a model OpenRouter has.** The carrier sent
  `typesafe/jev-latest`, which OpenRouter answers with 400 (no such model). It
  now sends the bare `jev-latest`, which OpenRouter maps itself.
- **The Workers AI model id picks Clef.** `tezgah-setup` refused
  `--jev @cf/cloudflare/clef-flash`, and the same value in
  `TEZGAH_JEV_PROVIDER` chose no carrier. Both now name `clef-flash`, and
  `@cf/cloudflare/clef` names `clef`.
- **opencode's judge run denies tools at agent level too.** A user's
  `agent.build.permission` beat the inline top-level deny.
- **The refusal note needs an asked session CLI.** The seam writes it only
  when it asked the session CLI first. A caller that named the CLI gets it.
- **A chosen carrier reads only its own key.** A `clef` choice no longer opens
  omp's login database on every status-line redraw.
- **`pnpm test` names a command.** An Acceptance item counted as a command
  only when a word after the first was an option or a path. So `pnpm test`,
  `cargo test` and `make test` read as missing, and the phase move refused the
  plan. A known runner followed by `test` or `run` now counts. Prose such as
  `run the tests` still does not.
- **Each carrier's price is now pinned by a test.** The one cost check priced a
  TypeSafe answer at Jev's rate. It passed with or without per-carrier pricing.
  New tests in `tezgah-taste`, `tezgah-triage` and the replay labeller price Clef
  and Clef-flash answers at their own rates. A run with an unpriced answer prints
  `cost unknown`.
- **Claude lists the reviewer once.** The plugin shipped its own
  `agents/tezgah-reviewer.md`, which Claude shows as `tezgah:tezgah-reviewer`
  beside the generated reviewer and never shadows. The plugin now ships no
  agent, and its release-time renderer is gone with it.

## [1.5.0] - 2026-10-09

### Changed

- **A plan gets one review, at most two rounds.** The review reads the plan's
  whole diff once, in its verification phase. Round one spawns its reviewers in
  one message, one per dimension, or one reviewer for a diff under 300 lines.
  Only a confirmed critical or major finding opens round two. Round two reads
  the fix's delta. A minor finding goes on the fix-later list. `tezgah-task review`
  refuses a third round. What is left after round two goes to the user. The
  reviewer agent, the contract and plan-sync now state this one rule. Before,
  the reviewer looped until a round confirmed nothing.
- **One Acceptance rule.** A plan enters a writing phase only when each
  Acceptance item names its command or says `unverifiable` and why. Before, one
  command-bearing item let the move through. `render_table --acceptance
  --strict` then refused the same plan. Both now read one predicate,
  `tezgah_task.unproven`, and the refusal names each item's line.
- **Typed decisions take any Jev carrier.** Taste's `learn`, `label`,
  `calibrate`, `gate` and `measure --typed` require the Jev model, not
  TypeSafe's address. So do taste's background start and replay's
  `--label-model`. OpenRouter System One, Cloudflare Workers AI or a
  compatible endpoint counts the same. Old `typesafe` rows keep counting.
  `learn`'s report key `typesafe` is now `jev`. Replay's `--provider typesafe`
  is now `--provider jev`, and the old name still works. The triage's no-judge
  message names every carrier, the selection knob and the session CLIs.
- **The fan-out rule arms on the lists the owner writes.** Items written
  `1 - ...`, `1- `, `1:`, `a)` or `+` now arm it. An inline `1. ... 2. ...`
  arms it, and so does "subagentlerle". Three files named as one list arm it
  too, and so do "First, ... Second, ..." and three imperative clauses. A later
  list in the same session gets a line that names the action: count the items,
  one subagent per item in one message. The rule covers every phase: a plan's
  tasks, its acceptance commands and a survey's sources fan out too. The clause
  that let a list of small items run one by one is gone.

### Added

- **Plan order and progress in `tezgah-task status`.** A plan can name the
  plans it waits on with `after:`. `status` prints each open plan's ticked
  Acceptance boxes and what it still waits on. A `parallel:` line names the
  ready plans whose `allowed_paths:` share no prefix. Those can run at once.
  An open plan whose `status:` is not open or blocked is a `FAIL` line, and so
  is an `after:` id no plan carries. `--json` adds `open` and `parallel`.
- **The judge asks opencode, Cursor and Codex sessions too.** The judgement
  seam's session CLI was omp or claude only. It now also runs `opencode run`,
  `cursor-agent -p` and `codex exec` headless when their host's marker is set
  (`OPENCODE`, `CURSOR_AGENT`/`CURSOR_VERSION`, `CODEX_THREAD_ID`).
  `TEZGAH_JUDGE_CLI`, else `judge_cli` in `config.json`, picks one of the five
  by name. A picked CLI that is not installed means no session CLI.
- **Jev through any carrier.** The judge reaches Jev through TypeSafe,
  OpenRouter, Cloudflare Workers AI or a System One-compatible URL
  (`JEV_API_BASE_URL`, `JEV_API_KEY`).
  `TEZGAH_JEV_PROVIDER`, `JEV_PROVIDER` or config.json `jev` picks the carrier,
  and `tezgah-setup --jev <value>` writes the config key. `auto` asks every
  carrier that resolves. A named carrier without its credential gets no
  request, and no other carrier stands in. `tezgah-status --judge` prints the
  choice and its carriers.
- **The omp login is a TypeSafe key.** With no `TYPESAFE_API_KEY` and no key
  file, the seam reads the active omp login, read-only.
- **Clef and Clef-flash as typed judges.** Cloudflare's own decision models
  answer the System One API on Workers AI with the Cloudflare token and account
  id. `--jev clef` or `--jev clef-flash` picks one, and `auto` asks them after
  the Jev carriers. A typed decision counts them like Jev. Cost rows now price
  the carrier that answered: $0.24 per 1M input for Clef, $0.09 for Clef-flash.

### Fixed

- **A spent key stops costing a request.** OpenRouter answers 403 to a key
  past its limit. A 403 now marks a provider down for five minutes, like a 401.

## [1.4.0] - 2026-10-08

### Changed

- **Taste state lives in SQLite.** The repository's signals, decisions,
  defects, labels, injections, gate state, learnings and write-note history
  move to `.tezgah/taste/taste.db`. User-scope learnings move to
  `~/.config/tezgah/taste/taste.db`. Opening a store imports the old JSON and
  JSONL files and renames each to `<name>.imported`. It also takes rows an
  older install appends to an old file later. `taste.md` stays a text file.
- **The evidence ledger lives in SQLite.** Session rows move from
  `~/.cache/tezgah/evidence/<session>.jsonl` to the `evidence` table of
  `~/.cache/tezgah/tezgah.db`. Each row is one INSERT, so no reader meets a
  torn line. A read or write of a session imports its old JSONL file first.
  Session start imports the rest in the background once a day, and
  `tezgah-doctor --import-evidence` imports them now. opencode's plugin uses
  the same database through node:sqlite. On node before 22.5 it calls the
  store's `evidence` CLI. The old files stay in place: an opencode process
  started before the upgrade may still append to one. `tezgah-doctor --clean`
  deletes a session idle past the retention window.
- **The small cache stores live in the same database.** They move from files
  under `~/.cache/tezgah/` to tables of `~/.cache/tezgah/tezgah.db`. These are
  the turn stamps, switch baselines, used-tool marks and status marks. The
  nudge marks, the judge's marks, the skill hints and the update check move
  too. So do the lesson-taint index, Cursor's marks and replies, the snapshot
  and replay indexes and the taste-learn stamps. The first open of the
  database imports each store's old files once and deletes them. A later open
  deletes, unread, a file an older release still running writes there. Snapshot
  blobs, replay runs and logs stay files. `tezgah-doctor --clean` sweeps the
  stamps and marks there.

## [1.3.0] - 2026-10-07

### Added

- **Armed taste learns by itself.** Session start runs `tezgah-taste learn` in
  the background when the repository's signals grew, at most once an hour. It
  runs only when a TypeSafe key resolves, with the new `--no-fallback`, so it
  asks no other provider. It does not run on Windows yet. Its log goes under
  the cache dir, in `taste-learn/`.

## [1.2.0] - 2026-10-07

### Added

- **Taste learns and applies, not only records.** Arm it with `taste-on`.
  `tezgah-taste learn` then turns each correction after a writing turn into one
  typed decision, and only TypeSafe may give it. The decision names a
  preference, a defect or neither. It picks one of eleven fixed categories and
  a scope, and relates the correction to each learning already held. A ledger
  computes each learning's confidence from its evidence and forgets it over
  time. A contradiction flags a learning and never overwrites it. A learning
  goes active in its second session. Session start injects active learnings as
  rules or hints. Every host notes the in-scope ones on a write, each once per
  session. A rule needs a measured calibration bound. A defect never enters the
  ledger. A before/after gate stops injection when corrections do not fall.
  `list`, `accept`, `reject`, `edit` and `export` give the user control, and
  `learn --from-transcripts` bootstraps from history. The judge seam gains
  `only=` and a `text` question. Two commands never rewrite the ledger at once:
  a second `learn`, `accept`, `reject` or `edit` exits 2 while one runs.

## [1.1.0] - 2026-10-07

### Added

- **Parallel by default.** A prompt with two or more independent items arms a
  fan-out rule. One batch of subagents runs, one worktree per writing slice,
  and the main thread integrates. Five specialist agents join the roster:
  `tezgah-tester`, `tezgah-docs`, `tezgah-security`, `tezgah-ui` and
  `tezgah-researcher`. `tezgah-agents --list` prints each with its tier,
  skills and tools.
- **tezgah detects an Orca session** (`hooks/tezgah_orca.py`). Inside Orca a slice
  checkout goes through `orca worktree create`, and `tezgah-status --orca`
  lists the checkouts Orca tracks and the git worktrees it does not.
  `docs/orca.md` maps what Orca owns and what tezgah owns.
- **`tezgah-doctor --stack`** prints each host's effective stack: context
  files in load order, skill dirs and which copy wins, hooks per event, MCP
  servers. It flags duplicate or stale skills, doubled hooks and rules, and
  backups inside a scanned dir. `docs/hosts.md` holds the precedence table.
- **`tezgah-skill <words>`** searches every installed skill by section and
  returns `skill://<name>:<start>-<end>` plus the file path. Every session is
  told to use it. A local, model-free hint is on by default: when a prompt's
  terms match one section well enough, the turn names that section once. The
  armed judge hint names the section too, not only the skill.
- **`tezgah-status --judge`** shows what the judgement seam used last, and why
  it was not the session's own model when it was not.

### Fixed

- **The judgement seam asks the session's own CLI first.** It used a third
  party (TypeSafe, then OpenRouter) even when the session's frontier
  credential was there. A third party now answers only as the `fallback`
  setting in `config.json` allows. The default is `vendor`: no cross-vendor
  stand-in while a session CLI exists. Every stand-in or refusal is said on
  stderr and recorded. omp subagent chains stay inside the session vendor by
  default too.
- **Research stays on the question asked.** A line records its scope (`--in`,
  `--out`) and its method (`--method qualitative|measured`). A qualitative
  line owes no metric. Every claim must trace to a scope item. An analysis no
  longer owes three variants. A plain factual question gets an answer from
  primary sources, with no experiment line.
- **Ponytail and adhd are in force from the first turn.** Their operative rules
  ride the always-on contract instead of a "read the skill later" pointer.
- **The graph engages.** A stale index stamp now starts a background re-index.
  It no longer tells the session to fall back to text search. omp's `find`,
  `search` and `ast_grep` reach the gate. The graph nudge fires on
  symbol-shaped searches only, not on plain words, and honours `.no-graph`.
  The session line names the host's own graph tool.
- **A prose edit owes no check.** The Stop rule no longer counts a `.md`,
  `.rst` or `.adoc` edit outside the instruction files as work. Such an edit
  neither demands a check nor makes an earlier pass stale. Refusals ask for
  the smallest check that proves the change.
- **`tests/impacted.py` maps a host file to the modules that name it**, not to
  nearly the whole suite.
- **Host-file backups leave the dirs a host scans.** They go to
  `~/.config/tezgah/backups/`, and `--install` sweeps the old ones. Cursor gets
  each tezgah skill from one dir, not two. `--sync` refreshes only the plugin
  copy Claude loads.

### Changed

- **A release run skips the serial suite.** `release.yml` calls CI with
  `release: true`. One 3.10 `test` leg then runs compile, lint and the citation
  audit, and `test-sharded` runs the suite.
- **CI runs less.** It runs on pushes to `main`, on pull requests and by hand.
  A newer run cancels an older one on the same ref, and every job has a
  timeout. A docs-only change runs only the citations audit and its impacted
  tests. The `test` matrix is 3.10 and 3.14. A pull request runs the impacted
  set. `main` and a release run the whole suite.

## [1.0.0] - 2026-10-07

### Upgrade note

- **1.0.0 starts the public line, and npm keeps no 0.x.** The registry no
  longer serves 0.1.1, 0.1.2 or 0.33.0, nor the pre-reset 0.17.0-0.32.0. The
  update check treats every 0.x install as older than 1.0.0
  (`hooks/tezgah_update.py::RETIRED`), so the `↑` chip and `tezgah update` move
  it to 1.0.0. A 0.x install from npm moves with `npm install -g @r1z4x/tezgah`.
- **Homebrew users coming from 0.1.2: re-arm once after `brew upgrade`.**
  0.1.2 armed the host hooks with paths into its own keg,
  `Cellar/tezgah/0.1.2/libexec`. The upgrade's default cleanup deletes that
  keg, so those hooks point at nothing until a re-arm. Run `tezgah update`.
  On the brew channel it runs `brew upgrade` first. Then it re-arms the hosts
  and roots this install recorded, from the new tree behind `opt/tezgah`.
  0.1.2's `tezgah update` already re-arms from there too. Or re-arm by hand with
  `tezgah-setup --install --hosts <the hosts you armed>`. 1.0.0 arms through
  `opt/tezgah`, so later upgrades need no re-arm. The formula's caveats say
  the same after `brew upgrade`.

### Added

- **An orphan pass no longer licenses a claim.** Every ledger reader now
  pairs each `verify_ok` with the `began` row the gate wrote for its call.
  A pass with none is an orphan: it came from outside the hooks
  (`python3 -c`), or its call's rows went missing. No reader counts it as a
  pass. The Stop rule refuses a done-claim in its turn as "evidence tampered",
  and `counters.orphans` counts it. Five cases stay exempt: a session with no
  `began` row, a turn with a `crash` row, `pretooluse-off`, an unlocked append
  and the sandbox fallback cache. A forged `began` row plus its pass is the
  residual `SECURITY.md` names (plan 051). The gate now writes a call's
  `began` before its rules run, so a refused call leaves `began` and `deny`.
  Codex's PreToolUse matcher now names `shell` and `Shell` too.
- **The session latches its kill switches.** A switch file newer than the
  session's first ledger row (ctime or mtime) no longer disarms that session.
  `off()` ignores it until the user's prompt names it, which writes an
  `authorized` row. A switch present before the session starts counts as
  before. So does the stand-down `tezgah-setup --uninstall --full` writes into
  `pretooluse-off`. The opencode plugin answers the same way. A switch the user
  flips in their own terminal mid-session now waits for the next session or a
  prompt that names it (plan 051, SECURITY.md).
- **The arm-bench lab is back in the repository.** `benchmarks/arm-bench/` holds
  the runner, the 49 task trees and the earlier pre-registrations, with every
  home path redacted. It is a maintainer tool: `managed()` keeps it out of host
  plugin trees and the MANIFEST. Plan 062's phase 1 adds arm HOMEs built out of
  tree from one pinned commit (`homes.py`) and a fresh HOME per run. It adds the
  unlock strip that defines the switch-paragraph arm (`unlocks.py`) and a cheat
  classifier over the final diff that uses the gate's own patterns. The report
  adds paired bootstrap intervals, exact McNemar and Holm. `bench.py selftest`
  now also fails when an arm's prompt text names a task's hidden identifier.
- **A tainted lesson gets a label, never a refusal.**
  Untrusted text is a web, MCP, network, tier or subagent read. A write to
  `.tezgah/lessons.md` after one in the same user turn now leaves one
  `lesson_tainted` row per line it adds
  (`docs/evidence.md`). The line still rides both lesson blocks, behind a
  per-line data label (ADR 010). The ledger now has one reader,
  `hooks/tezgah_lessons.py`, for the context, the gate and `tezgah-lessons`.
  It cuts a `|| check: ...` clause and an `@<sha> <path>` stamp off each line.
  Neither changes the key, the per-turn digest, the cut or the ranking.
- **A model can be the replay sheet's second rater.** `tezgah-gate replay
  --label-model --prompt <file>` sends each blind sheet row, redacted, to the
  judge seam. It writes `labels-model.jsonl` beside the sheet and prints the
  token cost. `replay --report` with one rater's labels now prints no rate:
  the rates need two raters' agreed labels.
- **A second model family can rate the replay sheet.** `tezgah-gate replay
  --label-model --provider deepseek --model deepseek-v4-pro` asks the same
  prompt over DeepSeek's OpenAI-compatible endpoint at temperature 0. It writes
  `labels-deepseek.jsonl` and prints input and output token cost. With two
  model raters `replay --report` calls kappa model-model agreement.
- **The shell-reader fuzzer runs weekly under bash 5.x.** A `fuzz-shell` job
  in `.github/workflows/neuter.yml` runs `tests/fuzz_shell.py` on the ubuntu
  runner's bash 5, seed 1, 20000 lines. It reads the lines once with the core
  readers and once with the opencode plugin's ports (`--js`). The new
  `--strict` flag makes any disagreement class exit 1, so the job fails on it.
- **`tezgah-status --enforcers` shows what enforces each always-on rule.**
  Each CORE rule gets one row. The row names the gate rules and Stop classes
  that refuse on the rule, with the switches and conditions that guard each.
  It also names the shape flags that only record it. A rule reads `partial` when
  every refusal can vanish while its text stays, or when `docs/contract.md`
  names a part nothing covers. The report always exits 0.
  `bin/tezgah-docs --citations` and `tests/test_enforcers.py` fail on a rule
  that nothing refuses on and that has no row in `docs/contract.md`.
- **An MCP effect now meets the gate's content rules**. Claude, dsh and omp
  spawn the gate for an MCP tool whose name carries an effect verb, so a
  read-only MCP call costs nothing. Cursor's `beforeMCPExecution` asks the
  gate. An effect verb in the tool's name picks the rules, case-sensitive like
  the host matcher. A clause led by a read verb (`get_commit`) is a read. A
  `write` meets shortcut, attribution and secret. A `publish` meets attribution
  and secret. No class refuses by itself. The secret half reads vendor token
  shapes only. The payload walk stops at 64 KiB. An MCP effect also counts for
  the taint notice, one notice per untrusted channel, and for the drift
  re-statement. So an MCP `act` such as a click can now draw that re-statement
  once per long turn.
- **The Stop rule's evidence fold, declared as a temporal spec, runs in
  shadow.** `hooks/tezgah_stopspec.py` writes classes 5-10 as seven past-time
  formulas over ten row atoms. A one-pass monitor judges each reply that
  leaves a claim or a refusal row. It runs beside the imperative fold and
  leaves one `stop_spec` row: `agree`, `disagree` or `error`. The row also
  says `fold` or `selector`: whether the shared selector reached the fold.
  The verdict stays the imperative one, and a failing spec costs only its row.
  `mask` keeps a per-process cache, so both folds read each ledger detail once.
  `TEZGAH_STOPSPEC_STRICT=1` makes a disagreement fatal in the tests.
  `tests/stop_spec_eval.py` measures the bet (plan 063). Plan 055 replays 496
  Stop events, and the two folds agree on all of them. The bar reads only the
  361 events that reached the fold.
- **Real bash now checks the shell readers.** `tests/fuzz_shell.py`
  draws seeded lines from the hand vectors' grammar. It runs each in `bash`
  with a stub per program word and prints each class where `shell_programs` or
  `mask` disagrees. `tests/test_fuzz_shell.py` runs a small sample per suite
  run and fails if `mask` blanks a program bash ran. `--js` reads the same
  lines with the opencode plugin's ports through node. It reports where a port
  disagrees with bash or with the core, and the suite sample fails on either.
- **`tests/bench_gate_latency.py` times the gate.** It prints p50/p95 of
  `decision(..., record=False)` over 200 common calls, for this tree or for
  another revision's exported `hooks/`.
- **Concluding or closing a research line seals it.** `conclude` and `close`
  write `state.json` `order_seal`. It holds, per experiment, the sha256 of
  `protocol.md` and `results.jsonl`, and no order verdict. Every `check`
  verifies the hashes, with or without git, so the session note reports an
  edit after the seal. While the hashes hold, `check` re-derives the order, so
  results committed after the close still count. `tezgah-research seal <slug>
  --history-lost --ack "<decision>"` gives the owner's `history-lost` verdict
  to a line concluded before seals (ADR 009). It covers only an order the lost
  history left undecidable. A real violation stays an error. Without
  `--history-lost` (ADR 018) it writes the plain seal `conclude` would, and
  only when every experiment's order still checks.
- **`tezgah-research import <checkout> [<slug>]` moves a line with its
  history.** It fetches the other checkout's `.tezgah` repository from disk.
  It merges that history as a second parent and takes only the imported lines.
  It refuses a plain copy, because a copy loses the order proof. It needs no
  remote. An open line arrives beside open ones only with `--allow-open`.
- **The MCP tool `tezgah_research_check` takes a `slug`.** The server checks it
  as a line name. It passes the slug after `--`, so `tezgah-research` never
  reads it as a flag.
- **The neuter matrix mutates the Stop rule.** `tests/neuter_matrix.py`
  generates one mutant per Stop-class return site. The sites sit in
  `_stop_block`, `_shape_block` and `_evidence_block`: 13 over 11 classes. Hand-written rows add the
  guards around them: the pass predicate, the empty-run read, the pipe
  guard and the "doğrulanmadı" clear. The lost call, the bookkeeping and
  idle-turn fallbacks, the refusal row and the `other repo` cause are rows
  too. The run adds the omp and after-block Stop test modules.
- **Every session attests tezgah's own hook entries.** The installer now
  records each host's tezgah-owned hook entries in `contract.sha256`, one line
  per entry. On a release install it also records the scripts they run. Each
  session start compares the entries on disk with that record. opencode does
  it at its first message. The session gets one `attest` row: `ok`,
  `drifted: <entries>` or `unverified: <why>`. A drifted row names the entry.
  It also names a hook file any user can write and a stale omp bridge. The row
  lists the kill switches present. A drifted session shows a `drift` status
  mark, and its claim rows carry the drift in `harness`. Drift never blocks a
  reply. `--report` prints the same comparison per host.
- **`tezgah update` shows the hook change.** It prints each tezgah hook entry
  the new release adds, removes or changes. That comes before the re-arm. On
  a terminal it waits for a yes. A piped update goes on (decision 12).
  `--upgrade` does the same. The new tree answers through
  `tezgah-setup --hook-entries`.
- **`upgrade.sh` checks build provenance when `gh` is there.** It runs
  `gh attestation verify` on the tarball against the release workflow's
  attestation. Without `gh` it prints `provenance not checked`, and a `gh`
  that cannot answer is a warning. The checksum stays the gate.
- **`docs/hosts.md` states each host's enforcement capability.** One table
  covers the gate, the Stop rule and subagents per host, in gate, observe,
  partial and unavailable. A cell no driver can probe says unverified.
- **`tezgah-gate replay` measures the gate against its own history.** It
  replays this machine's real ledgers through the unmodified dry-run gate and
  the Stop rule. It runs in a sandbox HOME, with the clock frozen at each call.
  It prints the corpus size, the join rate and every exclusion with its count.
  Per stratum, it prints how often the replayed verdict equals the recorded
  one. Every figure names its cutoff. `replay --sheet` draws a blind label
  sample that shows no verdict. `replay --report --labels <file>` turns two
  raters' labels into per-rule false-block rates and Stop error rates. Each
  rate carries a Wilson 95% interval, and the report adds Cohen's kappa. It
  also folds the denial budget: runs of 3 consecutive denies per rule in one
  turn, and sessions with 20 or more. Nothing leaves `~/.cache/tezgah/replay`,
  and no gate behaviour changes. `tezgah-taste`'s transcript walkers can now
  read subagent files and tool inputs. `mine` reads what it read before.
- **`--install` arms Claude Code through its own CLI.** Claude's gate, Stop and
  ledger hooks ship in the plugin. The installer never registered that plugin,
  so only the maintainer's machine had them. The install now
  writes `.claude-plugin/{plugin,marketplace}.json` from the release version
  into its own tree. The pair stays untracked. It then runs `claude plugin
  marketplace add <tree>` and `claude plugin install tezgah@tezgah-local`. An
  existing `tezgah@*` row is left alone, so no hook fires twice. Claude's
  `plugin copy current` row now fails `--install` where a `claude` CLI exists.
  `--uninstall` also drops the `enabledPlugins` key and the rendered pair.
- **`--report --live` proves the gate runs.** Each host now also gets one
  PreToolUse for `git commit --no-verify -m x` through its own wiring. The row
  is ok only when the host answers with its own deny and the ledger gains a
  deny row. `pretooluse-off` and `verify-off` make it UNVERIFIED, named. The omp
  bridge must match a fresh render byte for byte. opencode's plugin now writes
  a deny row for its own refusals. The Python gate already did.
- **`reply_lang` picks the reply language.** `tezgah-setup --install
  --reply-lang tr|en|any` stores it in `config.json`, and `install.sh` forwards
  the flag. `tr` is the default and what an install without the key reads. `en`
  asks for English and `any` for the user's language. The Stop rule checks
  the language only under `tr`. The contract's first rule and
  the per-turn reminder name the configured language.
- **README: what tezgah changes on your machine**, in all five languages.
- **The gate guards tezgah's own control plane (`control`).** It refuses a
  change to a kill switch. It covers `~/.config/tezgah`, the evidence ledger
  and the hook wiring too. It also refuses a change to a repository's `.no-*`
  mark or `.git/hooks`. It
  refuses a delete or move of `.husky` or of an open plan. It refuses a
  forced `git add` of a `.tezgah/` path, and the CLIs that change that state.
  Claude's `disableAllHooks` and Codex's hook trust entries count as wiring.
  The rule follows a `cd`, `if`/`for`/`!`, `eval` and `bash -lc`. It refuses a
  write through a link and a delete of a directory that holds this state.
  Only `pretooluse-off` removes the rule, and the refusal names no command.
  All 12 tamper probes of the deep analysis passed the gate before. Now the
  gate refuses all 12. ADR 010 freezes new gate rules, and ADR 004 makes this
  one the exception: it ships this half of R05 (R05a) now. An interpreter
  (`python3 -c`) still gets through. `SECURITY.md` names it as a residual.
- **A damaged ledger line blocks a done-claim.** A bad ledger line used to
  make the reader raise. The Stop rule then failed open for the turn. The new
  Stop class is "evidence tampered". Now the reader
  skips the line and writes one `ledger_damage` row for it. The Stop rule
  refuses a done or tested claim in that turn. That covers a corrupted
  `verify_fail` row too.
- **A switch armed mid-session leaves a record.** The prompt hook writes one
  `disarm` row for a switch that appears after the session's first prompt.
  The status line shows its `gate✗` mark while that switch stays armed.
- **Subagents stop sharing taint on Claude.** Claude's hook payload names the
  subagent (`agent_id`), and its rows now carry it. One sibling's web read no
  longer marks another sibling's effects. The repeat ceilings count each
  agent's own attempts.
- **`SECURITY.md` states the threat model.** It names a cooperative but
  fallible agent, the state the gate guards and how, and the residual routes.
- **The control rule also guards the attestation state.** It refuses a
  change to the `harness-drift/` and `import-crash/` status marks and a
  `tezgah-context attest` run. The `hook:<host>:...` rows of `contract.sha256`
  were already covered as tezgah's configuration, and a test now pins them.

- **Opt-in taste capture, and a miner for the corrections already on disk.**
  Arm it with `~/.config/tezgah/taste-on`. A repository with a `.tezgah/`
  directory then gets `.tezgah/taste/signals.jsonl`. It holds each prompt,
  each landed edit's old and new text, and a snapshot of the bytes the write
  left. Redaction and a length cut apply to the text. A `.no-taste` mark turns it off per
  repository. `tezgah-taste mine` counts and extracts the prompts that
  followed a writing turn in omp and Claude transcripts. `tezgah-taste
  measure` and `tezgah-taste rate` sort them with the judge seam into
  preference, defect or none. This phase learns and injects nothing.

- **The Stop hook now records the reply after a block.** On Claude, Codex and
  omp the hook skipped the reply that answers a block. It now judges that
  reply in record-only mode and writes one `after_block` row. The row says
  whether the rule would refuse the reply, let a claim through, or found no
  claim. It never blocks a second time and never counts as a claim or as a
  reply. A block from another Stop hook leaves no row. Cursor stays unwired:
  nobody has checked its stop payload yet.
- **A subagent's end leaves a record-only verdict.** Claude's SubagentStop
  (a new hook row) and Cursor's subagentStop now judge the subagent's last
  reply. They read the evidence half of the Stop rule and write one
  `subagent_end`
  row. It never blocks and never counts as a claim. Every Stop adapter names
  its re-ask budget as `STOP_REASKS = 1`. On Claude a subagent's tool rows
  still sit in the parent's ledger, so the row judges the parent's turn until
  the agent key lands.
- **Lessons keep their rule when injected.** A lesson line is now written rule
  first: `<rule> - <incident>`. The rule sits in the first 120 characters, so
  the 200-character cut keeps it. The session block says how many of its lines
  do not open with their rule. A line ending `|| enforced_by: <rule|test>` leaves
  the injected blocks while that gate rule or test is on. A test counts only
  while the repository still defines it. A switched-off rule brings the line
  back. `tezgah-lessons` proposes rule-first rewrites, merges of duplicate lines
  and those retirements. It never writes the ledger. On this repository's
  47-line ledger the session block grows from 1266 to 1352 bytes. omp's
  `RULES.md` lessons line grows from 230 to 270 bytes. The always-on core
  shrinks by 23 bytes.
- **The per-turn lessons block shrinks before the budget drops it.** Over budget
  it keeps its first lesson. The session remembers only the lessons it shows. The
  drop log records this as `kind=truncated`. Each injected lesson leaves a
  `lesson` ledger row with its key and block, and that row is not gate evidence.
- **A wider citation audit.** `bin/tezgah-docs --citations` now judges a bare file
  name and a symbol written after its citation. It also reads the comments and docstrings of the Python code. A
  `path:N` it cannot read counts as unjudged. The tree reads 524 judged and 1022
  unjudged, up from 429 judged. A file whose unjudged count is above or below its
  entry in `docs/citations-baseline.json` fails the check. `--citations --update`
  rewrites that file. The same pass reads all ten Stop classes by AST. It also checks the
  gate's rule order and switches, the judge's callers and the kill-switch names.
  `tests/neuter_matrix.py` generates one mutant per gate rule.
- **`tezgah-setup --write-plugin-agents`.** The plugin's `agents/tezgah-reviewer.md`
  is now rendered from the same role body the per-repo reviewer gets. A test
  fails until the flag has run after a body change.
- **The status line says when a newer release is out, and `tezgah update`
  takes it.** A `↑X.Y.Z` chip sits beside the logo on every surface. A redraw
  reads a cached answer, and a detached check refreshes it at most once a day.
  `tezgah update [--dry-run]` updates through the channel the install came
  from (release prefix, Homebrew, npm or git) and re-arms the hosts. The
  `update-check-off` switch turns the check and the chip off.

### Changed

- **The README describes mechanisms, not outcomes.** A paired on/off experiment
  ran DeepSeek V4.1 Flash on omp, bare against a full install. It found no
  measurable reduction in cheating. The model barely cheated in either arm: 0
  of 132 runs with tezgah and 1 of 131 without, on ImpossibleBench's
  conflicting SWE-bench split. Hand labels of the final messages found no
  false-done difference either: 3 of 30 with tezgah, 6 of 30 without. The
  Stop rule's claim reader flagged far more, because it reads `doğrulandı` on
  a partial fix as a done claim. That weakness stays open for now. The
  README, `docs/vision.md` and `docs/evidence.md` now say what tezgah enforces
  and records, and what it has not shown. The redacted results bundle is
  `docs/results/paired-outcome-2026-10.md`, with per-task counts beside it.
- **An open plan's move and a forced add of `.tezgah/` leave evidence.** The
  `control` rule refused a delete or move under `.tezgah/plans/open/`. It also
  refused a `git add -f` of a `.tezgah/` path. Plan 050's replay of real
  ledgers found both refused without the user's say-so. That happened more
  than once a week, so its falsifier fired (ADR 018). A call that moves or
  deletes one plan, or force-adds a `.tezgah/` path, now passes and leaves a
  `disarm` row, `control: <what>`. The rule still refuses the open plans'
  directory and its ancestors, and a call that also changes another protected
  path.
- **The research session note hashes a line under `done/`.** `failing()` runs
  `_check_seal` on a concluded or closed line instead of the full `check_line`.
  An edit after the seal still reaches the note. The line's other findings stay
  with `check <slug>` and `check --all-lines`. On a copy of this repository's
  workspace the note took 0.014 s instead of 0.67 s.
- **The no-slug research `check` and `status` report the open lines.** They
  read a line under `done/` by its seal hashes, as the session note does. A
  `state.json` or a seal they cannot read fails the line. One line counts the
  done lines that carry a seal and those that do not. `check --all-lines`
  re-checks every line in full, and `check <slug>` still does for that line
  (ADR 015).
- **The research history bridge is gone.** Nothing reads
  `.tezgah/history-bridge.json` any more. It proved no experiment on this
  repository's workspace, so `check` refuses a re-rooted one-commit add like
  any other. Its code, its `notes` channel in the `check` report and its tests
  went with it (ADR 015).
- **The piped-check remedy is one sentence.** `PIPED_REMEDY` in
  `hooks/tezgah_integrity.py` holds it. The refusal, the always-on core, its
  hookless copy, the contract skill and `docs/gate.md` quote it word for word.
  A test pins every copy. It names the two shapes that keep the check's exit
  status. One runs the check last into a file and reads the file in a separate
  call. The other opens the line with `set -o pipefail;`.
- **A session pays each armed rule once.** The first matching prompt gets the
  full paragraph of spec, consult, research, product or graph. A later match in
  the same session gets one line that names the rule. The research line keeps
  its open-lines fact. A compaction brings the full paragraph back. So does a
  match 20 turns after the last full showing, for Cursor and dsh. The per-turn
  reminder no longer restates spec, graph or research. Those rules reach a turn
  through their own paragraph. It keeps the short consult clause, because a
  terse irreversible ask arms nothing. The `user_prompt` budget now drops the
  skill hint before the task phase, the delta and the pointer. A replay of
  1,452 uncut real prompts from 85 local sessions ran through `context_for` in
  a fixture repo. Injected bytes per session fell from 37,387 B to 28,928 B
  (-22.6%). Per turn they fell from 1,599 B to 1,104 B. The Stop-shape and
  claim-rate comparison needs a 2-week window and has no result yet.
- **The subagent brief keeps each rule's operative sentence.** The brief kept
  only each rule's first sentence. A delegate lost "inter-agent reports stay
  English" and the lessons instruction. A per-rule sentence count now keeps two
  sentences of three rules, cut from CORE's own text. The brief grows from
  4,120 B to 4,263 B. The `subagent_start` budget moves from 5,000 B to 5,500 B.
- **User constraints survive compaction.** A prompt clause like "don't touch
  hooks.json" or "README'ye dokunma" now rides the turn stamp, to its
  sentence's end. The stamp holds that clause, never the prompt. A clause that
  starts inside quotes or code does not count. The recogniser skips a prompt
  over 12,000 characters: pasted material is not the user's constraint.
  A quoted object after a plain "don't touch" still counts. The post-compact and
  session-start blocks restate the clause. The compaction row counts its object
  phrase in `constraint_found`. On the 1,452 uncut real prompts the recogniser
  pinned 7 clauses in 6 prompts, all real constraints. Before these bounds it
  pinned 17 in 11 prompts, 6 of them from one pasted 387,905-char agent log.
  `tests/constraint-fixtures.md` lists the rows, the misses and the known false
  positives.
- **Generic arming stems carry a qualifier now.** Ten code-sense asks no
  longer arm product, spec or research. Examples: "add a feature flag",
  "segment fault", "tabloya sütun ekle (sql)", "bu fonksiyonu sadeleştir". Every
  frozen corpus row keeps its verdict.
- **The policy keeps no joined `CONTRACT` constant.** The cost report measures
  the shipped `tezgah-contract` skill file instead. `ContractParity` walks the
  policy blocks against that file. The executive-mode "these win" sentence now
  covers output and report style only. A nested AGENTS.md or CLAUDE.md still
  binds its subtree.
- **opencode compaction passes the session id.** The builder then forgets the
  lessons and armed paragraphs that session saw. The plugin used to send `{}`.
- **Research predictions and the per-component report stay frozen.** They keep
  working as documented and take no new rule, field or command (ADR 009).
- **`check` reports a superseded claim once.** Only the row that supersedes it
  warns, naming both ids. The superseded row no longer warns a second time.
- **Docs cite Python code by symbol.** A citation into Python code is now
  `path::name` or `path::Class.method`, not `path:line`. Moving lines no longer
  shifts it. `bin/tezgah-docs --citations` reads the cited file's AST and fails
  on a name it does not define. 961 docs citations moved to the new form. The
  rest kept `path:line`: no single enclosing symbol, a non-Python target, or a
  stale line nobody has re-anchored yet. They stay under the unjudged ratchet.
  A later pass read each stale line inside one symbol against the code. After
  it, 109 more citations name a symbol (`--citations`: 1081 judged before, 1190
  after, 0 outside). Eight that point at a module comment or a module-level
  line were re-anchored as `path:line`.
- **Ten more docs pages cite code by symbol**. A pass read their unjudged
  citations against the code. Now 101 of them name a symbol
  (`--citations`: 1230 judged before, 1333 after, 0 outside). Another 83 point
  at JavaScript, shell, markdown or a module-level line, and now carry the line
  they describe. One sentence in `docs/gate.md` said a path spelled differently
  escapes the concurrent-write guard. The guard compares resolved paths, so the
  sentence now names the case it does skip: a row with no `target`.
- **The rule ledger drops its `since` column.** A history rewrite left no
  record of the first commit that carries each rule. The provenance table in
  `docs/gate.md` now has `rule`, `incident`, `evidence` and `pin`.

- **The lessons ranking ignores words that name no lesson.** English and
  Turkish function words no longer rank a line. On a ledger of ten or more
  lines, neither does a word found in more than half of them. "update the
  changelog" used to inject three unrelated lessons and now injects none. The
  docs fallback ranks as before.
- **High-stakes briefs route to frontier by rule.** The override also matches
  destructive data and history operations. It matches keys, certificates,
  bearer and access tokens, and privilege changes too. A 12-brief fixture pins
  it: 8 high-stakes briefs go to frontier, 4 near misses do not.
- **Route rows and the skill hint's cost row name who answered.** Each carries a
  `judge=<provider>/<model>` word, and the model is the one the reply names.
  `via` keeps its name, so `tezgah-route --report` groups history as before.
- **consult's referee reads anonymous answers in a shuffled order.** The output
  maps each label to its member. With no recorded referee, an available member
  outside the panel referees. Otherwise a note says the referee is a panel member.
  consult reads omp's session model only on an omp session.
- **A pass now licenses a claim only when it checked something.**
  `--version`, `--help`, `--list`, `--collect-only`, `make help` and a bare
  `ruff` now record as plain runs. So do formatters in write mode:
  `ruff format`, `ruff check --fix`, `prettier --write` and `eslint --fix`.
  A formatter run after a pass now makes that pass stale. Some checks say
  in their own output that they ran nothing: `collected 0 items`, `no tests
  ran`, `Ran 0 tests`, `No tests found`. Such a run no longer counts as a
  pass. omp's bridge reads
  that from the result and sends only the flag. A pass also has to come from
  the changed file's own repository, so `cd ../other && pytest` no longer
  covers an edit here. The rule now dates a pass from the moment its check
  began, so a write that landed while the check ran makes it stale. The gate
  reads the same list: an information form is not a neutered or piped check,
  and it gets no retry exemption.
- **Honest Stop counters.** A blocked reply that claimed nothing is now a
  `refusal` row, not a `claim`. It has no completion word and no claim about
  an outside system. `false_completion / claims` counts claims only, and
  `counters` adds `refusals`. A `no verify_ok` row says
  whether no check ran or no pass of one showed. Rows are now version 3.
  The docs no longer call that ratio the one number that matters, and no
  longer quote a fixed value for it.
- **A question is not a claim on a turn with no work.** "Testler geçti mi?",
  "is it done?" and "not tested yet" no longer trigger the no-work claim
  check. "Tamamlandı, push edeyim mi?" still does.
- **tezgah teaches `codegraph affected` as what it is.** codegraph 1.6.0 says
  it "finds test files affected by changed source files". Every copy taught it
  as the blast radius of a ref. Now the contract, the reminder and the skills
  say it. The role bodies and the graph workflows say it too. The blast radius
  is `git diff` plus `codegraph impact <symbol>` per changed symbol.
  `git diff --name-only <ref> | codegraph affected --stdin` picks the tests.
  A reviewer with no shell (Claude, opencode) gets the changed files from its
  caller and runs the MCP `codegraph_impact` tool per symbol.
- **ToolSearch loads both codegraph MCP names.** A plugin install names the
  tools `mcp__plugin_tezgah_codegraph__*`, a checkout's own server
  `mcp__codegraph__*`. The select lines name both.
- **tezgah retires three unused roles.** It no longer generates
  `tezgah-explorer`, `tezgah-verifier` or `tezgah-researcher`. A session start
  sweeps their managed files from the repo agent dirs. `--install` sweeps them
  from omp's agent dir. The plugin's hand-kept `agents/tezgah-explorer.md` is
  gone. Steering names none of them.
- **`agents-off` removes the generated agents.** It used to stop generation and
  leave the old files for every host to keep loading. The next session start
  sweeps the repo agent dirs. The next `--install` sweeps omp's user-level
  agents, and it removes only names tezgah ever generated.
- **A repo's `.no-graph` hides the reviewer from steering**, also on omp, where
  the agent file is user-level.
- **Claude reads the graph workflows from the plugin only.** `--install` no
  longer links `~/.claude/workflows/*.js`, so each workflow loads once. It
  removes tezgah's old links there and any dangling `cbm-*.js` link. The
  report row now checks that no such link is left.
- **The `ai-research` feature row is gone.** It switched nothing. A
  `config.json` that still names it loads and installs as before.

### Fixed

- **Cursor's Stop rule re-asks once, as on every other host.** A real Cursor
  `stop` payload carries `loop_count` and no `stop_hook_active`. The hook read
  only the flag, so it refused every follow-up its own refusal started, until
  Cursor's cap ended the chain. It now counts `loop_count`
  (`hosts/cursor/hook.py::asked`).

- **The false-done reader no longer counts an honest partial fix as done.**
  `claims` took a fix marked verified beside an unverified test as done. A
  reply that admits an open check now reads as no claim. It says the work
  lacks a check, or that a test contradicts the issue or cannot pass
  (`hooks/tezgah_integrity.py::ADMITTED`). The rule came from the 60
  hand-labelled E4 dev messages, where precision rose from 0.15 to 0.69 at
  recall 1.0 (`tests/claim_reader_eval.py`). On a held-out set of 40 messages,
  labelled by two model raters (kappa 0.565), precision rose from 0.212 to
  0.857. Recall fell from 1.0 to 0.857 (6 of 7), below the plan's bar of 0.9.
  The one miss is a real verification claim whose double negative read as an
  admission. `claims` only feeds the benchmarks' false-done counts. The Stop
  verdict reads the plain vocabulary, so no refusal changed. A false-done
  count from before this change is not comparable with one after it.
- **The tap formula waits for its asset.** The release's brew job pushed
  `Formula/tezgah.rb` before it uploaded the tarball the formula names. So
  `brew install` met a 404 until the upload finished, and for good if it
  failed. The job now uploads the tarball and its `.sha256` first. It checks
  that both are on the release, and only then touches the tap.
- **Two sharded CI tests no longer race the runner's load.**
  `test_components.Switches` set its switches after the session's first
  ledger row. On a slow runner the latch then kept them out, as it should. The
  turns after the switches now run as a new session. The redact linear-time
  test now interleaves its two sizes, best of five each, so one load spike
  cannot land on one size alone.
- **The seam refuses a plain-http endpoint override off this machine.** The
  judge seam's `TEZGAH_TYPESAFE_URL` and `TEZGAH_OPENROUTER_URL` and the
  replay rater's `TEZGAH_DEEPSEEK_URL` all route through
  `tezgah_judge.override`. An `http://` URL to another host would have sent
  the bearer key and the state in clear. Loopback stays allowed for the tests.
  `consult` now refuses a plain-http `CONSULT_URL` off this machine the same
  way, before any request, as failure class `plain-http`.
- **A Homebrew install survives `brew upgrade` with its default cleanup.**
  The installer now names its keg through the stable `opt/tezgah` link
  (`hooks/tezgah_paths.py::stable_root`). So the farm links, the omp bridge's
  hook path and dsh's `configPath`/`pluginRoot` no longer name the
  versioned keg the cleanup deletes. The session-start attest reads the same
  root, so a brew session reports no drift before or after an upgrade. A
  checkout still names itself.
- **A Windows release install can update, upgrade and uninstall itself.**
  `running_prefix()` now accepts the junction `install.ps1` makes. It also
  accepts the copy `install.ps1` makes when Windows refuses the junction. So
  `tezgah update` finds the release prefix. The default prefix is
  `%LOCALAPPDATA%\tezgah` on Windows. `install.ps1` passes `-Prefix` to
  `--install`. `--upgrade` runs
  `install.ps1 -NoInstall` there instead of `bash`. A missing `bash` or
  `powershell` is a refusal that names it, not a traceback. `--uninstall`
  removes the junction as a link (`bin/tezgah-setup::is_link`).
- **The opencode plugin reads Windows roots.** `TEZGAH_ROOTS` splits on the
  platform delimiter (`;` on Windows), and `shell.env` joins with it. The
  root test uses `path.relative`. So a `C:\` root no longer leaves the plugin
  inert.
- **The `control` rule refuses fewer harmless calls.** A replay of real
  ledgers found 19 refusals. 13 of them were false.
  A multi-line `python3 -c '...'` is now one word, not lines of commands, so a
  switch path, a `>=` or `tezgah-capture` in the script is data. So is the
  body of a `python3 - <<PY` heredoc when bash expands nothing in it. A write
  under the install checkout's own `.tezgah/` is not hook wiring. A Claude
  `settings.json` counts in `~/.claude` or under a root, not in a temp
  fixture. A shell's script (`bash -c`, `bash <<EOF`) is still read.
- **opencode keeps one snapshot per write and one nudge per session.**
  The core captures a write it answers through `tezgah-gate decide`.
  The plugin now captures only a call the core did not answer.
  Both sides name the nudge mark `sha1(session)[:16]`
  (`hooks/tezgah_gate.py::nudge_mark`).
- **The update chip reaches installs on the retired 0.2.0-0.32.0 line.** A
  re-root on 2026-10-04 restarted the numbering at 0.1.1.
  npm last served 0.32.0 before it. `newer()` compared 0.30.0 higher than every
  0.1.x release, so those installs never saw the chip. One constant,
  `hooks/tezgah_update.py::RETIRED`, now holds the retired range. The check
  offers the public release to an install inside it, and the chip adds
  `(line reset)`.

- **omp marks the first effect after an untrusted read.** Its post-tool hook
  now calls the shared `marks`. The effect's row carries the inherited channel.
  The taint notice rides the result. A subagent's report keeps its label, though
  the bridge never sends the report's body.
- **tezgah labels more shell reads as network reads.** These now count:
  `gh issue view|list` and `gh pr view|diff|checkout|list`. A `git clone`
  counts unless it names a local path. A `git pull` or `fetch` counts when it
  names a URL.
  They also count behind `sudo`, `git -C dir` or an `X=1` prefix. A bare
  `git pull` or `fetch`, or one naming a remote, reads the user's own tree and
  stays unlabelled. Every host and the opencode plugin read them the same way.
  Nothing new gets refused.
- **A shell call after a subagent keeps its result size.** On Claude, dsh and
  Codex, such a call inherits the subagent channel. Its row then lost
  `out_bytes`, because the report's byte rule keyed on that channel. The rule
  now keys on the call's own channel. A background Agent launch now records no
  `out_bytes` (unknown) instead of its result's field count.
- **One credential rule on every write route.** It refuses a `ghp_`,
  `sk-live-` or `AKIA` token in a Write, an Edit, a patch and a heredoc. All
  four pass
  `password = os.environ[...]`. The `name=value` shape now counts only next to
  a shell sink. The gate refuses `git add .env` and passes `.env.example`,
  `.env.sample`, `.env.template`, `.env.dist` and `.env.defaults`.
  An identifier such as `pk_users_organization_id` passes: a bare `sk-`, `pk_`
  or `rk_` counts only with its qualifier (`sk-live-`). A documentation
  placeholder (`AKIAIOSFODNN7EXAMPLE`, `ghp_xxxx...`) passes, and so does a
  token in a template or a test fixture. A token the file already holds is
  not refused again.
- **The skip rule reads every write dialect.** A test skip that arrived through
  `patch`, `new_str` or `file_text` used to pass. The rule now reads an
  `apply_patch` file by file, so a skip in its non-test file still passes.
- **A shell redirect or `tee` meets the race and task rules.** The gate refuses
  a shell write into the task record or outside its allowlist. A temp file or a
  device is scratch: `pytest > /tmp/check.log` meets no allowlist and no race.
  A shell `run` row that writes any other file now carries `target`, on Python
  and on opencode. Two sessions that write one file through the shell now
  collide like two edits.
- **One corpus holds every host to the core.** `tests/gate_vectors.json` sends
  each vector through every host's own entry point and matcher. At the base
  commit 44 cells disagreed with the core. Now none does, outside one named
  opencode ceiling.
- **The masker and the status reader drop three misreads.** An escaped `\$'` no longer
  opens an ANSI-C string. A quote left open blanks only what follows it, and an
  apostrophe in a heredoc body opens no quote. A quoted newline, a comment, a
  heredoc body and `exit $?` after a check no longer take the check's status.
  The opencode plugin reads all of these the same way.
- **The word reader follows bash on three shapes.** A `$'it\'s'` is one
  word, so the line after it no longer falls to the
  rough read. The words after a `$( )` or backtick close stay that command's
  arguments. `shell_programs` names the substitutions of an unquoted heredoc
  body and nothing of a quoted one. The fuzzer found all three.
- **The opencode plugin reads a shell line the way the core does.** Its
  masker, word reader, program reader and ledger kind follow the core's. A
  shared corpus pins both sides: the gate-01 prefixes and the status shapes.
- **A prefix bash reads as words no longer hides a shell rule.** Such a
  prefix is a URL's `//`, `a#b`, a glob pair or `'x\'`. The masker read it as
  a comment or an open string and hid the command after it: `HUSKY=0 git
  commit`, `pytest || true`, `tezgah-task phase` or a credential write. `mask()` now
  reads a shell line the way bash does. Source files keep the old reading
  (`mask_source`). `shell_programs` uses the gate's own reader, so `a#b`, a
  redirect target and an unreadable line no longer mislead it. The opencode
  plugin reads the line the same way.
- **A check whose status the line does not keep is no longer a pass.** These
  lines record as ran: `pytest; echo done`, `pytest; echo EXIT=$?`, `pytest &`,
  `pytest > log; tail log`. Each exits 0 whatever pytest found.
  `pytest && echo ok`, `cd x && pytest` and a `set -o pipefail;` pipe still
  pass (`status_hidden`). The NEUTER comment now names only what it denies.
  The piped and neutered remedies name the shape that keeps the status.
- **Two lines each delivering their own `to_human/report.md` are no longer
  serial twins.** `serial_twins` compares the resolved file, not the spelling.
- **A claim's `path:line` citation is not a number.** The containment rule
  lifts it off the statement, like a date.
- **The research skill's `init` example carries `--ask`.** Without it, `init`
  refused the command. The skill also says `source` does not check for a commit
  of the protocol. The order rule proves commit order, not run order.
- **A hook whose core cannot import fails open and says so.** Eleven entry
  points imported the core outside `safe()`. A rename or a broken module ended
  them with a traceback, and on omp that disabled the gate for the session.
  They now exit 0, print one stderr line and write a `crash` row. The status
  line shows a `crash` mark for that session. `tezgah-gate check` exits 3, so
  the MCP `gate_check` no longer reads a dead gate as a pass.
- **The disarmed-gate mark no longer counts PostToolUse rows.** A PostToolUse
  hook keeps writing while a broken PreToolUse lets every call through. Only a
  row from the gate now proves it ran, over write and shell calls.
- **`--sync` no longer leaves a half-empty plugin copy.** It used to delete
  the copy, then copy into it. It now builds each copy in a staging tree beside
  the plugin cache and swaps it in, keeping the copy's `.git`. A sync stopped
  mid-swap is put back by the next one, `.git` included. A failed copy makes
  `--sync` exit 1. Every copied file is 0644, or 0755 when executable.
- **The omp report row compares the bridge byte for byte.** It checked six
  handler names, so a stale or edited bridge passed. It now compares the
  bridge with a fresh render.
- **A malformed `~/.config/tezgah/config.json` is no longer rewritten.**
  `--install` read it as empty and wrote its defaults over the user's roots.
  It now refuses the file, names it, leaves its bytes alone and exits 1.
- **The graph workflows report a failed agent as unknown.** `graph-review` said
  "all four dimensions came back clean" when every dimension failed. It listed
  a finding as refuted when both refuters failed. `graph-impact` dropped a
  failed planner and turned a failed sweep into "no blind spots". Each script
  now names every failure in an `unknown` list. A finding no refuter answered
  stays unverified. A stub runtime (`tests/_workflow_harness.mjs`) tests both.
- **`graph-impact` parses again.** It had one closing parenthesis too many, so
  Claude's runtime could not load it at all.
- **The status line marks graph use on a plugin install.** It tested only
  `mcp__codegraph__`. It now shares the PostToolUse store's test.
- **tezgah records a Claude skill load.** The plugin's PostToolUse matcher
  carries `Skill`, and so does dsh's manifest, which mirrors it. The hook writes
  `skill:<name>` (or the pony/adhd mark). The skill-fitness report then counts
  Claude sessions. Nobody has checked that Claude fires PostToolUse for the
  Skill tool.
- **A host config the installer cannot parse is left alone.** Seven install
  steps read a host's JSON config and then rewrote it. They cover Codex and
  Cursor `hooks.json`, opencode's `opencode.json` and `tui.json`, Cursor's
  `mcp.json` and `cli-config.json`, and omp's `mcp.json`. A trailing comma, a
  `//` comment or a top level that is not an object made the installer write
  its default over the file. `--install` now names that file and the parse
  error, leaves its bytes alone and exits 1.
- **The skill hint can no longer outlive the hook.** It asks once, with a 4 s
  wall-clock deadline, well under omp's 10 s hook kill. The prompt goes out
  redacted and cut at 2,000 characters.
- **A dead judge provider is not paid for on every call.** A 401, 402 or 5xx
  marks it down for five minutes. The mark covers that provider, endpoint and
  key. Until it expires the seam answers with no judgement and sends no request.
- **codegen guards its egress.** It refuses a redirect to another host, a plain
  `http` endpoint off this machine, and a file that carries a credential. Each
  exits 2, so the caller writes the change itself.
- **Every changing write keeps its own backup.** A write that changes a file
  copies it to `<file>.<timestamp>.tezgah-bak` first. Before, only the first
  write left a backup. The oldest timestamped copy is always kept, beside the
  newest four. A bare `<file>.tezgah-bak` from an older release stays as is.
  A full uninstall removes the timestamped backups of tezgah's own state too.
- **`--install` fails when a planned host is not armed.** The run printed MISS
  under a host and still exited 0. Now it exits 1 and names the host and row
  under `not armed:`. Only the arming rows count: hooks wired, the contract
  current, and omp's extension row where an omp CLI exists. Codex
  `hooks trusted`, the provider keys and Claude's plugin copy stay out,
  because a correct fresh install leaves them MISS.
- **Codex write rows know where they ran.** The Codex hook was the one host
  that gave the ledger no cwd. Its write rows carried no workspace, and a
  relative path resolved against the hook process instead of the repository.
- **`tezgah-capture` no longer counts as a read of the screen.** It is the
  pre-write file snapshot CLI. A turn could end on a done claim because this
  run stood in for a screen proof or for a passing check.
- **dsh has no Stop rule.** Its bridge drops every call's outcome, so no check
  there can show a pass. The rule could only refuse honest work there. The
  Stop entry leaves `hosts/dsh/hooks.json` until the bridge carries outcomes.

- **A release publishes only after CI passed on its commit.** `release.yml`
  now runs `ci.yml` as its `ci` job. `npm-publish` and `brew-formula` wait for
  it. v0.1.2 reached npm and brew while its own CI run failed.
- **A test run that runs nothing no longer passes.** A docs-only
  `tests/impacted.py --run` matched no test file and passed with 0 tests. It
  now runs the docs modules. A run where nothing maps, and a `--ref` with no
  change, exit 5. It prints a failed module's log, not only its path.
- **The suite stays out of the real ledger.** Importing `tests/support.py`
  gives the process a temp HOME and drops `TEZGAH_SESSION`. `tests/test_models.py`
  does the same for the `tezgah-route` runs it starts.
- **CI shows what it checks.** The plan report step read the gitignored
  `.tezgah/` and could never fail, so it left CI. It stays a local check. The
  docs now take the CI version list from `.github/workflows/ci.yml`.
  `test-sharded` runs `tests/impacted.py --all` on 3.10 and 3.14 as a
  four-week shadow of the four-version matrix. No matrix cancels its other
  legs on a failure.
- **`bin/tezgah-mcp.py` exists**, the `.py` twin every other Python entry
  point in `bin/` has.

- **Docs that disagreed with the code.** `docs/gate.md` listed Secret before Workspace,
  and `decision` checks them the other way. The Language section did not name `lang-off`.
  `docs/judge.md` counted four callers, and `bin/tezgah-taste` is the fifth. The READMEs
  said fourteen kill switches. CORE names sixteen. Forty-one bare-file citations, six in
  code comments, and the repeat-guard anchor in "Adding a rule" pointed at the wrong
  lines.

- **Uninstall sweeps four more legacy switches.** An uninstall now also sweeps
  `workspace-off`, `triage-off`, `docs-judge-off` and `update-check-off` from `~/.claude`.
- **The Homebrew formula runs.** It copied `tezgah-setup` out of the tree, so
  the copy could not find `hooks/` and died on import. It now links into the
  installed tree, and also installs the command as `tezgah`.

[Unreleased]: https://github.com/r1z4x/tezgah/compare/v1.8.3...HEAD
[1.8.3]: https://github.com/r1z4x/tezgah/releases/tag/v1.8.3
[1.8.2]: https://github.com/r1z4x/tezgah/releases/tag/v1.8.2
[1.8.1]: https://github.com/r1z4x/tezgah/releases/tag/v1.8.1
[1.8.0]: https://github.com/r1z4x/tezgah/releases/tag/v1.8.0
[1.7.0]: https://github.com/r1z4x/tezgah/releases/tag/v1.7.0
[1.6.0]: https://github.com/r1z4x/tezgah/releases/tag/v1.6.0
[1.5.1]: https://github.com/r1z4x/tezgah/releases/tag/v1.5.1
[1.5.0]: https://github.com/r1z4x/tezgah/releases/tag/v1.5.0
[1.4.0]: https://github.com/r1z4x/tezgah/releases/tag/v1.4.0
[1.3.0]: https://github.com/r1z4x/tezgah/releases/tag/v1.3.0
[1.2.0]: https://github.com/r1z4x/tezgah/releases/tag/v1.2.0
[1.1.0]: https://github.com/r1z4x/tezgah/releases/tag/v1.1.0
[1.0.0]: https://github.com/r1z4x/tezgah/releases/tag/v1.0.0
