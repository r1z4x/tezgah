# Evals

Four inputs a session can be handed where this skill could misfire, and what a
good answer has to contain. Each case is built so a plausible but shallow answer
fails at least one check.

Run a case by giving the session only the **Input**, with the skill reachable
from the router. A case passes when every Must-contain line is met and no
Must-not line is triggered.

---

## Case 1 - The trap: analysing a product nobody can observe

**Input**
> Retention on our mobile app is falling. Why, and what should we build next to
> fix it? (The app ships with an analytics SDK that was never configured.)

**Must contain**
- [ ] States first that the behaviour is not observable today: "we cannot see this yet"
- [ ] Marks every causal claim about retention as a hypothesis, with the cheapest test that would falsify it
- [ ] Defines retention as a ratio with numerator, denominator and window under a Goal -> Signal -> Metric chain
- [ ] Frames opportunities as user needs, with at least three candidate solutions plus the status quo

**Must not**
- Name a cause of the drop as fact with no `behaviour` or `user-verbatim` evidence
- Recommend a feature as the answer before the opportunity it serves

**Why this case** - "The gate: can we see it at all" says an unobservable product
is "the first finding ... not a footnote", and the value axis says "an
opportunity is a need".

---

## Case 2 - The trap: a UX verdict read from source

**Input**
> Here is the repo for our booking web app. Do a UX audit of the checkout - you
> can read the React components, no need to run anything.

**Must contain**
- [ ] Says a UI claim from source is not `ui-observed` evidence, and runs the app through `analyze-app` or marks the usability axis as not observed
- [ ] Builds the state matrix per interactive component and data view, naming each state that does not exist
- [ ] Rates findings on the 0-4 severity scale and labels each a `failure` or a `judgement`, with the rater count
- [ ] Names the WCAG 2.2 level claimed and what axe-core cannot see

**Must not**
- Report usability findings tagged `ui-observed` that came only from reading components
- Present one pass as a panel, or give a judgement a `certain` confidence

**Why this case** - the evidence table says a `ui-observed` finding "does not
count" when it is "a UI claim inferred from source". The UX discipline says "An
agent is one rater ... report the rater count".

---

## Case 3 - The trap: a feature list where nothing is cut

**Input**
> We have 14 features in the admin panel and limited engineering time. Which
> ones matter? Everything feels important to the team.

**Must contain**
- [ ] Gives every feature a verdict of keep, fix, cut or bet
- [ ] Gives each verdict its deciding metric, threshold, timeframe, action, flag and owner
- [ ] Says what the analysis did not look at and what would flip a verdict

**Must not**
- Rank the features without cutting any
- Accept "everything is important" as a verdict
- Leave a cut with no owner

**Why this case** - the triage axis says "every feature gets keep, fix, cut or
bet; 'everything is important' is not a verdict; a cut nobody owns will not
happen", and "A feature list where nothing is ever cut" is a named failure mode.

---

## Case 4 - The trap: a state matrix filled from one snapshot

**Input**
> Fill the state matrix for the settings form. The app runs on localhost:3000
> and the form component is in `src/settings/Form.tsx`.

**Must contain**
- [ ] Reads each component's states with `tezgah-triage --states FILE --component <ref>` over the analyze-app snapshot
- [ ] Says a static snapshot shows only the current state, and drives or routes a state reported as not shown before calling it missing
- [ ] Names the read behind every cell: the snapshot, the driven re-read, or not observed

**Must not**
- Fill a cell with a state inferred from source
- Call hover, focus or an error state missing from one at-rest snapshot

**Why this case** - the depth ladder says "The state matrix is mandatory for
every interactive component", and its state read says a static snapshot "shows
only the state the route happens to be in".

---

## What these do not prove

These are trap cases for a human or judge rater, not a behavioural measurement.
`skills/research` owns the standard a claim about behaviour has to meet.
