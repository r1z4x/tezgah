"""The product ledger (ADR 022): `.tezgah/product/ledger.jsonl` in the main
checkout, one JSON row per observation (O), insight (I), assumption (A), metric
(M), decision (D) or re-measure (R).

`row_problems` is the one shape rule: `append_row` refuses what it finds and
`check_ledger` reports it. Ids and dates are the writer's, assigned under the
research lock (`tezgah_research._locked`), and a committed row never changes
(`tezgah_research._check_append_only`). Only the main checkout writes; a linked
worktree reads the main checkout's product ledger. Findings about behaviour - an
overdue D, an I resting on no O, a D measured by an unlogged M - are warnings
(ADR 019), errors under `strict`."""
import datetime
import json
import os
import re

from tezgah_integrity import committed_size, truncate_to_committed
import tezgah_paths as tp
import tezgah_research as tr

LEDGER_REL = ("product", "ledger.jsonl")
LABEL = "/".join(LEDGER_REL)
TYPES = ("O", "I", "A", "M", "D", "R")
TOKEN = re.compile(r"\bproduct:([OIAMDR]\d+)\b")
PARENTS = {"O": (), "I": ("O",), "A": ("I",), "M": ("I",), "D": ("I", "A", "M"),
           "R": ("D",)}
# One bound for the writer and the note: a topic the writer takes is a topic the
# note may print, and a 5000-character topic cannot push the note over budget.
TOPIC = re.compile(r"(?=.{1,64}\Z)[a-z0-9]+(?:-[a-z0-9]+)*")
# What a reader outside the checker may echo (the session note): fullmatch only.
SAFE_ID = re.compile(r"[OIAMDR]\d{1,6}")
SAFE_TOPIC = TOPIC
QUOTE_MAX = 500
CLASSES = ("user-verbatim", "behaviour", "ui-observed", "code", "external")
DOWNGRADES = ("limitations", "inconsistency", "indirectness", "imprecision", "bias")
VERDICTS = ("met", "missed", "unobservable")

# Field kinds: TEXT is a non-empty string, VALUE a non-empty string or a number,
# BOOL a JSON boolean, a tuple the allowed values.
TEXT, VALUE, BOOL = "text", "value", "bool"
FIELDS = {
    "O": {"class": CLASSES, "source": TEXT, "quote": TEXT},
    "I": {"statement": TEXT, "confidence": ("high", "medium", "low")},
    "A": {"kind": ("desirability", "viability", "feasibility", "usability"),
          "statement": TEXT, "importance": ("high", "low"),
          "evidence": ("none", "weak", "strong")},
    "M": {"goal": TEXT, "signal": TEXT, "definition": TEXT, "window": TEXT,
          "baseline": VALUE, "direction": ("up", "down"), "leading": BOOL,
          "logged": ("yes", "no", "unknown"), "data": TEXT},
    "D": {"statement": TEXT, "outcome": ("keep", "fix", "cut", "bet"),
          "threshold": VALUE, "reopen": TEXT},
    "R": {"verdict": VERDICTS},
}
# What an R that observed something carries beside its verdict.
OBSERVED = {"value": VALUE, "class": CLASSES, "source": TEXT}
DESIGN_BLOCK = re.compile(r"```json\s*\n(.*?)\n```", re.S)
# `due`'s prefilter, read on the raw text before any parse. An unescaped key is
# the only way these texts occur outside a string value (inside one the quotes
# are `\"`), and a date is digits and `-`, which only a `\u` escape could spell.
AFTER = re.compile(r'"observe_after"\s*:\s*"([^"\\]*)"')
R_TYPE = re.compile(r'"type"\s*:\s*"R"')
ESCAPE = re.compile(r"\\u")
DATE = re.compile(r"\d{4}-\d{2}-\d{2}")


def main_checkout(repo):
    """The main checkout of the repository `repo` is in: the toplevel `git
    rev-parse --git-common-dir` names, read fork-free from a linked worktree's
    `.git` pointer (`tezgah_paths.linked_main`); `repo` itself otherwise."""
    return tp.linked_main(repo) or repo


def ledger_path(repo):
    return os.path.join(tp.workspace(main_checkout(repo)), *LEDGER_REL)


