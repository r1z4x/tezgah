"""Captured evidence for research rules 8 (plan 127, spec 1.1-1.5).

The tool, not the session, fetches what a line cites: `cite` stores each registry's
raw answer as a receipt, `fetch` stores a source's extracted text and the passages
around every quote the line makes of it, `search` stores each connector's raw
output. `check` re-derives every receipt and search from those bytes offline,
refuses a capture that changed after its first commit, and names the certainty
steps a missing capture costs.

Interface (plan 127):
- COMMANDS = {"cite", "fetch", "search"}: handler(repo, args) -> exit code, prints.
- check(repo, slug, base, state, errors, warnings, strict, git, steps): reads
  steps["#flags"] ({"online", "orx"}), appends report lines to steps["#report"] and
  step names to steps[<claim id>].
- fetch_url(url, body=None, headers=None) -> (status, bytes): the one network call;
  TEZGAH_CAPTURE_MAP answers instead of the network when set.
- write_capture(base, rel, data) / write_captures(base, {rel: data}) -> problem|None.
- append_rows(base, rel, rows); commit_capture(repo, base, rels, command, slug) -> error|None.
- engine_runs(state) -> (runs|None, error): `orx runs` scoped by experiment.
- citation_problem(row) / quote_problem(quote, text) -> str|None: release-check's scorers.
"""
import collections
import decimal
import hashlib
import html
import json
import os
import re
import subprocess
import sys
import time
import unicodedata
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET

import tezgah_paths as tp
import tezgah_research as tr
import tezgah_research_stats as st

PROVIDERS = ("arxiv", "crossref", "openalex", "semanticscholar")
ORX_CONNECTORS = ("discover", "paper")
TAGS = ("primary", "snowball", "counter", "known")
SEARCH_CLASSES = ("R1", "R2", "R7", "R8", "R9", "R10")
STOPWORDS = {"a", "an", "the", "of", "and", "for", "in", "on", "to", "with"}
ATOM = "{http://www.w3.org/2005/Atom}"
ARXIV_API = "https://export.arxiv.org/api/query?id_list=%s&max_results=1"
S2_PAPER = ("https://api.semanticscholar.org/graph/v1/paper/%s"
            "?fields=title,authors,year,externalIds,abstract")
SEARCH_URLS = {
    "arxiv": "https://export.arxiv.org/api/query?search_query=all:%s&max_results=50",
    "crossref": "https://api.crossref.org/works?query=%s&rows=50",
    "openalex": "https://api.openalex.org/works?search=%s&per-page=50",
    "semanticscholar": ("https://api.semanticscholar.org/graph/v1/paper/search?query=%s"
                        "&limit=50&fields=title,externalIds,year")}
ORX_ARXIV = re.compile(r"(?<![\d.])(\d{4}\.\d{4,5})(?:v\d+)?(?!\d)")
ORX_DOI = re.compile(r"10\.\d{4,9}/[^\s\"'<>]+")
ID_ORDER = ("arXiv:", "doi:", "openalex:", "s2:")

INDEX = "literature/INDEX.jsonl"
RECEIPTS = "literature/.receipts/RECEIPTS.jsonl"
SOURCES = "literature/.sources/SOURCES.jsonl"
SEARCHES = "searches/SEARCHES.jsonl"
SCREENING = "searches/screening.jsonl"
CAPTURE = re.compile(r"^(?:literature/\.receipts/|literature/\.sources/|searches/raw/"
                     r"|experiments/[^/]+/raw/|instruments/gold/)")
LEDGER = re.compile(r"^(?:literature/\.receipts/RECEIPTS|literature/\.sources/SOURCES"
                    r"|searches/SEARCHES|instruments/[^/]+)\.jsonl$")
# A number as `source --value` takes it: `12`, `-0.5`, `1.2e-3`.
VALUE_NUMBER = r"-?\d+(?:\.\d+)?(?:[eE][-+]?\d+)?"
# A number as a run log writes it: VALUE_NUMBER, or one grouped by thousands (`12,345`),
# which is read whole, so its tail is never a number of its own (K6 rater Y2). A unit
# glued on after it - letters or `%` up to a word end (`22.3ms`, `512MB`, `3.2x`, `45%`)
# - leaves it that number (plan 128 K6); letters in front (`r1`, `h2`) or digits after
# the letters (a sha such as `2fb1370`) leave it no number.
# ponytail: a CSV row of integers whose later fields have three digits (`5,300`) reads
# as one grouped number; a log that means two fields there is the ceiling.
LOG_NUMBER = re.compile(r"(?<![\w.])-?(?:[1-9]\d{0,2}(?:,\d{3})+|\d+)(?:\.\d+)?"
                        r"(?:[eE][-+]?\d+)?(?=(?:[^\W\d_]+|%)?(?![\w]|\.\d))")

NO_REGISTRY = "resolves in no registry"
NOT_IN_SOURCE = "quote not in the captured source text"
# The version of the receipt and search parsers (`parse_receipt`, `receipt_ids`,
# `receipt_urls`, `schema_ok`, `search_records`) a row records as `parser`; a row
# without it predates the field (version 0). Bump it when a parser's reading changes.
PARSER = 1
# An open-access page is a work's body when its text holds this many distinct
# sentences of BODY_WORDS or more words: the repository landing pages of K6 rater Y4
# (metadata, the abstract, its citation exports) held 41 and 47, the arXiv HTML and
# PDF bodies beside them 497 to 814.
BODY_SENTENCES = 100
BODY_WORDS = 10


def log_numbers(text):
    """Every number of a run log, as Decimals: what a `--value` has to equal."""
    return {decimal.Decimal(t.replace(",", "")) for t in LOG_NUMBER.findall(text)}


# --- the shared capture helpers -------------------------------------------------
def fetch_url(url, body=None, headers=None):
    """(status, bytes) of one GET (or a POST when `body` is bytes). The only network
    call of the capture commands: with TEZGAH_CAPTURE_MAP set, the map answers - a GET
    keyed by its URL, a POST by `POST <url> <sha256 of body>`, an unknown key 404."""
    cmap = os.environ.get("TEZGAH_CAPTURE_MAP")
    if cmap:
        key = url if body is None else "POST %s %s" % (url, hashlib.sha256(body).hexdigest())
        try:
            with open(cmap, encoding="utf-8") as fh:
                table = json.load(fh)
        except (OSError, ValueError):
            table = {}
        entry = table.get(key) if isinstance(table, dict) else None
        if entry is None:
            return 404, b""
        status, rel = ((200, entry) if isinstance(entry, str)
                       else (int(entry.get("status", 200)), entry.get("body")))
        if not rel:
            return status, b""
        try:
            with open(os.path.join(os.path.dirname(os.path.abspath(cmap)), rel), "rb") as fh:
                return status, fh.read()
        except OSError:
            return status, b""
    request = urllib.request.Request(url, data=body, headers=dict(
        {"User-Agent": "tezgah-research"}, **(headers or {})))
    try:
        with urllib.request.urlopen(request, timeout=30) as resp:
            return resp.status, resp.read()
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read()
    except (urllib.error.URLError, OSError, ValueError):
        return 0, b""


def run_orx(args):
    """(exit code or None when orx is missing, stdout bytes)."""
    orx = tp.orx_bin()
    if not orx:
        return None, b""
    try:
        proc = subprocess.run([orx] + list(args), capture_output=True, timeout=600)
    except (OSError, subprocess.TimeoutExpired):
        return None, b""
    return proc.returncode, proc.stdout


