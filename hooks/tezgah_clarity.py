"""The clarity ratchet: countable prose rules over the English docs, held to a baseline.

Four rules are counted per file over docs/*.md and CHANGELOG.md: sentences over
25 words, semicolons, a short list of words with a plainer replacement, and
passive voice. Only English prose written for people is read: fenced code,
code spans (including one broken across lines), link targets, HTML comments,
tables, headings and any line holding a Turkish letter are blanked first, with
their newlines kept so a hit still names its line.

The counts are a ratchet, not a style gate: `docs/clarity-baseline.json` holds
each file's count per rule as measured, a file may not exceed it, a file the
baseline does not list is held to 0, and a count that drops is written back
(lowered) on the next run. Raising a count needs `tezgah-docs --clarity --update`.
The rules and the word list are the frozen measurer of the research line that
chose this check (E1, `measure.py` k1), with the multi-line span fix it required.
"""
import glob
import json
import os
import re

RULES = ("long_sentences", "semicolons", "replace_words", "passive")
LONG = 25
REPLACE = ("commence", "initiate", "utilize", "prior to", "in order to", "ensure",
           "replenish", "indicate", "verify")
REPLACE_RE = re.compile(r"\b(?:%s)\b" % "|".join(re.escape(w) for w in REPLACE), re.I)
PASSIVE = re.compile(r"\b(?:is|are|was|were|be|been|being)\s+(?:\w+ly\s+)?\w+(?:ed|en)\b", re.I)
SENT = re.compile(r"(?<=[.!?])\s+(?=[A-Z(\"'`*])")
ABBREV = re.compile(r"\b(e\.g|i\.e|etc|vs|cf)\.")
WORD = re.compile(r"[A-Za-z0-9][\w'./-]*")
FENCE = re.compile(r"^\s*(```|~~~)")
# a span closes on a backtick run of the same length, across lines inside its paragraph
SPAN = re.compile(r"(?<!`)(`+)(?!`)(.+?)(?<!`)\1(?!`)", re.S)
COMMENT = re.compile(r"<!--.*?-->", re.S)
LINK_TARGET = re.compile(r"\]\([^)]*\)|\]\[[^\]]*\]|<https?://[^>]*>|https?://\S+")
TURKISH = re.compile(r"[ğĞışŞçÇöÖüÜİ]")
SKIP_LINE = re.compile(r"^\s*(?:#|\||\[[^\]]+\]:\s)")
ITEM = re.compile(r"^\s*(?:[-*+]|\d+[.)])\s+")
BASELINE = os.path.join("docs", "clarity-baseline.json")


def _blank(match, keep=""):
    return keep + "\n" * match.group(0).count("\n")


def prose(text):
    """The text with everything but English prose blanked, line count unchanged."""
    lines, fenced = text.split("\n"), None
    for i, line in enumerate(lines):
        m = FENCE.match(line)
        if fenced or m:
            if m and (fenced is None or m.group(1) == fenced):
                fenced = None if fenced else m.group(1)
            lines[i] = ""
    out = []
    # a code span cannot cross a blank line, so an unmatched backtick stays in its paragraph
    for para in re.split(r"(\n[ \t]*\n)", "\n".join(lines)):
        out.append(SPAN.sub(lambda m: _blank(m, " CODE "), para))
    text = LINK_TARGET.sub(lambda m: "]" if m.group(0)[0] == "]" else "",
                           COMMENT.sub(_blank, "".join(out)))
    return "\n".join("" if SKIP_LINE.match(line) or TURKISH.search(line) else line
                     for line in text.split("\n"))


def units(text):
    """(first line number, text) per paragraph or list item of the prose."""
    found, cur, start = [], [], 0
    for n, line in enumerate(prose(text).split("\n") + [""], 1):
        body = ITEM.sub("", line.strip().lstrip(">").lstrip()).strip()
        if not body or ITEM.match(line.strip().lstrip(">").lstrip()):
            if cur:
                found.append((start, " ".join(cur)))
            cur, start = ([body], n) if body else ([], 0)
            continue
        if not cur:
            start = n
        cur.append(body)
    return found


def sentences(unit):
    flat = ABBREV.sub(r"\1", " ".join(unit.split()))
    return [s for s in SENT.split(flat) if WORD.search(s)]


def measure(text):
    """(counts per rule, [(line, rule, snippet)]) for one file's text."""
    counts, hits = dict.fromkeys(RULES, 0), []
    for line, unit in units(text):
        plain = re.sub(r"\bCODE\b", " ", unit)
        found = [("semicolons", m) for m in re.findall(";", plain)]
        found += [("replace_words", m) for m in REPLACE_RE.findall(plain)]
        found += [("passive", m) for m in PASSIVE.findall(plain)]
        found += [("long_sentences", s[:60] + "...") for s in sentences(unit)
                  if len(WORD.findall(s)) > LONG]
        for rule, snippet in found:
            counts[rule] += 1
            hits.append((line, rule, snippet))
    return counts, hits


def files(root):
    return sorted(os.path.relpath(p, root).replace(os.sep, "/")
                  for p in glob.glob(os.path.join(root, "docs", "*.md"))
                  + glob.glob(os.path.join(root, "CHANGELOG.md")))


def tree(root):
    """{relpath: (counts, hits)} for every file the ratchet reads."""
    out = {}
    for rel in files(root):
        with open(os.path.join(root, rel), encoding="utf-8") as fh:
            out[rel] = measure(fh.read())
    return out


def load(path):
    try:
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)
    except FileNotFoundError:
        return {}


def save(path, baseline):
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(baseline, fh, indent=2, sort_keys=True)
        fh.write("\n")


def over(measured, baseline):
    """[(file, rule, count, allowed)] for each count above its baseline (absent: 0)."""
    return [(rel, rule, counts[rule], baseline.get(rel, {}).get(rule, 0))
            for rel, (counts, _) in sorted(measured.items()) for rule in RULES
            if counts[rule] > baseline.get(rel, {}).get(rule, 0)]


def lowered(measured, baseline):
    """The baseline with every count that dropped written down, nothing raised."""
    new = {}
    for rel, allowed in baseline.items():
        if rel in measured:
            counts = measured[rel][0]
            new[rel] = {r: min(allowed.get(r, 0), counts[r]) for r in RULES}
    return new


def report(root, update=False, out=print):
    """Print the per-file counts, the hits of each rule over baseline and one
    summary line; lower (or with `update`, rewrite) the baseline. 0 or 1."""
    path = os.path.join(root, BASELINE)
    measured, baseline = tree(root), load(path)
    for rel, (counts, _) in sorted(measured.items()):
        out("%s  %s" % (rel, " ".join("%s=%d" % (r, counts[r]) for r in RULES)))
    bad = [] if update else over(measured, baseline)
    for rel, rule, count, allowed in bad:
        for line, hit_rule, snippet in measured[rel][1]:
            if hit_rule == rule:
                out("%s:%d  %s  %s" % (rel, line, rule, snippet))
        out("%s  %s: %d, baseline %d" % (rel, rule, count, allowed))
    new = ({rel: counts for rel, (counts, _) in measured.items()} if update
           else lowered(measured, baseline))
    if new != baseline:
        save(path, new)
    totals = {r: sum(c[r] for c, _ in measured.values()) for r in RULES}
    out("clarity: %d files, %s; %d rule(s) over baseline%s"
        % (len(measured), ", ".join("%s %d" % (r, totals[r]) for r in RULES), len(bad),
           " (baseline rewritten)" if update and new != baseline
           else " (baseline lowered)" if new != baseline else ""))
    return 1 if bad else 0
