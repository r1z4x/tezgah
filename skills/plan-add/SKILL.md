---
name: plan-add
description: >
  Creates a new plan file under <git root>/.tezgah/plans/open/ from free text, bootstraps
  the .tezgah/plans/ layer (README + open/ + done/) if missing, refreshes the README status
  table, and commits it as `plan: add NNN slug` in the private .tezgah repository. Use when a piece of work
  spans sessions or waits on something and the user says "/tezgah:plan-add <text>",
  "add a plan", "track this as a plan", or "make a plan for ...". Do NOT use for
  small self-contained edits that fit in one session.
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
   name no command). State: `not started` plus the findings from step 4. Next: the
   first concrete action. Dates: `date +%F`. `allowed_paths:`: the globs the work
   will write, from the files step 4 found (`apps/admin/**`, `packages/ui/src/**`),
   narrow enough that a write outside them is a surprise - the plan names its own
   scope, and `tezgah-task start` without `--allow` holds the task to it.
6. Rewrite the README status table: `~/.config/tezgah/bin/tezgah-render-table` (installed by `bin/tezgah-setup --install`; if it is missing, run that script)
   (one row per open plan, sorted by id; it prints the rows). A new plan has no PR
   state to enrich, so no `--pr-info` here; that enrichment belongs to plan-status.
7. Commit in the private repository, never the project's:
   `git -C "$ROOT/.tezgah" add plans/README.md plans/open/NNN-slug.md &&
   git -C "$ROOT/.tezgah" -c user.name=tezgah -c user.email=tezgah@localhost commit -q -m "plan: add NNN slug"`
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
   scope included - and never suggest dropping it. Moving the phase
   later is the user's action too: when a write is refused for its phase or its
   path, ask the user to change the task - do not run this command, and do not
   retype the frontmatter - because the gate refuses a session's own edit to the
   record and a session's own call to the CLI, which is what keeps the boundary
   the user set. The refusal names no command; the ask is the way through it.

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

## README template (write verbatim when .tezgah/plans/ is missing)

```
# Plans

One markdown file per piece of work that spans sessions or waits on something.
Small self-contained edits do not get a plan.

- `open/`  status open or blocked. `done/` status done or discarded.
- File: `NNN-slug.md`, frontmatter id/title/status/branch/pr/created/updated,
  `allowed_paths` (the plan's scope), `phase` while it is the active task and
  `review` once a fresh reviewer read its diff,
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
