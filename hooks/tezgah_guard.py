#!/usr/bin/env python3
"""One guard for every entry point: a crashing core degrades one feature.

Each host entry point decodes its payload defensively and then calls into the
shared core. That call is where a bug stops being a bug and becomes an outage:
on Claude, Codex and Cursor the session loses one envelope, but on omp the
bridge turns the same crash into a *session-wide* disable - the gate, the ledger
and the status line all go off for the rest of the session, with the model told
not to fix it - and opencode's plugin waits on a core process with no deadline.
Same fault, blast radii that differ by two orders of magnitude.

`safe` is the single place that fault is caught, and it is applied at every call
site rather than re-derived per host, for the reason the gate's own refusals are
recorded: "a deny nobody counts is a rule whose effect can never be argued
about". A crash swallowed in silence would be worse than the crash - it would
look like a rule that fired and a core that answered - so the caught class is
written to the ledger as a `crash` row, best effort, and the row is the only
thing this module does besides returning None.

It fails open, deliberately, and in the direction the whole layer already
chooses: the gate passes a call whose record it cannot read, the context builder
returns None outside a root, and a judgement that cannot be made returns "". A
core that has crashed has not refused anything, so the call it was guarding
proceeds - the alternative is a session in which a broken *rule* blocks every
action, which is the fail-closed trap the design names.
"""
import os
import sys
import time

# TEZGAH_DEBUG=1 appends one line per hook process to `<cache>/debug.log`: the
# host, the entry script, every guarded core call with its outcome, and the
# elapsed time. Audit L-11 (GAP-10) found no debug level at all, so a slow or
# silently failing hook could only be diagnosed by editing it. Every entry point
# reaches the core through `safe`, and a hook is one process per event, so the
# line is written once at exit from what `safe` saw. Off by default, and then
# the whole cost is this one environment read.
DEBUG = os.environ.get("TEZGAH_DEBUG", "") not in ("", "0")
_CALLS = []
_START = time.monotonic()


def _host():
    """`hosts/<name>/...` names its host; the shared `hooks/projects-*.py`
    scripts run on Claude and dsh alike, so they are named by the script."""
    parts = os.path.realpath(sys.argv[0] if sys.argv else "").split(os.sep)
    return parts[parts.index("hosts") + 1] if "hosts" in parts[:-1] else "claude/dsh"


def _write_debug():
    """The line, appended to a file created owner-only (it names the calls a
    session made). Best effort: a debug log must never cost the hook."""
    try:
        from tezgah_paths import cache_dir
        line = "%d host=%s script=%s calls=%s ms=%d\n" % (
            int(time.time()), _host(), os.path.basename(sys.argv[0] if sys.argv else ""),
            ",".join(_CALLS) or "none", (time.monotonic() - _START) * 1000)
        fd = os.open(os.path.join(cache_dir(), "debug.log"),
                     os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)
        with os.fdopen(fd, "a", encoding="utf-8") as fh:
            fh.write(line)
    except Exception:
        pass


if DEBUG:
    import atexit
    atexit.register(_write_debug)


def safe(session_id, fn, *args, **kwargs):
    """`fn(*args, **kwargs)`, or None when it raises. Never raises itself.

    `session_id` is the guard's own argument, not the callee's: it is what the
    crash row is filed under, so the first argument of the call is passed after
    it. A caller with no session id passes None, which `note` treats as the
    unowned ledger the rest of the module already writes to."""
    try:
        out = fn(*args, **kwargs)
        if DEBUG:
            # `answer`: the core returned something (a deny reason, a context
            # block, a block decision); `none`: it had nothing to say
            _CALLS.append("%s:%s" % (getattr(fn, "__name__", "?"),
                                     "none" if out is None else "answer"))
        return out
    except Exception as exc:
        if DEBUG:
            _CALLS.append("%s:%s" % (getattr(fn, "__name__", "?"),
                                     type(exc).__name__))
        try:
            import tezgah_integrity
            tezgah_integrity.note(
                session_id, "crash",
                "%s: %s" % (getattr(fn, "__name__", str(fn)), str(exc)[:120]))
        except Exception:
            # The record is best effort by construction: a guard that raised
            # while reporting a raise would be the failure it exists to stop.
            pass
        return None
