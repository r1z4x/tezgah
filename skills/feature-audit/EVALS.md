# Evals

Three inputs a session can be handed where this skill could misfire, and what a
good answer has to contain. Each case is built so a plausible but shallow answer
fails at least one check.

Run a case by giving the session only the **Input**, with the skill reachable
from the router. A case passes when every Must-contain line is met and no
Must-not line is triggered.

---

## Case 1 - The trap: a screen-level fix for a capability that does not exist

**Input**
> On our admin "Invite user" form, invited people never get anything - they just
> show up as pending forever. Make the form better so admins understand what
> happens.

**Must contain**
- [ ] Fills the capability matrix for invite, including what the recipient actually receives
- [ ] Cites the `path:line` (or the search) showing there is no delivery path for the invite
- [ ] Emits a capability-change proposal with a rejectable artifact (a contract or schema diff, a typed flag with an expiry, or an ADR with a status)
- [ ] Gives every finding a Prevent line

**Must not**
- Recommend only form copy, a tooltip or a "pending" badge as the fix
- Claim the delivery path is absent without naming the search that proves it

**Why this case** - the skill's "The end of the action" row says an action
with no delivery path "succeeded in the database and failed the user". Its
proposal rule says "if the fix list for a finding names no layer that already
exists, the proposal is required."

---

## Case 2 - The trap: auditing only the form fields

**Input**
> Audit the Orders area of our back office - it is a list page with filters and
> a detail view, plus an edit form. What is missing?

**Must contain**
- [ ] Audits the orders table, the filters and the detail view to the same depth as the edit form
- [ ] Checks data-view rules such as real headers, `aria-sort`, a visible active filter state, and a "not provided" value in the detail view
- [ ] Includes pass rows where layers agree, and marks unchecked cells `[NOT CHECKED: reason]`
- [ ] States coverage per matrix and how many passes ran, from which entry points

**Must not**
- Limit the audit to form inputs and validation messages
- Present a list of defects with no pass rows and no coverage counts

**Why this case** - "The unit" says "Nothing here is restricted to form fields:
a table is audited to the same depth as an input", and "Data views come first,
not last".

---

## Case 3 - The trap: a clean axe run taken as covering the hand-checks

**Input**
> We ran axe on the checkout wizard and it reported zero violations. Can you
> confirm the wizard's errors, status messages and focus are fine?

**Must contain**
- [ ] States that axe has no rule for SC 3.3.1, 3.3.3, 4.1.3, 2.4.7 or 1.4.10, and that `target-size` is off by default
- [ ] Hand-checks error text, status announcements, visible focus and reflow at 320 px, or marks each as not checked
- [ ] Fills the flow matrix, including whether each step's precondition is enforced on the server

**Must not**
- Confirm the wizard as fine on the strength of the axe run
- Treat a client-only step check as enforced

**Why this case** - "What cannot be checked mechanically" lists exactly these
gaps as "hand-checks, never assumptions". Matrix 3 says "a check that lives
only in the client is not enforced".

---

## What these do not prove

These are trap cases for a human or judge rater, not a behavioural measurement.
`skills/research` owns the standard a claim about behaviour has to meet.
