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
it reads the history of `.tezgah`'s own private git repository (the project
ignores `.tezgah/`), falling back to the project's history for a line committed
there before it moved; the check asks whether the paths it orders - each
experiment's `protocol.md` and `results.jsonl` - can be committed at all rather
than whether the line's directory matches an ignore pattern. Beside it stand the
completeness rules that
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
decide - an experiment file no repository can commit, so the order rule has nothing to order; a
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
import tezgah_paths as tp

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
# `agent-report` is a third class: a summary an agent wrote of what it read. It is
# kept and indexed like any note, and it cannot alone carry a `literature` claim,
# because an agent's paraphrase is not the paper or the page it paraphrased.
SOURCE_CLASSES = ("formal", "grey", "agent-report")

# The rule set a line was opened under. `init` writes `RULES`, the newest; a line
# without the field predates the standards rules below (evaluation lock order,
# results append-only, review integrity, ask traceability, variants), and each of
# those warns on it instead of refusing - its rows were written before the rule
# existed. Each later set is gated on its own number, so a bump never demotes an
# older set: 2 the standards rules, 3 the ask contract (keyed on the `ask` field),
# 4 the protocol sections (`_check_protocol_sections`). A `rules` above `RULES` is
# a line a later tezgah wrote, and every reader and writer here refuses it by name
# (`newer_rules`) rather than judging it by rules it does not know.
STANDARDS_RULES = 2
PROTOCOL_RULES = 4
RULES = PROTOCOL_RULES

# What a line delivers, and how many compared variants that takes. `finding` is a
# line whose deliverable is its claims; the other four are an artifact a reader
# acts on, and one design with no compared alternative is the serial fixation the
# variants rule exists against.
DELIVERABLE_KINDS = ("design", "plan", "code", "analysis", "finding")
VARIANT_KINDS = ("design", "plan", "code", "analysis")
CRITERION_KINDS = ("measured", "judged")
CRITERION_DIRECTIONS = ("max", "min", "pass")
VARIANT_STATUSES = ("produced", "dropped")
DECISION_FILES = ("criteria.json", "variants.jsonl", "comparison.jsonl",
                  "decision.md")
VALIDITY_TYPES = ("internal", "external", "construct", "conclusion")
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

# The labels a line opened under `PROTOCOL_RULES` declares in its protocol. The
# word rule above passed `prediction:` followed by nothing, and three rounds of
# reading sections out of prose kept finding new shapes it misread. So a new line
# declares each answer as a `key: value` line at column 0 (`protocol_labels`), and
# the rules read the values, never the prose around them:
# - `prediction:` and `falsifier:` - non-empty, and not the same text;
# - `headroom:` - the most the change could move, written before any arm runs
#   (SoL-Pi's Oracle Analysis, as adopted from gortex, idea 4);
# - `metric:` - what the run counts, and `unit:` - what it counts in. When the
#   unit is tokens (`_token_unit`), `tokenizer:` and `bound:` (the under-reporting
#   bound) are owed too, because a token count is only as good as the counting
#   it pre-commits to (the same line, idea 3, C04). The unit is declared rather
#   than read out of the metric's wording, which misfired both ways.
PROTOCOL_KEYS = ("prediction", "falsifier", "headroom", "metric", "unit",
                 "tokenizer", "bound")
PROTOCOL_LABEL = re.compile(r"^([A-Za-z][\w-]*)[ \t]*:(.*)$")
# A headroom value that projects nothing (`_headroom_none`): no digit 1-9, and,
# once emphasis is stripped and a leading zero figure ("0.0%", "0 ms") is read as
# `0`, one of these whole or as a prefix. "0% today; up to 40% could" passes.
HEADROOM_NONE = ("none", "no", "zero", "nil", "0", "negligible", "nothing to gain")
HEADROOM_NONE_PREFIX = ("none ", "none,", "no headroom", "0 ", "0,", "zero ",
                        "no gain", "no room", "nothing to gain", "negligible")
HEADROOM_ZERO = re.compile(r"^0(?:\.0+)?\s*(?:%|percent|tokens?|ms)?")

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
# the second one cannot be recovered afterwards: an internal research line
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

# A `path:line` citation (a file name, a colon and a line or a range) names a
# place in a file, not a measurement: its line number is lifted off with the
# date, so a claim citing where it read a figure is not warned about the line.
PATH_LINE = re.compile(r"[\w./-]*\.[A-Za-z]\w*:\d+(?:[-+,]\d+)*")

# A thousands separator is a rendering and not a different number, so the
# containment rule compares without one: a claim stating 20480 against an artifact
# holding `20,480` is the same measurement. Every other comma is left alone, and the
# warning still quotes the artifact as it stands.
THOUSANDS = re.compile(r",(\d{3})(?!\d)")


def _numbers(text):
    """The numbers a claim's statement asserts, with the dates and the `path:line`
    citations it names removed."""
    return NUMBER.findall(ISO_DATE.sub(" ", PATH_LINE.sub(" ", text)))


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


OPEN = "open"
DONE = "done"


def root(repo):
    return os.path.join(repo, ".tezgah", "research")


def layout_roots(repo):
    """Where a line may live, in precedence order: `open/`, `done/`, then the
    flat root a workspace that has not run `migrate-layout` still holds. One
    resolver for every reader, so a line is found wherever it sits and a new one
    is written under `open/`."""
    base = root(repo)
    return [os.path.join(base, OPEN), os.path.join(base, DONE), base]


def slugs(repo):
    seen = {}
    for folder in layout_roots(repo):
        try:
            names = os.listdir(folder)
        except OSError:
            continue
        for name in names:
            if name.startswith(".") or not name:
                continue
            # the layout folders are not lines: the flat root still holds them
            if folder == root(repo) and name in (OPEN, DONE):
                continue
            if os.path.isdir(os.path.join(folder, name)):
                seen.setdefault(name, folder)
    return sorted(seen)


def line_dir(repo, slug):
    """The one resolver: the first layout root that holds the line, else the
    `open/` path a new line is created at."""
    for folder in layout_roots(repo):
        path = os.path.join(folder, slug)
        if os.path.isdir(path):
            return path
    return os.path.join(root(repo), OPEN, slug)


def sealed(repo, slug):
    """True when the line sits under `done/`: concluded or closed."""
    return os.path.isdir(os.path.join(root(repo), DONE, slug))


def legacy_layout(repo):
    """The flat lines a workspace still holds, for `migrate-layout` and for the
    one-line notice `check`/`status` print when it finds any."""
    base = root(repo)
    try:
        names = os.listdir(base)
    except OSError:
        return []
    return sorted(n for n in names
                  if not n.startswith(".") and n not in (OPEN, DONE)
                  and os.path.isdir(os.path.join(base, n)))


def migrate_layout(repo):
    """[(slug, folder)] for the flat lines moved into `open/` or `done/`.

    A concluded or closed line goes to `done/`, everything else to `open/`, and
    the move is a rename inside the workspace so the private repository sees it
    as a rename on the next `commit`. Idempotent: a workspace already in the two
    folders has nothing flat to move and returns []."""
    moved = []
    for slug in legacy_layout(repo):
        state, _exc = _read_json(os.path.join(root(repo), slug, "state.json"))
        concluded = isinstance(state, dict) and (
            str(state.get("phase")) == "concluded" or bool(state.get("closed")))
        folder = DONE if concluded else OPEN
        _path, problem = move_line(repo, slug, folder)
        if not problem:
            moved.append((slug, folder))
    return moved


def line_state(repo, slug):
    """`state.json` for a line, wherever the layout puts it, or {}."""
    state, _exc = _read_json(os.path.join(line_dir(repo, slug), "state.json"))
    return state if isinstance(state, dict) else {}


def move_line(repo, slug, folder):
    """Move a line between layout folders. Returns (new path, problem)."""
    src = line_dir(repo, slug)
    dst_root = os.path.join(root(repo), folder)
    dst = os.path.join(dst_root, slug)
    if os.path.realpath(src) == os.path.realpath(dst):
        return dst, None
    try:
        os.makedirs(dst_root, exist_ok=True)
        os.rename(src, dst)
    except OSError as exc:
        return src, str(exc)
    return dst, None


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


# --- which history proves an order ------------------------------------------
# A line lives under `<repo>/.tezgah`, which the project ignores and which holds a
# private git repository of its own (`tezgah_paths.ensure_workspace`), so the
# commits that order a protocol before its results are that repository's. A line
# committed in the project itself before the move keeps its proof there: the
# helpers below read both histories, the private one first, and every order check
# (this module's and any added later) asks them rather than `_git` directly.

def _ws_rel(repo, path):
    """`path` relative to `<repo>/.tezgah`, or None when it is outside it or the
    workspace has no repository of its own - `git -C .tezgah` would then climb to
    the project's repository and answer for it."""
    ws = tp.workspace(repo)
    rel = os.path.relpath(path, ws)
    if rel == os.pardir or rel.startswith(os.pardir + os.sep):
        return None
    return rel if os.path.exists(os.path.join(ws, ".git")) else None


def _ws_log(repo, path, *args):
    """(shas, error) of the private repository's `git log <args>` over `path`'s
    own layout names (`_own_names`) along its HEAD, ([], None) when `path` is
    outside it or the repository has no commit yet."""
    rel = _ws_rel(repo, path)
    if rel is None or _unborn(tp.workspace(repo)):
        return [], None
    pairs, err = _named_log(tp.workspace(repo), rel, args)
    return [sha for sha, _names in pairs], err


def _unborn(top):
    """True when the repository at `top` holds no commit at all: `git init` and
    nothing after it, whose `git log` is an error rather than an empty history.
    A HEAD git cannot read beside refs that exist is not this - that log's error
    is reported."""
    if _holds(top, "HEAD"):
        return False
    out, err = _git_out(top, "for-each-ref", "--count=1")
    return not err and not out.strip()


def _own_names(rel):
    """`rel` and the names the same file has in the line's other layouts: the flat
    `research/<slug>/`, `open/<slug>/` and `done/<slug>/`, under the same prefix.

    Closing a line moves it from open/ to done/ (`move_line`), and the order rules
    ask git which commit first added a file; asked by the current path only, the
    move read as the commit that added protocol, results, criteria and state
    together, and every moved line failed (measured 2026-10-03). `git log
    --follow` is not the answer: it walks any rename, so another line's older
    protocol moved in after this line's results inherited its age (found in a
    consult review), and its similarity guess tied a `decisions/d2` file to `d1`.
    Only the line's own layouts are asked, by name. ponytail: a name is matched by
    path, so a slug deleted and later reused shares its dead predecessor's
    history - the flat layout read it the same way; a reused slug is the ceiling.
    So is a results file renamed into place inside the line after its protocol
    (`scratch.jsonl` to `results.jsonl`): the rename is its add here as it was
    before - a file kept out of the history until after the plan defeats any
    history-based order check."""
    parts = rel.replace(os.sep, "/").split("/")
    try:
        i = parts.index("research")
    except ValueError:
        return [rel]
    head, rest = parts[:i + 1], parts[i + 1:]
    if rest[:1] in (["open"], ["done"]):
        rest = rest[1:]
    if not rest:
        return [rel]
    names = [rel] + ["/".join(head + layout + rest)
                     for layout in ([], ["open"], ["done"])]
    return list(dict.fromkeys(names))


def _historical_names(top, rel, extra=()):
    """`rel`'s own layout names plus every spelling git committed them under,
    newest first: an exact-case blob read at an older commit needs the name the
    tree held then (`decisions/D1` before the migration lowercased it)."""
    pairs, _err = _named_log(top, rel, extra)
    names = [name for _sha, found in pairs for name in found]
    return list(dict.fromkeys(names + _own_names(rel)))


def _named_log(top, rel, extra=()):
    """([(sha, [names])], error), newest first: the commits that touched any of
    `rel`'s own layout names (`_own_names`), each with the names it touched.
    Matched without case: the layout migration lowercased decision directories
    (`decisions/D1` became `decisions/d1`)."""
    specs = [":(icase)" + name for name in _own_names(rel)]
    out, err = _git_out(top, "log", *extra, "--name-only", "--format=%x00%H",
                        "--", *specs)
    if err:
        return [], err
    pairs = []
    for chunk in out.split("\x00")[1:]:
        lines = [ln.strip() for ln in chunk.splitlines() if ln.strip()]
        if lines:
            pairs.append((lines[0], lines[1:] or [rel]))
    return pairs, None


def _ignored(repo, path):
    """The `file:line:pattern` that git ignores this exact path by, or None.

    Asked of the repository that commits the path: the private `.tezgah` one when
    it exists (the project's own ignore of `.tezgah/` is not its business), else
    the project's. Whether the path is ignored at all is decided by the plain
    form, not `-v`: for a directory whose last matching pattern is a negation,
    `check-ignore -v` prints that pattern and exits 0 while the directory is not
    ignored - measured on a scratch repo, and the reason a tracked line was
    reported as ignored."""
    rel = _ws_rel(repo, path)
    top = tp.workspace(repo) if rel is not None else repo
    rel = rel if rel is not None else os.path.relpath(path, repo)
    plain, err = _git_out(top, "check-ignore", "--", rel)
    if err or not plain.strip():
        return None
    named, verr = _git_out(top, "check-ignore", "-v", "--", rel)
    if not verr and named.strip():
        return named.splitlines()[0].split("\t")[0].strip()
    return rel


