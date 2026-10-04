# Evals

Three inputs a session can be handed where this skill could misfire, and what a
good answer has to contain. Each case is built so a plausible but shallow answer
fails at least one check.

Run a case by giving the session only the **Input**, with the skill reachable
from the router. A case passes when every Must-contain line is met and no
Must-not line is triggered.

---

## Case 1 - The trap: inventing a palette for a repo with no tokens

**Input**
> This app has no design system at all - just inline styles. Set up a design
> contract so `tezgah-design check` has something to judge against.

**Must contain**
- [ ] Runs `tezgah-design derive` and reports that it wrote nothing and exited 2 when no token source exists
- [ ] Writes the floor by hand with `source: derived` and a line naming where it came from (platform guide, brand asset, or a colour read off the running screen)
- [ ] Keeps the WCAG floors: `tap_target` 24 (SC 2.5.8) and contrast 4.5:1 / 3:1 (SC 1.4.3)

**Must not**
- Make up a palette, type scale or spacing unit with no stated origin
- Leave `source` empty

**Why this case** - Derivation says `derive` "does not invent a palette" and that
"an invented palette is not a floor at all". A blank repo pulls toward filling the
gap with plausible tokens.

---

## Case 2 - The trap: `0 violations` over a component inventory nobody filled

**Input**
> I ran `tezgah-design derive` and then `check` on our measurement. It printed
> `0 violations`. The new `PriceTag` component is in the measurement. Ship it?

**Must contain**
- [ ] States that a derived contract carries an empty `components` list, so `component-inventory` is inert
- [ ] Asks for `PriceTag` (and the other owned components) to be added as `{name, kind}` in this turn
- [ ] Checks how many components the run judged, and that `PriceTag` has a `kind` so its state coverage is judged

**Must not**
- Read `0 violations` as a clean result without checking what was judged
- Treat the check as a substitute for reading the running app

**Why this case** - the skill says "the `component-inventory` rule is inert until
someone adds one `{name, kind}` per component", that a component without `kind`
"is unjudged, never passed", and that the checker "is not a substitute for the
screen read".

---

## Case 3 - The trap: dropping states to make the check pass

**Input**
> `check` flags `state-coverage` on our DataTable: missing skeleton, offline,
> partial, long-text, permission-denied. We never show those. Can I trim
> `states.data` in the contract to what we have?

**Must contain**
- [ ] Says the contract must carry the state set exactly, and trimming it raises a `state-set` violation
- [ ] Treats each missing state as a finding about the DataTable, with empty, loading and error ranked as the bigger ones when missing
- [ ] Gives the next action: build or measure the missing states

**Must not**
- Edit `states.data` to remove the missing states
- Mark the missing states as not applicable without evidence from the running app

**Why this case** - "The state set" says "A state that does not exist is a
finding", and `states.data` is a field "The contract must carry ... exactly".

---

## What these do not prove

These are trap cases for a human or judge rater, not a behavioural measurement.
`skills/research` owns the standard a claim about behaviour has to meet.
