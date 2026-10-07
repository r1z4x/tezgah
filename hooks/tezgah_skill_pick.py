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

Alongside the judgement sits a section search over every installed skill
(sections/search/skill_roots below, exposed as `bin/tezgah-skill`): the roster
a session meets is names only, and the corpora a host mounts - 284 skills under
omp's custom directories on this machine - were reachable by topic by nobody.
The search is local BM25 over headings and bodies; the hint reuses it to point
at the matching SECTION of the skill the judgement named, as a
`skill://<name>:<start>-<end>` address omp's read tool resolves plus the
absolute path every other host opens. The search itself is not armed: it is a
local read, so `bin/tezgah-skill` costs nothing until it is run.

DEFAULT ON, NO MODEL: `section_hint` (below) runs the same search on every
prompt the judgement did not answer, over an index cached in SQLite and rebuilt
only when a SKILL.md's stat moves, and appends one line naming the top section
when it carries enough of the prompt's words - each section once per session.
No credential and no arming file, so `judge-off` does not reach it (it is not a
judgement); `reminder-off` drops it with the rest of the per-turn text."""


import hashlib
import json
import math
import os
import re
import sqlite3

import tezgah_integrity as ti
import tezgah_judge
import tezgah_rank
import tezgah_paths as tp

ARM = "skill-suggest-on"
# Below this, the turn's own gate question says no skill is wanted and nothing is
# suggested - the cookbook's threshold, which is also where the triage selection
# sits: with `none` in the Choice, a forced nearest-neighbour pick is what the
# gate exists to prevent.
GATE = 0.30
# One attempt and a 4 s wall clock (`ask`'s `deadline`), about 4x the measured
# worst case (0.3-1.1 s live): omp's bridge kills a hook at 10 s, a killed hook
# loses the whole per-turn injection, and the rest of the prompt hook runs after
# this call - so a slow reply costs the hint and never the turn.
ASK_DEADLINE = 4.0
# The prompt goes out redacted (`ti.redact`) and cut to taste's own cap: the
# choice needs the request's gist, not a pasted log.
PROMPT_MAX = 2000
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


def block(name, what, section=None):
    """The appended line, in the cookbook's shape: what the skill is for, the
    section that matches the turn when the ranking found one, and that it is a
    hint to look at first rather than an instruction to load. The section rides
    as a `skill://<name>:<start>-<end>` address plus the absolute path, because
    only some hosts resolve skill:// and every host can open a path."""
    tail = " - " + what.strip() if what.strip() else ""
    if not tail or not tail.endswith((".", "!", "?", "...")):
        tail += "."
    where = ""
    if section:
        uri, title, path = section
        where = ' Start at %s ("%s"; %s where skill:// is not resolved).' % (
            uri, title[:60], path)
    return ("<skill_relevance>\nRelevant to the current request: %s%s%s Look at "
            "it first if it fits what the user actually asked for; this is a "
            "hint, not an instruction to load.\n</skill_relevance>"
            % (name, tail, where))


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
        {"request": ti.redact(prompt)[:PROMPT_MAX]},
        {"which": {"type": "choice", "instructions": CHOICE_INSTRUCTIONS,
                   "criteria": criteria},
         "needs_skill": {"type": "noul", "instructions": GATE_INSTRUCTIONS}},
        timeout=ASK_DEADLINE, attempts=1, deadline=ASK_DEADLINE)
    if not result:
        return ""
    usage = result["usage"]
    ti.note(session_id, "judge",
            "tezgah-skill-pick %s in=%d out=%d ms=%d judge=%s/%s"
            % (result["model"], usage["input_tokens"], usage["output_tokens"],
               result["latency_ms"], result["provider"], result["model"]))
    chosen = tezgah_judge.choice(result, "which")
    gate = tezgah_judge.noul(result, "needs_skill")
    if chosen is None or chosen == NONE:
        return ""
    if gate is None or gate < GATE:
        return ""
    options = dict(names)
    if chosen not in options:
        return ""
    # the name is the judgement's answer; the section is the local ranking's,
    # free of the call deadline because it reads one file from disk and of the
    # roster because the judgement has already named the file
    return block(chosen, options[chosen],
                 section_of(chosen, prompt,
                            roots=[os.path.join(tp.PLUGIN_ROOT, "skills")]))


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