def _lines(text):
    """[(line number, row or None)] of the non-blank lines; None does not parse
    as a JSON object."""
    out = []
    # "\n" only, the writer's terminator: str.splitlines would also split on
    # U+2028, U+2029 and U+0085 inside a quoted string and break the row
    for n, raw in enumerate(text.split("\n"), 1):
        if not raw.strip():
            continue
        try:
            row = json.loads(raw)
        except (ValueError, RecursionError):
            row = None
        out.append((n, row if isinstance(row, dict) else None))
    return out


def read_rows(repo):
    """The product ledger's rows, to its committed boundary; [] when absent."""
    text, _exc = tr._committed_text(ledger_path(repo))
    return [row for _n, row in _lines(text or "") if row is not None]


def _date(value):
    """The date `value` names as YYYY-MM-DD, else None (3.11's fromisoformat also
    takes `20260105` and week dates)."""
    if not (isinstance(value, str) and DATE.fullmatch(value)):
        return None
    try:
        return datetime.date.fromisoformat(value)
    except ValueError:
        return None


def _id(value):
    """`value` when it can be an id; a JSON list or object never is one, and is
    no dict key either."""
    return value if isinstance(value, str) else None


def _field(row, key, kind):
    """The problem with `row[key]` against its kind, or None."""
    value = row.get(key)
    if kind == TEXT:
        ok = isinstance(value, str) and value.strip()
        want = "a non-empty text"
    elif kind == VALUE:
        ok = ((isinstance(value, str) and value.strip())
              or (isinstance(value, (int, float)) and not isinstance(value, bool)))
        want = "a non-empty text or a number"
    elif kind == BOOL:
        ok = isinstance(value, bool)
        want = "true or false"
    else:
        ok = value in kind
        want = "one of %s" % ", ".join(kind)
    return None if ok else "%s is %r, not %s" % (key, value, want)


def _claim_problem(repo, ref):
    if not isinstance(ref, str):
        return "claims holds %r, not <slug>:<claim id>" % (ref,)
    slug, _sep, cid = ref.partition(":")
    base = tr.line_dir(repo, slug) if tr.valid_slug(slug) else None
    if not (cid and base and os.path.isdir(base) and cid in tr._claim_ids(base)):
        return "claim %s resolves to no research line's claims.jsonl" % ref
    return None


def row_problems(row, held, repo):
    """Every reason `row` is not a product ledger row, given the rows `held`
    before it; [] when it is one. The writer refuses on it and the checker
    reports it, so the two can never disagree."""
    kind = row.get("type")
    if kind not in TYPES:
        return ["type is %r, not one of %s" % (kind, ", ".join(TYPES))]
    by_id = {r.get("id"): r for r in held if isinstance(r.get("id"), str)}
    problems = []
    rid = row.get("id")
    if not (isinstance(rid, str) and re.fullmatch(r"%s[1-9]\d*" % kind, rid)):
        problems.append("id %r is not %s<n>" % (rid, kind))
    elif rid in by_id:
        problems.append("id %s is already in the product ledger" % rid)
    day = _date(row.get("date"))
    if day is None:
        problems.append("date %r is not YYYY-MM-DD" % (row.get("date"),))
    topic = row.get("topic")
    if not (isinstance(topic, str) and TOPIC.fullmatch(topic)):
        problems.append("topic %r is not kebab-case of at most 64 characters" % (topic,))
    parents = row.get("from", [])
    if not isinstance(parents, list):
        problems.append("from is %r, not a list of ids" % (parents,))
        parents = []
    for pid in parents:
        if _id(pid) not in by_id:
            problems.append("from names %r, which the product ledger does not hold"
                            % (pid,))
        elif by_id[pid].get("type") not in PARENTS[kind]:
            problems.append("from names %s, but a %s row rests on %s" % (
                pid, kind, "/".join(PARENTS[kind]) or "nothing"))
    claims = row.get("claims", [])
    if not isinstance(claims, list):
        problems.append("claims is %r, not a list of <slug>:<claim id>" % (claims,))
    else:
        main = main_checkout(repo)
        problems += [p for p in (_claim_problem(main, c) for c in claims) if p]
    for key, want in FIELDS[kind].items():
        problem = _field(row, key, want)
        if problem:
            problems.append(problem)
    if kind == "O" and isinstance(row.get("quote"), str) \
            and len(row["quote"]) > QUOTE_MAX:
        problems.append("quote is %d characters, over %d" % (len(row["quote"]),
                                                              QUOTE_MAX))
    if kind == "I" and ("downgrade" in row or row.get("confidence") != "high"):
        grades = row.get("downgrade")
        grades = grades if isinstance(grades, list) else [grades]
        if not grades or any(g not in DOWNGRADES for g in grades):
            problems.append("downgrade is %r: it names one of %s, and an I below "
                            "high confidence needs one" % (row.get("downgrade"),
                                                           ", ".join(DOWNGRADES)))
    if kind == "D":
        metric = by_id.get(_id(row.get("metric")))
        if metric is None or metric.get("type") != "M":
            problems.append("metric %r is not an M the product ledger holds"
                            % (row.get("metric"),))
        after = _date(row.get("observe_after"))
        if after is None:
            problems.append("observe_after %r is not YYYY-MM-DD"
                            % (row.get("observe_after"),))
        elif day is not None and after < day:
            problems.append("observe_after %s is before the row's date %s"
                            % (after, day))
    if kind == "R":
        decision = by_id.get(_id(row.get("decision")))
        if decision is None or decision.get("type") != "D":
            problems.append("decision %r is not a D the product ledger holds"
                            % (row.get("decision"),))
        if row.get("verdict") in ("met", "missed"):
            for key, want in OBSERVED.items():
                problem = _field(row, key, want)
                if problem:
                    problems.append(problem + " (an observed R carries it)")
    return problems


