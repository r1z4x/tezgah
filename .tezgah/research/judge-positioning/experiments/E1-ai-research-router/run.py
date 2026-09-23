#!/usr/bin/env python3
"""E1: can the judgement seam serve a ~98-option routing Choice?

Arm A asks one Choice over all 98 ai-research entries (criteria = name -> 100-char
purpose, the shape tezgah_skill_pick uses for the roster). Arm B asks the six
stages first and then that stage's entries. Both arms answer the same 14
hand-labelled queries; results go to results.jsonl as JSON lines.

Read-only against the repo; the only thing it writes is stdout, which the caller
redirects into the experiment directory.
"""
import json
import os
import sys

REPO = "/Users/rizax/Projects/tezgah"
sys.path.insert(0, os.path.join(REPO, "hooks"))
import tezgah_judge  # noqa: E402

LIB = json.load(open(os.path.join(REPO, "skills", "ai-research", "library.json")))
CLAUSE_CAP = 100
NONE_ENTRY = "none"
NONE_STAGE = "none"
FLAT = ("Which single entry of this library is the right one to read for the "
        "reader's request? Match the topic, not the wording: the reader may name "
        "the same subject with a different word. Answer 'none' when no entry "
        "covers the request.")
STAGE = ("Which single stage of this research library holds the entry the "
         "reader's request needs? The stages run in research order - framing the "
         "question, data, training, measurement and safety, running and serving, "
         "and writing up. Answer 'none' when no stage covers the request.")

# (id, query, label) - each query names exactly one entry; the query keeps the
# discriminating technical term and drops the vendor name.
QUERIES = [
    ("Q01", "I want to serve a 7B model with continuous batching and prefix "
            "caching to maximise throughput per GPU.", "serving-llms-vllm"),
    ("Q02", "Quantise a 70B model down to 4-bit without needing any calibration "
            "data.", "hqq-quantization"),
    ("Q03", "Extend my model's context window from 8k to 128k with YaRN.", "long-context"),
    ("Q04", "Train a Mixture of Experts model.", "moe-training"),
    ("Q05", "Train and analyse sparse autoencoders to decompose activations into "
            "interpretable features.", "sparse-autoencoder-training"),
    ("Q06", "Measure pass@k on HumanEval and MBPP for a code generation model.",
            "evaluating-code-models"),
    ("Q07", "Give me a minimal educational GPT implementation in a few hundred "
            "lines of code.", "nanogpt"),
    ("Q08", "Run a 4-bit LLM on Apple Silicon with no NVIDIA GPU.", "llama-cpp"),
    ("Q09", "Merge two fine-tuned checkpoints into one model without retraining.",
            "model-merging"),
    ("Q10", "Distil a 70B teacher into a 3B student to cut inference cost.",
            "knowledge-distillation"),
    ("Q11", "Write a paper for OSDI or SOSP.", "systems-paper-writing"),
    ("Q12", "Optimise my prompts automatically instead of hand-tuning them.", "dspy"),
    ("Q13", "Speed up inference by predicting several tokens ahead with draft heads.",
            "speculative-decoding"),
    ("Q14", "Visualise attention hooks and activation caches inside a "
            "transformer.", "transformer-lens-interpretability"),
]


def clause(text, cap=CLAUSE_CAP):
    text = " ".join(str(text).split())
    return text[:cap - 3].rstrip() + "..." if len(text) > cap else text


def entries():
    out = []
    for s in LIB["skills"]:
        out.append((s["name"], clause(s["purpose"]), s["upstream_path"]))
    return out


def stages():
    """{stage: [entry names]} in the file's own order."""
    by_path = {s["upstream_path"]: s["name"] for s in LIB["skills"]}
    out = {}
    for stage, paths in LIB["stages"].items():
        out[stage] = [by_path[p] for p in paths if p in by_path]
    return out


def pick(answers, key):
    a = answers.get(key) if isinstance(answers, dict) else None
    return a.get("choice") if isinstance(a, dict) else None


def call(state, criteria, instructions, key="q"):
    result = tezgah_judge.ask(state, {key: {"type": "choice",
                                            "instructions": instructions,
                                            "criteria": criteria}}, timeout=60)
    return result


def main():
    if not tezgah_judge.available():
        sys.stderr.write("no credential or judge-off is armed\n")
        return 1
    ents = entries()
    flat_criteria = {name: cl for name, cl, _ in ents}
    flat_criteria[NONE_ENTRY] = "no entry in this library covers the request"
    st = stages()
    stage_criteria = {s: "%d entries: %s" % (len(n), ", ".join(n)) for s, n in st.items()}
    stage_criteria[NONE_STAGE] = "no stage covers the request"
    by_name = {name: cl for name, cl, _ in ents}

    for qid, query, label in QUERIES:
        row = {"id": qid, "query": query, "label": label}
        ra = call(query, flat_criteria, FLAT)
        if ra:
            row["flat"] = {"choice": pick(ra["answers"], "q"),
                           "usage": ra["usage"], "latency_ms": ra["latency_ms"],
                           "cost_usd": ra["usage"]["input_tokens"] * 0.042 / 1e6}
        rb1 = call(query, stage_criteria, STAGE)
        chosen_stage = pick(rb1["answers"], "q") if rb1 else None
        row["stage_pick"] = chosen_stage
        row["stage_usage"] = rb1["usage"] if rb1 else None
        if chosen_stage in st:
            sub = {n: by_name[n] for n in st[chosen_stage]}
            sub[NONE_ENTRY] = "no entry in this stage covers the request"
            rb2 = call(query, sub, FLAT)
            row["two_stage"] = {"choice": pick(rb2["answers"], "q") if rb2 else None,
                                "usage": rb2["usage"] if rb2 else None,
                                "latency_ms": rb2["latency_ms"] if rb2 else None}
        else:
            row["two_stage"] = {"choice": chosen_stage, "usage": None, "latency_ms": None}
        row["flat_correct"] = row.get("flat", {}).get("choice") == label
        row["two_stage_correct"] = row["two_stage"]["choice"] == label
        print(json.dumps(row, ensure_ascii=False))
        sys.stdout.flush()
    return 0


if __name__ == "__main__":
    sys.exit(main())
