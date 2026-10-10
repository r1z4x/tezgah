# Evals

Three inputs a session can be handed where this skill could misfire, and what a
good answer has to contain. Each case is built so a plausible but shallow answer
fails at least one check.

Run a case by giving the session only the **Input**, with the skill reachable
from the router. A case passes when every Must-contain line is met and no
Must-not line is triggered.

---

## Case 1 - The trap: drawing the dashboard before the flow says so

**Input**
> Bu veriye uygun bir metric dashboard tasarla. (attached: `sales.csv` - date,
> region, product, orders, revenue, returns)

**Must contain**
- [ ] Picks one kebab-case topic and runs `tezgah-research next --topic <t>` before any layout, and does the first missing step it names
- [ ] Writes each step's note under its `## <step>` heading in `.tezgah/analysis/<t>/flow.md`, each naming the note it rests on
- [ ] Takes the metrics from `## metrics` notes that rest on a need under `## research` (goal, signal, definition, window, baseline, logged), written before the design step
- [ ] Gives the decision under `## decision` a metric, a threshold and an `observe after: YYYY-MM-DD` date
- [ ] Names that decision in `.tezgah/analysis/<t>/spec.md` and in the design-contract component

**Must not**
- Lay out charts for the CSV's columns before a metric and a decision exist
- Skip a step whose artifact is missing because the data seems to answer it

**Why this case** - the skill says to "find the first step whose artifact is
missing" and do "that step, and only that step". A data file pulls toward drawing
its columns at once.

---

## Case 2 - The trap: a research worker writing the flow's artifacts

**Input**
> We want to add saved searches to the app. Spin up research on how users
> re-run searches and take it from there.

**Must contain**
- [ ] Runs `tezgah-research next --topic <t> --flow feature` (no metric is in view) and starts from the first missing step
- [ ] Briefs any research worker to report its sources and insights - class, source with its read date, quote, statement, confidence - in its result
- [ ] Writes those findings under `## research` in `flow.md` from the main session

**Must not**
- Let a worker or subagent write `flow.md` or `spec.md` itself
- Start the forward spec before `## decision` exists

**Why this case** - "Who writes" says "Only the main session writes the flow's
artifacts". A delegated research step pulls toward letting the worker write its
own findings.

---

## Case 3 - The trap: "just build the chart"

**Input**
> Skip the process, just build the chart of weekly revenue. No need for metrics
> or goals.

**Must contain**
- [ ] Runs `next` for the topic and states which steps are missing before the build, naming the metric and the decision
- [ ] Says the chart has no goal above it, and asks for the goal or writes the gap down as a step still missing
- [ ] Offers the shortest route through the missing steps, one note each, rather than refusing

**Must not**
- Build the chart and report the flow as done
- Claim the metric or decision steps do not apply to this ask

**Why this case** - every step's artifact "names the earlier artifact it rests
on": a built chart with no metric and no decision leaves the earlier steps missing
however good the chart is.

---

## What these do not prove

These are trap cases for a human or judge rater, not a behavioural measurement.
`skills/research` owns the standard a claim about behaviour has to meet.
