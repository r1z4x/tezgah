"""A bash-oracle fuzzer for the shell readers (plan 054).

Seeded lines are drawn from the hand vectors' grammar - the gate-01 prefixes,
quotes including `$'...'`, comments, redirects, heredocs, command and backtick
substitutions, and every separator - and each is run by the real `bash` with a
hermetic PATH holding one stub per program word. A stub logs its name and
exits 0 on the first run and 1 on the second, so a branch `&&` or `||` skips on
one run is taken on the other; the union of both logs is what bash ran.

Two readers are compared with it:
- `programs`: `tezgah_context.shell_programs`, which names the programs a line
  runs. `hidden` is a program bash ran that the reader does not name; `phantom`
  is one it names that bash never ran.
- `mask`: `tezgah_integrity.mask`, the text every shell deny rule matches. A
  program bash ran whose name `mask` blanked everywhere is `hidden` from every
  rule - the gate-01 fault class.

Each grammar position holds a program name of its own (`s1` only ever sits in
single quotes, `h2` only in an unquoted heredoc body's `$( )`), so the name in
a disagreement is its class: one shape rather than one line.

    python3 tests/fuzz_shell.py --seed 1 --lines 10000
"""
import argparse
import functools
import json
import os
import random
import shutil
import subprocess
import sys
import tempfile
from collections import Counter

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "hooks"))
import tezgah_context as tc  # noqa: E402
import tezgah_integrity as ti  # noqa: E402

# Every word is a stub, so each exits 0 on one run and 1 on the other - a
# builtin would always succeed and hide the branch after its `||`.
PROGRAMS = ("p0", "p1", "curl", "ls", "cat")
# (feature, argument text): the gate-01 prefixes the old masker misread, the
# quotes that hold a name bash does not run, the substitutions that run one,
# and the redirects whose target is not a program
ARGS = (
    ("plain", "x"),
    ("squote", "'q s1'"),
    ("dquote", '"q d1 \\" d2"'),
    ("ansi", "$'it\\'s a1'"),
    ("hash", "a#b"),
    ("url", "https://example.com/u1"),
    ("glob", "src/*.py"),
    ("glob", "lib/*/"),
    ("backslash", "'x\\'"),
    ("redirect", "> r1"),
    ("redirect", "2>&1"),
    ("redirect", "&> r2"),
    ("redirect", "< /dev/null"),
    ("subst", "$(c1 x)"),
    ("backtick", "`b1`"),
)
STUBS = PROGRAMS + ("s1", "d1", "d2", "a1", "u1", "r1", "r2", "c1", "b1",
                    "m1", "h1", "h2", "h3", "h4")
SEPARATORS = ("; ", " && ", " || ", " | ", "\n", " & ")


def bash():
    return shutil.which("bash")


def bash_version():
    out = subprocess.run([bash(), "-c", "echo $BASH_VERSION"],
                         capture_output=True, text=True, timeout=10)
    return out.stdout.strip()


def _command(rnd):
    words = ["X=1"] if rnd.random() < 0.15 else []
    words.append(rnd.choice(PROGRAMS))
    words += [rnd.choice(ARGS)[1] for _ in range(rnd.randint(0, 3))]
    return " ".join(words)


def line(rnd):
    """One generated line: up to four commands, then a comment or a heredoc."""
    parts = [_command(rnd)]
    for _ in range(rnd.randint(0, 3)):
        parts += [rnd.choice(SEPARATORS), _command(rnd)]
    text = "".join(parts)
    roll = rnd.random()
    if roll < 0.1:
        text += " # m1 x"
    elif roll < 0.15:
        text += "\ncat <<E\nh1 body\n$(h2)\nE"
    elif roll < 0.2:
        text += "\ncat <<'E'\nh3 body\n$(h4)\nE"
    return text


