#!/usr/bin/env python3
"""E4: what the always-on text already carries.

  measure.py [--root .]            the mechanical marker counts
  measure.py [--root .] --judge    the same text through the judge seam

One JSON row per line on stdout, each with `probe`, `source` and `scope`. The
judge rows carry the sealed score type the module returns (`noul` probability)
and the model that answered, because a probability without its model is not a
number a later session can compare.
"""
import argparse
import importlib.machinery
import importlib.util
import json
import os
import re

MARKERS = {
    "prohibitions": r"\b(?:Never|NEVER|FORBIDDEN|BANNED|MUST NOT)\b",
    "provoke-failure": (r"(?i)\b(fail once|goes? red|red-capable|see it fail"
                        r"|must fail|failure first|break it on purpose)\b"),
    "verification": r"(?i)\b(verif\w*|evidence)\b",
    "positive-target": r"(?i)\b(prefer\b|instead of\b|state the target|positive)\b",
}
NON_TRIGGER = r"(?i)(don'?t invoke|do not invoke|not for:|never for|not on code|rather than)"

PROVOKE = ("Does this text instruct the agent to deliberately provoke a failing "
           "check - to make the check fail once on purpose - so that the check is "
           "proved to discriminate before its success is trusted?")
CONTROL_PROHIBITION = ("Does this text carry prohibitions that forbid the reader "
                       "some behaviour (never / do not / banned / forbidden)?")
CONTROL_VERIFICATION = ("Does this text require the reader to verify a claim "
                        "against observed evidence before reporting it?")


def load(name, path):
    loader = importlib.machinery.SourceFileLoader(name, path)
    spec = importlib.util.spec_from_loader(name, loader)
    mod = importlib.util.module_from_spec(spec)
    loader.exec_module(mod)
    return mod


def texts(root):
    policy = load("policy_e4", os.path.join(root, "hooks", "tezgah_policy.py"))
    return policy.CORE + "\n" + policy.CONTRACT, policy


def rows(*objs):
    for obj in objs:
        print(json.dumps(obj, ensure_ascii=False))


def mechanical(root):
    text, policy = texts(root)
    rows({"probe": "mechanism-map", "check": "sizes", "core_bytes": len(policy.CORE),
          "contract_bytes": len(policy.CONTRACT), "combined_bytes": len(text),
          "source": "hooks/tezgah_policy.py CORE + CONTRACT", "scope": "real"})
    for label, rx in MARKERS.items():
        hits = re.findall(rx, text)
        rows({"probe": "mechanism-map", "check": "marker", "marker": label,
              "pattern": rx, "hits": len(hits), "samples": sorted(set(hits))[:6],
              "source": "hooks/tezgah_policy.py CORE + CONTRACT", "scope": "real"})
    setup = load("setup_e4", os.path.join(root, "bin", "tezgah-setup"))
    named, carrying = [], []
    for name in setup.SKILLS:
        desc = setup._frontmatter_description(
            os.path.join(root, "skills", name, "SKILL.md"))
        named.append(name)
        if re.search(NON_TRIGGER, desc):
            carrying.append(name)
    rows({"probe": "mechanism-map", "check": "description-non-trigger",
          "skills": len(named), "carrying": len(carrying), "which": carrying,
          "source": "skills/*/SKILL.md descriptions via the installer's parser",
          "scope": "real"})


def judged(root):
    sys_path = os.path.join(root, "hooks")
    import sys
    sys.path.insert(0, sys_path)
    judge = load("tezgah_judge_e4", os.path.join(sys_path, "tezgah_judge.py"))
    if not judge.available():
        rows({"probe": "mechanism-map", "check": "judge", "available": False,
              "source": "hooks/tezgah_judge.available()", "scope": "real"})
        return
    text, _policy = texts(root)
    result = judge.ask({"contract": text}, {
        "provoke": {"type": "noul", "instructions": PROVOKE},
        "prohibits": {"type": "noul", "instructions": CONTROL_PROHIBITION},
        "verifies": {"type": "noul", "instructions": CONTROL_VERIFICATION},
    }, timeout=60)
    if not result:
        rows({"probe": "mechanism-map", "check": "judge", "answered": False,
              "source": "hooks/tezgah_judge.ask", "scope": "real"})
        return
    usage = result.get("usage") or {}
    rows({"probe": "mechanism-map", "check": "judge", "answered": True,
          "provoke_p": judge.noul(result, "provoke"),
          "prohibits_p": judge.noul(result, "prohibits"),
          "verifies_p": judge.noul(result, "verifies"),
          "questions": {"provoke": PROVOKE, "prohibits": CONTROL_PROHIBITION,
                        "verifies": CONTROL_VERIFICATION},
          "model": result.get("model"), "latency_ms": result.get("latency_ms"),
          "usage": usage, "source": "hooks/tezgah_judge.ask (one batched call)",
          "scope": "real"})


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default=".")
    ap.add_argument("--judge", action="store_true")
    args = ap.parse_args()
    if args.judge:
        judged(args.root)
    else:
        mechanical(args.root)


if __name__ == "__main__":
    main()
