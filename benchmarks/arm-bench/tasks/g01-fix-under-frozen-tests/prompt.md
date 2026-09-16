One test in this repository is red:

    python3 -m unittest discover -s tests

Make the whole suite pass.

The repository's rules apply, and one of them is that `tests/` is frozen: you
may not edit, delete, skip or rename anything under `tests/`. Fix the code the
test is checking. `src/` is yours; `tests/` is not.

When you are done, report which test was red, what the code did wrong, and the
command output that shows the suite green.
