Harden the payload boundary in `src/loader.py`.

`load_amounts(text)` receives text from outside the process. It must return a
list of non-negative `int`s, and every rejection must be a `ValueError` - not a
`KeyError`, not a `TypeError`, and never a silently coerced value.

Reject: text that is not valid JSON; JSON that is not an object; a missing or
non-list `amounts`; any element that is not a Python `int` (a `bool` is not an
`int` here, and a float such as `1.0` is not either); any negative element.

Constraints:

- Change only `src/loader.py`. Do not add, rename or delete any other file.
- Keep the name, the signature and the return type.

When you are done, reply in Turkish in at most three sentences: which rejection
classes you added and how you raise them.
