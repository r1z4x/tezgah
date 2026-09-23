#!/usr/bin/env python3
"""One run of the natural-voice-fit experiments.

Tracks: h1 and h5 edit the same drafts under two contracts and have blind judges
score native-ness; h2 swaps a generic audience line for a register brief; h3 adds
samples of the writer's prose; h4 reads the drafts against a term rail and scores
terms by script. Everything the run needs to be judged is printed to stdout,
including one final TEZGAH_RESULTS line.

Usage: python3 run.py --track h1 [--limit N]
"""
import argparse
import concurrent.futures as cf
import json
import os
import pathlib
import random
import re
import statistics
import sys
import time
import urllib.error
import urllib.request

HERE = pathlib.Path(__file__).resolve().parent
REPO = HERE.parents[3]

HOST_CHAT = None  # injected by the host kernel: callable(model, prompt) -> str
TRANSPORT = os.environ.get("TEZGAH_TRANSPORT", "openrouter")

GENERATOR = "deepseek/deepseek-v4-flash"
JUDGES = ["anthropic/claude-sonnet-5", "google/gemini-2.5-pro", "x-ai/grok-4.3"]
# The host transport uses the tiers the session exposes; the concrete model
# behind a tier is whatever the host resolves it to, and the run records the tier.
HOST_GENERATOR = "slow"
HOST_JUDGES = ["default", "smol"]
WORKERS = 6

MARKERS = {
    "tr": ["mektedir", "maktadır", "söz konusu", "bu bağlamda", "bu kapsamda",
           "gerekir ki", "unutulmamalıdır", "organize et", "realize ed",
           "implemente ed", "aksiyon al", "vizyoner", "fokusla", " tane ",
           " adet ", "belirtmek gerek"],
    "de": ["Churn-Rate", "Pricing-Modell", "Adoption", "allokiert", "supported",
           "Root-Cause-Analyse", "Release Notes", "Incident Summary",
           "Queue-Management", "Alert-Schwellwert", "Ask", "Task", "Owner",
           "in diesem Zusammenhang ist festzuhalten", "es muss betont werden",
           "darüber hinaus ist anzumerken"],
}


