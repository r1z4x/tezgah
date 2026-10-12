"""Profile files on disk: one JSON object per file.

The in-memory profile is a dict {"name": str, "mail": str, "tags": str}, where
tags is a comma-separated string ("" for no tags).
"""
import json
from pathlib import Path

from profiles.errors import ProfileError


def save(profile, path):
    """Write `profile` to `path` as JSON."""
    data = {"name": profile["name"], "mail": profile["mail"], "tags": profile["tags"]}
    Path(path).write_text(json.dumps(data, sort_keys=True) + "\n", encoding="utf-8")


def load(path):
    """Read the profile stored at `path`.

    A missing or unreadable file raises ProfileError."""
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise ProfileError("cannot read %s: %s" % (path, exc)) from exc
    return {"name": data["name"], "mail": data["mail"], "tags": data["tags"]}
