---
name: plan-add
description: >
  Creates a new plan file under <git root>/.tezgah/plans/open/ from free text, bootstraps
  the .tezgah/plans/ layer (README + open/ + done/) if missing, refreshes the README status
  table, and commits it as `plan: add NNN slug` in the private .tezgah repository. Use when a piece of work
  spans sessions or waits on something and the user says "/tezgah:plan-add <text>",
  "add a plan", "track this as a plan", or "make a plan for ...". Do NOT use for
  small self-contained edits that fit in one session. Not for reading which plans
  are open - use `plan-status`.
argument-hint: "<one-line description of the work>"
---

# plan-add

Input: `$ARGUMENTS` (free text describing the work). Run these steps in order.

1. Resolve the root: `ROOT=$(git rev-parse --show-toplevel)`. If it fails, stop and
   say plans need a git repo.
2. Bootstrap what is missing under `$ROOT/.tezgah/plans` - a partial tree counts: run
   `mkdir -p .tezgah/plans/open .tezgah/plans/done`, and write `.tezgah/plans/README.md` from the template
   below ONLY when that file is absent. Never overwrite an existing README: it is
   the plans layer's own doc, and other plans' rows live in its table. `.tezgah/`
   never enters the project's git: it is listed in `$ROOT/.gitignore` (`/.tezgah/`)
   and holds its own repository, `$ROOT/.tezgah/.git`. Session start creates both;
   if either is missing, append `/.tezgah/` to `.gitignore` and run
   `git init -q "$ROOT/.tezgah"`. Never force-add a `.tezgah` path into the project.
3. Next id: `ls .tezgah/plans/open .tezgah/plans/done | grep -oE '^[0-9]{3}' | sort -n | tail -1`,
   plus 1, zero-padded to 3 digits (`001` if empty). Slug = kebab-case, at most 5
   words, derived from the title you distill from `$ARGUMENTS`, in English: the
   slug becomes both the file name and the branch (`plan/NNN-slug`), and both are
   permanent and public, so the gate refuses one that is not English (the language
   rule) - any non-ASCII letter, or a Turkish word it knows: `durum-onarimi` is
   `status-repair`. If the wording came from
   the user and is not Turkish, say so and let them settle it.
4. Capture surroundings, at most a few tool calls: `git log --oneline -10`, then
   `grep -rIl --exclude-dir=.git --exclude-dir=node_modules '<key noun>' .` for the
   1-3 key nouns in the request. Note file paths and anything that changes the plan.
5. Write `.tezgah/plans/open/NNN-slug.md` in the Format below. Goal from the request.
   Acceptance: checkable criteria, each with the command that proves it - or the
   word `unverifiable` and why, since *when possible* is the loophole
   (`~/.config/tezgah/bin/tezgah-render-table --acceptance` reports the items that
   name no command). An item that names no command keeps the plan out of a
   writing phase (`tezgah-task` refuses it, through the predicate `--strict`
   refuses on), so this is the plan's own check, not a report read later. State:
   `not started` plus the findings from
   step 4. Next: the first concrete action. Dates: `date +%F`. `allowed_paths:`:
   the globs the work will write, from the files step 4 found (`apps/admin/**`,
   `packages/ui/src/**`), narrow enough that a write outside them is a surprise
   - the plan names its own scope, and `tezgah-task start` without `--allow`
   holds the task to it. A plan that has to spike an assumption first (does the
   approach work at all?) writes the four `spike:` keys below: `implementation`
   is refused while `spike_recorded:` names no answer, so the answer is recorded
   before the build rather than after it. `after:`: the ids of the open plans
   this one cannot start before (`after: 012, 015`), only when step 4 found a
   real dependency - a plan with none can run beside the others, and
   `tezgah-task status` names which ready plans share no `allowed_paths:` prefix.
6. Rewrite the README status table: `~/.config/tezgah/bin/tezgah-render-table` (installed by `bin/tezgah-setup --install`; if it is missing, run that script)
   (one row per open plan, sorted by id; it prints the rows). A new plan has no PR
   state to enrich, so no `--pr-info` here; that enrichment belongs to plan-status.
7. Commit in the private repository, never the project's:
   `git -C "$ROOT/.tezgah" add plans/README.md plans/open/NNN-slug.md &&
   git -C "$ROOT/.tezgah" commit -q -m "plan: add NNN slug"`
   (explicit paths only: `git -C .tezgah add plans` would sweep in files another
   agent is writing). It has no remote, so nothing is pushed.
   The message must carry no AI/model attribution of any kind: no Co-Authored-By,
   no "Generated with" / "Made with", no robot emoji, no Claude/Anthropic/OpenAI/
   GPT/Codex/Gemini/Cursor/Copilot credit.
