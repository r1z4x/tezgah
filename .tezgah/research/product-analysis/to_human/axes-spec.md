# Closing the gap: every point of the product, not only the code

Follow-up to `report.md`. The Ustam run produced a *code* analysis: all findings
one class, no UI/UX axis, no competitive axis, no keep/cut verdict, and no
"what does the best version look like". This is the spec for closing that.

## What the first run could not do, and the standard that fixes it

| Gap | Named standard, read this session |
|---|---|
| No UI/UX axis at all | Nielsen's 10 usability heuristics + the 0-4 severity scale (frequency x impact x persistence), NN/g "How to Conduct a Heuristic Evaluation" (2023-06-25) and "Severity Ratings" (1994-11-01) |
| No accessibility axis | WCAG 2.2 AA, whose success criteria are "written as testable statements"; the W3C note *Guidance on Applying WCAG 2.2 to Mobile Applications* (WCAG2Mobile, W3C Draft Note 2025-05-06) for native/hybrid |
| No platform-feel reference | Apple Human Interface Guidelines; Material 3 |
| No competitive axis | Umbrex *Product Teardown Analysis* (updated 2026-09-18): five layers - architecture, components/materials, manufacturing/assembly, cost/performance, strategic meaning - plus "define the units of analysis ... inconsistent units are one of the fastest ways to weaken the analysis" |
| No market voice | Appbot, *How to Analyze Competitor App Reviews* (2026-03-17): six steps - identify competitors, collect reviews, categorise into themes, sentiment per category, compare against your own app, name gaps |
| No keep/cut verdict | Mind the Product, *The case for kill criteria* (2026-09-10): kill criteria are metric + failure level + timeframe + pre-decided action; features fail as adoption, perception, performance, monetization or trust; and the line from threshold to flag to named owner |
| No "how the best version looks" | the same teardown step 7 - convert observation into a decision - read together with the reference product that already does it |

## The axes (five, not two)

1. **PM / value** - is it worth building. HEART's Goals -> Signals -> Metrics; an
   opportunity is a need; three solutions before a choice.
2. **UX / usability** - can a person use it. Nielsen 10 + 0-4 severity; WCAG 2.2 AA
   (with WCAG2Mobile for native); platform HIG/Material for feel; the running app
   inspected through `analyze-app`, not imagined from source.
3. **PE / feasibility** - does it do what it says. A cited `path:line`; a
   doc-vs-code gap is a finding only when both sides are cited.
4. **Competitive / position** - where it stands and where it can lead. Teardown
   layers against a stated comparison basis; review mining for the market's own
   words; every competitor fact carries its artifact and date.
5. **Triage / keep-cut** - what stays, what goes. For each feature: keep, fix, cut
   or bet, with the metric, threshold, timeframe and action that would decide it,
   and the flag+owner that would execute the cut.

Plus one gate before all of them: **measurement readiness** - if the telemetry is
inert, "we cannot see this yet" is the first finding, not a footnote.

## Evidence classes (five, not four)

Adds one: | class | counts | does not count |
|---|---|---|
| `ui-observed` | a screen state read from the running app - screen, element, state, and how it was read (`analyze-app` view tree or screenshot) | a UI claim inferred from source; "it looks cluttered" with no screen named |

The other four stay: `user-verbatim`, `behaviour` (ratio + definition + window +
source), `code` (`path:line` or graph symbol), `external` (a URL or paper read this
session; for a competitor artifact, its URL **and** the date it was read).

## The UX axis's discipline (from the sources, not invented)

- **Three to five independent evaluations**, never one: "each individual ... is
  likely to miss some of the potential usability issues"; independence is the
  point, so evaluators do not see each other's findings first.
- **Narrow scope**: one task, one section, one user group, one device.
- **Two passes**: one to learn the product, one to find violations.
- **A violated heuristic is not automatically a problem** - the source is explicit
  ("just because a design choice violates a heuristic, that does not necessarily
  mean it's a problem ... it depends"). Context and alternatives decide.
- **Severity is frequency x impact x persistence**, rated 0-4, and a single rater
  is "too unreliable to be trusted"; the mean of three is satisfactory.

## The competitive axis's discipline

- State the comparison basis before comparing (cost, latency, feature density,
  task time) - inconsistent units weaken the analysis fastest.
- Compare against a *representative* version, and say which version it is.
- Cost/effort numbers are ranges with their assumptions, never certainties;
  "false precision" is the framework's own first limitation.
- Pair every teardown observation with customer evidence before calling it a gap.

## Additions to the artifact

6. The UX section: scope (task/section/device), the heuristics checked, findings
   with screen + severity 0-4, and the WCAG 2.2 AA level claimed or missing.
7. The competitive section: the comparison basis, the set compared, per-competitor
   cited facts with dates, and the review themes with their volume.
8. The triage table: keep / fix / cut / bet per feature, with the deciding metric,
   threshold, timeframe and action, and the flag + owner.
9. For each recommendation, the reference: the product or pattern that already
   does it best, cited, and what we would adopt from it.

## Acceptance criteria

- AC1: a product prompt still arms the rule; a non-product prompt still arms nothing.
- AC2: the shipped rule names all five axes and all five evidence classes.
- AC3: the skill carries the UX, competitive and triage sections with their named
  standards and the sources' own caveats.
- AC4: the mirrors (contract skill, output-style) stay in step; suite, ruff,
  compileall and the citation audit stay green.
- AC5: the research line still passes `tezgah-research check`.

## Non-goals

- Not automating the app inspection: `analyze-app` already drives a running web or
  mobile app; this spec wires it in as the source for `ui-observed`.
- Not inventing a competitor database: public artifacts, cited, with their date.
- Not promising that more axes means a longer report: the artifact shape caps each
  section, and a section with no evidence says so in one line.
