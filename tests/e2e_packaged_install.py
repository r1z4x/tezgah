#!/usr/bin/env python3
"""End-to-end check: the release artifact installs and arms a host from a temp dir.

Builds the tarball from the working tree (`packaging/build.sh --version
0.0.0-test --out <tmp>`), checks its `.sha256`, unpacks it, and runs
`bin/tezgah-setup --install --hosts omp` from the unpacked tree with HOME pointed
at a temp directory and TEZGAH_NO_DEPS=1. The dsh host is armed the same way
after it: its launcher is the one entry that is a real file rather than a link on
Windows, so an install that wired the wrong one would read as armed on a machine
that cannot start it, and this is the only job that runs on Windows - the entry
the installer wrote is started there through cmd.exe and held to the same
missing-CLI refusal the POSIX wrapper gives.

That is the shape a user receives: no git, no .tezgah/plans/, and no manifest outside the
artifact - so the artifact has to answer the installer's own questions.

Not collected by the stdlib suite (name does not match `test*.py`). It exits 0
with "SKIP: ..." when sh, tar or python3 is missing, and 1 under
TEZGAH_E2E_STRICT=1 so CI cannot go green on a skip.

    TEZGAH_E2E_STRICT=1 python3 tests/e2e_packaged_install.py
"""
import hashlib
import os
import re
import shutil
import subprocess
import sys
import tarfile
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
VERSION = "0.0.0-test"
# "  ok  " is tezgah-setup's OK symbol (bin/tezgah-setup:154).
OK_ROW = re.compile(r"^ *ok +", re.M)
STRICT = os.environ.get("TEZGAH_E2E_STRICT") == "1"


def skipped(reason):
    """A missing tool is a SKIP - a failure when CI asked for no skips."""
    print("SKIP: %s" % reason)
    return 1 if STRICT else 0


def run(argv, cwd, env):
    return subprocess.run(argv, cwd=cwd, env=env, stdout=subprocess.PIPE,
                          stderr=subprocess.STDOUT, universal_newlines=True)


def setup_argv(py, setup, *args):
    """This tree's installer with these arguments.

    On Windows a tree script has no shebang to run, so it is started through the
    interpreter the smoke probe runs under; naming it in one place keeps
    `--version` from becoming the interpreter's own answer (which is what a
    sliced argv produced: `python --version` exits 0 and prints a version, so the
    assertion passed without the installer ever being asked)."""
    return ([py, setup] if os.name != "posix" else [setup]) + list(args)


def launcher_entry(home):
    """Where the installer wires the dsh launcher on this platform.

    The platform decides it (bin/tezgah-setup's dsh_launcher): the entry is the
    `sh` wrapper's link on POSIX and a `.cmd` copy on Windows, where cmd.exe
    resolves a command through PATHEXT."""
    return os.path.join(home, ".local", "bin",
                        "dsh.cmd" if os.name == "nt" else "dsh")


def launcher_row(text):
    """The dsh launcher row of a report, "" when the report carries none."""
    return next((line for line in text.splitlines()
                 if "dsh launcher on PATH" in line), "")


def run_windows_launcher(env, home, tree):
    """Windows only: start the wired launcher the way a user's shell does.

    Proves the three things a POSIX host cannot: cmd.exe finds `dsh` through
    PATHEXT (a batch file named `dsh` would not be found at all), it can start
    the `.cmd`, and the missing CLI refuses with the two lines and the non-zero
    code the `sh` wrapper prints. PATH holds System32 (cmd.exe itself) and the
    entry's dir, so `npx` cannot be found and the run cannot reach the network;
    XDG_CONFIG_HOME points at an empty dir, so the index warm-up finds no farm
    entry and starts no worker."""
    empty = os.path.join(home, "empty-config")
    os.makedirs(empty, exist_ok=True)
    path = os.pathsep.join([
        os.path.join(os.environ.get("SystemRoot", r"C:\Windows"), "System32"),
        os.path.dirname(launcher_entry(home))])
    probe = run(["cmd", "/c", "dsh", "--version"], tree,
                dict(env, XDG_CONFIG_HOME=empty, PATH=path))
    if probe.returncode != 127 or "dsh CLI not found at" not in probe.stdout:
        print("FAIL: the wired launcher exited %d, not 127 with the missing-CLI "
              "refusal:\n%s" % (probe.returncode, probe.stdout))
        return 1
    if "npx -y @deepseek-ai/dsh" not in probe.stdout:
        print("FAIL: the refusal did not name the install channel:\n%s" % probe.stdout)
        return 1
    print("OK: `dsh` on PATH starts the .cmd and refuses with exit 127 (cmd.exe "
          "resolved dsh.cmd through PATHEXT)")
    return 0


