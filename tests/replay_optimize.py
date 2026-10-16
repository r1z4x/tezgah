#!/usr/bin/env python3
"""Replay recorded turns through the planner's `already green` rule.

    python3 tests/replay_optimize.py            # the counts, exit 1 on a lost failure
    python3 tests/replay_optimize.py --baseline # the same line, as the plan names it
    python3 tests/replay_optimize.py --limit 200 --json

The rule under test is `bin/tezgah-optimize next`'s second half: a check whose
green row is already recorded is `already green`, and the session does not run it
again. The recorded turns are the real evidence ledgers under
`<cache>/tezgah/evidence/`: one file per session, and one `verify` row per check a
session ran, with the command and its exit code.

What the ledger does not carry is the sha a run belongs to, so the session is the
stand-in and the report says so: a check is a repeat when the same command already
ran green earlier in the same session. `saving` is how many checks the rule would
have skipped. `lost` is a repeat that failed after a green run of the same command
- the failure the rule would have missed - and any `lost` above 0 fails this run,
because fewer checks only count as a win while nothing is lost with them.

The two numbers are what the plan's acceptance item is about, and they are read
from the machine's own ledgers rather than from a fixture: a fixture would prove
the arithmetic and nothing about this repository's sessions.
"""
import glob
import json
import os
import sys

HERE = os.path.dirname(os.path.realpath(__file__))
CACHE = os.environ.get("TEZGAH_CACHE") or os.path.join(
    os.environ.get("XDG_CACHE_HOME") or os.path.expanduser("~/.cache"), "tezgah")
DEFAULT_LIMIT = 200


def ledgers(limit):
    """The newest `limit` session ledgers, newest first."""
    found = glob.glob(os.path.join(CACHE, "evidence", "*.jsonl"))
    return sorted(found, key=os.path.getmtime, reverse=True)[:limit]


def checks(path):
    """[(command, exit)] for one ledger's `verify` rows, oldest first - the checks
    a session ran, in the order it ran them. A row without a command, or one that
    does not parse, is skipped: a reader that failed a whole session on one torn
    line would report nothing about the rest."""
    out = []
    try:
        with open(path, encoding="utf-8", errors="replace") as fh:
            for line in fh:
                try:
                    row = json.loads(line)
                except ValueError:
                    continue
                if not isinstance(row, dict) or row.get("kind") != "verify":
                    continue
                command = " ".join(str(row.get("detail") or "").split())
                if not command:
                    continue
                try:
                    code = int(row.get("exit"))
                except (TypeError, ValueError):
                    continue
                out.append((command, code))
    except OSError:
        return []
    return out


def replay(rows):
    """(checks, repeats, saving, lost) for one session's checks: `repeats` counts a
    check whose command already ran green in this session, and `lost` counts the
    repeats that failed - the failures the `already green` rule would have
    skipped."""
    green = set()
    repeats = saving = lost = 0
    for command, code in rows:
        if command in green:
            repeats += 1
            saving += 1
            if code:
                lost += 1
            continue
        if not code:
            green.add(command)
    return len(rows), repeats, saving, lost


def main(argv):
    limit = DEFAULT_LIMIT
    if "--limit" in argv:
        i = argv.index("--limit")
        try:
            limit = int(argv[i + 1])
        except (IndexError, ValueError):
            print("replay_optimize: --limit takes a whole number of ledgers",
                  file=sys.stderr)
            return 2
    per_repo = {}
    totals = {"ledgers": 0, "checks": 0, "repeats": 0, "saving": 0, "lost": 0}
    for path in ledgers(limit):
        rows = checks(path)
        if not rows:
            continue
        checked, repeats, saving, lost = replay(rows)
        totals["ledgers"] += 1
        totals["checks"] += checked
        totals["repeats"] += repeats
        totals["saving"] += saving
        totals["lost"] += lost
        name = os.path.basename(path)
        per_repo[name] = {"checks": checked, "repeats": repeats, "lost": lost}
    if "--json" in argv:
        print(json.dumps({"totals": totals, "ledgers": per_repo}, indent=2,
                         sort_keys=True))
    else:
        print("ledgers: %d; checks: %d; repeated after a green run: %d; "
              "saving: %d; lost failures: %d"
              % (totals["ledgers"], totals["checks"], totals["repeats"],
                 totals["saving"], totals["lost"]))
        worst = sorted(per_repo.items(), key=lambda kv: -kv[1]["repeats"])[:3]
        for name, row in worst:
            if row["repeats"]:
                print("  %s: %d repeat(s), %d lost" % (name, row["repeats"],
                                                       row["lost"]))
        if not totals["ledgers"]:
            print("no ledger under %s: nothing recorded to replay"
                  % os.path.join(CACHE, "evidence"))
    if totals["lost"]:
        print("FAIL: %d repeat(s) failed after a green run of the same command, so "
              "the `already green` rule would have skipped a real failure - it is a "
              "win only while this stays 0" % totals["lost"])
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
