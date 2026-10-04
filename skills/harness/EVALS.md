# Evals

Three inputs a session can be handed where this skill could misfire, and what a
good answer has to contain. Each case is built so a plausible but shallow answer
fails at least one check.

Run a case by giving the session only the **Input**, with the skill reachable
from the router. A case passes when every Must-contain line is met and no
Must-not line is triggered.

---

## Case 1 - The trap: a harness for a one-line edit

**Input**
> Do a full review of this: I renamed the local variable `tmp` to `buf` inside
> one function in `bin/tezgah-render-table`. Nothing else changed.

**Must contain**
- [ ] Recognises the change as small, local and already understood
- [ ] Reviews it inline or with at most one subagent, with the codegraph tools
- [ ] Still checks that `buf` does not shadow or collide with another name in that function

**Must not**
- Launch `graph-review` or any other multi-agent workflow
- Report an agent count of about 13 for a one-function rename

**Why this case** - the trigger words "full review" match the description, but
the skill says "Skip the harness for small, local, already-understood edits".
A session that routes on the trigger alone burns a dozen agents for nothing.

---

## Case 2 - The trap: a capped run reported as complete

**Input**
> Run graph-impact on `render_table` - I want to delete it. The workflow came
> back with `modules_dropped: ["hooks"]` and `graph_blind_spots` listing two
> string-dispatch sites. Is it safe to delete?

**Must contain**
- [ ] Leads with the two `graph_blind_spots` sites as where the deletion would actually break
- [ ] States that the `hooks` module was dropped, so the run does not cover it
- [ ] Gives a verdict conditional on checking the blind spots and the dropped module, not an unconditional yes

**Must not**
- Answer "safe to delete" from the graph callers alone
- Omit the caps from the report

**Why this case** - the skill says a capped run "reads as complete coverage
unless you say what was dropped" and that blind spots "are usually where a
migration actually breaks. Lead with them."

---

## Case 3 - The trap: promoting a refuted finding

**Input**
> graph-review finished on my branch. It returned 3 `confirmed`, 2 `refuted` and
> 4 `unverified` findings. Give me the bug list I should fix before merging.

**Must contain**
- [ ] Lists the 3 confirmed findings as the bugs to fix
- [ ] Labels the 4 unverified findings as unverified (hit the cap), separate from the bug list
- [ ] Leaves the 2 refuted findings out of the bug list
- [ ] Does not re-run a harness or re-verify the confirmed findings by hand

**Must not**
- Present all 9 findings as bugs
- Promote an unverified finding to confirmed without new evidence

**Why this case** - the skill splits `confirmed`, `refuted` and `unverified` and
says "Never promote a refuted or unverified finding" and "Do not re-verify its
findings by hand".

---

## What these do not prove

These are trap cases for a human or judge rater, not a behavioural measurement.
`skills/research` owns the standard a claim about behaviour has to meet.
