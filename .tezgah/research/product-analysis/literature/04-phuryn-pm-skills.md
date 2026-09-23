# The prior art: a shipped product-management skill marketplace

- **Source:** `phuryn/pm-skills` — "PM Skills Marketplace", read through the GitHub API
  (repository listing + `README.md`) on 2026-09-19. Licence: **MIT** (LICENSE in the
  repository root; the README ends "MIT - see LICENSE").
- **Scale at read time:** 26,443 stars, 2,818 forks. The README states "69 PM skills
  and 42 chained workflows across 9 plugins" and lists the plugins
  (`pm-product-discovery`, `pm-product-strategy`, `pm-market-research`,
  `pm-data-analytics`, `pm-go-to-market`, `pm-marketing-growth`, `pm-execution`,
  `pm-toolkit`, `pm-ai-shipping`).

## What it contains, read directly

- `pm-product-discovery/skills/opportunity-solution-tree/SKILL.md` — the Opportunity
  Solution Tree (attributed to Teresa Torres, *Continuous Discovery Habits*): four
  levels outcome -> opportunities -> solutions -> experiments, with the Opportunity
  Score given as **Importance x (1 - Satisfaction)** and attributed to Dan Olsen,
  *The Lean Product Playbook*; rules "One outcome at a time", "Opportunities, not
  features", "Always generate at least 3 solutions per opportunity", and "Discovery
  is not linear".
- `pm-product-discovery/skills/metrics-dashboard/SKILL.md` — metric layers (North Star,
  input, health, business), and a metric table whose columns are Metric, Definition
  (exact calculation: numerator/denominator, time window), Data Source, Visualization,
  Target, Alert Threshold. It attributes the "4 criteria for a good metric"
  (understandable, comparative, ratio or rate, behavior-changing) to Ben Yoskovitz,
  *Lean Analytics*, and points at HEART and AARRR as companion frameworks.
- `pm-ai-shipping/skills/intended-vs-implemented/SKILL.md` — read in full. The method:
  intent is what the docs claim, implementation evidence is "a cited file and line -
  the actual authorization check, the actual query filter, the actual sanitizer";
  "'It's probably handled upstream' is not evidence; the code path is". A finding must
  name documented intent (quote the doc), implemented reality (cite the code),
  attacker and victim, and the concrete fix: "If you cannot cite both sides of the
  gap, it is a question to investigate, not a finding to report." Documented-but-
  unenforced is itself a finding; "Never fabricate intent to manufacture a gap."
- `pm-data-analytics/skills/{cohort-analysis,ab-test-analysis,sql-queries}` — the
  measurement half (retention curves, significance, sample-size validation).
- `pm-ai-shipping` also ships `shipping-artifacts` (the durable documentation set) and
  commands for security and performance audits and a test-coverage map.

## What this settles for the structure

1. The two axes already have prior art, and it is MIT-licensed: PM discovery and
   metrics on one side (`pm-product-discovery`, `pm-data-analytics`), feasibility and
   code review on the other (`pm-ai-shipping`).
2. The single most transferable rule is `intended-vs-implemented`'s evidence
   requirement: a gap is a finding only when both sides are cited. That is the
   PE-axis analogue of HEART's rule that a metric must trace to a goal, and it is the
   rule this repository's product analysis should adopt.
3. The marketplace is *marketplace-shaped*: 9 plugins, `$ARGUMENTS`-driven skills,
   `/slash` commands, and a plugin/marketplace manifest. Adopting it wholesale means
   adopting that packaging surface, not just the frameworks.

## What this source does NOT support

- Star count and licensing were read from the GitHub API; the *quality* of the 69
  skills was not measured. Three skill files were read, not 69.
- The frameworks are attributed inside that repository to Torres, Olsen, Savoia,
  Cagan, Yoskovitz and others. This note verifies what the marketplace *says*; it does
  not verify the marketplace against those books.