def engine_runs(state):
    """(runs, error): `orx runs <orx_project>`, scoped by `--experiment <orx_experiment>`
    when the line names one, as a list of objects; (None, None) without a project."""
    project = state.get("orx_project")
    if not isinstance(project, str) or not project.strip():
        return None, None
    argv = ["runs", project]
    if isinstance(state.get("orx_experiment"), str) and state["orx_experiment"].strip():
        argv += ["--experiment", state["orx_experiment"]]
    code, out = run_orx(argv)
    if code != 0:
        return None, "orx %s failed" % " ".join(argv)
    try:
        doc = json.loads(out.decode("utf-8"))
    except (UnicodeDecodeError, ValueError):
        return None, "orx %s did not print JSON" % " ".join(argv)
    runs = doc.get("runs") if isinstance(doc, dict) else doc
    return [r for r in runs if isinstance(r, dict)] if isinstance(runs, list) else [], None


def run_id(run):
    return run.get("id") or run.get("runId")


def write_captures(base, files):
    """Write every `{rel: bytes}` under `base`, or nothing: a target that exists with
    other bytes is the `capture exists` refusal (identical bytes are already there)."""
    for rel, data in sorted(files.items()):
        path = os.path.join(base, rel)
        if os.path.lexists(path):
            try:
                with open(path, "rb") as fh:
                    if fh.read() == data:
                        continue
            except OSError:
                pass
            return "%s: capture exists with other bytes; a capture is written once" % rel
    for rel, data in files.items():
        path = os.path.join(base, rel)
        if not os.path.exists(path):
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, "wb") as fh:
                fh.write(data)
    return None


def write_capture(base, rel, data):
    return write_captures(base, {rel: data})


def append_rows(base, rel, rows):
    """Append JSON rows to a ledger, repairing an unterminated tail first."""
    path = os.path.join(base, rel)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "a+b") as fh:
        tr.truncate_to_committed(fh)
        fh.write(b"".join(json.dumps(r).encode("utf-8") + b"\n" for r in rows))


def commit_capture(repo, base, rels, command, slug):
    """Commit exactly `rels` (line-relative) as `capture: <command> <slug>` in
    `.tezgah`'s repository, or the project's when `.tezgah` is folded; error or None."""
    ws = tp.ensure_workspace(repo)
    if ws is None and tr.folded(repo):
        top = repo

        def git(*args):
            return subprocess.run(["git", "-C", repo] + list(args), capture_output=True,
                                  text=True)
    elif ws is None:
        return "no repository to commit the capture into (.tezgah could not be set up)"
    else:
        top = ws

        def git(*args):
            return tp.ws_git(repo, *args)
    names = [os.path.relpath(os.path.realpath(os.path.join(base, r)), os.path.realpath(top))
             for r in rels]
    try:
        done = git("add", "--", *names)
        if not done.returncode:
            done = git("commit", "-q", "-m", "capture: %s %s" % (command, slug), "--", *names)
    except OSError as exc:
        return "commit failed: %s" % exc
    if done.returncode:
        return "commit failed: %s" % (done.stderr or done.stdout).strip()
    return None


def _now():
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _sha(data):
    return hashlib.sha256(data).hexdigest()


def _rows(base, rel):
    return tr._row_objects(os.path.join(base, rel))


def _read(base, rel):
    """Bytes of a line-relative file, or None (also for a path leaving the line)."""
    if not isinstance(rel, str) or not rel or os.path.isabs(rel) or ".." in rel.split("/"):
        return None
    try:
        with open(os.path.join(base, rel), "rb") as fh:
            return fh.read()
    except OSError:
        return None


def _misuse(message):
    print("tezgah-research: %s" % message, file=sys.stderr)
    return 2


def _line(repo, slug):
    return tr.line_dir(repo, slug) if slug in tr.slugs(repo) else None


# --- text and ids -----------------------------------------------------------------
QUOTE_MARKS = str.maketrans({"\u2018": "'", "\u2019": "'", "\u201a": "'", "\u201b": "'",
                             "\u201c": '"', "\u201d": '"', "\u201e": '"', "\u201f": '"',
                             "\u2013": "-", "\u2014": "-", "\u223c": "~"})
# A TeX command and the token it sits in: LaTeXML's annotation beside rendered math
# (`∼ \sim`, `𝐱 \mathbf{x}`) reads as the rendered symbol alone.
TEX_TOKEN = re.compile(r"\S*\\[A-Za-z]+\S*")
# A space beside a math symbol (`∼ 100B` against `~100B`): rendered math has none.
MATH_SPACE = re.compile(r" ?([%s]) ?" % re.escape("".join(
    sorted(set("+<=>|~\u00ac\u00b1\u00d7\u00f7") | {chr(c) for c in range(0x2000, 0x2c00)
                                                    if unicodedata.category(chr(c)) == "Sm"}))))


def normalise(text):
    """Spec 0's text normalisation, for quotes, passages and titles."""
    text = unicodedata.normalize("NFKC", str(text or ""))
    text = TEX_TOKEN.sub(" ", text)
    # a marker split by tags or spaces (LaTeXML's `[<a>12</a>]` reads `[ 12 ]`) too
    text = re.sub(r"\[\s*\d+(?:\s*[,\u2013-]\s*\d+)*\s*\]", "", text).translate(QUOTE_MARKS)
    text = re.sub(r"-\s+", "", text)
    # a hyphen between two letters reads as a space: `tail-latency` quotes `tail latency`
    text = re.sub(r"(?<=[^\W\d_])-(?=[^\W\d_])", " ", text)
    # inner quotation marks are optional, in the quote and in the text (plan 128 C4)
    text = text.replace('"', "").replace("'", "")
    return MATH_SPACE.sub(r"\1", " ".join(text.split())).casefold().strip()


def body_sentences(text):
    """The distinct sentences of >= BODY_WORDS words in `text`: a work's body holds
    BODY_SENTENCES of them, a landing page (metadata and abstract) fewer."""
    return len({s for s in re.split(r"(?<=[.!?])\s+", normalise(text))
                if len(s.split()) >= BODY_WORDS})


# A bare arXiv id: new style `YYMM.NNNN[N]`, old style `archive[.SUB]/YYMMNNN`
ARXIV_BARE = re.compile(r"((?:\d{2}(?:0[1-9]|1[0-2])\.\d{4,5})|(?:[a-z-]+(?:\.[A-Z]{2})?/"
                        r"\d{2}(?:0[1-9]|1[0-2])\d{3}))(?:v\d+)?$")


def norm_id(raw):
    """The normalised id (`arXiv:`, `doi:`, `openalex:W`, `s2:`), or None. A bare arXiv
    id is read from a string only: a JSON number is a number, never an id."""
    s = str(raw or "").strip()
    low = s.lower()
    if low.startswith(("https://", "http://", "arxiv.org/", "www.arxiv.org/")):
        m = ARXIV_URL.search(s)
        if m:
            return "arXiv:" + m.group(1)
    m = ARXIV_BARE.match(s) if isinstance(raw, str) else None
    if m:
        return "arXiv:" + m.group(1)
    if re.match(r"10\.\d{4,9}/\S", low):
        s = low = "doi:" + low
    for prefix in ("https://doi.org/", "http://doi.org/", "https://dx.doi.org/"):
        if low.startswith(prefix):
            s = low = "doi:" + low[len(prefix):]
    if low.startswith(("https://openalex.org/", "http://openalex.org/")):
        return "openalex:" + s.rsplit("/", 1)[1]
    m = re.match(r"(?i)arxiv:\s*(\S+?)(?:v\d+)?$", s)
    if m:
        return "arXiv:" + m.group(1)
    if low.startswith("doi:") and low[4:].strip():
        doi = low[4:].strip()
        if doi.startswith("10.48550/arxiv."):
            return "arXiv:" + re.sub(r"v\d+$", "", doi[len("10.48550/arxiv."):])
        return "doi:" + doi
    for prefix in ("openalex:", "s2:"):
        if low.startswith(prefix) and s[len(prefix):].strip():
            return prefix + s[len(prefix):].strip()
    return None


