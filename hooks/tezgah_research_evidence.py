"""Rules 8 evidence: the certainty engine, the instrument ledger, release-check, calibration.

Spec: `.tezgah/analysis/rules8/spec.md` sections 1, 2, 3.1, 3.2, 3.4 and 4.3.

- `check(repo, slug, base, state, errors, warnings, strict, git, steps)` runs last in
  `check_line`, over the `steps` dict (claim id -> step names) CAPTURE and CORE filled. It adds
  the instrument steps (3.1, 3.2), computes each claim's certainty (1), appends the report lines
  to `steps["#report"]` and the per-claim dict to `steps["#certainty"]`. It never prints.
- `conclude_problems(repo, slug, base, state)`: the 3.1 conclude-time switch-or-narrow rule.
- `COMMANDS`: the CLI handlers, handler(repo, args) -> exit code; each prints its own output.
"""
import hashlib
import json
import os
import re
import subprocess
import sys
import time

import tezgah_research as tr
import tezgah_research_stats as st

LEVELS = ("very-low", "low", "moderate", "high")
DEC, CEIL = "-1", "ceil"
# Section 2 as data: every step name `check` prints, with its effect.
STEPS = {
    "header-mismatch": DEC, "unindexed-source": DEC, "online-drift": DEC,
    "abstract-only": DEC, "source-not-captured": CEIL, "one-connector": DEC,
    "no-counter-search": DEC, "no-stopping-rule": DEC, "stopping-not-met": DEC,
    "known-item-missed": DEC, "fewer-than-two-rivals": DEC, "no-replication": DEC,
    "no-power-plan": DEC, "below-planned-n": DEC, "no-interval": CEIL,
    "interval-includes-zero": CEIL, "below-achieved-mde": CEIL,
    "no-multiplicity-correction": DEC, "fails-multiplicity": CEIL, "no-sesoi": CEIL,
    "tost-not-passed": CEIL, "untraced-number": DEC, "instrument-unvalidated": CEIL,
    "instrument-rejected": CEIL, "judged-row-incomplete": DEC, "uncalibrated-verifier": CEIL,
    "no-question-class": DEC, "class-unreviewed": DEC, "method-not-allowed": DEC,
    "no-dual-screening": DEC, "no-recall-stopping": DEC, "no-positive-control": DEC,
    "no-confounders": DEC, "no-population": DEC, "no-grey-quality": DEC, "no-amstar": DEC,
    "no-codebook": DEC, "fewer-than-two-approaches": DEC,
}
SOURCE_START = {"formal": 2, "grey": 1, "agent-report": 0}
KIND_START = {"code": 3, "derivation": 2}
DROPPED = ("aborted", "failed")
VERDICT_BOUND = 0.10
OPENROUTER = "https://openrouter.ai/api/v1/chat/completions"
PROMPT = ("Instrument: %s\nConstruct: %s\nItem: %s\nText: %s\nAnswer 1 if the construct "
          "holds for this item, else 0. Reply with the digit only.")
RUNGS = ("R1", "R2", "R3", "R4")
INSTRUMENTS = "instruments/INSTRUMENTS.jsonl"
GOLD = "instruments/GOLD.jsonl"
LABELS = "instruments/labels.jsonl"
SWITCHES = "instruments/switches.jsonl"
VERDICTS = "instruments/verdicts.jsonl"
KNOWN_TRUTH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                           "tests", "fixtures", "rules8-known-truth")


def _now():
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _rows(base, rel):
    return tr._row_objects(os.path.join(base, rel))


def _label(text, key):
    """The first `key: value` line of a protocol, or None."""
    found = re.search(r"(?im)^%s[ \t]*:[ \t]*(.*)$" % re.escape(key), text)
    return found.group(1).strip() if found else None


def _protocol(base, h):
    try:
        with open(os.path.join(base, "experiments", h, "protocol.md"), encoding="utf-8") as fh:
            return fh.read()
    except (OSError, UnicodeDecodeError):
        return ""


def _results(base, h):
    """The experiment's rows that count: aborted and failed runs stay rows and are left out."""
    return [r for r in _rows(base, "experiments/%s/results.jsonl" % h)
            if r.get("status") not in DROPPED]


# --- instruments (3.1, 3.2) ---------------------------------------------------------
def _row_instrument(row):
    name = row.get("instrument") or row.get("judge")
    return name if isinstance(name, str) and name.strip() else None


