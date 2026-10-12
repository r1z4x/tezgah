"""Profile files on disk: one JSON object per file.

The in-memory profile is a dict {"name": str, "email": str, "tags": list[str]}.
Files are written in format version 2:
    {"version": 2, "name": str, "email": str, "tags": [str, ...]}
Version 1 files (no "version" key, or "version": 1) carry "mail" and tags as a
comma-separated string ("" for no tags); load() still reads them.
"""
import json
from pathlib import Path

from profiles.errors import ProfileError

VERSION = 2


def save(profile, path):
    """Write `profile` to `path` in format version 2."""
    data = {"version": VERSION, "name": profile["name"], "email": profile["email"],
            "tags": list(profile["tags"])}
    Path(path).write_text(json.dumps(data, sort_keys=True) + "\n", encoding="utf-8")


def read_raw(path):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise ProfileError("cannot read %s: %s" % (path, exc)) from exc


def upgrade(data):
    """The in-memory profile for a raw file object of any supported version."""
    version = data.get("version", 1)
    if version == 1:
        tags = data["tags"]
        return {"name": data["name"], "email": data["mail"],
                "tags": tags.split(",") if tags else []}
    if version == VERSION:
        return {"name": data["name"], "email": data["email"], "tags": list(data["tags"])}
    raise ProfileError("unsupported profile version: %r" % (version,))


def load(path):
    """Read the profile stored at `path`, version 1 or 2.

    A missing or unreadable file, or an unknown version, raises ProfileError."""
    return upgrade(read_raw(path))
