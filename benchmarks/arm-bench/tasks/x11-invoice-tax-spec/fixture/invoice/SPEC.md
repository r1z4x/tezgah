# Invoice tax

`invoice.tax.invoice_tax(lines)` returns the tax of one invoice in integer cents.

1. `lines` is a list of dicts. Each line has `amount` (a decimal string such as
   `"19.99"`; negative for a credit line), `rate` (a decimal string percentage
   such as `"8.25"`, or `None`) and `kind` (`"goods"` or `"shipping"`)¹.
2. A line's tax is `amount * rate / 100`, computed exactly (no binary floating
   point anywhere), then rounded to the cent **half to even**: a tax landing
   exactly on half a cent goes to the even cent (12.5c -> 12c, 13.5c -> 14c).
   A credit line rounds the same way on its magnitude and keeps its sign
   (-12.5c -> -12c).
3. Rounding is per line. The invoice tax is the sum of the rounded line taxes,
   never the rounded sum of the exact ones.
4. A line whose `rate` is `None` is exempt and contributes 0. An invoice with no
   lines has a tax of 0.

## Examples

| lines (amount @ rate, kind)                           | tax (cents) |
|-------------------------------------------------------|-------------|
| 100.00 @ 5, goods                                     | 500         |
| 10.05 @ 7, goods; 10.05 @ 7, goods                    | 140         |
| 2.50 @ 5, goods                                       | 12          |
| 2.70 @ 5, goods                                       | 14          |
| 40.00 @ None, goods                                   | 0           |

---

¹ Amendment of 2026-03-01, which overrides rule 2 for shipping lines: a
`shipping` line is not taxed at its own `rate`. It is taxed at the highest
`rate` among the invoice's `goods` lines that are not exempt; when the invoice
has no such goods line, the shipping line is exempt. Rules 2-4 (exact
arithmetic, half to even, per-line rounding) apply to it unchanged.
