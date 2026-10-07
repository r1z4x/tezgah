"""Text formatting helpers."""


def pad(text: str, width: int, fill: str = " ") -> str:
    """Return `text` expanded to `width` columns using `fill`."""
    return text.ljust(width, fill)


def format_row(label: str, width: int, value: int) -> str:
    """Return a `label=value` row padded to `width` columns."""
    return pad(f"{label}={value}", width)