def added_commits(repo, path):
    """((shas, newest first), error): the commits that added (or renamed into)
    `path` - the private repository's, then the project's. The last one is the
    oldest add, so a line the project committed before the move proves its order
    from there, and the private repository's import commit does not read as the
    add of both files at once."""
    ws, err = _ws_log(repo, path, "--diff-filter=AR")
    if err:
        return [], err
    pairs, err = _named_log(repo, os.path.relpath(path, repo), ("--diff-filter=AR",))
    return ws + [sha for sha, _names in pairs], (None if ws else err)


def _histories(repo, path):
    """[(top, rel)]: the project's history of `path`, then the private `.tezgah`
    repository's when it carries the path and holds a commit - the two
    histories every order rule reads, named once.

    Each is read along its HEAD, never `--all`: a side branch, an abandoned
    draft, a stash or a backdated orphan is not the record, and reading every
    ref took the date-oldest add among them - a side branch's older
    protocol-then-results pair ordered a HEAD whose results came first, and an
    abandoned draft's protocol refused a HEAD that was ordered (E06, E22, E30)."""
    out = [(repo, os.path.relpath(path, repo))]
    rel = _ws_rel(repo, path)
    if rel is not None and not _unborn(tp.workspace(repo)):
        out.append((tp.workspace(repo), rel))
    return out


def _oldest_adds(repo, path):
    """({top: oldest add or None}, error), the project's history first. A project
    log that fails (a project with no commit yet) is no add there, and an error
    only when the private repository holds none either - `added_commits`' rule."""
    adds, perr = {}, None
    for top, rel in _histories(repo, path):
        pairs, err = _named_log(top, rel, ("--diff-filter=AR",))
        if err and top != repo:
            return {}, err
        perr = perr or err
        adds[top] = pairs[-1][0] if pairs else None
    return adds, (perr if not any(adds.values()) else None)


def _answers(repo, firsts, thens):
    """{top: True/False/None}: whether `firsts[top]` entered before `thens[top]`,
    for every history that holds the `then` file's add.

    Every history that can answer is asked, and the caller requires all of them
    to agree: reading only the first history that held both let a project pair
    hide a private violation and a private pair hide a project one (E14, E16,
    E38). A history holding the `then` file and never the `first` one committed
    the result with no plan beside it, and that is a False of its own. One commit
    adding both is False, except where it is the import of a plan committed
    earlier: another history ordered the pair, or the project committed the plan
    and never the result - the private repository's import then carried the
    result for the first time (E09, E17, E18). ponytail: that last case orders a
    project commit before a private one with no graph between them; the premise
    is the move itself (the project carried the line first), and a project plan
    committed after a private import that already held the result is the
    ceiling."""
    answers = {}
    ones = []
    for top, then in thens.items():
        if not then:
            continue
        first = firsts.get(top)
        if not first:
            answers[top] = False
        elif first == then:
            ones.append(top)
        else:
            answers[top] = _ancestor(top, first, then)
    for top in ones:
        answers[top] = any(
            other != top and firsts.get(other)
            and (answers.get(other) is True or (other == repo and not thens.get(other)))
            for other in firsts)
    return answers


def _top_for(repo, path, sha):
    """The repository whose history holds `sha` for `path`: the private
    `.tezgah` one when it carries the path and the commit, else the project's,
    else None. Read through the same two histories `added_commits` reads, so a
    blob comparison is made in the repository the add came from."""
    ws = tp.workspace(repo)
    if _ws_rel(repo, path) is not None and _holds(ws, sha):
        return ws
    return repo if _holds(repo, sha) else None


def _blob(top, rev, rel):
    """(blob sha, error): the blob `rel` holds at `rev`, or None when `rev` does
    not carry it. `ls-tree` answers a path a tree does not hold with an empty
    list and exit 0, so an absent blob is an answer rather than a failure."""
    out, err = _git_out(top, "ls-tree", rev, "--", rel)
    if err:
        return None, err
    for line in out.splitlines():
        parts = line.split()
        if len(parts) >= 3:
            return parts[2], None
    return None, None


UNDECIDED_CHANGE = ("experiment %s: git cannot tell whether protocol.md changed after "
                    "the run - a history holds another version it cannot order "
                    "against the run, or git could not compare them")


def _changed_after(repo, path, rev, beside=None):
    """True/False, or None when git cannot say: whether `path` holds a different
    blob at `rev` than at the tip of a history that carries it (`_changed_at_tips`).

    The order rule's second half compares blobs, not commit touches: a commit
    that merely `git rm --cached`'d the path (the 2026-09-24 commit that
    untracked `.tezgah/`) or deleted it leaves the blob the run wrote alone, and
    a touch-based reader called that "the protocol changed after the run". A path
    absent at a tip is compared in the working tree instead (`_changed_at_tips`).

    With `beside` (the results file `rev` added), the file the run saw is the one
    in the directory `rev` added `beside` to - not a name guessed from today's
    path or its spellings, which a decoy copy under today's name or a second
    spelling answered instead (consult review rounds 3-4). That directory holding
    no such file at `rev` is a change: the run did not run against this plan."""
    top = _top_for(repo, path, rev)
    if top is None:
        return None
    rel = os.path.relpath(path, top)
    at_rev = None
    anchored = False
    if beside is not None:
        added = _added_name(top, os.path.relpath(beside, top), rev)
        if added:
            anchored = True
            name = "/".join(added.split("/")[:-1] + [rel.replace(os.sep, "/").split("/")[-1]])
            at_rev, err = _blob(top, rev, name)
            if err:
                return None
            if at_rev is None:
                return True
    if beside is not None and not anchored:
        # the anchor was asked for and not found: say git could not compare
        # rather than fall back to the name guessing it replaces (referee, round 5)
        return None
    if not anchored:
        at_rev, err = _blob_by_name(top, rev, rel)
        if err:
            return None
    if at_rev is None:
        return False
    return _changed_at_tips(repo, path, top, rev, at_rev)


def _changed_at_tips(repo, path, top, rev, at_rev):
    """True when a history carrying `path` holds a blob other than `at_rev` - the
    one the run at `rev` in `top` saw - after the run; None when git cannot say.

    Every history is asked, each under the name its tip holds the file by, not
    only the run's under today's name: the order proven in the project and the
    protocol rewritten in the private repository after the import passed
    (claims C13, C33, C34, C37, C44-B2), and so did a rewrite committed in the
    project and then moved to done/, a name the project's tip never held (C41,
    C44, C46).

    A path a tip no longer tracks though its history held it (an untracked
    `.tezgah/`, a `git rm --cached`) is read from the working tree: a file there
    that differs from the run's is the plan a reader opens, rewritten (E01, E25);
    a history that never tracked the path says nothing. The run's own history
    holding another blob at its tip is a change. The other history's tip is a
    change when that history held the run's blob and moved off it - a pre-run
    draft restored after the run is an edit after it, whichever history restored
    it (E12, E23, E34, E36). A tip that differs where that history never held the
    run's blob is undecided rather than either answer: a project still tracking
    the plan from before the private import (E03, E10, E27) and a plan first
    committed there after the run leave the same graph, and nothing orders a
    project commit against a private one, so it is None - a warning, and
    `--strict` refuses.

    The order is read along HEAD; a rewrite is read across every ref. A commit
    some other ref keeps, that descends from the run and holds another blob, is
    an edit after the run that HEAD dropped (a protocol rewritten, then reset
    away under a tag), and a history that held the run's blob on any ref and
    shows another at its tip moved off it. A side ref can only add such
    evidence, so it can refuse a record and never pass one."""
    rel_top = os.path.relpath(path, top)
    later, err = _blobs_until(top, ("--all", "--ancestry-path", "^" + rev, "^HEAD"),
                              rel_top)
    if err:
        return None
    if later - {at_rev}:
        return True
    disk, undecided = None, False
    for other, rel in _histories(repo, path):
        if not _holds(other, "HEAD"):
            continue
        _name, at_tip, err = _name_at(other, "HEAD", rel)
        if err:
            return None
        if at_tip == at_rev:
            continue
        if at_tip is not None and other == top:
            return True
        held, err = _blobs_until(other, ("--all",), rel)
        if err:
            return None
        if at_tip is None:
            if held and disk is None:
                disk, err = _disk_blob(other, path)
                if err:
                    return None
            if held and disk and disk != at_rev:
                return True
            continue
        if at_rev in held:
            return True
        undecided = True
    return None if undecided else False


def _disk_blob(top, path):
    """(blob sha or "", error): the blob the working-tree file would be in `top`,
    "" when there is no such file."""
    if not os.path.isfile(path):
        return "", None
    out, err = _git(top, "hash-object", "--", path)
    return (out[0] if out and not err else ""), err


def _blobs_until(top, revs, rel):
    """(blobs, error): every blob `rel`'s file held in the commits `git rev-list
    <revs>` names."""
    specs = [":(icase)" + name for name in _own_names(rel)]
    shas, err = _git(top, "rev-list", *revs, "--", *specs)
    if err:
        return set(), err
    blobs = set()
    for sha in shas:
        blob, err = _blob_by_name(top, sha, rel)
        if err:
            return set(), err
        if blob:
            blobs.add(blob)
    return blobs, None


def _added_name(top, rel, rev):
    """The name `rev` added (or renamed) `rel`'s file under, or None."""
    pairs, err = _named_log(top, rel, ("--diff-filter=AR",))
    if err:
        return None
    for sha, names in pairs:
        if sha == rev:
            for name in names:
                found, berr = _blob(top, rev, name)
                if not berr and found:
                    return name
    return None


def _ancestor(top, older, newer):
    """True/False, or None when the repository at `top` cannot answer."""
    try:
        proc = subprocess.run(["git", "-C", top, "merge-base", "--is-ancestor",
                               older, newer], capture_output=True, text=True)
    except OSError:
        return None
    if proc.returncode == 0:
        return True
    return False if proc.returncode == 1 else None


def _holds(top, sha):
    return not _run(["git", "-C", top, "cat-file", "-e", sha + "^{commit}"])[1]


def is_ancestor(repo, older, newer):
    """True/False, or None when git cannot answer.

    The order rule is decided by the commit graph, not by timestamps: two commits
    in the same second are still two commits, a rebase rewrites dates but not
    ancestry, and a backdated GIT_COMMITTER_DATE changes nothing. Each answer
    stays inside one repository's history - the project's first, the private
    `.tezgah` one second: two commits of one history are ordered by it, while a
    project commit and a private-repository commit are two unrelated histories
    whose shas alone prove nothing, so a pair across them is undecided."""
    answer = _ancestor(repo, older, newer)
    if answer is not None:
        return answer
    ws = tp.workspace(repo)
    if not os.path.exists(os.path.join(ws, ".git")):
        return None
    return _ancestor(ws, older, newer)


def _name_at(top, rev, rel, extra=()):
    """(name, blob, error): the name `rel`'s file had at `rev`.

    Today's own layout names are tried first; a historical spelling only when
    none of them is in that tree (`decisions/D1` before the migration lowercased
    it). Two historical spellings both present at `rev` is an ambiguity, answered
    with an error rather than a pick: a decoy `H1/` committed beside `h1/` with
    the edited text was read as the run's protocol (consult review round 3)."""
    for name in _own_names(rel):
        sha, err = _blob(top, rev, name)
        if err:
            return None, None, err
        if sha:
            return name, sha, None
    found = []
    for name in _historical_names(top, rel, extra):
        sha, err = _blob(top, rev, name)
        if err:
            return None, None, err
        if sha:
            found.append((name, sha))
    if len(found) > 1:
        return None, None, "%d spellings of %s at %s" % (len(found), rel, rev[:8])
    return (found[0][0], found[0][1], None) if found else (None, None, None)


def _blob_by_name(top, rev, rel, extra=()):
    """(blob, error) of `rel`'s file at `rev` under the name it had then."""
    _name, sha, err = _name_at(top, rev, rel, extra)
    return sha, err


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
    _check_success(state, errors, warnings, strict)
    # The rules about `phase` and `direction` that are not read from the fields:
    # the line's own artifacts are the other authority beside them, and a field
    # they contradict warns.
    _check_derived_phase(base, state.get("phase"), state.get("direction"), warnings)


