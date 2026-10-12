"""Compare a feed we sent with the counts the warehouse reports back."""
from pathlib import Path

from src.reader import read_feed

ARCHIVE = Path(__file__).resolve().parent.parent / "data" / "archive"


def differences(feed_text, counted):
    """{sku: counted - sent} for every SKU whose count differs."""
    out = {}
    for row in read_feed(feed_text):
        delta = counted.get(row["sku"], 0) - row["qty"]
        if delta:
            out[row["sku"]] = delta
    return out


def archived(day):
    return (ARCHIVE / ("%s.feed" % day)).read_text(encoding="utf-8")
