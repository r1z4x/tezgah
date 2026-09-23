# Corpus correction: A13 is withdrawn, and what survives it

Committed after E7's two prompted raters answered the question, and before the
second feature's arms are re-scored. Cause: the row asserted a mechanism the code
does not have.

## What A13 claimed, and what the code does

A13 said the create-user handler "fills every missing value from a default, so a
record can be created with an empty email, an empty password and a viewer role".

Read at source after the prompt:
`apps/.../admin/backend/src/handlers/admin.rs:892-905` binds each missing field to an
empty string, and `:906-913` then rejects the request -

    if email.is_empty() || password.is_empty() || tenant_id.is_empty() {
        return err(StatusCode::BAD_REQUEST, "email, password, and tenant_id are required");
    }
    if password.len() < 8 {
        return err(StatusCode::BAD_REQUEST, "Password must be at least 8 characters");
    }

So the defaults exist only to build the validation inputs, the request fails, and no
record is created. **A13's claim is false as written and the row is withdrawn.** Both
E7 raters reached this independently, and their citations agree with the code read
above.

## What survives: A15, same class, correct claim

The defect that exists on that path is on the other side of the boundary:

> **A15 (class C8, form pattern).** The create form has no client-side guard at all:
> the modal is not a `<form>` element, no field receives `required` or an error prop,
> the submit button is disabled only while a request is in flight, and the server's
> 400 is surfaced as a toast with no field marked, no error summary and no focus move,
> while the application's other create surfaces validate the same way this one does
> not.

Evidence: `admin/frontend/src/pages/Users.tsx:244-271` (no `<form>`, no required
props, button guarded only by `isPending`), `:36` (form state defaults), `:49-53`
(error path is one `toast.error`), `:52` (no field binding);
`admin/backend/src/handlers/admin.rs:906-913` (the refusal);
`admin/frontend/src/pages/Tenants.tsx:164,184` (a sibling create surface that does
validate). Class `code`.

## Effect on scoring

| Row | Before | After |
|---|---|---|
| A13 | a C8 defect row | withdrawn |
| A15 | - | the C8 defeat row |

The denominator stays at six defect classes. An arm that reported *A13's mechanism*
(the silent-default story) has made a claim the code contradicts, and is scored as a
**false claim** rather than a detection; an arm that reported the client-guard and
error-association behaviour is scored as detecting C8 via A15.
