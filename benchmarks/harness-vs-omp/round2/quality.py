#!/usr/bin/env python3
"""Qualitative / structural analysis of round-2 run outputs.

For every run it diffs the resulting repo against the pristine fixture and
records: files touched, added/removed lines, added comments, added docstrings,
and task-specific implementation-quality signals. Also scores the final reply.
"""
import difflib
import json
import re
from pathlib import Path

BASE = Path(__file__).resolve().parent
FIXTURE = BASE / "fixture"
RESULTS = BASE / "results"
SKIP = {".git", "__pycache__", ".pytest_cache", ".codebase-memory", ".omp"}

TASK_SIGNALS = {
    "t1": [("round(", r"round\("), ("float-div", r"/\s*100")],
    "t2": [("raises", r"raise ValueError"), ("round", r"round\(")],
    "t7": [("none-idiom", r"items\s*=\s*None"), ("copy", r"(list\(|\[:\]|copy)")],
    "t8": [("page-1", r"\(\s*page\s*-\s*1\s*\)"), ("min-clamp", r"min\(")],
    "t9": [("space-fmt", r'\{[^}]*\}\s*\{?currency')],
    "t13": [("set-or-dict", r"(set\(|dict\.fromkeys|=\{|\bset\b)"), ("list-scan", r"not in .*\[:")],
    "t16": [("nfc", r"unicodedata\.normalize"), ("split-join", r"split\(\)")],
    "t18": [("tzinfo-check", r"tzinfo\s+is\s+None"), ("utcoffset", r"utcoffset")],
    "t15": [("domain-err", r"raise InventoryError"), ("exact-msg", r"must be positive")],
    "t12": [("domain-err", r"raise InventoryError"), ("index", r"enumerate\(")],
    "t17": [("casefold-or-lower", r"(casefold\(|\.lower\()")],
}


def changed_files(repo):
    out = {}
    for p in FIXTURE.rglob("*.py"):
        if SKIP & set(p.parts):
            continue
        rel = p.relative_to(FIXTURE)
        q = repo / rel
        a = p.read_text().splitlines(keepends=True)
        b = q.read_text().splitlines(keepends=True) if q.exists() else []
        if a != b:
            out[str(rel)] = (a, b)
    return out


def diff_stats(pairs):
    added, removed, comments, docstrings = 0, 0, 0, 0
    for _, (a, b) in pairs.items():
        sm = difflib.unified_diff(a, b, n=0)
        in_doc = False
        for line in sm:
            if line.startswith("+++") or line.startswith("---") or line.startswith("@@"):
                continue
            if line.startswith("+"):
                added += 1
                body = line[1:].strip()
                if body.startswith("#"):
                    comments += 1
                if body.startswith('"""') or body.startswith("'''"):
                    docstrings += (1 if body.count('"""') < 2 else 0)
                    in_doc = body.count('"""') == 1
            elif line.startswith("-"):
                removed += 1
    return added, removed, comments, docstrings


TR_WORDS = ["ve", "için", "bir", "bu", "olarak", "ile", "değil", "var", "eklendi",
            "düzeltildi", "fonksiyon", "test", "geçiyor", "yapıldı"]


def reply_scores(text):
    low = text.lower()
    tr = sum(len(re.findall(r"(?<![\wçğıöşü])" + w + r"(?![\wçğıöşü])", low)) for w in TR_WORDS)
    words = len(re.findall(r"\S+", text))
    verified = bool(re.search(r"(test|pytest|unittest|geçiyor|doğrulad|passed|ok\b)", low))
    bullets = len(re.findall(r"(?m)^\s*[-*]\s", text))
    return {"words": words, "tr_hits": tr, "claims_verification": verified, "bullets": bullets}


def main():
    rows = [json.loads(l) for l in open(RESULTS / "results.jsonl") if l.strip()]
    out = []
    for r in rows:
        repo = RESULTS / f"{r['task']}__{r['arm'].replace('+', '_')}" / "repo"
        pairs = changed_files(repo)
        added, removed, comments, docstrings = diff_stats(pairs)
        signals = {}
        for label, pat in TASK_SIGNALS.get(r["task"], []):
            blob = "\n".join("".join(b) for _, (a, b) in pairs.items() if a != b) or ""
            signals[label] = bool(re.search(pat, blob))
        rs = reply_scores(r.get("final_text") or "")
        out.append({
            "task": r["task"], "arm": r["arm"], "pass": r["pass"],
            "files_touched": sorted(pairs.keys()), "n_files": len(pairs),
            "added": added, "removed": removed, "comments_added": comments,
            "docstring_lines": docstrings, "signals": signals, **rs,
        })
    with open(RESULTS / "quality.jsonl", "w") as f:
        for o in out:
            f.write(json.dumps(o) + "\n")
    print(f"wrote {len(out)} rows to results/quality.jsonl")


if __name__ == "__main__":
    main()
