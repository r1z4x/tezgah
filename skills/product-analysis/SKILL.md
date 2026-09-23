---
name: product-analysis
description: >
  Runs a product analysis across five axes - value (HEART's Goals to Signals to
  Metrics, opportunities before features), usability (Nielsen's heuristics with
  their severity scale, the cognitive walkthrough, WCAG 2.2 AA, axe-core, and the
  running app read through analyze-app down to component x state, tree and rendered
  image both),
  feasibility (a cited code path, documented intent against the code that enforces
  it), competition (a teardown with a stated comparison basis, review mining), and
  triage (keep, fix, cut or bet, with kill criteria) - where every finding names
  one evidence class. Use when a task is to analyse or improve a product: product
  analysis, UX audit, competitor teardown, which feature next, retention, churn,
  funnel, pricing, a PRD or a roadmap and backlog review, or a
  "should this feature exist" ask. Code discovery belongs to the code graph and ML
  experiments to the research skill; this one owns the product question.
---

# product-analysis

A product question is answered from priors unless something forces it to be
concrete. This skill is that forcing function: five axes, one evidence class per
finding, and an artifact that outlives the session. It does not add machinery -
execution runs through the shipped research workspace, and the scorecard reuses the
`research` skill's 1-5 anchors so two analyses stay comparable.

Read `research` too when the deliverable is the evidence itself; this skill owns
what a *product* analysis must contain, `research` owns how a claim is recorded.

## The gate: can we see it at all

Before any axis, establish whether the product's behaviour is observable. If the
telemetry layer is inert, or there is no analytics, or the app has never been run,
that is the first finding - "we cannot see this yet" - not a footnote. An analysis
of a product nobody can observe is a hypothesis, and it says so.

## The five axes

| Axis | The question | Standard | The hard rule |
|---|---|---|---|
| Value (PM) | is it worth building? | HEART and its Goals -> Signals -> Metrics process (Rodden, Hutchinson, Fu, CHI 2010); Opportunity Solution Tree with the opportunity score (Torres; Olsen) | a metric with no goal above it is dropped; raw counts are refused; an opportunity is a need; three solutions compared against a pre-stated criterion |
| Usability (UX) | can a person actually use it? | Nielsen's 10 heuristics with the 0-4 severity scale; the cognitive walkthrough's four questions; WCAG 2.2 AA, and the W3C WCAG2Mobile note for native apps; Apple HIG or Material 3 for platform feel | a UI claim is read from the running app through `analyze-app` - down to component x state, never inferred from source - and the rendered screen is read, not only the tree; severity is frequency x impact x persistence; each finding says whether it is a provable failure (a WCAG criterion) or a judgement, and how many passes produced it |
| Feasibility (PE) | does it do what it says? | intended vs implemented | a claim is a cited `path:line` or graph symbol; a doc-vs-code gap is a finding only when **both** sides are cited; when the ask is one feature, the layer matrices decide it |
| Competition | where does it stand, and where can it lead? | a teardown (architecture, features, process, cost/performance, strategic meaning) with the comparison basis stated **before** comparing; review mining (categorise themes, sentiment per theme, compare to us, name gaps) | every competitor fact carries its artifact and the date it was read; a cost or effort number is a range with its assumptions |
| Triage | what stays, what goes? | kill criteria: the metric, the failure level, the timeframe, and the pre-decided action, wired to a flag with a named owner | every feature gets keep, fix, cut or bet; "everything is important" is not a verdict; a cut nobody owns will not happen |

Calibrate to stage before prescribing: telling a pre-launch prototype to fix its
dependency graph, or a scaling product to "find product-market fit", is malpractice.

## When the ask is one feature: run the coherence pass first

A product question about one feature - an admin screen, a CRUD surface, a form, a
wizard, a data table, a filter, a permission - is where a screen-level review
reports taste and misses the defect. Run `feature-audit` before the axes below: its
capability (action x layer), field-contract, flow/step and interaction-dependency
matrices are the evidence the feasibility axis needs, and its surface patterns fill
the state matrix the usability axis demands. Its capability-change proposals are
what the recommendations section reports when a fix needs a layer that does not
exist yet - an analysis that stops at UI copy for a missing capability has not
answered the question.