def identity(ids):
    """A record's identity: its first id in the order arXiv, doi, openalex, s2."""
    for prefix in ID_ORDER:
        for i in ids:
            if i.startswith(prefix):
                return i
    return ids[0] if ids else None


def _bare(rid):
    return rid.split(":", 1)[1] if rid and ":" in rid else rid


def _json(data):
    try:
        return json.loads(data.decode("utf-8"))
    except (UnicodeDecodeError, ValueError):
        return None


def _dig(obj, *path):
    for key in path:
        if isinstance(key, int):
            obj = obj[key] if isinstance(obj, list) and len(obj) > key else None
        else:
            obj = obj.get(key) if isinstance(obj, dict) else None
    return obj


def _text(value):
    return " ".join(value.split()) if isinstance(value, str) and value.strip() else None


def _last_word(name):
    words = str(name).split() if isinstance(name, str) else []
    return words[-1] if words else None


def _year(value):
    if isinstance(value, bool):
        return None
    try:
        return int(str(value)[:4]) if isinstance(value, str) else int(value)
    except (TypeError, ValueError):
        return None


def _atom_entries(data):
    try:
        root = ET.fromstring(data)
    except ET.ParseError:
        return []
    out = []
    for entry in root.iter(ATOM + "entry"):
        def field(tag, el=entry):
            found = el.find(tag)
            return found.text if found is not None and found.text else ""
        out.append({"id": field(ATOM + "id"), "title": field(ATOM + "title"),
                    "published": field(ATOM + "published"),
                    "summary": field(ATOM + "summary"),
                    "author": field("%sauthor/%sname" % (ATOM, ATOM))})
    return out


def html_to_text(data):
    """Tags dropped (script and style with their content), entities unescaped."""
    text = data.decode("utf-8", "replace")
    text = re.sub(r"(?is)<(script|style)\b.*?</\1\s*>", " ", text)
    return html.unescape(re.sub(r"(?s)<[^>]*>", " ", text))


# --- 1.1 receipts -----------------------------------------------------------------
def receipt_urls(rid):
    """[(provider, url)] queried for a normalised id; [] for an id `cite` skips."""
    if rid and rid.startswith("arXiv:"):
        a = rid[6:]
        return [("arxiv", ARXIV_API % a),
                ("crossref", "https://api.crossref.org/works/10.48550/arXiv." + a),
                ("openalex", "https://api.openalex.org/works/doi:10.48550/arXiv." + a),
                ("semanticscholar", S2_PAPER % ("arXiv:" + a))]
    if rid and rid.startswith("doi:"):
        d = rid[4:]
        return [("crossref", "https://api.crossref.org/works/" + d),
                ("openalex", "https://api.openalex.org/works/doi:" + d),
                ("semanticscholar", S2_PAPER % ("DOI:" + d))]
    if rid and rid.startswith("openalex:"):
        return [("openalex", "https://api.openalex.org/works/" + rid[9:])]
    if rid and rid.startswith("s2:"):
        return [("semanticscholar", S2_PAPER % rid[3:])]
    return []


ARXIV_URL = re.compile(r"(?i)arxiv\.org/(?:abs|pdf|html)/(\S+?)(?:v\d+)?(?:\.pdf)?/?$")


def _url_id(value):
    if not isinstance(value, str):
        return None
    m = ARXIV_URL.search(value.strip())
    return "arXiv:" + m.group(1) if m else norm_id(value)


def receipt_ids(provider, data):
    """The normalised ids a provider's answer names: arXiv entry ids, Crossref
    `message.DOI`, OpenAlex `id`/`doi`/`ids` and location URLs (a merged work keeps an
    arXiv preprint there), S2 `paperId`/`externalIds`."""
    if provider == "arxiv":
        values = [e["id"] for e in _atom_entries(data or b"")]
    else:
        doc = _json(data or b"")
        doc = doc if isinstance(doc, dict) else {}
        values = []
        if provider == "crossref":
            values = [("doi:", _dig(doc, "message", "DOI"))]
        elif provider == "openalex":
            ids = doc.get("ids") if isinstance(doc.get("ids"), dict) else {}
            places = [doc.get("primary_location"), doc.get("best_oa_location")]
            places += doc.get("locations") if isinstance(doc.get("locations"), list) else []
            values = [doc.get("id"), doc.get("doi")] + list(ids.values()) + [
                p.get(k) for p in places if isinstance(p, dict)
                for k in ("landing_page_url", "pdf_url")]
        elif provider == "semanticscholar":
            ext = doc.get("externalIds") if isinstance(doc.get("externalIds"), dict) else {}
            values = [("s2:", doc.get("paperId")), ("doi:", ext.get("DOI")),
                      ("arXiv:", ext.get("ArXiv"))]
    values = [v[0] + v[1] if isinstance(v, tuple) and isinstance(v[1], str) else v
              for v in values]
    return {i for i in map(_url_id, values) if i}


def parse_receipt(provider, rid, status, data):
    """{resolved, title, first_author, year, abstract} of one provider's answer, by the
    provider field table of spec 1.1; parsed fields None when absent."""
    out = {"resolved": False, "title": None, "first_author": None, "year": None,
           "abstract": None}
    if status != 200 or not data:
        return out
    if provider == "arxiv":
        aid = _bare(rid) or ""
        hit = re.compile(r"(?<![\d.])%s(?:v\d+)?/?$" % re.escape(aid))
        for entry in _atom_entries(data):
            title = _text(entry["title"])
            if aid and hit.search(entry["id"].strip()) and title and title != "Error":
                out.update(title=title, first_author=_last_word(entry["author"]),
                           year=_year(entry["published"]), abstract=_text(entry["summary"]))
                break
    else:
        doc = _json(data)
        if not isinstance(doc, dict):
            return out
        if provider == "crossref":
            msg = doc.get("message")
            abstract = _dig(msg, "abstract")
            out.update(title=_text(_dig(msg, "title", 0)),
                       first_author=_text(_dig(msg, "author", 0, "family")),
                       year=_year(_dig(msg, "issued", "date-parts", 0, 0)),
                       abstract=_text(re.sub(r"<[^>]+>", " ", abstract))
                       if isinstance(abstract, str) else None)
        elif provider == "openalex":
            index = doc.get("abstract_inverted_index")
            words = {}
            if isinstance(index, dict):
                for word, places in index.items():
                    for place in places if isinstance(places, list) else ():
                        if isinstance(place, int):
                            words[place] = word
            out.update(title=_text(doc.get("title")),
                       first_author=_last_word(_dig(doc, "authorships", 0, "author",
                                                    "display_name")),
                       year=_year(doc.get("publication_year")),
                       abstract=_text(" ".join(words[k] for k in sorted(words))))
        elif provider == "semanticscholar":
            out.update(title=_text(doc.get("title")),
                       first_author=_last_word(_dig(doc, "authors", 0, "name")),
                       year=_year(doc.get("year")), abstract=_text(doc.get("abstract")))
    out["resolved"] = bool(out["title"])
    return out


def _title_words(title):
    return set(re.findall(r"[a-z0-9]+", normalise(title))) - STOPWORDS


def title_agrees(index_title, receipt_title):
    """citecheck's measure: max(|a&b|/|a|b|, |a&b|/|b|) >= 0.5 over title words."""
    a, b = _title_words(index_title), _title_words(receipt_title)
    if not a or not b:
        return False
    both = len(a & b)
    return max(both / len(a | b), both / len(b)) >= 0.5


def header_agrees(row, rec):
    year, theirs = _year(row.get("year")), rec.get("year")
    author = str(row.get("first_author") or "").strip()
    return (title_agrees(row.get("title"), rec.get("title")) and year is not None
            and theirs is not None and abs(year - theirs) <= 1
            and (not author or author.casefold()
                 == str(rec.get("first_author") or "").casefold()))


