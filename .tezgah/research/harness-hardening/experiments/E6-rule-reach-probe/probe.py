#!/usr/bin/env python3
"""E6 probe: issue the `explorer` and `order` rules their own shape, against the
real gate.

`explorer` (`EXPLORE_DENY`, hooks/tezgah_gate.py:409) and `order` (`ORDER_DENY`,
hooks/tezgah_gate.py:1426) have no deny row in 1613 ledgers over six days. The
report read them as possibly unreachable and then withdrew that. This drives
`hooks/tezgah_gate.decision` in a throwaway HOME and root, issues each shape, and
records the refusal the gate returns - with a control that refuses under the same
environment, so a None is distinguishable from a probe that never reached the
gate.

It bounds reachability for the shapes enumerated here. It proves nothing about
unreachability.
"""
import json
import os
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.realpath(os.path.join(HERE, "..", "..", "..", "..", ".."))
HOOKS = os.path.join(REPO, "hooks")
# The run's own identity, so a row a reader opens can be re-issued and matches
# the protocol committed before it ran.
COMMAND = "python3 %s" % os.path.relpath(os.path.abspath(__file__), REPO)

# The throwaway HOME and root, in the environment before the hooks modules are
# imported: tezgah_paths reads HOME (and XDG_CONFIG_HOME) at import, so the
# ledger this probe writes lives under a temp dir and the user's own state is
# never touched. `_tmp` owns the dir; cleanup removes that path and nothing else.
_tmp = tempfile.TemporaryDirectory(prefix="tezgah-e6-")
HOME = os.path.realpath(_tmp.name)
ROOTS = os.path.join(HOME, "Projects")
CWD = os.path.join(ROOTS, "proj")
OUT = os.path.join(HERE, "results.jsonl")
os.makedirs(CWD, exist_ok=True)
os.environ.update({
    "HOME": HOME,
    "XDG_CONFIG_HOME": os.path.join(HOME, ".config"),
    "TEZGAH_ROOTS": ROOTS,
    # a path that does not exist => cbm_bin()/orx_bin() are None, so no
    # auto-index and no research routing runs off the machine's own installs
    "TEZGAH_CBM_BIN": os.path.join(HOME, "no-such-cbm"),
    "TEZGAH_ORX_BIN": os.path.join(HOME, "no-such-orx"),
})
sys.path.insert(0, HOOKS)

import tezgah_gate as tg          # noqa: E402
import tezgah_integrity as ti     # noqa: E402

EXPERIMENT = "E6-rule-reach-probe"

# rule, case, shape, tool, input, session, seeded checks [(command, failed)], expected refusal
CASES = (
    ("explorer", "subagent-explore",
     "Task with subagent_type=explore", "Task",
     {"subagent_type": "explore"}, "e6-explorer-explore", (), True),
    ("explorer", "subagent-explorer",
     "Task with subagent_type=explorer", "Task",
     {"subagent_type": "explorer"}, "e6-explorer-explorer", (), True),
    ("explorer", "subagent-general-purpose",
     "Task with subagent_type=general-purpose", "Task",
     {"subagent_type": "general-purpose"}, "e6-explorer-negative", (), False),
    ("order", "commit-after-failed-check",
     "Bash git commit -m x, newest check a verify_fail", "Bash",
     {"command": "git commit -m x"}, "e6-order-fail",
     (("pytest -q", True),), True),
    ("order", "commit-after-passed-check",
     "Bash git commit -m x, newest check a verify_ok", "Bash",
     {"command": "git commit -m x"}, "e6-order-pass",
     (("pytest -q", False),), False),
    ("order", "commit-after-no-check",
     "Bash git commit -m x, no check in the session", "Bash",
     {"command": "git commit -m x"}, "e6-order-none", (), False),
    # The control: a commit the `shortcut` rule refuses under the same throwaway
    # gate, in a session whose newest check failed too, so the None the `order`
    # negative cases return is the rule deciding and not a broken probe.
    ("control", "shortcut-on-no-verify",
     "Bash git commit --no-verify -m x, newest check a verify_fail", "Bash",
     {"command": "git commit --no-verify -m x"}, "e6-control-shortcut",
     (("pytest -q", True),), True),
)


def seed(session, command, failed):
    """The row a host PostToolUse hook writes after a check ran, through the real
    writer: `note_tool` classifies `pytest -q` as a check and records the outcome
    `failed` carries, which is the row `_last_verify` folds into fail/ok."""
    ti.note_tool(session, "Bash", {"command": command},
                 failed=failed, out_bytes=12, cwd=CWD)


def ledger_label(session):
    """The rule name on the newest deny row this session has, or None - the text
    before the first colon, which is the label E2's fold counts."""
    denials = [r for r in ti.events(session) if r.get("kind") == "deny"]
    return str(denials[-1].get("detail", "")).split(":", 1)[0] if denials else None


def run_case(rule, case, shape, tool, inp, session, seeds, expect):
    for command, failed in seeds:
        seed(session, command, failed)
    reason = tg.decision(tool, inp, CWD, session)
    return {
        "experiment": EXPERIMENT,
        "rule": rule,
        "case": case,
        "shape": shape,
        "session": session,
        "seeded": ["%s failed=%s" % (c, f) for c, f in seeds],
        "expect_refusal": expect,
        "refused": reason is not None,
        "reason": reason,
        "reason_label": ledger_label(session),
        "source": COMMAND,
        "command": COMMAND,
    }


def main():
    rows = [run_case(*c) for c in CASES]
    unexpected = [r for r in rows if r["refused"] != r["expect_refusal"]]
    rows.append({
        "experiment": EXPERIMENT,
        "totals": True,
        "cases": len(rows),
        "refused": sum(1 for r in rows if r["refused"]),
        "unexpected": len(unexpected),
        "unexpected_cases": [r["case"] for r in unexpected],
        "source": COMMAND,
        "command": COMMAND,
    })
    with open(OUT, "w") as fh:
        for row in rows:
            line = json.dumps(row)
            fh.write(line + "\n")
            print(line)
    print("wrote %d rows to %s" % (len(rows), os.path.relpath(OUT, REPO)), file=sys.stderr)
    return 0


try:
    code = main()
finally:
    # Only the dir mkdtemp made, never a path derived from TMPDIR.
    _tmp.cleanup()
sys.exit(code)
