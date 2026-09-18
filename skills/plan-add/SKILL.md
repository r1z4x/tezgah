---
name: plan-add
description: >
  Creates a new plan file under <git root>/plans/open/ from free text, bootstraps
  the plans/ layer (README + open/ + done/) if missing, refreshes the README status
  table, and commits it on main as `plan: add NNN slug`. Use when a piece of work
  spans sessions or waits on something and the user says "/tezgah:plan-add <text>",
  "add a plan", "track this as a plan", or "make a plan for ...". Do NOT use for
  small self-contained edits that fit in one session.
argument-hint: "<one-line description of the work>"
---

# plan-add

Input: `$ARGUMENTS` (free text describing the work). Run these steps in order.

1. Resolve the root: `ROOT=$(git rev-parse --show-toplevel)`. If it fails, stop and
   say plans need a git repo.
2. Bootstrap what is missing under `$ROOT/plans` - a partial tree counts: run
   `mkdir -p plans/open plans/done`, and write `plans/README.md` from the template
   below ONLY when that file is absent. Never overwrite an existing README: it is
   the plans layer's own doc, and other plans' rows live in its table.
3. Next id: `ls plans/open plans/done | grep -oE '^[0-9]{3}' | sort -n | tail -1`,
   plus 1, zero-padded to 3 digits (`001` if empty). Slug = kebab-case, at most 5
   words, derived from the title you distill from `$ARGUMENTS`.
4. Capture surroundings, at most a few tool calls: `git log --oneline -10`, then
   `grep -rIl --exclude-dir=.git --exclude-dir=node_modules '<key noun>' .` for the
   1-3 key nouns in the request. Note file paths and anything that changes the plan.
5. Write `plans/open/NNN-slug.md` in the Format below. Goal from the request.
   Acceptance: checkable criteria, each with the command that proves it when
   possible. State: `not started` plus the findings from step 4. Next: the first
   concrete action. Dates: `date +%F`.
6. Rewrite the README status table: `~/.config/tezgah/bin/tezgah-render-table` (installed by `bin/tezgah-setup --install`; if it is missing, run that script)
   (one row per open plan, sorted by id; it prints the rows). A new plan has no PR
   state to enrich, so no `--pr-info` here; that enrichment belongs to plan-status.
7. Commit on main - first check you are there: `git symbolic-ref --short HEAD` must print
   `main`, otherwise stop and tell the user (a plan committed on a feature branch is
   invisible to plan-sync). Then `git add plans/README.md plans/open/NNN-slug.md &&
   git commit -m "plan: add NNN slug"`, and `git push` ONLY if `git remote` is non-empty
   (explicit paths only: `git add plans` would sweep in files another agent is writing)`.
   The message must carry no AI/model attribution of any kind: no Co-Authored-By,
   no "Generated with" / "Made with", no robot emoji, no Claude/Anthropic/OpenAI/
   GPT/Codex/Gemini/Cursor/Copilot credit.
8. Report the file path and the table row.
9. Hand it to `tezgah-task` - the user's command, never the session's:
   `~/.config/tezgah/bin/tezgah-task start NNN --phase discovery [--allow '<glob>' ...]`
   writes `phase:` (and `allowed_paths:` with `--allow`) into this file and
   clears the phase from every other open plan, and the gate then allows a write
   only from `implementation` on and only inside those globs. Moving the phase
   later is the user's action too: when a write is refused for its phase or its
   path, ask the user to change the task - do not run this command, and do not
   retype the frontmatter - because the gate refuses a session's own edit to the
   record and a session's own call to the CLI, which is what keeps the boundary
   the user set. The refusal names no command; the ask is the way through it.

## Format

Plan file (`plans/open/NNN-slug.md`, moved to `plans/done/` when done or discarded):

```
---
id: 001
title: <one line>
status: open | blocked | done | discarded
branch: plan/001-slug
pr:
created: YYYY-MM-DD
updated: YYYY-MM-DD
phase:                 # optional; tezgah-task writes it (step 9)
allowed_paths:         # optional; `- glob` lines tezgah-task writes with --allow
  - <glob>
---
## Goal
<1-3 sentences>
## Acceptance
- [ ] <checkable criterion, ideally with the command that proves it>
## State
<current state + observed evidence; "not started" initially>
## Next
<single next action, or "BLOCKED: <reason>">
```

Both keys are optional and absent from a plan this skill writes: `tezgah-task`
sets them when the user starts the task (step 9). `phase:` - `discovery`,
`implementation` or `verification`, at most one open plan carrying it - is the
activation key the gate reads, and `allowed_paths:` is the scope its writes have
to stay inside, one glob per `- ` line; empty or absent means any path in the
repo.

## README template (write verbatim when plans/ is missing)

```
# Plans

One markdown file per piece of work that spans sessions or waits on something.
Small self-contained edits do not get a plan.

- `open/`  status open or blocked. `done/` status done or discarded.
- File: `NNN-slug.md`, frontmatter id/title/status/branch/pr/created/updated,
  plus the optional `phase` and `allowed_paths` while the plan is the active task,
  sections Goal, Acceptance (checkboxes), State (evidence), Next (one action or BLOCKED).
- Work for a plan happens on branch `plan/NNN-slug`; a merged PR (or a branch merged
  into main) is the done signal read by `/tezgah:plan-sync`.
- Plan edits are committed on main as `plan: <verb> NNN <slug>` and pushed.
- Skills: `/tezgah:plan-add <text>`, `/tezgah:plan-status`, `/tezgah:plan-sync`.

<!-- status:start -->
| id | title | status | branch | pr | next |
|---|---|---|---|---|---|
<!-- status:end -->
```
