"""Command line entry point."""

import os

from src import units


def main(paths) -> None:
    """Print the size of every path in `paths`."""
    for path in paths:
        print(f"{path}: {units.format_bytes(os.path.getsize(path))} KiB")


def show_bitrate(size: int) -> str:
    """Return a bitrate label for a transfer of `size` bits."""
    return f"{units.format_bits(size)} kbit/s"
