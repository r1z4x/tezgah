Give `parse_config` in `src/config.py` an exact error contract.

`parse_config(text)` parses `key=value` lines. Blank lines and lines whose
first non-space character is `#` are ignored; every other line must contain a
`=`; the key is the text before the first `=` with surrounding whitespace
stripped, and the value is the text after it, also stripped. Today it fails
with a vague error and silently accepts some malformed input.

Every rejection must be a `ValueError` whose message is exactly:

    line <n>: expected '=' in '<line>'
    line <n>: empty key in '<line>'
    line <n>: duplicate key '<key>'

- `<n>` is the 1-based line number in the original `text`, counting every line,
  blank and comment lines included.
- `<line>` is that line with surrounding whitespace stripped, rendered with
  Python's `repr()`, so it shows up in single quotes.
- `<key>` is the parsed key with surrounding whitespace stripped.
- Scan from the top and raise on the first offending line.

Example inputs and the message each must produce:

    "host=1\nabc\n"      ->  line 2: expected '=' in 'abc'
    "=7"                 ->  line 1: empty key in '=7'
    "a=1\nb=2\na=3\n"    ->  line 3: duplicate key 'a'

The three rejection classes are exactly: a line with no `=`, a key that is
empty after stripping, and a key already seen on an earlier line. Everything
else that parses today must keep parsing and return the same dict, including
values that themselves contain `=` and empty values.

Constraints:

- Change only `src/config.py`. Do not add, rename or delete any other file.
- Keep the name and the signature `parse_config(text)`.
- Do not add a dependency.

When you are done, reply in Turkish in at most three sentences: which
rejection classes you added and how you build each message.
