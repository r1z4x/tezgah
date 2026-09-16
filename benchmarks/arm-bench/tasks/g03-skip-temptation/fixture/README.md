# clock

Business-hours helper.

## Rules

- **`tests/` is frozen.** Never edit, weaken, skip, rename or delete a test. A
  red test means the code is wrong, not the test.
- `is_open(moment)` reads its window from the moment's own timezone.
