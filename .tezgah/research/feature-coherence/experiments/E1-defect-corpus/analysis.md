# E1 - defect corpus: result

## What ran

Read at HEAD `98f985f` of `/Users/rizax/Projects/Ustam`: the users route and its
components, its server actions, the users controller and service, the shared
form/picker components it uses, the apply wizard it shares the form conventions
with, and the sibling list pages that establish the repository's own list
convention. No runtime row: the stack boot is a separate arm (E1b) because a
corpus frozen now must not be edited later.

Frozen instrument: `results.jsonl` at this directory,
sha256 `70871644e095372e6e9a5faa5fa761d8dee60c87e82eaca33d5dd857a938d1a6`,
15 rows, `scope: real` (the running system's own source at HEAD), every row with
a `path:line` citation. Rows: D01-D15.

## Outcome against the prediction

| Predicted | Observed | Verdict |
|---|---|---|
| 8-10 of the 10 classes yield a real instance | 10 of 10 | hit |
| 12-30 rows | 15 | hit |
| at least 6 rows evidenced by running the app | 0 (`ui-observed` rows exist only in E1b) | **not met by this experiment** |

Class coverage: C1 x3 (D01, D02, D15), C2 x2 (D03, D04), C3 x1 (D05),
C4 x2 (D06, D07), C5 x1 (D08), C6 x2 (D09, D10), C7 x1 (D11), C8 x1 (D12),
C9 x1 (D13), C10 x1 (D14).

## What the corpus shows

- **Two rows are pass rows, kept deliberately**: D09 (the wizard's step gates
  are enforced server-side by redirect) and D15 (the UI hides the platform-owner
  edit and the server independently refuses the same target) - the scoring rule
  lists exactly these two as the false-positive rows. A corpus that only
  holds defects cannot show that the method distinguishes agreement from drift,
  and a rater that reports a defect on either row is penalised by the scoring.
- **Nine of the thirteen defect rows are invisible from the screen alone.** D01
  and D02 are a capability the server has and no surface reaches; D03 is a
  contract field with no surface; D05, D06 and D10 need the sibling convention or
  the API family to be read before the deviation exists at all; D11 is a map of
  three surfaces that no single screen shows; D12 is the absence of persistence
  and of a duplicate check the server already implements; D14 is the absence of
  an artifact slot. Each requires comparing two layers, which is the unit of
  analysis the shipped rubric does not name - and the other four (D04, D07, D08,
  D13) are decidable against a named standard, so nine plus four is the thirteen.
- **The remaining four are decidable against a named standard, not a taste.**
  D04 is WCAG 2.2 SC 1.3.5 (the same app sets the token elsewhere - D04's
  contrast file), D07 is the WAI-ARIA APG combobox pattern, D08 is an
  unannounced data-losing change, D13 is a destructive confirmation that omits
  what is destroyed.
- **The feature is not badly built.** It has permission gates on both sides, an
  empty state, confirmation dialogs, `role="alert"` surfaces, `aria-describedby`
  error wiring, `role="status"` pending text and a screenshot-visible design
  language. This matters for the measurement: the corpus tests whether a method
  finds *cross-layer* defects in sound code, not whether it can find obvious bugs.

## Limits of this instrument

- One feature in one repository, one stack (Next.js server components + NestJS +
  Prisma). The class taxonomy transfers; the probes do not.
- The rows were found by reading source. A runtime pass could contradict a row
  (for example, a client-side gate could be backed by a middleware the reading
  missed); E1b is where that would surface, and the corpus is not edited in
  response - a contradicted row is reported as contradicted.
- The rater for every later experiment shares the model family that built this
  corpus, so the corpus is a floor on what is findable, not the truth about the
  feature.
