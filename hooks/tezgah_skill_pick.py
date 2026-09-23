#!/usr/bin/env python3
"""One cheap judgement in front of the skill choice: at most one skill, one line.

A session meets the roster as an index of one-line descriptions, truncated by the
host, so the skill that authors a file reads like the one that edits it, and a
list of names invites a guess even on a turn where nothing in it fits. TypeSafe's
own skill-suggestion cookbook puts a ranking in front of that choice and reports
the effect over 488 requests: wrong skill loads 16.8% -> 7.3%, needless loads
9.8% -> 4.0%.

This is the smallest version of that recipe that fits a hook: ONE batched request
carrying a Choice over the installed skill names (with `none` as an option) and a
Noul asking whether the turn needs a skill at all. The winner becomes one
`<skill_relevance>` line appended to the per-turn text, naming what the skill is
for and saying the line is a hint to look at first. The roster itself is left
untouched - the cookbook keeps it so the host's prefix cache over it still holds,
and on five of the six hosts tezgah does not write that text anyway.

The roster is the plugin's own `skills/` - the 13 this checkout ships and every
host links - because a name no host can open would be a hint to nothing.

OFF UNLESS ARMED: `skill-suggest-on` in `~/.config/tezgah` turns it on. The
roster here is 13 skills, and an independent chooser was measured at 0 of 20
wrong on a labelled set WITHOUT any hint, so the line's benefit on this roster is
unproven while its cost is not (about 78 tokens and 0.8 s per fresh prompt), and a
capability that costs a certain amount for an unmeasured gain is opt-in. Total by
design: no credential, a timeout, a refused request, a reply that is not the
documented shape, a cache dir that cannot be written - every one of them returns
"" instead of raising, since this runs on the prompt path of every turn and a
missing hint must cost the turn nothing.
"""
import hashlib
import json
import os
import re

import tezgah_integrity as ti
import tezgah_judge
import tezgah_paths as tp

ARM = "skill-suggest-on"
# Below this, the turn's own gate question says no skill is wanted and nothing is
# suggested - the cookbook's threshold, which is also where the triage selection
# sits: with `none` in the Choice, a forced nearest-neighbour pick is what the
# gate exists to prevent.
GATE = 0.30
# 10x the measured worst case (0.3-1.1 s live), so a slow reply costs the hint and
# not the user's turn.
ASK_TIMEOUT = 8.0
# The criteria the judge reads per skill, and what the appended line says the
# skill is for. One line: it must not cost more than the index entry it points at
# (the host's own entry is 60 characters), and 120 keeps the whole appended block
# under 320 characters (measured 305-317). The router line in bin/tezgah-setup
# caps its own copy of this sentence at 140.
CLAUSE_CAP = 120
NONE = "none"
CHOICE_INSTRUCTIONS = ("Which of these skills, if any, is the right one to load "
                       "to help with the user's latest request?")
# What "needs a skill" means for THIS roster: tezgah's 13 skills are working
# rules (scope, output shape, workflow, evidence), not the external procedures
# the cookbook's roster holds, so its "documented procedure" question is the wrong
# one here - measured on 8 prompts it put `ponytail` at 0.05-0.24 and lost two
# correct picks. This wording keeps them at 0.47-0.67 and separates the five that
# want a skill (0.80-0.98) from the three that do not (0.01-0.15).
GATE_INSTRUCTIONS = ("Does this request ask for work on the user's repository, "
                     "code, plans, analysis or writing, rather than a question "
                     "answered from general knowledge?")
# One session's answered prompts. Bounded because a session can be long, and keyed
# on the prompt so an identical submission is never paid for twice.
KEPT = 200
_FRONTMATTER = re.compile(r"^---\s*\n(.*?)\n---", re.S)
_FOLDED = re.compile(r"description:\s*[>|]-?\s*\n((?:\s+.*\n?)+)")
_INLINE = re.compile(r"description:\s*(.+)")


def slug(text):
    """A filename-safe form of a host's session id."""
    return re.sub(r"[^A-Za-z0-9]+", "-", str(text)).strip("-")


