---
name: plan-sync
description: >
  Closes out finished plans: fetches origin, checks each open plan's branch for a
  merged or closed PR (or a branch merged into main), marks it done or discarded,
  moves it to plans/done/, rewrites the README status table, and commits one
  `plan: done NNN slug` (or `plan: discard`) per moved plan. Use when the user says
  "/plan-sync", "sync plans", "close finished plans", or after PRs were merged.
  Never deletes branches and never touches files outside plans/.
---

# plan-sync

1. Resolve the root: `ROOT=$(git rev-parse --show-toplevel)`. If it fails, stop and
   say plans need a git repo. If `$ROOT/plans/open` is missing, say so and stop.
2. `git fetch --prune origin`.
3. For each `plans/open/*.md` with a non-empty `branch:`, run
   `gh pr list --head <branch> --state all --json number,state,mergedAt --limit 1`.
   If the command fails (auth, network), record the exact error, skip that plan, and
   report the failure at the end. Never treat a failed call as "no PR".
4. Decide per plan:
   - `state == "MERGED"`: set `status: done`, `updated: $(date +%F)`, fill `pr:` if
     empty, append to `## State` the line `merged PR #N on <mergedAt>`.
   - `state == "CLOSED"` and `mergedAt == null`: set `status: discarded`,
     `updated: $(date +%F)`, append `closed without merge, PR #N`.
   - gh returned `[]`: fallback `git branch -r --merged origin/main | grep -q "origin/<branch>"`.
     If it matches, treat as done and append `merged without PR`.
   - otherwise: leave the plan untouched.
5. For every plan marked done: if `## Acceptance` still has `- [ ]` boxes, still move
   it but append the line `acceptance boxes unchecked at sync` to `## State`.
6. Move each done or discarded plan: `git mv plans/open/NNN-slug.md plans/done/NNN-slug.md`.
7. Rewrite the README status table: `~/.config/tezgah/bin/tezgah-render-table` (installed by `bin/tezgah-setup --install`; if it is missing, run that script)
   (one row per open plan, sorted by id; it prints the rows). For plan-status pass
   `--pr-info NNN='(STATE | review | checks)'` per enriched plan.
8. If anything moved, one commit per moved plan:
   `git add plans/README.md plans/open/NNN-slug.md plans/done/NNN-slug.md && git commit -m "plan: done NNN slug"`
   (explicit paths only, never `git add -A plans`) (verb `discard` for
   discarded plans; the README change rides with the first commit), then `git push`.
   Messages must carry no AI/model attribution of any kind: no Co-Authored-By,
   no "Generated with" / "Made with", no robot emoji, no Claude/Anthropic/OpenAI/
   GPT/Codex/Gemini/Cursor/Copilot credit.
9. Report three lists: moved plans (with done/discarded and the evidence line),
   still-open plans, and gh failures. Never delete branches, never edit code outside
   `plans/`.

## Format

Plan file `plans/open/NNN-slug.md` (status open|blocked) or `plans/done/NNN-slug.md`
(status done|discarded). Frontmatter: id, title, status, branch (`plan/NNN-slug`),
pr, created, updated. Sections: `## Goal`, `## Acceptance` (checkboxes), `## State`
(evidence), `## Next` (one action or `BLOCKED: <reason>`). README table lives between
`<!-- status:start -->` and `<!-- status:end -->` with columns
`| id | title | status | branch | pr | next |`.
