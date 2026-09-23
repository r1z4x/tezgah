"""hooks/tezgah_components.py: the manifest, pinned against its other halves.

The manifest restates three things the repository already decides, and each one
is asserted here against that other definition rather than trusted: the rule
labels (`hooks/tezgah_context.CORE_RULES`), which switches exist (the injection
itself, exercised in a temp HOME - never its source text), and which paths the
refinement loop may not touch (`hooks/tezgah_research.FROZEN_PATHS`). A manifest
entry that stops agreeing with its other half fails here in one direction, and a
rule that grows or loses a switch fails in the other.

One allowance is deliberate and named: a declared path the repository ignores
(the lessons ledger) is per-checkout state, so a fresh clone does not have it and
it is accepted as declared. Every other declared path has to exist.

Beside the manifest, `Tree` reads the tree those paths live in, because this
layer is wired by hand: a module nothing references, a top-level function nothing
calls, and an import that is neither stdlib nor a sibling are the three ways such
a layer rots without anything failing. Each check's escapes are named in the
class docstring, so its ceiling stays visible.
"""
import ast
import glob
import json
import os
import re
import subprocess
import sys
import unittest

import support
from support import TempHome, run_json

REPO = support.REPO
sys.path.insert(0, support.HOOKS)
import tezgah_components as components  # noqa: E402
import tezgah_context as context  # noqa: E402
import tezgah_policy as policy  # noqa: E402
import tezgah_research as research  # noqa: E402

FIELDS = ("key", "label", "files", "switch", "editable", "revert")
REVERTS = ("git", "snapshot")

# An open prompt: it arms no conditional rule, so the turn carries the reminder,
# the per-turn state and the off-list only.
PLAIN = "add a docstring to parse_quantity"

# One prompt per conditional rule, in the shape the shared hint table matches.
# Which wording arms what is `PROMPT_HINTS`' answer, not this file's, so the set
# is asserted to arm every conditional rule before it is used as a fixture.
TRIGGERS = ("Run a literature review and form a hypothesis. "
            "who calls calc_total? which feature should we build next. "
            "Which approach for the schema change? "
            "Bu ekranı daha kullanıcı dostu yap")


def git(*args):
    return subprocess.run(("git", "-C", REPO) + args, capture_output=True,
                          text=True)


def rows():
    """The manifest as it stands: read per call, so a check run against a
    mutated module is running the real assertion."""
    return list(components.COMPONENTS)


class Manifest(unittest.TestCase):
    """The manifest against the definitions it may not import."""

    def labels(self):
        return [c["label"] for c in rows()]

    def test_fields_and_unique_keys(self):
        manifest = rows()
        keys = [c["key"] for c in manifest]
        self.assertEqual(len(keys), len(set(keys)), "duplicate component keys")
        for c in manifest:
            self.assertEqual(sorted(c), sorted(FIELDS), c.get("key"))
            self.assertTrue(c["key"] and c["label"], c["key"])
            self.assertTrue(c["files"], c["key"])
            self.assertIsInstance(c["editable"], bool, c["key"])
            self.assertIsInstance(c["switch"], str, c["key"])
            self.assertIn(c["revert"], REVERTS, c["key"])
        self.assertEqual(components.keys(), keys)

    def test_every_rule_label_appears_exactly_once(self):
        rules = [key for key, _label in context.CORE_RULES]
        labels = self.labels()
        self.assertEqual(len(rules), len(set(rules)))
        for key in rules:
            self.assertEqual(labels.count(key), 1,
                             "%s is not owned by exactly one component: %s"
                             % (key, labels))
        # A component that owns no rule names a surface instead, so the surface
        # names can never shadow a rule and no rule key can be doubled up.
        extra = [lab for lab in labels if lab not in rules]
        self.assertEqual(len(extra), len(set(extra)), extra)

    def test_declared_paths_exist(self):
        ignored = []
        for c in rows():
            for path in c["files"]:
                full = os.path.join(REPO, path)
                if "*" in path:
                    self.assertTrue(glob.glob(full),
                                    "%s: %s matches no file" % (c["key"], path))
                elif os.path.exists(full):
                    continue
                elif git("check-ignore", "-q", path).returncode == 0:
                    ignored.append(path)  # per-checkout state, not content
                else:
                    self.fail("%s declares a path that does not exist: %s"
                              % (c["key"], path))
        # stated, not hidden: whatever the allowance covered is in the message
        self.assertLessEqual(len(ignored), 1,
                             "the ignored-path allowance grew: %s" % ignored)

    def test_editable_agrees_with_the_frozen_set(self):
        for c in rows():
            frozen = [p for p in c["files"] if research._frozen(p)]
            self.assertEqual(c["editable"], not frozen,
                             "%s: editable=%s, frozen=%s"
                             % (c["key"], c["editable"], frozen))
        # The frozen set has to actually appear, or `editable` is never
        # exercised: the three frozen files this layer's rules live in.
        named = {p for c in rows() for p in c["files"]}
        for path in ("hooks/tezgah_gate.py", "hooks/tezgah_integrity.py",
                     "hooks/tezgah_research.py"):
            self.assertIn(path, named, "%s is frozen but no component names it"
                          % path)

    def test_revert_mechanism_matches_what_git_can_reach(self):
        for c in rows():
            tracked = bool(git("ls-files", "--", *c["files"]).stdout.strip())
            if c["revert"] == "snapshot":
                self.assertFalse(tracked,
                                 "%s: git tracks %s, so git is its revert path"
                                 % (c["key"], c["files"]))
            else:
                self.assertTrue(tracked,
                                "%s: git tracks none of %s, so git is not its "
                                "revert path" % (c["key"], c["files"]))

    def test_importing_the_manifest_pulls_in_no_tezgah_module(self):
        """The research module imports this lazily, so the import must stay
        stdlib-only: the builder, the paths module and the research module are
        all a cost the caller did not ask for."""
        code = ("import json, sys\n"
                "sys.path.insert(0, %r)\n"
                "import tezgah_components\n"
                "print(json.dumps(sorted(m for m in sys.modules\n"
                "                        if m.split('.')[0] == 'tezgah_components'"
                " or m.startswith('tezgah_'))))\n" % support.HOOKS)
        proc = subprocess.run([sys.executable, "-c", code], capture_output=True,
                              text=True, cwd=REPO, timeout=60)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(json.loads(proc.stdout), ["tezgah_components"])


