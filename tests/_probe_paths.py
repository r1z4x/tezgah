#!/usr/bin/env python3
"""Test probe: run tezgah_paths in a controlled environment, print JSON."""
import json
import os
import sys

sys.path.insert(0, os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "hooks"))
import tezgah_paths as tp  # noqa: E402

op = sys.argv[1]
if op == "roots":
    out = tp.roots()
elif op == "root_for":
    out = tp.root_for(sys.argv[2])
elif op == "off":
    out = tp.off(sys.argv[2])
elif op == "default_root":
    out = tp.DEFAULT_ROOT
elif op == "config":
    out = tp.config()
elif op == "off_dirs":
    out = list(tp.OFF_DIRS)
else:
    raise SystemExit("unknown op: %s" % op)
print(json.dumps(out))
