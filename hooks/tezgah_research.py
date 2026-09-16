#!/usr/bin/env python3
"""The research workspace: what a research line keeps in the repository, and the
check that its protocol really predates its results.

A research task's deliverable is evidence, not a code change, so the discipline
that makes it auditable lives next to the repository it is about:

  <repo>/.tezgah/research/<slug>/
    state.json        the question, the phase, the chosen direction
    log.md            the decision timeline, newest last
    findings.md       what we know / patterns / lessons / open questions
    claims.jsonl      one fiddly claim per line: statement, status, provenance,
                      falsification criterion, proof, dependencies
    experiments/<h>/  protocol.md (committed before the run), results.jsonl,
                      analysis.md
    literature/       one note per source
    to_human/         reports for the person paying for the research

`check` enforces one rule an agent can otherwise cheat on - a protocol committed
after its results is not a prediction - and the completeness rules that make the
rest readable a week later: a claim with no falsification criterion or no
evidence, a claim whose provenance is unstated, results with no analysis, a
findings file that answers none of the four questions.
"""
import json
import os
import subprocess

PHASES = ("bootstrap", "inner", "outer", "concluded")
DIRECTIONS = ("undecided", "deepen", "broaden", "pivot", "conclude")
PROVENANCE = ("user", "ai-suggested", "ai-executed", "user-revised")
STATUSES = ("hypothesis", "untested", "testing", "supported", "weakened",
            "refuted", "revised")
FINDINGS_SECTIONS = ("What we know", "Patterns", "Lessons", "Open questions")
STATE_FILES = ("state.json", "log.md", "findings.md", "claims.jsonl")


def root(repo):
    return os.path.join(repo, ".tezgah", "research")


def slugs(repo):
    try:
        names = os.listdir(root(repo))
    except OSError:
        return []
    return sorted(n for n in names if os.path.isdir(os.path.join(root(repo), n))
                  and not n.startswith("."))


def line_dir(repo, slug):
    return os.path.join(root(repo), slug)


def first_commit_time(repo, path):
    """When the file was first committed, or None when it was never committed."""
    rel = os.path.relpath(path, repo)
    try:
        out = subprocess.run(
            ["git", "-C", repo, "log", "--diff-filter=A", "--format=%ct", "--", rel],
            capture_output=True, text=True).stdout.split()
    except OSError:
        return None
    return min(int(t) for t in out) if out else None


def _read_json(path):
    try:
        with open(path) as fh:
            return json.load(fh), None
    except Exception as exc:
        return None, str(exc)


def _check_state(base, errors):
    path = os.path.join(base, "state.json")
    if not os.path.isfile(path):
        return
    state, exc = _read_json(path)
    if exc or not isinstance(state, dict):
        errors.append("state.json does not parse (%s)" % (exc or "not an object"))
        return
    if not str(state.get("question", "")).strip():
        errors.append("state.json records no question")
    if state.get("phase") not in PHASES:
        errors.append("state.json phase %r is not one of %s"
                      % (state.get("phase"), ", ".join(PHASES)))
    if state.get("direction") not in DIRECTIONS:
        errors.append("state.json direction %r is not one of %s"
                      % (state.get("direction"), ", ".join(DIRECTIONS)))


def _check_findings(base, errors):
    path = os.path.join(base, "findings.md")
    if not os.path.isfile(path):
        return
    with open(path) as fh:
        text = fh.read()
    missing = [s for s in FINDINGS_SECTIONS if ("## " + s) not in text]
    if missing:
        errors.append("findings.md does not answer: %s" % ", ".join(missing))


def _check_claims(base, errors, warnings):
    path = os.path.join(base, "claims.jsonl")
    if not os.path.isfile(path):
        return 0
    count = 0
    with open(path) as fh:
        for n, raw in enumerate(fh, 1):
            raw = raw.strip()
            if not raw:
                continue
            count += 1
            try:
                claim = json.loads(raw)
            except ValueError as exc:
                errors.append("claims.jsonl:%d does not parse (%s)" % (n, exc))
                continue
            cid = claim.get("id") or "line %d" % n
            if not str(claim.get("statement", "")).strip():
                errors.append("claim %s states nothing" % cid)
            if not str(claim.get("falsification", "")).strip():
                errors.append("claim %s carries no falsification criterion" % cid)
            if not claim.get("proof"):
                errors.append("claim %s cites no evidence" % cid)
            if claim.get("provenance") not in PROVENANCE:
                errors.append("claim %s provenance %r is not one of %s"
                              % (cid, claim.get("provenance"), ", ".join(PROVENANCE)))
            if claim.get("status") not in STATUSES:
                errors.append("claim %s status %r is not one of %s"
                              % (cid, claim.get("status"), ", ".join(STATUSES)))
    if not count:
        warnings.append("no claims recorded yet")
    return count


