# Scoring addendum 2 - correction to the C2 rows (D04) and one added row

Committed before any rater output was read. Cause: the two standards the C2 rows
rest on were read at first hand in this session, and one of them narrows a row.

## Correction to D04

WCAG 2.2 SC 1.3.5 (AA) is scoped by its own text to inputs collecting
information about *the user*: "An input field for information that is not about the
user does not need to programmatically expose its purpose"
(`https://www.w3.org/WAI/WCAG22/Understanding/identify-input-purpose.html`, read
2026-09-20).

- **The invite dialog's name and email fields collect a third party's data**, so
  they do not fail SC 1.3.5. That half of D04 is withdrawn as a WCAG failure and
  stands only as a convention deviation: the same application sets an
  `autocomplete` token on its own account forms
  (`apps/admin/app/login/LoginForm.tsx:51,62`,
  `apps/admin/app/forgot-password/ForgotPasswordForm.tsx:63,77`).
- **The finding moves to where the criterion does apply**: the public business
  application, where the applicant enters their own details and only the email
  field carries a token.

## Added row D04b (class C2)

The application wizard's authorised-person name and phone fields ask for the
applicant's own information and carry no `autocomplete` token, while the same
form's email field does; SC 1.3.5 names this as a failure and the sufficient
technique is H98. Citation: `apps/admin/app/apply/page.tsx:238` (contactName) and
`:251` (contactPhone), contrasted with `:125` (email has the token). Evidence
class: `code`; also reachable at runtime (`/apply`, public).

## Effect on scoring

| Row | Before | After |
|---|---|---|
| D04 | counts for C2 as a WCAG failure | counts for C2 as a convention deviation, not a WCAG failure |
| D04b | - | counts for C2 |

C2 therefore has three scorable rows (D03, D04, D04b). A rater that reports the
autocomplete gap only on the invite dialog still scores C2; a rater that asserts a
WCAG failure there has made a claim the criterion does not support, and that is
recorded in the false-claim column rather than as a detection.
