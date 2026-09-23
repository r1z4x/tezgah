"""The recurring refusal shapes the local ledgers hold, folded.

`failure_shapes()` reads every ledger on this machine - the same corpus walk
`tezgah_integrity.counters_all()` makes, through the same two readers
(`ledgers()` and `events_path()`) - and groups the `deny` rows by the rule label
its writer put before the first colon, which is the label `_counts` already
folds by. A shape is reported only when it recurs in at least
`RECURRING_SESSIONS` distinct sessions: one session's repeated refusal is an
anecdote about that session, and a report that could not tell the two apart
would recommend a change to a shape that met its rule once.

**It is a report, not a gate.** Nothing here refuses a call, no caller reads it
on the hot path, and the CLI that prints it always exits 0. The corpus size it
read is printed with the answer, because an empty report must not read as
"nothing recurs" when the fold read nothing at all.

**The precision proxy is not optional, and raw frequency must never rank this
list.** Every shape carries `fires_per_session` = its fires over the sessions it
fired in, so a count inflated by one long session repeating itself (a value well
above 1.0) is visible beside the count that inflated it. The trap the field
exists for is the highest-firing rule on this machine, `drift`: it fires on long
careful turns whether or not anything is drifting
(`.tezgah/research/harness-hardening/findings.md`, C04/C11 - 181 fires in 143
sessions, and it fired three times while that experiment was written), so a
report ranked by fires would hand its reader the one rule whose count carries
the least signal about a real failure. The ledger stores no ground truth for
whether a refusal was a failure worth fixing - the detail is the reason text and
the row says nothing about what the turn was doing - so `fires_per_session` is a
proxy for how much of a shape's count is repetition, and never a precision
measurement.
"""
from collections import Counter, defaultdict
import re

import tezgah_integrity as ti

# The floor a shape must clear to be reported at all: distinct sessions, not
# rows. Below it, a shape is one session's habit.
RECURRING_SESSIONS = 5

# How many of a shape's most common command shapes come with it.
MAX_COMMANDS = 3

# The one normalization a shape text gets: a digit run is a variant of one
# shape, not a shape of its own (`drift`'s `Long turn (25 work rows...)`,
# `(26 work rows...)` and `(27 ...)` are one shape, three fires).
DIGITS = re.compile(r"\d+")


def _label(detail):
    """The rule label of a deny row's detail: the text before the first colon,
    or `other` when there is none - the derivation `_counts` folds by, so a
    shape's name and a counter's key are the same string."""
    return str(detail or "").split(":", 1)[0].strip() or "other"


def _command(detail):
    """One deny row's command shape: what its writer recorded after the label -
    the refused call's own reason text, already credential-redacted by the one
    append every row goes through (`tezgah_integrity.note_path`), which is why
    no second redactor lives here - with digit runs collapsed and whitespace
    folded, so the variants of one refusal read as one shape."""
    text = str(detail or "")
    tail = text.split(":", 1)[1] if ":" in text else ""
    return DIGITS.sub("N", " ".join(ti.redact(tail).split()))


def _contract(value):
    """A row's contract version as the report names it: `v1`, or `unversioned`
    for a row written before the writer stamped one."""
    return "unversioned" if value is None else "v%s" % value


def failure_shapes():
    """Every shape recurring in at least `RECURRING_SESSIONS` distinct sessions.

    Returns `ledgers` (how many files the fold read), `recurring_sessions` (the
    floor it applied) and `shapes`: one object per shape with `rule`,
    `sessions`, `fires`, `fires_per_session` and up to `MAX_COMMANDS` of its
    most common command shapes, most common first, ties by text so two runs of
    the report agree. Ranked by distinct sessions descending - the
    cross-instance recurrence this exists to find - never by fires, and the
    module docstring says why.

    `row_versions` counts the rows the fold read by the contract that wrote them
    (`unversioned` for a row predating the field): a shape can move because the
    rule changed or because a row's meaning did, and a report that cannot tell
    the two apart would attribute one to the other.

    Bound: none, like `counters_all`, and for the same reason - a window would
    make the report contradict the corpus it claims to be about."""
    files = ti.ledgers()
    sessions = defaultdict(set)
    fires = Counter()
    commands = defaultdict(Counter)
    versions = Counter()
    for path in files:
        for row in ti.events_path(path):
            # A string label, not the raw value: a None key beside int keys makes
            # `json.dumps(..., sort_keys=True)` raise, and the report is printed
            # as JSON by the CLI.
            versions[_contract(row.get("v"))] += 1
            if row.get("kind") != "deny":
                continue
            label = _label(row.get("detail"))
            fires[label] += 1
            sessions[label].add(path)
            commands[label][_command(row.get("detail"))] += 1
    shapes = [{"rule": label, "sessions": len(paths), "fires": fires[label],
               "fires_per_session": round(fires[label] / len(paths), 2),
               "commands": [text for text, _ in sorted(
                   commands[label].items(),
                   key=lambda kv: (-kv[1], kv[0]))[:MAX_COMMANDS]]}
              for label, paths in sessions.items()
              if len(paths) >= RECURRING_SESSIONS]
    shapes.sort(key=lambda s: (-s["sessions"], s["rule"]))
    return {"ledgers": len(files), "recurring_sessions": RECURRING_SESSIONS,
            "shapes": shapes,
            # Which row contracts the fold actually read, for the same reason the
            # ledger count is here: a shape can move because the rule changed or
            # because the row's meaning did, and a reader that cannot tell the two
            # apart would attribute one to the other. None is the pre-version rows.
            "row_versions": dict(versions)}