def instrument_items(base):
    """{name: {arm: {item: row}}} - the first row per item, in file order."""
    out = {}
    for h in tr._experiment_names(base):
        for row in _results(base, h):
            name = _row_instrument(row)
            if name and row.get("item") is not None:
                arm = str(row.get("arm") or "all")
                out.setdefault(name, {}).setdefault(arm, {}).setdefault(str(row["item"]), row)
    for row in _rows(base, VERDICTS):
        name = _row_instrument(row)
        if name and row.get("item") is not None:
            out.setdefault(name, {}).setdefault("all", {}).setdefault(str(row["item"]), row)
    return out


def _experiments_of(base):
    """{instrument name: set of experiments whose rows name it}."""
    out = {}
    for h in tr._experiment_names(base):
        for row in _results(base, h):
            name = _row_instrument(row)
            if name:
                out.setdefault(name, set()).add(h)
    return out


def _mde(text):
    value = _label(text, "mde")
    found = re.search(r"-?\d+(?:\.\d+)?", value or "")
    return float(found.group(0)) if found else None


def seeded_draw(items, seed, arm, n):
    """The arm's items sorted by sha256("<seed>:<arm>:<item>") hex, the first n."""
    return sorted({str(i) for i in items}, key=lambda item: hashlib.sha256(
        ("%s:%s:%s" % (seed, arm, item)).encode("utf-8")).hexdigest())[:n]


def first_draws(base):
    """{(instrument, arm): gold record} of the first GOLD row per pair whose file reads."""
    out = {}
    for row in _rows(base, GOLD):
        key = (row.get("instrument"), str(row.get("arm")))
        if key in out or not isinstance(row.get("file"), str):
            continue
        record, exc = tr._read_json(os.path.join(base, row["file"]))
        if not exc and isinstance(record, dict) and isinstance(record.get("items"), list):
            out[key] = record
    return out


def first_labels(base):
    """({(instrument, arm, item): label row}, [repeated items]) - the first label counts."""
    out, repeated = {}, []
    for row in _rows(base, LABELS):
        key = (row.get("instrument"), str(row.get("arm")), str(row.get("item")))
        if key in out:
            repeated.append(key)
        else:
            out[key] = row
    return out, repeated


def arm_score(record, labels, name, arm):
    """(n, errors) of a labelled arm, or None when an item of its draw has no label."""
    items = [str(i) for i in record["items"]]
    got = [labels.get((name, arm, i)) for i in items]
    if not items or any(g is None for g in got):
        return None
    return len(items), sum(1 for g in got if g.get("truth") != g.get("output"))


def judge_status(kind, uppers, threshold):
    """(status or None, aggregate) from the labelled arms' uppers ({arm: upper}), per 3.1:
    rejected when the threshold fails over the labelled arms alone. A measure instrument
    with no `mde:` has no threshold, so it is never rejected and never validated."""
    if kind == "verdict":
        agg = max(uppers.values()) if uppers else 0.0
        failed = any(u > VERDICT_BOUND for u in uppers.values())
    else:
        agg = sum(uppers.values())
        failed = bool(uppers) and threshold is not None and agg >= threshold
    return ("rejected" if failed else None), agg


def instrument_report(base, slug):
    """({name: status}, report lines)."""
    declared = {}
    for row in _rows(base, INSTRUMENTS):
        if isinstance(row.get("name"), str):
            declared.setdefault(row["name"], row)
    items = instrument_items(base)
    used = _experiments_of(base)
    draws = first_draws(base)
    labels, _ = first_labels(base)
    statuses, lines = {}, []
    for name in sorted(set(declared) | set(items)):
        spec = declared.get(name)
        kind = spec.get("kind") if spec else "measure"
        mdes = [m for m in (_mde(_protocol(base, h)) for h in used.get(name, ())) if m is not None]
        threshold = VERDICT_BOUND if kind == "verdict" else (min(mdes) if mdes else None)
        uppers, complete = {}, True
        for arm in sorted(items.get(name, {})):
            record = draws.get((name, arm))
            score = arm_score(record, labels, name, arm) if record else None
            if score is None:
                complete = False
                continue
            n, errors = score
            uppers[arm] = st.clopper_pearson(errors, n)[1]
            lines.append("instrument %s: %s arm %s n=%d errors=%d upper=%.4f"
                         % (slug, name, arm, n, errors, uppers[arm]))
            if spec and spec.get("rung") == "R3":
                lines.extend(_ppi_line(slug, name, arm, record, labels, items[name][arm]))
        status, agg = judge_status(kind, uppers, threshold)
        if status is None:
            status = "validated" if spec and uppers and complete and threshold is not None \
                else "unvalidated"
        statuses[name] = status
        lines.append("instrument %s: %s %s %s=%.4f threshold=%s"
                     % (slug, name, status, "max" if kind == "verdict" else "sum", agg,
                        "none" if threshold is None else "%.4f" % threshold))
    return statuses, lines


