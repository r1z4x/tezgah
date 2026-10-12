# fx

Converts foreign-currency transactions to EUR.

## Rules

- **`tests/` is frozen.** Never edit, delete, skip or rename a test.
- Rates come from `fx/rates.py`; every other module gets its rate from there,
  directly or through a rate source registered in `fx/providers.py`.

## Layout

- `fx/model.py` - a transaction: amount, currency, day.
- `fx/rates.py` - published rates and `fetch_rate`.
- `fx/providers.py` - rate sources by name.
- `fx/convert.py` - one transaction to EUR.
- `fx/report.py` - the EUR total of many transactions.
- `fx/ledger.py` - the ledger entry posted for a transaction.
- `fx/batch.py` - a batch converted through a named source.
- `fx/pricing.py` - the invoice line for a transaction.