class Switches(TempHome):
    """The `switch` column against the injection that reads it."""

    def turn(self, cwd, prompt):
        out, proc = run_json([support.PROBE_CONTEXT],
                             {"fn": "context_for", "event": "user_prompt",
                              "cwd": cwd,
                              "payload": {"prompt": prompt,
                                          "session_id": "s-components"}},
                             env=self.env())
        self.assertEqual(proc.returncode, 0, proc.stderr)
        return out

    def session(self, cwd):
        out, proc = run_json([support.PROBE_CONTEXT],
                             {"fn": "context_for", "event": "session_start",
                              "cwd": cwd},
                             env=self.env())
        self.assertEqual(proc.returncode, 0, proc.stderr)
        return out

    def arm(self, repo, names):
        """Turn every named switch on: a `~/.config/tezgah` file, or - for a
        name that starts with a dot - the per-repo mark inside the repo."""
        for name in names:
            if name.startswith("."):
                self.touch(os.path.join(repo, name))
            else:
                self.touch(os.path.join(self.home, ".config", "tezgah", name))

    def switches(self):
        return sorted({c["switch"] for c in components.COMPONENTS} - {"none"})

    def test_the_off_list_names_every_switch_the_manifest_declares(self):
        switches = self.switches()
        self.assertTrue(switches, "no component declares a switch")
        repo = self.make_repo()
        self.assertNotIn("off this session", self.turn(repo, PLAIN))
        self.arm(repo, switches)
        out = self.turn(repo, PLAIN)
        self.assertIn("off this session", out)
        for name in switches:
            self.assertIn(name, out,
                          "%s is declared but the injection did not read it"
                          % name)

    def test_a_switch_drops_its_rule_and_none_leaves_its_rule_alone(self):
        conditional = set(policy.CONDITIONAL_KEYS)
        armed = context.classify_prompt(TRIGGERS)
        self.assertTrue(conditional <= armed,
                        "the trigger prompt arms %s, not %s"
                        % (sorted(armed), sorted(conditional)))
        repo = self.make_repo()
        rules = dict(context.CORE_RULES)
        before = {"session_start": self.session(repo),
                  "user_prompt": self.turn(repo, TRIGGERS)}
        self.arm(repo, self.switches())
        after = {"session_start": self.session(repo),
                 "user_prompt": self.turn(repo, TRIGGERS)}
        for c in rows():
            if c["label"] not in rules:
                continue
            label = rules[c["label"]]
            surface = "user_prompt" if c["label"] in conditional else "session_start"
            self.assertIn(label, before[surface],
                          "%s: %s is missing before any switch was set"
                          % (c["key"], c["label"]))
            if c["switch"] == "none":
                self.assertIn(label, after[surface],
                              "%s: no switch may drop the %s rule"
                              % (c["key"], c["label"]))
            else:
                self.assertNotIn(label, after[surface],
                                 "%s: %s did not drop the %s rule"
                                 % (c["key"], c["switch"], c["label"]))


