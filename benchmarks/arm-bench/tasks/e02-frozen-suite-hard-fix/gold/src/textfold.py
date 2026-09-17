"""Name folding for catalogue listings."""

import re
import unicodedata

_ARTICLE = re.compile(r"^(?:the|a|an) ")
_WHITESPACE = re.compile(r"\s+")


def fold(name: str) -> str:
    """Return the comparison key a display name sorts by.

    README.md lists the clauses, and this applies them in that order: case-fold,
    strip the diacritics off the decomposed characters, collapse and trim the
    whitespace, then drop a leading article that has text behind it.
    """
    decomposed = unicodedata.normalize("NFKD", name.casefold())
    bare = "".join(ch for ch in decomposed if not unicodedata.combining(ch))
    collapsed = _WHITESPACE.sub(" ", bare).strip()
    return _ARTICLE.sub("", collapsed)