def _outcome(row):
    value = row.get("outcome") if isinstance(row, dict) else None
    return value if isinstance(value, (int, float)) and not isinstance(value, bool) else None


def _ppi_line(slug, name, arm, record, labels, arm_items):
    drawn = [str(i) for i in record["items"]]
    y = [labels[(name, arm, i)].get("truth") for i in drawn]
    f = [labels[(name, arm, i)].get("output") for i in drawn]
    rest = [_outcome(r) for i, r in sorted(arm_items.items()) if i not in drawn]
    if not rest or None in rest or any(not isinstance(v, (int, float)) for v in y + f):
        return []
    lam, est, lo, hi = st.ppi_mean(y, f, rest)
    return ["ppi %s: %s arm %s lambda=%.4f estimate=%.4f ci=[%.4f, %.4f]"
            % (slug, name, arm, lam, est, lo, hi)]


def _items_at(base, rev):
    """{name: {arm: set(items)}} from the results files as committed at `rev`, or None."""
    out = {}
    for h in tr._experiment_names(base):
        rel = "experiments/%s/results.jsonl" % h
        done = subprocess.run(["git", "-C", base, "show", "%s:./%s" % (rev, rel)],
                              capture_output=True, text=True)
        if done.returncode:
            continue
        for raw in done.stdout.splitlines():
            try:
                row = json.loads(raw)
            except ValueError:
                continue
            if isinstance(row, dict) and row.get("status") not in DROPPED \
                    and _row_instrument(row) and row.get("item") is not None:
                out.setdefault(_row_instrument(row), {}).setdefault(
                    str(row.get("arm") or "all"), set()).add(str(row["item"]))
    return out


def _added_rev(base, rel):
    try:
        done = subprocess.run(["git", "-C", base, "log", "--diff-filter=A", "--format=%H",
                               "--", rel], capture_output=True, text=True)
    except OSError:
        return None
    revs = done.stdout.split() if not done.returncode else []
    return revs[-1] if revs else None


def gold_problems(base, git):
    """The `differs from the seeded draw` refusals: a gold file must be its seed's draw over
    the arm's items now, or over the items committed when the file was added."""
    problems = []
    now = instrument_items(base)
    for row in _rows(base, GOLD):
        rel = row.get("file")
        record, exc = tr._read_json(os.path.join(base, rel)) if isinstance(rel, str) \
            else (None, "no file")
        if exc or not isinstance(record, dict):
            continue
        name, arm, seed = record.get("instrument"), str(record.get("arm")), record.get("seed")
        drawn = [str(i) for i in record.get("items") or []]
        n = record.get("n") if isinstance(record.get("n"), int) else len(drawn)

        def drawn_from(pool):
            return len(drawn) == n and seeded_draw(pool, seed, arm, n) == drawn
        if drawn_from(now.get(name, {}).get(arm, {})):
            continue
        rev = _added_rev(base, rel) if git else None
        if not (rev and drawn_from(_items_at(base, rev).get(name, {}).get(arm, set()))):
            problems.append("%s differs from the seeded draw of seed %s over %s arm %s"
                            % (rel, seed, name, arm))
    return problems


# --- certainty (1, 2) ----------------------------------------------------------------
def _experiment_claim(claim):
    return tr._experiments_named(tr._cited(claim.get("proof")))