def _check_experiments(repo, base, errors, git):
    exps = os.path.join(base, "experiments")
    if not os.path.isdir(exps):
        return []
    out = []
    for h in sorted(os.listdir(exps)):
        d = os.path.join(exps, h)
        if not os.path.isdir(d) or h.startswith("."):
            continue
        out.append(h)
        proto = os.path.join(d, "protocol.md")
        results = os.path.join(d, "results.jsonl")
        if not os.path.isfile(proto):
            errors.append("experiment %s has no protocol.md" % h)
            continue
        if not os.path.isfile(results):
            continue
        if not os.path.isfile(os.path.join(d, "analysis.md")):
            errors.append("experiment %s has results but no analysis.md" % h)
        if not git:
            continue
        proto_at = first_commit_time(repo, proto)
        results_at = first_commit_time(repo, results)
        if proto_at is None:
            errors.append("experiment %s: protocol.md is not committed, so it "
                          "cannot show the plan came before the run" % h)
        elif results_at is not None and proto_at >= results_at:
            errors.append("experiment %s: protocol.md was committed at or after "
                          "results.jsonl - a protocol written after the run is "
                          "not a prediction" % h)
    return out


def check_line(repo, slug, git=True):
    """(errors, warnings) for one research line. `git=False` skips the checks that
    need git history, for callers that must stay cheap (the session context)."""
    base = line_dir(repo, slug)
    errors, warnings = [], []
    if not os.path.isdir(base):
        return ["%s does not exist" % base], warnings
    for name in STATE_FILES:
        if not os.path.isfile(os.path.join(base, name)):
            errors.append("%s is missing" % name)
    _check_state(base, errors)
    _check_findings(base, errors)
    _check_claims(base, errors, warnings)
    _check_experiments(repo, base, errors, git)
    return errors, warnings


def check(repo, slug=None, git=True):
    """{slug: {"errors": [...], "warnings": [...]}} for one line or every line."""
    out = {}
    for name in ([slug] if slug else slugs(repo)):
        errors, warnings = check_line(repo, name, git=git)
        out[name] = {"errors": errors, "warnings": warnings}
    return out


def failing(repo, git=False):
    """(slug, error) pairs, for a one-line session note. Structural only by
    default: the session context must not pay for git history."""
    rows = []
    for slug, report in check(repo, git=git).items():
        for err in report["errors"]:
            rows.append((slug, err))
    return rows


def summary(repo):
    """One line per research line, for `status` and the session note."""
    out = []
    for slug in slugs(repo):
        report = check(repo, slug=slug)
        errors = report[slug]["errors"]
        out.append("%s: %s" % (slug, "ok" if not errors else "%d problem(s)" % len(errors)))
    return out


STATE_TEMPLATE = {
    "question": "",
    "phase": "bootstrap",
    "direction": "undecided",
    "created": "",
    "evaluation": {"metric": "", "baseline": "", "locked_at": ""},
    "hypotheses": [],
    "sessions": [],
}

FINDINGS_TEMPLATE = """# Findings

## What we know

## Patterns

## Lessons

## Open questions
"""

LOG_TEMPLATE = """# Research log

Newest last. One line per decision, experiment, dead end or pivot, with the
evidence that drove it.
"""


def init(repo, slug, question="", created=""):
    """Scaffold a research line. Returns the paths created (never overwrites)."""
    base = line_dir(repo, slug)
    made = []
    for sub in ("experiments", "literature", "to_human"):
        path = os.path.join(base, sub)
        os.makedirs(path, exist_ok=True)
    state = dict(STATE_TEMPLATE)
    state["question"] = question
    state["created"] = created
    files = {
        "state.json": json.dumps(state, indent=2) + "\n",
        "findings.md": FINDINGS_TEMPLATE,
        "log.md": LOG_TEMPLATE,
        "claims.jsonl": "",
    }
    for name, text in files.items():
        path = os.path.join(base, name)
        if os.path.exists(path):
            continue
        with open(path, "w") as fh:
            fh.write(text)
        made.append(path)
    return made
