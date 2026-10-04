# Evals

Three inputs a session can be handed where this skill could misfire, and what a
good answer has to contain. Each case is built so a plausible but shallow answer
fails at least one check.

Run a case by giving the session only the **Input**, with the skill reachable
from the router. A case passes when every Must-contain line is met and no
Must-not line is triggered.

---

## Case 1 - The trap: a static snapshot read as "the state is missing"

**Input**
> Check the Save button on `/settings` for missing states. I only need a quick
> look at the snapshot.

**Must contain**
- [ ] Reads the tree with `browser_snapshot` and acts on element references
- [ ] Drives the interactive states (hover, focus, active, disabled) before calling any of them missing
- [ ] Routes the data-side states it checks (loading, error, offline) with the network tools before judging them
- [ ] Says which states were driven and re-read, and which only the static tree showed

**Must not**
- Report hover or focus as missing because the static snapshot does not show them
- Judge the states from a screenshot alone, without the tree

**Why this case** - the triage section says "a static snapshot never shows hover",
and that a state reported as not shown is "driven ... and routed ... and then
re-read, before it is called missing". "Quick look at the snapshot" invites the
shortcut.

---

## Case 2 - The trap: a mobile contrast claim from the view tree

**Input**
> On the iOS simulator build, is the grey caption text on the onboarding screen
> readable? Check the contrast and the tap targets.

**Must contain**
- [ ] States that contrast and tap-target size are not measurable from the Mobile MCP view tree
- [ ] Takes a screenshot and names why (colour and size the tree cannot carry), or declines to make the claim
- [ ] Labels any readability verdict as a judgement and says how many passes agreed

**Must not**
- Give a contrast ratio or a pass/fail read off `mobile_list_elements_on_screen`
- Call a `mobile_verify_*` tool or claim an assertion that Mobile MCP does not offer

**Why this case** - "Mobile caveats" says contrast and tap-target size "are
**not measurable** from the tree: take the screenshot (naming why), or do not
make the claim", and that there is no `mobile_verify_*`.

---

## Case 3 - The trap: a clean axe run read as WCAG conformance

**Input**
> Run axe on the checkout page. If it comes back clean we can say we are WCAG
> 2.2 AA compliant, right?

**Must contain**
- [ ] Injects axe-core from a pinned build with `browser_evaluate`
- [ ] States that axe covers on average 57% of WCAG issues and reports its `incomplete` results
- [ ] Names the gaps it hand-checks or leaves open: focus appearance, target size, dragging, accessible authentication
- [ ] Names the viewport widths it judged

**Must not**
- Load axe from a `@latest` CDN script
- Declare WCAG 2.2 AA conformance from a clean axe run alone

**Why this case** - "The automated sweeps" says axe finds "on average 57% of WCAG
issues automatically" and that the named gaps "are hand-checked, not assumed";
it also forbids a `@latest` script.

---

## What these do not prove

These are trap cases for a human or judge rater, not a behavioural measurement.
`skills/research` owns the standard a claim about behaviour has to meet.
