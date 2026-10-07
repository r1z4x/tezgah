"""Row formatting helpers."""


def label(text):
    """Wrap text in square brackets."""
    return f"[{text}]"


def labeled_row(name, amount):
    """Return a labelled row for a name and amount."""
    return f"{label(name)} {amount:.2f}"
