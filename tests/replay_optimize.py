#!/usr/bin/env python3
"""Replay recorded turns through the planner's `already green` rule.

    python3 tests/replay_optimize.py            # the counts, exit 1 on a lost failure
    python3 tests/replay_optimize.py --baseline # the same line, as the plan names it
    python3 tests/replay_optimize.py --limit 200 --json

The rule under test is `bin/tezgah-optimize next`'s second half: a check whose
green row is already recorded is `already green`, the session does not run it
again - and the answer is refused while the working tree holds uncommitted edits,
because a row for the same sha then describes a tree that has moved.

The recorded turns are the real evidence ledger, read through `tezgah_store`: the
same store the hooks write, one `verify` row per check a session ran and one
`edit` row per edit it made. An earlier version of this script read the JSONL
files beside the database, which stopped being written on 2026-10-08, so it
reported a 7% sample as the whole record (review of plan 109, F1).

The session is the sha's stand-in, and the report says so: a check is a repeat when
the same command already ran green earlier in the same session with no `edit` in
between - the ledger's own record of the tree moving, which is what the rule's
dirty-tree guard reads. `saving` is how many checks the rule would have skipped,
and `lost` is a repeat that failed. Any `lost` above 0 fails this run, because
fewer checks only count as a win while nothing is lost with them.
"""
import json
import os
import sys

HERE = os.path.dirname(os.path.realpath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "hooks"))
import tezgah_store as store  # noqa: E402
import tezgah_paths as tp  # noqa: E402

DEFAULT_LIMIT = 0
# The rows a turn's cost is read from: a check and an edit. Both are what the
# ledger already writes for every session, so this reads the record rather than a
# summary of it.
KINDS = ("verify", "edit")


def turns(cache, limit):
    """[(session, [(kind, command, exit)])] for the newest `limit` sessions that
    ran a check - every session with `limit` 0, which is the default - oldest
    first per session and in the ledger's own append order."""
    known = [sid for sid, _ts in store.sessions(cache)]
    newest = known if not limit else known[:limit]
    wanted = set(newest)
    per = {}
    for session, _ts, text in store.recent_rows(cache, 0, KINDS, ""):
        if session not in wanted:
            continue
        try:
            row = json.loads(text)
        except ValueError:
            continue
        if row.get("kind") == "edit":
            per.setdefault(session, []).append(("edit", "", 0))
            continue
        command = " ".join(str(row.get("detail") or "").split())
        try:
            code = int(row.get("exit"))
        except (TypeError, ValueError):
            continue
        if command:
            per.setdefault(session, []).append(("verify", command, code))
    return [(sid, per[sid]) for sid in newest if per.get(sid)]


def replay(rows):
    """(checks, saving, lost) for one session's rows in order.

    `green` is the set of commands whose last run in this session passed. An `edit`
    clears it: the tree moved, so no recorded pass describes what is in front of
    the session - which is the rule's own dirty-tree guard, read from the ledger's
    own rows. A check whose command is still in `green` is a repeat the rule would
    skip; one that fails is a lost failure."""
    green = set()
    checks = saving = lost = 0
    for kind, command, code in rows:
        if kind == "edit":
            green.clear()
            continue
        checks += 1
        if command in green:
            saving += 1
            if code:
                lost += 1
            continue
        if not code:
            green.add(command)
    return checks, saving, lost


def main(argv):
    limit = DEFAULT_LIMIT
    if "--limit" in argv:
        i = argv.index("--limit")
        try:
            limit = int(argv[i + 1])
        except (IndexError, ValueError):
            print("replay_optimize: --limit takes a whole number of sessions",
                  file=sys.stderr)
            return 2
    cache = tp.cache_dir()
    totals = {"sessions": 0, "checks": 0, "saving": 0, "lost": 0}
    worst = []
    for name, rows in turns(cache, limit):
        checked, saving, lost = replay(rows)
        if not checked:
            continue
        totals["sessions"] += 1
        totals["checks"] += checked
        totals["saving"] += saving
        totals["lost"] += lost
        if saving:
            worst.append((saving, lost, name))
    worst.sort(reverse=True)
    if "--json" in argv:
        print(json.dumps({"totals": totals,
                          "sessions": [{"session": n, "saving": s, "lost": lost}
                                       for s, lost, n in worst[:10]]},
                         indent=2, sort_keys=True))
    else:
        print("sessions: %d; checks: %d; repeated after a green run with no edit "
              "between: %d; saving: %d; lost failures: %d"
              % (totals["sessions"], totals["checks"], totals["saving"],
                 totals["saving"], totals["lost"]))
        for saving, lost, name in worst[:3]:
            print("  %s: %d repeat(s), %d lost" % (name, saving, lost))
        if not totals["sessions"]:
            print("no session with a check row in %s: nothing recorded to replay"
                  % cache)
    if totals["lost"]:
        print("FAIL: %d repeat(s) failed after a green run of the same command with "
              "no edit between them, so the `already green` rule would have skipped "
              "a real failure - it is a win only while this stays 0"
              % totals["lost"])
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
