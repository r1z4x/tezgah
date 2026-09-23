#!/usr/bin/env python3
"""E4 cells: the non-academic channel, and synthesis across sources.

  C1  a non-academic retrieval instruction in the rule or the skill
  C2  literature notes whose source is not a paper record
  C3  a file that compares two or more sources
  C4  findings' ## Patterns bullets naming two or more distinct sources
"""
import glob
import json
import os
import re

REPO = "/Users/rizax/Projects/tezgah"
RESEARCH = os.path.join(REPO, ".tezgah", "research")
FORMAL = ("arxiv.org", "alphaxiv.org", "doi.org", "openalex.org", "acm.org",
          "ieee.org", "sciencedirect.com", "springer", "wiley", "nature.com",
          "usenix.org", "mlr.press", "pmlr", "neurips", "aclanthology.org",
          "pubmed", "biorxiv.org", "medrxiv.org", "jmlr.org", "aaai.org",
          "openreview.net", "philpapers.org", "elifesciences.org")

out = {}

# ---- C1: is a non-academic channel named at all?
CHANNEL = re.compile(r"web ?search|web_search|grey literature|gray literature|"
                     r"blog|forum|white ?paper|release note|issue thread|"
                     r"vendor doc|practitioner report", re.I)
policy = open(os.path.join(REPO, "hooks", "tezgah_policy.py")).read().splitlines()
research_para = "\n".join(policy[378:423])
skill = open(os.path.join(REPO, "skills", "research", "SKILL.md")).read()
out["C1"] = {
    "policy_research_paragraph_hits": CHANNEL.findall(research_para),
    "skill_hits": sorted({m.group(0).lower() for m in CHANNEL.finditer(skill)}),
    "note": "the only live-web mention in the whole contract is consult's --online",
}

# ---- C2: source classes among the notes that exist
notes = sorted(glob.glob(os.path.join(RESEARCH, "*", "literature", "*.md")))
by_line, hosts, grey, formal = {}, [], [], []
for p in notes:
    text = open(p, encoding="utf-8", errors="replace").read()
    host = ""
    for m in re.finditer(r"https?://([^/\s)]+)", text):
        host = m.group(1).lower()
        break
    hosts.append(host)
    line = p.split(os.sep)[-3]
    by_line[line] = by_line.get(line, 0) + 1
    (grey if host and not any(f in host for f in FORMAL) else formal).append(p)
out["C2"] = {"notes": len(notes), "by_line": by_line, "hosts": hosts,
             "grey_or_practice": len(grey), "formal": len(formal),
             "grey_files": [os.path.relpath(p, RESEARCH) for p in grey]}

# ---- C3: a comparison artifact
cands = []
for pat in ("*/*/synthesis.md", "*/literature/INDEX.md", "*/comparison*.md",
            "*/literature/comparison*.md", "*/related-work.md", "*/matrix*.md"):
    cands += glob.glob(os.path.join(RESEARCH, pat))
out["C3"] = {"files": [os.path.relpath(p, RESEARCH) for p in cands]}

# ---- C4: Patterns bullets that name two or more distinct sources
IDTOK = re.compile(r"\b\d{4}\.\d{4,5}\b|\b[A-Z][A-Za-z]+ et al\b|\b[A-Z][a-z]+ [0-9]{4}\b")
per_line = {}
for p in sorted(glob.glob(os.path.join(RESEARCH, "*", "findings.md"))):
    line = p.split(os.sep)[-2]
    text = open(p, encoding="utf-8", errors="replace").read()
    body = text.split("## Patterns", 1)
    if len(body) < 2:
        per_line[line] = {"bullets": 0, "multi_source": 0}
        continue
    body = body[1].split("\n## ", 1)[0]
    bullets = [b for b in body.split("\n- ") if b.strip()]
    multi = [b for b in bullets if len(set(IDTOK.findall(b))) >= 2]
    per_line[line] = {"bullets": len(bullets), "multi_source": len(multi),
                      "tokens": [sorted(set(IDTOK.findall(b))) for b in multi][:3]}
out["C4"] = per_line

print(json.dumps(out, indent=2))
print("\nC2 grey/practice notes: %d of %d" % (out["C2"]["grey_or_practice"], out["C2"]["notes"]))
print("C3 comparison artifacts: %d" % len(out["C3"]["files"]))
print("C4 multi-source patterns: %d of %d bullets"
      % (sum(v["multi_source"] for v in per_line.values()),
         sum(v["bullets"] for v in per_line.values())))
