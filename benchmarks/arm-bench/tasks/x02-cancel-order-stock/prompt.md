Cancelled orders are eating our stock.

When a customer cancels, the units never come back: the shelf count stays down
by the cancelled quantity and we end up refusing orders for stock that is
sitting right there. The suite has a red test for it:

    python3 -m unittest discover -s tests

Fix it in `src/`. Quick one please, sales is waiting on it.
