Product names are typed by hand, so a stored name and the name a caller looks up
often differ in letter case or in surrounding whitespace. Make lookup ignore both,
end to end, using the package's own normaliser `inventory.textnorm.normalize_name`.

Three behaviours have to hold together:

1. `inventory.core.find_item(items, name)` finds a stored item whose name differs
   from `name` only in case or surrounding whitespace, and returns the stored item
   itself - the stored name is never rewritten.
2. `inventory.report.describe(items, name)` goes through that lookup, and both of
   its lines print the name exactly as the caller passed it, never the normalised
   form.
3. `inventory.search.find_by_prefix(items, prefix)` matches prefixes the same way
   (case and surrounding whitespace ignored) and still returns the stored names,
   unchanged. It stays a prefix match: a prefix that only appears inside a name
   does not match.

Change only those three files. `python3 -m unittest discover -s tests` must still
pass.
