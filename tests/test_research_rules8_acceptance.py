#!/usr/bin/env python3
"""Acceptance runner for research rules 8 (plan 127, wave 0), written before the code.

Every case drives `bin/tezgah-research` as a subprocess inside its own
tempfile.mkdtemp() git project with a temp HOME, an empty global git config, a stub
`orx` (TEZGAH_ORX_BIN) and the canned-HTTP switch (TEZGAH_CAPTURE_MAP), so no case
touches the network or the user's state. The fixtures port the research-rigor audit's
probes (`audit/probes.py`: C0, C1, P1-P12) to rules 8 and add the plan's forgery probes,
three sound lines and one case per acceptance cell a black-box test can express. The
expected outcome of each case - refused with its substring, capped with its step name,
or warned - is the interface spec of plan 127 (`.tezgah/analysis/rules8/spec.md`).

It fails on the code that predates plan 127, and passes once waves 1-4 are built.
Only directories this process created with mkdtemp are removed.
"""
import copy
import hashlib
import json
import math
import os
import re
import shutil
import statistics
import subprocess
import sys
import tempfile
import unittest
import urllib.parse

HERE = os.path.dirname(os.path.abspath(__file__))
CLI = os.path.join(os.path.dirname(HERE), "bin", "tezgah-research")
PREFIX = "rules8-accept-"

Q = "does caching the lookups lower p95 latency?"
ITEM = "the cache's effect on p95"
ITEM_L = "what the literature reports about caching and tail latency"
ARX, ARX2 = "2401.00001", "2402.00002"
NOTE, NOTE2 = "lit/2401.00001-smith.md", "lit/2402.00002-jones.md"
TITLE, TITLE2 = "Caching for tail latency", "Warm caches and slow requests"
QUOTE = "caching lowers tail latency in every workload we measured"
QUOTE2 = "a warm cache halves the slowest requests"
PRIMARY_Q = ["caching", "tail", "latency"]
COUNTER_Q = ["caching", "no", "effect", "on", "tail", "latency"]
OPENROUTER = "https://openrouter.ai/api/v1/chat/completions"
DIMENSIONS = {"evidence_relevance": 4, "falsifiability": 4, "scope_calibration": 4,
              "argument_coherence": 4, "exploration_integrity": 3,
              "methodological_rigour": 3}
LEVELS = ("very-low", "low", "moderate", "high")
CERTAINTY = re.compile(r"^certainty q: (\S+) (very-low|low|moderate|high) start=\S+ steps=\S+$",
                       re.M)


# ----------------------------------------------------------------- canned registry bodies
def arxiv_api(aid):
    return "https://export.arxiv.org/api/query?id_list=%s&max_results=1" % aid


def openalex_url(aid):
    return "https://api.openalex.org/works/doi:10.48550/arXiv.%s" % aid


def html_url(aid):
    return "https://arxiv.org/html/%s" % aid


def search_url(connector, words):
    q = urllib.parse.quote_plus(" ".join(words))
    return {"arxiv": "https://export.arxiv.org/api/query?search_query=all:%s&max_results=50",
            "openalex": "https://api.openalex.org/works?search=%s&per-page=50"}[connector] % q


def atom(entries):
    """An arXiv Atom feed; entries are (id, title, year, author, summary)."""
    body = "".join(
        "<entry><id>http://arxiv.org/abs/%sv1</id><title>%s</title><summary>%s</summary>"
        "<published>%d-01-02T00:00:00Z</published><author><name>%s</name></author></entry>"
        % (aid, title, summary, year, author) for aid, title, year, author, summary in entries)
    return ('<?xml version="1.0" encoding="UTF-8"?>\n'
            '<feed xmlns="http://www.w3.org/2005/Atom">%s</feed>\n' % body)


def openalex_body(aid, title, year, author, wid):
    return json.dumps({"id": "https://openalex.org/%s" % wid,
                       "doi": "https://doi.org/10.48550/arxiv.%s" % aid,
                       "title": title, "display_name": title, "publication_year": year,
                       "authorships": [{"author": {"display_name": author}}],
                       "open_access": {"oa_url": None}})


def html_body(title, sentence):
    return ("<html><head><title>%s</title><style>p {color: red}</style></head><body>"
            "<h1>%s</h1><p>Section 4. In our study, %s, across the three services.</p>"
            "</body></html>\n" % (title, title, sentence))


def paper_map(aid, title, author, sentence, wid, year=2024):
    return {arxiv_api(aid): atom([(aid, title, year, author, "We study caching.")]),
            openalex_url(aid): openalex_body(aid, title, year, author, wid),
            html_url(aid): html_body(title, sentence)}


def index_row(note, aid, title, author):
    return {"note": note, "id": "arXiv:%s" % aid, "class": "formal",
            "source": "https://arxiv.org/abs/%s" % aid,
            "inclusion": "a paper on caching and tail latency (S1)",
            "verified": ["arxiv:%s" % aid, "openalex:W%s" % aid.replace(".", "")],
            "title": title, "year": 2024, "first_author": author}


def note_text(title, quote):
    return "# %s\n\nRead: section 4.\n\n> \"%s\" (sec. 4)\n" % (title, quote)


# ----------------------------------------------------------------- the specs
def protocol(h="h1", falsifier="p95 > 110 on cache", rivals=True, plan=True, extra=""):
    text = ("# Protocol %s\n\n"
            "change: cache the lookups\n"
            "design: experiment\n"
            "prediction: p95 latency drops from 120 ms to at most 95 ms\n"
            "falsifier: %s\n"
            "headroom: p95 sits 30%% above the floor\n"
            "metric: p95 latency\n"
            "unit: ms\n"
            "k: 2\n"
            "compare: cache vs base on p95, lower is better\n" % (h, falsifier))
    if plan:
        text += "alpha: 0.05\npower: 0.8\nmde: 10\nn: 2\n"
    if rivals:
        text += ("rival: the OS page cache alone lowers p95 excludes: base runs at or below "
                 "95 ms\n"
                 "rival: a quieter host lowers p95 excludes: base runs that stay above "
                 "110 ms\n")
    return text + extra


def runs(base=(120, 121), cache=(90, 91), scope="real", fixture=None):
    out, n = [], 0
    for arm, values in (("base", base), ("cache", cache)):
        for value in values:
            n += 1
            out.append({"run": "r%d" % n, "arm": arm, "values": {"p95": value},
                        "scope": scope, "fixture": fixture})
    return out


def evidence_claim(cid, statement, **extra):
    claim = {"id": cid, "statement": statement, "kind": "evidence",
             "proof": ["experiments/h1/results.jsonl"],
             "falsification": "a rerun shows p95 above 110 ms", "provenance": "ai-executed",
             "status": "supported", "trace": "S1", "scope": "real"}
    claim.update(extra)
    return claim


def literature_claim(cid, statement, notes, quote=None):
    claim = {"id": cid, "statement": statement, "kind": "literature",
             "proof": ["literature/" + n for n in notes],
             "falsification": "the paper does not report a tail-latency effect",
             "provenance": "ai-executed", "status": "supported", "trace": "S1"}
    if quote:
        claim["quote"] = quote
    return claim


VALIDITY = ("- Internal validity: one host, warm cache.\n"
            "- External validity: one benchmark.\n"
            "- Construct validity: p95 is the latency asked about.\n"
            "- Conclusion validity: two runs per arm.\n")


def report(lead, certainty, closed=None):
    text = "# Report\n\n%s\n\n## Certainty\n\n" % lead
    text += "".join("- %s: %s\n" % pair for pair in certainty)
    if closed:
        text += "\nclosed-access: %d of %d\n" % closed
    return text + ("\n## What this does not show\n\nIt does not show the effect on other "
                   "hosts.\n\n" + VALIDITY)


def review(cls, findings, family="openai"):
    return {"producer": "session-a", "reviewer": "reviewer-b",
            "producer_family": "anthropic", "reviewer_family": family,
            "question_class": cls, "dimensions": dict(DIMENSIONS), "findings": findings}


def state(method, cls, **extra):
    out = {"rules": 8, "phase": "concluded", "direction": "conclude", "method": method,
           "question_class": cls, "tier": "study", "orx_project": "proj-1",
           "orx_experiment": "exp-q",
           "deliverable": {"kind": "finding"},
           "scope": {"in": [ITEM if method == "measured" else ITEM_L],
                     "out": ["other changes"]},
           "success": [{"id": "A1", "criterion": "A1: the question is answered",
                        "verdict": "met", "evidence": "claims C1"}],
           "sessions": [{"date": "2026-01-01", "tag": "ai-executed", "what": "ran the line"}],
           "hypotheses": []}
    if method == "measured":
        out["evaluation"] = {"metric": "p95 latency (ms)", "baseline": "120 ms uncached",
                             "locked_at": "2026-01-01"}
        out["hypotheses"] = [{"id": "H1", "text": "caching the lookups lowers p95 latency",
                              "status": "supported", "probability": 0.7}]
    out.update(extra)
    return out


def empty_spec(method, cls):
    return {"method": method, "class": cls, "state": state(method, cls), "protocol": {},
            "pre_files": {}, "runs": {}, "orx_extra": {}, "typed_rows": {}, "analysis": {},
            "claims": [], "notes": {}, "index": [], "map": {}, "cite": False, "fetch": [],
            "searches": [], "ops": [], "findings": "", "log": "", "report": "",
            "review": {}, "files": {}, "env": {}, "orx_papers": {}, "tmp_files": {}}


FINDINGS = ("# Findings\n\n## What we know\n\n- caching lowers p95 [C1]\n\n"
            "## Patterns\n\n%s\n\n## Lessons\n\n- lock the metric first\n\n"
            "## Open questions\n\n- none\n")
LOG = "# Research log\n\n- 2026-01-01 [ai-executed] ran the line\n"


def mixed_spec():
    """C0: the control, a sound mixed line (one measured claim, one literature claim)."""
    spec = empty_spec("measured", "R6")
    spec["protocol"]["h1"] = protocol()
    spec["runs"]["h1"] = runs()
    spec["analysis"]["h1"] = ("# Analysis h1\n\nCONFIRMATORY: p95 went from 120 ms and 121 ms "
                              "(base runs r1, r2) to 90 ms and 91 ms (cache runs r3, r4).\n")
    spec["claims"] = [
        evidence_claim("C1", "p95 latency dropped from 120 ms to 90 ms after caching"),
        literature_claim("C2", "Smith et al. report that caching lowers tail latency",
                         [NOTE], QUOTE)]
    spec["notes"] = {NOTE: note_text(TITLE, QUOTE)}
    spec["index"] = [index_row(NOTE, ARX, TITLE, "Smith")]
    spec["map"] = paper_map(ARX, TITLE, "Ann Smith", QUOTE, "W4390000001")
    spec["cite"] = True
    spec["fetch"] = [NOTE]
    spec["findings"] = FINDINGS % "- caching lowers tail latency [C1] [C2]"
    spec["log"] = LOG
    spec["report"] = report("Caching lowered p95 latency from 120 ms to 90 ms (C1).",
                            [("C1", "high"), ("C2", "moderate")], (0, 1))
    spec["review"] = review("R6", [
        {"severity": "minor", "target": "to_human/report.md", "quote": "two runs per arm"},
        {"severity": "minor", "target": "experiments/h1/raw/r3.log", "quote": "p95 90"}])
    return spec


def measured_spec():
    """A sound measured-only line: two evidence claims on captured runs."""
    spec = mixed_spec()
    spec["claims"] = [
        evidence_claim("C1", "p95 latency dropped from 120 ms to 90 ms after caching"),
        evidence_claim("C2", "p95 latency with the cache stayed between 90 ms and 91 ms "
                             "across runs")]
    for key in ("notes", "map"):
        spec[key] = {}
    spec["index"], spec["fetch"], spec["cite"] = [], [], False
    spec["findings"] = FINDINGS % "- caching lowers p95 in both cache runs [C1] [C2]"
    spec["report"] = report("Caching lowered p95 latency from 120 ms to 90 ms (C1, C2).",
                            [("C1", "high"), ("C2", "high")])
    return spec


def literature_spec(cls="R1"):
    """A sound literature-only line (a scoping review): three claims on two notes."""
    spec = empty_spec("qualitative", cls)
    spec["state"]["stopping"] = {"rule": "pragmatic",
                                 "risk": "a paper outside both registries is missed"}
    spec["state"]["known_items"] = ["arXiv:%s" % ARX]
    spec["claims"] = [
        literature_claim("C1", "Smith et al. report that caching lowers tail latency",
                         [NOTE], QUOTE),
        literature_claim("C2", "Jones et al. report that a warm cache halves the slowest "
                               "requests", [NOTE2], QUOTE2),
        literature_claim("C3", "Both indexed papers report lower tail latency with caching",
                         [NOTE, NOTE2])]
    spec["notes"] = {NOTE: note_text(TITLE, QUOTE), NOTE2: note_text(TITLE2, QUOTE2)}
    spec["index"] = [index_row(NOTE, ARX, TITLE, "Smith"),
                     index_row(NOTE2, ARX2, TITLE2, "Jones")]
    spec["map"] = paper_map(ARX, TITLE, "Ann Smith", QUOTE, "W4390000001")
    spec["map"].update(paper_map(ARX2, TITLE2, "Bo Jones", QUOTE2, "W4390000002"))
    primary, counter = PRIMARY_Q, COUNTER_Q
    spec["map"][search_url("openalex", primary)] = json.dumps({"results": [
        {"id": "https://openalex.org/W4390000001",
         "doi": "https://doi.org/10.48550/arxiv.%s" % ARX, "title": TITLE},
        {"id": "https://openalex.org/W4390000002",
         "doi": "https://doi.org/10.48550/arxiv.%s" % ARX2, "title": TITLE2}]})
    spec["map"][search_url("arxiv", counter)] = atom([
        (ARX, TITLE, 2024, "Ann Smith", "We study caching."),
        (ARX2, TITLE2, 2024, "Bo Jones", "We study warm caches.")])
    spec["searches"] = [
        {"tag": "primary", "item": ITEM_L, "argv": ["openalex"] + primary},
        {"tag": "counter", "item": ITEM_L, "argv": ["arxiv"] + counter}]
    spec["cite"] = True
    spec["fetch"] = [NOTE, NOTE2]
    spec["findings"] = FINDINGS.replace("caching lowers p95 [C1]", "caching lowers tail "
                                        "latency [C1]") % "- caching lowers tail latency [C1] [C2] [C3]"
    spec["log"] = LOG
    spec["report"] = report("Two papers report lower tail latency with caching (C1, C2, C3).",
                            [("C1", "moderate"), ("C2", "moderate"), ("C3", "moderate")],
                            (0, 2))
    spec["review"] = review(cls, [{"severity": "minor", "target": "to_human/report.md",
                                   "quote": "closed-access: 0 of 2"}])
    return spec


