---
name: plan-status
description: >
  Reads every open plan under <git root>/plans/open/, enriches rows with live PR
  state from `gh`, rewrites the README status table, commits it as
  `plan: update status`, and ends with a single recommendation for which plan to
  work on next. Use when the user says "/plan-status", "what plans are open",
  "plan status", "where are we on the plans", or at the start of a session to pick
  work. Read-only except the README table and filling an empty `pr:` field.
---

# plan-status

1. Resolve the root: `ROOT=$(git rev-parse --show-toplevel)`. If it fails, stop and
   say plans need a git repo. If `$ROOT/plans/open` is missing, say so and stop.
2. For each `plans/open/*.md`: read the frontmatter (id, title, status, branch, pr)
   and the first line of the `## Next` section.
3. If `pr:` is set, run
   `gh pr view <pr> --json state,mergedAt,reviewDecision,statusCheckRollup -q '[.state, .reviewDecision, ([.statusCheckRollup[]?.conclusion] | unique | join(","))] | map(select(. != null and . != "")) | join(" | ")'`
   and append the result to that row's `pr` cell, e.g. `#12 (OPEN | APPROVED | SUCCESS)`.
4. If `pr:` is empty and `branch:` is set, run
   `gh pr list --head <branch> --state all --json number -q '.[0].number'`. If a
   number comes back, write it into the plan file's `pr:` field and set
   `updated: $(date +%F)`. This is the only plan-file write this skill makes.
5. If any `gh` call fails (exit code non-zero, auth error, network error), record the
   exact error and say so in the report. Never present a failed call as "no PR".
6. Rewrite the README status table: `~/.claude/bin/tezgah-render-table` (installed by `bin/tezgah-setup --install`; if it is missing, run that script)
   (one row per open plan, sorted by id; it prints the rows). For plan-status pass
   `--pr-info NNN='(STATE | review | checks)'` per enriched plan.
7. If `git status --porcelain plans` shows changes:
   `git add plans/README.md <plan files you changed> && git commit -m "plan: update status" && git push
   (explicit paths only, never `git add plans`)`.
   The message must not contain Anthropic, Claude, or any Co-Authored-By trailer.
8. Print the table, then one line per plan with `status: blocked` quoting its
   `BLOCKED: <reason>`, then any gh failures.
9. End with exactly one recommendation: "Work on NNN <slug> next: <reason>". No menu.
   Prefer plans with an approved PR and green CI, then open plans with no blocker,
   oldest first.

## Format

Plan file `plans/open/NNN-slug.md` (status open|blocked) or `plans/done/NNN-slug.md`
(status done|discarded). Frontmatter: id, title, status, branch (`plan/NNN-slug`),
pr, created, updated. Sections: `## Goal`, `## Acceptance` (checkboxes), `## State`
(evidence), `## Next` (one action or `BLOCKED: <reason>`). README table lives between
`<!-- status:start -->` and `<!-- status:end -->` with columns
`| id | title | status | branch | pr | next |`.
