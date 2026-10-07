"""The file records, as the service keeps them.

`state` is `active`, `removed` or `failed`. `blob` is the storage key the bytes
live under, and a record can outlive the bytes it names: `BLOBS` is what storage
actually holds.
"""

RECORDS = (
    {"id": "f1", "owner": "u1", "name": "a.txt", "state": "active",
     "blob": "blobs/f1", "uploaded_at": 100},
    {"id": "f2", "owner": "u1", "name": "b.txt", "state": "removed",
     "blob": None, "uploaded_at": 200},
    {"id": "f3", "owner": "u1", "name": "c.txt", "state": "active",
     "blob": "blobs/gone", "uploaded_at": 300},
    {"id": "f4", "owner": "u2", "name": "d.txt", "state": "active",
     "blob": "blobs/f4", "uploaded_at": 400},
)

# What storage holds right now. A record whose key is absent here is a record
# with no bytes behind it.
BLOBS = {"blobs/f1", "blobs/f4"}


def records_for(owner):
    """Every record this owner has, newest first."""
    rows = [dict(r) for r in RECORDS if r["owner"] == owner]
    rows.sort(key=lambda r: r["uploaded_at"], reverse=True)
    return rows


def find(file_id):
    """One record by id, or None."""
    for row in RECORDS:
        if row["id"] == file_id:
            return dict(row)
    return None


def blob_exists(key):
    """Whether the bytes are still in storage under this key."""
    return bool(key) and key in BLOBS
