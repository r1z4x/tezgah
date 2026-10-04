# Evals

Three inputs a turn on this library can actually be handed, and what a good
answer has to contain. Each case is built so a plausible-sounding but shallow
answer fails at least one check - the first one, deliberately, is the mistake the
vendored corpus itself made before it was corrected.

Run a case by giving the session only the **Input**, with the library reachable
from the router. Score against **Must contain**: a case passes when every
Must-contain line is met and no Must-not line is triggered.

---

## Case 1 - The trap: a size quoted against the wrong level

**Input**
> Our spec says buttons must be 44x44 because that is the WCAG AA minimum for
> touch. Our design system ships 32x32 buttons. Are we failing WCAG AA?

**Must contain**
- [ ] States that SC 2.5.8 Target Size (Minimum) is Level AA at 24x24 CSS px
- [ ] States that 44x44 is SC 2.5.5 Target Size (Enhanced), Level AAA - and the common platform guideline, not the AA floor
- [ ] Places 32x32 above the AA floor and below the platform guideline, naming which claim that makes it
- [ ] Gives the next action (spacing, hit area, or a documented exception), not just a verdict

**Must not**
- Repeat that 44x44 is the WCAG AA minimum
- Call 32x32 a WCAG AA failure without naming the criterion it fails

**Why this case** - upstream's touch-target body said exactly this; it is the one
body `SOURCE` records as adapted
(`inclusive-interaction/skills/touch-target-design/SKILL.md`). An answer that
parrots the library without the correction fails on the first Must-not line.

---

## Case 2 - The trap: a tracking artefact read as a design problem

**Input**
> Our signup funnel drops 60% of users between "account created" and "profile
> completed". Leadership wants the profile step redesigned this quarter. Where do
> we start?

**Must contain**
- [ ] Questions what the two events fire on before proposing any redesign
- [ ] Names at least one non-design explanation (the step is skippable, the event fires on render, the profile is reachable later)
- [ ] Says what would confirm or kill the tracking explanation, cheaply
- [ ] Gives one ranked next action rather than everything that could be wrong

**Must not**
- Accept the 60% at face value and go straight to redesign recommendations
- Answer with a generic list of form-usability tips

**Why this case** - `design-research/skills/behavioural-analytics` exists for
this reading, and the shallow answer is indistinguishable from it in tone.

---

## Case 3 - The trap: a verdict with no dimension and no evidence

**Input**
> Here is a screenshot of our dashboard. Is the design good?

**Must contain**
- [ ] One critique per dimension it did read, each with an Observation, a Problem and a Fix
- [ ] A rating per finding - pass, minor or major - not a single overall score
- [ ] At least hierarchy, density and typography named, and the evidence each reading rests on (what on the screen shows it)
- [ ] Separates a contract or token violation from a taste preference

**Must not**
- Deliver "looks clean and modern" as the answer
- Propose a redesign without an observation that the redesign answers

**Why this case** - `visual-critique` is a fixed vocabulary with a rating, and the
per-dimension shape is the whole of its value; a one-line verdict is the failure
mode `feature-audit` and `product-analysis` are also built to avoid.

---

## What these do not prove

Nothing here measures whether reading a vendored body changes what a session
produces - these are three trap cases with a human or judge rater, not a
behavioural measurement. `skills/research` owns the standard a claim about
behaviour has to meet.
