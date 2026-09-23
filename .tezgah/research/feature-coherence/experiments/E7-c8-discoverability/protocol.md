# E7 - why the silent-defaults class stayed invisible

## What changes

Nothing. This experiment diagnoses one class: **C8**, whose only row on the second
corpus (A13) says the create-user path submits with any field empty and the handler
fills every missing value from a default, so a user can be created with an empty
e-mail, an empty password and a viewer role.

Measured fact to explain: **four raters in E5's two arms - and ten more across E1-E4's
two arms on the first feature - never reported this class unprompted.**

## Method

Two fresh rater contexts, same feature as E5, same blindness rules, with one added
sentence in the brief: *"Before you finish, answer one question with evidence: what
does this feature do when the create form is submitted with its fields left empty?"*
They apply `feature-audit` as usual; the question is the only difference from E5's
treatment arm.

The comparison is with E5's four raters, who were asked for a general audit; this
path was only the extra question.

## Predicts

Both prompted raters name the behaviour - the field defaults on the server, the
client's submit button being enabled with empty fields, and the absence of any
required/format check on that path - so the class is **findable when looked for and
invisible to an unprompted sweep**. The row's own evidence is then sound and its
absence from four artifacts is a coverage property of the method, not a defect in the
corpus.

## Falsification criterion

Zero of two prompted raters naming the behaviour would falsify that reading: the row
would then be either wrong (and the corpus needs correcting by an addendum) or
undiscoverable from source, and this experiment's analysis says which, with the
rater artifacts as the evidence.

## Why

A class that nobody finds may be a corpus artefact. Before the finding is reported as
a coverage gap, the same raters must be given the question that names it; otherwise
the line is describing its own instrument as a property of the method.