def aux_experiment(spec, h, rows, mde="0.10"):
    """Add a binary-outcome experiment `h` with hand-written rows (an instrument's items)."""
    spec["protocol"][h] = (
        "# Protocol %s\n\nchange: cache the lookups\ndesign: experiment\n"
        "prediction: the share of slow items falls by at least 0.2\n"
        "falsifier: outcome > 0.9 on b\nheadroom: half the items are slow\n"
        "metric: p95 latency of %s items\nunit: share\n"
        "alpha: 0.05\npower: 0.8\nmde: %s\nn: 2\n"
        "rival: the items differ by arm excludes: equal item sets\n"
        "rival: the labeler drifts excludes: a stable gold error rate\n" % (h, h, mde))
    spec["typed_rows"][h] = rows
    spec["analysis"][h] = "# Analysis %s\n\nEXPLORATORY: instrument rows.\n" % h
    spec["report"] += "\nThe p95 latency of %s items was registered and is reported here.\n" % h


def item_rows(instrument, arms, outcomes):
    """rows of `instrument`: outcomes is {arm: [0/1, ...]}, items i001.. per arm."""
    rows = []
    for arm in arms:
        for n, value in enumerate(outcomes[arm], 1):
            rows.append({"item": "i%03d" % n, "arm": arm, "instrument": instrument,
                         "outcome": value, "scope": "fixture", "fixture": "generated items",
                         "source": "fixture.py %s i%03d" % (arm, n)})
    return rows


def seeded_draw(items, seed, arm, n):
    """The gold draw spec.md fixes: items sorted by sha256("<seed>:<arm>:<item>")."""
    def key(item):
        return hashlib.sha256(("%s:%s:%s" % (seed, arm, item)).encode()).hexdigest()
    return sorted({str(i) for i in items}, key=key)[:n]


def gold_ops(spec, instrument, arm, n, seed, outcomes, wrong=0):
    """Ops drawing a gold sample for `arm` and labelling it; the first `wrong` drawn
    items get the opposite truth."""
    items = ["i%03d" % k for k in range(1, len(outcomes[arm]) + 1)]
    drawn = seeded_draw(items, seed, arm, n)
    labels = []
    for k, item in enumerate(drawn):
        out = outcomes[arm][int(item[1:]) - 1]
        labels.append({"item": item, "truth": 1 - out if k < wrong else out})
    spec["ops"].append((["gold", "q", instrument, "--arm", arm, "--n", str(n),
                         "--seed", str(seed)], None))
    spec["ops"].append((["label", "q", instrument, "--arm", arm, "--human", "rater one",
                         "--ack", "the user labelled these items by hand"],
                        "".join(json.dumps(r) + "\n" for r in labels)))
    return drawn, labels


def instrument_spec(per_arm, n, wrong, arms=("a", "b"), seed=5, mde="0.10"):
    """C0 plus a binary experiment h2 measured by instrument judge-x on arms a and b, and for
    each arm in `arms` a gold draw of n items with its labels (`wrong` of them flipped)."""
    spec = mixed_spec()
    outcomes = {arm: [k % 2 for k in range(per_arm)] for arm in ("a", "b")}
    aux_experiment(spec, "h2", item_rows("judge-x", ("a", "b"), outcomes), mde=mde)
    spec["ops"].append((["instrument", "add", "q", "judge-x", "--kind", "measure",
                         "--rung", "R4", "--construct", "slow item"], None))
    spec["gold"] = {}
    for arm in arms:
        spec["gold"][arm] = gold_ops(spec, "judge-x", arm, n, seed, outcomes, wrong=wrong)
    return spec


def hypergeometric_spec(dropped_after):
    """The literature line with a hypergeometric stop: a 300-record haystack, 95 records kept,
    5 dropped, then `dropped_after` more dropped - the counts buscarpy's oracle was run on."""
    spec = literature_spec()
    spec["state"]["stopping"] = {"rule": "hypergeometric", "recall": 0.95, "confidence": 0.95}
    others = ["W5%09d" % k for k in range(1, 299)]
    results = [{"id": "https://openalex.org/W4390000001",
                "doi": "https://doi.org/10.48550/arxiv.%s" % ARX, "title": TITLE},
               {"id": "https://openalex.org/W4390000002",
                "doi": "https://doi.org/10.48550/arxiv.%s" % ARX2, "title": TITLE2}]
    results += [{"id": "https://openalex.org/%s" % w, "title": "Record %s" % w} for w in others]
    spec["map"][search_url("openalex", PRIMARY_Q)] = json.dumps({"results": results})
    kept = ["arXiv:%s" % ARX, "arXiv:%s" % ARX2] + ["openalex:%s" % w for w in others[:93]]
    dropped = ["openalex:%s" % w for w in others[93:98 + dropped_after]]
    rows = [{"search": 1, "id": i, "decision": "kept", "reason": "on topic",
             "screener": "rater one"} for i in kept]
    rows += [{"search": 1, "id": i, "decision": "dropped", "reason": "off topic",
              "screener": "rater one"} for i in dropped]
    spec["files"]["searches/screening.jsonl"] = "".join(json.dumps(r) + "\n" for r in rows)
    return spec


def done_line(project):
    """A done line `old` holding one refuted claim whose statement is this line's question."""
    old = os.path.join(project, ".tezgah", "research", "done", "old")
    _write(os.path.join(old, "state.json"), json.dumps(
        {"question": "does a warm OS page cache change request latency?",
         "phase": "concluded", "direction": "conclude", "rules": 7}) + "\n")
    _write(os.path.join(old, "claims.jsonl"), json.dumps(
        {"id": "C1", "statement": Q, "kind": "derivation", "status": "refuted",
         "proof": ["findings.md"], "falsification": "n/a", "provenance": "ai-executed"}) + "\n")
    _write(os.path.join(old, "to_human", "report.md"),
           "# Report\n\nThe warm cache claim was refuted.\n")
    _write(os.path.join(old, "to_human", "review.json"), json.dumps(
        {"producer": "a", "reviewer": "b", "dimensions": DIMENSIONS,
         "findings": [{"severity": "minor", "target": "to_human/report.md",
                       "quote": "was refuted", "status": "accepted"}]}) + "\n")


def provider_key(name, construct, item, text, model):
    """The capture-map key of one `label --provider` POST, built as spec.md 3.1 fixes it."""
    prompt = ("Instrument: %s\nConstruct: %s\nItem: %s\nText: %s\nAnswer 1 if the construct "
              "holds for this item, else 0. Reply with the digit only."
              % (name, construct, item, text))
    body = json.dumps({"messages": [{"content": prompt, "role": "user"}], "model": model,
                       "temperature": 0}, sort_keys=True, separators=(",", ":"))
    return "POST %s %s" % (OPENROUTER, hashlib.sha256(body.encode("utf-8")).hexdigest())


def cp_upper(k, n, alpha=0.05):
    """Two-sided Clopper-Pearson upper bound, by bisection on the binomial cdf."""
    if k >= n:
        return 1.0

    def cdf(p):
        return sum(math.comb(n, i) * p ** i * (1 - p) ** (n - i) for i in range(k + 1))
    lo, hi = 0.0, 1.0
    for _ in range(100):
        mid = (lo + hi) / 2
        lo, hi = (mid, hi) if cdf(mid) > alpha / 2 else (lo, mid)
    return (lo + hi) / 2


# ----------------------------------------------------------------- the builder
STUB_ORX = r'''#!@PYTHON@
import json, sys
data = json.load(open(@DATA@, encoding="utf-8"))
args = sys.argv[1:]
if args[:1] == ["logs"] and len(args) >= 2:
    run = data["runs"].get(args[1])
    if run is None:
        sys.stderr.write("no such run %s\n" % args[1])
        sys.exit(1)
    sys.stdout.write(run["log"])
    sys.exit(0)
if args[:1] == ["runs"]:
    exp = args[args.index("--experiment") + 1] if "--experiment" in args else None
    print(json.dumps([{"id": k, "status": v["status"], "experiment": v["experiment"]}
                      for k, v in sorted(data["runs"].items())
                      if exp is None or v["experiment"] == exp]))
    sys.exit(0)
if args[:2] == ["paper", "--full"] and len(args) >= 3:
    text = data.get("papers", {}).get(args[2])
    if not text:
        sys.stderr.write("no paper %s\n" % args[2])
        sys.exit(1)
    sys.stdout.write(text)
    sys.exit(0)
if args[:1] == ["projects"]:
    print("[]")
    sys.exit(0)
sys.stderr.write("stub orx: unsupported %r\n" % (args,))
sys.exit(2)
'''


def _write(path, body):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    mode = "wb" if isinstance(body, bytes) else "w"
    with open(path, mode, **({} if mode == "wb" else {"encoding": "utf-8"})) as fh:
        fh.write(body)


def _remove(path):
    """Remove a directory this process made with mkdtemp, and nothing else."""
    if (os.path.isdir(path) and os.path.basename(path).startswith(PREFIX)
            and os.path.realpath(os.path.dirname(path))
            == os.path.realpath(tempfile.gettempdir())):
        shutil.rmtree(path)


def run_log(run):
    head = "run %s%s\n" % (run["run"], " arm %s" % run["arm"] if run.get("arm") else "")
    body = "".join("%s %s\n" % (k, v) for k, v in run.get("values", {}).items())
    return head + (body or "aborted before the first measurement\n")


class Fixture(object):
    def __init__(self, tmp, env):
        self.tmp = tmp
        self.env = env
        self.project = os.path.join(tmp, "project")
        self.base = os.path.join(self.project, ".tezgah", "research", "open", "q")
        self.map_dir = os.path.join(tmp, "capture")
        self.map = {}

    def run(self, argv, stdin=None):
        proc = subprocess.run([sys.executable, CLI] + list(argv), cwd=self.project,
                              env=self.env, input=stdin, capture_output=True, text=True,
                              timeout=180)
        return proc.returncode, proc.stdout + proc.stderr

    def must(self, argv, stdin=None):
        rc, out = self.run(argv, stdin)
        if rc != 0:
            raise RuntimeError("fixture step failed: tezgah-research %s -> exit %d\n%s"
                               % (" ".join(argv), rc, out))
        return out

    def git(self, *argv):
        proc = subprocess.run(["git"] + list(argv), cwd=self.project, env=self.env,
                              capture_output=True, text=True, timeout=60)
        if proc.returncode:
            raise RuntimeError("git %s: %s" % (" ".join(argv), proc.stderr))
        return proc.stdout

    def check(self, *flags):
        return self.run(["check", "q"] + list(flags))

    def path(self, rel):
        return os.path.join(self.base, rel)

    def set_map(self, url, body):
        """Point `url` at `body` (text, or {"status": n[, "body": text]}) in the map."""
        entry = copy.deepcopy(body)
        if isinstance(body, dict):
            if "body" in body:
                name = "b%d.txt" % len(os.listdir(self.map_dir))
                _write(os.path.join(self.map_dir, name), body["body"])
                entry["body"] = name
        else:
            name = "b%d.txt" % len(os.listdir(self.map_dir))
            _write(os.path.join(self.map_dir, name), body)
            entry = name
        self.map[url] = entry
        _write(os.path.join(self.map_dir, "map.json"), json.dumps(self.map, indent=1))


def sandbox(case):
    """(tmp, env): a temp root with HOME, an empty git config, a stub orx and an empty
    capture map, removed when the case ends."""
    tmp = tempfile.mkdtemp(prefix=PREFIX)
    case.addCleanup(_remove, tmp)
    home = os.path.join(tmp, "home")
    os.makedirs(home)
    gitcfg = os.path.join(tmp, "gitconfig")
    _write(gitcfg, "[user]\n\tname = Probe\n\temail = probe@example.invalid\n"
                   "[commit]\n\tgpgsign = false\n[init]\n\tdefaultBranch = main\n")
    orx = os.path.join(tmp, "bin", "orx")
    _write(orx, STUB_ORX.replace("@PYTHON@", sys.executable)
           .replace("@DATA@", repr(os.path.join(tmp, "orx.json"))))
    os.chmod(orx, 0o755)
    _write(os.path.join(tmp, "orx.json"), json.dumps({"runs": {}}))
    os.makedirs(os.path.join(tmp, "capture"))
    _write(os.path.join(tmp, "capture", "map.json"), "{}")
    env = {"PATH": os.environ.get("PATH", "/usr/bin:/bin"), "HOME": home,
           "LANG": "C.UTF-8", "TMPDIR": tmp, "GIT_CONFIG_GLOBAL": gitcfg,
           "GIT_CONFIG_NOSYSTEM": "1", "TEZGAH_ORX_BIN": orx,
           "TEZGAH_CAPTURE_MAP": os.path.join(tmp, "capture", "map.json")}
    return tmp, env


