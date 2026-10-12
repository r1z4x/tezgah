"""Invoice tax in integer cents. The contract is invoice/SPEC.md."""
from decimal import ROUND_HALF_EVEN, Decimal


def _line_tax(amount, rate):
    cents = Decimal(amount) * Decimal(rate)        # amount * rate / 100, in cents
    return int(cents.quantize(Decimal(1), rounding=ROUND_HALF_EVEN))


def invoice_tax(lines):
    """The tax of one invoice, in cents."""
    goods_rates = [Decimal(g["rate"]) for g in lines
                   if g["kind"] == "goods" and g["rate"] is not None]
    shipping_rate = max(goods_rates) if goods_rates else None
    total = 0
    for line in lines:
        rate = shipping_rate if line["kind"] == "shipping" else line["rate"]
        if rate is not None:
            total += _line_tax(line["amount"], rate)
    return total
