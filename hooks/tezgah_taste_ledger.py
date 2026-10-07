#!/usr/bin/env python3
"""Taste learning: the symbolic layer and the meta loop of taste-1's architecture
(research line taste-architecture, design T1P), and what the hooks inject from it.

The decision - preference, defect or none; which category; which scope; how the
signal relates to each learning already held - is a typed System One call made
by `bin/tezgah-taste learn`. This module never calls out: it takes those typed
answers and keeps the ledger.

- Fixed categories (`CATEGORIES`); a learning outside them is never created.
- Confidence is the beta expectation (r+1)/(r+s+2) over supporting (r) and
  contradicting (s) evidence, each weighted by the probability the decision gave
  it, with a per-scope forgetting factor per day (Beta Reputation System).
- States: candidate -> active after `SESSIONS_TO_ACTIVE` sessions; a
  contradiction flags an active learning `conflicted` and stores the contrary
  claim `quarantined`; `narrows` adds a narrower learning beside the broader one;
  a user's reject retires one. A conflict ends when one side falls below
  `RESOLVE_BELOW` or the user decides.
- Meta loop: a learning injected in a session whose category then gets a
  preference correction that does not support it takes s += weight.
- Apply: a rule needs confidence >= `RULE_AT` and a calibration bound >=
  `BOUND_AT` (Clopper-Pearson on an independently labelled sample); a hint needs
  `HINT_AT`; a learning whose evidence paths are all gone from the tree is
  suspended. The benefit gate's stop file turns injection off.

Store: `<repo>/.tezgah/taste/ledger.json` for path, language and repository
learnings, `~/.config/tezgah/taste/ledger.json` for user learnings.
"""
import datetime
import fnmatch
import json
import math
import os

from tezgah_paths import CONFIG_DIR, cache_dir

CATEGORIES = ("architecture", "naming", "structure", "error-handling", "testing",
              "dependencies", "language-idiom", "formatting", "docs-and-comments",
              "tooling", "workflow-output")
SCOPES = ("path", "language", "repository", "user")  # narrowest first
FORGET = {"path": 0.98, "language": 0.98, "repository": 0.99, "user": 0.995}
RELATIONS = ("supports", "contradicts", "narrows", "unrelated")
RULE_AT, HINT_AT, RESOLVE_BELOW, BOUND_AT = 0.8, 0.6, 0.4, 0.8
SESSIONS_TO_ACTIVE = 2
FORGOTTEN_BELOW = 0.25  # a one-session candidate or quarantined claim whose r fell under this is dropped
INJECT_MAX, TEXT_MAX = 12, 160


def now_day():
    """Days since the epoch, as a float: the unit forgetting is counted in."""
    return datetime.datetime.now(datetime.timezone.utc).timestamp() / 86400.0


def store_dir(root):
    return os.path.join(root, ".tezgah", "taste")


def user_dir():
    return os.path.join(CONFIG_DIR, "taste")


def _load(path):
    try:
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
        if isinstance(data, dict) and isinstance(data.get("learnings"), dict):
            data.setdefault("meta", {})
            return data
    except (OSError, ValueError):
        pass
    return {"v": 1, "learnings": {}, "meta": {}}