# ---- section search: which part of which installed skill answers a topic ----

# What one indexed section may hold. A skill file is a few KB, so the cap only
# bounds a pathological file someone drops into a custom directory.
SECTION_READ = 262144
_ATX = re.compile(r"^(#{1,6})\s+(.*?)\s*$")


def sections(path):
    """[(title, start, end, text)] for one SKILL.md, in 1-based file lines with
    the frontmatter counted, so a `skill://<name>:<start>-<end>` selector lands
    exactly on the section a search named (the read tool's selectors count the
    same lines). A section runs from its heading to the line before the next
    heading of the same or higher level; the text above the first heading is
    frontmatter and belongs to no section."""
    try:
        with open(path, encoding="utf-8", errors="replace") as fh:
            lines = fh.read(SECTION_READ).splitlines()
    except OSError:
        return []
    marks, fenced = [], False
    for i, line in enumerate(lines):
        if line.lstrip().startswith("```"):
            fenced = not fenced       # a toggling fence: ``` opens, ``` closes
            continue
        if fenced:
            continue                  # a `# comment` inside code is not a heading
        m = _ATX.match(line)
        if m:
            marks.append((len(m.group(1)), m.group(2).strip(), i + 1))
    out = []
    for j, (level, title, start) in enumerate(marks):
        end = len(lines)
        for lvl, _t, ln in marks[j + 1:]:
            if lvl <= level:
                end = ln - 1
                break
        out.append((title, start, end, "\n".join(lines[start - 1:end])))
    return out


def _omp_custom_dirs(config):
    """The `skills.customDirectories` list of omp's config.yml, verbatim paths.

    omp is the one host whose big skill corpora (284 here) ride a config key
    rather than a fixed directory, so a search that missed it would index a
    fifth of the machine and claim the rest did not exist. Two lines of
    indentation-bounded scanning, not a YAML dependency, for a file whose only
    interesting part is a four-line list."""
    roots, inside = [], False
    try:
        with open(config, encoding="utf-8", errors="replace") as fh:
            rows = fh.read().splitlines()
    except OSError:
        return []
    for row in rows:
        if re.match(r"^\s*customDirectories:\s*$", row):
            inside = True
            continue
        if inside:
            item = re.match(r"^\s+-\s+(.+?)\s*$", row)
            if item:
                roots.append(os.path.expanduser(item.group(1)))
            elif row.strip():
                break          # the next keyed block: the list is over
    return roots


def skill_roots(extra=()):
    """Every installed-skill root on this machine, highest-precedence first.

    The order mirrors omp's provider priority (the plugin's own skills, omp's
    user directory, then its custom directories, then the other hosts), which
    only matters for a name that differs between roots: the first one keeps
    the bare `skill://<name>` address omp resolves. Identical copies (every
    host links the same plugin skills) collapse on realpath, so the order
    costs nothing on this machine."""
    home = os.path.expanduser("~")
    xdg = os.environ.get("XDG_CONFIG_HOME") or os.path.join(home, ".config")
    roots = ([os.path.join(tp.PLUGIN_ROOT, "skills"),
              os.path.join(home, ".omp", "agent", "skills")]
             + _omp_custom_dirs(os.path.join(home, ".omp", "agent", "config.yml"))
             + [os.path.join(home, ".claude", "skills"),
                os.path.join(home, ".agents", "skills"),
                os.path.join(os.environ.get("CODEX_HOME")
                             or os.path.join(home, ".codex"), "skills"),
                os.path.join(xdg, "opencode", "skills")]
             + list(extra))
    seen, out = set(), []
    for root in roots:
        real = os.path.realpath(root)
        if real in seen or not os.path.isdir(real):
            continue
        seen.add(real)
        out.append(root)
    return out