def _provider(name):
    name = str(name or "").lower()
    return "arxiv" if name == "alphaxiv" or name.startswith("orx") else name


def citation_verdict(row, recs):
    """The 1.1 refusal substring, the step name, or None, for an INDEX row and its
    [(provider, parsed receipt)]: one provider is the `one-provider` step."""
    resolved = [(p, r) for p, r in recs if r.get("resolved")]
    if not resolved:
        reason = row.get("unindexed_reason")
        return "unindexed-source" if isinstance(reason, str) and reason.strip() else NO_REGISTRY
    if not any(header_agrees(row, r) for _p, r in resolved):
        return "header-mismatch"
    if len({_provider(p) for p, _r in resolved}) < 2:
        return "one-provider"
    return None


def citation_problem(row):
    """release-check's scorer: the 1.1 verdict of one INDEX-like row, its four
    providers queried in memory (no file written)."""
    rid = norm_id(row.get("id"))
    return citation_verdict(row, [(p, parse_receipt(p, rid, *fetch_url(url)))
                                  for p, url in receipt_urls(rid)])


def cmd_cite(repo, args):
    if len(args) != 1:
        return _misuse("cite <slug>")
    slug = args[0]
    base = _line(repo, slug)
    if base is None:
        return _misuse("no such research line: %s" % slug)
    files, receipts, asked = {}, [], False
    for row in _rows(base, INDEX):
        if row.get("class") != "formal":
            continue
        rid = norm_id(row.get("id"))
        urls = receipt_urls(rid)
        if not urls:
            print("skipped %s: id %r is not an arXiv, DOI, OpenAlex or Semantic Scholar id"
                  % (row.get("note"), row.get("id")))
            continue
        for provider, url in urls:
            asked = True
            status, data = fetch_url(url)
            if status != 200:
                # an answer other than 200 (a 404, a 429 rate limit) is no receipt: a
                # later `check --online` would read the provider's answer as drift
                print("receipt %s %s: status %d, not recorded" % (rid, provider, status))
                continue
            parsed = parse_receipt(provider, rid, status, data)
            rel = "literature/.receipts/%s.raw" % _sha(data) if data else None
            if rel:
                files[rel] = data
            receipts.append(dict({"id": rid, "provider": provider, "url": url,
                                  "status": status, "resolved": parsed["resolved"],
                                  "file": rel, "sha256": _sha(data) if data else None,
                                  "fetched_at": _now(), "parser": PARSER},
                                 **{k: parsed[k] for k in ("title", "first_author", "year",
                                                           "abstract")}))
            print("receipt %s %s: status %d, %s" % (rid, provider, status, "resolved"
                                                    if parsed["resolved"] else "unresolved"))
    if not receipts:
        print("cite %s: %s" % (slug, "no registry answered 200, so nothing was written"
                               if asked else "no formal row with an arXiv, DOI, OpenAlex "
                               "or Semantic Scholar id to cite"))
        return 0
    return _store(repo, base, slug, "cite", files, RECEIPTS, receipts)


def _store(repo, base, slug, command, files, ledger, rows):
    problem = write_captures(base, files)
    if problem:
        print("FAIL %s: %s" % (slug, problem))
        return 1
    append_rows(base, ledger, rows)
    problem = commit_capture(repo, base, sorted(files) + [ledger], command, slug)
    if problem:
        print("FAIL %s: %s" % (slug, problem))
        return 1
    return 0


# --- 1.2 sources --------------------------------------------------------------------
QUOTED = re.compile(r"[\"\u201c]([^\"\u201c\u201d]+)[\"\u201d]")
BLOCKQUOTE = re.compile(r"(?m)^\s*>\s*[\"\u201c](.+?)[\"\u201d]")


def quote_fragments(quote):
    """A quote split on `...`, `…` and `[...]`, normalised; fragments of >= 3 words."""
    parts = re.split(r"\[(?:\.\.\.|\u2026)\]|\.\.\.|\u2026", str(quote))
    return [f for f in (normalise(p) for p in parts) if len(f.split()) >= 3]


def _locate(fragments, text):
    """[(fragment, index or -1)], each searched after the previous match."""
    out, pos = [], 0
    for frag in fragments:
        i = text.find(frag, pos)
        out.append((frag, i))
        if i >= 0:
            pos = i + len(frag)
    return out


def quote_problem(quote, text):
    """release-check's scorer: the 1.2 refusal when a fragment of `quote` is absent
    from `text` (in order), else None."""
    found = _locate(quote_fragments(quote), normalise(text))
    return NOT_IN_SOURCE if any(i < 0 for _f, i in found) else None


def _claims(base):
    return [c for c in _rows(base, "claims.jsonl") if isinstance(c.get("id"), str)]


def cited_tokens(proof):
    """The path tokens a proof cites, trailing sentence punctuation stripped: one
    reading for the capture rules (`_citing`) and the start level (`start_level`),
    so `see literature/smith2020.` cites `smith2020` for both."""
    return {t.rstrip(".,;:)") for t in tr._cited(proof)}


def _citing(claims, note):
    want = {"literature/" + note, note}
    return [c for c in claims if want & cited_tokens(c.get("proof"))]


def claim_quotes(claim):
    """A claim's quotes: its `quote` field and every double-quoted span of >= 3 words
    in its statement."""
    quote = claim.get("quote")
    out = [q for q in (quote if isinstance(quote, list) else [quote]) if isinstance(q, str)]
    out += [q for q in QUOTED.findall(str(claim.get("statement") or "")) if len(q.split()) >= 3]
    return list(dict.fromkeys(q for q in out if q.strip()))


def note_quotes(base, note):
    """The note's own `> "..."` blockquotes."""
    data = _read(base, "literature/" + note)
    return [q for q in BLOCKQUOTE.findall(data.decode("utf-8", "replace")) if q.strip()] \
        if data else []


def gather_quotes(base, note, claims):
    """The quotes the line makes of `note`: those of each claim citing it, and the
    note's own blockquotes."""
    return list(dict.fromkeys([q for c in _citing(claims, note) for q in claim_quotes(c)]
                              + note_quotes(base, note)))


def _index_row(base, note):
    return next((r for r in _rows(base, INDEX) if r.get("note") == note), None)


def _receipts_for(base, rid):
    return [r for r in _rows(base, RECEIPTS) if norm_id(r.get("id")) == rid]


