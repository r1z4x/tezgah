# Data views

The rules a dashboard, a chart or a metric tile is held to, on top of the state set
in `SKILL.md`. The metrics themselves - which ones, their definition, window,
baseline and whether they are logged - come from `product-analysis`'s Metrics
section; this file decides how they are shown. Each rule names its source, and a
rule with no primary source found says so.

## The dashboard type comes first

Decide whether the screen is **operational** - critical information read quickly
during a time-sensitive task - or **analytical** - at-a-glance information for
analysis and decision making (NN/g). Carbon draws the same line as presentation
against exploration dashboards. The type sets the density, the refresh rate and
how much interaction the screen owes; a dashboard that has not named its type has
not named its user.

## Chart choice follows the question

Name the question each view answers, then pick the encoding:

| The question | Encoding | Source |
|---|---|---|
| comparison - which is bigger? | bars on a common baseline | NN/g (length on a common scale) |
| trend - how did it move over time? | a line over a time axis | NN/g (position) |
| part-to-whole - what share is each? | a stacked bar, or a bar of shares | tezgah's own: no primary source read |
| distribution - how is it spread? | a histogram or a box plot | tezgah's own: no primary source read |
| relationship - does one move with another? | a scatter plot | NN/g (position on two axes) |

Length and position carry quantity, because people compare them accurately; area
and angle (pie, gauge, radar) do not (NN/g, after Cleveland and McGill). Colour
never encodes a magnitude: it is a redundant grouping cue beside a label, a shape
or a position, and every chart passes the greyscale test - it still reads with the
colour removed (NN/g; the design library's `colour-independence` entry).

## Every number has context and a window

A bare number cannot be judged: "Compared to what? Is this good or bad?" (Few,
*Common Pitfalls in Dashboard Design*). Every figure shown carries its comparison
- a target, the previous period or a benchmark - and the window it covers, and is
formatted with its unit and no more precision than the decision needs (Few's
"excessive detail or precision" pitfall). The record behind each comes from the
metric's `baseline` and `window` fields.

## Three to five metrics by default

The default view shows 3-5 key metrics and the primary actions; the rest sit
behind a fuller view the user opens (the design library's `simplified-views`
entry). Carbon's "Limit the number of metrics" and Few's "exceeding the
boundaries of a single screen" say the same. The most important metric gets the
largest area and the highest contrast (Carbon).

## The widget state set

Every widget - tile, chart, table - owes each of these states, and a state that
does not exist is a finding:

| State | What it shows | Source |
|---|---|---|
| loading | that data is on the way, in the widget's own frame | Carbon's loading pattern, seen but not read at source |
| no-data | that the query returned nothing, and what would fill it | Carbon empty states |
| error | that the system failed, per widget, with a text-only message when many fail | Carbon empty states ("Systems issue") |
| permission-denied | that data exists but this user may not see it | Carbon empty states ("Permissions issue") |
| configuration-needed | that the widget cannot run until something is set up | Carbon empty states ("Configuration required") |
| stale | the last good data, with its "as of" time | tezgah's own rule: no primary source found |
| partial | which part of the data is missing, beside what arrived | tezgah's own rule: no primary source found |

Against the contract: loading, error, partial and permission-denied are already in
`states.data`, and no-data is its `empty`; configuration-needed and stale are
reported as observed state names beside the shipped set, and their absence is a
finding the reviewer names, since `check` does not require them.

## Sources

- Stephen Few, *Common Pitfalls in Dashboard Design* (2006),
  http://www.perceptualedge.com/articles/Whitepapers/Common_Pitfalls.pdf
- NN/g, *Dashboards: Making Charts and Graphs Easier to Understand* (2017),
  https://www.nngroup.com/articles/dashboards-preattentive/
- Carbon Design System, Dashboards,
  https://www.carbondesignsystem.com/data-visualization/dashboards
- Carbon Design System, Empty states,
  https://www.carbondesignsystem.com/building-blocks/core/patterns/empty-states
- The design library: [colour-independence](../design-library/adaptive-interfaces/skills/colour-independence/SKILL.md)
  ("Always test charts in greyscale") and
  [simplified-views](../design-library/adaptive-interfaces/skills/simplified-views/SKILL.md)
  (its Dashboard Simplification patterns: a default of three to five key metrics).