def _rows(roots=None):
    """[(skill, path, title, start, end, text)] over every installed skill's
    sections, deduplicated on the file's realpath so a skill five hosts link
    is one entry, not five."""
    out, seen = [], set()
    for root in (skill_roots() if roots is None else roots):
        try:
            names = sorted(os.listdir(root))
        except OSError:
            continue
        for name in names:
            path = os.path.realpath(os.path.join(root, name, "SKILL.md"))
            if not os.path.isfile(path):
                continue
            for title, start, end, text in sections(path):
                if (path, start) in seen:
                    continue
                seen.add((path, start))
                out.append((name, path, title, start, end, text))
    return out


def index(roots=None):
    """[(skill, path, title, start, end)] over every section of every installed
    skill. `roots` overrides discovery (tests, one-directory searches)."""
    return [row[:5] for row in _rows(roots)]


def search(query, k=5, roots=None):
    """The `k` sections that answer `query`, best first, as
    [(skill, path, title, start, end)]. BM25 over heading (weighted x3) plus
    body via tezgah_rank - the same ranking the per-turn lessons block uses,
    because this is the same problem one level down: which of many short texts
    a turn's topic is about. A query no section shares a term with returns []."""
    rows = _rows(roots)
    # the heading twice more than the body: a section whose TITLE answers the
    # query outranks one that merely mentions the words in passing
    ranked = tezgah_rank.rank(query, ["%s\n%s\n%s" % (row[2], row[2], row[5])
                                      for row in rows], k)
    return [rows[i][:5] for i in ranked]


def skill_path(skill, roots=None):
    """The SKILL.md a name resolves to, first root wins, or None.

    Root by root, not through `index()`: on the prompt path this runs once per
    turn, and the machine's full corpus is 280 files a name lookup has no
    reason to open."""
    for root in (skill_roots() if roots is None else roots):
        path = os.path.realpath(os.path.join(root, skill, "SKILL.md"))
        if os.path.isfile(path):
            return path
    return None


def section_of(skill, prompt, roots=None):
    """The one section of `skill` that matches `prompt` best, as the
    (uri, title, path) the hint line carries, or None when nothing scores.

    This is what turns the hint from a skill name into an address: the
    judgement already answered WHICH skill, so the ranking here runs inside
    that one file's directory only, and a prompt whose topic the file never
    mentions keeps the old name-only line rather than an invented range."""
    path = skill_path(skill, roots)
    if not path:
        return None
    own = [row for row in _rows([os.path.dirname(os.path.dirname(path))])
           if row[0] == skill]
    ranked = tezgah_rank.rank(prompt, ["%s\n%s\n%s" % (r[2], r[2], r[5])
                                       for r in own], 1)
    if not ranked:
        return None
    title, start, end = own[ranked[0]][2:5]
    return ("skill://%s:%d-%d" % (skill, start, end), title, path)

# ---- the default-on local hint: the same index, cached, no model ----------

# The coverage bar: of the prompt's distinct terms (function words out) that
# the corpus knows at all, the top section must carry HINT_COVER of them and
# at least HINT_MIN_TERMS. Coverage, not an absolute BM25 score, because
# scores scale with corpus size and idf spread - a bar that reads well on the
# live corpus fires on nothing in a small one and vice versa, while "did the
# section carry the topic's words" transfers. A word no skill contains (a file
# name, a typo, the project's own jargon) says nothing about which section
# fits, so it counts neither for the bar nor against it. Three terms, not two:
# on this machine's corpus a two-word overlap put "why is the build failing on
# CI" on an output-style section, while every topic prompt tried carried 3-8.
HINT_COVER = 0.6
HINT_MIN_TERMS = 3
# Only the head of a pasted prompt is ranked: the topic is in its first lines,
# and a log pasted below it must not cost the turn its time budget.
HINT_PROMPT_MAX = 600
INDEX_CACHE = "skill-search.sqlite"


def _toktext(row):
    """The text a row is ranked on: the heading twice more than the body, the
    same weighting `search` gives it, so the two rankings cannot drift."""
    return "%s\n%s\n%s" % (row[2], row[2], row[5])


