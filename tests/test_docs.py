"""docs/: the engineering layer an agent reaches in one hop.

The layer is only reachable if its index is true, so these tests pin the index
against the directory rather than pinning any page's prose: a page that exists
without an entry, or an entry that names a file nobody wrote, fails here.

The other promise a page makes is its citations, and one of them is checkable
in full: the rule-provenance table in docs/gate.md names, for every rule, the
case that guards it. `bin/tezgah-docs --citations` checks that record and this
module drives it, so a rule with no row and a row whose `pin` names no test
both fail there rather than in a reader's trust.
"""
import importlib.machinery
import importlib.util
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


def docs_module():
    """bin/tezgah-docs as a module, for the rule-ledger check it carries.

    Loaded by path, the way tests/test_packaging.py loads bin/tezgah-setup: the
    script has no `.py` in its name, so it is imported under one of its own."""
    if "tezgah_docs_ledger" in sys.modules:
        return sys.modules["tezgah_docs_ledger"]
    loader = importlib.machinery.SourceFileLoader("tezgah_docs_ledger", CLI)
    module = importlib.util.module_from_spec(
        importlib.util.spec_from_loader("tezgah_docs_ledger", loader))
    sys.modules["tezgah_docs_ledger"] = module
    loader.exec_module(module)
    return module


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
                # The default router ranks on the Turkish phrasings too
                # (bin/tezgah-docs ranked() reads title_tr and answers_tr).
                title_tr, answers_tr = page.get("title_tr"), page.get("answers_tr")
                self.assertTrue(isinstance(title_tr, str) and title_tr.strip(),
                                "%s has no title_tr" % page["path"])
                self.assertTrue(
                    isinstance(answers_tr, list) and answers_tr
                    and all(isinstance(a, str) and a.strip() for a in answers_tr),
                    "%s has no answers_tr list of non-empty strings" % page["path"])

    def test_the_router_links_every_page(self):
        router = read(os.path.join(DOCS, ROUTER))
        for page in index()["pages"]:
            name = os.path.basename(page["path"])
            self.assertIn("(%s)" % name, router,
                          "the router does not link %s" % name)

    def test_every_page_states_what_it_documents_and_cites_the_code(self):
        # A page without `## Source of truth` cannot be re-verified after a
        # change; a page without a single citation - `path::symbol` or
        # `path:line` - is prose nobody can check.
        for page in index()["pages"]:
            with self.subTest(page=page["path"]):
                text = read(os.path.join(support.REPO, page["path"]))
                self.assertIn("## Source of truth", text)
                self.assertRegex(
                    text, r"(?:bin/[\w.-]+|[\w./-]+\.(?:py|js|ts|tsx|json|toml|yml|md))"
                          r"(?::\d|::[A-Za-z_])", "no path::symbol or path:line citation")

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

    def citation_file(self, path):
        """The file a citation points at, or None. A page writes a repo-relative
        path when the file is not in a conventional directory and the bare file
        name otherwise (`test_context.py:51`, `ci.yml:8`), so a bare name is
        looked for in the directories the layer cites from."""
        if os.path.isfile(os.path.join(support.REPO, path)):
            return os.path.join(support.REPO, path)
        if "/" in path:
            return None
        for directory in ("tests", "hooks", "bin", "hosts", "hosts/omp",
                          "hosts/dsh/statusline/lib", "skills", "workflows",
                          "docs", ".tezgah/plans", ".github/workflows"):
            candidate = os.path.join(support.REPO, directory, path)
            if os.path.isfile(candidate):
                return candidate
        return None

    # The bound check's shape: an extension-bearing path, or a `bin/` script,
    # which has none (`bin/tezgah-setup:843`) and was outside the old pattern.
    BOUNDED = re.compile(
        r"(bin/[\w.-]+|[\w./-]+\.(?:py|js|ts|tsx|json|yml|toml|md)):(\d+)(?:-(\d+))?")

    def test_the_bound_check_reads_an_extensionless_bin_citation(self):
        self.assertEqual(self.BOUNDED.findall("see `bin/tezgah-setup:843-845`"),
                         [("bin/tezgah-setup", "843", "845")])

    def test_every_citation_points_into_a_file_that_has_that_line(self):
        # A page's promise is a citation: the claim is checkable. For `path:line`
        # this is the half a script can check - the file is there and the line is
        # inside it - and it is deliberately not more than that: whether the line
        # still shows the thing the sentence names is a judgement an audit makes,
        # not a regex, and a test that guessed at it would fail on rewording
        # rather than on drift. A `path::symbol` has no line to bound; its name is
        # resolved by `bin/tezgah-docs --citations` (`CitationAudit` below).
        for page in index()["pages"]:
            text = read(os.path.join(support.REPO, page["path"]))
            cites = self.BOUNDED.findall(text)
            self.assertTrue(cites or re.search(r"`[\w./-]+::[A-Za-z_]", text),
                            "%s cites no file" % page["path"])
            for path, start, end in cites:
                if path.startswith(".tezgah/plans/"):
                    # The plan layer is deliberately local: `.gitignore` keeps
                    # `.tezgah/plans/` out of the repository, so a clean checkout
                    # - what CI has - cannot resolve a citation into it. Counting
                    # those as not judgeable is the honest answer; failing would
                    # only report the layer's own design back at the reader.
                    continue
                with self.subTest(page=page["path"], cite="%s:%s" % (path, start)):
                    full = self.citation_file(path)
                    self.assertIsNotNone(full, "%s is cited but missing" % path)
                    with open(full, encoding="utf-8", errors="replace") as fh:
                        lines = len(fh.read().splitlines())
                    self.assertLessEqual(
                        int(end or start), lines,
                        "%s:%s is past the end of the file (%d lines)"
                        % (path, end or start, lines))

    def test_no_citation_repeats_its_own_file_name_or_runs_backwards(self):
        # The corruption the bound check above cannot see: a path stitched to
        # itself (`bin/tezgah-setupbin/tezgah-setup:2259-2256`) or a range whose
        # end precedes its start. Both keep the `path:line` shape, so the file
        # exists and the number is inside it and the check above stays green.
        # Yet neither can be a citation a reader follows - no path names its own
        # file twice, and no range ends before it starts - so this needs no
        # allowlist: a token that trips either rule is corrupt by construction.
        # The shape is any backticked `path:line`, not only the extension-bearing
        # files the check above names: the path half of `bin/tezgah-setup` has no
        # extension, so an extension-shaped pattern never reaches the corruption.
        cite = re.compile(r"`([\w./-]+):(\d+)(?:-(\d+))?`")
        for page in index()["pages"]:
            text = read(os.path.join(support.REPO, page["path"]))
            for cite_match in cite.finditer(text):
                token, path = cite_match.group(0), cite_match.group(1)
                start, end = cite_match.group(2), cite_match.group(3)
                name = os.path.basename(path)
                with self.subTest(page=page["path"], cite=token):
                    self.assertEqual(
                        token.count(name), 1,
                        "%s names %s %d times" % (token, name, token.count(name)))
                    self.assertLessEqual(
                        int(start), int(end or start),
                        "%s ends before it starts" % token)