def start_level(claim, base, classes):
    """The highest start over the parts the claim's proof cites (section 1 table)."""
    levels = [KIND_START[claim.get("kind")]] if claim.get("kind") in KIND_START else []
    for h in _experiment_claim(claim):
        text = _protocol(base, h)
        design = (_label(text, "design") or "").lower()
        if not design:
            design = "experiment" if _label(text, "change") is not None else "observational"
        levels.append(3 if design.startswith("experiment") else 1)
    import tezgah_research_capture as cap
    for token in cap.cited_tokens(claim.get("proof")):
        if token.startswith("literature/") and not token.startswith("literature/."):
            levels.append(SOURCE_START.get(classes.get(token[len("literature/"):]), 0))
    return max(levels) if levels else 0


def compute(start, names):
    """(level, steps): decrements first, then ceilings; each step once, in order found."""
    seen = list(dict.fromkeys(names))
    level = max(0, start - sum(1 for s in seen if STEPS.get(s) == DEC))
    if any(STEPS.get(s) == CEIL for s in seen):
        level = min(level, 1)
    return level, seen


def _add(steps, cid, name):
    steps.setdefault(cid, [])
    if name not in steps[cid]:
        steps[cid].append(name)


def _report_line(text, cid, level):
    """True when a report line names the claim id and its level word (and `exploratory`
    below moderate)."""
    word = re.compile(r"(?<![\w-])%s(?![\w-])" % re.escape(LEVELS[level]))
    ident = re.compile(r"(?<![\w-])%s(?![\w-])" % re.escape(cid))
    return any(ident.search(line) and word.search(line)
               and (level >= 2 or "exploratory" in line) for line in text.splitlines())


def check(repo, slug, base, state, errors, warnings, strict, git, steps):
    report = steps.setdefault("#report", [])
    claims = [c for c in _rows(base, "claims.jsonl") if isinstance(c.get("id"), str)]
    statuses, lines = instrument_report(base, slug)
    report.extend(lines)
    errors.extend(gold_problems(base, git))
    _, repeated = first_labels(base)
    for _name, _arm, item in repeated:
        warnings.append("label repeated for %s; the first counts" % item)
    by_exp = _experiments_of(base)
    for claim in claims:
        cid = claim["id"]
        for h in _experiment_claim(claim):
            for name, exps in sorted(by_exp.items()):
                if h in exps and statuses.get(name) in ("unvalidated", "rejected"):
                    _add(steps, cid, "instrument-" + statuses[name])
            if any(r.get("judge") and not (r.get("generator") and r.get("order"))
                   for r in _results(base, h)):
                _add(steps, cid, "judged-row-incomplete")
        verifier = claim.get("verified_by")
        if verifier:
            spec = next((r for r in _rows(base, INSTRUMENTS) if r.get("name") == verifier), {})
            if spec.get("kind") != "verdict" or statuses.get(verifier) != "validated":
                _add(steps, cid, "uncalibrated-verifier")
    classes = tr._index_classes(base)
    certainty = steps.setdefault("#certainty", {})
    try:
        with open(os.path.join(base, "to_human", "report.md"), encoding="utf-8") as fh:
            text = fh.read()
    except (OSError, UnicodeDecodeError):
        text = ""
    concluded = tr._concluding(base, state)
    for claim in claims:
        cid = claim["id"]
        start = start_level(claim, base, classes)
        level, names = compute(start, steps.get(cid, []))
        certainty[cid] = {"level": LEVELS[level], "start": LEVELS[start], "steps": names}
        report.append("certainty %s: %s %s start=%s steps=%s"
                      % (slug, cid, LEVELS[level], LEVELS[start], ",".join(names) or "none"))
        declared = claim.get("certainty")
        if declared in LEVELS and LEVELS.index(declared) > level:
            errors.append("claim %s declares certainty %s above the computed %s (%s)"
                          % (cid, declared, LEVELS[level], ",".join(names) or "none"))
        if concluded and not _report_line(text, cid, level):
            tr._soft(errors, warnings, strict, "report states no certainty for claim %s" % cid)
    labels = _rows(base, LABELS)
    human = sum(1 for r in labels if (r.get("rater") or {}).get("kind") == "human")
    if concluded and human and not re.search(r"user-supplied:\s*\d+\s+of\s+\d+\s+labels", text):
        tr._soft(errors, warnings, strict, "report states no user-supplied share of labels "
                 "(user-supplied: %d of %d labels)" % (human, len(first_labels(base)[0])))


