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


_OPS = {"not": "not {0}", "O": "{0} or {self}", "S": "{1} or ({0} and {self})"}


def _source(formula):
    """The monitor of one formula as Python source: one assignment per
    subformula, run once over no row (all atoms false) and then once per row.
    A temporal node reads its own variable before reassigning it, which is its
    value at the previous row - the whole state the monitor keeps."""
    nodes = _nodes(formula, [])
    var = {n: "v%d" % k for k, n in enumerate(nodes)}
    atoms = sorted({n for n in nodes if isinstance(n, str)})

    def body(leaf):
        lines = []
        for n in nodes:
            if isinstance(n, str):
                expr = leaf(n)
            elif n[0] in ("and", "or"):
                expr = "(%s)" % (" %s " % n[0]).join(var[a] for a in n[1:])
            else:
                expr = _OPS[n[0]].format(*(var[a] for a in n[1:]), self=var[n])
            lines.append("%s = %s" % (var[n], expr))
        return lines

    src = ["def monitor(trace):"]
    src += ["    c_%s = trace.col(%r)" % (a, a) for a in atoms]
    src += ["    %s = False" % var[n] for n in nodes]
    src += ["    " + line for line in body(lambda a: "False")]
    src += ["    for i in range(len(trace.rows)):"]
    src += ["        " + line for line in body(lambda a: "c_%s[i]" % a)]
    src += ["    return %s" % var[nodes[-1]]]
    return "\n".join(src)


def compile_table(formulas=None):
    """Per formula, its monitor: a function of a `Trace`, compiled from the
    table at import (and from a mutant's table by the mutation run)."""
    out = {}
    for name, f in (formulas or FORMULAS).items():
        scope = {}
        exec(compile(_source(f), "<stopspec %s>" % name, "exec"), scope)
        out[name] = scope["monitor"]
    return out


_TABLE = compile_table()


class Trace:
    """The atom columns of one trace, each computed once and only when a formula
    the decision list reaches reads it - the way the imperative fold never reads
    a UI write once the newest check has failed. X is read only when the reply
    makes an external claim, as the imperative fold reads it."""

    def __init__(self, rows, external):
        self.rows, self.external, self.cols, self._masked = rows, external, {}, {}

    def masked(self, i):
        if i not in self._masked:
            self._masked[i] = ti.mask(str(self.rows[i].get("detail") or ""))
        return self._masked[i]

    def col(self, name):
        if name not in self.cols:
            self.cols[name] = (self._pb() if name == "Pb"
                               else [self.atom(name, i, r) for i, r in enumerate(self.rows)])
        return self.cols[name]

    def atom(self, name, i, row):
        kind = str(row.get("kind"))
        if name == "Vany":
            return kind in ("verify", "verify_ok", "verify_fail")
        if name == "Vfail":
            return kind == "verify_fail"
        if name == "P":
            return ti.passing_check(row)
        if name == "C":
            return ti._change_row(row)
        if name == "U":
            return bool(ti._ui_write(row))
        if name == "Sp":
            return ((self.col("P")[i] and bool(ti.UI_CHECK.search(self.masked(i))))
                    or ti._screen_read(row)
                    or (bool(ti.UI_TOOL_CMD.search(self.masked(i)))
                        and row.get("exit") in (None, 0) and not row.get("fail_class")))
        if name == "Dc":
            return self.col("U")[i] and bool(ti.DESIGN_COMPONENT.search(self.masked(i)))
        if name == "Dk":
            return self.col("P")[i] and bool(ti.DESIGN_CHECK.search(self.masked(i)))
        if name == "X":
            return (self.external is not None
                    and kind in ("run", "verify", "verify_ok", "verify_fail")
                    and bool(ti.EXTERNAL_READ.search(self.masked(i))))
        if name == "W":
            return kind in ti.WORK_KINDS
        if name == "T":
            return kind == ti.TURN_KIND
        raise KeyError(name)

    def _pb(self):
        """P through escapes E1 (placed at its check's `began` row) and E2 (kept
        only in the newest change's repository)."""
        out, starts, waiting = [False] * len(self.rows), [], {}
        passing = self.col("P")
        for i, row in enumerate(self.rows):
            digest, kind = row.get("id"), row.get("kind")
            if kind == ti.BEGAN_KIND:
                if digest:
                    waiting.setdefault(digest, []).append(i)
                continue
            start = (waiting[digest].pop()
                     if kind in ti.OUTCOME_KINDS and waiting.get(digest) else i)
            if passing[i]:
                starts.append((start, row.get("repo")))
        changes = self.col("C")
        last = max((i for i, c in enumerate(changes) if c), default=-1)
        repo = ti._change_repo(self.rows, last)
        for start, where in starts:
            if ti._same_repo(where, repo):
                out[start] = True
        return out


def verdict(rows, worked, external, table=None):
    """The class `ORDER` picks, or None to allow; a formula is evaluated only
    when the list reaches it."""
    table, trace = table or _TABLE, Trace(rows, external)

    def holds(name):
        return table[name](trace)

    for cls in ("check failed", "partial failure", "no ui_ok"):
        if holds(cls):
            return cls
    unread = external is not None and not holds("read")
    if holds("fresh"):
        if not unread:
            return None
    elif holds("stale"):
        return "stale evidence"
    elif worked or holds("worked"):
        return "no verify_ok"
    return "no external read" if unread else None


def fold(rows, worked, external, where="this turn", table=None):
    """`_evidence_block`'s signature and contract, the class from the spec. The
    text is the class itself: shadow reads only the class (part 10, the switch,
    would carry the imperative texts over)."""
    cls = verdict(rows, worked, external, table)
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
