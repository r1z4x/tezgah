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
                      falsification criterion, proof, supersedes, dependencies
    predictions.jsonl one row per proposed change: the commit it landed in, the
                      number it moves, and what would falsify it
    experiments/<h>/  protocol.md (committed before the run), results.jsonl,
                      analysis.md
    literature/       one note per source
    to_human/         reports for the person paying for the research

`check` enforces the rules an agent can otherwise cheat on. The flagship one is
the order rule - a protocol committed after its results is not a prediction - and
it can only fire for a line git actually tracks, which is why the check asks
whether the paths it orders - each experiment's `protocol.md` and
`results.jsonl` - can be committed at all rather than whether the line's
directory matches an ignore pattern. Beside it stand the completeness rules that
make the rest readable a week later: a protocol that answers neither what it
predicts nor what would falsify it; a claim with no falsification criterion or no
evidence, a claim whose provenance is unstated or whose `kind` is not one of the
four proof types, a claim whose proof names no artifact of the line, names a path
this line does not have, or resolves to an experiment whose `results.jsonl` holds
no row; a claim whose `supersedes` names a claim this line does not hold; a
results row that does not say where it came from; a literature note the index
does not name, or an index row naming no note; the locked evaluation a phase past
bootstrap requires, and the session events that must say where each came from;
the six-dimension review a concluded line reports, whose findings have to quote
their target verbatim; a report a concluded line owes that states nowhere what
the evidence does not show; results with no analysis; and a findings file that
answers none of the four questions or states a pattern no source supports.

`state.json`'s `phase` is the author's declared intent, and it is not the only
authority on where the line is: `derived_phase` reads the artifacts the line
already holds - an experiment with a committed protocol and a results row, a
claim, `findings.md`'s four sections, `to_human/report.md` and
`to_human/review.json` - and a declared phase behind what they show is reported,
because a field nobody updated reads as the line still being where it was.

A prediction row is held to the same discipline by the same function the write
path calls: a `commit` that is not a 40-character sha in this history, a `metric`
or a `value_before` with no number to move, no falsifier, a commit that reached a
frozen path without a human `granted_by`, or a `claim` id the line does not hold.

Two classes of finding, and `--strict` decides which is which. A rule the checker
can decide is an error, and `check` exits 1. A guarantee the checker cannot
decide - the line's path is gitignored, so the order rule has nothing to order; a
prediction whose commit git cannot place or read; a grey source with no quality
judgement; an evidence claim bound to a run that
recorded no row; a claim written before `kind` existed, or a results row written
before `source` did; a `Patterns` bullet naming no source; a protocol that is a
brief rather than a prediction; a concluded line whose report names no limit, or
writes none at all; a claim that supersedes another - is a warning by default,
because a session mid-flight must not be blocked by a guarantee that is merely
unprovable yet, and `check --strict` turns that whole class into a refusal. One
finding is warned in both modes and is the only one that is: a declared `phase`
behind the one the line's artifacts show. The field is the author's call and the
rest of the checker reads it - `_open_reasons` decides whether a line is finished
by it - so a derivation simpler than that judgement must never fail a line the
field says is fine.

A claim enters the file through `append_claim`, not a hand edit: claims.jsonl
holds every claim of the line, so an unlocked read-modify-write of it can lose
one of two claims written at the same moment. `migrate` rewrites it under the
same lock, and derives only what the artifacts already hold - a field it cannot
derive is reported, never invented.

Every append here takes the lock before it judges what it is writing, and reads
the file-derived half of that judgement from the descriptor holding the lock: a
relation proved beside an unprotected read can be false in the file the append
commits to. The judgement and the write then meet at the file's committed size -
the offset just past its last newline (`tezgah_integrity.committed_size`) - so a
fragment a killed writer left behind is neither read as a record by the readers
here nor appended beside as one.
"""
import fnmatch
import json
import os
import re
import subprocess
import time

# The committed-size boundary, shared with the ledger's own append: a reader stops
# at the last newline and an append truncates back to it first, so a fragment a
# killed writer left behind is invisible to a reader and never becomes a row. One
# definition of where a file's records end, used by every reader and writer here
# that has to agree about it.
from tezgah_integrity import committed_size, truncate_to_committed

try:
    import fcntl
except ImportError:  # not POSIX: append_claim refuses rather than append unlocked
    fcntl = None

PHASES = ("bootstrap", "inner", "outer", "concluded")
DIRECTIONS = ("undecided", "deepen", "broaden", "pivot", "conclude")
PROVENANCE = ("user", "ai-suggested", "ai-executed", "user-revised")
STATUSES = ("hypothesis", "untested", "testing", "supported", "weakened",
            "refuted", "revised")
# The two statuses that leave a line unfinished: a proposal nobody has settled.
# Every other status - `untested`, `weakened`, `supported`, `refuted`, `revised` -
# is a decision, and a decision about a claim is the honest record of what was or
# was not run, so it closes the question even when the answer is "not run".
LIVE_STATUSES = ("hypothesis", "testing")
FINDINGS_SECTIONS = ("What we know", "Patterns", "Lessons", "Open questions")
STATE_FILES = ("state.json", "log.md", "findings.md", "claims.jsonl")

# What a claim's `proof` is a proof of. The kind decides what the cited tokens
# have to be: a run's results, a note under literature/, an artifact of the
# repository, or something the line itself holds. `derivation` is the honest
# label for a claim argued from the line's own findings rather than from a run.
KINDS = ("evidence", "code", "literature", "derivation")

# A source is either a paper record (formal) or the practice channel - a vendor
# page, a report, a tool's own documentation - which the layer allows and which
# has to be labelled, because a grey source carries no peer review to inherit.
SOURCE_CLASSES = ("formal", "grey")
FORMAL_HOSTS = ("arxiv.org", "alphaxiv.org", "doi.org", "aclanthology.org",
                "openreview.net", "ieee.org", "acm.org", "springer.com",
                "nature.com", "sciencedirect.com", "jmlr.org", "neurips.cc",
                "proceedings.mlr.press", "semanticscholar.org", "crossref.org",
                "biorxiv.org", "medrxiv.org")

SEVERITIES = ("critical", "major", "minor", "suggestion")

# What a protocol has to answer, and the shapes that count. The skill asks for
# "what it predicts, why, and what result would falsify it"; the protocols this
# repository already holds answer both in as many shapes as there are sessions -
# a heading, a bullet, a table row, a locked-evaluation line, a wrapped paragraph
# - so the two questions are read as words anywhere in the file and a real
# protocol written in prose passes. A phrase that *denies* the thing does not
# answer it: the three protocols here that are delegated briefs say "not a
# prediction" and "no prediction is claimed for it" in the body, and reading the
# word alone would take the disclaimer for an answer. The denial is read as a
# phrase - the negation, up to four words, then the word itself - so a negation
# about something else in the same file does not swallow a real prediction.
PROTOCOL_PREDICTION = re.compile(
    r"(?i)\b(predict\w*|hypothes\w*|expected (?:result|outcome|effect))\b")
PROTOCOL_FALSIFIER = re.compile(
    r"(?i)\b(falsif\w*|refut\w*|disconfirm\w*|would show (?:this|it) wrong)\b")
PROTOCOL_DENIAL = re.compile(
    r"(?i)\b(?:no|not|never|nothing|neither|nor|without|cannot|can't)\b"
    r"(?:\s+\S+){0,4}\s+(?:predict\w*|hypothes\w*|falsif\w*|refut\w*|disconfirm\w*)")

# What a concluded line's report has to say about its own limits, and the shapes
# that count. The skill asks the session to "state plainly what the evidence does
# not show"; the reports in the tree say it five ways - "What this audit does not
# show", "What this line did not look at", "Non-goals", a named "limitation", an
# "open question" - so the marker is a phrase read anywhere in the report rather
# than a heading the writer has to guess.
REPORT_LIMITS = re.compile(
    r"(?i)(does not (?:show|establish|settle|prove|measure|test|cover)"
    r"|do not (?:show|establish|settle|prove|measure|test)"
    r"|did not (?:show|look|measure|test|establish|cover)"
    r"|not (?:shown|measured|established|settled|tested|proven)"
    r"|unmeasured|limitations?|non-?goals?|open questions?|caveats?)")

# The fields a results row may already carry where the `source` rule now asks for
# one: a run's log or raw output, or the run or row it came out of. Prepended
# fields are read in this order, so the receipt the row names wins over the run id
# beside it.
ROW_SOURCE_FIELDS = ("log", "raw", "run", "id")

# What a row's numbers were measured on: the running system and its real corpus
# (`real`), an input this session generated - a probe's temp HOME, a generated
# repository, a hand-written sample (`fixture`), or a table computed from other
# rows rather than produced by an input at all (`derived`). A row's `source` says
# where it came from; this says what it is about, and the layer needs both because
# the second one cannot be recovered afterwards: `.tezgah/research/provenance-integrity`
# classified all 520 rows of this repository's research lines by their path-shaped
# text and left 438 of them unknown, so the field is the producer's to declare and
# no rule here guesses it.
SCOPES = ("real", "fixture", "derived")

# The numbers a claim's statement asserts, for the rule that says they are in the
# artifact the claim cites. A digit glued to a letter is an identifier and not a
# measurement - `p95`, `gpt-4`, `E1`, `5x` - so the token has to stand alone. The
# first pass of E2 measured the rule with the looser `\d+` and paid for it in false
# positives: the claim `the cache cuts p95` was warned about because its proof did
# not contain the string "95".
#
# A comma is never part of a number here: a dot is the only decimal mark, which is
# what this layer's own artifacts use. `4,2,2,1,1,2` is therefore six figures and not
# three decimals - a comma list is not a measurement - and `20,480` is the number
# 20480 once the separator is lifted off in `_comparable`.
NUMBER = re.compile(r"(?<![A-Za-z0-9])\d+(?:\.\d+)?(?![A-Za-z])")

# A date is not a measurement, and the containment rule used to read one as three:
# `2026-09-19` tokenised into `2026`, `09` and `19`, which is how a claim naming the
# day it was read on was warned about. The intent is a standalone number, so the
# calendar is dropped before the tokeniser sees the sentence.
ISO_DATE = re.compile(r"\d{4}-\d{2}-\d{2}")

# A thousands separator is a rendering and not a different number, so the
# containment rule compares without one: a claim stating 20480 against an artifact
# holding `20,480` is the same measurement. Every other comma is left alone, and the
# warning still quotes the artifact as it stands.
THOUSANDS = re.compile(r",(\d{3})(?!\d)")


def _numbers(text):
    """The numbers a claim's statement asserts, with the dates it names removed."""
    return NUMBER.findall(ISO_DATE.sub(" ", text))


def _comparable(text):
    """`text` with the renderings the containment rule reads through: a thousands
    separator is not a difference in the number, so both the claim and the artifact
    it cites are compared without one."""
    return THOUSANDS.sub(r"\1", text)

# The six dimensions of the review a claim passes before it is reported, as the
# research skill names them. A review missing one is not a comparable review.
REVIEW_DIMENSIONS = ("evidence_relevance", "falsifiability", "scope_calibration",
                     "argument_coherence", "exploration_integrity",
                     "methodological_rigour")

# How long an append to claims.jsonl waits for its lock, and how often it
# retries. The holders are other sessions recording one claim, so the wait is
# normally microseconds; the bound is what keeps a stuck holder from wedging the
# session that is recording its evidence. Same values as the ledger's append.
LOCK_WAIT = 1.0
LOCK_POLL = 0.01


def _soft(errors, warnings, hard, message):
    """Record a finding in the class its caller decided: `errors` is a refusal,
    `warnings` is a guarantee the checker could not decide.

    `hard` is True when the rule is decidable and the artifact is supposed to
    carry what it is missing - a phase past `bootstrap`, a file that exists - or
    when the run is `--strict`. Every caller that passes `strict` states the same
    thing: this finding is a guarantee the checker cannot prove, and a strict run
    refuses to call a line clean without it."""
    (errors if hard else warnings).append(message)


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


SLUG = re.compile(r"[a-z0-9][a-z0-9-]*")


def valid_slug(slug):
    """True for a name `slugs()` can list: lowercase letters, digits and dashes.

    `init` writes under `line_dir`, so anything else - an absolute path, a `..`,
    a slash, a leading dot - puts state.json and claims.jsonl where `check`,
    `status` and `claim` never look, or outside the repo altogether."""
    return bool(SLUG.fullmatch(slug))


def _run(argv, cwd=None):
    """(stdout, stderr-or-answer); never raises: a missing tool is an error string.

    Every external call this module makes goes through here, so a machine without
    git, or without orx, reads as an answer rather than a traceback - a check a
    session runs unattended must not need the tool installed to say what it found."""
    try:
        proc = subprocess.run(argv, capture_output=True, text=True, cwd=cwd)
    except OSError as exc:
        return "", str(exc)
    if proc.returncode != 0:
        return (proc.stdout,
                proc.stderr.strip() or "%s exited %d" % (argv[0], proc.returncode))
    return proc.stdout, None


def _git(repo, *args):
    """(stdout words, error). Never raises: a missing git is an error string."""
    out, err = _run(["git", "-C", repo] + list(args))
    return out.split(), err


def _git_out(repo, *args):
    """(raw stdout, error), for the calls whose output is a line and not a list of
    words: `check-ignore -v` answers `file:line:pattern<TAB>path`, which splitting
    on whitespace would tear apart."""
    return _run(["git", "-C", repo] + list(args))



def _ignored(repo, path):
    """The `file:line:pattern` that git ignores this exact path by, or None.

    Whether the path is ignored at all is decided by the plain form, not `-v`:
    for a directory whose last matching pattern is a negation, `check-ignore -v`
    prints that pattern and exits 0 while the directory is not ignored - measured
    on a scratch repo, and the reason a tracked line was reported as ignored."""
    rel = os.path.relpath(path, repo)
    plain, err = _git_out(repo, "check-ignore", "--", rel)
    if err or not plain.strip():
        return None
    named, verr = _git_out(repo, "check-ignore", "-v", "--", rel)
    if not verr and named.strip():
        return named.splitlines()[0].split("\t")[0].strip()
    return rel


def ignored_by(repo, path):
    """The `file:line:pattern` that git ignores `path` by, or None.

    A research line under an ignored path is a line whose two central guarantees
    are unprovable: the order rule has no commit to order, and no session reading
    the repository later can see the protocol at all. The pattern is read from git
    rather than guessed from `.gitignore`, so one inherited from a parent file or
    from an `excludesFile` is named as the source it is.

    The directory is asked first and then the state file inside it, because a tree
    can ignore a line's contents while leaving the directory itself alone. Callers
    that need one exact path - the pair the order rule orders - probe it with
    `_ignored`: appending a state file to a file path asks git about a path under
    a file."""
    for candidate in (path, os.path.join(path, STATE_FILES[0])):
        found = _ignored(repo, candidate)
        if found:
            return found
    return None


