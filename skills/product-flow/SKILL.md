---
name: product-flow
description: >
  Carries a new product capability from evidence to a measured result: it runs
  `tezgah-research next --topic <t>`, which prints every step of the flow with its
  status read from the product ledger, and does the first missing step with the
  skill that step names, so each hand-off is a `product:<id>` row instead of a
  memory. Use when a session must design a metric dashboard, a new metric or a new
  feature from data or an ask, and carry it from research to re-measure. Not for
  auditing an existing feature - use `feature-audit`.
---

# product-flow

A new product capability - a dashboard over a data file, a metric, a feature
someone asked for - drifts when its steps live in the session's head: the chart
gets drawn before anyone says which goal it serves, and nobody comes back to see
whether the decision held. This skill keeps the sequence outside the session. The
steps and the rule that marks each one done are defined once, in code
(`FLOWS`, `hooks/tezgah_product.py`), and the status of each step is computed from
the product ledger rows of one topic and the files they cite. Nothing here stores
a step's state, and this file does not list the steps: a second copy of the list
would drift from the one the command reads.

## When to use it

- A new capability from data: "bu veriye uygun metric dashboard tasarla", a CSV or
  export with "what should we track".
- A new capability from an ask: "add a feature that ...", "we need a metric for ...".
- A topic already on the product ledger, to see what is left of it.

Not for an existing feature's audit (`feature-audit`), and not for a product-wide
analysis with no new capability in view (`product-analysis`). Both are steps this
flow can hand off to.

## The loop

1. Pick one kebab-case topic for the capability, such as `signup-dashboard`. Every
   row of this capability carries it.
2. Ask what is left:

   ```
   ~/.config/tezgah/bin/tezgah-research next --topic signup-dashboard
   ~/.config/tezgah/bin/tezgah-research next --topic signup-dashboard --flow feature
   ```

   Use `--flow feature` when the ask names no metric, `metric-dashboard` (the
   default) otherwise. It prints each step as `done`, `missing`, `due` or `n/a`, then a `next:` line
   with the skill and the command for the first step that is missing or due. A
   topic with no rows yet exits 2 and names `record`: write the first observation,
   then ask again.
3. Do that step, and only that step, with the skill it names. Read that skill; it
   says which rows the step leaves behind.
4. Record the rows the step produced, one JSON object per call on stdin:

   ```
   echo '{"topic": "signup-dashboard", "from": [], "class": "external", "source": "<url, read 2026-10-10>", "quote": "<what it says>"}' \
     | ~/.config/tezgah/bin/tezgah-research record O
   ```

   The writer assigns the id and the date and prints `recorded <id>`; a refused row
   prints one `FAIL product:` line per problem and stays out of the file. Cite the
   ids it printed in `from` of the next row, and as `product:<id>` in any spec,
   plan or design-contract component that rests on them.
5. Commit the rows in `.tezgah`'s private repository, so the append-only rule has a
   history to read:

   ```
   ~/.config/tezgah/bin/tezgah-research commit --product "signup-dashboard: research rows"
   ```

6. Run `next` again. Stop when it prints `next: nothing left`, or when the only
   step left is a re-measure that is not due yet; `tezgah-research due` lists the
   decisions whose re-measure date has passed.

The `build` step is always `n/a` here: building the screen is judged by the
design check and the Stop UI rule, not by the product ledger.

## Who records

Only the main session writes the product ledger. A research worker, a subagent or a
specialist reports its O and I candidates - the class, the source with the date it
was read, the quote, the statement and its confidence - in its result, and the main
session records them. A worker never runs `record`: it may run in a linked worktree,
where `record` exits 1 and names the main checkout, and two writers would race for
the same ids.

## What this skill does not do

- It does not decide what a metric is, how a dashboard looks or what a feature
  spec holds: the skill each step names owns that (`product-analysis`, `research`,
  `feature-audit`, `design-contract`, `analyze-app`).
- It does not replace the product ledger's rules. The row types, their fields and
  the append-only rule are in the "The product ledger" section of `docs/research.md`.