class Rules8(unittest.TestCase):
    maxDiff = None

    def build(self, spec):
        tmp, env = sandbox(self)
        fx = Fixture(tmp, env)
        os.makedirs(fx.project)
        fx.git("init", "-q")
        _write(os.path.join(fx.project, "README.md"), "fixture\n")
        _write(os.path.join(fx.project, ".gitignore"), "/.tezgah/\n")
        fx.git("add", "-A")
        fx.git("commit", "-q", "-m", "fixture project")
        fx.env.update(spec["env"])
        orx = {"runs": {}, "papers": spec["orx_papers"]}
        for h, rows in spec["runs"].items():
            for r in rows:
                orx["runs"][r["run"]] = {"log": run_log(r),
                                         "status": r.get("status", "completed"),
                                         "experiment": r.get("experiment", "exp-q")}
        for run, extra in spec["orx_extra"].items():
            orx["runs"][run] = dict({"experiment": "exp-q"}, **extra)
        _write(os.path.join(tmp, "orx.json"), json.dumps(orx))
        for name, body in spec["tmp_files"].items():
            _write(os.path.join(tmp, name), body)
        init = ["init", "q", "--ask", Q, "--question", Q, "--method", spec["method"],
                "--in", spec["state"]["scope"]["in"][0], "--out", "other changes"]
        if spec["class"]:
            init += ["--class", spec["class"]]
        fx.must(init)
        with open(fx.path("state.json"), encoding="utf-8") as fh:
            st = json.load(fh)
        st.update(copy.deepcopy(spec["state"]))
        _write(fx.path("state.json"), json.dumps(st, indent=2) + "\n")
        for h, body in spec["protocol"].items():
            _write(fx.path("experiments/%s/protocol.md" % h), body)
        for rel, body in spec["pre_files"].items():
            _write(fx.path(rel), body)
        fx.must(["commit", "q", "protocol and evaluation lock"])
        for h, rows in spec["runs"].items():
            for r in rows:
                argv = ["source", "q", h, "--run", r["run"], "--scope", r.get("scope", "real")]
                if r.get("arm"):
                    argv += ["--arm", r["arm"]]
                if r.get("item"):
                    argv += ["--item", r["item"]]
                if r.get("instrument"):
                    argv += ["--instrument", r["instrument"]]
                for key, value in r.get("values", {}).items():
                    argv += ["--value", "%s=%s" % (key, value)]
                if r.get("fixture"):
                    argv += ["--fixture", r["fixture"]]
                fx.must(argv)
        for h, rows in spec["typed_rows"].items():
            path = fx.path("experiments/%s/results.jsonl" % h)
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, "a", encoding="utf-8") as fh:
                fh.write("".join(json.dumps(r) + "\n" for r in rows))
        for h, body in spec["analysis"].items():
            _write(fx.path("experiments/%s/analysis.md" % h), body)
        if spec["analysis"]:
            fx.must(["commit", "q", "results"])
        _write(fx.path("claims.jsonl"), "".join(json.dumps(c) + "\n" for c in spec["claims"]))
        for note, body in spec["notes"].items():
            _write(fx.path("literature/" + note), body)
        if spec["index"]:
            _write(fx.path("literature/INDEX.jsonl"),
                   "".join(json.dumps(r) + "\n" for r in spec["index"]))
        for url, body in spec["map"].items():
            fx.set_map(url, body)
        if spec["cite"]:
            fx.must(["cite", "q"])
        for entry in spec["fetch"]:
            note, extra = (entry, []) if isinstance(entry, str) else entry
            fx.must(["fetch", "q", note] + [a.replace("@TMP@", tmp) for a in extra])
        for s in spec["searches"]:
            fx.must(["search", "q", "--tag", s["tag"]]
                    + (["--item", s["item"]] if s.get("item") else []) + ["--"] + s["argv"])
        for argv, stdin in spec["ops"]:
            fx.must(argv, stdin)
        _write(fx.path("findings.md"), spec["findings"])
        _write(fx.path("log.md"), spec["log"])
        _write(fx.path("to_human/report.md"), spec["report"])
        _write(fx.path("to_human/review.json"), json.dumps(spec["review"], indent=2) + "\n")
        for rel, body in spec["files"].items():
            _write(fx.path(rel), body)
        fx.must(["commit", "q", "report and review"])
        return fx

    # assertions ------------------------------------------------------------
    def refused(self, spec, text, flags=()):
        fx = self.build(spec)
        rc, out = fx.check(*flags)
        self.assertEqual(rc, 1, out)
        self.assertRegex(out, r"(?m)^FAIL q: .*" + re.escape(text), out)
        return fx, out

    def capped(self, spec, *steps):
        fx = self.build(spec)
        rc, out = fx.check()
        self.assertEqual(rc, 0, "a cap narrows the claim and never refuses the line:\n" + out)
        for step in steps:
            self.assertRegex(out, r"(?m)^certainty q: \S+ \S+ start=\S+ steps=\S*\b%s\b"
                             % re.escape(step), out)
        return fx, out

    def certainties(self, out):
        return dict(CERTAINTY.findall(out))

    def build_check(self, spec, *flags):
        fx = self.build(spec)
        return fx, fx.check(*flags)[1]


# ----------------------------------------------------------------- C0, C1, P1-P12
class Controls(Rules8):
    def test_c0_compliant_line_passes_check_and_strict(self):
        fx = self.build(mixed_spec())
        rc, out = fx.check()
        self.assertEqual(rc, 0, out)
        rc, strict = fx.check("--strict")
        self.assertEqual(rc, 0, strict)
        self.assertEqual(self.certainties(out), {"C1": "high", "C2": "moderate"}, out)

    def test_c1_positive_control_prediction_equals_falsifier_refused(self):
        spec = mixed_spec()
        spec["protocol"]["h1"] = protocol(
            falsifier="p95 latency drops from 120 ms to at most 95 ms")
        self.refused(spec, "say the same thing")


class Probes(Rules8):
    def test_p1_causal_claim_from_one_run_capped(self):
        spec = mixed_spec()
        spec["runs"]["h1"] = [{"run": "r1", "values": {"p95_before": 120, "p95_after": 90}}]
        spec["analysis"]["h1"] = "# Analysis h1\n\nOne run: p95 120 ms before, 90 ms after.\n"
        spec["claims"][0]["statement"] = ("caching the lookups causes p95 to drop from 120 ms "
                                          "to 90 ms")
        spec["review"]["findings"][1] = {"severity": "minor",
                                         "target": "experiments/h1/raw/r1.log",
                                         "quote": "p95_after 90"}
        self.capped(spec, "no-replication")

    def test_p2_one_run_per_arm_no_interval_capped(self):
        spec = mixed_spec()
        spec["runs"]["h1"] = runs(base=(120,), cache=(90,))
        spec["analysis"]["h1"] = "# Analysis h1\n\nbase 120 ms, cache 90 ms, one run each.\n"
        spec["claims"][0]["statement"] = "the cache improves p95 from 120 ms to 90 ms"
        spec["review"]["findings"][1]["target"] = "experiments/h1/raw/r2.log"
        self.capped(spec, "no-replication", "no-interval")

    def test_p3_quote_absent_from_captured_text_refused(self):
        spec = mixed_spec()
        spec["claims"][1]["statement"] = ('Smith et al. state that "retrieval eliminates '
                                          'hallucinated citations"')
        self.refused(spec, "quote not in the captured source text")

    def test_p4_one_provider_agreeing_with_the_header_capped(self):
        # K-2 (parent, round two): plan 0.1 said refused; one agreeing provider is a step.
        spec = mixed_spec()
        spec["index"][0]["verified"] = ["orx-discover:%s" % ARX, "orx-paper:%s" % ARX]
        del spec["map"][openalex_url(ARX)]
        fx, out = self.capped(spec, "one-provider")
        self.assertNotIn("receipts from fewer than 2 providers", out)

    def test_p5_citation_that_cannot_exist_refused(self):
        spec = mixed_spec()
        spec["index"][0].update({"id": "arXiv:2499.99999",
                                 "source": "https://arxiv.org/abs/2499.99999",
                                 "verified": ["arxiv:2499.99999", "semanticscholar:0000000000"]})
        spec["notes"][NOTE] = ("# Doe 2024, A paper that does not exist\n\n> \"%s\" (sec. 4)\n"
                               % QUOTE)
        self.refused(spec, "resolves in no registry")

    def test_p6_unvalidated_llm_judge_capped(self):
        spec = mixed_spec()
        spec["protocol"]["h1"] = (
            "# Protocol h1\n\nchange: rewrite the prompt\ndesign: experiment\n"
            "prediction: the LLM judge score rises from 5 to at least 7\n"
            "falsifier: the LLM judge score stays at or below 5\n"
            "headroom: the judge scale tops out at 10\n"
            "metric: LLM judge score 1-10\nunit: points\n")
        spec["runs"]["h1"] = []
        spec["typed_rows"]["h1"] = [
            {"item": i, "judge": "model-x", "score": v, "scope": "real",
             "source": "judge.py item %d" % i} for i, v in ((1, 7), (2, 8), (3, 7))]
        spec["analysis"]["h1"] = "# Analysis h1\n\nThe judge scored 7, 8 and 7.\n"
        spec["claims"][0]["statement"] = "the rewritten prompt scores 7 or 8 with the LLM judge"
        spec["state"]["evaluation"].update({"metric": "LLM judge score", "baseline": "5"})
        spec["report"] += "\nThe LLM judge score 1-10 is the registered metric.\n"
        spec["review"]["findings"].pop(1)
        self.capped(spec, "instrument-unvalidated", "judged-row-incomplete")

    def test_p7_registered_metric_not_reported_refused(self):
        spec = mixed_spec()
        spec["protocol"]["h1"] = protocol().replace(
            "metric: p95 latency\n", "metric: p95 latency, p50 latency, error rate, memory, cpu\n")
        extra = ({"p50": 40, "error_rate": 0.02, "memory_mb": 300, "cpu": 0.5},
                 {"p50": 41, "error_rate": 0.02, "memory_mb": 310, "cpu": 0.5},
                 {"p50": 55, "error_rate": 0.09, "memory_mb": 900, "cpu": 0.9},
                 {"p50": 56, "error_rate": 0.08, "memory_mb": 910, "cpu": 0.9})
        for row, values in zip(spec["runs"]["h1"], extra):
            row["values"].update(values)
        self.refused(spec, "neither reported nor marked not_reported")

    def test_p8_falsifier_that_cannot_fail_capped(self):
        # K-1 (parent, round two): plan 0.1 said refused; an unevaluable falsifier is a step.
        spec = mixed_spec()
        spec["protocol"]["h1"] = protocol(falsifier="results may vary between runs")
        self.capped(spec, "falsifier-not-evaluable")

    def p9_spec(self):
        spec = mixed_spec()
        outcomes = {"base": [1, 1, 1, 1, 1, 1, 0, 0, 0, 0],
                    "cache": [1, 1, 0, 0, 0, 0, 0, 0, 0, 0]}
        aux_experiment(spec, "h2", item_rows("regex-labeler", ("base", "cache"), outcomes))
        spec["ops"].append((["instrument", "add", "q", "regex-labeler", "--kind", "measure",
                             "--rung", "R4", "--construct", "a slow call"], None))
        gold_ops(spec, "regex-labeler", "base", 10, 1, outcomes, wrong=4)
        claim = evidence_claim("C3", "the regex labeler marks fewer slow calls in the cache "
                                     "arm", proof=["experiments/h2/results.jsonl"])
        claim["scope"] = "fixture"
        spec["claims"].append(claim)
        spec["report"] += "- C3: low, exploratory\n"
        return spec

    def test_p9_rejected_instrument_without_switch_capped(self):
        self.capped(self.p9_spec(), "instrument-rejected")

    def test_p10_best_of_twenty_arms_without_correction_capped(self):
        spec = mixed_spec()
        rows = []
        for arm in range(1, 21):
            for rep in (1, 2, 3):
                value = 81 if arm == 17 else 100 + (arm * 7 + rep * 3) % 19
                rows.append({"arm": "v%d" % arm, "repeat": rep, "p95": value, "scope": "real",
                             "source": "bench.py v%d rep %d" % (arm, rep)})
        spec["runs"]["h1"] = []
        spec["typed_rows"]["h1"] = rows
        spec["analysis"]["h1"] = "# Analysis h1\n\nv17 is best at 81 ms in all three repeats.\n"
        spec["claims"][0]["statement"] = "variant v17 is the best of the variants at p95 81 ms"
        spec["review"]["findings"].pop(1)
        self.capped(spec, "no-multiplicity-correction")

    def test_p11_reviewer_equals_producer_up_to_case_refused(self):
        spec = mixed_spec()
        spec["review"]["producer"] = "main-session"
        spec["review"]["reviewer"] = "Main-Session"
        self.refused(spec, "is the producer")

    def test_p12_generalisation_from_one_fixture_warned(self):
        spec = mixed_spec()
        spec["runs"]["h1"] = runs(scope="fixture", fixture="one generated repository of 3 files")
        spec["claims"][0]["statement"] = ("the cache lowers p95 from 120 ms to 90 ms on every "
                                          "repository")
        spec["claims"][0]["scope"] = "fixture"
        spec["report"] += "\nThe rows are a fixture: one generated repository.\n"
        fx = self.build(spec)
        rc, out = fx.check()
        self.assertEqual(rc, 0, out)
        self.assertRegex(out, r"(?m)^warn q: .*overclaim", out)