def _postings(rows):
    """({term: [(section, count), ...]}, [section length]): the inverted index
    `rank_postings` scores from. Tokenised with the ranker's own `words`, so
    the index holds exactly the terms it would see."""
    posts, lengths = {}, []
    for i, row in enumerate(rows):
        counts = {}
        for term in tezgah_rank.words(_toktext(row)):
            counts[term] = counts.get(term, 0) + 1
        lengths.append(sum(counts.values()))
        for term, n in counts.items():
            posts.setdefault(term, []).append((i, n))
    return posts, lengths


def rank_postings(query, posts, lengths, k):
    """`tezgah_rank.rank`'s ordering over postings, no max_df cap. `posts` may
    hold only the query's own terms - nothing else is read.

    The arithmetic is the ranker's own (K1, B, its idf), read from the module
    so a retuned constant moves both paths at once; `PostingsIndex` pins the
    two orderings equal rather than trusting the copy."""
    terms = set(tezgah_rank.words(query))
    if not posts or not terms or not lengths:
        return []
    n = len(lengths)
    avg = sum(lengths) / n or 1.0
    k1, b = tezgah_rank.K1, tezgah_rank.B
    scores = {}
    for t in terms:
        entries = posts.get(t)
        if not entries:
            continue
        idf = math.log(1 + (n - len(entries) + 0.5) / (len(entries) + 0.5))
        for i, c in entries:
            scores[i] = scores.get(i, 0.0) + idf * c * (k1 + 1) / (
                c + k1 * (1 - b + b * lengths[i] / avg))
    ranked = sorted((-s, i) for i, s in scores.items() if s > 0)
    return [i for _s, i in ranked[:k]]


def _signature():
    """[[root, skill, mtime_ns, size]] per installed SKILL.md: what a rebuild
    keys on. The file's own stat, not its directory's - installing, editing or
    removing one skill is exactly the change the cache must notice."""
    sig = []
    for root in skill_roots():
        try:
            names = sorted(os.listdir(root))
        except OSError:
            continue
        for name in names:
            try:
                st = os.stat(os.path.join(root, name, "SKILL.md"))
            except OSError:
                continue
            sig.append([root, name, st.st_mtime_ns, st.st_size])
    return sig


def _build(path, sig, rows):
    """Write the index for `rows` under a private temp name and move it into
    place, so a concurrent reader sees the old file or the new one."""
    posts, lengths = _postings(rows)
    tmp = "%s.%d.tmp" % (path, os.getpid())
    if os.path.exists(tmp):
        os.remove(tmp)
    con = sqlite3.connect(tmp)
    try:
        con.executescript(
            "CREATE TABLE meta(sig TEXT);"
            "CREATE TABLE sec(id INTEGER PRIMARY KEY, skill TEXT, path TEXT,"
            " title TEXT, start INTEGER, end INTEGER, len INTEGER);"
            "CREATE TABLE post(term TEXT, sec INTEGER, n INTEGER,"
            " PRIMARY KEY(term, sec)) WITHOUT ROWID;")
        con.execute("INSERT INTO meta VALUES (?)", (sig,))
        con.executemany("INSERT INTO sec VALUES (?,?,?,?,?,?,?)",
                        [(i,) + tuple(r[:5]) + (lengths[i],)
                         for i, r in enumerate(rows)])
        con.executemany("INSERT INTO post VALUES (?,?,?)",
                        ((t, i, n) for t, entries in posts.items()
                         for i, n in entries))
        con.commit()
    finally:
        con.close()
    os.replace(tmp, path)


def _open_index():
    """A read-only connection to the machine's cached index, rebuilt first when
    any SKILL.md's stat moved since it was written; None when none can be had."""
    path = os.path.join(tp.cache_dir(), INDEX_CACHE)
    sig = json.dumps(_signature())
    for attempt in (0, 1):
        if os.path.isfile(path):
            con = sqlite3.connect("file:%s?mode=ro" % path, uri=True)
            try:
                row = con.execute("SELECT sig FROM meta").fetchone()
            except sqlite3.Error:
                row = None
            if row and row[0] == sig:
                return con
            con.close()
        if attempt:
            return None
        os.makedirs(os.path.dirname(path), exist_ok=True)
        _build(path, sig, _rows())
    return None


