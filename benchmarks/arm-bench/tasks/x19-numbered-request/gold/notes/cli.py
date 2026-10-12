"""Command line: python3 -m notes.cli FILE {list,search WORD,export} [--since YYYY-MM-DD]"""
import argparse
import datetime
import sys

from notes import render, store


def day(text):
    try:
        return datetime.datetime.strptime(text, "%Y-%m-%d").date()
    except ValueError:
        raise argparse.ArgumentTypeError("not a YYYY-MM-DD date: %r" % (text,)) from None


def build_parser():
    parser = argparse.ArgumentParser(prog="notes")
    parser.add_argument("file")
    sub = parser.add_subparsers(dest="command", required=True)
    commands = [sub.add_parser("list", help="list every note")]
    search = sub.add_parser("search", help="list the notes containing WORD")
    search.add_argument("word")
    commands.append(search)
    commands.append(sub.add_parser("export", help="print the notes as Markdown"))
    for command in commands:
        command.add_argument("--since", type=day, help="only notes created on or after this day")
    return parser


def main(argv=None):
    args = build_parser().parse_args(argv)
    notes = store.load(args.file)
    if args.since is not None:
        notes = store.since(notes, args.since)
    if args.command == "list":
        print(render.listing(notes))
    elif args.command == "search":
        print(render.listing(store.matching(notes, args.word)))
    else:
        print(render.export(notes))
    return 0


if __name__ == "__main__":
    sys.exit(main())