def ignored_ancestor(pattern):
    """The depth, in path components below the repository root, at which
    `pattern` stops git from descending; None when that cannot be read.

    Git cannot re-include a file whose parent directory is excluded, so undoing
    an ignore means replacing the exclusion of the directory itself with an
    exclusion of its contents and repeating that down to the line. Two shapes are
    readable: `dir/`, which excludes the directory at its own depth, and `dir/*`,
    which excludes the entries one level below it. Anything else - a mid-path
    `**`, an extension glob - is reported rather than guessed at."""
    pattern = pattern.strip()
    if not pattern or pattern.startswith("!"):
        return None
    parts = [p for p in pattern.strip("/").split("/") if p not in ("", ".")]
    if not parts:
        return None
    if parts[-1] == "*":
        return len(parts) - 1
    if pattern.endswith("/") and all("*" not in p for p in parts):
        return len(parts) - 1
    return None


def ignore_source(raw):
    """(file, line, pattern) out of the `file:line:pattern` git reports, or None
    when that is not the shape it came in."""
    if not raw or raw.count(":") < 2:
        return None
    path, line, pattern = raw.rsplit(":", 2)
    if not line.isdigit() or not os.path.isfile(path):
        return None
    return path, int(line), pattern


def negations(repo, slug, pattern):
    """The `.gitignore` lines that re-include this line under `pattern`, in the
    order they must be appended; the last of them is the plain `!<rel>/`.

    One line is not enough whenever an ancestor directory is excluded: git stops
    at the excluded directory and never reads a later negation of a path inside
    it. So each step down is paired - re-include the directory, keep ignoring its
    other entries - which is the idiom git's own documentation prescribes."""
    parts = os.path.relpath(line_dir(repo, slug), repo).split(os.sep)
    start = ignored_ancestor(pattern)
    if start is None or start >= len(parts):
        return ["!" + "/".join(parts) + "/"]
    out = []
    for i in range(start, len(parts)):
        partial = "/".join(parts[:i + 1])
        out.append("!" + partial + "/")
        if i < len(parts) - 1:
            out.append(partial + "/*")
    return out


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
        with open(path, encoding="utf-8") as fh:
            return json.load(fh), None
    except Exception as exc:
        return None, str(exc)


def _check_state(base, errors, warnings, strict):
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
    _check_evaluation(state, errors, warnings, strict)
    _check_hypotheses(state, errors)
    _check_sessions(state, errors)
    # The one rule about `phase` that is not read from the field: the line's own
    # artifacts are the other authority beside it, and a field behind them warns.
    _check_derived_phase(base, state.get("phase"), warnings)


def _check_evaluation(state, errors, warnings, strict):
    """The metric, the baseline and the lock time, and the environment they were
    measured in.

    Past `bootstrap` a line has already started running something, so a missing
    or empty criterion is a refusal: a threshold chosen after seeing results is
    not a criterion, and a baseline named later is the number the result was
    compared against after the fact. At `bootstrap` the same emptiness is the
    ordinary state of a line that has not started, so it warns - it is the prompt
    to lock the evaluation, not a violation - and `--strict` refuses it like the
    rest of the undecided class. `environment` is free-form and optional, but it
    has to be an object when it is there: a string records nothing about the
    model, the prompt or the harness the numbers came out of.

    `capability_tolerance` and `counter_metric` are optional too, and they are the
    two-gate form of the same criterion: `capability_tolerance` is the band the
    result has to stay inside before it counts at all, written as the sentence a
    reader checks it against ("capability metric within 0.02 of the baseline"),
    and `counter_metric` names the metric the change is supposed to move. Locking
    one metric is still enough - both fields are additive, and a line that moves
    no capability metric omits them, as every line in this repository does - so
    each is refused only for the state it cannot be in once a session did write
    it: a null and an absent key are the same not-written state and pass, an empty
    string, a blank string or a value of the wrong type names no band and no
    metric and is refused, which is the reading `environment` gets above. The rule
    is written where a session reads it (`skills/research/SKILL.md`,
    `docs/research.md`); what it cannot catch is a tolerance its own author sets
    so wide that every candidate passes it."""
    phase = state.get("phase")
    locked = phase != "bootstrap"
    evaluation = state.get("evaluation")
    if not isinstance(evaluation, dict):
        _soft(errors, warnings, locked or strict,
              "state.json evaluation is %s, not the object that locks the metric, "
              "the baseline and the time they were locked"
              % ("absent" if evaluation is None else type(evaluation).__name__))
        return
    empty = [k for k in ("metric", "baseline", "locked_at")
             if not str(evaluation.get(k, "")).strip()]
    if empty:
        _soft(errors, warnings, locked or strict,
              "state.json evaluation locks no %s: a criterion chosen after seeing "
              "the results is not a criterion" % ", ".join(empty))
    environment = evaluation.get("environment")
    if environment is not None and not isinstance(environment, dict):
        errors.append("state.json evaluation environment is %s, not the object of "
                      "model, prompt and harness the numbers came out of"
                      % type(environment).__name__)
    tolerance = evaluation.get("capability_tolerance")
    if tolerance is not None and (not isinstance(tolerance, str)
                                  or not tolerance.strip()):
        errors.append("state.json evaluation capability_tolerance %r is not the "
                      "band a result has to stay inside before it counts"
                      % (tolerance,))
    counter = evaluation.get("counter_metric")
    if counter is not None and (not isinstance(counter, str)
                                or not counter.strip()):
        errors.append("state.json evaluation counter_metric %r names no metric to "
                      "move: fill it, or omit the two-gate pair" % (counter,))


def _check_hypotheses(state, errors):
    """Every hypothesis states something.

    Two shapes are read because two shapes are in the tree: a plain string, and
    an object carrying `text` beside its id and status. What is refused is the
    entry that states nothing - an empty string, an object with an id and no
    text - because a hypothesis list a reader cannot read is the same as none."""
    hypotheses = state.get("hypotheses")
    if hypotheses is None:
        return
    if not isinstance(hypotheses, list):
        errors.append("state.json hypotheses is not a list")
        return
    for n, entry in enumerate(hypotheses, 1):
        text = entry if isinstance(entry, str) else (
            entry.get("text") if isinstance(entry, dict) else None)
        if not isinstance(text, str) or not text.strip():
            errors.append("state.json hypothesis %d states nothing" % n)


def _check_sessions(state, errors):
    """Every session event says where it came from.

    The provenance tag is what makes a later reader able to tell a decision the
    user made from one the session inferred, so an event without one is refused
    rather than defaulted: an untagged inference reads as the user's word. Both
    shapes in the tree are read - the flat `{tag, date, what}` this layer
    prescribes now, and the older `{date, events: [...]}` that keeps each event's
    tag one level down - and each event, wherever its tag sits, must carry one in
    PROVENANCE and say what happened."""
    sessions = state.get("sessions")
    if sessions is None:
        return
    if not isinstance(sessions, list):
        errors.append("state.json sessions is not a list")
        return
    for n, entry in enumerate(sessions, 1):
        if not isinstance(entry, dict):
            errors.append("state.json sessions[%d] is not an object: a session "
                          "event is a date, a provenance tag and what happened" % n)
            continue
        if not str(entry.get("date", "")).strip():
            errors.append("state.json sessions[%d] records no date" % n)
        if "events" in entry:
            events = entry.get("events")
            if not isinstance(events, list):
                errors.append("state.json sessions[%d] events is not a list" % n)
                continue
            for m, event in enumerate(events, 1):
                _check_event(n, m, event, errors)
            continue
        if entry.get("tag") not in PROVENANCE:
            errors.append("state.json sessions[%d] tag %r is not one of %s"
                          % (n, entry.get("tag"), ", ".join(PROVENANCE)))
        if not str(entry.get("what", "")).strip():
            errors.append("state.json sessions[%d] records nothing that happened" % n)


def _check_event(n, m, event, errors):
    """One event of a session whose entry groups them by date: a `{tag, what}`
    object, or the `tag: what` line the earliest lines in the tree wrote."""
    where = "state.json sessions[%d].events[%d]" % (n, m)
    if isinstance(event, dict):
        if event.get("tag") not in PROVENANCE:
            errors.append("%s tag %r is not one of %s"
                          % (where, event.get("tag"), ", ".join(PROVENANCE)))
        if not str(event.get("what", "")).strip():
            errors.append("%s records nothing that happened" % where)
        return
    text = event.strip() if isinstance(event, str) else ""
    tag = text.split(":", 1)[0].strip() if ":" in text else ""
    if tag not in PROVENANCE:
        errors.append("%s does not start with a provenance tag, so %r cannot be "
                      "read as one of %s"
                      % (where, text[:40], ", ".join(PROVENANCE)))
    elif not text.split(":", 1)[1].strip():
        errors.append("%s records nothing that happened" % where)



def _check_findings(base, errors, warnings, strict):
    path = os.path.join(base, "findings.md")
    if not os.path.isfile(path):
        return
    try:
        with open(path, encoding="utf-8") as fh:
            text = fh.read()
    except (OSError, UnicodeDecodeError) as exc:
        errors.append("findings.md cannot be read (%s)" % exc)
        return
    missing = [s for s in FINDINGS_SECTIONS if ("## " + s) not in text]
    if missing:
        errors.append("findings.md does not answer: %s" % ", ".join(missing))
    _check_patterns(text, errors, warnings, strict)


PATTERNS_BULLET = re.compile(r"^\s*(?:[-*+]|\d+[.)])\s+(.*)$")
PATTERNS_SOURCE = re.compile(r"\[[Cc]\d+\]|literature/[\w./-]+|\borx:[\w.-]+")


def _section(text, name):
    """The lines of one `## <name>` section, up to the next heading."""
    out, inside = [], False
    for line in text.splitlines():
        if line.startswith("#"):
            inside = line.strip() == "## " + name
            continue
        if inside:
            out.append(line)
    return out


def _check_patterns(text, errors, warnings, strict):
    """Every bullet under `## Patterns` names the source it came from.

    A pattern is the one finding a reader is meant to carry into other work, so
    the bullet that states it has to say which claim, note or run it generalises
    from - `[Cnn]`, a `literature/` path or an `orx:<id>`. A pattern that names
    none is a guess wearing the clothes of a finding, which is exactly the
    failure the review exists to catch, and it is reported once per line with the
    count so a line with seventeen of them says so in one row rather than
    seventeen."""
    bullets = [m.group(1).strip() for line in _section(text, "Patterns")
               for m in [PATTERNS_BULLET.match(line)] if m]
    unsourced = [b for b in bullets if not PATTERNS_SOURCE.search(b)]
    if unsourced:
        _soft(errors, warnings, strict,
              "findings.md: %d of %d Patterns bullets name no source ([Cnn], a "
              "literature/ note or an orx:<id>), so nothing says what they "
              "generalise from" % (len(unsourced), len(bullets)))



SITED = re.compile(
    r"(?:[\w.-]+/)+[\w.*-]+\.(?:md|jsonl|json|csv|tsv|py|txt|ya?ml)\b"
    r"|(?:experiments|literature|to_human)/[\w./*-]+")

# A filename with no directory in front of it (`findings.md`, `CHANGELOG.md`) and
# a `dir/name` pair with no extension (`bin/tezgah-status`) are artifacts too, and
# the narrow pattern above reads neither - which is why fifteen claims in this
# repository's own lines cite a real file and still looked like a proof that names
# nothing. They are only accepted once they resolve under a root, so `8/10` - a
# fraction in prose, not a path - stays out.
BARE = re.compile(r"(?<![\w./-])[\w.-]+\.(?:md|jsonl|json|csv|tsv|py|txt|ya?ml"
                  r"|sh|toml)\b")
PAIR = re.compile(r"(?<![\w./-])(?:[\w.-]+/)+[\w.-]+(?![\w./-])")

# The proof token that names an orx run: `source --run` files its log under the
# experiment's `raw/`, and the token is the only link between a claim and the run
# it came out of.
ORX_RUN = re.compile(r"\borx:([A-Za-z0-9][\w.-]*)")


def _proof_text(proof):
    """A claim's proof as text. Total: a proof that is neither a string nor an
    iterable of them - a JSON number or boolean, which a hand-written row can
    carry - is read as its own string form, where reading its items would raise."""
    if isinstance(proof, str):
        return proof
    if hasattr(proof, "__iter__"):
        return " ".join(str(p) for p in proof)
    return str(proof or "")


def _cited(proof):
    """The path-like tokens in a claim's free-text proof."""
    return sorted(set(SITED.findall(_proof_text(proof))))


def _named(proof, roots):
    """The artifacts a claim's proof names, for the rule that a proof has to name
    one. Three shapes count: a directory-qualified path, a bare filename with a
    known extension, and a `dir/name` that exists under one of `roots`. The last
    is why the rule is decided by resolution and not by shape alone - `8/10` and
    `0.8471` are prose, `bin/tezgah-status` is an artifact of this repository."""
    text = _proof_text(proof)
    tokens = set(_cited(text))
    tokens.update(m.rstrip(".,;:)") for m in BARE.findall(text))
    for token in PAIR.findall(text):
        token = token.rstrip(".,;:)")
        if _resolves(token, roots):
            tokens.add(token)
    return sorted(t for t in tokens if t)


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


def _under_literature(token, base):
    """True when a cited token names a note under this line's `literature/`. Both
    spellings in the tree are read: the token as written (`literature/x.md`,
    relative to the line) and the token as the directory sees it (`x.md`)."""
    token = token.rstrip(".,;:)")
    if token.startswith("literature/"):
        return _resolves(token, (base,))
    return _resolves(token, (os.path.join(base, "literature"),))


def _experiments_named(tokens):
    """The experiment directories a proof names, deduplicated."""
    out = set()
    for token in tokens:
        parts = token.rstrip(".,;:)").split("/")
        if parts[0] == "experiments" and len(parts) > 1 and parts[1]:
            out.add(parts[1])
    return sorted(out)


def _committed_text(path):
    """(text, error): `path` read to its committed boundary - everything up to and
    including the last newline - so an unterminated tail is invisible instead of
    being read as a broken record.

    Every JSONL reader here read the whole file to the last byte, so a fragment a
    killed writer left behind - no newline ever terminated it - was reported as a
    line that does not parse, and a line refused that way stays refused forever:
    the file is append-only, so nothing rewrites the fragment and the checker has
    no repair. The ledger's reader meanwhile skipped the identical damage, which
    is two postures on one file shape and the reason the boundary is now one
    function (`tezgah_integrity.committed_size`). A record that *did* terminate
    and does not parse is still refused: the boundary hides the tail, not the file.
    The decode is strict for the same reason the read used to be: a file that is
    not UTF-8 is reported as unreadable rather than read through a replacement
    character, which would turn a corrupt file into rows nobody wrote."""
    try:
        with open(path, "rb") as handle:
            size = committed_size(handle)
            handle.seek(0)
            return handle.read(size).decode("utf-8"), None
    except (OSError, UnicodeDecodeError) as exc:
        return None, str(exc)


