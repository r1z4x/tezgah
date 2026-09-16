#!/usr/bin/env python3
"""End-to-end check: the tezgah status line renders in the real omp TUI.

Starts `omp` in a pty with no prompt (so the run costs no model call), reads the
TUI's own output and asserts the tezgah marks appear in the footer the extension
writes them to. The unit tests cover what the hook answers; only this covers
that omp draws it.

The mark is matched with its color attached: `setStatus` is the one omp surface
that strips ANSI, so a green escape in the frame is exactly what proves the line
went through the widget path instead.

Opt-in local check, not collected by the stdlib suite (name does not match
`test*.py`): it needs the omp binary and the extension tezgah-setup installs. It
exits 0 with "SKIP: ..." when one of those is missing, and 1 only on a real
render failure.

    python3 tests/e2e_omp_statusline.py
"""
import fcntl
import os
import pty
import select
import shutil
import signal
import struct
import subprocess
import sys
import termios
import time

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
AGENT = os.path.join(os.path.expanduser("~"), ".omp", "agent")
EXTENSION = os.path.join(AGENT, "hooks", "pre", "tezgah-hook.ts")
TIMEOUT = 45.0
# the first segment of the status string with the color its "on" state paints
# (hooks/tezgah_context.render_line)
MARK = "\x1b[32mpony"


def omp_bin():
    for p in (shutil.which("omp"),
              os.path.join(os.path.expanduser("~"), ".local", "bin", "omp")):
        if p and os.access(p, os.X_OK):
            return p
    return None


def render(omp):
    """Start the TUI in a pty and return its output up to the status line."""
    master, slave = pty.openpty()
    # the TUI lays out to the real terminal size, so give it one
    fcntl.ioctl(slave, termios.TIOCSWINSZ, struct.pack("HHHH", 40, 120, 0, 0))
    # the check pins the colored form, so a NO_COLOR shell must not turn it into
    # a hang: the mark would never arrive and the deadline is the only exit
    env = dict(os.environ, TERM="xterm-256color")
    env.pop("NO_COLOR", None)
    proc = subprocess.Popen([omp, "--cwd", REPO], stdin=slave, stdout=slave,
                            stderr=slave, cwd=REPO, start_new_session=True,
                            env=env)
    os.close(slave)
    seen = b""
    deadline = time.time() + TIMEOUT
    try:
        while time.time() < deadline:
            # a blocking read would sit on a quiet TUI until the pty closes, so
            # the deadline above could never fire; poll instead
            if not select.select([master], [], [], 0.5)[0]:
                continue
            try:
                chunk = os.read(master, 65536)
            except OSError:
                break
            if not chunk:
                break
            seen += chunk
            if MARK.encode() in seen:
                break
        return seen.decode("utf-8", "replace")
    finally:
        stop(proc)
        os.close(master)


def stop(proc):
    """SIGTERM the TUI's process group, then SIGKILL: omp traps the first."""
    try:
        pgid = os.getpgid(proc.pid)
    except OSError:
        return
    for sig in (signal.SIGTERM, signal.SIGKILL):
        try:
            os.killpg(pgid, sig)
        except OSError:
            return
        try:
            proc.wait(timeout=8)
            return
        except subprocess.TimeoutExpired:
            continue


def run():
    omp = omp_bin()
    if not omp:
        return "SKIP: omp is not installed"
    if not os.path.exists(EXTENSION):
        return ("SKIP: %s is missing (tezgah-setup --install --hosts omp)"
                % EXTENSION)
    try:
        frame = render(omp)
    except subprocess.TimeoutExpired:
        return "FAIL: omp ignored SIGTERM"
    if MARK in frame:
        return "PASS: the tezgah status line rendered in the omp footer"
    return ("FAIL: no colored tezgah status line in %d bytes of omp TUI output"
            % len(frame))


def main():
    result = run()
    print(result)
    return 0 if result.startswith(("PASS", "SKIP")) else 1


if __name__ == "__main__":
    sys.exit(main())
