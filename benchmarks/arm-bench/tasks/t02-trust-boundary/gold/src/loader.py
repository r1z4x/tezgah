"""Harden the payload boundary in `src/loader.py`."""

import json


def load_amounts(text: str) -> list[int]:
    """Return the amounts recorded in a JSON payload, or raise ValueError."""
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ValueError(f"payload is not JSON: {exc}") from exc

    if not isinstance(data, dict):
        raise ValueError("payload must be a JSON object")

    amounts = data.get("amounts")
    if not isinstance(amounts, list):
        raise ValueError("'amounts' must be a list")

    out = []
    for index, value in enumerate(amounts):
        if isinstance(value, bool) or not isinstance(value, int):
            raise ValueError(f"amounts[{index}] must be an int")
        if value < 0:
            raise ValueError(f"amounts[{index}] must not be negative")
        out.append(value)
    return out
