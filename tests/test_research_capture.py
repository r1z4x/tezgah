#!/usr/bin/env python3
"""Unit tests for hooks/tezgah_research_capture.py (plan 127, spec 1.1-1.5).

Every network answer comes from a canned TEZGAH_CAPTURE_MAP and orx is a stub, so
no case touches the network; each case runs in its own mkdtemp git project."""
import contextlib
import hashlib
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "hooks"))
import tezgah_research as tr  # noqa: E402
import tezgah_research_capture as cap  # noqa: E402

CLI = os.path.join(ROOT, "bin", "tezgah-research")
ARX = "2401.00001"
TITLE = "Caching for tail latency"
QUOTE = "caching lowers tail latency in every workload we measured"
NOTE = "lit/smith.md"
ITEM = "what the literature reports about caching"


def atom(entries):
    body = "".join(
        "<entry><id>http://arxiv.org/abs/%sv1</id><title>%s</title><summary>%s</summary>"
        "<published>%d-01-02T00:00:00Z</published><author><name>%s</name></author></entry>"
        % e for e in entries)
    return '<feed xmlns="http://www.w3.org/2005/Atom">%s</feed>' % body


def openalex(aid=ARX, title=TITLE, wid="W1", oa=None):
    return json.dumps({"id": "https://openalex.org/%s" % wid,
                       "doi": "https://doi.org/10.48550/arxiv.%s" % aid, "title": title,
                       "publication_year": 2024,
                       "authorships": [{"author": {"display_name": "Ann Smith"}}],
                       "abstract_inverted_index": {"We": [0], "study": [1], "caching.": [2]},
                       "open_access": {"oa_url": oa}})


ARXIV_API = cap.ARXIV_API % ARX
OPENALEX = "https://api.openalex.org/works/doi:10.48550/arXiv.%s" % ARX
HTML = "https://arxiv.org/html/%s" % ARX
SEARCH_OA = cap.SEARCH_URLS["openalex"] % "caching+tail"
SEARCH_AX = cap.SEARCH_URLS["arxiv"] % "caching+no+effect"


class Pure(unittest.TestCase):
    def test_normalise_follows_spec_zero(self):
        # plan 128 C4: the quotation marks themselves are optional, so they read as none
        self.assertEqual(cap.normalise("\u201cTail\u201d  lat- ency [3, 4] \u2013 OK"),
                         "tail latency ok")

    def test_ids_normalise_and_identity_prefers_arxiv(self):
        self.assertEqual(cap.norm_id("arXiv:2401.00001v3"), "arXiv:2401.00001")
        self.assertEqual(cap.norm_id("https://doi.org/10.48550/ARXIV.2401.00001"),
                         "arXiv:2401.00001")
        self.assertEqual(cap.norm_id("doi:10.1145/ABC"), "doi:10.1145/abc")
        self.assertEqual(cap.norm_id("https://openalex.org/W9"), "openalex:W9")
        self.assertEqual(cap.identity(["openalex:W9", "doi:10.1/x", "arXiv:1"]), "arXiv:1")

    def test_a_bare_arxiv_id_and_an_arxiv_url_read_as_arxiv(self):
        # K6 Y2: a bare `1805.08612` INDEX id was skipped by `cite` and refused; X2 (4):
        # an `arxiv.org/abs/...` URL as an id was not normalised
        for raw, want in (("1805.08612", "arXiv:1805.08612"),
                          ("1805.08612v3", "arXiv:1805.08612"),
                          ("hep-th/9901001", "arXiv:hep-th/9901001"),
                          ("math.GT/0309136v2", "arXiv:math.GT/0309136"),
                          ("https://arxiv.org/abs/1805.08612v2", "arXiv:1805.08612"),
                          ("http://arxiv.org/pdf/1805.08612.pdf", "arXiv:1805.08612"),
                          ("https://arxiv.org/html/2401.00001v1", "arXiv:2401.00001"),
                          ("arxiv.org/abs/hep-th/9901001", "arXiv:hep-th/9901001")):
            self.assertEqual(cap.norm_id(raw), want, raw)
        self.assertTrue(cap.receipt_urls(cap.norm_id("1805.08612")))
        # a number is no id: a JSON float, a year, a ratio, a month 13
        for raw in (1805.08612, "3.14", "2024", "0.05", "1813.08612", "12345.6789"):
            self.assertIsNone(cap.norm_id(raw), raw)

    def test_title_measure_year_window_and_author(self):
        rec = {"title": TITLE, "year": 2024, "first_author": "Smith"}
        self.assertTrue(cap.header_agrees({"title": "Caching for Tail Latency",
                                           "year": 2025, "first_author": "smith"}, rec))
        self.assertFalse(cap.header_agrees({"title": TITLE, "year": 2022}, rec))
        self.assertFalse(cap.header_agrees({"title": "Request memoization for interactive "
                                                     "services", "year": 2024}, rec))
        self.assertFalse(cap.header_agrees({"title": TITLE, "year": 2024,
                                            "first_author": "Jones"}, rec))

    def test_a_word_extraction_split_in_two_still_cites(self):
        """K6 rater Y6's probe: pdftotext wrote `human-inthe-loop` for the PDF's
        `human-in-the-loop`, and the verbatim quote was refused. Only the source's
        spacing is missing, so the fragment still sits there; a missing letter is
        still a miss."""
        text = ("The paper argues for a human-inthe-loop evaluation harness across "
                "all ten tasks.")
        self.assertIsNone(cap.quote_problem(
            "argues for a human-in-the-loop evaluation harness", text))
        self.assertEqual(cap.quote_problem(
            "argues for a human-inloop evaluation harness", text), cap.NOT_IN_SOURCE)
        # the exact text is still the first reading, and order still holds
        self.assertIsNone(cap.quote_problem(
            "human-inthe-loop evaluation harness ... across all ten tasks", text))
        self.assertEqual(cap.quote_problem(
            "across all ten tasks ... human-inthe-loop evaluation harness", text),
            cap.NOT_IN_SOURCE)

    def test_the_systematic_review_connectors_parse(self):
        """K6 rater X6, row 7: PubMed, Scopus and ACM DL are standard for a systematic
        review and were refused as not on the allowlist. Each parses under its own
        answer and yields registry ids: PubMed its PMIDs, Scopus and ACM their DOIs."""
        pm = json.dumps({"esearchresult": {"idlist": ["42891471", "42872930"]}}).encode()
        self.assertTrue(cap.schema_ok("pubmed", pm))
        self.assertEqual(cap.search_records("pubmed", pm),
                         [["pubmed:42891471"], ["pubmed:42872930"]])
        self.assertFalse(cap.schema_ok("pubmed", b'{"error": {}}'))
        sc = json.dumps({"search-results": {"entry": [
            {"prism:doi": "10.1145/A"}, {"eid": "2-s2.0-1"}]}}).encode()
        self.assertTrue(cap.schema_ok("scopus", sc))
        self.assertEqual(cap.search_records("scopus", sc), [["doi:10.1145/a"]])
        self.assertFalse(cap.schema_ok("scopus", b'{"service-error": {}}'))
        acm = json.dumps({"message": {"items": [{"DOI": "10.1145/B"}]}}).encode()
        self.assertTrue(cap.schema_ok("acm", acm))
        self.assertEqual(cap.search_records("acm", acm), [["doi:10.1145/b"]])
        self.assertFalse(cap.schema_ok("acm", b"<html></html>"))

    def test_each_provider_parses_by_the_field_table(self):
        rid = "arXiv:" + ARX
        got = cap.parse_receipt("arxiv", rid, 200, atom([(ARX, TITLE, "We study.", 2024,
                                                         "Ann Smith")]).encode())
        self.assertEqual((got["resolved"], got["first_author"], got["year"]),
                         (True, "Smith", 2024))
        self.assertFalse(cap.parse_receipt("arxiv", "arXiv:2499.99999", 200, atom([(
            ARX, TITLE, "x", 2024, "A B")]).encode())["resolved"])
        got = cap.parse_receipt("openalex", rid, 200, openalex().encode())
        self.assertEqual(got["abstract"], "We study caching.")
        cross = json.dumps({"message": {"title": [TITLE], "author": [{"family": "Smith"}],
                                        "issued": {"date-parts": [[2023, 5]]},
                                        "abstract": "<jats:p>We study.</jats:p>"}})
        got = cap.parse_receipt("crossref", rid, 200, cross.encode())
        self.assertEqual((got["year"], got["abstract"]), (2023, "We study."))
        s2 = json.dumps({"title": TITLE, "authors": [{"name": "Ann Smith"}], "year": 2024})
        self.assertTrue(cap.parse_receipt("semanticscholar", rid, 200, s2.encode())["resolved"])
        self.assertFalse(cap.parse_receipt("crossref", rid, 404, cross.encode())["resolved"])

    def test_receipt_ids_by_provider(self):
        self.assertEqual(cap.receipt_ids("crossref", b'{"message": {"title": ["x"]}}'), set())
        self.assertEqual(cap.receipt_ids("crossref", b'{"message": {"DOI": "10.1/X"}}'),
                         {"doi:10.1/x"})
        merged = json.dumps({"doi": "https://doi.org/10.65215/a", "ids": {"mag": "1"},
                             "locations": [{"landing_page_url": "https://arxiv.org/abs/%s"
                                            % ARX}]})
        self.assertEqual(cap.receipt_ids("openalex", merged.encode()),
                         {"doi:10.65215/a", "arXiv:" + ARX})
        s2 = json.dumps({"paperId": "abc", "externalIds": {"ArXiv": ARX}})
        self.assertEqual(cap.receipt_ids("semanticscholar", s2.encode()),
                         {"s2:abc", "arXiv:" + ARX})
        self.assertEqual(cap.receipt_ids("arxiv", atom([(ARX, TITLE, "x", 2024, "A B")])
                                         .encode()), {"arXiv:" + ARX})

    def test_citation_verdicts(self):
        row = {"title": TITLE, "year": 2024}
        good = {"resolved": True, "title": TITLE, "year": 2024}
        self.assertIsNone(cap.citation_verdict(row, [("arxiv", good), ("openalex", good)]))
        self.assertEqual(cap.citation_verdict(row, [("arxiv", good), ("alphaxiv", good)]),
                         "one-provider")
        self.assertEqual(cap.citation_verdict(row, []), cap.NO_REGISTRY)
        self.assertEqual(cap.citation_verdict(dict(row, unindexed_reason="a workshop"), []),
                         "unindexed-source")
        self.assertEqual(cap.citation_verdict({"title": "Other words", "year": 2024},
                                              [("arxiv", good), ("openalex", good)]),
                         "header-mismatch")

    def test_quote_fragments_ellipsis_and_marker(self):
        text = "In our study, %s, across the three services." % QUOTE
        self.assertIsNone(cap.quote_problem("caching lowers tail latency ... in every "
                                            "workload we measured [12]", text))
        self.assertEqual(cap.quote_problem("in every workload we measured \u2026 caching "
                                           "lowers tail latency", text), cap.NOT_IN_SOURCE)

    def test_search_records_per_connector(self):
        oa = json.dumps({"results": [{"id": "https://openalex.org/W1",
                                      "doi": "https://doi.org/10.48550/arxiv.2401.00001"},
                                     {"id": "https://openalex.org/W2", "doi": None}]})
        self.assertEqual(cap.search_records("openalex", oa.encode()),
                         [["openalex:W1", "arXiv:2401.00001"], ["openalex:W2"]])
        s2 = json.dumps({"data": [{"paperId": "abc", "externalIds": {"DOI": "10.1/X"}}]})
        self.assertEqual(cap.search_records("semanticscholar", s2.encode()),
                         [["s2:abc", "doi:10.1/x"]])
        cr = json.dumps({"message": {"items": [{"DOI": "10.1/Y"}]}})
        self.assertEqual(cap.search_records("crossref", cr.encode()), [["doi:10.1/y"]])
        orx = b"2401.00001v2 and 10.48550/arXiv.2401.00001 and 10.1145/z"
        self.assertEqual(cap.search_records("orx", orx),
                         [["arXiv:2401.00001"], ["doi:10.1145/z"]])

    # plan 128 ------------------------------------------------------------------
    def test_inner_quotation_marks_are_optional(self):
        # C4: curly or straight, single or double, in the quote or in the text
        text = "It just uses the same prompt \u201cLet\u2019s think step by step\u201d across all tasks."
        for quote in ("the same prompt 'Let's think step by step' across all tasks",
                      "the same prompt Let's think step by step across all tasks",
                      'the same prompt "Let\u2019s think step by step" across all tasks',
                      "the same prompt \u2018Lets think step by step\u2019 across all tasks"):
            self.assertIsNone(cap.quote_problem(quote, text), quote)
        self.assertIsNone(cap.quote_problem("uses the same prompt across",
                                            "uses 'the same' \"prompt\" across"))
        self.assertEqual(cap.quote_problem("the same prompt 'think slowly' across", text),
                         cap.NOT_IN_SOURCE)

    def test_arxiv_html_math_reads_as_rendered(self):
        # C5: LaTeXML keeps the TeX annotation beside the rendered symbol
        page = ('<p>and only yields performance gains when used with models of <math '
                'alttext="\\sim" display="inline"><semantics><mo>\u223c</mo><annotation '
                'encoding="application/x-tex">\\sim</annotation></semantics></math>100B '
                'parameters. We modify the input question <math alttext="\\mathbf{x}">'
                '<semantics><mi>\U0001d431</mi><annotation encoding="application/x-tex">'
                '\\mathbf{x}</annotation></semantics></math> into a prompt.</p>').encode()
        text = cap.html_to_text(page)
        for quote in ("used with models of ~100B parameters",
                      "used with models of \u223c100B parameters",
                      "used with models of \u223c 100B parameters",
                      "we modify the input question x into a prompt"):
            self.assertIsNone(cap.quote_problem(quote, text), quote)
        # the stored capture text of a real arXiv HTML page (K6 rater Y4, probe P1)
        self.assertIsNone(cap.quote_problem(
            "models of ~100B parameters",
            "used with models of    \u223c  \\sim   100B parameters.\nWe qualitatively"))
        self.assertEqual(cap.quote_problem("used with models of ~10B parameters", text),
                         cap.NOT_IN_SOURCE)

    def test_a_landing_page_holds_no_body(self):
        # C3: the rule and its constants
        body = " ".join("Sentence %d of the body reports one more finding about caching "
                        "and tail latency here." % i for i in range(cap.BODY_SENTENCES))
        self.assertEqual(cap.body_sentences(body), cap.BODY_SENTENCES)
        self.assertEqual(cap.body_sentences(" ".join([body.split(". ")[0] + "."] * 400)), 1)
        self.assertEqual(cap.body_sentences("Title. Authors. Abstract: We study caching."), 0)


