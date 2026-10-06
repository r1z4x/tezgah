#!/usr/bin/env python3
"""The Stop rule's evidence fold as a declared past-time temporal spec (plan 063,
roadmap R16), run in shadow beside the imperative `_evidence_block`.

**What is declared.** `ROW_ATOMS` are the ten row-local predicates the spec reads,
each computed once per row by the readers `tezgah_integrity` already has.
`FORMULAS` are seven past-time LTL formulas over them, evaluated at the last row
of the trace: `("S", a, b)` is "a since b" (b held at some row and a at every row
after it), `("O", a)` is "once a", plus `not`/`and`/`or`. `ORDER` is the
decision list: the first class whose condition holds is the verdict, in the
order the imperative fold returns them.

**What is not a formula, stated so the bounds cannot be gamed.**
- The scope selector is `tezgah_integrity._stop_block`, shared with the
  imperative fold: which rows the fold reads (this turn, the session before this
  turn, the settled-bookkeeping and idle-turn claim fallbacks), the lost-began
  path, and the "evidence tampered" guard (a `ledger_damage` row says the trace
  is not a trace; it is checked before any fold). The spec replaces only the
  fold the selector calls.
- `SCOPE_ATOMS`: the turn marker `T`, which scopes "partial failure" to the
  newest turn of the rows given (`_partial_state`).
- The reply atoms - the external-state claim and the selector's work flag - are
  constants over one trace, passed in, never read off a row.
- `ESCAPES` lists, before any shadow row exists, the predicates that are not
  row-local and count against the "<= 3" bar; `NOT_COUNTED` lists the rest of
  the candidates plan 063 named and why each does not count.

**The monitor** (`fold`) is one in-process pass over the rows at Stop: atoms per
row, then each formula's value from its value at the previous row. Nothing is
persisted between Stops. `shadow` records its verdict beside the imperative one
as a `stop_spec` row and never feeds the verdict; `TEZGAH_STOPSPEC_STRICT` turns a
disagreement into an exception, for the test suite.
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)
import tezgah_integrity as ti  # noqa: E402

STRICT = "TEZGAH_STOPSPEC_STRICT"
ROW_KIND = "stop_spec"

ROW_ATOMS = (
    "Vany",   # a verify-family row: verify, verify_ok, verify_fail (`_last_verify`)
    "Vfail",  # a verify_fail row
    "P",      # a check whose pass was seen (`passing_check`)
    "C",      # a write the freshness fold counts as a change (`_change_row`)
    "U",      # a UI source write (`_ui_write`)
    "Sp",     # a screen proof: a UI check that passed, a screen read (`_ui_evidence`)
    "Dc",     # a component write (`_design_evidence`)
    "Dk",     # a `tezgah-design check` that passed
    "X",      # a read of an external system's own state (`_external_read_row`)
    "W",      # a work row (`WORK_KINDS`)
)
SCOPE_ATOMS = ("T",)  # the turn marker

# `Pb` is P read through escapes E1 and E2 below: the same pass, placed at its
# check's start and kept only in the newest change's repository. Not an atom of
# its own - a pass relocated by two declared non-row-local joins.
FORMULAS = {
    "check failed": ("S", ("not", "Vany"), "Vfail"),
    "partial failure": ("and", ("S", ("not", "T"), "Vfail"),
                        ("not", ("S", ("not", "Vany"), "P"))),
    "no ui_ok": ("or",
                 ("and", ("O", "U"),
                  ("not", ("S", ("not", "U"), ("and", "Sp", ("not", "U"))))),
                 ("and", ("O", "Dc"), ("not", ("S", ("not", "Dc"), "Dk")))),
    "fresh": ("S", ("not", "C"), ("and", ("or", "Pb", "Sp", "X"), ("not", "C"))),
    "stale": ("O", "Pb"),
    "worked": ("O", "W"),
    "read": ("O", "X"),
}

# The decision list. `unread` is the external claim with no read (`read` false).
ORDER = (
    ("check failed", "check failed"),
    ("partial failure", "partial failure"),
    ("no ui_ok", "no ui_ok"),
    ("allow", "fresh and not unread"),
    ("stale evidence", "not fresh and stale"),
    ("no verify_ok", "not fresh and (worked or the selector's work flag)"),
    ("no external read", "unread"),
)

# Pre-registered 2026-10-06, before any shadow row: the non-row-local predicates
# that count against GO 4 (<= 3).
ESCAPES = (
    ("E1 began-join", "Pb sits at the newest earlier `began` row of the pass's id "
                      "(`_last_pass`): an id join across rows"),
    ("E2 repo-bind", "Pb counts only in the repository of the newest change's "
                     "target (`_change_repo`): needs the last C before the fold"),
    ("E3 lost-began", "an unanswered check `began` row against the session's "
                      "delivered set (`unanswered`, `_began_fold`), in the selector"),
)
NOT_COUNTED = (
    ("session fallbacks", "scope selector (plan 063 part 3): `_settled`, "
                          "`_bookkeeping_turn`, `_before_turn`, the idle-turn claim "
                          "fallback choose the rows, the formulas judge them"),
    ("reply atoms", "claims, NEGATED, the external claim and the shape classes are "
                    "constants over one trace, read off the reply, not a row"),
    ("evidence tampered", "a trace-validity guard in the selector, before the fold"),
)
# GO 2's live floor: shadow rows needed before the 99% bar is read. At 400 a
# 99% rate is 4 disagreements, so one more or less moves it by 0.25 pp.
MIN_LIVE_N = 400


def _nodes(formula, out):
    """Every subformula of `formula`, children before parents, each once."""
    if isinstance(formula, tuple):
        for arg in formula[1:]:
            _nodes(arg, out)
    if formula not in out:
        out.append(formula)
    return out


def compile_table(formulas=None):
    """(nodes, program, formulas): the subformulas in evaluation order and, per
    node, its operator and argument indices - so a step is a walk over a list."""
    formulas = formulas or FORMULAS
    nodes = []
    for f in formulas.values():
        _nodes(f, nodes)
    index = {n: i for i, n in enumerate(nodes)}
    program = [(n, ()) if isinstance(n, str) else (n[0], tuple(index[a] for a in n[1:]))
               for n in nodes]
    return nodes, program, {name: index[f] for name, f in formulas.items()}


_TABLE = compile_table()


def _step(program, atoms, prev):
    now = []
    for op, args in program:
        if not args:
            v = atoms.get(op, False)
        elif op == "not":
            v = not now[args[0]]
        elif op == "and":
            v = all(now[a] for a in args)
        elif op == "or":
            v = any(now[a] for a in args)
        elif op == "O":
            v = now[args[0]] or prev[len(now)]
        elif op == "S":
            v = now[args[1]] or (now[args[0]] and prev[len(now)])
        else:
            raise ValueError("unknown operator %r" % op)
        now.append(v)
    return now


def atoms(rows, external):
    """The atom valuation per row, plus Pb (escapes E1, E2). X is read only when
    the reply makes an external claim, as the imperative fold reads it."""
    out, starts, waiting, last_change = [], [], {}, -1
    for i, row in enumerate(rows):
        kind = str(row.get("kind"))
        detail = ti.mask(str(row.get("detail") or ""))
        passing = ti.passing_check(row)
        ui = ti._ui_write(row)
        change = ti._change_row(row)
        ok_exit = row.get("exit") in (None, 0) and not row.get("fail_class")
        if change:
            last_change = i
        a = {"Vany": kind in ("verify", "verify_ok", "verify_fail"),
             "Vfail": kind == "verify_fail", "P": passing, "C": change, "U": bool(ui),
             "Sp": (passing and bool(ti.UI_CHECK.search(detail)))
             or ti._screen_read(row)
             or (bool(ti.UI_TOOL_CMD.search(detail)) and ok_exit),
             "Dc": bool(ui) and bool(ti.DESIGN_COMPONENT.search(detail)),
             "Dk": passing and bool(ti.DESIGN_CHECK.search(detail)),
             "X": external is not None
             and kind in ("run", "verify", "verify_ok", "verify_fail")
             and bool(ti.EXTERNAL_READ.search(detail)),
             "W": kind in ti.WORK_KINDS, "T": kind == ti.TURN_KIND, "Pb": False}
        out.append(a)
        # E1: the pass's position is its check's start
        digest = row.get("id")
        if kind == ti.BEGAN_KIND:
            if digest:
                waiting.setdefault(digest, []).append(i)
            continue
        start = (waiting[digest].pop()
                 if kind in ti.OUTCOME_KINDS and waiting.get(digest) else i)
        if passing:
            starts.append((start, row.get("repo")))
    # E2: bound to the newest change's repository
    repo = ti._change_repo(rows, last_change)
    for start, where in starts:
        if ti._same_repo(where, repo):
            out[start]["Pb"] = True
    return out


def monitor(rows, external, table=None):
    """Each formula's value at the trace's last row: one pass, no stored state.
    The first step reads no row, so an empty trace is the all-false valuation."""
    _, program, names = table or _TABLE
    now = _step(program, {}, [False] * len(program))
    for a in atoms(rows, external):
        now = _step(program, a, now)
    return {name: now[i] for name, i in names.items()}


def verdict(values, worked, external):
    """The class `ORDER` picks from the formula values, or None to allow."""
    unread = external is not None and not values["read"]
    for cls in ("check failed", "partial failure", "no ui_ok"):
        if values[cls]:
            return cls
    if values["fresh"]:
        if not unread:
            return None
    elif values["stale"]:
        return "stale evidence"
    elif worked or values["worked"]:
        return "no verify_ok"
    return "no external read" if unread else None


def fold(rows, worked, external, where="this turn", table=None):
    """`_evidence_block`'s signature and contract, the class from the spec. The
    text is the class itself: shadow reads only the class (part 10, the switch,
    would carry the imperative texts over)."""
    cls = verdict(monitor(rows, external, table), worked, external)
    return (cls, cls)


def judge(text, session_id, rows, cwd, shape, table=None):
    """The spec's verdict class for one Stop: the shared selector with the spec
    as its fold."""
    return ti._stop_block(text, session_id, rows=rows, cwd=cwd, shape=shape,
                          fold=lambda r, w, e, where="this turn":
                          fold(r, w, e, where, table))[0]


def check(imperative, text, session_id, rows, cwd, shape):
    """(spec class, agree) for one Stop; raises under `TEZGAH_STOPSPEC_STRICT`
    when the two disagree."""
    spec = judge(text, session_id, rows, cwd, shape)
    agree = spec == imperative
    if not agree and os.environ.get(STRICT):
        raise AssertionError("stop spec disagrees: imperative %r, spec %r"
                             % (imperative, spec))
    return spec, agree


def shadow(imperative, text, session_id, rows, cwd, shape, key):
    """Record the spec's verdict beside the imperative one as one `stop_spec`
    row per reply per turn. Never returns a verdict: the caller's is final.
    A failure of the spec is recorded as `error: <type>` and re-raised only under
    the strict switch."""
    if any(r.get("kind") == ROW_KIND and r.get("id") == key for r in rows):
        return
    try:
        spec, agree = check(imperative, text, session_id, rows, cwd, shape)
        detail = ("agree: %s" % (imperative or "ok") if agree else
                  "disagree: %s -> %s" % (imperative or "ok", spec or "ok"))
    except Exception as exc:
        if os.environ.get(STRICT):
            raise
        detail = "error: %s" % type(exc).__name__
    ti.note(session_id, ROW_KIND, detail, id=key)