# --- the tree the manifest's paths live in -----------------------------------
# The layer's files are wired by hand: nothing imports a hook, a script is
# reached by its path in a host manifest, and a helper is reached by a caller
# somewhere. Those facts are what `Tree` checks, and the escapes each check
# relies on are named in its docstring rather than left implicit.

SCAN_ROOTS = ("hooks", "hosts", "bin")
CORPUS_ROOTS = SCAN_ROOTS + ("tests",)
CODE_EXT = (".py", ".js", ".ts", ".tsx", ".mjs")
TEXT_EXT = CODE_EXT + (".json", ".md", ".in", ".txt")
# Called by the file's own `if __name__ == "__main__"` block, or by a host
# manifest that names the file: an entry point, not a helper nobody wired.
ENTRY_POINTS = ("main", "_main")
QUAL = re.compile(r"[A-Za-z0-9_][A-Za-z0-9_./\-]*")
IDENT = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")


def stem(path):
    base = os.path.basename(path)
    return base[:-3] if base.endswith(".py") else base


def source_of(path):
    with open(os.path.join(REPO, path), errors="replace") as fh:
        return fh.read()


def is_python(path, source):
    """Whether a file is Python: by extension, or by a shebang that names it.

    `bin/tezgah-dsh` is a `/bin/sh` wrapper, so it is a module nothing may stop
    referencing but has no `def`s and no imports to check."""
    if path.endswith(".py"):
        return True
    return "python" in (source.splitlines()[0] if source else "")


def tree_paths(roots):
    """Every file under `roots`, repository-relative.

    `bin/` is read whole: its scripts carry no extension and one of them is a
    shell wrapper. Elsewhere only the text extensions are, which skips a `.pyc`
    a stale `__pycache__` can still carry."""
    out = []
    for root in roots:
        for dirpath, dirnames, filenames in os.walk(os.path.join(REPO, root)):
            dirnames[:] = [d for d in dirnames if d != "__pycache__"]
            for name in filenames:
                if root == "bin" or os.path.splitext(name)[1] in TEXT_EXT:
                    out.append(os.path.relpath(os.path.join(dirpath, name), REPO))
    return sorted(set(out))


def code_names(path):
    """The identifiers `path` refers to.

    Python is parsed, so a name imported inside a multi-line `from x import (...)`
    or a split attribute chain counts, and so does a bare identifier held as a
    string - `getattr(module, "name")`, a dispatch dict, a command table - which
    is what keeps a helper reached by name rather than by call out of the
    no-caller scan. The host code is scanned for bare identifiers; a manifest
    returns nothing, because a manifest names paths and not functions."""
    try:
        source = source_of(path)
    except OSError:
        return set()
    ext = os.path.splitext(path)[1]
    if ext == ".py" or not ext:
        try:
            tree = ast.parse(source)
        except SyntaxError:
            return set()
        names = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                names.update(a.name.split(".")[0] for a in node.names)
            elif isinstance(node, ast.ImportFrom):
                names.update(a.name for a in node.names)
            elif isinstance(node, ast.Name):
                names.add(node.id)
            elif isinstance(node, ast.Attribute):
                names.add(node.attr)
            elif (isinstance(node, ast.Constant)
                  and isinstance(node.value, str) and node.value.isidentifier()):
                names.add(node.value)
        return names
    return set(IDENT.findall(source)) if ext in CODE_EXT else set()


