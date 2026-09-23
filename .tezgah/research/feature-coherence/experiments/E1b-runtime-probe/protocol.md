# E1b - runtime rows for the frozen corpus

## What changes

Nothing in either repository. This experiment exercises the running Ustam admin
app and records which of the E1 corpus rows are observable at runtime, which are
contradicted by it, and which cannot be reached from the surface. E1's `results.jsonl`
is not edited: this experiment writes its own file, and the corpus stays frozen at
sha256 `70871644e095372e6e9a5faa5fa761d8dee60c87e82eaca33d5dd857a938d1a6`.

Environment, as booted and observed in this session (recorded because the numbers
are meaningless without it): admin `next dev` at `http://127.0.0.1:3000`, API at
`http://127.0.0.1:3001/api/v1` against the seeded `servistek` database,
authenticated as `platform@servistek.test` (SUPER_ADMIN in the PLATFORM
organization) with the cookie state captured to
`/tmp/ustam-probe/admin-auth-state.json`.

## Method

For each corpus row that runtime can settle, drive the app and record the
observation with the tool call, the state, and the rendered evidence:

1. Network: load `/users` with request logging on, and record which of
   `/api/v1/users`, `/users/:id` and `/users/:id/deactivate` the surface actually
   calls (settles D01, D02).
2. Rendered columns: read the table's header and one row against the API response
   for the same request (settles D03).
3. Attributes and live regions: read the invite form's controls' attributes in the
   live DOM, and the accessible names/roles of the count paragraph (settles D04,
   D06's announcement half).
4. Empty and filtered states: search for a string that matches nothing and read
   the result (D06, and the list's empty state row).
5. Breakpoints: the same screen at 320 / 768 / 1280 CSS px (the reflow row).
6. The wizard: request `/apply?step=3` and `/apply?step=2` in a fresh context and
   record the redirect (D09's runtime half).
7. The picker: reach a screen that uses the picker, change the customer select and
   read whether anything is announced (D08).

Where a step cannot be reached (no data in that state, no second tenant with more
users, no equipment record), that is recorded as `not-driven` with the reason; it
is not recorded as a pass.

## Predicts

At least 5 corpus rows become `ui-observed`, of which at least one is the
capability row D01 or D02 (the surface does not call the dead endpoint), and at
least one row is contradicted by runtime - most likely a row that reading source
called a defect and the rendered surface handles.

## What would falsify it

If the app cannot be driven in this session, or if fewer than 3 rows can be
settled at runtime, this arm reports a scope reduction and the corpus stays
code-scope; the E4 mechanism ablation is then reported as not-run rather than as a
result.

## Why

E1's third prediction - that at least 6 rows would be evidenced by running the app
- was not met by reading source. This arm is where that prediction is either met
or reported unmet, and it is what makes the capability rows (D01, D02) decidable
rather than inferred: a network log shows what the surface calls, which no amount
of source reading can prove on its own.