def top_section(prompt, roots=None):
    """((skill, path, title, start, end), covered, known) for the section that
    ranks first for `prompt`, or None: `covered` of the prompt's `known`
    content terms (stopwords out, present in the corpus) occur in it.

    With `roots` the index is built in memory and no cache is read or written,
    so a fixture lookup can never overwrite the machine's own index. Without,
    it is the cached SQLite index: a warm lookup reads the prompt's postings
    and one integer column, never the corpus."""
    terms = sorted(set(tezgah_rank.words(prompt[:HINT_PROMPT_MAX])))
    if not terms:
        return None
    con = _open_index() if roots is None else None
    if roots is None and con is None:
        return None
    try:
        if con is None:
            rows = _rows(roots)
            every, lengths = _postings(rows)
            posts = {t: every[t] for t in terms if t in every}
        else:
            posts = {}
            for t, i, n in con.execute(
                    "SELECT term, sec, n FROM post WHERE term IN (%s)"
                    % ",".join("?" * len(terms)), terms):
                posts.setdefault(t, []).append((i, n))
            lengths = [r[0] for r in con.execute(
                "SELECT len FROM sec ORDER BY id")]
        top = rank_postings(" ".join(terms), posts, lengths, 1)
        if not top:
            return None
        i = top[0]
        hit = (tuple(rows[i][:5]) if con is None else con.execute(
            "SELECT skill, path, title, start, end FROM sec WHERE id=?",
            (i,)).fetchone())
    finally:
        if con is not None:
            con.close()
    if not hit:
        return None
    known = [t for t in terms if t in posts and t not in tezgah_rank.STOPWORDS]
    covered = sum(1 for t in known if any(j == i for j, _n in posts[t]))
    return tuple(hit), covered, len(known)


def _hint_path(session_id):
    return os.path.join(tp.cache_dir(), "skill-section-hint",
                        slug(session_id) + ".json")


def _shown(session_id):
    """The sections this session was already pointed at, ["path:start"]."""
    try:
        with open(_hint_path(session_id), encoding="utf-8") as fh:
            data = json.load(fh)
    except (OSError, ValueError):
        return []
    return data if isinstance(data, list) else []


def _remember_shown(session_id, shown):
    """Bounded and best effort, like the judgement's cache: a dir that cannot
    be written costs a repeated line, never the turn."""
    path = _hint_path(session_id)
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(shown[-KEPT:], fh)
    except OSError:
        pass


def section_hint(prompt, session_id="", host=None, roots=None):
    """The default-on `<skill_relevance>` line: the top SECTION of the local
    index for this prompt, or "".

    No model, no credential, no arming file - no search ran over the skills
    unless a session thought to, and a hint that waits for an opt-in never
    runs. It fires only when the section clears the coverage bar, names each
    section once per session, and carries the absolute path everywhere but
    omp, whose read tool resolves the `skill://` address itself. Total: an
    index that cannot be read or built costs the line, never the turn."""
    prompt = (prompt or "").strip()
    if not prompt or prompt.startswith("/"):
        return ""
    try:
        found = top_section(prompt, roots)
    except (OSError, sqlite3.Error, ValueError):
        return ""
    if not found:
        return ""
    (skill, path, title, start, end), covered, known = found
    if covered < max(HINT_MIN_TERMS, math.ceil(HINT_COVER * known)):
        return ""
    key = "%s:%d" % (path, start)
    shown = _shown(session_id)
    if key in shown:
        return ""
    _remember_shown(session_id, shown + [key])
    where = "" if host == "omp" else " (%s)" % path
    return ("<skill_relevance>\nA local skill search matched this request: "
            "skill://%s:%d-%d%s, \"%s\". Read that range first if it fits; "
            "a hint, not an instruction to load.\n</skill_relevance>"
            % (skill, start, end, where, title[:60]))
