"""One interpreter, resolved in one place: the manifest token, the adapter
resolvers and `tezgah_paths.python_cmd()` answer the same question, and no file
names an interpreter of its own.

The bug this guards is a literal that comes back into a file, so the check runs
over the real files rather than a copy of their text: a stale `python3` on disk is
what must fail here, not a stale string in this test.

Two rules, one per kind of file:

- A manifest or template (`hooks/hooks.json`, `hosts/dsh/hooks.json`,
  `hosts/cursor/hooks.json`) carries the shell expansion
  `"${TEZGAH_PYTHON:-python3}"` as its interpreter. `TEZGAH_PYTHON` is the runtime
  override - the one name every installer line and every adapter resolves through,
  and the name a user sets to pin an interpreter that is not on PATH. `python3`
  survives only as that expansion's documented default, and anywhere else in a
  command it fails.
- An adapter (`hosts/omp/tezgah-hook.ts.in`, `hosts/opencode/plugins/tezgah.js`,
  `hosts/opencode/tui/tezgah-tui.tsx`, `hosts/dsh/statusline/lib/index.js`)
  resolves the interpreter inside its own
  `pythonBin()` - one candidate list, the override first - and every
  `spawn`-shaped call site (`spawn`, `spawnSync`, `execFile`, `execFileSync`)
  passes that resolution. A python
  literal outside `pythonBin()` fails, and so does a call site that names one.
  The one exception is `python3?`: a regex quantifier can only be matching the
  text of a command, never starting one.

What this cannot settle here: how a host invokes a command string on Windows, so
the manifest token is proven against `sh -c` only (the shell the dsh bridge runs
its own manifest with - tests/test_dsh_hooks.DshLedger). The adapters need no
such proof: each resolves a name and hands it to the OS, which is one call on
every platform.
"""
import json
import os
import re
import shlex
import subprocess
import sys
import unittest
from unittest import mock

import support
from support import TempHome

sys.path.insert(0, support.HOOKS)
import tezgah_paths as tp  # noqa: E402

STATUSLINE = os.path.join(support.REPO, "hosts", "dsh", "statusline", "lib",
                          "index.js")
TUI = os.path.join(support.REPO, "hosts", "opencode", "tui", "tezgah-tui.tsx")
PATHS_MODULE = os.path.join(support.HOOKS, "tezgah_paths.py")
# The interpreter token a host runs its hook through, and the override inside it.
TOKEN = '"${TEZGAH_PYTHON:-python3}"'
OVERRIDE = "TEZGAH_PYTHON"
# An adapter's resolver, and the name it is reached by at every call site.
ADAPTERS = {support.OMP_EXTENSION: "pythonBin",
            support.OPENCODE_PLUGIN: "pythonBin",
            TUI: "pythonBin",
            STATUSLINE: "pythonBin"}
MANIFESTS = [os.path.join(support.HOOKS, "hooks.json"),
             os.path.join(support.REPO, "hosts", "dsh", "hooks.json"),
             os.path.join(support.REPO, "hosts", "cursor", "hooks.json")]
CALL = re.compile(r"\b(?:spawnSync|spawn|execFileSync|execFileAsync|execFile)\s*\(")
LITERAL = re.compile(r"python3")
# A command's leading env assignment (dsh declares its unobservable outcome this
# way) is not the interpreter: only what follows it is.
ENV_PREFIX = re.compile(r"^[A-Z_][A-Z0-9_]*=\S+\s+")


def text(path):
    with open(path, encoding="utf-8") as fh:
        return fh.read()


def line_of(src, index):
    return src.count("\n", 0, index) + 1


def definition(src, marker, closer):
    """The line range `marker`'s definition occupies: from the marker to the first
    piece `closer` matches after it - a column-0 `}` for the adapters, the next
    `def` for the Python module. The rule below is about where a literal may live,
    so it is checked against the real definition rather than a guess at its end."""
    start = src.index(marker)
    end = closer.search(src, start)
    end = len(src) if end is None else end.start()
    return line_of(src, start), line_of(src, end)


def first_arg(src, start):
    """The first argument of a call whose `(` ends at `start`.

    Scanned rather than matched: `spawn(pythonBin(), argv)` and an argument that
    is itself a call have to answer with the whole expression, and a comma inside
    it (or inside a string in it) is not the argument's end."""
    depth, i, out = 0, start, []
    while i < len(src):
        ch = src[i]
        if ch in "\"'`":
            end = src.find(ch, i + 1)
            end = len(src) if end < 0 else end + 1
            out.append(src[i:end])
            i = end
            continue
        if ch in "([{":
            depth += 1
        elif ch in ")]}":
            if depth == 0:
                break
            depth -= 1
        elif ch == "," and depth == 0:
            break
        out.append(ch)
        i += 1
    return "".join(out).strip()