# ----------------------------------------------------------------- forgery probes
class Forgery(Rules8):
    def test_f1_receipt_edited_in_a_later_commit_refused(self):
        fx = self.build(mixed_spec())
        with open(fx.path("literature/.receipts/RECEIPTS.jsonl"), encoding="utf-8") as fh:
            rows = [json.loads(line) for line in fh if line.strip()]
        target = next(r["file"] for r in rows if r.get("file"))
        with open(os.path.join(fx.base, target), "ab") as fh:
            fh.write(b"\n<!-- edited after capture -->\n")
        fx.must(["commit", "q", "edit a receipt"])
        rc, out = fx.check()
        self.assertEqual(rc, 1, out)
        self.assertIn("changed after its first commit", out)

    def test_f2_search_row_without_capture_refused(self):
        fx = self.build(literature_spec())
        row = {"n": 3, "tag": "primary", "item": ITEM_L, "connector": "openalex",
               "query": "caching", "url": search_url("openalex", ["caching"]),
               "file": "searches/raw/" + "0" * 64 + ".raw", "sha256": "0" * 64, "hits": 1,
               "ids": ["arXiv:%s" % ARX], "searched_at": "2026-01-01T00:00:00Z"}
        with open(fx.path("searches/SEARCHES.jsonl"), "a", encoding="utf-8") as fh:
            fh.write(json.dumps(row) + "\n")
        fx.must(["commit", "q", "a search typed by hand"])
        rc, out = fx.check()
        self.assertEqual(rc, 1, out)
        self.assertIn("has no capture", out)

    def test_f3_gold_sample_unlike_the_seeded_draw_refused(self):
        spec = mixed_spec()
        outcomes = {"a": [1, 0] * 10, "b": [0, 1] * 10}
        aux_experiment(spec, "h2", item_rows("judge-x", ("a", "b"), outcomes))
        spec["ops"].append((["instrument", "add", "q", "judge-x", "--kind", "measure",
                             "--rung", "R4", "--construct", "slow item"], None))
        fx = self.build(spec)
        drawn = seeded_draw(["i%03d" % k for k in range(1, 21)], 7, "a", 5)
        forged = sorted({"i%03d" % k for k in range(1, 21)} - set(drawn))[:5]
        record = {"instrument": "judge-x", "arm": "a", "seed": 7, "n": 5, "items": forged}
        body = json.dumps(record, indent=2) + "\n"
        rel = "instruments/gold/judge-x-a-7.json"
        _write(fx.path(rel), body)
        with open(fx.path("instruments/GOLD.jsonl"), "a", encoding="utf-8") as fh:
            fh.write(json.dumps({"instrument": "judge-x", "arm": "a", "seed": 7, "n": 5,
                                 "file": rel,
                                 "sha256": hashlib.sha256(body.encode()).hexdigest(),
                                 "drawn_at": "2026-01-01T00:00:00Z"}) + "\n")
        fx.must(["commit", "q", "a gold sample drawn by hand"])
        rc, out = fx.check()
        self.assertEqual(rc, 1, out)
        self.assertIn("differs from the seeded draw", out)


# ----------------------------------------------------------------- the sound lines (R2)
class SoundLines(Rules8):
    def test_sound_lines_keep_four_in_five_claims_at_moderate_or_above(self):
        levels = {}
        for name, spec in (("literature", literature_spec()), ("measured", measured_spec()),
                           ("mixed", mixed_spec())):
            fx = self.build(spec)
            rc, out = fx.check()
            self.assertEqual(rc, 0, "%s line:\n%s" % (name, out))
            got = self.certainties(out)
            self.assertEqual(len(got), len(spec["claims"]),
                             "%s line prints no certainty per claim:\n%s" % (name, out))
            for cid, level in got.items():
                levels["%s/%s" % (name, cid)] = level
        below = [k for k, v in levels.items() if LEVELS.index(v) < LEVELS.index("moderate")]
        self.assertGreaterEqual(len(levels), 5, levels)
        self.assertLessEqual(5 * len(below), len(levels),
                             "more than one in five sound claims end below moderate: %s"
                             % levels)


# ----------------------------------------------------------------- wave 1: captures
class Captures(Rules8):
    def test_unindexed_reason_caps_instead_of_refusing(self):
        spec = mixed_spec()
        spec["index"][0].update({"id": "arXiv:2499.99999",
                                 "unindexed_reason": "a workshop paper no registry indexes"})
        fx, out = self.capped(spec, "unindexed-source")
        self.assertNotIn("resolves in no registry", out)

    def test_preprint_versus_venue_title_capped_not_refused(self):
        spec = mixed_spec()
        spec["index"][0]["title"] = "Request memoization for interactive services"
        fx, out = self.capped(spec, "header-mismatch")
        self.assertNotIn("FAIL", out)

    def test_online_drift_capped_and_reported(self):
        fx = self.build(mixed_spec())
        fx.set_map(arxiv_api(ARX), atom([(ARX, "A different title entirely", 2024,
                                          "Ann Smith", "We study caching.")]))
        rc, out = fx.check("--online")
        self.assertEqual(rc, 0, out)
        self.assertRegex(out, r"(?m)^online q: arXiv:%s arxiv title drifted" % re.escape(ARX))
        self.assertRegex(out, r"(?m)^certainty q: C2 .*\bonline-drift\b", out)

    def test_quote_only_in_the_agents_note_refused(self):
        spec = mixed_spec()
        spec["map"][html_url(ARX)] = html_body(TITLE, "caching changed nothing we measured")
        self.refused(spec, "quote not in the captured source text")

    def test_closed_source_with_abstract_only_capped_not_refused(self):
        spec = mixed_spec()
        spec["map"][html_url(ARX)] = {"status": 404}
        spec["report"] = spec["report"].replace("closed-access: 0 of 1", "closed-access: 1 of 1")
        fx, out = self.capped(spec, "abstract-only")
        self.assertNotIn("quote not in the captured source text", out)

    def test_connector_outside_the_allowlist_refused(self):
        fx = self.build(literature_spec())
        rc, out = fx.run(["search", "q", "--tag", "primary", "--item", ITEM_L, "--",
                          "curl", "https://example.org/search?q=caching"])
        self.assertEqual(rc, 1, out)
        self.assertIn("connector not on the allowlist", out)

    def test_hypergeometric_stopping_recomputed_from_captured_counts(self):
        # Oracle: buscarpy 0.0.2 calculate_h0 (scipy), haystack 300, recall 0.95.
        for dropped_after, oracle in ((150, "p=0.000166 met"), (20, "p=0.453536 not met")):
            fx, out = self.build_check(hypergeometric_spec(dropped_after))
            self.assertIn("stopping q: hypergeometric " + oracle, out)
            if oracle.endswith("not met"):
                self.assertRegex(out, r"(?m)^certainty q: .*\bstopping-not-met\b", out)

    def test_run_census_reports_an_engine_run_with_no_row(self):
        spec = mixed_spec()
        spec["orx_extra"] = {"r9": {"log": "run r9 arm cache\np95 92\n",
                                    "status": "completed"},
                             "r8": {"log": "run r8 arm cache\np95 93\n",
                                    "status": "completed", "experiment": "exp-other"}}
        fx = self.build(spec)
        rc, out = fx.check("--orx")
        self.assertEqual(rc, 0, out)
        self.assertIn("orx run r9 has no results row", out)
        self.assertNotIn("orx run r8", out)

    def test_aborted_run_is_a_row_and_does_not_refuse(self):
        spec = mixed_spec()
        spec["runs"]["h1"].append({"run": "r5", "arm": "cache", "values": {},
                                   "status": "aborted"})
        fx = self.build(spec)
        with open(fx.path("experiments/h1/results.jsonl"), encoding="utf-8") as fh:
            rows = [json.loads(line) for line in fh if line.strip()]
        self.assertIn("aborted", [r.get("status") for r in rows if r.get("run") == "r5"])
        for flags in ((), ("--strict",)):
            rc, out = fx.check(*flags)
            self.assertEqual(rc, 0, out)

    def test_source_value_absent_from_the_run_log_refused(self):
        spec = mixed_spec()
        spec["orx_extra"] = {"r6": {"log": "run r6 arm cache\np95 92\n", "status": "completed"}}
        fx = self.build(spec)
        rc, out = fx.run(["source", "q", "h1", "--run", "r6", "--arm", "cache",
                          "--value", "p95=77", "--scope", "real"])
        self.assertEqual(rc, 1, out)
        self.assertIn("value not in the run log", out)


# ----------------------------------------------------------------- wave 2
class Certainty(Rules8):
    def test_declared_high_over_two_missing_obligations_refused_with_both_steps(self):
        spec = mixed_spec()
        spec["protocol"]["h1"] = protocol(rivals=False).replace("n: 2\n", "")
        spec["claims"][0]["certainty"] = "high"
        fx, out = self.refused(spec, "above the computed")
        self.assertRegex(out, r"(?m)^certainty q: C1 low start=high steps=\S*")
        line = re.search(r"(?m)^certainty q: C1 .*$", out).group(0)
        self.assertIn("no-power-plan", line)
        self.assertIn("fewer-than-two-rivals", line)

    def test_supported_claim_over_a_fired_falsifier_refused(self):
        spec = mixed_spec()
        spec["runs"]["h1"] = runs(cache=(115, 116))
        spec["claims"][0]["statement"] = "p95 latency went from 120 ms to 115 ms after caching"
        spec["review"]["findings"][1]["quote"] = "p95 115"
        self.refused(spec, "while its falsifier fired")

    def test_hypothesis_left_testing_in_a_concluded_line_refused(self):
        spec = mixed_spec()
        spec["state"]["hypotheses"][0]["status"] = "testing"
        self.refused(spec, "has no terminal status")

    def test_interval_including_zero_capped(self):
        spec = mixed_spec()
        spec["runs"]["h1"] = runs(base=(120, 90), cache=(91, 119))
        spec["claims"][0]["statement"] = "p95 latency dropped from 120 ms to 91 ms after caching"
        spec["review"]["findings"][1]["quote"] = "p95 91"
        self.capped(spec, "interval-includes-zero", "below-achieved-mde")

    def test_binary_arm_prints_wilson_and_clopper_pearson_at_zero_of_twenty(self):
        spec = mixed_spec()
        aux_experiment(spec, "h2", item_rows("counter", ("a", "b"),
                                             {"a": [0] * 20, "b": [1] * 20}))
        fx = self.build(spec)
        rc, out = fx.check()
        self.assertIn("stats q: h2 a n=20 k=0 wilson=[0.0000, 0.1611] cp=[0.0000, 0.1684]", out)

    def test_number_in_no_row_capped(self):
        spec = mixed_spec()
        spec["claims"][0]["statement"] = "p95 latency dropped from 120 ms to 85 ms after caching"
        self.capped(spec, "untraced-number")

    def test_derived_number_recomputed(self):
        spec = mixed_spec()
        spec["claims"][0]["statement"] = "mean p95 latency with the cache was 90.5 ms"
        spec["claims"][0]["derived_from"] = {"90.5": {"op": "mean",
                                                       "of": ["h1/r3:p95", "h1/r4:p95"]}}
        fx = self.build(spec)
        rc, out = fx.check()
        self.assertNotRegex(out, r"(?m)^certainty q: C1 .*untraced-number", out)
        self.assertNotIn("does not recompute", out)
        spec["claims"][0]["derived_from"]["90.5"]["of"] = ["h1/r1:p95", "h1/r4:p95"]
        self.refused(spec, "does not recompute")

    def test_metric_other_than_the_locked_one_refused(self):
        spec = mixed_spec()
        spec["protocol"]["h1"] = protocol().replace("metric: p95 latency\n",
                                                    "metric: p50 latency\n")
        spec["report"] += "\np50 latency is reported here.\n"
        self.refused(spec, "metric other than the locked one")

    def test_evaluator_edited_after_lock_refused(self):
        spec = mixed_spec()
        spec["protocol"]["h1"] = protocol(extra="evaluator: experiments/h1/eval.py\n")
        spec["pre_files"]["experiments/h1/eval.py"] = "print('p95')\n"
        spec["files"]["experiments/h1/eval.py"] = "print('p95 minus ten')\n"
        self.refused(spec, "evaluator file changed after lock")

    def test_select_rule_that_picks_another_group_refused(self):
        spec = mixed_spec()
        spec["protocol"]["h1"] = protocol(extra="select: min p95\n")
        spec["analysis"]["h1"] += "\nselected: base\n"
        self.refused(spec, "select rule picks")


