#!/usr/bin/env python3
"""Grade `standings` against league/SPEC.md, one clause per argument.

  ranks      rule 5: a three-way and a two-way shared rank, each followed by the
             skipped place.
  names      rule 4's last key: fully level teams listed by casefolded name
             ("alpha", "Bravo", "charlie"), which a raw sort puts "Bravo" first.
  unplayed   rule 1: a None score counts for nothing but lists its teams with 0
             played; an empty list gives [].
  h2h        the 2026 amendment at the end of SPEC.md: teams level on points are
             separated by the points they took off each other before goal
             difference - a pair, and a group of three whose head-to-head order
             is the reverse of their goal-difference order.
"""
import sys

sys.path.insert(0, ".")

CASES = {
    "ranks": [
        ([("A", "B", 1, 1), ("B", "C", 1, 1), ("C", "A", 1, 1), ("D", "E", 0, 0)],
         [(1, "A", 2, 2, 0, 2), (1, "B", 2, 2, 0, 2), (1, "C", 2, 2, 0, 2),
          (4, "D", 1, 1, 0, 0), (4, "E", 1, 1, 0, 0)]),
    ],
    "names": [
        ([("alpha", "Bravo", 0, 0), ("Bravo", "charlie", 0, 0), ("charlie", "alpha", 0, 0)],
         [(1, "alpha", 2, 2, 0, 0), (1, "Bravo", 2, 2, 0, 0), (1, "charlie", 2, 2, 0, 0)]),
    ],
    "unplayed": [
        ([], []),
        ([("A", "B", 2, 0), ("C", "A", None, None)],
         [(1, "A", 1, 3, 2, 2), (2, "C", 0, 0, 0, 0), (3, "B", 1, 0, -2, 0)]),
        ([("A", "B", None, None)],
         [(1, "A", 0, 0, 0, 0), (1, "B", 0, 0, 0, 0)]),
        ([("A", "B", 1, None), ("B", "C", 0, 1)],
         [(1, "C", 1, 3, 1, 1), (2, "A", 0, 0, 0, 0), (3, "B", 1, 0, -1, 0)]),
    ],
    "h2h": [
        # A and B on 3 points; A beat B, B has the better goal difference
        ([("A", "B", 1, 0), ("B", "C", 6, 0), ("A", "D", 0, 2), ("C", "D", 0, 0)],
         [(1, "D", 2, 4, 2, 2), (2, "A", 2, 3, -1, 1), (3, "B", 2, 3, 5, 6),
          (4, "C", 2, 1, -6, 0)]),
        # A, B, C on 6 points: head-to-head 6, 3, 0; goal difference 2, 5, 16
        ([("A", "B", 1, 0), ("A", "C", 1, 0), ("B", "C", 1, 0),
          ("B", "D", 5, 0), ("C", "D", 9, 0), ("C", "E", 9, 0)],
         [(1, "A", 2, 6, 2, 2), (2, "B", 3, 6, 5, 6), (3, "C", 4, 6, 16, 18),
          (4, "E", 1, 0, -9, 0), (5, "D", 2, 0, -14, 0)]),
    ],
}


def main(clause):
    try:
        from league.table import standings
    except Exception as exc:                                  # noqa: BLE001
        print("cannot import standings: %r" % exc)
        return 1
    bad = 0
    for matches, want in CASES[clause]:
        try:
            got = [tuple(row) for row in standings(list(matches))]
        except Exception as exc:                              # noqa: BLE001
            print("raise  %r: %r" % (matches, exc))
            bad += 1
            continue
        if got != want:
            print("wrong  %r\n   got  %r\n  want  %r" % (matches, got, want))
            bad += 1
    print("%s: %d/%d tables" % (clause, len(CASES[clause]) - bad, len(CASES[clause])))
    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1]))
