"""Heredoc vectors measured against the bash that would run them.

The gate's heredoc reader (`hooks/tezgah_integrity._heredocs` and its opencode
mirror) decides which lines of a command are heredoc body. A line it calls body
is hidden from every rule, so a reader that disagrees with bash in that
direction lets `git commit --no-verify` through. Each review round of
2026-10-02 found such a shape by reasoning, and each was settled by running it
through /bin/bash 3.2. Bash 5.x parses a command substitution recursively, so a
vector can differ there; CI's ubuntu legs run the same check on bash 5.

`bash_runs_commit` executes a vector under the `bash` on PATH with `git`
shimmed to print RAN, stdin closed, so the answer is what bash does, not what a
reader of the grammar expects.
"""
import os
import shutil
import subprocess
import tempfile

COMMIT = "git commit --no-verify -m x"

# Shapes where a reader can take a line bash runs for heredoc body. The test
# requires the gate to refuse every one bash actually runs the commit in.
EXPOSED = (
    "git commit --no-verify -m x",
    # quoted, commented and here-string markers are not operators (review R1)
    "echo \"<<'X'\"\n%s\nX" % COMMIT,
    "ls # <<'X'\n%s\nX" % COMMIT,
    "grep x <<< 'X'\n%s\nX" % COMMIT,
    # arithmetic shifts are not heredocs (review S1)
    "echo $((1<<2))\n%s\n2" % COMMIT,
    "(( a = 1 <<b ))\n%s\nb" % COMMIT,
    "f() ((x<<2))\n%s" % COMMIT,
    "case a in a) ((y<<2));; esac\n%s" % COMMIT,
    "echo $[1<<2]\n%s" % COMMIT,
    "echo ${x:-<<EOF}\n%s" % COMMIT,
    "echo \"`echo \"<<X\"`\"\n%s\nX" % COMMIT,
    # a body starts at a newline token of the operator's own frame (consult)
    "cat <<X \"a\nb\"; %s\nbody\nX" % COMMIT,
    "cat <<X 'a\nb'; %s\nbody\nX" % COMMIT,
    "cat <<X $((1\n+1)); %s\nbody\nX" % COMMIT,
    "cat <<X $(echo a\necho b); %s\nbody\nX" % COMMIT,
    "echo $(cat <<X); echo $(true\n%s\nX\n)" % COMMIT,
    "echo \"$(cat <<X)\"; echo \"$(true\n%s\nX\n)\"" % COMMIT,
    "echo $(cat <<X)\n%s\nX" % COMMIT,
    "cat <<X # don't\nbody\nX\n%s" % COMMIT,
)

# Real heredoc bodies that mention the commit: bash runs none of them, and the
# gate must not read a body as a command (review S2: the usual commit-message
# shape was refused).
HIDDEN = (
    "git commit -m \"$(cat <<'EOF'\nfix: gate\n\n%s\nEOF\n)\"" % COMMIT,
    "git commit -F - <<'MSG'\n%s\nMSG" % COMMIT,
    "cat <<'EOF'\n%s\nEOF" % COMMIT,
    "(cat <<EOF\n%s\nEOF\n)" % COMMIT,
    "x=`cat <<EOF\n%s\nEOF\n`" % COMMIT,
    "diff <(cat <<EOF\n%s\nEOF\n) /dev/null" % COMMIT,
)


def bash():
    """The `bash` on PATH: the one a host's shell tool runs."""
    return shutil.which("bash")


def bash_version():
    out = subprocess.run([bash(), "-c", "echo $BASH_VERSION"],
                         capture_output=True, text=True, timeout=10)
    return out.stdout.strip()


def bash_runs_commit(command):
    """True when bash executes a `git ... --no-verify` call in `command`."""
    shim = tempfile.mkdtemp()
    try:
        git = os.path.join(shim, "git")
        with open(git, "w", encoding="utf-8") as fh:
            # only the bypass invocation counts: the outer `git commit -m
            # "$(cat <<EOF ...)"` of a message vector runs too, without the flag
            # and only as a whole argument, not a word inside the message
            fh.write('#!/bin/sh\nfor a in "$@"; do\n'
                     '  [ "$a" = --no-verify ] && echo RAN\ndone\nexit 0\n')
        os.chmod(git, 0o755)
        env = dict(os.environ, PATH=shim + os.pathsep + os.environ.get("PATH", ""))
        out = subprocess.run([bash(), "-c", command], capture_output=True,
                             text=True, env=env, cwd=shim,
                             stdin=subprocess.DEVNULL, timeout=10)
        return "RAN" in out.stdout
    finally:
        shutil.rmtree(shim, ignore_errors=True)
