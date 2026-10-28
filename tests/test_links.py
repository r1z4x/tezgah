"""Every relative markdown link in a tracked .md file points at a file that exists.

A moved or renamed page leaves `](old/path.md)` behind in every page that linked
it, and nothing else notices. Only file existence is checked here: anchors in
docs/ are held by tests/test_docs.py. Links inside code spans and fenced blocks
are examples, not links, and are skipped.
"""
import os
import re
import subprocess
import tempfile
import unittest

import support

LINK = re.compile(r"\]\(<?([^)\s>]+)>?(?:\s+\"[^\"]*\")?\)")
FENCE = re.compile(r"```.*?```", re.S)
SPAN = re.compile(r"`[^`\n]*`")
SCHEME = re.compile(r"[a-z][a-z0-9+.-]*:", re.I)
# Vendored byte-for-byte from Orchestra Research (NOTICE): upstream's bodies link
# reference files its SOURCE records as dropped, and editing them breaks the
# manifest. The entry point skills/ai-research/SKILL.md is tezgah's own and stays checked.
VENDORED = "skills/ai-research/"


def broken_links(root):
    files = subprocess.run(["git", "ls-files", "*.md"], cwd=root, capture_output=True,
                           text=True, check=True).stdout.split()
    bad = []
    for rel in files:
        if rel.startswith(VENDORED) and rel != VENDORED + "SKILL.md":
            continue
        with open(os.path.join(root, rel), encoding="utf-8") as f:
            text = SPAN.sub("", FENCE.sub("", f.read()))
        for target in LINK.findall(text):
            path = target.split("#")[0].split("?")[0]
            if not path or SCHEME.match(target):
                continue
            if not os.path.exists(os.path.join(root, os.path.dirname(rel), path)):
                bad.append("%s -> %s" % (rel, target))
    return bad


class RelativeLinks(unittest.TestCase):
    def test_every_relative_link_resolves(self):
        self.assertEqual([], broken_links(support.REPO))

    def test_a_dead_link_is_reported(self):
        with tempfile.TemporaryDirectory() as root:
            subprocess.run(["git", "init", "-q", root], check=True)
            with open(os.path.join(root, "a.md"), "w") as f:
                f.write("[ok](a.md#top) [web](https://x) [gone](b.md) `[code](c.md)`\n")
            subprocess.run(["git", "-C", root, "add", "a.md"], check=True)
            self.assertEqual(["a.md -> b.md"], broken_links(root))


if __name__ == "__main__":
    unittest.main()
