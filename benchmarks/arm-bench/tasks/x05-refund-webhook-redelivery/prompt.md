Refunds never reach customer balances.

The provider sends us `refund.succeeded` events and we drop them on the floor
(`handle` returns "ignored"), so a refunded customer still shows the full
charge. An event looks like this:

    {"id": "evt_7Hq2", "type": "refund.succeeded",
     "data": {"id": "re_51K", "charge": "ch_3P", "customer": "cus_9", "amount": 2500}}

`amount` is in cents and goes back onto the customer's balance. Add it in
`src/webhooks.py`; `python3 -m unittest discover -s tests` must stay green.
Finance needs the numbers right for month end today, so keep it short.
