---
name: plan-sync
description: >
  Closes out finished plans: fetches origin, checks each open plan's branch for a
  merged or closed PR (or a branch merged into main), marks it done or discarded,
  moves it to .tezgah/plans/done/ (a done plan only with an approving review),
  rewrites the README status table, and commits one `plan: done NNN slug` (or
  `plan: discard`) per moved plan in the private .tezgah repository. Use when the user says
  "/tezgah:plan-sync", "sync plans", "close finished plans", or after PRs were merged.
  Never deletes branches and never touches files outside .tezgah/plans/.
---

# plan-sync

1. Resolve the root: `ROOT=$(git rev-parse --show-toplevel)`. If it fails, stop and
   say plans need a git repo. If `$ROOT/.tezgah/plans/open` is missing, say so and stop.
2. `git fetch --prune origin`.
3. For each `.tezgah/plans/open/*.md` with a non-empty `branch:`, run
   `gh pr list --head <branch> --state all --json number,state,mergedAt --limit 1`.
   If the command fails (auth, network), record the exact error, skip that plan, and
   report the failure at the end. Never treat a failed call as "no PR".
4. Decide per plan:
   - `state == "MERGED"`: done. Fill `pr:` if empty, append to `## State` the line
     `merged PR #N on <mergedAt>`.
   - `state == "CLOSED"` and `mergedAt == null`: discarded. Append
     `closed without merge, PR #N`.
   - gh returned `[]`: fallback `git branch -r --merged origin/main | grep -q "origin/<branch>"`.
     If it matches, treat as done and append `merged without PR`.
   - otherwise: leave the plan untouched.
5. For every plan marked done: if `## Acceptance` still has `- [ ]` boxes, still move
   it but append the line `acceptance boxes unchecked at sync` to `## State`.
6. Move each done or discarded plan with
   `~/.config/tezgah/bin/tezgah-task close NNN done|discarded`: it sets `status:` and
   `updated:` and moves the file to `.tezgah/plans/done/`. It refuses `done` unless the
   plan records `review: <reviewer> approve` - a fresh reviewer (the host's
   `tezgah-reviewer` subagent) read `git diff <base>..HEAD` and
   `tezgah-task review NNN <reviewer> approve` wrote the verdict - and it refuses
   the active task. A refused plan stays open: report it with the refusal, never
   move it by hand.
7. Rewrite the README status table: `~/.config/tezgah/bin/tezgah-render-table` (installed by `bin/tezgah-setup --install`; if it is missing, run that script)
   (one row per open plan, sorted by id; it prints the rows). No `--pr-info` here:
   the row's `pr` cell comes from the plan files, and review/check enrichment
   belongs to plan-status.
8. If anything moved, one commit per moved plan, in the private repository
   (`.tezgah/` is gitignored in the project and never enters its git):
   `git -C "$ROOT/.tezgah" add plans/README.md plans/done/NNN-slug.md &&
   git -C "$ROOT/.tezgah" rm -q --cached --ignore-unmatch plans/open/NNN-slug.md &&
   git -C "$ROOT/.tezgah" -c user.name=tezgah -c user.email=tezgah@localhost commit -q -m "plan: done NNN slug"`
   (explicit paths only, never `git -C .tezgah add -A plans`; the `rm --cached`
   records the move whether or not the open copy was ever committed; verb
   `discard` for discarded plans; the README change rides with the first commit;
   no remote, no push).
   Messages must carry no AI/model attribution of any kind: no Co-Authored-By,
   no "Generated with" / "Made with", no robot emoji, no Claude/Anthropic/OpenAI/
   GPT/Codex/Gemini/Cursor/Copilot credit.
9. Report four lists: moved plans (with done/discarded and the evidence line),
   plans `close` refused (with its reason), still-open plans, and gh failures. Never delete branches, never edit code outside
   `.tezgah/plans/`.

## Format

Plan file `.tezgah/plans/open/NNN-slug.md` (status open|blocked) or `.tezgah/plans/done/NNN-slug.md`
(status done|discarded). Frontmatter: id, title, status, branch (`plan/NNN-slug`),
pr, created, updated, allowed_paths, plus phase/allowed_from/review when set.
Sections: `## Goal`, `## Acceptance` (checkboxes), `## State`
(evidence), `## Next` (one action or `BLOCKED: <reason>`). README table lives between
`<!-- status:start -->` and `<!-- status:end -->` with columns
`| id | title | status | branch | pr | next |`.
