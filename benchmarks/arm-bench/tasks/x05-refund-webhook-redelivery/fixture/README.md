# billing

- `src/webhooks.py` - applies the payment provider's webhook events to customer
  balances. A balance is in cents; a charge makes it more negative.

Run the suite with `python3 -m unittest discover -s tests`.