class RuleLedger(unittest.TestCase):
    """The record that maps a refused rule to the case that guards it.

    `docs/gate.md`'s `## Rule provenance` table is read by the citation pass
    (`bin/tezgah-docs --citations`, the audit's sibling): every rule name the
    gate can produce has a row, and every row's `pin` names a test that exists.
    The first test holds the real table to that; the next two prove the check
    itself, on a doctored table, so removing either half turns them red."""

    def test_every_rule_has_a_row_and_every_pin_names_a_test(self):
        module = docs_module()
        self.assertEqual(module.ledger_failures(module.ledger_rows()), [])

    def test_every_stop_class_is_read_the_evidence_half_included(self):
        # `_evidence_block` returns six of the ten Stop classes; a reader that
        # skipped it saw four and let a renamed evidence class go unrecorded.
        import ast
        module = docs_module()
        tree = ast.parse(module.source(module.STOP), filename=module.STOP)
        evidence = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) and node.name == "_evidence_block":
                evidence = module.returned_classes(node)
        self.assertTrue(evidence, "_evidence_block returns no class")
        self.assertLessEqual(evidence, module.stop_triggers())

    def test_a_rule_with_no_row_is_refused(self):
        module = docs_module()
        rows = module.ledger_rows()
        rule = rows.pop(0)["rule"]
        failures = module.ledger_failures(rows)
        self.assertTrue(any(rule in f for f in failures),
                        "%s was not refused for having no row: %r"
                        % (rule, failures))

    def test_a_row_whose_pin_names_no_test_is_refused(self):
        # The drift the check is for: the case a row leans on is renamed or
        # deleted and the row goes on naming it.
        module = docs_module()
        rows = module.ledger_rows()
        self.assertTrue(rows, "no rule-provenance rows were parsed")
        rows[0]["pin"] = "tests/test_gate.py::test_this_case_was_deleted"
        failures = module.ledger_failures(rows)
        self.assertTrue(
            any("test_this_case_was_deleted" in f for f in failures),
            "a pin naming a deleted test was not refused: %r" % (failures,))


