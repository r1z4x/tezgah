# E9 - the runtime half on the second stack: result

## What ran

One pass, with Docker allowed: `COMPOSE_PROJECT_NAME=fce9 make admin-dev` on a fresh
project scope (no shared container, volume or network touched; the repository's own
target used unchanged).

## Outcome against the prediction

The prediction had three clauses. **The first is falsified, the other two hold after a
bridge:**

| Clause | Result |
|---|---|
| the stack starts as issued | **falsified** - `postgres` and `admin-backend` come up healthy (backend healthcheck passes at 8081, boot wall clock 163 s), while `admin-frontend` crash-loops nine times with `nginx: [emerg] host not found in upstream "aibim" in /etc/nginx/conf.d/default.conf:46` |
| the surface renders | holds after a docker-only bridge: sign-in through the real form, `GET /auth/me` 200, `GET /api/v1/admin/users?limit=200` 200, `http://localhost:3001/users` rendered with real data |
| a C7 row appears and at least one row is `ui-observed` | holds - a C7 row at 320 and 768, and **13 `ui-observed` rows** |

## The finding inside the failure

`admin/frontend/nginx.conf:44-46` proxies `/ws/` to `http://aibim:8080`, a service that
`make admin-dev` (`Makefile:582-583`) does not start: the target brings up
`admin-backend`, `admin-frontend` and `postgres` only. nginx resolves upstreams at
config load, so the frontend never starts - which means **the repository's own dev
entry point cannot reach its own users surface**, and that is why every earlier arm
audited this stack from source. It is the same defect class the line is about (a layer
referenced by another that the composition does not provide), found here in the tooling
rather than in the product.

## What the runtime added to the second corpus

| Row | Class | What was measured |
|---|---|---|
| A16 | C7 | the table overflows its container at 320 (469 vs 55 px with short content, 733 vs 55 with a long row) and at 768 when a row is long (230 px over); `.table-container` computes `overflow-x: hidden` and no rule declares `overflow-x: auto`, so **the clipped columns are unreachable**, not scrollable |
| A17 | C7 | at 768 with short content the table fits exactly (503 == 503), so the defect is content-dependent - a state the source-only corpus could not have stated |
| A18 | C2 | the rendered surface shows the empty state ("No users found") and one server-validation error; the array/state vocabulary the source predicted is visible, and the row is `ui-observed` rather than `code` |

Recorded as `runtime-addendum.md` beside the frozen corpus: the corpus file itself is
not edited, and both readings (with and without these rows) are reported.

## Limits

- The app backend (`aibim`) never ran, so anything behind `/ws/` or the app API is
  unmeasured, and the SPA was served from the image's prebuilt `dist` - no Vite
  dev-server behaviour.
- Only default, empty and one validation-error state were reached; no axe sweep, no
  hover/focus/disabled/loading/permission-denied read, no other page of the shell.
- One rater, one pass; the measurements are geometry and rendered text, not an
  interaction model.
