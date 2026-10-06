"""The bash-oracle fuzzer (tests/fuzz_shell.py) on a fixed seed.

The normal suite runs a small sample; `TEZGAH_FUZZ_LINES=10000` runs a larger
one. What it holds is the deny rules' reader: no program bash ran may be
blanked by `mask`, the text every shell deny rule matches (gate-01). The
program reader's open classes are printed, not asserted (plan 054). The same
sample read by the opencode plugin's ports (`--js`, through node) must blank
nothing bash ran and must answer exactly as the core does on every line.
"""
import os
import shutil
import unittest

import fuzz_shell

LINES = int(os.environ.get("TEZGAH_FUZZ_LINES") or 60)


@unittest.skipUnless(fuzz_shell.bash(), "no bash on PATH")
class FuzzShell(unittest.TestCase):
    def test_mask_never_hides_a_program_bash_ran(self):
        classes, _invalid, examples = fuzz_shell.run(seed=1, lines=LINES)
        hidden = {k: examples[k] for k in classes if k.startswith("mask:")}
        self.assertEqual(hidden, {})

    @unittest.skipUnless(shutil.which("node"), "node missing")
    def test_the_opencode_ports_hide_nothing_and_match_the_core(self):
        classes, _invalid, examples = fuzz_shell.run(seed=1, lines=LINES, js=True)
        off = {k: examples[k] for k in classes
               if k.startswith(("js-mask:", "js-parity:"))}
        self.assertEqual(off, {})

    def test_the_oracle_sees_what_bash_runs(self):
        # the oracle itself: a quoted name is not run, a substitution is, and
        # the branch `||` skips on the first run is taken on the second
        oracle = fuzz_shell.Oracle()
        try:
            self.assertEqual(oracle.ran("p0 'q s1' $(c1 x) || p1"),
                             {"p0", "c1", "p1"})
        finally:
            oracle.close()


if __name__ == "__main__":
    unittest.main()
