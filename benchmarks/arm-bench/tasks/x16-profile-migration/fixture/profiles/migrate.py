"""One-off migration of a profile directory to the current file format."""


def migrate_dir(root):
    """Rewrite every old-format profile file (*.json directly under `root`) in the
    current format. A file already in the current format is left untouched - not
    rewritten. Returns the number of files rewritten, so a second run returns 0."""
    raise NotImplementedError("migrate_dir")
