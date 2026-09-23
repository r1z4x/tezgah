#!/usr/bin/env python3
"""Detached graph auto-index worker: lock-guarded, bounded retry.

Spawned by tezgah_context.autoindex as
    [python, tezgah_index.py, binary, root, head, stamp_path, lock_path]

`binary` is the resolved codegraph executable, so the worker never re-resolves
it. codegraph keeps one live writer per project, so two indexers on one repo is
the failure the flock below covers; it is also why the retry and the stamp are
shared with every other caller. HEAD is stamped only after a successful index, so
a failed run is retried on the next session start rather than being mistaken for
current. A final failure leaves a `<stamp>.failed` marker that autoindex surfaces
to the next session, instead of looping invisibly. The flock dies with the
process, so a crash never leaves a stale lock behind. A host without `fcntl`
(Windows) still runs this worker: the lock step says it is indexing unlocked and
carries on, because the index is worth having without one - the same degrading
import `tezgah_integrity` and `tezgah_research` use. Stdlib only.
"""
import os
import signal
import subprocess
import sys
import time

try:
    import fcntl
except ImportError:  # not POSIX: index unlocked, and say so on stderr (below)
    fcntl = None

RETRIES = int(os.environ.get("TEZGAH_INDEX_RETRIES", "5"))
DELAY = float(os.environ.get("TEZGAH_INDEX_RETRY_DELAY", "3"))
# How long one index attempt may run before its process group is killed.
# Generous on purpose - the worker is detached and retries, so the bound exists
# to stop an unbounded wait, not to time a slow index. Without it a codegraph
# that hangs holds this repo's flock forever, and the next session's auto-index
# then declines to start for the rest of the machine's uptime.
RUN_TIMEOUT = float(os.environ.get("TEZGAH_INDEX_TIMEOUT", "600"))


def run_bounded(argv, timeout=None):
    """Run one index attempt in its own process group and return its exit status.

    The group is what makes the bound real: `subprocess.run(timeout=)` kills the
    direct child only, so a codegraph that spawns a helper and then hangs leaves
    the helper behind and the wait continues one level down. The child is started
    with `start_new_session=True` - the same shape `tezgah_context.autoindex`
    already gives this worker - so one `killpg` takes the whole tree. A failed
    kill is not fatal: the worker exits anyway, and the flock dies with it."""
    timeout = RUN_TIMEOUT if timeout is None else timeout
    try:
        proc = subprocess.Popen(argv, stdout=subprocess.DEVNULL,
                                stderr=subprocess.DEVNULL,
                                start_new_session=True)
    except OSError:
        return 1
    try:
        return proc.wait(timeout=timeout)
    except subprocess.TimeoutExpired:
        try:
            os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
        except OSError:
            try:
                proc.kill()
            except OSError:
                pass
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            pass
        return 1


def command(binary, root):
    """The argv for one codegraph run over one repository.

    codegraph's own switch is whether the project carries an index already: a
    project it has never seen takes `init` (non-interactive, so a detached worker
    cannot hang on a prompt) and one it has takes the incremental `sync`."""
    if os.path.exists(os.path.join(root, ".codegraph", "codegraph.db")):
        return [binary, "sync", root]
    return [binary, "init", root, "-y"]


def main():
    binary, root, head, stamp, lock = sys.argv[1:6]
    os.makedirs(os.path.dirname(lock), exist_ok=True)
    handle = open(lock, "w", encoding="utf-8")
    if fcntl is None:
        # No advisory lock on this host. Refusing would leave a Windows repo with
        # no index at all, so run unlocked - but never silently: the parent sends
        # this to the repo's index log, which is the file a session names when it
        # reports an index problem.
        sys.stderr.write(
            "tezgah: no fcntl on this host; indexing %s unlocked\n" % root)
    else:
        try:
            fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            return 0  # another indexer holds this repo; its run will stamp HEAD
    argv = command(binary, root)
    failed = stamp + ".failed"
    for _ in range(RETRIES):
        if run_bounded(argv) != 0:
            time.sleep(DELAY)
            continue
        with open(stamp, "w", encoding="utf-8") as fh:
            fh.write(head)
        try:
            os.remove(failed)
        except OSError:
            pass
        return 0
    # leave a marker so the next session reports the failure instead of only
    # re-spawning the worker silently
    try:
        with open(failed, "w", encoding="utf-8") as fh:
            fh.write("codegraph index failed after %d attempt(s)\n" % RETRIES)
    except OSError:
        pass
    return 1


if __name__ == "__main__":
    sys.exit(main())
