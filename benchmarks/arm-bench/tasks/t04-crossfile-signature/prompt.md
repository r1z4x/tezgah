Rename the second parameter of `format_row` in `src/formatting.py`.

`format_row(label, width, value)` is called from `src/orders.py` and
`src/invoices.py`, and each caller has its own `width` parameter that it
forwards by keyword. The name `width` is wrong for all of them: rename it to
`columns` in the helper's signature, in both callers' signatures, and in every
call site, so the whole chain uses one consistent name.

After the rename `format_row(label=..., columns=..., value=...)`,
`render_order_table(rows, columns=12)` and
`render_invoice_table(rows, columns=16)` must all work, and the old keyword
name `width` must no longer be accepted anywhere in that chain.

Behaviour must not change. `pad` is out of scope: its parameter is called
`width` and `pad(text, width=...)` must keep working exactly as it does now.

Constraints:

- Change only `src/formatting.py`, `src/orders.py` and `src/invoices.py`.
  Do not add, rename or delete any other file.
- Keep the function names, the parameter order and every default value.
- Do not add a dependency.

When you are done, reply in Turkish in at most three sentences: which files you
edited and how you avoided renaming unrelated parameters.
