"""Command line: python3 -m notes.cli FILE {list,search WORD,export}"""
import argparse
import sys

from notes import render, store


def build_parser():
    parser = argparse.ArgumentParser(prog="notes")
    parser.add_argument("file")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("list", help="list every note")
    search = sub.add_parser("search", help="list the notes containing WORD")
    search.add_argument("word")
    sub.add_parser("export", help="print the notes as Markdown")
    return parser


def main(argv=None):
    args = build_parser().parse_args(argv)
    notes = store.load(args.file)
    if args.command == "list":
        print(render.listing(notes))
    elif args.command == "search":
        print(render.listing(store.matching(notes, args.word)))
    else:
        print(render.export(notes))
    return 0


if __name__ == "__main__":
    sys.exit(main())