# ----------------------------------------------------------------- wave 3
class Instruments(Rules8):
    def instrument_line(self, per_arm, n, wrong, arms=("a", "b")):
        return instrument_spec(per_arm, n, wrong, arms)

    def test_seventy_two_clean_gold_items_pass_twenty_do_not(self):
        fx = self.build(self.instrument_line(80, 72, 0))
        rc, out = fx.check()
        self.assertIn("instrument q: judge-x arm a n=72 errors=0 upper=0.0499", out)
        self.assertRegex(out, r"(?m)^instrument q: judge-x validated sum=0\.0999 "
                              r"threshold=0\.1000$")
        fx = self.build(self.instrument_line(80, 20, 0))
        rc, out = fx.check()
        self.assertIn("instrument q: judge-x arm a n=20 errors=0 upper=0.1684", out)
        self.assertRegex(out, r"(?m)^instrument q: judge-x rejected ")

    def test_one_error_needs_one_hundred_ten_items(self):
        fx = self.build(self.instrument_line(120, 110, 1))
        rc, out = fx.check()
        self.assertIn("arm a n=110 errors=1 upper=%.4f" % cp_upper(1, 110), out)
        self.assertRegex(out, r"(?m)^instrument q: judge-x validated ")
        fx = self.build(self.instrument_line(120, 109, 1))
        rc, out = fx.check()
        self.assertRegex(out, r"(?m)^instrument q: judge-x rejected ")

    def test_gold_from_one_arm_does_not_validate_the_other(self):
        spec = self.instrument_line(80, 72, 0, arms=("a",))
        spec["claims"].append(evidence_claim("C3", "the judge marks slow items in both arms",
                                             proof=["experiments/h2/results.jsonl"],
                                             scope="fixture"))
        fx, out = self.capped(spec, "instrument-unvalidated")
        self.assertRegex(out, r"(?m)^instrument q: judge-x unvalidated ")

    def test_ppi_lambda_hat_equals_the_hand_computation(self):
        spec = mixed_spec()
        values = [1, 0, 1, 1, 0, 1, 0, 0, 1, 1]
        outcomes = {"a": values}
        aux_experiment(spec, "h2", item_rows("j3", ("a",), outcomes))
        spec["ops"].append((["instrument", "add", "q", "j3", "--kind", "measure", "--rung",
                             "R3", "--construct", "slow item"], None))
        drawn, labels = gold_ops(spec, "j3", "a", 5, 3, outcomes, wrong=1)
        fx = self.build(spec)
        y = [r["truth"] for r in labels]
        f = [values[int(i[1:]) - 1] for i in drawn]
        rest = [v for k, v in enumerate(values, 1) if "i%03d" % k not in drawn]
        my, mf = statistics.mean(y), statistics.mean(f)
        cov = sum((a - my) * (b - mf) for a, b in zip(y, f)) / (len(y) - 1)
        lam = cov / ((1 + len(f) / len(rest)) * statistics.variance(f + rest))
        lam = min(1.0, max(0.0, lam))
        estimate = lam * statistics.mean(rest) + statistics.mean(
            [a - lam * b for a, b in zip(y, f)])
        rc, out = fx.check()
        self.assertIn("ppi q: j3 arm a lambda=%.4f estimate=%.4f" % (lam, estimate), out)

    def test_conclude_refused_while_a_rejected_instrument_has_no_switch(self):
        fx = self.build(Probes.p9_spec(self))
        rc, out = fx.run(["conclude", "q"])
        self.assertEqual(rc, 1, out)
        self.assertIn("has no switch or narrowing row", out)
        fx.must(["switch", "q", "regex-labeler", "--to", "R2", "--reason",
                 "hand labels from two raters replace the regex"])
        rc, out = fx.run(["conclude", "q"])
        self.assertNotIn("has no switch or narrowing row", out)

    def test_claim_on_an_uncalibrated_verifier_capped(self):
        spec = mixed_spec()
        spec["claims"][1]["verified_by"] = "cite-verifier"
        spec["ops"].append((["instrument", "add", "q", "cite-verifier", "--kind", "verdict",
                             "--rung", "R4", "--construct", "the quote supports the claim"],
                            None))
        self.capped(spec, "uncalibrated-verifier")


class Routing(Rules8):
    def test_r7_line_without_dual_screening_shows_the_step(self):
        self.capped(literature_spec("R7"), "no-dual-screening")

    def test_class_choice_without_review_shows_its_step(self):
        spec = mixed_spec()
        del spec["review"]["question_class"]
        self.capped(spec, "class-unreviewed")

    def test_method_the_class_does_not_allow_shows_its_step(self):
        spec = mixed_spec()
        spec["class"] = spec["state"]["question_class"] = "R1"
        spec["review"]["question_class"] = "R1"
        self.capped(spec, "method-not-allowed")

    def test_r0_gets_no_line(self):
        tmp, env = sandbox(self)
        fx = Fixture(tmp, env)
        os.makedirs(fx.project)
        fx.git("init", "-q")
        rc, out = fx.run(["init", "q", "--ask", "what does RFC 9110 say about 304?",
                          "--class", "R0"])
        self.assertEqual(rc, 1, out)
        self.assertIn("R0 gets no line", out)


class ReleaseCheck(Rules8):
    def known_truth(self, defects, sound):
        tmp, env = sandbox(self)
        root = os.path.join(tmp, "known-truth")
        cases, cmap = [], {}
        for k in range(sound):
            aid = "2401.1%04d" % k
            title = "Sound paper number %d on caching" % k
            cases.append({"kind": "citation", "id": "arXiv:" + aid, "title": title,
                          "year": 2024, "truth": "sound"})
            for url, body in paper_map(aid, title, "Ann Smith", QUOTE, "W9%07d" % k).items():
                name = "b%d.txt" % len(cmap)
                _write(os.path.join(root, name), body)
                cmap[url] = name
        for k in range(defects):
            cases.append({"kind": "citation", "id": "arXiv:2499.9%04d" % k,
                          "title": "Invented paper %d" % k, "year": 2024, "truth": "defect"})
        _write(os.path.join(root, "cases.jsonl"), "".join(json.dumps(c) + "\n" for c in cases))
        _write(os.path.join(root, "capture-map.json"), json.dumps(cmap))
        proc = subprocess.run([sys.executable, CLI, "release-check", "--fixtures", root],
                              cwd=tmp, env=env, capture_output=True, text=True, timeout=180)
        return proc.returncode, proc.stdout + proc.stderr

    def test_release_check_prints_both_bounds_and_passes_inside_them(self):
        rc, out = self.known_truth(36, 17)
        self.assertEqual(rc, 0, out)
        self.assertIn("misses: 0/36 upper=%.4f" % cp_upper(0, 36), out)
        self.assertIn("false alarms: 0/17 upper=%.4f" % cp_upper(0, 17), out)

    def test_release_check_fails_when_the_miss_bound_crosses(self):
        rc, out = self.known_truth(20, 17)
        self.assertEqual(rc, 1, out)
        self.assertIn("misses: 0/20 upper=0.1684", out)


# ----------------------------------------------------------------- wave 4
class Review(Rules8):
    def test_same_family_review_warns(self):
        spec = mixed_spec()
        spec["review"]["reviewer_family"] = " Anthropic "
        fx = self.build(spec)
        rc, out = fx.check()
        self.assertEqual(rc, 0, out)
        self.assertRegex(out, r"(?m)^warn q: .*same-family review")

    def test_overlap_with_a_refuted_done_claim_warns_until_related(self):
        fx = self.build(mixed_spec())
        done_line(fx.project)
        rc, out = fx.check()
        self.assertIn("overlaps refuted claim old/C1", out)
        _write(fx.path("related.jsonl"), json.dumps(
            {"line": "old", "claim": "C1", "relation": "dismissed",
             "reason": "the old line measured a cold cache"}) + "\n")
        rc, out = fx.check()
        self.assertNotIn("overlaps refuted claim old/C1", out)

    def test_brier_score_over_three_hypotheses(self):
        spec = mixed_spec()
        spec["state"]["hypotheses"] = [
            {"id": "H1", "text": "the cache lowers p95", "status": "supported",
             "probability": 0.8},
            {"id": "H2", "text": "the cache raises memory past 1 GB", "status": "refuted",
             "probability": 0.3},
            {"id": "H3", "text": "the cache changes p50", "status": "refuted",
             "probability": 0.6}]
        fx = self.build(spec)
        rc, out = fx.run(["calibration"])
        self.assertEqual(rc, 0, out)
        brier = ((1 - 0.8) ** 2 + 0.3 ** 2 + 0.6 ** 2) / 3
        self.assertIn("brier: %.4f over 3 resolved hypotheses" % brier, out)

    def decision(self, chosen_text):
        fx = self.build(mixed_spec())
        d = "decisions/d1/"
        _write(fx.path(d + "criteria.json"), json.dumps(
            {"question": Q, "baseline_variant": "V1",
             "criteria": [{"id": "K1", "name": "gain", "kind": "measured",
                           "direction": "max", "definition": "p95 ms saved"}]}) + "\n")
        for vid in ("V1", "V2"):
            _write(fx.path(d + vid + ".md"), "# %s\n\nvariant %s of the cache\n" % (vid, vid))
        _write(fx.path(d + "variants.jsonl"), "".join(json.dumps(
            {"id": v, "title": "variant " + v, "artifact": d + v + ".md",
             "status": "produced"}) + "\n" for v in ("V1", "V2")))
        fx.must(["commit", "q", "criteria and variants"])
        _write(fx.path(d + "comparison.jsonl"), "".join(json.dumps(
            {"variant": v, "criterion": "K1", "value": n, "source": d + v + ".md"}) + "\n"
            for v, n in (("V1", 1), ("V2", 2))))
        fx.must(["commit", "q", "first cells"])
        _write(fx.path(d + "V3.md"), "# V3\n\nvariant V3, designed after the cells\n")
        with open(fx.path(d + "variants.jsonl"), "a", encoding="utf-8") as fh:
            fh.write(json.dumps({"id": "V3", "title": "variant V3", "artifact": d + "V3.md",
                                 "status": "produced"}) + "\n")
        with open(fx.path(d + "comparison.jsonl"), "a", encoding="utf-8") as fh:
            fh.write(json.dumps({"variant": "V3", "criterion": "K1", "value": 3,
                                 "source": d + "V3.md"}) + "\n")
        fx.must(["commit", "q", "a later variant"])
        _write(fx.path(d + "decision.md"), "# d1 decision\n\nchosen: V3\n\n%s\n"
               "V1 is ruled out on K1: it saves the least.\n"
               "V2 is ruled out on K1: it saves less than V3.\n\n"
               "flip: a variant scoring above 3 on K1\n" % chosen_text)
        fx.must(["commit", "q", "decision"])
        return fx.check()

    def test_post_hoc_variant_chosen_without_saying_so_refused(self):
        rc, out = self.decision("V3 scores highest on K1.")
        self.assertEqual(rc, 1, out)
        self.assertIn("without saying post-hoc", out)
        rc, out = self.decision("V3 is a post-hoc variant: it was written after the first "
                                "cell, and it scores highest on K1.")
        self.assertNotIn("without saying post-hoc", out)

    def supersedes_spec(self, line):
        spec = mixed_spec()
        spec["claims"].append(evidence_claim(
            "C3", "p95 latency dropped from 120 ms to 91 ms after caching", supersedes="C1"))
        spec["report"] += line
        return spec

    def test_strict_accepts_a_supersedes_the_report_names(self):
        fx = self.build(self.supersedes_spec("- C3: high, supersedes C1: run r4 measured "
                                             "91 ms\n"))
        rc, out = fx.check("--strict")
        self.assertEqual(rc, 0, out)

    def test_supersedes_the_report_does_not_name_still_warns(self):
        fx = self.build(self.supersedes_spec("- C3: high\n"))
        rc, out = fx.check()
        self.assertRegex(out, r"(?m)^warn q: .*supersedes C1")

    def test_patterns_source_on_a_continuation_line_counts(self):
        spec = mixed_spec()
        spec["findings"] = FINDINGS % ("- caching lowers tail latency in both arms\n"
                                       "  (literature/%s)" % NOTE)
        fx = self.build(spec)
        rc, out = fx.check("--strict")
        self.assertEqual(rc, 0, out)
        self.assertNotIn("Patterns bullets name no source", out)

    def test_patterns_bullet_with_no_source_still_warns(self):
        spec = mixed_spec()
        spec["findings"] = FINDINGS % "- caching lowers tail latency\n  in both arms"
        fx = self.build(spec)
        rc, out = fx.check()
        self.assertIn("Patterns bullets name no source", out)


# ----------------------------------------------------------------- added after the spec review
def certainty_line(case, out, cid):
    found = re.search(r"(?m)^certainty q: %s .*$" % re.escape(cid), out)
    case.assertIsNotNone(found, "no certainty line for %s:\n%s" % (cid, out))
    return found.group(0)


def bare_project(case):
    """A sandboxed git project with no research line yet."""
    tmp, env = sandbox(case)
    fx = Fixture(tmp, env)
    os.makedirs(fx.project)
    fx.git("init", "-q")
    _write(os.path.join(fx.project, ".gitignore"), "/.tezgah/\n")
    fx.git("add", "-A")
    fx.git("commit", "-q", "-m", "fixture project")
    return fx