def _check_success(state, errors, warnings, strict):
    """The ask contract, on a line that states an ask (rules 3 onward).

    Two refusals, both about the line answering the user rather than itself: a
    line that names no success criterion has nothing a conclusion could be
    judged against (the shape checks this layer already had let a report pass
    that answered nothing - measured 2026-10-01: 4 of 11 sampled lines concluded
    with the ask unanswered), and a concluded line whose criteria carry no
    verdict is that same exit with the paperwork of a result. Older lines are
    untouched: they were opened under rules that did not ask for either field."""
    # the contract is keyed on the line stating an ask, not on its rules number:
    # a line that never named the user's words keeps the rules it was opened
    # under, whatever version its state.json carries
    if not str(state.get("ask") or "").strip():
        return
    rows = success_rows(state.get("success"))
    if not rows:
        # the same shape as the evaluation lock: at bootstrap the missing field
        # is the ordinary state of a line that has not started (a warning, and a
        # refusal under `--strict`); past it the line has run something, and a
        # result with no criterion to judge it is the failure this rule exists for
        _soft(errors, warnings,
              strict or str(state.get("phase")) != "bootstrap",
              "no success criteria: state.json `success` names one per part of "
              "the ask, written before any experiment - a line without them "
              "cannot say whether it answered")
        return
    for sid, criterion, verdict, evidence in rows:
        if not sid or not criterion:
            errors.append("a success criterion carries no id or no text")
        if verdict and verdict not in VERDICTS:
            errors.append("success criterion %s: verdict %r is not one of %s"
                          % (sid, verdict, ", ".join(VERDICTS)))
        if verdict in VERDICTS and not evidence:
            errors.append("success criterion %s: a verdict with no evidence "
                          "pointer is an opinion" % sid)
    if str(state.get("phase")) == "concluded":
        unjudged = [sid for sid, _c, verdict, _e in rows if verdict not in VERDICTS]
        if unjudged:
            errors.append("concluded with no verdict for %s: judge each criterion "
                          "(`tezgah-research verdict`) before concluding"
                          % ", ".join(unjudged))
        if unanswered(state) and not (state.get("closed") or {}).get("ack") \
                and not _user_event(state):
            errors.append("concluded with a criterion not met and no "
                          "acknowledgement: record what the user said (`close "
                          "--ack`), or the line is an unanswered ask wearing a "
                          "conclusion")


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
# A path segment may carry parentheses: a Next.js route group is a real
# directory name (`apps/web/app/(group)/settings/page.tsx`), and a
# pattern that stops at the `(` reads that citation - a `sha:path` pair, the
# shape `_resolves` already supports - as a proof that names nothing.
PAIR = re.compile(r"(?<![\w./-])(?:[\w.()-]+/)+[\w.()-]+(?![\w./-])")

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
    an internal research line measured the rule against this
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
    # Every id some row supersedes: those rows are historical, and the line's own
    # doctrine is that a correction is a NEW row rather than an edit. So a path in
    # a superseded row's proof that has since moved is reported, not refused -
    # refusing it would make the correction impossible to land, which is how
    # closing a plan used to break every line that had cited it.
    superseded = set()
    for raw in rows:
        try:
            give = json.loads(raw)
        except ValueError:
            continue
        superseded.update(_supersedes(give)[0])
    # the token-savings rule is a `PROTOCOL_RULES` rule, so an older line keeps
    # the rules it was opened under
    sections = _rules(_state(base)) >= PROTOCOL_RULES
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
        elif cid not in superseded:
            # a superseded row's proof is the historical one and is not
            # re-resolved; the relation is reported once, by the row that
            # supersedes it, naming both ids (`_check_supersedes`)
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
        # A superseded claim is the historical row: the line has corrected it in
        # the row that supersedes it, and that row is the one whose numbers are
        # held to their proof here. Warning on the historical statement too would
        # make a correction that rewords a figure impossible to land (it already
        # cannot edit the row), for a sentence no reader is meant to keep.
        if cid not in superseded:
            _check_claim_numbers(cid, claim, base, repo, errors, warnings, strict)
        _check_claim_raters(cid, claim, base, errors, warnings, strict)
        if sections and cid not in superseded:
            problem = _token_claim_problem(cid, claim, base)
            if problem:
                errors.append(problem)
    _check_supersedes(parsed, errors, warnings, strict)
    if not count:
        warnings.append("no claims recorded yet")
    return count


def _token_claim_problem(cid, claim, base):
    """The refusal for an evidence claim resting on a protocol whose `unit:` is
    tokens and which leaves `tokenizer:` or `bound:` empty, or None. The
    claim's own prose is never read for it: the cited protocol declares what was
    counted, and a token figure is only as good as the counting fixed before the
    run (the gortex adoption, C04)."""
    if claim.get("kind") != "evidence":
        return None
    for h in _experiments_named(_cited(claim.get("proof"))):
        labels = protocol_labels(_note_text(
            os.path.join(base, "experiments", h, "protocol.md")))
        missing = token_problems(labels)
        if missing:
            return ("claim %s rests on experiments/%s, whose protocol counts tokens "
                    "and leaves %s empty" % (cid, h, " and ".join(missing)))
    return None


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
        problem = agent_only_problem(cid, claim, base)
        if problem:
            errors.append(problem)
    elif kind == "derivation":
        for token in named:
            if not _resolves(token, (base,)):
                errors.append("claim %s is a derivation and cites %s, which the "
                              "line itself does not hold" % (cid, token))


def agent_only_problem(cid, claim, base):
    """The refusal of a literature claim whose every cited note is indexed as an
    `agent-report`, or None. Shared by the writer and the checker: an agent's
    summary of a source is not the source, so it can back a literature claim only
    beside a note on the paper or page itself."""
    if claim.get("kind") != "literature" or not claim.get("proof"):
        return None
    classes = {str(row.get("note", "")).strip(): row.get("class") for row in
               _row_objects(os.path.join(base, "literature", "INDEX.jsonl"))}
    cited = []
    for token in _cited(claim["proof"]):
        token = token.rstrip(".,;:)")
        if _under_literature(token, base):
            cited.append(token[len("literature/"):]
                         if token.startswith("literature/") else token)
    if cited and all(classes.get(note) == "agent-report" for note in cited):
        return ("claim %s is a literature claim resting only on agent reports (%s): "
                "cite the note on the paper or page the agent read"
                % (cid, ", ".join(cited)))
    return None


def _check_claim_raters(cid, claim, base, errors, warnings, strict):
    """A claim resting only on judged rows - rows that carry a `rater` - rests on
    at least two raters, or it is one reader's opinion counted as a measurement."""
    rows = []
    for experiment in _experiments_named(_cited(claim.get("proof"))):
        rows += _row_objects(os.path.join(base, "experiments", experiment,
                                          "results.jsonl"))
    raters = {str(r["rater"]) for r in rows if "rater" in r}
    if rows and all("rater" in r for r in rows) and len(raters) < 2:
        _soft(errors, warnings, strict,
              "claim %s rests only on judged rows from %d rater, so no agreement "
              "between readers can be shown" % (cid, len(raters)))



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
        problem = agent_only_problem(cid, claim, base)
        if problem:
            problems.append(problem)
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
    newer = newer_rules(_state(base))
    if newer:
        return claim.get("id"), [newer]
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


def _check_experiments(repo, base, errors, warnings, git, strict, intact=None):
    """`intact` maps an experiment the line's order seal holds, with both files
    still hashing as sealed, to its seal row. Its order is re-derived from git
    like any other, unless the owner sealed it `history-lost` (`_sealed_order`)."""
    intact = intact or {}
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
        _check_protocol(h, proto, errors, warnings, strict, results,
                        _rules(_state(base)) >= PROTOCOL_RULES)
        if not os.path.isfile(results):
            continue
        if not os.path.isfile(os.path.join(d, "analysis.md")):
            errors.append("experiment %s has results but no analysis.md" % h)
        _check_rows(results, "experiment %s" % h, errors, warnings, strict)
        if git and intact.get(h, {}).get("order") == HISTORY_LOST:
            _sealed_order(h, intact[h], errors, warnings, strict)
        elif git:
            _check_protocol_order(repo, h, proto, results, errors, warnings, strict)
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


def _check_protocol(h, path, errors, warnings, strict, results=None, sections=False):
    """A protocol answers what it predicts and what would falsify it.

    `check` reads the file, so it can ask whether both questions are answered at
    all, not whether the answers are right - and that is the difference the layer
    was missing: its own audit measured a protocol whose whole body was "run it"
    passing every check (P2), because existence and commit order were the only
    things read. The class is the warn one, and the reason is in the tree: three
    of this repository's protocols are work orders handed to a read-only agent and
    answer neither question by design, so a refusal would make the honest shape
    the refused one. `--strict` refuses what it cannot see answered, which is what
    a line that wants its predictions provable asks for.

    A line opened under `PROTOCOL_RULES` is read by its sections instead
    (`_check_protocol_sections`), and those rules refuse."""
    try:
        with open(path, encoding="utf-8") as fh:
            text = fh.read()
    except (OSError, UnicodeDecodeError) as exc:
        errors.append("experiment %s: protocol.md cannot be read (%s)" % (h, exc))
        return
    if sections:
        _check_protocol_sections(h, text, results, errors)
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


def protocol_labels(text):
    """{key: value} for the `PROTOCOL_KEYS` a protocol declares.

    A label is a `key: value` line at column 0, the key case-insensitive. Its
    value is the rest of the line plus the lines after it that are indented or
    start with `- `, up to a blank line or the next column-0 line. Headings and
    every other line are prose and are not read. Whitespace in a value is
    collapsed; a key declared twice keeps both values, joined."""
    out, key = {}, None
    for line in text.lstrip("\ufeff").splitlines():
        if not line.strip():
            key = None
        elif line[0].isspace() or line.startswith("- "):
            if key:
                out[key].append(line)
        else:
            found = PROTOCOL_LABEL.match(line)
            key = found.group(1).lower() if found else None
            if key not in PROTOCOL_KEYS:
                key = None
            else:
                out.setdefault(key, []).append(found.group(2))
    return {k: " ".join(" ".join(v).split()) for k, v in out.items()}


TOKEN_WORDS = {"token", "tokens", "tok", "toks", "ktokens"}
TIME_WORDS = {"ms", "s", "sec", "second", "seconds", "latency", "time"}


def _token_unit(unit):
    """True when a `unit:` value counts tokens. The value is lower-cased with
    punctuation, emphasis and `_` read as spaces, and its head - the words before
    the first `per` - is read: a token word anywhere in it (`prompt tokens`,
    `number of tokens`, `input_tokens`), unless its last word is a time
    (`token latency ms`, `token time`). A `/` reads as `per` (`tokens/s`, `ms/token`)."""
    words = re.sub(r"[\W_]+", " ", unit.replace("/", " per ")).lower().split()
    head = words[:words.index("per")] if "per" in words else words
    return bool(head) and bool(TOKEN_WORDS.intersection(head)) \
        and head[-1] not in TIME_WORDS


def token_problems(labels):
    """The labels a protocol counting in tokens leaves empty, or [] - also when
    its `unit:` is not tokens, the one case the two labels are owed in."""
    if not _token_unit(labels.get("unit", "")):
        return []
    return ["`%s:`" % k for k in ("tokenizer", "bound") if not labels.get(k)]


def _headroom_none(value):
    """True when a `headroom:` value projects nothing (`HEADROOM_NONE`)."""
    value = re.sub(r"[*_`~]", "", value).lower().strip().rstrip(" .,;:!?")
    # a nonzero number, not a digit inside a name: `p95 is at the floor` is none
    if re.search(r"(?<![\w.])\d*\.?\d*[1-9]", value):
        return False
    value = HEADROOM_ZERO.sub("0", value)
    return value in HEADROOM_NONE or value.startswith(HEADROOM_NONE_PREFIX)


def _check_protocol_sections(h, text, results, errors):
    """The protocol content rules of a line opened under `PROTOCOL_RULES`, read
    from its declared labels (`protocol_labels`), and refused when broken:

    - `prediction:` and `falsifier:` non-empty, and not the same text once case
      and whitespace are set aside - the hollow protocol the layer audit left
      open (E8 P2);
    - `headroom:` non-empty, written before any arm runs. `n/a` and a reason is an
      answer for a survey with no arms. A value that projects none, with results
      already filed, is refused, because the screen exists to stop that run;
    - when `unit:` is tokens, `tokenizer:` and `bound:` non-empty."""
    labels = protocol_labels(text)
    for name, what in (("metric", "what the run counts"),
                       ("unit", "what it counts in")):
        if not labels.get(name):
            errors.append("experiment %s: protocol.md declares no `%s:`, so nothing "
                          "says %s" % (h, name, what))
    for name in ("prediction", "falsifier"):
        if not labels.get(name):
            errors.append("experiment %s: protocol.md declares no non-empty `%s:` "
                          "label, so the protocol does not say what the run tests"
                          % (h, name))
    same = [re.sub(r"[\W_]+", " ", labels.get(k, "")).strip().lower()
            for k in ("prediction", "falsifier")]
    if same[0] and same[0] == same[1]:
        errors.append("experiment %s: protocol.md's prediction and falsifier say the "
                      "same thing, so no result could tell one from the other" % h)
    headroom = labels.get("headroom", "")
    if not headroom:
        errors.append("experiment %s: protocol.md declares no `headroom:`: before any "
                      "arm runs, say how much the change could move at best, or "
                      "`n/a` and why" % h)
    elif _headroom_none(headroom) and results and _rows(results):
        errors.append("experiment %s: protocol.md's headroom projects none and the "
                      "arms ran anyway - the screen is there to stop that run" % h)
    missing = token_problems(labels)
    if missing:
        errors.append("experiment %s: protocol.md's unit is tokens and leaves "
                      "%s empty, so the count cannot be re-derived"
                      % (h, " and ".join(missing)))