class Inventories(unittest.TestCase):
    """The lists a page keeps by hand, checked against the code read by AST.

    Each check has a real-tree case (the page holds today) and a doctored one
    (the check can fail), so deleting the check turns the second red."""

    def test_every_deny_site_of_decision_is_read_with_its_guards(self):
        sites = docs_module().rule_sites()
        self.assertEqual(len(sites), 24)
        order = []
        for site in sites:
            if site[0] not in order:
                order.append(site[0])
        self.assertEqual(order, [
            "control", "explorer", "shortcut", "piped", "attribution", "lang", "race",
            "task", "workspace", "secret", "plan", "order", "loop", "retry",
            "drift"])
        by_rule = {s[0]: s for s in sites}
        self.assertEqual(by_rule["lang"][3], ("lang-off",))
        self.assertEqual(by_rule["explorer"][3], ())
        self.assertIn("BASH_TOOLS", by_rule["secret"][4])
        self.assertLess(by_rule["drift"][1], by_rule["drift"][2] + 1)

    def test_a_deny_site_in_a_handler_or_a_case_is_read(self):
        module = docs_module()
        text = (
            "def _deny(session_id, rule, reason):\n    return reason\n\n\n"
            "def decision(t, session_id=None):\n"
            "    try:\n        pass\n"
            "    except ValueError:\n"
            "        return _deny(session_id, \"caught\", \"r\")\n"
            "    match t:\n"
            "        case \"x\":\n"
            "            return _deny(session_id, \"matched\", \"r\")\n"
            "    return None\n")
        self.assertEqual([s[0] for s in module.rule_sites(text)], ["caught", "matched"])
        self.assertEqual(module.rule_site_failures(text), [])

    def test_a_deny_call_the_reader_cannot_place_is_refused(self):
        # `out = _deny(...); return out` is a rule with no statement span to
        # mutate and no place in the order: it must fail, not vanish.
        module = docs_module()
        text = ("def decision(t, session_id=None):\n"
                "    out = _deny(session_id, \"hidden\", \"r\")\n"
                "    return out\n")
        failures = module.rule_site_failures(text)
        self.assertTrue(any("hidden" in f for f in failures), failures)
        self.assertEqual(module.rule_site_failures(), [])

    def test_the_page_heads_the_rules_in_the_order_decision_checks_them(self):
        self.assertEqual(docs_module().rule_order_failures(), [])

    def test_a_heading_out_of_order_is_refused(self):
        module = docs_module()
        text = read(module.LEDGER)
        swapped = text.replace("### Piped", "### TMP").replace(
            "### Shortcut", "### Piped").replace("### TMP", "### Shortcut")
        failures = module.rule_order_failures(swapped)
        self.assertTrue(any("order" in f for f in failures), failures)

    def test_a_rule_section_that_does_not_name_its_switch_is_refused(self):
        module = docs_module()
        text = read(module.LEDGER).replace("`lang-off`", "the switch")
        failures = module.rule_order_failures(text)
        self.assertTrue(any("lang-off" in f for f in failures), failures)

    def test_every_judge_caller_has_a_row_and_the_count_is_right(self):
        module = docs_module()
        self.assertIn("bin/tezgah-taste", module.judge_callers())
        self.assertEqual(module.judge_caller_failures(), [])
        page = read(module.JUDGE_PAGE).replace("| `bin/tezgah-taste` |", "| taste |")
        failures = module.judge_caller_failures(page)
        self.assertTrue(any("bin/tezgah-taste" in f for f in failures), failures)

    def test_the_switches_code_reads_are_the_core_names_plus_the_open_four(self):
        # ADR 007 leaves these four unclassified: two `off()` names no CORE
        # paragraph lists and two opt-in markers read with `armed()`. Until the
        # owner classifies them they are this explicit set, and a fifth name
        # outside CORE fails the check instead of joining it silently.
        module = docs_module()
        self.assertEqual(module.UNCLASSIFIED_SWITCHES, frozenset((
            "agents-off", "update-check-off", "taste-on", "skill-suggest-on")))
        self.assertEqual(len(module.core_switches()), 16)
        self.assertEqual(module.switch_failures(), [])
        failures = module.switch_failures(core=module.core_switches() - {"lang-off"})
        self.assertTrue(any("lang-off" in f for f in failures), failures)


