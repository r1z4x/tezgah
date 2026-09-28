---
name: design-library
description: >
  The vendored MC Dean design/UX library - cognitive accessibility, adaptive
  interfaces, visual-critique vocabulary and behavioural analytics - read one
  entry at a time from its own index. Use when a UI or product turn needs a
  cognitive-load, inclusive-interaction or visual-critique method tezgah has no
  counterpart for.
---

# design-library

Thirty-nine `SKILL.md` from two Owl-Listener repositories, vendored into this
repository at pinned revisions (both MIT, `9a6930c` and `6e0740f`) and kept at
the upstream path, so a path here is the path there. `SOURCE` records the
revisions, the per-file sha256 and the two bodies this copy adapted; `NOTICE`
records the licence.

Tezgah owns the design floor: `design-contract` is the artifact shape a
repository's tokens and states are read into, and `bin/tezgah-design` is the
check that fails on them. This library owns the methods that sit on top of that
floor - what to do about cognitive load, motion, target size, focus and
comprehension, and how to critique a rendered screen dimension by dimension.

## Read path - two steps, and only the second costs anything

1. **`INDEX.md`** - one line per entry: `name - what it makes - path`. Read the
   line that matches the work in hand.
2. **the entry's `SKILL.md`** - the file the line names, e.g.
   `inclusive-interaction/skills/touch-target-design/SKILL.md`. That is the
   upstream body.

`EVALS.md` holds the three trap cases this library is scored against.

## What is in it

| plugin | entries | for |
|---|---|---|
| `cognitive-accessibility` | 11 | cognitive load, memory load, focus, plain language, wayfinding, error recovery, help and personalisation |
| `adaptive-interfaces` | 9 | information density, flexible typography, colour independence, user preferences, responsive and simplified views |
| `inclusive-interaction` | 10 | keyboard navigation, focus management, gesture alternatives, motion sensitivity, target size, multi-modal input, voice |
| `visual-critique` | 7 | one critique per dimension - hierarchy, composition, colour, typography, density, affordance, brand - each with a pass/minor/major rating |
| `design-research` | 2 | funnel and retention reading, and qualitative/quantitative triangulation |

## Where tezgah's own rules still win

1. **The corrected floor.** `inclusive-interaction/skills/touch-target-design`
   was adapted: WCAG 2.2 SC 2.5.8 (Level AA) is 24x24 CSS px, SC 2.5.5 (Level AAA)
   is 44x44, and this repository enforces 24 (`bin/tezgah-design`'s
   `TAP_TARGET`). Where an entry and the checker disagree, the checker is right.
2. **The contract.** A vendored body never overrides `design-contract`'s token,
   state or component rules, and a finding still carries one named evidence class.
3. **Nothing executes.** These are read as instructions; no script here runs
   against a user's repository.

Neither the library nor an entry in it is a tezgah file: file an upstream bug
upstream, and record a correction as an adaptation in `SOURCE` and `NOTICE` the
way the touch floor is recorded.