class CaptureIntegrity(Rules8):
    def test_f4_receipt_row_appended_over_a_real_capture_refused(self):
        fx = self.build(mixed_spec())
        path = fx.path("literature/.receipts/RECEIPTS.jsonl")
        with open(path, encoding="utf-8") as fh:
            rows = [json.loads(line) for line in fh if line.strip()]
        real = next(r for r in rows if r.get("provider") == "arxiv" and r.get("resolved"))
        with open(path, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(dict(real, title="A title the registry never returned")) + "\n")
        fx.must(["commit", "q", "a receipt row typed over a real capture"])
        rc, out = fx.check()
        self.assertEqual(rc, 1, out)
        self.assertRegex(out, r"(?m)^FAIL q: .*not derived from its capture")

    def test_every_capture_kind_edited_in_a_later_commit_refused(self):
        cases = (("source text", mixed_spec, "literature/.sources/SOURCES.jsonl"),
                 ("search output", literature_spec, "searches/SEARCHES.jsonl"),
                 ("run log", mixed_spec, "experiments/h1/raw/r1.log"),
                 ("gold file", lambda: instrument_spec(80, 72, 0),
                  "instruments/gold/judge-x-a-5.json"))
        for kind, make, rel in cases:
            with self.subTest(kind=kind):
                fx = self.build(make())
                if rel.endswith(".jsonl"):
                    with open(fx.path(rel), encoding="utf-8") as fh:
                        rel = json.loads(fh.readline())["file"]
                with open(fx.path(rel), "ab") as fh:
                    fh.write(b"\nedited after capture\n")
                fx.must(["commit", "q", "edit a %s" % kind])
                rc, out = fx.check()
                self.assertEqual(rc, 1, out)
                self.assertRegex(out, r"(?m)^FAIL q: .*changed after its first commit")

    def test_refiled_run_gets_a_new_log_and_the_first_stays(self):
        fx = self.build(mixed_spec())
        with open(fx.path("experiments/h1/raw/r1.log"), "rb") as fh:
            before = fh.read()
        fx.must(["source", "q", "h1", "--run", "r1", "--arm", "base", "--value", "p95=120",
                 "--scope", "real"])
        self.assertTrue(os.path.isfile(fx.path("experiments/h1/raw/r1.1.log")))
        with open(fx.path("experiments/h1/raw/r1.log"), "rb") as fh:
            self.assertEqual(fh.read(), before)
        rc, out = fx.check()
        self.assertNotIn("changed after its first commit", out)

    def test_gold_draw_over_grown_items_is_a_capture_that_exists(self):
        few = ["i%03d" % k for k in range(1, 21)]
        many = ["i%03d" % k for k in range(1, 41)]
        seed = next(s for s in range(1, 500)
                    if seeded_draw(few, s, "a", 5) != seeded_draw(many, s, "a", 5))
        spec = mixed_spec()
        aux_experiment(spec, "h2", item_rows("judge-x", ("a",), {"a": [k % 2 for k in range(20)]}))
        spec["ops"] += [(["instrument", "add", "q", "judge-x", "--kind", "measure", "--rung",
                          "R4", "--construct", "slow item"], None),
                        (["gold", "q", "judge-x", "--arm", "a", "--n", "5", "--seed", str(seed)],
                         None)]
        fx = self.build(spec)
        grown = item_rows("judge-x", ("a",), {"a": [k % 2 for k in range(40)]})[20:]
        with open(fx.path("experiments/h2/results.jsonl"), "a", encoding="utf-8") as fh:
            fh.write("".join(json.dumps(r) + "\n" for r in grown))
        fx.must(["commit", "q", "more items"])
        rc, out = fx.run(["gold", "q", "judge-x", "--arm", "a", "--n", "5", "--seed", str(seed)])
        self.assertEqual(rc, 1, out)
        self.assertIn("capture exists", out)

    def test_screening_row_naming_an_unreturned_id_capped(self):
        # K-8: a hand-search screening row is a step, not a refusal.
        spec = literature_spec()
        spec["files"]["searches/screening.jsonl"] = json.dumps(
            {"search": 1, "id": "openalex:W1", "decision": "kept", "reason": "on topic",
             "screener": "rater one"}) + "\n"
        fx, out = self.capped(spec, "screened-outside-search")
        self.assertNotIn("screens an id no captured search returned", out)

    def test_search_obligations_each_cap_their_own_step(self):
        def one_connector(s):
            s["searches"] = [{"tag": "counter", "item": ITEM_L,
                              "argv": ["openalex"] + PRIMARY_Q}]

        def no_counter(s):
            s["searches"][1]["tag"] = "primary"

        def no_stopping(s):
            del s["state"]["stopping"]

        def missed(s):
            s["state"]["known_items"] = ["arXiv:2499.00009"]
        for step, change in (("one-connector", one_connector), ("no-counter-search", no_counter),
                             ("no-stopping-rule", no_stopping), ("known-item-missed", missed)):
            with self.subTest(step=step):
                spec = literature_spec()
                change(spec)
                self.capped(spec, step)

    def test_saturation_stop_recomputed_from_the_last_search(self):
        spec = literature_spec()
        spec["state"]["stopping"] = {"rule": "saturation", "run": 1}
        fx, out = self.build_check(spec)
        self.assertIn("stopping q: saturation met", out)
        spec = literature_spec()
        spec["state"]["stopping"] = {"rule": "saturation", "run": 1}
        spec["map"][search_url("arxiv", COUNTER_Q)] = atom([
            (ARX, TITLE, 2024, "Ann Smith", "We study caching."),
            (ARX2, TITLE2, 2024, "Bo Jones", "We study warm caches."),
            ("2403.00003", "A third caching paper", 2024, "Cy Lee", "New.")])
        fx, out = self.build_check(spec)
        self.assertIn("stopping q: saturation not met", out)
        self.assertRegex(out, r"(?m)^certainty q: .*\bstopping-not-met\b")

    def test_user_supplied_full_text_needs_an_ack_and_the_report_names_it(self):
        spec = mixed_spec()
        spec["map"][html_url(ARX)] = html_body(TITLE, "caching changed nothing we measured")
        spec["tmp_files"]["paper.txt"] = "Section 4. In our study, %s.\n" % QUOTE
        ack = "the user pasted section 4 of the paper"
        spec["fetch"] = [(NOTE, ["--file", "@TMP@/paper.txt", "--ack", ack])]
        fx = self.build(spec)
        rc, out = fx.run(["fetch", "q", NOTE, "--file", os.path.join(fx.tmp, "paper.txt")])
        self.assertEqual(rc, 2, out)
        with open(fx.path("literature/.sources/SOURCES.jsonl"), encoding="utf-8") as fh:
            rows = [json.loads(line) for line in fh if line.strip()]
        self.assertEqual(rows[-1]["access"], "user")
        with open(fx.path(rows[-1]["file"]), encoding="utf-8") as fh:
            self.assertEqual(json.load(fh)["ack"], ack)
        rc, out = fx.check()
        self.assertEqual(rc, 0, out)
        self.assertNotIn("quote not in the captured source text", out)
        self.assertRegex(out, r"(?m)^warn q: .*report states no user-supplied share")
        with open(fx.path("to_human/report.md"), "a", encoding="utf-8") as fh:
            fh.write("\nuser-supplied: 1 of 1 sources\n")
        fx.must(["commit", "q", "the report names the user-supplied share"])
        rc, out = fx.check()
        self.assertNotIn("report states no user-supplied share", out)

    def test_fetch_takes_orx_full_text_before_the_abstract(self):
        spec = mixed_spec()
        spec["map"][html_url(ARX)] = {"status": 404}
        spec["orx_papers"] = {ARX: "Section 4. In our study, %s.\n" % QUOTE}
        fx, out = self.build_check(spec)
        self.assertEqual(self.certainties(out).get("C2"), "moderate", out)
        spec = mixed_spec()
        spec["map"][html_url(ARX)] = html_body(TITLE, "caching changed nothing we measured")
        spec["orx_papers"] = {ARX: "Section 4. In our study, %s.\n" % QUOTE}
        spec["fetch"] = [(NOTE, ["--orx"])]
        fx, out = self.build_check(spec)
        self.assertNotIn("quote not in the captured source text", out)

    def test_report_without_the_closed_access_share_warns(self):
        spec = mixed_spec()
        spec["report"] = spec["report"].replace("\nclosed-access: 0 of 1\n", "\n")
        fx, out = self.build_check(spec)
        self.assertRegex(out, r"(?m)^warn q: .*report states no closed-access share")

    def test_quote_with_ellipsis_and_citation_marker_is_found(self):
        spec = mixed_spec()
        spec["claims"][1]["quote"] = ("caching lowers tail latency ... in every workload we "
                                      "measured [12]")
        fx, out = self.build_check(spec)
        self.assertNotIn("quote not in the captured source text", out)
        self.assertEqual(self.certainties(out).get("C2"), "moderate", out)

    def test_year_within_one_of_the_receipt_agrees(self):
        spec = mixed_spec()
        spec["index"][0]["year"] = 2025
        fx, out = self.build_check(spec)
        self.assertEqual(self.certainties(out).get("C2"), "moderate", out)

    def test_source_value_naming_a_reserved_key_is_misuse(self):
        spec = mixed_spec()
        spec["orx_extra"] = {"r6": {"log": "run r6 arm cache\nscope 1\n", "status": "completed"}}
        fx = self.build(spec)
        rc, out = fx.run(["source", "q", "h1", "--run", "r6", "--arm", "cache", "--value",
                          "scope=1", "--scope", "real"])
        self.assertEqual(rc, 2, out)


class StatisticsAndReport(Rules8):
    def test_report_without_a_claims_certainty_warns(self):
        spec = mixed_spec()
        spec["report"] = report("Caching lowered p95 latency from 120 ms to 90 ms (C1).",
                                [("C1", "high")], (0, 1))
        fx, out = self.build_check(spec)
        self.assertRegex(out, r"(?m)^warn q: .*report states no certainty for claim C2")

    def test_untraced_number_is_never_refused_under_strict(self):
        spec = mixed_spec()
        spec["claims"][0]["statement"] = "p95 latency dropped from 120 ms to 85 ms after caching"
        spec["report"] = spec["report"].replace("- C1: high", "- C1: moderate")
        fx, out = self.build_check(spec, "--strict")
        self.assertNotRegex(out, r"(?m)^FAIL", out)
        self.assertIn("untraced-number", certainty_line(self, out, "C1"))

    def test_no_difference_claim_needs_a_sesoi_and_a_passing_tost(self):
        for extra, present, absent in (("", ("no-sesoi",), ()),
                                       ("sesoi: 5\n", ("tost-not-passed",), ()),
                                       ("sesoi: 200\n", (), ("no-sesoi", "tost-not-passed"))):
            with self.subTest(sesoi=extra.strip() or "none"):
                spec = mixed_spec()
                spec["protocol"]["h1"] = protocol(extra=extra)
                spec["runs"]["h1"] = runs(base=(120, 90), cache=(91, 119))
                spec["claims"][0].update(statement="caching left p95 latency unchanged",
                                         effect="no-difference")
                spec["review"]["findings"][1]["quote"] = "p95 91"
                fx, out = self.build_check(spec)
                line = certainty_line(self, out, "C1")
                for step in present:
                    self.assertIn(step, line)
                for step in absent:
                    self.assertNotIn(step, line)

    def test_bh_correction_caps_only_the_experiment_it_does_not_reject(self):
        spec = mixed_spec()
        spec["protocol"]["h1"] = protocol(extra="correction: bh\n")
        spec["protocol"]["h2"] = protocol("h2", extra="correction: bh\n")
        spec["typed_rows"]["h2"] = [
            {"run": "t%d" % n, "arm": arm, "p95": v, "scope": "real",
             "source": "bench.py t%d" % n}
            for n, (arm, v) in enumerate((("base", 100), ("base", 110), ("cache", 105),
                                          ("cache", 105)), 1)]
        spec["analysis"]["h2"] = "# Analysis h2\n\nCONFIRMATORY: no change between builds.\n"
        spec["claims"].append(evidence_claim("C3", "the second cache build lowered p95 latency",
                                             proof=["experiments/h2/results.jsonl"]))
        spec["report"] += "- C3: low, exploratory\n"
        fx, out = self.build_check(spec)
        self.assertIn("fails-multiplicity", certainty_line(self, out, "C3"))
        self.assertNotIn("fails-multiplicity", certainty_line(self, out, "C1"))

    def test_fewer_rows_than_the_planned_n_capped(self):
        spec = mixed_spec()
        spec["protocol"]["h1"] = protocol().replace("n: 2\n", "n: 3\n")
        self.capped(spec, "below-planned-n")

    def test_effect_line_matches_a_hand_welch_interval(self):
        fx, out = self.build_check(mixed_spec())
        se = math.sqrt(0.5 / 2 + 0.5 / 2)  # both groups have variance 0.5; Welch df is 2
        t = 0.95 / math.sqrt(2 * 0.975 * 0.025)  # the exact 0.975 t quantile at df 2
        z = statistics.NormalDist()
        mde = (z.inv_cdf(0.975) + z.inv_cdf(0.8)) * se
        self.assertIn("effect q: h1 cache vs base on p95 effect=30.0000 ci=[%.4f, %.4f] "
                      "mde=%.4f" % (30 - t * se, 30 + t * se, mde), out)

    def test_falsifier_in_words_is_accepted(self):
        spec = mixed_spec()
        spec["protocol"]["h1"] = protocol(falsifier="p95 latency exceeds 110 ms on the cache arm")
        fx, out = self.build_check(spec)
        self.assertNotIn("falsifier holds no comparator and number", out)


