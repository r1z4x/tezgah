"""Customer search by name. The contract is crm/SPEC.md."""
import unicodedata


def _norm(text):
    return " ".join(unicodedata.normalize("NFC", text).casefold().split())


def _matches(q, name):
    words = name.split(" ")
    return any(" ".join(words[i:]).startswith(q) for i in range(len(words)))


def search(query, customers):
    """The customers whose name matches `query`, in display order."""
    q = _norm(query) if query is not None else ""
    if not q:
        return []
    found = [c for c in customers if _matches(q, _norm(c["name"]))]
    # sorted() is stable, so customers equal on both keys keep their input order
    return sorted(found, key=lambda c: (_norm(c["name"]).split(" ")[-1], _norm(c["name"])))
