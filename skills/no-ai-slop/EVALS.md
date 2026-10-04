# Evals

Three inputs a session can be handed where this skill could misfire, and what a
good answer has to contain. Each case is built so a plausible but shallow answer
fails at least one check.

Run a case by giving the session only the **Input**, with the skill reachable
from the router. A case passes when every Must-contain line is met and no
Must-not line is triggered.

---

## Case 1 - The trap: a detect request answered with a rewrite and a score

**Input**
> Does this read as AI? Don't change it, just tell me.
>
> "In today's fast-paced world, our platform stands as a testament to
> innovation. It's not just a tool - it's a partner. Ultimately, we empower
> teams to do their best work."

**Must contain**
- [ ] Names each pattern from the skill with the quoted line: "In today's world" phrase, importance puffery ("stands as a testament"), binary contrast ("not just a tool - it's a partner"), summary ending ("Ultimately"), banned word ("empower")
- [ ] Gives the fix for each in a few words
- [ ] Offers to edit the draft afterwards

**Must not**
- Return a rewritten paragraph
- Give a score, a percentage, or a verdict on whether AI wrote it

**Why this case** - the Detect job says "Do not rewrite, score the draft, or
guess whether AI wrote it. AI detectors guess. Named patterns are evidence the
user can check."

---

## Case 2 - The trap: polishing away the writer's voice

**Input**
> Clean this up for our team channel, it reads rough:
>
> "ok so honestly the migration was a mess. I think we lost like two days to the
> schema thing, which, fine, my fault. but it works now and deploys take 4 min
> instead of 40."

**Must contain**
- [ ] Keeps the blunt admission ("my fault"), the real-uncertainty "I think" and the 40 -> 4 minute figure
- [ ] Makes a minimum effective edit that still sounds like the same person
- [ ] Ends with a short **What changed** section

**Must not**
- Turn it into formal corporate prose ("The migration encountered challenges...")
- Delete "I think" or "honestly" only because they appear on the often-empty list

**Why this case** - the skill says "Preserve the writer's real voice", "Make
the minimum effective edit" and keep "I think" when it expresses "real
uncertainty, self-awareness, or the writer's spoken rhythm". The word lists pull
the other way.

---

## Case 3 - The trap: English rules and translated terms in a Turkish draft

**Input**
> Bu PR açıklamasını daha doğal yaz, çeviri gibi duruyor:
>
> "`render_table` fonksiyonu artık `--pr-info` bayrağını destekliyor. Bu
> değişiklik, kullanıcı deneyimini kaldıraçlıyor ve tablonun 140 ms içinde
> render edilmesini sağlıyor."

**Must contain**
- [ ] Keeps `render_table`, `--pr-info` and `140 ms` exactly as written
- [ ] Replaces the calque ("kaldıraçlıyor", a word-for-word "leverage") with a Turkish verb, citing or naming a Turkish authority to check against
- [ ] Says which legs of the rail it has for Turkish and which it lacks

**Must not**
- Translate, respell or pluralise the identifiers or the unit symbol
- Apply the English banned-word list translated into Turkish as rules

**Why this case** - "Terms that must not be translated" lists identifiers and
unit symbols, and "Writing in another language" says "Do not translate them into
another language and apply them as rules".

---

## What these do not prove

These are trap cases for a human or judge rater, not a behavioural measurement.
`skills/research` owns the standard a claim about behaviour has to meet.