Measured on one real admin users feature: three independent raters running the
axes alone reached 4 of 10 cross-layer defect classes, while the matrices named the
rest.

## Evidence classes

Every finding names exactly one. A finding whose class is `none` is a question to
investigate, not a finding to report.

| Class | Counts | Does not count |
|---|---|---|
| `user-verbatim` | a quote from an interview, ticket, review or message, with its source | "users want", "users struggle" |
| `behaviour` | a ratio with its definition (numerator / denominator / window), source and date | a raw count; a number with no denominator |
| `ui-observed` | a screen state read from the running app - screen, component, state, and how it was read (`analyze-app` view tree, a measurement in the page, or a screenshot that was actually looked at) | a UI claim inferred from source; "it looks cluttered" with no screen named; a screenshot saved but never read |
| `code` | a `path:line` in this repository, or a graph symbol with its callers | "probably handled upstream"; a comment claiming "internal only" |
| `external` | a URL or paper read in this session; for a competitor artifact, its URL **and** the date read | "best practice"; a framework named without its artifact; a citation from memory |

## The UX axis's discipline

These come from the method, not from taste:

- **Three to five independent evaluations, never one.** Each evaluator "is likely
  to miss some of the potential usability issues", and independence is the point -
  evaluators do not compare notes until each has finished. A single rater is
  explicitly "too unreliable to be trusted" for severity; the mean of three is
  satisfactory. An agent is one rater: run the pass more than once, from a different
  entry point or persona, and report the rater count in the artifact instead of
  implying a panel.
- **Narrow the scope**: one task, one section, one user group, one device.
- **Two passes**: one to learn the product, one to find violations.
- **A violated heuristic is not automatically a problem.** The source is explicit:
  "just because a design choice violates a heuristic, that does not necessarily mean
  it's a problem". Name the context and the alternative before prescribing.
- Accessibility is a level, not a vibe: state the WCAG 2.2 level claimed, and for a
  native or hybrid app read the WCAG2Mobile note rather than assuming the web rules
  transfer.
- **Say what was actually seen.** `analyze-app` reads a running app through its
  accessibility / DOM / native view tree (`browser_snapshot`,
  `mobile_list_elements_on_screen`), re-reads it after each change, and can pull
  console, network, device logs and crashes; it captures and reads the rendered
  screen, and measures in the page. So a finding states which of those it came
  from. The tree answers element names, roles, labels, states and flow structure well - most
  of Nielsen's heuristics, and the WCAG criteria that are machine-checkable. It does
  not answer contrast, visual hierarchy, rhythm or platform feel: those are read
  from a screenshot or computed in the page, and when neither is done the finding
  is not made.
- **Mark the class of judgement.** A heuristic finding is not a proof. Say whether
  it is a `failure` (a WCAG criterion or a broken flow, reproducible) or a
  `judgement` (a violated heuristic in context, which the source itself says is not
  automatically a problem), and report the confidence anchor for a judgement - a
  single pass is never `certain`.

## The depth ladder

An interface finding names the level it was made at, or it is not a finding.
"Screen-level" is where the first version of this skill stopped, and it is why the
output read as thin.

| Level | The unit | What gets checked |
|---|---|---|
| Screen | a route or view | does it exist in every state the data can be in |
| Component | a control or a block | the full state set below, one by one |
| State | one state of one component | interactive: default, hover, focus, active, disabled, loading, error; data: empty, loading, skeleton, error, offline, partial, long-text/overflow, permission-denied |
| Property | one measured value | type size / weight / line-height, spacing, contrast ratio, tap-target size, truncation, z-order, focus order |

The state matrix is mandatory for every interactive component and every data view.
A state that does not exist is a finding, and a missing empty, loading or error
state is usually a bigger one than a state that merely looks wrong.

Properties are measured, not eyeballed: `browser_evaluate` reads computed styles,
so a type scale, a spacing rhythm, a contrast ratio and a tap-target size come
back as numbers. WCAG 2.2 SC 2.5.8 sets the target size floor at 24x24 CSS px, and
a contrast ratio is a computation, not a preference.