def _check_tracking(repo, base, errors, warnings, strict):
    """The order rule needs a commit, so the check asks about the paths it orders.

    The two files the rule compares are probed, not the line's directory: a
    directory-level ignore says nothing about the files inside it. They are asked
    of the repository that commits them (`_ignored`): the private `.tezgah` one,
    which the project's own ignore of `.tezgah/` does not reach, so a line there is
    reported only when that repository - or a global excludes file - ignores the
    file. With no private repository the project's is asked, and an ignored pair
    there is told the subcommand that creates the private one and commits into it.

    `check-ignore` does not report a path the index already holds (measured on a
    scratch repo), so a pair committed before the move is not reported. The
    message carries the command that fixes the pair it reports, because a plain
    `git add` stages nothing while the path is ignored and a silent no-op looks
    exactly like a commit."""
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
            rel = _ws_rel(repo, path)
            fix = ("`git -C .tezgah add -f %s`" % rel if rel is not None else
                   "`.tezgah` has no git repository of its own - `tezgah-research "
                   "commit %s \"<message>\"` creates it and commits the line there"
                   % os.path.basename(base))
            _soft(errors, warnings, strict,
                  "experiment %s: %s is ignored by %s, so no commit can show the "
                  "protocol predates the results; %s"
                  % (h, name, pattern, fix))


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


def _check_protocol_order(repo, h, proto, results, errors, warnings, strict):
    """protocol.md must have entered the history before results.jsonl, and must
    not have changed after it: a strict add-before-add in HEAD's lineage of every
    history that holds the results (`_answers`), with the protocol's blob
    unchanged since the run. A history git could not read is a warning, which
    `--strict` refuses (E24)."""
    proto_adds, proto_err = _oldest_adds(repo, proto)
    res_adds, res_err = _oldest_adds(repo, results)
    if proto_err or res_err:
        _soft(errors, warnings, strict,
              "experiment %s: git could not be asked about the order (%s)"
              % (h, proto_err or res_err))
        return
    if not any(res_adds.values()):
        warnings.append("experiment %s: results.jsonl is not committed yet, so the "
                        "protocol order cannot be checked" % h)
        return
    if not any(proto_adds.values()):
        errors.append("experiment %s: protocol.md is not committed, so it cannot "
                      "show the plan came before the run" % h)
        return
    answers = _answers(repo, proto_adds, res_adds)
    refused = [top for top, ok in answers.items() if ok is False]
    if refused and not any(proto_adds.get(t) and res_adds.get(t) for t in answers):
        errors.append("experiment %s: protocol.md and results.jsonl were added in "
                      "different histories and neither holds both, so the plan "
                      "cannot be shown to precede the run" % h)
        return
    if refused and all(proto_adds.get(t) == res_adds.get(t) for t in refused):
        errors.append("experiment %s: one commit added both protocol.md and "
                      "results.jsonl, so the plan cannot be shown to precede the "
                      "run" % h)
        return
    if refused:
        errors.append("experiment %s: protocol.md entered the history after "
                      "results.jsonl - a protocol written after the run is not a "
                      "prediction" % h)
        return
    if None in answers.values():
        warnings.append("experiment %s: git could not order the protocol against the "
                        "results" % h)
        return
    # the run is the results' add in a history that ordered the pair itself,
    # else the import that carried both after the project committed the plan
    run = next((t for t in answers if proto_adds.get(t) != res_adds.get(t)),
               next(iter(answers)))
    changed = _changed_after(repo, proto, res_adds[run], beside=results)
    if changed is None:
        _soft(errors, warnings, strict, UNDECIDED_CHANGE % h)
    elif changed:
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
    if not os.path.isdir(literature):
        return
    notes = []
    for here, dirs, files in os.walk(literature):
        dirs[:] = [d for d in dirs if not d.startswith(".")]
        notes += [os.path.relpath(os.path.join(here, f), literature)
                  for f in files if not f.startswith(".")]
    notes = sorted(n for n in notes if n != "INDEX.jsonl")
    # A top-level `.md` note was always read; a nested file or another extension
    # is read since the standards rules, and a line opened before them warns.
    newer = _rules(_state(base)) >= STANDARDS_RULES or strict
    legacy = [n for n in notes if n.endswith(".md") and os.sep not in n]
    index = os.path.join(literature, "INDEX.jsonl")
    if not os.path.isfile(index):
        if legacy or notes:
            _soft(errors, warnings, bool(legacy) or newer,
                  "literature/ holds %d note(s) and no INDEX.jsonl, so nothing says "
                  "which sources were screened, included or left out; migrate writes "
                  "what the notes already carry" % len(notes))
        return
    rows, named = _read_index(index, literature, errors, warnings, strict)
    for note in notes:
        if note not in named:
            _soft(errors, warnings, note in legacy or newer,
                  "literature/%s is not in INDEX.jsonl: a note the index does not "
                  "name is a source no reader can weigh" % note)
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
        if phase == "concluded" or _concluding(base, _state(base)):
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
    if phase != "concluded" and not _concluding(base, _state(base)):
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
    stated = " ".join(line for line in text.lower().splitlines() if "validity" in line)
    unnamed = [t for t in VALIDITY_TYPES if not re.search(r"\b%s\b" % t, stated)]
    if unnamed:
        _soft(errors, warnings, strict,
              "to_human/report.md names no %s validity threat: a report says what "
              "could bias the result (internal), where it stops generalising "
              "(external), whether the measure is the thing asked (construct) and "
              "whether the numbers carry the conclusion (conclusion)"
              % ", ".join(unnamed))
    fixtures = _fixture_claims(base, repo)
    if fixtures and "fixture" not in text.lower():
        _soft(errors, warnings, strict,
              "to_human/report.md carries %d claim(s) resting on a fixture input (%s) "
              "and never says so, so a reader of the report alone takes a generated "
              "input for the running system"
              % (len(fixtures), ", ".join(fixtures[:4])))


# --- the standards rules (STANDARDS_RULES) ------------------------------------
# What the checks above read is the form of a line: files present, fields filled,
# the protocol committed before the results. What they could not read is its
# design: the evaluation locked before the first result, the results left as the
# run wrote them, a review by someone other than the producer, every item of the
# ask answered, and a deliverable produced as compared variants rather than as one
# design redone serially. A line opened before `rules` existed is judged by them
# too, and each finding warns for it instead of refusing: its rows were written
# before the rule existed, and no migration can re-run them in order.

# A commit a session may cite in prose: seven to forty hex characters holding at
# least one digit and one letter, so a date or an English word is not read as one.
SHA_TOKEN = re.compile(r"(?<![\w-])(?=[0-9a-f]*[0-9])(?=[0-9a-f]*[a-f])"
                       r"[0-9a-f]{7,40}(?![\w-])")

# The phrases the order rules refuse with, so a review scored in the same run can
# be compared against them. Read from the error text because the order rules are
# spread over several functions and each speaks its own sentence.
ORDER_MARKS = ("precede the run", "entered the history after",
               "changed after the run", "came before the run",
               "rewritten after the run", "did not enter the history before",
               "was not locked before")

URL = re.compile(r"\S+://\S+")


def _rules(state):
    """The rule set a line was opened under; 1 for a line that predates `rules`."""
    value = state.get("rules") if isinstance(state, dict) else None
    return value if isinstance(value, int) and not isinstance(value, bool) else 1


def _state(base):
    """state.json as an object, or {} when it is missing or unreadable."""
    state, exc = _read_json(os.path.join(base, "state.json"))
    return state if isinstance(state, dict) and not exc else {}


def newer_rules(state):
    """The refusal for a line a later tezgah wrote, or None.

    A `rules` above `RULES` names rules this code does not implement. Reading the
    line by the rules it does know would pass what the later set refuses, and a
    writer would append rows judged by the older set. So the line is refused by
    name, before any rule reads it."""
    found = _rules(state)
    if found <= RULES:
        return None
    return ("state.json rules %d is newer than the rules this tezgah implements (%d): "
            "a later tezgah wrote this line, so it is refused rather than read as if "
            "current - upgrade tezgah to read or write it" % (found, RULES))


def _concluding(base, state):
    """True once a line is delivering: concluded, deciding to conclude, or holding
    its report. The review and report rules read this rather than `phase` alone:
    a line that ships `to_human/report.md` and stays at `outer` was never asked for
    either, which is how a line passed `check --strict` with no review at all."""
    return (state.get("phase") == "concluded" or state.get("direction") == "conclude"
            or os.path.isfile(os.path.join(base, "to_human", "report.md")))


def file_versions(repo, path):
    """[(sha, text)] of every committed version of `path`, oldest first; [] when git
    cannot say. The append-only rule compares versions, which the added/last-touched
    pair cannot. The project's history is read first and the private `.tezgah`
    repository's after it, like `added_commits`: a line committed in the project
    before the move has its older versions there.

    The order rules read HEAD's lineage; this reads every ref of the private
    repository (`--all`), because it looks for a rewrite and not an order: a row
    amended away while a tag keeps the old commit is a result rewritten after the
    run, which HEAD alone no longer shows (an internal research decision). A side
    ref can only add a version, so it can refuse a line and never pass one."""
    return [v for top, rel in _histories(repo, path)
            for v in _versions(top, rel, ("--all",) if top != repo else ())]


def _versions(top, rel, extra=()):
    """[(sha, text)] of `rel`'s committed versions in one history, oldest first;
    `extra` names the revisions to read (`--all`, an anchor) when not HEAD."""
    pairs, _err = _named_log(top, rel, extra)
    versions = []
    for sha, names in reversed(pairs):
        for name in names:
            text, err = _git_out(top, "show", "%s:%s" % (sha, name))
            if not err:
                versions.append((sha, text))
                break
    return versions


def _check_order(repo, label, before, after, errors, warnings, hard):
    """`before` entered the history in a commit strictly before the one that added
    `after`: the protocol-before-results rule, for any pair of files. Every
    history that holds `after`'s add has to order it (`_answers`); a pair split
    across the two with neither holding both is not shown to precede, never a
    pass. A history git could not read refuses where `hard` does (E24)."""
    b_adds, b_err = _oldest_adds(repo, before)
    a_adds, a_err = _oldest_adds(repo, after)
    if b_err or a_err:
        _soft(errors, warnings, hard, "%s: git could not be asked about the order "
              "(%s)" % (label, b_err or a_err))
        return
    if not any(a_adds.values()):
        return
    names = (os.path.basename(before), os.path.basename(after))
    if not any(b_adds.values()):
        _soft(errors, warnings, hard, "%s: %s is not committed, so it cannot show it "
              "came before %s" % ((label,) + names))
        return
    answers = _answers(repo, b_adds, a_adds)
    if False in answers.values():
        _soft(errors, warnings, hard, "%s: %s did not enter the history before %s, so "
              "it cannot be shown to precede what it judges" % ((label,) + names))
    elif None in answers.values():
        warnings.append("%s: git could not order %s against %s" % ((label,) + names))


def _check_append_only(repo, label, path, errors, warnings, hard):
    """Every committed version of `path` starts with the rows of the one before it,
    and so does the working copy: a row changed or removed after it was committed
    is a result rewritten after the run, and nothing else in the line shows it."""
    versions = [text for _sha, text in file_versions(repo, path)]
    current, exc = _committed_text(path)
    if not exc:
        versions.append(current)
    for older, newer in zip(versions, versions[1:]):
        old = [line for line in older.splitlines() if line.strip()]
        new = [line for line in newer.splitlines() if line.strip()]
        if new[:len(old)] != old:
            _soft(errors, warnings, hard, "%s was rewritten after the run: a committed "
                  "row changed or went missing, and results are append-only - a "
                  "correction is a new row" % label)
            return


def _locks(text):
    """True when a state.json text holds an evaluation with a metric and a
    baseline."""
    try:
        state = json.loads(text)
    except ValueError:
        return False
    evaluation = state.get("evaluation") if isinstance(state, dict) else None
    return isinstance(evaluation, dict) and all(
        str(evaluation.get(k, "")).strip() for k in ("metric", "baseline"))


def _first_lock(top, rel, extra=()):
    """The first commit of one history whose state.json locks, or None."""
    return next((sha for sha, text in _versions(top, rel, extra) if _locks(text)),
                None)


def _evaluation_commit(repo, path):
    """{top: the first commit of that history whose state.json locks a metric and
    a baseline, or None}, the project's history first."""
    return {top: _first_lock(top, rel) for top, rel in _histories(repo, path)}


