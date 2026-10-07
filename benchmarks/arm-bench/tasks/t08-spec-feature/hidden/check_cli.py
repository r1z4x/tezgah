#!/usr/bin/env python3
"""Hidden CLI checks for t08. Run with the candidate tree as the cwd.

Drives `src/ledger_cli.py` as a subprocess and asserts exact stdout, exit codes
and error handling for the new flag and for the unchanged default report.
"""
import os
import subprocess
import sys
import tempfile

CLI = os.path.join(os.getcwd(), "src", "ledger_cli.py")

LEDGER = """\
# january expenses
food 10.00
travel 25.50
food 2.50
books 25.50
misc 1.00
"""

# Line 3 has one field instead of two.
BROKEN = """\
food 10.00
travel 25.50
books
"""

# books 25.50, food 12.50, misc 1.00, travel 25.50 -> TOTAL 64.50
DEFAULT_STDOUT = (
    "books 25.50\n"
    "food 12.50\n"
    "misc 1.00\n"
    "travel 25.50\n"
    "TOTAL 64.50\n"
)

failures = []


def run(*args):
    return subprocess.run(
        [sys.executable, CLI, *args], cwd=os.getcwd(), capture_output=True, text=True
    )


def check(label, proc, exit_code, stdout=None, stderr_has=(), stderr_empty=False):
    if proc.returncode != exit_code:
        failures.append(
            f"{label}: exit {proc.returncode}, want {exit_code} "
            f"(stdout {proc.stdout[:120]!r}, stderr {proc.stderr.strip()[:200]!r})"
        )
    if stdout is not None and proc.stdout != stdout:
        failures.append(f"{label}: stdout {proc.stdout!r}, want {stdout!r}")
    for needle in stderr_has:
        if needle not in proc.stderr:
            failures.append(f"{label}: stderr {proc.stderr.strip()[:200]!r} does not contain {needle!r}")
    if stderr_empty and proc.stderr != "":
        failures.append(f"{label}: stderr is not empty: {proc.stderr.strip()[:200]!r}")


with tempfile.TemporaryDirectory() as tmp:
    good = os.path.join(tmp, "ledger.txt")
    broken = os.path.join(tmp, "broken.txt")
    empty = os.path.join(tmp, "empty.txt")
    missing = os.path.join(tmp, "nope.txt")
    for path, text in ((good, LEDGER), (broken, BROKEN), (empty, "# nothing here\n")):
        with open(path, "w", encoding="utf-8") as handle:
            handle.write(text)

    # The default report, with the flag absent, must be untouched.
    check("default report", run(good), 0, stdout=DEFAULT_STDOUT, stderr_empty=True)
    check("default report, empty ledger", run(empty), 0, stdout="TOTAL 0.00\n", stderr_empty=True)
    check("default, unreadable file", run(missing), 1, stdout="", stderr_has=["error:", "cannot read"])

    # The new flag: exact output, exit 0, clean stderr.
    check("--largest 2", run("--largest", "2", good), 0,
          stdout="books 25.50\ntravel 25.50\n", stderr_empty=True)
    check("--largest 3", run("--largest", "3", good), 0,
          stdout="books 25.50\ntravel 25.50\nfood 12.50\n", stderr_empty=True)
    check("--largest 10 clamps", run("--largest", "10", good), 0,
          stdout="books 25.50\ntravel 25.50\nfood 12.50\nmisc 1.00\n", stderr_empty=True)
    check("--largest 1 on empty ledger", run("--largest", "1", empty), 0, stdout="", stderr_empty=True)
    check("unreadable file under the flag", run("--largest", "2", missing), 1,
          stdout="", stderr_has=["error:", "cannot read"])

    # Bad N: usage error, exit 2, nothing on stdout.
    for raw in ("0", "-1", "abc"):
        check(f"--largest {raw}", run("--largest", raw, good), 2, stdout="", stderr_has=["error:"])

    # Malformed input under the flag: the same handling as the default path.
    proc = run("--largest", "2", broken)
    check("--largest on malformed input", proc, 1, stdout="", stderr_has=["error:", "line 3"])
    if "Traceback" in proc.stderr:
        failures.append(f"--largest on malformed input: stderr carries a traceback: {proc.stderr.strip()[:200]!r}")

if failures:
    print("\n".join(failures))
    sys.exit(1)
print("ok")
