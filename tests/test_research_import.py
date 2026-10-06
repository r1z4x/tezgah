"""`tezgah-research import`: a line moves between checkouts with its history.

Each checkout keeps its own private `.tezgah` repository, so a line copied from
one to another arrives with no commits and loses its protocol-before-results
proof (hallucination-guardrails, research-layer-02). `import` fetches the other
checkout's repository from disk - no remote - and merges it as a second parent,
taking only the imported lines' paths. Scratch repositories only.
"""
import os
import shutil
import sys
import unittest

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO, "hooks"))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import tezgah_research as tr  # noqa: E402
from test_research import BOTH_TOGETHER, Workspace, hit  # noqa: E402

ORDER = ("protocol.md entered", "one commit added both", "added in different "
         "histories", "protocol.md is not committed", "results.jsonl is not "
         "committed", "protocol order", "protocol.md changed after the run")


def order_errors(errors):
    return [e for e in errors if any(n in e for n in ORDER)]


class Import(Workspace):
    def source(self):
        """A checkout holding a strict-clean line `q`, committed protocol first,
        and an unrelated line `other` that an import of `q` must not bring."""
        src = self.repo("src")
        self.clean(src)
        self.line(src, "other", question="an unrelated question")
        self.commit(src, "rest", when="2021-07-07T00:00:00+0000")
        self.assertEqual(tr.check_line(src, "q", strict=True)[0], [])
        return src

    def target(self, born=True):
        dst = self.repo("dst")
        self.assertIsNotNone(tr.tp.ensure_workspace(dst))
        if born:
            self.line(dst, "mine", question="this checkout's own question")
            self.commit(dst, "mine")
        return dst

    def test_an_imported_line_keeps_its_order_proof_under_strict(self):
        src, dst = self.source(), self.target()
        imported, problem = tr.import_line(dst, src, "q")
        self.assertEqual((imported, problem), (["q"], None))
        self.assertEqual(tr.slugs(dst), ["mine", "q"])
        errors = tr.check_line(dst, "q", strict=True)[0]
        self.assertEqual(order_errors(errors), [])
        self.assertEqual(errors, [])
        ws = os.path.join(dst, ".tezgah")
        parents = self.git(ws, "log", "-1", "--format=%P").split()
        self.assertEqual(len(parents), 2, "the two-parent shape")
        self.assertEqual(self.git(ws, "status", "--porcelain", "--", "research"), "")

    def test_a_fresh_checkout_takes_the_line_with_its_history(self):
        src, dst = self.source(), self.target(born=False)
        self.assertEqual(tr.import_line(dst, src, "q"), (["q"], None))
        self.assertEqual(tr.slugs(dst), ["q"])
        self.assertEqual(order_errors(tr.check_line(dst, "q", strict=True)[0]), [])

    def test_no_slug_imports_every_line_this_checkout_lacks(self):
        src, dst = self.source(), self.target()
        self.assertEqual(tr.import_line(dst, src), (["other", "q"], None))
        self.assertEqual(tr.import_line(dst, src), ([], None))

    def test_a_plain_copy_is_refused(self):
        src, dst = self.source(), self.target()
        # a line the source never committed has no history to bring
        self.line(src, "draft", question="a draft never committed")
        imported, problem = tr.import_line(dst, src, "draft")
        self.assertEqual(imported, [])
        self.assertIn("plain copy is refused", problem)
        # a source with no private repository is refused, not copied
        bare = self.repo("bare")
        os.makedirs(os.path.join(bare, ".tezgah", "research", "open", "q"))
        self.assertIn("refuses a plain copy", tr.import_line(dst, bare, "q")[1])
        # a copy already in this checkout is refused, not merged over
        shutil.copytree(tr.line_dir(src, "q"),
                        os.path.join(tr.root(dst), "open", "q"))
        self.assertIn("already holds q", tr.import_line(dst, src, "q")[1])
        self.assertEqual(self.git(os.path.join(dst, ".tezgah"), "log", "-1",
                                  "--format=%s").strip(), "mine")

    def test_the_copy_import_replaces_loses_the_proof(self):
        """The contrast the command exists for: the same line copied and committed
        in one commit is refused by the order rule."""
        src, dst = self.source(), self.target()
        shutil.copytree(tr.line_dir(src, "q"),
                        os.path.join(tr.root(dst), "open", "q"))
        self.commit(dst, "copy")
        self.assertTrue(hit(BOTH_TOGETHER, tr.check_line(dst, "q")[0]))

    def test_the_cli_imports_without_a_remote(self):
        src, dst = self.source(), self.target()
        self.assertEqual(self.git(os.path.join(dst, ".tezgah"), "remote"), "")
        proc = self.cli(dst, "import", src, "q")
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        self.assertIn("imported q from %s" % src, proc.stdout)
        proc = self.cli(dst, "check", "--strict", "--", "q")
        self.assertEqual(proc.returncode, 0, proc.stdout)
        self.assertEqual(self.cli(dst, "import", src, "--x").returncode, 2)


if __name__ == "__main__":
    unittest.main()