class Oracle:
    """A sandbox with one stub per program word on a PATH of its own."""

    def __init__(self):
        self.root = tempfile.mkdtemp()
        self.bin = os.path.join(self.root, "bin")
        os.mkdir(self.bin)
        for name in STUBS:
            path = os.path.join(self.bin, name)
            with open(path, "w", encoding="utf-8") as fh:
                fh.write('#!/bin/sh\necho %s >> "$FUZZ_LOG"\nexit "$FUZZ_CODE"\n'
                         % name)
            os.chmod(path, 0o755)
        self.log = os.path.join(self.root, "log")

    def close(self):
        shutil.rmtree(self.root, ignore_errors=True)

    def valid(self, text):
        out = subprocess.run([bash(), "-n", "-c", text], capture_output=True,
                             stdin=subprocess.DEVNULL, timeout=10)
        return out.returncode == 0

    def ran(self, text):
        """The program words bash ran over the two runs."""
        names = set()
        for code in ("0", "1"):
            open(self.log, "w").close()
            env = {"PATH": self.bin, "FUZZ_LOG": self.log, "FUZZ_CODE": code,
                   "HOME": self.root}
            subprocess.run([bash(), "--norc", "--noprofile", "-c", text + "\nwait"],
                           capture_output=True, stdin=subprocess.DEVNULL,
                           env=env, cwd=self.root, timeout=10)
            with open(self.log, encoding="utf-8") as fh:
                names.update(fh.read().split())
        return names


def _visible(name, masked):
    return any(w.strip("`$()") == name for w in masked.replace(";", " ").split())


def disagreements(text, ran, js=None):
    """`reader:direction:program` for every way the readers differ from bash.
    With `js` (the plugin's {mask, programs} for this line) the readers are the
    opencode ports, prefixed `js-`, plus `js-parity:<reader>` where the port's
    answer is not the core's."""
    py_named, py_masked = tc.shell_programs(text), ti.mask(text)
    if js is None:
        named, masked, tag, parity = py_named, py_masked, "", []
    else:
        named, masked, tag = js["programs"], js["mask"], "js-"
        parity = ([] if named == py_named else ["js-parity:programs"]) + (
            [] if masked == py_masked else ["js-parity:mask"])
    named = set(named) & set(STUBS)
    return (["%sprograms:hidden:%s" % (tag, p) for p in sorted(ran - named)]
            + ["%sprograms:phantom:%s" % (tag, p) for p in sorted(named - ran)]
            + ["%smask:hidden:%s" % (tag, p) for p in sorted(ran)
               if not _visible(p, masked)] + parity)


PLUGIN = os.path.join(os.path.dirname(HERE), "hosts", "opencode", "plugins",
                      "tezgah.js")


def js_read(texts):
    """The opencode plugin's {mask, programs} for each line, one node process."""
    out = subprocess.run([shutil.which("node"),
                          os.path.join(HERE, "_fuzz_shell_reader.mjs"), PLUGIN],
                         input=json.dumps(texts), capture_output=True, text=True,
                         timeout=600, check=True)
    return json.loads(out.stdout)


@functools.lru_cache(maxsize=None)
def bash_pass(seed, lines):
    """((line, frozenset of programs bash ran), ...) for the valid lines, and the
    invalid-line count. Cached, so the core and the JS legs share one bash run."""
    rnd = random.Random(seed)
    oracle = Oracle()
    seen, invalid = [], 0
    try:
        for _ in range(lines):
            text = line(rnd)
            if not oracle.valid(text):
                invalid += 1
                continue
            seen.append((text, frozenset(oracle.ran(text))))
    finally:
        oracle.close()
    return tuple(seen), invalid


def run(seed, lines, js=False):
    """(Counter of lines per disagreement class, invalid-line count, one example
    line per class). `js` reads each line with the opencode plugin's ports."""
    seen, invalid = bash_pass(seed, lines)
    reads = js_read([t for t, _ in seen]) if js else [None] * len(seen)
    classes, examples = Counter(), {}
    for (text, ran), read in zip(seen, reads):
        for key in disagreements(text, ran, read):
            classes[key] += 1
            examples.setdefault(key, text)
    return classes, invalid, examples


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--lines", type=int, default=10000)
    ap.add_argument("--js", action="store_true",
                    help="read with the opencode plugin's ports (needs node)")
    ap.add_argument("--strict", action="store_true",
                    help="exit 1 on any disagreement class (the CI leg)")
    args = ap.parse_args(argv)
    classes, invalid, examples = run(args.seed, args.lines, args.js)
    print("bash %s, seed %d, %d lines, %d invalid, reader %s"
          % (bash_version(), args.seed, args.lines, invalid,
             "opencode plugin (node)" if args.js else "core (python)"))
    for key, n in classes.most_common():
        print("%6d  (%.1f per 10^4)  %s\n        e.g. %r"
              % (n, n * 1e4 / args.lines, key, examples[key]))
    return 1 if args.strict and classes else 0


if __name__ == "__main__":
    sys.exit(main())
