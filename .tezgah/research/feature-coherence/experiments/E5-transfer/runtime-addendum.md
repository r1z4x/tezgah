# Runtime addendum to the second corpus

E9 brought the second stack up and drove the surface, so three rows exist that the
source-only corpus could not carry. The frozen corpus
(`E5-transfer/corpus.jsonl`, sha256
`9c72a2d42f2c764d3b7614746f0abb1eabe60ed61e8c5d57c8393f366e505c5a`) is **not edited**:
these rows are an addendum, and both readings are reported wherever they change a
number.

| id | class | statement | evidence |
|---|---|---|---|
| A16 | C7 | The users table overflows its container at 320 CSS px (469 px of table in 55 px with the seeded row; 733 px with a long row) and at 768 when a row is long (230 px over). `.table-container` computes `overflow-x: hidden` and no rule in the stylesheet declares `overflow-x: auto`, and the page itself does not scroll horizontally, so the clipped columns are **unreachable** - not scrollable as they are on the first feature. | `ui-observed`, E9: measured `scrollWidth` vs `clientWidth` of `.table-container` and `table` at 320/768/1440, with the computed `overflow-x` read in the page |
| A17 | C7 | The overflow is content-dependent: at 768 with the single short seeded row the table fits exactly (503 == 503), and with a 72-character name and a 128-character address it overflows by 230 px. A source-only audit cannot state which state fails. | `ui-observed`, E9: the same measurement against a row with long values |
| A18 | C2 | The rendered surface shows the empty state ("No users found") and a server-validation error, and the role/status vocabulary the source predicted is what renders; the row is `ui-observed` rather than `code`. | `ui-observed`, E9: the rendered list after sign-in, the empty state, and the create-form refusal |

## Effect on the second feature's scoring

- **C7 stops being unmeasured on this stack.** The class now has three rows (A16, A17,
  A18 is C2), so the denominator for a *runtime-capable* reading of the second corpus is
  seven defect classes rather than six.
- The arms in E5 and E6 (code-scope) could not reach C7; that is a scope limit of those
  arms, not a property of the artifact. Both readings are reported: 6 classes code-scope,
  7 with the runtime half.
- A18 also upgrades one C2 statement from `code` to `ui-observed`, which is the evidence
  class the rubric prefers and the one the earlier arms had to declare unavailable.
