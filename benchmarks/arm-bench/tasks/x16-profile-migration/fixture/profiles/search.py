"""Filters over a list of in-memory profiles."""


def by_tag(profiles, tag):
    """Profiles carrying `tag` (exact match), in input order."""
    return [p for p in profiles if tag in p["tags"].split(",")]


def by_domain(profiles, domain):
    """Profiles whose address is at `domain` (case-insensitive), in input order."""
    return [p for p in profiles if p["mail"].lower().endswith("@" + domain.lower())]