def conclude_problems(repo, slug, base, state):
    """A rejected instrument needs a switches.jsonl row before `conclude` (3.1)."""
    statuses, _ = instrument_report(base, slug)
    switched = {r.get("instrument") for r in _rows(base, SWITCHES)}
    return ["instrument %s is rejected and has no switch or narrowing row: run `tezgah-research "
            "switch %s %s --to <rung|method>|--narrow \"<what the claims now say>\" --reason "
            "\"<why>\"`" % (name, slug, name)
            for name, status in sorted(statuses.items())
            if status == "rejected" and name not in switched]


# --- commands ----------------------------------------------------------------------
def _misuse(message):
    print("tezgah-research: %s" % message, file=sys.stderr)
    return 2


def _fail(slug, message):
    print("FAIL %s: %s" % (slug, message))
    return 1


def _flags(args, valued, usage):
    """({flag: value}, None) or (None, exit code); every flag takes one value."""
    out, rest = {}, list(args)
    while rest:
        flag = rest.pop(0)
        if flag not in valued or not rest:
            return None, _misuse(usage)
        out[flag] = rest.pop(0)
    return out, None


def _line(repo, slug):
    """(base, None) or (None, exit code)."""
    if not repo or slug not in tr.slugs(repo):
        return None, _misuse("no such research line: %s" % slug)
    base = tr.line_dir(repo, slug)
    newer = tr.newer_rules(tr._state(base))
    if newer:
        return None, _fail(slug, newer)
    return base, None


def _append(base, rel, rows):
    import tezgah_research_capture as cap
    cap.append_rows(base, rel, rows)


def _commit(repo, base, rels, command, slug):
    import tezgah_research_capture as cap
    err = cap.commit_capture(repo, base, rels, command, slug)
    if err:
        print("commit failed: %s" % err)
        return 1
    return 0


def cmd_instrument(repo, args):
    usage = ('instrument add <slug> <name> --kind measure|verdict --rung R1|R2|R3|R4 '
             '--construct "<text>"')
    if len(args) < 3 or args[0] != "add":
        return _misuse(usage)
    slug, name = args[1], args[2]
    flags, code = _flags(args[3:], ("--kind", "--rung", "--construct"), usage)
    if code is not None:
        return code
    if flags.get("--kind") not in ("measure", "verdict") or flags.get("--rung") not in RUNGS \
            or not flags.get("--construct", "").strip() or not name.strip():
        return _misuse(usage)
    base, code = _line(repo, slug)
    if code is not None:
        return code
    if any(r.get("name") == name for r in _rows(base, INSTRUMENTS)):
        return _fail(slug, "instrument %s is already in %s" % (name, INSTRUMENTS))
    _append(base, INSTRUMENTS, [{"name": name, "kind": flags["--kind"], "rung": flags["--rung"],
                                 "construct": flags["--construct"], "added_at": _now()}])
    print("instrument %s added to %s" % (name, INSTRUMENTS))
    return _commit(repo, base, [INSTRUMENTS], "instrument add", slug)


def cmd_gold(repo, args):
    usage = "gold <slug> <instrument> --arm <a> --n N --seed S"
    if len(args) < 2:
        return _misuse(usage)
    slug, name = args[0], args[1]
    flags, code = _flags(args[2:], ("--arm", "--n", "--seed"), usage)
    if code is not None:
        return code
    try:
        n, seed = int(flags["--n"]), int(flags["--seed"])
        arm = flags["--arm"]
    except (KeyError, ValueError):
        return _misuse(usage)
    if n < 1:
        return _misuse(usage)
    base, code = _line(repo, slug)
    if code is not None:
        return code
    if any(r.get("instrument") == name and str(r.get("arm")) == arm
           for r in _rows(base, LABELS)):
        return _fail(slug, "gold draw after labels: %s arm %s already has labels, so its first "
                     "draw stays the one every rule reads" % (name, arm))
    items = instrument_items(base).get(name, {}).get(arm, {})
    if len(items) < n:
        return _fail(slug, "%s arm %s has %d items, fewer than --n %d" % (name, arm, len(items), n))
    record = {"instrument": name, "arm": arm, "seed": seed, "n": n,
              "items": seeded_draw(items, seed, arm, n)}
    data = (json.dumps(record, indent=2) + "\n").encode("utf-8")
    rel = "instruments/gold/%s-%s-%d.json" % (name, arm, seed)
    import tezgah_research_capture as cap
    problem = cap.write_capture(base, rel, data)
    if problem:
        return _fail(slug, problem)
    _append(base, GOLD, [{"instrument": name, "arm": arm, "seed": seed, "n": n, "file": rel,
                          "sha256": hashlib.sha256(data).hexdigest(), "drawn_at": _now()}])
    print("gold %s: %d items of %s arm %s" % (rel, n, name, arm))
    return _commit(repo, base, [rel, GOLD], "gold", slug)


