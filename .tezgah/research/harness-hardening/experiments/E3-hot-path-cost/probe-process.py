#!/usr/bin/env python3
"""E3 probe, second half: what a host actually pays per gated call.

Every host runs its PreToolUse hook as a fresh process, so the honest per-call
cost is interpreter start + import + decision, not the in-process time. This
times (a) the real probe process `tests/_probe_gate.py` with the same payload the
in-process measurement used, (b) the same for `bin/tezgah-context`, and (c) a
bare `import tezgah_gate`, with `-X importtime`'s top rows named.

Usage: python3 hh-proc.py [--reps 40]
"""
import json
import os
import shutil
import statistics
import subprocess
import sys
import tempfile
import time

REPO = "/Users/rizax/Projects/tezgah"


def stats(values):
    ordered = sorted(values)
    return {"n": len(ordered), "p50_ms": round(statistics.median(ordered), 1),
            "p95_ms": round(ordered[min(len(ordered) - 1,
                                        int(round(0.95 * (len(ordered) - 1))))], 1),
            "max_ms": round(max(ordered), 1),
            "min_ms": round(min(ordered), 1),
            "mean_ms": round(statistics.fmean(ordered), 1)}


def main():
    reps = 40
    if "--reps" in sys.argv:
        reps = int(sys.argv[sys.argv.index("--reps") + 1])

    home = tempfile.mkdtemp(prefix="hh-proc-home-")
    root = os.path.join(home, "proj")
    os.makedirs(os.path.join(root, "src"), exist_ok=True)
    os.makedirs(os.path.join(home, ".config", "tezgah"), exist_ok=True)
    env = dict(os.environ, HOME=home,
               XDG_CONFIG_HOME=os.path.join(home, ".config"),
               TEZGAH_ROOTS=root)
    payload = json.dumps({"tool": "edit", "cwd": root, "session_id": "hh-proc",
                          "input": {"file_path": os.path.join(root, "src", "a.py"),
                                    "old_string": "x = 1", "new_string": "x = 2"}})

    def time_proc(argv, stdin_text, count):
        vals = []
        for _ in range(count):
            t0 = time.perf_counter()
            subprocess.run(argv, input=stdin_text, text=True, env=env,
                           capture_output=True)
            vals.append((time.perf_counter() - t0) * 1000.0)
        return vals

    probe = os.path.join(REPO, "tests", "_probe_gate.py")
    rows = [
        ("hook process: tests/_probe_gate.py", time_proc([sys.executable, probe], payload, reps)),
        ("bin/tezgah-context", time_proc([os.path.join(REPO, "bin", "tezgah-context")],
                                        payload, max(10, reps // 4))),
        ("bare interpreter", time_proc([sys.executable, "-c", "pass"], "", max(10, reps // 4))),
        ("import tezgah_gate only",
         time_proc([sys.executable, "-c",
                    "import sys; sys.path.insert(0, %r); import tezgah_gate" % os.path.join(REPO, "hooks")],
                   "", max(10, reps // 4))),
    ]
    for name, vals in rows:
        row = stats(vals)
        row.update({"call": name, "python": sys.version.split()[0],
                    "source": "subprocess wall clock"})
        print(json.dumps(row))

    importtime = subprocess.run(
        [sys.executable, "-X", "importtime", "-c",
         "import sys; sys.path.insert(0, %r); import tezgah_gate" % os.path.join(REPO, "hooks")],
        capture_output=True, text=True, env=env)
    entries = []
    for line in importtime.stderr.splitlines():
        parts = line.split("|")
        if len(parts) >= 2 and parts[0].strip().isdigit():
            entries.append((int(parts[0].strip()), parts[-1].strip()))
    entries.sort(reverse=True)
    print(json.dumps({"call": "importtime top", "top_us": entries[:8],
                      "source": "python3 -X importtime"}))
    shutil.rmtree(home, ignore_errors=True)


if __name__ == "__main__":
    main()
