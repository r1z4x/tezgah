"""Size helpers used by the reporting modules."""


def format_bytes(size: int) -> int:
    """Return `size` rounded up to whole kibibytes."""
    return -(-size // 1024)


def format_bits(size: int) -> int:
    """Return `size` rounded up to whole kilobits."""
    return -(-size // 128)