def cmd_fetch(repo, args):
    usage = 'fetch <slug> <note> [--file <path> --ack "<the user\'s words>" | --orx]'
    if len(args) < 2:
        return _misuse(usage)
    slug, note, rest = args[0], args[1], list(args[2:])
    path = ack = None
    use_orx = False
    while rest:
        flag = rest.pop(0)
        if flag == "--file" and rest:
            path = rest.pop(0)
        elif flag == "--ack" and rest:
            ack = rest.pop(0)
        elif flag == "--orx":
            use_orx = True
        else:
            return _misuse(usage)
    if path and not (ack or "").strip():
        return _misuse('fetch --file needs --ack "<the user\'s words>"')
    if (path and use_orx) or (ack and not path):
        return _misuse(usage)
    base = _line(repo, slug)
    if base is None:
        return _misuse("no such research line: %s" % slug)
    row = _index_row(base, note)
    if row is None:
        return _misuse("literature/INDEX.jsonl names no note %s" % note)
    rid = norm_id(row.get("id"))
    receipts = _receipts_for(base, rid) if rid else []
    data = text = url = None
    access = "full"
    if path:
        try:
            with open(path, "rb") as fh:
                data = fh.read()
        except OSError as exc:
            return _misuse("cannot read --file %s: %s" % (path, exc))
        text = (html_to_text(data) if path.lower().endswith((".html", ".htm"))
                else data.decode("utf-8", "replace"))
        access = "user"
    tried_orx = False
    if text is None and use_orx and rid:
        tried_orx = True
        data, text, url = _orx_paper(rid)
    if text is None and rid and rid.startswith("arXiv:"):
        url = "https://arxiv.org/html/%s" % rid[6:]
        status, body = fetch_url(url)
        if status == 200 and body.strip():
            data, text = body, html_to_text(body)
    landing = None
    if text is None and rid and rid.startswith("doi:"):
        url = _oa_url(base, receipts)
        status, body = fetch_url(url) if url else (0, b"")
        if status == 200 and body.strip() and not body.startswith(b"%PDF"):
            page = html_to_text(body)
            if body_sentences(page) >= BODY_SENTENCES:
                data, text = body, page
            else:
                landing = url, body, page
    if text is None and rid and not tried_orx:
        data, text, url = _orx_paper(rid)
    reason = None
    if text is None and landing:
        # a repository landing page holds the metadata and the abstract, not the body
        # (K6 rater Y4's Tilburg and EUR Pure pages): the abstract-only step
        (url, data, text), access = landing, "abstract"
        reason = ("the open-access page holds %d distinct sentences of %d+ words, under "
                  "the %d of a work's body: a landing page" % (
                      body_sentences(text), BODY_WORDS, BODY_SENTENCES))
    elif text is None:
        rec = next((r for r in receipts if r.get("resolved") and _text(r.get("abstract"))),
                   None)
        if rec:
            access, url, text = "abstract", rec.get("url"), rec["abstract"]
            data = text.encode("utf-8")
        else:
            access, url = "none", None
            reason = ("no step yielded text: no arXiv HTML, open-access copy, orx full text "
                      "or receipt abstract")
    norm = normalise(text or "")
    passages = []
    for quote in gather_quotes(base, note, _claims(base)):
        for frag, i in _locate(quote_fragments(quote), norm):
            passages.append({"quote": quote, "found": i >= 0,
                             "text": norm[max(0, i - 300):i + len(frag) + 300] if i >= 0
                             else ""})
    record = {"note": note, "id": rid, "url": url, "access": access, "reason": reason,
              "ack": ack, "sha256": _sha(data) if data is not None else None,
              "chars": len(text or ""), "passages": passages}
    files = {}
    if text is not None:
        # the whole extracted text, write-once beside its record: `check` finds a quote
        # written after the capture in it, with no refetch
        whole = text.encode("utf-8")
        record.update(text_file="literature/.sources/%s.txt" % _sha(whole),
                      text_sha256=_sha(whole))
        files[record["text_file"]] = whole
    body = (json.dumps(record, indent=1) + "\n").encode("utf-8")
    rel = "literature/.sources/%s.json" % _sha(body)
    files[rel] = body
    code = _store(repo, base, slug, "fetch", files, SOURCES, [
        {"note": note, "file": rel, "sha256": _sha(body), "access": access, "url": url,
         "fetched_at": _now()}])
    if not code:
        print("fetch %s: access %s%s%s" % (note, access, " (%s)" % url if url else "",
                                           " - %s" % reason if reason else ""))
    return code


def _orx_paper(rid):
    code, out = run_orx(["paper", "--full", _bare(rid)])
    if code == 0 and out.strip():
        return out, out.decode("utf-8", "replace"), "orx paper --full %s" % _bare(rid)
    return None, None, None


def _oa_url(base, receipts):
    for rec in receipts:
        if rec.get("provider") == "openalex" and rec.get("resolved"):
            url = _dig(_json(_read(base, rec.get("file")) or b""), "open_access", "oa_url")
            if isinstance(url, str) and url.startswith(("http://", "https://")):
                return url
    return None


# --- 1.3 searches -------------------------------------------------------------------
def _allowed(connector, argv):
    return connector in PROVIDERS or (connector == "orx" and isinstance(argv, list)
                                      and argv[1:2] in ([c] for c in ORX_CONNECTORS))


def schema_ok(connector, data):
    """True when a search's raw bytes parse under its connector's response schema: an
    Atom feed (arXiv), a JSON object holding `message.items` (Crossref), `results`
    (OpenAlex) or `data`/`total` (Semantic Scholar, which omits `data` at 0 hits),
    UTF-8 text (orx). A capture filed under another connector is not derived from it."""
    if connector == "arxiv":
        try:
            return ET.fromstring(data).tag == ATOM + "feed"
        except ET.ParseError:
            return False
    if connector == "orx":
        try:
            data.decode("utf-8")
        except UnicodeDecodeError:
            return False
        return True
    doc = _json(data)
    if not isinstance(doc, dict):
        return False
    if connector == "crossref":
        return isinstance(_dig(doc, "message", "items"), list)
    if connector == "openalex":
        return isinstance(doc.get("results"), list)
    return connector == "semanticscholar" and (isinstance(doc.get("data"), list)
                                               or "total" in doc)


def search_records(connector, data):
    """[[normalised ids]] - one list per record - derived from a search's raw output."""
    records = []
    if connector == "arxiv":
        for entry in _atom_entries(data):
            m = re.search(r"abs/(\S+?)(?:v\d+)?/?$", entry["id"].strip())
            records.append([norm_id("arXiv:" + m.group(1))] if m else [])
    elif connector == "orx":
        text = data.decode("utf-8", "replace")
        found = [(m.start(), "arXiv:" + m.group(1)) for m in ORX_ARXIV.finditer(text)]
        found += [(m.start(), "doi:" + m.group(0)) for m in ORX_DOI.finditer(text)]
        ids = list(dict.fromkeys(norm_id(i) for _pos, i in sorted(found)))
        records = [[i] for i in ids if i]
    else:
        doc = _json(data)
        if connector == "crossref":
            items = _dig(doc, "message", "items")
            records = [[norm_id("doi:%s" % i.get("DOI"))] if i.get("DOI") else []
                       for i in items if isinstance(i, dict)] if isinstance(items, list) else []
        elif connector == "openalex":
            results = _dig(doc, "results")
            records = [[norm_id(r.get(k)) for k in ("id", "doi") if r.get(k)]
                       for r in results if isinstance(r, dict)] \
                if isinstance(results, list) else []
        elif connector == "semanticscholar":
            data_rows = _dig(doc, "data")
            for r in data_rows if isinstance(data_rows, list) else ():
                if isinstance(r, dict):
                    ext = r.get("externalIds") if isinstance(r.get("externalIds"), dict) else {}
                    records.append([i for i in (
                        norm_id("s2:%s" % r["paperId"]) if r.get("paperId") else None,
                        norm_id("arXiv:%s" % ext["ArXiv"]) if ext.get("ArXiv") else None,
                        norm_id("doi:%s" % ext["DOI"]) if ext.get("DOI") else None) if i])
    return [[i for i in r if i] for r in records if any(r)]