def _save(path, data):
    os.makedirs(os.path.dirname(path), mode=0o700, exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(data, fh, ensure_ascii=False, indent=1, sort_keys=True)
    os.replace(tmp, path)


def load(root):
    """{"repo": ledger, "user": ledger}."""
    return {"repo": _load(os.path.join(store_dir(root), "ledger.json")),
            "user": _load(os.path.join(user_dir(), "ledger.json"))}


def save(root, ledgers):
    _save(os.path.join(store_dir(root), "ledger.json"), ledgers["repo"])
    _save(os.path.join(user_dir(), "ledger.json"), ledgers["user"])


def every(ledgers):
    """Both ledgers' learnings in one id map (the ids are kept distinct)."""
    return dict(ledgers["repo"]["learnings"], **ledgers["user"]["learnings"])


# --- the evidence calculus -------------------------------------------------------

def decayed(learning, day):
    """(r, s) forgotten forward to `day` at the learning's scope rate."""
    rate = FORGET.get(learning.get("scope"), FORGET["repository"])
    age = max(0.0, day - float(learning.get("updated", day)))
    keep = rate ** age
    return learning.get("r", 0.0) * keep, learning.get("s", 0.0) * keep


def confidence(learning, day=None):
    r, s = decayed(learning, now_day() if day is None else day)
    return (r + 1.0) / (r + s + 2.0)


def _touch(learning, day):
    learning["r"], learning["s"] = decayed(learning, day)
    learning["updated"] = day


def cp_lower(x, n, alpha=0.05):
    """The two-sided (1-alpha) Clopper-Pearson lower bound on a proportion x/n:
    the p at which P(X >= x | n, p) = alpha/2. 0 when there is no evidence."""
    if n <= 0 or x <= 0:
        return 0.0
    if x >= n:
        return (alpha / 2.0) ** (1.0 / n)

    def tail(p):
        return sum(math.comb(n, k) * p ** k * (1 - p) ** (n - k) for k in range(x, n + 1))
    lo, hi = 0.0, x / n
    for _ in range(60):
        mid = (lo + hi) / 2.0
        if tail(mid) < alpha / 2.0:
            lo = mid
        else:
            hi = mid
    return lo


def rows(path):
    try:
        with open(path, encoding="utf-8") as fh:
            for line in fh:
                try:
                    row = json.loads(line)
                except ValueError:
                    continue
                if isinstance(row, dict):
                    yield row
    except OSError:
        return


def append(path, row):
    os.makedirs(os.path.dirname(path), mode=0o700, exist_ok=True)
    with open(path, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(row, ensure_ascii=False) + "\n")


def calibration(root):
    """(x, n, bound): of the labelled signals the typed decision called a
    preference, how many the label agrees with, and the Clopper-Pearson lower
    bound on that precision. Only typed-provider decisions count; the labels are
    a sample drawn independently of what was injected (`tezgah-taste label`)."""
    x = n = 0
    for row in rows(os.path.join(store_dir(root), "labels.jsonl")):
        if row.get("provider") != "typesafe" or row.get("decided") != "preference":
            continue
        n += 1
        x += row.get("label") == "preference"
    return x, n, cp_lower(x, n)


# --- the symbolic layer -------------------------------------------------------------

def where_for(scope, paths):
    """The scope's value for a signal's written paths: a directory glob, an
    extension glob, the repository or every repository."""
    paths = [p for p in paths or () if p]
    if scope == "path" and paths:
        common = os.path.commonpath([os.path.dirname(p) or "." for p in paths])
        return (common.rstrip("/") + "/**") if common not in ("", ".") else "**"
    if scope == "language" and paths:
        ext = os.path.splitext(paths[0])[1]
        return "*" + ext if ext else "*"
    return "*" if scope == "user" else "."


def _evidence_row(sig):
    return {"signal": sig.get("id"), "session": sig.get("session"),
            "paths": list(sig.get("paths") or [])[:8]}


def _new(ledgers, sig, category, scope, weight, day, state="candidate", parent=None):
    book = ledgers["user" if scope == "user" else "repo"]
    taken = every(ledgers)
    prefix = "u" if scope == "user" else "t"
    # a monotonic counter: an id a forgotten learning held is never issued
    # again, so a stale `conflicts` entry or injected row cannot name a stranger
    n = max(int(book["meta"].get("next_id", 1)), len(book["learnings"]) + 1)
    while "%s%04d" % (prefix, n) in taken:
        n += 1
    book["meta"]["next_id"] = n + 1
    lid = "%s%04d" % (prefix, n)
    book["learnings"][lid] = {
        "id": lid, "category": category, "scope": scope,
        "where": where_for(scope, sig.get("paths")),
        "text": " ".join((sig.get("text") or "").split())[:400],
        "written": False, "r": weight, "s": 0.0, "sessions": [sig.get("session") or ""],
        "evidence": [_evidence_row(sig)], "state": state, "conflicts": [],
        "parent": parent, "accepted": False, "edited": False,
        "created": day, "updated": day}
    return book["learnings"][lid]


def _support(learning, sig):
    learning["evidence"] = (learning.get("evidence") or [])[-19:] + [_evidence_row(sig)]
    if sig.get("session") and sig["session"] not in learning["sessions"]:
        learning["sessions"].append(sig["session"])


def apply(ledgers, sig, dec, day, applied=()):
    """Fold one decided signal into the ledgers; returns what happened:
    `unverified`, `defect`, `none` or `learned`.

    `dec` is the typed decision: `kind`, `category`, `scope` as (choice,
    probability), `relations` {learning id: (relation, probability)} and
    `verified`, True only when TypeSafe answered - any other provider's decision
    is never applied. `applied` are the ids injected in the signal's session."""
    if not dec.get("verified"):
        return "unverified"
    kind, p_kind = dec["kind"]
    if kind != "preference":
        return kind if kind in ("defect", "none") else "none"
    category = dec["category"][0]
    if category not in CATEGORIES:
        return "none"
    scope = dec["scope"][0] if dec["scope"][0] in SCOPES else "repository"
    w = float(p_kind)
    known = every(ledgers)
    relations = dec.get("relations") or {}
    contrary, linked = None, False
    for lid, (rel, p) in relations.items():
        learning = known.get(lid)
        if learning is None or learning["state"] == "retired":
            continue
        _touch(learning, day)
        if rel == "supports":
            learning["r"] += w * p
            _support(learning, sig)
            if learning["state"] == "quarantined" and \
                    len(learning["sessions"]) >= SESSIONS_TO_ACTIVE:
                # corroborated, but its partner still stands: withheld as a
                # conflict until one side falls below RESOLVE_BELOW or the user decides
                learning["state"] = "conflicted" if _live_partners(learning, known) \
                    else "candidate"
            linked = True
        elif rel == "contradicts":
            learning["s"] += w * p
            if contrary is None:
                contrary = _new(ledgers, sig, category, scope, w, day, state=(
                    "quarantined" if learning["state"] in ("active", "conflicted")
                    else "candidate"))
            if learning["state"] == "active":
                learning["state"] = "conflicted"
            for a, b in ((learning, contrary), (contrary, learning)):
                if b["id"] not in a["conflicts"]:
                    a["conflicts"].append(b["id"])
            linked = True
        elif rel == "narrows" and SCOPES.index(scope) < SCOPES.index(learning["scope"]):
            _new(ledgers, sig, category, scope, w * p, day, parent=lid)
            linked = True
    # the meta loop: a learning applied in this session and then corrected in
    # its category and scope by a signal that neither supports nor contradicts it
    for lid in applied:
        learning = known.get(lid)
        if learning is None or learning["category"] != category \
                or not in_scope(learning, sig.get("paths")):
            continue
        if relations.get(lid, ("unrelated", 0.0))[0] in ("unrelated", "narrows"):
            _touch(learning, day)
            learning["s"] += w
    if not linked:
        _new(ledgers, sig, category, scope, w, day)
    settle(ledgers, day)
    return "learned"


def _live_partners(learning, known):
    return [known[c] for c in learning["conflicts"]
            if c in known and known[c]["state"] != "retired"]


def in_scope(learning, paths):
    """True when a path or language learning covers one of `paths`; a
    repository or user learning covers everything."""
    if learning["scope"] not in ("path", "language"):
        return True
    return any(fnmatch.fnmatch(p, learning["where"]) for p in paths or ())


def settle(ledgers, day):
    """Promote, resolve and forget: the transitions that depend on totals."""
    known = every(ledgers)
    for learning in known.values():
        if learning["state"] == "candidate" and \
                len(learning["sessions"]) >= SESSIONS_TO_ACTIVE:
            # two claims that contradict each other never go active together
            learning["state"] = "conflicted" if _live_partners(learning, known) \
                else "active"
        if learning["state"] == "conflicted":
            others = _live_partners(learning, known)
            if confidence(learning, day) < RESOLVE_BELOW:
                learning["state"] = "retired"
                for other in others:
                    if other["state"] == "quarantined":
                        other["state"] = "candidate"
            elif all(confidence(o, day) < RESOLVE_BELOW for o in others):
                for other in others:
                    other["state"] = "retired"
                learning["state"] = "active"
    gone = set()
    for book in (ledgers["repo"], ledgers["user"]):
        for lid in [k for k, v in book["learnings"].items()
                    if v["state"] in ("candidate", "quarantined")
                    and len(v["sessions"]) < SESSIONS_TO_ACTIVE
                    and not v.get("accepted")
                    and decayed(v, day)[0] < FORGOTTEN_BELOW]:
            del book["learnings"][lid]
            gone.add(lid)
    if gone:
        for learning in every(ledgers).values():
            learning["conflicts"] = [c for c in learning["conflicts"] if c not in gone]


def decide_user(ledgers, lid, verdict, day, text=None):
    """The user's own call on one learning: accept, reject or edit. An accepted
    learning beats any learned one, so the learnings it conflicts with retire.
    True when the id was found."""
    known = every(ledgers)
    learning = known.get(lid)
    if learning is None:
        return False
    _touch(learning, day)
    if verdict == "accept":
        learning.update(state="active", accepted=True)
        learning["r"] += 1.0
        for c in learning["conflicts"]:
            if c in known:
                known[c]["state"] = "retired"
    elif verdict == "reject":
        learning["state"] = "retired"
    elif verdict == "edit" and text and text.strip():
        learning.update(text=" ".join(text.split())[:400], edited=True, written=True)
    else:
        return False
    return True


# --- apply ----------------------------------------------------------------------------

def suspended(learning, root):
    """True when every evidence path the learning cites is gone from `root`.
    ponytail: capture records paths, not symbols, so a renamed symbol in a file
    that still exists is not caught; add symbols when capture records them."""
    if learning["scope"] == "user":
        return False
    paths = [p for ev in learning.get("evidence") or () for p in ev.get("paths") or ()]
    return bool(paths) and not any(os.path.exists(os.path.join(root, p)) for p in paths)


def stopped(root):
    """True when the benefit gate stopped injection for this repository."""
    try:
        with open(os.path.join(store_dir(root), "gate.json"), encoding="utf-8") as fh:
            return bool(json.load(fh).get("stopped"))
    except (OSError, ValueError, AttributeError):
        return False


def usable(root, day=None):
    """[(mode, learning)] that may be injected, narrowest scope first, then by
    confidence: mode `rule` or `hint`."""
    day = now_day() if day is None else day
    bound = calibration(root)[2]
    out = []
    for learning in every(load(root)).values():
        if learning["state"] != "active" or suspended(learning, root):
            continue
        conf = confidence(learning, day)
        if learning.get("accepted") or (conf >= RULE_AT and bound >= BOUND_AT):
            out.append(("rule", learning))
        elif conf >= HINT_AT:
            out.append(("hint", learning))
    out.sort(key=lambda m: (SCOPES.index(m[1]["scope"]), -confidence(m[1], day)))
    return out[:INJECT_MAX]


def _line(mode, learning):
    where = "" if learning["scope"] in ("repository", "user") else " in %s" % learning["where"]
    text = " ".join((learning.get("text") or "").split())[:TEXT_MAX]
    return "- %s [%s%s, %s]: %s" % (mode, learning["category"], where, learning["id"], text)


def block(root, day=None):
    """(text, ids): the session-start text and the learning ids in it, or
    ("", []). The caller records the ids with `record_injection` only once the
    text survived its context budget, so a dropped block never counts against
    the learnings the model did not see."""
    if stopped(root):
        return "", []
    picked = usable(root, day)
    if not picked:
        return "", []
    return (("Taste (learned from this user's own corrections; follow a rule, treat a "
             "hint as the default; the narrower scope wins - path, then language, then "
             "repository, then user - and AGENTS.md/CLAUDE.md beat every learning; "
             "`tezgah-taste reject <id>` drops one):\n"
             + "\n".join(_line(mode, learning) for mode, learning in picked)),
            [m[1]["id"] for m in picked])


def record_injection(root, session_id, ids, day=None):
    """One `injected.jsonl` row: the meta loop counts a later correction in this
    session against these ids, and the benefit gate splits its arms at the first."""
    if ids:
        append(os.path.join(store_dir(root), "injected.jsonl"),
               {"session": str(session_id or ""), "day": now_day() if day is None else day,
                "ids": list(ids)})


def injected(root, session_id):
    """The learning ids injected in one session."""
    ids = set()
    for row in rows(os.path.join(store_dir(root), "injected.jsonl")):
        if row.get("session") == session_id:
            ids.update(row.get("ids") or ())
    return ids


def write_note(root, session_id, rel_path):
    """The in-scope learnings for a write to `rel_path` not yet shown in this
    session, or "" - each learning once per session, so a long turn does not
    repeat it and a path learning still shows at its directory's first write."""
    if not session_id or not rel_path or stopped(root):
        return ""
    kind = os.path.splitext(rel_path)[1] or os.path.basename(rel_path)
    seen_path = os.path.join(cache_dir(), "taste-notes",
                             "%s.json" % str(session_id).replace(os.sep, "_"))
    try:
        with open(seen_path, encoding="utf-8") as fh:
            seen = set(json.load(fh))
    except (OSError, ValueError, TypeError):
        seen = set()
    hits = [(mode, learning) for mode, learning in usable(root)
            if learning["scope"] in ("path", "language") and learning["id"] not in seen
            and fnmatch.fnmatch(rel_path, learning["where"])]
    if not hits:
        return ""
    seen.update(m[1]["id"] for m in hits)
    try:
        os.makedirs(os.path.dirname(seen_path), mode=0o700, exist_ok=True)
        with open(seen_path, "w", encoding="utf-8") as fh:
            json.dump(sorted(seen), fh)
    except OSError:
        return ""
    record_injection(root, session_id, [m[1]["id"] for m in hits])
    return ("Taste for %s files (narrower scope wins):\n" % kind
            + "\n".join(_line(mode, learning) for mode, learning in hits))


# --- markdown and export ----------------------------------------------------------------

def markdown(root, day=None):
    """Rewrite `<store>/<category>/taste.md` from the active learnings; the JSON
    ledger stays the source of truth. Returns the files written."""
    day = now_day() if day is None else day
    by_cat = {}
    for learning in every(load(root)).values():
        if learning["state"] == "active":
            by_cat.setdefault(learning["category"], []).append(learning)
    written = []
    for category in CATEGORIES:
        path = os.path.join(store_dir(root), category, "taste.md")
        items = by_cat.get(category)
        if not items:
            if os.path.exists(path):
                os.remove(path)
            continue
        lines = ["# %s" % category, ""]
        for learning in sorted(items, key=lambda v: -confidence(v, day)):
            scope = learning["scope"] + ("" if learning["scope"] in ("repository", "user")
                                         else " " + learning["where"])
            lines.append("- %s (%s, %s). Confidence: %.2f" % (
                " ".join(learning["text"].split()), scope, learning["id"],
                confidence(learning, day)))
        os.makedirs(os.path.dirname(path), mode=0o700, exist_ok=True)
        with open(path, "w", encoding="utf-8") as fh:
            fh.write("\n".join(lines) + "\n")
        written.append(path)
    return written


START, END = "<!-- tezgah-taste:start -->", "<!-- tezgah-taste:end -->"


def export_agents(root):
    """Write the accepted learnings into the repository's AGENTS.md between the
    two markers, creating the file or the block. Returns how many were written."""
    picked = [v for v in every(load(root)).values()
              if v.get("accepted") and v["state"] == "active"]
    path = os.path.join(root, "AGENTS.md")
    try:
        with open(path, encoding="utf-8") as fh:
            text = fh.read()
    except OSError:
        text = ""
    has_block = START in text and END in text
    if not picked and not has_block:
        return 0
    body = "\n".join([START, "## Taste (accepted learnings)", ""]
                     + ["- %s" % " ".join(v["text"].split()) for v in picked] + [END])
    if has_block:
        text = text[:text.index(START)] + body + text[text.index(END) + len(END):]
    else:
        text = (text.rstrip("\n") + "\n\n" if text else "") + body + "\n"
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(text)
    return len(picked)


# --- the benefit gate --------------------------------------------------------------------

def first_injection(root):
    """The day of the first injection, or None: where the gate's arms split."""
    days = [r["day"] for r in rows(os.path.join(store_dir(root), "injected.jsonl"))
            if isinstance(r.get("day"), (int, float))]
    return min(days) if days else None


def gate(root, need=980, alpha=0.1):
    """The pooled before/after test on preference corrections per writing turn.

    Every decided signal is one prompt after a writing turn. The arms split at
    the first injection, by when the turn happened (`at`), not by when `learn`
    decided it, so a backfill of old sessions stays in the before arm. Once both
    arms hold `need` turns, `gate.json` says stopped unless the after-rate is
    lower at one-sided p < `alpha`. Returns the report."""
    first = first_injection(root)
    arms = {"before": [0, 0], "after": [0, 0]}
    for row in rows(os.path.join(store_dir(root), "decisions.jsonl")):
        at = row.get("at")
        if row.get("provider") != "typesafe" or not isinstance(at, (int, float)):
            continue
        arm = arms["after" if first is not None and at >= first else "before"]
        arm[0] += 1
        arm[1] += row.get("kind") == "preference"
    (n1, x1), (n2, x2) = arms["before"], arms["after"]
    report = {"first_injection": first, "before": {"turns": n1, "preference": x1},
              "after": {"turns": n2, "preference": x2}, "need": need, "p": None,
              "stopped": stopped(root)}
    if n1 and n2:
        pool = (x1 + x2) / (n1 + n2)
        se = math.sqrt(pool * (1 - pool) * (1 / n1 + 1 / n2)) if 0 < pool < 1 else 0.0
        z = ((x1 / n1) - (x2 / n2)) / se if se else 0.0
        report["p"] = round(0.5 * math.erfc(z / math.sqrt(2)), 4)
    if n1 >= need and n2 >= need:
        report["stopped"] = not (report["p"] is not None and report["p"] < alpha)
        _save(os.path.join(store_dir(root), "gate.json"),
              {"stopped": report["stopped"], "report": report})
    return report