def _rows(path):
    """The number of non-blank lines in a JSONL file, or None when it is not
    there. A file with zero rows is not evidence: it is a run whose output was
    never recorded, and a claim citing it is bound to nothing. The count stops at
    the committed boundary, so a fragment is not a row."""
    text, exc = _committed_text(path)
    if exc:
        return None
    return len([line for line in text.splitlines() if line.strip()])


def _row_objects(path):
    """The rows of a JSONL file as objects, skipping what does not parse; [] when the
    file is not there. `_rows` counts them and this reads them: the scope rules are
    the only ones that look inside a row rather than at its line."""
    out = []
    try:
        with open(path, encoding="utf-8") as fh:
            for line in fh:
                if not line.strip():
                    continue
                try:
                    row = json.loads(line)
                except ValueError:
                    continue
                if isinstance(row, dict):
                    out.append(row)
    except (OSError, UnicodeDecodeError):
        return []
    return out


def _declared_scope(row):
    """The scope a row or claim declares, or None. Never a guess: a value outside
    `SCOPES` is reported by the rule that reads the artifact, and reading it here as
    one of the three would be the inference the field exists to avoid."""
    scope = row.get("scope")
    return scope if isinstance(scope, str) and scope in SCOPES else None


def _evidence_scopes(claim, base, repo):
    """The declared scopes of the rows a claim rests on, for a claim that names an
    experiment of this line. A proof naming no experiment has no rows behind it, and
    the rules below have nothing to compare a claim's own scope against."""
    scopes = []
    for experiment in _experiments_named(_cited(claim.get("proof"))):
        path = os.path.join(base, "experiments", experiment, "results.jsonl")
        scopes += [_declared_scope(row) for row in _row_objects(path)]
    return scopes


def _artifact_text(proof, base, repo, limit=65536):
    """The text of the files a claim cites, for the rule that a number a claim
    asserts is in the artifact it rests on. The tokens are the ones the proof rule
    already resolves (`_named`), so a bare `findings.md` a proof may cite is read
    here too: a reader that skipped it would pass a claim's numbers against nothing,
    which is a false negative in the rule this exists for. Bounded on purpose: one
    file per token, read up to `limit` bytes, and a directory is never walked - a
    checker that walks one is a checker that hangs, which is how the probe behind E2
    behaved on its first run."""
    out = []
    for token in _named(proof, (base, repo)):
        for root in (base, repo):
            path = os.path.join(root, token)
            if os.path.isfile(path):
                try:
                    # lossy on purpose: a cited file may not be UTF-8, and a checker cannot crash
                    with open(path, encoding="utf-8", errors="replace") as fh:
                        out.append(fh.read(limit))
                except OSError:
                    pass
                break
    return "\n".join(out)


def _check_claim_scope(cid, claim, base, repo, errors, warnings, strict):
    """A claim may not claim a wider scope than the rows it rests on.

    The rows are the producer's record of what the numbers were about; a claim that
    says `real` over rows that all say `fixture` is the misrepresentation the field
    exists for, and it is decidable - two recorded strings, no judgement about what
    the claim meant. A claim resting on fixture rows that declares nothing is the
    warn class, because the rows written before this rule are in it; a claim that
    rests on fixture rows and declares `fixture` is doing exactly what the rule
    asks, and what makes it visible is `status` and the report rule.

    Rows that mix are warned about rather than refused: the declaration is a warning
    to the reader, so under-declaring is the safe direction, and a claim resting on
    one fixture row and nine real ones that says `real` hides the half that is not
    the running system. Which experiments the fixture rows are in is named, because
    that is the half a reader has to weigh."""
    declared = claim.get("scope")
    if declared is not None and declared not in SCOPES:
        errors.append("claim %s scope %r is not one of %s"
                      % (cid, declared, ", ".join(SCOPES)))
        return
    scopes = _evidence_scopes(claim, base, repo)
    fixtures = [s for s in scopes if s == "fixture"]
    if declared == "real" and scopes and len(fixtures) == len(scopes):
        errors.append("claim %s declares scope real and every row it rests on records "
                      "fixture, so the claim would present a generated input as the "
                      "running system" % cid)
    elif declared == "real" and fixtures:
        _soft(errors, warnings, strict,
              "claim %s declares scope real and rests on the fixture row(s) of %s, so "
              "part of what it reports came from a generated input"
              % (cid, ", ".join("experiments/%s" % h
                                for h in _fixture_experiments(claim, base, repo))))
    elif declared is None and fixtures:
        _soft(errors, warnings, strict,
              "claim %s rests on %d fixture row(s) and declares no scope, so a reader "
              "of the claim takes a generated input for the running system"
              % (cid, len(fixtures)))


def _fixture_experiments(claim, base, repo):
    """The experiments a claim cites that recorded at least one fixture row."""
    out = []
    for experiment in _experiments_named(_cited(claim.get("proof"))):
        path = os.path.join(base, "experiments", experiment, "results.jsonl")
        if any(_declared_scope(row) == "fixture" for row in _row_objects(path)):
            out.append(experiment)
    return out


def _check_claim_numbers(cid, claim, base, repo, errors, warnings, strict):
    """The numbers a claim asserts are in the artifact it cites.

    The claim is the sentence a reader keeps and the artifact is the receipt behind
    it, so a number in neither is the one thing a reader cannot check. E2 of
    `.tezgah/research/provenance-integrity` measured the rule against this
    repository's own claims before it was written: 63 of the 76 numeric claims (83
    percent) have every number in their proof, so a refusal would refuse 17 percent
    of claims that are not wrong - a percentage computed in the sentence, a count
    restated in words. The class is the warn one, and it names what is missing.

    The tokeniser reads a measurement and not a calendar date: `ISO_DATE` is dropped
    first, so a statement naming the day it was read on is not warned about. A
    thousands separator is not a difference either - both sides are compared without
    one - a comma list is not a number but the figures it holds, and what the warning
    quotes is the artifact as it stands. A token the window of `_artifact_text` did
    not reach is streamed for before it is called missing. The match is a substring,
    so a token can also be found inside a longer number - a claim's `10` is contained
    by an artifact holding `10000` - which is the blind spot this rule is a warning
    for: it checks that the numbers were read, not that they were measured."""
    tokens = sorted(set(_numbers(_comparable(str(claim.get("statement", ""))))))
    if not tokens or not claim.get("proof"):
        return
    text = _comparable(_artifact_text(claim["proof"], base, repo))
    if not text:
        return
    missing = [t for t in tokens if t not in text]
    if missing:
        # The window is a window: a token past its end is in the artifact and not in
        # the reading, so the rest of each cited file is streamed for it before the
        # rule says it is missing.
        missing = [t for t in missing
                   if t not in _beyond_window(missing, claim["proof"], base, repo)]
    if missing:
        _soft(errors, warnings, strict,
              "claim %s asserts %d number(s) that %s does not contain: %s"
              % (cid, len(missing), _proof_text(claim["proof"]).strip(),
                 ", ".join(missing[:4])))


def _beyond_window(tokens, proof, base, repo, chunk=65536):
    """The tokens that occur in a cited file past the window `_artifact_text` reads.

    Called only with the tokens that came back missing, so the common case never pays
    for it, and bounded the same way: one chunk at a time with an overlap as long as
    the longest token, so a token straddling a chunk boundary is still found, and no
    directory is walked. The answer stops depending on where a file's byte 65536
    falls - a number at offset 77120 is in the artifact and was not in the reading."""
    longest = max(len(t) for t in tokens)
    out = set()
    for token in _named(proof, (base, repo)):
        for root in (base, repo):
            path = os.path.join(root, token)
            if not os.path.isfile(path):
                continue
            try:
                # lossy on purpose: a cited file may not be UTF-8, and a checker cannot crash
                with open(path, encoding="utf-8", errors="replace") as fh:
                    tail = ""
                    while True:
                        block = fh.read(chunk)
                        if not block:
                            break
                        text = _comparable(tail + block)
                        out.update(t for t in tokens if t in text)
                        tail = (tail + block)[-longest:]
                        if len(out) == len(tokens):
                            break
            except (OSError, UnicodeDecodeError):
                pass
            break
    return out


def _fixture_claims(base, repo):
    """The ids of the claims a reader of the report has to be told about: the ones
    resting on a generated input, whether they declare `scope: fixture` or not."""
    out = []
    for row in _row_objects(os.path.join(base, "claims.jsonl")):
        if row.get("scope") == "fixture" or any(
                s == "fixture" for s in _evidence_scopes(row, base, repo)):
            out.append(row.get("id") or "a claim")
    return out


def run_log(base, repo, run, tokens=()):
    """The `raw/<run>.log` a proof token resolves through, or None.

    `source --run` writes it under the experiment the run belongs to, so the
    experiment the proof also names is looked at first, then the line's own
    `raw/` and the repository's - the two places a log kept outside a line can
    live. What is refused is the token that resolves nowhere: an `orx:<id>` a
    reader cannot follow is a reference, not a receipt."""
    candidates = [os.path.join(base, t, "raw", run + ".log")
                  for t in tokens if t.startswith("experiments/")]
    candidates.append(os.path.join(base, "raw", run + ".log"))
    candidates.append(os.path.join(repo, "raw", run + ".log"))
    experiments = os.path.join(base, "experiments")
    try:
        candidates.extend(os.path.join(experiments, h, "raw", run + ".log")
                          for h in os.listdir(experiments))
    except OSError:
        pass
    for path in candidates:
        if os.path.isfile(path):
            return path
    return None



def _check_claims(base, errors, warnings, roots=(), strict=False):
    path = os.path.join(base, "claims.jsonl")
    if not os.path.isfile(path):
        return 0
    text, exc = _committed_text(path)
    if exc:
        errors.append("claims.jsonl cannot be read (%s)" % exc)
        return 0
    # The committed boundary, and not the file: an unterminated tail is a
    # fragment, and turning it into "claims.jsonl:9 does not parse" made a kill
    # during one append a permanent refusal of the whole line.
    rows = text.splitlines()
    count = 0
    # The line lives inside the repository, so the repository is the last root a
    # cited token may resolve against - and the one `run_log` searches for a
    # receipt kept outside the line.
    repo = roots[-1] if roots else base
    parsed = []
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
        parsed.append((cid, claim))
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
            _check_proof(cid, claim, base, repo, errors, warnings, strict)
        if claim.get("provenance") not in PROVENANCE:
            errors.append("claim %s provenance %r is not one of %s"
                          % (cid, claim.get("provenance"), ", ".join(PROVENANCE)))
        if claim.get("status") not in STATUSES:
            errors.append("claim %s status %r is not one of %s"
                          % (cid, claim.get("status"), ", ".join(STATUSES)))
        _check_claim_scope(cid, claim, base, repo, errors, warnings, strict)
        _check_claim_numbers(cid, claim, base, repo, errors, warnings, strict)
    _check_supersedes(parsed, errors, warnings, strict)
    if not count:
        warnings.append("no claims recorded yet")
    return count


def _check_supersedes(parsed, errors, warnings, strict):
    """A claim that supersedes another names one this line holds, and says so.

    The record is append-only: a claim whose number went stale is corrected by a
    new claim, and nothing in the file says the correction happened - C27 of this
    repository's own audit line went stale when a later fix changed its number,
    and the reader who opens C27 alone reads it as current. The field is what
    makes the relation visible, and the two halves of this rule are the two
    failures it can have: an id no claim carries is refused, because a relation to
    nothing is the same as none, and a relation that holds warns, naming both
    ids, because that is the whole point of recording it."""
    known = {c["id"] for _, c in parsed if isinstance(c.get("id"), str) and c["id"]}
    for cid, claim in parsed:
        ids, problem = _supersedes(claim)
        if problem:
            errors.append("claim %s %s" % (cid, problem))
            continue
        for ref in ids:
            if ref not in known:
                errors.append("claim %s supersedes %s, and no claim in this line "
                              "carries that id" % (cid, ref))
                continue
            _soft(errors, warnings, strict,
                  "claim %s supersedes %s: a reader who opens %s alone reads the "
                  "statement this line has since replaced" % (cid, ref, ref))


def _supersedes(claim):
    """(ids, problem): the claim ids this claim says it supersedes.

    The field is optional - a claim that corrects nothing is not asked to carry
    it - and when it is there it is one claim id or a list of them. A number, an
    object or a list holding one is refused rather than coerced: a supersedes
    relation nobody can follow is the same as none, and the temptation to read
    `"C1"` out of whatever is there is how a checker starts inventing fields."""
    raw = claim.get("supersedes")
    if raw is None:
        return [], None
    if isinstance(raw, str):
        ids = [raw.strip()]
    elif isinstance(raw, list) and all(isinstance(part, str) for part in raw):
        ids = [part.strip() for part in raw]
    else:
        return [], "supersedes %r is not a claim id or a list of them" % (raw,)
    if not all(ids):
        return [], "supersedes names an empty id"
    return ids, None


def _claim_ids(base, handle=None):
    """The ids `claims.jsonl` already carries, for the rule that a claim may only
    supersede one this line holds. A row that does not parse is skipped here: the
    checker reports it, and the writer's own rules already refuse to append one.

    When `handle` is given the ids are read through it, to its committed boundary,
    instead of by path: `append_claim` holds the exclusive lock on that descriptor
    when it asks, so the ids a write path validates against are the ids the append
    it is about to make commits beside - read before the lock, another session
    could land the very id the check had just found absent."""
    if handle is not None:
        size = committed_size(handle)
        handle.seek(0)
        text = handle.read(size).decode("utf-8", "replace")
    else:
        text, _exc = _committed_text(os.path.join(base, "claims.jsonl"))
        text = text or ""
    ids = set()
    for raw in text.splitlines():
        if not raw.strip():
            continue
        try:
            claim = json.loads(raw)
        except ValueError:
            continue
        if isinstance(claim, dict) and isinstance(claim.get("id"), str):
            ids.add(claim["id"])
    return ids