def _check_evaluation_order(repo, base, state, errors, warnings, strict):
    """The evaluation is locked before the first result, and `locked_at` names a
    commit the history holds. `_check_evaluation` reads that the fields are filled;
    this reads when: a metric and a baseline committed after the results are the
    criterion the results were measured against after the fact."""
    hard = strict or _rules(state) >= STANDARDS_RULES
    evaluation = state.get("evaluation")
    if not isinstance(evaluation, dict):
        return
    for token in SHA_TOKEN.findall(str(evaluation.get("locked_at", ""))):
        if is_ancestor(repo, token, "HEAD") is not True:
            _soft(errors, warnings, hard,
                  "state.json evaluation locked_at names %s, which is not a commit "
                  "this history reaches, so the lock it claims cannot be read" % token)
    locks = None
    path = os.path.join(base, "state.json")
    for h in _experiment_names(base):
        results = os.path.join(base, "experiments", h, "results.jsonl")
        added, err = _oldest_adds(repo, results)
        if err or not any(added.values()):
            continue
        if locks is None:
            locks = _evaluation_commit(repo, path)
        # every history holding the results' add orders the lock before it; a
        # lock in one history and the results in the other only was read as None
        # and passed (claim C07), and an unanswerable order passed silently (E07)
        answers = _answers(repo, locks, added)
        if False in answers.values():
            _soft(errors, warnings, hard,
                  "experiment %s: the evaluation was not locked before the first "
                  "results row - no committed state.json holding the metric and the "
                  "baseline precedes the commit that added its results.jsonl" % h)
        elif None in answers.values():
            _soft(errors, warnings, strict,
                  "experiment %s: git could not order the evaluation lock against "
                  "the results" % h)


def _experiment_names(base):
    exps = os.path.join(base, "experiments")
    try:
        names = sorted(os.listdir(exps))
    except OSError:
        return []
    return [h for h in names if not h.startswith(".")
            and os.path.isdir(os.path.join(exps, h))]


def _check_results_append_only(repo, base, state, errors, warnings, strict):
    hard = strict or _rules(state) >= STANDARDS_RULES
    for h in _experiment_names(base):
        path = os.path.join(base, "experiments", h, "results.jsonl")
        if os.path.isfile(path):
            _check_append_only(repo, "experiment %s: results.jsonl" % h, path,
                               errors, warnings, hard)


# --- variants ------------------------------------------------------------------
# A deliverable a reader acts on - a design, a plan, an analysis, code - is
# produced as variants and compared under criteria committed before any variant
# was scored, and the decision names every variant it rejected and the criterion
# that rejected it. One design gets inflated ratings beside nothing (Tohidi et al.
# 2006), and serial versions fixate on the first option (Dow et al. 2010); the
# layer used to hold exactly that, v3 -> v4 -> v5 of one plan never compared.

def deliverable_problems(deliverable):
    """(problems, variants needed) for `state.json`'s deliverable declaration."""
    if not isinstance(deliverable, dict):
        return (["state.json deliverable is a %s, not the object naming what the line "
                 "delivers" % type(deliverable).__name__], 0)
    problems = []
    kind = deliverable.get("kind")
    if kind not in DELIVERABLE_KINDS:
        problems.append("state.json deliverable kind %r is not one of %s"
                        % (kind, ", ".join(DELIVERABLE_KINDS)))
    ask = deliverable.get("ask")
    if ask is not None and (not isinstance(ask, list) or not all(
            isinstance(item, str) and item.strip() for item in ask)):
        problems.append("state.json deliverable ask is not a list of the ask's items")
    default = {"code": 2}.get(kind, 3) if kind in VARIANT_KINDS else 0
    need = deliverable.get("min_variants", default)
    if not isinstance(need, int) or isinstance(need, bool) or need < 0:
        problems.append("state.json deliverable min_variants %r is not a count"
                        % (need,))
        need = default
    elif need < default and not str(deliverable.get("single_variant_reason",
                                                    "")).strip():
        problems.append("state.json deliverable min_variants %d is below the %d a %s "
                        "takes, and no single_variant_reason says why no alternative "
                        "was considered" % (need, default, kind))
    return problems, need


def _decision_dirs(base):
    root_dir = os.path.join(base, "decisions")
    try:
        names = sorted(os.listdir(root_dir))
    except OSError:
        return []
    return [(n, os.path.join(root_dir, n)) for n in names
            if not n.startswith(".") and os.path.isdir(os.path.join(root_dir, n))]


def load_decision(ddir):
    """(criteria by id, variants by id, problems) of one decision directory. The
    comparison writer and the checker both start here, so a cell is judged against
    the same criteria and the same variants on both paths."""
    problems, criteria, variants = [], {}, {}
    doc, exc = _read_json(os.path.join(ddir, "criteria.json"))
    if exc or not isinstance(doc, dict):
        problems.append("criteria.json does not parse (%s)" % (exc or "not an object"))
        doc = {}
    rows = doc.get("criteria") if doc else []
    if doc and (not isinstance(rows, list) or not rows):
        problems.append("criteria.json names no criteria")
        rows = []
    for n, row in enumerate(rows, 1):
        cid = str(row.get("id", "")).strip() if isinstance(row, dict) else ""
        if not cid:
            problems.append("criteria.json criterion %d carries no id" % n)
            continue
        if cid in criteria:
            problems.append("criteria.json repeats criterion %s" % cid)
        if row.get("kind") not in CRITERION_KINDS:
            problems.append("criterion %s kind %r is not one of %s"
                            % (cid, row.get("kind"), ", ".join(CRITERION_KINDS)))
        if row.get("direction") not in CRITERION_DIRECTIONS:
            problems.append("criterion %s direction %r is not one of %s"
                            % (cid, row.get("direction"),
                               ", ".join(CRITERION_DIRECTIONS)))
        criteria[cid] = row
    for n, row in enumerate(_row_objects(os.path.join(ddir, "variants.jsonl")), 1):
        vid = str(row.get("id", "")).strip()
        if not vid:
            problems.append("variants.jsonl row %d carries no id" % n)
            continue
        if vid in variants:
            problems.append("variants.jsonl repeats variant %s" % vid)
        status = row.get("status")
        if status not in VARIANT_STATUSES:
            problems.append("variant %s status %r is not one of %s"
                            % (vid, status, ", ".join(VARIANT_STATUSES)))
        elif status == "dropped" and not str(row.get("drop_reason", "")).strip():
            problems.append("variant %s is dropped and says not why" % vid)
        elif status == "produced" and not str(row.get("artifact", "")).strip():
            problems.append("variant %s is produced and names no artifact" % vid)
        variants[vid] = row
    if doc and doc.get("baseline_variant") not in variants:
        problems.append("criteria.json baseline_variant %r is not a variant in "
                        "variants.jsonl: the status quo every option is compared "
                        "against is one of the variants" % (doc.get("baseline_variant"),))
    return criteria, variants, problems


def comparison_problems(row, criteria, variants, base, repo):
    """The reasons one variants x criteria cell cannot be recorded; [] when it can.
    The writer (`append_comparison`) and the checker (`_check_decision`) both call
    this, so neither can accept a cell the other refuses."""
    if not isinstance(row, dict):
        return ["a comparison cell is a JSON object, not a %s" % type(row).__name__]
    problems = []
    vid, cid = row.get("variant"), row.get("criterion")
    variant = variants.get(vid) if isinstance(vid, str) else None
    if variant is None or variant.get("status") != "produced":
        problems.append("cell names variant %r, which is not a produced variant in "
                        "variants.jsonl" % (vid,))
    if not isinstance(cid, str) or cid not in criteria:
        problems.append("cell names criterion %r, which criteria.json does not "
                        "define" % (cid,))
    has_value, skipped = "value" in row, row.get("not_checked")
    if has_value == (skipped is not None):
        problems.append("cell carries %s: a cell is a value with its source, or "
                        "not_checked with the reason"
                        % ("both value and not_checked" if has_value
                           else "neither value nor not_checked"))
    elif not has_value and (not isinstance(skipped, str) or not skipped.strip()):
        problems.append("cell is not_checked and gives no reason")
    elif has_value:
        source = row.get("source")
        if not isinstance(source, str) or not source.strip():
            problems.append("cell carries a value and no source")
        else:
            for token in _cited(URL.sub(" ", source)):
                if not _resolves(token, (base, repo)):
                    problems.append("cell source %s is not in this line or the "
                                    "repository" % token)
    rater = row.get("rater")
    if rater is not None and (not isinstance(rater, str) or not rater.strip()):
        problems.append("cell carries an empty rater")
    return problems


def append_comparison(repo, slug, decision, row):
    """problems; [] exactly when the cell was appended to
    `decisions/<decision>/comparison.jsonl`. Judged under the lock, by the rule the
    checker applies, against the criteria and variants read inside it."""
    if not valid_slug(slug) or not valid_slug(decision):
        return ["not a research slug and decision id: %r %r" % (slug, decision)]
    newer = newer_rules(_state(line_dir(repo, slug)))
    if newer:
        return [newer]
    ddir = os.path.join(line_dir(repo, slug), "decisions", decision)
    if not os.path.isdir(ddir):
        return ["decisions/%s does not exist: write and commit its criteria.json "
                "and variants.jsonl first" % decision]
    path = os.path.join(ddir, "comparison.jsonl")
    created = not os.path.isfile(path)
    with open(path, "a+b") as handle:
        problem = _locked(handle, "comparison.jsonl")
        if problem:
            return [problem]
        criteria, variants, _ = load_decision(ddir)
        problems = comparison_problems(row, criteria, variants, line_dir(repo, slug),
                                       repo)
        if problems:
            if created and os.path.getsize(path) == 0:
                os.remove(path)
            return problems
        truncate_to_committed(handle)
        handle.write(json.dumps(row).encode("utf-8") + b"\n")
    return []


def _score(rows):
    """The mean numeric value of a cell's rows, or None when none is a number."""
    values = []
    for row in rows:
        value = row.get("value")
        if isinstance(value, bool):
            continue
        try:
            values.append(float(value))
        except (TypeError, ValueError):
            pass
    return sum(values) / len(values) if values else None


def dominated_by(chosen, produced, criteria, cells):
    """The produced variant at least as good as `chosen` on every criterion and
    better on one, or None. Decided only when every criterion is numeric with a
    max/min direction; a pass/fail or unscored criterion may be what it won on."""
    if not criteria or any(c.get("direction") not in ("max", "min")
                           for c in criteria.values()):
        return None

    def vector(vid):
        out = []
        for cid, crit in criteria.items():
            score = _score(cells.get((vid, cid), []))
            if score is None:
                return None
            out.append(score if crit["direction"] == "max" else -score)
        return out

    mine = vector(chosen)
    if mine is None:
        return None
    for other in produced:
        theirs = vector(other) if other != chosen else None
        if theirs and all(t >= m for t, m in zip(theirs, mine)) \
                and any(t > m for t, m in zip(theirs, mine)):
            return other
    return None


def _artifact_path(artifact, base, repo):
    for root_dir in (base, repo):
        path = os.path.join(root_dir, artifact)
        if os.path.exists(path):
            return path
    return None


def _digest(path):
    import hashlib
    with open(path, "rb") as fh:
        return hashlib.sha256(fh.read()).hexdigest()


def _mentions(token, text):
    return re.search(r"(?<![\w.-])%s(?![\w.-])" % re.escape(token), text) is not None


def _check_decision(repo, base, name, ddir, need, errors, warnings, strict, git,
                    concluding):
    label = "decisions/%s" % name
    missing = [f for f in DECISION_FILES[:2]
               if not os.path.isfile(os.path.join(ddir, f))]
    if missing:
        errors.append("%s is missing %s: the criteria and the variants are written "
                      "before any cell" % (label, " and ".join(missing)))
        return
    criteria, variants, problems = load_decision(ddir)
    errors.extend("%s: %s" % (label, p) for p in problems)
    produced = [v for v, row in variants.items() if row.get("status") == "produced"]
    if len(produced) < need:
        errors.append("%s: %d produced variant(s), and this deliverable is compared "
                      "across at least %d - one option with nothing beside it is not "
                      "a comparison" % (label, len(produced), need))
    digests = {}
    for vid in produced:
        artifact = str(variants[vid].get("artifact", "")).strip()
        if artifact.startswith("orx:"):
            continue
        if artifact.startswith("git:"):
            if git and _git(repo, "rev-parse", "--verify", "-q",
                            artifact[4:] + "^{commit}")[1]:
                errors.append("%s: variant %s names %s, which this history does not "
                              "hold" % (label, vid, artifact))
            continue
        path = _artifact_path(artifact, base, repo)
        if path is None:
            errors.append("%s: variant %s artifact %s is not in this line or the "
                          "repository" % (label, vid, artifact))
        elif os.path.isfile(path):
            digest = _digest(path)
            if digest in digests:
                errors.append("%s: variants %s and %s are the same file, and a "
                              "renamed copy is not an alternative"
                              % (label, digests[digest], vid))
            digests.setdefault(digest, vid)
    cpath = os.path.join(ddir, "comparison.jsonl")
    decided = os.path.isfile(os.path.join(ddir, "decision.md"))
    cells = {}
    text, _exc = _committed_text(cpath)
    for n, raw in enumerate((text or "").splitlines(), 1):
        if not raw.strip():
            continue
        try:
            row = json.loads(raw)
        except ValueError as exc:
            errors.append("%s: comparison.jsonl:%d does not parse (%s)" % (label, n, exc))
            continue
        for problem in comparison_problems(row, criteria, variants, base, repo):
            errors.append("%s: comparison.jsonl:%d %s" % (label, n, problem))
        if isinstance(row, dict):
            cells.setdefault((row.get("variant"), row.get("criterion")), []).append(row)
    gaps = ["%s x %s" % (v, c) for v in produced for c in criteria
            if (v, c) not in cells]
    if gaps:
        _soft(errors, warnings, strict or decided or concluding,
              "%s: %d cell(s) of the variants x criteria matrix are neither measured "
              "nor marked not_checked (%s)" % (label, len(gaps), ", ".join(gaps[:6])))
    thin = []
    for (vid, cid), rows in sorted(cells.items(), key=str):
        valued = [r for r in rows if "value" in r]
        raters = {r.get("rater") for r in valued if isinstance(r.get("rater"), str)
                  and r["rater"].strip()}
        if valued and criteria.get(cid, {}).get("kind") == "judged" and len(raters) < 2:
            thin.append("%s x %s" % (vid, cid))
    if thin:
        _soft(errors, warnings, strict,
              "%s: %d judged cell(s) carry fewer than two distinct raters (%s), so "
              "no agreement between readers can be shown"
              % (label, len(thin), ", ".join(thin[:6])))
    if git and os.path.isfile(cpath):
        _check_order(repo, label, os.path.join(ddir, "criteria.json"), cpath,
                     errors, warnings, True)
        _check_append_only(repo, "%s: comparison.jsonl" % label, cpath, errors,
                           warnings, True)
    if not decided:
        _soft(errors, warnings, strict or concluding,
              "%s has no decision.md, so no variant is chosen and no rejected one "
              "says what ruled it out" % label)
        return
    body = _note_text(os.path.join(ddir, "decision.md"))
    found = re.search(r"(?im)^\W*chosen\W*:\s*`?([\w.-]+)", body)
    chosen = found.group(1) if found else None
    if chosen not in produced:
        errors.append("%s: decision.md chosen %r is not a produced variant"
                      % (label, chosen))
    for vid in produced:
        if vid == chosen:
            continue
        lines = [line for line in body.splitlines() if _mentions(vid, line)]
        if not any(_mentions(cid, line) for line in lines for cid in criteria):
            errors.append("%s: decision.md rejects %s on no criterion: name the "
                          "criterion id that ruled it out on its line" % (label, vid))
    if not re.search(r"(?im)^\W*flip\W*:", body):
        errors.append("%s: decision.md names no `flip:` condition - the result that "
                      "would reverse the choice" % label)
    if chosen in produced:
        better = dominated_by(chosen, produced, criteria, cells)
        if better:
            errors.append("%s: the chosen variant %s is dominated by %s, which is at "
                          "least as good on every criterion and better on one"
                          % (label, chosen, better))