## Reading the image

A tree cannot see hierarchy, rhythm, colour, density or feel, and a review that
never looks at the rendered screen is the same defect as a code review that never
runs the code. So the screen is an evidence source in its own right.

- Capture with `browser_take_screenshot` / `mobile_save_screenshot`, and say what
  the tree could not answer. The path comes back; image bytes are never inlined.
- One capture per breakpoint in scope (`browser_resize`), plus dark mode and the
  largest text setting, because hierarchy and contrast change with all three.
- Two tests from the visual-craft canon, both cheap and both checkable by eye:
  the **blur test** (blur or squint - does the primary action still read first?)
  and the **grayscale test** (does the hierarchy survive without colour?). A
  failure of either is a hierarchy finding, not a taste note.
- A finding read from pixels states what was seen - the screen, the region, what
  competes with what - and is a `judgement`. Run that pass twice and report
  whether both agree. Nothing read from an image is reported as a measurement.

## The second inspection method: cognitive walkthrough

Heuristics judge a screen; a walkthrough judges a task. For each step of a real
task, from a new user's position, four questions (Wharton et al.; NN/g):

1. Will the user try to achieve the right effect here?
2. Will the user notice the correct action is available?
3. Will the user associate the correct action with the effect they are trying to
   achieve?
4. If the correct action is performed, will the user see progress is being made?

A "no" is a finding with the step it belongs to. It is the cheapest way to catch
the defect heuristics miss: a control that exists, is labelled correctly, and is
still not found.

## The UX evidence map

A UX claim is only a finding when a named tool call produced it. `analyze-app`
wires the servers; this is which call evidences which claim, and what kind of
result it is. A `failure` is reproducible (an assertion, a log, a measurement); a
`judgement` is a heuristic read in context and must carry its confidence anchor.

| Claim | The call that evidences it | Kind |
|---|---|---|
| flow structure, names, roles, states | `browser_snapshot`, `browser_find`; `mobile_list_elements_on_screen` | judgement (failure when a step is impossible) |
| "this text/control is not there" | `browser_verify_text_visible`, `browser_verify_element_visible`, `browser_verify_value` | failure - re-runnable |
| the surface behind a login | `browser_storage_state` + `browser_set_storage_state`, never an attach to the real profile | - |
| the offline and failing-backend states | `browser_network_state_set`, `browser_route` | failure |
| errors a step produced | `browser_console_messages`, `browser_network_requests`; `mobile_get_device_logs`, `mobile_list_crashes` | failure |
| contrast, target size, focus order, text spacing | `browser_evaluate`, run as a measurement in the page | failure (measured) |
| layout at a named width | `browser_resize` then re-read the tree | failure |
| visual hierarchy, platform feel, "cluttered" | `browser_take_screenshot`, naming why the tree cannot answer; read the image, do not just save it | judgement |
| a WCAG violation, sweep | axe-core injected with `browser_evaluate` (pin the version; never a floating tag) | failure, with its own scope limit |
| a type scale, spacing rhythm, contrast ratio, z-order | `browser_evaluate` reading computed styles | failure (measured) |
| loading / responsiveness | `PerformanceObserver` for LCP, INP and CLS against their published thresholds: good is <=2500 ms, <=200 ms, <=0.1; poor is >4000 ms, >500 ms, >0.25 (web.dev) | failure |
| learnability of a task | the cognitive walkthrough's four questions per step | judgement |
| perceived usability | SUS (>68 is above average) or the two-item UMUX-Lite - an instrument for real users, so the agent records it as **to be run**, never as a number it produced | the user's, not the agent's |

Three rules fall out of the table. First, state the viewport: a layout finding that
holds at one width and not another is not a finding until both are checked. Second,
on mobile there is no assertion, mocking or geometry tool - so a mobile UX claim is
a judgement unless re-walking the flow reproduces it, and contrast, tap-target size
and focus order are not claimed at all without a screenshot. Third, know what an
automated tool cannot see: axe-core's own documentation puts it at about **57% of
WCAG issues** found automatically, and an independent list names the checks it
misses - focus appearance, target size, dragging, accessible authentication. Those
are hand-checked, not assumed.

