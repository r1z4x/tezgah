# stock

Warehouse stock helpers. Counts are whole units.

## Rules

- `available(item)` is what is left to reserve: `stock` minus what is already
  `reserved`.
- `reserve(item, count)` refuses rather than clamps. Asking for more units than
  are available raises `ValueError` and leaves `item` unchanged; the call never
  reserves a smaller number than it was asked for.
- A red test means the code is wrong, not the test.