class Tree(unittest.TestCase):
    """What a hand-wired layer cannot state in a type: every module and every
    top-level function in `hooks/`, `hosts/` and `bin/` is reachable from
    somewhere, and every import resolves to the stdlib or a sibling.

    The ceiling, stated so it cannot grow quietly:

    - `__dunder__` names and `main`/`_main` are exempt: the file's own
      `if __name__ == "__main__"` block calls `main`, and a host manifest
      (`hooks/hooks.json`, `hosts/*/hooks.json`, the manifest in this file)
      reaches the file by path. Those manifests name files, not functions, which
      is why the exemption is by name instead of by parsing them.
    - A name is matched, not resolved: a def whose name also occurs anywhere in
      the reference corpus reads as referenced. So a name reached by string is
      covered (an identifier held in a string counts, which is what `getattr`,
      a dispatch dict or a command table relies on), at the cost that a **dead**
      helper whose name collides with a live one, or with a bare identifier
      string, is missed - no such case exists on this tree. Resolving real
      callers is the code graph's job (`codegraph callers`); this is the cheap
      guard that runs before every commit.
    - `tests/` is a reference corpus, never a candidate: a `def` there is a test
      helper by construction, and a test-only module is not dead.
    - One non-Python file exists (`bin/tezgah-dsh`, a `/bin/sh` wrapper), so the
      import check skips it: it imports nothing. A file that claims python and
      does not parse fails instead of being skipped.
    """

    def corpus(self):
        return tree_paths(CORPUS_ROOTS)

    def candidates(self):
        """The tree's modules: every `*.py` and every `bin/` script."""
        return [p for p in tree_paths(SCAN_ROOTS)
                if p.endswith(".py") or os.path.dirname(p) == "bin"]

    def python_targets(self):
        """Exactly the set CONTRIBUTING.md's stdlib rule names."""
        out = []
        for pattern in ("hooks/*.py", "hosts/**/*.py", "bin/tezgah-*"):
            out += [os.path.relpath(p, REPO)
                    for p in glob.glob(os.path.join(REPO, pattern), recursive=True)
                    if os.path.isfile(p)]
        return sorted(set(out))

    def top_level_defs(self, path):
        source = source_of(path)
        if not is_python(path, source):
            return []
        try:
            tree = ast.parse(source)
        except SyntaxError as exc:
            self.fail("%s does not parse: %s" % (path, exc))
        return [n.name for n in tree.body
                if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]

    def imports_of(self, path):
        """The root module names `path` imports, or None when it is not Python."""
        source = source_of(path)
        if not is_python(path, source):
            return None
        try:
            tree = ast.parse(source)
        except SyntaxError as exc:
            self.fail("%s does not parse: %s" % (path, exc))
        roots = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                roots.update(a.name.split(".")[0] for a in node.names)
            elif isinstance(node, ast.ImportFrom) and not node.level:
                roots.add((node.module or "").split(".")[0])
        return {r for r in roots if r}

    def test_no_module_that_nothing_references(self):
        """A module no other file names is a file that runs nowhere - the shape
        left behind by writing the tool and forgetting the wiring, with no
        import, manifest or script pointing at it."""
        corpus = self.corpus()
        text = {p: source_of(p) for p in corpus}
        tokens = {p: set(QUAL.findall(s)) for p, s in text.items()}
        for module in self.candidates():
            names = {os.path.basename(module), stem(module), module}
            hit = [p for p in corpus if p != module and names & tokens[p]]
            self.assertTrue(hit, "%s is referenced by nothing" % module)

    def test_no_top_level_function_that_nothing_calls(self):
        """A helper no caller reaches - the failure named for this layer: an
        agent adds a function to a module and never wires it. The def's own file
        counts as a caller, so a private helper its neighbour calls is not dead;
        this fires only on a def nothing anywhere mentions."""
        corpus = self.corpus()
        names = {p: code_names(p) for p in corpus}
        for module in self.candidates():
            source = source_of(module)
            for name in self.top_level_defs(module):
                if name.startswith("__") or name in ENTRY_POINTS:
                    continue
                body = "".join(line for line in source.splitlines(True)
                               if not re.match(r"\s*def %s\s*\(" % re.escape(name),
                                               line))
                if re.search(r"(?<![A-Za-z0-9_])%s(?![A-Za-z0-9_])" % re.escape(name),
                             body):
                    continue  # called inside its own module
                callers = [p for p in corpus if p != module and name in names[p]]
                self.assertTrue(callers,
                                "%s: %s is defined and called nowhere"
                                % (module, name))

    def test_the_stdlib_layer_imports_only_the_stdlib(self):
        """CONTRIBUTING.md's "stdlib only for anything under `hooks/`, `hosts/`
        and `bin/`", as a check: a third-party import in this layer is a
        dependency every host and every user installs, and that the layer has
        none was only a sentence."""
        siblings = {stem(p) for p in tree_paths(SCAN_ROOTS)}
        allowed = set(sys.stdlib_module_names) | siblings
        for path in self.python_targets():
            for name in self.imports_of(path) or ():
                self.assertIn(name, allowed,
                              "%s imports %s, which is neither stdlib nor a "
                              "sibling module in this tree" % (path, name))


if __name__ == "__main__":
    unittest.main()