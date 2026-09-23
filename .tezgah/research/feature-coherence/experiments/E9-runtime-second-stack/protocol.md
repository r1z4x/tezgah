# E9 - the runtime half on the second stack

## What changes
Nothing in either repository. E5/E6 audited the aibim-app admin users area from
source only, so the layout class (C7) had no row there and no finding could be
`ui-observed`. This experiment tries to start that stack and drive the surface.

## Method
`make admin-dev` (Docker Compose: Postgres + the Rust backend + the Vite frontend),
time-boxed to 20 minutes. If it comes up, sign in with an admin created through the
repo's own `make create-admin`, then read the users surface: the table at 320 / 768 /
1280, the create modal, the detail panel, the search control; record states and
measure the table against its container. If it does not come up, the experiment
reports the failure and its cause, and the class stays unmeasured on this stack.

## Predicts
The stack starts and the surface renders; a C7 row appears (a table whose width
exceeds its container at one or more of the three widths), and at least one row is
`ui-observed` - which would mean the second stack's corpus can carry the classes the
first one did.

## Falsification criterion
Either the stack does not start (reported with the failing command and the error), or
it starts and the table fits at every width measured - which would leave C7 absent on
this stack for a reason other than tooling and would be recorded as such.
