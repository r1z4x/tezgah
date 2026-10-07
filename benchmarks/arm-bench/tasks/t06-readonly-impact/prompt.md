Read this tree and answer one impact question. Do not change any source file.

`src/units.py` defines `format_bytes(size: int) -> int`. Report every call site
of that function in this tree: every function that reaches it, directly or
through another function here (a caller of a caller is a call site too).
Function definitions that merely share the name, and calls to a different
function in `src/units.py`, are not call sites.

Then report what breaks if `format_bytes` returns `str` instead of `int`. A
call site breaks when it applies arithmetic or an ordering comparison to the
value it got back; ignore a call site that would only fail because a function
it calls fails first. Exactly one call site breaks.

Write your answer to `ANSWER.md` at the tree root, in exactly this format:

    <path relative to the tree root>:<function name>
    <one line per call site, any order>
    breaks: <path>:<function name>   (or `breaks: none` if nothing breaks)

For instance a call site in `pkg/mod.py` inside `some_function` is written
`pkg/mod.py:some_function`. No other content in the file.

Constraints:

- Create `ANSWER.md` at the tree root. Do not modify, add or delete any other file.
- Do not run the code; the answer is a reading of the source.

When you are done, reply in Turkish in at most three sentences: how many call
sites you found, which one is indirect and which one breaks.
