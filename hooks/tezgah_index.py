#!/usr/bin/env python3
"""Detached graph auto-index worker: lock-guarded, bounded retry.

Spawned by tezgah_context.autoindex as
    [python, tezgah_index.py, cbm, root, head, stamp_path, lock_path]

Two sessions in one repo must not index at once, and a concurrent CBM
generation makes the CLI refuse to start ("pre-coordination or unverified CBM
generation is active"), which is transient. So this holds an exclusive flock for
the whole run and retries the CLI a few times. HEAD is stamped only after a
successful index, so a failed run is retried on the next session start rather
than being mistaken for current. A final failure leaves a `<stamp>.failed`
marker that autoindex surfaces to the next session, instead of looping
invisibly. The flock dies with the process, so a crash never leaves a stale lock
behind. Stdlib only.
"""
import fcntl
import os
import subprocess
import sys
import time

RETRIES = int(os.environ.get("TEZGAH_INDEX_RETRIES", "5"))
DELAY = float(os.environ.get("TEZGAH_INDEX_RETRY_DELAY", "3"))


def main():
    cbm, root, head, stamp, lock = sys.argv[1:6]
    os.makedirs(os.path.dirname(lock), exist_ok=True)
    handle = open(lock, "w")
    try:
        fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        return 0  # another indexer holds this repo; its run will stamp HEAD
    try:  # warm daemon: idempotent, cuts MCP connect time
        subprocess.run([cbm, "daemon", "start"], stdout=subprocess.DEVNULL,
                       stderr=subprocess.DEVNULL)
    except OSError:
        pass
    failed = stamp + ".failed"
    for _ in range(RETRIES):
        done = subprocess.run(
            [cbm, "cli", "index_repository", "--repo-path", root, "--mode", "fast"],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        if done.returncode == 0:
            with open(stamp, "w") as fh:
                fh.write(head)
            try:
                os.remove(failed)
            except OSError:
                pass
            return 0
        time.sleep(DELAY)
    # leave a marker so the next session reports the failure instead of only
    # re-spawning the worker silently
    try:
        with open(failed, "w") as fh:
            fh.write("index_repository failed after %d attempt(s)\n" % RETRIES)
    except OSError:
        pass
    return 1


if __name__ == "__main__":
    sys.exit(main())
