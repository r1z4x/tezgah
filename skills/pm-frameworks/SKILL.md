---
name: pm-frameworks
description: >
  Two product-management methods vendored offline behind the `product-analysis`
  skill: the intended-vs-implemented gap audit (a gap is a finding only when the
  documented intent and the code that enforces it are both cited) and the
  Opportunity Solution Tree (one outcome, opportunities as needs, solutions
  compared, the cheapest experiment per assumption). Use when a product question
  needs the method, not just the framework name: intended-vs-implemented audits,
  opportunity solution trees, discovery mapping and assumption tests. Read the
  one entry the task needs, never both by default.
---

# pm-frameworks

Two methods, kept byte-for-byte from `https://github.com/phuryn/pm-skills` (MIT)
at the revision recorded in `SOURCE`. They are here so an offline session can
read the method rather than cite its name.

| Read | When |
|---|---|
| `intended-vs-implemented/SKILL.md` | auditing what a system says it does against what the code does - permissions, trust boundaries, an "internal only" comment that nothing enforces. The PE axis of `product-analysis`. |
| `opportunity-solution-tree/SKILL.md` | structuring discovery: one outcome, opportunities as customer needs, three or more solutions compared before a choice, the cheapest experiment per risky assumption. The PM axis of `product-analysis`. |

`product-analysis` is the tezgah skill that consumes both; this one is the text.
Neither file is a rule: the contract's evidence classes, the `research`
workspace's claim record and its falsification criterion still govern what may be
reported as a finding.

The rest of the marketplace (9 plugins, 69 skills) is deliberately not vendored.
Fetch the one skill a task needs from the upstream repository named in `SOURCE`:
its raw URL is `https://raw.githubusercontent.com/phuryn/pm-skills/main/` plus the
upstream path recorded for that skill in the table there.