class CitationAudit(unittest.TestCase):
    """The `--citations` judgement, run on a small tree of its own.

    Every script under bin/ has a `.py` symlink beside it so tests can import
    it, and both match the `bin/*` glob. The audit (M-11a) measured what that
    did: each bin symbol read as defined in two files, was dropped as
    ambiguous, and `--citations` reported 0 stale citations while 25 were."""

    TOOL = ("import os\n\n\ndef first():\n    return 1\n\n\n"
            "def second():\n    return 2\n")

    def audit(self, files, baseline=None):
        """(known, flagged, judged, unjudged, invisible) over a tree holding
        `files` ({relpath: text}) and the bin/tool above with its twin."""
        import tempfile
        module = docs_module()
        with tempfile.TemporaryDirectory() as root:
            for rel, text in dict({"bin/tool": self.TOOL}, **files).items():
                os.makedirs(os.path.dirname(os.path.join(root, rel)), exist_ok=True)
                with open(os.path.join(root, rel), "w", encoding="utf-8") as fh:
                    fh.write(text)
            os.symlink("tool", os.path.join(root, "bin", "tool.py"))
            here = module.HERE
            module.HERE = root
            try:
                known = module.symbols()
                return (known,) + module.citations(known)
            finally:
                module.HERE = here

    def test_a_stale_citation_into_a_symlinked_script_is_reported(self):
        known, flagged, judged, _, _ = self.audit(
            {"docs/page.md": "The helper is `first` (`bin/tool:8-9`).\n"})
        self.assertEqual(known.get("first"), ("bin/tool", [(4, 7)]))
        self.assertEqual(judged, 1)
        self.assertEqual([f[1] for f in flagged], ["`bin/tool:8-9`"])
        self.assertEqual(flagged[0][0], "docs/page.md:1")

    def test_a_bare_file_name_is_judged_against_the_one_file_of_that_name(self):
        _, flagged, judged, unjudged, _ = self.audit({
            "hooks/x.py": self.TOOL.replace("first", "alpha").replace("second", "beta"),
            "docs/page.md": "`beta` (`x.py:4-5`) and `alpha` (`x.py:4-5`).\n"})
        self.assertEqual(judged, 2)
        self.assertEqual([f[1] for f in flagged], ["`x.py:4-5`"])
        self.assertEqual(sum(unjudged.values()), 0)

    def test_a_symbol_written_after_its_citation_is_read(self):
        _, flagged, judged, _, _ = self.audit({
            "docs/page.md": "owned - `bin/tool:8` (`first`), then `bin/tool:8` (`second`)\n"})
        self.assertEqual(judged, 2)
        self.assertEqual([f[1] for f in flagged], ["`bin/tool:8`"])

    def test_comments_and_docstrings_are_judged_and_fixture_strings_are_not(self):
        _, flagged, judged, _, _ = self.audit({"hooks/y.py": (
            '"""Module: `first` (`bin/tool:8-9`)."""\n'
            "PAGE = \"`first` (`bin/tool:8`)\"\n"
            "\n\ndef go():\n"
            "    # `second` (`bin/tool:4`)\n"
            "    return PAGE\n")})
        self.assertEqual(judged, 2)
        self.assertEqual(sorted((f[0], f[1]) for f in flagged),
                         [("hooks/y.py:1", "`bin/tool:8-9`"),
                          ("hooks/y.py:6", "`bin/tool:4`")])

    def test_a_citation_the_pattern_cannot_read_is_counted_as_unjudged(self):
        _, flagged, judged, unjudged, invisible = self.audit({
            "docs/page.md": "see bin/tool:4 and `first` (`bin/tool:4,8`); "
                            "not https://example.com:443 nor nothing/here.py:3\n"})
        self.assertEqual((judged, invisible), (0, 2))
        self.assertEqual(unjudged, {"docs/page.md": 2})

    def test_a_symbol_anchor_is_judged_by_ast_and_a_missing_one_is_flagged(self):
        # `path::Class.method` carries no line number, so an edit above the
        # symbol cannot shift it; what can go wrong is the name, and the AST of
        # the cited file is what answers it.
        _, flagged, judged, unjudged, _ = self.audit({
            "hooks/k.py": ("\n\nclass K:\n    def m(self):\n        def inner():\n"
                           "            pass\n\n\nLIMIT = 3\n"),
            "docs/page.md": ("`bin/tool::first`, `hooks/k.py::K.m`, "
                             "`hooks/k.py::K.m.inner`, `hooks/k.py::LIMIT`, "
                             "`k.py::K`, `hooks/k.py::m`.\n"
                             "Gone: `bin/tool::third`, `hooks/k.py::K.n`, "
                             "`hooks/nope.py::K`.\n")})
        self.assertEqual(judged, 9)
        self.assertEqual(sum(unjudged.values()), 0)
        self.assertEqual([(f[0], f[1]) for f in flagged],
                         [("docs/page.md:2", "`bin/tool::third`"),
                          ("docs/page.md:2", "`hooks/k.py::K.n`"),
                          ("docs/page.md:2", "`hooks/nope.py::K`")])

    def test_a_function_local_def_does_not_stand_in_for_a_gone_symbol(self):
        # The dotless fallback is for a test pin naming a method of its
        # TestCase; a def local to a function is not a name a page can cite, so
        # a deleted top-level `_frozen` must not pass on a same-named helper.
        _, flagged, judged, _, _ = self.audit({
            "hooks/m.py": ("def migrate():\n    def _frozen():\n        pass\n\n\n"
                           "class T:\n    def test_x(self):\n        pass\n"),
            "docs/page.md": "`hooks/m.py::_frozen` and `hooks/m.py::test_x`.\n"})
        self.assertEqual(judged, 2)
        self.assertEqual([f[1] for f in flagged], ["`hooks/m.py::_frozen`"])

    def test_a_symbol_anchor_in_a_comment_is_judged(self):
        _, flagged, judged, _, _ = self.audit({"hooks/y.py": (
            "# see `bin/tool::second` and `bin/tool::gone`\n"
            "PAGE = \"`bin/tool::also_gone`\"\n")})
        self.assertEqual(judged, 2)
        self.assertEqual([(f[0], f[1]) for f in flagged],
                         [("hooks/y.py:1", "`bin/tool::gone`")])

    def test_a_symbol_anchor_does_not_move_when_lines_are_inserted_above_it(self):
        tool = "\n" * 5 + self.TOOL
        _, flagged, judged, _, _ = self.audit({
            "bin/tool": tool,
            "docs/page.md": "`bin/tool::second`, and `second` (`bin/tool:8-9`).\n"})
        self.assertEqual(judged, 2)
        self.assertEqual([f[1] for f in flagged], ["`bin/tool:8-9`"])

    def test_a_count_that_moved_either_way_is_drift(self):
        # Over: a new unjudged citation. Under: one was fixed, and a baseline
        # left high would let the next new one in silently, so it fails too
        # until `--citations --update` writes the lower count down.
        module = docs_module()
        unjudged = {"docs/a.md": 3, "docs/b.md": 1}
        self.assertEqual(module.ratchet_drift(unjudged, {"docs/a.md": {"unjudged": 3}}),
                         [("docs/b.md", 1, 0)])
        self.assertEqual(module.ratchet_drift({"docs/a.md": 2},
                                              {"docs/a.md": {"unjudged": 3}}),
                         [("docs/a.md", 2, 3)])
        self.assertEqual(module.ratchet_drift({}, {"docs/gone.md": {"unjudged": 1}}),
                         [("docs/gone.md", 0, 1)])
        self.assertEqual(module.ratchet_drift({"docs/a.md": 3},
                                              {"docs/a.md": {"unjudged": 3}}), [])

    def test_the_real_tree_holds_its_unjudged_baseline_exactly(self):
        module = docs_module()
        _, _, unjudged, _ = module.citations(module.symbols())
        self.assertEqual(module.ratchet_drift(unjudged, module.ratchet_baseline()), [])


if __name__ == "__main__":
    unittest.main()
