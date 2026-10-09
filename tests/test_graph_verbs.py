"""Every copy that teaches a codegraph verb teaches the verb the CLI has.

`codegraph affected` (codegraph 1.6.0) is a test-file selector: "Usage:
codegraph affected [options] [files...]" / "Find test files affected by changed
source files". It was taught for years as the blast radius of a ref or a
branch, so sessions ran `codegraph affected <sha>` and read an empty test list
as "nothing breaks". The blast radius is `git diff` plus `codegraph impact` per
changed symbol; the test selection is `git diff --name-only <ref> | codegraph
affected --stdin`. This pins every hand-kept copy and every generated role body
to that reading, and, when the binary is installed, each taught verb's usage
line to the one recorded here.

The frozen hint corpus (`tests/test_hint_coverage.py`) holds the prompt "run
codegraph affected on parse_quantity": user input, not teaching, so it is not
read here.
"""
import os
import re
import shutil
import subprocess
import sys
import unittest

import support

REPO = support.REPO
sys.path.insert(0, support.HOOKS)
COPIES = ("hooks/tezgah_policy.py", "hooks/tezgah_context.py",
          "hooks/tezgah_agents.py",
          "workflows/graph-review.js", "workflows/graph-impact.js",
          "skills/harness/SKILL.md", "skills/tezgah-contract/SKILL.md")
# `codegraph affected` is right only fed files: `--stdin` from a diff, or a
# file list. Any other continuation - `<ref>`, `<target>`, a bare mention in a
# blast-radius sentence - is the old reading.
WRONG = re.compile(r"codegraph affected(?! --stdin| <files?>)")
# The usage line of each verb a copy teaches, as codegraph 1.6.0 prints it.
USAGE = {"affected": "Usage: codegraph affected [options] [files...]",
         "impact": "Usage: codegraph impact [options] <symbol>",
         "callers": "Usage: codegraph callers [options] <symbol>",
         "callees": "Usage: codegraph callees [options] <symbol>",
         "node": "Usage: codegraph node [options] [name]",
         "files": "Usage: codegraph files [options]",
         "query": "Usage: codegraph query [options] <search>",
         "status": "Usage: codegraph status [options] [path]",
         "explore": "Usage: codegraph explore [options] <query...>"}


def _texts():
    for rel in COPIES:
        with open(os.path.join(REPO, rel), encoding="utf-8") as fh:
            yield rel, fh.read()
    import tezgah_agents as ta
    for name, _desc, _cap, body, _ro in ta.ROLES:
        for host in ("claude", "opencode", "codex", "omp"):
            yield "%s(%s)" % (name, host), body(host)
    yield "orchestrator", ta._orch_body([r[0] for r in ta.ROLES])


class TaughtVerbs(unittest.TestCase):
    def test_no_copy_teaches_affected_as_a_blast_radius(self):
        bad = ["%s: ...%s..." % (rel, " ".join(text[m.start() - 40:m.end() + 30].split()))
               for rel, text in _texts() for m in WRONG.finditer(text)]
        self.assertEqual([], bad)

    def test_the_test_selection_recipe_is_taught_where_affected_is_named(self):
        for rel, text in _texts():
            if "codegraph affected" in text:
                self.assertIn("codegraph affected --stdin", text, rel)

    @unittest.skipUnless(shutil.which("codegraph"), "codegraph not installed")
    def test_each_taught_verb_matches_the_installed_usage_line(self):
        for verb, want in USAGE.items():
            out = subprocess.run(["codegraph", verb, "--help"], capture_output=True,
                                 text=True, timeout=30, stdin=subprocess.DEVNULL)
            self.assertEqual(want, (out.stdout or out.stderr).splitlines()[0], verb)
        out = subprocess.run(["codegraph", "affected", "--help"], capture_output=True,
                             text=True, timeout=30, stdin=subprocess.DEVNULL)
        self.assertIn("--stdin", out.stdout)


if __name__ == "__main__":
    unittest.main()
