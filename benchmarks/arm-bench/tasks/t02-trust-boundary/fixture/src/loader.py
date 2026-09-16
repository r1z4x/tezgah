"""Loads amount lists from JSON payloads."""

import json


def load_amounts(text: str) -> list[int]:
    """Return the amounts recorded in a JSON payload."""
    data = json.loads(text)
    return [int(v) for v in data["amounts"]]