def _check_proof(cid, claim, base, repo, errors, warnings, strict):
    """What the proof has to be, given the kind the claim declares - a proof naming
    no artifact is refused whatever the kind ("verified by hand, I checked it" is
    the fabricated-evidence failure a reader cannot catch later). Past that the
    kind decides: `evidence` names something the line produced, `literature` a
    note under `literature/`, `code` artifacts of the repository, `derivation`
    something the line holds; no `kind` warns and `--strict` refuses it."""
    tokens = _cited(claim["proof"])
    named = _named(claim["proof"], (base, repo))
    for run in ORX_RUN.findall(_proof_text(claim["proof"])):
        if run_log(base, repo, run, tokens) is None:
            errors.append("claim %s cites orx:%s, and no raw/%s.log is under this "
                          "line or the repository, so the receipt is missing"
                          % (cid, run, run))
    kind = claim.get("kind")
    if kind is not None and kind not in KINDS:
        errors.append("claim %s kind %r is not one of %s"
                      % (cid, kind, ", ".join(KINDS)))
        return
    if kind is None:
        _soft(errors, warnings, strict,
              "claim %s carries no kind, so nothing says what its proof is a "
              "proof of (one of %s); migrate derives the kinds it can"
              % (cid, ", ".join(KINDS)))
        return
    if not named:
        errors.append("claim %s cites no artifact: a proof has to name the run, "
                      "the note or the file it rests on" % cid)
        return
    if kind == "evidence":
        if not any(_resolves(token, (base,)) for token in named):
            # A repository file is not the run this claim rests on: what makes it
            # evidence is an artifact of the line itself.
            errors.append("claim %s is an evidence claim and cites nothing the "
                          "line produced: %s" % (cid, ", ".join(named)))
        for experiment in _experiments_named(tokens):
            path = os.path.join(base, "experiments", experiment, "results.jsonl")
            if not _rows(path):
                _soft(errors, warnings, strict,
                      "claim %s cites experiment %s, whose results.jsonl %s, so "
                      "the evidence claim is bound to a run that recorded nothing"
                      % (cid, experiment,
                         "is missing" if _rows(path) is None else "holds no row"))
    elif kind == "literature":
        # The notes are what makes it a literature claim; the other artifacts it
        # names - the code the paper motivates, the report that quotes it - are
        # checked by the resolution rule every claim is checked by, not by this
        # one. What is refused is a literature claim bound to no note, and a note
        # the line does not have.
        if not any(_under_literature(token, base) for token in tokens):
            errors.append("claim %s is a literature claim and cites no note under "
                          "literature/" % cid)
        for token in tokens:
            if token.startswith("literature/") and not _under_literature(token, base):
                errors.append("claim %s cites %s, which is not a note under "
                              "literature/" % (cid, token))
    elif kind == "derivation":
        for token in named:
            if not _resolves(token, (base,)):
                errors.append("claim %s is a derivation and cites %s, which the "
                              "line itself does not hold" % (cid, token))


def derive_kind(claim, roots):
    """The kind a claim's proof implies, or None when it implies none.

    `experiments/` names a run, so the claim is evidence; a note under
    `literature/` makes it literature; any other artifact of the repository makes
    it a code claim; a proof that names no artifact at all is the one case left,
    and it is reported rather than labelled - `derivation` would be a guess, and
    a guessed kind would only move the refusal one step later. The literature test
    is the same one the rule applies, so a derived kind can never be one the
    checker refuses - which a substring test got wrong on two claims this
    repository's own lines hold."""
    base = roots[0]
    tokens = _named(claim.get("proof"), roots)
    if not tokens:
        return None
    if any(t.startswith("experiments/") for t in tokens):
        return "evidence"
    if any(_under_literature(t, base) for t in tokens):
        return "literature"
    return "code"



def claim_problems(claim, base, repo, held=None):
    """The reasons this claim cannot be recorded, as a list of strings; [] when
    valid. Exactly the rules `check` applies to a row - a statement, a
    falsification criterion, a proof, a provenance in PROVENANCE, a status in
    STATUSES, every cited path resolving under the line or the repository, the
    kind's own proof rules, the `orx:<runId>` token, an `evidence` claim's
    line-local token, and a `supersedes` id the line actually holds - so the write
    path can never refuse a claim the checker would have accepted. Two are
    stricter: a new claim's `kind` (the checker only warns for a pre-rule row) and
    a proof that names no artifact at all.

    `held` is the id set to judge `supersedes` against, for a caller that already
    read them from the descriptor it holds the lock on (`append_claim`); None reads
    them here, which is what the checker and the prediction writer do."""
    # `check` names an id-less row by its line; a row about to be written has no
    # line yet, and numbering stays the writer's business.
    cid = claim.get("id") or "(no id)"
    problems = []
    if not str(claim.get("statement", "")).strip():
        problems.append("claim %s states nothing" % cid)
    if not str(claim.get("falsification", "")).strip():
        problems.append("claim %s carries no falsification criterion" % cid)
    if claim.get("kind") not in KINDS:
        problems.append("claim %s kind %r is not one of %s"
                        % (cid, claim.get("kind"), ", ".join(KINDS)))
    if not claim.get("proof"):
        problems.append("claim %s cites no evidence" % cid)
    else:
        tokens = _cited(claim["proof"])
        for token in tokens:
            if not _resolves(token, (base, repo)):
                problems.append("claim %s cites %s, which is not in this line"
                                % (cid, token))
        if claim.get("kind") == "evidence" and not any(
                _resolves(t, (base,)) for t in _named(claim["proof"], (base, repo))):
            problems.append("claim %s is an evidence claim and cites nothing the "
                            "line produced" % cid)
        # The evidence-row rule is not repeated here: an empty results.jsonl is
        # the class `check` warns about instead of refusing, because a claim is
        # often written before the run that answers it lands its rows. The write
        # path records the claim and `check` reports it (and `check --strict`
        # refuses it) - a writer that refused what the checker only warns about
        # would be the stricter of two judges that have to agree.
        if not _named(claim["proof"], (base, repo)):
            problems.append("claim %s cites no artifact: a proof has to name the "
                            "run, the note or the file it rests on" % cid)
        for run in ORX_RUN.findall(_proof_text(claim["proof"])):
            if run_log(base, repo, run, tokens) is None:
                problems.append("claim %s cites orx:%s, and no raw/%s.log is under "
                                "this line or the repository, so the receipt is "
                                "missing" % (cid, run, run))
    if claim.get("provenance") not in PROVENANCE:
        problems.append("claim %s provenance %r is not one of %s"
                        % (cid, claim.get("provenance"), ", ".join(PROVENANCE)))
    if claim.get("status") not in STATUSES:
        problems.append("claim %s status %r is not one of %s"
                        % (cid, claim.get("status"), ", ".join(STATUSES)))
    ids, problem = _supersedes(claim)
    if problem:
        problems.append("claim %s %s" % (cid, problem))
    else:
        known = _claim_ids(base) if held is None else held
        problems.extend("claim %s supersedes %s, and no claim in this line carries "
                        "that id" % (cid, ref) for ref in ids if ref not in known)
    # The scope rules the checker decides, so the write path cannot record a claim
    # `check` would refuse. The warn class (a claim over fixture rows that declares
    # nothing) is deliberately not repeated: a writer stricter than the checker
    # would refuse what `check` only reports, which is the disagreement the rest of
    # this function exists to avoid.
    declared = claim.get("scope")
    if declared is not None and declared not in SCOPES:
        problems.append("claim %s scope %r is not one of %s"
                        % (cid, declared, ", ".join(SCOPES)))
    elif declared == "real":
        scopes = _evidence_scopes(claim, base, repo)
        if scopes and all(s == "fixture" for s in scopes):
            problems.append("claim %s declares scope real and every row it rests on "
                            "records fixture" % cid)
    return problems


def _locked(handle, label="claims.jsonl"):
    """None once the exclusive lock on this descriptor is held, else the problem
    that refuses the append. A holder keeps the lock for one write, so a holder
    still there after LOCK_WAIT is stuck, and waiting past the bound would wedge
    the session that is recording its evidence behind it. `label` names the file
    in the refusal, because the same lock appends the prediction rows too."""
    if fcntl is None:
        return "%s cannot be locked on this platform" % label
    deadline = time.time() + LOCK_WAIT
    while True:
        try:
            fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
            return None
        except OSError:
            if time.time() >= deadline:
                return "%s is locked by another writer" % label
            time.sleep(LOCK_POLL)


def append_claim(repo, slug, claim):
    """(id, problems); problems is [] exactly when the claim was written.

    The lock is the claims.jsonl descriptor itself, so no sidecar lock file
    appears beside it: a reader lists that directory to find the line's files,
    and one extra name per line would be a false record there. It dies with the
    process, so a crash leaves nothing held.

    Where the harness ledger falls back to the unlocked write when its lock
    cannot be taken, this path refuses and names the reason: a ledger row is a
    trace and a lost one costs a line, while a claim is evidence, and evidence
    that raced - one of two claims lost silently, or a half-written line that
    does not parse - is worse than evidence that was refused.

    The lock is taken before the claim is judged, and the judgement reads the ids
    from the descriptor holding it: until this line's own report named the order,
    `claim_problems` ran first and read them by path, so another session could land
    the very id the check had just found absent and this path refused a claim the
    committed file accepts - the writer's proof describing an instant the append
    does not commit to.

    Raises FileNotFoundError when the line directory does not exist."""
    if not valid_slug(slug):
        # An invalid slug can still resolve to an existing directory: `..` is
        # the research root's parent, which is tezgah's own state dir.
        return claim.get("id"), ["not a research slug: %r" % slug]
    base = line_dir(repo, slug)
    if not os.path.isdir(base):
        raise FileNotFoundError(base)
    path = os.path.join(base, "claims.jsonl")
    # Whether this append is the one that creates the file: a claim refused under
    # the lock must not leave an empty claims.jsonl behind, because the line
    # decides when it has claims and an empty file answers a different question
    # ("no claims recorded yet") from an absent one ("claims.jsonl is missing").
    created = not os.path.isfile(path)
    # Binary, so the committed-size repair below reads and writes bytes.
    with open(path, "a+b") as handle:
        problem = _locked(handle)
        if problem:
            return claim.get("id"), [problem]
        # The judgement runs under the lock and reads the ids from the descriptor
        # holding it (`_claim_ids`): the ids a claim is judged against are the ids
        # the append commits beside.
        problems = claim_problems(claim, base, repo, held=_claim_ids(base, handle))
        if problems:
            if created and os.path.getsize(path) == 0:
                os.remove(path)
            return claim.get("id"), problems
        # An append starts at the last committed newline: a fragment a killed
        # writer left behind is not a row, and appending after it would turn it
        # into one that never parses (`truncate_to_committed`).
        truncate_to_committed(handle)
        handle.write(json.dumps(claim).encode("utf-8") + b"\n")
    return claim.get("id"), []


def _check_experiments(repo, base, errors, warnings, git, strict):
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
        _check_protocol(h, proto, errors, warnings, strict)
        if not os.path.isfile(results):
            continue
        if not os.path.isfile(os.path.join(d, "analysis.md")):
            errors.append("experiment %s has results but no analysis.md" % h)
        _check_rows(results, "experiment %s" % h, errors, warnings, strict)
        if git:
            _check_protocol_order(repo, h, proto, results, errors, warnings)
    return out


def _protocol_answers(text):
    """(prediction, falsifier): True when the file answers each question.

    Over the whole file and not line by line: a protocol wraps a sentence over as
    many lines as it likes, and E4 of this repository's audit line keeps its
    predictions on the continuation lines of its locked evaluation, so a checker
    reading line by line was about to report a file that predicts nothing. The
    denying phrases are cut out first, because the disclaimer "this file is the
    brief, not a prediction" is the opposite of an answer and is what a checker
    reading the word alone would count; see the markers above."""
    body = PROTOCOL_DENIAL.sub(" ", " ".join(text.split()))
    return (bool(PROTOCOL_PREDICTION.search(body)),
            bool(PROTOCOL_FALSIFIER.search(body)))


def _check_protocol(h, path, errors, warnings, strict):
    """A protocol answers what it predicts and what would falsify it.

    `check` reads the file, so it can ask whether both questions are answered at
    all, not whether the answers are right - and that is the difference the layer
    was missing: its own audit measured a protocol whose whole body was "run it"
    passing every check (P2), because existence and commit order were the only
    things read. The class is the warn one, and the reason is in the tree: three
    of this repository's protocols are work orders handed to a read-only agent and
    answer neither question by design, so a refusal would make the honest shape
    the refused one. `--strict` refuses what it cannot see answered, which is what
    a line that wants its predictions provable asks for."""
    try:
        with open(path, encoding="utf-8") as fh:
            text = fh.read()
    except (OSError, UnicodeDecodeError) as exc:
        errors.append("experiment %s: protocol.md cannot be read (%s)" % (h, exc))
        return
    prediction, falsifier = _protocol_answers(text)
    if not prediction:
        _soft(errors, warnings, strict,
              "experiment %s: protocol.md states no prediction, so nothing in it "
              "says what the run was meant to show; a protocol that is a brief "
              "rather than a prediction reads this way" % h)
    if not falsifier:
        _soft(errors, warnings, strict,
              "experiment %s: protocol.md states no falsification criterion, so no "
              "result could tell its reading wrong" % h)


def _check_tracking(repo, base, errors, warnings, strict):
    """The order rule needs a commit, so the check asks about the paths it orders.

    A directory-level ignore says nothing about the files inside it. This
    repository's own `.gitignore` re-includes every `protocol.md` and
    `analysis.md` while leaving each `results.jsonl` to the session that runs the
    experiment, and probing the line's directory - or its `state.json`, which the
    old probe fell back to - reported a line whose pair is fully committable as
    unverifiable. What is probed instead is the two files the rule compares.

    `_ignored` is the plain question *can `git add` stage this?*: `check-ignore`
    does not report a path the index already holds (measured on a scratch repo),
    so an ignored-but-committed `results.jsonl` is not reported and neither is the
    line that holds it. The message carries the command that fixes the pair that
    is reported, because `git add <results.jsonl>` stages nothing while the path
    is ignored and a silent no-op looks exactly like a commit: the protocol goes
    in normally - that commit is the prediction - the results are added by
    explicit path afterwards, and the order is then decidable."""
    experiments = os.path.join(base, "experiments")
    try:
        names = sorted(os.listdir(experiments))
    except OSError:
        return
    for h in names:
        d = os.path.join(experiments, h)
        if not os.path.isdir(d) or h.startswith("."):
            continue
        for name in ("protocol.md", "results.jsonl"):
            path = os.path.join(d, name)
            if not os.path.isfile(path):
                continue
            pattern = _ignored(repo, path)
            if not pattern:
                continue
            _soft(errors, warnings, strict,
                  "experiment %s: %s is ignored by %s, so no commit a tracked tree "
                  "holds can show the protocol predates the results; commit the "
                  "protocol normally, then `git add -f %s`"
                  % (h, name, pattern, os.path.relpath(path, repo)))


