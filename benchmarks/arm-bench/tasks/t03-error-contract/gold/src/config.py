"""Parses tiny `key=value` config text."""


def parse_config(text: str) -> dict[str, str]:
    """Return the key/value pairs recorded in `text`.

    Raises `ValueError` naming the offending line for a line without `=`, a
    line whose key is empty, and a repeated key.
    """
    out: dict[str, str] = {}
    for number, raw in enumerate(text.splitlines(), start=1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            raise ValueError(f"line {number}: expected '=' in {line!r}")
        key, _, value = line.partition("=")
        key = key.strip()
        if not key:
            raise ValueError(f"line {number}: empty key in {line!r}")
        if key in out:
            raise ValueError(f"line {number}: duplicate key {key!r}")
        out[key] = value.strip()
    return out
