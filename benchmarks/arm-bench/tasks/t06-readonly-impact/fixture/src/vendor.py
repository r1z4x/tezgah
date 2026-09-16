"""Vendored size formatting, kept as it was published upstream."""


def format_bytes(size: int) -> int:
    """Return `size` in whole kibibytes, as the upstream library defines it."""
    return (size + 1023) // 1024
