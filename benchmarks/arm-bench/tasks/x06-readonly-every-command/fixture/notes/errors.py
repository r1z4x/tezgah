class NotesError(Exception):
    """Base class for every error this package raises."""


class UnknownCommand(NotesError):
    """The shell has no command by that name."""


class ReadOnlyError(NotesError):
    """A command tried to change a store opened read-only."""