def cmd_search(repo, args):
    usage = ('search <slug> --tag primary|snowball|counter|known [--item "<scope.in item>"] '
             '-- <connector> <args...>')
    if "--" not in args:
        return _misuse(usage)
    cut = args.index("--")
    head, tail = list(args[:cut]), list(args[cut + 1:])
    if not head or not tail:
        return _misuse(usage)
    slug, tag, item = head.pop(0), None, None
    while head:
        flag = head.pop(0)
        if flag == "--tag" and head:
            tag = head.pop(0)
        elif flag == "--item" and head:
            item = head.pop(0)
        else:
            return _misuse(usage)
    if tag not in TAGS:
        return _misuse(usage)
    base = _line(repo, slug)
    if base is None:
        return _misuse("no such research line: %s" % slug)
    if tag == "counter" and item not in tr._scope_items(tr._state(base)):
        return _misuse("search --tag counter needs an --item equal to a scope.in entry")
    connector, words = tail[0], tail[1:]
    argv = url = None
    if connector == "orx" and words[:1] in ([c] for c in ORX_CONNECTORS):
        argv = ["orx"] + words
        code, data = run_orx(words)
        status = 200 if code == 0 else code
    elif connector in PROVIDERS:
        if not " ".join(words).strip():
            return _misuse(usage)
        url = SEARCH_URLS[connector] % urllib.parse.quote_plus(" ".join(words))
        status, data = fetch_url(url)
    else:
        print("FAIL %s: %s: connector not on the allowlist (%s, orx discover, orx paper)"
              % (slug, connector, ", ".join(PROVIDERS)))
        return 1
    if status != 200:
        print("FAIL %s: the %s search answered %s; nothing was written"
              % (slug, connector, "status %s" % status if url else "exit %s" % status))
        return 1
    if not schema_ok(connector, data):
        print("FAIL %s: the %s answer does not parse as a %s response; nothing was written"
              % (slug, connector, connector))
        return 1
    records = search_records(connector, data)
    rows = _rows(base, SEARCHES)
    rel = "searches/raw/%s.raw" % _sha(data)
    twin = next((r for r in rows if r.get("file") == rel), None)
    if twin:
        print("search: the %s answer is byte-identical to search %s's capture; one capture "
              "backs one row, so no row was written" % (connector, twin.get("n")))
        return 0
    n = 1 + max([r["n"] for r in rows if isinstance(r.get("n"), int)] or [0])
    row = {"n": n, "tag": tag, "item": item, "connector": connector, "query": " ".join(words)}
    row.update({"argv": argv} if argv else {"url": url})
    row.update({"file": rel, "sha256": _sha(data), "hits": len(records),
                "ids": [identity(r) for r in records], "searched_at": _now(),
                "parser": PARSER})
    code = _store(repo, base, slug, "search", {rel: data}, SEARCHES, [row])
    if not code:
        print("search %d: %s, %d hit(s)" % (n, connector, len(records)))
    return code


COMMANDS = {"cite": cmd_cite, "fetch": cmd_fetch, "search": cmd_search}


# --- check ----------------------------------------------------------------------------
def _step(steps, claims, name):
    for claim in claims:
        names = steps.setdefault(claim["id"], [])
        if name not in names:
            names.append(name)


def check(repo, slug, base, state, errors, warnings, strict, git, steps):
    """Spec 1.1-1.5 on one rules-8 line: refusals into `errors`, soft rules into
    `warnings`, steps per claim id, report lines into steps["#report"]."""
    flags = steps.get("#flags") or {}
    report = steps.setdefault("#report", [])
    claims = _claims(base)
    if git:
        _check_write_once(repo, base, errors)
    _check_ledger_files(base, errors)
    _check_receipts(slug, base, claims, errors, warnings, steps, report, flags.get("online"))
    _check_sources(base, state, claims, errors, warnings, strict, steps)
    _check_searches(repo, slug, base, state, claims, errors, warnings, steps, report, git)
    if flags.get("orx"):
        _census(base, state, warnings)


def _line_key(path, names):
    for name in names:
        if path.lower().startswith(name.lower() + "/"):
            return path[len(name) + 1:]
    return None


def _check_write_once(repo, base, errors):
    """1.5: a capture file differs from the blob its first commit added (in a later
    commit or the working tree), or a ledger row present at a commit changed later."""
    seen = set()
    for top, rel in tr._histories(repo, base):
        names = tr._own_names(rel)
        out, err = tr._git_out(top, "log", "--root", "--format=%x00%H", "--raw",
                               "--no-abbrev", "--no-renames", "--", *names)
        if err:
            continue
        history = {}
        for chunk in out.split("\x00")[1:]:
            lines = chunk.splitlines()
            for ln in lines[1:]:
                if not ln.startswith(":") or "\t" not in ln:
                    continue
                meta, path = ln.split("\t", 1)
                blob, key = meta.split()[3], _line_key(path, names)
                if key and CAPTURE.match(key) and not LEDGER.match(key) and blob.strip("0"):
                    history.setdefault(key, []).append((lines[0].strip(), blob))
        disk = sorted(k for k in history if os.path.isfile(os.path.join(base, k)))
        blobs = {}
        if disk:
            hashed, herr = tr._git_out(top, "hash-object", "--",
                                       *[os.path.join(base, k) for k in disk])
            if not herr:
                blobs = dict(zip(disk, hashed.split()))
        for key, versions in sorted(history.items()):
            first_sha, first = versions[-1]
            if key not in seen and (any(b != first for _s, b in versions)
                                    or blobs.get(key, first) != first):
                seen.add(key)
                errors.append("%s changed after its first commit (%s): a capture is written "
                              "once, so a new capture is a new file" % (key, first_sha[:12]))
    for rel in _ledgers(base):
        path = os.path.join(base, rel)
        # the results reading, every ref: a row a tag still holds was committed
        versions = [text for _sha_, text in tr.file_versions(repo, path)]
        current, exc = tr._committed_text(path)
        if not exc:
            versions.append(current)
        # every row of each version is still in the latest, as a multiset with the order
        # aside: two branches that appended and merged pass (K6 rater X3's probe-merge).
        # ponytail: a branch not merged yet reads every row it appended as gone from the
        # latest; ancestry per version pair is the fuller rule.
        latest = collections.Counter(ln for ln in (versions or [""])[-1].splitlines()
                                     if ln.strip())
        if any(collections.Counter(ln for ln in older.splitlines() if ln.strip()) - latest
               for older in versions[:-1]):
            errors.append("%s: a row changed or went missing after its first commit; "
                          "a ledger is append-only" % rel)


def _ledgers(base):
    out = [r for r in (RECEIPTS, SOURCES, SEARCHES) if os.path.isfile(os.path.join(base, r))]
    try:
        names = sorted(os.listdir(os.path.join(base, "instruments")))
    except OSError:
        names = []
    return out + ["instruments/" + n for n in names if n.endswith(".jsonl")]


def _check_ledger_files(base, errors):
    """Every ledger row's `file` exists and hashes to its `sha256`; a SEARCHES or
    SOURCES row with no `file` has no capture."""
    for rel in _ledgers(base):
        for n, row in enumerate(_rows(base, rel), 1):
            if not row.get("file"):
                if rel in (SEARCHES, SOURCES):
                    errors.append("%s row %d names no file, so it has no capture" % (rel, n))
                continue
            data = _read(base, row["file"])
            if data is None:
                errors.append("%s row %d names %s, which has no capture" % (rel, n, row["file"]))
            elif row.get("sha256") and _sha(data) != row["sha256"]:
                errors.append("%s row %d: hash mismatch - %s does not hash to its sha256"
                              % (rel, n, row["file"]))


def _notes_by_id(base):
    out = {}
    for row in _rows(base, INDEX):
        rid = norm_id(row.get("id"))
        if rid and isinstance(row.get("note"), str):
            out.setdefault(rid, []).append(row["note"])
    return out


def _held(warnings, rel, versions):
    """One warning per ledger naming the parser versions its rows were held under."""
    if versions:
        warnings.append("%s: rows of parser version %s are held to their hash alone; this "
                        "check re-derives parser version %d rows only"
                        % (rel, ", ".join(sorted(versions)), PARSER))


