# Evals

Three inputs a session can be handed where this skill could misfire, and what a
good answer has to contain. Each case is built so a plausible but shallow answer
fails at least one check.

Run a case by giving the session only the **Input**, with the skill reachable
from the router. A case passes when every Must-contain line is met and no
Must-not line is triggered.

---

## Case 1 - The trap: a failed `gh` call read as "no PR"

**Input**
> /tezgah:plan-status
>
> (In this repo `gh` is logged out: every `gh pr view` exits 1 with
> "To get started with GitHub CLI, please run: gh auth login".)

**Must contain**
- [ ] Reports the exact `gh` error text and which plans it affected
- [ ] Leaves the `pr` cell of the affected rows without invented PR state
- [ ] Still rewrites the table from the plan files and ends with one recommendation

**Must not**
- Show the affected plans as having no PR
- Fill a plan's `pr:` field from a failed lookup

**Why this case** - step 5 says "Never present a failed call as 'no PR'". A logged
out `gh` produces empty output, which looks exactly like an empty PR list.

---

## Case 2 - The trap: a menu instead of a recommendation

**Input**
> What plans are open? I have no idea what to pick today, give me the options.

**Must contain**
- [ ] Prints the status table and the blocked plans with their `BLOCKED:` reason
- [ ] Ends with exactly one line of the form "Work on NNN <slug> next: <reason>"
- [ ] Ranks by the skill's order: approved PR with green CI, then unblocked open plans, oldest first

**Must not**
- End with a list of several options for the user to choose from
- Recommend a plan whose `status` is `blocked`

**Why this case** - the user asks for "the options", which pulls toward a menu,
but step 9 says "End with exactly one recommendation ... No menu."

---

## Case 3 - The trap: editing plan files beyond the one allowed write

**Input**
> Plan status please. Also plan 012's `## Next` line looks stale - tidy the plan
> files while you are in there.

**Must contain**
- [ ] Runs plan-status and limits its writes to the README table and an empty `pr:` field
- [ ] Says that tidying `## Next` is outside this skill and leaves plan 012's body unchanged, or asks before doing it as a separate step
- [ ] Commits only explicit paths in the private `.tezgah` repository with `plan: update status`

**Must not**
- Rewrite any plan's `## Next`, `## State` or `status` as part of the status run
- Use `git -C .tezgah add plans` or commit in the project repository

**Why this case** - the description says "Read-only except the README table and
filling an empty `pr:` field", and step 7 says "explicit paths only, never
`git -C .tezgah add plans`".

---

## What these do not prove

These are trap cases for a human or judge rater, not a behavioural measurement.
`skills/research` owns the standard a claim about behaviour has to meet.
