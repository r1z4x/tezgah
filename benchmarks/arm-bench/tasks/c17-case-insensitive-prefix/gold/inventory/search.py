"""Search helpers."""


def find_by_prefix(items, prefix):
    """Return the names of items whose name starts with prefix, ignoring case."""
    needle = prefix.casefold()
    return [item["name"] for item in items if item["name"].casefold().startswith(needle)]
