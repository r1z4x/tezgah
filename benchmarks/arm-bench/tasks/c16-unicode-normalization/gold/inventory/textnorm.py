"""Text normalization helpers."""

import re
import unicodedata

_WHITESPACE_RUN = re.compile(r"\s+")


def normalize_name(text):
    """NFC-normalize, collapse whitespace and lowercase a product name."""
    composed = unicodedata.normalize("NFC", text)
    return _WHITESPACE_RUN.sub(" ", composed).strip().lower()
