#!/usr/bin/env python3
"""tezgah-skill [-k N] [--json] [--root DIR] QUERY... - find the skill section
that answers a topic.

The roster a session meets is hundreds of one-line names, so the skill that
holds the answer is a guess unless something searches the bodies. This is that
search: every installed skill root on the machine (the plugin's own, omp's user
and custom-directories corpora, Claude/Codex/Agents/opencode), indexed by
heading, ranked by the same BM25 the per-turn lessons block uses. Each hit is a
section, not a file:

  skill://attack-jwt:26-122  /abs/SKILL.md  JWT Token Attack

The `skill://<name>:<start>-<end>` address is what omp's read tool resolves
(line selectors included); the absolute path is for the hosts that have no
skill:// transport, and is also the tiebreaker where two roots hold different
skills under one name (the search reports the first root's copy, omp's own
precedence order - it does not resolve the collision for you).

--root DIR adds a directory to the discovered roots (a project's vendored
skills); --json prints the machine shape. Exit 0 hits, 1 none, 2 usage.
"""
import argparse
import json
import os
import sys

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(HERE, "hooks"))
import tezgah_skill_pick as sp  # noqa: E402


def main(argv=None):
    parser = argparse.ArgumentParser(
        prog="tezgah-skill", description=__doc__.splitlines()[0])
    parser.add_argument("query", nargs="+", help="the topic to search for")
    parser.add_argument("-k", type=int, default=5, metavar="N",
                        help="sections to print (default 5)")
    parser.add_argument("--root", action="append", default=[], metavar="DIR",
                        help="an extra skills directory to index (repeatable)")
    parser.add_argument("--json", action="store_true",
                        help="print [{skill, uri, path, title, start, end}]")
    args = parser.parse_args(argv)
    query = " ".join(args.query)
    hits = sp.search(query, k=max(1, args.k),
                     roots=(sp.skill_roots(args.root) if args.root else None))
    if args.json:
        print(json.dumps([{"skill": h[0],
                           "uri": "skill://%s:%d-%d" % (h[0], h[3], h[4]),
                           "path": h[1], "title": h[2],
                           "start": h[3], "end": h[4]} for h in hits], indent=1))
    else:
        for skill, path, title, start, end in hits:
            print("skill://%s:%d-%d\t%s\t%s" % (skill, start, end, path, title))
    return 0 if hits else 1


if __name__ == "__main__":
    sys.exit(main())
