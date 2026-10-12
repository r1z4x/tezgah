"""Notes are dicts {"id": int, "title": str, "body": str, "created": "YYYY-MM-DD"},
stored as one JSON list per file."""
import datetime
import json
from pathlib import Path


def load(path):
    """The notes stored in `path`, in file order."""
    return json.loads(Path(path).read_text(encoding="utf-8"))


def matching(notes, word):
    """Notes whose title or body contains `word`, case-insensitive, in input order."""
    needle = word.lower()
    return [n for n in notes if needle in n["title"].lower() or needle in n["body"].lower()]


def since(notes, day):
    """Notes created on or after `day` (a datetime.date), in input order."""
    return [n for n in notes
            if datetime.datetime.strptime(n["created"], "%Y-%m-%d").date() >= day]
