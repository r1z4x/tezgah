"""Parses tiny `key=value` config text."""


def parse_config(text: str) -> dict[str, str]:
    """Return the key/value pairs recorded in `text`."""
    out = {}
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        key, value = line.split("=", 1)
        out[key.strip()] = value.strip()
    return out