def main():
    sh = shutil.which("sh") or shutil.which("bash")
    if not sh:
        return skipped("sh (or bash) is not on PATH")
    if not shutil.which("tar"):
        return skipped("tar is not on PATH")
    py = shutil.which("python3") or shutil.which("python") or sys.executable
    if not py:
        return skipped("python3 is not on PATH")
    tmp = tempfile.mkdtemp(prefix="tezgah-e2e-")
    try:
        return install(sh, py, tmp)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def install(sh, py, tmp):
    env = dict(os.environ, TEZGAH_PYTHON=py)
    dist = os.path.join(tmp, "dist")
    built = run([sh, os.path.join("packaging", "build.sh"),
                 "--version", VERSION, "--out", dist], ROOT, env)
    if built.returncode != 0:
        print("FAIL: packaging/build.sh: %s" % built.stdout.strip())
        return 1

    tarball = os.path.join(dist, "tezgah-%s.tar.gz" % VERSION)
    with open(tarball, "rb") as fh:
        got = hashlib.sha256(fh.read()).hexdigest()
    with open(tarball + ".sha256") as fh:
        want = fh.read().split()[0]
    if want != got:
        print("FAIL: .sha256 records %s, the build is %s" % (want, got))
        return 1
    print("OK: built %s (%d bytes, sha256 verified)"
          % (os.path.basename(tarball), os.path.getsize(tarball)))

    tree = os.path.join(tmp, "unpacked")
    with tarfile.open(tarball, "r:gz") as tar:
        # 3.12+ warns about an unfiltered extractall, so the filter is used
        # wherever the unpacking module offers one.
        if hasattr(tarfile, "data_filter"):
            tar.extractall(tree, filter="data")
        else:
            tar.extractall(tree)
    if not os.path.isfile(os.path.join(tree, "MANIFEST")):
        print("FAIL: the artifact carries no MANIFEST - an installed tree cannot list itself")
        return 1
    unpacked = sum(len(names) for _, _, names in os.walk(tree))
    print("OK: unpacked %d files to %s" % (unpacked, tree))

    # A machine that has nothing: HOME (USERPROFILE drives expanduser on Windows)
    # points at the temp dir, so no host wiring and no config touch this machine.
    home = os.path.join(tmp, "home")
    os.makedirs(home)
    env.update(HOME=home, USERPROFILE=home, TEZGAH_NO_DEPS="1")
    setup = os.path.join(tree, "bin", "tezgah-setup")
    done = run(setup_argv(py, setup, "--install", "--hosts", "omp"), tree, env)
    if done.returncode != 0:
        print("FAIL: %s --install --hosts omp exited %d\n%s"
              % (setup, done.returncode, done.stdout))
        return 1
    section = re.search(r"^omp:$", done.stdout, re.M)
    rows = OK_ROW.findall(done.stdout[section.end():]) if section else []
    if not section or not rows:
        print("FAIL: `--install --hosts omp` printed no ok row for omp\n%s" % done.stdout)
        return 1
    print("OK: --install --hosts omp armed omp (%d ok rows) from the artifact" % len(rows))

    # The dsh host, whose launcher is the one wiring that is a real file on
    # Windows: a row reading ok for the `sh` wrapper there would report a host
    # that is armed and cannot start.
    dsh = run(setup_argv(py, setup, "--install", "--hosts", "dsh", "--no-deps"),
              tree, env)
    if dsh.returncode != 0:
        print("FAIL: --install --hosts dsh exited %d\n%s" % (dsh.returncode, dsh.stdout))
        return 1
    entry = launcher_entry(home)
    if not os.path.exists(entry):
        print("FAIL: --install --hosts dsh wired no %s\n%s" % (entry, dsh.stdout))
        return 1
    # Windows gets a real .cmd, not the relay a symlink-less install would leave:
    # a `/bin/sh` one-liner there is a file cmd.exe cannot start
    if os.name == "nt" and (os.path.islink(entry) or not os.path.isfile(entry)):
        print("FAIL: %s is not the real .cmd this platform needs\n%s"
              % (entry, dsh.stdout))
        return 1
    if os.name != "nt" and not os.path.islink(entry):
        print("FAIL: %s is not a link to the sh launcher\n%s" % (entry, dsh.stdout))
        return 1
    row = launcher_row(dsh.stdout)
    launcher = "tezgah-dsh.cmd" if os.name == "nt" else "tezgah-dsh"
    label = "dsh launcher on PATH (~/.local/bin/%s -> %s)" % (
        os.path.basename(entry), launcher)
    if not row.strip().startswith("ok") or label not in row:
        print("FAIL: the dsh launcher row does not read ok for the launcher this "
              "platform wired (%s): %r\n%s" % (label, row, dsh.stdout))
        return 1
    print("OK: --install --hosts dsh wired %s and its row names %s"
          % (entry, launcher))
    if os.name == "nt" and run_windows_launcher(env, home, tree):
        return 1

    version = run(setup_argv(py, setup, "--version"), tree, env)
    printed = version.stdout.strip().splitlines()
    if version.returncode != 0 or not printed or printed[-1] == "unknown":
        print("FAIL: --version answered %r on an unpacked tree (exit %d)"
              % (version.stdout.strip(), version.returncode))
        return 1
    print("OK: --version -> %s (no .git, no .claude-plugin)" % printed[-1])
    return 0


if __name__ == "__main__":
    sys.exit(main())