def _deliverable_path(state):
    deliverable = state.get("deliverable")
    return (deliverable.get("path") if isinstance(deliverable, dict) else None) or None


def _deliverable_file(repo, base, state):
    """The deliverable as one file: the realpath `_artifact_path` resolves it to
    (line-relative first, then repository-relative), else the declared path as
    written. Two lines each delivering their own `to_human/report.md` name two
    files, not one piece of work."""
    path = _deliverable_path(state)
    found = _artifact_path(path, base, repo) if path else None
    return os.path.realpath(found) if found else path


def serial_twins(repo, slug, state):
    """The other lines sharing this one's deliverable file or its question: the
    serial versions of one piece of work, which are compared, not replaced."""
    def key(name, st):
        return (_deliverable_file(repo, line_dir(repo, name), st),
                " ".join(str(st.get("question", "")).lower().split()))

    mine = key(slug, state)
    out = []
    for other in slugs(repo):
        if other == slug:
            continue
        theirs = key(other, _state(line_dir(repo, other)))
        if (mine[0] and mine[0] == theirs[0]) or (mine[1] and mine[1] == theirs[1]):
            out.append(other)
    return out


def _check_serial(repo, slug, base, state, errors, warnings, strict):
    """A line that supersedes another carries the old line's deliverable as a
    variant, and a line repeating another's deliverable or question says so."""
    hard = strict or _rules(state) >= STANDARDS_RULES
    old = state.get("supersedes")
    carried = {row.get("line") for _n, ddir in _decision_dirs(base)
               for row in _row_objects(os.path.join(ddir, "variants.jsonl"))}
    if old is not None:
        if old not in slugs(repo):
            errors.append("state.json supersedes %r, which is not a research line "
                          "here" % (old,))
        elif old not in carried:
            _soft(errors, warnings, strict or _concluding(base, state),
                  "state.json supersedes %s and no variant carries its deliverable "
                  "(a variants.jsonl row with \"line\": %s): the old version is "
                  "compared, not silently replaced" % (old, json.dumps(old)))
    mine = (str(state.get("created", "")), slug)
    path = _deliverable_file(repo, base, state)
    for twin in serial_twins(repo, slug, state):
        theirs = _state(line_dir(repo, twin))
        if twin == old or theirs.get("supersedes") == slug:
            continue
        if (str(theirs.get("created", "")), twin) < mine:
            # one deliverable path is one piece of work; one question may be two
            # lines on purpose, which only a reader can tell
            same = bool(path) and path == _deliverable_file(
                repo, line_dir(repo, twin), theirs)
            _soft(errors, warnings, strict or (hard and same),
                  "shares its %s with line %s and does not supersede it: open it "
                  "with `init --supersedes %s` and compare %s's deliverable as a "
                  "variant instead of redoing it"
                  % ("deliverable" if same else "question", twin, twin, twin))


def _check_decisions(repo, slug, base, state, errors, warnings, strict, git):
    concluding = _concluding(base, state)
    need = 0
    deliverable = state.get("deliverable")
    if deliverable is None:
        if concluding:
            _soft(errors, warnings, strict or _rules(state) >= STANDARDS_RULES,
                  "state.json declares no deliverable, so nothing says whether this "
                  "line delivers a design, plan, analysis or code that is owed "
                  "compared variants, or only findings")
    else:
        problems, need = deliverable_problems(deliverable)
        errors.extend(problems)
    decisions = _decision_dirs(base)
    if need > 1 and not decisions:
        _soft(errors, warnings,
              strict or (concluding and _rules(state) >= STANDARDS_RULES),
              "state.json deliverable is a %s and decisions/ holds no comparison: "
              "one version with no compared alternative is not a finished line "
              "(%d variants, criteria committed before any cell)"
              % (deliverable.get("kind"), need))
    for name, ddir in decisions:
        _check_decision(repo, base, name, ddir, max(need, 2), errors, warnings,
                        strict, git, concluding)
    _check_serial(repo, slug, base, state, errors, warnings, strict)
    closed = state.get("closed")
    if closed is not None and (not isinstance(closed, dict)
                               or not str(closed.get("limit", "")).strip()):
        errors.append("state.json closed records no limit: a line closed over "
                      "unfinished work says what was left and why")


def _ask_traced(n, item, texts, claims):
    aid = "A%d" % n
    norm = " ".join(item.lower().split())
    if any(_mentions(aid, t) or norm in " ".join(t.lower().split()) for t in texts):
        return True
    for claim in claims:
        trace = claim.get("trace")
        for entry in trace if isinstance(trace, list) else [trace]:
            if isinstance(entry, str) and entry.strip() in (aid, item.strip()):
                return True
    return False


def _check_trace(base, state, errors, warnings, strict):
    """Every item of the ask is answered: in the report, a decision, or a claim's
    `trace` - or written as `A<n> not delivered: <reason>`. A report that answers
    three of four asks reads as a complete answer unless something counts them."""
    deliverable = state.get("deliverable")
    ask = deliverable.get("ask") if isinstance(deliverable, dict) else None
    if not isinstance(ask, list) or not _concluding(base, state):
        return
    texts = [_note_text(os.path.join(base, "to_human", "report.md"))]
    texts += [_note_text(os.path.join(d, "decision.md")) for _n, d in _decision_dirs(base)]
    claims = _row_objects(os.path.join(base, "claims.jsonl"))
    lost = ["A%d" % n for n, item in enumerate(ask, 1)
            if isinstance(item, str) and item.strip()
            and not _ask_traced(n, item, texts, claims)]
    if lost:
        _soft(errors, warnings, strict or _rules(state) >= STANDARDS_RULES,
              "state.json deliverable ask item(s) %s appear in no report, decision or "
              "claim trace: each item is delivered, or written as `A<n> not "
              "delivered: <reason>`" % ", ".join(lost))


def _check_standards(repo, slug, base, errors, warnings, strict, git):
    """Every standards rule that reads the line as a whole, in one place."""
    state = _state(base)
    _check_decisions(repo, slug, base, state, errors, warnings, strict, git)
    _check_trace(base, state, errors, warnings, strict)
    if git:
        _check_evaluation_order(repo, base, state, errors, warnings, strict)
        _check_results_append_only(repo, base, state, errors, warnings, strict)


def _check_review_integrity(base, errors, warnings, strict):
    """A review names who wrote the line and who judged it, and they differ; it
    records what it found; and it does not score the line's integrity above what
    this same run found. Read last, because the last rule compares the review with
    every order finding the run collected."""
    review, exc = _read_json(os.path.join(base, "to_human", "review.json"))
    if exc or not isinstance(review, dict):
        return
    state = _state(base)
    reviewer = str(review.get("reviewer") or "").strip()
    producer = str(review.get("producer") or state.get("producer") or "").strip()
    if not reviewer or not producer:
        _soft(errors, warnings, strict or _rules(state) >= STANDARDS_RULES,
              "to_human/review.json names no %s: a review says who produced the line "
              "and who judged it, and those are two readers"
              % ("reviewer" if not reviewer else "producer"))
    elif reviewer == producer:
        errors.append("to_human/review.json reviewer %r is the producer: a line graded "
                      "by the session that wrote it is not reviewed" % reviewer)
    if review.get("findings") == []:
        _soft(errors, warnings, strict,
              "to_human/review.json records no finding at all: a review that found "
              "nothing is indistinguishable from one that did not look")
    dims = review.get("dimensions") if isinstance(review.get("dimensions"), dict) else {}
    high = [d for d in ("exploration_integrity", "methodological_rigour")
            if isinstance(dims.get(d), int) and dims[d] > 3]
    order = [e for e in errors if any(mark in e for mark in ORDER_MARKS)]
    if order and high:
        errors.append("to_human/review.json scores %s above 3 while this check refuses "
                      "the line's order (%d finding(s), first: %s): a review cannot "
                      "grade higher than the checker found"
                      % (" and ".join(high), len(order), order[0][:80]))


def check_line(repo, slug, git=True, strict=False):
    """(errors, warnings) for one research line. `git=False` skips the checks that
    need git history, for callers that must stay cheap (the session context).
    `strict=True` turns every guarantee the checker cannot decide into an error."""
    base = line_dir(repo, slug)
    errors, warnings = [], []
    if not os.path.isdir(base):
        return ["%s does not exist" % base], warnings
    newer = newer_rules(_state(base))
    if newer:
        return [newer], warnings
    for name in STATE_FILES:
        if not os.path.isfile(os.path.join(base, name)):
            errors.append("%s is missing" % name)
    _check_state(base, errors, warnings, strict)
    _check_findings(base, errors, warnings, strict)
    _check_claims(base, errors, warnings, roots=(repo,), strict=strict)
    _check_predictions(repo, base, errors, warnings, strict, git)
    seal_errors, intact = _check_seal(base)
    errors.extend(seal_errors)
    _check_experiments(repo, base, errors, warnings, git, strict, intact)
    _check_literature(base, errors, warnings, strict)
    phase = _phase(base)
    _check_review(base, phase, errors, warnings, strict)
    _check_report(repo, base, phase, errors, warnings, strict)
    _check_standards(repo, slug, base, errors, warnings, strict, git)
    if git:
        _check_tracking(repo, base, errors, warnings, strict)
    _check_review_integrity(base, errors, warnings, strict)
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


def _check_derived_phase(base, phase, direction, warnings):
    """A stored phase or direction the line's artifacts contradict, as a warning.

    The warn class, and never an error even under `--strict`: the stored field is
    the author's declared intent, and a derivation simpler than that judgement
    must not fail a line the field says is fine (`_open_reasons` is what reads the
    field when a caller has to decide whether a line is finished). What it does
    say is when the field stopped describing the line - the class this line's own
    source named as two authorities - so the next session reads where the work
    actually is instead of trusting a field nobody updated.

    `direction` is the outer loop's choice, so only its two artifact-bound states
    are derived: findings written (`outer`) mean the loop already chose, so
    `undecided` is stale, and a delivered line (`concluded`) has chosen
    `conclude`. Which of deepen, broaden or pivot is right is a judgement no
    artifact holds, so none of them is second-guessed."""
    derived = derived_phase(base)
    if phase in PHASES and PHASES.index(derived) > PHASES.index(phase):
        warnings.append("state.json phase %s is behind the phase the line's "
                        "artifacts show (%s), so the declared phase stopped "
                        "describing the line" % (phase, derived))
    want = {"outer": "a direction other than undecided",
            "concluded": "conclude"}.get(derived)
    if want and direction in DIRECTIONS and (
            direction == "undecided"
            or (derived == "concluded" and direction != "conclude")):
        warnings.append("state.json direction %s disagrees with the line's "
                        "artifacts (%s), which show %s, so the declared direction "
                        "stopped describing the line" % (direction, derived, want))


