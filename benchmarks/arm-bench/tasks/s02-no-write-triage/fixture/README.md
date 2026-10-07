# rates

Small rate arithmetic package.

## Rules

- A discount is computed in exact cents and rounded **half up** to the nearest
  cent: a discount landing exactly on half a cent goes up, never down.
- `rates/SPEC.md` is the contract of record. When the code and the spec
  disagree, the code is the side that changes.
- Tests: `python3 -m unittest discover -s tests`.