def clause(path):
    """What the skill is for, in one line: the description sentence carrying the
    trigger, or the opening one.

    The `Use when ...` sentence wins for the same reason the router line in
    bin/tezgah-setup takes it over the opening one: a description whose first
    sentence is a preface otherwise reaches the judge stripped of every word a
    request matches on. Capped the way that router line is capped."""
    try:
        with open(path, encoding="utf-8", errors="replace") as fh:
            text = fh.read(4000)
    except OSError:
        return ""
    block = _FRONTMATTER.search(text)
    if not block:
        return ""
    folded = _FOLDED.search(block.group(1))
    if folded:
        desc = " ".join(line.strip() for line in folded.group(1).splitlines())
    else:
        inline = _INLINE.search(block.group(1))
        desc = inline.group(1).strip().strip("\"'") if inline else ""
    desc = re.sub(r"\s+", " ", desc).strip()
    sentences = re.split(r"(?<=[.!?])\s+", desc)
    line = next((s for s in sentences if re.match(r"(?:Also )?[Uu]se\b", s)),
                sentences[0] if sentences else "")
    return line[:CLAUSE_CAP - 3].rstrip() + "..." if len(line) > CLAUSE_CAP else line


def roster():
    """[(name, clause)] over the installed skills, name-sorted."""
    base = os.path.join(tp.PLUGIN_ROOT, "skills")
    try:
        names = sorted(os.listdir(base))
    except OSError:
        return []
    out = []
    for name in names:
        path = os.path.join(base, name, "SKILL.md")
        if os.path.isfile(path):
            out.append((name, clause(path)))
    return out


def block(name, what):
    """The appended line, in the cookbook's shape: what the skill is for, and that
    it is a hint to look at first rather than an instruction to load."""
    tail = " - " + what.strip() if what.strip() else ""
    if not tail or not tail.endswith((".", "!", "?", "...")):
        tail += "."
    return ("<skill_relevance>\nRelevant to the current request: %s%s Look at its "
            "SKILL.md first if it fits what the user actually asked for; this is a "
            "hint, not an instruction to load.\n</skill_relevance>" % (name, tail))


def available():
    """True when the suggestion can be asked for: armed by the user, and a credential.

    Nothing is asked before the arming file exists, so an unarmed install makes no
    request at all rather than one whose answer is thrown away."""
    return tp.armed(ARM) and tezgah_judge.available()


def judge(prompt, names, session_id=""):
    """The appended line for one prompt, or "" for none / a failed call.

    A successful call writes one `judge` ledger row before its answer is read -
    what the turn paid for is true whatever the answer turns out to be - in the
    shape the status counters fold on. That row is a cost, never a step and never
    a check, so nothing here can license a done claim; and a ledger that cannot be
    written costs nothing that the turn sees."""
    criteria = dict(names)
    criteria[NONE] = "no skill in this roster applies to the request"
    result = tezgah_judge.ask(
        {"request": prompt},
        {"which": {"type": "choice", "instructions": CHOICE_INSTRUCTIONS,
                   "criteria": criteria},
         "needs_skill": {"type": "noul", "instructions": GATE_INSTRUCTIONS}},
        timeout=ASK_TIMEOUT)
    if not result:
        return ""
    usage = result["usage"]
    ti.note(session_id, "judge",
            "tezgah-skill-pick %s in=%d out=%d ms=%d"
            % (tezgah_judge.MODEL, usage["input_tokens"], usage["output_tokens"],
               result["latency_ms"]))
    chosen = tezgah_judge.choice(result, "which")
    gate = tezgah_judge.noul(result, "needs_skill")
    if chosen is None or chosen == NONE:
        return ""
    if gate is None or gate < GATE:
        return ""
    options = dict(names)
    return block(chosen, options[chosen]) if chosen in options else ""


def _path(session_id):
    return os.path.join(tp.cache_dir(), "skill-pick",
                        slug(session_id) + ".json")


def _remembered(session_id):
    try:
        with open(_path(session_id), encoding="utf-8") as fh:
            data = json.load(fh)
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def _remember(session_id, digest, line):
    """Best effort: a host may sandbox hook writes, and a cache that cannot be
    written costs one more call, never the line."""
    data = _remembered(session_id)
    data[digest] = line
    for old in list(data)[:max(0, len(data) - KEPT)]:
        del data[old]
    path = _path(session_id)
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(data, fh)
    except OSError:
        pass


def suggest(prompt, session_id=""):
    """The `<skill_relevance>` line this prompt earns, or "".

    Nothing is asked for a slash command (the user named the work, not the task
    class), and nothing is asked twice for one prompt in one session."""
    prompt = (prompt or "").strip()
    if not prompt or prompt.startswith("/") or not available():
        return ""
    digest = hashlib.sha1(prompt.encode()).hexdigest()
    known = _remembered(session_id)
    if digest in known:
        return known[digest] if isinstance(known[digest], str) else ""
    names = roster()
    line = judge(prompt, names, session_id) if names else ""
    _remember(session_id, digest, line)
    return line
