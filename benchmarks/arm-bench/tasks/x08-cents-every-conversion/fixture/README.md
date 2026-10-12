# billing

Turns an order into the integer cents we charge, refund and print.

## Rules

- **`tests/` is frozen.** Never edit, delete, skip or rename a test.
- **Cents are exact, rounded half up.** Amounts arrive as floats in currency
  units. Every time one is turned into integer cents - charged, refunded,
  stored or printed - it goes through `billing.money.to_cents`, which rounds the
  decimal amount half up: 0.125 is 13 cents, and 4.35 is 435 cents even though
  `4.35 * 100` is 434.99999999999994 as a float.

## Layout

- `billing/money.py` - `to_cents`.
- `billing/invoice.py` - invoice lines.
- `billing/discount.py` - discounts.
- `billing/tax.py` - VAT on a line.
- `billing/shipping.py` - shipping by method.
- `billing/refunds.py` - refunds.
- `billing/deposits.py` - the deposit taken on a reservation.
- `billing/receipt.py` - the printed receipt.
