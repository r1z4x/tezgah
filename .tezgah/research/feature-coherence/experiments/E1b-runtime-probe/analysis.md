# E1b - runtime probe: result

## What ran

The live stack booted earlier in this session (admin `next dev` on
`http://127.0.0.1:3000`, API on `:3001`, seeded `servistek` database) was driven
through a real browser context authenticated as `platform@servistek.test`. Nine
rows in `results.jsonl`: three that settle a corpus row's runtime half (R01, R02,
R03), one that confirms the corpus gate row (R06), two corpus gaps the reading
missed (R04, R05), and three `not-driven` rows with their reason (N01, N02, N03).

Rows: 6 observed, 3 not driven. Scope `real`.

## Outcome against the prediction

| Predicted | Observed | Verdict |
|---|---|---|
| at least 5 corpus rows become `ui-observed` | 3 (D03, D04, D06) plus D09's gate row | **not met** |
| at least one settled row is the capability row D01 or D02 | 0 - N01 explains why | **falsified** |
| at least one corpus row is contradicted by runtime | 0 | not met |

Both failures have the same cause, and it is the finding of this experiment: **the
browser's request log cannot see a server-rendered surface's capability use.** The
admin calls the API from the Next server, so `/users` produces exactly one entry in
the page's own network log, and which API paths the surface uses is invisible from
outside. A capability matrix therefore cannot be filled from the UI side alone: it
needs the API's access log, a proxy in front of it, or the code. That is worth
knowing before anyone builds a probe that assumes the network tab answers it.

## What the runtime pass added that reading did not

- **R04: the table overflows at every measured width**, 1140 px of table inside
  242 / 686 / 924 px of container at 320 / 768 / 1280. Reading the source shows a
  wrapper with `tabIndex` and `role=region`; only measurement shows that no
  breakpoint ever fits it. This is exactly the class a source-only pass reports as
  "has a scroll container" and stops.
- **R05: the wizard's URL state disagrees with the rendered state** for a visitor
  with no application (`step=2` lands on `step=3`, which renders the start card).
  The code that produces it reads as a gate; the rendered effect is a URL naming a
  step that is not shown.
- **R03's second half**: the empty state exists and is correct, and the page holds
  zero live regions. A state that exists (empty) and a state that does not
  (announcement) are different findings, and only the second is the defect.
- **N02's side finding**: a shared component can be unreachable for an entire
  panel configuration - the picker lives behind a route the platform organization
  does not have. A capability matrix built from the component's own file would
  never say so.

## Limits

- One organization, one user, one credential: the states that need more data are
  `not-driven`, and N03 names exactly what seeding would unblock.
- The session's access cookie expired mid-run; the 1280 measurement was retaken
  after re-authenticating, and the first, unauthenticated reading was discarded
  rather than reported.
- Driving the app writes nothing to it: every step here is a read (navigate, open
  a dialog, filter, measure). Nothing was created, updated or deleted, so no
  fixture or production data was touched.