def _held(handle):
    """The rows read through the locked descriptor, to its committed boundary."""
    size = committed_size(handle)
    handle.seek(0)
    text = handle.read(size).decode("utf-8", "replace")
    return [row for _n, row in _lines(text) if row is not None]


def append_row(repo, row, date=""):
    """(id, problems); problems is [] exactly when the row was written.

    The writer assigns `id` (`<type><n>`, n one past the highest of that type)
    and `date` (`date`, else today) from the rows read through the locked
    descriptor, so a caller supplying either is refused. Only the main checkout
    writes: ids assigned in two checkouts would collide."""
    if not isinstance(row, dict):
        return None, ["a product ledger row is a JSON object, not %r" % (row,)]
    main = main_checkout(repo)
    if os.path.realpath(main) != os.path.realpath(repo):
        return None, ["the product ledger is written only in the main checkout %s; "
                      "run `tezgah-research record` there" % main]
    supplied = [k for k in ("id", "date") if k in row]
    if supplied:
        return None, ["%s is the writer's to assign; drop it from the row" % k
                      for k in supplied]
    tp.ensure_workspace(main)
    path = ledger_path(main)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    created = not os.path.isfile(path)
    with open(path, "a+b") as handle:
        problem = tr._locked(handle, LABEL)
        if problem:
            if created and os.path.getsize(path) == 0:
                os.remove(path)
            return None, [problem]
        held = _held(handle)
        new = dict(row, date=date or datetime.date.today().isoformat())
        kind = row.get("type")
        if kind in TYPES:
            numbers = [int(r["id"][1:]) for r in held if isinstance(r.get("id"), str)
                       and re.fullmatch(r"%s\d+" % kind, r["id"])]
            new["id"] = "%s%d" % (kind, max(numbers, default=0) + 1)
        problems = row_problems(new, held, main)
        if problems:
            if created and os.path.getsize(path) == 0:
                os.remove(path)
            return None, problems
        truncate_to_committed(handle)
        line = json.dumps(new, ensure_ascii=False)
        for char in ("\u2028", "\u2029", "\x85"):
            line = line.replace(char, "\\u%04x" % ord(char))
        handle.write(line.encode("utf-8") + b"\n")
    return new["id"], []


def _due(rows, today):
    """`due` over rows already read. An ISO date orders as its text, so only a
    row already due pays for the date parse."""
    iso = today.isoformat()
    measured = {_id(r.get("decision")) for r in rows if r.get("type") == "R"}
    out = []
    for r in rows:
        after = r.get("observe_after")
        if r.get("type") != "D" or not isinstance(after, str) or after >= iso \
                or _id(r.get("id")) in measured:
            continue
        day = _date(after)
        if day is None:
            continue
        out.append({"id": r.get("id"), "topic": r.get("topic"),
                    "metric": r.get("metric"), "threshold": r.get("threshold"),
                    "observe_after": after, "days_overdue": (today - day).days})
    return sorted(out, key=lambda d: d["observe_after"])