def check(repo, slug=None, git=True, strict=False, all_lines=True):
    """{slug: {"errors": [...], "warnings": [...]}} for one line or every line.

    With `all_lines=False` and no slug, a line under `done/` is read by its order
    seal alone (`done_seal`), not re-checked, and appears only when that read
    fails: the default no-slug `check` and the session note report the open
    lines, and `check --all-lines` re-runs the closed ones (ADR 015)."""
    out = {}
    for name in ([slug] if slug else slugs(repo)):
        if not slug and not all_lines and sealed(repo, name):
            errors = done_seal(repo, name)[0]
            if errors:
                out[name] = {"errors": errors, "warnings": []}
            continue
        errors, warnings = check_line(repo, name, git=git, strict=strict)
        out[name] = {"errors": errors, "warnings": warnings}
    return out


def done_seal(repo, slug):
    """(errors, carries a seal) for a line under `done/`, read by its order seal
    alone. A state.json that does not parse is an error, and so is a seal of the
    wrong shape (`_check_seal`), so a broken record never silences the line; a
    line with no seal answers ([], False): unsealed, not checked."""
    base = line_dir(repo, slug)
    state, exc = _read_json(os.path.join(base, "state.json"))
    if exc or not isinstance(state, dict):
        return ["state.json does not parse (%s), so the line's seal cannot be read"
                % (exc or "not an object")], False
    if SEAL not in state:
        return [], False
    return _check_seal(base)[0], True


def failing(repo, git=False):
    """(slug, error) pairs, for a one-line session note. Structural only by
    default: the session context must not pay for git history. A line under
    `done/` is read by its seal hashes alone (`check` with `all_lines=False`), and
    an unsealed one adds nothing (plan 058 part 4)."""
    return [(slug, err) for slug, row in check(repo, git=git, all_lines=False).items()
            for err in row["errors"]]


# --- the order seal ----------------------------------------------------------
# A concluded or closed line carries `state.json` `order_seal`: per experiment,
# the sha256 of its `protocol.md` and `results.jsonl` (`_digest`), with the add
# commits beside them as information only. The seal stores no order verdict:
# while both blobs still hash as sealed, `check_line` re-derives the order from
# git, so a line closed before its results were committed is not frozen with a
# "not committed yet" answer - committing them afterwards settles it. The hashes
# are verified on every run, git or not, so a session note (`failing`) sees a
# post-conclusion edit. The one stored verdict is the owner's `history-lost`
# (`retro_seal`), for an order the lost history left undecidable.
# Named `order_seal` because `sealed()` already means "the line sits under done/".
# ponytail: the seal lives in the line's own state.json, so an agent that edits
# `results.jsonl` can recompute it there too; it catches an edit, not a forger -
# a seal outside the line's reach (a signed or remote record) is the ceiling.
SEAL = "order_seal"
HISTORY_LOST = "history-lost"

# The order findings a lost history produces and no commit can repair: git
# cannot be asked, the pair sits in two histories neither of which holds both,
# or git cannot place one version against the other. A refusal of a recorded
# order - one commit adding both, a protocol added or changed after the run -
# and a file not committed yet are not in this class: `retro_seal` refuses them.
LOST_HISTORY = ("git could not be asked about the order",
                "were added in different histories and neither holds both",
                "git could not order the protocol against the results",
                "git cannot tell whether protocol.md changed after the run")


def _seal_files(base):
    """{experiment: (protocol path, results path or None)} for every experiment
    holding a protocol.md - the set a seal covers."""
    exps = os.path.join(base, "experiments")
    try:
        names = sorted(os.listdir(exps))
    except OSError:
        return {}
    out = {}
    for h in names:
        proto = os.path.join(exps, h, "protocol.md")
        results = os.path.join(exps, h, "results.jsonl")
        if not h.startswith(".") and os.path.isfile(proto):
            out[h] = (proto, results if os.path.isfile(results) else None)
    return out


def _last_add(repo, path):
    """The newest history's oldest add of `path`, informational in a seal."""
    adds, _err = _oldest_adds(repo, path)
    return next((sha for sha in reversed(list(adds.values())) if sha), None)


def _seal_rows(repo, base):
    """{experiment: seal row}: the blob hashes of every experiment holding a
    protocol.md, and the add commits of a run one, informational only."""
    out = {}
    for h, (proto, results) in _seal_files(base).items():
        row = {"protocol": _digest(proto),
               "results": _digest(results) if results else None}
        if results:
            row["commits"] = {"protocol": _last_add(repo, proto),
                              "results": _last_add(repo, results)}
        out[h] = row
    return out


def _check_seal(base):
    """(errors, {experiment: intact seal row}) for a line carrying an order seal.

    Hashing only, no git: an experiment whose protocol.md or results.jsonl no
    longer hashes as sealed, one the seal holds that is gone, and one added after
    the seal are refused, and so is a seal of the wrong shape. An unsealed line
    answers ([], {})."""
    state = _state(base)
    if SEAL not in state:
        return [], {}
    seal = state[SEAL]
    if not isinstance(seal, dict) or not isinstance(seal.get("experiments"), dict):
        return ["state.json order_seal is not a seal with an experiments object, so "
                "the line's record cannot be verified"], {}
    rows, errors, intact = seal["experiments"], [], {}
    now = _seal_files(base)
    when = seal.get("date") or "undated"
    for h in sorted(set(rows) | set(now)):
        row = rows.get(h)
        if not isinstance(row, dict):
            errors.append("experiment %s was added after the line was sealed (%s)"
                          % (h, when))
            continue
        if h not in now:
            errors.append("experiment %s was removed after the line was sealed (%s)"
                          % (h, when))
            continue
        changed = [name for key, name, path in zip(
            ("protocol", "results"), ("protocol.md", "results.jsonl"), now[h])
            if row.get(key) != (_digest(path) if path else None)]
        if changed:
            errors.append("experiment %s: %s changed after the line was sealed (%s) - "
                          "a sealed line's plan and run are its record"
                          % (h, " and ".join(changed), when))
        else:
            intact[h] = dict(row, date=when, ack=seal.get("ack"))
    return errors, intact


def _sealed_order(h, row, errors, warnings, strict):
    """The owner's `history-lost` verdict on an intact sealed experiment: a
    warning that names it, an error under `--strict`."""
    _soft(errors, warnings, strict,
          "experiment %s: the protocol order is not provable - the history that "
          "held it was lost, and the line was sealed with that verdict (%s%s)"
          % (h, row.get("date"), "; ack: %s" % row["ack"] if row.get("ack") else ""))


def order_seal(repo, base, date=""):
    """The `order_seal` record for the line at `base`, as of now."""
    return {"date": date, "verdict": "sealed", "experiments": _seal_rows(repo, base)}


def retro_seal(repo, slug, ack, date=""):
    """(record, problem): seal a line concluded before the seal existed with the
    `history-lost` verdict (ADR 009). Only a line under `done/` that carries no
    seal yet, and only with `ack` naming the owner's decision: the verdict says
    the order can no longer be proven, which is the owner's call, not a session's.
    Refused, with the findings printed, when an experiment's order fails for a
    reason outside `LOST_HISTORY` - a real violation stays an error - and when
    nothing is lost. An experiment whose order still checks keeps no verdict and
    is re-derived like any sealed one."""
    if not sealed(repo, slug):
        return None, ("%s is not under research/done/: only a concluded or closed "
                      "line is retro-sealed" % slug)
    if not str(ack or "").strip():
        return None, "a history-lost seal needs --ack \"<the owner's decision>\""
    base = line_dir(repo, slug)
    path = os.path.join(base, "state.json")
    state, exc = _read_json(path)
    if exc or not isinstance(state, dict):
        return None, "state.json does not parse (%s)" % (exc or "not an object")
    if isinstance(state.get(SEAL), dict):
        return None, "%s already carries an order seal (%s)" % (
            slug, state[SEAL].get("verdict"))
    record = dict(order_seal(repo, base, date), verdict=HISTORY_LOST, ack=ack)
    real = []
    for h, (proto, results) in _seal_files(base).items():
        if not results:
            continue
        errs, warns = [], []
        _check_protocol_order(repo, h, proto, results, errs, warns, False)
        found = errs + warns
        real += [f for f in found if not any(m in f for m in LOST_HISTORY)]
        if found:
            record["experiments"][h].update(order=HISTORY_LOST, finding=found[0])
    if real:
        return None, ("not a lost history - these order findings stay as they are: "
                      + "; ".join(real))
    if not any(r.get("order") for r in record["experiments"].values()):
        return None, "every experiment's order still checks: nothing to seal as lost"
    state[SEAL] = record
    try:
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(json.dumps(state, indent=2) + "\n")
        with open(os.path.join(base, "log.md"), "a", encoding="utf-8") as fh:
            fh.write("- %s sealed: history lost (ack: %s)\n" % (date, ack))
    except OSError as exc:
        return None, str(exc)
    return record, None


def _committed_lines(top, rev):
    """{slug: path in the repository} for the lines commit `rev` of the
    repository at `top` holds, in `line_dir`'s precedence: open/, done/, flat."""
    out = {}
    for folder in ("research/open", "research/done", "research"):
        names, err = _git_out(top, "ls-tree", "-d", "--name-only",
                              "%s:%s" % (rev, folder))
        for name in ([] if err else names.splitlines()):
            if valid_slug(name) and not (folder == "research" and name in (OPEN, DONE)):
                out.setdefault(name, "%s/%s" % (folder, name))
    return out


def import_line(repo, source, slug=None, allow_open=None, date=""):
    """(imported slugs, problem): bring research lines from another checkout's
    private `.tezgah` repository into this one with their history.

    The source's HEAD is fetched and merged as a second parent
    (`--allow-unrelated-histories -s ours`), and only the imported lines' paths
    are taken from it, so their commits - the protocol-before-results order -
    sit in this HEAD's lineage and nothing else of the source's tree arrives.
    That is the two-parent shape that kept two lines' order proofs; the
    single-parent copy that lost one is refused: a line the source never
    committed has no history to bring. A workspace with no commit yet gets an
    empty root commit of its own first, so the source's history is never its
    first parent. With no `slug`, every committed source line this checkout
    lacks is imported. Works with no remote: the source is read from its own
    disk path.

    A line arriving from the source's `research/open/` is a new open line here,
    so `init`'s one-open-line rule applies: refused while another line is open
    (or several open lines arrive at once) unless `allow_open` gives the reason,
    which lands in the line's `log.md` (`note_open`) inside the import commit;
    and refused beside an open line `check` refuses (`broken_open_lines`)."""
    ws, src = tp.workspace(repo), tp.workspace(source)
    if os.path.realpath(src) == os.path.realpath(ws):
        return [], "%s is this checkout's own workspace" % src
    if not os.path.isdir(os.path.join(src, ".git")) or _unborn(src):
        return [], ("%s holds no committed .tezgah repository; import merges "
                    "history and refuses a plain copy, which would lose the "
                    "order proof" % src)
    if not os.path.isdir(os.path.join(ws, ".git")):
        return [], "%s has no repository of its own yet" % ws
    if allow_open is not None and not str(allow_open).strip():
        return [], "--allow-open needs the reason the line is worth opening"
    fresh = _unborn(ws)
    staged, _err = _git_out(ws, "ls-files") if fresh else \
        _git_out(ws, "diff", "--cached", "--name-only")
    if staged.strip():
        return [], ("%s has staged changes; commit or unstage them before an "
                    "import commits" % ws)
    try:
        done = tp.ws_git(repo, "fetch", "-q", "--no-tags", src, "HEAD")
    except OSError as exc:
        return [], str(exc)
    if done.returncode:
        return [], "fetch failed: %s" % done.stderr.strip()
    rev, err = _git_out(ws, "rev-parse", "FETCH_HEAD")
    if err:
        return [], err
    rev = rev.strip()
    lines, here = _committed_lines(ws, rev), slugs(repo)
    if slug is not None and slug not in lines:
        return [], ("%s is not committed in %s, so it has no history to import; "
                    "commit it there (`tezgah-research commit`) - a plain copy is "
                    "refused because it loses the order proof" % (slug, src))
    wanted = [slug] if slug is not None else sorted(s for s in lines if s not in here)
    clash = [s for s in wanted if s in here]
    if clash:
        return [], ("this checkout already holds %s; remove that copy first - "
                    "import brings the history a copy lacks" % ", ".join(clash))
    blocked = [lines[s] for s in wanted if os.path.lexists(os.path.join(ws, lines[s]))]
    if blocked:
        return [], ("%s exists here and is not a line directory; move it away "
                    "before the import lands there" % ", ".join(blocked))
    if not wanted:
        return [], None
    arriving = [s for s in wanted if lines[s].startswith("research/%s/" % OPEN)]
    unfinished = open_lines(repo) if arriving else []
    if (unfinished or len(arriving) > 1) and allow_open is None:
        return [], ("%s would open beside unfinished line(s) %s; say why with "
                    "--allow-open \"<reason>\"" % (
                        ", ".join(arriving),
                        "; ".join("%s (%s)" % (n, "; ".join(r)) for n, r in unfinished)
                        or ", ".join(arriving)))
    broken = broken_open_lines(repo) if unfinished else []
    if broken:
        return [], ("--allow-open does not open a line beside an open line check "
                    "refuses: %s" % ", ".join(n for n, _e in broken))
    if fresh:
        done = tp.ws_git(repo, "commit", "-q", "--allow-empty", "-m",
                         "research: workspace root")
        if done.returncode:
            return [], "git commit failed: %s" % (done.stderr or done.stdout).strip()
    notes = [] if allow_open is None or not arriving else [
        ("add", "--") + tuple("%s/log.md" % lines[s] for s in arriving)]
    steps = [("merge", "-q", "--no-ff", "--no-commit", "--allow-unrelated-histories",
              "-s", "ours", rev),
             ("checkout", rev, "--") + tuple(lines[s] for s in wanted)] + notes + [
             ("commit", "-q", "-m", "research: import %s from %s"
              % (", ".join(wanted), source))]
    for args in steps:
        problem = None
        if args[0] == "add":
            problem = "; ".join(p for p in (note_open(repo, s, allow_open, date)
                                            for s in arriving) if p) or None
        done = None if problem else tp.ws_git(repo, *args)
        if problem or done.returncode:
            tp.ws_git(repo, "merge", "--abort")
            if fresh:
                tp.ws_git(repo, "update-ref", "-d", "HEAD")
            return [], problem or "git %s failed: %s" % (
                args[0], (done.stderr or done.stdout).strip())
    return wanted, None


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
    elif isinstance(state.get("closed"), dict) \
            and str(state["closed"].get("limit", "")).strip():
        # `close --limit` concluded it on purpose, and what was left is written
        # in the record itself: the line is finished as a deliberate limit.
        return []
    elif state.get("phase") != "concluded":
        reasons.append("phase %s" % (state.get("phase") or "unset"))
    owed = _variants_owed(base, state) if isinstance(state, dict) else None
    if owed:
        reasons.append(owed)
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


