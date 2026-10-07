A reviewer went through this package and filed six findings. Fix all six. Each is
independent, and each is verified by a check you never see.

1. **`inventory/core.py::apply_discount` rounds the wrong way.** The documented
   contract is exact cents rounded half up: a discount landing exactly on half a
   cent goes up. It truncates today.

2. **`inventory/paginate.py::page_bounds` is off by one.** The docstring says the
   pages are 1-based: page 1 must return the first item, so the start of a page
   is `(page - 1) * size`, not `page * size`.

3. **`inventory/cart.py::make_cart` shares one list between every cart it has ever
   made.** Two carts made with no arguments must not share state, and a list
   passed in must be copied, not adopted.

4. **`inventory/validate.py::load_items` does not validate.** Its docstring is the
   contract: every entry must be a dict carrying a **non-empty** string `name`
   and a numeric `price` greater than zero. Anything else raises `InventoryError`
   (the module already imports it). Valid input comes back as cleaned dicts.

5. **`inventory/parsing.py::parse_quantity` raises the wrong error.** It must keep
   parsing `' 12 '` as 12, and must raise `InventoryError` with the message
   `invalid quantity: <text>` - the text as passed - for anything it cannot parse.

6. **`inventory/core.py::find_item` is case- and whitespace-sensitive.** It must
   find a stored item whose name differs from the argument only in letter case or
   in surrounding whitespace, and it must return the stored item unchanged.

Change only these five files: `inventory/core.py`, `inventory/paginate.py`,
`inventory/cart.py`, `inventory/validate.py`, `inventory/parsing.py`.

`python3 -m unittest discover -s tests` must still pass.
