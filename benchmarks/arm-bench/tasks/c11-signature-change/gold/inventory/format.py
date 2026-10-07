"""Row formatting helpers."""


def tag(text, upper=False):
    """Wrap text in square brackets, uppercased when upper is true."""
    if upper:
        text = text.upper()
    return f"[{text}]"


def labeled_row(name, amount):
    """Return a labelled row for a name and amount."""
    return f"{tag(name)} {amount:.2f}"
