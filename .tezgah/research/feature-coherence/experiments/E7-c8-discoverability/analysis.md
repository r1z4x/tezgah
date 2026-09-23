# E7 - why the silent-defaults class stayed invisible: result

## What ran

Two rater contexts applied `feature-audit` to the same feature as E5 with one added
question: *what does this feature do when the create form is submitted with its
fields left empty?* Both traced it end to end and both answered the same way:

- the modal is not a `<form>` element, no field carries `required` or an error prop,
  and the submit button is disabled only while a request is in flight
  (`Users.tsx:244-271`, `:263-264`), so the client posts empty strings;
- the handler then refuses: `admin.rs:906-913` returns
  `400 {"success":false,"error":"email, password, and tenant_id are required"}` (and a
  separate 400 for a password under eight characters);
- the refusal reaches the operator only as a toast: no field is marked, no error
  summary appears, focus does not move, and the modal keeps what was typed
  (`Users.tsx:49-53`).

## Outcome against the prediction

The prediction was that both prompted raters name the behaviour, which would mean the
class is findable when looked for. Both did - **and in doing so they contradicted the
row the class was built on.** E7's falsification branch fired:

> the row would then be either wrong (and the corpus needs correcting by an addendum)
> or undiscoverable from source, and this experiment's analysis says which, with the
> rater artifacts as the evidence.

It was **wrong**. A13 claimed the handler fills missing values from defaults and
creates the record anyway; the handler validates and refuses.
`E5-transfer/corpus-correction.md` withdraws A13 and replaces it with A15, which
states the defect that does exist on that path (no client-side guard, the refusal
surfaced only as a toast, a sibling create surface that does validate).

## What this means for the coverage question

- **The class was not invisible; my row was undetected because it was not true.** Ten
  raters across two features did not report A13's mechanism; the reason is that no
  such mechanism exists. The absence was evidence about the corpus, and the corpus is
  what changed.
- **The method kept the first feature's arms honest by accident.** Every arm that
  reported *something* about this path (E6-ctl2 among them) reported the
  silent-default story - the story the corpus told it - which is what a wrong row
  does to a measurement: it manufactures agreements.
- **The corrected row is discoverable, and the treatment arm reaches it.** Under A15,
  the behaviour the prompted raters described counts as a C8 detection for any arm
  that reported the client guard and the error association; the unprompted E5 arms did
  not, which is the honest coverage statement: this class needs the path named.

## Limits

- Two prompted raters, one feature, one question: this measures that the behaviour is
  findable when asked, not the rate at which an unprompted sweep finds it.
- The correction was written after E5' arms ran and after their numbers were first
  computed; the recomputation is reported in E5's analysis with both readings, and the
  frozen corpus file itself is not edited - a correction is a new artifact, not an
  amendment.