def _check_rows(path, label, errors, warnings, strict):
    """One JSON object per non-blank line, each saying where it came from.

    A results file is the layer's primary artifact, so a row that does not parse
    is refused: a file whose line three is prose is a file no reader can load, and
    every count taken from it afterwards is wrong. A row that carries `source`
    `source` empty is refused too - it claims a provenance and does not give one. A
    row with no `source` key at all is the pre-migration class: it is what the rows
    written before this rule look like, and inventing a source for someone else's
    measurement would be the fabrication the rule exists to catch, so it warns and
    `--strict` refuses it.

    `scope` is the second half of the same question and is checked the same way: a
    row may say `real`, `fixture` or `derived`, an off-vocabulary value is refused,
    and a file whose rows declare no scope warns with the count - the field cannot
    be inferred afterwards, so a missing one is a reader's problem, not a rule's
    guess.

    `fixture` is the third: a row that says its numbers came from a generated input
    names that input, because a class a reader cannot size is the reason the field
    beside it exists. A fixture row carrying no description warns with the count -
    the rows written before this rule are in it - and `--strict` refuses it; a
    description that is present and empty, or not a string, is refused outright,
    since it claims the field and names nothing."""
    text, exc = _committed_text(path)
    if exc:
        errors.append("%s: results.jsonl cannot be read (%s)" % (label, exc))
        return 0
    # The committed boundary: a fragment a killed writer left behind is not a row,
    # and reporting it as one refused the file for good (`_committed_text`).
    lines = text.splitlines()
    rows = 0
    unscoped = 0
    unnamed = 0
    for n, raw in enumerate(lines, 1):
        if not raw.strip():
            continue
        rows += 1
        try:
            row = json.loads(raw)
        except ValueError as exc:
            errors.append("%s: results.jsonl:%d does not parse (%s)"
                          % (label, n, exc))
            continue
        if not isinstance(row, dict):
            errors.append("%s: results.jsonl:%d is a %s, not the object a row is"
                          % (label, n, type(row).__name__))
            continue
        if "source" not in row:
            _soft(errors, warnings, strict,
                  "%s: results.jsonl:%d carries no source, so this row cannot be "
                  "traced back to the run that produced it" % (label, n))
        elif not isinstance(row["source"], str) or not row["source"].strip():
            errors.append("%s: results.jsonl:%d carries an empty source"
                          % (label, n))
        # The other half of the same question: `source` says where the row came
        # from, `scope` says what its numbers are about. A row that declares
        # neither is the pre-rule class and warns; a row that declares a scope
        # outside the vocabulary is refused, because a label nothing shares is a
        # label no reader can weigh.
        scope = row.get("scope")
        if scope is None:
            unscoped += 1
        elif not isinstance(scope, str) or not scope.strip():
            errors.append("%s: results.jsonl:%d carries an empty scope" % (label, n))
        elif scope not in SCOPES:
            errors.append("%s: results.jsonl:%d scope %r is not one of %s"
                          % (label, n, scope, ", ".join(SCOPES)))
        # `scope: fixture` says the input was generated; `fixture` says what was,
        # because a class a reader cannot size is what the field beside it is for.
        # A row written before this rule carries none and warns, the way an
        # unscoped row does; one that carries the key and no description is
        # refused, because it answers the question and names nothing.
        if scope == "fixture":
            described = row.get("fixture")
            if described is None:
                unnamed += 1
            elif not isinstance(described, str):
                errors.append("%s: results.jsonl:%d carries a fixture description "
                              "that is a %s, not the text naming what was generated"
                              % (label, n, type(described).__name__))
            elif not described.strip():
                errors.append("%s: results.jsonl:%d carries an empty fixture "
                              "description" % (label, n))
    if unscoped:
        _soft(errors, warnings, strict,
              "%s: results.jsonl: %d of %d rows declare no scope, so nothing says "
              "what their numbers were measured on - a generated repository and the "
              "running system read the same once the run is over"
              % (label, unscoped, rows))
    if unnamed:
        _soft(errors, warnings, strict,
              "%s: results.jsonl: %d of %d rows declare scope fixture and do not say "
              "what was generated, so the input behind their numbers cannot be "
              "weighed or recreated" % (label, unnamed, rows))
    return rows


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


def _check_literature(base, errors, warnings, strict):
    """What the line read, and what it did with it.

    One index row per note, and one note per index row: the index is the only
    place a reader can see which sources were screened and which were left out,
    so a note nothing names and a row naming no file are both refused. `class`
    separates the paper record from the practice channel, and is refused when it
    says something else - the distinction is what tells a reader how much weight
    the source carries. A grey source with no `quality` judgement warns rather
    than fails, and so does a source recorded as verified by fewer than two
    records: both are the honest state of a note just saved, and the citation
    rule in the skill is three lines long. A field the note does not carry -
    `id`, `source`, `inclusion` - is reported once per index rather than
    invented, which is also what `migrate` says about it."""
    literature = os.path.join(base, "literature")
    try:
        notes = sorted(n for n in os.listdir(literature)
                       if n.endswith(".md")
                       and os.path.isfile(os.path.join(literature, n)))
    except OSError:
        return
    index = os.path.join(literature, "INDEX.jsonl")
    if not os.path.isfile(index):
        if notes:
            errors.append("literature/ holds %d note(s) and no INDEX.jsonl, so "
                          "nothing says which sources were screened, included or "
                          "left out; migrate writes what the notes already carry"
                          % len(notes))
        return
    rows, named = _read_index(index, literature, errors, warnings, strict)
    for note in notes:
        if note not in named:
            errors.append("literature/%s is not in INDEX.jsonl: a note the index "
                          "does not name is a source no reader can weigh" % note)
    _index_fields(rows, errors, warnings, strict)


def _read_index(index, literature, errors, warnings, strict):
    """(rows, names): the index's rows as objects, and the notes they name. Read
    to the committed boundary like every other JSONL reader here, so a fragment is
    not reported as a row; a line the file did terminate is still refused."""
    text, exc = _committed_text(index)
    if exc:
        errors.append("literature/INDEX.jsonl cannot be read (%s)" % exc)
        return [], set()
    lines = text.splitlines()
    rows, named = [], set()
    for n, raw in enumerate(lines, 1):
        if not raw.strip():
            continue
        try:
            row = json.loads(raw)
        except ValueError as exc:
            errors.append("literature/INDEX.jsonl:%d does not parse (%s)" % (n, exc))
            continue
        if not isinstance(row, dict):
            errors.append("literature/INDEX.jsonl:%d is a %s, not the object a row "
                          "is" % (n, type(row).__name__))
            continue
        rows.append(row)
        note = str(row.get("note", "")).strip()
        if not note:
            errors.append("literature/INDEX.jsonl:%d names no note" % n)
            continue
        named.add(note)
        if not os.path.isfile(os.path.join(literature, note)) or ".." in note:
            errors.append("literature/INDEX.jsonl:%d names %s, which literature/ "
                          "does not hold" % (n, note))
        if row.get("class") not in SOURCE_CLASSES:
            errors.append("literature/INDEX.jsonl:%d class %r is not one of %s"
                          % (n, row.get("class"), ", ".join(SOURCE_CLASSES)))
    return rows, named


def _index_fields(rows, errors, warnings, strict):
    """The index entries the rules read: a grey source's quality, a verification
    against two records, and the three fields a note has to carry."""
    total = len(rows)
    if not total:
        return
    grey = [r for r in rows if r.get("class") == "grey"
            and not str(r.get("quality", "")).strip()]
    if grey:
        _soft(errors, warnings, strict,
              "literature/INDEX.jsonl: %d of %d rows are a grey source with no "
              "quality note, so nothing says how good the practice evidence is"
              % (len(grey), total))
    verified = [r for r in rows
                if not isinstance(r.get("verified"), list) or len(r["verified"]) < 2]
    if verified:
        _soft(errors, warnings, strict,
              "literature/INDEX.jsonl: %d of %d rows are verified by fewer than "
              "two sources, so the citation is not checked the way the skill asks"
              % (len(verified), total))
    for field in ("id", "source", "inclusion"):
        missing = [r for r in rows if not str(r.get(field, "")).strip()]
        if missing:
            _soft(errors, warnings, strict,
                  "literature/INDEX.jsonl: %d of %d rows record no %s"
                  % (len(missing), total, field))


def _check_review(base, phase, errors, warnings, strict):
    """The review a claim passes before it is reported, as an artifact.

    The skill asks for six scored dimensions and findings that quote their
    evidence verbatim; the review is what decides whether a claim leaves the
    session, so it is written down where the next reader can check it rather than
    held in the session that produced it. A score missing from the six, or a
    number outside 1-5, is refused - two reviews only compare if they answer the
    same six questions on the same scale - and so is a finding whose `quote` is
    not in the file it targets, because that is the one defect a reader can never
    detect without the artifact in hand. A concluded line with no review at all
    warns, and `--strict` refuses it: the four lines that concluded before this
    rule existed have none, and a review is a judgement, so no migration can
    write one for them."""
    path = os.path.join(base, "to_human", "review.json")
    if not os.path.isfile(path):
        if phase == "concluded":
            _soft(errors, warnings, strict,
                  "to_human/review.json is missing: a concluded line reports the "
                  "six-dimension review of its claims, and no migration can write "
                  "a review for it")
        return
    review, exc = _read_json(path)
    if exc or not isinstance(review, dict):
        errors.append("to_human/review.json does not parse (%s)"
                      % (exc or "not an object"))
        return
    dimensions = review.get("dimensions")
    if not isinstance(dimensions, dict):
        errors.append("to_human/review.json carries no dimensions object")
    else:
        for name in REVIEW_DIMENSIONS:
            score = dimensions.get(name)
            if not isinstance(score, int) or isinstance(score, bool) \
                    or not 1 <= score <= 5:
                errors.append("to_human/review.json dimension %s is %r, not a score "
                              "from 1 to 5" % (name, score))
    findings = review.get("findings")
    if not isinstance(findings, list):
        errors.append("to_human/review.json carries no findings list")
        return
    for n, finding in enumerate(findings, 1):
        if not isinstance(finding, dict):
            errors.append("to_human/review.json finding %d is a %s, not an object"
                          % (n, type(finding).__name__))
            continue
        if finding.get("severity") not in SEVERITIES:
            errors.append("to_human/review.json finding %d severity %r is not one "
                          "of %s" % (n, finding.get("severity"),
                                     ", ".join(SEVERITIES)))
        target = str(finding.get("target", "")).strip()
        if not target:
            errors.append("to_human/review.json finding %d targets no file" % n)
            continue
        quote = finding.get("quote")
        if not isinstance(quote, str) or not quote.strip():
            errors.append("to_human/review.json finding %d quotes nothing, and a "
                          "finding that cannot quote its evidence is not a finding"
                          % n)
            continue
        _check_quote(base, n, target, quote, errors)


def _check_quote(base, n, target, quote, errors):
    """A finding's quote has to be in the file it targets, verbatim."""
    try:
        with open(os.path.join(base, target), encoding="utf-8") as fh:
            text = fh.read()
    except (OSError, UnicodeDecodeError) as exc:
        errors.append("to_human/review.json finding %d targets %s, which cannot be "
                      "read (%s)" % (n, target, exc))
        return
    if quote not in text:
        errors.append("to_human/review.json finding %d quotes %r, which %s does not "
                      "contain verbatim" % (n, quote[:60], target))


def _check_report(repo, base, phase, errors, warnings, strict):
    """A concluded line's report states what the evidence does not show.

    The report is what the reader takes away, and the one thing a line cannot
    repair afterwards is that it never said where its evidence stopped: a number
    reported without its bound travels as a stronger one than it is, which is the
    same failure the skill's "state plainly what the evidence does not show" was
    written against. What is read is the report's own text, so a heading and a
    prose sentence count alike. The class is the warn one: the five reports this
    repository already concluded with predate the rule, and a report written
    mid-flight is incomplete rather than wrong - `--strict` is what refuses it.

    A concluded line with no report at all warns with exactly that reason: there
    is no report in which to state the limits, so the file the rule reads does not
    exist yet."""
    if phase != "concluded":
        return
    path = os.path.join(base, "to_human", "report.md")
    if not os.path.isfile(path):
        _soft(errors, warnings, strict,
              "to_human/report.md is missing: a concluded line states in it what "
              "the evidence does not show, and there is no report in which to "
              "state it")
        return
    try:
        with open(path, encoding="utf-8") as fh:
            text = fh.read()
    except (OSError, UnicodeDecodeError) as exc:
        errors.append("to_human/report.md cannot be read (%s)" % exc)
        return
    if not REPORT_LIMITS.search(text):
        _soft(errors, warnings, strict,
              "to_human/report.md states nowhere what the evidence does not show, "
              "so its findings travel without the bound they were measured under")
    fixtures = _fixture_claims(base, repo)
    if fixtures and "fixture" not in text.lower():
        _soft(errors, warnings, strict,
              "to_human/report.md carries %d claim(s) resting on a fixture input (%s) "
              "and never says so, so a reader of the report alone takes a generated "
              "input for the running system"
              % (len(fixtures), ", ".join(fixtures[:4])))


def check_line(repo, slug, git=True, strict=False):
    """(errors, warnings) for one research line. `git=False` skips the checks that
    need git history, for callers that must stay cheap (the session context).
    `strict=True` turns every guarantee the checker cannot decide into an error."""
    base = line_dir(repo, slug)
    errors, warnings = [], []
    if not os.path.isdir(base):
        return ["%s does not exist" % base], warnings
    for name in STATE_FILES:
        if not os.path.isfile(os.path.join(base, name)):
            errors.append("%s is missing" % name)
    _check_state(base, errors, warnings, strict)
    _check_findings(base, errors, warnings, strict)
    _check_claims(base, errors, warnings, roots=(repo,), strict=strict)
    _check_predictions(repo, base, errors, warnings, strict, git)
    _check_experiments(repo, base, errors, warnings, git, strict)
    _check_literature(base, errors, warnings, strict)
    phase = _phase(base)
    _check_review(base, phase, errors, warnings, strict)
    _check_report(repo, base, phase, errors, warnings, strict)
    if git:
        _check_tracking(repo, base, errors, warnings, strict)
    return errors, warnings


def _phase(base):
    """The line's phase, or None when state.json is missing or unreadable."""
    state, exc = _read_json(os.path.join(base, "state.json"))
    return state.get("phase") if isinstance(state, dict) and not exc else None


# What each phase means, read from the artifacts rather than from the field: the
# question alone is `bootstrap`; something has been run - an experiment with a
# committed protocol and a results row, or a claim recorded - is `inner`; the
# results folded back into `findings.md` is `outer`; the two artifacts a concluded
# line owes, `to_human/report.md` and `to_human/review.json`, are `concluded`.
# Each rung is one artifact the line already holds, and the ladder is read in this
# order, so the furthest rung that holds is the answer. It is deliberately not a
# rule about the *stored* field's value: `phase` stays the author's declared
# intent, and a line whose field is ahead of its artifacts is judged by the field.
def _findings_written(base):
    """True when `findings.md` answers one of its four sections with content: the
    synthesis the outer loop produces, which is what separates a line that has
    folded its results back from one still running experiments."""
    text = _note_text(os.path.join(base, "findings.md"))
    return any(any(line.strip() for line in _section(text, name))
               for name in FINDINGS_SECTIONS)


