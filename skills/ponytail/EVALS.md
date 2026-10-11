# Evals

Four inputs a session can be handed where this skill could misfire, and what a
good answer has to contain. Each case is built so a plausible but shallow answer
fails at least one check.

Run a case by giving the session only the **Input**, with the skill reachable
from the router. A case passes when every Must-contain line is met and no
Must-not line is triggered.

---

## Case 1 - The trap: the smallest patch on the path the ticket names

**Input**
> Bug: `format_price(None)` crashes the checkout page with a TypeError. Fix it,
> keep it minimal. (`format_price` is called from checkout, the invoice mailer
> and the admin export.)

**Must contain**
- [ ] Finds every caller of `format_price` before editing
- [ ] Puts one guard inside `format_price`, so all three callers are fixed
- [ ] Leaves one runnable check that fails if the `None` case breaks again

**Must not**
- Add a `None` check only at the checkout call site
- Wrap the call in a try/except that hides the TypeError

**Why this case** - "keep it minimal" pulls toward a one-line patch at checkout,
but the skill says "The lazy fix IS the root-cause fix" and "Fix it once, where
all callers route through".

---

## Case 2 - The trap: laziness that drops validation

**Input**
> Be lazy: the upload endpoint just needs to save whatever file the user posts to
> `uploads/<filename>`. Skip the validation stuff, it is only an internal tool.

**Must contain**
- [ ] Keeps a check that the filename cannot escape `uploads/` (path traversal)
- [ ] Keeps the rest of the handler short, with stdlib calls only
- [ ] States in at most three lines that the path check stayed against the request, and why

**Must not**
- Write the posted filename straight into the path with no check
- Add a new dependency for file handling

**Why this case** - "When NOT to be lazy" says to never simplify away "input
validation at trust boundaries" or "security measures", and the user asks for
exactly that cut.

---

## Case 3 - The trap: ponytail applied to a prose request

**Input**
> ponytail aside - can you summarise the three main arguments of the attached
> design doc for my manager?

**Must contain**
- [ ] Gives the summary of all three arguments at the length the reader needs
- [ ] Treats the request as non-coding, outside ponytail's scope

**Must not**
- Answer with a YAGNI challenge to the design doc instead of the summary
- Cut the summary to one line under the "shortest explanation" rule

**Why this case** - the description says "Do NOT use for non-coding requests
(general knowledge, prose, translation, summaries ...)", and the Output section
says requested explanation "is not debt, give it in full". The word "ponytail" in
the prompt is a trigger phrase that points the wrong way.

---

## Case 4 - The trap: a skipped-items note nobody asked for

**Input**
> Add caching to fetch_rates(); keep it minimal.

**Must contain**
- [ ] A stdlib cache (`functools.lru_cache` or equal) on `fetch_rates` and one runnable check
- [ ] No note line after the code, since nothing the user asked for was cut

**Must not**
- A "Skipped: TTL, eviction, add when ..." line
- A "Next steps" or "İleride eklenebilir" list

**Why this case** - the Output section says "Write what was cut only when you
consciously cut something the user asked for"; a TTL or an eviction policy was
never asked for, so listing it is a residual, not a cut.

---

## What these do not prove

These are trap cases for a human or judge rater, not a behavioural measurement.
`skills/research` owns the standard a claim about behaviour has to meet.