def _check_receipts(slug, base, claims, errors, warnings, steps, report, online):
    # a receipt is judged for an id the INDEX holds now: a corrected id, cited again,
    # leaves the old id's rows in the append-only ledger unjudged
    held = {norm_id(r.get("id")) for r in _rows(base, INDEX) if r.get("class") == "formal"}
    parsed, older = [], set()
    for n, row in enumerate(_rows(base, RECEIPTS), 1):
        rid, provider = norm_id(row.get("id")), row.get("provider")
        data = _read(base, row.get("file")) if row.get("file") else b""
        if data is None or not rid or rid not in held:
            continue
        if row.get("parser", 0) != PARSER:
            # another parser's row is held to its hash (`_check_ledger_files`) and counts
            # as it was recorded: a re-parse under this parser would refuse it for good
            older.add(str(row.get("parser", 0)))
            got = {k: row.get(k) for k in ("resolved", "title", "first_author", "year")}
            parsed.append((row, rid, dict(got, id=rid)))
            continue
        got = parse_receipt(provider, rid, row.get("status"), data)
        wrong = [k for k in ("resolved", "title", "first_author", "year") if got[k] != row.get(k)]
        if wrong:
            errors.append("%s row %d (%s %s) is not derived from its capture: %s differ from "
                          "a re-parse of its raw bytes" % (RECEIPTS, n, rid, provider,
                                                           ", ".join(wrong)))
        named = receipt_ids(provider, data)
        got["id"] = rid if rid in named else None
        if got["resolved"]:
            url = dict(receipt_urls(rid)).get(provider)
            if not got["id"]:
                # a registry answering an alias with the work's other id: no receipt for
                # this id, and no refusal - the other providers resolve it, or none does
                note = ("%s: the %s receipt for %s names %s, not that id, so it does not "
                        "count for it" % (RECEIPTS, provider, rid,
                                          ", ".join(sorted(named)) or "no id"))
                if note not in warnings:
                    warnings.append(note)
                continue
            if row.get("url") != url:
                errors.append("%s row %d (%s %s): %s is not the %s receipt URL for that id "
                              "(%s)" % (RECEIPTS, n, rid, provider, row.get("url"), provider,
                                        url))
                continue
        parsed.append((row, rid, got))
    _held(warnings, RECEIPTS, older)
    for row in _rows(base, INDEX):
        if row.get("class") != "formal":
            continue
        rid = norm_id(row.get("id")) or row.get("id")
        note = str(row.get("note"))
        verdict = citation_verdict(row, [(r.get("provider"), g) for r, i, g in parsed
                                         if rid and i == rid])
        if verdict == NO_REGISTRY:
            errors.append("literature/%s: %s %s - no receipt resolved it (run `cite`, or "
                          "record `unindexed_reason`)" % (note, row.get("id") or "an empty id",
                                                          NO_REGISTRY))
        elif verdict:
            _step(steps, _citing(claims, note), verdict)
    if not online:
        return
    # only a receipt recorded from a 200 has an answer to drift from (a 429 row of an
    # older `cite` read as drift once the provider answered)
    targets = [(r, i, g) for r, i, g in parsed if r.get("status") == 200]
    if len(targets) > 10:
        targets = sorted(targets, key=lambda t: str(t[0].get("sha256") or ""))[:10]
    notes = _notes_by_id(base)
    for row, rid, got in targets:
        provider = row.get("provider")
        status, data = fetch_url(dict(receipt_urls(rid)).get(provider)
                                 or str(row.get("url") or ""))
        now = parse_receipt(provider, rid, status, data)
        now["id"] = rid if rid in receipt_ids(provider, data) else None
        for field in ("id", "title", "first_author", "year"):
            if now[field] != got[field]:
                report.append("online %s: %s %s %s drifted" % (slug, rid, provider, field))
                for note in notes.get(rid, ()):
                    _step(steps, _citing(claims, note), "online-drift")


def _source_records(base):
    """{note: [(ledger row, record)]} in ledger order. A row counts only when its
    `file` is a `.sources/` record for that note: a row with no file, or naming a
    receipt or another note's record, sets no access."""
    out = {}
    for row in _rows(base, SOURCES):
        note, rel = row.get("note"), row.get("file")
        if not (isinstance(note, str) and isinstance(rel, str)
                and rel.startswith("literature/.sources/") and rel.endswith(".json")):
            continue
        record = _json(_read(base, rel) or b"")
        if isinstance(record, dict) and record.get("note") == note:
            out.setdefault(note, []).append((row, record))
    return out


def _access(entry):
    return entry[1].get("access")


def _in_order(frags, texts):
    """Fragment k in texts[k], and no adjacent pair reversed in a window holding both."""
    if len(texts) != len(frags) or not all(f in t for f, t in zip(frags, texts)):
        return False
    return not any(frags[k] in t and frags[k + 1] in t and _locate(frags[k:k + 2], t)[1][1] < 0
                   for k in range(len(frags) - 1) for t in texts[k:k + 2])


def _found(quote, records, texts=()):
    """1.2 at `check`: every fragment of `quote` found in order - all in one whole
    captured text (normalised `texts`: the sources' extracted text, the receipts'
    abstracts) or one passage text of the captures, or fragment k in the k-th passage
    a capture stored for this quote (fragments far apart sit in separate windows)."""
    frags = quote_fragments(quote)
    if not frags:
        return True
    stored = [[p for p in r.get("passages") or () if isinstance(p, dict)] for r in records]
    if any(all(i >= 0 for _f, i in _locate(frags, t))
           for t in list(texts) + [str(p.get("text") or "") for ps in stored for p in ps]):
        return True
    return any(_in_order(frags, [str(p.get("text") or "") for p in ps if p.get("quote") == quote])
               for ps in stored)


def _source_text(base, record, errors):
    """The whole extracted text a `fetch` record names, or None; a named text file that
    is gone or hashes otherwise is refused like a ledger's capture."""
    rel = record.get("text_file")
    if not rel:
        return None
    data = _read(base, rel) if str(rel).startswith("literature/.sources/") else None
    if data is None:
        problem = "a source record names %s, which has no capture" % rel
    elif _sha(data) != record.get("text_sha256"):
        problem = "hash mismatch - %s does not hash to its text_sha256" % rel
    else:
        return data.decode("utf-8", "replace")
    if problem not in errors:
        errors.append(problem)
    return None


def _receipt_abstracts(base, rid):
    """The abstracts re-parsed from the raw receipts that name `rid`."""
    out = []
    for row in _receipts_for(base, rid) if rid else ():
        provider, data = row.get("provider"), _read(base, row.get("file"))
        if data and rid in receipt_ids(provider, data):
            abstract = parse_receipt(provider, rid, row.get("status"), data)["abstract"]
            out += [abstract] if abstract else []
    return out


def _quote_missing(errors, where, quote, notes, searched):
    """1.2's refusal: `quote` found in the captured text of none of `notes`."""
    if not any(_found(quote, *searched[n]) for n in notes):
        errors.append('%s: "%s": %s (searched %s; if it is not a quote, rephrase it without '
                      'quotation marks; if it is, `fetch --file` the version quoted)'
                      % (where, quote, NOT_IN_SOURCE,
                         ", ".join("literature/" + n for n in notes)))


