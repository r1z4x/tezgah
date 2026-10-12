"""Text output for the command line."""


def listing(notes):
    """One line per note: right-aligned id, created date, title."""
    return "\n".join("%3d %s %s" % (n["id"], n["created"], n["title"]) for n in notes)


def export(notes):
    """Markdown: a header line counting the notes, then one section per note."""
    lines = ["# %d notes" % len(notes)]
    for n in notes:
        lines += ["", "## %s (%s)" % (n["title"], n["created"]), "", n["body"]]
    return "\n".join(lines)
