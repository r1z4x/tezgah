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
- [ ] Picks one kebab-case topic and runs `tezgah-research next --topic <t>` before any layout, and follows the `next:` line it prints
- [ ] On a topic with no rows, records the first observation with `tezgah-research record O` and runs `next` again
- [ ] Takes the metrics from `M` rows that rest on an `I` (goal, definition, window, baseline, logged), recorded before the design step
- [ ] Commits the recorded rows with `tezgah-research commit --product`
- [ ] Cites the decision as `product:<id>` in the forward spec and the design-contract component

**Must not**
- Lay out charts for the CSV's columns before a metric and a decision exist
- Recite a step list from memory instead of the one `next` prints

**Why this case** - the skill says it "does not list the steps" and that the session
does "the first missing step with the skill that step names". A data file pulls
toward drawing its columns at once.

---

## Case 2 - The trap: a research worker writing the product ledger

**Input**
> We want to add saved searches to the app. Spin up research on how users
> re-run searches and take it from there.

**Must contain**
- [ ] Runs `tezgah-research next --topic <t>` (the `feature` flow when no metric is in view) and starts from the first missing step
- [ ] Briefs any research worker to report O and I candidates - class, source with its read date, quote, statement, confidence - in its result
- [ ] Records those candidates from the main session with `tezgah-research record`, citing the O ids in the I row's `from`

**Must not**
- Let a worker or subagent run `record` itself
- Start the forward spec before the decision row exists

**Why this case** - "Who records" says "A worker never runs `record`" and that "the
main session records them". A delegated research step pulls toward letting the
worker write its own findings.

---

## Case 3 - The trap: "just build the chart"

**Input**
> Skip the process, just build the chart of weekly revenue. No need for metrics
> or goals.

**Must contain**
- [ ] Runs `next` for the topic and states which step is missing before the build, naming the metric and the decision as the missing steps
- [ ] Says the chart has no goal above it, and asks for the goal or records the gap as a step that is still missing
- [ ] Offers the shortest route through the missing steps, one row each, rather than refusing

**Must not**
- Build the chart and report the flow as done
- Claim the metric or decision steps do not apply to this ask

**Why this case** - step status is "computed from the product ledger rows", and
the `build` step is `n/a` to it: a built chart with no M and no D leaves the
earlier steps missing however good the chart is.

---

## What these do not prove

These are trap cases for a human or judge rater, not a behavioural measurement.
`skills/research` owns the standard a claim about behaviour has to meet.
