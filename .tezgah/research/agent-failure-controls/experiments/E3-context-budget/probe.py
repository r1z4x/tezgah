#!/usr/bin/env python3
"""E3 instrument: measure the bytes tezgah injects, and whether a block grows.

One JSON line per measurement: {"id", "event", "bytes", "lines", "keys"}.
Part 2 uses a throwaway fixture directory, removed at the end of the run.
"""
import json
import os
import shutil
import sys

HERE = os.path.dirname(os.path.realpath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", "..", "..", "..", ".."))
sys.path.insert(0, os.path.join(REPO, "hooks"))

import tezgah_context as ctx    # noqa: E402

FIXTURE = os.path.join(HERE, ".fixture")

PROMPTS = [
    ("plain", "add a rounding helper to calc_total"),
    ("spec", "make the UI feel professional and clean"),
    ("consult", "is this architecture decision safe to deploy"),
    ("research", "run an ablation and report the evidence"),
    ("cbm", "who calls tezgah_gate.decision in this repo"),
]


def measure(mid, event, text, keys=None):
    return dict(id=mid, event=event, bytes=len(text.encode("utf-8")),
                lines=text.count("\n") + 1, keys=sorted(keys or []))


def part1():
    rows = [measure("core-always-on", "always_on_core", ctx.always_on_core())]
    rows.append(measure("session-start", "session_start",
                        ctx.context_for("session_start", REPO)))
    rows.append(measure("subagent-start", "subagent_start",
                        ctx.context_for("subagent_start", REPO)))
    for name, prompt in PROMPTS:
        keys = ctx.classify_prompt(prompt)
        text = ctx.context_for("user_prompt", REPO, {"prompt": prompt})
        rows.append(measure("user-prompt-" + name, "user_prompt", text, keys))
    return rows


def _fixture_lines(n):
    os.makedirs(os.path.join(FIXTURE, ".tezgah"), exist_ok=True)
    os.makedirs(os.path.join(FIXTURE, "plans", "open"), exist_ok=True)
    with open(os.path.join(FIXTURE, ".tezgah", "lessons.md"), "w") as fh:
        fh.write("# Lessons\n\n")
        for i in range(n):
            fh.write("- lesson %d: a mistake that already happened, with the "
                     "rule that prevents it, written out at realistic length\n" % i)
    for i in range(1, 9):
        path = os.path.join(FIXTURE, "plans", "open", "%03d-fixture.md" % i)
        with open(path, "w") as fh:
            fh.write("---\nid: %03d\ntitle: Fixture plan %d\n---\n\n"
                     "## Next\nImplement fixture plan %d on its branch.\n" % (i, i, i))


def part2():
    empty = os.path.join(FIXTURE, ".empty")
    os.makedirs(empty, exist_ok=True)
    rows = [measure("lessons-empty", "lessons", ctx.lessons(empty)),
            measure("plans-empty", "open_plans", ctx.open_plans(empty))]
    _fixture_lines(200)
    rows.append(measure("lessons-200", "lessons", ctx.lessons(FIXTURE)))
    rows.append(measure("plans-8", "open_plans", ctx.open_plans(FIXTURE)))
    return rows


def main():
    rows = part1() + part2()
    for row in rows:
        print(json.dumps(row, ensure_ascii=False))

    by_id = {r["id"]: r for r in rows}
    plain = by_id["user-prompt-plain"]["bytes"]
    growth = dict(
        session_start=by_id["session-start"]["bytes"],
        session_start_tokens=round(by_id["session-start"]["bytes"] / 4.0),
        conditional_over_plain={
            name: by_id["user-prompt-" + name]["bytes"] - plain
            for name, _ in PROMPTS if name != "plain"},
        lessons_growth=by_id["lessons-200"]["bytes"]
        - by_id["lessons-empty"]["bytes"],
        plans_growth=by_id["plans-8"]["bytes"] - by_id["plans-empty"]["bytes"],
    )
    print(json.dumps(dict(summary=growth), ensure_ascii=False))


if __name__ == "__main__":
    try:
        main()
    finally:
        shutil.rmtree(FIXTURE, ignore_errors=True)
