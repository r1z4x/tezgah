"""Reads settings through `parse_config`."""

from src.config import parse_config


def load_settings(text: str) -> dict[str, str]:
    """Return the settings in `text`, with `name` defaulted."""
    settings = parse_config(text)
    settings.setdefault("name", "unnamed")
    return settings
