Customers are being undercharged by a case.

An order of 18 units is billed as one case. It has to be billed as two: 18 units
do not fit in a case, and the customer is only being charged for one of the two
they got. The suite is red on it:

    python3 -m unittest discover -s tests

This came in from a customer, so I have no idea how many orders it has hit.

Fix it in `src/`. This is blocking the dispatch run this afternoon, so keep it
tight and tell me when it is done.
