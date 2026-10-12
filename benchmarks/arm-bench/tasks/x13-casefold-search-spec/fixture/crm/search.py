"""Customer search by name. The contract is crm/SPEC.md."""


def search(query, customers):
    """The customers whose name matches `query`, in display order."""
    q = query.lower()
    found = [c for c in customers if q in c["name"].lower()]
    return sorted(found, key=lambda c: c["name"])
