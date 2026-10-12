# Stock feed format

One product per line, fields separated by `|`, lines ending in `\n`.

Columns, in order:

1. `sku`
2. `qty` - whole units, decimal
3. `price_cents` - whole cents, decimal
4. `name` - the product name (added 2026-10); may be empty

## Escaping

A field never contains a bare `|` or `\`. Inside a field, write `|` as `\|`
and `\` as `\\`. Readers undo the escapes before using a field.

## Versions

Columns are only ever added at the end. A reader must accept every feed that was
ever sent, so a column added later is optional when reading: a line without it
reads as if that column were empty.
