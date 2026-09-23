# E4b - the static capability probe: result

## What ran

One pipeline over two artifacts both sides already ship: the API's committed
contract (`docs/openapi.json`, 337 paths) and the admin app's literal API call
sites. Output, verbatim:

    contract endpoints under /users:
       GET /users            GET /users/roles      GET /users/{id}
       PATCH /users/{id}     POST /users/invite    POST /users/{id}/deactivate
    surface call sites under /users:
       GET /users            GET /users/roles      PATCH /users/${id}
       POST /users/invite
    contract-only (a layer yes, surface no):
       GET /users/{id}
       POST /users/{id}/deactivate
    surface-only (surface yes, a layer no):
       (none)

## Outcome against the prediction

Both predictions hit: at least one contract-only endpoint (two), and a runtime of
3.09 s with no credential, no running app and no browser.

## What it settles

- **D01 and D02 are mechanical, not editorial.** E1 found both by reading call
  sites; E1b proved the browser's request log cannot see them because the admin
  calls the API from the Next server. The contract-vs-call-site set difference
  reproduces both rows in one command, and a reviewer can re-run it.
- **The pair is the rejectable artifact.** The proposal section's load-bearing rule
  says a capability claim needs an artifact something other than its author can
  reject. Here the contract document is that artifact: the diff is checkable by
  anyone, unlike a sentence asserting "nothing calls this".
- **The probe is a probe, not a substitute for one on the other side.** It answers
  the "layer yes, surface no" column of the capability matrix. It cannot answer
  "surface yes, a layer no" (that needs the runtime denial, i.e. an API call with a
  credential that must fail), which is why the matrix still names both.

## Limits

- The call-site extraction is textual: a path built by concatenation the pattern
  misses would appear as a false "contract-only" row. The probe therefore reports
  the strings it compared, so a reader can see what it covered.
- The contract can itself be stale - a declared endpoint that the server no longer
  serves would read as a live capability. `contract-only` means "declared and
  unreached", not "working"; the verification column of the proposal is what closes
  that gap.

## A note on the protocol text

The protocol file is byte-identical to the version committed before the probe ran.
Two wording edits were made while the results were still uncommitted, and both were
reverted, because a protocol edited after its run is not a prediction. The falsifier
the committed text carries, verbatim: *"The probe finding no difference at all where
E1's reading found both rows: the static comparison is not sufficient for the
capability matrix, and the matrix's \"layer yes, surface no\" column must name a
server-side probe (a running API with a credential, or the server's access log)
instead."* `tezgah-research check` reads that file as stating no falsification
criterion: its denial pattern matches a negation within four words of the word
`falsif`, and the committed sentence "needs no credential, no running app and no
browser" sits close enough to the heading to swallow it. The criterion is there; the
checker's proximity window is what cannot see it, which is the class of false
negative the research layer's own audit already recorded.