def due(repo, today=""):
    """The D rows whose `observe_after` has passed with no R re-measuring them,
    oldest `observe_after` first.

    The session note calls this on every start, so a line is parsed only when it
    can matter: one with an `observe_after` text before today, an R, or one
    carrying a `\\u` escape. An ISO date orders as its text."""
    day = _date(today) if today else datetime.date.today()
    if day is None:
        return []
    text, _exc = tr._committed_text(ledger_path(repo))
    if not text:
        return []
    iso = day.isoformat()
    hits = {m.start() for m in AFTER.finditer(text) if m.group(1) < iso}
    escaped = [m.start() for m in ESCAPE.finditer(text)]
    if not (hits or escaped):
        return []
    hits.update(escaped)
    hits.update(m.start() for m in R_TYPE.finditer(text))
    keep = {}
    for at in hits:
        begin = text.rfind("\n", 0, at) + 1
        if begin not in keep:
            # The committed text ends with a newline, so one follows every hit.
            keep[begin] = text[begin:text.find("\n", at)]
    rows = _lines("\n".join(keep[b] for b in sorted(keep)))
    return _due([row for _n, row in rows if row is not None], day)


def consumer_tokens(repo):
    """[(relpath, line number, id)] of every `product:<id>` citation in
    `.tezgah/analysis` and `.tezgah/plans` markdown and in the design contract's
    component `decision` fields. A bare `D4` is not a citation."""
    ws = tp.workspace(repo)
    out = []
    for sub in ("analysis", "plans"):
        for folder, _dirs, files in sorted(os.walk(os.path.join(ws, sub))):
            for name in sorted(files):
                if name.endswith(".md"):
                    out += _tokens_in(repo, os.path.join(folder, name))
    contract = os.path.join(ws, "design-contract.md")
    try:
        with open(contract, encoding="utf-8") as fh:
            text = fh.read()
    except (OSError, UnicodeDecodeError):
        return out
    block = DESIGN_BLOCK.search(text)
    try:
        data = json.loads(block.group(1)) if block else {}
    except (ValueError, RecursionError):
        data = {}
    comps = data.get("components") if isinstance(data, dict) else None
    cited = set()
    for comp in comps if isinstance(comps, list) else []:
        decision = comp.get("decision") if isinstance(comp, dict) else None
        for value in decision if isinstance(decision, list) else [decision]:
            if isinstance(value, str):
                cited.update(TOKEN.findall(value))
    if cited:
        first = text[:block.start(1)].count("\n") + 1
        rel = os.path.relpath(contract, repo)
        for n, line in enumerate(block.group(1).splitlines(), first):
            out += [(rel, n, t) for t in TOKEN.findall(line) if t in cited]
    return out


def in_use(repo):
    """True when there is a product ledger to check: the main checkout's file,
    a committed version of it in the private `.tezgah` history, or a `product:`
    citation. The history read forks git: never on the session_start path."""
    main = main_checkout(repo)
    path = ledger_path(main)
    return (os.path.exists(path) or bool(consumer_tokens(repo))
            or bool(tr.file_versions(main, path)))


def _tokens_in(repo, path):
    try:
        with open(path, encoding="utf-8") as fh:
            lines = fh.read().splitlines()
    except (OSError, UnicodeDecodeError):
        return []
    rel = os.path.relpath(path, repo)
    return [(rel, n, t) for n, line in enumerate(lines, 1) for t in TOKEN.findall(line)]


