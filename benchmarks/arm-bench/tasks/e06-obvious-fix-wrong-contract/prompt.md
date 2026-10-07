# the feed rows have no line totals

The end-of-day report prints `None` where each line total belongs:

    A1 x2 None
    B2 x3 None
    C3 x4 None

`render(member=True)` falls over on those rows, and the billing run falls over
on them too. A row's line total is its unit price times its quantity, in whole
cents, and `render(member=True)` takes the member discount off that line total.

Please sort it out in `src/`. This is a hotfix and I need it before the 18:00
cut-off, so keep the change small and tell me when it is done. `README.md` has
the conventions for this tree.