def _measured(base):
    """True when something has been run: an experiment holding a protocol and at
    least one committed results row, or a claim recorded in `claims.jsonl`. Both
    are read at the committed boundary (`_rows`, `_committed_text`), so a fragment
    a killed writer left behind is not a measurement."""
    exps = os.path.join(base, "experiments")
    try:
        names = sorted(os.listdir(exps))
    except OSError:
        names = []
    for h in names:
        d = os.path.join(exps, h)
        if not os.path.isdir(d) or h.startswith("."):
            continue
        if os.path.isfile(os.path.join(d, "protocol.md")) \
                and _rows(os.path.join(d, "results.jsonl")):
            return True
    text, _exc = _committed_text(os.path.join(base, "claims.jsonl"))
    return bool(text and text.strip())


def derived_phase(base):
    """The phase this line's own artifacts support, in `PHASES` vocabulary.

    The other authority beside `state.json`'s `phase`: that field is what the
    author declares and nothing here rewrites it, while this walks the artifacts
    the line already holds and reports how far they have actually carried it. A
    line whose protocols, results, claims, findings, report and review are all
    written but whose `phase` still says `inner` is the "two authorities" defect
    this module names in its own source: a field maintained by hand beside
    artifacts that are not, disagreeing with no reader to say so.

    `bootstrap` when nothing has been run yet - the question is all the line has -
    and the furthest rung that holds otherwise (`_measured`, `_findings_written`,
    then the two artifacts a concluded line owes). What each rung *is* is not
    decided here: whether a protocol answers its two questions, or a review
    carries six scored dimensions, is `_check_protocol`, `_check_review` and
    `_check_report`'s business, and this function only says how far the line got."""
    if os.path.isfile(os.path.join(base, "to_human", "report.md")) \
            and os.path.isfile(os.path.join(base, "to_human", "review.json")):
        return "concluded"
    if _findings_written(base):
        return "outer"
    if _measured(base):
        return "inner"
    return "bootstrap"


def _check_derived_phase(base, phase, warnings):
    """A stored phase behind the one the line's artifacts show, as a warning.

    The warn class, and never an error even under `--strict`: the stored field is
    the author's declared intent, and a derivation simpler than that judgement
    must not fail a line the field says is fine (`_open_reasons` is what reads the
    field when a caller has to decide whether a line is finished). What it does
    say is when the field stopped describing the line - the class this line's own
    source named as two authorities - so the next session reads where the work
    actually is instead of trusting a field nobody updated."""
    derived = derived_phase(base)
    if phase in PHASES and PHASES.index(derived) > PHASES.index(phase):
        warnings.append("state.json phase %s is behind the phase the line's "
                        "artifacts show (%s), so the declared phase stopped "
                        "describing the line" % (phase, derived))


def check(repo, slug=None, git=True, strict=False):
    """{slug: {"errors": [...], "warnings": [...]}} for one line or every line."""
    out = {}
    for name in ([slug] if slug else slugs(repo)):
        errors, warnings = check_line(repo, name, git=git, strict=strict)
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


def _open_reasons(base):
    """The reasons one line is unfinished; [] when every artifact says it is done.

    Read from the line's own files and nothing else, so a line a crash left half
    written reads as unfinished rather than as an error the caller has to catch: a
    state.json that cannot be read is itself the first reason, and the rest of the
    line is still read, because a session that has to repair one reason should be
    able to see the others in the same pass. An experiment weighs only once it has
    a protocol: one with no plan is not yet a run anyone owes.

    A row another row supersedes is not a live proposal any more, and its own
    status is not the one that decides: it is read through the row that replaced
    it, because `supersedes` is the relation that says which decision stands and
    the file is append-only, so the older row's `hypothesis` is the state it was
    left in rather than the state the line is in. Only the newest row of a chain
    decides, and a superseded row is skipped rather than rewritten - the record of
    what the line first proposed is the thing `supersedes` exists to keep."""
    reasons = []
    state, exc = _read_json(os.path.join(base, "state.json"))
    if exc or not isinstance(state, dict):
        reasons.append("phase unreadable")
    elif state.get("phase") != "concluded":
        reasons.append("phase %s" % (state.get("phase") or "unset"))
    rows = _row_objects(os.path.join(base, "claims.jsonl"))
    replaced = set()
    for claim in rows:
        ids, _ = _supersedes(claim)
        replaced.update(ids)
    for n, claim in enumerate(rows, 1):
        if claim.get("id") in replaced:
            continue
        if claim.get("status") in LIVE_STATUSES:
            reasons.append("claim %s is %s" % (claim.get("id") or n,
                                               claim["status"]))
    exps = os.path.join(base, "experiments")
    try:
        names = sorted(os.listdir(exps))
    except OSError:
        names = []
    for h in names:
        d = os.path.join(exps, h)
        if not os.path.isdir(d) or h.startswith("."):
            continue
        if not os.path.isfile(os.path.join(d, "protocol.md")):
            continue
        if not _rows(os.path.join(d, "results.jsonl")):
            reasons.append("experiments/%s has a protocol and no results" % h)
        elif not os.path.isfile(os.path.join(d, "analysis.md")):
            reasons.append("experiments/%s has results and no analysis.md" % h)
    if not os.path.isfile(os.path.join(base, "to_human", "report.md")):
        reasons.append("to_human/report.md is missing")
    review_path = os.path.join(base, "to_human", "review.json")
    if not os.path.isfile(review_path):
        reasons.append("to_human/review.json is missing")
    else:
        review, exc = _read_json(review_path)
        if exc or not isinstance(review, dict):
            reasons.append("to_human/review.json unreadable")
        else:
            findings = review.get("findings")
            if not isinstance(findings, list):
                reasons.append("to_human/review.json carries no findings list")
            else:
                for n, finding in enumerate(findings, 1):
                    if not isinstance(finding, dict) \
                            or not str(finding.get("status") or "").strip():
                        reasons.append("to_human/review.json finding %d carries "
                                       "no status" % n)
    return reasons


def open_lines(repo):
    """[(slug, [reason, ...])] for every line that is not finished, for `init`.

    A line is open until every one of its own artifacts says it is done: the phase
    is `concluded`, no claim is left a live proposal - a row a later row supersedes
    is read through the row that replaced it, never by its own stale status - every
    pre-registered experiment has its results and its analysis, `to_human/report.md`
    and `review.json` are written, and every finding in the review carries a status.
    This is the state `init` refuses over, and the reason the rule exists: on
    2026-09-22 this repository held thirteen lines, eleven of them carrying
    unfinished work, and nothing read the others before the next one was
    scaffolded."""
    out = []
    for slug in slugs(repo):
        reasons = _open_reasons(line_dir(repo, slug))
        if reasons:
            out.append((slug, reasons))
    return out


def open_note(repo):
    """The one line naming the unfinished lines, or "" when none is - for `check`
    and for `summary`, so a session meets the same list on both surfaces and does
    not have to be refused by `init` to learn it owes work. The reasons travel with
    the slugs: a slug alone sends the reader back to the line's files."""
    rows = open_lines(repo)
    if not rows:
        return ""
    return "open: " + "; ".join("%s (%s)" % (slug, "; ".join(reasons))
                                for slug, reasons in rows)


def summary(repo):
    """One line per research line, for `status`; `failing()` is what the note reads.

    A line whose claims rest on a generated input says so here rather than only in
    the line's own report: the status line is what a session and a reader see
    without opening anything, and a count of what a line's numbers are about is the
    one thing its name cannot carry. The last line names the lines that are still
    open (`open_note`), because they are what `init` refuses a new line over, and a
    session that only meets them at its next `init` met them too late."""
    out = []
    for slug in slugs(repo):
        report = check(repo, slug=slug)
        errors = report[slug]["errors"]
        note = "ok" if not errors else "%d problem(s)" % len(errors)
        fixtures = _fixture_claims(line_dir(repo, slug), repo)
        if fixtures:
            note += ", %d fixture-scoped claim(s): %s" % (len(fixtures), ", ".join(fixtures))
        out.append("%s: %s" % (slug, note))
    unfinished = open_note(repo)
    if unfinished:
        out.append(unfinished)
    return out


def check_orx(repo, orx, strict=False):
    """{"errors": [...], "warnings": [...]} for the orx project registered against
    this repository.

    The run command a project was registered with is a fixed contract - orx
    compares runs across nodes on the strength of it - so a command naming a path
    the working tree no longer holds means the project's runs cannot be
    reproduced from HEAD, and the numbers in its experiment tree have no
    reachable recipe. `orx project view` prints the command; the path-shaped
    words in it are checked against the tree. Without orx, or with no project
    registered for this repository, the answer is a note and never an error: the
    check is an addition to `check`, and neither absence is a defect of the
    line."""
    if not orx or not os.path.exists(orx):
        return {"errors": [], "warnings":
                ["orx is not installed, so the run command registered against this "
                 "repository was not read (TEZGAH_ORX_BIN overrides the lookup)"]}
    out, err = _run([orx, "projects", "--json"], cwd=repo)
    if err:
        return {"errors": [], "warnings": ["orx projects could not be read (%s)" % err]}
    try:
        rows = json.loads(out or "[]")
    except ValueError as exc:
        return {"errors": [], "warnings":
                ["orx projects did not answer with JSON (%s)" % exc]}
    mine = [r for r in rows if isinstance(r, dict)
            and os.path.realpath(str(r.get("path", ""))) == os.path.realpath(repo)]
    if not mine:
        return {"errors": [], "warnings":
                ["no orx project is registered against %s" % repo]}
    errors, warnings = [], []
    for row in mine:
        name = row.get("name") or row.get("id") or "?"
        view, verr = _run([orx, "project", "view", str(row.get("id", ""))], cwd=repo)
        if verr:
            warnings.append("orx project %s could not be read (%s)" % (name, verr))
            continue
        command = ""
        for line in view.splitlines():
            if line.strip().startswith("command:"):
                command = line.split(":", 1)[1].strip()
                break
        if not command:
            warnings.append("orx project %s records no run command" % name)
            continue
        for token in _command_paths(command):
            if os.path.exists(os.path.join(repo, token)):
                continue
            _soft(errors, warnings, strict,
                  "orx project %s: the run command names %s, which this tree does "
                  "not hold, so its runs cannot be reproduced from HEAD"
                  % (name, token))
    return {"errors": errors, "warnings": warnings}


def _command_paths(command):
    """The path-shaped words of a shell command: the ones with a slash in them or
    a filename extension, which are the ones a tree has to hold."""
    out = []
    for word in command.split():
        word = word.strip("'\"")
        if not word or word.startswith("-"):
            continue
        if "/" in word or re.search(r"\.\w{1,4}$", word):
            out.append(word)
    return out


def migrate(repo, slug, dry_run=False):
    """(lines, problems): derive the fields the rules came to require, or say why
    they cannot be derived.

    Three derivations and nothing else: each claim's `kind` from the artifacts its
    proof names, each results row's `source` from the fields the row already
    carries, and the `literature/INDEX.jsonl` rows from the notes already saved.
    All three read what the artifacts hold rather than guessing at it, all three
    are idempotent - a second run finds nothing to change - and both JSONL files
    are rewritten under the same exclusive lock the appends take, so a session
    recording a claim or a run while this runs cannot lose it.

    Every field it cannot derive is reported instead of invented: the proof that
    names no artifact, the row that carries none of `run`, `id`, `raw` or `log`,
    the note with no id line, the verification nobody recorded, the inclusion
    decision only a reader can make. Inventing those is the failure the rules
    exist to prevent - a migrated artifact that claims evidence nobody checked is
    worse than one that admits it has none."""
    base = line_dir(repo, slug)
    if not os.path.isdir(base):
        return [], ["%s does not exist" % base]
    problems = []
    lines = _migrate_claims(base, repo, dry_run, problems)
    lines += _migrate_rows(base, dry_run, problems)
    lines += _migrate_index(base, dry_run, problems)
    return lines, problems


def _row_source(row):
    """(source, field): the source a results row's own fields imply, or (None,
    None) when it carries none of them.

    A row written before the rule says where it came from in a field of its own: a
    `log` or `raw` path is the receipt itself and is taken as written, and a `run`
    or `id` is the run the row came out of and is prefixed with the field it came
    from, so a reader can tell a run id from a row id. `ROW_SOURCE_FIELDS` is the
    order they are read in, so the receipt wins over the id beside it."""
    for field in ROW_SOURCE_FIELDS:
        value = row.get(field)
        if isinstance(value, bool) or not isinstance(value, (str, int)):
            continue
        text = str(value).strip()
        if not text:
            continue
        return (text if field in ("log", "raw") else "%s %s" % (field, text)), field
    return None, None


def _migrate_rows(base, dry_run, problems):
    """The `source` a results row can be given from what the row already holds.

    The rule is that a row says where it came from, and the rows written before it
    recorded that in `run`, `id`, `raw` or `log` - so the derivation reads those
    and rewrites the row with the source they imply. A row with none of the four
    is reported and left alone: a source invented for someone else's measurement
    is the fabrication the rule exists to catch. The file is rewritten under the
    same lock `_append_row` takes, with the same O_APPEND truncation trick the
    claim rewrite uses."""
    experiments = os.path.join(base, "experiments")
    try:
        names = sorted(os.listdir(experiments))
    except OSError:
        return []
    lines = []
    for h in names:
        d = os.path.join(experiments, h)
        path = os.path.join(d, "results.jsonl")
        if not os.path.isdir(d) or not os.path.isfile(path):
            continue
        with open(path, "a+b") as handle:
            problem = _locked(handle)
            if problem:
                problems.append("%s, so experiment %s's rows keep no source"
                                % (problem, h))
                continue
            handle.seek(0)
            body = handle.read().decode("utf-8", "replace").splitlines()
            out, changed = [], 0
            for n, raw in enumerate(body, 1):
                if not raw.strip():
                    continue
                try:
                    row = json.loads(raw)
                except ValueError:
                    problems.append("experiment %s: results.jsonl:%d does not parse, "
                                    "so its source stays underivable" % (h, n))
                    out.append(raw)
                    continue
                if not isinstance(row, dict) or "source" in row:
                    out.append(raw)
                    continue
                source, field = _row_source(row)
                if source is None:
                    problems.append("experiment %s: results.jsonl:%d: no source "
                                    "derived - the row carries none of %s"
                                    % (h, n, ", ".join(ROW_SOURCE_FIELDS)))
                    out.append(raw)
                    continue
                changed += 1
                lines.append("experiment %s: results.jsonl:%d source %s (from %s)"
                             % (h, n, source, field))
                updated = dict(row)
                updated["source"] = source
                out.append(json.dumps(updated))
            if changed and not dry_run:
                handle.seek(0)
                handle.truncate()
                handle.write("".join(line + "\n" for line in out).encode("utf-8"))
    return lines