8. Report the file path and the table row.
9. Hand it to `tezgah-task` - the user's command, never the session's:
   `~/.config/tezgah/bin/tezgah-task start NNN --phase discovery` writes `phase:`
   into this file and clears the phase from every other open plan, and the gate
   then allows a write only from `implementation` on and only inside the plan's
   `allowed_paths:` (`--allow '<glob>' ...` replaces them). Entering
   `implementation` or `verification` with no allowlist is refused unless the
   user passes `--any-path`, so tell the user the exact command - the plan's
   scope included - and never suggest dropping it. Three more refusals land at
   the same moment, and the user fixes them in the plan, not the command: a
   writing phase while any Acceptance item names no command, and
   `implementation` while the plan's spike is unanswered (both refused with the
   file and the reader that reported it); and `implementation` is refused while
   the tree is dirty, because the phase starts by recording `checkpoint:` - the
   commit the work returns to - and uncommitted work has none to record. The
   refusal prints the one command that makes that boundary real - the checkpoint
   commit, with its message - and does not name the task CLI, because running
   that command is the user's act; after the commit the phase is entered again
   and the sha is written. Moving the phase
   later is the user's action too: when a write is refused for its phase or its
   path, ask the user to change the task - do not run this command, and do not
   retype the frontmatter - because the gate refuses a session's own edit to the
   record and a session's own call to the CLI, which is what keeps the boundary
   the user set. That refusal names no command; the ask is the way through it.

10. If the work settles a decision that is hard to reverse, spans components, or
    keeps being re-explained, record it as an ADR under `.tezgah/decisions/` with
    `~/.config/tezgah/bin/tezgah-decisions` - one `NNN-slug.md` in the private `.tezgah` repository,
    carrying the context, the decision, its status and its consequences. It is the
    one artifact a later reader can reject without reading the diff, which is why
    `skills/feature-audit/SKILL.md` makes a capability change owe one. Check the
    layer with `~/.config/tezgah/bin/tezgah-decisions check`; it refuses a record with no status and
    a `supersedes:` naming no record.

## Format

Plan file (`.tezgah/plans/open/NNN-slug.md`, moved to `.tezgah/plans/done/` when done or discarded):

```
---
id: 001
title: <one line>
status: open | blocked | done | discarded
branch: plan/001-slug
pr:
created: YYYY-MM-DD
updated: YYYY-MM-DD
allowed_paths:
  - <glob>
after:
---
## Goal
<1-3 sentences>
## Acceptance
- [ ] <checkable criterion, with the command that proves it - or `unverifiable`
      and why>
## State
<current state + observed evidence; "not started" initially>
## Next
<single next action, or "BLOCKED: <reason>">
```

`allowed_paths:` is written here, at creation (step 5): the scope the task's
writes have to stay inside, one glob per `- ` line. `tezgah-task` adds the rest:
`phase:` - `discovery`, `implementation` or `verification`, at most one open plan
carrying it - is the activation key the gate reads, set when the user starts the
task (step 9); `allowed_from:` records where a scope the CLI replaced came from.
`tezgah-task phase verification` lists what the plan owes before it is done: its
acceptance commands run unpiped, and a fresh reviewer (the host's
`tezgah-reviewer` subagent) reading the diff, whose verdict
`tezgah-task review NNN <reviewer> approve|changes` records as `review:`.
`tezgah-task close NNN done` (plan-sync) refuses without an `approve`.

`after:` names the plans that must be done before this one starts - a `- NNN`
block or `after: 012, 015`. `tezgah-task status` reads it: each open plan's
Acceptance boxes ticked (`acceptance 3/8 checked`), what it still waits on
(`waits on 012 (open)`), and a `parallel:` line naming the ready plans whose
`allowed_paths:` share no prefix, which can run at once in separate worktrees.
An `after:` id no plan carries, or an open plan whose `status:` is not open or
blocked, is a `FAIL` line there.

`checkpoint:` is written by `tezgah-task` when the phase moves to
`implementation`: the sha of the commit the work returns to, or `pending` while
the tree still holds work no commit names - and while it reads `pending` the gate
refuses that phase's writes until the tree is committed, because one state to
return to is what a large refactor has instead of 200 per-file snapshots
(`bin/tezgah-rollback` restores one file; it is not a checkpoint).

The four `spike:` keys are optional and go together, on a plan that must answer
one question before it can be built: `spike:` is that question, `spike_box:` the
time box (minutes, or one focused session), `spike_recorded:` where the answer
is recorded - empty until it is, which is what refuses `implementation` - and
`spike_throwaway:` whether the code is thrown away once it has answered. Nothing
enforces the throwaway half, because `allowed_paths:` already does: a spike pins
its scope to a scratch path and is never merged, and the knowledge, not the
prototype, is what the plan keeps.

## README template (write verbatim when .tezgah/plans/ is missing)

```
# Plans

One markdown file per piece of work that spans sessions or waits on something.
Small self-contained edits do not get a plan.

- `open/`  status open or blocked. `done/` status done or discarded.
- File: `NNN-slug.md`, frontmatter id/title/status/branch/pr/created/updated,
  `allowed_paths` (the plan's scope), `phase` while it is the active task,
  `checkpoint` in the implementation phase (the commit the work returns to) and
  `review` once a fresh reviewer read its diff, plus the optional `spike` keys
  on a plan that answers one question before building and `after` (the plan ids
  it waits on),
  sections Goal, Acceptance (checkboxes: each item carries the command that proves
  it, or `unverifiable` and why), State (evidence), Next (one action or BLOCKED).
- Work for a plan happens on branch `plan/NNN-slug`; a merged PR (or a branch merged
  into main) is the done signal read by `/tezgah:plan-sync`.
- `.tezgah/` is gitignored in the project and is its own git repository; plan
  edits are committed there as `plan: <verb> NNN <slug>`, never in the project.
- Skills: `/tezgah:plan-add <text>`, `/tezgah:plan-status`, `/tezgah:plan-sync`.

<!-- status:start -->
| id | title | status | branch | pr | next |
|---|---|---|---|---|---|
<!-- status:end -->
```