class InstrumentLedger(Rules8):
    def test_redraw_after_labels_refused(self):
        fx = self.build(instrument_spec(80, 72, 0))
        rc, out = fx.run(["gold", "q", "judge-x", "--arm", "a", "--n", "72", "--seed", "6"])
        self.assertEqual(rc, 1, out)
        self.assertIn("gold draw after labels", out)

    def test_a_repeated_label_warns_and_the_first_counts(self):
        spec = instrument_spec(80, 72, 0)
        drawn, labels = spec["gold"]["a"]
        flipped = "".join(json.dumps({"item": r["item"], "truth": 1 - r["truth"]}) + "\n"
                          for r in labels)
        spec["ops"].append((["label", "q", "judge-x", "--arm", "a", "--human", "rater two",
                             "--ack", "the user relabelled them"], flipped))
        fx, out = self.build_check(spec)
        self.assertRegex(out, r"(?m)^instrument q: judge-x validated ")
        self.assertRegex(out, r"(?m)^warn q: .*label repeated for ")

    def test_label_outside_the_gold_sample_refused_and_an_ack_required(self):
        spec = instrument_spec(80, 72, 0, arms=("a",))
        drawn, _ = spec["gold"]["a"]
        outside = next(i for i in ("i%03d" % k for k in range(1, 81)) if i not in drawn)
        fx = self.build(spec)
        rc, out = fx.run(["label", "q", "judge-x", "--arm", "a", "--human", "rater one",
                          "--ack", "the user labelled it"],
                         json.dumps({"item": outside, "truth": 0}) + "\n")
        self.assertEqual(rc, 1, out)
        self.assertIn("not in the gold sample", out)
        rc, out = fx.run(["label", "q", "judge-x", "--arm", "a", "--human", "rater one"],
                         json.dumps({"item": drawn[0], "truth": 0}) + "\n")
        self.assertEqual(rc, 2, out)

    def test_provider_label_records_the_models_own_name(self):
        spec = mixed_spec()
        values = [1, 0, 1, 0, 1, 0, 1, 0, 1, 0]
        rows = item_rows("judge-m", ("a",), {"a": values})
        for row in rows:
            row["text"] = "call %s took long" % row["item"]
        aux_experiment(spec, "h2", rows)
        drawn = seeded_draw([r["item"] for r in rows], 2, "a", 4)
        answer = json.dumps({"model": "openai/gpt-x-2026-01",
                             "choices": [{"message": {"content": "Answer: 1"}}]})
        for item in drawn:
            key = provider_key("judge-m", "a slow item", item, "call %s took long" % item,
                               "openai/gpt-x")
            spec["map"][key] = answer
        spec["ops"] += [(["instrument", "add", "q", "judge-m", "--kind", "measure", "--rung",
                          "R4", "--construct", "a slow item"], None),
                        (["gold", "q", "judge-m", "--arm", "a", "--n", "4", "--seed", "2"],
                         None),
                        (["label", "q", "judge-m", "--arm", "a", "--provider", "openrouter",
                          "--model", "openai/gpt-x"], None)]
        spec["env"]["OPENROUTER_API_KEY"] = "test-key"
        fx, out = self.build_check(spec)
        with open(fx.path("instruments/labels.jsonl"), encoding="utf-8") as fh:
            labels = [json.loads(line) for line in fh if line.strip()]
        self.assertEqual(sorted(r["item"] for r in labels), sorted(drawn))
        for row in labels:
            self.assertEqual(row["truth"], 1)
            self.assertEqual(row["rater"], {"kind": "model", "provider": "openrouter",
                                            "model": "openai/gpt-x-2026-01"})
        errors = sum(1 for i in drawn if values[int(i[1:]) - 1] != 1)
        self.assertIn("instrument q: judge-m arm a n=4 errors=%d upper=%.4f"
                      % (errors, cp_upper(errors, 4)), out)
        del fx.env["OPENROUTER_API_KEY"]
        rc, out = fx.run(["label", "q", "judge-m", "--arm", "a", "--provider", "openrouter",
                          "--model", "openai/gpt-x"])
        self.assertEqual(rc, 2, out)

    def test_switch_narrow_row_lets_conclude_past_the_rejected_instrument(self):
        fx = self.build(Probes.p9_spec(self))
        fx.must(["switch", "q", "regex-labeler", "--narrow",
                 "C3 now reports the labeler's output only", "--reason",
                 "4 of 10 gold labels disagree"])
        rc, out = fx.run(["conclude", "q"])
        self.assertNotIn("has no switch or narrowing row", out)


class RoutingAndReview(Rules8):
    def test_init_prints_the_class_obligations(self):
        fx = bare_project(self)
        rc, out = fx.run(["init", "q", "--ask", Q, "--question", Q, "--method", "qualitative",
                          "--class", "R7", "--in", ITEM_L, "--out", "other changes"])
        self.assertEqual(rc, 0, out)
        line = re.search(r"(?m)^obligations: .*$", out)
        self.assertIsNotNone(line, out)
        for step in ("no-dual-screening", "no-recall-stopping", "one-connector"):
            self.assertIn(step, line.group(0))

    def test_budget_line_counts_sources_searches_and_runs(self):
        fx, out = self.build_check(mixed_spec())
        self.assertIn("budget q: sources 1/30 searches 0/40 runs 4/40", out)

    def test_default_known_truth_set_holds_enough_cases(self):
        tmp, env = sandbox(self)
        proc = subprocess.run([sys.executable, CLI, "release-check"], cwd=tmp, env=env,
                              capture_output=True, text=True, timeout=600)
        out = proc.stdout + proc.stderr
        self.assertEqual(proc.returncode, 0, out)
        misses = re.search(r"(?m)^misses: \d+/(\d+) upper=", out)
        alarms = re.search(r"(?m)^false alarms: \d+/(\d+) upper=", out)
        self.assertIsNotNone(misses, out)
        self.assertIsNotNone(alarms, out)
        self.assertGreaterEqual(int(misses.group(1)), 36)
        self.assertGreaterEqual(int(alarms.group(1)), 17)

    def test_review_quoting_no_raw_log_or_code_warns(self):
        spec = mixed_spec()
        spec["review"]["findings"].pop(1)
        fx, out = self.build_check(spec)
        self.assertRegex(out, r"(?m)^warn q: .*review quotes no raw log or code")

    def test_init_lists_overlapping_done_claims(self):
        fx = bare_project(self)
        done_line(fx.project)
        rc, out = fx.run(["init", "q", "--ask", Q, "--question", Q, "--method", "measured",
                          "--class", "R6", "--in", ITEM, "--out", "other changes"])
        self.assertEqual(rc, 0, out)
        self.assertRegex(out, r"(?m)^overlap: old/C1 refuted \d\.\d\d$")


# ----------------------------------------------------------------- review rounds one and two
def tz_git(fx, *argv, **extra_env):
    """git in the fixture's `.tezgah` repository (where the line's commits live)."""
    proc = subprocess.run(["git", "-C", os.path.join(fx.project, ".tezgah")] + list(argv),
                          env=dict(fx.env, **extra_env), capture_output=True, text=True,
                          timeout=60)
    if proc.returncode:
        raise RuntimeError("git %s: %s" % (" ".join(argv), proc.stderr))
    return proc.stdout.strip()


def ledger_rows(fx, rel):
    with open(fx.path(rel), encoding="utf-8") as fh:
        return [json.loads(line) for line in fh if line.strip()]


def append_row(fx, rel, row):
    with open(fx.path(rel), "a", encoding="utf-8") as fh:
        fh.write(json.dumps(row) + "\n")


class RoundOne(Rules8):
    def test_protocol_numbers_read_as_written(self):
        spec = mixed_spec()
        spec["protocol"]["h1"] = (protocol().replace("alpha: 0.05", "alpha: .05")
                                  .replace("power: 0.8", "power: 80%")
                                  .replace("mde: 10", "mde: 1e1"))
        fx, out = self.build_check(spec)
        self.assertNotIn("is not a number", out)
        self.assertEqual(self.certainties(out), {"C1": "high", "C2": "moderate"}, out)
        self.assertIn("effect q: h1 cache vs base on p95 effect=30.0000", out)

    def test_protocol_number_outside_its_range_refused(self):
        for old, new, text in (("alpha: 0.05", "alpha: 1.5", "is not a number in (0, 1)"),
                               ("mde: 10", "mde: 0", "is not a number above 0")):
            with self.subTest(value=new):
                spec = mixed_spec()
                spec["protocol"]["h1"] = protocol().replace(old, new)
                self.refused(spec, text)

    def test_ppi_with_one_gold_item_prints_no_interval(self):
        spec = mixed_spec()
        outcomes = {"a": [1, 0, 1, 1, 0, 1, 0, 0, 1, 1]}
        aux_experiment(spec, "h2", item_rows("j3", ("a",), outcomes))
        spec["ops"].append((["instrument", "add", "q", "j3", "--kind", "measure", "--rung",
                             "R3", "--construct", "slow item"], None))
        gold_ops(spec, "j3", "a", 1, 3, outcomes)
        fx, out = self.build_check(spec)
        self.assertNotIn("Traceback", out)
        self.assertRegex(out, r"(?m)^ppi q: j3 arm a lambda=\S+ estimate=\S+ ci=none$")

    def test_derived_number_rounds_in_decimal(self):
        for written, refused in (("2.675", False), ("2.68", False), ("2.67", True)):
            with self.subTest(written=written):
                spec = mixed_spec()
                aux_experiment(spec, "h2", [
                    {"run": "t%d" % n, "arm": "a", "v": v, "scope": "fixture",
                     "fixture": "generated values", "source": "fixture.py t%d" % n}
                    for n, v in ((1, 2.6), (2, 2.75))])
                spec["claims"].append(evidence_claim(
                    "C3", "the mean v of the two runs was %s" % written,
                    proof=["experiments/h2/results.jsonl"], scope="fixture",
                    derived_from={written: {"op": "mean", "of": ["h2/t1:v", "h2/t2:v"]}}))
                if refused:
                    self.refused(spec, "does not recompute")
                else:
                    fx, out = self.build_check(spec)
                    self.assertNotIn("does not recompute", out)

    def test_boolean_outcomes_count_as_one_and_zero(self):
        spec = mixed_spec()
        aux_experiment(spec, "h2", item_rows("counter", ("a", "b"),
                                             {"a": [False] * 20, "b": [True] * 20}))
        fx, out = self.build_check(spec)
        self.assertIn("stats q: h2 a n=20 k=0 wilson=[0.0000, 0.1611] cp=[0.0000, 0.1684]", out)

    def test_worded_comparator_is_evaluated(self):
        spec = mixed_spec()
        spec["protocol"]["h1"] = protocol(falsifier="p95 at least 110 on cache")
        spec["runs"]["h1"] = runs(cache=(115, 116))
        spec["claims"][0]["statement"] = "p95 latency went from 120 ms to 115 ms after caching"
        spec["review"]["findings"][1]["quote"] = "p95 115"
        self.refused(spec, "while its falsifier fired")

    def test_ledger_rows_with_no_file_have_no_capture(self):
        for kind, make, rel, row in (
                ("sources", mixed_spec, "literature/.sources/SOURCES.jsonl",
                 {"note": NOTE, "access": "full", "url": html_url(ARX), "sha256": None,
                  "fetched_at": "2026-01-01T00:00:00Z"}),
                ("searches", literature_spec, "searches/SEARCHES.jsonl",
                 {"n": 3, "tag": "primary", "item": ITEM_L, "connector": "openalex",
                  "query": "caching", "hits": 1, "ids": ["arXiv:%s" % ARX],
                  "searched_at": "2026-01-01T00:00:00Z"})):
            with self.subTest(ledger=kind):
                fx = self.build(make())
                append_row(fx, rel, row)
                fx.must(["commit", "q", "a %s row with no file" % kind])
                rc, out = fx.check()
                self.assertEqual(rc, 1, out)
                self.assertRegex(out, r"(?m)^FAIL q: .*names no file, so it has no capture")

    def test_receipt_row_with_another_url_refused(self):
        fx = self.build(mixed_spec())
        real = next(r for r in ledger_rows(fx, "literature/.receipts/RECEIPTS.jsonl")
                    if r.get("provider") == "arxiv" and r.get("resolved"))
        append_row(fx, "literature/.receipts/RECEIPTS.jsonl",
                   dict(real, url=arxiv_api("2401.00009")))
        fx.must(["commit", "q", "a receipt row with another url"])
        rc, out = fx.check()
        self.assertEqual(rc, 1, out)
        self.assertRegex(out, r"(?m)^FAIL q: .*receipt URL")

    def test_receipt_whose_bytes_name_another_id_refused(self):
        fx = self.build(literature_spec())
        other = next(r for r in ledger_rows(fx, "literature/.receipts/RECEIPTS.jsonl")
                     if r.get("provider") == "arxiv" and r.get("resolved")
                     and r.get("id") == "arXiv:%s" % ARX2)
        append_row(fx, "literature/.receipts/RECEIPTS.jsonl",
                   dict(other, id="arXiv:%s" % ARX, url=arxiv_api(ARX)))
        fx.must(["commit", "q", "a receipt row over another id's bytes"])
        rc, out = fx.check()
        self.assertEqual(rc, 1, out)
        self.assertRegex(out, r"(?m)^FAIL q: .*not derived from its capture")

    def test_online_compares_the_id(self):
        fx = self.build(mixed_spec())
        fx.set_map(arxiv_api(ARX), atom([("2401.00009", TITLE, 2024, "Ann Smith",
                                          "We study caching.")]))
        rc, out = fx.check("--online")
        self.assertRegex(out, r"(?m)^online q: arXiv:%s arxiv id drifted" % re.escape(ARX))

    def test_empty_formal_id_resolves_in_no_registry(self):
        spec = mixed_spec()
        spec["index"][0]["id"] = ""
        self.refused(spec, "resolves in no registry")

    def test_cited_note_with_trailing_punctuation_is_still_checked(self):
        spec = mixed_spec()
        spec["claims"][1]["statement"] = ('Smith et al. state that "retrieval eliminates '
                                          'hallucinated citations"')
        spec["claims"][1]["proof"] = ["literature/%s." % NOTE]
        self.refused(spec, "quote not in the captured source text")

    def test_quote_fragments_out_of_order_refused(self):
        spec = mixed_spec()
        spec["claims"][1]["quote"] = ("in every workload we measured ... caching lowers tail "
                                      "latency")
        self.refused(spec, "quote not in the captured source text")

    def test_spaced_citation_marker_inside_html_is_dropped(self):
        spec = mixed_spec()
        spec["map"][html_url(ARX)] = html_body(
            TITLE, 'caching lowers tail latency [<a href="#r12">12</a>] in every workload we '
                   'measured')
        fx, out = self.build_check(spec)
        self.assertNotIn("quote not in the captured source text", out)
        self.assertEqual(self.certainties(out).get("C2"), "moderate", out)

    def test_gold_row_naming_another_instruments_file_refused(self):
        fx = self.build(instrument_spec(80, 72, 0, arms=("a",)))
        rel = "instruments/gold/judge-x-a-5.json"
        with open(fx.path(rel), "rb") as fh:
            digest = hashlib.sha256(fh.read()).hexdigest()
        append_row(fx, "instruments/GOLD.jsonl",
                   {"instrument": "judge-y", "arm": "a", "seed": 5, "n": 72, "file": rel,
                    "sha256": digest, "drawn_at": "2026-01-01T00:00:00Z"})
        fx.must(["commit", "q", "a gold row naming another instrument's file"])
        rc, out = fx.check()
        self.assertEqual(rc, 1, out)
        self.assertRegex(out, r"(?m)^FAIL q: .*differs from the seeded draw")

    def test_label_row_without_an_output_is_no_label(self):
        spec = instrument_spec(80, 72, 0, arms=("a",))
        spec["ops"].append((["gold", "q", "judge-x", "--arm", "b", "--n", "72", "--seed", "5"],
                            None))
        fx = self.build(spec)
        for item in seeded_draw(["i%03d" % k for k in range(1, 81)], 5, "b", 72):
            append_row(fx, "instruments/labels.jsonl",
                       {"instrument": "judge-x", "arm": "b", "item": item, "truth": 0})
        fx.must(["commit", "q", "label rows with no output"])
        rc, out = fx.check()
        self.assertNotIn("label output differs", out)
        self.assertRegex(out, r"(?m)^instrument q: judge-x unvalidated ")

    def test_label_output_unlike_its_results_row_refused(self):
        spec = instrument_spec(80, 72, 0, arms=("a",))
        drawn, labels = spec["gold"]["a"]
        fx = self.build(spec)
        output = 1 - [k % 2 for k in range(80)][int(drawn[0][1:]) - 1]
        append_row(fx, "instruments/labels.jsonl",
                   {"instrument": "judge-x", "arm": "a", "item": drawn[0], "truth": output,
                    "output": output, "rater": {"kind": "human", "name": "rater two",
                                                "ack": "typed by hand"}})
        fx.must(["commit", "q", "a label row with another output"])
        rc, out = fx.check()
        self.assertEqual(rc, 1, out)
        self.assertRegex(out, r"(?m)^FAIL q: .*label output differs from its results row")

    def test_mde_above_one_leaves_a_measure_instrument_unvalidated(self):
        fx, out = self.build_check(instrument_spec(80, 72, 0, mde="10"))
        self.assertRegex(out, r"(?m)^instrument q: judge-x unvalidated ")


