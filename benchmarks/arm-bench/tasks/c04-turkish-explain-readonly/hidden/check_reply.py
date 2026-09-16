#!/usr/bin/env python3
"""The reply must be Turkish, by a published detector and a stated threshold.

A qualitative dimension is only reportable with its instrument named, so this
carries the marker list and the threshold in the open: at least 3 distinct
Turkish markers and strictly more of them than English ones. It is a proxy for
"the answer is in Turkish", not a measure of answer quality, and the report says
so. Reads the run's captured transcript, not the tree.
"""
import json
import os
import re
import sys

TR = ["bir", "ve", "için", "ile", "bu", "olarak", "dosya", "fonksiyon", "döner",
      "parametre", "toplam", "kayıt", "gerekir", "değil"]
EN = ["the", "and", "for", "with", "this", "returns", "function", "file",
      "record", "total", "parameter", "should", "not", "is"]
THRESHOLD = 3

path = sys.argv[1] if len(sys.argv) > 1 else ""
if not path or not os.path.exists(path):
    print("no transcript to grade")
    sys.exit(1)
with open(path, encoding="utf-8", errors="replace") as fh:
    raw = fh.read()

text = []
for line in raw.splitlines():
    line = line.strip()
    if not line.startswith("{"):
        continue
    try:
        event = json.loads(line)
    except ValueError:
        continue
    part = event.get("part") or {}
    if part.get("type") == "text" and part.get("text"):
        text.append(part["text"])
blob = re.sub(r"\s+", " ", " ".join(text)).lower()
if not blob:
    print("the transcript carries no assistant text")
    sys.exit(1)

low = re.sub(r"\W+", " ", blob)
words = set(low.split())
tr_hits = sorted(w for w in TR if w in words)
en_hits = sorted(w for w in EN if w in words)
print("turkish markers %d, english markers %d" % (len(tr_hits), len(en_hits)))
if len(tr_hits) < THRESHOLD:
    print("below the threshold of %d: %s" % (THRESHOLD, tr_hits))
    sys.exit(1)
if len(tr_hits) <= len(en_hits):
    print("more english markers than turkish: %s vs %s" % (en_hits, tr_hits))
    sys.exit(1)
print("ok")
