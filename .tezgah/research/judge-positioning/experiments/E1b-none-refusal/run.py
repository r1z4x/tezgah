#!/usr/bin/env python3
"""E1b: does the 98-option Choice answer `none` for a query no entry covers?

The same two arms as E1, over queries that name work this library does not carry.
Imports the option-building and arm code from E1's runner so the two runs answer
the same shape.
"""
import json
import os
import sys

HERE = os.path.dirname(os.path.realpath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "E1-ai-research-router"))

import run as e1  # noqa: E402

OUT_OF_LIBRARY = [
    ("N01", "Set up a Kafka cluster for streaming telemetry."),
    ("N02", "Design a Postgres schema for multi-tenant billing."),
    ("N03", "Build a React dashboard for my metrics."),
    ("N04", "Configure nginx as a reverse proxy."),
]


def main():
    ents = e1.entries()
    flat_criteria = {name: cl for name, cl, _ in ents}
    flat_criteria[e1.NONE_ENTRY] = "no entry in this library covers the request"
    st = e1.stages()
    stage_criteria = {s: "%d entries: %s" % (len(n), ", ".join(n)) for s, n in st.items()}
    stage_criteria[e1.NONE_STAGE] = "no stage covers the request"
    by_name = {name: cl for name, cl, _ in ents}
    for qid, query in OUT_OF_LIBRARY:
        row = {"id": qid, "query": query, "label": "none"}
        ra = e1.call(query, flat_criteria, e1.FLAT)
        row["flat"] = {"choice": e1.pick(ra["answers"], "q"),
                       "usage": ra["usage"]} if ra else None
        rb1 = e1.call(query, stage_criteria, e1.STAGE)
        chosen_stage = e1.pick(rb1["answers"], "q") if rb1 else None
        row["stage_pick"] = chosen_stage
        if chosen_stage in st:
            sub = {n: by_name[n] for n in st[chosen_stage]}
            sub[e1.NONE_ENTRY] = "no entry in this stage covers the request"
            rb2 = e1.call(query, sub, e1.FLAT)
            row["two_stage"] = e1.pick(rb2["answers"], "q") if rb2 else None
        else:
            row["two_stage"] = chosen_stage
        row["flat_refused"] = row["flat"]["choice"] == "none"
        row["two_stage_refused"] = row["two_stage"] == "none"
        print(json.dumps(row, ensure_ascii=False))
        sys.stdout.flush()
    return 0


if __name__ == "__main__":
    sys.exit(main())