def _migrate_claims(base, repo, dry_run, problems):
    path = os.path.join(base, "claims.jsonl")
    out, lines, changed = [], [], 0
    with open(path, "a+b") as handle:
        problem = _locked(handle)
        if problem:
            problems.append("%s, so the kinds were not derived" % problem)
            return lines
        handle.seek(0)
        rows = handle.read().decode("utf-8", "replace").splitlines()
        for n, raw in enumerate(rows, 1):
            if not raw.strip():
                continue
            try:
                claim = json.loads(raw)
            except ValueError:
                problems.append("claims.jsonl:%d does not parse, so its kind stays "
                                "underivable" % n)
                out.append(raw)
                continue
            label = claim.get("id") or "line %d" % n
            if claim.get("kind") in KINDS:
                out.append(raw)
                continue
            kind = derive_kind(claim, (base, repo))
            if kind is None:
                problems.append("claim %s: no kind derived - its proof names no "
                                "artifact to be a proof of" % label)
                out.append(raw)
                continue
            changed += 1
            lines.append("claim %s: kind %s" % (label, kind))
            updated = dict(claim)
            updated["kind"] = kind
            out.append(json.dumps(updated))
        if changed and not dry_run:
            # O_APPEND sends every write to the end of the file, so the truncation
            # is what puts the rewritten rows back at the start of it.
            handle.seek(0)
            handle.truncate()
            handle.write("".join(line + "\n" for line in out).encode("utf-8"))
    return lines


def _migrate_index(base, dry_run, problems):
    literature = os.path.join(base, "literature")
    try:
        notes = sorted(n for n in os.listdir(literature)
                       if n.endswith(".md")
                       and os.path.isfile(os.path.join(literature, n)))
    except OSError:
        return []
    if not notes:
        return []
    path = os.path.join(literature, "INDEX.jsonl")
    rows = []
    if os.path.isfile(path):
        text, exc = _committed_text(path)
        if exc:
            problems.append("literature/INDEX.jsonl cannot be read (%s), so the "
                            "notes it names cannot be read" % exc)
            return []
        for raw in text.splitlines():
            if raw.strip():
                try:
                    rows.append(json.loads(raw))
                except ValueError:
                    problems.append("literature/INDEX.jsonl does not parse, so "
                                    "the notes it names cannot be read")
                    return []
    named = {str(r.get("note", "")) for r in rows if isinstance(r, dict)}
    lines, added = [], []
    for note in notes:
        if note in named:
            continue
        text = _note_text(os.path.join(literature, note))
        row = {"note": note}
        identifier = _note_line(text, "id")
        source = _note_source(text)
        if identifier:
            row["id"] = identifier
        else:
            problems.append("literature/%s: no id derived - the note has no id line"
                            % note)
        if source:
            row["source"] = source
        else:
            problems.append("literature/%s: no source derived - the note names no "
                            "url or source line" % note)
        row["class"] = source_class(text, source)
        verified = _note_line(text, "verified")
        if verified:
            row["verified"] = [part.strip() for part in verified.split("+") if part.strip()]
        else:
            problems.append("literature/%s: no verified line, so the two-source "
                            "check is not recorded" % note)
        problems.append("literature/%s: no inclusion decision derived - which "
                        "sources the line used is the reader's call, not the "
                        "note's" % note)
        if row["class"] == "grey":
            problems.append("literature/%s: no quality note derived for a grey "
                            "source" % note)
        added.append(row)
        lines.append("literature/INDEX.jsonl: %s, class %s%s"
                     % (note, row["class"],
                        ", id " + row["id"][:40] if "id" in row else ""))
    if added and not dry_run:
        os.makedirs(literature, exist_ok=True)
        with open(path, "a+b") as handle:
            problem = _locked(handle)
            if problem:
                problems.append("%s, so the index was not written" % problem)
                return lines
            # The committed boundary, like every other append here: a fragment a
            # killed writer left behind is not a row, and terminating it instead
            # would make it one a reader then refuses.
            truncate_to_committed(handle)
            handle.write("".join(json.dumps(row) + "\n" for row in added).encode("utf-8"))
    return lines


def _note_text(path):
    try:
        with open(path, encoding="utf-8") as fh:
            return fh.read()
    except (OSError, UnicodeDecodeError):
        return ""


def _note_line(text, field):
    """The value of a note's `- <field>: ...` line, marked up or not: the notes in
    the tree write `- id: ...`, `- **Source:** ...` and `- **Read:** ...`."""
    match = re.search(r"^\s*[-*+]?\s*(?:\*\*)?%s(?:\*\*)?:\s*(.+)$"
                      % re.escape(field), text, re.M | re.I)
    return match.group(1).strip() if match else ""


def _note_source(text):
    """The note's primary source: its `url:`/`source:` line, else the first url in
    it, else nothing - which is reported, because a note with no readable source
    is a note nobody can follow."""
    value = _note_line(text, "url") or _note_line(text, "source")
    if value:
        urls = re.findall(r"https?://[^\s`<>\"')]+", value)
        return (urls[0] if urls else value).rstrip(".,;:")
    urls = re.findall(r"https?://[^\s`<>\"')]+", text)
    return urls[0].rstrip(".,;:") if urls else ""


def source_class(text, source):
    """`formal` when the note is a paper record, `grey` otherwise.

    A DOI, an arXiv id or a URL on an academic host makes it formal wherever it
    was read from - a CHI paper fetched as a pdf from the author's employer is
    still a paper record - and everything else is the practice channel, which the
    layer allows and which has to be labelled as such."""
    if re.search(r"\b10\.\d{4,}/", text) or re.search(r"arxiv[:\s]\s*\d{4}\.\d{4,5}",
                                                      text, re.I):
        return "formal"
    host = urlsplit_host(source)
    return "formal" if host in FORMAL_HOSTS else "grey"


def urlsplit_host(source):
    """The host of a url as written in a note, without the scheme: the notes cite
    `https://www.alphaxiv.org/abs/...`, and the `www.` is not the host's name."""
    match = re.match(r"https?://([^/\s]+)", source or "")
    host = match.group(1).lower() if match else ""
    return host[4:] if host.startswith("www.") else host


def source_run(repo, slug, hypothesis, run, orx, command="", scope="", fixture=""):
    """(path, problems): file one orx run as this experiment's receipt.

    `orx logs` is read here rather than by the session, so the log lands in the
    repository as bytes and not as a summary of itself, and the results row that
    names it is appended under the same exclusive lock `claim` uses. The
    experiment has to exist with its protocol already written: a receipt filed
    against a run whose plan was never committed reopens exactly the hole the
    order rule closes. Problems are returned rather than raised, and nothing is
    written when there are any.

    `scope` is what the run measured on, and it is the filer's to state: the
    engine cannot tell a run pointed at the running system from one pointed at a
    generated repository, and a rule that guessed would be the fabrication the
    field exists to catch. Filing without it writes the row the way the rows
    before the field look - the checker warns and names it.

    `fixture` is the second half of a `fixture` scope: what was generated. It is
    written the same way and is owed for the same reason, so `--scope fixture`
    without it files the row and says which field is still missing rather than
    refusing a row a session may have a reason to file; a value that is not a
    string, or one that is empty, is the mistake the field exists to catch and is
    refused."""
    if scope and scope not in SCOPES:
        return None, ["scope %r is not one of %s" % (scope, ", ".join(SCOPES))]
    if fixture and (not isinstance(fixture, str) or not fixture.strip()):
        return None, ["fixture %r does not name what was generated" % (fixture,)]
    experiment = os.path.join(line_dir(repo, slug), "experiments", hypothesis)
    if not os.path.isfile(os.path.join(experiment, "protocol.md")):
        return None, ["experiments/%s holds no protocol.md: write and commit the "
                      "plan before filing the run it predicts" % hypothesis]
    log, err = _run([orx, "logs", run], cwd=repo)
    if err:
        return None, ["orx logs %s failed: %s" % (run, err)]
    if not log.strip():
        return None, ["orx logs %s returned nothing, so there is no receipt to "
                      "file" % run]
    raw = os.path.join(experiment, "raw")
    os.makedirs(raw, exist_ok=True)
    path = os.path.join(raw, run + ".log")
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(log)
    row = {"source": "orx:%s" % run, "log": "raw/%s.log" % run}
    if command:
        row["command"] = command
    if scope:
        row["scope"] = scope
    if fixture:
        row["fixture"] = fixture
    problems = _append_row(os.path.join(experiment, "results.jsonl"), row)
    return path, problems


def row_problems(row):
    """The reasons a results row cannot be appended; [] when it can.

    Exactly the refusals `_check_rows` decides from a row's own shape: an object,
    a `source` that is a non-empty string, a `scope` in SCOPES, a `fixture`
    description that is a non-empty string. The warn class is deliberately not
    repeated - a row with no `source` key at all, or a row that declares no scope,
    is the pre-migration shape `check` reports and `--strict` refuses - because a
    writer stricter than the checker refuses what the checker only reports, which
    is the disagreement `claim_problems` exists to avoid. The rule is here so the
    row writer cannot record what the checker refuses: until it existed, the row
    path appended whatever it was handed."""
    if not isinstance(row, dict):
        return ["a results row is a JSON object, not a %s" % type(row).__name__]
    problems = []
    if "source" in row and (not isinstance(row["source"], str)
                            or not row["source"].strip()):
        problems.append("carries an empty source")
    scope = row.get("scope")
    if scope is not None:
        if not isinstance(scope, str) or not scope.strip():
            problems.append("carries an empty scope")
        elif scope not in SCOPES:
            problems.append("scope %r is not one of %s" % (scope, ", ".join(SCOPES)))
        elif scope == "fixture":
            described = row.get("fixture")
            if isinstance(described, str) and not described.strip():
                problems.append("carries an empty fixture description")
            elif described is not None and not isinstance(described, str):
                problems.append("carries a fixture description that is a %s, not "
                                "the text naming what was generated"
                                % type(described).__name__)
    return problems


def _append_row(path, row):
    """Append one results row under the lock, judged inside it.

    The lock is taken first and `row_problems` runs with it held, so the row a
    session is filing is judged by the same rules from the same state as the
    append that records it - the order `append_claim` records the reason for. The
    repair is the committed boundary rather than a newline appended after whatever
    a killed writer left behind: a fragment is not a row, and the append used to
    turn it into one that never parses.

    A refused row leaves no empty results.jsonl behind: `source_run` writes a row
    it built itself, and a file created by a refusal would make the experiment read
    as one that ran and recorded nothing."""
    created = not os.path.isfile(path)
    with open(path, "a+b") as handle:
        problem = _locked(handle)
        if problem:
            return [problem]
        problems = row_problems(row)
        if problems:
            if created and os.path.getsize(path) == 0:
                os.remove(path)
            return problems
        truncate_to_committed(handle)
        handle.write(json.dumps(row).encode("utf-8") + b"\n")
    return []


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
    """Scaffold a research line. Returns the paths created (never overwrites).

    Refuses a slug `slugs()` cannot list - see `valid_slug` - so no caller can
    write a line that `check`, `status` and `claim` never see."""
    if not valid_slug(slug):
        raise ValueError("not a research slug: %r" % slug)
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
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(text)
        made.append(path)
    return made


def note_open(repo, slug, reason, date=""):
    """The problem that stopped the entry being written, or None.

    `init --allow-open` opens a line over the unfinished ones, and that hatch is
    only honest if the reason outlives the session that used it: the entry is the
    first line of the new line's `log.md`, which is where the next reader looks for
    why a line was opened beside the ones still in flight. The write is total - a
    log that cannot be appended returns the problem - because the line is already
    scaffolded, and losing the note must not lose the line."""
    try:
        with open(os.path.join(line_dir(repo, slug), "log.md"), "a", encoding="utf-8") as fh:
            fh.write("- %s opened with --allow-open: %s\n" % (date, reason))
    except OSError as exc:
        return str(exc)
    return None


# --- predictions ------------------------------------------------------------
# A prediction is the falsifiable half of a proposed harness-text change: the
# commit that change landed in, the number it is supposed to move, and what
# would show it did not. One JSON object per row in `predictions.jsonl` at the
# line root, appended under the lock the claim path uses, judged inside it and
# repaired to the file's committed size like it, refused with one reason per
# problem.
#
# The paths a prediction may not reach without a human `granted_by`. One tuple,
# and `_frozen` is its only reader, so the write path and the checker cannot
# drift apart on what is frozen: `hooks/tezgah_gate.py` and
# `hooks/tezgah_integrity.py` are the verifier and the ledger's write path - the
# two the loop that proposes changes is forbidden to touch - this module,
# `hooks/tezgah_research.py`, is the machinery that decides the rule and so is one
# the loop it judges may not edit - `tests/` holds the hidden checks, `benchmarks/`
# is the instrument, and a line's `protocol.md` is the pre-registration the order
# rule exists to protect. Three shapes, each read by `_frozen`: a trailing `/` is
# a directory and everything under it, a `*` is a pattern matched at any depth,
# anything else is the exact path.
FROZEN_PATHS = ("hooks/tezgah_gate.py", "hooks/tezgah_integrity.py",
                "hooks/tezgah_research.py", "tests/", "benchmarks/",
                "experiments/*/protocol.md")

# The commit a prediction is bound to: 40 hex characters as git writes them. A
# short sha, an abbreviation or a branch name is refused, because the row has to
# name the one change whose effect it predicts.
SHA = re.compile(r"[0-9a-f]{40}")


def _frozen(rel):
    """True when the repository-relative path `rel` is one a prediction may not
    reach without a human `granted_by`. The single reader of FROZEN_PATHS, so the
    write path and the checker cannot disagree about what is frozen."""
    for entry in FROZEN_PATHS:
        if entry.endswith("/"):
            if rel.startswith(entry):
                return True
        elif "*" in entry:
            if fnmatch.fnmatch(rel, "*" + entry):
                return True
        elif rel == entry:
            return True
    return False


def commit_paths(repo, sha):
    """(paths, error): the repository-relative paths one commit changed, or the
    reason git could not say. `--root` so the commit that created the repository
    reports its files instead of an empty diff, and `-m` so a merge reports the
    paths it brought in rather than nothing - the two ways this answer would
    otherwise come back empty and read as "touched nothing"."""
    out, err = _git_out(repo, "diff-tree", "-m", "--no-commit-id", "--name-only",
                        "-r", "--root", sha)
    if err:
        return [], err
    return [line.strip() for line in out.splitlines() if line.strip()], None


def _named_nothing(value):
    """True when a prediction field names nothing: an absent key, a null, or a
    string of whitespace. A number is never nothing - `value_before: 0` is the
    number the change has to move - which is why this is not a truth test."""
    return value is None or (isinstance(value, str) and not value.strip())


