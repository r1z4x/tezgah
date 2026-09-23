"""Every text-mode `open()` in shipped code names its encoding.

Python's text-mode `open()` falls back to the locale codec - UTF-8 on POSIX,
cp1252 on Windows - so a file with a Turkish letter in it writes on the machine
tezgah is developed on and dies on the machine it is installed on. The
`windows-latest` CI job found the cost of the fallback: the omp install died in
`set_managed_md` with

    UnicodeEncodeError: 'charmap' codec can't encode character '\\u011f' in
    position 477

The rule is one line wide: a text-mode handle carries `encoding="utf-8"`. A
binary handle (`"rb"`, `"wb"`) carries bytes and is left alone, and
`json.load`/`json.dump` inherit the handle's encoding, so the `open()` is the
only place the fix belongs.

The bug this guards is a call that comes back, so the check parses the real
files rather than a copy of their text. A call whose mode is not a literal
(`open(path, mode)`) is a site this scan cannot read: it is reported, the way
the docs citation audit names the `path:line` half it cannot check, rather than
guessed at or dropped. `something.open(...)` is a different method and not this
builtin at all - `OPENER.open` is urllib's request opener, `Image.open` is
PIL's - so it never enters the scan.

Run it as `python3 -m unittest tests/test_encoding.py`. (The suite's own runner,
`python3 -m unittest discover -s tests -p 'test_encoding.py'`, finds it the same
way: `tests/` carries no `__init__.py`, so the path form's `tests.test_encoding`
can resolve to an unrelated installed `tests` package instead.)

Captured on the unfixed tree - `plan/011-packaged-install` at 61c0efc, before
the two encoding fixes landed - that failed with, in part:

    122 text-mode open() call(s) with no encoding=:
      bin/tezgah-setup:265
      hooks/tezgah_research.py:402
      hooks/tezgah_context.py:250
      hooks/tezgah_agents.py:91
      hosts/cursor/hook.py:171

Once the encoding fixes land the same command passes; this test is the guard
that keeps it that way.
"""
import ast
import glob
import os
import unittest

import support

REPO = support.REPO
# The two readings a bare `open()` can get. Both fail the scan: an unencoded
# text handle for what it is, and an unreadable mode for not being judgeable
# here rather than for being wrong.
NO_ENCODING = "no encoding"
CANNOT_JUDGE = "mode is not a literal"


def corpus():
    """The shipped Python: every file tezgah runs or installs.

    `hooks/*.py`, `hosts/**/*.py`, `skills/**/*.py` and `statusline.py` by
    extension; `bin/` whole, because its scripts carry no extension. A `bin/*.py`
    entry is a symlink to its extensionless twin (`bin/tezgah-setup.py` ->
    `bin/tezgah-setup`), so it is skipped as the same bytes twice. The one
    non-Python file there, `bin/tezgah-dsh`, is a `/bin/sh` wrapper and is left
    to the shebang check below.
    """
    paths = [os.path.join(REPO, "statusline.py")]
    for pattern in ("hooks/*.py", "hosts/**/*.py", "skills/**/*.py"):
        paths += glob.glob(os.path.join(REPO, pattern), recursive=True)
    for name in os.listdir(os.path.join(REPO, "bin")):
        path = os.path.join(REPO, "bin", name)
        if name.endswith(".py") and os.path.islink(path):
            continue
        if os.path.isfile(path):
            paths.append(path)
    return sorted(os.path.relpath(path, REPO) for path in paths)


def is_python(path, source):
    """Whether the file is Python: by extension, or by the shebang `bin/`'s
    extensionless scripts carry (`bin/tezgah-dsh` is `/bin/sh`)."""
    if path.endswith(".py"):
        return True
    return "python" in (source.splitlines()[0] if source else "")


def opens(source):
    """Every bare `open()` call that is text-mode, as `(line, problem)`.

    A call that names `encoding=` is done: the handle is told how to encode,
    whatever its mode then does with the value. A literal binary mode (`"rb"`,
    `"wb"`) is bytes, which have no encoding to name. Everything else is either
    a text-mode call with no encoding (`NO_ENCODING`) or a mode this scan cannot
    read (`CANNOT_JUDGE`). A `*`/`**` expansion is the second of those: the mode
    may be in what it unpacks.
    """
    found = []
    for node in ast.walk(ast.parse(source)):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        if not (isinstance(func, ast.Name) and func.id == "open"):
            continue
        mode, encoding, unreadable = None, None, False
        for arg in node.args:
            unreadable = unreadable or isinstance(arg, ast.Starred)
        for kw in node.keywords:
            if kw.arg is None:
                unreadable = True
            elif kw.arg == "encoding":
                encoding = kw.value
            elif kw.arg == "mode":
                mode = kw.value
        if mode is None and len(node.args) > 1:
            mode = node.args[1]
        # `encoding=None` is the locale fallback written out, not an encoding.
        if isinstance(encoding, ast.Constant) and encoding.value is None:
            encoding = None
        if encoding is not None:
            continue
        if unreadable:
            found.append((node.lineno, CANNOT_JUDGE))
        elif mode is None or (isinstance(mode, ast.Constant)
                              and mode.value is None):
            found.append((node.lineno, NO_ENCODING))
        elif isinstance(mode, ast.Constant) and isinstance(mode.value, str):
            if "b" not in mode.value:
                found.append((node.lineno, NO_ENCODING))
        else:
            found.append((node.lineno, CANNOT_JUDGE))
    return found


class Corpus(unittest.TestCase):
    """The real files: no shipped text-mode `open()` is left on the locale."""

    def test_every_text_open_names_its_encoding(self):
        missing, unjudged = [], []
        for path in corpus():
            with open(os.path.join(REPO, path), encoding="utf-8") as fh:
                source = fh.read()
            if not is_python(path, source):
                continue
            for line, problem in opens(source):
                site = "%s:%d" % (path, line)
                (missing if problem == NO_ENCODING else unjudged).append(site)
        self.assertFalse(
            missing, "%d text-mode open() call(s) with no encoding=:\n  %s"
            % (len(missing), "\n  ".join(missing)))
        self.assertFalse(
            unjudged, "%d open() call(s) whose mode this scan cannot read (name "
            "the mode as a literal, or pass encoding=):\n  %s"
            % (len(unjudged), "\n  ".join(unjudged)))


class Scanner(unittest.TestCase):
    """The classifier, on a snippet small enough to read whole: the corpus has
    no unreadable mode yet, and a method named `open` is not this builtin."""

    SNIPPET = (
        'open("a")                      # 1: text default, no encoding\n'
        'open("a", "rb")                # 2: bytes, no encoding needed\n'
        'open("a", encoding="utf-8")    # 3: explicit, whatever the mode\n'
        'open("a", mode)                # 4: a mode the scan cannot read\n'
        "OPENER.open(request)           # 5: urllib, not this builtin\n"
        "Image.open(path)               # 6: PIL, not this builtin\n"
    )

    def test_a_call_is_read_by_its_encoding_then_its_mode(self):
        self.assertEqual(opens(self.SNIPPET),
                         [(1, NO_ENCODING), (4, CANNOT_JUDGE)])


if __name__ == "__main__":
    unittest.main()