class RoundTwo(Rules8):
    def test_degenerate_alpha_is_refused_without_a_traceback(self):
        spec = mixed_spec()
        spec["protocol"]["h1"] = protocol().replace("alpha: 0.05", "alpha: 1e-20")
        fx, out = self.build_check(spec)
        self.assertNotIn("Traceback", out)
        self.assertRegex(out, r"(?m)^FAIL q: .*statistics could not be computed")

    def test_long_s_comparator_is_no_operator(self):
        spec = mixed_spec()
        spec["protocol"]["h1"] = protocol(falsifier="p95 at mo\u017ft 95 on cache")
        fx, out = self.build_check(spec)
        self.assertNotIn("Traceback", out)
        self.assertNotIn("while its falsifier fired", out)
        self.assertIn("falsifier-not-evaluable", certainty_line(self, out, "C1"))

    def test_ledger_row_dropped_from_the_branch_but_held_by_a_tag_refused(self):
        fx = self.build(mixed_spec())
        tz_git(fx, "tag", "keep")
        rows = ledger_rows(fx, "literature/.receipts/RECEIPTS.jsonl")
        _write(fx.path("literature/.receipts/RECEIPTS.jsonl"),
               "".join(json.dumps(r) + "\n" for r in rows[1:]))
        tz_git(fx, "add", "-A")
        tree = tz_git(fx, "write-tree")
        root = tz_git(fx, "commit-tree", tree, "-m", "history without the first receipt row")
        tz_git(fx, "reset", "-q", "--hard", root)
        rc, out = fx.check()
        self.assertEqual(rc, 1, out)
        self.assertRegex(out, r"(?m)^FAIL q: .*went missing after its first commit")

    def test_backdated_side_branch_does_not_satisfy_the_stopping_order(self):
        spec = literature_spec()
        del spec["state"]["stopping"]
        fx = self.build(spec)
        branch = tz_git(fx, "rev-parse", "--abbrev-ref", "HEAD")
        rel = "research/open/q/state.json"
        first = tz_git(fx, "log", "--diff-filter=A", "--format=%H", "--", rel).split()[-1]
        stopping = {"rule": "pragmatic", "risk": "a paper outside both registries is missed"}
        tz_git(fx, "checkout", "-q", "-b", "side", first)
        with open(fx.path("state.json"), encoding="utf-8") as fh:
            st = json.load(fh)
        _write(fx.path("state.json"), json.dumps(dict(st, stopping=stopping), indent=2) + "\n")
        old = "2000-01-01T00:00:00 +0000"
        tz_git(fx, "commit", "-q", "-am", "stopping on a side branch",
               GIT_AUTHOR_DATE=old, GIT_COMMITTER_DATE=old)
        tz_git(fx, "checkout", "-q", branch)
        with open(fx.path("state.json"), encoding="utf-8") as fh:
            st = json.load(fh)
        _write(fx.path("state.json"), json.dumps(dict(st, stopping=stopping), indent=2) + "\n")
        fx.must(["commit", "q", "stopping after the searches"])
        rc, out = fx.check()
        self.assertRegex(out, r"(?m)^certainty q: .*\bno-stopping-rule\b", out)

    def test_search_row_whose_file_lies_outside_searches_raw_has_no_capture(self):
        fx = self.build(literature_spec())
        first = ledger_rows(fx, "searches/SEARCHES.jsonl")[0]
        receipt = next(r for r in ledger_rows(fx, "literature/.receipts/RECEIPTS.jsonl")
                       if r.get("file"))
        append_row(fx, "searches/SEARCHES.jsonl",
                   dict(first, n=3, file=receipt["file"], sha256=receipt["sha256"]))
        fx.must(["commit", "q", "a search row on a receipt file"])
        rc, out = fx.check()
        self.assertEqual(rc, 1, out)
        self.assertRegex(out, r"(?m)^FAIL q: .*has no capture")

    def test_search_capture_backing_a_second_row_has_no_capture(self):
        fx = self.build(literature_spec())
        first = ledger_rows(fx, "searches/SEARCHES.jsonl")[0]
        append_row(fx, "searches/SEARCHES.jsonl", dict(first, n=3, tag="counter"))
        fx.must(["commit", "q", "a second search row on the same capture"])
        rc, out = fx.check()
        self.assertEqual(rc, 1, out)
        self.assertRegex(out, r"(?m)^FAIL q: .*has no capture")

    def test_search_capture_that_does_not_parse_under_its_connector_does_not_count(self):
        # R2-5: bytes under searches/raw/ that are not the row's connector output count for
        # nothing, so a forged second connector leaves the one-connector step standing.
        spec = literature_spec()
        spec["searches"] = [{"tag": "counter", "item": ITEM_L, "argv": ["openalex"] + PRIMARY_Q}]
        fx = self.build(spec)
        first = ledger_rows(fx, "searches/SEARCHES.jsonl")[0]
        body = b"<html><body>rate limited</body></html>\n"
        sha = hashlib.sha256(body).hexdigest()
        rel = "searches/raw/%s.raw" % sha
        _write(fx.path(rel), body)
        row = dict(first, n=2, tag="primary", connector="arxiv", query=" ".join(COUNTER_Q),
                   file=rel, sha256=sha, hits=0, ids=[])
        if "argv" in first:
            row["argv"] = ["arxiv"] + COUNTER_Q
        if "url" in first:
            row["url"] = search_url("arxiv", COUNTER_Q)
        append_row(fx, "searches/SEARCHES.jsonl", row)
        fx.must(["commit", "q", "a second connector whose capture is not its output"])
        rc, out = fx.check()
        self.assertNotIn("Traceback", out)
        self.assertRegex(out, r"(?m)^certainty q: .*\bone-connector\b")


class FalseRefusalsTurnedIntoSteps(Rules8):
    def test_receipt_for_an_id_no_index_row_holds_is_ignored(self):
        fx = self.build(mixed_spec())
        append_row(fx, "literature/.receipts/RECEIPTS.jsonl",
                   {"id": "arXiv:2499.00001", "provider": "arxiv", "url": "https://example.org",
                    "status": 200, "resolved": True, "file": None, "sha256": None,
                    "fetched_at": "2026-01-01T00:00:00Z", "title": "an alias left behind",
                    "first_author": None, "year": None, "abstract": None})
        fx.must(["commit", "q", "a receipt for an id the index no longer holds"])
        rc, out = fx.check()
        self.assertEqual(rc, 0, out)

    def test_quotes_found_in_full_text_abstract_and_across_a_hyphen(self):
        fx = self.build(mixed_spec())
        for cid, quote in (("C3", "across the three services"), ("C4", "We study caching"),
                           ("C5", "caching lowers tail-latency in every workload we measured")):
            append_row(fx, "claims.jsonl", literature_claim(
                cid, "Smith et al. report that caching lowers tail latency", [NOTE], quote))
        fx.must(["commit", "q", "claims written after the capture"])
        rc, out = fx.check()
        self.assertEqual(rc, 0, out)
        self.assertNotIn("quote not in the captured source text", out)

    def test_bare_doi_is_read(self):
        doi = "10.1145/3600006"
        spec = mixed_spec()
        spec["index"][0].update({"id": doi, "source": "https://doi.org/" + doi})
        spec["map"] = {
            "https://api.crossref.org/works/" + doi: json.dumps(
                {"status": "ok", "message": {"DOI": doi, "title": [TITLE],
                                             "author": [{"family": "Smith", "given": "Ann"}],
                                             "issued": {"date-parts": [[2024]]}}}),
            "https://api.openalex.org/works/doi:" + doi: json.dumps(
                {"id": "https://openalex.org/W4390000009", "doi": "https://doi.org/" + doi,
                 "title": TITLE, "display_name": TITLE, "publication_year": 2024,
                 "authorships": [{"author": {"display_name": "Ann Smith"}}],
                 "open_access": {"oa_url": None},
                 "abstract_inverted_index": {"We": [0], "study": [1], "caching.": [2]}})}
        fx, out = self.build_check(spec)
        self.assertNotIn("resolves in no registry", out)
        self.assertNotIn("fewer than 2 providers", out)
        line = certainty_line(self, out, "C2")
        self.assertNotIn("header-mismatch", line)
        self.assertNotIn("one-provider", line)

    def test_source_value_matches_a_logged_number_numerically(self):
        spec = mixed_spec()
        spec["orx_extra"] = {"r6": {"log": "run r6 arm cache\np95 91.50\n",
                                    "status": "completed"}}
        fx = self.build(spec)
        rc, out = fx.run(["source", "q", "h1", "--run", "r6", "--arm", "cache", "--value",
                          "p95=91.5", "--scope", "real"])
        self.assertEqual(rc, 0, out)

    def test_source_rows_can_carry_an_instrument_for_gold(self):
        spec = mixed_spec()
        aux_experiment(spec, "h2", [])
        del spec["typed_rows"]["h2"]
        spec["runs"]["h2"] = [
            {"run": "s%d" % k, "arm": "a", "item": "i%03d" % k, "instrument": "judge-s",
             "values": {"outcome": k % 2}, "scope": "fixture", "fixture": "generated items"}
            for k in range(1, 5)]
        spec["ops"] += [(["instrument", "add", "q", "judge-s", "--kind", "measure", "--rung",
                          "R4", "--construct", "slow item"], None),
                        (["gold", "q", "judge-s", "--arm", "a", "--n", "2", "--seed", "1"],
                         None)]
        fx = self.build(spec)
        rows = ledger_rows(fx, "experiments/h2/results.jsonl")
        self.assertEqual({r.get("instrument") for r in rows}, {"judge-s"})
        self.assertTrue(os.path.isfile(fx.path("instruments/gold/judge-s-a-1.json")))


if __name__ == "__main__":
    unittest.main()