def call_sites(src):
    """The index of every `spawn(...)`-shaped call in code.

    Whole comments and strings are skipped, because a sentence about spawning
    something is not a call site and a test that reads it as one reports a
    failure nobody can fix. Regex literals are not tracked: a pattern matching the
    text of a call is the one place a call could hide, and these three files have
    none."""
    i, n = 0, len(src)
    while i < n:
        two = src[i:i + 2]
        if two == "//":
            end = src.find("\n", i)
            i = n if end < 0 else end
        elif two == "/*":
            end = src.find("*/", i + 2)
            i = n if end < 0 else end + 2
        elif src[i] in "\"'`":
            end = src.find(src[i], i + 1)
            i = n if end < 0 else end + 1
        elif CALL.match(src, i):
            yield i
            i = CALL.match(src, i).end()
        else:
            i += 1


class ManifestInterpreter(unittest.TestCase):
    """Every command a host is armed with reaches python through the override."""

    def commands(self, path):
        """Every command in one manifest: the Claude shape nests a `hooks` list
        under the event, cursor's template puts `command` on the event entry."""
        with open(path) as fh:
            groups = json.load(fh)["hooks"]
        for event, entries in groups.items():
            for entry in entries:
                for hook in entry.get("hooks") or [entry]:
                    if "command" in hook:
                        yield event, hook["command"]

    def test_each_command_starts_with_the_override_token(self):
        for path in MANIFESTS:
            for event, cmd in self.commands(path):
                rest = ENV_PREFIX.sub("", cmd)
                self.assertTrue(rest.startswith(TOKEN),
                                "%s %s: %s" % (path, event, cmd))
                # `python3` may survive only inside the expansion, so a command
                # that carried the token and then named an interpreter anyway is
                # caught here as well
                self.assertNotIn("python3", rest.replace(TOKEN, ""),
                                 "%s %s: %s" % (path, event, cmd))

    def test_every_file_carries_the_same_token(self):
        # Claude, dsh and cursor are armed by three different installers; one
        # token means one override name to document and one to set.
        seen = {ENV_PREFIX.sub("", cmd).split()[0]
                for path in MANIFESTS for _, cmd in self.commands(path)}
        self.assertEqual(seen, {TOKEN})

    def test_the_token_expands_in_a_posix_shell(self):
        # A host runs this string through a shell (the dsh bridge does, and
        # tests/test_dsh_hooks.DshLedger runs the manifest that way), so the
        # expansion - not a comment - is what makes the override real. The pinned
        # value carries a space, which is what the quotes are for.
        token = ENV_PREFIX.sub("", next(self.commands(MANIFESTS[0]))[1]).split()[0]
        env = {k: v for k, v in os.environ.items() if k != OVERRIDE}
        out = subprocess.run(["sh", "-c", "printf %s " + token], env=env,
                             capture_output=True, text=True, timeout=60)
        self.assertEqual(out.stdout, "python3", out.stderr)
        pinned = "/opt/tezgah py/python"
        env[OVERRIDE] = pinned
        out = subprocess.run(["sh", "-c", "printf %s " + token], env=env,
                             capture_output=True, text=True, timeout=60)
        self.assertEqual(out.stdout, pinned, out.stderr)


class AdapterInterpreter(unittest.TestCase):
    """Every adapter starts python through its own resolver, and names it once."""

    def test_every_call_site_starts_the_resolver(self):
        for path, resolver in ADAPTERS.items():
            src = text(path)
            for index in call_sites(src):
                arg = first_arg(src, CALL.match(src, index).end())
                self.assertIn(resolver + "(", arg,
                              "%s:%d starts an interpreter without %s(): %s"
                              % (path, line_of(src, index), resolver, arg))

    def test_a_python_literal_lives_in_the_resolver_only(self):
        for path, resolver in ADAPTERS.items():
            src = text(path)
            start, end = definition(src, "function " + resolver, re.compile(r"\n\}"))
            quoted = sum(1 for m in LITERAL.finditer(src)
                         if src[m.start() - 1:m.start()] in "\"'")
            # one candidate list, in the resolver, and nothing that spelled an
            # interpreter somewhere else
            self.assertEqual(quoted, 1,
                             "%s quotes %d interpreter literals" % (path, quoted))
            inside = 0
            for match in LITERAL.finditer(src):
                line = line_of(src, match.start())
                if start <= line <= end:
                    inside += 1
                    continue
                # `python3?` is a regex quantifier: that can only be matching the
                # text of a command, never starting one.
                self.assertEqual("?", src[match.end():match.end() + 1],
                                 "%s:%d names an interpreter outside %s()"
                                 % (path, line, resolver))
            self.assertEqual(inside, 1,
                             "%s spells %s outside %s()" % (path, LITERAL.pattern,
                                                            resolver))
            # the override has to be read inside the resolver, not pasted beside
            # it: a file that names it in a comment and ignores it in code is the
            # same bug as a hard-coded literal
            self.assertIn("process.env." + OVERRIDE,
                          "\n".join(src.splitlines()[start - 1:end]), path)


