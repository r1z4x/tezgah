#!/usr/bin/env python3
"""E1 probe: per-block byte sizes of the injected text, per event.

Builds a synthetic root (a plan with a phase and an allowlist, a lessons file,
a graph-shaped repo) under a temp HOME, arms tezgah over it with TEZGAH_ROOTS,
then calls tezgah_context.context_for for each event. `budgeted` is wrapped to
capture the (key, text) parts before the budget is applied, so the sizes are the
builder's own blocks and not a guess from the returned string.

Usage: python3 hh-budget.py [--big]
  --big   multiply the lessons file and the open plans 5x, to find which key
          crosses a budget first.
Prints one JSON object per (event, with_core, variant) on stdout.
"""
import json
import os
import shutil
import sys
import tempfile

REPO = "/Users/rizax/Projects/tezgah"
sys.path.insert(0, os.path.join(REPO, "hooks"))


def build_repo(root, big=False):
    os.makedirs(os.path.join(root, "plans", "open"), exist_ok=True)
    os.makedirs(os.path.join(root, "src"), exist_ok=True)
    for i in range(40):
        with open(os.path.join(root, "src", "mod%02d.py" % i), "w") as fh:
            fh.write("def f%d():\n    return %d\n" % (i, i))
    for i in range(20 if big else 4):
        lines = ["---", "id: %03d" % (i + 1), "title: plan %d" % (i + 1),
                 "status: open", "created: 2026-09-20", "updated: 2026-09-20"]
        if i == 0:
            lines += ["phase: implementation", "allowed_paths:", "  - src/**"]
        lines += ["---", "## Goal", "the goal of plan %d" % (i + 1), ""]
        with open(os.path.join(root, "plans", "open", "%03d-plan.md" % (i + 1)), "w") as fh:
            fh.write("\n".join(lines))
    os.makedirs(os.path.join(root, ".tezgah"), exist_ok=True)
    lesson = "- a lesson line that is long enough to matter for a byte budget\n"
    with open(os.path.join(root, ".tezgah", "lessons.md"), "w") as fh:
        fh.write(lesson * (60 if big else 12))
    return root


def main():
    big = "--big" in sys.argv
    home = tempfile.mkdtemp(prefix="hh-e1-home-")
    root = build_repo(os.path.join(home, "proj"), big=big)
    os.environ["HOME"] = home
    os.environ["XDG_CONFIG_HOME"] = os.path.join(home, ".config")
    os.environ["XDG_CACHE_HOME"] = os.path.join(home, ".cache")
    os.environ["TEZGAH_ROOTS"] = root
    os.makedirs(os.path.join(home, ".config", "tezgah"), exist_ok=True)

    import tezgah_context as tc

    captured = []
    real = tc.budgeted

    def wrapped(event, parts):
        captured[:] = list(parts)
        return real(event, parts)

    tc.budgeted = wrapped

    for event in ("session_start", "user_prompt", "subagent_start"):
        for with_core in (True, False):
            captured[:] = []
            payload = None
            if event == "user_prompt":
                payload = {"prompt": "please implement the thing in the plan",
                           "session_id": "hh-e1"}
            try:
                out = tc.context_for(event, root, payload, with_core=with_core)
            except Exception as exc:  # a probe reports, it does not hide
                print(json.dumps({"event": event, "with_core": with_core,
                                  "error": "%s: %s" % (type(exc).__name__, exc)}))
                continue
            blocks = {k: len(t.encode()) for k, t in captured if t}
            limit = tc.CONTEXT_BUDGET.get(event, tc.DEFAULT_BUDGET)
            total = len(out.encode()) if out else 0
            print(json.dumps({
                "event": event, "with_core": with_core,
                "variant": "big" if big else "normal",
                "limit": limit, "total_bytes": total,
                "pct_of_limit": round(100.0 * total / limit, 1),
                "blocks": dict(sorted(blocks.items(), key=lambda kv: -kv[1])),
                "returned": bool(out),
            }))
    shutil.rmtree(home, ignore_errors=True)


if __name__ == "__main__":
    main()