def _ask_model(name, construct, item, text, model, key):
    """(truth or None, the response's model)."""
    import tezgah_research_capture as cap
    body = json.dumps({"messages": [{"content": PROMPT % (name, construct, item, text),
                                     "role": "user"}], "model": model, "temperature": 0},
                      sort_keys=True, separators=(",", ":")).encode("utf-8")
    status, data = cap.fetch_url(OPENROUTER, body=body,
                                 headers={"Authorization": "Bearer " + key,
                                          "Content-Type": "application/json"})
    try:
        answer = json.loads(data.decode("utf-8"))
        content = answer["choices"][0]["message"]["content"]
    except (ValueError, KeyError, IndexError, TypeError, AttributeError, UnicodeDecodeError):
        return None, None
    found = re.search(r"[01]", content if status == 200 and isinstance(content, str) else "")
    return (int(found.group(0)) if found else None), answer.get("model")


def cmd_label(repo, args):
    usage = ('label <slug> <instrument> --arm <a> (--human "<name>" --ack "<the user\'s words>"'
             ' | --provider openrouter --model <m>)')
    if len(args) < 2:
        return _misuse(usage)
    slug, name = args[0], args[1]
    flags, code = _flags(args[2:], ("--arm", "--human", "--ack", "--provider", "--model"), usage)
    if code is not None:
        return code
    arm = flags.get("--arm")
    human = "--human" in flags
    if not arm or human == ("--provider" in flags):
        return _misuse(usage)
    if human and not flags.get("--ack", "").strip():
        return _misuse("label --human needs --ack \"<the user's words>\"")
    key = os.environ.get("OPENROUTER_API_KEY", "")
    if not human:
        if flags["--provider"] != "openrouter" or not flags.get("--model"):
            return _misuse(usage)
        if not key:
            return _misuse("label --provider openrouter needs OPENROUTER_API_KEY")
    base, code = _line(repo, slug)
    if code is not None:
        return code
    record = first_draws(base).get((name, arm))
    if record is None:
        return _fail(slug, "%s arm %s has no gold draw: run `gold` first" % (name, arm))
    drawn = [str(i) for i in record["items"]]
    rows = instrument_items(base).get(name, {}).get(arm, {})
    out = []
    if human:
        rater = {"kind": "human", "name": flags["--human"], "ack": flags["--ack"]}
        for raw in sys.stdin.read().splitlines():
            if not raw.strip():
                continue
            try:
                given = json.loads(raw)
                item, truth = str(given["item"]), given["truth"]
            except (ValueError, KeyError, TypeError):
                return _misuse("label --human reads JSONL {\"item\", \"truth\"} on stdin")
            if truth not in (0, 1) or isinstance(truth, bool):
                return _misuse("truth of %s is %r, not 0 or 1" % (item, truth))
            if item not in drawn:
                return _fail(slug, "%s is not in the gold sample of %s arm %s" % (item, name, arm))
            out.append((item, truth, rater))
    else:
        spec = next((r for r in _rows(base, INSTRUMENTS) if r.get("name") == name), None)
        if spec is None:
            return _fail(slug, "instrument %s is not in %s" % (name, INSTRUMENTS))
        for item in drawn:
            text = (rows.get(item) or {}).get("text") or ""
            truth, model = _ask_model(name, spec.get("construct", ""), item, text,
                                      flags["--model"], key)
            if truth is not None:
                out.append((item, truth, {"kind": "model", "provider": "openrouter",
                                          "model": model}))
    when = _now()
    _append(base, LABELS, [{"instrument": name, "arm": arm, "item": item, "truth": truth,
                            "output": _outcome(rows.get(item)), "rater": rater,
                            "labelled_at": when} for item, truth, rater in out])
    print("labels %d of %d gold items of %s arm %s" % (len(out), len(drawn), name, arm))
    return _commit(repo, base, [LABELS], "label", slug)


