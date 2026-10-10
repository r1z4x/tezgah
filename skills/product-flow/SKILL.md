---
name: product-flow
description: >
  Carries a new product capability from evidence to a measured result: it walks
  the nine steps of the flow in order - research, metrics, assumptions,
  decision, instrumentation, forward spec, design, build, re-measure - and does
  the first step whose artifact is missing with the skill that step names, so
  each hand-off is a written artifact that names the one before it instead of a
  memory. Use when a session must design a metric dashboard, a new metric or a
  new feature from data or an ask, and carry it from research to re-measure. Not
  for auditing an existing feature - use `feature-audit`.
---

# product-flow

A new product capability - a dashboard over a data file, a metric, a feature
someone asked for - drifts when its steps live in the session's head: the chart
gets drawn before anyone says which goal it serves, and nobody comes back to see
whether the decision held. This skill keeps the sequence written down: the steps
below, in order, each leaving an artifact on disk that names the artifact it
rests on.

## When to use it

- A new capability from data: "bu veriye uygun metric dashboard tasarla", a CSV or
  export with "what should we track".
- A new capability from an ask: "add a feature that ...", "we need a metric for ...".
- A topic already in progress, to see what is left of it.

Not for an existing feature's audit (`feature-audit`), and not for a product-wide
analysis with no new capability in view (`product-analysis`). Both are steps this
flow can hand off to.

## The steps

Pick one kebab-case topic for the capability, such as `signup-dashboard`. Every
artifact of this capability lives under `.tezgah/analysis/<topic>/`: the notes of
steps 1-5 and 9 in `flow.md`, one `## <step>` heading per step, and the forward
spec in `spec.md`. Each step's artifact names the earlier artifact it rests on.

1. **research** (`research` skill). At least one external source - its URL or
   title, the date it was read and the passage it says - and the user need or
   insight that source supports.
2. **metrics** (`product-analysis`). Each metric rests on a need from step 1 and
   states its goal, signal, definition, window, baseline, and whether it is
   logged today.
3. **assumptions** (`product-analysis`). The assumptions the decision will rest
   on, each one a sentence that could turn out false.
4. **decision** (`product-analysis`). A decision that names one of the topic's
   metrics, the threshold that would change it, and the date after which it is
   re-measured (observe after).
5. **instrumentation** (`product-analysis`). Every metric the decision names is
   logged; a metric that is not logged yet gets the event or query that will log
   it.
6. **forward-spec** (`feature-audit`, forward mode). `.tezgah/analysis/<topic>/spec.md`,
   naming the decision it implements.
7. **design** (`design-contract`). A component in `.tezgah/design-contract.md`
   that names the decision it serves.
8. **build** (`design-contract`). Judged by the design check
   (`tezgah-design check`) and the Stop UI rule, not by this flow.
9. **re-measure** (`analyze-app`). Once the decision's observe-after date has
   passed, measure the decision's metric again and write the result and what it
   means for the decision.

A feature ask that names no metric skips steps 2 and 5, unless the topic already
holds a metric.

## The loop

The step source is `~/.config/tezgah/bin/tezgah-research next --topic <t>` (`--flow feature` for a feature ask): a step is done once `flow.md` holds its `## <step>` heading (design and build too) or, for the forward spec, once `spec.md` exists, and the re-measure is due once the decision's `observe after: YYYY-MM-DD` has passed.

1. Read what already exists under `.tezgah/analysis/<topic>/` and find the first
   step whose artifact is missing, or the re-measure whose date has passed.
2. Do that step, and only that step, with the skill it names. Read that skill; it
   says what the step's artifact holds.
3. Write the artifact, naming the artifact it rests on.
4. Go back to 1. Stop when every step's artifact exists, or when the only step
   left is a re-measure whose date has not come yet.

## Who writes

Only the main session writes the flow's artifacts. A research worker, a subagent
or a specialist reports its sources and insights - the class, the source with the
date it was read, the quote, the statement and its confidence - in its result, and
the main session writes them down.

## What this skill does not do

It does not decide what a metric is, how a dashboard looks or what a feature spec
holds: the skill each step names owns that (`product-analysis`, `research`,
`feature-audit`, `design-contract`, `analyze-app`).