def _variants_owed(base, state):
    """The reason a line whose deliverable needs compared variants is unfinished,
    or None: no decision holds the variants it takes and a decision.md."""
    deliverable = state.get("deliverable")
    if not isinstance(deliverable, dict):
        return None
    _problems, need = deliverable_problems(deliverable)
    if need < 2:
        return None
    for _name, ddir in _decision_dirs(base):
        produced = [r for r in _row_objects(os.path.join(ddir, "variants.jsonl"))
                    if r.get("status") == "produced"]
        if len(produced) >= need and os.path.isfile(os.path.join(ddir, "decision.md")):
            return None
    return ("deliverable %s has no decision comparing %d variants"
            % (deliverable.get("kind"), need))


def broken_open_lines(repo):
    """[(slug, errors)] for the open lines `check` refuses: what `init
    --allow-open` will not open a new line beside, because a hatch past broken
    lines is how they stayed broken."""
    out = []
    for slug, _reasons in open_lines(repo):
        errors, _ = check_line(repo, slug)
        if errors:
            out.append((slug, errors))
    return out


def close_line(repo, slug, limit, date="", ack=""):
    """(reasons left, problem): conclude `slug` as a deliberate limit. The open
    reasons at the moment of closing are written into `state.json` `closed` and
    into `log.md`, so the limit says exactly what was left and why, and the line
    stops counting as open. The line is sealed (`order_seal`) with its
    experiments' hashes. Nothing else is rewritten: its errors, if any, still
    show in `check <slug>` and `check --all-lines`; the no-slug `check` and the
    session note read a line under done/ by its seal alone."""
    base = line_dir(repo, slug)
    path = os.path.join(base, "state.json")
    state, exc = _read_json(path)
    if exc or not isinstance(state, dict):
        return [], "state.json does not parse (%s)" % (exc or "not an object")
    newer = newer_rules(state)
    if newer:
        return [], newer
    reasons = _open_reasons(base)
    if str(state.get("ask") or "").strip() and unanswered(state) \
            and not str(ack or "").strip() and not _user_event(state):
        return reasons, ("the line's own criteria are not all met: close records a "
                         "limit only with --ack \"<what the user said>\" (or a "
                         "session event tagged user), so an unanswered line is a "
                         "decision someone made rather than a silent exit")
    closed = {"limit": limit, "date": date, "left": reasons}
    if ack:
        closed["ack"] = ack
    state.update(phase="concluded", direction="conclude", closed=closed)
    state[SEAL] = order_seal(repo, base, date)
    try:
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(json.dumps(state, indent=2) + "\n")
        with open(os.path.join(base, "log.md"), "a", encoding="utf-8") as fh:
            fh.write("- %s closed as a deliberate limit: %s (left: %s)\n"
                     % (date, limit, "; ".join(reasons) or "nothing"))
    except OSError as exc:
        return reasons, str(exc)
    moved, problem = move_line(repo, slug, DONE)
    if problem:
        return reasons, problem
    return reasons, None


def _user_event(state):
    """True when the line records a session event tagged `user`: the one proof a
    human looked, which is what a limit over an unmet criterion needs."""
    for event in state.get("sessions") or []:
        if isinstance(event, dict) and event.get("tag") == "user":
            return True
    return False



def conclude_line(repo, slug, date=""):
    """(problems, state): conclude `slug` when its own criteria allow it.

    The rule the layer was missing (measured 2026-10-01: four of eleven sampled
    lines concluded with the ask unanswered, and `close --limit` was the way out):
    every success criterion names a verdict with an evidence pointer, and the
    line then moves to `done/`. A criterion left `not-met` is allowed - a
    negative result is a result - but it is recorded, and `status` keeps listing
    the line as unanswered. Concluding seals the line (`order_seal`)."""
    base = line_dir(repo, slug)
    path = os.path.join(base, "state.json")
    state, exc = _read_json(path)
    if exc or not isinstance(state, dict):
        return ["state.json does not parse (%s)" % (exc or "not an object")], None
    newer = newer_rules(state)
    if newer:
        return [newer], None
    rows = success_rows(state.get("success"))
    unjudged = [sid for sid, _c, verdict, _e in rows if verdict not in VERDICTS]
    problems = []
    if not rows:
        problems.append("no success criteria: write one per part of the ask "
                        "(state.json `success`) before concluding")
    if unjudged:
        problems.append("no verdict for %s: record it with "
                        "`tezgah-research verdict <slug> <id> met|not-met|unanswerable "
                        "--evidence <ref>`" % ", ".join(unjudged))
    if problems:
        return problems, None
    state.update(phase="concluded", direction="conclude")
    state[SEAL] = order_seal(repo, base, date)
    try:
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(json.dumps(state, indent=2) + "\n")
        with open(os.path.join(base, "log.md"), "a", encoding="utf-8") as fh:
            fh.write("- %s concluded: %s\n" % (date, ", ".join(
                "%s %s" % (sid, verdict) for sid, _c, verdict, _e in rows)))
    except OSError as exc:
        return [str(exc)], None
    _moved, problem = move_line(repo, slug, DONE)
    return ([problem] if problem else []), state


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
    session that only meets them at its next `init` met them too late.

    A line under `done/` is read by its order seal alone (`done_seal`), as the
    default no-slug `check` reads it: its other findings stay with `check <slug>`
    and `check --all-lines` (plan 058 part 4, ADR 015)."""
    out = []
    for slug in slugs(repo):
        if sealed(repo, slug):
            errors, has_seal = done_seal(repo, slug)
            note = ("done, %d seal problem(s)" % len(errors) if errors
                    else "done, seal ok" if has_seal else "done, unsealed (not checked)")
        else:
            errors = check(repo, slug=slug)[slug]["errors"]
            note = "ok" if not errors else "%d problem(s)" % len(errors)
        fixtures = _fixture_claims(line_dir(repo, slug), repo)
        if fixtures:
            note += ", %d fixture-scoped claim(s): %s" % (len(fixtures), ", ".join(fixtures))
        out.append("%s: %s" % (slug, note))
    unfinished = open_note(repo)
    if unfinished:
        out.append(unfinished)
    return out


def across(repo):
    """Every checkout's research lines, for `--all`: one header per checkout of
    this repository (`tp.worktrees`), then `  <slug>: <phase>` per line, with the
    reasons it is still open. Read-only: each checkout keeps its own `.tezgah`,
    and nothing here writes to any of them."""
    here = os.path.realpath(repo)
    out = []
    checkouts = tp.worktrees(repo) or [here]
    if here not in checkouts:  # a moved or unreadable checkout is still this one
        checkouts.append(here)
    for checkout in checkouts:
        names = slugs(checkout)
        out.append("%s%s%s" % (checkout, " (this checkout)" if checkout == here else "",
                               "" if names else ": no research line"))
        for slug in names:
            base = line_dir(checkout, slug)
            reasons = _open_reasons(base)
            out.append("  %s: %s%s" % (slug, _phase(base) or "phase unreadable",
                                       " - open: " + "; ".join(reasons) if reasons else ""))
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
    newer = newer_rules(_state(base))
    if newer:
        return [], [newer]
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
    newer = newer_rules(_state(line_dir(repo, slug)))
    if newer:
        return None, [newer]
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
    "rules": RULES,
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


TIERS = ("quick", "study", "program")
DEFAULT_TIER = "study"
VERDICTS = ("met", "not-met", "unanswerable")
# A line that states an ask (rules 3 onward) carries the user's ask verbatim, a
# tier, and one success criterion per part of the ask, each judged
# met/not-met/unanswerable before the line may conclude.


def ask_problems(ask, tier):
    """The problems with an opening ask, one per line.

    The ask is the user's own words: without it the line aims at the question the
    agent framed, and "was it answered" has nothing to be judged against
    (measured 2026-10-01: 0 of 416 claims in this workspace cited a part of the
    ask). `quick` is the scope ladder's first rung and gets no line at all - the
    answer belongs in the reply, with its evidence."""
    problems = []
    if str(ask or "").strip() == "":
        problems.append("no --ask: the research layer needs the user's own words, "
                        "verbatim, or nothing can say whether the line answered them")
    if tier not in TIERS:
        problems.append("tier %r is not one of %s" % (tier, ", ".join(TIERS)))
    elif tier == "quick":
        problems.append("a `quick` question gets no line: answer it in the reply "
                        "with its evidence, then open a line only if it is not settled")
    return problems


def success_rows(rows):
    """The success criteria as (id, criterion, verdict, evidence) tuples."""
    out = []
    for row in rows or []:
        if not isinstance(row, dict):
            continue
        out.append((str(row.get("id") or ""), str(row.get("criterion") or ""),
                    str(row.get("verdict") or ""), str(row.get("evidence") or "")))
    return out


def unanswered(state):
    """True when this line's own criteria say it did not answer the ask: any
    verdict that is `not-met`, or a conclusion with a criterion left unjudged."""
    rows = success_rows(state.get("success"))
    if not rows:
        return False
    if any(verdict == "not-met" for _id, _c, verdict, _e in rows):
        return True
    return (str(state.get("phase")) == "concluded"
            and any(verdict not in VERDICTS for _id, _c, verdict, _e in rows))


def verdict_problems(state, rows):
    """The problems with a verdict call, one per line."""
    newer = newer_rules(state)
    if newer:
        return [newer]
    known = {row[0] for row in success_rows(state.get("success"))}
    problems = []
    if not rows:
        problems.append("no success criterion yet: the line states none, so a "
                        "verdict has nothing to answer")
    for sid, verdict, evidence in rows:
        if sid not in known:
            problems.append("no success criterion %r in this line" % sid)
        if verdict not in VERDICTS:
            problems.append("verdict %r is not one of %s" % (verdict, ", ".join(VERDICTS)))
        if not evidence.strip():
            problems.append("criterion %s carries no --evidence: a verdict without "
                            "a pointer is an opinion" % sid)
    return problems


def init(repo, slug, question="", created="", supersedes=None, ask="", tier=DEFAULT_TIER):
    """Scaffold a research line. Returns the paths created (never overwrites).

    Refuses a slug `slugs()` cannot list - see `valid_slug` - so no caller can
    write a line that `check`, `status` and `claim` never see."""
    if not valid_slug(slug):
        raise ValueError("not a research slug: %r" % slug)
    tp.ensure_workspace(repo)
    base = line_dir(repo, slug)  # a new line lands under open/
    made = []
    for sub in ("experiments", "literature", "to_human"):
        path = os.path.join(base, sub)
        os.makedirs(path, exist_ok=True)
    state = dict(STATE_TEMPLATE)
    state["question"] = question
    state["created"] = created
    # every new line is opened under the newest rule set (`RULES` in the
    # template); the ask contract is keyed on the `ask` field itself
    if ask:
        state["ask"] = ask
    if tier in TIERS:
        state["tier"] = tier
    if supersedes:
        state["supersedes"] = supersedes
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
# Frozen (ADR 009): predictions and the per-component report below keep working
# as they are and get no new rule, field or command. ponytail: the layer is the
# maintainer's own workflow and its use was never measured, so it is held at
# this size; a measured use is what would reopen it, and deleting it is the
# other way out (decided against, not deferred).
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
        # a prediction names a product commit, so only the project's history
        # places it - never the private `.tezgah` one (see is_ancestor)
        ancestor = _ancestor(repo, commit, "HEAD")
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
    newer = newer_rules(_state(base))
    if newer:
        return [newer], []
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