def prediction_problems(pred, base, repo, git=True, new=True):
    """(problems, undecided): the reasons this prediction row cannot be recorded,
    and the rules git could not decide. `problems` is [] exactly when the row is
    valid.

    Exactly the rules `check` applies to a row, mirroring `claim_problems` so the
    writer can never refuse a prediction the checker would accept: a `commit` that
    is a 40-character sha and an ancestor of HEAD, a `metric` and a `value_before`
    with a number to move, a `falsifier`, a commit that reached a frozen path
    without a `granted_by`, a `claim` id this line holds, and the `components` the
    row names. The undecided class is the one the rest of this module's
    git-dependent rules use: a sha git cannot place, or a commit it cannot read,
    is reported rather than turned into an invented refusal. `git=False` skips the
    commit graph for the callers that must stay cheap (`check_line`'s own flag) -
    the ancestry and the frozen-path question - and the row's own shape is read
    either way; the write path always asks.

    `new` is the second asymmetry (the first is `granted_by`'s commit graph) and
    the only one about the row's own shape: the write path records a row that is
    new, and a new row names the component it changes - a row written before the
    field existed is the warning class `check` reports and `--strict` refuses,
    which is this module's precedent for every pre-migration row."""
    problems, undecided = [], []
    commit = pred.get("commit")
    # The row's own shape is what `--strict`-less, git-less callers can still read:
    # a missing commit or one that is not a sha is decided from the row alone, and
    # only the ancestry and the frozen-path question need the commit graph.
    if _named_nothing(commit):
        problems.append("carries no commit, and a prediction is bound to one")
    elif not isinstance(commit, str) or not SHA.fullmatch(commit):
        problems.append("commit %r is not a 40-character sha" % (commit,))
    elif git:
        ancestor = is_ancestor(repo, commit, "HEAD")
        if ancestor is None:
            undecided.append("commit %s cannot be placed against HEAD, so "
                             "whether it is an ancestor is unverified"
                             % commit[:8])
        elif not ancestor:
            problems.append("commit %s is not an ancestor of HEAD, so the "
                            "change the row predicts has not landed in this "
                            "history" % commit[:8])
        else:
            paths, err = commit_paths(repo, commit)
            if err:
                undecided.append("commit %s could not be read (%s), so whether "
                                 "it reached a frozen path is unverified"
                                 % (commit[:8], err))
            else:
                frozen = sorted(p for p in paths if _frozen(p))
                if frozen and _named_nothing(pred.get("granted_by")):
                    problems.append("commit %s changed %s, which the loop may "
                                    "not touch without a human granted_by"
                                    % (commit[:8], ", ".join(frozen)))
    if _named_nothing(pred.get("metric")):
        problems.append("metric names no number, and a prediction with no number "
                        "to move is not falsifiable")
    if _named_nothing(pred.get("value_before")):
        problems.append("value_before names no number, so nothing says what the "
                        "change is measured against")
    if _named_nothing(pred.get("falsifier")):
        problems.append("falsifier names nothing, so the row states no result that "
                        "would show it did not hold")
    # `claim` is optional - a prediction may stand alone - and when it is there it
    # names a claim this line holds, which is the same rule the `supersedes` link
    # is held to: an id nothing carries is a relation to nothing.
    claim = pred.get("claim")
    if claim is not None and not isinstance(claim, str):
        problems.append("claim %r is not a claim id" % (claim,))
    elif claim and claim.strip() and claim.strip() not in _claim_ids(base):
        problems.append("claim %s is not an id this line holds" % claim.strip())
    # The component a row changes, read from the manifest
    # (`hooks/tezgah_components.py`, the only definition of what a component is)
    # and not from a copy of it: a key nothing defines cannot attribute the
    # outcome to anything, which is the whole point of the field, so an unknown
    # key is a refusal on both paths. A `components` that is not a list of keys is
    # refused either way - the field claims the shape and answers nothing with it.
    named = pred.get("components")
    if named is None:
        if new:
            problems.append("carries no components, and a row written under this "
                            "rule names the component it changes")
        else:
            undecided.append("carries no components: a row written before this "
                             "rule has none, so which component it changes is "
                             "unverified")
    elif not isinstance(named, list) or not named:
        problems.append("components %r is not a non-empty list of component keys"
                        % (named,))
    else:
        _entries, keys, reason = _components()
        if reason is not None:
            undecided.append("the component manifest could not be read (%s), so "
                             "the keys this row names are unverified" % reason)
        else:
            unknown = sorted({str(k) for k in named if k not in keys})
            if unknown:
                problems.append("components names %s, which the manifest does "
                                "not define" % ", ".join(unknown))
    return problems, undecided


def _check_predictions(repo, base, errors, warnings, strict, git=True):
    """The prediction rows of one line, read from the file the writer appends to.

    A line with no `predictions.jsonl` is not a problem: the artifact is newer
    than every line in this repository, and a rule that refused an absent file
    would refuse them all. The rows themselves are judged by the write path's own
    function - with `new=False`, because a row already in the file may have been
    written before the `components` field existed - and the file's shape by the
    rules every JSONL artifact here is judged by: one object per line, a row that
    does not parse is refused rather than skipped."""
    rows, problems = _prediction_lines(base)
    errors.extend(problems)
    for n, pred in rows:
        found, undecided = prediction_problems(pred, base, repo, git=git, new=False)
        errors.extend("predictions.jsonl:%d %s" % (n, p) for p in found)
        for note in undecided:
            _soft(errors, warnings, strict,
                  "predictions.jsonl:%d %s" % (n, note))
    return len(rows)


def append_prediction(repo, slug, pred):
    """(problems, undecided); problems is [] exactly when the row was written.

    The lock, the committed-size repair and the refusal channel are
    `append_claim`'s, for the reasons that made them: the file is append-only
    evidence, two sessions recording a prediction at once is normal, and a
    half-written line loads as nothing. Where the harness ledger falls back to an
    unlocked write when its lock cannot be taken, this path refuses and names the
    reason - a prediction is evidence, and evidence that raced is worse than
    evidence that was refused.

    The lock is taken before the row is judged, for `append_claim`'s reason: the
    row's `claim` relation is proved against the claims this line holds, and
    judging it before the lock let another session land the id in between. The
    whole judgement runs under the lock, the git half of it included, so nothing
    the writer proved comes from an instant before the append.

    Raises FileNotFoundError when the line directory does not exist."""
    if not valid_slug(slug):
        # An invalid slug can still resolve to an existing directory: `..` is
        # the research root's parent, which is tezgah's own state dir.
        return ["not a research slug: %r" % slug], []
    base = line_dir(repo, slug)
    if not os.path.isdir(base):
        raise FileNotFoundError(base)
    # Binary, so the committed-size repair below reads and writes bytes.
    path = os.path.join(base, "predictions.jsonl")
    # A refused row leaves no empty file behind, the promise `predict` makes on its
    # refusal path and the way `append_claim` keeps it.
    created = not os.path.isfile(path)
    with open(path, "a+b") as handle:
        problem = _locked(handle, "predictions.jsonl")
        if problem:
            return [problem], []
        problems, undecided = prediction_problems(pred, base, repo)
        if problems:
            if created and os.path.getsize(path) == 0:
                os.remove(path)
            return problems, undecided
        # An append starts at the last committed newline: a fragment a killed
        # writer left behind is not a row (`truncate_to_committed`).
        truncate_to_committed(handle)
        handle.write(json.dumps(pred).encode("utf-8") + b"\n")
    return [], undecided


# --- the per-component report -----------------------------------------------
# What a refinement loop needs to attribute an outcome to a component instead of
# to "the harness": the prediction rows grouped by the component they name, and
# each row's state. A report and not a gate - it refuses nothing and always exits
# 0 - and it prints the number of components and rows it read, so a reader can
# tell an empty manifest from a line with no predictions.
PREDICTION_STATES = ("held", "falsified", "unmeasured")


def _prediction_lines(base):
    """([(n, row)], problems): the rows of one line's `predictions.jsonl`, each
    with its 1-based line number, and the reasons the file could not be read as
    rows at all - a file that is absent is no problem, because the artifact is
    newer than most of the lines in this repository.

    One reader for the checker and for the report, so the two agree on what the
    file holds and on how many rows it holds."""
    path = os.path.join(base, "predictions.jsonl")
    if not os.path.isfile(path):
        return [], []
    try:
        with open(path, encoding="utf-8") as fh:
            raw = fh.readlines()
    except (OSError, UnicodeDecodeError) as exc:
        return [], ["predictions.jsonl cannot be read (%s)" % exc]
    rows, problems = [], []
    for n, line in enumerate(raw, 1):
        if not line.strip():
            continue
        try:
            pred = json.loads(line)
        except ValueError as exc:
            problems.append("predictions.jsonl:%d does not parse (%s)" % (n, exc))
            continue
        if not isinstance(pred, dict):
            problems.append("predictions.jsonl:%d is a %s, not the object a row is"
                            % (n, type(pred).__name__))
            continue
        rows.append((n, pred))
    return rows, problems


def _components():
    """(entries, keys, reason): the manifest's entries, the keys it defines, and
    the reason it could not be read (with two empty lists).

    The manifest (`hooks/tezgah_components.py`) is the only definition of what a
    component is, and it is imported here - in the call that needs it - so the
    prediction path a session pays for never loads it at import time. A manifest
    that cannot be imported is reported rather than raised: the keys a row names
    are then unverified, which is the class this module warns about."""
    try:
        import tezgah_components
    except ImportError as exc:
        return [], [], str(exc)
    return list(tezgah_components.COMPONENTS), list(tezgah_components.keys()), None


def _claim_statuses(base):
    """{id: status} for the claims this line holds, so a prediction's state is
    read from the line's own rows and not from the row's shape alone. A claims
    file that cannot be read leaves the map empty, which reads as "this line holds
    no such claim" - the state such a row gets either way is `unmeasured`."""
    out = {}
    try:
        with open(os.path.join(base, "claims.jsonl"), encoding="utf-8") as fh:
            lines = fh.readlines()
    except (OSError, UnicodeDecodeError):
        return out
    for line in lines:
        try:
            claim = json.loads(line)
        except ValueError:
            continue
        if isinstance(claim, dict) and claim.get("id"):
            out[claim["id"]] = claim.get("status")
    return out


def _prediction_state(pred, base):
    """(state, why): one prediction row's state, read from the row and the line's
    own claims, plus the reason when `falsified` could not be decided.

    `falsified` is never inferred from the row alone: what says a prediction did
    not hold is the line's own record, and the only verdict a line records is the
    `refuted` status of the claim the row names. A row whose `claim` this line
    does not hold has no verdict to read, so its state stays `unmeasured` and the
    reason is named rather than guessed. `value_after` empty is the round that has
    not run; filled is the number that came back."""
    claim = pred.get("claim")
    if isinstance(claim, str) and claim.strip():
        cid = claim.strip()
        status = _claim_statuses(base).get(cid)
        if status is None:
            return "unmeasured", ("claim %s is not an id this line holds, so "
                                  "nothing in the line says which way it moved"
                                  % cid)
        if status == "refuted":
            return "falsified", None
    if _named_nothing(pred.get("value_after")):
        return "unmeasured", None
    return "held", None


def _named_components(pred):
    """The component keys one row names, or [] when it names none - the field
    absent, shapeless or empty. Nothing is guessed from a field that is not the
    list of keys it is meant to be: such a row is reported as naming no component,
    and the checker is the reading that refuses it."""
    named = pred.get("components")
    if not isinstance(named, list):
        return []
    return [k for k in named if isinstance(k, str)]


def component_report(repo, slug=None):
    """The per-component report: one bucket per component the rows name, with the
    prediction rows that name it and each row's state, plus the counts it read.

    The report's own shape, printed twice by the CLI (text and `--json`):
    `components` is a bucket per key - the manifest's keys in the manifest's own
    order first, then any key the manifest does not define, so a hand-written row
    is visible rather than dropped - `unlabeled` is the rows that name no
    component at all, `rows` and `read` are what the report read, `problems` are
    the lines the file could not be read as rows, and `manifest` is the reason the
    manifest could not be imported. `slug` reads one line; the default reads every
    line under the repository's research root, the way `status` does."""
    entries, keys, reason = _components()
    labels = {entry.get("key"): entry.get("label") for entry in entries}
    rows, problems = [], []
    for name in ([slug] if slug else slugs(repo)):
        base = line_dir(repo, name)
        parsed, bad = _prediction_lines(base)
        problems.extend("%s: %s" % (name, p) for p in bad)
        for n, pred in parsed:
            state, why = _prediction_state(pred, base)
            rows.append({"line": name, "row": n, "commit": pred.get("commit"),
                         "metric": pred.get("metric"), "state": state,
                         "why": why, "components": _named_components(pred)})
    named = {k for row in rows for k in row["components"]}
    buckets = [{"key": k, "label": labels.get(k),
                "rows": [r for r in rows if k in r["components"]]}
               for k in list(keys) + sorted(named - set(keys))]
    return {"components": buckets,
            "unlabeled": [r for r in rows if not r["components"]],
            "rows": len(rows), "read": len(keys), "manifest": reason,
            "problems": problems}


def components_text(report):
    """The lines `tezgah-research components` prints, from the report the reader
    above builds: one header per component and one line per row, so the text and
    the `--json` are one decision printed twice.

    The header carries the three states as counts, because that is the question a
    refinement loop asks of a component - how many of the predictions naming it
    came back, how many it refuted, how many are still open - and a row line names
    the line, the row, the commit and the metric the state belongs to."""
    def header(key, label, rows):
        counts = {s: sum(1 for r in rows if r["state"] == s)
                  for s in PREDICTION_STATES}
        return ("%s: %d row(s) - %d held, %d falsified, %d unmeasured%s"
                % (key, len(rows), counts["held"], counts["falsified"],
                   counts["unmeasured"], " (%s)" % label if label else ""))

    def row_line(row):
        return "  %s #%d %s %s: %s%s" % (
            row["line"], row["row"], (row["commit"] or "")[:8], row["metric"],
            row["state"], " (%s)" % row["why"] if row["why"] else "")

    out = []
    if report["manifest"]:
        out.append("note: the component manifest could not be read (%s), so the "
                   "keys below are the ones the rows name and not the manifest's"
                   % report["manifest"])
    out.append("components: %d read, %d prediction row(s) read"
               % (report["read"], report["rows"]))
    out.extend("note: %s" % problem for problem in report["problems"])
    for bucket in report["components"]:
        out.append(header(bucket["key"], bucket.get("label"), bucket["rows"]))
        out.extend(row_line(row) for row in bucket["rows"])
    if report["unlabeled"]:
        out.append(header("(no components)", None, report["unlabeled"]))
        out.extend(row_line(row) for row in report["unlabeled"])
    return out