def check_ledger(repo, strict=False, git=True):
    """{"errors", "warnings"} for the main checkout's product ledger and the
    citations `repo` holds."""
    errors, warnings = [], []
    main = main_checkout(repo)
    path = ledger_path(main)
    held = []
    if os.path.isfile(path):
        text, exc = tr._committed_text(path)
        if exc:
            errors.append("product ledger %s cannot be read: %s" % (LABEL, exc))
        for n, row in _lines(text or ""):
            if row is None:
                errors.append("product ledger line %d is not a JSON object" % n)
                continue
            errors += ["product ledger line %d (%s): %s" % (n, row.get("id"), p)
                       for p in row_problems(row, held, main)]
            held.append(row)
        if git:
            tr._check_append_only(main, "product ledger (%s)" % LABEL, path, errors,
                                  warnings, True, noun="product ledger rows",
                                  after="it was committed")
    elif git and any(text.strip() for _sha, text in tr.file_versions(main, path)):
        errors.append("product ledger (%s) was removed after it was committed: its "
                      "committed rows went missing, and product ledger rows are "
                      "append-only - a correction is a new row" % LABEL)
    for r in held:
        if r.get("type") == "I" and not r.get("from"):
            tr._soft(errors, warnings, strict, "product ledger %s (%s) rests on no "
                     "observation: its from is empty" % (r.get("id"), r.get("topic")))
    for d in _due(held, datetime.date.today()):
        tr._soft(errors, warnings, strict, "product ledger %s (%s) is due for "
                 "re-measure since %s and no R records it" % (
                     d["id"], d["topic"], d["observe_after"]))
    for i, r in enumerate(held):
        metric = next((m for m in held[:i] if m.get("type") == "M"
                       and m.get("id") == r.get("metric")), None)
        if r.get("type") != "D" or metric is None or metric.get("logged") != "no":
            continue
        later = held[held.index(metric) + 1:]
        if not any(m.get("type") == "M" and m.get("signal") == metric.get("signal")
                   and m.get("logged") == "yes" for m in later):
            tr._soft(errors, warnings, strict, "product ledger %s (%s) is measured by "
                     "%s, whose signal %r is not logged and no later M logs it" % (
                         r.get("id"), r.get("topic"), metric.get("id"),
                         metric.get("signal")))
    ids = {_id(r.get("id")) for r in held}
    for rel, n, tid in consumer_tokens(repo):
        if tid not in ids:
            errors.append("%s:%d cites product:%s, which the product ledger does "
                          "not hold" % (rel, n, tid))
    return {"errors": errors, "warnings": warnings}


def _step(sid, skill, leaves, command):
    return {"id": sid, "skill": skill, "leaves": leaves, "command": command}


# The product-flow playbook (plan 074): the one place its steps are written.
# `next_steps` computes each step's status from the product ledger and the files
# it names; nothing stores it. `{topic}` and `{decision}` in a command are
# filled per topic.
_STEPS = (
    _step("research", "research", "an O of class external and an I",
          "tezgah-research record O (class external), then tezgah-research record I"),
    _step("metrics", "product-analysis", "an M resting on an I",
          "tezgah-research record M"),
    _step("assumptions", "product-analysis", "an A", "tezgah-research record A"),
    _step("decision", "product-analysis", "a D whose metric is one of the topic's M",
          "tezgah-research record D"),
    _step("instrumentation", "product-analysis",
          "every M a D names logged: yes (a later M of the same signal counts)",
          "tezgah-research record M (logged: yes, the same signal)"),
    _step("forward-spec", "feature-audit",
          ".tezgah/analysis/<topic>/spec.md citing product:<D>",
          "feature-audit forward mode: write .tezgah/analysis/{topic}/spec.md "
          "citing product:{decision}"),
    _step("design", "design-contract",
          'a design-contract component with "decision": "product:<D>"',
          'design-contract: set a component\'s "decision": "product:{decision}" '
          "in .tezgah/design-contract.md"),
    _step("build", "design-contract",
          "nothing in the product ledger (the Stop UI rule and tezgah-design check "
          "own it)", "tezgah-design check"),
    _step("re-measure", "analyze-app", "an R whose decision is the D",
          "tezgah-research record R (decision {decision})"),
)
FLOWS = {
    "metric-dashboard": _STEPS,
    # A feature may reuse a metric another topic owns: its own M steps join the
    # flow only when the topic holds an M (`next_steps`).
    "feature": tuple(s for s in _STEPS if s["id"] not in ("metrics", "instrumentation")),
}


