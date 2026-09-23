# The UX, competitive and triage standards, read 2026-09-20

Five sources, each read in this session at the level stated. They are what the
five-axis extension of the `product-analysis` rule and skill rests on.

## 1. Nielsen / NN/g - heuristic evaluation

- **Source:** Kate Moran, Kelley Gordon, "How to Conduct a Heuristic Evaluation",
  Nielsen Norman Group, 2023-06-25 (`https://www.nngroup.com/articles/how-to-conduct-a-heuristic-evaluation/`),
  read in full.
- Verbatim: "**three to five people should independently evaluate** the same
  interface"; each individual "is likely to miss some of the potential usability
  issues"; "the narrower the scope, the easier and more detailed the evaluation
  will be" (one task, one section, one user group, one device); "reserving about
  1-2 hours"; two passes - one "just to learn the system", then one to find
  violations; consolidate by affinity diagramming.
- The caveat that matters most: "**just because a design choice violates a
  heuristic, that does not necessarily mean it's a problem** ... it depends on the
  particular context and the available alternatives", illustrated with a hamburger
  menu that violates heuristic 6 but is often the right mobile tradeoff.
- And the boundary: heuristic evaluations "**cannot replace user research**".

## 2. Nielsen / NN/g - severity ratings

- **Source:** Jakob Nielsen, "Severity Ratings for Usability Problems",
  1994-11-01 (`https://www.nngroup.com/articles/how-to-rate-the-severity-of-usability-problems/`),
  read in full.
- Severity is "a combination of three factors": **frequency** (common or rare),
  **impact** (easy or difficult to overcome), **persistence** (one-time or
  repeated), plus a market-impact judgement.
- The scale, verbatim: **0** "I don't agree that this is a usability problem at
  all"; **1** "Cosmetic problem only"; **2** "Minor usability problem"; **3**
  "Major usability problem"; **4** "Usability catastrophe: imperative to fix this
  before product can be released".
- "severity ratings from a single evaluator are **too unreliable to be trusted**";
  "the mean of a set of ratings from three evaluators is satisfactory for many
  practical purposes".

## 3. W3C - WCAG 2.2 and its mobile note

- **Sources:** WCAG 2.2 (`https://www.w3.org/TR/WCAG22/`), whose success criteria
  are "written as testable statements that are not technology-specific"; and
  *Guidance on Applying WCAG 2.2 to Mobile Applications* (WCAG2Mobile), W3C Draft
  Note, 2025-05-06 (`https://www.w3.org/TR/wcag2mobile-22/`), editors Jon Gibbins,
  Jamie Herrera, Joe Humbert, Jan Jaap de Groot, Julian Kittelson-Aldred.
- WCAG2Mobile "describes how Web Content Accessibility Guidelines (WCAG) 2.2
  principles, guidelines, and success criteria can be applied to mobile
  applications, including native mobile apps, mobile web apps and hybrid apps",
  and is explicitly **informative**: "guidance that is not normative and does not
  set requirements". Read: abstract and metadata only.
- Level AA is a conformance claim, not a feeling: it is asserted per level.

## 4. Umbrex - product teardown analysis

- **Source:** Umbrex, *Product Teardown Analysis* (Competitive Intelligence
  Frameworks), modified 2026-09-18, read in full.
- Five core layers: architecture; components and materials; manufacturing and
  assembly; cost and performance; strategic meaning.
- "Define the units of analysis ... **inconsistent units are one of the fastest
  ways to weaken the analysis**"; state the comparison basis (cost per unit,
  weight, performance, assembly time, serviceability, feature density).
- Pitfalls named by the source itself: studying "the wrong product version"
  (outdated, premium-only, region-specific) and generalising; "selfestimating
  costs as facts" - "treat cost numbers as ranges, not certainties"; "false
  precision"; ignoring customer value; "stopping at observation" instead of
  decisions with owners.
- Its own scope limit, which is why this axis is paired with review mining: the
  framework is weak "when the primary source of advantage lies outside the
  physical product - brand, ecosystem, software, data network effects, service
  model, installed base, or regulatory positioning". A software product is mostly
  that case, so the software adaptation compares *observable product artifacts*
  (store listing, docs, pricing page, changelog, the app itself) and the market's
  own words.

## 5. Appbot - competitor review mining

- **Source:** Claire McGregor, "How to Analyze Competitor App Reviews (And Turn
  Them Into Growth)", Appbot, published 2026-03-17, read in full.
- Six steps, verbatim order: "Identify key competitors; Collect app store reviews;
  Categorize feedback into themes; Analyze sentiment within each category; Compare
  results against your app; Identify gaps and opportunities."
- What to track: "sentiment by category (bugs, UX, features, pricing)", "volume of
  mentions", "trends over time".
- Why it is worth the axis: users "highlight what's broken, what's missing, and
  what they expect" - the market states its needs in public, and a competitor's
  review section is the cheapest user research that exists.

## 6. Mind the Product - kill criteria

- **Source:** Reuben John, "The case for kill criteria in product management",
  Mind the Product, published 2026-09-10, modified 2026-09-08, read in full.
- "Every feature has a launch plan, but almost none have a kill plan." A useful
  kill criterion has four components: **what you are measuring; at what level the
  metric signals failure; how long you give it; what happens when the threshold is
  breached** - e.g. "If checkout completion rate drops below 68% within 14 days of
  launch, we roll back to the previous flow and run a post-mortem".
- The five ways features fail: **adoption, perception, performance, monetization,
  trust**.
- "If you can't draw that line from **threshold to flag to owner**, the feature
  isn't ready to ship, no matter how good the demo looked."
- The audit it proposes, which is the triage axis in one question: "Look at the
  last ten features your team shipped. How many are still live? How many have been
  evaluated against their original success metrics? How many would you ship again,
  knowing what you know now?"

## What these do NOT support

- None of them measures this repository's change. They are the standards the rule
  cites, not evidence that citing them improves an analysis.
- The NN/g method assumes a panel of human evaluators; an agent is one rater. The
  skill therefore requires the rater count to be reported rather than implying a
  panel, and this note records that as a known limitation rather than a solved
  problem.
- Umbrex is a physical-products framework; its software adaptation (observable
  artifacts, review mining, effort ranges) is this repository's, not the source's.
