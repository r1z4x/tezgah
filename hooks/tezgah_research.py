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
evidence, a claim whose provenance is unstated, a claim whose proof names a path
this line does not have, results with no analysis, a findings file that answers
none of the four questions.
"""
import json
import os
import re
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


def _git(repo, *args):
    """(stdout words, error). Never raises: a missing git is an error string."""
    try:
        proc = subprocess.run(["git", "-C", repo] + list(args),
                              capture_output=True, text=True)
    except OSError as exc:
        return [], str(exc)
    if proc.returncode != 0:
        return [], (proc.stderr.strip() or "git exited %d" % proc.returncode)
    return proc.stdout.split(), None


def added_commits(repo, path):
    """The commits that added (or renamed into) `path`, newest first."""
    rel = os.path.relpath(path, repo)
    return _git(repo, "log", "--diff-filter=AR", "--format=%H", "--", rel)


def last_touch(repo, path):
    """The newest commit that touched `path`, or None."""
    rel = os.path.relpath(path, repo)
    out, err = _git(repo, "log", "-1", "--format=%H", "--", rel)
    return (out[0] if out else None), err


def is_ancestor(repo, older, newer):
    """True/False, or None when git cannot answer.

    The order rule is decided by the commit graph, not by timestamps: two commits
    in the same second are still two commits, a rebase rewrites dates but not
    ancestry, and a backdated GIT_COMMITTER_DATE changes nothing."""
    try:
        proc = subprocess.run(["git", "-C", repo, "merge-base", "--is-ancestor",
                               older, newer], capture_output=True, text=True)
    except OSError:
        return None
    if proc.returncode == 0:
        return True
    return False if proc.returncode == 1 else None


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


def _check_findings(base, errors, warnings):
    path = os.path.join(base, "findings.md")
    if not os.path.isfile(path):
        return
    try:
        with open(path) as fh:
            text = fh.read()
    except (OSError, UnicodeDecodeError) as exc:
        errors.append("findings.md cannot be read (%s)" % exc)
        return
    missing = [s for s in FINDINGS_SECTIONS if ("## " + s) not in text]
    if missing:
        errors.append("findings.md does not answer: %s" % ", ".join(missing))


SITED = re.compile(
    r"(?:[\w.-]+/)+[\w.*-]+\.(?:md|jsonl|json|csv|tsv|py|txt|ya?ml)\b"
    r"|(?:experiments|literature|to_human)/[\w./*-]+")


def _cited(proof):
    """The path-like tokens in a claim's free-text proof."""
    text = proof if isinstance(proof, str) else " ".join(str(p) for p in proof or [])
    return sorted(set(SITED.findall(text)))


def _resolves(token, roots):
    """True when a cited token names something that exists under one of `roots`.

    `proof` is prose, so this is deliberately forgiving: bare filenames, globs
    and git refs are left alone, and a `ref:path` pair is satisfied by either
    side. What it refuses is a path the line never produced - the fabricated
    evidence failure - because that is the one part of a proof a checker can
    decide without reading the claim."""
    token = token.rstrip(".,;:)")
    if not token or "*" in token:
        return True
    parts = [token.split(":")[0]]
    if ":" in token:
        parts.insert(0, token.rsplit(":", 1)[-1])
    return any(os.path.exists(os.path.join(root, part))
               for root in roots for part in parts if part)


def _check_claims(base, errors, warnings, roots=()):
    path = os.path.join(base, "claims.jsonl")
    if not os.path.isfile(path):
        return 0
    try:
        with open(path) as fh:
            rows = fh.readlines()
    except (OSError, UnicodeDecodeError) as exc:
        errors.append("claims.jsonl cannot be read (%s)" % exc)
        return 0
    count = 0
    for n, raw in enumerate(rows, 1):
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
        else:
            for token in _cited(claim["proof"]):
                if not _resolves(token, (base,) + tuple(roots)):
                    errors.append("claim %s cites %s, which is not in this line"
                                  % (cid, token))
        if claim.get("provenance") not in PROVENANCE:
            errors.append("claim %s provenance %r is not one of %s"
                          % (cid, claim.get("provenance"), ", ".join(PROVENANCE)))
        if claim.get("status") not in STATUSES:
            errors.append("claim %s status %r is not one of %s"
                          % (cid, claim.get("status"), ", ".join(STATUSES)))
    if not count:
        warnings.append("no claims recorded yet")
    return count


def _check_experiments(repo, base, errors, warnings, git):
    exps = os.path.join(base, "experiments")
    try:
        names = sorted(os.listdir(exps))
    except OSError:
        return []
    out = []
    for h in names:
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
        if git:
            _check_protocol_order(repo, h, proto, results, errors, warnings)
    return out


def _check_protocol_order(repo, h, proto, results, errors, warnings):
    """protocol.md must have entered the history before results.jsonl, and must
    not have changed after it."""
    proto_add, proto_err = added_commits(repo, proto)
    res_add, res_err = added_commits(repo, results)
    if proto_err or res_err:
        warnings.append("experiment %s: git could not be asked about the order (%s)"
                        % (h, proto_err or res_err))
        return
    if not res_add:
        warnings.append("experiment %s: results.jsonl is not committed yet, so the "
                        "protocol order cannot be checked" % h)
        return
    if not proto_add:
        errors.append("experiment %s: protocol.md is not committed, so it cannot "
                      "show the plan came before the run" % h)
        return
    p_add, r_add = proto_add[-1], res_add[-1]
    if p_add == r_add:
        errors.append("experiment %s: one commit added both protocol.md and "
                      "results.jsonl, so the plan cannot be shown to precede the "
                      "run" % h)
        return
    before = is_ancestor(repo, p_add, r_add)
    if before is None:
        warnings.append("experiment %s: git could not order the protocol against the "
                        "results" % h)
        return
    if not before:
        errors.append("experiment %s: protocol.md entered the history after "
                      "results.jsonl - a protocol written after the run is not a "
                      "prediction" % h)
        return
    last, last_err = last_touch(repo, proto)
    if last_err or last is None or last == p_add:
        return
    if last == r_add or is_ancestor(repo, last, r_add) is False:
        errors.append("experiment %s: protocol.md changed after the run - a protocol "
                      "edited after the results is not a prediction" % h)


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
    _check_findings(base, errors, warnings)
    _check_claims(base, errors, warnings, roots=(repo,))
    _check_experiments(repo, base, errors, warnings, git)
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
