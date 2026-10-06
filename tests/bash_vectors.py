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
    "f() ((x<<2))\n%s\n2" % COMMIT,
    "case a in a) ((y<<2));; esac\n%s\n2" % COMMIT,
    # `)` ends a case pattern and `f()`, so a command starts after it
    "case a in a) a[1<<2]=5\n;; esac\n%s\n2]=5" % COMMIT,
    # a subscript inside a compound assignment has no name before its `[`
    "a=([1<<2]=5)\n%s\n2]=5" % COMMIT,
    "echo $[1<<2]\n%s\n2]" % COMMIT,
    "echo ${x:-<<EOF}\n%s\nEOF}" % COMMIT,
    # `for ((`, `$[ ]`, `${ }` and an array subscript are arithmetic or
    # expansion contexts too: their `<<` is a shift, never a heredoc
    "for ((i=1<<2;i<5;i++)); do :; done\n%s\n2" % COMMIT,
    "x=ab; echo ${x:0:1<<1}\n%s\n1}" % COMMIT,
    "a[1<<2]=5\n%s\n2]=5" % COMMIT,
    "echo \"`echo \"<<X\"`\"\n%s\nX" % COMMIT,
    # a heredoc opened in a backtick pair that closes on its own line gets an
    # empty body: the next lines run
    "v=`cat <<X `\n%s\nX" % COMMIT,
    "v=`cat <<X;`\n%s\nX" % COMMIT,
    # an unquoted heredoc body expands `$( )` and backticks: bash runs them
    "cat <<EOF\n$(%s)\nEOF" % COMMIT,
    "cat <<EOF\n`%s`\nEOF" % COMMIT,
    # a body starts at a newline token of the operator's own frame (consult)
    "cat <<X \"a\nb\"; %s\nbody\nX" % COMMIT,
    "cat <<X 'a\nb'; %s\nbody\nX" % COMMIT,
    "cat <<X $((1\n+1)); %s\nbody\nX" % COMMIT,
    "cat <<X $(echo a\necho b); %s\nbody\nX" % COMMIT,
    "echo $(cat <<X); echo $(true\n%s\nX\n)" % COMMIT,
    "echo \"$(cat <<X)\"; echo \"$(true\n%s\nX\n)\"" % COMMIT,
    "echo $(cat <<X)\n%s\nX" % COMMIT,
    "cat <<X # don't\nbody\nX\n%s" % COMMIT,
    # review round 2 of an internal plan: each hid a command from a frame-tracking
    # reader (P1-P4 pre-existing, N1-N3 introduced by the round-1 frames)
    "x=`cat <<EOF\nhi\nEOF`\n%s\nEOF" % COMMIT,
    "cat <(cat <<EOF\nhi\nEOF) >/dev/null\n%s\nEOF" % COMMIT,
    "cat <<EOF\n$(\n%s\n)\nEOF" % COMMIT,
    "cat <<EOF\n`\n%s\n`\nEOF" % COMMIT,
    "x=\"`cat <<EOF\nhi\nEOF`\"\n%s\nEOF" % COMMIT,
    "((cd . && cat <<X\n%s\nX\n) ; true)" % COMMIT,
    "cat <<EOF \"a=(\" [x\nEOF\n]\n%s\nEOF" % COMMIT,
    "a=(\n[1<<2]=5\n)\n%s\n2]=5" % COMMIT,
    # a quoted heredoc is data, and the line after its terminator is not
    "cat > f <<'EOF'\ndata\nEOF\n%s" % COMMIT,
)

# The EXPOSED vectors bash 5.2.37 keeps as body: a heredoc opened in a closed
# `$( )` takes its body from the outer lines there, so the commit after it does
# not run (measured 2026-10-03 in python:3.12-slim; bash 3.2 runs all of them).
# A vector outside this set that stops running is lost evidence, not a version
# difference, and fails the test.
BODY_ON_BASH5 = frozenset((
    "echo $(cat <<X); echo $(true\n%s\nX\n)" % COMMIT,
    "echo \"$(cat <<X)\"; echo \"$(true\n%s\nX\n)\"" % COMMIT,
    "echo $(cat <<X)\n%s\nX" % COMMIT,
))

# The EXPOSED vectors bash 3.2 does not run: a multi-line compound assignment
# is a syntax error there, and bash 5.2 runs the commit after it.
NOT_RUN_ON_BASH3 = frozenset((
    "a=(\n[1<<2]=5\n)\n%s\n2]=5" % COMMIT,
))

# Heredoc bodies the gate hides: only the shapes the reader fully follows - a
# quoted tag on a plain line, and the commit-message argument `"$(cat <<'EOF'`
# closed by `EOF` then `)"` or by `EOF)"` (tezgah_integrity._heredocs). Bash
# runs none of them, and the gate must not read the body as a command.
HIDDEN = (
    "git commit -m \"$(cat <<'EOF'\nfix: gate\n\n%s\nEOF\n)\"" % COMMIT,
    "git commit -F - <<'MSG'\n%s\nMSG" % COMMIT,
    "cat <<'EOF'\n%s\nEOF" % COMMIT,
    "cat <<\\EOF\n%s\nEOF" % COMMIT,
    "git commit -m \"$(cat <<'EOF'\nfix: never use %s here\nEOF)\"" % COMMIT,
    "git commit -m \"$(cat <<'EOF'\na %s\nEOF\n)\" && "
    "git commit -m \"$(cat <<'EOF'\nb %s\nEOF\n)\"" % (COMMIT, COMMIT),
)

# Data the gate shows anyway: bash runs no commit in these, and the reader no
# longer decides where an unquoted body, a subshell, a backtick or a process
# substitution ends, so it refuses them. Pinned so the trade is visible: a
# false refusal of data is the cost of never hiding a command.
ACCEPTED_REFUSALS = (
    "cat <<EOF\n%s\nEOF" % COMMIT,
    "(cat <<EOF\n%s\nEOF\n)" % COMMIT,
    "x=`cat <<EOF\n%s\nEOF\n`" % COMMIT,
    "diff <(cat <<EOF\n%s\nEOF\n) /dev/null" % COMMIT,
    "((cd . && cat <<X) ; true)\n%s\nX" % COMMIT,
    "(cat <<'EOF'\n%s\nEOF\n)" % COMMIT,
)

# gate-01's prefixes (plan 054): bash reads a URL's `//`, a word's `#`, a
# `/* */` glob pair and `'x\'` as plain words, and a polyglot masker read them as
# a comment or an open string, blanking the command after them. `%s` is that
# command; the gate and its opencode mirror both test every wrap.
GATE01_WRAPS = ("curl -s https://example.com/health; %s",
                "echo a#b; %s",
                "ls src/*.py; %s; ls lib/*/",
                "echo 'x\\'; %s; echo '\\'")


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