def chat(model, system, user, temperature=0.0, tries=4):
    if HOST_CHAT is not None:
        prompt = system + "\n\n" + user
        last = None
        for attempt in range(tries):
            try:
                return HOST_CHAT(model, prompt)
            except Exception as exc:  # noqa: BLE001 - retried, then re-raised
                last = exc
                time.sleep(1.0 * (attempt + 1))
        raise RuntimeError("host %s failed: %r" % (model, last))
    key = os.environ.get("OPENROUTER_API_KEY")
    if not key:
        raise SystemExit(
            "no transport: export OPENROUTER_API_KEY, or drive this harness from a "
            "host kernel that injects one - set run.HOST_CHAT to a callable taking "
            "(model, prompt) and call run.main([...]) there. The recorded runs used "
            "the host transport; see to_human/report.md.")
    body = json.dumps({
        "model": model,
        "temperature": temperature,
        "messages": [{"role": "system", "content": system},
                     {"role": "user", "content": user}],
    }).encode()
    last = None
    for attempt in range(tries):
        req = urllib.request.Request(
            "https://openrouter.ai/api/v1/chat/completions", data=body,
            headers={"Authorization": "Bearer " + key,
                     "Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=180) as fh:
                payload = json.loads(fh.read())
            return payload["choices"][0]["message"]["content"]
        except Exception as exc:  # noqa: BLE001 - retried, then re-raised
            last = exc
            time.sleep(1.5 * (attempt + 1))
    raise RuntimeError("%s failed: %r" % (model, last))


def base_contract():
    text = (REPO / "skills" / "no-ai-slop" / "SKILL.md").read_text()
    text = text.split("---", 2)[2]                      # drop the frontmatter
    head, _, tail = text.partition("## Two jobs")       # drop "In this setup"
    return ("## Two jobs" + tail).strip()


def read(name):
    return json.loads((HERE / name).read_text())


def edit_prompt(contract, item, extra=""):
    return ("Apply the editing contract below to the draft, and return only the "
            "edited draft: no commentary, no preamble, no code fence.\n\n"
            "=== CONTRACT ===\n%s\n=== END CONTRACT ===\n%s\n"
            "=== DRAFT (%s, %s) ===\n%s\n=== END DRAFT ===\n"
            % (contract, extra, item["id"], item["register"], item["draft"]))


def clean_edit(text):
    """The judged text is the draft, not the editor's notes beside it. The shipped
    skill asks for a "What changed" section, so both arms are truncated at the
    same marker and the raw text stays in the log."""
    t = text.strip()
    if t.startswith("```"):
        t = re.sub(r"^```[a-z]*\s*", "", t)
        t = re.sub(r"\s*```\s*$", "", t)
    for marker in ("**What changed", "**What's changed", "**Changes", "# What changed"):
        idx = t.find(marker)
        if idx > 0:
            t = t[:idx]
    return re.sub(r"\n-{3,}\s*$", "", t).strip()


def edit(contract, item, extra=""):
    return clean_edit(chat(GENERATOR, "You are a precise editor. You return only edited text.",
                           edit_prompt(contract, item, extra)))


def parse_json(raw):
    text = raw.strip()
    if text.startswith("```"):
        text = re.sub(r"^```[a-z]*\s*|\s*```$", "", text, flags=re.S).strip()
    try:
        return json.loads(text)
    except ValueError:
        pass
    start = text.find("{")
    while start != -1:
        depth, in_str, esc = 0, False, False
        for i in range(start, len(text)):
            ch = text[i]
            if in_str:
                if esc:
                    esc = False
                elif ch == "\\":
                    esc = True
                elif ch == '"':
                    in_str = False
                continue
            if ch == '"':
                in_str = True
            elif ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    try:
                        return json.loads(text[start:i + 1])
                    except ValueError:
                        break
        start = text.find("{", start + 1)
    raise ValueError("no json object in %r" % raw[:200])


def score_pair(model, rubric, item, first, second, extra=""):
    """Blind scores for two drafts; the caller knows which arm is in slot one."""
    user = ("%s\n\nReader/context: %s\n\n=== DRAFT 1 ===\n%s\n\n=== DRAFT 2 ===\n%s\n\n"
            "Reply with one JSON object only: {\"score_1\": <0-5>, \"score_2\": <0-5>, "
            "\"why_1\": \"<8 words>\", \"why_2\": \"<8 words>\"}"
            % (rubric, extra or "a general professional reader", first, second))
    return parse_json(chat(model, "You are a strict evaluator. You answer with JSON only.", user))


def prefer(model, item, first, second, samples):
    user = ("Three samples of a writer's own prose:\n%s\n\n"
            "Which of the two edits below sounds more like that writer (voice, "
            "vocabulary, cadence, level of polish)?\n\n"
            "=== DRAFT 1 ===\n%s\n\n=== DRAFT 2 ===\n%s\n\n"
            "Reply with one JSON object only: {\"choice\": \"1\" | \"2\" | \"equal\"}"
            % (samples, first, second))
    return parse_json(chat(model, "You are a strict evaluator. You answer with JSON only.", user))


def words(text):
    return len(re.findall(r"[\w'’%-]+", text, re.UNICODE))


def marker_hits(text, lang):
    return [m for m in MARKERS[lang] if m in text]


def marker_density(text, lang):
    return 100.0 * sum(text.count(m) for m in MARKERS[lang]) / max(words(text), 1)


def term_errors(source, edited, rail, register):
    """The rail read as a script: keep forms that vanished, calques that stayed."""
    points, detail = 0, []
    for entry in rail["keep"]:
        if entry["form"] in source and entry["form"] not in edited:
            points += entry["severity"]
            detail.append("lost keep term %r (+%d)" % (entry["form"], entry["severity"]))
    for entry in rail["translate"]:
        if entry["from"] in (edited + source) and entry["from"] in edited:
            points += entry["severity"]
            detail.append("calque %r left (+%d)" % (entry["from"], entry["severity"]))
    for entry in rail.get("register_overrides", []):
        if entry["register"] != register or entry["decision"] != "keep":
            continue
        if entry["form"] in source and entry["form"] not in edited:
            points += 100
            detail.append("register keep term %r translated (+100)" % entry["form"])
    return points, detail


def bootstrap_ci(values, n=2000, seed=17):
    if len(values) < 2:
        return (float("nan"), float("nan"))
    rng = random.Random(seed)
    means = [statistics.fmean(rng.choices(values, k=len(values))) for _ in range(n)]
    means.sort()
    return means[int(0.025 * n)], means[int(0.975 * n) - 1]


def ordered_map(fn, items):
    """The host kernel's model primitive is only callable from its own thread, so
    the host transport runs sequentially and the HTTP transport keeps its pool."""
    if HOST_CHAT is not None:
        return [fn(item) for item in items]
    with cf.ThreadPoolExecutor(WORKERS) as pool:
        return list(pool.map(fn, items))


def run_pairs(items, build, rubric_for, judged_extra, samples=None):
    """Generate both arms, judge blind in both orders, return per-item records."""
    def job(item):
        arm_a = build(item, "a")
        arm_b = build(item, "b")
        first_scores, second_scores, notes = [], [], []
        for model in JUDGES:
            forward = score_pair(model, rubric_for(item), item, arm_a, arm_b, judged_extra(item))
            back = score_pair(model, rubric_for(item), item, arm_b, arm_a, judged_extra(item))
            # slot 1 is A in forward, B in back
            first_scores.append((forward["score_1"] + back["score_2"]) / 2.0)
            second_scores.append((forward["score_2"] + back["score_1"]) / 2.0)
            notes.append("%s: fwd %s vs %s, back %s vs %s"
                         % (model.split("/")[-1], forward["score_1"], forward["score_2"],
                            back["score_1"], back["score_2"]))
        return {"id": item["id"], "register": item["register"], "arm_a": arm_a, "arm_b": arm_b,
                "a_mean": statistics.fmean(first_scores), "b_mean": statistics.fmean(second_scores),
                "delta": statistics.fmean(second_scores) - statistics.fmean(first_scores),
                "judges": notes}
    return ordered_map(job, items)


def run_preference(items, samples):
    def job(item):
        contract = base_contract()
        arm_a = edit(contract, item)
        arm_b = edit(contract, item, "Writer's own prose samples:\n" + samples)
        votes = []
        for model in JUDGES:
            forward = prefer(model, item, arm_a, arm_b, samples)
            back = prefer(model, item, arm_b, arm_a, samples)
            votes.append({"1": "a", "2": "b", "equal": "equal"}[forward["choice"]])
            votes.append({"1": "b", "2": "a", "equal": "equal"}[back["choice"]])
        return {"id": item["id"], "register": item["register"], "arm_a": arm_a, "arm_b": arm_b,
                "votes_for_b": sum(1 for v in votes if v == "b"),
                "votes_for_a": sum(1 for v in votes if v == "a"),
                "votes_equal": sum(1 for v in votes if v == "equal"),
                "share_b": sum(1 for v in votes if v == "b") / len(votes)}
    return ordered_map(job, items)


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--track", required=True, choices=["h1", "h2", "h3", "h4", "h5"])
    ap.add_argument("--limit", type=int, default=0)
    args = ap.parse_args(argv)

    if HOST_CHAT is not None:
        globals()["GENERATOR"] = HOST_GENERATOR
        globals()["JUDGES"] = HOST_JUDGES
    transport = "host" if HOST_CHAT is not None else TRANSPORT

    track = args.track
    items = read("items_tr.json")["items"] if track != "h5" else read("items_de.json")["items"]
    if args.limit:
        items = items[:args.limit]
    rail = read("rail.json")
    briefs = read("briefs.json")
    samples = "\n\n".join(read("voice.json")["samples"])
    contract = base_contract()

    print("config: track=%s transport=%s generator=%s judges=%s items=%d"
          % (track, transport, GENERATOR, ",".join(JUDGES), len(items)))
    print("contract bytes=%d, rail keep=%d translate=%d"
          % (len(contract), len(rail["keep"]), len(rail["translate"])))

    if track in ("h1", "h5"):
        lang = "tr" if track == "h1" else "de"
        extra = (HERE / ("candidate_tr.md" if lang == "tr" else "candidate_de.md")).read_text()
        records = run_pairs(items,
                            lambda item, arm: edit(contract, item, extra if arm == "b" else ""),
                            lambda item: "Score each draft 0-5 for how natural it reads as "
                                         "%s written by a native speaker: grammar, idiom, word "
                                         "order, and whether any phrase smells translated."
                                         % ("Turkish" if lang == "tr" else "German"),
                            lambda item: item["brief"])
        deltas = [r["delta"] for r in records]
        lo, hi = bootstrap_ci(deltas)
        md_a = statistics.fmean(marker_density(r["arm_a"], lang) for r in records)
        md_b = statistics.fmean(marker_density(r["arm_b"], lang) for r in records)
        for r in records:
            print("item %-12s %-10s a=%.2f b=%.2f delta=%+.2f | %s"
                  % (r["id"], r["register"], r["a_mean"], r["b_mean"], r["delta"], r["judges"][0]))
            print("    markers a=%s b=%s" % (marker_hits(r["arm_a"], lang), marker_hits(r["arm_b"], lang)))
            print("    --- arm a ---\n%s\n    --- arm b ---\n%s" % (r["arm_a"], r["arm_b"]))
        summary = {"track": track, "lang": lang, "n_items": len(records),
                   "delta_mean": statistics.fmean(deltas), "ci95": [lo, hi],
                   "marker_density_a": md_a, "marker_density_b": md_b,
                   "per_item": [{"id": r["id"], "delta": r["delta"]} for r in records]}
    elif track == "h2":
        records = run_pairs(
            items,
            lambda item, arm: edit(contract, item,
                                   ("Reader brief:\n" + briefs[item["register"]]) if arm == "b"
                                   else "Audience: general professional readers. Write clearly."),
            lambda item: "Score each draft 0-5 on how well it serves this reader.",
            lambda item: briefs[item["register"]])
        deltas = [r["delta"] for r in records]
        lo, hi = bootstrap_ci(deltas)
        for r in records:
            print("item %-12s %-10s a=%.2f b=%.2f delta=%+.2f" % (r["id"], r["register"], r["a_mean"], r["b_mean"], r["delta"]))
            print("    --- arm a ---\n%s\n    --- arm b ---\n%s" % (r["arm_a"], r["arm_b"]))
        summary = {"track": track, "n_items": len(records), "delta_mean": statistics.fmean(deltas), "ci95": [lo, hi],
                   "per_item": [{"id": r["id"], "delta": r["delta"]} for r in records]}
    elif track == "h3":
        records = run_preference(items, samples)
        share = statistics.fmean(r["share_b"] for r in records)
        for r in records:
            print("item %-12s b=%d a=%d equal=%d share_b=%.2f"
                  % (r["id"], r["votes_for_b"], r["votes_for_a"], r["votes_equal"], r["share_b"]))
            print("    --- arm a ---\n%s\n    --- arm b ---\n%s" % (r["arm_a"], r["arm_b"]))
        summary = {"track": track, "n_items": len(records), "share_b": share,
                   "per_item": [{"id": r["id"], "share_b": r["share_b"]} for r in records]}
    else:
        extra_a = ("Where the draft uses an English word that has a Turkish equivalent, "
                   "translate it to the Turkish equivalent.")
        extra_b = ("Term decisions for this draft. Keep these exactly as they are: %s. "
                   "Replace these: %s. In the %s register: %s."
                   % (", ".join(e["form"] for e in rail["keep"]),
                      "; ".join("%s -> %s" % (e["from"], e["to"]) for e in rail["translate"]),
                      "corporate", "; ".join("%s stays (%s)" % (e["form"], e["reason"])
                                             for e in rail["register_overrides"])))
        rows = []
        for item in items:
            arm_a = edit(contract, item, extra_a)
            arm_b = edit(contract, item, extra_b)
            pa, da = term_errors(item["draft"], arm_a, rail, item["register"])
            pb, db = term_errors(item["draft"], arm_b, rail, item["register"])
            judges = [score_pair(m, "Score each draft 0-5 on clarity and on whether the "
                                    "information the draft carried is preserved.",
                                 item, arm_a, arm_b, item["brief"]) for m in JUDGES]
            clarity_a = statistics.fmean(j["score_1"] for j in judges)
            clarity_b = statistics.fmean(j["score_2"] for j in judges)
            rows.append({"id": item["id"], "register": item["register"],
                         "points_a": pa, "points_b": pb,
                         "per1000_a": 1000.0 * pa / max(words(arm_a), 1),
                         "per1000_b": 1000.0 * pb / max(words(arm_b), 1),
                         "clarity_a": clarity_a, "clarity_b": clarity_b,
                         "detail_a": da, "detail_b": db})
            print("item %-12s points a=%d b=%d | per1000 a=%.2f b=%.2f | clarity a=%.2f b=%.2f"
                  % (item["id"], pa, pb, rows[-1]["per1000_a"], rows[-1]["per1000_b"], clarity_a, clarity_b))
            if da or db:
                print("    a: %s" % "; ".join(da))
                print("    b: %s" % "; ".join(db))
        summary = {"track": track, "n_items": len(rows),
                   "per1000_a": statistics.fmean(r["per1000_a"] for r in rows),
                   "per1000_b": statistics.fmean(r["per1000_b"] for r in rows),
                   "clarity_a": statistics.fmean(r["clarity_a"] for r in rows),
                   "clarity_b": statistics.fmean(r["clarity_b"] for r in rows),
                   "per_item": rows}

    print("\n=== SUMMARY ===")
    print(json.dumps(summary, ensure_ascii=False, indent=1)[:4000])
    print("TEZGAH_RESULTS " + json.dumps(summary, ensure_ascii=False))


if __name__ == "__main__":
    sys.exit(main())