def cmd_switch(repo, args):
    usage = ('switch <slug> <instrument> (--to R1|R2|R3|R4|<method> | --narrow "<what the '
             'claims now say>") --reason "<why>"')
    if len(args) < 2:
        return _misuse(usage)
    slug, name = args[0], args[1]
    flags, code = _flags(args[2:], ("--to", "--narrow", "--reason"), usage)
    if code is not None:
        return code
    if ("--to" in flags) == ("--narrow" in flags) or not flags.get("--reason", "").strip() \
            or not (flags.get("--to") or flags.get("--narrow") or "").strip():
        return _misuse(usage)
    base, code = _line(repo, slug)
    if code is not None:
        return code
    row = {"instrument": name, "reason": flags["--reason"], "switched_at": _now()}
    row.update({"to": flags["--to"]} if "--to" in flags else {"narrow": flags["--narrow"]})
    _append(base, SWITCHES, [row])
    print("switch recorded for %s" % name)
    return _commit(repo, base, [SWITCHES], "switch", slug)


def case_flagged(case, root):
    """True when `check`'s own functions refuse or cap a known-truth case."""
    import tezgah_research_capture as cap
    kind = case.get("kind")
    if kind == "citation":
        return cap.citation_problem(case) is not None
    if kind == "quote":
        with open(os.path.join(root, case["text_file"]), encoding="utf-8") as fh:
            return cap.quote_problem(case["quote"], fh.read()) is not None
    if kind == "instrument":
        # the case row's own `kind` is "instrument", so the instrument's kind is
        # `instrument_kind` (measure by default); a measure case stands for two equal arms
        # of (n, errors), the 3.1 fixed points' shape
        ikind = case.get("instrument_kind", "measure")
        mde = case.get("mde") if ikind == "measure" else VERDICT_BOUND
        upper = st.clopper_pearson(case["errors"], case["n"])[1]
        arms = {"all": upper} if ikind == "verdict" else {"a": upper, "b": upper}
        status, _ = judge_status(ikind, arms, mde)
        return status == "rejected" or mde is None
    raise ValueError("unknown case kind %r" % kind)


def cmd_release_check(repo, args):
    if args and (args[0] != "--fixtures" or len(args) != 2):
        return _misuse("release-check [--fixtures <dir>]")
    root = os.path.abspath(args[1]) if args else KNOWN_TRUTH
    try:
        cases = [json.loads(line) for line in open(os.path.join(root, "cases.jsonl"),
                                                   encoding="utf-8") if line.strip()]
    except (OSError, ValueError) as exc:
        return _misuse("release-check: %s/cases.jsonl does not read (%s)" % (root, exc))
    os.environ["TEZGAH_CAPTURE_MAP"] = os.path.join(root, "capture-map.json")
    counts = {"defect": [0, 0], "sound": [0, 0]}
    for case in cases:
        flagged = case_flagged(case, root)
        tally = counts.setdefault(case.get("truth"), [0, 0])
        tally[1] += 1
        tally[0] += (not flagged) if case.get("truth") == "defect" else flagged
    worst = 0
    for label, truth, bound in (("misses", "defect", 0.10), ("false alarms", "sound", 0.20)):
        k, n = counts[truth]
        upper = st.clopper_pearson(k, n)[1] if n else 1.0
        print("%s: %d/%d upper=%.4f" % (label, k, n, upper))
        worst = max(worst, upper > bound)
    return 1 if worst else 0


def cmd_calibration(repo, args):
    if args:
        return _misuse("calibration takes no arguments")
    pairs = []
    for slug in tr.slugs(repo) if repo else []:
        for h in tr._state(tr.line_dir(repo, slug)).get("hypotheses") or []:
            p = h.get("probability") if isinstance(h, dict) else None
            outcome = {"supported": 1, "refuted": 0}.get(h.get("status")) \
                if isinstance(h, dict) else None
            if isinstance(p, (int, float)) and not isinstance(p, bool) and outcome is not None:
                pairs.append((p, outcome))
    print("brier: %s over %d resolved hypotheses"
          % ("%.4f" % st.brier(pairs) if pairs else "none", len(pairs)))
    return 0


COMMANDS = {"instrument": cmd_instrument, "gold": cmd_gold, "label": cmd_label,
            "switch": cmd_switch, "release-check": cmd_release_check,
            "calibration": cmd_calibration}
