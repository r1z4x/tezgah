"""Search helpers."""

from inventory.textnorm import normalize_name


def find_by_prefix(items, prefix):
    """Return the names of items whose name starts with prefix.

    The comparison ignores case and surrounding whitespace, and it is still a
    prefix test: a prefix that only occurs inside a name does not match. The
    names returned are the stored ones.
    """
    wanted = normalize_name(prefix)
    return [item["name"] for item in items
            if normalize_name(item["name"]).startswith(wanted)]
