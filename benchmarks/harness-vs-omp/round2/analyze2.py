#!/usr/bin/env python3
"""Summarise round-2 results with reasoning-inclusive token accounting.

`omp` folds reasoning tokens into `output`; opencode reports them in a separate
`reasoning` field. This reads the raw per-run logs so the two are compared
like-for-like: generated = text + reasoning.
"""
import json
import statistics
from pathlib import Path

BASE = Path(__file__).resolve().parent
RESULTS = BASE / "results"
ARMS = ["tezgah+opencode", "omp+graph", "omp+tezgah-port"]
TASKS = [f"t{i}" for i in range(1, 21)]


def tokens_from_log(path, arm):
    inp = gen = reas = cache = cost = steps = 0
    for line in open(path):
        line = line.strip()
        if not line.startswith("{"):
            continue
        try:
            ev = json.loads(line)
        except json.JSONDecodeError:
            continue
        if arm == "tezgah+opencode" and ev.get("type") == "step_finish":
            p = ev.get("part", {})
            t = p.get("tokens", {}) or {}
            steps += 1
            inp += t.get("input", 0) or 0
            gen += t.get("output", 0) or 0
            reas += t.get("reasoning", 0) or 0
            cache += ((t.get("cache") or {}).get("read", 0)) or 0
            cost += p.get("cost", 0) or 0
        elif arm != "tezgah+opencode" and ev.get("type") == "agent_end":
            for m in ev.get("messages", []):
                if m.get("role") != "assistant":
                    continue
                u = m.get("usage") or {}
                c = u.get("cost") or {}
                steps += 1
                inp += u.get("input", 0) or 0
                gen += u.get("output", 0) or 0
                reas += u.get("reasoningTokens", 0) or 0
                cache += u.get("cacheRead", 0) or 0
                cost += (c.get("total", 0) if isinstance(c, dict) else 0) or 0
    if arm == "tezgah+opencode":
        generated = gen + reas          # output excludes reasoning here
        text = gen
    else:
        generated = gen                 # output already includes reasoning
        text = gen - reas
    return {"input": inp, "cache": cache, "text": text, "reasoning": reas,
            "generated": generated, "cost": cost, "steps": steps}


def load_rows():
    rows = [json.loads(l) for l in open(RESULTS / "results.jsonl") if l.strip()]
    for r in rows:
        log = RESULTS / f"{r['task']}__{r['arm'].replace('+', '_')}" / "stdout.log"
        r["tok"] = tokens_from_log(log, r["arm"]) if log.exists() else {}
    return rows


def main():
    rows = load_rows()
    by = {(r["task"], r["arm"]): r for r in rows}

    print("=== GÖREV x KOL ===")
    print(f"{'task':5}" + "".join(f"{a:>18}" for a in ARMS))
    for t in TASKS:
        line = f"{t:5}"
        for a in ARMS:
            r = by.get((t, a))
            line += f"{(('PASS' if r['pass'] else 'fail') if r else '-'):>18}"
        print(line)

    print("\n=== KOL TOPLAM (reasoning-dahil) ===")
    print(f"{'arm':20}{'pass':>7}{'cost$':>9}{'text':>8}{'reas':>7}{'generated':>10}"
          f"{'input':>9}{'cache':>10}{'steps':>7}{'graph':>7}")
    for a in ARMS:
        sub = [r for r in rows if r["arm"] == a]
        agg = {k: sum(r["tok"].get(k, 0) for r in sub) for k in
               ("input", "cache", "text", "reasoning", "generated", "cost", "steps")}
        g = sum(r.get("graph_calls", 0) for r in sub)
        p = sum(1 for r in sub if r["pass"])
        print(f"{a:20}{f'{p}/{len(sub)}':>7}{agg['cost']:>9.4f}{agg['text']:>8}{agg['reasoning']:>7}"
              f"{agg['generated']:>10}{agg['input']:>9}{agg['cache']:>10}{agg['steps']:>7}{g:>7}")

    print("\n=== BAŞARISIZ KOŞULAR ===")
    fails = [r for r in rows if not r["pass"]]
    print("yok" if not fails else "")
    for r in fails:
        print(f"  {r['task']:4}{r['arm']:18} {r.get('reasons')}")

    print("\n=== GRAF KULLANIMI ===")
    for r in rows:
        if r.get("graph_calls"):
            print(f"  {r['task']:4}{r['arm']:18} graph={r['graph_calls']}")


if __name__ == "__main__":
    main()
