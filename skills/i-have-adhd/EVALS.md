# Evals

Three inputs a session can be handed where this skill could misfire, and what a
good answer has to contain. Each case is built so a plausible but shallow answer
fails at least one check.

Run a case by giving the session only the **Input**, with the skill reachable
from the router. A case passes when every Must-contain line is met and no
Must-not line is triggered.

---

## Case 1 - The trap: the five-item cap applied to the analysis

**Input**
> Find every place in this repo that still reads the old `TEZGAH_HOME`
> environment variable. I need the complete list - I am deleting the variable
> tomorrow.

**Must contain**
- [ ] Runs the search across the whole repo and reports every hit with its `path:line`
- [ ] Groups the hits under headers so a long list stays skimmable
- [ ] Opens with the count of hits and the first action, not with context

**Must not**
- Show five hits and hold the rest back
- Report a partial search as the complete list

**Why this case** - Rule 8 caps a list at five, but says it "never trims the
analysis, the search" and that "when completeness is the point the list runs as
long as the topic needs". The user states that completeness is the point.

---

## Case 2 - The trap: a confident cause the evidence does not show

**Input**
> The deploy failed. Here is the last log line:
> `Error: connect ETIMEDOUT 10.0.4.12:5432`. What broke and what do I do?

**Must contain**
- [ ] States the location (the connection to `10.0.4.12:5432`) and what is known from the line
- [ ] Separates what the line shows (a timeout to the database port) from guesses about why
- [ ] Names the one check that would confirm the leading guess, as the next action

**Must not**
- State a single root cause (firewall, wrong password, database down) as fact
- Open with "Uh oh" or "There seems to be a problem"

**Why this case** - Rule 6 says "Name a cause only when the evidence identifies
it" and "a confident wrong cause is worse than a named unknown". A timeout has
several causes, and the log line does not pick one.

---

## Case 3 - The trap: a walkthrough cut to one line

**Input**
> Walk me through how the gate decides whether a shell command is allowed. I am
> new to this code and want to understand it end to end, not just the answer.

**Must contain**
- [ ] Explains the flow in full, in the order the code runs, with headers
- [ ] Opens with the explanation itself, not an announcement of it
- [ ] Ends without a "hope this helps" closer

**Must not**
- Compress the walkthrough into a single first-line answer and a next step
- Drop steps of the flow to stay under five list items

**Why this case** - "When to break these rules" item 1 says "The user asks to
explain or walk through: explain fully ... the body runs as long as the topic
needs". The output-shaping rules would otherwise delete the answer.

---

## What these do not prove

These are trap cases for a human or judge rater, not a behavioural measurement.
`skills/research` owns the standard a claim about behaviour has to meet.