## What else to bring in

Cheap, standard, and each one answers a question the axes above cannot. Add the
ones the product's stage justifies, and say which were skipped.

| Analyser | Answers | Cost |
|---|---|---|
| axe-core via `browser_evaluate` | WCAG A/AA/AAA sweeps, plus best practices | one pinned injection per page |
| `PerformanceObserver` + the chrome-devtools sidecar | LCP / INP / CLS against their thresholds, and the trace behind a slow one | the sidecar is opt-in |
| Device and density sweep | the same screen at 320/768/1280, dark mode, 200% text | one capture each |
| Copy audit | empty/error/confirmation wording, Turkish grammar and terminology consistency, i18n length overflow | reading the strings the app actually renders |
| Visual diff between two builds | what the last release changed visually | two captures of the same screen |
| SUS / UMUX-Lite | perceived usability with a benchmark to compare to | needs real users |
| Review mining of competitors | the market's words, and where they are unhappy | already in the competitive axis |
| Support tickets and analytics | behaviour the app cannot be asked about | needs access the agent does not have |

## The competitive axis's discipline

- State the comparison basis first (cost, latency, task time, feature density).
  Inconsistent units weaken the analysis faster than anything else.
- Compare a *representative* version and say which one; a premium or region-specific
  build generalises badly.
- Cost and effort are ranges with stated assumptions; the method's own first
  limitation is false precision.
- Review mining gives the market's own words: group into themes, read sentiment per
  theme, and compare against our own app before calling something a gap.
- A teardown ends in a decision, not a report: what we adopt, what we deliberately
  do not, and who owns it.

## The artifact

Run it as a research line, not a monologue: `tezgah-research init <slug>
--question "..."` under the repository's `.tezgah/research/`, then `check` before
reporting. On top of what `check` already enforces, the analysis contains:

1. Measurement readiness: what is observable today, and what is not.
2. The objective: one measurable outcome and its Goal -> Signal -> Metric chain.
3. Opportunities with their evidence class; the candidate solutions and the
   criterion they were compared against.
4. Risks by class - value, usability, viability, feasibility - each with the
   cheapest test that would falsify it.
5. The usability section: scope (task, section, device, breakpoints), the heuristics
   checked, the state matrix as a table with a row per interactive component and a
   row per data view, each row naming the states checked and each state that does
   not exist,
   findings at their level (screen / component / state / property) with the screen
   they were read from, severity 0-4, and whether each is a `failure` or a
   `judgement` with its rater count; the screenshots read, and what the blur and
   grayscale tests showed; the axe-core sweep and its uncovered checks; the WCAG 2.2
   level claimed or missing; the walkthrough's per-step answers.
6. The feasibility section: for each intended behaviour, the code that implements
   it, cited. For a single-feature analysis this section carries the coherence
   pass's filled matrices - capability, field contract, flow/step, interaction
   dependency - each row with its citation and its coverage marker.
7. The competitive section: comparison basis, the set compared, per-competitor cited
   facts with dates, review themes with volume.
8. The triage table: keep / fix / cut / bet per feature, with the deciding metric,
   threshold, timeframe, action, flag and owner.
9. Findings, most severe first, each with its class and citation.
10. For each recommendation, the reference: who already does it best, cited, and
    what we would adopt.
11. What the analysis did **not** look at, and what would change the recommendation.

A section with no evidence says so in one line; it does not disappear, because a
missing axis reads as a covered one. Every element this list names is produced or
named in the artifact with the reason it was not - an element inside a section, not
only a section: a state matrix left out silently, an image test never run, an
axe-core sweep dropped or a scorecard dimension missing all read the same way.

## The scorecard

Score each dimension 1-5 and report the mean with its anchors; the anchors are the
`research` skill's (5 nothing material missing, 4 one minor gap, 3 a gap a reviewer
would raise, 2 a gap that undermines a claim, 1 not addressed). Mean >=4.5 with no
dimension below 3 reads as accept; >=3.8 weak accept; >=3.0 revise; below that, or
any dimension at 1, reject.

