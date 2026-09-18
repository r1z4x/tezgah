"""docs/: the engineering layer an agent reaches in one hop.

The layer is only reachable if its index is true, so these tests pin the index
against the directory rather than pinning any page's prose: a page that exists
without an entry, or an entry that names a file nobody wrote, fails here.
"""
import json
import os
import re
import subprocess
import sys
import unittest

import support

DOCS = os.path.join(support.REPO, "docs")
INDEX = os.path.join(DOCS, "index.json")
CLI = os.path.join(support.REPO, "bin", "tezgah-docs")
ROUTER = "README.md"


def read(path):
    with open(path, encoding="utf-8") as fh:
        return fh.read()


def index():
    with open(INDEX, encoding="utf-8") as fh:
        return json.load(fh)


class DocsLayer(unittest.TestCase):
    def pages(self):
        """Every page under docs/, relative to the repository."""
        return sorted(os.path.relpath(os.path.join(DOCS, n), support.REPO)
                      for n in os.listdir(DOCS) if n.endswith(".md"))

    def test_every_page_has_an_index_entry_and_every_entry_resolves(self):
        # The index is the router: a page nobody can reach from it is invisible,
        # and an entry pointing at a missing file is worse (it reads as a page
        # that exists). The router itself is the index's front door, not a leaf.
        listed = {p["path"] for p in index()["pages"]}
        on_disk = {p for p in self.pages()
                   if os.path.basename(p) != ROUTER}
        self.assertEqual(sorted(on_disk - listed), [],
                         "page(s) with no index entry")
        self.assertEqual(sorted(listed - on_disk), [],
                         "index entr(ies) with no page")

    def test_every_index_entry_carries_its_whole_contract(self):
        for page in index()["pages"]:
            with self.subTest(page=page["path"]):
                self.assertTrue(page.get("title"))
                self.assertTrue(page.get("answers"))
                self.assertTrue(page.get("sources"))

    def test_the_router_links_every_page(self):
        router = read(os.path.join(DOCS, ROUTER))
        for page in index()["pages"]:
            name = os.path.basename(page["path"])
            self.assertIn("(%s)" % name, router,
                          "the router does not link %s" % name)

    def test_every_page_states_what_it_documents_and_cites_the_code(self):
        # A page without `## Source of truth` cannot be re-verified after a
        # change; a page without a single `path:line` is prose nobody can check.
        for page in index()["pages"]:
            with self.subTest(page=page["path"]):
                text = read(os.path.join(support.REPO, page["path"]))
                self.assertIn("## Source of truth", text)
                self.assertRegex(text, r"[\w./-]+\.(?:py|js|ts|tsx|json|toml|yml|md):\d",
                                 "no path:line citation")

    def anchors(self, text):
        """Every anchor a page carries: the slug of each heading, plus any
        explicit `<a id="...">` alias. A heading's slug is not its text - the
        section `### per-repo mark` answers to `#per-repo-mark` - so a link is
        checked against the slug, the way a reader's browser resolves it."""
        found = set(re.findall(r'<a id="([^"]+)"', text))
        for line in text.splitlines():
            heading = re.match(r"^#{1,6}\s+(.*)$", line)
            if not heading:
                continue
            slug = re.sub(r"[^\w\s-]", "", heading.group(1).strip().lower())
            found.add(re.sub(r"\s+", "-", slug).strip("-"))
        return found

    def test_every_cross_page_anchor_resolves(self):
        # A link to `glossary.md#ledger` is a promise that the glossary carries
        # that anchor. Ten pages linking to each other rot silently otherwise, and
        # a dead anchor reads as a term the glossary defines but does not.
        for page in index()["pages"]:
            text = read(os.path.join(support.REPO, page["path"]))
            for target, anchor in re.findall(r"\]\(([\w.-]+\.md)#([\w.-]+)\)", text):
                with self.subTest(page=page["path"], to=target, anchor=anchor):
                    path = os.path.join(DOCS, target)
                    self.assertTrue(os.path.isfile(path), "%s is missing" % target)
                    self.assertIn(anchor, self.anchors(read(path)),
                                  "%s has no %r anchor" % (target, anchor))

    def test_the_cli_reaches_a_page_from_a_query(self):
        proc = subprocess.run([sys.executable, CLI, "status", "mark"],
                              capture_output=True, text=True, timeout=60)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("docs/status-line.md", proc.stdout)

    def test_the_cli_lists_every_page_and_refuses_an_empty_match(self):
        listed = subprocess.run([sys.executable, CLI], capture_output=True,
                                text=True, timeout=60)
        self.assertEqual(listed.returncode, 0, listed.stderr)
        for page in index()["pages"]:
            self.assertIn(page["path"], listed.stdout)
        missing = subprocess.run([sys.executable, CLI, "zzz-nothing-matches"],
                                 capture_output=True, text=True, timeout=60)
        self.assertEqual(missing.returncode, 1)


if __name__ == "__main__":
    unittest.main()
