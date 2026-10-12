from . import plugins
from .errors import ReadOnlyError, UnknownCommand


class Shell:
    """Runs one command line against a store.

    `verb rest`: the verb names a `do_<verb>` method (a dash in the verb is an
    underscore in the method name), else a handler in plugins.HANDLERS."""

    def __init__(self, store):
        self.store = store

    def run(self, line):
        verb, _, rest = line.strip().partition(" ")
        method = getattr(self, "do_" + verb.replace("-", "_"), None)
        if method is not None:
            return method(rest)
        handler = plugins.HANDLERS.get(verb)
        if handler is None:
            raise UnknownCommand(verb)
        return handler(self.store, rest)

    def do_add(self, rest):
        if self.store.readonly:
            raise ReadOnlyError("add")
        key, _, text = rest.partition(" ")
        self.store.items[key] = text
        self.store.save()
        return key

    def do_show(self, rest):
        return self.store.items[rest]

    def do_list(self, rest):
        return sorted(self.store.items)

    def do_remove(self, rest):
        if self.store.readonly:
            raise ReadOnlyError("remove")
        del self.store.items[rest]
        self.store.save()

    def do_rename(self, rest):
        if self.store.readonly:
            raise ReadOnlyError("rename")
        old, _, new = rest.partition(" ")
        self.store.items[new] = self.store.items.pop(old)
        self.store.save()
        return new

    def do_clear_all(self, rest):
        if self.store.readonly:
            raise ReadOnlyError("clear-all")
        self.store.items.clear()
        self.store.save()
