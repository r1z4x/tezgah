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
from fractions import Fraction

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
            "review": {}, "files": {}}


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
    primary = ["caching", "tail", "latency"]
    counter = ["caching", "no", "effect", "on", "tail", "latency"]
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
    spec["ops"].append((["label", "q", instrument, "--arm", arm, "--human", "rater one"],
                        "".join(json.dumps(r) + "\n" for r in labels)))
    return drawn, labels


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


def hypergeometric_p(pool, sample, found, seen, recall):
    target = math.floor(Fraction(seen) / Fraction(str(recall)) + 1) - (seen - found)
    return sum(math.comb(target, i) * math.comb(pool - target, sample - i)
               for i in range(found + 1)) / math.comb(pool, sample)


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
    print(json.dumps([{"id": k, "status": v["status"]}
                      for k, v in sorted(data["runs"].items())]))
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
        orx = {"runs": {}}
        for h, rows in spec["runs"].items():
            for r in rows:
                orx["runs"][r["run"]] = {"log": run_log(r), "status": r.get("status",
                                                                            "completed")}
        orx["runs"].update(copy.deepcopy(spec["orx_extra"]))
        _write(os.path.join(tmp, "orx.json"), json.dumps(orx))
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
        for note in spec["fetch"]:
            fx.must(["fetch", "q", note])
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
        self.assertIn("FAIL q:", out)
        self.assertIn(text, out)
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

    def test_p4_two_records_of_one_provider_refused(self):
        spec = mixed_spec()
        spec["index"][0]["verified"] = ["orx-discover:%s" % ARX, "orx-paper:%s" % ARX]
        del spec["map"][openalex_url(ARX)]
        self.refused(spec, "receipts from fewer than 2 providers")

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
        self.capped(spec, "instrument-unvalidated")

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

    def test_p8_falsifier_that_cannot_fail_refused(self):
        spec = mixed_spec()
        spec["protocol"]["h1"] = protocol(falsifier="results may vary between runs")
        self.refused(spec, "falsifier holds no comparator and number")

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

    def test_hypergeometric_stopping_recomputed_from_counts(self):
        for sample, verdict in ((500, "met"), (200, "not met")):
            spec = literature_spec()
            spec["state"]["stopping"] = {"rule": "hypergeometric", "pool": 1000,
                                         "sample": sample, "found_in_sample": 0,
                                         "seen_relevant": 95, "recall": 0.95,
                                         "confidence": 0.95}
            fx = self.build(spec)
            rc, out = fx.check()
            p = hypergeometric_p(1000, sample, 0, 95, 0.95)
            self.assertIn("stopping q: hypergeometric p=%.4f %s" % (p, verdict), out)
            if verdict == "not met":
                self.assertRegex(out, r"(?m)^certainty q: .*\bstopping-not-met\b", out)

    def test_run_census_reports_an_engine_run_with_no_row(self):
        spec = mixed_spec()
        spec["orx_extra"] = {"r9": {"log": "run r9 arm cache\np95 92\n",
                                    "status": "completed"}}
        fx = self.build(spec)
        rc, out = fx.check("--orx")
        self.assertEqual(rc, 0, out)
        self.assertIn("orx run r9 has no results row", out)

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
        self.capped(spec, "interval-includes-zero")

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
    def instrument_line(self, per_arm, n, wrong, arms=("a", "b"), items=None):
        spec = mixed_spec()
        items = items or per_arm
        outcomes = {arm: [k % 2 for k in range(items)] for arm in ("a", "b")}
        aux_experiment(spec, "h2", item_rows("judge-x", ("a", "b"), outcomes))
        spec["ops"].append((["instrument", "add", "q", "judge-x", "--kind", "measure",
                             "--rung", "R4", "--construct", "slow item"], None))
        for arm in arms:
            gold_ops(spec, "judge-x", arm, n, 5, outcomes, wrong=wrong)
        return spec

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
        old = os.path.join(fx.project, ".tezgah", "research", "done", "old")
        _write(os.path.join(old, "state.json"), json.dumps(
            {"question": "does a warm OS page cache change request latency?",
             "phase": "concluded", "direction": "conclude", "rules": 7}) + "\n")
        _write(os.path.join(old, "claims.jsonl"), json.dumps(
            {"id": "C1", "statement": Q, "kind": "derivation", "status": "refuted",
             "proof": ["findings.md"], "falsification": "n/a",
             "provenance": "ai-executed"}) + "\n")
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
        spec["findings"] = FINDINGS % "- caching lowers tail latency\n  in both arms [C1] [C2]"
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


if __name__ == "__main__":
    unittest.main()
