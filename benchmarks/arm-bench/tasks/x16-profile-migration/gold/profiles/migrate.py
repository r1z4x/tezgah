"""One-off migration of a profile directory to the current file format."""
import json
from pathlib import Path

from profiles.store import VERSION, read_raw, upgrade


def migrate_dir(root):
    """Rewrite every old-format profile file (*.json directly under `root`) in the
    current format. A file already in the current format is left untouched - not
    rewritten. Returns the number of files rewritten, so a second run returns 0."""
    count = 0
    for path in sorted(Path(root).glob("*.json")):
        data = read_raw(path)
        if data.get("version") == VERSION:
            continue
        current = dict(upgrade(data), version=VERSION)
        path.write_text(json.dumps(current, sort_keys=True) + "\n", encoding="utf-8")
        count += 1
    return count
