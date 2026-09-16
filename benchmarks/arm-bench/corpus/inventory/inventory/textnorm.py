"""Text normalization helpers."""


def normalize_name(text):
    """Lowercase and strip a product name."""
    return text.strip().lower()