class Captures(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="capture-unit-")
        self.addCleanup(shutil.rmtree, self.tmp)
        home = os.path.join(self.tmp, "home")
        os.makedirs(home)
        cfg = os.path.join(self.tmp, "gitconfig")
        with open(cfg, "w") as fh:
            fh.write("[user]\n\tname = U\n\temail = u@example.invalid\n"
                     "[commit]\n\tgpgsign = false\n[init]\n\tdefaultBranch = main\n")
        self.orx_data = os.path.join(self.tmp, "orx.json")
        orx = os.path.join(self.tmp, "orx")
        with open(orx, "w") as fh:
            fh.write("#!%s\nimport json, sys\nd = json.load(open(%r))\na = sys.argv[1:]\n"
                     "if a[:1] == ['logs']:\n    sys.stdout.write(d['logs'][a[1]])\n"
                     "elif a[:1] == ['runs']:\n    v = d['runs']\n"
                     "    sys.stdout.write(v if isinstance(v, str) else json.dumps(v))\n"
                     "elif a[:2] == ['paper', '--full'] and a[2] in d.get('papers', {}):\n"
                     "    sys.stdout.write(d['papers'][a[2]])\n"
                     "else:\n    sys.exit(1)\n" % (sys.executable, self.orx_data))
        os.chmod(orx, 0o755)
        self.orx({"logs": {"r1": "run r1\np95 120\n"}, "runs": [{"id": "r1", "status":
                                                                  "completed"}]})
        self.map_path = os.path.join(self.tmp, "map.json")
        self.map = {}
        self.env = {"HOME": home, "GIT_CONFIG_GLOBAL": cfg, "GIT_CONFIG_NOSYSTEM": "1",
                    "TEZGAH_ORX_BIN": orx, "TEZGAH_CAPTURE_MAP": self.map_path,
                    "LANG": "C.UTF-8"}
        patch = mock.patch.dict(os.environ, self.env)
        patch.start()
        self.addCleanup(patch.stop)
        self.set_map({ARXIV_API: atom([(ARX, TITLE, "We study caching.", 2024, "Ann Smith")]),
                      OPENALEX: openalex(),
                      HTML: "<html><style>p{}</style><p>In our study, %s.</p></html>" % QUOTE,
                      SEARCH_OA: json.dumps({"results": [
                          {"id": "https://openalex.org/W1",
                           "doi": "https://doi.org/10.48550/arxiv.%s" % ARX}]}),
                      SEARCH_AX: atom([(ARX, TITLE, "x", 2024, "Ann Smith")])})
        self.repo = os.path.join(self.tmp, "project")
        os.makedirs(self.repo)
        self.git("init", "-q")
        self.write(os.path.join(self.repo, ".gitignore"), "/.tezgah/\n")
        self.git("add", "-A")
        self.git("commit", "-q", "-m", "project")
        self.cli("init", "q", "--ask", "does caching lower tail latency?", "--question",
                 "does caching lower tail latency?", "--method", "qualitative", "--in", ITEM,
                 "--out", "other")
        self.base = tr.line_dir(self.repo, "q")
        st = tr._state(self.base)
        st.update({"rules": 8, "question_class": "R1", "orx_project": "p",
                   "known_items": ["arXiv:" + ARX]})
        if not self._testMethodName.startswith("test_stopping_committed_after"):
            st["stopping"] = {"rule": "saturation", "run": 1}
        self.write(self.at("state.json"), json.dumps(st))
        os.makedirs(self.at("experiments/h1"))
        self.write(self.at("experiments/h1/protocol.md"), "# h1\nprediction: x\nfalsifier: y\n")
        self.write(self.at("literature/" + NOTE), '# Smith\n\n> "%s" (sec. 4)\n' % QUOTE)
        self.write(self.at("literature/INDEX.jsonl"), json.dumps({
            "note": NOTE, "id": "arXiv:" + ARX, "class": "formal", "title": TITLE,
            "year": 2024, "first_author": "Smith"}) + "\n")
        self.write(self.at("claims.jsonl"), json.dumps({
            "id": "C1", "statement": "Smith reports lower tail latency", "kind": "literature",
            "proof": ["literature/" + NOTE], "quote": QUOTE}) + "\n")
        self.cli("commit", "q", "lock")

    # helpers -------------------------------------------------------------------
    def orx(self, data):
        with open(self.orx_data, "w") as fh:
            json.dump(data, fh)

    def set_map(self, entries):
        for url, body in entries.items():
            name = "b%d" % len(self.map)
            self.write(os.path.join(self.tmp, name), body)
            self.map[url] = name
        self.write(self.map_path, json.dumps(self.map))

    def write(self, path, body):
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(body)

    def at(self, rel):
        return os.path.join(self.base, rel)

    def git(self, *args):
        subprocess.run(["git", "-C", self.repo] + list(args), check=True, capture_output=True)

    def cli(self, *args, code=0):
        proc = subprocess.run([sys.executable, CLI] + list(args), cwd=self.repo,
                              capture_output=True, text=True)
        self.assertEqual(proc.returncode, code, proc.stdout + proc.stderr)
        return proc.stdout + proc.stderr

    def run_cmd(self, name, *args):
        out = io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(out):
            code = cap.COMMANDS[name](self.repo, list(args))
        return code, out.getvalue()

    def check(self, flags=None):
        errors, warnings, steps = [], [], {"#flags": flags or {}}
        cap.check(self.repo, "q", self.base, tr._state(self.base), errors, warnings, False,
                  True, steps)
        return errors, warnings, steps

    def rows(self, rel):
        return tr._row_objects(self.at(rel))

    def captured(self):
        for args in (("cite", "q"), ("fetch", "q", NOTE),
                     ("search", "q", "--tag", "primary", "--", "openalex", "caching", "tail"),
                     ("search", "q", "--tag", "counter", "--item", ITEM, "--", "arxiv",
                      "caching", "no", "effect")):
            code, out = self.run_cmd(*args)
            self.assertEqual(code, 0, out)

    def ws_log(self):
        return subprocess.run(["git", "-C", os.path.join(self.repo, ".tezgah"), "log",
                               "--format=%s"], capture_output=True, text=True).stdout

    # cases ---------------------------------------------------------------------
    def test_sound_captures_check_clean_and_commit_each_command(self):
        self.captured()
        receipts = self.rows(cap.RECEIPTS)
        # plan 128 C10: the canned map answers Crossref and S2 404, so no receipt for them
        self.assertEqual([r["provider"] for r in receipts], ["arxiv", "openalex"])
        self.assertEqual([r["resolved"] for r in receipts], [True, True])
        self.assertEqual(self.rows(cap.SOURCES)[-1]["access"], "full")
        self.assertEqual(self.rows(cap.SEARCHES)[0]["ids"], ["arXiv:" + ARX])
        for command in ("cite", "fetch", "search"):
            self.assertIn("capture: %s q" % command, self.ws_log())
        errors, warnings, steps = self.check()
        self.assertEqual(errors, [])
        self.assertEqual(steps.get("C1", []), [])
        self.assertIn("stopping q: saturation met", steps["#report"])

    def test_forged_receipt_row_is_not_derived_from_its_capture(self):
        self.captured()
        real = self.rows(cap.RECEIPTS)[0]
        with open(self.at(cap.RECEIPTS), "a") as fh:
            fh.write(json.dumps(dict(real, title="Another title")) + "\n")
        errors, _w, _s = self.check()
        self.assertTrue(any("not derived from its capture" in e for e in errors), errors)

    def test_capture_edited_in_a_later_commit_and_ledger_row_rewritten(self):
        self.captured()
        raw = self.rows(cap.RECEIPTS)[0]["file"]
        with open(self.at(raw), "a") as fh:
            fh.write("edited")
        self.cli("commit", "q", "edit")
        errors, _w, _s = self.check()
        self.assertTrue(any(raw in e and "changed after its first commit" in e
                            for e in errors), errors)
        self.assertTrue(any("hash mismatch" in e for e in errors), errors)
        with open(self.at(cap.SEARCHES)) as fh:
            lines = fh.readlines()
        self.write(self.at(cap.SEARCHES), "".join(lines[1:]))
        errors, _w, _s = self.check()
        self.assertTrue(any(e.startswith(cap.SEARCHES) and "after its first commit" in e
                            for e in errors), errors)

    def test_capture_exists_refuses_other_bytes(self):
        self.assertIsNone(cap.write_capture(self.base, "searches/raw/x.raw", b"a"))
        self.assertIsNone(cap.write_capture(self.base, "searches/raw/x.raw", b"a"))
        self.assertIn("capture exists", cap.write_captures(
            self.base, {"searches/raw/y.raw": b"b", "searches/raw/x.raw": b"c"}))
        self.assertFalse(os.path.exists(self.at("searches/raw/y.raw")))

    def test_search_files_the_systematic_review_connectors(self):
        """The allowlist's exit (X6, row 7): PubMed, Scopus and ACM DL through the same
        command. Scopus needs a key, and says which variable when it has none."""
        words = "caching tail"
        self.set_map({cap.SEARCH_URLS["pubmed"] % "caching+tail":
                      json.dumps({"esearchresult": {"idlist": ["42891471"]}}),
                      cap.SEARCH_URLS["acm"] % "caching+tail":
                      json.dumps({"message": {"items": [{"DOI": "10.1145/B"}]}})})
        code, out = self.run_cmd("search", "q", "--tag", "primary", "--", "pubmed",
                                 "caching", "tail")
        self.assertEqual(code, 0, out)
        self.assertEqual(self.rows(cap.SEARCHES)[-1]["connector"], "pubmed")
        self.assertEqual(self.rows(cap.SEARCHES)[-1]["ids"], ["pubmed:42891471"])
        self.assertEqual(self.run_cmd("search", "q", "--tag", "primary", "--", "scopus",
                                      "caching", "tail")[0], 2)
        os.environ["TEZGAH_SCOPUS_KEY"] = "k"
        self.set_map({cap.SEARCH_URLS["scopus"] % "caching+tail": json.dumps(
            {"search-results": {"entry": [{"prism:doi": "10.1145/A"}]}})})
        code, out = self.run_cmd("search", "q", "--tag", "primary", "--", "scopus",
                                 "caching", "tail")
        self.assertEqual(code, 0, out)
        self.assertEqual(self.rows(cap.SEARCHES)[-1]["ids"], ["doi:10.1145/a"])
        code, out = self.run_cmd("search", "q", "--tag", "primary", "--", "acm",
                                 "caching", "tail")
        self.assertEqual(code, 0, out)
        self.assertEqual(self.rows(cap.SEARCHES)[-1]["ids"], ["doi:10.1145/b"])

    def test_search_rows_screening_and_steps(self):
        code, out = self.run_cmd("search", "q", "--tag", "primary", "--", "curl", "x")
        self.assertEqual(code, 1)
        self.assertIn("connector not on the allowlist", out)
        self.assertEqual(self.run_cmd("search", "q", "--tag", "counter", "--", "arxiv",
                                      "x")[0], 2)
        self.run_cmd("search", "q", "--tag", "primary", "--", "openalex", "caching", "tail")
        self.write(self.at(cap.SCREENING), json.dumps({"search": 1, "id": "openalex:W7",
                                                       "decision": "kept"}) + "\n")
        st = tr._state(self.base)
        st["known_items"] = ["arXiv:2499.00009"]
        self.write(self.at("state.json"), json.dumps(st))
        with open(self.at(cap.SEARCHES), "a") as fh:
            fh.write(json.dumps({"n": 2, "connector": "openalex", "file": "searches/raw/"
                                 + "0" * 64 + ".raw", "sha256": "0" * 64, "hits": 0,
                                 "ids": []}) + "\n")
        errors, _w, steps = self.check()
        self.assertTrue(any("has no capture" in e for e in errors), errors)
        self.assertIn("screened-outside-search", steps["C1"])
        for step in ("one-connector", "no-counter-search", "known-item-missed"):
            self.assertIn(step, steps["C1"])

    def test_stopping_committed_after_the_first_search_is_no_rule(self):
        # setUp committed no stopping rule for this case
        st = tr._state(self.base)
        self.run_cmd("search", "q", "--tag", "primary", "--", "openalex", "caching", "tail")
        st["stopping"] = {"rule": "pragmatic", "risk": "late"}
        self.write(self.at("state.json"), json.dumps(st))
        self.cli("commit", "q", "late stopping")
        _e, _w, steps = self.check()
        self.assertIn("no-stopping-rule", steps["C1"])
        self.assertIn("stopping q: pragmatic met", steps["#report"])

    def test_receipt_refusals_and_header_step(self):
        self.write(self.at("literature/INDEX.jsonl"), json.dumps({
            "note": NOTE, "id": "arXiv:2499.99999", "class": "formal", "title": TITLE,
            "year": 2024}) + "\n")
        self.run_cmd("cite", "q")
        errors, _w, _s = self.check()
        self.assertTrue(any(cap.NO_REGISTRY in e for e in errors), errors)
        self.write(self.at("literature/INDEX.jsonl"), json.dumps({
            "note": NOTE, "id": "arXiv:" + ARX, "class": "formal", "title": "Other words "
            "entirely here", "year": 2024}) + "\n")
        self.run_cmd("cite", "q")
        errors, _w, steps = self.check()
        self.assertFalse([e for e in errors if "registry" in e or "providers" in e], errors)
        self.assertIn("header-mismatch", steps["C1"])

    def test_orx_runs_its_table_answer_reads_as_runs(self):
        """K6 rater Y5: orx 0.2.20's `orx runs` has no `--json` and prints a table, so
        the run census reported `did not print JSON`. The table's rows are the runs; an
        answer that is neither JSON nor that table still says so."""
        self.orx({"logs": {"r1": "run r1\n"}, "runs":
                  "ID                                    STATUS  EXPERIMENT  COMMIT  "
                  "DURATION  UPDATED\n"
                  "────────────────────────────────────  ──────  ──────────  ──────  "
                  "────────  ───────\n"
                  "38645db6-07c3-4098-a81b-069245bc4cef  done    join        0eb3669  6s   "
                  "     5h ago\n"})
        runs, err = cap.engine_runs({"orx_project": "p"})
        self.assertIsNone(err)
        self.assertEqual([(cap.run_id(r), r.get("status")) for r in runs],
                         [("38645db6-07c3-4098-a81b-069245bc4cef", "done")])
        self.orx({"logs": {"r1": "x"}, "runs": "no such project\n"})
        self.assertEqual(cap.engine_runs({"orx_project": "p"}),
                         (None, "orx runs p printed neither JSON nor a run table"))

    def test_a_receipt_recorded_from_a_429_never_drifts(self):
        """Plan 128 C10, confirmed here: `cite` writes no receipt for an answer other
        than 200, and `check --online` drifts only a receipt recorded from a 200, so an
        older 429 row is not read as drift when the provider answers."""
        row = {"id": "arXiv:" + ARX, "provider": "arxiv", "url": ARXIV_API, "file": None,
               "sha256": None, "fetched_at": "2026-01-01T00:00:00Z", "parser": cap.PARSER,
               "title": None, "first_author": None, "year": None, "abstract": None}
        self.set_map({ARXIV_API: atom([(ARX, "A different title", "x", 2024, "A B")])})
        self.append(cap.RECEIPTS, dict(row, status=429))
        _e, _w, steps = self.check({"online": True})
        self.assertFalse([line for line in steps["#report"] if "drifted" in line],
                         steps["#report"])
        # the same row at 200 is the one the rule reads
        self.write(self.at(cap.RECEIPTS), json.dumps(dict(row, status=200)) + "\n")
        _e, _w, steps = self.check({"online": True})
        self.assertIn("online q: arXiv:%s arxiv title drifted" % ARX, steps["#report"])

    def test_online_drift_and_abstract_only(self):
        self.map[HTML] = {"status": 404}
        self.write(self.map_path, json.dumps(self.map))
        self.run_cmd("cite", "q")
        self.run_cmd("fetch", "q", NOTE)
        self.assertEqual(self.rows(cap.SOURCES)[-1]["access"], "abstract")
        self.set_map({ARXIV_API: atom([(ARX, "A different title", "x", 2024, "Ann Smith")])})
        errors, _w, steps = self.check({"online": True})
        self.assertIn("online q: arXiv:%s arxiv title drifted" % ARX, steps["#report"])
        self.assertIn("online-drift", steps["C1"])
        self.assertIn("abstract-only", steps["C1"])
        self.assertFalse([e for e in errors if cap.NOT_IN_SOURCE in e], errors)

    def test_fetch_user_file_needs_ack_and_orx_comes_before_the_abstract(self):
        self.run_cmd("cite", "q")
        paper = os.path.join(self.tmp, "paper.txt")
        self.write(paper, "Section 4: %s.\n" % QUOTE)
        self.assertEqual(self.run_cmd("fetch", "q", NOTE, "--file", paper)[0], 2)
        self.assertEqual(self.run_cmd("fetch", "q", NOTE, "--file", paper, "--ack",
                                      "the user pasted it")[0], 0)
        row = self.rows(cap.SOURCES)[-1]
        with open(self.at(row["file"])) as fh:
            record = json.load(fh)
        self.assertEqual((record["access"], record["ack"]), ("user", "the user pasted it"))
        self.assertTrue(all(p["found"] for p in record["passages"]))
        self.map[HTML] = {"status": 404}
        self.write(self.map_path, json.dumps(self.map))
        body = " ".join(
            "Measure %d: the cache lowered tail latency in every workload we measured." % i
            for i in range(120))
        self.orx({"logs": {}, "runs": [], "papers": {ARX: body}})
        self.run_cmd("fetch", "q", NOTE)
        self.assertEqual(self.rows(cap.SOURCES)[-1]["access"], "full")

    def test_orx_metadata_and_abstract_read_as_abstract(self):
        """K6 raters Y5 and Y6: `orx paper --full` answers with metadata and an abstract
        for a paper it cannot read whole, and that was labelled `full`, so a verbatim body
        quote was refused. The same body test the open-access page gets applies."""
        self.run_cmd("cite", "q")
        self.map[HTML] = {"status": 404}
        self.write(self.map_path, json.dumps(self.map))
        self.orx({"logs": {}, "runs": [], "papers": {ARX: "Abstract only. %s." % QUOTE}})
        self.assertEqual(self.run_cmd("fetch", "q", NOTE)[0], 0)
        row = self.rows(cap.SOURCES)[-1]
        self.assertEqual(row["access"], "abstract")
        with open(self.at(row["file"])) as fh:
            record = json.load(fh)
        self.assertIn("not full text", record["reason"])

    def test_quote_absent_from_the_capture_is_refused(self):
        self.set_map({HTML: "<p>caching changed nothing we measured</p>"})
        self.run_cmd("cite", "q")
        self.run_cmd("fetch", "q", NOTE)
        errors, _w, _s = self.check()
        self.assertTrue(any(cap.NOT_IN_SOURCE in e for e in errors), errors)

    def test_source_values_refile_status_and_census(self):
        # a rules-8 `source` is refused until a committed state.json locks the
        # evaluation (its capture is committed at once, so a later lock could never
        # precede it), and this line's fixture locks none: commit one first
        st = tr._state(self.base)
        st["evaluation"] = {"metric": "p95", "baseline": "120 uncached",
                            "locked_at": "2026-01-01"}
        self.write(self.at("state.json"), json.dumps(st))
        self.cli("commit", "q", "evaluation lock")
        self.cli("source", "q", "h1", "--run", "r1", "--arm", "base", "--value", "p95=120")
        out = self.cli("source", "q", "h1", "--run", "r1", "--value", "p95=77", code=1)
        self.assertIn("value not in the run log", out)
        self.cli("source", "q", "h1", "--run", "r1", "--value", "scope=1", code=2)
        self.cli("source", "q", "h1", "--run", "r1")
        self.assertTrue(os.path.isfile(self.at("experiments/h1/raw/r1.1.log")))
        rows = self.rows("experiments/h1/results.jsonl")
        self.assertEqual(rows[0], {"source": "orx:r1", "log": "raw/r1.log", "run": "r1",
                                   "arm": "base", "p95": 120, "status": "completed"})
        self.assertEqual(rows[1]["log"], "raw/r1.1.log")
        self.assertIn("capture: source q", self.ws_log())
        self.orx({"logs": {}, "runs": [{"id": "r1", "status": "completed"},
                                       {"runId": "r9", "status": "failed"}]})
        _e, warnings, _s = self.check({"orx": True})
        self.assertIn("orx run r9 has no results row", warnings)
        self.assertNotIn("orx run r1 has no results row", warnings)

    def test_fetch_url_canned_post_key_and_missing(self):
        body = b'{"a":1}'
        key = "POST https://x.example/api %s" % hashlib.sha256(body).hexdigest()
        self.set_map({key: "answer"})
        self.assertEqual(cap.fetch_url("https://x.example/api", body), (200, b"answer"))
        self.assertEqual(cap.fetch_url("https://x.example/none"), (404, b""))

    # plan 127 review round one, group G2 -----------------------------------------
    def append(self, rel, *rows):
        os.makedirs(os.path.dirname(self.at(rel)), exist_ok=True)
        with open(self.at(rel), "a") as fh:
            fh.write("".join(json.dumps(r) + "\n" for r in rows))

    def index(self, **row):
        self.write(self.at("literature/INDEX.jsonl"), json.dumps(dict({
            "note": NOTE, "id": "arXiv:" + ARX, "class": "formal", "title": TITLE,
            "year": 2024, "first_author": "Smith"}, **row)) + "\n")

    def wsgit(self, *args, when=None):
        env = dict(os.environ, GIT_AUTHOR_DATE=when, GIT_COMMITTER_DATE=when) if when else None
        return subprocess.run(["git", "-C", os.path.join(self.repo, ".tezgah")] + list(args),
                              check=True, capture_output=True, text=True, env=env).stdout

    def test_search_row_with_no_file_has_no_capture_and_counts_for_nothing(self):
        # D1-1: a hand-typed counter row on a second connector, with no capture
        self.run_cmd("search", "q", "--tag", "primary", "--", "openalex", "caching", "tail")
        self.append(cap.SEARCHES, {"n": 2, "tag": "counter", "item": ITEM,
                                   "connector": "crossref", "hits": 0, "ids": []})
        errors, _w, steps = self.check()
        self.assertTrue(any("row 2" in e and "has no capture" in e for e in errors), errors)
        self.assertIn("one-connector", steps.get("C1", []))
        self.assertIn("no-counter-search", steps.get("C1", []))

    def test_source_row_without_its_own_record_sets_no_access(self):
        # D1-2: no `file`; a receipt's file; another note's source record
        self.run_cmd("cite", "q")
        receipt = next(r for r in self.rows(cap.RECEIPTS) if r["file"])
        record = json.dumps({"note": "lit/other.md", "access": "full", "passages": []}).encode()
        rel = "literature/.sources/%s.json" % hashlib.sha256(record).hexdigest()
        os.makedirs(self.at("literature/.sources"), exist_ok=True)
        with open(self.at(rel), "wb") as fh:
            fh.write(record)
        for row in ({"note": NOTE, "access": "full"},
                    {"note": NOTE, "file": receipt["file"], "sha256": receipt["sha256"],
                     "access": "full"},
                    {"note": NOTE, "file": rel, "sha256": hashlib.sha256(record).hexdigest(),
                     "access": "full"}):
            self.append(cap.SOURCES, row)
            errors, _w, steps = self.check()
            self.assertIn("source-not-captured", steps.get("C1", []), row)
        self.assertTrue(any(cap.SOURCES in e and "row 1" in e and "has no capture" in e
                            for e in errors), errors)

    def test_receipt_for_another_id_or_url_is_refused(self):
        # D1-4: the raw bytes must name the INDEX id, the url must be the table's; plan
        # 128 C6: bytes naming another id are no receipt for it, and a warning
        fake, real = "10.9999/invented.2024.001", "10.1000/real.2024.042"
        self.index(id="doi:" + fake)
        rows = []
        for provider, url, body in (
                ("crossref", "https://api.crossref.org/works/" + fake,
                 {"message": {"DOI": real, "title": [TITLE], "author": [{"family": "Smith"}],
                              "issued": {"date-parts": [[2024]]}}}),
                ("openalex", "https://api.openalex.org/works/doi:" + real,
                 {"doi": "https://doi.org/" + fake, "title": TITLE, "publication_year": 2024,
                  "authorships": [{"author": {"display_name": "Ann Smith"}}]})):
            data = json.dumps(body).encode()
            rel = "literature/.receipts/%s.raw" % hashlib.sha256(data).hexdigest()
            os.makedirs(self.at("literature/.receipts"), exist_ok=True)
            with open(self.at(rel), "wb") as fh:
                fh.write(data)
            rows.append({"id": "doi:" + fake, "provider": provider, "url": url, "status": 200,
                         "resolved": True, "file": rel,
                         "sha256": hashlib.sha256(data).hexdigest(), "title": TITLE,
                         "first_author": "Smith", "year": 2024, "abstract": None,
                         "parser": cap.PARSER})
        self.append(cap.RECEIPTS, *rows)
        errors, warnings, _s = self.check()
        self.assertFalse([e for e in errors if "crossref" in e], errors)
        self.assertTrue(any("crossref" in w and "doi:" + real in w for w in warnings), warnings)
        self.assertTrue(any("openalex" in e and "is not the openalex receipt URL" in e
                            for e in errors), errors)
        self.assertTrue(any(cap.NO_REGISTRY in e for e in errors), errors)

    def test_online_compares_the_id(self):
        # D1-4: a re-fetch naming another paper is id drift
        self.run_cmd("cite", "q")
        self.set_map({OPENALEX: openalex(aid="2401.99999")})
        _e, _w, steps = self.check({"online": True})
        self.assertIn("online q: arXiv:%s openalex id drifted" % ARX, steps["#report"])

    def test_stopping_committed_after_search_side_branch_neither_passes_nor_breaks(self):
        # D1-11: setUp committed no stopping rule for this case
        fork = self.wsgit("rev-parse", "HEAD").strip()
        main = self.wsgit("branch", "--show-current").strip()
        self.run_cmd("search", "q", "--tag", "primary", "--", "openalex", "caching", "tail")
        st = tr._state(self.base)
        st["stopping"] = {"rule": "pragmatic", "risk": "late"}
        self.write(self.at("state.json"), json.dumps(st))
        self.cli("commit", "q", "late stopping")
        with open(self.at(cap.SEARCHES)) as fh:
            ledger = fh.read()
        raw = self.rows(cap.SEARCHES)[0]["file"]
        with open(self.at(raw)) as fh:
            raw_text = fh.read()
        self.wsgit("checkout", "-q", "-b", "draft", fork)
        self.write(self.at("state.json"), json.dumps(st))
        self.wsgit("commit", "-qam", "stopping", when="2020-01-01T00:00:00Z")
        self.write(self.at(cap.SEARCHES), ledger)
        self.write(self.at(raw), raw_text)
        self.wsgit("add", "-A")
        self.wsgit("commit", "-qm", "search", when="2020-01-02T00:00:00Z")
        self.write(self.at(cap.SEARCHES), ledger.replace('"hits": 1', '"hits": 7'))
        self.write(self.at(raw), raw_text + "edited")
        self.wsgit("commit", "-qam", "rewrite", when="2020-01-03T00:00:00Z")
        self.wsgit("checkout", "-q", main)
        errors, _w, steps = self.check()
        self.assertIn("no-stopping-rule", steps["C1"])
        # the capture file reads HEAD's lineage; the ledger, like results, every ref (R2-3)
        self.assertFalse([e for e in errors if raw in e and "after its first commit" in e],
                         errors)
        self.assertTrue(any(e.startswith(cap.SEARCHES) and "after its first commit" in e
                            for e in errors), errors)

    def test_proof_ending_in_a_period_still_cites_the_note(self):
        # D2-4, D2-5: one cited-note reading for the quote check and the capture step
        note = "smith2020"
        self.write(self.at("literature/" + note), '# Smith\n\n> "%s" (sec. 4)\n' % QUOTE)
        self.index(note=note)
        self.write(self.at("claims.jsonl"), json.dumps({
            "id": "C1", "statement": "Smith reports lower tail latency", "kind": "literature",
            "proof": "see literature/%s." % note,
            "quote": "retrieval eliminates hallucinated citations"}) + "\n")
        self.run_cmd("cite", "q")
        _e, _w, steps = self.check()
        self.assertIn("source-not-captured", steps.get("C1", []))
        self.run_cmd("fetch", "q", note)
        errors, _w, _s = self.check()
        self.assertTrue(any("retrieval eliminates" in e and cap.NOT_IN_SOURCE in e
                            for e in errors), errors)

    def test_quote_fragments_must_be_found_in_order_at_check(self):
        # D2-3: both halves are in the source, the second only before the first
        self.write(self.at("claims.jsonl"), json.dumps({
            "id": "C1", "statement": "Smith reports lower tail latency", "kind": "literature",
            "proof": ["literature/" + NOTE],
            "quote": "in every workload we measured ... caching lowers tail latency"}) + "\n")
        self.run_cmd("cite", "q")
        self.run_cmd("fetch", "q", NOTE)
        errors, _w, _s = self.check()
        self.assertTrue(any("in every workload we measured ..." in e and cap.NOT_IN_SOURCE in e
                            for e in errors), errors)

    def test_quote_fragments_far_apart_in_order_are_found(self):
        self.write(self.at("literature/" + NOTE), "# Smith\n")
        self.set_map({HTML: "<p>caching lowers tail latency, %s and in every workload we "
                            "measured.</p>" % ("as table two shows " * 60)})
        self.write(self.at("claims.jsonl"), json.dumps({
            "id": "C1", "statement": "Smith reports lower tail latency", "kind": "literature",
            "proof": ["literature/" + NOTE],
            "quote": "caching lowers tail latency ... in every workload we measured"}) + "\n")
        self.run_cmd("cite", "q")
        self.run_cmd("fetch", "q", NOTE)
        errors, _w, _s = self.check()
        self.assertFalse([e for e in errors if cap.NOT_IN_SOURCE in e], errors)

    def test_citation_marker_split_by_tags_is_dropped(self):
        # D2-10: LaTeXML's `[<a>12</a>]` reads `[ 12 ]` once its tags are dropped
        self.set_map({HTML: '<p>caching lowers tail latency <cite>[<a href="#bib.bib12">12'
                            '</a>, <a href="#bib.bib13">13</a>]</cite> in every workload we '
                            'measured.</p>'})
        self.run_cmd("cite", "q")
        self.run_cmd("fetch", "q", NOTE)
        errors, _w, _s = self.check()
        self.assertFalse([e for e in errors if cap.NOT_IN_SOURCE in e], errors)
        self.assertEqual(cap.normalise("latency [ 12 ] in [3 , 4]"), "latency in")
        # an editorial change keeps its letter and loses only its brackets (Y6's probe)
        self.assertEqual(cap.normalise("[T]he thing"), cap.normalise("the thing"))
        self.assertEqual(cap.normalise("the [T]hing"), "the thing")

    def test_formal_row_with_an_empty_id_resolves_in_no_registry(self):
        # D2-6
        self.index(id="")
        errors, _w, _s = self.check()
        self.assertTrue(any(cap.NO_REGISTRY in e for e in errors), errors)
        self.index(id="", unindexed_reason="a workshop with no DOI")
        errors, _w, steps = self.check()
        self.assertFalse([e for e in errors if cap.NO_REGISTRY in e], errors)
        self.assertIn("unindexed-source", steps.get("C1", []))

    # plan 127 review round two and the K6 exits ----------------------------------
    def raw_search(self, connector, body, n=2, **row):
        data = body.encode()
        rel = "searches/raw/%s.raw" % hashlib.sha256(data).hexdigest()
        with open(self.at(rel), "wb") as fh:
            fh.write(data)
        self.append(cap.SEARCHES, dict({"n": n, "tag": "primary", "item": None,
                                        "connector": connector, "query": "x", "file": rel,
                                        "sha256": hashlib.sha256(data).hexdigest(),
                                        "hits": 0, "ids": []}, **row))

    def test_ledger_row_removed_from_head_while_a_tag_holds_it_is_refused(self):
        # R2-3: the ledgers have the results reading, every ref
        self.run_cmd("cite", "q")
        self.wsgit("tag", "keep")
        self.wsgit("reset", "-q", "--soft", "HEAD~1")
        with open(self.at(cap.RECEIPTS)) as fh:
            kept = [ln for ln in fh if '"openalex"' not in ln]
        self.write(self.at(cap.RECEIPTS), "".join(kept))
        self.wsgit("add", "-A")
        self.wsgit("commit", "-qm", "rewrite", when="2030-01-01T00:00:00Z")
        errors, _w, _s = self.check()
        self.assertTrue(any(e.startswith(cap.RECEIPTS) and "went missing after its first "
                            "commit" in e for e in errors), errors)

    def test_search_row_naming_a_file_outside_searches_raw_has_no_capture(self):
        # R2-4: refused, and it counts for nothing - not even saturation's last run
        self.run_cmd("cite", "q")
        self.run_cmd("search", "q", "--tag", "primary", "--", "openalex", "caching", "tail")
        receipt = next(r for r in self.rows(cap.RECEIPTS) if r["file"])
        self.append(cap.SEARCHES, {"n": 2, "tag": "primary", "connector": "openalex",
                                   "file": receipt["file"], "sha256": receipt["sha256"],
                                   "hits": 0, "ids": []})
        errors, _w, steps = self.check()
        self.assertTrue(any(cap.SEARCHES in e and "row 2" in e and "has no capture" in e
                            for e in errors), errors)
        self.assertIn("stopping q: saturation not met", steps["#report"])

    def test_one_capture_backs_one_search_row(self):
        # R2-5: a second row borrowing row 1's capture under another connector
        self.run_cmd("search", "q", "--tag", "primary", "--", "openalex", "caching", "tail")
        first = self.rows(cap.SEARCHES)[0]
        self.append(cap.SEARCHES, {"n": 2, "tag": "counter", "item": ITEM,
                                   "connector": "arxiv", "file": first["file"],
                                   "sha256": first["sha256"], "hits": 0, "ids": []})
        errors, _w, steps = self.check()
        self.assertTrue(any("row 2" in e and "has no capture" in e for e in errors), errors)
        self.assertIn("no-counter-search", steps.get("C1", []))
        # the writer keeps to it: a byte-identical answer writes no second row
        self.write(self.at(cap.SEARCHES), json.dumps(first) + "\n")
        code, out = self.run_cmd("search", "q", "--tag", "primary", "--", "openalex",
                                 "caching", "tail")
        self.assertEqual(code, 0, out)
        self.assertIn("no row was written", out)
        self.assertEqual(len(self.rows(cap.SEARCHES)), 1)

    def test_search_capture_must_parse_under_the_rows_connector(self):
        # R2-5: OpenAlex JSON filed as an arXiv answer re-parses as 0 hits yet is no Atom feed
        self.run_cmd("search", "q", "--tag", "primary", "--", "openalex", "caching", "tail")
        self.raw_search("arxiv", json.dumps({"results": []}), tag="counter", item=ITEM,
                        parser=cap.PARSER)
        errors, _w, steps = self.check()
        self.assertTrue(any("row 2" in e and "not derived from its capture" in e
                            for e in errors), errors)
        self.assertIn("one-connector", steps.get("C1", []))
        self.assertTrue(cap.schema_ok("semanticscholar", b'{"total": 0, "offset": 0}'))
        self.assertFalse(cap.schema_ok("crossref", b'{"results": []}'))

    def test_one_provider_with_header_agreement_is_a_step(self):
        # K-2
        self.map[OPENALEX] = {"status": 404}
        self.write(self.map_path, json.dumps(self.map))
        self.run_cmd("cite", "q")
        errors, _w, steps = self.check()
        self.assertFalse([e for e in errors if "provider" in e], errors)
        self.assertIn("one-provider", steps.get("C1", []))

    def test_receipts_of_an_id_the_index_no_longer_holds_are_not_judged(self):
        # K-3: correct the INDEX id, `cite` again, and the id mismatch clears; plan 128
        # C6: until then the alias resolves in no registry, with a warning, not refused
        alias, real = "10.1000/alias.7", "10.1000/real.7"
        body = {"message": {"DOI": real, "title": [TITLE], "author": [{"family": "Smith"}],
                            "issued": {"date-parts": [[2024]]}}}
        self.set_map({"https://api.crossref.org/works/" + alias: json.dumps(body),
                      "https://api.crossref.org/works/" + real: json.dumps(body)})
        self.index(id="doi:" + alias)
        self.run_cmd("cite", "q")
        errors, warnings, _s = self.check()
        self.assertFalse([e for e in errors if "not derived" in e], errors)
        self.assertTrue(any(cap.NO_REGISTRY in e for e in errors), errors)
        self.assertTrue(any("doi:" + real in w for w in warnings), warnings)
        self.index(id="doi:" + real)
        self.run_cmd("cite", "q")
        errors, _w, steps = self.check()
        self.assertFalse([e for e in errors if "not derived" in e or "provider" in e], errors)
        self.assertIn("one-provider", steps.get("C1", []))

    def test_an_openalex_or_s2_id_is_cited_through_its_own_registry(self):
        # an indexed source known only by its OpenAlex or Semantic Scholar id was
        # skipped by `cite`, so it cleared `resolves in no registry` only through
        # `unindexed_reason`; one registry answering it is the K-2 step
        s2 = json.dumps({"paperId": "abc123", "title": TITLE, "year": 2024,
                         "authors": [{"name": "Ann Smith"}]})
        self.set_map({"https://api.openalex.org/works/W7": openalex(wid="W7"),
                      cap.S2_PAPER % "abc123": s2})
        for rid in ("openalex:W7", "s2:abc123"):
            self.index(id=rid)
            code, out = self.run_cmd("cite", "q")
            self.assertEqual(code, 0, out)
            self.assertIn("receipt %s" % rid, out)
            errors, _w, steps = self.check()
            self.assertFalse([e for e in errors if cap.NO_REGISTRY in e or "not derived" in e
                              or "receipt URL" in e], errors)
            self.assertIn("one-provider", steps.get("C1", []))

    def test_quote_written_after_the_capture_is_found_in_the_whole_text(self):
        # K-4: the full text is a capture; a later quote needs no refetch
        later = "a second claim about warm caches"
        self.set_map({HTML: "<p>%s, %s and %s here.</p>" % (QUOTE, "padding words " * 80,
                                                            later)})
        self.run_cmd("cite", "q")
        self.run_cmd("fetch", "q", NOTE)
        with open(self.at(self.rows(cap.SOURCES)[-1]["file"])) as fh:
            record = json.load(fh)
        self.assertTrue(os.path.isfile(self.at(record["text_file"])))
        self.append("claims.jsonl", {"id": "C2", "statement": "Smith", "kind": "literature",
                                     "proof": ["literature/" + NOTE], "quote": later})
        self.append("claims.jsonl", {"id": "C3", "statement": "Smith", "kind": "literature",
                                     "proof": ["literature/" + NOTE],
                                     "quote": "We study caching"})
        errors, _w, _s = self.check()
        self.assertFalse([e for e in errors if cap.NOT_IN_SOURCE in e], errors)
        self.append("claims.jsonl", {"id": "C4", "statement": "Smith", "kind": "literature",
                                     "proof": ["literature/" + NOTE],
                                     "quote": "caching never helped anyone"})
        errors, _w, _s = self.check()
        self.assertTrue(any(cap.NOT_IN_SOURCE in e and "without quotation marks" in e
                            and "fetch --file" in e for e in errors), errors)
        with open(self.at(record["text_file"]), "a") as fh:
            fh.write("edited")
        errors, _w, _s = self.check()
        self.assertTrue(any(record["text_file"] in e and "hash mismatch" in e
                            for e in errors), errors)

    def test_hyphen_between_letters_reads_as_a_space_and_bare_doi_reads(self):
        # K-4, K-5
        self.assertEqual(cap.normalise("tail-latency drops; cach-\ning, 3-4"),
                         "tail latency drops; caching, 3-4")
        self.assertIsNone(cap.quote_problem("caching lowers tail latency",
                                            "Caching lowers tail-latency."))
        self.assertEqual(cap.norm_id("10.1145/ABC.1"), "doi:10.1145/abc.1")
        self.assertEqual(cap.norm_id("10.48550/arXiv.2401.00001"), "arXiv:2401.00001")
        self.assertIsNone(cap.norm_id("10.1/x"))

    def test_screening_an_id_no_search_returned_is_a_step(self):
        # K-8
        self.run_cmd("search", "q", "--tag", "primary", "--", "openalex", "caching", "tail")
        self.write(self.at(cap.SCREENING), json.dumps({"search": 1, "id": "openalex:W7",
                                                       "decision": "kept"}) + "\n")
        errors, _w, steps = self.check()
        self.assertFalse([e for e in errors if cap.SCREENING in e], errors)
        self.assertIn("screened-outside-search", steps.get("C1", []))

    # plan 128 ------------------------------------------------------------------
    def second_note(self, text):
        """A grey note `lit/jones.md` captured from the user's file holding `text`."""
        other = "lit/jones.md"
        self.write(self.at("literature/" + other), "# Jones\n")
        with open(self.at("literature/INDEX.jsonl"), "a") as fh:
            fh.write(json.dumps({"note": other, "id": "", "class": "grey",
                                 "title": "Jones"}) + "\n")
        paper = os.path.join(self.tmp, "jones.txt")
        self.write(paper, text)
        code, out = self.run_cmd("fetch", "q", other, "--file", paper, "--ack", "pasted")
        self.assertEqual(code, 0, out)
        return other

    def test_a_quote_found_in_any_cited_note_passes(self):
        # C1: a synthesis claim cites two full-text notes and quotes one of them
        self.run_cmd("cite", "q")
        self.run_cmd("fetch", "q", NOTE)
        other = self.second_note("Jones measured warm caches only.\n")
        claim = {"id": "C1", "statement": "Smith and Jones agree", "kind": "literature",
                 "proof": ["literature/" + NOTE, "literature/" + other], "quote": QUOTE}
        self.write(self.at("claims.jsonl"), json.dumps(claim) + "\n")
        errors, _w, _s = self.check()
        self.assertFalse([e for e in errors if cap.NOT_IN_SOURCE in e], errors)
        self.append("claims.jsonl", dict(claim, id="C2", quote="caching never helped anyone"))
        errors, _w, _s = self.check()
        self.assertTrue(any(e.startswith("claim C2") and cap.NOT_IN_SOURCE in e
                            and "literature/%s, literature/%s" % (NOTE, other) in e
                            for e in errors), errors)

    def test_quotes_of_a_superseded_claim_are_not_checked(self):
        # C2: the documented exit - a superseding claim without quotation marks
        self.run_cmd("cite", "q")
        self.run_cmd("fetch", "q", NOTE)
        self.write(self.at("claims.jsonl"), json.dumps({
            "id": "C1", "statement": 'Smith: "caching never helped anyone"',
            "kind": "literature", "proof": ["literature/" + NOTE]}) + "\n")
        errors, _w, _s = self.check()
        self.assertTrue(any(cap.NOT_IN_SOURCE in e for e in errors), errors)
        self.append("claims.jsonl", {"id": "C2", "statement": "Smith reports lower latency",
                                     "kind": "literature", "proof": ["literature/" + NOTE],
                                     "supersedes": "C1"})
        errors, _w, _s = self.check()
        self.assertFalse([e for e in errors if cap.NOT_IN_SOURCE in e], errors)

    def doi_line(self, page):
        """The INDEX row a DOI whose OpenAlex oa_url answers `page`; cite run."""
        doi = "10.1000/landing.1"
        work = json.dumps({"id": "https://openalex.org/W5", "doi": "https://doi.org/" + doi,
                           "title": TITLE, "publication_year": 2024,
                           "authorships": [{"author": {"display_name": "Ann Smith"}}],
                           "abstract_inverted_index": {"We": [0], "study": [1],
                                                       "caching.": [2]},
                           "open_access": {"oa_url": "https://repo.example/pub/5"}})
        self.set_map({"https://api.openalex.org/works/doi:" + doi: work,
                      "https://repo.example/pub/5": page})
        self.index(id="doi:" + doi)
        self.run_cmd("cite", "q")

    def test_an_oa_landing_page_is_abstract_only(self):
        # C3: K6 rater Y4's Tilburg/EUR Pure pages were labelled `full`
        self.doi_line("<html><h1>%s</h1><p>Ann Smith, Research output: Contribution to "
                      "journal</p><h2>Abstract</h2><p>We study caching.</p><p>Cite this: "
                      "APA Harvard BibTeX RIS</p></html>" % TITLE)
        code, out = self.run_cmd("fetch", "q", NOTE)
        self.assertEqual(code, 0, out)
        row = self.rows(cap.SOURCES)[-1]
        self.assertEqual((row["access"], row["url"]), ("abstract", "https://repo.example/pub/5"))
        with open(self.at(row["file"])) as fh:
            self.assertIn("landing page", json.load(fh)["reason"])
        errors, _w, steps = self.check()
        self.assertFalse([e for e in errors if cap.NOT_IN_SOURCE in e], errors)
        self.assertIn("abstract-only", steps.get("C1", []))

    def test_an_oa_page_holding_the_body_is_full(self):
        # C3: the same step reads a body as full text, and a quote it lacks is refused
        body = "".join("<p>Section %d reports one more measured finding about caching and "
                       "tail latency.</p>" % i for i in range(cap.BODY_SENTENCES))
        self.doi_line("<html>%s<p>In our study, %s.</p></html>" % (body, QUOTE))
        self.run_cmd("fetch", "q", NOTE)
        self.assertEqual(self.rows(cap.SOURCES)[-1]["access"], "full")
        errors, _w, _s = self.check()
        self.assertFalse([e for e in errors if cap.NOT_IN_SOURCE in e], errors)

    def test_a_receipt_naming_another_id_for_the_work_warns(self):
        # C6: Crossref answers an alias DOI with the work's other DOI; OpenAlex names it
        alias, real = "10.1000/alias.9", "10.1000/real.9"
        cross = {"message": {"DOI": real, "title": [TITLE], "author": [{"family": "Smith"}],
                             "issued": {"date-parts": [[2024]]}}}
        work = json.dumps({"id": "https://openalex.org/W9", "doi": "https://doi.org/" + alias,
                           "title": TITLE, "publication_year": 2024,
                           "authorships": [{"author": {"display_name": "Ann Smith"}}]})
        self.set_map({"https://api.crossref.org/works/" + alias: json.dumps(cross),
                      "https://api.openalex.org/works/doi:" + alias: work})
        self.index(id="doi:" + alias)
        self.run_cmd("cite", "q")
        self.run_cmd("cite", "q")
        errors, warnings, steps = self.check()
        self.assertFalse([e for e in errors if "not derived" in e or cap.NO_REGISTRY in e],
                         errors)
        named = [w for w in warnings if "doi:" + real in w]
        self.assertEqual(len(named), 1, warnings)
        self.assertIn("one-provider", steps.get("C1", []))

    def test_the_share_of_sources_without_full_text_takes_its_words(self):
        # C7: abstract-only counts with closed access, under any of the three words
        self.map[HTML] = {"status": 404}
        self.write(self.map_path, json.dumps(self.map))
        self.run_cmd("cite", "q")
        self.run_cmd("fetch", "q", NOTE)
        for words in ("not full text: 1 of 1", "closed-access: 1 of 1",
                      "abstract-only: 1 of 1"):
            self.write(self.at("to_human/report.md"), "# Report\n\n%s\n" % words)
            _e, warnings, _s = self.check()
            self.assertFalse([w for w in warnings if "closed-access share" in w], words)
        self.write(self.at("to_human/report.md"), "# Report\n\nclosed-access: 0 of 1\n")
        _e, warnings, _s = self.check()
        self.assertTrue(any("closed-access share" in w and "`not full text: 1 of 1`" in w
                            and "`abstract-only: 1 of 1`" in w for w in warnings), warnings)

    def test_two_branches_appending_to_a_ledger_and_merged_pass(self):
        # C8: K6 rater X3's probe-merge, on the receipts ledger
        self.run_cmd("cite", "q")
        main = self.wsgit("branch", "--show-current").strip()
        first = self.rows(cap.RECEIPTS)[0]
        mine, theirs = dict(first, fetched_at="2030-01-01"), dict(first, fetched_at="2030-01-02")
        self.wsgit("checkout", "-q", "-b", "other")
        self.append(cap.RECEIPTS, theirs)
        self.wsgit("commit", "-qam", "theirs")
        self.wsgit("checkout", "-q", main)
        self.append(cap.RECEIPTS, mine)
        self.wsgit("commit", "-qam", "mine")
        with open(self.at(cap.RECEIPTS)) as fh:
            merged = fh.read() + json.dumps(theirs) + "\n"
        subprocess.run(["git", "-C", os.path.join(self.repo, ".tezgah"), "merge", "-q",
                        "other", "-m", "merge"], capture_output=True)
        self.write(self.at(cap.RECEIPTS), merged)
        self.wsgit("add", "-A")
        self.wsgit("commit", "-qm", "merge")
        errors, _w, _s = self.check()
        self.assertFalse([e for e in errors if "append-only" in e], errors)
        # a row changed after the merge is still refused
        self.write(self.at(cap.RECEIPTS), merged.replace("2030-01-01", "2031-01-01"))
        errors, _w, _s = self.check()
        self.assertTrue(any(e.startswith(cap.RECEIPTS) and "append-only" in e
                            for e in errors), errors)

    def test_reordered_ledger_rows_are_refused(self):
        # C8: the ledgers' readers depend on order (the latest SOURCES record), so a
        # reordered ledger is refused like a changed one
        self.run_cmd("cite", "q")
        with open(self.at(cap.RECEIPTS)) as fh:
            lines = fh.read().splitlines()
        self.assertGreater(len(set(lines)), 1, lines)
        self.write(self.at(cap.RECEIPTS), "\n".join(reversed(lines)) + "\n")
        self.wsgit("add", "-A")
        self.wsgit("commit", "-qm", "reorder")
        errors, _w, _s = self.check()
        self.assertTrue(any(e.startswith(cap.RECEIPTS) and "append-only" in e
                            for e in errors), errors)

    def test_a_row_without_parser_is_re_derived_and_refused(self):
        # C9: no row is held to its hash on its own say-so
        self.captured()
        self.assertEqual({r.get("parser") for r in self.rows(cap.RECEIPTS)
                          + self.rows(cap.SEARCHES)}, {cap.PARSER})
        old = {k: v for k, v in self.rows(cap.RECEIPTS)[0].items() if k != "parser"}
        self.append(cap.RECEIPTS, dict(old, first_author="Smith-Jones"))
        self.raw_search("openalex", json.dumps({"results": [{"id": "https://openalex.org/W3"}]}),
                        n=3)
        errors, warnings, _s = self.check()
        self.assertTrue(any(e.startswith(cap.RECEIPTS) and "not derived from its capture" in e
                            for e in errors), errors)
        self.assertTrue(any(e.startswith(cap.SEARCHES) and "not derived from its capture" in e
                            for e in errors), errors)
        self.assertFalse([w for w in warnings if "parser" in w], warnings)

    def test_a_row_naming_a_newer_parser_is_refused(self):
        # C9: a row a later tezgah wrote is the one `parser` value read
        self.captured()
        old = self.rows(cap.RECEIPTS)[0]
        self.append(cap.RECEIPTS, dict(old, parser=cap.PARSER + 1))
        search = self.rows(cap.SEARCHES)[0]
        with open(self.at(search["file"])) as fh:
            body = fh.read() + " "
        self.raw_search(search["connector"], body, n=3, hits=search["hits"],
                        ids=search["ids"], parser=cap.PARSER + 1)
        errors, _w, _s = self.check()
        for rel in (cap.RECEIPTS, cap.SEARCHES):
            self.assertTrue(any(e.startswith(rel) and "newer than this check's" in e
                                for e in errors), errors)

    def test_cite_records_only_a_200_and_online_compares_only_those(self):
        # C10: a 429 at cite time read as drift once the provider answered
        s2 = cap.S2_PAPER % ("arXiv:" + ARX)
        self.write(os.path.join(self.tmp, "limited"), '{"message": "Too Many Requests"}')
        self.map[s2] = {"status": 429, "body": "limited"}
        self.write(self.map_path, json.dumps(self.map))
        code, out = self.run_cmd("cite", "q")
        self.assertEqual(code, 0, out)
        self.assertEqual([r["status"] for r in self.rows(cap.RECEIPTS)], [200, 200])
        # a ledger 2fb1370's cite wrote holds the 429 row
        data = b'{"message": "Too Many Requests"}'
        rel = "literature/.receipts/%s.raw" % hashlib.sha256(data).hexdigest()
        with open(self.at(rel), "wb") as fh:
            fh.write(data)
        self.append(cap.RECEIPTS, {"id": "arXiv:" + ARX, "provider": "semanticscholar",
                                   "url": s2, "status": 429, "resolved": False, "file": rel,
                                   "sha256": hashlib.sha256(data).hexdigest(),
                                   "fetched_at": "2026-01-01T00:00:00Z", "title": None,
                                   "first_author": None, "year": None, "abstract": None,
                                   "parser": cap.PARSER})
        self.set_map({s2: json.dumps({"paperId": "abc", "title": TITLE, "year": 2024,
                                      "authors": [{"name": "Ann Smith"}],
                                      "externalIds": {"ArXiv": ARX}})})
        _e, _w, steps = self.check({"online": True})
        self.assertFalse([r for r in steps["#report"] if "semanticscholar" in r],
                         steps["#report"])
        self.assertNotIn("online-drift", steps.get("C1", []))


if __name__ == "__main__":
    unittest.main()
