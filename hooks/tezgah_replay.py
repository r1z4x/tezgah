#!/usr/bin/env python3
"""The replay corpus: the real ledgers replayed through the current gate and Stop
code, a blind label sheet drawn from them, and the report that reads the labels
(plan 055, roadmap R12; corpus spec REPORT.md §4.4.3).

  tezgah-gate replay [--cutoff WHEN] [--since WHEN] [--json]
  tezgah-gate replay --report [--run DIR] [--labels FILE ...] [--json]
  tezgah-gate replay --sheet [--run DIR] [--seed N] [--rules FILE]

**Corpus.** Every ledger under the cache's `evidence/` is read read-only; a
ledger is dropped whole when `fixture_ledger` says it is a fixture tree, or when
the session id behind its file stem is not a host UUID (probe, smoke and test
ids). Rows drop after the cutoff and when they are `route` rows (written by the
test suite). The items are the `deny`, `began` and `claim` rows; an item drops
when its deny names a rule `tezgah_gate.DENY_RULES` no longer holds (consent,
sink), when its `detail` is at `DETAIL_MAX`, or when it holds `[redacted:`.

**Join.** omp and Claude transcripts, subagent files included, are walked by
`bin/tezgah-taste` (`calls=True`). A call joins a row when
`call_id(tool, args)` - omp's `i` key dropped - equals the row's `id` inside the
ledger `_slug(session id)` names. A shell `began` row with no transcript call
joins from its own detail when that detail is under the cap and hashes to the
row's id. A `claim` row joins the assistant reply nearest its timestamp within
`REPLY_WINDOW` seconds. Nothing else is tried: an unjoined row stays unjoined.

**Replay.** A child process with a sandbox HOME under the run directory: every
kept row of every kept ledger is appended to the sandbox ledger in timestamp
order (each ledger in its own order, the file's mtime set to the row's ts), and
each item is replayed just before its own row lands, with `time.time` frozen at
the row's ts. Gate items go through the unmodified
`tezgah_gate.decision(..., record=False)`; the rule a replayed deny names is the
rule argument `decision` hands `_deny`, read by an observer and labelled through
`_deny_rule`, the one rule-label derivation. Stop items go through
`_stop_block(text, sid, rows=<turn prefix>)` with `events` swapped to the session
prefix. The rows the gate writes beside a refusal (drift and nudge marks) and the
Stop path's `shape` row are moved after their item, because live they were the
call's own output.

**Output.** Everything is written under `~/.cache/tezgah/replay/<run>/`, owner
only, and never leaves the machine: `corpus.jsonl` (the items, with their
inputs), `results.jsonl`, `summary.json`, and the sheet files. The sandbox HOME
and the row stream are deleted when the child returns.
"""
import argparse
import datetime
import importlib.machinery
import importlib.util
import json
import math
import os
import random
import re
import shutil
import subprocess
import sys
import time
from collections import Counter, defaultdict
from heapq import merge

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)
import tezgah_integrity as ti  # noqa: E402
import tezgah_paths as tp  # noqa: E402

# The one rule-label derivation; nothing in this module maps text to a rule.
rule_of = ti._deny_rule

# `34f63e3`'s commit time (2026-10-04 21:31:35 +03): the rows since it are the
# ones current rules still produce, and the H1 prediction is tested on them.
SINCE_RELEASE = 1791138695
REPLY_WINDOW = 2
ITEM_KINDS = ("deny", "began", "claim")
TEST_ROW_KINDS = ("route",)
# Rows a live call wrote just before its own item row: they are moved after it.
SIDE_KINDS = {"deny": ("drift", "nudge"), "began": ("drift", "nudge"),
              "claim": ("shape",)}
# The rule the family fold (plan 055 part 6, D32a) is about.
RACE_RULE = "race"
RACE_BAR_UNMEASURABLE = ("not measurable on this corpus: no race item is on the sheet "
                         "(every joined live race deny predates the `target` field)")
# Which rules read only the call and the ledger (replayable as they ran) and
# which read the disk as it is today. Keyed by `_deny_rule` labels. A rule in
# `disk_on_write` is disk-state on a write tool; one in `disk_on_file` is
# disk-state when the command reads a message file.
STRATA = {"ledger": ("loop", "retry", "order", "drift", "race", "piped",
                     "attribution", "secret", "shortcut"),
          "disk": ("task", "plan", "workspace", "explorer"),
          "disk_on_write": ("shortcut",),
          "disk_on_file": ("lang",)}
MESSAGE_FILE = re.compile(r"(?:^|\s)(?:-F|--file)(?:\s|=|$)")
UUID = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$")
# The H2 sampling frame (protocol committed before any label).
QUOTA = {"deny:drift": 96, "deny:piped": 96, "deny:race": 96, "deny:other": 32,
         "allow": 30, "stop:allow": 25, "stop:block": 25}
SEED = 55
CUT_PROMPT, CUT_INPUT, CUT_REPLY = 1500, 2000, 3000
STOP_CONTEXT = ("run", "edit", "verify", "verify_ok", "verify_fail",
                "interrupted", "external")


def replay_root():
    """Where every replay run lives: under the cache, never under `.tezgah/`."""
    return os.path.join(tp.CACHE, "replay")


