"""The gate's heredoc reader agrees with the bash that runs the command.

Differential, not hand-written expectations: each vector in tests/bash_vectors
is run through the `bash` on PATH with `git` shimmed, and the gate has to refuse
every command whose commit line bash executed. A local run measures the
machine's bash (3.2 on macOS); CI's ubuntu legs measure bash 5.x, where a command
substitution is parsed recursively. The opencode mirror is held to the same
vectors in test_opencode_plugin.
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "hooks"))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import bash_vectors as bv  # noqa: E402
import tezgah_integrity as ti  # noqa: E402


class BashAgreement(unittest.TestCase):
    def test_every_commit_bash_runs_is_refused(self):
        missed = []
        # a HIDDEN vector bash does run is held to the same rule: skipping it
        # would let a hidden commit through on that bash (consult review)
        for command in bv.EXPOSED + bv.HIDDEN:
            if not bv.bash_runs_commit(command):
                if command in bv.EXPOSED:
                    missed.append(command)
                continue
            self.assertIsNotNone(
                ti.shortcut_command(command),
                "bash %s runs the commit in %r, the gate let it through"
                % (bv.bash_version(), command))
        # the vectors are only evidence while bash really runs them: a shim
        # that never fired would make every assertion above vacuous. Only the
        # measured bash 5 bodies may not run, and they are named, not counted.
        self.assertEqual(set(missed) - bv.BODY_ON_BASH5, set(),
                         "bash %s no longer runs these" % bv.bash_version())

    def test_a_heredoc_body_bash_does_not_run_is_not_read_as_a_command(self):
        kept = [c for c in bv.HIDDEN if not bv.bash_runs_commit(c)]
        self.assertEqual(len(kept), len(bv.HIDDEN), bv.bash_version())
        for command in kept:
            self.assertIsNone(
                ti.shortcut_command(command),
                "bash %s keeps %r as heredoc body, the gate refused it"
                % (bv.bash_version(), command))

if __name__ == "__main__":
    unittest.main()