def _check_sources(base, state, claims, errors, warnings, strict, steps):
    captures = _source_records(base)
    index = _rows(base, INDEX)
    texts = {n: [_source_text(base, rec, errors) for _row, rec in c]
             for n, c in captures.items()}
    access, searched = {}, {}
    for row in index:
        note = row.get("note")
        if not isinstance(note, str):
            continue
        mine = captures.get(note, [])
        access[note] = _access(mine[-1]) if mine else None
        citing = _citing(claims, note)
        if access[note] in (None, "none"):
            _step(steps, citing, "source-not-captured")
        elif access[note] == "abstract":
            _step(steps, citing, "abstract-only")
        elif access[note] in ("full", "user"):
            records = [rec for _row, rec in mine if rec.get("access") in ("full", "user")]
            whole = [normalise(t) for (_row, rec), t in zip(mine, texts.get(note, []))
                     if t is not None and rec.get("access") in ("full", "user")]
            whole += [normalise(a) for a in _receipt_abstracts(base, norm_id(row.get("id")))]
            searched[note] = (records, whole)
            for quote in note_quotes(base, note):
                _quote_missing(errors, "literature/" + note, quote, [note], searched)
    # a claim's quote is searched in every note it cites, and refused only when every one
    # of them holds full text and none holds the quote: a cited note without full text
    # already narrows the claim by its step. A claim another row supersedes is history.
    superseded = tr._superseded(claims)
    for claim in claims:
        notes = [n for n in access if _citing([claim], n)]
        if claim["id"] in superseded or not notes or not all(n in searched for n in notes):
            continue
        for quote in claim_quotes(claim):
            _quote_missing(errors, "claim " + claim["id"], quote, notes, searched)
    formal = [r.get("note") for r in index if r.get("class") == "formal"]
    if not formal or not tr._concluding(base, state):
        return
    latest = {n: _access(c[-1]) for n, c in captures.items() if c}
    closed = sum(1 for n in formal if latest.get(n) in (None, "abstract", "none"))
    user = sum(1 for n in formal if latest.get(n) == "user")
    text = (_read(base, "to_human/report.md") or b"").decode("utf-8", "replace")
    # the share counts every source without full text, closed and abstract-only alike,
    # under any of the words a report may use for it
    shares = ("closed-access", "not full text", "abstract-only")
    if not any(re.search(r"%s:\s*%d\s+of\s+%d\b" % (re.escape(w), closed, len(formal)), text)
               for w in shares):
        tr._soft(errors, warnings, strict, "report states no closed-access share: %d of %d "
                 "sources have no full text (%s)" % (closed, len(formal), " or ".join(
                     "`%s: %d of %d`" % (w, closed, len(formal)) for w in shares)))
    if user and not re.search(r"user-supplied:\s*%d\s+of\s+%d\s+sources" % (user, len(formal)),
                              text):
        tr._soft(errors, warnings, strict, "report states no user-supplied share "
                 "(`user-supplied: %d of %d sources`)" % (user, len(formal)))


def _search_line(state):
    cls = state.get("question_class")
    return cls is None or cls in SEARCH_CLASSES or state.get("method") == "qualitative"


def _valid_stopping(stop):
    if not isinstance(stop, dict):
        return False

    def unit(v):
        return isinstance(v, (int, float)) and not isinstance(v, bool) and 0 < v < 1

    rule = stop.get("rule")
    if rule == "hypergeometric":
        return unit(stop.get("recall")) and unit(stop.get("confidence"))
    if rule == "saturation":
        run = stop.get("run")
        return isinstance(run, int) and not isinstance(run, bool) and run > 0
    return rule == "pragmatic" and isinstance(stop.get("risk"), str) and bool(
        stop["risk"].strip())


def _stopping_first(repo, base):
    """True when a valid `state.stopping` was committed strictly before the commit
    that added the first SEARCHES row (or when no search row is committed yet)."""
    searches = tr.file_versions(repo, os.path.join(base, SEARCHES), every_ref=False)
    if not searches:
        return True
    first = next((sha for sha, text in tr.file_versions(repo, os.path.join(base, "state.json"),
                                                        every_ref=False)
                  if _valid_stopping(_dig(_json(text.encode("utf-8")), "stopping"))), None)
    return bool(first) and first != searches[0][0] and tr.is_ancestor(
        repo, first, searches[0][0]) is True


def _check_searches(repo, slug, base, state, claims, errors, warnings, steps, report, git):
    rows = _rows(base, SEARCHES)
    per_row, counted, backs, older = [], [], {}, set()
    for n, row in enumerate(rows, 1):
        connector, rel = row.get("connector"), row.get("file")
        # only a row whose file is a search capture, backing no earlier row, counts
        # (connector, tag, records)
        data = None
        if rel and not str(rel).startswith("searches/raw/"):
            errors.append("%s row %d names %s, which is not under searches/raw/, so it has "
                          "no capture" % (SEARCHES, n, rel))
        elif rel in backs:
            errors.append("%s row %d names %s, which backs row %d: one capture backs one "
                          "row, so it has no capture" % (SEARCHES, n, rel, backs[rel]))
        elif rel:
            backs[rel] = n
            data = _read(base, rel)
        if not _allowed(connector, row.get("argv")):
            errors.append("%s row %d names %r: connector not on the allowlist"
                          % (SEARCHES, n, connector))
            data = None
        if data is not None and row.get("parser", 0) != PARSER:
            # another parser's row is held to its hash and counts as it was recorded; its
            # records are read where this parser still reads the capture
            older.add(str(row.get("parser", 0)))
            records = (search_records(connector, data) if schema_ok(connector, data) else []) \
                or [[i] for i in row.get("ids") or () if isinstance(i, str)]
        elif data is not None and not schema_ok(connector, data):
            errors.append("%s row %d is not derived from its capture: %s does not parse as a "
                          "%s response" % (SEARCHES, n, rel, connector))
            data = None
        else:
            records = search_records(connector, data) if data is not None else []
            if data is not None and (row.get("hits") != len(records)
                                     or row.get("ids") != [identity(r) for r in records]):
                errors.append("%s row %d is not derived from its capture: hits/ids differ "
                              "from a re-parse of %s" % (SEARCHES, n, rel))
        if data is not None:
            counted.append(row)
            per_row.append(records)
    _held(warnings, SEARCHES, older)
    owner = {}
    for records in per_row:
        for rec in records:
            for i in rec:
                owner.setdefault(i, identity(rec))
    literature = [c for c in claims if any(t.startswith("literature/")
                                           for t in tr._cited(c.get("proof")))]
    labels, decided = [], set()
    for row in _rows(base, SCREENING):
        sid = norm_id(row.get("id")) or row.get("id")
        if sid not in owner:
            # a hand search's record: screened, but no capture shows a search returned it
            _step(steps, literature, "screened-outside-search")
            continue
        if owner[sid] not in decided and row.get("decision") in ("kept", "dropped"):
            decided.add(owner[sid])
            labels.append(1 if row["decision"] == "kept" else 0)
    if not _search_line(state):
        return
    connectors = {(r.get("connector"), tuple(r.get("argv") or ())[1:2]) for r in counted}
    if len(connectors) < 2:
        _step(steps, literature, "one-connector")
    for item in tr._scope_items(state):
        if not any(r.get("tag") == "counter" and r.get("item") == item for r in counted):
            _step(steps, literature, "no-counter-search")
    stop = state.get("stopping")
    if not _valid_stopping(stop) or (git and not _stopping_first(repo, base)):
        _step(steps, literature, "no-stopping-rule")
    if _valid_stopping(stop):
        if stop["rule"] == "hypergeometric":
            p = st.hypergeometric_p(labels, len(set(owner.values())), stop["recall"])
            met = p < 1 - stop["confidence"]
            report.append("stopping %s: hypergeometric p=%.6f %s"
                          % (slug, p, "met" if met else "not met"))
        else:
            met = stop["rule"] == "pragmatic" or st.saturated(
                [[identity(r) for r in records] for records in per_row], stop["run"])
            report.append("stopping %s: %s %s" % (slug, stop["rule"], "met" if met
                                                  else "not met"))
        if not met:
            _step(steps, literature, "stopping-not-met")
    known = state.get("known_items")
    for item in known if isinstance(known, list) else ():
        if (norm_id(item) or item) not in owner:
            _step(steps, literature, "known-item-missed")


def _census(base, state, warnings):
    """1.4: every engine run of this line's experiment has a results row."""
    runs, err = engine_runs(state)
    if err:
        warnings.append("%s, so the run census was not taken" % err)
    if not runs:
        return
    filed = set()
    for h in tr._experiment_names(base):
        filed |= {r.get("source") for r in _rows(base, "experiments/%s/results.jsonl" % h)}
    for run in runs:
        rid = run_id(run)
        if rid and "orx:%s" % rid not in filed:
            warnings.append("orx run %s has no results row" % rid)