def _taste():
    """bin/tezgah-taste as a module (it has no `.py` suffix): its walkers are the
    transcript readers, so the corpus and `mine` read one format one way."""
    path = os.path.join(os.path.dirname(HERE), "bin", "tezgah-taste")
    loader = importlib.machinery.SourceFileLoader("tezgah_taste", path)
    spec = importlib.util.spec_from_loader("tezgah_taste", loader)
    module = importlib.util.module_from_spec(spec)
    loader.exec_module(module)
    return module


def _when(text):
    """An epoch from an int or an ISO time; None for None."""
    if text is None:
        return None
    try:
        return int(text)
    except ValueError:
        return int(datetime.datetime.fromisoformat(text).timestamp())


def _stamp(epoch):
    return datetime.datetime.fromtimestamp(epoch).astimezone().strftime(
        "%Y-%m-%d %H:%M:%S %z")


def _owner_write(path, text):
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    os.fchmod(fd, 0o600)  # the create mode does not reach a file that already exists
    with os.fdopen(fd, "w", encoding="utf-8") as fh:
        fh.write(text)


def _write_jsonl(path, rows):
    _owner_write(path, "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows))


def _read_jsonl(path):
    with open(path, encoding="utf-8") as fh:
        return [json.loads(line) for line in fh if line.strip()]


def stratum(kind, rule, tool, inp):
    """The stratum an item's agreement is reported under."""
    if kind == "claim":
        return "stop"
    if rule is None:
        return "allow"
    t = str(tool or "").lower()
    if rule in STRATA["disk_on_write"] and t in ti.WRITE_TOOLS:
        return "disk"
    if rule in STRATA["disk_on_file"]:
        command = str((inp or {}).get("command") or "")
        return "disk" if MESSAGE_FILE.search(command) else "ledger"
    for name in ("ledger", "disk"):
        if rule in STRATA[name]:
            return name
    return "unclassified"


def _summary_of(name, args):
    """One line naming a call, for the sheet's context: no verdict in it."""
    args = args if isinstance(args, dict) else {}
    text = args.get("command") or args.get("cmd") or args.get("file_path") \
        or args.get("path") or json.dumps(args, ensure_ascii=False)
    return "%s: %s" % (name, str(text).splitlines()[0][:160] if str(text) else "")


def _legacy(sid):
    """The ledger stem a session id had before `_slug` grew its hash suffix:
    the readable prefix alone. Older ledgers on disk still carry it."""
    return re.sub(r"[^A-Za-z0-9]+", "-", str(sid)).strip("-")[:40]


def _test_polluted(stem):
    """True when the session id behind a ledger stem is not a host UUID. The
    stem is the raw id's readable prefix plus `-<12 hex>`, or the prefix alone
    for a ledger older than the hash suffix."""
    return not (UUID.match(stem) or UUID.match(stem.rsplit("-", 1)[0]))


# ------------------------------------------------------------------ corpus --

def _ledgers():
    """(stem, path, rows, reason) per ledger read; `reason` names why a whole
    ledger is dropped (fixture, test-polluted), None for a kept one."""
    out = []
    for path in sorted(ti.ledgers()):
        stem = os.path.basename(path)[:-len(".jsonl")]
        rows = ti._foreign_rows(path)
        reason = ("fixture" if ti.fixture_ledger(rows)
                  else "test-polluted" if _test_polluted(stem) else None)
        out.append((stem, path, rows, reason))
    return out


def _transcripts(wanted):
    """Per ledger stem: the transcript calls whose id is wanted, the assistant
    replies, the session cwd and host, and the parent links (`parent_of`, a
    stem or None for a known top-level session)."""
    taste = _taste()
    found = defaultdict(lambda: {"calls": defaultdict(list), "replies": [],
                                 "cwd": None, "host": None, "sid": None})
    parent_of, sid_of_file = {}, {}
    for host in ("omp", "claude"):
        walk = taste.HOSTS[host][2]
        for path, cwd in taste.sessions(host, "", nested=True):
            sid, parent = taste.session_id(host, path)
            if not sid:
                continue
            keys = (ti._slug(sid), _legacy(sid))
            sid_of_file[path] = sid
            # omp names a subagent's parent; a Claude file is its own session's
            parent_of.setdefault(keys[0], parent if host == "omp" else None)
            stem = next((k for k in keys if k in wanted), None)
            if stem is None:
                continue
            entry = found[stem]
            entry.update(cwd=entry["cwd"] or cwd, host=host, sid=sid)
            ids = wanted[stem]
            prompt, prior = "", []
            for event in walk(path, calls=True):
                if event[0] == "user":
                    if not taste.harness_prompt(event[1]):
                        prompt, prior = event[1], []
                elif event[0] == "reply":
                    entry["replies"].append((event[2], event[1], cwd))
                elif event[0] == "call":
                    name, args, ts = event[1], event[2], event[3]
                    digest = ti.call_id(name, args)
                    if digest in ids:
                        # the cwd of the file the call came from: one session's
                        # files (a subagent, a scratch workspace) differ in it
                        entry["calls"][digest].append(
                            {"tool": name, "input": args, "ts": ts, "cwd": cwd,
                             "prompt": prompt[:CUT_PROMPT], "prior": prior[-8:]})
                    prior.append(_summary_of(name, args))
    # omp names a subagent's parent by its file; the parent's stem is its id's slug
    for stem, parent in list(parent_of.items()):
        if parent is None:
            continue
        psid = sid_of_file.get(parent) or (
            os.path.exists(str(parent)) and taste.session_id("omp", parent)[0]) or None
        parent_of[stem] = ti._slug(psid) if psid else "unknown"
    return found, parent_of


def _nearest(candidates, ts):
    best = None
    for cand in candidates:
        if cand["ts"] is None:
            continue
        if best is None or abs(cand["ts"] - ts) < abs(best["ts"] - ts):
            best = cand
    return best or (candidates[0] if candidates else None)


def build_corpus(cutoff, since=None):
    """The corpus: items, the ordered row stream, ledger file names and the
    counts the summary prints."""
    import tezgah_gate as tg
    ledgers = _ledgers()
    counts = {"ledgers": Counter(), "excluded": Counter(), "candidates": 0}
    kept, wanted, claim_stems = [], defaultdict(set), set()
    spawned_parent = {}
    for stem, path, rows, reason in ledgers:
        counts["ledgers"]["read"] += 1
        if reason:
            counts["ledgers"][reason] += 1
            continue
        counts["ledgers"]["kept"] += 1
        live = []
        for row in rows:
            kind = row.get("kind")
            ts = row.get("ts") if isinstance(row.get("ts"), (int, float)) else None
            if kind in ITEM_KINDS:
                counts["candidates"] += 1
            if kind in TEST_ROW_KINDS:
                counts["excluded"]["test-row"] += 1
                continue
            if ts is None or ts > cutoff:
                if kind in ITEM_KINDS:
                    counts["excluded"]["after-cutoff"] += 1
                continue
            if kind == "spawned" and row.get("parent"):
                spawned_parent[stem] = ti._slug(row["parent"])
            live.append(row)
            if kind in ("deny", "began") and row.get("id"):
                wanted[stem].add(row["id"])
            if kind == "claim":
                claim_stems.add(stem)
        kept.append((stem, path, live))
    for stem in claim_stems:
        wanted.setdefault(stem, set())
    found, parent_of = _transcripts(wanted)
    # The sandbox names a ledger the way today's gate does (`_slug(sid)`), so the
    # session's own file is the one `decision` opens; that name is the ledger's
    # key from here on. A ledger with no transcript keeps its stem as its id.
    canon_of = {}
    for stem, _path, _rows in kept:
        entry = found.get(stem)
        canon_of[stem] = ti._slug(entry["sid"] if entry else stem)
    for stem, parent in spawned_parent.items():
        parent_of[canon_of[stem]] = parent
    stems = [s for s, _p, _r, _reason in ledgers]

    items, streams = [], []
    for stem, path, rows in kept:
        entry = found.get(stem)
        sid = entry["sid"] if entry else stem
        fname = canon_of[stem] + ".jsonl"
        order = list(range(len(rows)))
        turn_start = 0
        for idx, row in enumerate(rows):
            kind, detail = row.get("kind"), str(row.get("detail") or "")
            if kind == ti.TURN_KIND:
                turn_start = idx + 1
            if kind not in ITEM_KINDS:
                continue
            reason = None
            if kind == "deny" and rule_of(detail) not in tg.DENY_RULES:
                reason = "retired-rule"
            elif len(detail) >= ti.DETAIL_MAX:
                reason = "capped"
            elif "[redacted:" in detail:
                reason = "redacted"
            if reason:
                counts["excluded"][reason] += 1
                continue
            if since is not None and row["ts"] < since:
                counts["excluded"]["before-since"] += 1
                continue
            item = {"i": len(items), "stem": canon_of[stem], "sid": sid, "kind": kind,
                    "ts": row["ts"], "id": row.get("id"), "host": entry and entry["host"],
                    "cwd": (entry and entry["cwd"]) or row.get("workspace"),
                    "live": ("block" if detail.startswith("blocked:") else "allow")
                    if kind == "claim" else ("deny" if kind == "deny" else "allow"),
                    "live_rule": rule_of(detail) if kind == "deny"
                    else detail.split(":", 1)[1].strip() if kind == "claim"
                    and detail.startswith("blocked:") else None,
                    "tool": row.get("tool"), "join": None}
            if kind == "claim":
                replies = [{"ts": ts, "text": text, "cwd": where} for ts, text, where in
                           (entry["replies"] if entry else []) if ts is not None
                           and abs(ts - row["ts"]) <= REPLY_WINDOW]
                best = _nearest(replies, row["ts"])
                if best:
                    item.update(join="position", text=best["text"], cwd=best["cwd"])
                prefix = rows[turn_start:idx]
                item["turn"] = [[r.get("kind"), str(r.get("detail") or "")[:300]]
                                for r in prefix if r.get("kind") in STOP_CONTEXT][-40:]
            else:
                call = _nearest(entry["calls"].get(row.get("id"), []) if entry else [],
                                row["ts"])
                if call:
                    item.update(join="transcript", tool=call["tool"], input=call["input"],
                                cwd=call["cwd"], prompt=call["prompt"], prior=call["prior"])
                elif (kind == "began" and str(row.get("tool") or "").lower() in ti.BASH_TOOLS
                      and ti.call_id("bash", {"command": detail}) == row.get("id")):
                    item.update(join="ledger", input={"command": detail},
                                prompt="", prior=[])
            if item["live_rule"] == RACE_RULE:
                item["foreign"] = _foreign_sessions(detail, stems, canon_of)
            item["stratum"] = stratum(kind, item["live_rule"], item["tool"],
                                      item.get("input"))
            items.append(item)
            row_item = item["i"] if item["join"] else None
            # the call's own side rows (drift/nudge marks, the Stop `shape` row)
            # sit just before it at the same ts: move them after the item
            j = order.index(idx)
            k = j
            while (k > 0 and rows[order[k - 1]].get("ts") == row["ts"]
                   and rows[order[k - 1]].get("kind") in SIDE_KINDS[kind]):
                k -= 1
            if k < j:
                order[k:j + 1] = [idx] + order[k:j]
            rows[idx] = dict(row, _item=row_item)
        streams.append([(rows[n].get("ts"), fname, sid, rows[n]) for n in order])
    stream = merge(*streams, key=lambda e: e[0])
    folds = deny_runs_fold([r for r in rows if r.get("kind") != "deny"
                            or rule_of(str(r.get("detail") or "")) in tg.DENY_RULES]
                           for _s, _p, rows in kept)
    return items, stream, counts, parent_of, folds


def deny_runs_fold(ledgers):
    import tezgah_shapes
    return tezgah_shapes.deny_runs(ledgers)


# ------------------------------------------------------------------ replay --

def _child_env(home):
    env = {k: v for k, v in os.environ.items()
           if not k.startswith(("TEZGAH_", "XDG_")) and k not in ("CODEX_HOME", "DSH_HOME")}
    env.update(HOME=home, TEZGAH_ROOTS=os.pathsep.join(tp.roots()),
               TEZGAH_UPDATE_CHECK="0",
               TEZGAH_FALLBACK_CACHE=os.path.join(home, "tmp"))
    return env


def child(run):
    """The sandbox half: runs with HOME pointing at `<run>/home`. Reads the row
    stream and the items, writes `results.jsonl`."""
    import tezgah_gate as tg
    items = {it["i"]: it for it in _read_jsonl(os.path.join(run, "corpus.jsonl"))}
    evidence = os.path.join(ti.cache_dir(), "evidence")
    nudged = os.path.join(ti.cache_dir(), "nudged")
    os.makedirs(evidence, mode=0o700, exist_ok=True)
    os.makedirs(nudged, mode=0o700, exist_ok=True)
    now = [0.0]

    def frozen():
        return now[0]

    time.time = frozen
    seen = []
    live_deny = tg._deny

    def observe(session_id, rule, reason, *args, **kwargs):
        seen.append(rule)
        return live_deny(session_id, rule, reason, *args, **kwargs)

    tg._deny = observe
    live_events = ti.events
    rows_of = defaultdict(list)
    results = []
    with open(os.path.join(run, "stream.jsonl"), encoding="utf-8") as fh:
        for line in fh:
            fname, sid, row = json.loads(line)
            at = row.pop("_item", None)
            if at is not None:
                it = items[at]
                now[0] = float(it["ts"])
                results.append(_replay_one(it, rows_of[fname], tg, seen, live_events))
            rows_of[fname].append(row)
            path = os.path.join(evidence, fname)
            with open(path, "a", encoding="utf-8") as out:
                out.write(json.dumps(row) + "\n")
            if isinstance(row.get("ts"), (int, float)):
                os.utime(path, (row["ts"], row["ts"]))
            if row.get("kind") == "nudge":
                # the once-per-session nudge mark the live gate wrote with this
                # row (`first_nudge`): disk state the ledger records
                open(os.path.join(nudged, sid), "w").close()
    _write_jsonl(os.path.join(run, "results.jsonl"), results)


def _replay_one(it, prefix, tg, seen, live_events):
    out = {"i": it["i"]}
    try:
        if it["kind"] == "claim":
            prefix = [r for r in prefix if not (r.get("kind") == "shape"
                                                and r.get("id") == it["id"])]
            turn = prefix[ti._turn_start(prefix):]
            turns = sum(1 for r in prefix if r.get("kind") == ti.TURN_KIND)

            def events(_sid, tail=None):
                return prefix[-tail:] if tail else list(prefix)

            ti.events = events
            try:
                cls, _reason = ti._stop_block(it["text"], it["sid"], rows=turn,
                                              cwd=it["cwd"])
            finally:
                ti.events = live_events
            out.update(replay="block" if cls else "allow", rule=cls,
                       text_ok=ti._claim_key(it["text"], turns) == it["id"])
        else:
            del seen[:]
            inp = it["input"]
            reason = tg.decision(it["tool"], inp, it["cwd"], it["sid"], record=False)
            rule = (rule_of("%s: %s" % (seen[-1], reason)) if seen else "unobserved") \
                if reason else None
            writers = sorted({w for p in tg.write_paths(inp)
                              for w in ti.writers_elsewhere(p, it["sid"],
                                                            tg.RACE_WINDOW_MIN,
                                                            cwd=it["cwd"])})
            out.update(replay="deny" if reason else "allow", rule=rule,
                       writers=writers)
    except Exception as exc:  # a crash is a result, never a silent allow
        out.update(replay="error", rule="%s: %s" % (type(exc).__name__, exc))
    return out


def _agree(it, res):
    if res.get("replay") != it["live"]:
        return False
    return it["live"] == "allow" or res.get("rule") == it["live_rule"]


def fidelity(items, results):
    """Per stratum (and per live rule inside it): agreement over joined items,
    whole corpus and since `SINCE_RELEASE`."""
    by = {r["i"]: r for r in results}
    table = defaultdict(lambda: Counter())
    for it in items:
        res = by.get(it["i"])
        if res is None:
            continue
        ok = _agree(it, res)
        keys = [it["stratum"], "%s/%s" % (it["stratum"], it["live_rule"] or it["live"])]
        for key in keys:
            table[key]["n"] += 1
            table[key]["agree"] += ok
            if it["ts"] >= SINCE_RELEASE:
                table[key]["n_since"] += 1
                table[key]["agree_since"] += ok
            table[key]["error"] += res.get("replay") == "error"
        if not ok:
            # what a disagreement turned into, so a fidelity loss names its rule
            moved = "%s->%s" % (it["live_rule"] or it["live"],
                                res.get("rule") or res.get("replay"))
            table[it["stratum"]]["to " + moved[:60]] += 1
    return {k: dict(v) for k, v in sorted(table.items())}


FOREIGN = re.compile(r"session ([0-9A-Za-z][0-9A-Za-z-]*)")


def _foreign_sessions(detail, stems, canon_of):
    """The ledgers a live race deny names, read from its own detail: each id it
    prints (cut at 80 characters, so possibly a prefix) resolved to the one
    ledger stem it starts; an id that matches none or several is left out."""
    out = []
    for cut in FOREIGN.findall(detail):
        hits = [s for s in stems if s.startswith(cut)]
        if len(hits) == 1:
            out.append(canon_of.get(hits[0], hits[0]))
    return out


def run_replay(cutoff=None, since=None):
    """Build, replay in the sandbox child, write the summary; returns it."""
    cutoff = int(cutoff or time.time())
    run = os.path.join(replay_root(), time.strftime("%Y%m%dT%H%M%S", time.localtime(cutoff)))
    # the root holds every run's transcript inputs: owner only, like the runs
    os.makedirs(replay_root(), mode=0o700, exist_ok=True)
    os.chmod(replay_root(), 0o700)
    os.makedirs(run, mode=0o700, exist_ok=True)
    items, stream, counts, parent_of, folds = build_corpus(cutoff, since)
    _write_jsonl(os.path.join(run, "corpus.jsonl"), items)
    streamed = os.path.join(run, "stream.jsonl")
    _owner_write(streamed, "".join(json.dumps([fname, sid, row]) + "\n"
                                   for _ts, fname, sid, row in stream))
    home = os.path.join(run, "home")
    os.makedirs(home, mode=0o700, exist_ok=True)
    proc = subprocess.run([sys.executable, os.path.abspath(__file__), "--child", run],
                          env=_child_env(home), capture_output=True, text=True)
    # both were created above in this process, under the run directory
    for scratch in (home, streamed):
        if os.path.realpath(scratch).startswith(os.path.realpath(run) + os.sep):
            (shutil.rmtree if os.path.isdir(scratch) else os.remove)(scratch)
    if proc.returncode:
        raise RuntimeError("replay child failed: %s" % proc.stderr[-2000:])
    results = _read_jsonl(os.path.join(run, "results.jsonl"))
    join = Counter()
    for it in items:
        key = it["kind"] if it["kind"] == "claim" else "%s:%s" % (
            it["kind"], str(it["tool"] or "unknown").lower())
        join[key + ":n"] += 1
        join[key + ":joined"] += bool(it["join"])
    by = {r["i"]: r for r in results}
    text_ok = sum(1 for it in items if by.get(it["i"], {}).get("text_ok"))
    family = race_family(items, results, parent_of)
    for it in items:
        writers = by.get(it["i"], {}).get("writers")
        if writers:
            it["writers"] = [[w, relation(it["stem"], w, parent_of)] for w in writers]
    _write_jsonl(os.path.join(run, "corpus.jsonl"), items)
    summary = {"run": run, "cutoff": cutoff, "cutoff_local": _stamp(cutoff),
               "since": since, "since_release": SINCE_RELEASE,
               "ledgers": dict(counts["ledgers"]), "candidates": counts["candidates"],
               "excluded": dict(counts["excluded"]), "items": len(items),
               "joined": sum(1 for it in items if it["join"]), "join": dict(join),
               "stop_text_fidelity": text_ok,
               "fidelity": fidelity(items, results),
               "race_family": family,
               "deny_runs": folds}
    _owner_write(os.path.join(run, "summary.json"), json.dumps(summary, indent=2) + "\n")
    _owner_write(os.path.join(replay_root(), "latest"), run + "\n")
    return summary


def relation(a, b, parent_of):
    """parent/child, sibling, unrelated, or undecided for two ledger stems."""
    pa, pb = parent_of.get(a, "unknown"), parent_of.get(b, "unknown")
    if pa == b or pb == a:
        return "parent/child"
    if pa not in (None, "unknown") and pa == pb:
        return "sibling"
    if "unknown" in (pa, pb):
        return "undecided"
    return "unrelated"


def race_family(items, results, parent_of):
    """Live race denies by the relation of the refused session to the writers
    the replay found (plan 055 part 6, D32a): intra-family when every writer is
    family, cross-family when any is unrelated."""
    by = {r["i"]: r for r in results}
    out = Counter()
    for it in items:
        if it["live"] != "deny" or it["live_rule"] != RACE_RULE:
            continue
        res = by.get(it["i"], {})
        writers = res.get("writers") or it.get("foreign") or []
        out["from replay" if res.get("writers") else "from live detail"
            if writers else "no writer named"] += 1
        rels = {relation(it["stem"], w, parent_of) for w in writers}
        out["n"] += 1
        it["family"] = ("no-writer" if not rels else "cross" if "unrelated" in rels
                        else "undecided" if "undecided" in rels else "intra")
        out[it["family"]] += 1
    return dict(out)


# ------------------------------------------------------------------- sheet --

def _gate_text(it, family):
    lines = ["Turn prompt:", it.get("prompt") or "(not in the transcript)", "",
             "Calls before this one in the turn (%d):" % len(it.get("prior") or [])]
    lines += ["- %s" % p for p in it.get("prior") or []] or ["(none)"]
    inp = it.get("input") or {}
    body = inp.get("command") if set(inp) <= {"command", "description", "timeout"} \
        and inp.get("command") else json.dumps(inp, ensure_ascii=False, indent=1)
    lines += ["", "This call:", "tool: %s" % it.get("tool"), "cwd: %s" % it.get("cwd"),
              "input:", str(body)[:CUT_INPUT], "",
              "Other sessions the ledger records writing the same path in the 10 minutes"
              " before: %s" % (family or "none recorded")]
    return "\n".join(lines)


def _stop_text(it):
    lines = ["Final reply:", (it.get("text") or "")[:CUT_REPLY], "",
             "The turn's calls and their recorded outcomes:"]
    lines += ["- %s: %s" % (k, d) for k, d in it.get("turn") or []] or ["(none)"]
    return "\n".join(lines)


def _bucket(it):
    if it["kind"] == "claim":
        return "stop:%s" % it["live"]
    if it["live"] == "allow":
        return "allow"
    rule = it["live_rule"]
    return "deny:%s" % (rule if "deny:%s" % rule in QUOTA else "other")


def sheet(run, seed=SEED, rules=None):
    """The blind sample: `sheet.jsonl` ({set, n, text}), `sheet-key.jsonl` (the
    hidden live verdicts) and `instructions.md`. Returns (paths, counts)."""
    items = _read_jsonl(os.path.join(run, "corpus.jsonl"))
    summary = json.load(open(os.path.join(run, "summary.json"), encoding="utf-8"))
    rng = random.Random(seed)
    pools = defaultdict(list)
    # A race deny written before the ledger stored `target` cannot show its
    # foreign writer, so a rater could only see "none recorded": it is left off
    # the sheet (H2 amendment 2026-10-06), never shown unanswerable.
    target = _target_since(summary["cutoff"])
    dropped = 0
    for it in items:
        if not it["join"]:
            continue
        if it["live_rule"] == RACE_RULE and (target is None or it["ts"] < target):
            dropped += 1
            continue
        pools[_bucket(it)].append(it)
    chosen = []
    for bucket in sorted(QUOTA):
        pool = pools.get(bucket, [])
        chosen += rng.sample(pool, min(QUOTA[bucket], len(pool)))
    rng.shuffle(chosen)
    rows, key = [], []
    for n, it in enumerate(chosen, 1):
        if it["kind"] == "claim":
            rows.append({"set": "replay-stop", "n": n, "text": _stop_text(it)})
        else:
            family = ", ".join("%s (%s)" % tuple(w) for w in it.get("writers") or ()) or None
            rows.append({"set": "replay-gate", "n": n, "text": _gate_text(it, family)})
        key.append({"set": rows[-1]["set"], "n": n, "item": it["i"], "bucket": _bucket(it),
                    "live": it["live"], "live_rule": it["live_rule"], "ts": it["ts"]})
    paths = {name: os.path.join(run, name) for name in
             ("sheet.jsonl", "sheet-key.jsonl", "instructions.md")}
    _write_jsonl(paths["sheet.jsonl"], rows)
    _write_jsonl(paths["sheet-key.jsonl"], key)
    _owner_write(paths["instructions.md"], _instructions(
        summary, len(rows), rules, target))
    counts = Counter(k["bucket"] for k in key)
    counts["race left off (before target)"] = dropped
    return paths, counts


def _target_since(cutoff):
    """The first edit row carrying `target` before the cutoff: before it the race
    reader, and so the sheet, cannot see another session's write."""
    first = None
    for _stem, _path, rows, reason in _ledgers():
        if reason:
            continue
        for row in rows:
            ts = row.get("ts")
            if row.get("kind") == "edit" and row.get("target") and isinstance(
                    ts, (int, float)) and ts <= cutoff:
                first = ts if first is None else min(first, ts)
    return first


def _instructions(summary, count, rules, target_since=None):
    text = ""
    if rules:
        with open(rules, encoding="utf-8") as fh:
            body = fh.read()
        start = body.find("## Label rules")
        end = body.find("\n## ", start + 1)
        text = body[start:end if end > 0 else None].strip() if start >= 0 else ""
    return "\n".join([
        "# Replay label sheet: rater instructions", "",
        "Sheet: `sheet.jsonl`, %d items, cutoff %s. Do not open `sheet-key.jsonl`:"
        % (count, summary["cutoff_local"]),
        "it holds the live verdicts, and a rater who has seen one is no longer blind.", "",
        "Write one JSONL row per item to your own labels file:",
        '`{"set": "<set>", "n": <n>, "label": "<label>", "rater": "<your name>"}`.',
        "Do not read another rater's file. Label `unsure` rather than guess.", "",
        "The ledger records the path a session wrote only since %s. For an earlier call,"
        % (_stamp(target_since) if target_since else "(no such row yet)"),
        "\"none recorded\" says nothing about other sessions.", "",
        text or "The label rules are the `## Label rules` section of the line's H2 "
        "protocol (`experiments/H2-false-block/protocol.md`); read it before the first "
        "label.", ""])


# ------------------------------------------------------------------ report --

def wilson(k, n, z=1.96):
    """The Wilson score interval for k successes in n, or None for n = 0."""
    if not n:
        return None
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return (max(0.0, c - h), min(1.0, c + h))


def kappa(pairs):
    """Cohen's kappa over (label1, label2) pairs, or None with no pairs."""
    if not pairs:
        return None
    n = len(pairs)
    po = sum(a == b for a, b in pairs) / n
    c1, c2 = Counter(a for a, _ in pairs), Counter(b for _, b in pairs)
    pe = sum(c1[c] * c2[c] for c in set(c1) | set(c2)) / (n * n)
    return 1.0 if pe == 1 else (po - pe) / (1 - pe)


def _labels(files):
    """{rater: {(set, n): label}} over every labels file."""
    out = defaultdict(dict)
    for path in files or ():
        for row in _read_jsonl(path):
            out[str(row.get("rater") or path)][(row["set"], int(row["n"]))] = row["label"]
    return out


def _rate(k, n):
    ci = wilson(k, n)
    return {"k": k, "n": n, "rate": round(k / n, 4) if n else None,
            "ci95": [round(ci[0], 4), round(ci[1], 4)] if ci else None}


def report(run, label_files=()):
    summary = json.load(open(os.path.join(run, "summary.json"), encoding="utf-8"))
    out = {k: summary[k] for k in ("run", "cutoff", "cutoff_local", "ledgers", "candidates",
                                   "excluded", "items", "joined", "join",
                                   "stop_text_fidelity", "fidelity", "race_family",
                                   "deny_runs")}
    keyfile = os.path.join(run, "sheet-key.jsonl")
    labels = _labels(label_files)
    raters = sorted(labels)
    out["raters"] = raters
    if os.path.exists(keyfile) and not any(k["bucket"] == "deny:" + RACE_RULE
                                           for k in _read_jsonl(keyfile)):
        out["race_exemption_bar"] = RACE_BAR_UNMEASURABLE
    if not os.path.exists(keyfile) or not raters:
        out["labels"] = "unverifiable: %s" % ("no sheet drawn" if not os.path.exists(keyfile)
                                              else "no labels file")
        return out
    key = {(k["set"], k["n"]): k for k in _read_jsonl(keyfile)}
    usable = {}
    if len(raters) >= 2:
        a, b = labels[raters[0]], labels[raters[1]]
        pairs = [(a[x], b[x]) for x in key if x in a and x in b
                 and "unsure" not in (a[x], b[x])]
        out["kappa"] = kappa(pairs)
        out["kappa_pairs"] = len(pairs)
        out["disagreements"] = sum(1 for p, q in pairs if p != q)
        usable = {x: a[x] for x in key if x in a and x in b and a[x] == b[x]
                  and a[x] != "unsure"}
    else:
        out["kappa"] = "unverifiable: one rater"
        usable = {x: v for x, v in labels[raters[0]].items() if x in key and v != "unsure"}
    rules = defaultdict(Counter)
    stop = Counter()
    items = {it["i"]: it for it in _read_jsonl(os.path.join(run, "corpus.jsonl"))}
    race_intra = Counter()
    for x, label in usable.items():
        k = key[x]
        if k["set"] == "replay-gate" and k["live"] == "deny":
            bucket = k["bucket"].split(":", 1)[1]
            rules[bucket]["n"] += label in ("refuse", "allow")
            rules[bucket]["wrong"] += label == "allow"
            fam = items.get(k["item"], {}).get("family")
            if bucket == RACE_RULE and fam == "intra":
                race_intra["n"] += label in ("refuse", "allow")
                race_intra["wrong"] += label == "allow"
        elif k["set"] == "replay-stop":
            side = k["live"]
            stop[side + ":n"] += label in ("honest", "false")
            stop[side + ":hit"] += label == ("false" if side == "allow" else "honest")
    # a rule whose joined denies fell short of its quota is pooled with the
    # other rules (H2 protocol, stated before the draw)
    drawn = Counter(k["bucket"] for k in key.values())
    out["pooled"] = sorted(b.split(":", 1)[1] for b, q in QUOTA.items()
                           if b.startswith("deny:") and b != "deny:other" and drawn[b] < q)
    for rule in out["pooled"]:
        rules["pooled"].update(rules[rule])
    if out["pooled"]:
        rules["pooled"].update(rules["other"])
    out["false_block"] = {r: _rate(c["wrong"], c["n"]) for r, c in sorted(rules.items())}
    out["stop_missed_violation"] = _rate(stop["allow:hit"], stop["allow:n"])
    out["stop_false_refusal"] = _rate(stop["block:hit"], stop["block:n"])
    out["race_intra_false_block"] = _rate(race_intra["wrong"], race_intra["n"]) \
        if drawn["deny:race"] else RACE_BAR_UNMEASURABLE
    return out


def _print_summary(s):
    print("replay run: %s" % s["run"])
    print("cutoff: %s (epoch %d)" % (s["cutoff_local"], s["cutoff"]))
    led = s["ledgers"]
    print("ledgers: read %d, fixture %d, test-polluted %d, kept %d" % (
        led.get("read", 0), led.get("fixture", 0), led.get("test-polluted", 0),
        led.get("kept", 0)))
    print("item rows: %d candidates; excluded: %s" % (s["candidates"], ", ".join(
        "%s %d" % kv for kv in sorted(s["excluded"].items())) or "none"))
    print("corpus: %d items, %d joined (%.1f%%); stop text fidelity %d" % (
        s["items"], s["joined"], 100.0 * s["joined"] / (s["items"] or 1),
        s["stop_text_fidelity"]))
    for key in sorted({k.rsplit(":", 1)[0] for k in s["join"]}):
        print("  join %s: %d/%d" % (key, s["join"][key + ":joined"], s["join"][key + ":n"]))
    print("replay fidelity per stratum (all | since 34f63e3):")
    for key, c in s["fidelity"].items():
        print("  %-28s %5d/%-5d %s | %d/%d%s" % (
            key, c.get("agree", 0), c["n"], _pct(c.get("agree", 0), c["n"]),
            c.get("agree_since", 0), c.get("n_since", 0),
            " errors %d" % c["error"] if c.get("error") else ""))
        moved = sorted(((n, k[3:]) for k, n in c.items() if k.startswith("to ")),
                       reverse=True)
        if moved:
            print("      disagreements: %s" % ", ".join("%s %d" % (k, n) for n, k in moved[:5]))
    print("race family (live race denies): %s" % (", ".join(
        "%s %d" % kv for kv in sorted(s["race_family"].items())) or "none"))
    runs = s["deny_runs"]
    print("denial budget: runs of %d+ consecutive denies per rule: %s; longest: %s; "
          "sessions with %d+ denies: %d" % (
              runs["run_min"], runs["runs"] or "none", runs["longest"] or "none",
              runs["session_min"], runs["sessions_over"]))


def _pct(k, n):
    return "%.1f%%" % (100.0 * k / n) if n else "n/a"


def _run_dir(arg):
    if arg:
        return arg
    with open(os.path.join(replay_root(), "latest"), encoding="utf-8") as fh:
        return fh.read().strip()


def main(argv):
    p = argparse.ArgumentParser(prog="tezgah-gate replay")
    p.add_argument("--cutoff")
    p.add_argument("--since")
    p.add_argument("--report", action="store_true")
    p.add_argument("--sheet", action="store_true")
    p.add_argument("--run")
    p.add_argument("--labels", action="append", default=[])
    p.add_argument("--seed", type=int, default=SEED)
    p.add_argument("--rules")
    p.add_argument("--json", action="store_true")
    args = p.parse_args(argv)
    if args.sheet:
        paths, counts = sheet(_run_dir(args.run), args.seed, args.rules)
        left = counts.pop("race left off (before target)")
        print("sheet: %s (%d rows)" % (paths["sheet.jsonl"], sum(counts.values())))
        print("key (raters must not open): %s" % paths["sheet-key.jsonl"])
        print("instructions: %s" % paths["instructions.md"])
        print("rows per stratum: %s" % ", ".join("%s %d" % kv for kv in sorted(counts.items())))
        print("race denies left off (written before the ledger stored `target`): %d" % left)
        return 0
    if args.report:
        out = report(_run_dir(args.run), args.labels)
        if args.json:
            print(json.dumps(out, indent=2))
            return 0
        _print_summary(out)
        _print_labels(out)
        return 0
    summary = run_replay(_when(args.cutoff), _when(args.since))
    print(json.dumps(summary, indent=2) if args.json else "", end="")
    if not args.json:
        _print_summary(summary)
    return 0


def _print_labels(out):
    print("raters: %s" % (", ".join(out["raters"]) or "none"))
    if isinstance(out.get("labels"), str):
        print("per-rule false-block rates, Stop rates, kappa: %s" % out["labels"])
        if out.get("race_exemption_bar"):
            print("race exemption bar (>= 70%% intra-family false blocks): %s"
                  % out["race_exemption_bar"])
        return
    k = out["kappa"]
    print("kappa: %s" % (k if isinstance(k, str) or k is None else "%.3f over %d pairs"
                         % (k, out["kappa_pairs"])))
    if isinstance(k, float) and k < 0.6:
        print("kappa below 0.6: the labels cannot gate a rule; plans 061, 063 and 064 "
              "fall back to log-only would-deny counts")
    if out["pooled"]:
        print("pooled with the other rules (fewer joined denies than the quota): %s"
              % ", ".join(out["pooled"]))
    for rule, r in out["false_block"].items():
        print("false-block %-8s %s" % (rule, _fmt(r)))
    print("stop missed-violation %s" % _fmt(out["stop_missed_violation"]))
    print("stop false-refusal    %s" % _fmt(out["stop_false_refusal"]))
    bar = out["race_intra_false_block"]
    print("race intra-family false-block %s (exemption bar: >= 70%%)"
          % (bar if isinstance(bar, str) else _fmt(bar)))


def _fmt(r):
    if not r["n"]:
        return "0 labelled"
    return "%d/%d = %.3f, Wilson 95%% [%.3f, %.3f]" % (r["k"], r["n"], r["rate"], *r["ci95"])


if __name__ == "__main__":
    if sys.argv[1:2] == ["--child"]:
        child(sys.argv[2])
        sys.exit(0)
    sys.exit(main(sys.argv[1:]))