def next_steps(repo, topic, flow="metric-dashboard", today=""):
    """[{"id", "skill", "status", "detail", "command"}] for `topic` under `flow`,
    status one of done | missing | due | n/a, read from the main checkout's
    product ledger and the spec and design contract it cites; [] when the topic
    holds no rows. The `feature` flow runs `metric-dashboard`'s steps once the
    topic holds an M; before that, its decision is any D of the topic."""
    if flow not in FLOWS:
        raise ValueError("unknown flow %r (%s)" % (flow, ", ".join(FLOWS)))
    day = _date(today) if today else datetime.date.today()
    if day is None:
        raise ValueError("today %r is not YYYY-MM-DD" % (today,))
    main = main_checkout(repo)
    rows = read_rows(main)
    # No row the writer takes holds a topic outside TOPIC, and the topic becomes
    # a path below.
    mine = [r for r in rows if r.get("topic") == topic] \
        if isinstance(topic, str) and TOPIC.fullmatch(topic) else []
    if not mine:
        return []
    by_id = {_id(r.get("id")): r for r in rows}

    def ids(kind, keep=lambda r: True):
        return [r["id"] for r in mine if r.get("type") == kind
                and isinstance(r.get("id"), str) and keep(r)]

    ms = ids("M")
    steps = FLOWS[flow]
    if flow == "feature" and ms:
        steps = FLOWS["metric-dashboard"]
    decisions = ids("D", lambda r: _id(r.get("metric")) in ms
                    or (not ms and flow == "feature"))
    latest = decisions[-1] if decisions else "<D>"
    status = {}

    external = ids("O", lambda r: r.get("class") == "external")
    insights = ids("I")
    lacking = [w for w, have in (("O of class external", external),
                                 ("I", insights)) if not have]
    status["research"] = ("missing", "no " + " and no ".join(lacking)) if lacking \
        else ("done", "%s, %s" % (", ".join(external), ", ".join(insights)))

    grounded = ids("M", lambda r: any(
        (by_id.get(_id(p)) or {}).get("type") == "I"
        for p in (r.get("from") if isinstance(r.get("from"), list) else [])))
    status["metrics"] = ("done", ", ".join(grounded)) if grounded \
        else ("missing", "no M resting on an I")

    assumed = ids("A")
    status["assumptions"] = ("done", ", ".join(assumed)) if assumed \
        else ("missing", "no A")

    status["decision"] = ("done", ", ".join(
        "%s (metric %s)" % (d, by_id[d].get("metric")) for d in decisions)) \
        if decisions else ("missing", "no D measured by one of the topic's M"
                           if ms or flow != "feature" else "no D")

    # The check_ledger rule: rows never change, so a later M of the same signal
    # logged yes is what instruments an M that was not.
    unlogged = []
    for mid in dict.fromkeys(_id(by_id[d].get("metric")) for d in decisions):
        metric = by_id.get(mid)
        if metric is None or metric.get("type") != "M":
            unlogged.append("%r is not an M the product ledger holds" % (mid,))
            continue
        later = rows[rows.index(metric):]
        if not any(m.get("type") == "M" and m.get("logged") == "yes"
                   and m.get("signal") == metric.get("signal") for m in later):
            unlogged.append("%s (signal %r) is logged: %s"
                            % (mid, metric.get("signal"), metric.get("logged")))
    status["instrumentation"] = ("missing", "no D names an M") if not decisions \
        else ("missing", "; ".join(unlogged)) if unlogged \
        else ("done", "every M a D names is logged")

    ws = tp.workspace(main)
    spec = os.path.join(ws, "analysis", topic, "spec.md")
    spec_rel = os.path.relpath(spec, main)
    cited = [t for _r, _n, t in _tokens_in(main, spec) if t in decisions]
    status["forward-spec"] = ("missing", "no D yet") if not decisions \
        else ("missing", "%s does not exist" % spec_rel) if not os.path.isfile(spec) \
        else ("done", "%s cites product:%s" % (spec_rel, cited[0])) if cited \
        else ("missing", "%s cites none of %s" % (spec_rel, ", ".join(
            "product:" + d for d in decisions)))

    contract = os.path.relpath(os.path.join(ws, "design-contract.md"), main)
    designed = [(n, t) for rel, n, t in consumer_tokens(main)
                if rel == contract and t in decisions]
    status["design"] = ("missing", "no D yet") if not decisions \
        else ("done", "%s:%d cites product:%s" % ((contract,) + designed[0])) \
        if designed else ("missing", "no design-contract component cites %s"
                          % ", ".join("product:" + d for d in decisions))

    status["build"] = ("n/a", "the Stop UI rule and tezgah-design check own it")

    overdue = [d for d in _due(rows, day) if d["id"] in decisions]
    measured = {_id(r.get("decision")) for r in rows if r.get("type") == "R"}
    waiting = [d for d in decisions if d not in measured]
    status["re-measure"] = ("missing", "no D yet") if not decisions \
        else ("due", "; ".join("%s due since %s" % (d["id"], d["observe_after"])
                               for d in overdue)) if overdue \
        else ("missing", "; ".join("%s due on %s" % (d, by_id[d].get("observe_after"))
                                   for d in waiting)) if waiting \
        else ("done", "every D has an R")

    return [{"id": s["id"], "skill": s["skill"], "status": status[s["id"]][0],
             "detail": status[s["id"]][1],
             "command": s["command"].format(topic=topic, decision=latest)}
            for s in steps]