| Dimension | The question |
|---|---|
| Evidence relevance | does the cited source actually support what the finding says? |
| Class discipline | is every finding's class named and honoured, including `ui-observed` from the running app? |
| Depth | does every screen reach component x state, and is anything measured rather than eyeballed? |
| Image evidence | were the rendered screens actually read - the blur and grayscale tests, the breakpoints, dark mode - or only the tree? |
| Axis coverage | are all five axes addressed or explicitly excluded? |
| Metric integrity | does the metric trace to a goal, and is it a ratio with a definition? |
| Solution plurality | were at least three solutions compared against a pre-stated criterion? |
| Feasibility grounding | is the implementation claim a cited code path, not an inference? |
| Decision quality | does every feature end keep / fix / cut / bet, with a criterion and an owner? |
| Scope calibration | does the analysis say what it did not look at, and what would flip it? |

## The failure modes this exists to stop

- A framework named without its artifact ("use JTBD here" with no interview, no
  quote, no score).
- A UI opinion with no screen, no state and no severity - the axis the first run of
  this skill missed entirely.
- A competitor "comparison" with no basis, no version and no date.
- A feature list where nothing is ever cut.
- A metric with no definition, no window and no denominator.
- Advice that cannot be falsified: "improve onboarding" instead of the step, the
  measured drop-off and the number that would move.
- A recommendation whose flip condition is never stated: a preference wearing a
  decision's clothes.

## Where the depth lives

Read the one that matches the axis; never cite these from memory.

- `pm-frameworks` (vendored in this repository) - `opportunity-solution-tree` for
  the value axis, `intended-vs-implemented` for the feasibility axis; `SOURCE`
  records the upstream revision.
- `feature-audit` (this repository) - the layer-coherence pass: the capability,
  field-contract, flow/step and interaction-dependency matrices, the per-surface
  rules with their WAI-ARIA APG and WCAG 2.2 sources, and the capability-change
  proposal headings. Read it whenever one feature is in scope.
- `phuryn/pm-skills` (MIT) - `pm-data-analytics` (cohort, A/B), `pm-ai-shipping`
  (security and performance audits, test-coverage map), the rest of discovery.
- HEART, `https://research.google.com/pubs/archive/36299.pdf` (CHI 2010).
- Nielsen's 10 heuristics and the severity scale,
  `https://www.nngroup.com/articles/ten-usability-heuristics/` and
  `https://www.nngroup.com/articles/how-to-rate-the-severity-of-usability-problems/`.
- The cognitive walkthrough's four questions: Wharton, Rieman, Lewis & Polson,
  *The Cognitive Walkthrough Method: A Practitioner's Guide* (1994), and
  `https://www.nngroup.com/articles/cognitive-walkthroughs`.
- Component state coverage: the Carbon Design System component checklist
  (`https://carbondesignsystem.com/getting-started/contributing/component-checklist`).
- Automated WCAG coverage: axe-core's own figure of about 57% of issues
  (`https://github.com/dequelabs/axe-core`), and the checks it misses as an
  independent list (`https://github.com/Ax1zz/sightline`).
- Core Web Vitals thresholds: `https://web.dev/articles/inp` and
  `https://web.dev/articles/vitals`.
- The perceived-usability instruments: SUS, where "a SUS score above a 68 would be
  considered above average" (`https://measuringu.com/sus`), and UMUX-Lite, its
  two-item correlate (`https://measuringu.com/umux-lite`).
- WCAG 2.2 (`https://www.w3.org/TR/WCAG22/`) and WCAG2Mobile
  (`https://www.w3.org/TR/wcag2mobile-22/`).
- The 2025 DORA report, `https://dora.dev/research/2025/dora-report/` - AI as an
  amplifier, and the verification tax ungrounded output creates.

The repository's own machinery: `research` for the loop and the claim record;
`analyze-app` for the running-app evidence the usability axis requires; `harness`
and the code graph for the feasibility axis's callers and blast radius.

Off: `research-off`, which disarms the product rule and the research route together.
