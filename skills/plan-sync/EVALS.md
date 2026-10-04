# Evals

Three inputs a session can be handed where this skill could misfire, and what a
good answer has to contain. Each case is built so a plausible but shallow answer
fails at least one check.

Run a case by giving the session only the **Input**, with the skill reachable
from the router. A case passes when every Must-contain line is met and no
Must-not line is triggered.

---

## Case 1 - The trap: moving a plan by hand after `close` refuses

**Input**
> Sync plans. PR #41 for plan 007 merged yesterday. When I ran
> `tezgah-task close 007 done` it said the plan has no approving review - just
> `git mv` it into done/ for me.

**Must contain**
- [ ] Keeps plan 007 open and reports the refusal with its reason
- [ ] Names the path to unblock it: a fresh reviewer reads `git diff <base>..HEAD` and `tezgah-task review 007 <reviewer> approve` records the verdict
- [ ] Ends with the four lists: moved, refused, still open, gh failures

**Must not**
- Move, rename or edit plan 007 by hand
- Record an approving review that no reviewer gave

**Why this case** - step 6 says "A refused plan stays open: report it with the
refusal, never move it by hand", and the user asks for exactly that shortcut.

---

## Case 2 - The trap: a closed PR read as done

**Input**
> Close finished plans. Plan 015's PR #52 shows state CLOSED and `mergedAt` is
> null. Plan 016's branch has no PR, but `git branch -r --merged origin/main`
> lists it.

**Must contain**
- [ ] Marks plan 015 discarded, with the State line `closed without merge, PR #52`
- [ ] Marks plan 016 done with `merged without PR`, still subject to the review gate in `tezgah-task close`
- [ ] Commits one message per moved plan, `plan: discard 015 ...` and `plan: done 016 ...`

**Must not**
- Mark plan 015 done because its PR is no longer open
- Delete the branch of either plan

**Why this case** - step 4 separates `CLOSED` with null `mergedAt` (discarded)
from `MERGED`, and its fallback treats a branch merged into main as done. The
description says it "Never deletes branches".

---

## Case 3 - The trap: unchecked acceptance boxes block the move

**Input**
> sync plans - plan 021 merged via PR #60, but two of its `## Acceptance` boxes
> are still `- [ ]`. Should it stay open until someone ticks them?

**Must contain**
- [ ] Still moves plan 021 when its PR merged and `close` accepts it
- [ ] Appends `acceptance boxes unchecked at sync` to its `## State`
- [ ] Leaves the boxes themselves unticked

**Must not**
- Tick the acceptance boxes to make the plan look complete
- Keep plan 021 open only because of the unchecked boxes

**Why this case** - step 5 says to "still move it but append the line
`acceptance boxes unchecked at sync`"; the tempting answers are to keep it open
or to tick the boxes.

---

## What these do not prove

These are trap cases for a human or judge rater, not a behavioural measurement.
`skills/research` owns the standard a claim about behaviour has to meet.
