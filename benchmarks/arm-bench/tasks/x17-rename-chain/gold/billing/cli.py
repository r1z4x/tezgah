"""Command line: python3 -m billing.cli <command> <qty>x<unit_cents> ...

Each command names the function in billing.totals that answers it."""
import sys

from billing import totals

COMMANDS = {"net": "subtotal", "count": "line_count"}


def parse(args):
    items = []
    for arg in args:
        qty, unit = arg.split("x")
        items.append({"qty": int(qty), "unit_cents": int(unit)})
    return items


def run(command, items):
    return getattr(totals, COMMANDS[command])(items)


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    if not argv or argv[0] not in COMMANDS:
        print("usage: billing.cli {%s} <qty>x<unit_cents> ..." % ",".join(sorted(COMMANDS)))
        return 2
    print(run(argv[0], parse(argv[1:])))
    return 0


if __name__ == "__main__":
    sys.exit(main())
