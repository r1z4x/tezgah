import json
import os
from pathlib import Path


class Store:
    """Notes keyed by name, persisted as one JSON object at `path`.

    `readonly=True` means the store must never change (README.md)."""

    def __init__(self, path, readonly=False):
        self.path = Path(path)
        self.readonly = readonly
        self.items = json.loads(self.path.read_text()) if self.path.exists() else {}

    def save(self):
        self.path.write_text(json.dumps(self.items, sort_keys=True))


def open_store(path):
    return Store(path, readonly=os.environ.get("NOTES_READONLY") == "1")