class PythonModuleInterpreter(unittest.TestCase):
    """The module that owns the rule names an interpreter in that rule only."""

    def test_the_module_spells_python_only_inside_python_cmd(self):
        src = text(PATHS_MODULE)
        start, end = definition(src, "def python_cmd():",
                                re.compile(r"\ndef hook_command"))
        for match in LITERAL.finditer(src):
            line = line_of(src, match.start())
            if line == 1:
                continue  # the shebang: how a user runs this module by hand
            self.assertTrue(start <= line <= end,
                            "%s:%d names an interpreter outside python_cmd()"
                            % (PATHS_MODULE, line))


class Resolver(TempHome):
    """`python_cmd()`'s own order, exercised in this process."""

    def path_with(self, *names):
        """A PATH directory holding exactly these executable names."""
        d = os.path.join(self.home, "bin-" + ("-".join(names) or "empty"))
        os.makedirs(d, exist_ok=True)
        for name in names:
            path = os.path.join(d, name)
            with open(path, "w") as fh:
                fh.write("#!/bin/sh\nexit 1\n")
            os.chmod(path, 0o755)
        return d

    def lookup(self, path_dir=None):
        """`python_cmd()` with nothing pinned, no absolute interpreter of its own,
        and a PATH the test owns: the state a hook on a bare machine starts in."""
        env = {k: v for k, v in os.environ.items() if k != OVERRIDE}
        if path_dir is not None:
            env["PATH"] = path_dir
        with mock.patch.dict(os.environ, env, clear=True), \
                mock.patch.object(tp.sys, "executable", ""), \
                mock.patch.object(tp, "USER_BINS", ()):
            return tp.python_cmd()

    def test_the_override_wins_and_is_taken_as_given(self):
        # An absolute path outside PATH and a name only the user knows are both
        # the answer: starting a different interpreter than the one pinned is a
        # worse failure than not starting one.
        for pinned in ("/opt/tezgah/python3.12", "python3.12"):
            with mock.patch.dict(os.environ, {OVERRIDE: pinned}):
                self.assertEqual(tp.python_cmd(), pinned)

    def test_the_running_interpreter_is_used_when_nothing_is_pinned(self):
        env = {k: v for k, v in os.environ.items() if k != OVERRIDE}
        with mock.patch.dict(os.environ, env, clear=True), \
                mock.patch.object(tp.sys, "executable", sys.executable):
            self.assertEqual(tp.python_cmd(), sys.executable)

    def test_the_platform_names_are_probed_in_the_order_they_answer_in(self):
        for names, expected in ((["python3", "python", "py"], "python3"),
                                (["python", "py"], "python"),
                                (["py"], "py")):
            with self.subTest(names=names):
                d = self.path_with(*names)
                self.assertEqual(self.lookup(d), os.path.join(d, expected))

    def test_a_machine_with_none_of_them_keeps_the_documented_name(self):
        # The caller has to have something to run: a named "python3: not found"
        # reads, an empty command does not.
        self.assertEqual(self.lookup(self.path_with()), "python3")

    def test_hook_command_quotes_both_halves(self):
        script = "/opt/My Tools/hooks/projects-stop.py"
        with mock.patch.dict(os.environ, {OVERRIDE: "/opt/py thon/python"}):
            cmd = tp.hook_command(script)
        self.assertEqual(cmd, '"%s" "%s"' % ("/opt/py thon/python", script))
        self.assertEqual(shlex.split(cmd), ["/opt/py thon/python", script])

    def test_hook_command_carries_the_resolved_interpreter(self):
        env = {k: v for k, v in os.environ.items() if k != OVERRIDE}
        with mock.patch.dict(os.environ, env, clear=True):
            self.assertEqual(shlex.split(tp.hook_command("/x/hook.py")),
                             [tp.python_cmd(), "/x/hook.py"])


if __name__ == "__main__":
    unittest.main()
