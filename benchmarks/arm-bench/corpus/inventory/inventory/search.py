"""Search helpers."""


def find_by_prefix(items, prefix):
    """Return the names of items whose name starts with prefix."""
    return [item["name"] for item in items if item["name"].startswith(prefix)]
