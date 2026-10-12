"""Shell commands that live outside the Shell class, registered by verb."""
import json
from pathlib import Path


def _tag(store, rest):
    key, _, tag = rest.partition(" ")
    store.items[key] = store.items[key] + " #" + tag
    store.save()
    return store.items[key]


def _count(store, rest):
    return len(store.items)


def _find(store, rest):
    return sorted(k for k, v in store.items.items() if rest in v)


def _import(store, rest):
    incoming = json.loads(Path(rest).read_text())
    store.items.update(incoming)
    store.save()
    return sorted(incoming)


HANDLERS = {
    "tag": _tag,
    "count": _count,
    "find": _find,
    "import": _import,
}
