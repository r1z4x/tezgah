# The rule base behind the surface-pattern matrix (practice note)

Standards and grey guidance, read at source 2026-09-20 by a delegated pass in this
session, except where a URL is marked otherwise. This note is the source record for
Matrix 5 of `skills/feature-audit/SKILL.md`; the skill keeps the decidable rule and
the source name, and this file keeps the URLs.

## Standards

- **WAI-ARIA Authoring Practices** - combobox, listbox, grid, table, dialog modal,
  alertdialog, disclosure, tabs: `https://www.w3.org/WAI/ARIA/apg/patterns/`. The
  combobox pattern read first hand in this session; the rule set covers roles and
  states (`aria-expanded` tracking the popup, `aria-controls`, `aria-activedescendant`
  for a listbox popup) and the keyboard contract (Down/Up, Escape returning focus,
  Enter accepting, the popup out of the Tab order).
- **WCAG 2.2 Understanding** - SC 1.3.1, 1.3.5, 1.4.3, 1.4.10, 1.4.11, 2.4.7,
  2.5.8, 3.3.1, 3.3.3, 3.3.4, 3.3.7, 4.1.3:
  `https://www.w3.org/WAI/WCAG22/Understanding/`. SC 1.3.5 was read first hand and
  is what narrowed a corpus row: it is scoped to inputs collecting information about
  *the user*, so a form collecting a third party's data is outside it.
- **GOV.UK Design System** - question pages, check answers, error message, error
  summary, validation, task list, table, summary list, pagination, notification
  banner, interruption pages: `https://design-system.service.gov.uk/`. Note
  `patterns/one-thing-per-page/` returns 404 as of 2026-09-20; the guidance now
  lives in `patterns/question-pages/`.

## Grey guidance, quoted for concrete rules

- Material 3 - text fields, lists, date pickers: `https://m3.material.io/`. The
  pages are JS shells; their text was read through a reader proxy.
- Apple HIG - text fields, lists and tables, pickers:
  `https://developer.apple.com/design/human-interface-guidelines/`, read through the
  JSON endpoint the pages load themselves.
- NN/g - data tables, banner blindness, infinite scrolling.

## What the automated sweep cannot see

From axe-core's own repository (`https://github.com/dequelabs/axe-core`, read
2026-09-20): it finds "on average 57% of WCAG issues automatically" - issues, not
success criteria. Its rule tags cover WCAG 1.3.1, 1.4.3, 1.3.5 and 2.5.8 (the
`target-size` rule is **disabled by default**); there is **no rule** tagged for SC
1.4.10, 2.4.7, 3.3.1, 3.3.3 or 4.1.3. Those are hand-checks, which is why the skill
lists eight of them.

Quality: the two W3C sources and GOV.UK are standards or a government design
system, cited for their rules. Material 3, Apple HIG and NN/g are vendor or
practice guidance, read for their concrete rules and marked grey as evidence of
correctness.
