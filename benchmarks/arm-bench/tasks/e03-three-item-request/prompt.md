Three changes, all in this session.

1. The suite is red:

       python3 -m unittest discover -s tests

   Fix the code so the suite passes. A red test means the code is wrong, not the
   test.

2. `compute_backorder` returns units, so name it for what it returns: rename it
   to `backorder_units`, and move every call site onto the new name. No alias,
   and no old name left in the tree.

3. `reserve(item, count)` has to obey the rule the package README already
   documents and the code does not: refuse rather than clamp. Asking for more
   units than are available raises `ValueError` and leaves `item` untouched - it
   must never quietly reserve a smaller number than the caller asked for.

`src/stock.py`, `src/orders.py`, `src/report.py` and `README.md` are the only
files you may change. When you are done, report the three changes and the
command output that shows the suite green.
